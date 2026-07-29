"""Independent conservative x-y finite volumes for the Phase 1 judge."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu, spsolve

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


ElectricalTimingCallback = Callable[[str, float], None]


@dataclass
class SheetElectricalTimings:
    """Accumulated wall times for one or more frozen-conductivity solves."""

    electrical_assembly_wall_s: float = 0.0
    factorization_wall_s: float = 0.0
    linear_solves_wall_s: float = 0.0
    Joule_port_postprocess_wall_s: float = 0.0
    electrical_assembly_calls: int = 0
    factorization_calls: int = 0
    linear_solve_calls: int = 0
    postprocess_calls: int = 0

    def record(self, name: str, elapsed_s: float) -> None:
        """Record one preregistered electrical timing stage."""

        elapsed = float(elapsed_s)
        if not np.isfinite(elapsed) or elapsed < 0.0:
            raise ValueError("electrical stage timing must be finite and nonnegative")
        if name == "electrical_assembly_wall_s":
            self.electrical_assembly_wall_s += elapsed
            self.electrical_assembly_calls += 1
        elif name == "factorization_wall_s":
            self.factorization_wall_s += elapsed
            self.factorization_calls += 1
        elif name == "linear_solves_wall_s":
            self.linear_solves_wall_s += elapsed
            self.linear_solve_calls += 1
        elif name == "Joule_port_postprocess_wall_s":
            self.Joule_port_postprocess_wall_s += elapsed
            self.postprocess_calls += 1
        else:
            raise ValueError(f"unregistered electrical timing stage: {name}")


@dataclass(frozen=True)
class SheetElectricalTopology:
    """Grid-bound CSR structure and vectorized finite-volume face geometry."""

    shape: tuple[int, int]
    thickness_m: float
    x_edges_m: np.ndarray
    y_edges_m: np.ndarray
    row_pointer: np.ndarray
    column_indices: np.ndarray
    diagonal_slots: np.ndarray
    x_forward_slots: np.ndarray
    x_reverse_slots: np.ndarray
    y_forward_slots: np.ndarray
    y_reverse_slots: np.ndarray
    x_left_nodes: np.ndarray
    x_right_nodes: np.ndarray
    y_lower_nodes: np.ndarray
    y_upper_nodes: np.ndarray
    source_nodes: np.ndarray
    ground_nodes: np.ndarray
    x_face_geometry_m: float
    y_face_geometry_m: float
    boundary_face_geometry_m: float

    def validate_grid(self, grid: GeoPhaseGrid) -> None:
        """Reject reuse across a different grid or physical geometry."""

        if (
            grid.shape != self.shape
            or float(grid.thickness_m) != self.thickness_m
            or not np.array_equal(grid.x_edges_m, self.x_edges_m)
            or not np.array_equal(grid.y_edges_m, self.y_edges_m)
        ):
            raise ValueError("electrical topology cannot cross grid context")


def _readonly(array: np.ndarray) -> np.ndarray:
    result = np.asarray(array).copy()
    result.setflags(write=False)
    return result


def _csr_slots(
    matrix: sparse.csr_matrix, rows: np.ndarray, columns: np.ndarray
) -> np.ndarray:
    slots = np.empty(rows.size, dtype=np.int64)
    for index, (row, column) in enumerate(zip(rows, columns, strict=True)):
        start = int(matrix.indptr[int(row)])
        stop = int(matrix.indptr[int(row) + 1])
        offset = int(np.searchsorted(matrix.indices[start:stop], int(column)))
        if offset >= stop - start or matrix.indices[start + offset] != column:
            raise RuntimeError("fixed electrical CSR topology is incomplete")
        slots[index] = start + offset
    return slots


def build_sheet_electrical_topology(grid: GeoPhaseGrid) -> SheetElectricalTopology:
    """Precompute the immutable CSR pattern and face geometry for one grid."""

    ny, nx = grid.shape
    if nx <= 1 or ny <= 1:
        raise ValueError("the electrical sheet requires at least two cells per axis")
    count = nx * ny
    nodes = np.arange(count, dtype=np.int64).reshape(grid.shape)
    diagonal_nodes = nodes.reshape(-1)
    x_left_nodes = nodes[:, :-1].reshape(-1)
    x_right_nodes = nodes[:, 1:].reshape(-1)
    y_lower_nodes = nodes[:-1, :].reshape(-1)
    y_upper_nodes = nodes[1:, :].reshape(-1)
    source_nodes = nodes[:, 0].reshape(-1)
    ground_nodes = nodes[:, -1].reshape(-1)

    rows = np.concatenate(
        (
            diagonal_nodes,
            x_left_nodes,
            x_right_nodes,
            y_lower_nodes,
            y_upper_nodes,
        )
    )
    columns = np.concatenate(
        (
            diagonal_nodes,
            x_right_nodes,
            x_left_nodes,
            y_upper_nodes,
            y_lower_nodes,
        )
    )
    pattern = sparse.coo_matrix(
        (np.ones(rows.size, dtype=float), (rows, columns)),
        shape=(count, count),
    ).tocsr()
    pattern.sort_indices()

    return SheetElectricalTopology(
        shape=grid.shape,
        thickness_m=float(grid.thickness_m),
        x_edges_m=_readonly(np.asarray(grid.x_edges_m, dtype=float)),
        y_edges_m=_readonly(np.asarray(grid.y_edges_m, dtype=float)),
        row_pointer=_readonly(pattern.indptr.astype(np.int64, copy=False)),
        column_indices=_readonly(pattern.indices.astype(np.int64, copy=False)),
        diagonal_slots=_readonly(_csr_slots(pattern, diagonal_nodes, diagonal_nodes)),
        x_forward_slots=_readonly(_csr_slots(pattern, x_left_nodes, x_right_nodes)),
        x_reverse_slots=_readonly(_csr_slots(pattern, x_right_nodes, x_left_nodes)),
        y_forward_slots=_readonly(_csr_slots(pattern, y_lower_nodes, y_upper_nodes)),
        y_reverse_slots=_readonly(_csr_slots(pattern, y_upper_nodes, y_lower_nodes)),
        x_left_nodes=_readonly(x_left_nodes),
        x_right_nodes=_readonly(x_right_nodes),
        y_lower_nodes=_readonly(y_lower_nodes),
        y_upper_nodes=_readonly(y_upper_nodes),
        source_nodes=_readonly(source_nodes),
        ground_nodes=_readonly(ground_nodes),
        x_face_geometry_m=float(grid.thickness_m * grid.dy_m / grid.dx_m),
        y_face_geometry_m=float(grid.thickness_m * grid.dx_m / grid.dy_m),
        boundary_face_geometry_m=float(
            grid.thickness_m * grid.dy_m / (0.5 * grid.dx_m)
        ),
    )


def _record_electrical_timing(
    timings: SheetElectricalTimings,
    callback: ElectricalTimingCallback | None,
    name: str,
    elapsed_s: float,
) -> None:
    timings.record(name, elapsed_s)
    if callback is not None:
        callback(name, float(elapsed_s))


@dataclass(frozen=True)
class FrozenSheetElectricalFactorization:
    """One SuperLU factorization bound to exactly one conductivity field."""

    topology: SheetElectricalTopology
    conductivity_matrix_csr: sparse.csr_matrix
    x_face_conductance_S: np.ndarray
    y_face_conductance_S: np.ndarray
    source_face_conductance_S: np.ndarray
    ground_face_conductance_S: np.ndarray
    linear_factorization: Any
    timings: SheetElectricalTimings
    timing_callback: ElectricalTimingCallback | None = None

    def solve(
        self, source_voltage_V: float, ground_voltage_V: float = 0.0
    ) -> SheetElectricalSolution:
        """Directly solve one RHS and vectorize port/Joule postprocessing."""

        if not np.isfinite([source_voltage_V, ground_voltage_V]).all():
            raise ValueError("terminal voltages must be finite")

        rhs = np.zeros(self.topology.shape[0] * self.topology.shape[1], dtype=float)
        rhs[self.topology.source_nodes] = (
            self.source_face_conductance_S * source_voltage_V
        )
        rhs[self.topology.ground_nodes] += (
            self.ground_face_conductance_S * ground_voltage_V
        )
        started = perf_counter()
        try:
            values = np.asarray(self.linear_factorization.solve(rhs), dtype=float)
        finally:
            _record_electrical_timing(
                self.timings,
                self.timing_callback,
                "linear_solves_wall_s",
                perf_counter() - started,
            )
        if not np.isfinite(values).all():
            raise FloatingPointError("electrical solve produced nonfinite potential")

        started = perf_counter()
        try:
            potential = values.reshape(self.topology.shape)
            source_drop = source_voltage_V - potential[:, 0]
            ground_drop = ground_voltage_V - potential[:, -1]
            source_current = float(
                np.sum(self.source_face_conductance_S * source_drop)
            )
            ground_current = float(
                np.sum(self.ground_face_conductance_S * ground_drop)
            )

            cell_joule = np.zeros(self.topology.shape, dtype=float)
            cell_joule[:, 0] += self.source_face_conductance_S * source_drop**2
            cell_joule[:, -1] += self.ground_face_conductance_S * ground_drop**2
            x_power = self.x_face_conductance_S * (
                potential[:, :-1] - potential[:, 1:]
            ) ** 2
            cell_joule[:, :-1] += 0.5 * x_power
            cell_joule[:, 1:] += 0.5 * x_power
            y_power = self.y_face_conductance_S * (
                potential[:-1, :] - potential[1:, :]
            ) ** 2
            cell_joule[:-1, :] += 0.5 * y_power
            cell_joule[1:, :] += 0.5 * y_power

            joule_power = float(np.sum(cell_joule))
            terminal_power = float(
                source_voltage_V * source_current
                + ground_voltage_V * ground_current
            )
            current_scale = max(abs(source_current) + abs(ground_current), 1.0e-30)
            power_scale = max(abs(terminal_power) + abs(joule_power), 1.0e-30)
            result = SheetElectricalSolution(
                potential_V=potential,
                source_current_A=source_current,
                ground_current_A=ground_current,
                cell_joule_power_W=cell_joule,
                joule_power_W=joule_power,
                terminal_device_power_W=terminal_power,
                relative_current_imbalance=abs(source_current + ground_current)
                / current_scale,
                relative_power_imbalance=abs(terminal_power - joule_power)
                / power_scale,
            )
        finally:
            _record_electrical_timing(
                self.timings,
                self.timing_callback,
                "Joule_port_postprocess_wall_s",
                perf_counter() - started,
            )
        return result


def _harmonic_mean(left: float, right: float) -> float:
    return 2.0 * left * right / (left + right)


def factor_sheet_electrical(
    grid: GeoPhaseGrid,
    conductivity_S_m: np.ndarray,
    *,
    topology: SheetElectricalTopology | None = None,
    timings: SheetElectricalTimings | None = None,
    timing_callback: ElectricalTimingCallback | None = None,
) -> FrozenSheetElectricalFactorization:
    """Assemble and factor one matrix for one frozen conductivity context."""

    if timing_callback is not None and not callable(timing_callback):
        raise TypeError("timing_callback must be callable")
    timing_totals = SheetElectricalTimings() if timings is None else timings
    started = perf_counter()
    try:
        fixed_topology = (
            build_sheet_electrical_topology(grid) if topology is None else topology
        )
        fixed_topology.validate_grid(grid)
        sigma = np.asarray(conductivity_S_m, dtype=float)
        if sigma.shape != grid.shape:
            raise ValueError("conductivity shape does not match the x-y grid")
        if not np.isfinite(sigma).all() or np.any(sigma <= 0.0):
            raise ValueError("conductivity must be finite and positive")

        x_face_conductance = (
            2.0
            * sigma[:, :-1]
            * sigma[:, 1:]
            / (sigma[:, :-1] + sigma[:, 1:])
            * fixed_topology.x_face_geometry_m
        )
        y_face_conductance = (
            2.0
            * sigma[:-1, :]
            * sigma[1:, :]
            / (sigma[:-1, :] + sigma[1:, :])
            * fixed_topology.y_face_geometry_m
        )
        source_face_conductance = (
            sigma[:, 0] * fixed_topology.boundary_face_geometry_m
        )
        ground_face_conductance = (
            sigma[:, -1] * fixed_topology.boundary_face_geometry_m
        )

        diagonal = np.zeros(sigma.size, dtype=float)
        x_flat = x_face_conductance.reshape(-1)
        y_flat = y_face_conductance.reshape(-1)
        np.add.at(diagonal, fixed_topology.x_left_nodes, x_flat)
        np.add.at(diagonal, fixed_topology.x_right_nodes, x_flat)
        np.add.at(diagonal, fixed_topology.y_lower_nodes, y_flat)
        np.add.at(diagonal, fixed_topology.y_upper_nodes, y_flat)
        np.add.at(
            diagonal, fixed_topology.source_nodes, source_face_conductance
        )
        np.add.at(
            diagonal, fixed_topology.ground_nodes, ground_face_conductance
        )

        data = np.zeros(fixed_topology.column_indices.size, dtype=float)
        data[fixed_topology.diagonal_slots] = diagonal
        data[fixed_topology.x_forward_slots] = -x_flat
        data[fixed_topology.x_reverse_slots] = -x_flat
        data[fixed_topology.y_forward_slots] = -y_flat
        data[fixed_topology.y_reverse_slots] = -y_flat
        matrix = sparse.csr_matrix(
            (
                data,
                fixed_topology.column_indices,
                fixed_topology.row_pointer,
            ),
            shape=(sigma.size, sigma.size),
            copy=False,
        )
    finally:
        _record_electrical_timing(
            timing_totals,
            timing_callback,
            "electrical_assembly_wall_s",
            perf_counter() - started,
        )

    started = perf_counter()
    try:
        linear_factorization = splu(matrix.tocsc(), permc_spec="COLAMD")
    finally:
        _record_electrical_timing(
            timing_totals,
            timing_callback,
            "factorization_wall_s",
            perf_counter() - started,
        )
    return FrozenSheetElectricalFactorization(
        topology=fixed_topology,
        conductivity_matrix_csr=matrix,
        x_face_conductance_S=_readonly(x_face_conductance),
        y_face_conductance_S=_readonly(y_face_conductance),
        source_face_conductance_S=_readonly(source_face_conductance),
        ground_face_conductance_S=_readonly(ground_face_conductance),
        linear_factorization=linear_factorization,
        timings=timing_totals,
        timing_callback=timing_callback,
    )


def solve_sheet_electrical(
    grid: GeoPhaseGrid,
    conductivity_S_m: np.ndarray,
    source_voltage_V: float,
    ground_voltage_V: float = 0.0,
) -> SheetElectricalSolution:
    """Solve div(t*sigma*grad(phi))=0 with finite left/right contacts."""

    return factor_sheet_electrical(grid, conductivity_S_m).solve(
        source_voltage_V, ground_voltage_V
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
