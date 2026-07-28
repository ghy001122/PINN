"""Conservative sheet-thermal finite volumes for Phase 1-v2 S2.

Electrical transport reuses the separately validated sheet-current solver.
Thermal transport is implemented here in areal form so Ti/Au contributions
remain confined to the electrode mask and no retired vertical ladder enters
the S2 state equation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import factorized, spsolve

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.solvers.geophase_2p5d_fvm import (
    SheetElectricalSolution,
    solve_sheet_electrical,
)


@dataclass(frozen=True)
class LateralFluxAudit:
    """Independent face reconstruction for the no-flux lateral boundary."""

    net_cell_outflow_W: np.ndarray
    x_face_flux_W: np.ndarray
    y_face_flux_W: np.ndarray
    boundary_face_flux_W: np.ndarray
    boundary_outflow_W: float
    internal_pair_cancellation_W: float
    face_to_cell_global_residual_W: float
    matrix_face_relative_mismatch: float
    matrix_face_roundoff_ratio: float


ThermalLinearSolver = Callable[[np.ndarray], np.ndarray]


def scale_unit_sheet_electrical_solution(
    unit_solution: SheetElectricalSolution, source_voltage_V: float
) -> SheetElectricalSolution:
    """Scale one frozen-conductivity 1 V solution without a second solve.

    The caller is responsible for keeping geometry, grid, temperature,
    conductive state, and conductivity fixed.  This function cannot cache or
    reuse a solution across a nonlinear state or accepted time step.
    """

    voltage = float(source_voltage_V)
    if not np.isfinite(voltage):
        raise ValueError("electrical scaling voltage must be finite")
    power_scale = voltage * voltage
    if voltage == 0.0:
        relative_current_imbalance = 0.0
        relative_power_imbalance = 0.0
    else:
        relative_current_imbalance = unit_solution.relative_current_imbalance
        relative_power_imbalance = unit_solution.relative_power_imbalance
    return SheetElectricalSolution(
        potential_V=np.asarray(unit_solution.potential_V, dtype=float) * voltage,
        source_current_A=float(unit_solution.source_current_A * voltage),
        ground_current_A=float(unit_solution.ground_current_A * voltage),
        cell_joule_power_W=(
            np.asarray(unit_solution.cell_joule_power_W, dtype=float) * power_scale
        ),
        joule_power_W=float(unit_solution.joule_power_W * power_scale),
        terminal_device_power_W=float(
            unit_solution.terminal_device_power_W * power_scale
        ),
        relative_current_imbalance=float(relative_current_imbalance),
        relative_power_imbalance=float(relative_power_imbalance),
    )


def _harmonic_mean(left: float, right: float) -> float:
    if left <= 0.0 or right <= 0.0:
        raise ValueError("sheet thermal conductances must be positive")
    return 2.0 * left * right / (left + right)


def _coefficient_field(
    grid: GeoPhaseGrid, sheet_conductance_W_K: np.ndarray | float
) -> np.ndarray:
    field = np.broadcast_to(
        np.asarray(sheet_conductance_W_K, dtype=float), grid.shape
    ).copy()
    if not np.isfinite(field).all() or np.any(field <= 0.0):
        raise ValueError("sheet thermal conductance must be finite and positive")
    return field


def assemble_sheet_thermal_matrix(
    grid: GeoPhaseGrid, sheet_conductance_W_K: np.ndarray | float
) -> sparse.csr_matrix:
    """Return ``L`` such that ``L @ T`` is conservative cell heat outflow."""

    coefficient = _coefficient_field(grid, sheet_conductance_W_K)
    ny, nx = grid.shape
    matrix = sparse.lil_matrix((nx * ny, nx * ny), dtype=float)

    def node(iy: int, ix: int) -> int:
        return iy * nx + ix

    for iy in range(ny):
        for ix in range(nx - 1):
            conductance = (
                _harmonic_mean(coefficient[iy, ix], coefficient[iy, ix + 1])
                * grid.dy_m
                / grid.dx_m
            )
            left = node(iy, ix)
            right = node(iy, ix + 1)
            matrix[left, left] += conductance
            matrix[right, right] += conductance
            matrix[left, right] -= conductance
            matrix[right, left] -= conductance
    for iy in range(ny - 1):
        for ix in range(nx):
            conductance = (
                _harmonic_mean(coefficient[iy, ix], coefficient[iy + 1, ix])
                * grid.dx_m
                / grid.dy_m
            )
            lower = node(iy, ix)
            upper = node(iy + 1, ix)
            matrix[lower, lower] += conductance
            matrix[upper, upper] += conductance
            matrix[lower, upper] -= conductance
            matrix[upper, lower] -= conductance
    return matrix.tocsr()


def reconstruct_lateral_fluxes(
    grid: GeoPhaseGrid,
    sheet_conductance_W_K: np.ndarray | float,
    temperature_K: np.ndarray,
    *,
    matrix: sparse.csr_matrix | None = None,
) -> LateralFluxAudit:
    """Reconstruct internal face fluxes independently of a row-sum identity."""

    coefficient = _coefficient_field(grid, sheet_conductance_W_K)
    temperature = np.asarray(temperature_K, dtype=float)
    if temperature.shape != grid.shape or not np.isfinite(temperature).all():
        raise ValueError("temperature must be finite and match the grid")
    net = np.zeros(grid.shape, dtype=float)
    ny, nx = grid.shape
    x_faces = np.zeros((ny, max(nx - 1, 0)), dtype=float)
    y_faces = np.zeros((max(ny - 1, 0), nx), dtype=float)
    for iy in range(ny):
        for ix in range(nx - 1):
            conductance = (
                _harmonic_mean(coefficient[iy, ix], coefficient[iy, ix + 1])
                * grid.dy_m
                / grid.dx_m
            )
            outward_left = conductance * (
                temperature[iy, ix] - temperature[iy, ix + 1]
            )
            x_faces[iy, ix] = outward_left
            net[iy, ix] += outward_left
            net[iy, ix + 1] -= outward_left
    for iy in range(ny - 1):
        for ix in range(nx):
            conductance = (
                _harmonic_mean(coefficient[iy, ix], coefficient[iy + 1, ix])
                * grid.dx_m
                / grid.dy_m
            )
            outward_lower = conductance * (
                temperature[iy, ix] - temperature[iy + 1, ix]
            )
            y_faces[iy, ix] = outward_lower
            net[iy, ix] += outward_lower
            net[iy + 1, ix] -= outward_lower

    # Boundary values are explicit face records, not an inferred matrix row sum.
    # All four outer boundaries are prescribed no-flux in Phase 1-v2.
    boundary_faces = np.zeros(2 * nx + 2 * ny, dtype=float)
    boundary_outflow = float(np.sum(boundary_faces))
    global_residual = float(np.sum(net) - boundary_outflow)
    operator = (
        assemble_sheet_thermal_matrix(grid, coefficient)
        if matrix is None
        else matrix
    )
    if operator.shape != (grid.nx * grid.ny, grid.nx * grid.ny):
        raise ValueError("cached lateral matrix has the wrong shape")
    if not np.isfinite(operator.data).all():
        raise ValueError("cached lateral matrix contains nonfinite entries")
    matrix_outflow = np.asarray(operator @ temperature.reshape(-1), dtype=float)
    difference = matrix_outflow - net.reshape(-1)
    denominator = max(
        float(np.linalg.norm(matrix_outflow)),
        float(np.linalg.norm(net.reshape(-1))),
        1.0e-30,
    )
    row_sum_norm = float(
        np.max(np.asarray(np.abs(operator).sum(axis=1), dtype=float))
    )
    roundoff_floor = (
        64.0
        * np.finfo(float).eps
        * max(row_sum_norm, 1.0e-300)
        * max(float(np.linalg.norm(temperature.reshape(-1))), 1.0)
    )
    difference_norm = float(np.linalg.norm(difference))
    return LateralFluxAudit(
        net_cell_outflow_W=net,
        x_face_flux_W=x_faces,
        y_face_flux_W=y_faces,
        boundary_face_flux_W=boundary_faces,
        boundary_outflow_W=boundary_outflow,
        internal_pair_cancellation_W=float(np.sum(net)),
        face_to_cell_global_residual_W=global_residual,
        matrix_face_relative_mismatch=difference_norm / denominator,
        matrix_face_roundoff_ratio=difference_norm / max(roundoff_floor, 1.0e-300),
    )


def build_s2_thermal_backward_euler_solver(
    grid: GeoPhaseGrid,
    fields: S2ThermalFields,
    dt_s: float,
    *,
    lateral_matrix: sparse.csr_matrix | None = None,
) -> ThermalLinearSolver:
    """Factor one invariant S2 thermal matrix for an exact time-step value."""

    fields.validate_grid(grid)
    if not np.isfinite([dt_s]).all() or dt_s <= 0.0:
        raise ValueError("thermal backward-Euler step must be finite and positive")
    area = grid.cell_area_m2
    capacity_cell = fields.effective_areal_capacity_J_m2K.reshape(-1) * area
    sink_cell = fields.vertical_conductance_W_m2K * area
    lateral = (
        assemble_sheet_thermal_matrix(grid, fields.sheet_thermal_conductance_W_K)
        if lateral_matrix is None
        else lateral_matrix
    )
    expected_shape = (grid.nx * grid.ny, grid.nx * grid.ny)
    if lateral.shape != expected_shape:
        raise ValueError("cached lateral matrix has the wrong shape")
    if not np.isfinite(lateral.data).all():
        raise ValueError("cached lateral matrix contains nonfinite entries")
    matrix = (
        sparse.diags(capacity_cell / dt_s + sink_cell, format="csc")
        + lateral.tocsc()
    )
    raw_solver = factorized(matrix)

    def solve(rhs: np.ndarray) -> np.ndarray:
        values = np.asarray(rhs, dtype=float)
        if values.shape != (grid.nx * grid.ny,) or not np.isfinite(values).all():
            raise ValueError("cached thermal solver RHS is invalid")
        result = np.asarray(raw_solver(values), dtype=float)
        if not np.isfinite(result).all():
            raise FloatingPointError("cached S2 thermal solve produced nonfinite values")
        return result

    return solve


def solve_s2_thermal_backward_euler(
    grid: GeoPhaseGrid,
    fields: S2ThermalFields,
    old_temperature_K: np.ndarray,
    cell_joule_power_W: np.ndarray,
    dt_s: float,
    *,
    external_areal_source_W_m2: np.ndarray | float = 0.0,
    lateral_matrix: sparse.csr_matrix | None = None,
    linear_solver: ThermalLinearSolver | None = None,
) -> np.ndarray:
    """Solve the linear S2 thermal block for one backward-Euler step."""

    fields.validate_grid(grid)
    old = np.asarray(old_temperature_K, dtype=float)
    joule = np.asarray(cell_joule_power_W, dtype=float)
    source = np.broadcast_to(
        np.asarray(external_areal_source_W_m2, dtype=float), grid.shape
    )
    if old.shape != grid.shape or joule.shape != grid.shape:
        raise ValueError("thermal state and cell Joule power must match the grid")
    if not np.isfinite([dt_s]).all() or dt_s <= 0.0:
        raise ValueError("thermal backward-Euler step must be finite and positive")
    if not np.isfinite(old).all() or not np.isfinite(joule).all() or not np.isfinite(source).all():
        raise ValueError("thermal backward-Euler inputs must be finite")
    if np.any(joule < -1.0e-18):
        raise ValueError("cell Joule power cannot be materially negative")

    area = grid.cell_area_m2
    capacity_cell = fields.effective_areal_capacity_J_m2K.reshape(-1) * area
    sink_cell = fields.vertical_conductance_W_m2K * area
    lateral = (
        assemble_sheet_thermal_matrix(grid, fields.sheet_thermal_conductance_W_K)
        if lateral_matrix is None
        else lateral_matrix
    )
    if lateral.shape != (grid.nx * grid.ny, grid.nx * grid.ny):
        raise ValueError("cached lateral matrix has the wrong shape")
    if not np.isfinite(lateral.data).all():
        raise ValueError("cached lateral matrix contains nonfinite entries")
    rhs = (
        capacity_cell / dt_s * old.reshape(-1)
        + joule.reshape(-1)
        + area * source.reshape(-1)
        + sink_cell * fields.ambient_temperature_K
    )
    solver = (
        build_s2_thermal_backward_euler_solver(
            grid, fields, dt_s, lateral_matrix=lateral
        )
        if linear_solver is None
        else linear_solver
    )
    values = np.asarray(solver(np.asarray(rhs, dtype=float)), dtype=float)
    if not np.isfinite(values).all():
        raise FloatingPointError("S2 thermal solve produced nonfinite temperature")
    return values.reshape(grid.shape)


def solve_steady_sheet_thermal_dirichlet(
    grid: GeoPhaseGrid,
    sheet_conductance_W_K: np.ndarray | float,
    vertical_conductance_W_m2K: float,
    ambient_temperature_K: float,
    left_temperature_K: float,
    right_temperature_K: float,
    *,
    external_areal_source_W_m2: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Manufactured steady helper with x Dirichlet and y no-flux faces."""

    coefficient = _coefficient_field(grid, sheet_conductance_W_K)
    source = np.broadcast_to(
        np.asarray(external_areal_source_W_m2, dtype=float), grid.shape
    )
    scalars = np.asarray(
        [
            vertical_conductance_W_m2K,
            ambient_temperature_K,
            left_temperature_K,
            right_temperature_K,
        ],
        dtype=float,
    )
    if not np.isfinite(scalars).all() or vertical_conductance_W_m2K < 0.0:
        raise ValueError("steady manufactured coefficients must be finite and nonnegative")
    if not np.isfinite(source).all():
        raise ValueError("steady manufactured source must be finite")

    area = grid.cell_area_m2
    matrix = assemble_sheet_thermal_matrix(grid, coefficient).tolil()
    matrix.setdiag(
        np.asarray(matrix.diagonal()) + vertical_conductance_W_m2K * area
    )
    rhs = (
        area * source.reshape(-1)
        + vertical_conductance_W_m2K * area * ambient_temperature_K
    )
    rhs = np.asarray(rhs, dtype=float)
    ny, nx = grid.shape
    for iy in range(ny):
        left_conductance = coefficient[iy, 0] * grid.dy_m / (0.5 * grid.dx_m)
        right_conductance = coefficient[iy, -1] * grid.dy_m / (0.5 * grid.dx_m)
        left = iy * nx
        right = iy * nx + nx - 1
        matrix[left, left] += left_conductance
        matrix[right, right] += right_conductance
        rhs[left] += left_conductance * left_temperature_K
        rhs[right] += right_conductance * right_temperature_K
    values = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float)
    if not np.isfinite(values).all():
        raise FloatingPointError("steady S2 manufactured solve produced nonfinite values")
    return values.reshape(grid.shape)


__all__ = [
    "LateralFluxAudit",
    "SheetElectricalSolution",
    "ThermalLinearSolver",
    "assemble_sheet_thermal_matrix",
    "build_s2_thermal_backward_euler_solver",
    "reconstruct_lateral_fluxes",
    "scale_unit_sheet_electrical_solution",
    "solve_s2_thermal_backward_euler",
    "solve_sheet_electrical",
    "solve_steady_sheet_thermal_dirichlet",
]
