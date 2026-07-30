"""Isolated implicit electrothermal solver for the Phase 1-v2 S2 closure.

The module shares continuous device parameters, geometry, the conservative
electrical flux solve, and the white-box VO2 closure with the historical
reference implementation. It does not import or emulate the retired vertical
material-stack/K-state solver and it has no thermal-memory state variable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

import numpy as np
from scipy.optimize import KrylovJacobian

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_ledgers import S2LedgerBundle, build_s2_ledgers
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_2p5d_fvm import (
    SheetElectricalSolution,
    SheetElectricalTopology,
    build_sheet_electrical_topology,
    factor_sheet_electrical,
    solve_sheet_electrical,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    LateralFluxAudit,
    ThermalLinearSolver,
    assemble_sheet_thermal_matrix,
    build_s2_thermal_backward_euler_solver,
    reconstruct_lateral_fluxes,
    scale_unit_sheet_electrical_solution,
    solve_s2_thermal_backward_euler,
)


@dataclass(frozen=True)
class S2State:
    time_s: float
    temperature_K: np.ndarray
    conductive_state: np.ndarray
    branch_memory: np.ndarray
    device_voltage_V: float


@dataclass(frozen=True)
class S2NonlinearDiagnostics:
    method: str
    iterations: int
    scaled_residual_inf: float
    scaled_update_inf: float
    converged: bool
    krylov_matvecs: int
    armijo_backtracks: int
    predictor_picard_iterations: int
    fallback_picard_iterations: int


@dataclass(frozen=True)
class S2StepResult:
    state: S2State
    electrical: SheetElectricalSolution
    ledgers: S2LedgerBundle
    lateral_flux: LateralFluxAudit
    nonlinear: S2NonlinearDiagnostics


@dataclass(frozen=True)
class S2AttemptObservation:
    """Read-only telemetry for one adaptive-controller candidate attempt."""

    previous_state: S2State
    candidate: S2StepResult | None
    dt_s: float
    input_voltage_V: float
    candidate_wall_time_s: float
    rejection_index: int
    endpoint_remainder: bool
    at_locked_floor: bool
    conductive_increment: float | None
    branch_increment: float | None
    transition_increment: float | None
    transition_threshold: float
    error_class: str | None
    error_message: str | None


@dataclass(frozen=True)
class S2AdaptiveDiagnostics:
    accepted_steps: int
    rejected_steps: int
    transition_rejections: int
    nonlinear_rejections: int
    endpoint_remainder_steps: int
    minimum_accepted_step_s: float
    maximum_accepted_step_s: float
    maximum_transition_increment: float
    fallback_steps: int
    newton_iterations: int
    krylov_matvecs: int
    armijo_backtracks: int
    fallback_picard_iterations: int
    step_wall_time_p50_s: float
    step_wall_time_p90_s: float
    step_wall_time_max_s: float
    accepted_dt_p10_s: float
    accepted_dt_p50_s: float
    accepted_dt_p90_s: float


@dataclass(frozen=True)
class S2ProtocolResult:
    steps: tuple[S2StepResult, ...]
    diagnostics: S2AdaptiveDiagnostics
    requested_final_time_s: float
    achieved_final_time_s: float
    completed: bool
    stop_reason: str


PERFORMANCE_TIMING_SEMANTICS = (
    "hierarchical_nonadditive_use_observed_sample_wall_time_for_forecast"
)


@dataclass
class S2PerformanceTimings:
    """Hierarchical, non-additive telemetry for repair bottleneck diagnosis."""

    electrical_assembly_wall_s: float = 0.0
    factorization_wall_s: float = 0.0
    linear_solves_wall_s: float = 0.0
    Joule_port_postprocess_wall_s: float = 0.0
    Picard_predictor_wall_s: float = 0.0
    Newton_Krylov_wall_s: float = 0.0
    fallback_wall_s: float = 0.0

    def add(self, name: str, elapsed_s: float) -> None:
        if name not in self.__dataclass_fields__:
            raise ValueError(f"undeclared S2 performance timing field: {name}")
        elapsed = float(elapsed_s)
        if not np.isfinite(elapsed) or elapsed < 0.0:
            raise ValueError("S2 performance timing must be finite and nonnegative")
        setattr(self, name, float(getattr(self, name)) + elapsed)

    def as_dict(self) -> dict[str, float]:
        return {
            name: float(getattr(self, name)) for name in self.__dataclass_fields__
        }


@dataclass
class S2SolverCache:
    """Case-local invariant sparse structures and exact-dt factorizations."""

    grid: GeoPhaseGrid
    fields: S2ThermalFields
    lateral_matrix: object
    electrical_topology: SheetElectricalTopology
    thermal_linear_solvers: dict[float, ThermalLinearSolver] = field(
        default_factory=dict
    )

    def validate_context(self, grid: GeoPhaseGrid, fields: S2ThermalFields) -> None:
        if self.grid is not grid or self.fields is not fields:
            raise ValueError(
                "S2 cache cannot cross geometry, grid, or thermal-field context"
            )

    def thermal_solver(self, dt_s: float) -> ThermalLinearSolver:
        key = float(dt_s)
        solver = self.thermal_linear_solvers.get(key)
        if solver is None:
            solver = build_s2_thermal_backward_euler_solver(
                self.grid,
                self.fields,
                key,
                lateral_matrix=self.lateral_matrix,
            )
            self.thermal_linear_solvers[key] = solver
        return solver


def build_s2_solver_cache(
    grid: GeoPhaseGrid, fields: S2ThermalFields
) -> S2SolverCache:
    """Create one cache that is intentionally scoped to a single case."""

    fields.validate_grid(grid)
    lateral = assemble_sheet_thermal_matrix(
        grid, fields.sheet_thermal_conductance_W_K
    )
    return S2SolverCache(
        grid=grid,
        fields=fields,
        lateral_matrix=lateral,
        electrical_topology=build_sheet_electrical_topology(grid),
    )


class _CountingKrylovJacobian(KrylovJacobian):
    """Count Jacobian-vector products used by the locked LGMRES correction."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.matvec_count = 0

    def matvec(self, vector):
        self.matvec_count += 1
        return super().matvec(vector)


