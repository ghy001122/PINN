"""Conservative finite-width thermal closure used only by the M42 preflight."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csc_matrix, diags, lil_matrix
from scipy.sparse.linalg import splu


@dataclass(frozen=True)
class ThermalGrid:
    x_edges_m: np.ndarray
    y_edges_m: np.ndarray
    z_edges_m: np.ndarray
    y_far_boundary: bool

    @property
    def shape(self) -> tuple[int, int, int]:
        return (
            self.z_edges_m.size - 1,
            self.y_edges_m.size - 1,
            self.x_edges_m.size - 1,
        )


def _normalized_geometric_widths(total: float, count: int, ratio: float = 6.0) -> np.ndarray:
    if count < 1 or total <= 0.0:
        raise ValueError("outer segment requires positive length and cell count")
    weights = np.geomspace(1.0, ratio, count)
    return total * weights / np.sum(weights)


def symmetric_clustered_edges(
    source_extent_m: float,
    half_domain_m: float,
    source_half_cells: int,
    outer_cells: int,
) -> np.ndarray:
    if source_extent_m <= 0.0 or half_domain_m <= 0.5 * source_extent_m:
        raise ValueError("domain must extend beyond the source")
    inner = np.linspace(0.0, 0.5 * source_extent_m, source_half_cells + 1)
    outer_widths = _normalized_geometric_widths(
        half_domain_m - 0.5 * source_extent_m, outer_cells
    )
    positive = np.concatenate((inner, inner[-1] + np.cumsum(outer_widths)))
    return np.concatenate((-positive[:0:-1], positive))


def depth_clustered_edges(
    near_depth_m: float,
    domain_depth_m: float,
    near_cells: int,
    outer_cells: int,
) -> np.ndarray:
    if near_depth_m <= 0.0 or domain_depth_m <= near_depth_m:
        raise ValueError("depth domain must extend beyond the near-source layer")
    near = np.linspace(0.0, near_depth_m, near_cells + 1)
    outer_widths = _normalized_geometric_widths(
        domain_depth_m - near_depth_m, outer_cells
    )
    return np.concatenate((near, near[-1] + np.cumsum(outer_widths)))


def build_grid(
    *,
    source_length_m: float,
    source_width_m: float,
    diffusion_length_m: float,
    domain_multiplier: float,
    source_half_cells: int,
    outer_cells: int,
    near_depth_cells: int,
    depth_outer_cells: int,
    extruded_2d: bool,
) -> ThermalGrid:
    half_x = 0.5 * source_length_m + domain_multiplier * diffusion_length_m
    x_edges = symmetric_clustered_edges(
        source_length_m, half_x, source_half_cells, outer_cells
    )
    if extruded_2d:
        y_edges = np.asarray([-0.5 * source_width_m, 0.5 * source_width_m])
    else:
        half_y = 0.5 * source_width_m + domain_multiplier * diffusion_length_m
        y_edges = symmetric_clustered_edges(
            source_width_m, half_y, source_half_cells, outer_cells
        )
    z_edges = depth_clustered_edges(
        max(source_length_m, 0.2 * source_width_m),
        domain_multiplier * diffusion_length_m,
        near_depth_cells,
        depth_outer_cells,
    )
    return ThermalGrid(x_edges, y_edges, z_edges, y_far_boundary=not extruded_2d)


def _index(iz: int, iy: int, ix: int, ny: int, nx: int) -> int:
    return (iz * ny + iy) * nx + ix


def assemble_constant_property_system(
    grid: ThermalGrid,
    *,
    thermal_conductivity_W_mK: float,
    volumetric_heat_capacity_J_m3K: float,
) -> tuple[np.ndarray, csc_matrix, np.ndarray, np.ndarray]:
    if min(thermal_conductivity_W_mK, volumetric_heat_capacity_J_m3K) <= 0.0:
        raise ValueError("thermal properties must be positive")
    dz = np.diff(grid.z_edges_m)
    dy = np.diff(grid.y_edges_m)
    dx = np.diff(grid.x_edges_m)
    nz, ny, nx = grid.shape
    n = nz * ny * nx
    matrix = lil_matrix((n, n), dtype=float)
    boundary_conductance = np.zeros(n, dtype=float)
    volume = np.empty(n, dtype=float)

    def connect(a: int, b: int, conductance: float) -> None:
        matrix[a, a] += conductance
        matrix[b, b] += conductance
        matrix[a, b] -= conductance
        matrix[b, a] -= conductance

    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                row = _index(iz, iy, ix, ny, nx)
                volume[row] = dx[ix] * dy[iy] * dz[iz]
                if ix + 1 < nx:
                    area = dy[iy] * dz[iz]
                    distance = 0.5 * (dx[ix] + dx[ix + 1])
                    connect(row, _index(iz, iy, ix + 1, ny, nx), thermal_conductivity_W_mK * area / distance)
                if iy + 1 < ny:
                    area = dx[ix] * dz[iz]
                    distance = 0.5 * (dy[iy] + dy[iy + 1])
                    connect(row, _index(iz, iy + 1, ix, ny, nx), thermal_conductivity_W_mK * area / distance)
                if iz + 1 < nz:
                    area = dx[ix] * dy[iy]
                    distance = 0.5 * (dz[iz] + dz[iz + 1])
                    connect(row, _index(iz + 1, iy, ix, ny, nx), thermal_conductivity_W_mK * area / distance)

                boundary = 0.0
                if ix in (0, nx - 1):
                    boundary += thermal_conductivity_W_mK * dy[iy] * dz[iz] / (0.5 * dx[ix])
                if grid.y_far_boundary and iy in (0, ny - 1):
                    boundary += thermal_conductivity_W_mK * dx[ix] * dz[iz] / (0.5 * dy[iy])
                if iz == nz - 1:
                    boundary += thermal_conductivity_W_mK * dx[ix] * dy[iy] / (0.5 * dz[iz])
                matrix[row, row] += boundary
                boundary_conductance[row] = boundary

    capacity = volumetric_heat_capacity_J_m3K * volume
    return capacity, matrix.tocsc(), boundary_conductance, volume


def independent_boundary_outflow_W(
    grid: ThermalGrid,
    theta_K: np.ndarray,
    thermal_conductivity_W_mK: float,
) -> float:
    """Recompute far-boundary heat flow without the assembled ledger vector."""
    dz = np.diff(grid.z_edges_m)
    dy = np.diff(grid.y_edges_m)
    dx = np.diff(grid.x_edges_m)
    nz, ny, nx = grid.shape
    theta = np.asarray(theta_K, dtype=float).reshape((nz, ny, nx))
    outward = 0.0
    for iz in range(nz):
        for iy in range(ny):
            outward += thermal_conductivity_W_mK * dy[iy] * dz[iz] * theta[iz, iy, 0] / (0.5 * dx[0])
            outward += thermal_conductivity_W_mK * dy[iy] * dz[iz] * theta[iz, iy, -1] / (0.5 * dx[-1])
    if grid.y_far_boundary:
        for iz in range(nz):
            for ix in range(nx):
                outward += thermal_conductivity_W_mK * dx[ix] * dz[iz] * theta[iz, 0, ix] / (0.5 * dy[0])
                outward += thermal_conductivity_W_mK * dx[ix] * dz[iz] * theta[iz, -1, ix] / (0.5 * dy[-1])
    for iy in range(ny):
        for ix in range(nx):
            outward += thermal_conductivity_W_mK * dx[ix] * dy[iy] * theta[-1, iy, ix] / (0.5 * dz[-1])
    return float(outward)


def run_constant_power_transient(
    grid: ThermalGrid,
    *,
    source_length_m: float,
    source_width_m: float,
    total_power_W: float,
    thermal_conductivity_W_mK: float,
    volumetric_heat_capacity_J_m3K: float,
    duration_s: float,
    dt_s: float,
) -> dict[str, object]:
    if min(total_power_W, duration_s, dt_s) <= 0.0:
        raise ValueError("power and time inputs must be positive")
    capacity, conductance, boundary_g, volume = assemble_constant_property_system(
        grid,
        thermal_conductivity_W_mK=thermal_conductivity_W_mK,
        volumetric_heat_capacity_J_m3K=volumetric_heat_capacity_J_m3K,
    )
    nz, ny, nx = grid.shape
    x = 0.5 * (grid.x_edges_m[:-1] + grid.x_edges_m[1:])
    y = 0.5 * (grid.y_edges_m[:-1] + grid.y_edges_m[1:])
    source_mask_2d = (
        (abs(y[:, None]) <= 0.5 * source_width_m * (1.0 + 1.0e-12))
        & (abs(x[None, :]) <= 0.5 * source_length_m * (1.0 + 1.0e-12))
    )
    source_indices = np.asarray(
        [_index(0, iy, ix, ny, nx) for iy, ix in np.argwhere(source_mask_2d)],
        dtype=int,
    )
    if source_indices.size == 0:
        raise RuntimeError("thermal source is not represented by the grid")
    source = np.zeros(capacity.size, dtype=float)
    source[source_indices] = total_power_W / source_indices.size

    steps = int(np.ceil(duration_s / dt_s))
    dt = duration_s / steps
    lhs = diags(capacity / dt, format="csc") + conductance
    factor = splu(lhs)
    theta = np.zeros(capacity.size, dtype=float)
    maximum_imbalance = 0.0
    maximum_boundary_flux_disagreement = 0.0
    cumulative_outflow = 0.0
    for _ in range(steps):
        previous = theta
        theta = factor.solve(capacity * previous / dt + source)
        storage_rate = float(np.dot(capacity, theta - previous) / dt)
        assembled_outward = float(np.dot(boundary_g, theta))
        outward = independent_boundary_outflow_W(
            grid, theta, thermal_conductivity_W_mK
        )
        flux_disagreement = abs(outward - assembled_outward) / max(
            abs(outward) + abs(assembled_outward), 1.0e-30
        )
        maximum_boundary_flux_disagreement = max(
            maximum_boundary_flux_disagreement, flux_disagreement
        )
        imbalance = abs(storage_rate + outward - total_power_W) / max(
            abs(storage_rate) + abs(outward) + abs(total_power_W), 1.0e-30
        )
        maximum_imbalance = max(maximum_imbalance, imbalance)
        cumulative_outflow += outward * dt

    final_enthalpy = float(np.dot(capacity, theta))
    cumulative_imbalance = abs(
        final_enthalpy + cumulative_outflow - total_power_W * duration_s
    ) / max(
        abs(final_enthalpy) + abs(cumulative_outflow) + abs(total_power_W * duration_s),
        1.0e-30,
    )
    source_volume = volume[source_indices]
    source_mean = float(np.average(theta[source_indices], weights=source_volume))
    return {
        "finite": bool(np.isfinite(theta).all()),
        "grid_shape": list(grid.shape),
        "cell_count": int(theta.size),
        "steps": steps,
        "dt_s": float(dt),
        "duration_s": float(duration_s),
        "source_cell_count": int(source_indices.size),
        "Tmean_rise_K": source_mean,
        "Tmax_rise_K": float(np.max(theta)),
        "final_enthalpy_J": final_enthalpy,
        "cumulative_outward_heat_J": float(cumulative_outflow),
        "maximum_enthalpy_imbalance": float(maximum_imbalance),
        "cumulative_enthalpy_imbalance": float(cumulative_imbalance),
        "maximum_boundary_flux_disagreement": float(
            maximum_boundary_flux_disagreement
        ),
        "clip_count": 0,
        "latent_heat_J_m3": 0.0,
    }


def relative_change(coarse: float, fine: float, floor: float = 1.0e-30) -> float:
    return abs(coarse - fine) / max(abs(fine), floor)
