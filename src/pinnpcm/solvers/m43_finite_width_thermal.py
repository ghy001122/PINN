"""M43 constant-property finite-width thermal component solver.

This module deliberately models only a homogeneous isotropic half space.  The
3-D model uses a quarter domain, while the x-z comparator uses the short-axis
half domain extruded through the registered full source width.  In both cases
the reported thermal impedance is normalized by the *full* registered power.

The finite-volume operator is separable.  One-dimensional symmetric
generalized eigensystems are combined in modal form, which avoids assembling a
large three-dimensional sparse matrix and makes the preregistered transient
comparisons inexpensive on CPU.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class QuarterThermalGrid:
    """Cell-face grid for the quarter-domain or x-z half-domain model."""

    x_edges_m: np.ndarray
    y_edges_m: np.ndarray
    z_edges_m: np.ndarray
    geometry: str
    mesh: str
    domain: str
    mode: str
    source_half_x_m: float
    source_half_y_m: float
    full_source_x_m: float
    full_source_y_m: float
    far_y_dirichlet: bool

    @property
    def shape(self) -> tuple[int, int, int]:
        return (
            self.z_edges_m.size - 1,
            self.y_edges_m.size - 1,
            self.x_edges_m.size - 1,
        )

    @property
    def cell_count(self) -> int:
        return int(np.prod(self.shape))


@dataclass(frozen=True)
class _ModalSystem:
    grid: QuarterThermalGrid
    widths_x_m: np.ndarray
    widths_y_m: np.ndarray
    widths_z_m: np.ndarray
    volume_m3: np.ndarray
    eigenvectors_x: np.ndarray
    eigenvectors_y: np.ndarray
    eigenvectors_z: np.ndarray
    eigenvalue_sum_m2_inv: np.ndarray
    source_W: np.ndarray
    source_mask: np.ndarray
    source_area_weights: np.ndarray
    boundary_x_W_K: np.ndarray
    boundary_y_W_K: np.ndarray
    boundary_z_W_K: np.ndarray
    source_flux_W_m2: float
    expected_model_power_W: float
    full_power_W: float
    thermal_conductivity_W_mK: float
    volumetric_heat_capacity_J_m3K: float


def _domain_number(domain: str) -> int:
    if domain not in {"D1", "D2", "D3"}:
        raise ValueError(f"unsupported M43 domain: {domain}")
    return int(domain[1:])


def _mesh_profile(config: Mapping[str, Any], geometry: str, mesh: str) -> tuple[int, int, int]:
    try:
        profile = config["grid"]["mesh_profiles"][mesh]
    except KeyError as exc:
        raise ValueError(f"unsupported M43 mesh: {mesh}") from exc
    key = "square_quarter_source_cells_xy" if geometry == "rho1" else "rho5_quarter_source_cells_xy"
    if geometry not in {"rho1", "rho5"}:
        raise ValueError(f"unsupported M43 geometry: {geometry}")
    nx, ny = (int(value) for value in profile[key])
    depth_key = "square_source_depth_cells" if geometry == "rho1" else "rho5_source_depth_cells"
    nz = int(profile[depth_key])
    if min(nx, ny, nz) < 1:
        raise ValueError("source cell counts must be positive")
    return nx, ny, nz


def _append_only_axis(
    *,
    aligned_extent_m: float,
    aligned_cells: int,
    targets_m: list[float],
    growth_ratio: float,
    requested_domain: int,
) -> np.ndarray:
    """Build a master axis and return the requested exact prefix.

    Domain boundaries are inserted as faces.  The construction proceeds to D3
    once and records prefix lengths, so D1 and D2 never stretch or relocate a
    near-source face.
    """

    if aligned_extent_m <= 0.0 or aligned_cells < 1:
        raise ValueError("aligned source extent and cell count must be positive")
    if growth_ratio <= 1.0:
        raise ValueError("outer-cell growth ratio must exceed one")
    if len(targets_m) != 3 or any(b <= a for a, b in zip(targets_m, targets_m[1:])):
        raise ValueError("D1-D3 targets must be strictly increasing")
    if targets_m[0] <= aligned_extent_m:
        raise ValueError("far boundary must lie beyond the aligned near-source block")

    edges = list(np.linspace(0.0, aligned_extent_m, aligned_cells + 1))
    nominal_width = aligned_extent_m / aligned_cells
    marks: list[int] = []
    for target in targets_m:
        while True:
            remaining = target - edges[-1]
            if remaining <= max(1.0e-14 * target, np.finfo(float).eps):
                edges[-1] = float(target)
                break
            proposed = nominal_width * growth_ratio
            # Avoid a tiny clipped cell at each registered domain boundary.
            if remaining <= 1.5 * proposed:
                edges.append(float(target))
                nominal_width = proposed
                break
            edges.append(edges[-1] + proposed)
            nominal_width = proposed
        marks.append(len(edges))
    return np.asarray(edges[: marks[requested_domain - 1]], dtype=float)


def build_quarter_grid(
    config: Mapping[str, Any],
    geometry: str,
    mesh: str,
    domain: str,
    mode: str = "3d",
) -> QuarterThermalGrid:
    """Build an exact source-edge-aligned append-only M43 grid."""

    if mode not in {"3d", "xz"}:
        raise ValueError("mode must be '3d' or 'xz'")
    nx_source, ny_source, nz_source = _mesh_profile(config, geometry, mesh)
    geometry_cfg = config["geometry"]
    if geometry == "rho1":
        side = float(np.sqrt(float(geometry_cfg["source_area_m2"])))
        full_x = side
        full_y = side
    else:
        full_x = float(geometry_cfg["source_full_x_m"])
        full_y = float(geometry_cfg["source_full_y_m"])
    half_x = 0.5 * full_x
    half_y = 0.5 * full_y

    multipliers = [float(value) for value in config["grid"]["domain_multipliers_of_maximum_diffusion_length"]]
    ell = float(config["time"]["maximum_diffusion_length_m"])
    growth = float(config["grid"]["outer_cell_growth_ratio"])
    domain_number = _domain_number(domain)
    x_targets = [half_x + multiplier * ell for multiplier in multipliers]
    x_edges = _append_only_axis(
        aligned_extent_m=half_x,
        aligned_cells=nx_source,
        targets_m=x_targets,
        growth_ratio=growth,
        requested_domain=domain_number,
    )

    if mode == "xz":
        # One extruded cell represents the registered full 500 nm width.  It
        # has no y-direction conductance or far-y boundary.
        y_edges = np.asarray([0.0, full_y], dtype=float)
        source_half_y = full_y
        far_y = False
    else:
        y_targets = [half_y + multiplier * ell for multiplier in multipliers]
        y_edges = _append_only_axis(
            aligned_extent_m=half_y,
            aligned_cells=ny_source,
            targets_m=y_targets,
            growth_ratio=growth,
            requested_domain=domain_number,
        )
        source_half_y = half_y
        far_y = True

    near_depth = min(half_x, half_y)
    z_targets = [multiplier * ell for multiplier in multipliers]
    z_edges = _append_only_axis(
        aligned_extent_m=near_depth,
        aligned_cells=nz_source,
        targets_m=z_targets,
        growth_ratio=growth,
        requested_domain=domain_number,
    )
    return QuarterThermalGrid(
        x_edges_m=x_edges,
        y_edges_m=y_edges,
        z_edges_m=z_edges,
        geometry=geometry,
        mesh=mesh,
        domain=domain,
        mode=mode,
        source_half_x_m=half_x,
        source_half_y_m=source_half_y,
        full_source_x_m=full_x,
        full_source_y_m=full_y,
        far_y_dirichlet=far_y,
    )


def _axis_stiffness(widths_m: np.ndarray, *, far_dirichlet: bool) -> np.ndarray:
    count = widths_m.size
    stiffness = np.zeros((count, count), dtype=float)
    for index in range(count - 1):
        conductance_per_area = 1.0 / (0.5 * (widths_m[index] + widths_m[index + 1]))
        stiffness[index, index] += conductance_per_area
        stiffness[index + 1, index + 1] += conductance_per_area
        stiffness[index, index + 1] -= conductance_per_area
        stiffness[index + 1, index] -= conductance_per_area
    if far_dirichlet:
        stiffness[-1, -1] += 1.0 / (0.5 * widths_m[-1])
    return stiffness


def _axis_modes(widths_m: np.ndarray, *, far_dirichlet: bool) -> tuple[np.ndarray, np.ndarray]:
    stiffness = _axis_stiffness(widths_m, far_dirichlet=far_dirichlet)
    inverse_sqrt_mass = 1.0 / np.sqrt(widths_m)
    symmetric = inverse_sqrt_mass[:, None] * stiffness * inverse_sqrt_mass[None, :]
    values, vectors = np.linalg.eigh(symmetric)
    values[np.abs(values) < 1.0e-12 * max(float(np.max(np.abs(values))), 1.0)] = 0.0
    return values, vectors


def _forward_modes(array: np.ndarray, system: _ModalSystem) -> np.ndarray:
    return np.einsum(
        "ia,jb,kc,ijk->abc",
        system.eigenvectors_z,
        system.eigenvectors_y,
        system.eigenvectors_x,
        array,
        optimize=True,
    )


def _inverse_modes(array: np.ndarray, system: _ModalSystem) -> np.ndarray:
    return np.einsum(
        "ia,jb,kc,abc->ijk",
        system.eigenvectors_z,
        system.eigenvectors_y,
        system.eigenvectors_x,
        array,
        optimize=True,
    )


def _prepare_system(config: Mapping[str, Any], grid: QuarterThermalGrid) -> _ModalSystem:
    widths_x = np.diff(grid.x_edges_m)
    widths_y = np.diff(grid.y_edges_m)
    widths_z = np.diff(grid.z_edges_m)
    volume = widths_z[:, None, None] * widths_y[None, :, None] * widths_x[None, None, :]
    lambda_x, vectors_x = _axis_modes(widths_x, far_dirichlet=True)
    lambda_y, vectors_y = _axis_modes(widths_y, far_dirichlet=grid.far_y_dirichlet)
    lambda_z, vectors_z = _axis_modes(widths_z, far_dirichlet=True)
    eigenvalue_sum = lambda_z[:, None, None] + lambda_y[None, :, None] + lambda_x[None, None, :]
    if np.any(eigenvalue_sum <= 0.0):
        raise RuntimeError("thermal modal operator is not positive definite")

    centers_x = 0.5 * (grid.x_edges_m[:-1] + grid.x_edges_m[1:])
    centers_y = 0.5 * (grid.y_edges_m[:-1] + grid.y_edges_m[1:])
    source_xy = (
        (centers_y[:, None] <= grid.source_half_y_m * (1.0 + 1.0e-12))
        & (centers_x[None, :] <= grid.source_half_x_m * (1.0 + 1.0e-12))
    )
    source_mask = np.zeros(grid.shape, dtype=bool)
    source_mask[0, :, :] = source_xy
    source_area = widths_y[:, None] * widths_x[None, :]
    source_area_weights = np.zeros(grid.shape, dtype=float)
    integrated_source_area = float(np.sum(source_area[source_xy]))
    source_area_weights[0, :, :][source_xy] = source_area[source_xy] / integrated_source_area

    full_power = float(config["geometry"]["full_power_W"])
    full_area = float(config["geometry"]["source_area_m2"])
    source_flux = full_power / full_area
    registered_power_key = "xz_half_domain_power_W" if grid.mode == "xz" else "quarter_power_W"
    expected_model_power = float(config["geometry"][registered_power_key])
    expected_fraction = 0.5 if grid.mode == "xz" else 0.25
    if not np.isclose(expected_model_power, full_power * expected_fraction, rtol=0.0, atol=1.0e-15):
        raise ValueError("registered model power violates full-power symmetry normalization")
    source_W = np.zeros(grid.shape, dtype=float)
    source_W[0, :, :][source_xy] = source_flux * source_area[source_xy]

    conductivity = float(config["material"]["thermal_conductivity_W_mK"])
    rho_cp = float(config["material"]["volumetric_heat_capacity_J_m3K"])
    boundary_x = np.zeros(grid.shape, dtype=float)
    boundary_x[:, :, -1] = (
        conductivity
        * widths_z[:, None]
        * widths_y[None, :]
        / (0.5 * widths_x[-1])
    )
    boundary_y = np.zeros(grid.shape, dtype=float)
    if grid.far_y_dirichlet:
        boundary_y[:, -1, :] = (
            conductivity
            * widths_z[:, None]
            * widths_x[None, :]
            / (0.5 * widths_y[-1])
        )
    boundary_z = np.zeros(grid.shape, dtype=float)
    boundary_z[-1, :, :] = (
        conductivity
        * widths_y[:, None]
        * widths_x[None, :]
        / (0.5 * widths_z[-1])
    )
    return _ModalSystem(
        grid=grid,
        widths_x_m=widths_x,
        widths_y_m=widths_y,
        widths_z_m=widths_z,
        volume_m3=volume,
        eigenvectors_x=vectors_x,
        eigenvectors_y=vectors_y,
        eigenvectors_z=vectors_z,
        eigenvalue_sum_m2_inv=eigenvalue_sum,
        source_W=source_W,
        source_mask=source_mask,
        source_area_weights=source_area_weights,
        boundary_x_W_K=boundary_x,
        boundary_y_W_K=boundary_y,
        boundary_z_W_K=boundary_z,
        source_flux_W_m2=source_flux,
        expected_model_power_W=expected_model_power,
        full_power_W=full_power,
        thermal_conductivity_W_mK=conductivity,
        volumetric_heat_capacity_J_m3K=rho_cp,
    )


def _edge_hash(grid: QuarterThermalGrid) -> str:
    digest = hashlib.sha256()
    for edges in (grid.x_edges_m, grid.y_edges_m, grid.z_edges_m):
        digest.update(np.asarray(edges, dtype="<f8").tobytes())
    return digest.hexdigest()


def _grid_summary(system: _ModalSystem) -> dict[str, Any]:
    grid = system.grid
    return {
        "geometry": grid.geometry,
        "mesh": grid.mesh,
        "domain": grid.domain,
        "mode": grid.mode,
        "shape": list(grid.shape),
        "cell_count": grid.cell_count,
        "far_extent_m": {
            "x": float(grid.x_edges_m[-1]),
            "y": float(grid.y_edges_m[-1]),
            "z": float(grid.z_edges_m[-1]),
        },
        "minimum_cell_width_m": float(
            min(
                np.min(system.widths_x_m),
                np.min(system.widths_y_m),
                np.min(system.widths_z_m),
            )
        ),
        "maximum_cell_width_m": float(
            max(
                np.max(system.widths_x_m),
                np.max(system.widths_y_m),
                np.max(system.widths_z_m),
            )
        ),
        "source_edge_aligned_x": bool(np.any(grid.x_edges_m == grid.source_half_x_m)),
        "source_edge_aligned_y": bool(
            grid.mode == "xz" or np.any(grid.y_edges_m == grid.source_half_y_m)
        ),
        "edge_sha256": _edge_hash(grid),
    }


def _source_summary(system: _ModalSystem) -> dict[str, Any]:
    integrated_area = float(
        np.sum(
            system.source_area_weights
            * (system.grid.full_source_x_m * system.grid.full_source_y_m)
            * (0.5 if system.grid.mode == "xz" else 0.25)
        )
    )
    # Recover area directly from P/q'' so the audit is independent of the
    # normalized mean weights above.
    integrated_area = float(np.sum(system.source_W) / system.source_flux_W_m2)
    expected_area = (
        system.grid.full_source_x_m * system.grid.full_source_y_m
        * (0.5 if system.grid.mode == "xz" else 0.25)
    )
    integrated_power = float(np.sum(system.source_W))
    area_error = abs(integrated_area - expected_area) / expected_area
    power_error = (
        abs(integrated_power - system.expected_model_power_W)
        / system.expected_model_power_W
    )
    source_aligned = bool(
        np.any(system.grid.x_edges_m == system.grid.source_half_x_m)
        and (
            system.grid.mode == "xz"
            or np.any(system.grid.y_edges_m == system.grid.source_half_y_m)
        )
    )
    source_indices = np.argwhere(system.source_mask)
    only_top_face = bool(source_indices.size and np.all(source_indices[:, 0] == 0))
    centers_x = 0.5 * (system.grid.x_edges_m[:-1] + system.grid.x_edges_m[1:])
    centers_y = 0.5 * (system.grid.y_edges_m[:-1] + system.grid.y_edges_m[1:])
    expected_xy = (
        (centers_y[:, None] <= system.grid.source_half_y_m * (1.0 + 1.0e-12))
        & (centers_x[None, :] <= system.grid.source_half_x_m * (1.0 + 1.0e-12))
    )
    support_exact = only_top_face and bool(np.array_equal(system.source_mask[0], expected_xy))
    return {
        "full_source_area_m2": float(
            system.grid.full_source_x_m * system.grid.full_source_y_m
        ),
        "model_source_area_m2": integrated_area,
        "expected_model_source_area_m2": float(expected_area),
        "source_area_integral_relative_error": float(area_error),
        "source_flux_W_m2": system.source_flux_W_m2,
        "integrated_input_power_W": integrated_power,
        "expected_model_power_W": system.expected_model_power_W,
        "source_power_integral_relative_error": float(power_error),
        "full_power_normalization_W": system.full_power_W,
        "source_face_count": int(np.count_nonzero(system.source_mask)),
        "source_smearing": bool(
            (not source_aligned) or (not support_exact) or area_error > 1.0e-12 or power_error > 1.0e-12
        ),
        "source_support_exact": support_exact,
        "source_only_top_face": only_top_face,
        "unregistered_extrapolation_count": 0,
        "surface_reconstruction": "Tcell+qflux*dz/(2k)",
    }


def _modal_functional(system: _ModalSystem, physical_weights: np.ndarray) -> np.ndarray:
    return _forward_modes(physical_weights / np.sqrt(system.volume_m3), system)


def _source_surface_mean(system: _ModalSystem, modal_state: np.ndarray) -> float:
    mean_functional = _modal_functional(system, system.source_area_weights)
    cell_mean = float(np.sum(mean_functional * modal_state))
    correction = (
        system.source_flux_W_m2
        * system.widths_z_m[0]
        / (2.0 * system.thermal_conductivity_W_mK)
    )
    return cell_mean + correction


def _physical_temperature(system: _ModalSystem, modal_state: np.ndarray) -> np.ndarray:
    return _inverse_modes(modal_state, system) / np.sqrt(system.volume_m3)


def run_steady_case(
    config: Mapping[str, Any],
    grid: QuarterThermalGrid,
) -> dict[str, Any]:
    """Solve one steady homogeneous half-space approximation case."""

    system = _prepare_system(config, grid)
    modal_source = _forward_modes(system.source_W / np.sqrt(system.volume_m3), system)
    modal_state = modal_source / (
        system.thermal_conductivity_W_mK * system.eigenvalue_sum_m2_inv
    )
    temperature = _physical_temperature(system, modal_state)
    surface_mean = _source_surface_mean(system, modal_state)
    boundary_x = float(np.sum(system.boundary_x_W_K * temperature))
    boundary_y = float(np.sum(system.boundary_y_W_K * temperature))
    boundary_z = float(np.sum(system.boundary_z_W_K * temperature))
    outward = boundary_x + boundary_y + boundary_z
    imbalance = abs(outward - system.expected_model_power_W) / system.expected_model_power_W
    resistance = surface_mean / system.full_power_W
    theta = (
        system.thermal_conductivity_W_mK
        * np.sqrt(system.grid.full_source_x_m * system.grid.full_source_y_m)
        * resistance
    )
    finite = bool(
        np.isfinite(temperature).all()
        and np.isfinite(surface_mean)
        and np.isfinite(outward)
    )
    return {
        "mode": "steady",
        "finite": finite,
        "grid": _grid_summary(system),
        "source": _source_summary(system),
        "metrics": {
            "Theta": float(theta),
            "Rs_K_W": float(resistance),
            "source_surface_mean_rise_K": float(surface_mean),
            "source_cell_mean_rise_K": float(
                surface_mean
                - system.source_flux_W_m2
                * system.widths_z_m[0]
                / (2.0 * system.thermal_conductivity_W_mK)
            ),
            "surface_reconstruction_rise_K": float(
                system.source_flux_W_m2
                * system.widths_z_m[0]
                / (2.0 * system.thermal_conductivity_W_mK)
            ),
            "maximum_cell_rise_K": float(np.max(temperature)),
        },
        "ledger": {
            "far_x_outward_power_W": boundary_x,
            "far_y_outward_power_W": boundary_y,
            "bottom_outward_power_W": boundary_z,
            "total_outward_power_W": outward,
            "expected_input_power_W": system.expected_model_power_W,
            "normalized_power_imbalance": float(imbalance),
        },
        "clip_count": 0,
    }


def _stable_geometric_sum(factor: np.ndarray, power: np.ndarray, count: int) -> np.ndarray:
    denominator = 1.0 - factor
    regular = factor * (1.0 - power) / denominator
    return np.where(np.abs(denominator) < 1.0e-12, float(count), regular)


def run_transient_case(
    config: Mapping[str, Any],
    grid: QuarterThermalGrid,
    *,
    times_s: np.ndarray | list[float],
    steps_per_output: int,
) -> dict[str, Any]:
    """Run a constant-flux step with backward Euler in modal coordinates."""

    times = np.asarray(times_s, dtype=float)
    if times.ndim != 1 or times.size == 0 or np.any(~np.isfinite(times)):
        raise ValueError("times_s must be a finite non-empty one-dimensional array")
    if np.any(times <= 0.0) or np.any(np.diff(times) <= 0.0):
        raise ValueError("times_s must be strictly increasing and positive")
    if steps_per_output < 1:
        raise ValueError("steps_per_output must be positive")

    system = _prepare_system(config, grid)
    sqrt_volume = np.sqrt(system.volume_m3)
    modal_source = _forward_modes(system.source_W / sqrt_volume, system)
    alpha = (
        system.thermal_conductivity_W_mK
        / system.volumetric_heat_capacity_J_m3K
    )
    decay_rate = alpha * system.eigenvalue_sum_m2_inv
    forcing = modal_source / system.volumetric_heat_capacity_J_m3K
    steady_modal = forcing / decay_rate
    modal_state = np.zeros_like(steady_modal)

    boundary_total = (
        system.boundary_x_W_K
        + system.boundary_y_W_K
        + system.boundary_z_W_K
    )
    modal_outward = _modal_functional(system, boundary_total)
    modal_energy = _modal_functional(
        system,
        system.volumetric_heat_capacity_J_m3K * system.volume_m3,
    )
    modal_source_mean = _modal_functional(system, system.source_area_weights)
    surface_correction = (
        system.source_flux_W_m2
        * system.widths_z_m[0]
        / (2.0 * system.thermal_conductivity_W_mK)
    )

    source_mean_values: list[float] = []
    maximum_values: list[float] = []
    outward_values: list[float] = []
    enthalpy_values: list[float] = []
    cumulative_outward_values: list[float] = []
    imbalance_values: list[float] = []
    cumulative_outward = 0.0
    previous_time = 0.0
    for target_time in times:
        interval = float(target_time - previous_time)
        dt = interval / steps_per_output
        factor = 1.0 / (1.0 + dt * decay_rate)
        factor_power = np.exp(steps_per_output * np.log(factor))
        sum_factor = _stable_geometric_sum(factor, factor_power, steps_per_output)
        initial = modal_state
        # Sum of the new-time states q_1 ... q_N for backward-Euler outflow.
        modal_state_sum = (
            steps_per_output * steady_modal
            + (initial - steady_modal) * sum_factor
        )
        modal_state = steady_modal + (initial - steady_modal) * factor_power
        cumulative_outward += dt * float(np.sum(modal_outward * modal_state_sum))

        source_mean = float(np.sum(modal_source_mean * modal_state)) + surface_correction
        temperature = _physical_temperature(system, modal_state)
        outward = float(np.sum(modal_outward * modal_state))
        enthalpy = float(np.sum(modal_energy * modal_state))
        input_energy = system.expected_model_power_W * float(target_time)
        imbalance = abs(enthalpy + cumulative_outward - input_energy) / input_energy
        source_mean_values.append(source_mean)
        maximum_values.append(float(np.max(temperature)))
        outward_values.append(outward)
        enthalpy_values.append(enthalpy)
        cumulative_outward_values.append(cumulative_outward)
        imbalance_values.append(float(imbalance))
        previous_time = float(target_time)

    zth = np.asarray(source_mean_values) / system.full_power_W
    finite = bool(
        np.isfinite(zth).all()
        and np.isfinite(maximum_values).all()
        and np.isfinite(imbalance_values).all()
    )
    return {
        "mode": "transient_xz" if grid.mode == "xz" else "transient_3d",
        "finite": finite,
        "grid": _grid_summary(system),
        "source": _source_summary(system),
        "metrics": {
            "time_s": times.tolist(),
            "Zth_K_W": zth.tolist(),
            "source_Zth_K_W": zth.tolist(),
            "source_surface_mean_rise_K": source_mean_values,
            "maximum_cell_rise_K": maximum_values,
            "steps_per_output": int(steps_per_output),
            "total_backward_euler_steps": int(steps_per_output * times.size),
        },
        "ledger": {
            "outward_power_W": outward_values,
            "boundary_outflow_W": outward_values,
            "box_sensible_enthalpy_J": enthalpy_values,
            "stored_sensible_energy_J": enthalpy_values,
            "cumulative_outward_heat_J": cumulative_outward_values,
            "normalized_sensible_energy_imbalance": imbalance_values,
            "maximum_normalized_sensible_energy_imbalance": float(
                np.max(imbalance_values)
            ),
            "expected_model_power_W": system.expected_model_power_W,
        },
        "clip_count": 0,
    }


__all__ = [
    "QuarterThermalGrid",
    "build_quarter_grid",
    "run_steady_case",
    "run_transient_case",
]