def initial_s2_state(
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
) -> S2State:
    fields.validate_grid(grid)
    initial = config["formal_protocols"]["common_initial_state"]
    temperature_value = float(initial["active_temperature_K"])
    branch_value = float(initial["branch_memory_b"])
    voltage = float(initial["device_voltage_V"])
    temperature = np.full(grid.shape, temperature_value, dtype=float)
    branch = np.full(grid.shape, branch_value, dtype=float)
    conductive = closure.equilibrium_state(temperature, branch)
    state = S2State(
        time_s=float(config["reference_solver"]["time_grid"]["initial_time_s"]),
        temperature_K=temperature,
        conductive_state=conductive,
        branch_memory=branch,
        device_voltage_V=voltage,
    )
    validate_s2_state(state, grid, closure)
    return state


def validate_s2_state(
    state: S2State, grid: GeoPhaseGrid, closure: EffectiveVO2Closure
) -> None:
    arrays = (state.temperature_K, state.conductive_state, state.branch_memory)
    if any(np.asarray(array).shape != grid.shape for array in arrays):
        raise ValueError("S2 state fields must match the grid")
    if any(not np.isfinite(np.asarray(array, dtype=float)).all() for array in arrays):
        raise ValueError("S2 state contains a nonfinite field")
    if not np.isfinite([state.time_s, state.device_voltage_V]).all():
        raise ValueError("S2 state scalar is nonfinite")
    closure.validate_temperature(state.temperature_K)
    if np.any(state.conductive_state < 0.0) or np.any(state.conductive_state > 1.0):
        raise ValueError("conductive state is outside [0,1]")
    if np.any(np.abs(state.branch_memory) > 1.0):
        raise ValueError("branch memory is outside [-1,1]")


def _pack(
    temperature_K: np.ndarray,
    conductive_state: np.ndarray,
    branch_memory: np.ndarray,
    device_voltage_V: float,
) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(temperature_K, dtype=float).reshape(-1),
            np.asarray(conductive_state, dtype=float).reshape(-1),
            np.asarray(branch_memory, dtype=float).reshape(-1),
            np.asarray([device_voltage_V], dtype=float),
        ]
    )


def _unpack(vector: np.ndarray, grid: GeoPhaseGrid) -> tuple[np.ndarray, ...]:
    values = np.asarray(vector, dtype=float)
    cells = grid.nx * grid.ny
    if values.shape != (3 * cells + 1,):
        raise ValueError("S2 nonlinear vector has the wrong dimension")
    temperature = values[:cells].reshape(grid.shape)
    conductive = values[cells : 2 * cells].reshape(grid.shape)
    branch = values[2 * cells : 3 * cells].reshape(grid.shape)
    return temperature, conductive, branch, float(values[-1])


def _circuit_parameters(config: dict) -> tuple[float, float]:
    circuit = config["physics_contract"]["circuit"]
    load = float(circuit["load_resistance_ohm"])
    capacitance = float(circuit["parallel_capacitance_F"])
    if not np.isfinite([load, capacitance]).all() or load <= 0.0 or capacitance <= 0.0:
        raise ValueError("S2 circuit parameters must be finite and positive")
    return load, capacitance


def _electrical_unit_and_actual(
    *,
    grid: GeoPhaseGrid,
    conductivity_S_m: np.ndarray,
    actual_voltage_V: float,
    topology: SheetElectricalTopology | None,
    use_equivalent_optimizations: bool,
    use_unit_voltage_scaling: bool,
    performance_timings: S2PerformanceTimings | None,
) -> tuple[SheetElectricalSolution, SheetElectricalSolution]:
    """Solve the unit and actual RHS without sharing a conductivity across calls."""

    if use_equivalent_optimizations:
        factorization = factor_sheet_electrical(
            grid,
            conductivity_S_m,
            topology=topology,
            timing_callback=(
                None if performance_timings is None else performance_timings.add
            ),
        )
        unit = factorization.solve(1.0)
        actual = (
            scale_unit_sheet_electrical_solution(unit, actual_voltage_V)
            if use_unit_voltage_scaling
            else factorization.solve(actual_voltage_V)
        )
        return unit, actual
    unit = solve_sheet_electrical(grid, conductivity_S_m, 1.0)
    actual = (
        scale_unit_sheet_electrical_solution(unit, actual_voltage_V)
        if use_unit_voltage_scaling
        else solve_sheet_electrical(grid, conductivity_S_m, actual_voltage_V)
    )
    return unit, actual


def _electrical_actual_only(
    *,
    grid: GeoPhaseGrid,
    conductivity_S_m: np.ndarray,
    actual_voltage_V: float,
    topology: SheetElectricalTopology | None,
    use_equivalent_optimizations: bool,
    performance_timings: S2PerformanceTimings | None,
) -> SheetElectricalSolution:
    if not use_equivalent_optimizations:
        return solve_sheet_electrical(grid, conductivity_S_m, actual_voltage_V)
    factorization = factor_sheet_electrical(
        grid,
        conductivity_S_m,
        topology=topology,
        timing_callback=(
            None if performance_timings is None else performance_timings.add
        ),
    )
    return factorization.solve(actual_voltage_V)


