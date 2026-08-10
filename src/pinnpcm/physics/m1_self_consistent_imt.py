"""Branch-conditioned self-consistent major-loop closure for the M1 operator.

This module is deliberately separate from :mod:`m1_torch_projection` so the
historical prescribed-state operator remains immutable.  The new closure maps
the Qiu source-contract limiting-loop parameters to an increasing effective
conductive-state coordinate and embeds it in the existing conservative M1
electrical/thermal solves.  It is a quasi-static major-branch model, not a
minor-loop, dynamic-state, or metallic-volume-fraction model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import torch

from pinnpcm.physics.m1_torch_projection import (
    M1TorchProjection,
    _as_batch_field,
    _as_batch_scalar,
    _relative_error,
)
from pinnpcm.physics.vo2_constitutive import vo2_sigma


Tensor = torch.Tensor

PRESCRIBED_STATE_MODE = "prescribed_effective_conductive_state_coordinate"
SELF_CONSISTENT_MAJOR_BRANCH_MODE = "self_consistent_major_branch"


@dataclass(frozen=True)
class QiuMajorBranchParameters:
    """Qiu source-contract values and their major-branch mapping.

    ``m_eq`` is the conductive complement of the source-contract limiting
    branch, so its temperature dependence is increasing.  Therefore
    ``wT = 1 / beta`` and the heating/cooling centres are ``Tc +/- loop/2``.
    """

    beta_per_K: float
    hysteresis_width_K: float
    critical_temperature_K: float
    T_c_up_K: float
    T_c_down_K: float
    nominal_transition_width_K: float
    source_contract_schema: str


@dataclass(frozen=True)
class FixedPointComparison:
    finite: bool
    temperature_rise_relative_l2_difference: float
    terminal_current_relative_difference: float
    unique: bool


@dataclass(frozen=True)
class LookaheadDefects:
    fixed_point_defect: float
    sigma_defect: float
    lookahead_temperature_K: Tensor


@dataclass(frozen=True)
class LocalContractionEstimate:
    singular_value_estimate: float
    power_iterations: int
    singular_value_history: tuple[float, ...]
    finite: bool
    method: str = "torch_autograd_jvp_vjp_power_iteration"


def qiu_major_branch_parameters_from_source_contract(
    source_contract: Mapping[str, Any],
) -> QiuMajorBranchParameters:
    """Derive ``Tc_up``, ``Tc_down`` and nominal ``wT`` from Qiu parameters."""

    try:
        values = source_contract["parameters"]
        beta = float(values["beta_per_K"])
        loop_width = float(values["hysteresis_width_K"])
        critical = float(values["critical_temperature_K"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Qiu source contract is missing its limiting-loop parameters") from exc
    scalar_values = torch.as_tensor(
        [beta, loop_width, critical], dtype=torch.float64
    )
    if not bool(torch.isfinite(scalar_values).all()) or beta <= 0.0 or loop_width <= 0.0:
        raise ValueError("Qiu limiting-loop parameters must be finite and positive")
    schema = str(source_contract.get("schema_version", "unversioned_qiu_source_contract"))
    return QiuMajorBranchParameters(
        beta_per_K=beta,
        hysteresis_width_K=loop_width,
        critical_temperature_K=critical,
        T_c_up_K=critical + 0.5 * loop_width,
        T_c_down_K=critical - 0.5 * loop_width,
        nominal_transition_width_K=1.0 / beta,
        source_contract_schema=schema,
    )


def _branch_tensor_for_temperature(branch: Tensor | float, temperature: Tensor) -> Tensor:
    value = torch.as_tensor(branch, dtype=temperature.dtype, device=temperature.device)
    if value.ndim == 1 and temperature.ndim >= 2 and value.numel() == temperature.shape[0]:
        value = value.reshape((value.numel(),) + (1,) * (temperature.ndim - 1))
    if not bool(torch.isfinite(value).all()) or bool(torch.any(torch.abs(value) > 1.0)):
        raise ValueError("major-branch coordinate must be finite and inside [-1, 1]")
    return value


def branch_transition_temperature_K(
    branch: Tensor | float,
    parameters: QiuMajorBranchParameters,
    *,
    like: Tensor | None = None,
) -> Tensor:
    """Return ``0.5*(1+b)*Tc_up + 0.5*(1-b)*Tc_down``."""

    reference = like if like is not None else torch.as_tensor(branch, dtype=torch.float64)
    branch_value = _branch_tensor_for_temperature(branch, reference)
    return (
        0.5 * (1.0 + branch_value) * parameters.T_c_up_K
        + 0.5 * (1.0 - branch_value) * parameters.T_c_down_K
    )


def equilibrium_conductive_state(
    temperature_K: Tensor | float,
    branch: Tensor | float,
    parameters: QiuMajorBranchParameters,
    *,
    phase_width_multiplier: float = 1.0,
) -> Tensor:
    """Return the bounded effective conductive-state coordinate ``m_eq``."""

    temperature = (
        temperature_K
        if isinstance(temperature_K, torch.Tensor)
        else torch.as_tensor(temperature_K, dtype=torch.float64)
    )
    multiplier = float(phase_width_multiplier)
    if not torch.isfinite(torch.as_tensor(multiplier)) or multiplier <= 0.0:
        raise ValueError("phase-width multiplier must be finite and positive")
    threshold = branch_transition_temperature_K(branch, parameters, like=temperature)
    width = parameters.nominal_transition_width_K * multiplier
    return torch.clamp(
        0.5 * (1.0 + torch.tanh((temperature - threshold) / width)),
        min=0.0,
        max=1.0,
    )


class M1SelfConsistentIMTProjection(M1TorchProjection):
    """M1 conservative projection with a branch-conditioned local IMT closure.

    ``raw_projection`` is the undamped M1 target and retains exact historical
    parity in prescribed-state mode at ``lambda_J=1``.  ``projection`` is the
    task-defined relaxed map ``P_alpha=(1-alpha)T+alpha*P_raw(T)``.
    """

    def __init__(
        self,
        *,
        qiu_major_branch_parameters: QiuMajorBranchParameters,
        constitutive_mode: str = SELF_CONSISTENT_MAJOR_BRANCH_MODE,
        phase_width_multiplier: float = 1.0,
        joule_feedback_multiplier: float = 1.0,
        relaxation_alpha: float = 0.35,
        **m1_operator_kwargs: Any,
    ) -> None:
        if constitutive_mode not in {
            PRESCRIBED_STATE_MODE,
            SELF_CONSISTENT_MAJOR_BRANCH_MODE,
        }:
            raise ValueError(f"unsupported M1 constitutive mode: {constitutive_mode}")
        if not 0.0 < float(relaxation_alpha) <= 1.0:
            raise ValueError("relaxation alpha must be inside (0, 1]")
        if not float(phase_width_multiplier) > 0.0:
            raise ValueError("phase-width multiplier must be positive")
        if not 0.0 < float(joule_feedback_multiplier) <= 1.0:
            raise ValueError("Joule-feedback multiplier must be inside (0, 1]")
        super().__init__(**m1_operator_kwargs)
        self.qiu_major_branch_parameters = qiu_major_branch_parameters
        self.constitutive_mode = constitutive_mode
        self.phase_width_multiplier = float(phase_width_multiplier)
        self.joule_feedback_multiplier = float(joule_feedback_multiplier)
        self.relaxation_alpha = float(relaxation_alpha)

    @property
    def transition_width_K(self) -> float:
        return (
            self.qiu_major_branch_parameters.nominal_transition_width_K
            * self.phase_width_multiplier
        )

    def equilibrium_state(self, temperature_K: Tensor, branch: Tensor | float) -> Tensor:
        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        branch_values = _as_batch_scalar(branch, temperature.shape[0], temperature)
        state = equilibrium_conductive_state(
            temperature,
            branch_values,
            self.qiu_major_branch_parameters,
            phase_width_multiplier=self.phase_width_multiplier,
        )
        return state[0] if squeezed else state

    def conductivity(self, temperature_K: Tensor, state_or_branch: Tensor | float) -> Tensor:
        if self.constitutive_mode == PRESCRIBED_STATE_MODE:
            return super().conductivity(temperature_K, state_or_branch)
        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        branch_values = _as_batch_scalar(
            state_or_branch, temperature.shape[0], temperature
        )
        state = equilibrium_conductive_state(
            temperature,
            branch_values,
            self.qiu_major_branch_parameters,
            phase_width_multiplier=self.phase_width_multiplier,
        )
        defect = torch.full_like(temperature, float(self.material_params["c_v_ref"]))
        conductivity = vo2_sigma(
            temperature,
            defect,
            m=state,
            params=self.material_params,
        )
        return conductivity[0] if squeezed else conductivity

    def raw_projection(
        self,
        temperature_K: Tensor,
        voltage_V: Tensor | float,
        state_or_branch: Tensor | float,
        sink_amplitude: Tensor | float,
        *,
        joule_feedback_multiplier: Tensor | float | None = None,
    ) -> dict[str, Tensor]:
        """Evaluate the undamped conservative target with explicit ``lambda_J``."""

        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        multiplier_value = (
            self.joule_feedback_multiplier
            if joule_feedback_multiplier is None
            else joule_feedback_multiplier
        )
        multiplier = _as_batch_scalar(multiplier_value, temperature.shape[0], temperature)
        if not bool(torch.isfinite(multiplier).all()) or bool(
            torch.any((multiplier <= 0.0) | (multiplier > 1.0))
        ):
            raise ValueError("Joule-feedback multiplier must be finite and inside (0, 1]")
        electrical = self.electrical(temperature_K, voltage_V, state_or_branch)
        total_joule = electrical["total_joule_cell_W"]
        if squeezed:
            feedback_joule = total_joule * multiplier[0]
            multiplier_output = multiplier[0]
        else:
            feedback_joule = total_joule * multiplier[:, None, None]
            multiplier_output = multiplier
        thermal = self.thermal(feedback_joule, sink_amplitude)
        result = {**electrical, **thermal}
        result["feedback_joule_cell_W"] = feedback_joule
        result["feedback_joule_W"] = torch.sum(
            feedback_joule.reshape((-1, self.cell_count)), dim=1
        )[0] if squeezed else torch.sum(
            feedback_joule.reshape((-1, self.cell_count)), dim=1
        )
        result["joule_feedback_multiplier"] = multiplier_output
        feedback_ledger = thermal["electrical_heat_sink_ledger_error"]
        result["feedback_heat_sink_ledger_error"] = feedback_ledger
        result["raw_subsolve_feedback_heat_sink_ledger_error"] = feedback_ledger
        result["unscaled_electrical_heat_feedback_sink_ledger_error"] = _relative_error(
            electrical["total_electrical_heat_W"] - thermal["vertical_sink_W"],
            electrical["total_electrical_heat_W"],
            thermal["vertical_sink_W"],
        )
        # Keep the generic heat-to-sink ledger aligned with the heat source
        # actually supplied to the thermal subsolve.  The unscaled electrical
        # comparison above is a separate diagnostic when lambda_J != 1.
        result["electrical_heat_sink_ledger_error"] = feedback_ledger
        if self.constitutive_mode == SELF_CONSISTENT_MAJOR_BRANCH_MODE:
            result["effective_conductive_state_coordinate"] = self.equilibrium_state(
                temperature_K, state_or_branch
            )
        result["linear_solve_count"] = torch.as_tensor(
            2,
            dtype=thermal["temperature_K"].dtype,
            device=thermal["temperature_K"].device,
        )
        return result

    def projection(
        self,
        temperature_K: Tensor,
        voltage_V: Tensor | float,
        state_or_branch: Tensor | float,
        sink_amplitude: Tensor | float,
        *,
        relaxation_alpha: float | None = None,
        joule_feedback_multiplier: Tensor | float | None = None,
    ) -> dict[str, Tensor]:
        """Evaluate the frozen damped map ``P_alpha`` used by A1/A2."""

        alpha = self.relaxation_alpha if relaxation_alpha is None else float(relaxation_alpha)
        if not 0.0 < alpha <= 1.0:
            raise ValueError("relaxation alpha must be inside (0, 1]")
        raw = self.raw_projection(
            temperature_K,
            voltage_V,
            state_or_branch,
            sink_amplitude,
            joule_feedback_multiplier=joule_feedback_multiplier,
        )
        raw_temperature = raw["temperature_K"]
        input_temperature = temperature_K.to(
            dtype=raw_temperature.dtype, device=raw_temperature.device
        )
        result = dict(raw)
        result["raw_temperature_target_K"] = raw_temperature
        result["raw_subsolve_temperature_K"] = raw_temperature
        result["raw_subsolve_terminal_electrical_heat_ledger_error"] = raw[
            "terminal_electrical_heat_ledger_error"
        ]
        result["raw_subsolve_feedback_heat_sink_ledger_error"] = raw[
            "feedback_heat_sink_ledger_error"
        ]
        result["temperature_K"] = (1.0 - alpha) * input_temperature + alpha * raw_temperature
        result["projection_alpha"] = torch.as_tensor(
            alpha, dtype=raw_temperature.dtype, device=raw_temperature.device
        )
        return result

    def damped_projection(self, *args: Any, **kwargs: Any) -> dict[str, Tensor]:
        return self.projection(*args, **kwargs)

    def forward(
        self,
        temperature_K: Tensor,
        voltage_V: Tensor | float,
        state_or_branch: Tensor | float,
        sink_amplitude: Tensor | float,
    ) -> dict[str, Tensor]:
        return self.projection(
            temperature_K, voltage_V, state_or_branch, sink_amplitude
        )


def compare_fixed_points(
    cold_temperature_K: Tensor,
    hot_temperature_K: Tensor,
    cold_terminal_current_A: Tensor | float,
    hot_terminal_current_A: Tensor | float,
    *,
    ambient_temperature_K: float,
    temperature_relative_tolerance: float = 1.0e-4,
    current_relative_tolerance: float = 1.0e-4,
) -> FixedPointComparison:
    """Apply the task's symmetric cold/hot uniqueness comparator."""

    cold = torch.as_tensor(cold_temperature_K, dtype=torch.float64)
    hot = torch.as_tensor(hot_temperature_K, dtype=torch.float64)
    cold_current = torch.as_tensor(cold_terminal_current_A, dtype=torch.float64)
    hot_current = torch.as_tensor(hot_terminal_current_A, dtype=torch.float64)
    finite = bool(
        torch.isfinite(cold).all()
        and torch.isfinite(hot).all()
        and torch.isfinite(cold_current).all()
        and torch.isfinite(hot_current).all()
    )
    denominator_T = torch.clamp(
        torch.maximum(
            torch.linalg.vector_norm(cold - ambient_temperature_K),
            torch.linalg.vector_norm(hot - ambient_temperature_K),
        ),
        min=1.0e-30,
    )
    temperature_difference = float(
        torch.linalg.vector_norm(cold - hot) / denominator_T
    )
    denominator_I = torch.clamp(
        torch.maximum(torch.abs(cold_current), torch.abs(hot_current)), min=1.0e-30
    )
    current_difference = float(torch.abs(cold_current - hot_current) / denominator_I)
    unique = bool(
        finite
        and temperature_difference <= float(temperature_relative_tolerance)
        and current_difference <= float(current_relative_tolerance)
    )
    return FixedPointComparison(
        finite=finite,
        temperature_rise_relative_l2_difference=temperature_difference,
        terminal_current_relative_difference=current_difference,
        unique=unique,
    )


