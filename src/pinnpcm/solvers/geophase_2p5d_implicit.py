"""Implicit electrothermal time integration for the Phase 1 reference judge.

This module is deliberately independent of every PINN residual implementation.
It combines a conservative sheet FVM, region-conditioned passive thermal
memory, and a backward-Euler external circuit.  It is a synthetic numerical
reference, not an author-code reproduction or a calibrated device model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np
from scipy import sparse
from scipy.optimize import KrylovJacobian
from scipy.sparse.linalg import spsolve

from pinnpcm.physics.geophase_geometry import (
    BARE_REGION,
    CONTACT_REGION,
    GeoPhaseGrid,
)
from pinnpcm.physics.geophase_ledgers import (
    LedgerBalance,
    circuit_ledger,
    combined_electrothermal_ledger,
    device_power_identity,
    thermal_ledger,
)
from pinnpcm.physics.vertical_thermal_memory import PassiveThermalLadder
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_2p5d_fvm import (
    SheetElectricalSolution,
    assemble_lateral_thermal_matrix,
    solve_sheet_electrical,
)


@dataclass(frozen=True)
class GeoPhaseState:
    time_s: float
    temperature_K: np.ndarray
    memory_temperature_K: np.ndarray
    conductive_state: np.ndarray
    branch_memory: np.ndarray
    device_voltage_V: float


@dataclass(frozen=True)
class NonlinearDiagnostics:
    method: str
    iterations: int
    scaled_residual_inf: float
    scaled_update_inf: float
    converged: bool


@dataclass(frozen=True)
class GeoPhaseStepResult:
    state: GeoPhaseState
    electrical: SheetElectricalSolution
    thermal_balance: LedgerBalance
    circuit_balance: LedgerBalance
    combined_balance: LedgerBalance
    device_power_balance: LedgerBalance
    nonlinear: NonlinearDiagnostics


@dataclass(frozen=True)
class AdaptiveProtocolDiagnostics:
    accepted_steps: int
    rejected_steps: int
    transition_rejections: int
    nonlinear_rejections: int
    minimum_accepted_step_s: float
    maximum_accepted_step_s: float
    maximum_transition_increment: float


@dataclass(frozen=True)
class GeoPhaseProtocolResult:
    steps: tuple[GeoPhaseStepResult, ...]
    diagnostics: AdaptiveProtocolDiagnostics


def _validate_ladders(
    ladders: Mapping[str, PassiveThermalLadder],
) -> tuple[PassiveThermalLadder, PassiveThermalLadder]:
    try:
        bare = ladders["bare_vo2"]
        contact = ladders["electrode_covered_vo2"]
    except KeyError as error:
        raise ValueError("both locked region-specific thermal ladders are required") from error
    if bare.order != contact.order:
        raise ValueError("both region ladders must use the same K order")
    if bare.order not in {1, 2, 3}:
        raise ValueError("the active Phase 1 solver only permits K=1,2,3")
    return bare, contact


def initial_state(
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    ladders: Mapping[str, PassiveThermalLadder],
    config: dict,
) -> GeoPhaseState:
    """Return the locked equilibrium initial condition."""

    bare, _ = _validate_ladders(ladders)
    ambient = float(config["physics_contract"]["thermal"]["ambient_temperature_K"])
    temperature = np.full(grid.shape, ambient, dtype=float)
    branch = np.ones(grid.shape, dtype=float)
    state = closure.equilibrium_state(temperature, branch)
    memory = np.full((bare.order, *grid.shape), ambient, dtype=float)
    return GeoPhaseState(
        time_s=0.0,
        temperature_K=temperature,
        memory_temperature_K=memory,
        conductive_state=state,
        branch_memory=branch,
        device_voltage_V=0.0,
    )


def _validate_state(
    state: GeoPhaseState,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    order: int,
) -> None:
    if state.temperature_K.shape != grid.shape:
        raise ValueError("temperature state shape does not match the grid")
    if state.memory_temperature_K.shape != (order, *grid.shape):
        raise ValueError("thermal-memory state shape does not match grid and K")
    if state.conductive_state.shape != grid.shape or state.branch_memory.shape != grid.shape:
        raise ValueError("phase-state shape does not match the grid")
    arrays = (
        state.temperature_K,
        state.memory_temperature_K,
        state.conductive_state,
        state.branch_memory,
        np.asarray([state.time_s, state.device_voltage_V]),
    )
    if any(not np.isfinite(array).all() for array in arrays):
        raise ValueError("the electrothermal state contains nonfinite values")
    closure.validate_temperature(state.temperature_K)
    closure.validate_temperature(state.memory_temperature_K)
    if np.any(state.conductive_state < 0.0) or np.any(state.conductive_state > 1.0):
        raise ValueError("conductive state is outside [0,1]")
    if np.any(np.abs(state.branch_memory) > 1.0):
        raise ValueError("branch memory is outside [-1,1]")


def _regional_parameter_fields(
    grid: GeoPhaseGrid,
    ladders: Mapping[str, PassiveThermalLadder],
) -> tuple[np.ndarray, np.ndarray]:
    bare, contact = _validate_ladders(ladders)
    order = bare.order
    capacities = np.empty((order, *grid.shape), dtype=float)
    links = np.empty((order + 1, *grid.shape), dtype=float)
    for index in range(order):
        capacities[index] = np.where(
            grid.region_index == BARE_REGION,
            bare.capacities_J_m2K[index],
            contact.capacities_J_m2K[index],
        )
    for index in range(order + 1):
        links[index] = np.where(
            grid.region_index == BARE_REGION,
            bare.conductances_W_m2K[index],
            contact.conductances_W_m2K[index],
        )
    if np.any(grid.region_index == CONTACT_REGION) and not np.any(grid.contact_mask):
        raise ValueError("contact thermal kernel is not mapped to a contact mask")
    return capacities, links


def _pack(
    temperature_K: np.ndarray,
    memory_temperature_K: np.ndarray,
    conductive_state: np.ndarray,
    branch_memory: np.ndarray,
    device_voltage_V: float,
) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(temperature_K, dtype=float).reshape(-1),
            np.asarray(memory_temperature_K, dtype=float).reshape(-1),
            np.asarray(conductive_state, dtype=float).reshape(-1),
            np.asarray(branch_memory, dtype=float).reshape(-1),
            np.asarray([device_voltage_V], dtype=float),
        ]
    )


def _unpack(vector: np.ndarray, grid: GeoPhaseGrid, order: int) -> tuple[np.ndarray, ...]:
    values = np.asarray(vector, dtype=float)
    cells = grid.nx * grid.ny
    expected = cells * (order + 3) + 1
    if values.shape != (expected,):
        raise ValueError("nonlinear vector has the wrong dimension")
    offset = 0
    temperature = values[offset : offset + cells].reshape(grid.shape)
    offset += cells
    memory = values[offset : offset + order * cells].reshape((order, *grid.shape))
    offset += order * cells
    state = values[offset : offset + cells].reshape(grid.shape)
    offset += cells
    branch = values[offset : offset + cells].reshape(grid.shape)
    voltage = float(values[-1])
    return temperature, memory, state, branch, voltage


def _solve_linear_thermal_memory(
    *,
    grid: GeoPhaseGrid,
    old_state: GeoPhaseState,
    cell_joule_power_W: np.ndarray,
    capacities_J_m2K: np.ndarray,
    links_W_m2K: np.ndarray,
    active_areal_capacity_J_m2K: float,
    lateral_matrix: sparse.csr_matrix,
    ambient_temperature_K: float,
    dt_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve the coupled linear T/z backward-Euler block exactly."""

    order = capacities_J_m2K.shape[0]
    cells = grid.nx * grid.ny
    area = grid.cell_area_m2
    active_capacity_cell = active_areal_capacity_J_m2K * area
    identity = sparse.eye(cells, format="csr")
    blocks: list[list[sparse.spmatrix | None]] = [
        [None for _ in range(order + 1)] for _ in range(order + 1)
    ]
    g0 = sparse.diags((area * links_W_m2K[0]).reshape(-1))
    blocks[0][0] = (
        active_capacity_cell / dt_s * identity + lateral_matrix + g0
    )
    blocks[0][1] = -g0
    rhs_parts = [
        active_capacity_cell / dt_s * old_state.temperature_K.reshape(-1)
        + np.asarray(cell_joule_power_W, dtype=float).reshape(-1)
    ]
    for index in range(order):
        left = sparse.diags((area * links_W_m2K[index]).reshape(-1))
        right = sparse.diags((area * links_W_m2K[index + 1]).reshape(-1))
        storage = sparse.diags(
            (area * capacities_J_m2K[index] / dt_s).reshape(-1)
        )
        blocks[index + 1][index + 1] = storage + left + right
        blocks[index + 1][index] = -left
        if index + 1 < order:
            blocks[index + 1][index + 2] = -right
        rhs = (
            area
            * capacities_J_m2K[index].reshape(-1)
            / dt_s
            * old_state.memory_temperature_K[index].reshape(-1)
        )
        if index + 1 == order:
            rhs = rhs + area * links_W_m2K[index + 1].reshape(-1) * ambient_temperature_K
        rhs_parts.append(rhs)
    matrix = sparse.bmat(blocks, format="csr")
    solution = np.asarray(spsolve(matrix, np.concatenate(rhs_parts)), dtype=float)
    if not np.isfinite(solution).all():
        raise FloatingPointError("implicit thermal-memory solve produced nonfinite values")
    temperature = solution[:cells].reshape(grid.shape)
    memory = solution[cells:].reshape((order, *grid.shape))
    return temperature, memory