def _fixed_point_map(
    vector: np.ndarray,
    *,
    old_state: S2State,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    lateral_matrix,
    thermal_linear_solver: ThermalLinearSolver | None,
    electrical_topology: SheetElectricalTopology | None,
    use_equivalent_optimizations: bool,
    use_unit_voltage_scaling: bool,
    performance_timings: S2PerformanceTimings | None,
    load_resistance_ohm: float,
    capacitance_F: float,
) -> np.ndarray:
    temperature, conductive, branch, _ = _unpack(vector, grid)
    conductivity = closure.conductivity_S_m(temperature, conductive)
    factorization = None
    if use_equivalent_optimizations:
        factorization = factor_sheet_electrical(
            grid,
            conductivity,
            topology=electrical_topology,
            timing_callback=(
                None if performance_timings is None else performance_timings.add
            ),
        )
        unit = factorization.solve(1.0)
    else:
        unit = solve_sheet_electrical(grid, conductivity, 1.0)
    device_conductance = unit.source_current_A
    denominator = (
        capacitance_F / dt_s
        + 1.0 / load_resistance_ohm
        + device_conductance
    )
    voltage = (
        capacitance_F / dt_s * old_state.device_voltage_V
        + input_voltage_V / load_resistance_ohm
    ) / denominator
    if use_unit_voltage_scaling:
        electrical = scale_unit_sheet_electrical_solution(unit, voltage)
    elif use_equivalent_optimizations:
        assert factorization is not None
        electrical = factorization.solve(voltage)
    else:
        electrical = solve_sheet_electrical(grid, conductivity, voltage)
    new_temperature = solve_s2_thermal_backward_euler(
        grid,
        fields,
        old_state.temperature_K,
        electrical.cell_joule_power_W,
        dt_s,
        lateral_matrix=lateral_matrix,
        linear_solver=thermal_linear_solver,
    )
    closure.validate_temperature(new_temperature)
    heating, cooling = closure.branch_activations(
        new_temperature, old_state.temperature_K, dt_s
    )
    ratio_b = dt_s / closure.branch_relaxation_s
    new_branch = (
        old_state.branch_memory + ratio_b * (heating - cooling)
    ) / (1.0 + ratio_b * (heating + cooling))
    equilibrium = closure.equilibrium_state(new_temperature, new_branch)
    ratio_s = dt_s / closure.state_relaxation_s
    new_conductive = (
        old_state.conductive_state + ratio_s * equilibrium
    ) / (1.0 + ratio_s)
    return _pack(new_temperature, new_conductive, new_branch, voltage)


def _scaled_residual(
    vector: np.ndarray,
    *,
    old_state: S2State,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    lateral_matrix,
    thermal_linear_solver: ThermalLinearSolver | None,
    electrical_topology: SheetElectricalTopology | None,
    use_equivalent_optimizations: bool,
    use_unit_voltage_scaling: bool,
    performance_timings: S2PerformanceTimings | None,
    load_resistance_ohm: float,
    capacitance_F: float,
) -> np.ndarray:
    temperature, conductive, branch, voltage = _unpack(vector, grid)
    closure.validate_temperature(temperature)
    if np.any(conductive < 0.0) or np.any(conductive > 1.0):
        raise ValueError("S2 nonlinear conductive state left [0,1]")
    if np.any(np.abs(branch) > 1.0):
        raise ValueError("S2 nonlinear branch state left [-1,1]")
    conductivity = closure.conductivity_S_m(temperature, conductive)
    unit_electrical, electrical = _electrical_unit_and_actual(
        grid=grid,
        conductivity_S_m=conductivity,
        actual_voltage_V=voltage,
        topology=electrical_topology,
        use_equivalent_optimizations=use_equivalent_optimizations,
        use_unit_voltage_scaling=use_unit_voltage_scaling,
        performance_timings=performance_timings,
    )
    area = grid.cell_area_m2
    capacity_cell = fields.effective_areal_capacity_J_m2K.reshape(-1) * area
    sink_cell = fields.vertical_conductance_W_m2K * area
    flat_temperature = temperature.reshape(-1)
    thermal = (
        capacity_cell
        * (flat_temperature - old_state.temperature_K.reshape(-1))
        / dt_s
        + lateral_matrix @ flat_temperature
        + sink_cell * (flat_temperature - fields.ambient_temperature_K)
        - electrical.cell_joule_power_W.reshape(-1)
    )
    temperature_scale_K = max(
        float(np.max(np.abs(temperature - old_state.temperature_K))),
        float(np.max(np.abs(temperature - fields.ambient_temperature_K))),
        1.0,
    )
    thermal_scale = np.maximum(
        capacity_cell / dt_s
        + np.asarray(lateral_matrix.diagonal())
        + sink_cell,
        1.0e-18,
    ) * temperature_scale_K
    heating, cooling = closure.branch_activations(
        temperature, old_state.temperature_K, dt_s
    )
    ratio_b = dt_s / closure.branch_relaxation_s
    branch_residual = (
        branch
        - old_state.branch_memory
        - ratio_b * (heating * (1.0 - branch) - cooling * (1.0 + branch))
    )
    equilibrium = closure.equilibrium_state(temperature, branch)
    ratio_s = dt_s / closure.state_relaxation_s
    state_residual = conductive - old_state.conductive_state - ratio_s * (
        equilibrium - conductive
    )
    circuit = (
        capacitance_F * (voltage - old_state.device_voltage_V) / dt_s
        - (input_voltage_V - voltage) / load_resistance_ohm
        + electrical.source_current_A
    )
    voltage_scale_V = max(
        abs(float(input_voltage_V)),
        abs(float(old_state.device_voltage_V)),
        abs(float(voltage)),
        1.0,
    )
    circuit_scale_A = max(
        (
            capacitance_F / dt_s
            + 1.0 / load_resistance_ohm
            + abs(unit_electrical.source_current_A)
        )
        * voltage_scale_V,
        1.0e-12,
    )
    return np.concatenate(
        [
            thermal / thermal_scale,
            state_residual.reshape(-1) / (1.0 + ratio_s),
            branch_residual.reshape(-1)
            / (1.0 + ratio_b * (heating + cooling)).reshape(-1),
            np.asarray([circuit / circuit_scale_A]),
        ]
    )