def true_lookahead_defects(
    operator: M1SelfConsistentIMTProjection,
    temperature_K: Tensor,
    voltage_V: Tensor | float,
    branch: Tensor | float,
    sink_amplitude: Tensor | float,
) -> LookaheadDefects:
    """Evaluate one diagnostic ``P_alpha`` look-ahead outside the mode budget."""

    lookahead = operator.projection(
        temperature_K, voltage_V, branch, sink_amplitude
    )["temperature_K"]
    fixed = torch.linalg.vector_norm(lookahead - temperature_K) / torch.clamp(
        torch.linalg.vector_norm(lookahead - operator.ambient_temperature_K),
        min=1.0e-30,
    )
    sigma_now = operator.conductivity(temperature_K, branch)
    sigma_lookahead = operator.conductivity(lookahead, branch)
    sigma = torch.linalg.vector_norm(sigma_lookahead - sigma_now) / torch.clamp(
        torch.linalg.vector_norm(sigma_lookahead), min=1.0e-30
    )
    return LookaheadDefects(
        fixed_point_defect=float(fixed.detach()),
        sigma_defect=float(sigma.detach()),
        lookahead_temperature_K=lookahead,
    )


def estimate_local_damped_map_singular_value(
    operator: M1SelfConsistentIMTProjection,
    fixed_point_temperature_K: Tensor,
    voltage_V: Tensor | float,
    branch: Tensor | float,
    sink_amplitude: Tensor | float,
    *,
    power_iterations: int = 8,
) -> LocalContractionEstimate:
    """Estimate the local largest singular value with deterministic JVP/VJP.

    This is a local diagnostic at the supplied fixed point, not a proof of a
    global contraction.
    """

    if int(power_iterations) <= 0:
        raise ValueError("power_iterations must be positive")
    fixed = fixed_point_temperature_K.detach().clone().to(dtype=torch.float64)
    if fixed.shape != (operator.ny, operator.nx) or not bool(torch.isfinite(fixed).all()):
        raise ValueError("contraction estimate requires one finite grid-shaped field")

    def map_temperature(value: Tensor) -> Tensor:
        return operator.projection(value, voltage_V, branch, sink_amplitude)[
            "temperature_K"
        ]

    index = torch.arange(fixed.numel(), dtype=fixed.dtype, device=fixed.device)
    direction = (
        torch.sin((index + 1.0) * 0.7548776662466927)
        + torch.cos((index + 1.0) * 0.5698402909980532)
    ).reshape_as(fixed)
    direction = direction / torch.linalg.vector_norm(direction)
    history: list[float] = []
    finite = True
    for _ in range(int(power_iterations)):
        _, jvp = torch.autograd.functional.jvp(
            map_temperature,
            fixed,
            direction,
            create_graph=False,
            strict=False,
        )
        singular_value = torch.linalg.vector_norm(jvp)
        _, normal_direction = torch.autograd.functional.vjp(
            map_temperature,
            fixed,
            v=jvp,
            create_graph=False,
            strict=False,
        )
        normal_norm = torch.linalg.vector_norm(normal_direction)
        step_finite = bool(
            torch.isfinite(singular_value)
            and torch.isfinite(normal_direction).all()
            and torch.isfinite(normal_norm)
        )
        finite = finite and step_finite
        history.append(float(singular_value.detach()))
        if not step_finite:
            break
        if float(normal_norm.detach()) <= 1.0e-30:
            direction = torch.zeros_like(direction)
        else:
            direction = normal_direction / normal_norm
    estimate = history[-1] if history else float("nan")
    return LocalContractionEstimate(
        singular_value_estimate=estimate,
        power_iterations=len(history),
        singular_value_history=tuple(history),
        finite=bool(finite and len(history) == int(power_iterations)),
    )


def empirical_contraction_ratio(
    operator: M1SelfConsistentIMTProjection,
    fixed_point_temperature_K: Tensor,
    perturbation_K: Tensor,
    voltage_V: Tensor | float,
    branch: Tensor | float,
    sink_amplitude: Tensor | float,
) -> float:
    """Return the deterministic finite-perturbation map ratio."""

    perturbation = perturbation_K.to(
        dtype=fixed_point_temperature_K.dtype,
        device=fixed_point_temperature_K.device,
    )
    denominator = torch.linalg.vector_norm(perturbation)
    if float(denominator) <= 0.0:
        raise ValueError("empirical contraction perturbation must be non-zero")
    baseline = operator.projection(
        fixed_point_temperature_K, voltage_V, branch, sink_amplitude
    )["temperature_K"]
    perturbed = operator.projection(
        fixed_point_temperature_K + perturbation,
        voltage_V,
        branch,
        sink_amplitude,
    )["temperature_K"]
    return float(torch.linalg.vector_norm(perturbed - baseline) / denominator)
