"""Versioned nonlinear solver repair for the frozen Phase 1-v2 S2 step.

This module deliberately leaves the historical implicit solver byte-for-byte
unchanged.  It reuses the same frozen residual, fixed-point map, electrical,
thermal, state, circuit, and ledger implementations while replacing only the
nonlinear convergence controller.  In particular, relaxed Picard increments
are telemetry rather than a success gate: publication requires both the full
fixed-point defect and the scaled residual to pass their original tolerances.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from time import perf_counter
from typing import Any, Callable

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers import geophase_phase1_v2_implicit as legacy
from pinnpcm.solvers import geophase_phase1_v2_controller_v2 as controller_v2
from pinnpcm.solvers import geophase_phase1_v2_controller_v3 as controller_v3


NLS_V1_ID = "phase1_s2_dual_gate_nonlinear_solver_v1"


@dataclass(frozen=True)
class NLSV1FixedPointIteration:
    iteration: int
    relaxed_increment_inf: float
    fixed_point_defect_inf: float
    scaled_residual_inf: float
    temperature_residual_inf: float
    conductive_state_residual_inf: float
    branch_residual_inf: float
    circuit_residual_inf: float
    contraction_ratio: float | None
    relaxation: float


@dataclass(frozen=True)
class NLSV1Diagnostics(legacy.S2NonlinearDiagnostics):
    solver_identity: str = NLS_V1_ID
    fixed_point_defect_inf: float = 0.0
    residual_blocks_inf: dict[str, float] = field(default_factory=dict)
    fallback_iteration_history: tuple[NLSV1FixedPointIteration, ...] = ()
    newton_failure: dict[str, Any] | None = None


class NLSV1SolveError(RuntimeError):
    """Fail-closed nonlinear error carrying JSON-ready solver telemetry."""

    def __init__(self, message: str, *, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class NLSV1EmbeddedAttemptObservation:
    previous_state: legacy.S2State
    step: controller_v2.S2EmbeddedStepResult | None
    full_candidate: legacy.S2StepResult | None
    first_half_candidate: legacy.S2StepResult | None
    second_half_candidate: legacy.S2StepResult | None
    diagnostics: controller_v2.S2EmbeddedIntervalDiagnostics
    error_class: str | None
    error_message: str | None
    error_diagnostics: dict[str, Any] | None = None
    aggregate_ledgers: Any | None = None
    aggregate_energy: Any | None = None


def _relative_increment(candidate: np.ndarray, previous: np.ndarray) -> float:
    candidate_values = np.asarray(candidate, dtype=float)
    previous_values = np.asarray(previous, dtype=float)
    if candidate_values.shape != previous_values.shape:
        raise ValueError("S2 nonlinear vectors must share a shape")
    return float(
        np.max(
            np.abs(candidate_values - previous_values)
            / np.maximum(np.abs(candidate_values), 1.0)
        )
    )


def _fixed_point_defect(mapped: np.ndarray, solution: np.ndarray) -> float:
    mapped_values = np.asarray(mapped, dtype=float)
    solution_values = np.asarray(solution, dtype=float)
    if mapped_values.shape != solution_values.shape:
        raise ValueError("S2 nonlinear vectors must share a shape")
    return float(
        np.max(
            np.abs(mapped_values - solution_values)
            / np.maximum(np.abs(solution_values), 1.0)
        )
    )


def _scaled_residual_block_norms(
    residual_vector: np.ndarray, grid: GeoPhaseGrid
) -> dict[str, float]:
    values = np.asarray(residual_vector, dtype=float)
    cells = grid.nx * grid.ny
    if values.shape != (3 * cells + 1,):
        raise ValueError("S2 scaled residual has the wrong shape")
    if not np.isfinite(values).all():
        raise FloatingPointError("S2 scaled residual is nonfinite")
    return {
        "temperature": float(np.max(np.abs(values[:cells]))),
        "conductive_state": float(np.max(np.abs(values[cells : 2 * cells]))),
        "branch": float(np.max(np.abs(values[2 * cells : 3 * cells]))),
        "circuit": float(abs(values[-1])),
    }


def _picard_nls_v1(
    initial: np.ndarray,
    mapping: Callable[[np.ndarray], np.ndarray],
    residual: Callable[[np.ndarray], np.ndarray],
    *,
    grid: GeoPhaseGrid,
    maximum_iterations: int,
    relaxation: float,
    update_tolerance: float,
    residual_tolerance: float,
) -> tuple[
    np.ndarray,
    int,
    float,
    float,
    float,
    dict[str, float],
    tuple[NLSV1FixedPointIteration, ...],
]:
    vector = np.asarray(initial, dtype=float).copy()
    if not np.isfinite(vector).all():
        raise FloatingPointError("initial S2 Picard vector is nonfinite")
    mapped = np.asarray(mapping(vector), dtype=float)
    if not np.isfinite(mapped).all():
        raise FloatingPointError("initial S2 Picard mapping is nonfinite")
    relaxed_increment = float("inf")
    defect = _fixed_point_defect(mapped, vector)
    scaled_residual = float("inf")
    block_norms: dict[str, float] = {}
    previous_defect: float | None = None
    history: list[NLSV1FixedPointIteration] = []
    for iteration in range(1, maximum_iterations + 1):
        candidate = (1.0 - relaxation) * vector + relaxation * mapped
        relaxed_increment = _relative_increment(candidate, vector)
        candidate_mapped = np.asarray(mapping(candidate), dtype=float)
        if not np.isfinite(candidate_mapped).all():
            raise FloatingPointError("S2 Picard mapping is nonfinite")
        defect = _fixed_point_defect(candidate_mapped, candidate)
        residual_vector = np.asarray(residual(candidate), dtype=float)
        block_norms = _scaled_residual_block_norms(residual_vector, grid)
        scaled_residual = max(block_norms.values())
        contraction_ratio = (
            defect / previous_defect
            if previous_defect is not None and previous_defect > 0.0
            else None
        )
        history.append(
            NLSV1FixedPointIteration(
                iteration=iteration,
                relaxed_increment_inf=relaxed_increment,
                fixed_point_defect_inf=defect,
                scaled_residual_inf=scaled_residual,
                temperature_residual_inf=block_norms["temperature"],
                conductive_state_residual_inf=block_norms["conductive_state"],
                branch_residual_inf=block_norms["branch"],
                circuit_residual_inf=block_norms["circuit"],
                contraction_ratio=contraction_ratio,
                relaxation=relaxation,
            )
        )
        vector = candidate
        mapped = candidate_mapped
        previous_defect = defect
        if defect <= update_tolerance and scaled_residual <= residual_tolerance:
            return (
                vector,
                iteration,
                relaxed_increment,
                defect,
                scaled_residual,
                block_norms,
                tuple(history),
            )
    return (
        vector,
        maximum_iterations,
        relaxed_increment,
        defect,
        scaled_residual,
        block_norms,
        tuple(history),
    )


def _newton_krylov_nls_v1(
    initial: np.ndarray,
    residual: Callable[[np.ndarray], np.ndarray],
    nonlinear: dict,
    linear: dict,
    *,
    telemetry: dict[str, Any],
) -> tuple[np.ndarray, int, float, float, int, int]:
    telemetry.update(
        {
            "krylov_matvecs": 0,
            "armijo_backtracks": 0,
            "iteration_endpoint": 0,
            "stage": "initial_residual",
        }
    )
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
    telemetry["scaled_residual_inf"] = residual_norm
    telemetry["scaled_update_inf"] = 0.0
    if residual_norm <= residual_limit:
        return vector, 0, 0.0, residual_norm, 0, 0
    jacobian = legacy._CountingKrylovJacobian(
        method="lgmres", inner_maxiter=50, outer_k=10
    )
    jacobian.setup(vector, function, residual)
    last_update = float("inf")
    initial_damping = float(nonlinear["initial_damping"])
    minimum_damping = float(nonlinear["minimum_damping"])
    armijo = float(nonlinear["armijo_coefficient"])
    armijo_backtracks = 0
    for iteration in range(1, int(nonlinear["maximum_newton_iterations"]) + 1):
        telemetry["iteration_endpoint"] = iteration
        telemetry["stage"] = "krylov_linear_solve"
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
            telemetry["krylov_matvecs"] = int(jacobian.matvec_count)
        if not np.isfinite(correction).all():
            raise RuntimeError("S2 Newton linear update is nonfinite")
        damping = initial_damping
        accepted = False
        while damping + 1.0e-15 >= minimum_damping:
            telemetry["stage"] = "armijo_search"
            candidate = base_vector + damping * correction
            try:
                candidate_function = np.asarray(residual(candidate), dtype=float)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                damping *= 0.5
                armijo_backtracks += 1
                telemetry["armijo_backtracks"] = armijo_backtracks
                continue
            if not np.isfinite(candidate_function).all():
                damping *= 0.5
                armijo_backtracks += 1
                telemetry["armijo_backtracks"] = armijo_backtracks
                continue
            candidate_norm = float(np.max(np.abs(candidate_function)))
            if candidate_norm <= residual_limit or candidate_norm <= (
                1.0 - armijo * damping
            ) * base_norm:
                vector = candidate
                function = candidate_function
                residual_norm = candidate_norm
                last_update = _relative_increment(candidate, base_vector)
                telemetry["scaled_residual_inf"] = residual_norm
                telemetry["scaled_update_inf"] = last_update
                accepted = True
                break
            damping *= 0.5
            armijo_backtracks += 1
            telemetry["armijo_backtracks"] = armijo_backtracks
        if not accepted:
            telemetry["stage"] = "armijo_minimum_damping"
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
    telemetry["stage"] = "maximum_iterations"
    telemetry["scaled_residual_inf"] = residual_norm
    telemetry["scaled_update_inf"] = last_update
    raise RuntimeError("S2 Newton reached the maximum iteration count")


def _newton_failure_payload(
    error: BaseException, telemetry: dict[str, Any]
) -> dict[str, Any]:
    return {
        "exception_class": type(error).__name__,
        "exception_message": str(error),
        "iteration_endpoint": int(telemetry.get("iteration_endpoint", 0)),
        "stage": str(telemetry.get("stage", "unknown")),
        "scaled_residual_inf": (
            None
            if telemetry.get("scaled_residual_inf") is None
            else float(telemetry["scaled_residual_inf"])
        ),
        "scaled_update_inf": (
            None
            if telemetry.get("scaled_update_inf") is None
            else float(telemetry["scaled_update_inf"])
        ),
        "krylov_matvecs": int(telemetry.get("krylov_matvecs", 0)),
        "armijo_backtracks": int(telemetry.get("armijo_backtracks", 0)),
    }


def advance_s2_backward_euler_nls_v1(
    old_state: legacy.S2State,
    *,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    cache: legacy.S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
    performance_timings: legacy.S2PerformanceTimings | None = None,
) -> legacy.S2StepResult:
    """Advance one frozen S2 backward-Euler step with NLS-v1 gates."""

    if not np.isfinite([input_voltage_V, dt_s]).all() or dt_s <= 0.0:
        raise ValueError("S2 input voltage and positive dt must be finite")
    legacy.validate_s2_state(old_state, grid, closure)
    fields.validate_grid(grid)
    closure.validate_temperature(old_state.temperature_K)
    load, capacitance = legacy._circuit_parameters(config)
    if cache is not None:
        cache.validate_context(grid, fields)
    lateral = (
        cache.lateral_matrix
        if cache is not None
        else legacy.assemble_sheet_thermal_matrix(
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
        else legacy.build_sheet_electrical_topology(grid)
        if use_equivalent_optimizations
        else None
    )
    old_vector = legacy._pack(
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
        legacy_result = legacy.advance_s2_backward_euler(
            old_state,
            input_voltage_V=input_voltage_V,
            dt_s=dt_s,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            cache=cache,
            use_equivalent_optimizations=use_equivalent_optimizations,
            use_unit_voltage_scaling=use_unit_voltage_scaling,
            performance_timings=performance_timings,
        )
        return replace(
            legacy_result,
            nonlinear=NLSV1Diagnostics(
                method="nls_v1_analytic_zero_drive_equilibrium",
                iterations=0,
                scaled_residual_inf=0.0,
                scaled_update_inf=0.0,
                converged=True,
                krylov_matvecs=0,
                armijo_backtracks=0,
                predictor_picard_iterations=0,
                fallback_picard_iterations=0,
                fixed_point_defect_inf=0.0,
                residual_blocks_inf={
                    "temperature": 0.0,
                    "conductive_state": 0.0,
                    "branch": 0.0,
                    "circuit": 0.0,
                },
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
    mapping = lambda vector: legacy._fixed_point_map(vector, **common)
    residual = lambda vector: legacy._scaled_residual(vector, **common)
    nonlinear = config["reference_solver"]["nonlinear_tolerances"]
    residual_limit = max(
        float(nonlinear["scaled_residual_absolute"]),
        float(nonlinear["scaled_residual_relative"]),
    )
    update_limit = float(nonlinear["scaled_update_relative"])

    predictor_started = perf_counter()
    try:
        predictor, predictor_iterations, _ = legacy._picard(
            old_vector,
            mapping,
            maximum_iterations=min(
                8, int(nonlinear["fixed_point_fallback_maximum_iterations"])
            ),
            relaxation=float(nonlinear["fixed_point_relaxation"]),
            update_tolerance=update_limit,
        )
    finally:
        if performance_timings is not None:
            performance_timings.add(
                "NLS_v1_Picard_predictor_wall_s",
                perf_counter() - predictor_started,
            )

    method = "nls_v1_damped_newton_krylov"
    krylov_matvecs = armijo_backtracks = fallback_iterations = 0
    fallback_history: tuple[NLSV1FixedPointIteration, ...] = ()
    newton_failure: dict[str, Any] | None = None
    newton_telemetry: dict[str, Any] = {}
    newton_started = perf_counter()
    try:
        (
            solved,
            iterations,
            _newton_update,
            _newton_residual,
            krylov_matvecs,
            armijo_backtracks,
        ) = _newton_krylov_nls_v1(
            predictor,
            residual,
            nonlinear,
            config["reference_solver"]["linear_solver_tolerances"],
            telemetry=newton_telemetry,
        )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        if performance_timings is not None:
            performance_timings.add(
                "NLS_v1_Newton_Krylov_wall_s", perf_counter() - newton_started
            )
        newton_failure = _newton_failure_payload(error, newton_telemetry)
        krylov_matvecs = int(newton_telemetry.get("krylov_matvecs", 0))
        armijo_backtracks = int(newton_telemetry.get("armijo_backtracks", 0))
        method = "nls_v1_fail_closed_fixed_point_fallback"
        fallback_started = perf_counter()
        try:
            (
                solved,
                fallback_iterations,
                _relaxed_increment,
                _fallback_defect,
                _fallback_residual,
                _fallback_blocks,
                fallback_history,
            ) = _picard_nls_v1(
                predictor,
                mapping,
                residual,
                grid=grid,
                maximum_iterations=int(
                    nonlinear["fixed_point_fallback_maximum_iterations"]
                ),
                relaxation=float(nonlinear["fixed_point_relaxation"]),
                update_tolerance=update_limit,
                residual_tolerance=residual_limit,
            )
        except (
            RuntimeError,
            ValueError,
            FloatingPointError,
            np.linalg.LinAlgError,
        ) as fallback_error:
            raise NLSV1SolveError(
                f"NLS-v1 fallback failed: {fallback_error}",
                diagnostics={
                    "solver_identity": NLS_V1_ID,
                    "method": method,
                    "newton_failure": newton_failure,
                    "fallback_error": {
                        "exception_class": type(fallback_error).__name__,
                        "exception_message": str(fallback_error),
                    },
                },
            ) from fallback_error
        finally:
            if performance_timings is not None:
                performance_timings.add(
                    "NLS_v1_fallback_wall_s", perf_counter() - fallback_started
                )
        iterations = fallback_iterations
    else:
        if performance_timings is not None:
            performance_timings.add(
                "NLS_v1_Newton_Krylov_wall_s", perf_counter() - newton_started
            )

    mapped = np.asarray(mapping(solved), dtype=float)
    defect_inf = _fixed_point_defect(mapped, solved)
    residual_vector = np.asarray(residual(solved), dtype=float)
    residual_blocks = _scaled_residual_block_norms(residual_vector, grid)
    residual_inf = max(residual_blocks.values())
    try:
        temperature, conductive, branch, voltage = legacy._unpack(solved, grid)
        new_state = legacy.S2State(
            time_s=old_state.time_s + dt_s,
            temperature_K=temperature,
            conductive_state=conductive,
            branch_memory=branch,
            device_voltage_V=voltage,
        )
        legacy.validate_s2_state(new_state, grid, closure)
    except (ValueError, FloatingPointError) as state_error:
        raise NLSV1SolveError(
            f"NLS-v1 final state failed validation: {state_error}",
            diagnostics={
                "solver_identity": NLS_V1_ID,
                "method": method,
                "scaled_residual_inf": residual_inf,
                "fixed_point_defect_inf": defect_inf,
                "residual_blocks_inf": residual_blocks,
                "newton_failure": newton_failure,
                "fallback_iteration_history": [
                    asdict(item) for item in fallback_history
                ],
            },
        ) from state_error
    if residual_inf > residual_limit or defect_inf > update_limit:
        message = (
            "NLS-v1 implicit step failed closed: "
            f"residual={residual_inf:.6e}, defect={defect_inf:.6e}, method={method}"
        )
        raise NLSV1SolveError(
            message,
            diagnostics={
                "solver_identity": NLS_V1_ID,
                "method": method,
                "iterations": int(iterations),
                "scaled_residual_inf": float(residual_inf),
                "fixed_point_defect_inf": float(defect_inf),
                "residual_blocks_inf": dict(residual_blocks),
                "newton_failure": newton_failure,
                "fallback_iteration_history": [
                    asdict(item) for item in fallback_history
                ],
            },
        )

    conductivity = closure.conductivity_S_m(temperature, conductive)
    electrical = (
        legacy.scale_unit_sheet_electrical_solution(
            legacy._electrical_actual_only(
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
        else legacy._electrical_actual_only(
            grid=grid,
            conductivity_S_m=conductivity,
            actual_voltage_V=voltage,
            topology=electrical_topology,
            use_equivalent_optimizations=use_equivalent_optimizations,
            performance_timings=performance_timings,
        )
    )
    flux = legacy.reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        temperature,
        matrix=lateral,
    )
    ledgers = legacy.build_s2_ledgers(
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
    return legacy.S2StepResult(
        state=new_state,
        electrical=electrical,
        ledgers=ledgers,
        lateral_flux=flux,
        nonlinear=NLSV1Diagnostics(
            method=method,
            iterations=int(iterations),
            scaled_residual_inf=float(residual_inf),
            scaled_update_inf=float(defect_inf),
            converged=True,
            krylov_matvecs=int(krylov_matvecs),
            armijo_backtracks=int(armijo_backtracks),
            predictor_picard_iterations=int(predictor_iterations),
            fallback_picard_iterations=int(fallback_iterations),
            fixed_point_defect_inf=float(defect_inf),
            residual_blocks_inf=dict(residual_blocks),
            fallback_iteration_history=tuple(fallback_history),
            newton_failure=newton_failure,
        ),
    )


def _combined_nonlinear_nls_v1(
    steps: tuple[legacy.S2StepResult, ...],
) -> NLSV1Diagnostics:
    histories = tuple(
        item
        for step in steps
        for item in getattr(step.nonlinear, "fallback_iteration_history", ())
    )
    failures = [
        step.nonlinear.newton_failure
        for step in steps
        if getattr(step.nonlinear, "newton_failure", None) is not None
    ]
    return NLSV1Diagnostics(
        method="embedded[" + ",".join(step.nonlinear.method for step in steps) + "]",
        iterations=sum(step.nonlinear.iterations for step in steps),
        scaled_residual_inf=max(step.nonlinear.scaled_residual_inf for step in steps),
        scaled_update_inf=max(step.nonlinear.scaled_update_inf for step in steps),
        converged=all(step.nonlinear.converged for step in steps),
        krylov_matvecs=sum(step.nonlinear.krylov_matvecs for step in steps),
        armijo_backtracks=sum(step.nonlinear.armijo_backtracks for step in steps),
        predictor_picard_iterations=sum(
            step.nonlinear.predictor_picard_iterations for step in steps
        ),
        fallback_picard_iterations=sum(
            step.nonlinear.fallback_picard_iterations for step in steps
        ),
        fixed_point_defect_inf=max(
            float(getattr(step.nonlinear, "fixed_point_defect_inf"))
            for step in steps
        ),
        residual_blocks_inf={
            name: max(
                float(step.nonlinear.residual_blocks_inf[name]) for step in steps
            )
            for name in ("temperature", "conductive_state", "branch", "circuit")
        },
        fallback_iteration_history=histories,
        newton_failure={"paths": failures} if failures else None,
    )


def attempt_s2_embedded_interval_nls_v1(
    state: legacy.S2State,
    *,
    protocol: dict,
    protocol_id: str,
    outer_interval_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    rejection_index: int = 0,
    below_floor_remainder: bool = False,
    at_outer_floor: bool = False,
    cache: legacy.S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
    performance_timings: legacy.S2PerformanceTimings | None = None,
) -> NLSV1EmbeddedAttemptObservation:
    """Run the frozen embedded estimator with NLS-v1 on all three paths."""

    interval = float(outer_interval_s)
    if not np.isfinite(interval) or interval <= 0.0:
        raise ValueError("outer interval must be finite and positive")
    controller_v2._validate_protocol_identity(config, protocol_id, protocol)
    half = 0.5 * interval
    start = float(state.time_s)
    midpoint = start + half
    stop = start + interval
    full_voltage = legacy.protocol_interval_voltage(protocol, start, stop)
    first_voltage = legacy.protocol_interval_voltage(protocol, start, midpoint)
    second_voltage = legacy.protocol_interval_voltage(protocol, midpoint, stop)
    voltage_scale = controller_v2.protocol_voltage_scale(config, protocol_id)
    started = perf_counter()
    full: legacy.S2StepResult | None = None
    first: legacy.S2StepResult | None = None
    second: legacy.S2StepResult | None = None
    full_integrity: controller_v2.S2PathIntegrity | None = None
    first_integrity: controller_v2.S2PathIntegrity | None = None
    second_integrity: controller_v2.S2PathIntegrity | None = None
    aggregate_integrity: controller_v2.S2AggregateIntegrity | None = None
    embedded: controller_v2.S2EmbeddedError | None = None
    energy: Any | None = None
    aggregate_ledgers: Any | None = None
    error_class: str | None = None
    error_message: str | None = None
    error_diagnostics: dict[str, Any] | None = None
    coupled_solves = 0
    active_path = "full_step"
    common = dict(
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=cache,
        use_equivalent_optimizations=use_equivalent_optimizations,
        use_unit_voltage_scaling=use_unit_voltage_scaling,
        performance_timings=performance_timings,
    )
    try:
        coupled_solves += 1
        full = advance_s2_backward_euler_nls_v1(
            state, input_voltage_V=full_voltage, dt_s=interval, **common
        )
        full_integrity = controller_v2.evaluate_s2_step_integrity(full, config)
        if not full_integrity.overall_pass:
            raise RuntimeError("NLS-v1 full-step integrity failed")

        active_path = "first_half_step"
        coupled_solves += 1
        first = advance_s2_backward_euler_nls_v1(
            state, input_voltage_V=first_voltage, dt_s=half, **common
        )
        first_integrity = controller_v2.evaluate_s2_step_integrity(first, config)
        if not first_integrity.overall_pass:
            raise RuntimeError("NLS-v1 first-half integrity failed")

        active_path = "second_half_step"
        coupled_solves += 1
        second = advance_s2_backward_euler_nls_v1(
            first.state, input_voltage_V=second_voltage, dt_s=half, **common
        )
        second_integrity = controller_v2.evaluate_s2_step_integrity(second, config)
        if not second_integrity.overall_pass:
            raise RuntimeError("NLS-v1 second-half integrity failed")

        active_path = "aggregate_ledgers"
        capacitance = float(
            config["physics_contract"]["circuit"]["parallel_capacitance_F"]
        )
        aggregate_ledgers, energy = controller_v2.build_s2_two_half_interval_ledgers(
            grid=grid,
            fields=fields,
            outer_initial_temperature_K=state.temperature_K,
            outer_initial_device_voltage_V=state.device_voltage_V,
            first_half=first,
            second_half=second,
            half_dt_s=half,
            capacitance_F=capacitance,
        )
        aggregate_integrity = controller_v2._aggregate_integrity(
            aggregate_ledgers, config
        )
        if not aggregate_integrity.overall_pass:
            raise RuntimeError("NLS-v1 aggregate ledger integrity failed")
        active_path = "embedded_error"
        embedded = controller_v2.compute_embedded_error(
            full.state,
            second.state,
            voltage_scale_V=voltage_scale,
            temperature_scale_K=float(
                controller_v2._controller(config)["embedded_error"][
                    "temperature_scale_K"
                ]
            ),
        )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        error_class = type(error).__name__
        error_message = str(error)
        structured = getattr(error, "diagnostics", None)
        error_diagnostics = structured if isinstance(structured, dict) else None
        if active_path == "full_step" and full_integrity is None:
            full_integrity = controller_v2._failed_integrity(error)
        elif active_path == "first_half_step" and first is None:
            first_integrity = controller_v2._failed_integrity(error)
        elif active_path == "second_half_step" and second is None:
            second_integrity = controller_v2._failed_integrity(error)
        elif active_path == "aggregate_ledgers" and aggregate_integrity is None:
            aggregate_integrity = controller_v2.S2AggregateIntegrity(
                finite=False,
                ledger_pass=False,
                overall_pass=False,
                ledger_relative_residuals={},
                error_class=error_class,
                error_message=error_message,
            )

    legacy_s = (
        None
        if second is None
        else float(
            np.max(np.abs(second.state.conductive_state - state.conductive_state))
        )
    )
    legacy_b = (
        None
        if second is None
        else float(np.max(np.abs(second.state.branch_memory - state.branch_memory)))
    )
    assert full_integrity is not None
    integrity_pass = bool(
        full_integrity.overall_pass
        and first_integrity is not None
        and first_integrity.overall_pass
        and second_integrity is not None
        and second_integrity.overall_pass
        and aggregate_integrity is not None
        and aggregate_integrity.overall_pass
    )
    accepted = bool(
        integrity_pass
        and embedded is not None
        and embedded.e_max
        <= float(
            controller_v2._controller(config)["embedded_error"]["acceptance_max"]
        )
    )
    path_steps = tuple(item for item in (full, first, second) if item is not None)
    any_fallback = any(
        "fixed_point_fallback" in step.nonlinear.method for step in path_steps
    )
    diagnostics = controller_v2.S2EmbeddedIntervalDiagnostics(
        outer_interval_s=interval,
        half_interval_s=half,
        voltage_scale_V=voltage_scale,
        full_input_voltage_V=float(full_voltage),
        first_half_input_voltage_V=float(first_voltage),
        second_half_input_voltage_V=float(second_voltage),
        full_step=full_integrity,
        first_half_step=first_integrity,
        second_half_step=second_integrity,
        aggregate=aggregate_integrity,
        full_nonlinear=None if full is None else full.nonlinear,
        first_half_nonlinear=None if first is None else first.nonlinear,
        second_half_nonlinear=None if second is None else second.nonlinear,
        embedded_error=embedded,
        legacy_conductive_increment=legacy_s,
        legacy_branch_increment=legacy_b,
        rejection_index=int(rejection_index),
        below_floor_remainder=bool(below_floor_remainder),
        at_outer_floor=bool(at_outer_floor),
        accepted=accepted,
        coupled_solve_count=coupled_solves,
        any_fallback=any_fallback,
        wall_time_s=float(perf_counter() - started),
    )
    step: controller_v2.S2EmbeddedStepResult | None = None
    if accepted:
        assert first is not None and second is not None
        assert aggregate_ledgers is not None and energy is not None
        step = controller_v2.S2EmbeddedStepResult(
            state=second.state,
            electrical=second.electrical,
            ledgers=aggregate_ledgers,
            lateral_flux=second.lateral_flux,
            nonlinear=_combined_nonlinear_nls_v1((first, second)),
            controller=diagnostics,
            aggregate_energy=energy,
            accepted_first_half=first,
        )
    return NLSV1EmbeddedAttemptObservation(
        previous_state=state,
        step=step,
        full_candidate=full,
        first_half_candidate=first,
        second_half_candidate=second,
        diagnostics=diagnostics,
        error_class=error_class,
        error_message=error_message,
        error_diagnostics=error_diagnostics,
        aggregate_ledgers=aggregate_ledgers,
        aggregate_energy=energy,
    )


def _nls_candidate_payload(candidate: legacy.S2StepResult | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    nonlinear = candidate.nonlinear
    return {
        "solver_identity": str(nonlinear.solver_identity),
        "method": str(nonlinear.method),
        "iterations": int(nonlinear.iterations),
        "scaled_residual_inf": float(nonlinear.scaled_residual_inf),
        "fixed_point_defect_inf": float(nonlinear.fixed_point_defect_inf),
        "residual_blocks_inf": {
            str(name): float(value)
            for name, value in nonlinear.residual_blocks_inf.items()
        },
        "krylov_matvecs": int(nonlinear.krylov_matvecs),
        "armijo_backtracks": int(nonlinear.armijo_backtracks),
        "predictor_picard_iterations": int(nonlinear.predictor_picard_iterations),
        "fallback_picard_iterations": int(nonlinear.fallback_picard_iterations),
        "fallback_iteration_history": [
            asdict(item) for item in nonlinear.fallback_iteration_history
        ],
        "newton_failure": nonlinear.newton_failure,
    }


def _attempt_payload_nls_v1(
    observation: NLSV1EmbeddedAttemptObservation, **kwargs: Any
) -> dict[str, Any]:
    payload = controller_v3._attempt_payload(observation, **kwargs)
    payload["nonlinear_solver_identity"] = NLS_V1_ID
    payload["error_diagnostics"] = observation.error_diagnostics
    payload["nls_v1"] = {
        "full_step": _nls_candidate_payload(observation.full_candidate),
        "first_half_step": _nls_candidate_payload(observation.first_half_candidate),
        "second_half_step": _nls_candidate_payload(observation.second_half_candidate),
    }
    return payload


def simulate_s2_protocol_nls_v1(
    initial_state: legacy.S2State,
    *,
    case_id: str,
    protocol: dict,
    protocol_id: str,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    time_divisor: int = 1,
    final_time_s: float | None = None,
    maximum_accepted_steps: int | None = None,
    maximum_wall_clock_s: float | None = None,
    retain_full_history: bool = True,
    retained_step_limit: int = 0,
    accepted_step_callback: Callable[
        [legacy.S2State, controller_v2.S2EmbeddedStepResult, float, float, float],
        None,
    ]
    | None = None,
    attempted_candidate_callback: Callable[[NLSV1EmbeddedAttemptObservation], None]
    | None = None,
    attempt_record_callback: Callable[[dict[str, Any]], None] | None = None,
    failure_callback: Callable[[dict[str, Any]], None] | None = None,
    cache: legacy.S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
    performance_timings: legacy.S2PerformanceTimings | None = None,
) -> legacy.S2ProtocolResult:
    """Run controller-v3 scheduling with the independently versioned NLS-v1."""

    if not case_id:
        raise ValueError("NLS-v1 protocol execution requires a nonempty case_id")
    if maximum_accepted_steps is not None and maximum_accepted_steps <= 0:
        raise ValueError("maximum_accepted_steps must be positive")
    if maximum_wall_clock_s is not None and (
        not np.isfinite(maximum_wall_clock_s) or maximum_wall_clock_s <= 0.0
    ):
        raise ValueError("maximum_wall_clock_s must be finite and positive")
    if retained_step_limit < 0:
        raise ValueError("retained_step_limit cannot be negative")

    maximum_interval, floor_interval = controller_v2.controller_v2_limits(
        config, time_divisor
    )
    minimum_recoverable = (
        floor_interval * controller_v3.SUBFLOOR_RECOVERY_MIN_FACTOR
    )
    stop = float(
        config["reference_solver"]["time_grid"]["final_time_s"]
        if final_time_s is None
        else final_time_s
    )
    if not np.isfinite(stop) or stop <= initial_state.time_s:
        raise ValueError("NLS-v1 final time must follow its initial time")
    controller_v2.protocol_voltage_scale(config, protocol_id)
    discontinuities = tuple(
        float(value)
        for value in legacy.protocol_discontinuities(protocol)
        if initial_state.time_s < float(value) <= stop
    )
    fields.validate_grid(grid)
    legacy.validate_s2_state(initial_state, grid, closure)
    if cache is not None:
        cache.validate_context(grid, fields)

    controller = config["reference_solver"]["active_time_controller"]
    rejection_cap = int(controller["outer_interval"]["outer_rejection_cap"])
    case_rejection_cap = int(
        config["reference_solver"]["time_grid"]["maximum_rejected_steps_per_case"]
    )
    easy_max = float(controller["growth"]["easy_error_max"])
    easy_required = int(controller["growth"]["required_consecutive_easy_intervals"])
    eps = max(1.0e-18, abs(stop) * 1.0e-14)

    state = initial_state
    current_interval = maximum_interval
    steps: list[controller_v2.S2EmbeddedStepResult] = []
    accepted_dts: list[float] = []
    interval_wall_times: list[float] = []
    accepted_steps = rejected = 0
    embedded_rejections = integrity_rejections = 0
    endpoint_remainders = growth_events = locked_floor_failures = 0
    full_solves = half_solves = total_solves = 0
    newton_iterations = krylov = armijo = fallback_picard = fallback_steps = 0
    maximum_increment = 0.0
    maxima = {name: 0.0 for name in ("e_T", "e_s", "e_b", "e_V", "e_max")}
    easy_streak = 0
    minimum_interval = float("inf")
    maximum_accepted_interval = 0.0
    stop_reason = "requested_final_time_reached"
    started = perf_counter()

    while state.time_s < stop - eps:
        if (
            maximum_wall_clock_s is not None
            and perf_counter() - started >= maximum_wall_clock_s
        ):
            stop_reason = "maximum_wall_clock_reached"
            break
        if (
            maximum_accepted_steps is not None
            and accepted_steps >= maximum_accepted_steps
        ):
            stop_reason = "maximum_accepted_steps_reached"
            break
        future = [value for value in discontinuities if value > state.time_s + eps]
        next_discontinuity = min(future) if future else None
        target = stop if next_discontinuity is None else min(stop, next_discontinuity)
        proposed_interval = current_interval
        remaining = target - state.time_s
        interval = min(proposed_interval, remaining)
        previous_state = state
        rejection_index = 0
        had_rejection = False
        interval_started = perf_counter()

        while True:
            below_floor_remainder = interval < floor_interval - eps
            observation = attempt_s2_embedded_interval_nls_v1(
                state,
                protocol=protocol,
                protocol_id=protocol_id,
                outer_interval_s=interval,
                grid=grid,
                closure=closure,
                fields=fields,
                config=config,
                rejection_index=rejection_index,
                below_floor_remainder=below_floor_remainder,
                at_outer_floor=bool(
                    interval <= floor_interval * (1.0 + 1.0e-12)
                ),
                cache=cache,
                use_equivalent_optimizations=use_equivalent_optimizations,
                use_unit_voltage_scaling=use_unit_voltage_scaling,
                performance_timings=performance_timings,
            )
            if attempted_candidate_callback is not None:
                attempted_candidate_callback(observation)
            attempt_record = _attempt_payload_nls_v1(
                observation,
                case_id=case_id,
                protocol_id=protocol_id,
                time_divisor=time_divisor,
                proposed_outer_interval_s=proposed_interval,
                attempted_outer_interval_s=interval,
                floor_outer_interval_s=floor_interval,
                target_time_s=target,
                next_discontinuity_s=next_discontinuity,
                remaining_to_target_s=remaining,
                minimum_recoverable_interval_s=minimum_recoverable,
                terminal=False,
            )
            if attempt_record_callback is not None:
                attempt_record_callback(attempt_record)

            solves = observation.diagnostics.coupled_solve_count
            total_solves += solves
            full_solves += int(solves >= 1)
            half_solves += int(solves >= 2) + int(solves >= 3)
            for candidate_path in (
                observation.full_candidate,
                observation.first_half_candidate,
                observation.second_half_candidate,
            ):
                if candidate_path is None:
                    continue
                nonlinear = candidate_path.nonlinear
                newton_iterations += nonlinear.iterations
                krylov += nonlinear.krylov_matvecs
                armijo += nonlinear.armijo_backtracks
                fallback_picard += nonlinear.fallback_picard_iterations
            embedded = observation.diagnostics.embedded_error
            if embedded is not None:
                for name in maxima:
                    maxima[name] = max(maxima[name], float(getattr(embedded, name)))
            if observation.step is not None:
                candidate = observation.step
                break

            integrity_failure = bool(
                attempt_record["rejection_class"] == "integrity_or_solver"
            )
            integrity_rejections += int(integrity_failure)
            embedded_rejections += int(not integrity_failure)
            locked_floor_failures += int(
                interval <= floor_interval * (1.0 + 1.0e-12)
            )
            terminal_message: str | None = None
            if rejected + 1 > case_rejection_cap:
                terminal_message = "NLS-v1 per-case rejection cap exceeded"
            elif rejection_index + 1 > rejection_cap:
                terminal_message = "NLS-v1 outer rejection cap exceeded"
            elif interval <= minimum_recoverable * (1.0 + 1.0e-12):
                terminal_message = "NLS-v1 sub-floor recovery exhausted"
            if terminal_message is not None:
                controller_v3._raise_terminal(
                    terminal_message,
                    observation,
                    attempt_record,
                    failure_callback=failure_callback,
                )
            rejected += 1
            rejection_index += 1
            had_rejection = True
            interval = max(0.5 * interval, minimum_recoverable)

        interval_wall = perf_counter() - interval_started
        accepted_steps += 1
        accepted_dts.append(float(interval))
        if retain_full_history:
            steps.append(candidate)
        elif retained_step_limit:
            steps.append(candidate)
            if len(steps) > retained_step_limit:
                del steps[0]
        accepted_voltage = candidate.controller.second_half_input_voltage_V
        if accepted_step_callback is not None:
            accepted_step_callback(
                previous_state,
                candidate,
                float(interval),
                float(accepted_voltage),
                float(interval_wall),
            )
        interval_wall_times.append(float(perf_counter() - interval_started))
        state = candidate.state
        minimum_interval = min(minimum_interval, interval)
        maximum_accepted_interval = max(maximum_accepted_interval, interval)
        maximum_increment = max(
            maximum_increment,
            float(candidate.controller.legacy_conductive_increment or 0.0),
            float(candidate.controller.legacy_branch_increment or 0.0),
        )
        endpoint_remainders += int(below_floor_remainder)
        fallback_steps += int(candidate.controller.any_fallback)
        embedded = candidate.controller.embedded_error
        assert embedded is not None
        if (
            embedded.e_max <= easy_max
            and not had_rejection
            and not candidate.controller.any_fallback
            and not below_floor_remainder
        ):
            easy_streak += 1
        else:
            easy_streak = 0
        if below_floor_remainder:
            current_interval = proposed_interval
        else:
            current_interval = interval
            if easy_streak >= easy_required:
                expanded_interval = min(2.0 * current_interval, maximum_interval)
                growth_events += int(expanded_interval > current_interval)
                current_interval = expanded_interval
                easy_streak = 0

    completed = bool(state.time_s >= stop - eps)
    dt_values = np.asarray(accepted_dts, dtype=float)
    wall_values = np.asarray(interval_wall_times, dtype=float)
    diagnostics = controller_v3._empty_diagnostics(
        accepted_steps=accepted_steps,
        rejected_steps=rejected,
        nonlinear_rejections=integrity_rejections,
        endpoint_remainder_steps=endpoint_remainders,
        minimum_accepted_step_s=(
            0.0 if not accepted_steps else minimum_interval
        ),
        maximum_accepted_step_s=maximum_accepted_interval,
        maximum_transition_increment=maximum_increment,
        fallback_steps=fallback_steps,
        newton_iterations=int(newton_iterations),
        krylov_matvecs=int(krylov),
        armijo_backtracks=int(armijo),
        fallback_picard_iterations=int(fallback_picard),
        step_wall_time_p50_s=(
            float(np.quantile(wall_values, 0.50)) if wall_values.size else 0.0
        ),
        step_wall_time_p90_s=(
            float(np.quantile(wall_values, 0.90)) if wall_values.size else 0.0
        ),
        step_wall_time_max_s=(
            float(np.max(wall_values)) if wall_values.size else 0.0
        ),
        accepted_dt_p10_s=(
            float(np.quantile(dt_values, 0.10)) if dt_values.size else 0.0
        ),
        accepted_dt_p50_s=(
            float(np.quantile(dt_values, 0.50)) if dt_values.size else 0.0
        ),
        accepted_dt_p90_s=(
            float(np.quantile(dt_values, 0.90)) if dt_values.size else 0.0
        ),
        embedded_error_rejections=embedded_rejections,
        integrity_rejections=integrity_rejections,
        locked_floor_failures=locked_floor_failures,
        growth_events=growth_events,
        full_step_solves=full_solves,
        half_step_solves=half_solves,
        total_coupled_solves=total_solves,
        **{f"maximum_{key}": value for key, value in maxima.items()},
    )
    return legacy.S2ProtocolResult(
        steps=tuple(steps),
        diagnostics=diagnostics,
        requested_final_time_s=stop,
        achieved_final_time_s=float(state.time_s),
        completed=completed,
        stop_reason="requested_final_time_reached" if completed else stop_reason,
    )


__all__ = [
    "NLS_V1_ID",
    "NLSV1Diagnostics",
    "NLSV1EmbeddedAttemptObservation",
    "NLSV1FixedPointIteration",
    "NLSV1SolveError",
    "advance_s2_backward_euler_nls_v1",
    "attempt_s2_embedded_interval_nls_v1",
    "simulate_s2_protocol_nls_v1",
]