def _picard(
    initial: np.ndarray,
    mapping: Callable[[np.ndarray], np.ndarray],
    *,
    maximum_iterations: int,
    relaxation: float,
    update_tolerance: float,
) -> tuple[np.ndarray, int, float]:
    vector = np.asarray(initial, dtype=float).copy()
    update = float("inf")
    for iteration in range(1, maximum_iterations + 1):
        mapped = np.asarray(mapping(vector), dtype=float)
        candidate = (1.0 - relaxation) * vector + relaxation * mapped
        update = float(
            np.max(np.abs(candidate - vector) / np.maximum(np.abs(candidate), 1.0))
        )
        vector = candidate
        if update <= update_tolerance:
            return vector, iteration, update
    return vector, maximum_iterations, update


def _newton_krylov(
    initial: np.ndarray,
    residual: Callable[[np.ndarray], np.ndarray],
    nonlinear: dict,
    linear: dict,
    *,
    telemetry: dict[str, int] | None = None,
) -> tuple[np.ndarray, int, float, float, int, int]:
    counters = telemetry if telemetry is not None else {}
    counters["krylov_matvecs"] = 0
    counters["armijo_backtracks"] = 0
    vector = np.asarray(initial, dtype=float).copy()
    function = np.asarray(residual(vector), dtype=float)
    if not np.isfinite(function).all():
        raise FloatingPointError("initial S2 Newton residual is nonfinite")
    residual_limit = max(
        float(nonlinear["scaled_residual_absolute"]),
        float(nonlinear["scaled_residual_relative"]),
    )
    update_limit = float(nonlinear["scaled_update_relative"])
    residual_norm = float(np.max(np.abs(function)))
    if residual_norm <= residual_limit:
        return vector, 0, 0.0, residual_norm, 0, 0
    jacobian = _CountingKrylovJacobian(
        method="lgmres", inner_maxiter=50, outer_k=10
    )
    jacobian.setup(vector, function, residual)
    last_update = float("inf")
    initial_damping = float(nonlinear["initial_damping"])
    minimum_damping = float(nonlinear["minimum_damping"])
    armijo = float(nonlinear["armijo_coefficient"])
    armijo_backtracks = 0
    for iteration in range(1, int(nonlinear["maximum_newton_iterations"]) + 1):
        base_vector = vector.copy()
        base_function = function.copy()
        base_norm = residual_norm
        inner_tolerance = max(
            float(linear["relative"]),
            float(linear["absolute"]) / max(base_norm, 1.0e-30),
        )
        try:
            correction = -np.asarray(
                jacobian.solve(base_function, tol=inner_tolerance), dtype=float
            )
        finally:
            counters["krylov_matvecs"] = int(jacobian.matvec_count)
        if not np.isfinite(correction).all():
            raise RuntimeError("S2 Newton linear update is nonfinite")
        damping = initial_damping
        accepted = False
        while damping + 1.0e-15 >= minimum_damping:
            candidate = base_vector + damping * correction
            try:
                candidate_function = np.asarray(residual(candidate), dtype=float)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                damping *= 0.5
                armijo_backtracks += 1
                counters["armijo_backtracks"] = armijo_backtracks
                continue
            if not np.isfinite(candidate_function).all():
                damping *= 0.5
                armijo_backtracks += 1
                counters["armijo_backtracks"] = armijo_backtracks
                continue
            candidate_norm = float(np.max(np.abs(candidate_function)))
            if candidate_norm <= residual_limit or candidate_norm <= (
                1.0 - armijo * damping
            ) * base_norm:
                vector = candidate
                function = candidate_function
                residual_norm = candidate_norm
                last_update = float(
                    np.max(
                        np.abs(damping * correction)
                        / np.maximum(np.abs(candidate), 1.0)
                    )
                )
                accepted = True
                break
            damping *= 0.5
            armijo_backtracks += 1
            counters["armijo_backtracks"] = armijo_backtracks
        if not accepted:
            raise RuntimeError("S2 Newton Armijo search reached minimum damping")
        jacobian.update(vector, function)
        if residual_norm <= residual_limit and last_update <= update_limit:
            return (
                vector,
                iteration,
                last_update,
                residual_norm,
                jacobian.matvec_count,
                armijo_backtracks,
            )
        if residual_norm <= residual_limit:
            return (
                vector,
                iteration,
                0.0,
                residual_norm,
                jacobian.matvec_count,
                armijo_backtracks,
            )
    raise RuntimeError("S2 Newton reached the maximum iteration count")