def _fixed_point_map(
    vector: np.ndarray,
    *,
    old_state: GeoPhaseState,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    capacities_J_m2K: np.ndarray,
    links_W_m2K: np.ndarray,
    active_areal_capacity_J_m2K: float,
    lateral_matrix: sparse.csr_matrix,
    ambient_temperature_K: float,
    load_resistance_ohm: float,
    capacitance_F: float,
) -> np.ndarray:
    order = capacities_J_m2K.shape[0]
    temperature, _, state, branch, _ = _unpack(vector, grid, order)
    conductivity = closure.conductivity_S_m(temperature, state)
    unit = solve_sheet_electrical(grid, conductivity, 1.0)
    device_conductance = unit.source_current_A
    denominator = capacitance_F / dt_s + 1.0 / load_resistance_ohm + device_conductance
    voltage = (
        capacitance_F / dt_s * old_state.device_voltage_V
        + input_voltage_V / load_resistance_ohm
    ) / denominator
    electrical = solve_sheet_electrical(grid, conductivity, voltage)
    new_temperature, new_memory = _solve_linear_thermal_memory(
        grid=grid,
        old_state=old_state,
        cell_joule_power_W=electrical.cell_joule_power_W,
        capacities_J_m2K=capacities_J_m2K,
        links_W_m2K=links_W_m2K,
        active_areal_capacity_J_m2K=active_areal_capacity_J_m2K,
        lateral_matrix=lateral_matrix,
        ambient_temperature_K=ambient_temperature_K,
        dt_s=dt_s,
    )
    closure.validate_temperature(new_temperature)
    heating_activation, cooling_activation = closure.branch_activations(
        new_temperature, old_state.temperature_K, dt_s
    )
    branch_ratio = dt_s / closure.branch_relaxation_s
    new_branch = (
        old_state.branch_memory
        + branch_ratio * (heating_activation - cooling_activation)
    ) / (
        1.0 + branch_ratio * (heating_activation + cooling_activation)
    )
    equilibrium = closure.equilibrium_state(new_temperature, new_branch)
    state_ratio = dt_s / closure.state_relaxation_s
    new_state = (old_state.conductive_state + state_ratio * equilibrium) / (
        1.0 + state_ratio
    )
    return _pack(new_temperature, new_memory, new_state, new_branch, voltage)


