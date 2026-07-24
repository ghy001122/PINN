"""Conservative M44 heterogeneous thermal-only finite-volume solver.

The voting model is deliberately limited to small-signal sensible heat in a
VO2/Ti/Au stack on an Al2O3 substrate.  It does not infer a Joule map, latent
heat, hysteresis, or any electrical parameter.  Three equal-power engineering
source families are supported so that source-location uncertainty remains
explicit.

Coordinates use a symmetry-reduced domain.  The 3-D model represents one
quarter of the registered device and the x-z comparator represents one half,
extruded through the full registered width.  Every reported impedance is
normalised by the *full* registered power.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from scipy.sparse import csc_matrix, diags, lil_matrix
from scipy.sparse.linalg import splu, spsolve


INACTIVE = -1
AL2O3 = 0
VO2 = 1
TI = 2
AU = 3

MATERIAL_NAMES = ("al2o3", "vo2", "ti", "au")


@dataclass(frozen=True)
class HeterogeneousThermalGrid:
    """Face-aligned symmetry-reduced Cartesian grid and material mask."""

    x_edges_m: np.ndarray
    y_edges_m: np.ndarray
    z_edges_m: np.ndarray
    material_id: np.ndarray
    mode: str
    mesh: str
    domain: str
    device_half_x_m: float
    device_half_y_m: float
    contact_start_x_m: float
    symmetry_fraction: float

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.material_id.shape

    @property
    def active_mask(self) -> np.ndarray:
        return self.material_id != INACTIVE

    @property
    def active_cell_count(self) -> int:
        return int(np.count_nonzero(self.active_mask))


@dataclass(frozen=True)
class HeterogeneousThermalSystem:
    """Assembled conservative thermal system in active-cell ordering."""

    grid: HeterogeneousThermalGrid
    active_flat_indices: np.ndarray
    flat_to_active: np.ndarray
    material_active: np.ndarray
    volume_m3: np.ndarray
    capacity_J_K: np.ndarray
    conductance_W_K: csc_matrix
    boundary_conductance_W_K: np.ndarray
    thermal_conductivity_W_mK: np.ndarray
    volumetric_heat_capacity_J_m3K: np.ndarray
    interface_resistance_m2K_W: Mapping[tuple[int, int], float]


def _material_arrays(config: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    conductivity: list[float] = []
    capacity: list[float] = []
    for name in MATERIAL_NAMES:
        item = config["materials"][name]
        conductivity.append(float(item["thermal_conductivity_W_mK"]))
        capacity.append(float(item["volumetric_heat_capacity_J_m3K"]))
    k = np.asarray(conductivity, dtype=float)
    cv = np.asarray(capacity, dtype=float)
    if np.any(~np.isfinite(k)) or np.any(~np.isfinite(cv)) or np.any(k <= 0.0) or np.any(cv <= 0.0):
        raise ValueError("all voting thermal properties must be finite and positive")
    return k, cv


def _append_geometric_edges(
    aligned_edges: np.ndarray,
    target_m: float,
    growth: float,
) -> np.ndarray:
    """Append remote cells while preserving every registered near-field face."""

    edges = list(np.asarray(aligned_edges, dtype=float))
    if len(edges) < 2 or target_m <= edges[-1] or growth <= 1.0:
        raise ValueError("invalid append-only axis request")
    width = edges[-1] - edges[-2]
    while edges[-1] + width < target_m * (1.0 - 1.0e-14):
        edges.append(edges[-1] + width)
        width *= growth
    if target_m > edges[-1]:
        edges.append(target_m)
    return np.asarray(edges, dtype=float)


def _layer_edges(thickness_m: float, cells: int, top_m: float) -> np.ndarray:
    return np.linspace(top_m - thickness_m, top_m, cells + 1)


def build_heterogeneous_grid(
    config: Mapping[str, Any],
    *,
    mesh: str,
    domain: str,
    mode: str = "3d",
) -> HeterogeneousThermalGrid:
    """Build a masked VO2/Ti/Au-on-substrate grid.

    Active-to-void faces are intentionally omitted by the assembler, giving
    the exposed material surfaces an adiabatic boundary.  Only remote
    substrate faces are held at the ambient reference temperature.
    """

    if mode not in {"3d", "xz"}:
        raise ValueError("mode must be '3d' or 'xz'")
    geometry = config["geometry"]
    profile = config["grid"]["mesh_profiles"][mesh]
    multiplier = float(config["grid"]["domain_multipliers_of_maximum_diffusion_length"][domain])
    ell = float(config["time"]["maximum_diffusion_length_m"])
    growth = float(config["grid"]["outer_cell_growth_ratio"])
    half_x = 0.5 * float(geometry["vo2_full_x_m"])
    half_y = 0.5 * float(geometry["vo2_full_y_m"])
    nx_inner = int(profile["vo2_half_x_cells"])
    ny_inner = int(profile["vo2_half_y_cells"])
    nvo2_z = int(profile["vo2_z_cells"])
    nsub_near = int(profile["substrate_near_cells"])
    if min(nx_inner, ny_inner, nvo2_z, nsub_near) < 1:
        raise ValueError("mesh profile cell counts must be positive")

    contact_fraction = float(geometry["contact_support_fraction_of_half_x"])
    if not 0.0 < contact_fraction <= 1.0:
        raise ValueError("contact support fraction must lie in (0, 1]")
    contact_start = half_x * (1.0 - contact_fraction)
    # The contact source/material support is a registered geometry boundary,
    # not a centre-selected approximation.  Insert it for coarse profiles too.
    x_inner = np.unique(
        np.append(np.linspace(0.0, half_x, nx_inner + 1), contact_start)
    )
    x_edges = _append_geometric_edges(x_inner, half_x + multiplier * ell, growth)
    if mode == "xz":
        y_edges = np.asarray([0.0, float(geometry["vo2_full_y_m"])], dtype=float)
        symmetry_fraction = 0.5
    else:
        y_inner = np.linspace(0.0, half_y, ny_inner + 1)
        y_edges = _append_geometric_edges(y_inner, half_y + multiplier * ell, growth)
        symmetry_fraction = 0.25

    vo2_t = float(geometry["vo2_thickness_m"])
    ti_t = float(geometry["ti_thickness_m"])
    au_t = float(geometry["au_thickness_m"])
    nti = max(1, int(np.ceil(nvo2_z * ti_t / vo2_t)))
    nau = max(1, int(np.ceil(nvo2_z * au_t / vo2_t)))
    au_edges = _layer_edges(au_t, nau, -(vo2_t + ti_t))
    ti_edges = _layer_edges(ti_t, nti, -vo2_t)
    vo2_edges = _layer_edges(vo2_t, nvo2_z, 0.0)
    near_depth = half_x
    substrate_near = np.linspace(0.0, near_depth, nsub_near + 1)
    substrate_edges = _append_geometric_edges(substrate_near, multiplier * ell, growth)
    z_edges = np.unique(np.concatenate((au_edges, ti_edges, vo2_edges, substrate_edges)))

    x = 0.5 * (x_edges[:-1] + x_edges[1:])
    y = 0.5 * (y_edges[:-1] + y_edges[1:])
    z = 0.5 * (z_edges[:-1] + z_edges[1:])
    nz, ny, nx = z.size, y.size, x.size
    material = np.full((nz, ny, nx), INACTIVE, dtype=np.int8)
    in_x = x <= half_x * (1.0 + 1.0e-12)
    if mode == "xz":
        in_y = np.ones_like(y, dtype=bool)
    else:
        in_y = y <= half_y * (1.0 + 1.0e-12)
    footprint = in_y[:, None] & in_x[None, :]
    if not np.any(np.isclose(x_edges, contact_start, rtol=0.0, atol=1.0e-20)):
        raise RuntimeError("contact support must coincide with a registered x face")
    contact_xy = footprint & (x[None, :] >= contact_start * (1.0 - 1.0e-12))

    for iz, zc in enumerate(z):
        if zc >= 0.0:
            material[iz, :, :] = AL2O3
        elif zc >= -vo2_t:
            material[iz, footprint] = VO2
        elif zc >= -(vo2_t + ti_t):
            material[iz, contact_xy] = TI
        else:
            material[iz, contact_xy] = AU

    return HeterogeneousThermalGrid(
        x_edges_m=x_edges,
        y_edges_m=y_edges,
        z_edges_m=z_edges,
        material_id=material,
        mode=mode,
        mesh=mesh,
        domain=domain,
        device_half_x_m=half_x,
        device_half_y_m=half_y,
        contact_start_x_m=contact_start,
        symmetry_fraction=symmetry_fraction,
    )


def build_homogeneous_anchor_grid(
    config: Mapping[str, Any],
    *,
    mesh: str,
    domain: str,
) -> HeterogeneousThermalGrid:
    """Build a substrate-only quarter-domain anchor without a raised stack."""

    geometry = config["geometry"]
    profile = config["grid"]["mesh_profiles"][mesh]
    multiplier = float(config["grid"]["domain_multipliers_of_maximum_diffusion_length"][domain])
    ell = float(config["time"]["maximum_diffusion_length_m"])
    growth = float(config["grid"]["outer_cell_growth_ratio"])
    half_x = 0.5 * float(geometry["vo2_full_x_m"])
    half_y = 0.5 * float(geometry["vo2_full_y_m"])
    x = _append_geometric_edges(
        np.linspace(0.0, half_x, int(profile["vo2_half_x_cells"]) + 1),
        half_x + multiplier * ell,
        growth,
    )
    y = _append_geometric_edges(
        np.linspace(0.0, half_y, int(profile["vo2_half_y_cells"]) + 1),
        half_y + multiplier * ell,
        growth,
    )
    near = np.linspace(0.0, half_x, int(profile["substrate_near_cells"]) + 1)
    z = _append_geometric_edges(near, multiplier * ell, growth)
    material = np.full((z.size - 1, y.size - 1, x.size - 1), AL2O3, dtype=np.int8)
    return HeterogeneousThermalGrid(
        x_edges_m=x,
        y_edges_m=y,
        z_edges_m=z,
        material_id=material,
        mode="3d",
        mesh=mesh,
        domain=domain,
        device_half_x_m=half_x,
        device_half_y_m=half_y,
        contact_start_x_m=half_x,
        symmetry_fraction=0.25,
    )


def build_layered_1d_grid(
    config: Mapping[str, Any],
    *,
    resolution: str = "base",
) -> HeterogeneousThermalGrid:
    """Build a full-area, laterally adiabatic 1-D multilayer FVM grid.

    This is the voting finite-volume comparator for the independent modal 1-D
    reference.  It retains the physical source area, uses the full registered
    power, and fixes only the bottom substrate face at ambient.
    """

    if resolution not in {"base", "fine"}:
        raise ValueError("resolution must be 'base' or 'fine'")
    geometry = config["geometry"]
    reference = config["layered_reference"]
    counts = reference[
        "reference_mesh_elements_per_layer_base"
        if resolution == "base"
        else "reference_mesh_elements_per_layer_fine"
    ]
    if len(counts) != 4 or min(int(value) for value in counts) < 1:
        raise ValueError("layered reference requires four positive element counts")
    nau, nti, nvo2, nsub = (int(value) for value in counts)
    vo2_t = float(geometry["vo2_thickness_m"])
    ti_t = float(geometry["ti_thickness_m"])
    au_t = float(geometry["au_thickness_m"])
    sub_t = float(reference["substrate_reference_depth_m"])
    au_edges = _layer_edges(au_t, nau, -(vo2_t + ti_t))
    ti_edges = _layer_edges(ti_t, nti, -vo2_t)
    vo2_edges = _layer_edges(vo2_t, nvo2, 0.0)
    sub_edges = np.linspace(0.0, sub_t, nsub + 1)
    z_edges = np.unique(np.concatenate((au_edges, ti_edges, vo2_edges, sub_edges)))
    z_centres = 0.5 * (z_edges[:-1] + z_edges[1:])
    material = np.empty((z_centres.size, 1, 1), dtype=np.int8)
    material[:, 0, 0] = np.where(
        z_centres >= 0.0,
        AL2O3,
        np.where(
            z_centres >= -vo2_t,
            VO2,
            np.where(z_centres >= -(vo2_t + ti_t), TI, AU),
        ),
    )
    full_x = float(geometry["vo2_full_x_m"])
    full_y = float(geometry["vo2_full_y_m"])
    return HeterogeneousThermalGrid(
        x_edges_m=np.asarray([0.0, full_x]),
        y_edges_m=np.asarray([0.0, full_y]),
        z_edges_m=z_edges,
        material_id=material,
        mode="layered1d",
        mesh=resolution,
        domain="finite_substrate",
        device_half_x_m=full_x,
        device_half_y_m=full_y,
        contact_start_x_m=0.0,
        symmetry_fraction=1.0,
    )
def _face_resistance(
    material_a: int,
    material_b: int,
    distance_a_m: float,
    distance_b_m: float,
    conductivity: np.ndarray,
    interface_resistance: Mapping[tuple[int, int], float],
) -> float:
    pair = tuple(sorted((int(material_a), int(material_b))))
    r_interface = float(interface_resistance.get(pair, 0.0))
    if r_interface < 0.0 or not np.isfinite(r_interface):
        raise ValueError("interface thermal resistance must be finite and non-negative")
    return distance_a_m / conductivity[material_a] + r_interface + distance_b_m / conductivity[material_b]


def assemble_heterogeneous_system(
    config: Mapping[str, Any],
    grid: HeterogeneousThermalGrid,
    *,
    interface_resistance_m2K_W: Mapping[tuple[int, int], float] | None = None,
) -> HeterogeneousThermalSystem:
    """Assemble a conservative active-cell FVM operator.

    The matrix contains only active cells.  Active-to-void faces contribute no
    conductance, whereas remote x/y/bottom substrate faces contribute an
    ambient Dirichlet conductance.
    """

    conductivity, volumetric_capacity = _material_arrays(config)
    interface = dict(interface_resistance_m2K_W or {})
    dz = np.diff(grid.z_edges_m)
    dy = np.diff(grid.y_edges_m)
    dx = np.diff(grid.x_edges_m)
    nz, ny, nx = grid.shape
    active_flat = np.flatnonzero(grid.active_mask.ravel())
    flat_to_active = np.full(grid.material_id.size, -1, dtype=int)
    flat_to_active[active_flat] = np.arange(active_flat.size)
    matrix = lil_matrix((active_flat.size, active_flat.size), dtype=float)
    boundary = np.zeros(active_flat.size, dtype=float)
    volume = np.empty(active_flat.size, dtype=float)
    material_active = grid.material_id.ravel()[active_flat].astype(int)

    def flat_index(iz: int, iy: int, ix: int) -> int:
        return (iz * ny + iy) * nx + ix

    def connect(a: int, b: int, conductance: float) -> None:
        matrix[a, a] += conductance
        matrix[b, b] += conductance
        matrix[a, b] -= conductance
        matrix[b, a] -= conductance

    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                material_here = int(grid.material_id[iz, iy, ix])
                if material_here == INACTIVE:
                    continue
                row = int(flat_to_active[flat_index(iz, iy, ix)])
                volume[row] = dx[ix] * dy[iy] * dz[iz]
                neighbours = (
                    (iz, iy, ix + 1, dy[iy] * dz[iz], 0.5 * dx[ix], 0.5 * dx[ix + 1])
                    if ix + 1 < nx else None,
                    (iz, iy + 1, ix, dx[ix] * dz[iz], 0.5 * dy[iy], 0.5 * dy[iy + 1])
                    if iy + 1 < ny else None,
                    (iz + 1, iy, ix, dx[ix] * dy[iy], 0.5 * dz[iz], 0.5 * dz[iz + 1])
                    if iz + 1 < nz else None,
                )
                for neighbour in neighbours:
                    if neighbour is None:
                        continue
                    jz, jy, jx, area, da, db = neighbour
                    material_there = int(grid.material_id[jz, jy, jx])
                    if material_there == INACTIVE:
                        continue
                    col = int(flat_to_active[flat_index(jz, jy, jx)])
                    resistance = _face_resistance(
                        material_here, material_there, da, db, conductivity, interface
                    )
                    connect(row, col, area / resistance)

                # Only remote substrate faces are fixed at ambient.  Symmetry
                # faces x=0/y=0 and every active-to-void/exposed face are zero flux.
                if material_here == AL2O3:
                    k_here = conductivity[material_here]
                    far = 0.0
                    if grid.mode != "layered1d" and ix == nx - 1:
                        far += k_here * dy[iy] * dz[iz] / (0.5 * dx[ix])
                    if grid.mode == "3d" and iy == ny - 1:
                        far += k_here * dx[ix] * dz[iz] / (0.5 * dy[iy])
                    if iz == nz - 1:
                        far += k_here * dx[ix] * dy[iy] / (0.5 * dz[iz])
                    matrix[row, row] += far
                    boundary[row] = far

    capacity = volumetric_capacity[material_active] * volume
    assembled = matrix.tocsc()
    if active_flat.size == 0 or np.any(capacity <= 0.0):
        raise RuntimeError("assembled thermal system has no positive-capacity active cells")
    return HeterogeneousThermalSystem(
        grid=grid,
        active_flat_indices=active_flat,
        flat_to_active=flat_to_active,
        material_active=material_active,
        volume_m3=volume,
        capacity_J_K=capacity,
        conductance_W_K=assembled,
        boundary_conductance_W_K=boundary,
        thermal_conductivity_W_mK=conductivity,
        volumetric_heat_capacity_J_m3K=volumetric_capacity,
        interface_resistance_m2K_W=interface,
    )


def build_layered_top_source(
    config: Mapping[str, Any],
    system: HeterogeneousThermalSystem,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply the full registered power to the top face of a 1-D stack."""

    if system.grid.mode != "layered1d":
        raise ValueError("layered top source requires a layered1d system")
    grid = system.grid
    nz, ny, nx = grid.shape
    iz, _, _ = np.unravel_index(system.active_flat_indices, (nz, ny, nx))
    top = iz == 0
    if np.count_nonzero(top) != 1:
        raise RuntimeError("layered 1-D grid must contain one top cell")
    power = float(config["geometry"]["full_power_W"])
    source = np.zeros_like(system.capacity_J_K)
    source[top] = power
    area = float(config["geometry"]["vo2_full_x_m"]) * float(
        config["geometry"]["vo2_full_y_m"]
    )
    return source, {
        "source_id": "S_layered_top_isoflux",
        "integrated_model_power_W": float(np.sum(source)),
        "expected_model_power_W": power,
        "full_power_W": power,
        "symmetry_fraction": 1.0,
        "source_power_integration_relative_error": 0.0,
        "source_geometry_integration_relative_error": 0.0,
        "surface_source_area_m2": area,
        "source_flux_W_m2": power / area,
    }


