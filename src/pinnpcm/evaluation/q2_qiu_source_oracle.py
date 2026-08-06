"""Independent Qiu S1--S7 source audit and zero-dimensional oracle.

This module is intentionally independent of the BranchConserve two-dimensional
production implementation.  It evaluates the published lumped equations as a
source oracle, enumerates all steady fixed points, certifies their local
linear stability, and applies a narrowly defined quasistatic reachability
test.  Its results can authorize a later L1 pilot; they cannot validate a 2-D
closure or a PINN.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml
from scipy import optimize


TERMINAL_DISPOSITIONS = {
    "A_GO_12K_DUAL_BRANCH_L1",
    "A_GO_DESIGNED_LOAD_L1",
    "A_PIVOT_FORWARD_ONLY",
    "A_STOP_STEADY_ROUTE",
    "A_INVALID_SOURCE_AUDIT",
}


class SourceAuditError(RuntimeError):
    """Fail-closed source, formula, or numerical-resolution error."""


@dataclass(frozen=True)
class OracleParameters:
    resistance_prefactor_ohm: float
    metallic_resistance_ohm: float
    activation_temperature_K: float
    beta_per_K: float
    loop_width_K: float
    critical_temperature_K: float
    dynamic_metallic_factor: float
    parallel_capacitance_F: float
    thermal_conductance_W_K: float
    thermal_capacitance_J_K: float
    ambient_temperature_K: float

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "OracleParameters":
        values = config["source_parameters"]
        result = cls(
            resistance_prefactor_ohm=float(values["resistance_prefactor_ohm"]),
            metallic_resistance_ohm=float(values["metallic_resistance_ohm"]),
            activation_temperature_K=float(values["activation_temperature_K"]),
            beta_per_K=float(values["beta_per_K"]),
            loop_width_K=float(values["loop_width_K"]),
            critical_temperature_K=float(values["critical_temperature_K"]),
            dynamic_metallic_factor=float(values["dynamic_metallic_factor"]),
            parallel_capacitance_F=float(values["parallel_capacitance_F"]),
            thermal_conductance_W_K=float(
                values["thermal_conductance_W_K"]
            ),
            thermal_capacitance_J_K=float(values["thermal_capacitance_J_K"]),
            ambient_temperature_K=float(values["ambient_temperature_K"]),
        )
        for name, value in asdict(result).items():
            if not math.isfinite(value) or value <= 0.0:
                raise SourceAuditError(f"{name} must be finite and positive")
        return result

    @property
    def thermal_time_constant_s(self) -> float:
        return self.thermal_capacitance_J_K / self.thermal_conductance_W_K


@dataclass(frozen=True)
class StabilityCertificate:
    analytic_fd_relative_frobenius: float
    eigenpair_relative_residual_max: float
    spectral_abscissa_per_s: float
    alpha_tau_dimensionless: float
    robust_stability_margin: float
    classification: str


@dataclass(frozen=True)
class FixedPoint:
    source_voltage_V: float
    load_resistance_ohm: float
    branch: str
    delta: int
    resistance_variant: str
    metallic_multiplier: float
    temperature_K: float
    device_voltage_V: float
    current_A: float
    resistance_ohm: float
    insulating_fraction: float
    conductive_state: float
    current_residual: float
    thermal_residual: float
    stability: StabilityCertificate

    def to_row(self, *, scope: str, root_index: int) -> dict[str, Any]:
        return {
            "scope": scope,
            "root_index": root_index,
            "source_voltage_V": self.source_voltage_V,
            "load_resistance_ohm": self.load_resistance_ohm,
            "branch": self.branch,
            "delta": self.delta,
            "resistance_variant": self.resistance_variant,
            "metallic_multiplier": self.metallic_multiplier,
            "temperature_K": self.temperature_K,
            "device_voltage_V": self.device_voltage_V,
            "current_A": self.current_A,
            "resistance_ohm": self.resistance_ohm,
            "insulating_fraction": self.insulating_fraction,
            "conductive_state": self.conductive_state,
            "current_residual": self.current_residual,
            "thermal_residual": self.thermal_residual,
            "analytic_fd_relative_frobenius": (
                self.stability.analytic_fd_relative_frobenius
            ),
            "eigenpair_relative_residual_max": (
                self.stability.eigenpair_relative_residual_max
            ),
            "spectral_abscissa_per_s": self.stability.spectral_abscissa_per_s,
            "alpha_tau_dimensionless": self.stability.alpha_tau_dimensionless,
            "robust_stability_margin": self.stability.robust_stability_margin,
            "stability_classification": self.stability.classification,
        }


@dataclass(frozen=True)
class RootDiscovery:
    fixed_points: tuple[FixedPoint, ...]
    stationary_temperatures_K: tuple[float, ...]
    coarse_root_temperatures_K: tuple[float, ...]
    fine_root_temperatures_K: tuple[float, ...]
    root_set_hausdorff_K: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_builtin(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.ndarray):
        return [_canonical_builtin(item) for item in value.tolist()]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite JSON value")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            _canonical_builtin(dict(payload)),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_canonical_builtin(dict(row)))
    temporary.replace(path)


def load_stage_a_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload["schema_version"] != (
        "q2_qiu_source_consistent_branchconserve_v2_stage_a_v1"
    ):
        raise SourceAuditError("unexpected Stage A schema")
    if set(payload["terminal_dispositions"]) != TERMINAL_DISPOSITIONS:
        raise SourceAuditError("terminal disposition vocabulary drifted")
    if bool(payload["scientific_vote"]):
        raise SourceAuditError("Stage A must remain non-voting")
    if int(payload["formal_execution_count"]) != 0:
        raise SourceAuditError("Stage A cannot consume a formal execution")
    return payload


def insulating_fraction(
    temperature_K: float | np.ndarray,
    delta: int,
    params: OracleParameters,
) -> float | np.ndarray:
    if delta not in (-1, 1):
        raise ValueError("delta must be +1 for heating or -1 for cooling")
    temperature = np.asarray(temperature_K, dtype=float)
    if not np.isfinite(temperature).all() or np.any(temperature <= 0.0):
        raise ValueError("temperature must be finite and positive")
    argument = params.beta_per_K * (
        params.critical_temperature_K
        + delta * params.loop_width_K / 2.0
        - temperature
    )
    result = 0.5 * (1.0 + np.tanh(argument))
    return float(result) if result.ndim == 0 else result


def resistance_and_derivative(
    temperature_K: float | np.ndarray,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    temperature = np.asarray(temperature_K, dtype=float)
    fraction = np.asarray(insulating_fraction(temperature, delta, params))
    argument = params.beta_per_K * (
        params.critical_temperature_K
        + delta * params.loop_width_K / 2.0
        - temperature
    )
    fraction_derivative = -0.5 * params.beta_per_K / np.cosh(argument) ** 2
    activated = params.resistance_prefactor_ohm * np.exp(
        params.activation_temperature_K / temperature
    )
    activated_derivative = (
        -params.activation_temperature_K / temperature**2 * activated
    )
    resistance = (
        activated * fraction
        + metallic_multiplier * params.metallic_resistance_ohm
    )
    derivative = activated_derivative * fraction + activated * fraction_derivative
    if not np.isfinite(resistance).all() or np.any(resistance <= 0.0):
        raise ValueError("source resistance became nonfinite or nonpositive")
    if not np.isfinite(derivative).all():
        raise ValueError("source resistance derivative became nonfinite")
    if resistance.ndim == 0:
        return float(resistance), float(derivative)
    return resistance, derivative


def _power_scale(source_voltage_V: float, load_resistance_ohm: float, params: OracleParameters) -> float:
    return max(
        source_voltage_V**2 / (4.0 * load_resistance_ohm),
        params.thermal_conductance_W_K * 1.0,
        1.0e-12,
    )


def thermal_balance(
    temperature_K: float | np.ndarray,
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
) -> float | np.ndarray:
    resistance, _ = resistance_and_derivative(
        temperature_K, delta, metallic_multiplier, params
    )
    temperature = np.asarray(temperature_K, dtype=float)
    resistance_array = np.asarray(resistance, dtype=float)
    value = (
        source_voltage_V**2
        * resistance_array
        / (load_resistance_ohm + resistance_array) ** 2
        - params.thermal_conductance_W_K
        * (temperature - params.ambient_temperature_K)
    )
    return float(value) if value.ndim == 0 else value


def thermal_balance_derivative(
    temperature_K: float | np.ndarray,
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
) -> float | np.ndarray:
    resistance, derivative = resistance_and_derivative(
        temperature_K, delta, metallic_multiplier, params
    )
    resistance_array = np.asarray(resistance, dtype=float)
    derivative_array = np.asarray(derivative, dtype=float)
    value = (
        source_voltage_V**2
        * derivative_array
        * (load_resistance_ohm - resistance_array)
        / (load_resistance_ohm + resistance_array) ** 3
        - params.thermal_conductance_W_K
    )
    return float(value) if value.ndim == 0 else value


def compact_rhs(
    state: np.ndarray,
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
) -> np.ndarray:
    device_voltage_V, temperature_K = map(float, np.asarray(state, dtype=float))
    resistance, _ = resistance_and_derivative(
        temperature_K, delta, metallic_multiplier, params
    )
    return np.asarray(
        [
            (
                (source_voltage_V - device_voltage_V) / load_resistance_ohm
                - device_voltage_V / resistance
            )
            / params.parallel_capacitance_F,
            (
                device_voltage_V**2 / resistance
                - params.thermal_conductance_W_K
                * (temperature_K - params.ambient_temperature_K)
            )
            / params.thermal_capacitance_J_K,
        ],
        dtype=float,
    )


def analytic_jacobian(
    state: np.ndarray,
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
) -> np.ndarray:
    device_voltage_V, temperature_K = map(float, np.asarray(state, dtype=float))
    resistance, resistance_derivative = resistance_and_derivative(
        temperature_K, delta, metallic_multiplier, params
    )
    return np.asarray(
        [
            [
                -(
                    1.0 / load_resistance_ohm + 1.0 / resistance
                )
                / params.parallel_capacitance_F,
                device_voltage_V
                * resistance_derivative
                / (params.parallel_capacitance_F * resistance**2),
            ],
            [
                2.0
                * device_voltage_V
                / (params.thermal_capacitance_J_K * resistance),
                (
                    -device_voltage_V**2
                    * resistance_derivative
                    / resistance**2
                    - params.thermal_conductance_W_K
                )
                / params.thermal_capacitance_J_K,
            ],
        ],
        dtype=float,
    )


def finite_difference_jacobian(
    state: np.ndarray,
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
) -> np.ndarray:
    values = np.asarray(state, dtype=float)
    result = np.empty((2, 2), dtype=float)
    step_factor = np.finfo(float).eps ** (1.0 / 3.0)
    for column in range(2):
        step = step_factor * max(1.0, abs(float(values[column])))
        plus = values.copy()
        minus = values.copy()
        plus[column] += step
        minus[column] -= step
        result[:, column] = (
            compact_rhs(
                plus,
                source_voltage_V=source_voltage_V,
                load_resistance_ohm=load_resistance_ohm,
                delta=delta,
                metallic_multiplier=metallic_multiplier,
                params=params,
            )
            - compact_rhs(
                minus,
                source_voltage_V=source_voltage_V,
                load_resistance_ohm=load_resistance_ohm,
                delta=delta,
                metallic_multiplier=metallic_multiplier,
                params=params,
            )
        ) / (2.0 * step)
    return result


def certify_stability(
    state: np.ndarray,
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> StabilityCertificate:
    analytic = analytic_jacobian(
        state,
        source_voltage_V=source_voltage_V,
        load_resistance_ohm=load_resistance_ohm,
        delta=delta,
        metallic_multiplier=metallic_multiplier,
        params=params,
    )
    finite_difference = finite_difference_jacobian(
        state,
        source_voltage_V=source_voltage_V,
        load_resistance_ohm=load_resistance_ohm,
        delta=delta,
        metallic_multiplier=metallic_multiplier,
        params=params,
    )
    denominator = max(float(np.linalg.norm(analytic, ord="fro")), np.finfo(float).tiny)
    relative_difference = float(
        np.linalg.norm(analytic - finite_difference, ord="fro") / denominator
    )
    values, vectors = np.linalg.eig(analytic)
    analytic_norm = max(float(np.linalg.norm(analytic, ord=2)), np.finfo(float).tiny)
    residuals = []
    for index, eigenvalue in enumerate(values):
        vector = vectors[:, index]
        residuals.append(
            float(
                np.linalg.norm(analytic @ vector - eigenvalue * vector)
                / (analytic_norm * np.linalg.norm(vector))
            )
        )
    residual_max = max(residuals)
    thresholds = config["stability"]
    if relative_difference > float(
        thresholds["analytic_fd_relative_frobenius_max"]
    ):
        raise SourceAuditError(
            "analytic and finite-difference Jacobians exceed the frozen gate"
        )
    if residual_max > float(thresholds["eigenpair_relative_residual_max"]):
        raise SourceAuditError("eigenpair numerical residual exceeds the frozen gate")
    spectral_abscissa = float(np.max(np.real(values)))
    alpha_tau = spectral_abscissa * params.thermal_time_constant_s
    stable_max = float(thresholds["stable_alpha_tau_max"])
    marginal_abs = float(thresholds["marginal_alpha_tau_abs_max"])
    if alpha_tau <= stable_max:
        classification = "stable"
    elif abs(alpha_tau) < marginal_abs:
        classification = "marginal"
    else:
        classification = "unstable"
    return StabilityCertificate(
        analytic_fd_relative_frobenius=relative_difference,
        eigenpair_relative_residual_max=residual_max,
        spectral_abscissa_per_s=spectral_abscissa,
        alpha_tau_dimensionless=alpha_tau,
        robust_stability_margin=-alpha_tau,
        classification=classification,
    )


def _deduplicate(values: Iterable[float], tolerance: float = 1.0e-10) -> list[float]:
    result: list[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def _bracketed_roots(
    function: Any,
    lower: float,
    upper: float,
    partition_count: int,
    *,
    scaled_tolerance: float,
    scale: float,
) -> list[float]:
    if upper < lower:
        raise ValueError("root interval is reversed")
    if upper == lower:
        value = float(function(lower))
        return [lower] if abs(value) / scale <= scaled_tolerance else []
    grid = np.linspace(lower, upper, partition_count, dtype=float)
    values = np.asarray(function(grid), dtype=float)
    if not np.isfinite(values).all():
        raise SourceAuditError("nonfinite value in nested root partition")
    roots: list[float] = []
    for index in range(partition_count - 1):
        left = float(grid[index])
        right = float(grid[index + 1])
        f_left = float(values[index])
        f_right = float(values[index + 1])
        if abs(f_left) / scale <= scaled_tolerance:
            roots.append(left)
        if f_left * f_right < 0.0:
            roots.append(
                float(
                    optimize.brentq(
                        function,
                        left,
                        right,
                        xtol=5.0e-14,
                        rtol=4.0 * np.finfo(float).eps,
                        maxiter=200,
                    )
                )
            )
    if abs(float(values[-1])) / scale <= scaled_tolerance:
        roots.append(float(grid[-1]))
    return _deduplicate(roots)


def _hausdorff(left: Sequence[float], right: Sequence[float]) -> float:
    if not left and not right:
        return 0.0
    if not left or not right:
        return math.inf
    return max(
        max(min(abs(a - b) for b in right) for a in left),
        max(min(abs(b - a) for a in left) for b in right),
    )


def _discover_temperatures(
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    delta: int,
    metallic_multiplier: float,
    params: OracleParameters,
    config: Mapping[str, Any],
    partition_count: int,
) -> tuple[list[float], list[float]]:
    lower = params.ambient_temperature_K
    upper = lower + source_voltage_V**2 / (
        4.0 * load_resistance_ohm * params.thermal_conductance_W_K
    )
    power_scale = _power_scale(source_voltage_V, load_resistance_ohm, params)

    def balance(temperature: float | np.ndarray) -> float | np.ndarray:
        return thermal_balance(
            temperature,
            source_voltage_V=source_voltage_V,
            load_resistance_ohm=load_resistance_ohm,
            delta=delta,
            metallic_multiplier=metallic_multiplier,
            params=params,
        )

    def derivative(temperature: float | np.ndarray) -> float | np.ndarray:
        return thermal_balance_derivative(
            temperature,
            source_voltage_V=source_voltage_V,
            load_resistance_ohm=load_resistance_ohm,
            delta=delta,
            metallic_multiplier=metallic_multiplier,
            params=params,
        )

    root_cfg = config["root_discovery"]
    roots = _bracketed_roots(
        balance,
        lower,
        upper,
        partition_count,
        scaled_tolerance=float(root_cfg["equilibrium_residual_max"]),
        scale=power_scale,
    )
    derivative_scale = max(params.thermal_conductance_W_K, 1.0e-12)
    stationary = _bracketed_roots(
        derivative,
        lower,
        upper,
        partition_count,
        scaled_tolerance=1.0e-11,
        scale=derivative_scale,
    )
    tangent_tolerance = float(root_cfg["tangent_candidate_scaled_residual_max"])
    for candidate in stationary:
        if abs(float(balance(candidate))) / power_scale <= tangent_tolerance:
            roots.append(candidate)
    return _deduplicate(roots), _deduplicate(stationary)


def discover_fixed_points(
    *,
    source_voltage_V: float,
    load_resistance_ohm: float,
    branch: str,
    resistance_variant: str,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> RootDiscovery:
    branch_cfg = config["branch_contract"][branch]
    delta = int(branch_cfg["delta"])
    metallic_multiplier = float(
        config["resistance_variants"][resistance_variant]["metallic_multiplier"]
    )
    coarse_count, fine_count = map(
        int, config["root_discovery"]["nested_partition_counts"]
    )
    coarse_roots, coarse_stationary = _discover_temperatures(
        source_voltage_V=source_voltage_V,
        load_resistance_ohm=load_resistance_ohm,
        delta=delta,
        metallic_multiplier=metallic_multiplier,
        params=params,
        config=config,
        partition_count=coarse_count,
    )
    fine_roots, fine_stationary = _discover_temperatures(
        source_voltage_V=source_voltage_V,
        load_resistance_ohm=load_resistance_ohm,
        delta=delta,
        metallic_multiplier=metallic_multiplier,
        params=params,
        config=config,
        partition_count=fine_count,
    )
    hausdorff = _hausdorff(coarse_roots, fine_roots)
    root_cfg = config["root_discovery"]
    if len(coarse_roots) != len(fine_roots) or hausdorff > float(
        root_cfg["root_set_temperature_hausdorff_max_K"]
    ):
        raise SourceAuditError(
            "nested root partitions disagree; the fixed-point set is unresolved"
        )
    stationary_hausdorff = _hausdorff(coarse_stationary, fine_stationary)
    if len(coarse_stationary) != len(fine_stationary) or stationary_hausdorff > float(
        root_cfg["root_set_temperature_hausdorff_max_K"]
    ):
        raise SourceAuditError(
            "nested root partitions disagree on stationary points"
        )
    fixed_points: list[FixedPoint] = []
    residual_max = float(root_cfg["equilibrium_residual_max"])
    for temperature_K in fine_roots:
        resistance, _ = resistance_and_derivative(
            temperature_K, delta, metallic_multiplier, params
        )
        device_voltage_V = (
            source_voltage_V
            * resistance
            / (load_resistance_ohm + resistance)
        )
        current_A = source_voltage_V / (load_resistance_ohm + resistance)
        current_scale = max(
            source_voltage_V / load_resistance_ohm,
            float(root_cfg["current_floor_A"]),
        )
        power_scale = _power_scale(source_voltage_V, load_resistance_ohm, params)
        current_residual = abs(
            (source_voltage_V - device_voltage_V) / load_resistance_ohm
            - device_voltage_V / resistance
        ) / current_scale
        thermal_residual = abs(
            device_voltage_V**2 / resistance
            - params.thermal_conductance_W_K
            * (temperature_K - params.ambient_temperature_K)
        ) / power_scale
        if max(current_residual, thermal_residual) > residual_max:
            raise SourceAuditError("a reported fixed point failed equilibrium certification")
        fraction = float(insulating_fraction(temperature_K, delta, params))
        state = np.asarray([device_voltage_V, temperature_K], dtype=float)
        certificate = certify_stability(
            state,
            source_voltage_V=source_voltage_V,
            load_resistance_ohm=load_resistance_ohm,
            delta=delta,
            metallic_multiplier=metallic_multiplier,
            params=params,
            config=config,
        )
        fixed_points.append(
            FixedPoint(
                source_voltage_V=source_voltage_V,
                load_resistance_ohm=load_resistance_ohm,
                branch=branch,
                delta=delta,
                resistance_variant=resistance_variant,
                metallic_multiplier=metallic_multiplier,
                temperature_K=temperature_K,
                device_voltage_V=device_voltage_V,
                current_A=current_A,
                resistance_ohm=resistance,
                insulating_fraction=fraction,
                conductive_state=1.0 - fraction,
                current_residual=current_residual,
                thermal_residual=thermal_residual,
                stability=certificate,
            )
        )
    return RootDiscovery(
        fixed_points=tuple(fixed_points),
        stationary_temperatures_K=tuple(fine_stationary),
        coarse_root_temperatures_K=tuple(coarse_roots),
        fine_root_temperatures_K=tuple(fine_roots),
        root_set_hausdorff_K=hausdorff,
    )


def build_source_to_code_discrepancy_rows() -> list[dict[str, str]]:
    return [
        {
            "source_equation": "S1",
            "physical_role": "quasistatic device major/minor-loop resistance",
            "parameter_and_unit": "R0 [ohm], Ea [K], Rm [ohm], F dimensionless",
            "present_repository_mapping": "qiu_author_compact_model.quasistatic_resistance_ohm is source-consistent; v1 2-D kernel is not S1",
            "inconsistency": "v1 mixes conductivity endmembers logarithmically instead of preserving additive device resistance",
            "proposed_v2_mapping": "S1 is the only later production-voting uniform-limit source oracle",
            "allowed_claim": "source-model-scale-anchored device-effective conductivity after a passed uniform-limit gate",
            "forbidden_claim": "intrinsic local VO2 conductivity or contact-resolved calibration",
        },
        {
            "source_equation": "S2 major-loop limit",
            "physical_role": "insulating fraction F_b(T), with T_pr=0 before reversal",
            "parameter_and_unit": "beta=0.253 K^-1, w=7.193 K, Tc=332.8 K, delta=+1/-1",
            "present_repository_mapping": "qiu_author_compact_model.major_branch_insulating_fraction is source-consistent",
            "inconsistency": "v1 expit uses w=7.193 K as sigmoid scale; source steepness is controlled by beta",
            "proposed_v2_mapping": "F_b=0.5[1+tanh(beta(Tc+delta*w/2-T))], s_b=1-F_b",
            "allowed_claim": "Qiu-source-consistent quasistatic major-branch shape",
            "forbidden_claim": "measured local metallic volume fraction",
        },
        {
            "source_equation": "S3",
            "physical_role": "reversal proximity temperature for minor loops",
            "parameter_and_unit": "T_pr [K], reversal temperature T_r [K]",
            "present_repository_mapping": "implemented in qiu_author_compact_model; inactive in the Stage A major-loop limit",
            "inconsistency": "none for source module; v1 equilibrium sigmoid omits this source meaning",
            "proposed_v2_mapping": "do not activate minor-loop dynamics in the steady major-branch production closure",
            "allowed_claim": "major-loop limit corresponds to no reversal and inactive T_pr",
            "forbidden_claim": "full Preisach or measured minor-loop dynamics",
        },
        {
            "source_equation": "S4",
            "physical_role": "empirical proximity function for minor loops",
            "parameter_and_unit": "gamma=0.956 dimensionless",
            "present_repository_mapping": "implemented in qiu_author_compact_model; unused by Stage A major branches",
            "inconsistency": "not a license to add branch-switching dynamics to the steady oracle",
            "proposed_v2_mapping": "retain as source provenance only for this task",
            "allowed_claim": "S1-S4 source mapping is explicit",
            "forbidden_claim": "validated local history dynamics",
        },
        {
            "source_equation": "S5",
            "physical_role": "device-voltage RC dynamics",
            "parameter_and_unit": "C=145 pF, Rload [ohm], Vin/Vd [V]",
            "present_repository_mapping": "qiu_author_compact_model.compact_rhs uses S7 resistance",
            "inconsistency": "S5 alone does not select S1 versus S7 resistance semantics",
            "proposed_v2_mapping": "independent 0-D oracle evaluates both variants and reports them separately",
            "allowed_claim": "source-lumped circuit stability scale",
            "forbidden_claim": "2-D electrical validation",
        },
        {
            "source_equation": "S6",
            "physical_role": "uniform-temperature device thermal dynamics",
            "parameter_and_unit": "Sth=0.206 mW/K, Cth=49.6 pJ/K",
            "present_repository_mapping": "qiu_author_compact_model.compact_rhs implements the lumped equation",
            "inconsistency": "source explicitly says fitted terms include VO2, electrodes, and substrate",
            "proposed_v2_mapping": "use only as 0-D uniform-limit oracle and local-stability time scale",
            "allowed_claim": "device-effective lumped thermal scale",
            "forbidden_claim": "local 2-D material conductance or heat capacity",
        },
        {
            "source_equation": "S7",
            "physical_role": "dynamic thin-filament effective resistance",
            "parameter_and_unit": "k=4.90 dimensionless multiplying Rm",
            "present_repository_mapping": "qiu_author_compact_model.dynamic_resistance_ohm is source-consistent",
            "inconsistency": "k is not intrinsic metallic resistance or a distributable local phase fraction",
            "proposed_v2_mapping": "diagnostic comparator only; never the automatic 2-D production closure",
            "allowed_claim": "source-reported dynamic-filament comparator",
            "forbidden_claim": "intrinsic/local S7 material law",
        },
        {
            "source_equation": "Qiu main Fig. 2",
            "physical_role": "9/12.5/15.8 V qualitative source-voltage regimes",
            "parameter_and_unit": "Vs [V], Rload=12 kOhm, T0=325 K",
            "present_repository_mapping": "source contract v3 correctly labels the three qualitative regimes",
            "inconsistency": "an algebraic fixed point at 12.5 V cannot negate the reported oscillatory regime",
            "proposed_v2_mapping": "12.5 V remains diagnostic-only and excluded from steady GT voting",
            "allowed_claim": "qualitative regime context",
            "forbidden_claim": "quantitative Qiu reproduction",
        },
        {
            "source_equation": "v1 2-D effective closure",
            "physical_role": "repository production conductivity and equilibrium coordinate",
            "parameter_and_unit": "expit scale=7.193 K; log-conductivity mixture",
            "present_repository_mapping": "vo2_effective_conductivity.EffectiveVO2Closure",
            "inconsistency": "neither source beta steepness nor S1 additive resistance is preserved",
            "proposed_v2_mapping": "replace only in a new Stage B identity after Stage A selects S1 and a valid domain",
            "allowed_claim": "v1 discrepancy is bounded and preserved",
            "forbidden_claim": "v1 cooling failure proves Qiu source physics fails",
        },
        {
            "source_equation": "direct beta+k patch",
            "physical_role": "prospective shortcut",
            "parameter_and_unit": "beta [K^-1], k dimensionless",
            "present_repository_mapping": "not implemented",
            "inconsistency": "beta fixes branch steepness while k belongs only to S7 filament resistance; they do not repair v1 mixing semantics",
            "proposed_v2_mapping": "REJECT_DIRECT_BETA_K_PATCH",
            "allowed_claim": "a source audit is required before any new 2-D closure",
            "forbidden_claim": "cooling is restored by a two-constant patch",
        },
    ]


def audit_source_contract(
    *, repo_root: Path, config: Mapping[str, Any], params: OracleParameters
) -> dict[str, Any]:
    started = time.perf_counter()
    source_contract_path = repo_root / config["sources"]["source_contract"]["path"]
    source_contract = yaml.safe_load(source_contract_path.read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}
    for role in ("main_article", "supporting_information"):
        entry = config["sources"][role]
        path = repo_root / entry["path"]
        actual = sha256_file(path)
        expected = str(entry["sha256"]).lower()
        if actual.lower() != expected:
            raise SourceAuditError(f"{role} SHA-256 mismatch")
        hashes[role] = actual

    locked = source_contract["source_author_fitted_lumped_quantities"]
    expected_values = {
        "resistance_prefactor_ohm": float(locked["resistance_prefactor_ohm"]["value"]),
        "metallic_resistance_ohm": float(locked["metallic_resistance_ohm"]["value"]),
        "activation_temperature_K": float(locked["activation_temperature_K"]["value"]),
        "beta_per_K": float(locked["beta_per_K"]["value"]),
        "loop_width_K": float(locked["loop_width_K"]["value"]),
        "critical_temperature_K": float(locked["critical_temperature_K"]["value"]),
        "dynamic_metallic_factor": float(locked["dynamic_metallic_factor"]["value"]),
        "parallel_capacitance_F": float(locked["parallel_capacitance_F"]["value"]),
        "thermal_conductance_W_K": float(locked["lumped_thermal_conductance_W_K"]["value"]),
        "thermal_capacitance_J_K": float(locked["lumped_thermal_capacitance_J_K"]["value"]),
    }
    actual_values = asdict(params)
    for name, expected in expected_values.items():
        if not math.isclose(actual_values[name], expected, rel_tol=0.0, abs_tol=1.0e-15):
            raise SourceAuditError(f"source parameter mismatch for {name}")

    from pinnpcm.physics.qiu_author_compact_model import (
        LLPReversalLedger,
        default_parameters,
        dynamic_resistance_ohm,
        major_branch_insulating_fraction,
        quasistatic_resistance_ohm,
    )

    repository_params = default_parameters()
    temperatures = np.linspace(320.0, 360.0, 81)
    parity_max = 0.0
    for branch in ("heating", "cooling"):
        delta = int(config["branch_contract"][branch]["delta"])
        direct_fraction = np.asarray(insulating_fraction(temperatures, delta, params))
        repository_fraction = np.asarray(
            major_branch_insulating_fraction(
                temperatures, delta, repository_params
            )
        )
        parity_max = max(
            parity_max,
            float(np.max(np.abs(direct_fraction - repository_fraction))),
        )
        ledger = LLPReversalLedger(
            delta=delta,
            reversed_once=False,
            reversal_temperature_K=params.ambient_temperature_K,
            reversal_fraction=float(direct_fraction[0]),
            proximity_temperature_K=0.0,
        )
        for variant, function, multiplier in (
            ("S1", quasistatic_resistance_ohm, 1.0),
            ("S7", dynamic_resistance_ohm, params.dynamic_metallic_factor),
        ):
            direct, _ = resistance_and_derivative(
                temperatures, delta, multiplier, params
            )
            repository = np.asarray(
                function(temperatures, ledger, repository_params)
            )
            relative = np.max(
                np.abs(np.asarray(direct) - repository)
                / np.maximum(np.abs(repository), 1.0)
            )
            parity_max = max(parity_max, float(relative))
            if not np.isfinite(relative):
                raise SourceAuditError(f"nonfinite {variant} formula parity")
    if parity_max > 1.0e-13:
        raise SourceAuditError("independent source oracle disagrees with source module")

    heating_threshold = params.critical_temperature_K + params.loop_width_K / 2.0
    cooling_threshold = params.critical_temperature_K - params.loop_width_K / 2.0
    logistic_scale = 1.0 / (2.0 * params.beta_per_K)
    branch_cfg = config["branch_contract"]
    if not math.isclose(
        heating_threshold,
        float(branch_cfg["heating"]["threshold_temperature_K"]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise SourceAuditError("heating branch threshold drifted")
    if not math.isclose(
        cooling_threshold,
        float(branch_cfg["cooling"]["threshold_temperature_K"]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise SourceAuditError("cooling branch threshold drifted")
    if not math.isclose(
        logistic_scale,
        float(branch_cfg["equivalent_logistic_scale_K"]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise SourceAuditError("equivalent logistic scale drifted")

    return {
        "status": "PASS",
        "major_loop_Tpr_semantics": "Tpr_inactive_before_reversal",
        "heating_threshold_temperature_K": heating_threshold,
        "cooling_threshold_temperature_K": cooling_threshold,
        "source_beta_equivalent_logistic_scale_K": logistic_scale,
        "v1_incorrect_sigmoid_scale_K": params.loop_width_K,
        "direct_beta_plus_k_patch_verdict": "REJECT_DIRECT_BETA_K_PATCH",
        "independent_repository_formula_parity_max": parity_max,
        "source_sha256": hashes,
        "source_contract_sha256": sha256_file(source_contract_path),
        "wall_time_s": time.perf_counter() - started,
    }


def _correct_connected_root(
    *,
    target_source_voltage_V: float,
    predictor_temperature_K: float,
    load_resistance_ohm: float,
    branch: str,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> FixedPoint:
    delta = int(config["branch_contract"][branch]["delta"])
    multiplier = float(
        config["resistance_variants"]["S1_QS"]["metallic_multiplier"]
    )

    def function(temperature: float) -> float:
        return float(
            thermal_balance(
                temperature,
                source_voltage_V=target_source_voltage_V,
                load_resistance_ohm=load_resistance_ohm,
                delta=delta,
                metallic_multiplier=multiplier,
                params=params,
            )
        )

    def derivative(temperature: float) -> float:
        return float(
            thermal_balance_derivative(
                temperature,
                source_voltage_V=target_source_voltage_V,
                load_resistance_ohm=load_resistance_ohm,
                delta=delta,
                metallic_multiplier=multiplier,
                params=params,
            )
        )

    upper = params.ambient_temperature_K + target_source_voltage_V**2 / (
        4.0 * load_resistance_ohm * params.thermal_conductance_W_K
    )
    corrected = float(
        optimize.newton(
            function,
            predictor_temperature_K,
            fprime=derivative,
            tol=1.0e-12,
            maxiter=50,
        )
    )
    if not math.isfinite(corrected) or not (
        params.ambient_temperature_K - 1.0e-10 <= corrected <= upper + 1.0e-10
    ):
        raise RuntimeError("corrector left the analytic temperature bound")
    discovery = discover_fixed_points(
        source_voltage_V=target_source_voltage_V,
        load_resistance_ohm=load_resistance_ohm,
        branch=branch,
        resistance_variant="S1_QS",
        params=params,
        config=config,
    )
    tolerance = float(config["reachability"]["root_match_temperature_tolerance_K"])
    matches = [
        point
        for point in discovery.fixed_points
        if abs(point.temperature_K - corrected) <= tolerance
    ]
    if len(matches) != 1:
        raise RuntimeError("corrector did not identify one enumerated fixed point")
    return matches[0]


def _source_track(config: Mapping[str, Any], *, descending: bool) -> list[float]:
    reach = config["reachability"]
    start = float(reach["source_voltage_grid_start_V"])
    stop = float(reach["source_voltage_grid_stop_V"])
    step = float(reach["source_voltage_grid_step_V"])
    count = int(round((stop - start) / step))
    values = [start + index * step for index in range(count + 1)]
    values.extend(float(item) for item in reach["extra_source_voltages_V"])
    values = sorted(set(round(item, 12) for item in values), reverse=descending)
    return values


def trace_continuous_reachability(
    *,
    load_resistance_ohm: float,
    branch: str,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    descending = branch == "cooling"
    targets = _source_track(config, descending=descending)
    endpoint_voltage = targets[0]
    endpoint = discover_fixed_points(
        source_voltage_V=endpoint_voltage,
        load_resistance_ohm=load_resistance_ohm,
        branch=branch,
        resistance_variant="S1_QS",
        params=params,
        config=config,
    )
    robust_min = float(config["stability"]["robust_margin_min"])
    if branch == "heating":
        endpoint_candidates = [
            point
            for point in endpoint.fixed_points
            if point.stability.classification == "stable"
            and point.stability.robust_stability_margin >= robust_min
            and point.conductive_state <= 0.10
        ]
    else:
        endpoint_candidates = [
            point
            for point in endpoint.fixed_points
            if point.stability.classification == "stable"
            and point.stability.robust_stability_margin >= robust_min
            and point.conductive_state
            >= float(config["reachability"]["cooling_endpoint_conductive_state_min"])
        ]
    records: list[dict[str, Any]] = []
    if len(endpoint_candidates) != 1:
        reason = (
            "ambiguous_or_missing_low_stable_endpoint"
            if branch == "heating"
            else "ambiguous_or_missing_high_stable_endpoint"
        )
        for point in endpoint.fixed_points:
            records.append(
                _reachability_row(
                    point,
                    reachable=False,
                    status=reason,
                    config=config,
                    target=True,
                )
            )
        return _append_post_switch_records(
            records=records,
            remaining_targets=targets[1:],
            load_resistance_ohm=load_resistance_ohm,
            branch=branch,
            params=params,
            config=config,
        )

    current = endpoint_candidates[0]
    records.append(
        _reachability_row(
            current,
            reachable=True,
            status="continuous_quasistatic_reachable",
            config=config,
            target=True,
        )
    )
    path_points = [(endpoint_voltage, current.temperature_K)]
    terminated_at_index: int | None = None
    minimum_step = float(config["reachability"]["minimum_source_step_V"])
    for target_index, target in enumerate(targets[1:], start=1):
        while abs(target - path_points[-1][0]) > 1.0e-12:
            current_voltage = path_points[-1][0]
            proposed_step = target - current_voltage
            attempt_step = proposed_step
            accepted: FixedPoint | None = None
            while abs(attempt_step) >= minimum_step - 1.0e-15:
                trial_voltage = current_voltage + attempt_step
                if len(path_points) >= 2:
                    (v0, t0), (v1, t1) = path_points[-2:]
                    slope = (t1 - t0) / (v1 - v0)
                    predictor = t1 + slope * (trial_voltage - v1)
                else:
                    predictor = path_points[-1][1]
                try:
                    candidate = _correct_connected_root(
                        target_source_voltage_V=trial_voltage,
                        predictor_temperature_K=predictor,
                        load_resistance_ohm=load_resistance_ohm,
                        branch=branch,
                        params=params,
                        config=config,
                    )
                except (RuntimeError, ValueError, SourceAuditError, OverflowError):
                    attempt_step *= 0.5
                    continue
                if candidate.stability.classification != "stable":
                    terminated_at_index = target_index
                    records.append(
                        _reachability_row(
                            candidate,
                            reachable=False,
                            status="continuous_component_terminated_at_nonstable_point",
                            config=config,
                            target=abs(trial_voltage - target) <= 1.0e-12,
                        )
                    )
                    break
                accepted = candidate
                path_points.append((trial_voltage, candidate.temperature_K))
                if abs(trial_voltage - target) <= 1.0e-12:
                    records.append(
                        _reachability_row(
                            candidate,
                            reachable=True,
                            status="continuous_quasistatic_reachable",
                            config=config,
                            target=True,
                        )
                    )
                break
            if terminated_at_index is not None:
                break
            if accepted is None:
                terminated_at_index = target_index
                break
        if terminated_at_index is not None:
            break

    if terminated_at_index is not None:
        remaining = targets[terminated_at_index:]
        return _append_post_switch_records(
            records=records,
            remaining_targets=remaining,
            load_resistance_ohm=load_resistance_ohm,
            branch=branch,
            params=params,
            config=config,
        )
    return records


def _reachability_row(
    point: FixedPoint,
    *,
    reachable: bool,
    status: str,
    config: Mapping[str, Any],
    target: bool,
) -> dict[str, Any]:
    diagnostics = {
        round(float(value), 12)
        for value in config["reachability"]["diagnostic_only_source_voltages_V"]
    }
    diagnostic_only = round(point.source_voltage_V, 12) in diagnostics
    robust_min = float(config["stability"]["robust_margin_min"])
    return {
        "load_resistance_ohm": point.load_resistance_ohm,
        "branch": point.branch,
        "source_voltage_V": point.source_voltage_V,
        "temperature_K": point.temperature_K,
        "device_voltage_V": point.device_voltage_V,
        "current_A": point.current_A,
        "conductive_state": point.conductive_state,
        "stability_classification": point.stability.classification,
        "robust_stability_margin": point.stability.robust_stability_margin,
        "reachable": reachable,
        "reachability_status": status,
        "target_grid_point": target,
        "diagnostic_only": diagnostic_only,
        "voting_eligible": bool(
            target
            and reachable
            and not diagnostic_only
            and point.stability.classification == "stable"
            and point.stability.robust_stability_margin >= robust_min
        ),
    }


def _append_post_switch_records(
    *,
    records: list[dict[str, Any]],
    remaining_targets: Sequence[float],
    load_resistance_ohm: float,
    branch: str,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    already = {
        round(float(row["source_voltage_V"]), 12)
        for row in records
        if bool(row["target_grid_point"])
    }
    for source_voltage in remaining_targets:
        if round(source_voltage, 12) in already:
            continue
        discovery = discover_fixed_points(
            source_voltage_V=source_voltage,
            load_resistance_ohm=load_resistance_ohm,
            branch=branch,
            resistance_variant="S1_QS",
            params=params,
            config=config,
        )
        for point in discovery.fixed_points:
            records.append(
                _reachability_row(
                    point,
                    reachable=False,
                    status="post_switch_reachability_unresolved",
                    config=config,
                    target=True,
                )
            )
    return records


def evaluate_domain_gates(
    records: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    forward_cfg = config["nondegenerate_forward_gate"]
    branch_results: dict[str, Any] = {}
    for branch in ("heating", "cooling"):
        voting = [
            row
            for row in records
            if row["branch"] == branch and bool(row["voting_eligible"])
        ]
        states = [float(row["conductive_state"]) for row in voting]
        span = max(states) - min(states) if states else 0.0
        transition_count = sum(
            float(forward_cfg["transition_coordinate_min"])
            <= value
            <= float(forward_cfg["transition_coordinate_max"])
            for value in states
        )
        high_count = sum(
            value >= float(forward_cfg["high_conductive_state_min"])
            for value in states
        )
        passed = bool(
            len(voting) >= int(forward_cfg["minimum_voting_biases"])
            and span >= float(forward_cfg["conductive_state_span_min"])
            and transition_count >= int(forward_cfg["minimum_transition_cases"])
            and high_count >= int(forward_cfg["minimum_high_conductive_cases"])
            and all(
                float(row["robust_stability_margin"])
                >= float(forward_cfg["robust_stability_margin_min"])
                for row in voting
            )
        )
        branch_results[branch] = {
            "pass": passed,
            "voting_bias_count": len(voting),
            "conductive_state_span": span,
            "transition_case_count": transition_count,
            "high_conductive_case_count": high_count,
            "voting_biases_V": [float(row["source_voltage_V"]) for row in voting],
        }

    dual_cfg = config["dual_branch_gate"]
    by_branch = {
        branch: {
            round(float(row["source_voltage_V"]), 12): row
            for row in records
            if row["branch"] == branch and bool(row["voting_eligible"])
        }
        for branch in ("heating", "cooling")
    }
    common = sorted(set(by_branch["heating"]) & set(by_branch["cooling"]))
    separated = [
        voltage
        for voltage in common
        if abs(
            float(by_branch["heating"][voltage]["conductive_state"])
            - float(by_branch["cooling"][voltage]["conductive_state"])
        )
        >= float(dual_cfg["conductive_state_branch_separation_min"])
    ]
    dual_pass = bool(
        len(common) >= int(dual_cfg["minimum_common_voting_biases"])
        and len(separated) >= int(dual_cfg["minimum_branch_separated_biases"])
    )
    return {
        "forward": branch_results,
        "any_forward_pass": any(item["pass"] for item in branch_results.values()),
        "dual_branch": {
            "pass": dual_pass,
            "common_voting_bias_count": len(common),
            "common_voting_biases_V": common,
            "branch_separated_bias_count": len(separated),
            "branch_separated_biases_V": separated,
        },
    }


def _environment_record(run_id: str) -> dict[str, Any]:
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        git_sha = "unavailable"
    return {
        "run_id": run_id,
        "git_sha": git_sha,
        "command": [sys.executable, *sys.argv],
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "blas_thread_environment": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    }


def _select_load(
    loads: Sequence[float], *, nominal_load_resistance_ohm: float
) -> float:
    return min(
        loads,
        key=lambda value: (
            abs(math.log(value / nominal_load_resistance_ohm)),
            value,
        ),
    )


def run_stage_a(
    *, config_path: Path, repo_root: Path, output_root: Path, run_id: str | None = None
) -> dict[str, Any]:
    config = load_stage_a_config(config_path)
    params = OracleParameters.from_config(config)
    run_identity = run_id or str(config["run_id"])
    output_dir = output_root / run_identity
    output_dir.mkdir(parents=True, exist_ok=True)
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    discrepancy_rows = build_source_to_code_discrepancy_rows()
    _atomic_csv(output_dir / "source_to_code_discrepancy.csv", discrepancy_rows)

    summary: dict[str, Any]
    terminal: dict[str, Any]
    try:
        audit = audit_source_contract(
            repo_root=repo_root, config=config, params=params
        )
        if audit["wall_time_s"] > float(config["budget"]["source_audit_wall_cap_s"]):
            raise SourceAuditError("source audit exceeded its wall-time budget")

        fixed_rows: list[dict[str, Any]] = []
        stability_rows: list[dict[str, Any]] = []
        stationary_rows: list[dict[str, Any]] = []
        base_case_summaries: list[dict[str, Any]] = []
        nominal_load = float(config["source_parameters"]["nominal_load_resistance_ohm"])
        for source_voltage in map(float, config["base_matrix"]["source_voltages_V"]):
            for branch in config["base_matrix"]["branches"]:
                for variant in config["base_matrix"]["resistance_variants"]:
                    discovery = discover_fixed_points(
                        source_voltage_V=source_voltage,
                        load_resistance_ohm=nominal_load,
                        branch=str(branch),
                        resistance_variant=str(variant),
                        params=params,
                        config=config,
                    )
                    case_id = f"Vs{source_voltage:g}_{branch}_{variant}"
                    for index, point in enumerate(discovery.fixed_points):
                        row = point.to_row(scope="base_matrix", root_index=index)
                        row["case_id"] = case_id
                        row["diagnostic_only"] = source_voltage == 12.5
                        fixed_rows.append(row)
                        stability_rows.append(
                            {
                                "case_id": case_id,
                                "root_index": index,
                                "source_voltage_V": source_voltage,
                                "branch": branch,
                                "resistance_variant": variant,
                                "temperature_K": point.temperature_K,
                                **asdict(point.stability),
                            }
                        )
                    for index, temperature in enumerate(
                        discovery.stationary_temperatures_K
                    ):
                        stationary_rows.append(
                            {
                                "case_id": case_id,
                                "stationary_index": index,
                                "source_voltage_V": source_voltage,
                                "branch": branch,
                                "resistance_variant": variant,
                                "temperature_K": temperature,
                            }
                        )
                    base_case_summaries.append(
                        {
                            "case_id": case_id,
                            "source_voltage_V": source_voltage,
                            "branch": branch,
                            "resistance_variant": variant,
                            "root_count": len(discovery.fixed_points),
                            "stationary_point_count": len(
                                discovery.stationary_temperatures_K
                            ),
                            "root_set_hausdorff_K": discovery.root_set_hausdorff_K,
                            "diagnostic_only": source_voltage == 12.5,
                        }
                    )
        _atomic_csv(output_dir / "fixed_points.csv", fixed_rows)
        _atomic_csv(output_dir / "stationary_points.csv", stationary_rows)
        _atomic_csv(output_dir / "stability.csv", stability_rows)

        reachability_rows: list[dict[str, Any]] = []
        load_summaries: list[dict[str, Any]] = []

        def evaluate_load(load_resistance_ohm: float) -> dict[str, Any]:
            load_started = time.perf_counter()
            records = []
            for branch_name in ("heating", "cooling"):
                records.extend(
                    trace_continuous_reachability(
                        load_resistance_ohm=load_resistance_ohm,
                        branch=branch_name,
                        params=params,
                        config=config,
                    )
                )
            elapsed = time.perf_counter() - load_started
            if elapsed > float(
                config["load_design_sentinel"]["per_load_wall_cap_s"]
            ):
                raise SourceAuditError(
                    f"load sentinel {load_resistance_ohm:g} ohm exceeded its wall cap"
                )
            gates = evaluate_domain_gates(records, config)
            for record in records:
                record["load_scope"] = (
                    "nominal_12k"
                    if math.isclose(load_resistance_ohm, nominal_load)
                    else "load_design_sentinel"
                )
            reachability_rows.extend(records)
            result = {
                "load_resistance_ohm": load_resistance_ohm,
                "wall_time_s": elapsed,
                **gates,
            }
            load_summaries.append(result)
            return result

        nominal_domain = evaluate_load(nominal_load)
        sentinel_executed = not bool(nominal_domain["dual_branch"]["pass"])
        if sentinel_executed:
            sentinel_started = time.perf_counter()
            for load in map(
                float, config["load_design_sentinel"]["load_resistances_ohm"]
            ):
                if math.isclose(load, nominal_load):
                    continue
                evaluate_load(load)
            if time.perf_counter() - sentinel_started > float(
                config["load_design_sentinel"]["total_wall_cap_s"]
            ):
                raise SourceAuditError("load-design sentinel exceeded total wall cap")

        _atomic_csv(output_dir / "continuous_reachability.csv", reachability_rows)
        load_rows: list[dict[str, Any]] = []
        for item in load_summaries:
            load_rows.append(
                {
                    "load_resistance_ohm": item["load_resistance_ohm"],
                    "wall_time_s": item["wall_time_s"],
                    "dual_branch_pass": item["dual_branch"]["pass"],
                    "common_voting_bias_count": item["dual_branch"][
                        "common_voting_bias_count"
                    ],
                    "branch_separated_bias_count": item["dual_branch"][
                        "branch_separated_bias_count"
                    ],
                    "heating_forward_pass": item["forward"]["heating"]["pass"],
                    "cooling_forward_pass": item["forward"]["cooling"]["pass"],
                    "heating_voting_bias_count": item["forward"]["heating"][
                        "voting_bias_count"
                    ],
                    "cooling_voting_bias_count": item["forward"]["cooling"][
                        "voting_bias_count"
                    ],
                    "heating_conductive_state_span": item["forward"]["heating"][
                        "conductive_state_span"
                    ],
                    "cooling_conductive_state_span": item["forward"]["cooling"][
                        "conductive_state_span"
                    ],
                }
            )
        _atomic_csv(output_dir / "load_design_sentinel.csv", load_rows)

        dual_pass_loads = [
            float(item["load_resistance_ohm"])
            for item in load_summaries
            if bool(item["dual_branch"]["pass"])
        ]
        forward_pass_loads = [
            float(item["load_resistance_ohm"])
            for item in load_summaries
            if bool(item["any_forward_pass"])
        ]
        if bool(nominal_domain["dual_branch"]["pass"]):
            disposition = "A_GO_12K_DUAL_BRANCH_L1"
            selected_load = nominal_load
        elif dual_pass_loads:
            selected_load = _select_load(
                dual_pass_loads,
                nominal_load_resistance_ohm=nominal_load,
            )
            disposition = "A_GO_DESIGNED_LOAD_L1"
        elif forward_pass_loads:
            selected_load = _select_load(
                forward_pass_loads,
                nominal_load_resistance_ohm=nominal_load,
            )
            disposition = "A_PIVOT_FORWARD_ONLY"
        else:
            selected_load = None
            disposition = "A_STOP_STEADY_ROUTE"

        wall_elapsed = time.perf_counter() - wall_started
        cpu_elapsed = time.process_time() - cpu_started
        if wall_elapsed > float(config["budget"]["stage_a_calendar_wall_cap_s"]):
            raise SourceAuditError("Stage A exceeded calendar wall budget")
        if cpu_elapsed > float(config["budget"]["stage_a_aggregate_cpu_cap_s"]):
            raise SourceAuditError("Stage A exceeded aggregate CPU budget")

        summary = {
            "schema_version": "q2_qiu_source_oracle_summary_v1",
            "task_id": config["task_id"],
            "run_id": run_identity,
            "validity": "valid",
            "lifecycle_state": "executed",
            "claim_status": (
                "qualified_supported"
                if disposition.startswith("A_GO")
                or disposition == "A_PIVOT_FORWARD_ONLY"
                else "failed_but_informative"
            ),
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": disposition,
            "direct_beta_plus_k_patch_verdict": "REJECT_DIRECT_BETA_K_PATCH",
            "audit": audit,
            "base_matrix_case_count": len(base_case_summaries),
            "base_matrix": base_case_summaries,
            "nominal_12k_domain": nominal_domain,
            "load_sentinel_executed": sentinel_executed,
            "load_domains": load_summaries,
            "selected_load_resistance_ohm_for_conditional_stage_b": selected_load,
            "stage_b_executed": False,
            "environment": _environment_record(run_identity),
            "config_path": config_path.relative_to(repo_root).as_posix(),
            "config_sha256": sha256_file(config_path),
            "aggregate_cpu_s": cpu_elapsed,
            "calendar_wall_s": wall_elapsed,
            "claim_boundary": config["claim_boundary"],
        }
        _atomic_json(output_dir / "source_oracle_summary.json", summary)
        terminal = {
            "schema_version": "q2_qiu_source_stage_a_terminal_v1",
            "task_id": config["task_id"],
            "run_id": run_identity,
            "validity": "valid",
            "lifecycle_state": "executed",
            "claim_status": summary["claim_status"],
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": disposition,
            "selected_load_resistance_ohm_for_conditional_stage_b": selected_load,
            "stage_b_authorized": False,
            "stage_b_executed": False,
            "aggregate_cpu_s": cpu_elapsed,
            "calendar_wall_s": wall_elapsed,
        }
    except Exception as exc:
        wall_elapsed = time.perf_counter() - wall_started
        cpu_elapsed = time.process_time() - cpu_started
        summary = {
            "schema_version": "q2_qiu_source_oracle_summary_v1",
            "task_id": config["task_id"],
            "run_id": run_identity,
            "validity": "invalid",
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": "A_INVALID_SOURCE_AUDIT",
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "stage_b_executed": False,
            "environment": _environment_record(run_identity),
            "aggregate_cpu_s": cpu_elapsed,
            "calendar_wall_s": wall_elapsed,
            "claim_boundary": config["claim_boundary"],
        }
        _atomic_json(output_dir / "source_oracle_summary.json", summary)
        terminal = {
            "schema_version": "q2_qiu_source_stage_a_terminal_v1",
            "task_id": config["task_id"],
            "run_id": run_identity,
            "validity": "invalid",
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": "A_INVALID_SOURCE_AUDIT",
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "stage_b_authorized": False,
            "stage_b_executed": False,
            "aggregate_cpu_s": cpu_elapsed,
            "calendar_wall_s": wall_elapsed,
        }
    _atomic_json(output_dir / "terminal.json", terminal)
    return summary