def _scaled_residual(
    vector: np.ndarray,
    *,
    old_state: GeoPhaseState,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    capacities_J_m2K: np.ndarray,
    links_W_m2K: np.ndarray,
    active_areal_capacity_J_m2K: float,
    lateral_matrix: sparse.csr_matrix,
    ambient_temperature_K: float,
    load_resistance_ohm: float,
    capacitance_F: float,
) -> np.ndarray:
    """Evaluate the fully coupled backward-Euler equations in SI-scaled form."""

    order = capacities_J_m2K.shape[0]
    temperature, memory, state, branch, voltage = _unpack(vector, grid, order)
    closure.validate_temperature(temperature)
    closure.validate_temperature(memory)
    if np.any(state < 0.0) or np.any(state > 1.0) or np.any(np.abs(branch) > 1.0):
        raise ValueError("nonlinear iterate left its admissible state bounds")
    conductivity = closure.conductivity_S_m(temperature, state)
    electrical = solve_sheet_electrical(grid, conductivity, voltage)
    area = grid.cell_area_m2
    active_capacity_cell = active_areal_capacity_J_m2K * area
    flat_temperature = temperature.reshape(-1)
    thermal = (
        active_capacity_cell
        * (flat_temperature - old_state.temperature_K.reshape(-1))
        / dt_s
        + lateral_matrix @ flat_temperature
        + area * links_W_m2K[0].reshape(-1) * (flat_temperature - memory[0].reshape(-1))
        - electrical.cell_joule_power_W.reshape(-1)
    )
    thermal_scale = np.maximum(
        active_capacity_cell / dt_s
        + np.asarray(lateral_matrix.diagonal())
        + area * links_W_m2K[0].reshape(-1),
        1.0e-18,
    )
    memory_residuals: list[np.ndarray] = []
    memory_scales: list[np.ndarray] = []
    for index in range(order):
        current = memory[index]
        previous = temperature if index == 0 else memory[index - 1]
        following = (
            np.full(grid.shape, ambient_temperature_K)
            if index + 1 == order
            else memory[index + 1]
        )
        residual = area * (
            capacities_J_m2K[index]
            * (current - old_state.memory_temperature_K[index])
            / dt_s
            + links_W_m2K[index] * (current - previous)
            + links_W_m2K[index + 1] * (current - following)
        )
        scale = area * (
            capacities_J_m2K[index] / dt_s
            + links_W_m2K[index]
            + links_W_m2K[index + 1]
        )
        memory_residuals.append(residual.reshape(-1))
        memory_scales.append(np.maximum(scale.reshape(-1), 1.0e-18))
    heating_activation, cooling_activation = closure.branch_activations(
        temperature, old_state.temperature_K, dt_s
    )
    branch_ratio = dt_s / closure.branch_relaxation_s
    branch_residual = (
        branch
        - old_state.branch_memory
        - branch_ratio
        * (
            heating_activation * (1.0 - branch)
            - cooling_activation * (1.0 + branch)
        )
    )
    equilibrium = closure.equilibrium_state(temperature, branch)
    state_residual = (
        state
        - old_state.conductive_state
        - dt_s / closure.state_relaxation_s * (equilibrium - state)
    )
    circuit = (
        capacitance_F * (voltage - old_state.device_voltage_V) / dt_s
        - (input_voltage_V - voltage) / load_resistance_ohm
        + electrical.source_current_A
    )
    circuit_scale = max(
        capacitance_F / dt_s,
        1.0 / load_resistance_ohm,
        abs(electrical.source_current_A),
        1.0e-12,
    )
    return np.concatenate(
        [
            thermal / thermal_scale,
            *(value / scale for value, scale in zip(memory_residuals, memory_scales)),
            state_residual.reshape(-1) / (1.0 + dt_s / closure.state_relaxation_s),
            branch_residual.reshape(-1)
            / (
                1.0
                + branch_ratio
                * (heating_activation + cooling_activation).reshape(-1)
            ),
            np.asarray([circuit / circuit_scale]),
        ]
    )


