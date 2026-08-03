"""Exact auxiliary-state condensation for the active S2 electrothermal model.

This module is deliberately independent of the historical implicit and NLS-v1
orchestration.  It reuses their frozen production residual and ledger
definitions, but solves only the temperature block.  For each temperature
iterate the branch memory, conductive state, circuit voltage, and electrical
fields are reconstructed algebraically.

The implementation has one nonlinear strategy.  Predictor, preconditioner,
Newton, Krylov, and line-search failures are fail-closed; there is no Picard,
portfolio, or cross-implementation fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

import numpy as np
from scipy.sparse.linalg import LinearOperator, lgmres

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_ledgers import build_s2_ledgers
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_2p5d_fvm import SheetElectricalSolution


@dataclass(frozen=True)
class ExactCondensedSettings:
    maximum_newton_iterations: int = 30
    maximum_krylov_matvecs: int = 512
    maximum_reduced_residual_evaluations: int = 640
    maximum_line_search_backtracks: int = 7
    armijo_c1: float = 1.0e-4
    minimum_damping: float = 1.0 / 128.0
    lgmres_inner_m: int = 30
    lgmres_outer_k: int = 10
    lgmres_rtol: float = 1.0e-4
    lgmres_atol: float = 0.0
    reduced_residual_tolerance: float = 1.0e-8
    full_residual_tolerance: float = 1.0e-8
    full_fixed_point_defect_tolerance: float = 1.0e-8
    auxiliary_residual_tolerance: float = 1.0e-12

    def validate(self) -> None:
        integer_values = (
            self.maximum_newton_iterations,
            self.maximum_krylov_matvecs,
            self.maximum_reduced_residual_evaluations,
            self.maximum_line_search_backtracks,
            self.lgmres_inner_m,
            self.lgmres_outer_k,
        )
        if any(int(value) != value or value <= 0 for value in integer_values):
            raise ValueError("exact-condensed integer budgets must be positive")
        values = np.asarray(
            [
                self.armijo_c1,
                self.minimum_damping,
                self.lgmres_rtol,
                self.lgmres_atol,
                self.reduced_residual_tolerance,
                self.full_residual_tolerance,
                self.full_fixed_point_defect_tolerance,
                self.auxiliary_residual_tolerance,
            ],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("exact-condensed settings must be finite")
        if not 0.0 < self.armijo_c1 < 1.0:
            raise ValueError("Armijo c1 must lie in (0,1)")
        if not 0.0 < self.minimum_damping <= 1.0:
            raise ValueError("minimum damping must lie in (0,1]")
        if self.lgmres_rtol <= 0.0 or self.lgmres_atol != 0.0:
            raise ValueError("locked LGMRES tolerances are rtol>0 and atol=0")
        if np.any(values[4:] <= 0.0):
            raise ValueError("exact-condensed certification gates must be positive")


DEFAULT_EXACT_CONDENSED_SETTINGS = ExactCondensedSettings()


@dataclass(frozen=True)
class ExactAuxiliaryState:
    temperature_K: np.ndarray
    conductive_state: np.ndarray
    branch_memory: np.ndarray
    device_voltage_V: float
    conductivity_S_m: np.ndarray
    unit_electrical: SheetElectricalSolution
    electrical: SheetElectricalSolution
    full_vector: np.ndarray
    full_scaled_residual: np.ndarray
    raw_thermal_residual_W_per_cell: np.ndarray

    @property
    def temperature_scaled_residual(self) -> np.ndarray:
        cells = self.temperature_K.size
        return self.full_scaled_residual[:cells]

    @property
    def auxiliary_scaled_residual_inf(self) -> float:
        cells = self.temperature_K.size
        auxiliary = self.full_scaled_residual[cells:]
        return float(np.max(np.abs(auxiliary)))


@dataclass(frozen=True)
class ExactCondensedRootTelemetry:
    status: str
    failure_code: str | None
    failure_message: str | None
    newton_iterations: int
    lgmres_calls: int
    krylov_matvecs: int
    reduced_residual_evaluations: int
    line_search_backtracks: int
    last_newton_update_inf: float
    reduced_residual_inf: float
    full_scaled_residual_inf: float
    full_fixed_point_defect_inf: float
    auxiliary_scaled_residual_inf: float
    raw_thermal_residual_inf_W_per_cell: float
    reduced_residual_history_inf: tuple[float, ...]
    accepted_damping_history: tuple[float, ...]
    lgmres_info_history: tuple[int, ...]
    predictor_wall_s: float
    residual_wall_s: float
    lgmres_wall_s: float
    line_search_wall_s: float
    certification_wall_s: float
    total_wall_s: float


@dataclass(frozen=True)
class ExactCondensedStepOutcome:
    step: production.S2StepResult
    telemetry: ExactCondensedRootTelemetry


class ExactCondensedRootFailure(RuntimeError):
    """Structured fail-closed termination of one reduced root."""

    def __init__(self, code: str, message: str, telemetry: ExactCondensedRootTelemetry):
        super().__init__(message)
        self.code = str(code)
        self.telemetry = telemetry


@dataclass
class _RootCounters:
    residual_evaluations: int = 0
    krylov_matvecs: int = 0
    lgmres_calls: int = 0
    backtracks: int = 0
    residual_wall_s: float = 0.0
    lgmres_wall_s: float = 0.0
    line_search_wall_s: float = 0.0
    residual_history: list[float] = field(default_factory=list)
    damping_history: list[float] = field(default_factory=list)
    lgmres_info_history: list[int] = field(default_factory=list)


def _thermal_terms(
    temperature_K: np.ndarray,
    *,
    old_state: production.S2State,
    electrical: SheetElectricalSolution,
    dt_s: float,
    grid: GeoPhaseGrid,
    fields: S2ThermalFields,
    lateral_matrix,
) -> tuple[np.ndarray, np.ndarray]:
    area = grid.cell_area_m2
    capacity_cell = fields.effective_areal_capacity_J_m2K.reshape(-1) * area
    sink_cell = fields.vertical_conductance_W_m2K * area
    flat_temperature = np.asarray(temperature_K, dtype=float).reshape(-1)
    raw = (
        capacity_cell
        * (flat_temperature - old_state.temperature_K.reshape(-1))
        / dt_s
        + lateral_matrix @ flat_temperature
        + sink_cell * (flat_temperature - fields.ambient_temperature_K)
        - electrical.cell_joule_power_W.reshape(-1)
    )
    temperature_scale_K = max(
        float(np.max(np.abs(temperature_K - old_state.temperature_K))),
        float(np.max(np.abs(temperature_K - fields.ambient_temperature_K))),
        1.0,
    )
    scale = np.maximum(
        capacity_cell / dt_s
        + np.asarray(lateral_matrix.diagonal(), dtype=float)
        + sink_cell,
        1.0e-18,
    ) * temperature_scale_K
    return np.asarray(raw, dtype=float), np.asarray(scale, dtype=float)


def reconstruct_exact_auxiliary_state(
    temperature_K: np.ndarray,
    old_state: production.S2State,
    dt_s: float,
    input_voltage_V: float,
    *,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: production.S2SolverCache,
    performance_timings: production.S2PerformanceTimings | None = None,
) -> ExactAuxiliaryState:
    """Exactly reconstruct ``b``, ``s``, ``Vd``, and electrical fields.

    The returned full residual is evaluated by the frozen production residual;
    this function does not carry a handwritten mirror of its scaled equations.
    """

    temperature = np.asarray(temperature_K, dtype=float)
    if temperature.shape != grid.shape:
        raise ValueError("candidate temperature must match the active grid")
    if not np.isfinite(temperature).all():
        raise ValueError("candidate temperature must be finite")
    if not np.isfinite([dt_s, input_voltage_V]).all() or dt_s <= 0.0:
        raise ValueError("input voltage and positive dt must be finite")
    production.validate_s2_state(old_state, grid, closure)
    fields.validate_grid(grid)
    cache.validate_context(grid, fields)
    closure.validate_temperature(temperature)

    heating, cooling = closure.branch_activations(
        temperature, old_state.temperature_K, dt_s
    )
    ratio_b = dt_s / closure.branch_relaxation_s
    branch = (
        old_state.branch_memory + ratio_b * (heating - cooling)
    ) / (1.0 + ratio_b * (heating + cooling))
    equilibrium = closure.equilibrium_state(temperature, branch)
    ratio_s = dt_s / closure.state_relaxation_s
    conductive = (
        old_state.conductive_state + ratio_s * equilibrium
    ) / (1.0 + ratio_s)

    conductivity = closure.conductivity_S_m(temperature, conductive)
    unit_electrical, _ = production._electrical_unit_and_actual(
        grid=grid,
        conductivity_S_m=conductivity,
        actual_voltage_V=1.0,
        topology=cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=performance_timings,
    )
    load_resistance_ohm, capacitance_F = production._circuit_parameters(config)
    denominator = (
        capacitance_F / dt_s
        + 1.0 / load_resistance_ohm
        + unit_electrical.source_current_A
    )
    if not np.isfinite(denominator) or denominator <= 0.0:
        raise FloatingPointError("exact circuit reconstruction denominator is invalid")
    voltage = (
        capacitance_F / dt_s * old_state.device_voltage_V
        + input_voltage_V / load_resistance_ohm
    ) / denominator
    electrical = production.scale_unit_sheet_electrical_solution(
        unit_electrical, voltage
    )
    vector = production._pack(temperature, conductive, branch, voltage)
    full_residual = production._scaled_residual(
        vector,
        old_state=old_state,
        input_voltage_V=float(input_voltage_V),
        dt_s=float(dt_s),
        grid=grid,
        closure=closure,
        fields=fields,
        lateral_matrix=cache.lateral_matrix,
        thermal_linear_solver=None,
        electrical_topology=cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=performance_timings,
        load_resistance_ohm=load_resistance_ohm,
        capacitance_F=capacitance_F,
    )
    raw_thermal, _ = _thermal_terms(
        temperature,
        old_state=old_state,
        electrical=electrical,
        dt_s=dt_s,
        grid=grid,
        fields=fields,
        lateral_matrix=cache.lateral_matrix,
    )
    return ExactAuxiliaryState(
        temperature_K=temperature.copy(),
        conductive_state=np.asarray(conductive, dtype=float),
        branch_memory=np.asarray(branch, dtype=float),
        device_voltage_V=float(voltage),
        conductivity_S_m=np.asarray(conductivity, dtype=float),
        unit_electrical=unit_electrical,
        electrical=electrical,
        full_vector=np.asarray(vector, dtype=float),
        full_scaled_residual=np.asarray(full_residual, dtype=float),
        raw_thermal_residual_W_per_cell=raw_thermal,
    )


def _relative_full_defect(
    vector: np.ndarray,
    *,
    old_state: production.S2State,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: production.S2SolverCache,
    performance_timings: production.S2PerformanceTimings | None,
) -> float:
    load, capacitance = production._circuit_parameters(config)
    mapped = production._fixed_point_map(
        vector,
        old_state=old_state,
        input_voltage_V=float(input_voltage_V),
        dt_s=float(dt_s),
        grid=grid,
        closure=closure,
        fields=fields,
        lateral_matrix=cache.lateral_matrix,
        thermal_linear_solver=cache.thermal_solver(dt_s),
        electrical_topology=cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=performance_timings,
        load_resistance_ohm=load,
        capacitance_F=capacitance,
    )
    return float(
        np.max(
            np.abs(np.asarray(mapped, dtype=float) - vector)
            / np.maximum(np.abs(vector), 1.0)
        )
    )


def _predict_temperature(
    *,
    old_state: production.S2State,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: production.S2SolverCache,
    performance_timings: production.S2PerformanceTimings | None,
) -> np.ndarray:
    frozen = reconstruct_exact_auxiliary_state(
        old_state.temperature_K,
        old_state,
        dt_s,
        input_voltage_V,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=cache,
        performance_timings=performance_timings,
    )
    area = grid.cell_area_m2
    capacity_cell = fields.effective_areal_capacity_J_m2K.reshape(-1) * area
    sink_cell = fields.vertical_conductance_W_m2K * area
    rhs = (
        capacity_cell / dt_s * old_state.temperature_K.reshape(-1)
        + sink_cell * fields.ambient_temperature_K
        + frozen.electrical.cell_joule_power_W.reshape(-1)
    )
    predictor = cache.thermal_solver(dt_s)(rhs).reshape(grid.shape)
    closure.validate_temperature(predictor)
    return predictor


def _failure_telemetry(
    *,
    code: str,
    message: str,
    counters: _RootCounters,
    newton_iterations: int,
    last_update: float,
    reduced_residual: float,
    predictor_wall_s: float,
    certification_wall_s: float,
    total_wall_s: float,
    auxiliary: ExactAuxiliaryState | None = None,
    full_defect: float = float("inf"),
) -> ExactCondensedRootTelemetry:
    return ExactCondensedRootTelemetry(
        status="FAIL",
        failure_code=str(code),
        failure_message=str(message),
        newton_iterations=int(newton_iterations),
        lgmres_calls=int(counters.lgmres_calls),
        krylov_matvecs=int(counters.krylov_matvecs),
        reduced_residual_evaluations=int(counters.residual_evaluations),
        line_search_backtracks=int(counters.backtracks),
        last_newton_update_inf=float(last_update),
        reduced_residual_inf=float(reduced_residual),
        full_scaled_residual_inf=(
            float("inf")
            if auxiliary is None
            else float(np.max(np.abs(auxiliary.full_scaled_residual)))
        ),
        full_fixed_point_defect_inf=float(full_defect),
        auxiliary_scaled_residual_inf=(
            float("inf")
            if auxiliary is None
            else auxiliary.auxiliary_scaled_residual_inf
        ),
        raw_thermal_residual_inf_W_per_cell=(
            float("inf")
            if auxiliary is None
            else float(np.max(np.abs(auxiliary.raw_thermal_residual_W_per_cell)))
        ),
        reduced_residual_history_inf=tuple(counters.residual_history),
        accepted_damping_history=tuple(counters.damping_history),
        lgmres_info_history=tuple(counters.lgmres_info_history),
        predictor_wall_s=float(predictor_wall_s),
        residual_wall_s=float(counters.residual_wall_s),
        lgmres_wall_s=float(counters.lgmres_wall_s),
        line_search_wall_s=float(counters.line_search_wall_s),
        certification_wall_s=float(certification_wall_s),
        total_wall_s=float(total_wall_s),
    )


def solve_exact_condensed_step(
    old_state: production.S2State,
    *,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: production.S2SolverCache | None = None,
    settings: ExactCondensedSettings = DEFAULT_EXACT_CONDENSED_SETTINGS,
    performance_timings: production.S2PerformanceTimings | None = None,
) -> ExactCondensedStepOutcome:
    """Solve one S2 backward-Euler step through exact block condensation."""

    started = perf_counter()
    settings.validate()
    if not np.isfinite([input_voltage_V, dt_s]).all() or dt_s <= 0.0:
        raise ValueError("input voltage and positive dt must be finite")
    production.validate_s2_state(old_state, grid, closure)
    fields.validate_grid(grid)
    active_cache = cache or production.build_s2_solver_cache(grid, fields)
    active_cache.validate_context(grid, fields)
    equilibrium = closure.equilibrium_state(
        old_state.temperature_K, old_state.branch_memory
    )
    exact_zero_equilibrium = (
        float(input_voltage_V) == 0.0
        and old_state.device_voltage_V == 0.0
        and np.array_equal(
            old_state.temperature_K,
            np.full(grid.shape, fields.ambient_temperature_K, dtype=float),
        )
        and np.array_equal(old_state.conductive_state, equilibrium)
    )
    if exact_zero_equilibrium:
        conductivity = closure.conductivity_S_m(
            old_state.temperature_K, old_state.conductive_state
        )
        electrical = production._electrical_actual_only(
            grid=grid,
            conductivity_S_m=conductivity,
            actual_voltage_V=0.0,
            topology=active_cache.electrical_topology,
            use_equivalent_optimizations=True,
            performance_timings=performance_timings,
        )
        flux = production.reconstruct_lateral_fluxes(
            grid,
            fields.sheet_thermal_conductance_W_K,
            old_state.temperature_K,
            matrix=active_cache.lateral_matrix,
        )
        state = production.S2State(
            time_s=float(old_state.time_s + dt_s),
            temperature_K=old_state.temperature_K.copy(),
            conductive_state=old_state.conductive_state.copy(),
            branch_memory=old_state.branch_memory.copy(),
            device_voltage_V=0.0,
        )
        load, capacitance = production._circuit_parameters(config)
        ledgers = build_s2_ledgers(
            grid=grid,
            fields=fields,
            old_temperature_K=old_state.temperature_K,
            new_temperature_K=state.temperature_K,
            old_device_voltage_V=old_state.device_voltage_V,
            new_device_voltage_V=0.0,
            input_voltage_V=0.0,
            load_resistance_ohm=load,
            capacitance_F=capacitance,
            dt_s=dt_s,
            electrical=electrical,
            lateral_boundary_outflow_W=flux.boundary_outflow_W,
        )
        step = production.S2StepResult(
            state=state,
            electrical=electrical,
            ledgers=ledgers,
            lateral_flux=flux,
            nonlinear=production.S2NonlinearDiagnostics(
                method="exact_condensed_analytic_zero_drive_equilibrium",
                iterations=0,
                scaled_residual_inf=0.0,
                scaled_update_inf=0.0,
                converged=True,
                krylov_matvecs=0,
                armijo_backtracks=0,
                predictor_picard_iterations=0,
                fallback_picard_iterations=0,
            ),
        )
        telemetry = ExactCondensedRootTelemetry(
            status="PASS",
            failure_code=None,
            failure_message=None,
            newton_iterations=0,
            lgmres_calls=0,
            krylov_matvecs=0,
            reduced_residual_evaluations=0,
            line_search_backtracks=0,
            last_newton_update_inf=0.0,
            reduced_residual_inf=0.0,
            full_scaled_residual_inf=0.0,
            full_fixed_point_defect_inf=0.0,
            auxiliary_scaled_residual_inf=0.0,
            raw_thermal_residual_inf_W_per_cell=0.0,
            reduced_residual_history_inf=(),
            accepted_damping_history=(),
            lgmres_info_history=(),
            predictor_wall_s=0.0,
            residual_wall_s=0.0,
            lgmres_wall_s=0.0,
            line_search_wall_s=0.0,
            certification_wall_s=0.0,
            total_wall_s=float(perf_counter() - started),
        )
        return ExactCondensedStepOutcome(step=step, telemetry=telemetry)
    counters = _RootCounters()
    predictor_wall = 0.0
    certification_wall = 0.0
    newton_iteration = 0
    last_update = 0.0
    residual_inf = float("inf")
    latest_auxiliary: ExactAuxiliaryState | None = None

    def fail(code: str, message: str, *, defect: float = float("inf")) -> None:
        telemetry = _failure_telemetry(
            code=code,
            message=message,
            counters=counters,
            newton_iterations=newton_iteration,
            last_update=last_update,
            reduced_residual=residual_inf,
            predictor_wall_s=predictor_wall,
            certification_wall_s=certification_wall,
            total_wall_s=perf_counter() - started,
            auxiliary=latest_auxiliary,
            full_defect=defect,
        )
        raise ExactCondensedRootFailure(code, message, telemetry)

    predictor_started = perf_counter()
    try:
        temperature = _predict_temperature(
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
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        predictor_wall = perf_counter() - predictor_started
        fail("PREDICTOR_FAILURE", str(error))
    predictor_wall = perf_counter() - predictor_started

    def evaluate(candidate: np.ndarray) -> ExactAuxiliaryState:
        if counters.residual_evaluations >= settings.maximum_reduced_residual_evaluations:
            fail(
                "REDUCED_RESIDUAL_BUDGET_EXHAUSTED",
                "reduced residual evaluation 641 was blocked",
            )
        counters.residual_evaluations += 1
        residual_started = perf_counter()
        try:
            result = reconstruct_exact_auxiliary_state(
                np.asarray(candidate, dtype=float).reshape(grid.shape),
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
        finally:
            counters.residual_wall_s += perf_counter() - residual_started
        return result

    for newton_iteration in range(0, settings.maximum_newton_iterations + 1):
        try:
            latest_auxiliary = evaluate(temperature)
        except ExactCondensedRootFailure:
            raise
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            fail("REDUCED_RESIDUAL_FAILURE", str(error))
        residual = latest_auxiliary.temperature_scaled_residual.reshape(-1)
        residual_inf = float(np.max(np.abs(residual)))
        residual_merit = 0.5 * float(np.dot(residual, residual))
        counters.residual_history.append(residual_inf)
        if residual_inf <= settings.reduced_residual_tolerance:
            break
        if newton_iteration >= settings.maximum_newton_iterations:
            fail("NEWTON_ITERATION_BUDGET_EXHAUSTED", "Newton iteration 31 was blocked")

        flat_temperature = temperature.reshape(-1).copy()
        _, thermal_scale = _thermal_terms(
            temperature,
            old_state=old_state,
            electrical=latest_auxiliary.electrical,
            dt_s=dt_s,
            grid=grid,
            fields=fields,
            lateral_matrix=active_cache.lateral_matrix,
        )

        def precondition(vector: np.ndarray) -> np.ndarray:
            values = np.asarray(vector, dtype=float)
            return active_cache.thermal_solver(dt_s)(thermal_scale * values)

        preconditioner = LinearOperator(
            shape=(flat_temperature.size, flat_temperature.size),
            matvec=precondition,
            dtype=float,
        )
        rdiff = np.finfo(float).eps ** 0.5
        omega = rdiff * max(1.0, float(np.max(np.abs(flat_temperature)))) / max(
            1.0, residual_inf
        )

        def jacobian_vector(vector: np.ndarray) -> np.ndarray:
            if counters.krylov_matvecs >= settings.maximum_krylov_matvecs:
                fail("KRYLOV_MATVEC_BUDGET_EXHAUSTED", "Krylov matvec 513 was blocked")
            values = np.asarray(vector, dtype=float)
            norm = float(np.linalg.norm(values))
            if norm == 0.0:
                return np.zeros_like(values)
            counters.krylov_matvecs += 1
            scale = omega / norm
            candidate = flat_temperature + scale * values
            try:
                shifted = evaluate(candidate).temperature_scaled_residual.reshape(-1)
            except ExactCondensedRootFailure:
                raise
            except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                fail("KRYLOV_RESIDUAL_FAILURE", str(error))
            result = (shifted - residual) / scale
            if not np.isfinite(result).all():
                fail("KRYLOV_NONFINITE", "finite-difference Jacobian product is nonfinite")
            return result

        remaining = settings.maximum_krylov_matvecs - counters.krylov_matvecs
        if remaining <= 1:
            fail("KRYLOV_MATVEC_BUDGET_EXHAUSTED", "insufficient matvec budget for LGMRES")
        inner_m = min(settings.lgmres_inner_m, max(1, remaining - 1))
        dynamic_maxiter = max(1, remaining // (inner_m + 1))
        jacobian = LinearOperator(
            shape=(flat_temperature.size, flat_temperature.size),
            matvec=jacobian_vector,
            dtype=float,
        )
        lgmres_started = perf_counter()
        counters.lgmres_calls += 1
        try:
            correction, info = lgmres(
                jacobian,
                -residual,
                M=preconditioner,
                inner_m=inner_m,
                outer_k=settings.lgmres_outer_k,
                maxiter=dynamic_maxiter,
                rtol=settings.lgmres_rtol,
                atol=settings.lgmres_atol,
            )
        except ExactCondensedRootFailure:
            raise
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            counters.lgmres_wall_s += perf_counter() - lgmres_started
            fail("LGMRES_FAILURE", str(error))
        counters.lgmres_wall_s += perf_counter() - lgmres_started
        counters.lgmres_info_history.append(int(info))
        correction = np.asarray(correction, dtype=float)
        if info != 0 or not np.isfinite(correction).all():
            fail("LGMRES_NOT_CONVERGED", f"LGMRES returned info={info}")

        line_started = perf_counter()
        accepted_temperature: np.ndarray | None = None
        accepted_auxiliary: ExactAuxiliaryState | None = None
        accepted_damping = 0.0
        for backtrack in range(settings.maximum_line_search_backtracks + 1):
            damping = 0.5**backtrack
            if damping < settings.minimum_damping:
                break
            trial = flat_temperature + damping * correction
            try:
                trial_auxiliary = evaluate(trial)
            except ExactCondensedRootFailure:
                raise
            except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
                trial_auxiliary = None
            if trial_auxiliary is not None:
                trial_vector = trial_auxiliary.temperature_scaled_residual.reshape(-1)
                trial_merit = 0.5 * float(np.dot(trial_vector, trial_vector))
                if trial_merit <= (
                    1.0 - settings.armijo_c1 * damping
                ) * residual_merit:
                    accepted_temperature = trial.reshape(grid.shape)
                    accepted_auxiliary = trial_auxiliary
                    accepted_damping = damping
                    counters.backtracks += backtrack
                    break
        counters.line_search_wall_s += perf_counter() - line_started
        if accepted_temperature is None or accepted_auxiliary is None:
            fail("ARMIJO_LINE_SEARCH_FAILURE", "no damping in [1,1/128] passed Armijo")
        last_update = float(
            np.max(
                np.abs(accepted_damping * correction)
                / np.maximum(np.abs(accepted_temperature.reshape(-1)), 1.0)
            )
        )
        counters.damping_history.append(float(accepted_damping))
        temperature = accepted_temperature
        latest_auxiliary = accepted_auxiliary

    assert latest_auxiliary is not None
    certification_started = perf_counter()
    try:
        full_defect = _relative_full_defect(
            latest_auxiliary.full_vector,
            old_state=old_state,
            input_voltage_V=input_voltage_V,
            dt_s=dt_s,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            cache=active_cache,
            performance_timings=performance_timings,
        )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        certification_wall = perf_counter() - certification_started
        fail("FULL_DEFECT_CERTIFICATION_FAILURE", str(error))
    full_residual_inf = float(
        np.max(np.abs(latest_auxiliary.full_scaled_residual))
    )
    auxiliary_inf = latest_auxiliary.auxiliary_scaled_residual_inf
    certification_wall = perf_counter() - certification_started
    failures: list[str] = []
    if residual_inf > settings.reduced_residual_tolerance:
        failures.append("reduced residual")
    if full_residual_inf > settings.full_residual_tolerance:
        failures.append("full residual")
    if full_defect > settings.full_fixed_point_defect_tolerance:
        failures.append("full fixed-point defect")
    if auxiliary_inf > settings.auxiliary_residual_tolerance:
        failures.append("auxiliary residual")
    if failures:
        fail(
            "FULL_CERTIFICATION_GATE_FAILURE",
            "failed exact-condensed gate(s): " + ", ".join(failures),
            defect=full_defect,
        )

    state = production.S2State(
        time_s=float(old_state.time_s + dt_s),
        temperature_K=latest_auxiliary.temperature_K.copy(),
        conductive_state=latest_auxiliary.conductive_state.copy(),
        branch_memory=latest_auxiliary.branch_memory.copy(),
        device_voltage_V=float(latest_auxiliary.device_voltage_V),
    )
    production.validate_s2_state(state, grid, closure)
    flux = production.reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        state.temperature_K,
        matrix=active_cache.lateral_matrix,
    )
    load, capacitance = production._circuit_parameters(config)
    ledgers = build_s2_ledgers(
        grid=grid,
        fields=fields,
        old_temperature_K=old_state.temperature_K,
        new_temperature_K=state.temperature_K,
        old_device_voltage_V=old_state.device_voltage_V,
        new_device_voltage_V=state.device_voltage_V,
        input_voltage_V=float(input_voltage_V),
        load_resistance_ohm=load,
        capacitance_F=capacitance,
        dt_s=float(dt_s),
        electrical=latest_auxiliary.electrical,
        lateral_boundary_outflow_W=flux.boundary_outflow_W,
    )
    step = production.S2StepResult(
        state=state,
        electrical=latest_auxiliary.electrical,
        ledgers=ledgers,
        lateral_flux=flux,
        nonlinear=production.S2NonlinearDiagnostics(
            method="exact_condensed_damped_newton_lgmres",
            iterations=int(newton_iteration),
            scaled_residual_inf=full_residual_inf,
            scaled_update_inf=float(full_defect),
            converged=True,
            krylov_matvecs=int(counters.krylov_matvecs),
            armijo_backtracks=int(counters.backtracks),
            predictor_picard_iterations=0,
            fallback_picard_iterations=0,
        ),
    )
    telemetry = ExactCondensedRootTelemetry(
        status="PASS",
        failure_code=None,
        failure_message=None,
        newton_iterations=int(newton_iteration),
        lgmres_calls=int(counters.lgmres_calls),
        krylov_matvecs=int(counters.krylov_matvecs),
        reduced_residual_evaluations=int(counters.residual_evaluations),
        line_search_backtracks=int(counters.backtracks),
        last_newton_update_inf=float(last_update),
        reduced_residual_inf=float(residual_inf),
        full_scaled_residual_inf=full_residual_inf,
        full_fixed_point_defect_inf=float(full_defect),
        auxiliary_scaled_residual_inf=float(auxiliary_inf),
        raw_thermal_residual_inf_W_per_cell=float(
            np.max(np.abs(latest_auxiliary.raw_thermal_residual_W_per_cell))
        ),
        reduced_residual_history_inf=tuple(counters.residual_history),
        accepted_damping_history=tuple(counters.damping_history),
        lgmres_info_history=tuple(counters.lgmres_info_history),
        predictor_wall_s=float(predictor_wall),
        residual_wall_s=float(counters.residual_wall_s),
        lgmres_wall_s=float(counters.lgmres_wall_s),
        line_search_wall_s=float(counters.line_search_wall_s),
        certification_wall_s=float(certification_wall),
        total_wall_s=float(perf_counter() - started),
    )
    return ExactCondensedStepOutcome(step=step, telemetry=telemetry)


__all__ = [
    "DEFAULT_EXACT_CONDENSED_SETTINGS",
    "ExactAuxiliaryState",
    "ExactCondensedRootFailure",
    "ExactCondensedRootTelemetry",
    "ExactCondensedSettings",
    "ExactCondensedStepOutcome",
    "reconstruct_exact_auxiliary_state",
    "solve_exact_condensed_step",
]
