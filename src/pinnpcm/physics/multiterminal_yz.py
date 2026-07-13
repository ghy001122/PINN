"""Finite-volume y-z electrical solver for segmented multilayer terminals.

The solver is a reduced synthetic device benchmark. It solves
``div(sigma grad(phi)) = 0`` on cell centers with harmonic face conductances,
Dirichlet electrode faces, and insulating unassigned boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve


@dataclass(frozen=True)
class ElectrodeSegment:
    name: str
    boundary: str
    start: int
    stop: int
    voltage_v: float


def _harmonic(a: float, b: float) -> float:
    return 2.0 * a * b / max(a + b, 1.0e-30)


def solve_multiterminal_yz(
    sigma_s_m: np.ndarray,
    dz_m: np.ndarray,
    dy_m: float,
    electrodes: Iterable[ElectrodeSegment],
    *,
    contact_resistance_ohm_m2: np.ndarray | None = None,
    depth_m: float = 1.0e-6,
) -> dict[str, object]:
    """Solve the cell-centered potential and return signed terminal currents."""
    sigma = np.asarray(sigma_s_m, dtype=float)
    dz = np.asarray(dz_m, dtype=float)
    if sigma.ndim != 2 or sigma.shape[0] != dz.size:
        raise ValueError("sigma must have shape [nz, ny] matching dz")
    if np.any(sigma <= 0.0) or np.any(dz <= 0.0) or dy_m <= 0.0:
        raise ValueError("conductivity and cell dimensions must be positive")
    nz, ny = sigma.shape
    contacts = np.zeros(max(nz - 1, 0), dtype=float) if contact_resistance_ohm_m2 is None else np.asarray(contact_resistance_ohm_m2, dtype=float)
    if contacts.shape != (max(nz - 1, 0),):
        raise ValueError("contact resistance must have nz-1 entries")
    segments = list(electrodes)
    face_map: dict[tuple[str, int], ElectrodeSegment] = {}
    for segment in segments:
        limit = ny if segment.boundary in {"top", "bottom"} else nz
        if segment.boundary not in {"top", "bottom", "left", "right"}:
            raise ValueError(f"Unknown electrode boundary: {segment.boundary}")
        if not (0 <= segment.start < segment.stop <= limit):
            raise ValueError(f"Invalid electrode range for {segment.name}")
        for index in range(segment.start, segment.stop):
            key = (segment.boundary, index)
            if key in face_map:
                raise ValueError(f"Overlapping electrode faces at {key}")
            face_map[key] = segment

    n = nz * ny
    matrix = sparse.lil_matrix((n, n), dtype=float)
    rhs = np.zeros(n, dtype=float)
    terminal_contributions: dict[str, list[tuple[int, float, float]]] = {segment.name: [] for segment in segments}

    def node(iz: int, iy: int) -> int:
        return iz * ny + iy

    def add_dirichlet(row: int, conductance: float, voltage: float, name: str) -> None:
        matrix[row, row] += conductance
        rhs[row] += conductance * voltage
        terminal_contributions[name].append((row, conductance, voltage))

    for iz in range(nz):
        for iy in range(ny):
            row = node(iz, iy)
            if iy > 0:
                g = _harmonic(sigma[iz, iy], sigma[iz, iy - 1]) * dz[iz] * depth_m / dy_m
                matrix[row, row] += g
                matrix[row, node(iz, iy - 1)] -= g
            if iy + 1 < ny:
                g = _harmonic(sigma[iz, iy], sigma[iz, iy + 1]) * dz[iz] * depth_m / dy_m
                matrix[row, row] += g
                matrix[row, node(iz, iy + 1)] -= g
            if iz > 0:
                area = dy_m * depth_m
                resistance_area = 0.5 * dz[iz] / sigma[iz, iy] + contacts[iz - 1] + 0.5 * dz[iz - 1] / sigma[iz - 1, iy]
                g = area / max(resistance_area, 1.0e-30)
                matrix[row, row] += g
                matrix[row, node(iz - 1, iy)] -= g
            if iz + 1 < nz:
                area = dy_m * depth_m
                resistance_area = 0.5 * dz[iz] / sigma[iz, iy] + contacts[iz] + 0.5 * dz[iz + 1] / sigma[iz + 1, iy]
                g = area / max(resistance_area, 1.0e-30)
                matrix[row, row] += g
                matrix[row, node(iz + 1, iy)] -= g

            for boundary, face_index, distance, area in (
                ("top", iy, 0.5 * dz[iz], dy_m * depth_m),
                ("bottom", iy, 0.5 * dz[iz], dy_m * depth_m),
                ("left", iz, 0.5 * dy_m, dz[iz] * depth_m),
                ("right", iz, 0.5 * dy_m, dz[iz] * depth_m),
            ):
                on_face = (boundary == "top" and iz == 0) or (boundary == "bottom" and iz == nz - 1) or (boundary == "left" and iy == 0) or (boundary == "right" and iy == ny - 1)
                segment = face_map.get((boundary, face_index)) if on_face else None
                if segment is not None:
                    add_dirichlet(row, sigma[iz, iy] * area / max(distance, 1.0e-30), segment.voltage_v, segment.name)

    if not segments:
        raise ValueError("At least one electrode is required")
    potential = np.asarray(spsolve(matrix.tocsr(), rhs), dtype=float).reshape(nz, ny)
    currents: dict[str, float] = {}
    for name, entries in terminal_contributions.items():
        currents[name] = float(sum(g * (voltage - potential.reshape(-1)[row]) for row, g, voltage in entries))
    current_balance = abs(sum(currents.values())) / max(sum(abs(value) for value in currents.values()), 1.0e-30)
    return {
        "potential_v": potential,
        "terminal_currents_a": currents,
        "current_balance_error": float(current_balance),
        "finite": bool(np.isfinite(potential).all() and all(np.isfinite(value) for value in currents.values())),
        "segmented_electrodes": True,
        "insulating_unassigned_boundaries": True,
    }


def uniform_series_current(
    sigma_by_layer_s_m: np.ndarray,
    dz_m: np.ndarray,
    voltage_v: float,
    area_m2: float,
    contact_resistance_ohm_m2: np.ndarray | None = None,
) -> float:
    sigma = np.asarray(sigma_by_layer_s_m, dtype=float)
    dz = np.asarray(dz_m, dtype=float)
    contacts = np.zeros(max(dz.size - 1, 0)) if contact_resistance_ohm_m2 is None else np.asarray(contact_resistance_ohm_m2, dtype=float)
    resistance_area = float(np.sum(dz / sigma) + np.sum(contacts))
    return float(voltage_v * area_m2 / max(resistance_area, 1.0e-30))