def _picard_predictor(
    initial_vector: np.ndarray,
    mapping: Callable[[np.ndarray], np.ndarray],
    *,
    maximum_iterations: int,
    relaxation: float,
    update_tolerance: float,
) -> tuple[np.ndarray, int, float]:
    vector = initial_vector.copy()
    update = float("inf")
    for iteration in range(1, maximum_iterations + 1):
        mapped = mapping(vector)
        candidate = (1.0 - relaxation) * vector + relaxation * mapped
        scale = np.maximum(np.abs(candidate), 1.0)
        update = float(np.max(np.abs(candidate - vector) / scale))
        vector = candidate
        if update <= update_tolerance:
            return vector, iteration, update
    return vector, maximum_iterations, update


def _damped_newton_krylov(
    initial_vector: np.ndarray,
    residual: Callable[[np.ndarray], np.ndarray],
    nonlinear_contract: dict,
    linear_contract: dict,
) -> tuple[np.ndarray, int, float, float]:
    """Matrix-free Newton solve with the explicitly locked Armijo bounds."""

    vector = np.asarray(initial_vector, dtype=float).copy()
    function = np.asarray(residual(vector), dtype=float)
    if not np.isfinite(function).all():
        raise FloatingPointError("initial Newton residual is nonfinite")
    residual_limit = max(
        float(nonlinear_contract["scaled_residual_absolute"]),
        float(nonlinear_contract["scaled_residual_relative"]),
    )
    update_limit = float(nonlinear_contract["scaled_update_relative"])
    residual_norm = float(np.max(np.abs(function)))
    if residual_norm <= residual_limit:
        return vector, 0, 0.0, residual_norm

    initial_damping = float(nonlinear_contract["initial_damping"])
    minimum_damping = float(nonlinear_contract["minimum_damping"])
    armijo = float(nonlinear_contract["armijo_coefficient"])
    if not 0.0 < minimum_damping <= initial_damping <= 1.0:
        raise ValueError("locked Newton damping bounds are invalid")
    if not 0.0 < armijo < 1.0:
        raise ValueError("locked Armijo coefficient must lie inside (0,1)")

    jacobian = KrylovJacobian(
        method="lgmres",
        inner_maxiter=50,
        outer_k=10,
    )
    jacobian.setup(vector, function, residual)

    last_update = float("inf")
    for iteration in range(1, int(nonlinear_contract["maximum_newton_iterations"]) + 1):
        base_vector = vector.copy()
        base_function = function.copy()
        base_norm = residual_norm
        inner_tolerance = max(
            float(linear_contract["relative"]),
            float(linear_contract["absolute"]) / max(base_norm, 1.0e-30),
        )
        correction = -np.asarray(
            jacobian.solve(base_function, tol=inner_tolerance), dtype=float
        )
        if not np.isfinite(correction).all():
            raise RuntimeError("Newton Krylov linear solve produced a nonfinite update")

        damping = initial_damping
        accepted = False
        while damping + 1.0e-15 >= minimum_damping:
            candidate = base_vector + damping * correction
            try:
                candidate_function = np.asarray(residual(candidate), dtype=float)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                damping *= 0.5
                continue
            if not np.isfinite(candidate_function).all():
                damping *= 0.5
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
        if not accepted:
            raise RuntimeError("Newton Armijo line search reached the locked minimum damping")
        jacobian.update(vector, function)
        if residual_norm <= residual_limit and last_update <= update_limit:
            return vector, iteration, last_update, residual_norm
        if residual_norm <= residual_limit:
            # The next exact Newton update is zero at a converged root.  Audit
            # it explicitly rather than accepting the preceding large step.
            return vector, iteration, 0.0, residual_norm
    raise RuntimeError("Newton reached the locked maximum iteration count")


