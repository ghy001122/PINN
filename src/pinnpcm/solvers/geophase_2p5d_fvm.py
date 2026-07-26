"""Independent conservative x-y finite volumes for the Phase 1 judge."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid


@dataclass(frozen=True)
class SheetElectricalSolution:
    potential_V: np.ndarray
    source_current_A: float
    ground_current_A: float
    cell_joule_power_W: np.ndarray
    joule_power_W: float
    terminal_device_power_W: float
    relative_current_imbalance: float
    relative_power_imbalance: float


def _harmonic_mean(left: float, right: float) -> float:
    return 2.0 * left * right / (left + right)


def solve_sheet_electrical(
    grid: GeoPhaseGrid,
    conductivity_S_m: np.ndarray,
    source_voltage_V: float,
    ground_voltage_V: float = 0.0,
) -> SheetElectricalSolution:
    """Solve div(t*sigma*grad(phi))=0 with finite left/right contacts."""

    sigma = np.asarray(conductivity_S_m, dtype=float)
    if sigma.shape != grid.shape:
        raise ValueError("conductivity shape does not match the x-y grid")
    if not np.isfinite(sigma).all() or np.any(sigma <= 0.0):
        raise ValueError("conductivity must be finite and positive")
    if not np.isfinite([source_voltage_V, ground_voltage_V]).all():
        raise ValueError("terminal voltages must be finite")

    ny, nx = grid.shape
    count = nx * ny
    matrix = sparse.lil_matrix((count, count), dtype=float)
    rhs = np.zeros(count, dtype=float)

    def node(iy: int, ix: int) -> int:
        return iy * nx + ix

    for iy in range(ny):
        for ix in range(nx):
            row = node(iy, ix)
            if ix:
                conductance = (
                    _harmonic_mean(sigma[iy, ix], sigma[iy, ix - 1])
                    * grid.thickness_m
                    * grid.dy_m
                    / grid.dx_m
                )
                matrix[row, row] += conductance
                matrix[row, node(iy, ix - 1)] -= conductance
            else:
                conductance = (
                    sigma[iy, ix]
                    * grid.thickness_m
                    * grid.dy_m
                    / (0.5 * grid.dx_m)
                )
                matrix[row, row] += conductance
                rhs[row] += conductance * source_voltage_V
            if ix + 1 < nx:
                conductance = (
                    _harmonic_mean(sigma[iy, ix], sigma[iy, ix + 1])
                    * grid.thickness_m
                    * grid.dy_m
                    / grid.dx_m
                )
                matrix[row, row] += conductance
                matrix[row, node(iy, ix + 1)] -= conductance
            else:
                conductance = (
                    sigma[iy, ix]
                    * grid.thickness_m
                    * grid.dy_m
                    / (0.5 * grid.dx_m)
                )
                matrix[row, row] += conductance
                rhs[row] += conductance * ground_voltage_V
            if iy:
                conductance = (
                    _harmonic_mean(sigma[iy, ix], sigma[iy - 1, ix])
                    * grid.thickness_m
                    * grid.dx_m
                    / grid.dy_m
                )
                matrix[row, row] += conductance
                matrix[row, node(iy - 1, ix)] -= conductance
            if iy + 1 < ny:
                conductance = (
                    _harmonic_mean(sigma[iy, ix], sigma[iy + 1, ix])
                    * grid.thickness_m
                    * grid.dx_m
                    / grid.dy_m
                )
                matrix[row, row] += conductance
                matrix[row, node(iy + 1, ix)] -= conductance

    values = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float)
    if not np.isfinite(values).all():
        raise FloatingPointError("electrical solve produced nonfinite potential")
    potential = values.reshape(grid.shape)
    source_current = 0.0
    ground_current = 0.0
    cell_joule = np.zeros(grid.shape, dtype=float)
    for iy in range(ny):
        left_conductance = (
            sigma[iy, 0]
            * grid.thickness_m
            * grid.dy_m
            / (0.5 * grid.dx_m)
        )
        right_conductance = (
            sigma[iy, -1]
            * grid.thickness_m
            * grid.dy_m
            / (0.5 * grid.dx_m)
        )
        source_current += left_conductance * (source_voltage_V - potential[iy, 0])
        ground_current += right_conductance * (ground_voltage_V - potential[iy, -1])
        cell_joule[iy, 0] += left_conductance * (
            source_voltage_V - potential[iy, 0]
        ) ** 2
        cell_joule[iy, -1] += right_conductance * (
            ground_voltage_V - potential[iy, -1]
        ) ** 2

    for iy in range(ny):
        for ix in range(nx - 1):
            conductance = (
                _harmonic_mean(sigma[iy, ix], sigma[iy, ix + 1])
                * grid.thickness_m
                * grid.dy_m
                / grid.dx_m
            )
            power = conductance * (potential[iy, ix] - potential[iy, ix + 1]) ** 2
            cell_joule[iy, ix] += 0.5 * power
            cell_joule[iy, ix + 1] += 0.5 * power
    for iy in range(ny - 1):
        for ix in range(nx):
            conductance = (
                _harmonic_mean(sigma[iy, ix], sigma[iy + 1, ix])
                * grid.thickness_m
                * grid.dx_m
                / grid.dy_m
            )
            power = conductance * (potential[iy, ix] - potential[iy + 1, ix]) ** 2
            cell_joule[iy, ix] += 0.5 * power
            cell_joule[iy + 1, ix] += 0.5 * power

    joule_power = float(np.sum(cell_joule))
    terminal_power = float(
        source_voltage_V * source_current + ground_voltage_V * ground_current
    )
    current_scale = max(abs(source_current) + abs(ground_current), 1.0e-30)
    power_scale = max(abs(terminal_power) + abs(joule_power), 1.0e-30)
    return SheetElectricalSolution(
        potential_V=potential,
        source_current_A=float(source_current),
        ground_current_A=float(ground_current),
        cell_joule_power_W=cell_joule,
        joule_power_W=joule_power,
        terminal_device_power_W=terminal_power,
        relative_current_imbalance=abs(source_current + ground_current) / current_scale,
        relative_power_imbalance=abs(terminal_power - joule_power) / power_scale,
    )


def assemble_lateral_thermal_matrix(
    grid: GeoPhaseGrid, thermal_conductivity_W_mK: np.ndarray | float
) -> sparse.csr_matrix:
    """Return L such that L@T is conservative outward in-plane heat flow."""

    conductivity = np.broadcast_to(
        np.asarray(thermal_conductivity_W_mK, dtype=float), grid.shape
    ).copy()
    if not np.isfinite(conductivity).all() or np.any(conductivity <= 0.0):
        raise ValueError("thermal conductivity must be finite and positive")
    ny, nx = grid.shape
    matrix = sparse.lil_matrix((nx * ny, nx * ny), dtype=float)

    def node(iy: int, ix: int) -> int:
        return iy * nx + ix

    for iy in range(ny):
        for ix in range(nx - 1):
            conductance = (
                _harmonic_mean(conductivity[iy, ix], conductivity[iy, ix + 1])
                * grid.thickness_m
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
                _harmonic_mean(conductivity[iy, ix], conductivity[iy + 1, ix])
                * grid.thickness_m
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


def solve_steady_thermal_dirichlet(
    grid: GeoPhaseGrid,
    thermal_conductivity_W_mK: float,
    left_temperature_K: float,
    right_temperature_K: float,
    areal_source_W_m2: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Manufactured-solution helper with x-face Dirichlet and y no-flux BCs."""

    source = np.broadcast_to(np.asarray(areal_source_W_m2, dtype=float), grid.shape)
    if not np.isfinite(source).all():
        raise ValueError("manufactured source must be finite")
    matrix = assemble_lateral_thermal_matrix(grid, thermal_conductivity_W_mK).tolil()
    rhs = (source * grid.cell_area_m2).reshape(-1).copy()
    ny, nx = grid.shape
    boundary_conductance = (
        thermal_conductivity_W_mK
        * grid.thickness_m
        * grid.dy_m
        / (0.5 * grid.dx_m)
    )
    for iy in range(ny):
        left = iy * nx
        right = iy * nx + nx - 1
        matrix[left, left] += boundary_conductance
        rhs[left] += boundary_conductance * left_temperature_K
        matrix[right, right] += boundary_conductance
        rhs[right] += boundary_conductance * right_temperature_K
    values = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float)
    if not np.isfinite(values).all():
        raise FloatingPointError("manufactured thermal solve produced nonfinite values")
    return values.reshape(grid.shape)