def advance_s2_backward_euler(
    old_state: S2State,
    *,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
    performance_timings: S2PerformanceTimings | None = None,
) -> S2StepResult:
    if not np.isfinite([input_voltage_V, dt_s]).all() or dt_s <= 0.0:
        raise ValueError("S2 input voltage and positive dt must be finite")
    validate_s2_state(old_state, grid, closure)
    fields.validate_grid(grid)
    closure.validate_temperature(old_state.temperature_K)
    load, capacitance = _circuit_parameters(config)
    if cache is not None:
        cache.validate_context(grid, fields)
    lateral = (
        cache.lateral_matrix
        if cache is not None
        else assemble_sheet_thermal_matrix(
            grid, fields.sheet_thermal_conductance_W_K
        )
    )
    thermal_linear_solver = (
        cache.thermal_solver(dt_s)
        if cache is not None and use_equivalent_optimizations
        else None
    )
    electrical_topology = (
        cache.electrical_topology
        if cache is not None and use_equivalent_optimizations
        else build_sheet_electrical_topology(grid)
        if use_equivalent_optimizations
        else None
    )
    old_vector = _pack(
        old_state.temperature_K,
        old_state.conductive_state,
        old_state.branch_memory,
        old_state.device_voltage_V,
    )
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
        electrical = _electrical_actual_only(
            grid=grid,
            conductivity_S_m=conductivity,
            actual_voltage_V=0.0,
            topology=electrical_topology,
            use_equivalent_optimizations=use_equivalent_optimizations,
            performance_timings=performance_timings,
        )
        flux = reconstruct_lateral_fluxes(
            grid,
            fields.sheet_thermal_conductance_W_K,
            old_state.temperature_K,
            matrix=lateral,
        )
        new_state = S2State(
            time_s=old_state.time_s + dt_s,
            temperature_K=old_state.temperature_K.copy(),
            conductive_state=old_state.conductive_state.copy(),
            branch_memory=old_state.branch_memory.copy(),
            device_voltage_V=0.0,
        )
        ledgers = build_s2_ledgers(
            grid=grid,
            fields=fields,
            old_temperature_K=old_state.temperature_K,
            new_temperature_K=new_state.temperature_K,
            old_device_voltage_V=old_state.device_voltage_V,
            new_device_voltage_V=0.0,
            input_voltage_V=0.0,
            load_resistance_ohm=load,
            capacitance_F=capacitance,
            dt_s=dt_s,
            electrical=electrical,
            lateral_boundary_outflow_W=flux.boundary_outflow_W,
        )
        return S2StepResult(
            state=new_state,
            electrical=electrical,
            ledgers=ledgers,
            lateral_flux=flux,
            nonlinear=S2NonlinearDiagnostics(
                method="analytic_zero_drive_equilibrium",
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
    common = dict(
        old_state=old_state,
        input_voltage_V=float(input_voltage_V),
        dt_s=float(dt_s),
        grid=grid,
        closure=closure,
        fields=fields,
        lateral_matrix=lateral,
        thermal_linear_solver=thermal_linear_solver,
        electrical_topology=electrical_topology,
        use_equivalent_optimizations=bool(use_equivalent_optimizations),
        use_unit_voltage_scaling=bool(use_unit_voltage_scaling),
        performance_timings=performance_timings,
        load_resistance_ohm=load,
        capacitance_F=capacitance,
    )
    mapping = lambda vector: _fixed_point_map(vector, **common)
    residual = lambda vector: _scaled_residual(vector, **common)
    nonlinear = config["reference_solver"]["nonlinear_tolerances"]
    predictor_started = perf_counter()
    try:
        predictor, predictor_iterations, _ = _picard(
            old_vector,
            mapping,
            maximum_iterations=min(
                8, int(nonlinear["fixed_point_fallback_maximum_iterations"])
            ),
            relaxation=float(nonlinear["fixed_point_relaxation"]),
            update_tolerance=float(nonlinear["scaled_update_relative"]),
        )
    finally:
        if performance_timings is not None:
            performance_timings.add(
                "Picard_predictor_wall_s", perf_counter() - predictor_started
            )
    method = "damped_newton_krylov"
    krylov_matvecs = 0
    armijo_backtracks = 0
    fallback_iterations = 0
    newton_telemetry: dict[str, int] = {}
    newton_started = perf_counter()
    try:
        (
            solved,
            iterations,
            update_inf,
            residual_inf,
            krylov_matvecs,
            armijo_backtracks,
        ) = _newton_krylov(
            predictor,
            residual,
            nonlinear,
            config["reference_solver"]["linear_solver_tolerances"],
            telemetry=newton_telemetry,
        )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
        if performance_timings is not None:
            performance_timings.add(
                "Newton_Krylov_wall_s", perf_counter() - newton_started
            )
        krylov_matvecs = int(newton_telemetry.get("krylov_matvecs", 0))
        armijo_backtracks = int(newton_telemetry.get("armijo_backtracks", 0))
        method = "fail_closed_fixed_point_fallback"
        fallback_started = perf_counter()
        try:
            solved, fallback_iterations, update_inf = _picard(
                predictor,
                mapping,
                maximum_iterations=int(
                    nonlinear["fixed_point_fallback_maximum_iterations"]
                ),
                relaxation=float(nonlinear["fixed_point_relaxation"]),
                update_tolerance=float(nonlinear["scaled_update_relative"]),
            )
        finally:
            if performance_timings is not None:
                performance_timings.add(
                    "fallback_wall_s", perf_counter() - fallback_started
                )
        iterations = fallback_iterations
        residual_inf = float(np.max(np.abs(residual(solved))))
    else:
        if performance_timings is not None:
            performance_timings.add(
                "Newton_Krylov_wall_s", perf_counter() - newton_started
            )
    mapped = mapping(solved)
    update_inf = float(
        np.max(np.abs(mapped - solved) / np.maximum(np.abs(solved), 1.0))
    )
    residual_limit = max(
        float(nonlinear["scaled_residual_absolute"]),
        float(nonlinear["scaled_residual_relative"]),
    )
    if residual_inf > residual_limit or update_inf > float(
        nonlinear["scaled_update_relative"]
    ):
        raise RuntimeError(
            "S2 implicit step failed closed: "
            f"residual={residual_inf:.6e}, update={update_inf:.6e}, method={method}"
        )
    temperature, conductive, branch, voltage = _unpack(solved, grid)
    new_state = S2State(
        time_s=old_state.time_s + dt_s,
        temperature_K=temperature,
        conductive_state=conductive,
        branch_memory=branch,
        device_voltage_V=voltage,
    )
    validate_s2_state(new_state, grid, closure)
    conductivity = closure.conductivity_S_m(temperature, conductive)
    electrical = (
        scale_unit_sheet_electrical_solution(
            _electrical_actual_only(
                grid=grid,
                conductivity_S_m=conductivity,
                actual_voltage_V=1.0,
                topology=electrical_topology,
                use_equivalent_optimizations=use_equivalent_optimizations,
                performance_timings=performance_timings,
            ),
            voltage,
        )
        if use_unit_voltage_scaling
        else _electrical_actual_only(
            grid=grid,
            conductivity_S_m=conductivity,
            actual_voltage_V=voltage,
            topology=electrical_topology,
            use_equivalent_optimizations=use_equivalent_optimizations,
            performance_timings=performance_timings,
        )
    )
    flux = reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        temperature,
        matrix=lateral,
    )
    ledgers = build_s2_ledgers(
        grid=grid,
        fields=fields,
        old_temperature_K=old_state.temperature_K,
        new_temperature_K=temperature,
        old_device_voltage_V=old_state.device_voltage_V,
        new_device_voltage_V=voltage,
        input_voltage_V=input_voltage_V,
        load_resistance_ohm=load,
        capacitance_F=capacitance,
        dt_s=dt_s,
        electrical=electrical,
        lateral_boundary_outflow_W=flux.boundary_outflow_W,
    )
    return S2StepResult(
        state=new_state,
        electrical=electrical,
        ledgers=ledgers,
        lateral_flux=flux,
        nonlinear=S2NonlinearDiagnostics(
            method=method,
            iterations=int(iterations),
            scaled_residual_inf=float(residual_inf),
            scaled_update_inf=float(update_inf),
            converged=True,
            krylov_matvecs=int(krylov_matvecs),
            armijo_backtracks=int(armijo_backtracks),
            predictor_picard_iterations=int(predictor_iterations),
            fallback_picard_iterations=int(fallback_iterations),
        ),
    )


def protocol_discontinuities(protocol: dict) -> tuple[float, ...]:
    kind = protocol["kind"]
    if kind == "constant_voltage_step_at_t0":
        return ()
    if kind == "rectangular_voltage_pulse":
        start = float(protocol["pulse_start_s"])
        stop = float(protocol["pulse_stop_s"])
        if not np.isfinite([start, stop]).all() or not 0.0 <= start < stop:
            raise ValueError("rectangular pulse times must be finite and ordered")
        return (start, stop)
    raise ValueError(f"unsupported Phase 1-v2 protocol kind: {kind}")


def protocol_voltage(protocol: dict, time_s: float) -> float:
    if not np.isfinite(time_s):
        raise ValueError("protocol evaluation time must be finite")
    kind = protocol["kind"]
    if kind == "constant_voltage_step_at_t0":
        voltage = float(protocol["input_voltage_V"])
        if not np.isfinite(voltage):
            raise ValueError("constant protocol voltage must be finite")
        return voltage
    if kind == "rectangular_voltage_pulse":
        protocol_discontinuities(protocol)
        voltage = float(
            protocol["pulse_voltage_V"]
            if float(protocol["pulse_start_s"]) <= time_s < float(protocol["pulse_stop_s"])
            else protocol["baseline_voltage_V"]
        )
        if not np.isfinite(voltage):
            raise ValueError("pulse protocol voltage must be finite")
        return voltage
    raise ValueError(f"unsupported Phase 1-v2 protocol kind: {kind}")


def protocol_interval_voltage(
    protocol: dict, interval_start_s: float, interval_stop_s: float
) -> float:
    """Return the constant drive on one discontinuity-clipped time interval."""

    if (
        not np.isfinite([interval_start_s, interval_stop_s]).all()
        or interval_stop_s <= interval_start_s
    ):
        raise ValueError("protocol interval must be finite and have positive width")
    for boundary in protocol_discontinuities(protocol):
        if interval_start_s < boundary < interval_stop_s:
            raise ValueError("protocol interval crosses a declared discontinuity")
    return protocol_voltage(protocol, 0.5 * (interval_start_s + interval_stop_s))


def simulate_s2_protocol(
    initial_state: S2State,
    *,
    protocol: dict,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    time_divisor: int = 1,
    final_time_s: float | None = None,
    maximum_accepted_steps: int | None = None,
    maximum_wall_clock_s: float | None = None,
    forced_times_s: tuple[float, ...] | list[float] | np.ndarray = (),
    retain_full_history: bool = True,
    retained_step_limit: int = 0,
    accepted_step_callback: Callable[
        [S2State, S2StepResult, float, float, float], None
    ]
    | None = None,
    attempted_candidate_callback: Callable[[S2AttemptObservation], None]
    | None = None,
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
) -> S2ProtocolResult:
    if time_divisor not in set(config["reference_solver"]["formal_time_step_divisors"]):
        raise ValueError("undeclared Phase 1-v2 time divisor")
    if maximum_accepted_steps is not None and maximum_accepted_steps <= 0:
        raise ValueError("maximum_accepted_steps must be positive when supplied")
    if maximum_wall_clock_s is not None and (
        not np.isfinite(maximum_wall_clock_s) or maximum_wall_clock_s <= 0.0
    ):
        raise ValueError("maximum_wall_clock_s must be finite and positive")
    if retained_step_limit < 0:
        raise ValueError("retained_step_limit cannot be negative")
    time_grid = config["reference_solver"]["time_grid"]
    stop = float(time_grid["final_time_s"] if final_time_s is None else final_time_s)
    if not np.isfinite(stop) or stop <= initial_state.time_s:
        raise ValueError("S2 final time must be finite and later than the initial state")
    protocol_discontinuities(protocol)
    protocol_voltage(protocol, initial_state.time_s)
    fields.validate_grid(grid)
    validate_s2_state(initial_state, grid, closure)
    if cache is not None:
        cache.validate_context(grid, fields)
    base_dt = float(time_grid["base_max_step_s"]) / time_divisor
    floor_dt = float(time_grid["transition_max_step_s"]) / time_divisor
    threshold = float(time_grid["transition_increment_threshold"])
    easy_threshold = float(time_grid["easy_transition_increment_max"])
    per_step_cap = int(time_grid["maximum_rejected_steps_per_accepted_step"])
    case_cap = int(time_grid["maximum_rejected_steps_per_case"])
    state = initial_state
    current_dt = base_dt
    steps: list[S2StepResult] = []
    accepted_steps = 0
    accepted_dts: list[float] = []
    step_wall_times: list[float] = []
    total_newton_iterations = 0
    total_krylov_matvecs = 0
    total_armijo_backtracks = 0
    total_fallback_picard_iterations = 0
    rejected = transition_rejections = nonlinear_rejections = 0
    endpoint_remainders = fallback_steps = 0
    easy_streak = 0
    minimum_dt = float("inf")
    maximum_dt = 0.0
    maximum_increment = 0.0
    eps = max(1.0e-18, abs(stop) * 1.0e-14)
    stop_reason = "requested_final_time_reached"
    run_wall_start = perf_counter()
    discontinuities = tuple(
        value
        for value in protocol_discontinuities(protocol)
        if initial_state.time_s < value < stop
    )
    forced = np.asarray(forced_times_s, dtype=float)
    if forced.ndim != 1 or not np.isfinite(forced).all():
        raise ValueError("forced S2 landing times must be finite and one-dimensional")
    if forced.size and np.any(np.diff(forced) <= 0.0):
        raise ValueError("forced S2 landing times must be strictly increasing")
    if forced.size and (
        forced[0] < initial_state.time_s - eps or forced[-1] > stop + eps
    ):
        raise ValueError("forced S2 landing times must lie inside the run window")
    landing_times = tuple(
        sorted(
            set(discontinuities)
            | {
                float(value)
                for value in forced
                if initial_state.time_s < float(value) < stop + eps
            }
        )
    )
    while state.time_s < stop - eps:
        if (
            maximum_wall_clock_s is not None
            and perf_counter() - run_wall_start >= maximum_wall_clock_s
        ):
            stop_reason = "maximum_wall_clock_reached"
            break
        if (
            maximum_accepted_steps is not None
            and accepted_steps >= maximum_accepted_steps
        ):
            stop_reason = "maximum_accepted_steps_reached"
            break
        remaining = stop - state.time_s
        dt = min(current_dt, remaining)
        future_boundaries = [
            value for value in landing_times if value > state.time_s + eps
        ]
        if future_boundaries:
            dt = min(dt, min(future_boundaries) - state.time_s)
        endpoint_remainder = remaining < floor_dt - eps
        if dt < floor_dt - eps and not endpoint_remainder:
            raise RuntimeError("S2 adaptive controller proposed a below-floor step")
        # Each accepted step is clipped at every declared discontinuity.  Use
        # an interior point of that interval so the value at the right-hand
        # boundary cannot be applied one full step early (or removed one step
        # early at a pulse stop).
        input_voltage = protocol_interval_voltage(
            protocol, state.time_s, state.time_s + dt
        )
        previous_state = state
        accepted_step_wall_start = perf_counter()
        rejections_this_step = 0
        had_rejection = False
        while True:
            candidate_wall_start = (
                perf_counter() if attempted_candidate_callback is not None else None
            )
            try:
                candidate = advance_s2_backward_euler(
                    state,
                    input_voltage_V=input_voltage,
                    dt_s=dt,
                    grid=grid,
                    closure=closure,
                    fields=fields,
                    config=config,
                        cache=cache,
                        use_equivalent_optimizations=use_equivalent_optimizations,
                        use_unit_voltage_scaling=use_unit_voltage_scaling,
                    )
            except (
                RuntimeError,
                ValueError,
                FloatingPointError,
                np.linalg.LinAlgError,
            ) as error:
                if attempted_candidate_callback is not None:
                    assert candidate_wall_start is not None
                    candidate_wall_time = perf_counter() - candidate_wall_start
                    attempted_candidate_callback(
                        S2AttemptObservation(
                            previous_state=state,
                            candidate=None,
                            dt_s=float(dt),
                            input_voltage_V=float(input_voltage),
                            candidate_wall_time_s=float(candidate_wall_time),
                            rejection_index=int(rejections_this_step),
                            endpoint_remainder=bool(endpoint_remainder),
                            at_locked_floor=bool(
                                dt <= floor_dt * (1.0 + 1.0e-12)
                            ),
                            conductive_increment=None,
                            branch_increment=None,
                            transition_increment=None,
                            transition_threshold=float(threshold),
                            error_class=type(error).__name__,
                            error_message=str(error),
                        )
                    )
                if endpoint_remainder or dt <= floor_dt * (1.0 + 1.0e-12):
                    raise RuntimeError("S2 adaptive solve failed at its locked floor")
                nonlinear_rejections += 1
                rejected += 1
                rejections_this_step += 1
                had_rejection = True
                if rejections_this_step > per_step_cap or rejected > case_cap:
                    raise RuntimeError("S2 adaptive nonlinear rejection cap reached")
                dt = max(0.5 * dt, floor_dt)
                input_voltage = protocol_interval_voltage(
                    protocol, state.time_s, state.time_s + dt
                )
                continue
            conductive_increment = float(
                np.max(
                    np.abs(candidate.state.conductive_state - state.conductive_state)
                )
            )
            branch_increment = float(
                np.max(np.abs(candidate.state.branch_memory - state.branch_memory))
            )
            increment = max(conductive_increment, branch_increment)
            if attempted_candidate_callback is not None:
                assert candidate_wall_start is not None
                candidate_wall_time = perf_counter() - candidate_wall_start
                attempted_candidate_callback(
                    S2AttemptObservation(
                        previous_state=state,
                        candidate=candidate,
                        dt_s=float(dt),
                        input_voltage_V=float(input_voltage),
                        candidate_wall_time_s=float(candidate_wall_time),
                        rejection_index=int(rejections_this_step),
                        endpoint_remainder=bool(endpoint_remainder),
                        at_locked_floor=bool(
                            dt <= floor_dt * (1.0 + 1.0e-12)
                        ),
                        conductive_increment=float(conductive_increment),
                        branch_increment=float(branch_increment),
                        transition_increment=float(increment),
                        transition_threshold=float(threshold),
                        error_class=None,
                        error_message=None,
                    )
                )
            if increment > threshold:
                if endpoint_remainder or dt <= floor_dt * (1.0 + 1.0e-12):
                    raise RuntimeError("S2 transition increment failed at locked floor")
                transition_rejections += 1
                rejected += 1
                rejections_this_step += 1
                had_rejection = True
                if rejections_this_step > per_step_cap or rejected > case_cap:
                    raise RuntimeError("S2 adaptive transition rejection cap reached")
                dt = max(0.5 * dt, floor_dt)
                input_voltage = protocol_interval_voltage(
                    protocol, state.time_s, state.time_s + dt
                )
                continue
            break
        accepted_step_wall_time = perf_counter() - accepted_step_wall_start
        accepted_steps += 1
        accepted_dts.append(float(dt))
        step_wall_times.append(float(accepted_step_wall_time))
        total_newton_iterations += int(getattr(candidate.nonlinear, "iterations", 0))
        total_krylov_matvecs += int(
            getattr(candidate.nonlinear, "krylov_matvecs", 0)
        )
        total_armijo_backtracks += int(
            getattr(candidate.nonlinear, "armijo_backtracks", 0)
        )
        total_fallback_picard_iterations += int(
            getattr(candidate.nonlinear, "fallback_picard_iterations", 0)
        )
        if retain_full_history:
            steps.append(candidate)
        elif retained_step_limit:
            steps.append(candidate)
            if len(steps) > retained_step_limit:
                del steps[0]
        if accepted_step_callback is not None:
            accepted_step_callback(
                previous_state,
                candidate,
                float(dt),
                float(input_voltage),
                float(accepted_step_wall_time),
            )
        state = candidate.state
        minimum_dt = min(minimum_dt, dt)
        maximum_dt = max(maximum_dt, dt)
        maximum_increment = max(maximum_increment, increment)
        endpoint_remainders += int(endpoint_remainder)
        fallback = (
            candidate.nonlinear.method == "fail_closed_fixed_point_fallback"
        )
        fallback_steps += int(fallback)
        if increment <= easy_threshold and not fallback and not had_rejection:
            easy_streak += 1
        else:
            easy_streak = 0
        current_dt = dt
        if easy_streak >= 2:
            current_dt = min(2.0 * current_dt, base_dt)
            easy_streak = 0
    completed = state.time_s >= stop - eps
    dt_values = np.asarray(accepted_dts, dtype=float)
    wall_values = np.asarray(step_wall_times, dtype=float)
    return S2ProtocolResult(
        steps=tuple(steps),
        diagnostics=S2AdaptiveDiagnostics(
            accepted_steps=accepted_steps,
            rejected_steps=rejected,
            transition_rejections=transition_rejections,
            nonlinear_rejections=nonlinear_rejections,
            endpoint_remainder_steps=endpoint_remainders,
            minimum_accepted_step_s=0.0 if not accepted_steps else minimum_dt,
            maximum_accepted_step_s=maximum_dt,
            maximum_transition_increment=maximum_increment,
            fallback_steps=fallback_steps,
            newton_iterations=int(total_newton_iterations),
            krylov_matvecs=int(total_krylov_matvecs),
            armijo_backtracks=int(total_armijo_backtracks),
            fallback_picard_iterations=int(total_fallback_picard_iterations),
            step_wall_time_p50_s=float(np.quantile(wall_values, 0.50))
            if wall_values.size
            else 0.0,
            step_wall_time_p90_s=float(np.quantile(wall_values, 0.90))
            if wall_values.size
            else 0.0,
            step_wall_time_max_s=float(np.max(wall_values))
            if wall_values.size
            else 0.0,
            accepted_dt_p10_s=float(np.quantile(dt_values, 0.10))
            if dt_values.size
            else 0.0,
            accepted_dt_p50_s=float(np.quantile(dt_values, 0.50))
            if dt_values.size
            else 0.0,
            accepted_dt_p90_s=float(np.quantile(dt_values, 0.90))
            if dt_values.size
            else 0.0,
        ),
        requested_final_time_s=stop,
        achieved_final_time_s=state.time_s,
        completed=bool(completed),
        stop_reason="requested_final_time_reached" if completed else stop_reason,
    )


def simulate_s2_decoupled_copies(
    *,
    initial_state_A: S2State,
    protocol_A: dict,
    initial_state_B: S2State,
    protocol_B: dict,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    time_divisor: int = 1,
    final_time_s: float | None = None,
    maximum_accepted_steps: int | None = None,
) -> tuple[S2ProtocolResult, S2ProtocolResult]:
    """Run independently driven A/B copies with exactly zero mutual coupling."""

    shared = dict(
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        time_divisor=time_divisor,
        final_time_s=final_time_s,
        maximum_accepted_steps=maximum_accepted_steps,
    )
    return (
        simulate_s2_protocol(initial_state_A, protocol=protocol_A, **shared),
        simulate_s2_protocol(initial_state_B, protocol=protocol_B, **shared),
    )


__all__ = [
    "PERFORMANCE_TIMING_SEMANTICS",
    "S2AdaptiveDiagnostics",
    "S2AttemptObservation",
    "S2NonlinearDiagnostics",
    "S2PerformanceTimings",
    "S2ProtocolResult",
    "S2SolverCache",
    "S2State",
    "S2StepResult",
    "advance_s2_backward_euler",
    "build_s2_solver_cache",
    "initial_s2_state",
    "protocol_discontinuities",
    "protocol_interval_voltage",
    "protocol_voltage",
    "simulate_s2_decoupled_copies",
    "simulate_s2_protocol",
    "validate_s2_state",
]