def advance_backward_euler(
    old_state: GeoPhaseState,
    *,
    input_voltage_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    ladders: Mapping[str, PassiveThermalLadder],
    config: dict,
) -> GeoPhaseStepResult:
    """Advance one fully coupled step and fail closed on any unmet contract."""

    if dt_s <= 0.0 or not np.isfinite([dt_s, input_voltage_V]).all():
        raise ValueError("time step and input voltage must be finite, with dt>0")
    bare, _ = _validate_ladders(ladders)
    _validate_state(old_state, grid, closure, bare.order)
    capacities, links = _regional_parameter_fields(grid, ladders)
    thermal_contract = config["parameter_contract"]["active_plane_thermal"]
    active_areal_capacity = (
        float(thermal_contract["vo2_volumetric_heat_capacity_J_m3K"])
        * grid.thickness_m
    )
    lateral = assemble_lateral_thermal_matrix(
        grid, float(thermal_contract["vo2_thermal_conductivity_W_mK"])
    )
    ambient = float(config["physics_contract"]["thermal"]["ambient_temperature_K"])
    circuit = config["physics_contract"]["circuit"]
    load_resistance = float(circuit["load_resistance_ohm"])
    capacitance = float(circuit["parallel_capacitance_F"])
    nonlinear = config["reference_solver"]["nonlinear_tolerances"]

    old_vector = _pack(
        old_state.temperature_K,
        old_state.memory_temperature_K,
        old_state.conductive_state,
        old_state.branch_memory,
        old_state.device_voltage_V,
    )
    common = dict(
        old_state=old_state,
        input_voltage_V=float(input_voltage_V),
        dt_s=float(dt_s),
        grid=grid,
        closure=closure,
        capacities_J_m2K=capacities,
        links_W_m2K=links,
        active_areal_capacity_J_m2K=active_areal_capacity,
        lateral_matrix=lateral,
        ambient_temperature_K=ambient,
        load_resistance_ohm=load_resistance,
        capacitance_F=capacitance,
    )
    mapping = lambda vector: _fixed_point_map(vector, **common)
    residual = lambda vector: _scaled_residual(vector, **common)
    predictor, _, _ = _picard_predictor(
        old_vector,
        mapping,
        maximum_iterations=min(
            8, int(nonlinear["fixed_point_fallback_maximum_iterations"])
        ),
        relaxation=float(nonlinear["fixed_point_relaxation"]),
        update_tolerance=float(nonlinear["scaled_update_relative"]),
    )

    method = "damped_newton_krylov"
    try:
        solved, iterations, update_inf, residual_inf = _damped_newton_krylov(
            predictor,
            residual,
            nonlinear,
            config["reference_solver"]["linear_solver_tolerances"],
        )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
        method = "fail_closed_fixed_point_fallback"
        solved, iterations, update = _picard_predictor(
            predictor,
            mapping,
            maximum_iterations=int(nonlinear["fixed_point_fallback_maximum_iterations"]),
            relaxation=float(nonlinear["fixed_point_relaxation"]),
            update_tolerance=float(nonlinear["scaled_update_relative"]),
        )
        update_inf = update
        residual_inf = float(np.max(np.abs(residual(solved))))
    residual_threshold = max(
        float(nonlinear["scaled_residual_absolute"]),
        float(nonlinear["scaled_residual_relative"]),
    )
    # Audit both solvers with the contract-equivalent final fixed-point defect.
    mapped_solution = mapping(solved)
    update_inf = float(
        np.max(np.abs(mapped_solution - solved) / np.maximum(np.abs(solved), 1.0))
    )
    converged = residual_inf <= residual_threshold and update_inf <= float(
        nonlinear["scaled_update_relative"]
    )
    if not converged:
        raise RuntimeError(
            "implicit step failed closed: "
            f"residual={residual_inf:.6e}, update={update_inf:.6e}, method={method}"
        )

    temperature, memory, state, branch, voltage = _unpack(solved, grid, bare.order)
    new_state = GeoPhaseState(
        time_s=old_state.time_s + dt_s,
        temperature_K=temperature,
        memory_temperature_K=memory,
        conductive_state=state,
        branch_memory=branch,
        device_voltage_V=voltage,
    )
    _validate_state(new_state, grid, closure, bare.order)
    conductivity = closure.conductivity_S_m(temperature, state)
    electrical = solve_sheet_electrical(grid, conductivity, voltage)
    area = grid.cell_area_m2
    active_storage = float(
        np.sum(active_areal_capacity * area * (temperature - old_state.temperature_K) / dt_s)
    )
    memory_storage = float(
        np.sum(area * capacities * (memory - old_state.memory_temperature_K) / dt_s)
    )
    sink = float(np.sum(area * links[-1] * (memory[-1] - ambient)))
    lateral_outflow = float(np.sum(lateral @ temperature.reshape(-1)))
    thermal_balance = thermal_ledger(
        joule_power_W=electrical.joule_power_W,
        active_storage_rate_W=active_storage,
        memory_storage_rate_W=memory_storage,
        vertical_sink_power_W=sink,
        lateral_outflow_power_W=lateral_outflow,
    )
    circuit_balance = circuit_ledger(
        input_voltage_V=input_voltage_V,
        old_device_voltage_V=old_state.device_voltage_V,
        new_device_voltage_V=voltage,
        load_resistance_ohm=load_resistance,
        capacitance_F=capacitance,
        device_current_A=electrical.source_current_A,
        dt_s=dt_s,
    )
    combined_balance = combined_electrothermal_ledger(
        input_voltage_V=input_voltage_V,
        old_device_voltage_V=old_state.device_voltage_V,
        new_device_voltage_V=voltage,
        load_resistance_ohm=load_resistance,
        capacitance_F=capacitance,
        dt_s=dt_s,
        active_storage_rate_W=active_storage,
        memory_storage_rate_W=memory_storage,
        vertical_sink_power_W=sink,
        lateral_outflow_power_W=lateral_outflow,
    )
    power_balance = device_power_identity(
        terminal_device_power_W=electrical.terminal_device_power_W,
        field_joule_power_W=electrical.joule_power_W,
    )
    return GeoPhaseStepResult(
        state=new_state,
        electrical=electrical,
        thermal_balance=thermal_balance,
        circuit_balance=circuit_balance,
        combined_balance=combined_balance,
        device_power_balance=power_balance,
        nonlinear=NonlinearDiagnostics(
            method=method,
            iterations=int(iterations),
            scaled_residual_inf=residual_inf,
            scaled_update_inf=update_inf,
            converged=True,
        ),
    )