def _active_coordinates(system: HeterogeneousThermalSystem) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid = system.grid
    nz, ny, nx = grid.shape
    indices = np.unravel_index(system.active_flat_indices, (nz, ny, nx))
    z = 0.5 * (grid.z_edges_m[:-1] + grid.z_edges_m[1:])[indices[0]]
    y = 0.5 * (grid.y_edges_m[:-1] + grid.y_edges_m[1:])[indices[1]]
    x = 0.5 * (grid.x_edges_m[:-1] + grid.x_edges_m[1:])[indices[2]]
    return x, y, z


def build_source_vector(
    config: Mapping[str, Any],
    system: HeterogeneousThermalSystem,
    source_id: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Construct one equal-power source family in the VO2 volume."""

    if source_id not in {"S_bulk", "S_contact", "S_mixed"}:
        raise ValueError("unsupported voting source family")
    x, _, _ = _active_coordinates(system)
    vo2 = system.material_active == VO2
    contact = vo2 & (x >= system.grid.contact_start_x_m * (1.0 - 1.0e-12))
    if not np.any(vo2) or not np.any(contact):
        raise RuntimeError("source support is not represented by the registered grid")
    bulk_weights = np.where(vo2, system.volume_m3, 0.0)
    contact_weights = np.where(contact, system.volume_m3, 0.0)
    actual_bulk_volume = float(np.sum(bulk_weights))
    actual_contact_volume = float(np.sum(contact_weights))
    expected_bulk_volume = (
        float(config["geometry"]["vo2_full_x_m"])
        * float(config["geometry"]["vo2_full_y_m"])
        * float(config["geometry"]["vo2_thickness_m"])
        * system.grid.symmetry_fraction
    )
    contact_fraction = float(config["geometry"]["contact_support_fraction_of_half_x"])
    expected_contact_volume = expected_bulk_volume * contact_fraction
    bulk_geometry_error = abs(actual_bulk_volume - expected_bulk_volume) / expected_bulk_volume
    contact_geometry_error = abs(actual_contact_volume - expected_contact_volume) / expected_contact_volume
    bulk_weights /= np.sum(bulk_weights)
    contact_weights /= np.sum(contact_weights)
    if source_id == "S_bulk":
        weights = bulk_weights
    elif source_id == "S_contact":
        weights = contact_weights
    else:
        weights = 0.5 * bulk_weights + 0.5 * contact_weights
    expected_power = float(config["geometry"]["full_power_W"]) * system.grid.symmetry_fraction
    registered_key = "xz_half_domain_power_W" if system.grid.mode == "xz" else "quarter_power_W"
    registered_power = float(config["geometry"][registered_key])
    if not np.isclose(expected_power, registered_power, rtol=0.0, atol=1.0e-18):
        raise ValueError("registered symmetry power is inconsistent with full power")
    source = expected_power * weights
    integration_error = abs(float(np.sum(source)) - expected_power) / expected_power
    return source, {
        "source_id": source_id,
        "integrated_model_power_W": float(np.sum(source)),
        "expected_model_power_W": expected_power,
        "full_power_W": float(config["geometry"]["full_power_W"]),
        "symmetry_fraction": system.grid.symmetry_fraction,
        "source_power_integration_relative_error": float(integration_error),
        "source_geometry_integration_relative_error": float(
            max(bulk_geometry_error, contact_geometry_error)
        ),
        "source_cell_count": int(np.count_nonzero(weights)),
        "vo2_source_support_volume_m3": float(np.sum(system.volume_m3[weights > 0.0])),
        "bulk_support_volume_m3": actual_bulk_volume,
        "expected_bulk_support_volume_m3": expected_bulk_volume,
        "contact_support_volume_m3": actual_contact_volume,
        "expected_contact_support_volume_m3": expected_contact_volume,
        "bulk_support_volume_relative_error": float(bulk_geometry_error),
        "contact_support_volume_relative_error": float(contact_geometry_error),
        "contact_support_fraction_of_half_x": contact_fraction,
        "contact_support_face_aligned": bool(
            np.any(
                np.isclose(
                    system.grid.x_edges_m,
                    system.grid.contact_start_x_m,
                    rtol=0.0,
                    atol=1.0e-20,
                )
            )
        ),
    }


def build_surface_anchor_source(
    config: Mapping[str, Any],
    system: HeterogeneousThermalSystem,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply an M43-compatible footprint isoflux to the substrate top face."""

    grid = system.grid
    if np.any(grid.material_id != AL2O3) or grid.z_edges_m[0] != 0.0:
        raise ValueError("surface anchor requires the dedicated substrate-only grid")
    nz, ny, nx = grid.shape
    dz_index, y_index, x_index = np.unravel_index(system.active_flat_indices, (nz, ny, nx))
    x = 0.5 * (grid.x_edges_m[:-1] + grid.x_edges_m[1:])
    y = 0.5 * (grid.y_edges_m[:-1] + grid.y_edges_m[1:])
    dx = np.diff(grid.x_edges_m)
    dy = np.diff(grid.y_edges_m)
    mask = (
        (dz_index == 0)
        & (x[x_index] <= grid.device_half_x_m * (1.0 + 1.0e-12))
        & (y[y_index] <= grid.device_half_y_m * (1.0 + 1.0e-12))
    )
    areas = dx[x_index] * dy[y_index]
    weights = np.where(mask, areas, 0.0)
    weights /= np.sum(weights)
    expected_power = float(config["geometry"]["quarter_power_W"])
    source = expected_power * weights
    return source, {
        "source_id": "S_surface_anchor",
        "integrated_model_power_W": float(np.sum(source)),
        "expected_model_power_W": expected_power,
        "full_power_W": float(config["geometry"]["full_power_W"]),
        "symmetry_fraction": 0.25,
        "source_power_integration_relative_error": float(abs(np.sum(source) - expected_power) / expected_power),
        "source_cell_count": int(np.count_nonzero(weights)),
        "surface_source_area_m2": float(np.sum(areas[mask])),
    }


def independent_boundary_outflow_W(
    system: HeterogeneousThermalSystem,
    theta_active_K: np.ndarray,
) -> float:
    """Recompute remote-substrate outflow without the ledger vector."""

    theta = np.asarray(theta_active_K, dtype=float)
    if theta.shape != system.capacity_J_K.shape:
        raise ValueError("active temperature shape mismatch")
    grid = system.grid
    nz, ny, nx = grid.shape
    dz = np.diff(grid.z_edges_m)
    dy = np.diff(grid.y_edges_m)
    dx = np.diff(grid.x_edges_m)
    outward = 0.0
    for active_index, flat_index in enumerate(system.active_flat_indices):
        iz, iy, ix = np.unravel_index(flat_index, (nz, ny, nx))
        material = int(grid.material_id[iz, iy, ix])
        if material != AL2O3:
            continue
        k = system.thermal_conductivity_W_mK[material]
        if grid.mode != "layered1d" and ix == nx - 1:
            outward += k * dy[iy] * dz[iz] * theta[active_index] / (0.5 * dx[ix])
        if grid.mode == "3d" and iy == ny - 1:
            outward += k * dx[ix] * dz[iz] * theta[active_index] / (0.5 * dy[iy])
        if iz == nz - 1:
            outward += k * dx[ix] * dy[iy] * theta[active_index] / (0.5 * dz[iz])
    return float(outward)


def surface_source_face_mean_rise_K(
    system: HeterogeneousThermalSystem,
    theta_active_K: np.ndarray,
    source_W: np.ndarray,
) -> float:
    """Reconstruct the area-mean Neumann source-face temperature.

    For a cell-centred FVM with a specified top-face heat flux, the boundary
    temperature is ``T_cell + q'' dz/(2k)``.  The function rejects volume
    sources so heterogeneous VO2 means cannot silently become surface values.
    """

    theta = np.asarray(theta_active_K, dtype=float)
    source = np.asarray(source_W, dtype=float)
    if theta.shape != system.capacity_J_K.shape or source.shape != theta.shape:
        raise ValueError("active temperature/source shape mismatch")
    grid = system.grid
    nz, ny, nx = grid.shape
    iz, iy, ix = np.unravel_index(system.active_flat_indices, (nz, ny, nx))
    source_cells = source > 0.0
    if not np.any(source_cells) or not np.all(iz[source_cells] == 0):
        raise ValueError("source is not confined to the registered top boundary cells")
    # A raised-stack volume source also occupies its top cell; require the top
    # grid face itself to be the exposed boundary used by anchor/1-D contracts.
    if grid.mode not in {"3d", "layered1d"}:
        raise ValueError("surface reconstruction is not registered for this mode")
    dx = np.diff(grid.x_edges_m)
    dy = np.diff(grid.y_edges_m)
    dz = np.diff(grid.z_edges_m)
    area = dx[ix[source_cells]] * dy[iy[source_cells]]
    q_flux = source[source_cells] / area
    materials = system.material_active[source_cells]
    correction = q_flux * dz[iz[source_cells]] / (
        2.0 * system.thermal_conductivity_W_mK[materials]
    )
    face = theta[source_cells] + correction
    return float(np.average(face, weights=area))


def _weighted_means(
    system: HeterogeneousThermalSystem,
    theta: np.ndarray,
    source: np.ndarray,
) -> dict[str, float]:
    vo2 = system.material_active == VO2
    if np.any(vo2):
        vo2_mean = float(np.average(theta[vo2], weights=system.volume_m3[vo2]))
        vo2_tmax = float(np.max(theta[vo2]))
    else:
        vo2_mean = float("nan")
        vo2_tmax = float("nan")
    source_mask = source > 0.0
    source_mean = float(np.average(theta[source_mask], weights=source[source_mask]))
    return {"vo2_mean_rise_K": vo2_mean, "vo2_tmax_rise_K": vo2_tmax, "source_mean_rise_K": source_mean}


def solve_steady(
    system: HeterogeneousThermalSystem,
    source_W: np.ndarray,
    *,
    full_power_W: float,
) -> dict[str, Any]:
    """Solve one constant-power steady thermal case."""

    source = np.asarray(source_W, dtype=float)
    if source.shape != system.capacity_J_K.shape or np.any(source < 0.0):
        raise ValueError("source must be a non-negative active-cell vector")
    theta = np.asarray(spsolve(system.conductance_W_K, source), dtype=float)
    outward = independent_boundary_outflow_W(system, theta)
    assembled_outward = float(np.dot(system.boundary_conductance_W_K, theta))
    input_power = float(np.sum(source))
    imbalance = abs(outward - input_power) / input_power
    means = _weighted_means(system, theta, source)
    try:
        surface_face_mean = surface_source_face_mean_rise_K(system, theta, source)
    except ValueError:
        surface_face_mean = None
    metrics: dict[str, Any] = {
        **means,
        "vo2_mean_Zth_K_W": means["vo2_mean_rise_K"] / full_power_W,
        "source_mean_Zth_K_W": means["source_mean_rise_K"] / full_power_W,
        "maximum_active_rise_K": float(np.max(theta)),
    }
    if surface_face_mean is not None:
        metrics["source_surface_face_mean_rise_K"] = surface_face_mean
        metrics["source_surface_face_Zth_K_W"] = surface_face_mean / full_power_W
    return {
        "finite": bool(np.isfinite(theta).all()),
        "positive": bool(np.min(theta) >= -1.0e-12 * max(float(np.max(theta)), 1.0)),
        "active_cell_count": system.grid.active_cell_count,
        "metrics": metrics,
        "ledger": {
            "input_power_W": input_power,
            "independent_outward_power_W": outward,
            "assembled_outward_power_W": assembled_outward,
            "normalized_power_imbalance": float(imbalance),
            "boundary_flux_relative_disagreement": float(abs(outward - assembled_outward) / max(abs(outward) + abs(assembled_outward), 1.0e-30)),
        },
        "theta_active_K": theta,
    }


def solve_transient(
    system: HeterogeneousThermalSystem,
    source_W: np.ndarray,
    *,
    full_power_W: float,
    times_s: np.ndarray | list[float],
    steps_per_interval: int,
) -> dict[str, Any]:
    """Backward-Euler constant-power step with an independent energy ledger."""

    source = np.asarray(source_W, dtype=float)
    times = np.asarray(times_s, dtype=float)
    if source.shape != system.capacity_J_K.shape or np.any(source < 0.0):
        raise ValueError("source must be a non-negative active-cell vector")
    if times.ndim != 1 or times.size == 0 or np.any(times <= 0.0) or np.any(np.diff(times) <= 0.0):
        raise ValueError("times must be strictly increasing and positive")
    if steps_per_interval < 1:
        raise ValueError("steps_per_interval must be positive")
    theta = np.zeros_like(system.capacity_J_K)
    previous_time = 0.0
    cumulative_outward = 0.0
    input_power = float(np.sum(source))
    vo2_mean: list[float] = []
    vo2_tmax: list[float] = []
    source_mean: list[float] = []
    surface_face_mean: list[float] = []
    maximum: list[float] = []
    outward_values: list[float] = []
    stored_values: list[float] = []
    cumulative_values: list[float] = []
    imbalance_values: list[float] = []
    flux_disagreement_values: list[float] = []
    total_steps = 0
    for target in times:
        dt = float(target - previous_time) / steps_per_interval
        lhs = diags(system.capacity_J_K / dt, format="csc") + system.conductance_W_K
        factor = splu(lhs)
        for _ in range(steps_per_interval):
            theta = factor.solve(system.capacity_J_K * theta / dt + source)
            outward = independent_boundary_outflow_W(system, theta)
            cumulative_outward += outward * dt
            total_steps += 1
        means = _weighted_means(system, theta, source)
        try:
            face_mean = surface_source_face_mean_rise_K(system, theta, source)
        except ValueError:
            face_mean = float("nan")
        assembled_outward = float(np.dot(system.boundary_conductance_W_K, theta))
        stored = float(np.dot(system.capacity_J_K, theta))
        input_energy = input_power * float(target)
        imbalance = abs(stored + cumulative_outward - input_energy) / input_energy
        vo2_mean.append(means["vo2_mean_rise_K"])
        vo2_tmax.append(means["vo2_tmax_rise_K"])
        source_mean.append(means["source_mean_rise_K"])
        surface_face_mean.append(face_mean)
        maximum.append(float(np.max(theta)))
        outward_values.append(outward)
        stored_values.append(stored)
        cumulative_values.append(cumulative_outward)
        imbalance_values.append(float(imbalance))
        flux_disagreement_values.append(float(abs(outward - assembled_outward) / max(abs(outward) + abs(assembled_outward), 1.0e-30)))
        previous_time = float(target)
    vo2_array = np.asarray(vo2_mean)
    source_array = np.asarray(source_mean)
    finite = bool(np.isfinite(theta).all() and np.isfinite(source_array).all())
    metrics: dict[str, Any] = {
        "time_s": times.tolist(),
        "vo2_mean_rise_K": vo2_mean,
        "vo2_tmax_rise_K": vo2_tmax,
        "source_mean_rise_K": source_mean,
        "vo2_mean_Zth_K_W": (vo2_array / full_power_W).tolist(),
        "source_mean_Zth_K_W": (source_array / full_power_W).tolist(),
        "maximum_active_rise_K": maximum,
        "steps_per_interval": int(steps_per_interval),
        "total_backward_euler_steps": total_steps,
    }
    if np.all(np.isfinite(surface_face_mean)):
        metrics["source_surface_face_mean_rise_K"] = surface_face_mean
        metrics["source_surface_face_Zth_K_W"] = (
            np.asarray(surface_face_mean) / full_power_W
        ).tolist()
    return {
        "finite": finite,
        "positive": bool(np.min(theta) >= -1.0e-12 * max(float(np.max(theta)), 1.0)),
        "monotone_vo2_mean": bool(np.all(np.diff(vo2_array[np.isfinite(vo2_array)]) >= -1.0e-12)),
        "active_cell_count": system.grid.active_cell_count,
        "metrics": metrics,
        "ledger": {
            "input_power_W": input_power,
            "independent_outward_power_W": outward_values,
            "stored_sensible_energy_J": stored_values,
            "cumulative_outward_heat_J": cumulative_values,
            "normalized_sensible_energy_imbalance": imbalance_values,
            "maximum_normalized_sensible_energy_imbalance": float(np.max(imbalance_values)),
            "maximum_boundary_flux_relative_disagreement": float(np.max(flux_disagreement_values)),
        },
        "theta_active_K": theta,
    }


__all__ = [
    "AL2O3",
    "AU",
    "INACTIVE",
    "TI",
    "VO2",
    "HeterogeneousThermalGrid",
    "HeterogeneousThermalSystem",
    "assemble_heterogeneous_system",
    "build_heterogeneous_grid",
    "build_homogeneous_anchor_grid",
    "build_layered_1d_grid",
    "build_layered_top_source",
    "build_source_vector",
    "build_surface_anchor_source",
    "independent_boundary_outflow_W",
    "solve_steady",
    "solve_transient",
    "surface_source_face_mean_rise_K",
]
