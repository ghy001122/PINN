"""Conservative masked x-z FVM for the Qiu-2024 VO2 thermal neuristor.

The solver treats Al2O3 as thermal-only, obtains device current exclusively
from terminal boundary flux, and reconstructs independent electrical and
thermal conservation ledgers from face fluxes and storage changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

from pinnpcm.physics.qiu_vo2_device import QiuMesh


@dataclass(frozen=True)
class BoundaryFace:
    name: str
    iz: int
    ix: int
    side: str
    value: float
    resistance_area: float = 0.0


_SIDES = {
    "left": (0, -1),
    "right": (0, 1),
    "bottom": (-1, 0),
    "top": (1, 0),
}


def _face_geometry(mesh: QiuMesh, iz: int, ix: int, side: str) -> tuple[float, float]:
    if side in {"left", "right"}:
        return float(mesh.dz_m[iz] * mesh.depth_m), float(0.5 * mesh.dx_m[ix])
    return float(mesh.dx_m[ix] * mesh.depth_m), float(0.5 * mesh.dz_m[iz])


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((str(a), str(b))))


def qiu_terminal_faces(mesh: QiuMesh, source_voltage_V: float) -> list[BoundaryFace]:
    return [
        *[
            BoundaryFace("source", iz, ix, "top", float(source_voltage_V))
            for iz, ix in mesh.source_terminal_cells
        ],
        *[
            BoundaryFace("ground", iz, ix, "top", 0.0)
            for iz, ix in mesh.ground_terminal_cells
        ],
    ]


def _node_map(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    node = np.full(mask.shape, -1, dtype=int)
    cells = np.argwhere(mask)
    for index, (iz, ix) in enumerate(cells):
        node[iz, ix] = index
    return node, cells


def solve_electrical(
    mesh: QiuMesh,
    conductivity_S_m: np.ndarray,
    terminals: Sequence[BoundaryFace],
    contact_resistance_m2_ohm: Mapping[tuple[str, str], float] | None = None,
    *,
    electrical_mask: np.ndarray | None = None,
) -> dict[str, object]:
    """Solve div(sigma grad(phi))=0 on the explicitly masked electrical domain."""
    sigma = np.asarray(conductivity_S_m, dtype=float)
    mask = mesh.electrical_mask if electrical_mask is None else np.asarray(electrical_mask, dtype=bool)
    if sigma.shape != mesh.shape or mask.shape != mesh.shape:
        raise ValueError("electrical fields must match the mesh")
    if np.any(sigma[mask] <= 0.0) or not np.isfinite(sigma[mask]).all():
        raise ValueError("active electrical conductivity must be finite and positive")
    contacts = {
        _pair_key(*key): float(value)
        for key, value in (contact_resistance_m2_ohm or {}).items()
    }
    node, cells = _node_map(mask)
    matrix = sparse.lil_matrix((len(cells), len(cells)), dtype=float)
    rhs = np.zeros(len(cells), dtype=float)
    terminal_map: dict[tuple[int, int, str], BoundaryFace] = {}
    terminal_entries: dict[str, list[tuple[int, float, float]]] = {}
    for face in terminals:
        if face.side not in _SIDES:
            raise ValueError(f"unknown terminal side {face.side}")
        key = (int(face.iz), int(face.ix), face.side)
        if key in terminal_map:
            raise ValueError(f"overlapping terminal face {key}")
        terminal_map[key] = face
        terminal_entries.setdefault(face.name, [])

    nz, nx = mesh.shape
    for iz, ix in cells:
        row = int(node[iz, ix])
        for side, (diz, dix) in _SIDES.items():
            jz, jx = int(iz + diz), int(ix + dix)
            if 0 <= jz < nz and 0 <= jx < nx and mask[jz, jx]:
                area, half_i = _face_geometry(mesh, int(iz), int(ix), side)
                opposite = "right" if side == "left" else "left" if side == "right" else "top" if side == "bottom" else "bottom"
                _, half_j = _face_geometry(mesh, jz, jx, opposite)
                rc = contacts.get(
                    _pair_key(mesh.material[iz, ix], mesh.material[jz, jx]), 0.0
                )
                resistance_area = half_i / sigma[iz, ix] + rc + half_j / sigma[jz, jx]
                conductance = area / max(resistance_area, 1.0e-30)
                matrix[row, row] += conductance
                matrix[row, int(node[jz, jx])] -= conductance
            else:
                face = terminal_map.get((int(iz), int(ix), side))
                if face is None:
                    continue
                area, half_i = _face_geometry(mesh, int(iz), int(ix), side)
                conductance = area / max(
                    half_i / sigma[iz, ix] + float(face.resistance_area), 1.0e-30
                )
                matrix[row, row] += conductance
                rhs[row] += conductance * face.value
                terminal_entries[face.name].append((row, conductance, face.value))
    if not terminal_entries or any(not entries for entries in terminal_entries.values()):
        raise ValueError("every electrical terminal must own at least one boundary face")
    values = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float)
    potential = np.full(mesh.shape, np.nan, dtype=float)
    for value, (iz, ix) in zip(values, cells, strict=True):
        potential[iz, ix] = value
    currents = {
        name: float(sum(g * (voltage - values[row]) for row, g, voltage in entries))
        for name, entries in terminal_entries.items()
    }
    denominator = max(sum(abs(value) for value in currents.values()), 1.0e-30)
    current_imbalance = abs(sum(currents.values())) / denominator

    cell_joule = np.zeros(mesh.shape, dtype=float)
    interface_records: list[dict[str, object]] = []
    # Count every internal face exactly once.
    for iz, ix in cells:
        for side, (diz, dix) in (("right", (0, 1)), ("top", (1, 0))):
            jz, jx = int(iz + diz), int(ix + dix)
            if not (0 <= jz < nz and 0 <= jx < nx and mask[jz, jx]):
                continue
            area, half_i = _face_geometry(mesh, int(iz), int(ix), side)
            opposite = "left" if side == "right" else "bottom"
            _, half_j = _face_geometry(mesh, jz, jx, opposite)
            rc = contacts.get(
                _pair_key(mesh.material[iz, ix], mesh.material[jz, jx]), 0.0
            )
            resistance_area = half_i / sigma[iz, ix] + rc + half_j / sigma[jz, jx]
            g = area / max(resistance_area, 1.0e-30)
            current = g * (potential[iz, ix] - potential[jz, jx])
            power = g * (potential[iz, ix] - potential[jz, jx]) ** 2
            cell_joule[iz, ix] += 0.5 * power
            cell_joule[jz, jx] += 0.5 * power
            if rc > 0.0:
                interface_records.append(
                    {
                        "cell_a": [int(iz), int(ix)],
                        "cell_b": [jz, jx],
                        "materials": [str(mesh.material[iz, ix]), str(mesh.material[jz, jx])],
                        "signed_current_A": float(current),
                        "contact_voltage_jump_V": float((current / area) * rc),
                    }
                )
    for face in terminals:
        area, half_i = _face_geometry(mesh, face.iz, face.ix, face.side)
        g = area / max(
            half_i / sigma[face.iz, face.ix] + face.resistance_area, 1.0e-30
        )
        power = g * (face.value - potential[face.iz, face.ix]) ** 2
        cell_joule[face.iz, face.ix] += power
    joule_total = float(np.sum(cell_joule))
    terminal_power = float(
        sum(
            face_voltage * currents[name]
            for name, entries in terminal_entries.items()
            for face_voltage in [entries[0][2]]
        )
    )
    power_imbalance = abs(terminal_power - joule_total) / max(
        abs(terminal_power) + abs(joule_total), 1.0e-30
    )
    return {
        "potential_V": potential,
        "terminal_currents_A": currents,
        "relative_current_imbalance": float(current_imbalance),
        "cell_joule_power_W": cell_joule,
        "joule_power_W": joule_total,
        "terminal_power_W": terminal_power,
        "relative_electrical_power_imbalance": float(power_imbalance),
        "interface_records": interface_records,
        "finite": bool(np.isfinite(values).all()),
    }


def cell_electric_field_V_m(
    mesh: QiuMesh,
    potential_V: np.ndarray,
    conductivity_S_m: np.ndarray,
) -> np.ndarray:
    """Estimate material-internal E from conservative face current densities."""
    phi = np.asarray(potential_V, dtype=float)
    sigma = np.asarray(conductivity_S_m, dtype=float)
    field = np.full(mesh.shape, np.nan, dtype=float)
    nz, nx = mesh.shape
    for iz in range(nz):
        for ix in range(nx):
            if not mesh.electrical_mask[iz, ix]:
                continue
            components: list[float] = []
            if ix > 0 and mesh.electrical_mask[iz, ix - 1] and mesh.material[iz, ix] == mesh.material[iz, ix - 1]:
                distance = 0.5 * (mesh.dx_m[ix] + mesh.dx_m[ix - 1])
                components.append((phi[iz, ix] - phi[iz, ix - 1]) / distance)
            if ix + 1 < nx and mesh.electrical_mask[iz, ix + 1] and mesh.material[iz, ix] == mesh.material[iz, ix + 1]:
                distance = 0.5 * (mesh.dx_m[ix] + mesh.dx_m[ix + 1])
                components.append((phi[iz, ix + 1] - phi[iz, ix]) / distance)
            ex = float(np.mean(components)) if components else 0.0
            components = []
            if iz > 0 and mesh.electrical_mask[iz - 1, ix] and mesh.material[iz, ix] == mesh.material[iz - 1, ix]:
                distance = 0.5 * (mesh.dz_m[iz] + mesh.dz_m[iz - 1])
                components.append((phi[iz, ix] - phi[iz - 1, ix]) / distance)
            if iz + 1 < nz and mesh.electrical_mask[iz + 1, ix] and mesh.material[iz, ix] == mesh.material[iz + 1, ix]:
                distance = 0.5 * (mesh.dz_m[iz] + mesh.dz_m[iz + 1])
                components.append((phi[iz + 1, ix] - phi[iz, ix]) / distance)
            ez = float(np.mean(components)) if components else 0.0
            field[iz, ix] = float(np.hypot(ex, ez))
    return field


def advance_thermal_implicit(
    mesh: QiuMesh,
    old_temperature_K: np.ndarray,
    thermal_conductivity_W_mK: np.ndarray,
    volumetric_heat_capacity_J_m3K: np.ndarray,
    cell_heat_power_W: np.ndarray,
    dt_s: float,
    ambient_temperature_K: float,
    bottom_conductance_W_K: float,
    interface_resistance_m2K_W: Mapping[tuple[str, str], float] | None = None,
) -> dict[str, object]:
    """Implicit conservative heat step with an independently rebuilt ledger."""
    if dt_s <= 0.0 or bottom_conductance_W_K < 0.0:
        raise ValueError("thermal step and boundary conductance are invalid")
    old = np.asarray(old_temperature_K, dtype=float)
    k = np.asarray(thermal_conductivity_W_mK, dtype=float)
    rho_cp = np.asarray(volumetric_heat_capacity_J_m3K, dtype=float)
    heat = np.asarray(cell_heat_power_W, dtype=float)
    if any(field.shape != mesh.shape for field in (old, k, rho_cp, heat)):
        raise ValueError("thermal fields must match mesh")
    mask = mesh.thermal_mask
    resistances = {
        _pair_key(*key): float(value)
        for key, value in (interface_resistance_m2K_W or {}).items()
    }
    node, cells = _node_map(mask)
    matrix = sparse.lil_matrix((len(cells), len(cells)), dtype=float)
    rhs = np.zeros(len(cells), dtype=float)
    bottom_cells = [(int(iz), int(ix)) for iz, ix in cells if iz == 0]
    bottom_area = sum(mesh.dx_m[ix] * mesh.depth_m for _, ix in bottom_cells)
    capacities = np.zeros(mesh.shape, dtype=float)
    nz, nx = mesh.shape
    for iz, ix in cells:
        row = int(node[iz, ix])
        volume = mesh.dx_m[ix] * mesh.dz_m[iz] * mesh.depth_m
        capacity = rho_cp[iz, ix] * volume
        capacities[iz, ix] = capacity
        matrix[row, row] += capacity / dt_s
        rhs[row] += capacity * old[iz, ix] / dt_s + heat[iz, ix]
        for side, (diz, dix) in _SIDES.items():
            jz, jx = int(iz + diz), int(ix + dix)
            if not (0 <= jz < nz and 0 <= jx < nx and mask[jz, jx]):
                continue
            area, half_i = _face_geometry(mesh, int(iz), int(ix), side)
            opposite = "right" if side == "left" else "left" if side == "right" else "top" if side == "bottom" else "bottom"
            _, half_j = _face_geometry(mesh, jz, jx, opposite)
            rth = resistances.get(
                _pair_key(mesh.material[iz, ix], mesh.material[jz, jx]), 0.0
            )
            conductance = area / max(
                half_i / k[iz, ix] + rth + half_j / k[jz, jx], 1.0e-30
            )
            matrix[row, row] += conductance
            matrix[row, int(node[jz, jx])] -= conductance
        if iz == 0 and bottom_area > 0.0:
            area = mesh.dx_m[ix] * mesh.depth_m
            conductance = bottom_conductance_W_K * area / bottom_area
            matrix[row, row] += conductance
            rhs[row] += conductance * ambient_temperature_K
    values = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float)
    new = np.full(mesh.shape, np.nan, dtype=float)
    for value, (iz, ix) in zip(values, cells, strict=True):
        new[iz, ix] = value

    storage_rate = float(np.nansum(capacities * (new - old)) / dt_s)
    boundary_outflow = 0.0
    if bottom_area > 0.0:
        for iz, ix in bottom_cells:
            area = mesh.dx_m[ix] * mesh.depth_m
            conductance = bottom_conductance_W_K * area / bottom_area
            boundary_outflow += conductance * (new[iz, ix] - ambient_temperature_K)
    source_power = float(np.sum(heat[mask]))
    imbalance = abs(storage_rate + boundary_outflow - source_power) / max(
        abs(storage_rate) + abs(boundary_outflow) + abs(source_power), 1.0e-30
    )
    return {
        "temperature_K": new,
        "storage_rate_W": storage_rate,
        "boundary_outflow_W": float(boundary_outflow),
        "source_power_W": source_power,
        "relative_energy_imbalance": float(imbalance),
        "cell_heat_capacity_J_K": capacities,
        "finite": bool(np.isfinite(values).all()),
    }


def solve_steady_thermal(
    mesh: QiuMesh,
    thermal_conductivity_W_mK: np.ndarray,
    boundaries: Sequence[BoundaryFace],
    interface_resistance_m2K_W: Mapping[tuple[str, str], float] | None = None,
) -> dict[str, object]:
    """Steady conduction verifier with Dirichlet temperature faces."""
    k = np.asarray(thermal_conductivity_W_mK, dtype=float)
    mask = mesh.thermal_mask
    node, cells = _node_map(mask)
    resistances = {
        _pair_key(*key): float(value)
        for key, value in (interface_resistance_m2K_W or {}).items()
    }
    bmap = {(b.iz, b.ix, b.side): b for b in boundaries}
    entries: dict[str, list[tuple[int, float, float]]] = {}
    matrix = sparse.lil_matrix((len(cells), len(cells)), dtype=float)
    rhs = np.zeros(len(cells), dtype=float)
    nz, nx = mesh.shape
    for iz, ix in cells:
        row = int(node[iz, ix])
        for side, (diz, dix) in _SIDES.items():
            jz, jx = int(iz + diz), int(ix + dix)
            if 0 <= jz < nz and 0 <= jx < nx and mask[jz, jx]:
                area, half_i = _face_geometry(mesh, int(iz), int(ix), side)
                opposite = "right" if side == "left" else "left" if side == "right" else "top" if side == "bottom" else "bottom"
                _, half_j = _face_geometry(mesh, jz, jx, opposite)
                rth = resistances.get(
                    _pair_key(mesh.material[iz, ix], mesh.material[jz, jx]), 0.0
                )
                g = area / max(half_i / k[iz, ix] + rth + half_j / k[jz, jx], 1.0e-30)
                matrix[row, row] += g
                matrix[row, int(node[jz, jx])] -= g
            else:
                face = bmap.get((int(iz), int(ix), side))
                if face is None:
                    continue
                area, half_i = _face_geometry(mesh, int(iz), int(ix), side)
                g = area / max(half_i / k[iz, ix] + face.resistance_area, 1.0e-30)
                matrix[row, row] += g
                rhs[row] += g * face.value
                entries.setdefault(face.name, []).append((row, g, face.value))
    values = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float)
    temperature = np.full(mesh.shape, np.nan, dtype=float)
    for value, (iz, ix) in zip(values, cells, strict=True):
        temperature[iz, ix] = value
    fluxes = {
        name: float(sum(g * (value - values[row]) for row, g, value in rows))
        for name, rows in entries.items()
    }
    balance = abs(sum(fluxes.values())) / max(sum(abs(v) for v in fluxes.values()), 1.0e-30)
    return {
        "temperature_K": temperature,
        "boundary_heat_in_W": fluxes,
        "relative_heat_imbalance": float(balance),
        "finite": bool(np.isfinite(values).all()),
    }


def implicit_rc_voltage(
    previous_voltage_V: float,
    input_voltage_V: float,
    load_resistance_ohm: float,
    capacitance_F: float,
    device_conductance_S: float,
    dt_s: float,
) -> float:
    numerator = previous_voltage_V + dt_s * input_voltage_V / (
        load_resistance_ohm * capacitance_F
    )
    denominator = 1.0 + dt_s * (
        1.0 / load_resistance_ohm + device_conductance_S
    ) / capacitance_F
    return float(numerator / denominator)


def rc_residual_A(
    previous_voltage_V: float,
    new_voltage_V: float,
    input_voltage_V: float,
    load_resistance_ohm: float,
    capacitance_F: float,
    device_current_A: float,
    dt_s: float,
) -> float:
    return float(
        capacitance_F * (new_voltage_V - previous_voltage_V) / dt_s
        - (input_voltage_V - new_voltage_V) / load_resistance_ohm
        + device_current_A
    )