def simulate_protocol(
    initial: GeoPhaseState,
    *,
    input_voltage: Callable[[float], float],
    time_steps_s: np.ndarray,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    ladders: Mapping[str, PassiveThermalLadder],
    config: dict,
) -> list[GeoPhaseStepResult]:
    """Run a declared sequence of positive steps; no adaptive post-hoc tuning."""

    steps = np.asarray(time_steps_s, dtype=float)
    if steps.ndim != 1 or steps.size == 0 or np.any(steps <= 0.0):
        raise ValueError("time_steps_s must be a non-empty positive vector")
    state = initial
    results: list[GeoPhaseStepResult] = []
    for dt_s in steps:
        result = advance_backward_euler(
            state,
            input_voltage_V=float(input_voltage(state.time_s + float(dt_s))),
            dt_s=float(dt_s),
            grid=grid,
            closure=closure,
            ladders=ladders,
            config=config,
        )
        results.append(result)
        state = result.state
    return results


def _transition_increment(
    old_state: GeoPhaseState, new_state: GeoPhaseState
) -> float:
    return float(
        max(
            np.max(
                np.abs(new_state.conductive_state - old_state.conductive_state)
            ),
            np.max(np.abs(new_state.branch_memory - old_state.branch_memory)),
        )
    )


def simulate_adaptive_protocol(
    initial: GeoPhaseState,
    *,
    input_voltage: Callable[[float], float],
    final_time_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    ladders: Mapping[str, PassiveThermalLadder],
    config: dict,
) -> GeoPhaseProtocolResult:
    """Run the locked fail-closed adaptive backward-Euler policy.

    Each accepted step begins with the locked base maximum step (or the exact
    remaining interval).  A nonlinear failure or an excessive state/branch
    increment rejects the trial and halves it.  The rejected trial is never
    committed, and neither rejection cap may be exceeded.
    """

    time_grid = config["reference_solver"]["time_grid"]
    base_step = float(time_grid["base_max_step_s"])
    transition_step = float(time_grid["transition_max_step_s"])
    threshold = float(time_grid["transition_increment_threshold"])
    per_step_cap = int(time_grid["maximum_rejected_steps_per_accepted_step"])
    per_case_cap = int(time_grid["maximum_rejected_steps_per_case"])
    if not (
        np.isfinite([initial.time_s, final_time_s, base_step, transition_step, threshold]).all()
        and final_time_s > initial.time_s
        and base_step >= transition_step > 0.0
        and threshold > 0.0
        and per_step_cap >= 0
        and per_case_cap >= per_step_cap
    ):
        raise ValueError("adaptive time-grid contract is invalid")

    state = initial
    results: list[GeoPhaseStepResult] = []
    accepted_steps: list[float] = []
    total_rejections = 0
    transition_rejections = 0
    nonlinear_rejections = 0
    maximum_increment = 0.0
    tolerance = 32.0 * np.finfo(float).eps * max(abs(final_time_s), 1.0)

    while state.time_s < final_time_s - tolerance:
        remaining = final_time_s - state.time_s
        trial_step = min(base_step, remaining)
        rejected_this_step = 0
        while True:
            nonlinear_failed = False
            try:
                trial = advance_backward_euler(
                    state,
                    input_voltage_V=float(input_voltage(state.time_s + trial_step)),
                    dt_s=trial_step,
                    grid=grid,
                    closure=closure,
                    ladders=ladders,
                    config=config,
                )
            except (RuntimeError, FloatingPointError, np.linalg.LinAlgError):
                nonlinear_failed = True
                trial = None

            increment = (
                float("inf")
                if trial is None
                else _transition_increment(state, trial.state)
            )
            if trial is not None and increment <= threshold:
                results.append(trial)
                accepted_steps.append(trial_step)
                maximum_increment = max(maximum_increment, increment)
                state = trial.state
                break

            total_rejections += 1
            rejected_this_step += 1
            if nonlinear_failed:
                nonlinear_rejections += 1
            else:
                transition_rejections += 1
            if rejected_this_step > per_step_cap or total_rejections > per_case_cap:
                raise RuntimeError("adaptive backward Euler exceeded a locked rejection cap")
            if trial_step <= transition_step * (1.0 + 1.0e-12):
                raise RuntimeError(
                    "adaptive backward Euler failed at the locked transition step floor"
                )
            trial_step = max(transition_step, 0.5 * trial_step)

    if not results:
        raise RuntimeError("adaptive protocol accepted no time step")
    if abs(results[-1].state.time_s - final_time_s) > tolerance:
        raise RuntimeError("adaptive protocol did not terminate at the locked final time")
    return GeoPhaseProtocolResult(
        steps=tuple(results),
        diagnostics=AdaptiveProtocolDiagnostics(
            accepted_steps=len(results),
            rejected_steps=total_rejections,
            transition_rejections=transition_rejections,
            nonlinear_rejections=nonlinear_rejections,
            minimum_accepted_step_s=float(min(accepted_steps)),
            maximum_accepted_step_s=float(max(accepted_steps)),
            maximum_transition_increment=maximum_increment,
        ),
    )


def simulate_decoupled_copies(
    state_a: GeoPhaseState,
    state_b: GeoPhaseState,
    *,
    input_voltage_a_V: float,
    input_voltage_b_V: float,
    dt_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    ladders: Mapping[str, PassiveThermalLadder],
    config: dict,
) -> tuple[GeoPhaseStepResult, GeoPhaseStepResult]:
    """Advance two strictly independent copies; no nonzero coupling exists here."""

    first = advance_backward_euler(
        state_a,
        input_voltage_V=input_voltage_a_V,
        dt_s=dt_s,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    second = advance_backward_euler(
        state_b,
        input_voltage_V=input_voltage_b_V,
        dt_s=dt_s,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    return first, second
