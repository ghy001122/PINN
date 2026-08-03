"""Safeguarded Anderson temperature root for the exact-condensed S2 step.

This is the single R2 nonlinear identity authorized after the R1 contraction
gate.  It does not modify or fall back to the historical damped-Newton root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_ledgers import build_s2_ledgers
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers import geophase_exact_condensed as exact_v1
from pinnpcm.solvers import geophase_phase1_v2_implicit as production


SOLVER_ID = "exact_condensed_temperature_safeguarded_anderson_v1"


@dataclass(frozen=True)
class SafeguardedAndersonSettings:
    depth: int = 3
    relaxation: float = 0.5
    maximum_map_evaluations: int = 80
    coefficient_regularization: float = 1.0e-10
    svd_rcond: float = 1.0e-12
    residual_scale_floor_K: float = 1.0e-30
    sufficient_decrease_c1: float = 1.0e-4
    reduced_residual_tolerance: float = 1.0e-8
    full_residual_tolerance: float = 1.0e-8
    full_fixed_point_defect_tolerance: float = 1.0e-8
    auxiliary_residual_tolerance: float = 1.0e-12

    def validate(self) -> None:
        if self.depth != 3:
            raise ValueError("safeguarded Anderson depth must remain 3")
        if self.relaxation != 0.5:
            raise ValueError("safeguarded Anderson relaxation must remain 0.5")
        if self.maximum_map_evaluations != 80:
            raise ValueError("safeguarded Anderson map budget must remain 80")
        positive = (
            self.coefficient_regularization,
            self.svd_rcond,
            self.residual_scale_floor_K,
            self.sufficient_decrease_c1,
            self.reduced_residual_tolerance,
            self.full_residual_tolerance,
            self.full_fixed_point_defect_tolerance,
            self.auxiliary_residual_tolerance,
        )
        if not np.isfinite(positive).all() or any(
            value <= 0.0 for value in positive
        ):
            raise ValueError(
                "safeguarded Anderson settings must be finite and positive"
            )


DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS = SafeguardedAndersonSettings()


@dataclass(frozen=True)
class SafeguardedAndersonRootTelemetry:
    solver_id: str
    status: str
    failure_code: str | None
    failure_message: str | None
    iterations: int
    map_evaluations: int
    anderson_attempts: int
    anderson_accepted: int
    anderson_rejected: int
    safeguarded_picard_steps: int
    history_restarts: int
    reduced_residual_inf: float | None
    full_scaled_residual_inf: float | None
    full_fixed_point_defect_inf: float | None
    auxiliary_scaled_residual_inf: float | None
    raw_thermal_residual_inf_W_per_cell: float | None
    unscaled_temperature_defect_history_inf_K: tuple[float, ...]
    accepted_step_kind_history: tuple[str, ...]
    coefficient_history: tuple[tuple[float, ...], ...]
    predictor_wall_s: float
    map_wall_s: float
    coefficient_wall_s: float
    certification_wall_s: float
    total_wall_s: float


@dataclass(frozen=True)
class _MapEvaluation:
    temperature_K: np.ndarray
    auxiliary: exact_v1.ExactAuxiliaryState
    mapped_full_vector: np.ndarray
    phi_temperature_K: np.ndarray
    unscaled_defect_K: np.ndarray
    unscaled_defect_inf_K: float
    reduced_residual_inf: float
    full_scaled_residual_inf: float
    full_fixed_point_defect_inf: float
    auxiliary_scaled_residual_inf: float


@dataclass
class _Counters:
    map_evaluations: int = 0
    iterations: int = 0
    anderson_attempts: int = 0
    anderson_accepted: int = 0
    anderson_rejected: int = 0
    safeguarded_picard_steps: int = 0
    history_restarts: int = 0
    map_wall_s: float = 0.0
    coefficient_wall_s: float = 0.0
    defect_history: list[float] = field(default_factory=list)
    accepted_step_kinds: list[str] = field(default_factory=list)
    coefficient_history: list[tuple[float, ...]] = field(default_factory=list)


def _finite_or_none(value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _telemetry(
    *,
    status: str,
    code: str | None,
    message: str | None,
    counters: _Counters,
    predictor_wall_s: float,
    certification_wall_s: float,
    total_wall_s: float,
    latest: _MapEvaluation | None,
) -> SafeguardedAndersonRootTelemetry:
    return SafeguardedAndersonRootTelemetry(
        solver_id=SOLVER_ID,
        status=str(status),
        failure_code=None if code is None else str(code),
        failure_message=None if message is None else str(message),
        iterations=int(counters.iterations),
        map_evaluations=int(counters.map_evaluations),
        anderson_attempts=int(counters.anderson_attempts),
        anderson_accepted=int(counters.anderson_accepted),
        anderson_rejected=int(counters.anderson_rejected),
        safeguarded_picard_steps=int(counters.safeguarded_picard_steps),
        history_restarts=int(counters.history_restarts),
        reduced_residual_inf=(
            None if latest is None else _finite_or_none(latest.reduced_residual_inf)
        ),
        full_scaled_residual_inf=(
            None
            if latest is None
            else _finite_or_none(latest.full_scaled_residual_inf)
        ),
        full_fixed_point_defect_inf=(
            None
            if latest is None
            else _finite_or_none(latest.full_fixed_point_defect_inf)
        ),
        auxiliary_scaled_residual_inf=(
            None
            if latest is None
            else _finite_or_none(latest.auxiliary_scaled_residual_inf)
        ),
        raw_thermal_residual_inf_W_per_cell=(
            None
            if latest is None
            else _finite_or_none(
                float(
                    np.max(
                        np.abs(latest.auxiliary.raw_thermal_residual_W_per_cell)
                    )
                )
            )
        ),
        unscaled_temperature_defect_history_inf_K=tuple(counters.defect_history),
        accepted_step_kind_history=tuple(counters.accepted_step_kinds),
        coefficient_history=tuple(counters.coefficient_history),
        predictor_wall_s=float(predictor_wall_s),
        map_wall_s=float(counters.map_wall_s),
        coefficient_wall_s=float(counters.coefficient_wall_s),
        certification_wall_s=float(certification_wall_s),
        total_wall_s=float(total_wall_s),
    )


def _is_certified(
    evaluation: _MapEvaluation,
    settings: SafeguardedAndersonSettings,
) -> bool:
    return bool(
        evaluation.reduced_residual_inf <= settings.reduced_residual_tolerance
        and evaluation.full_scaled_residual_inf <= settings.full_residual_tolerance
        and evaluation.full_fixed_point_defect_inf
        <= settings.full_fixed_point_defect_tolerance
        and evaluation.auxiliary_scaled_residual_inf
        <= settings.auxiliary_residual_tolerance
    )


def _anderson_coefficients(
    residuals: list[np.ndarray],
    *,
    regularization: float,
    rcond: float,
    scale_floor: float,
) -> tuple[np.ndarray, float]:
    scale = max(
        max(float(np.max(np.abs(item))) for item in residuals),
        float(scale_floor),
    )
    matrix = np.column_stack([item.reshape(-1) / scale for item in residuals])
    count = matrix.shape[1]
    normal = matrix.T @ matrix + regularization * np.eye(count, dtype=float)
    kkt = np.block(
        [
            [normal, np.ones((count, 1), dtype=float)],
            [np.ones((1, count), dtype=float), np.zeros((1, 1), dtype=float)],
        ]
    )
    rhs = np.concatenate([np.zeros(count, dtype=float), np.ones(1, dtype=float)])
    solution, _, _, _ = np.linalg.lstsq(kkt, rhs, rcond=rcond)
    coefficients = np.asarray(solution[:count], dtype=float)
    if not np.isfinite(coefficients).all():
        raise FloatingPointError("Anderson coefficient solve returned nonfinite values")
    if not np.isclose(float(np.sum(coefficients)), 1.0, rtol=0.0, atol=1.0e-10):
        raise FloatingPointError("Anderson coefficients violate the affine constraint")
    return coefficients, scale


def _run_safeguarded_iterations(
    initial_temperature_K: np.ndarray,
    *,
    evaluate: Any,
    validate_temperature: Any,
    settings: SafeguardedAndersonSettings,
    counters: _Counters,
) -> _MapEvaluation:
    temperature = np.asarray(initial_temperature_K, dtype=float).copy()
    history: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    while True:
        latest = evaluate(temperature)
        counters.defect_history.append(latest.unscaled_defect_inf_K)
        if _is_certified(latest, settings):
            return latest
        if latest.unscaled_defect_inf_K == 0.0:
            raise RuntimeError(
                "temperature map is fixed but the full certification still fails"
            )
        psi_current = (
            latest.temperature_K - settings.relaxation * latest.unscaled_defect_K
        )
        residual_current = psi_current - latest.temperature_K
        history.append(
            (
                latest.temperature_K.copy(),
                np.asarray(psi_current, dtype=float),
                np.asarray(residual_current, dtype=float),
            )
        )
        history = history[-(settings.depth + 1) :]
        accepted: _MapEvaluation | None = None
        attempted_anderson = len(history) >= 2
        if attempted_anderson:
            counters.anderson_attempts += 1
            coefficient_started = perf_counter()
            coefficients, _ = _anderson_coefficients(
                [item[2] for item in history],
                regularization=settings.coefficient_regularization,
                rcond=settings.svd_rcond,
                scale_floor=settings.residual_scale_floor_K,
            )
            counters.coefficient_wall_s += perf_counter() - coefficient_started
            counters.coefficient_history.append(tuple(float(x) for x in coefficients))
            candidate = np.zeros_like(temperature, dtype=float)
            for coefficient, (_, mapped_psi, _) in zip(coefficients, history):
                candidate = candidate + coefficient * mapped_psi
            validate_temperature(candidate)
            anderson_evaluation = evaluate(candidate)
            sufficient = bool(
                anderson_evaluation.unscaled_defect_inf_K
                <= (1.0 - settings.sufficient_decrease_c1)
                * latest.unscaled_defect_inf_K
            )
            if sufficient or _is_certified(anderson_evaluation, settings):
                accepted = anderson_evaluation
                counters.anderson_accepted += 1
                counters.accepted_step_kinds.append("anderson")
            else:
                counters.anderson_rejected += 1

        if accepted is None:
            validate_temperature(psi_current)
            picard_evaluation = evaluate(psi_current)
            sufficient = bool(
                picard_evaluation.unscaled_defect_inf_K
                <= (1.0 - settings.sufficient_decrease_c1)
                * latest.unscaled_defect_inf_K
            )
            if not sufficient and not _is_certified(picard_evaluation, settings):
                raise RuntimeError(
                    "the frozen relaxed Picard safeguard failed the 1e-4 decrease gate"
                )
            accepted = picard_evaluation
            counters.safeguarded_picard_steps += 1
            counters.accepted_step_kinds.append("safeguarded_picard")
            if attempted_anderson:
                history.clear()
                counters.history_restarts += 1
        temperature = accepted.temperature_K.copy()
        counters.iterations += 1


def solve_exact_condensed_safeguarded_anderson_step(
    old_state: production.S2State,
    *,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: production.S2SolverCache | None = None,
    anderson_settings: SafeguardedAndersonSettings = (
        DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    ),
    performance_timings: production.S2PerformanceTimings | None = None,
    **unsupported: Any,
) -> exact_v1.ExactCondensedStepOutcome:
    """Solve one exact-condensed step with the sole safeguarded-AA identity."""

    if unsupported:
        raise ValueError(
            "safeguarded Anderson received unsupported solver options: "
            + ", ".join(sorted(unsupported))
        )
    started = perf_counter()
    anderson_settings.validate()
    if not np.isfinite([input_voltage_V, dt_s]).all() or dt_s <= 0.0:
        raise ValueError("input voltage and positive dt must be finite")
    production.validate_s2_state(old_state, grid, closure)
    fields.validate_grid(grid)
    active_cache = cache or production.build_s2_solver_cache(grid, fields)
    active_cache.validate_context(grid, fields)
    counters = _Counters()
    predictor_wall = 0.0
    certification_wall = 0.0
    latest: _MapEvaluation | None = None
    cached: _MapEvaluation | None = None

    equilibrium = closure.equilibrium_state(
        old_state.temperature_K, old_state.branch_memory
    )
    exact_zero_equilibrium = bool(
        float(input_voltage_V) == 0.0
        and old_state.device_voltage_V == 0.0
        and np.array_equal(
            old_state.temperature_K,
            np.full(grid.shape, fields.ambient_temperature_K, dtype=float),
        )
        and np.array_equal(old_state.conductive_state, equilibrium)
    )
    if exact_zero_equilibrium:
        analytic = exact_v1.solve_exact_condensed_step(
            old_state,
            input_voltage_V=0.0,
            dt_s=dt_s,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            cache=active_cache,
            performance_timings=performance_timings,
        )
        if analytic.step.nonlinear.method != (
            "exact_condensed_analytic_zero_drive_equilibrium"
        ):
            raise RuntimeError("shared zero-drive analytic path changed identity")
        telemetry = SafeguardedAndersonRootTelemetry(
            solver_id=SOLVER_ID,
            status="PASS",
            failure_code=None,
            failure_message=None,
            iterations=0,
            map_evaluations=0,
            anderson_attempts=0,
            anderson_accepted=0,
            anderson_rejected=0,
            safeguarded_picard_steps=0,
            history_restarts=0,
            reduced_residual_inf=0.0,
            full_scaled_residual_inf=0.0,
            full_fixed_point_defect_inf=0.0,
            auxiliary_scaled_residual_inf=0.0,
            raw_thermal_residual_inf_W_per_cell=0.0,
            unscaled_temperature_defect_history_inf_K=(),
            accepted_step_kind_history=("shared_analytic_zero_drive",),
            coefficient_history=(),
            predictor_wall_s=0.0,
            map_wall_s=0.0,
            coefficient_wall_s=0.0,
            certification_wall_s=0.0,
            total_wall_s=float(perf_counter() - started),
        )
        return exact_v1.ExactCondensedStepOutcome(  # type: ignore[arg-type]
            step=analytic.step,
            telemetry=telemetry,
        )

    def fail(code: str, message: str) -> None:
        telemetry = _telemetry(
            status="FAIL",
            code=code,
            message=message,
            counters=counters,
            predictor_wall_s=predictor_wall,
            certification_wall_s=certification_wall,
            total_wall_s=perf_counter() - started,
            latest=latest,
        )
        raise exact_v1.ExactCondensedRootFailure(  # type: ignore[arg-type]
            code,
            message,
            telemetry,
        )

    def evaluate(candidate: np.ndarray) -> _MapEvaluation:
        nonlocal cached, latest
        values = np.asarray(candidate, dtype=float).reshape(grid.shape)
        if cached is not None and np.array_equal(values, cached.temperature_K):
            return cached
        if counters.map_evaluations >= anderson_settings.maximum_map_evaluations:
            fail(
                "MAP_EVALUATION_BUDGET_EXHAUSTED",
                "safeguarded Anderson map evaluation 81 was blocked",
            )
        counters.map_evaluations += 1
        map_started = perf_counter()
        try:
            auxiliary = exact_v1.reconstruct_exact_auxiliary_state(
                values,
                old_state,
                dt_s,
                input_voltage_V,
                grid=grid,
                closure=closure,
                fields=fields,
                config=config,
                cache=active_cache,
                performance_timings=performance_timings,
            )
            load_resistance, capacitance = production._circuit_parameters(config)
            mapped_full = production._fixed_point_map(
                auxiliary.full_vector,
                old_state=old_state,
                input_voltage_V=float(input_voltage_V),
                dt_s=float(dt_s),
                grid=grid,
                closure=closure,
                fields=fields,
                lateral_matrix=active_cache.lateral_matrix,
                thermal_linear_solver=active_cache.thermal_solver(dt_s),
                electrical_topology=active_cache.electrical_topology,
                use_equivalent_optimizations=True,
                use_unit_voltage_scaling=True,
                performance_timings=performance_timings,
                load_resistance_ohm=load_resistance,
                capacitance_F=capacitance,
            )
            mapped_temperature, _, _, _ = production._unpack(mapped_full, grid)
            defect = values - mapped_temperature
            full_defect = float(
                np.max(
                    np.abs(mapped_full - auxiliary.full_vector)
                    / np.maximum(np.abs(auxiliary.full_vector), 1.0)
                )
            )
            result = _MapEvaluation(
                temperature_K=values.copy(),
                auxiliary=auxiliary,
                mapped_full_vector=np.asarray(mapped_full, dtype=float),
                phi_temperature_K=np.asarray(mapped_temperature, dtype=float),
                unscaled_defect_K=np.asarray(defect, dtype=float),
                unscaled_defect_inf_K=float(np.max(np.abs(defect))),
                reduced_residual_inf=float(
                    np.max(np.abs(auxiliary.temperature_scaled_residual))
                ),
                full_scaled_residual_inf=float(
                    np.max(np.abs(auxiliary.full_scaled_residual))
                ),
                full_fixed_point_defect_inf=full_defect,
                auxiliary_scaled_residual_inf=(
                    auxiliary.auxiliary_scaled_residual_inf
                ),
            )
        except exact_v1.ExactCondensedRootFailure:
            raise
        except (
            RuntimeError,
            ValueError,
            FloatingPointError,
            np.linalg.LinAlgError,
        ) as error:
            counters.map_wall_s += perf_counter() - map_started
            fail("MAP_EVALUATION_FAILURE", str(error))
        counters.map_wall_s += perf_counter() - map_started
        cached = result
        latest = result
        return result

    predictor_started = perf_counter()
    try:
        temperature = exact_v1._predict_temperature(
            old_state=old_state,
            input_voltage_V=float(input_voltage_V),
            dt_s=float(dt_s),
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            cache=active_cache,
            performance_timings=performance_timings,
        )
    except (
        RuntimeError,
        ValueError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as error:
        predictor_wall = perf_counter() - predictor_started
        fail("PREDICTOR_FAILURE", str(error))
    predictor_wall = perf_counter() - predictor_started

    try:
        latest = _run_safeguarded_iterations(
            temperature,
            evaluate=evaluate,
            validate_temperature=closure.validate_temperature,
            settings=anderson_settings,
            counters=counters,
        )
    except exact_v1.ExactCondensedRootFailure:
        raise
    except (
        RuntimeError,
        ValueError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as error:
        code = (
            "SAFEGUARDED_PICARD_NO_SUFFICIENT_DECREASE"
            if "decrease gate" in str(error)
            else "ANDERSON_ITERATION_FAILURE"
        )
        fail(code, str(error))

    certification_started = perf_counter()
    assert latest is not None
    if not _is_certified(latest, anderson_settings):
        fail("FULL_CERTIFICATION_GATE_FAILURE", "final full certification failed")
    state = production.S2State(
        time_s=float(old_state.time_s + dt_s),
        temperature_K=latest.auxiliary.temperature_K.copy(),
        conductive_state=latest.auxiliary.conductive_state.copy(),
        branch_memory=latest.auxiliary.branch_memory.copy(),
        device_voltage_V=float(latest.auxiliary.device_voltage_V),
    )
    production.validate_s2_state(state, grid, closure)
    flux = production.reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        state.temperature_K,
        matrix=active_cache.lateral_matrix,
    )
    load_resistance, capacitance = production._circuit_parameters(config)
    ledgers = build_s2_ledgers(
        grid=grid,
        fields=fields,
        old_temperature_K=old_state.temperature_K,
        new_temperature_K=state.temperature_K,
        old_device_voltage_V=old_state.device_voltage_V,
        new_device_voltage_V=state.device_voltage_V,
        input_voltage_V=float(input_voltage_V),
        load_resistance_ohm=load_resistance,
        capacitance_F=capacitance,
        dt_s=float(dt_s),
        electrical=latest.auxiliary.electrical,
        lateral_boundary_outflow_W=flux.boundary_outflow_W,
    )
    certification_wall = perf_counter() - certification_started
    step = production.S2StepResult(
        state=state,
        electrical=latest.auxiliary.electrical,
        ledgers=ledgers,
        lateral_flux=flux,
        nonlinear=production.S2NonlinearDiagnostics(
            method=SOLVER_ID,
            iterations=int(counters.iterations),
            scaled_residual_inf=float(latest.full_scaled_residual_inf),
            scaled_update_inf=float(latest.full_fixed_point_defect_inf),
            converged=True,
            krylov_matvecs=0,
            armijo_backtracks=0,
            predictor_picard_iterations=0,
            fallback_picard_iterations=0,
        ),
    )
    telemetry = _telemetry(
        status="PASS",
        code=None,
        message=None,
        counters=counters,
        predictor_wall_s=predictor_wall,
        certification_wall_s=certification_wall,
        total_wall_s=perf_counter() - started,
        latest=latest,
    )
    return exact_v1.ExactCondensedStepOutcome(  # type: ignore[arg-type]
        step=step,
        telemetry=telemetry,
    )


__all__ = [
    "DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS",
    "SOLVER_ID",
    "SafeguardedAndersonRootTelemetry",
    "SafeguardedAndersonSettings",
    "_run_safeguarded_iterations",
    "solve_exact_condensed_safeguarded_anderson_step",
]
