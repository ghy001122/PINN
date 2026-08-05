"""Pure B1/B2 observation utilities; Batch 1 does not execute B2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid


def area_weighted_rms(field: np.ndarray, area_m2: np.ndarray | float) -> float:
    values = np.asarray(field, dtype=float)
    weights = np.broadcast_to(np.asarray(area_m2, dtype=float), values.shape)
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise ValueError("field and area weights must be finite; weights must be positive")
    return float(np.sqrt(np.sum(weights * values**2) / np.sum(weights)))


def y_average_by_x(field: np.ndarray, area_m2: np.ndarray | float) -> np.ndarray:
    values = np.asarray(field, dtype=float)
    weights = np.broadcast_to(np.asarray(area_m2, dtype=float), values.shape)
    if values.ndim != 2 or values.shape != weights.shape:
        raise ValueError("field must be two-dimensional and match area weights")
    average = np.sum(weights * values, axis=0) / np.sum(weights, axis=0)
    return np.broadcast_to(average[None, :], values.shape).copy()


def two_dimensional_response_ratio(
    response_K: np.ndarray, area_m2: np.ndarray | float
) -> float:
    denominator = area_weighted_rms(response_K, area_m2)
    if denominator <= 0.0:
        return 0.0
    nonuniform = np.asarray(response_K) - y_average_by_x(response_K, area_m2)
    return area_weighted_rms(nonuniform, area_m2) / denominator


def hotspot_centroid_m(
    grid: GeoPhaseGrid,
    temperature_K: np.ndarray,
    ambient_temperature_K: float,
) -> tuple[float, float]:
    temperature = np.asarray(temperature_K, dtype=float)
    if temperature.shape != grid.shape or not np.isfinite(temperature).all():
        raise ValueError("temperature must be finite and match the grid")
    x, y = np.meshgrid(grid.x_centers_m, grid.y_centers_m)
    weights = np.maximum(temperature - ambient_temperature_K, 0.0) ** 2
    weights *= grid.cell_area_m2
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError("hotspot centroid is undefined without positive temperature rise")
    return float(np.sum(weights * x) / total), float(np.sum(weights * y) / total)


def bilinear_observation(
    grid: GeoPhaseGrid,
    field: np.ndarray,
    x_m: float,
    y_m: float,
) -> float:
    values = np.asarray(field, dtype=float)
    if values.shape != grid.shape or not np.isfinite(values).all():
        raise ValueError("field must be finite and match the grid")
    x = np.asarray(grid.x_centers_m, dtype=float)
    y = np.asarray(grid.y_centers_m, dtype=float)
    if not x[0] <= x_m <= x[-1] or not y[0] <= y_m <= y[-1]:
        raise ValueError("sensor coordinate lies outside the cell-centre domain")
    ix1 = min(max(int(np.searchsorted(x, x_m)), 1), x.size - 1)
    iy1 = min(max(int(np.searchsorted(y, y_m)), 1), y.size - 1)
    ix0, iy0 = ix1 - 1, iy1 - 1
    tx = (x_m - x[ix0]) / (x[ix1] - x[ix0])
    ty = (y_m - y[iy0]) / (y[iy1] - y[iy0])
    return float(
        (1 - tx) * (1 - ty) * values[iy0, ix0]
        + tx * (1 - ty) * values[iy0, ix1]
        + (1 - tx) * ty * values[iy1, ix0]
        + tx * ty * values[iy1, ix1]
    )


@dataclass(frozen=True)
class SensorSelection:
    coordinates_m: tuple[tuple[float, float], ...]
    augmented_jacobian: np.ndarray


def select_sensor_blocks(
    o1_jacobian: np.ndarray,
    candidate_blocks: Mapping[tuple[float, float], np.ndarray],
    *,
    count: int,
) -> SensorSelection:
    """Greedily append complete ten-row sensor blocks using the frozen rule."""

    current = np.asarray(o1_jacobian, dtype=float)
    if current.ndim != 2 or current.shape[1] != 2:
        raise ValueError("O1 Jacobian must have two parameter columns")
    remaining = {key: np.asarray(value, dtype=float) for key, value in candidate_blocks.items()}
    if count < 0 or count > len(remaining):
        raise ValueError("requested sensor count is invalid")
    selected: list[tuple[float, float]] = []
    for _ in range(count):
        scored: list[tuple[float, float, tuple[float, float], np.ndarray]] = []
        for coordinate, block in remaining.items():
            if block.shape != (10, 2):
                raise ValueError("every sensor must contribute one 10x2 block")
            augmented = np.vstack((current, block))
            fisher = augmented.T @ augmented + 1.0e-12 * np.eye(2)
            sign, logdet = np.linalg.slogdet(fisher)
            singular = np.linalg.svd(augmented, compute_uv=False)
            sigma_min = float(singular[-1]) if singular.size == 2 else 0.0
            scored.append((float(logdet if sign > 0 else -np.inf), sigma_min, coordinate, augmented))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2][0], item[2][1]))
        _, _, coordinate, current = scored[0]
        selected.append(coordinate)
        remaining.pop(coordinate)
    return SensorSelection(tuple(selected), current)


def effective_rank_two_gate(whitened_jacobian: np.ndarray) -> dict[str, float | int | bool]:
    values = np.linalg.svd(np.asarray(whitened_jacobian, dtype=float), compute_uv=False)
    sigma1 = float(values[0]) if values.size else 0.0
    sigma2 = float(values[1]) if values.size > 1 else 0.0
    ratio = sigma2 / sigma1 if sigma1 > 0.0 else 0.0
    rank = int(np.sum(values >= 1.0))
    return {
        "effective_rank": rank,
        "sigma1": sigma1,
        "sigma2": sigma2,
        "sigma2_over_sigma1": ratio,
        "pass": bool(rank == 2 and ratio >= 1.0e-2 and sigma2 >= 1.0),
    }


def minimum_passing_tier(
    tier_jacobians: Mapping[str, np.ndarray],
) -> str | None:
    """Evaluate O1 then O2 then O3; O4 can never be the sole passing tier."""

    for name in ("O1", "O2", "O3"):
        if name not in tier_jacobians:
            raise ValueError(f"missing required observation tier {name}")
        if bool(effective_rank_two_gate(tier_jacobians[name])["pass"]):
            return name
    return None
