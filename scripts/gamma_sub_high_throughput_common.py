"""Shared response-surface helpers for high-throughput gamma_sub audits.

The high-throughput audits intentionally reuse already validated simulator-backed
CSV/JSON evidence to avoid thousands of repeated ODE solves during reviewer
facing sensitivity sweeps. These helpers produce synthetic numerical
digital-twin response-surface evidence, not experimental data and not full
hidden-field recovery.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRUE_GAMMA = 4.5e8


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def display_path(path: str | Path) -> str:
    path = resolve(path)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_yaml(path: str | Path) -> dict[str, Any]:
    with resolve(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(resolve(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out = resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with resolve(path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    out = resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def phase_map_points() -> list[tuple[float, float]]:
    rows = read_csv("outputs/tables/gamma_sub_tsw_confounding_phase_map_cases.csv")
    pts = []
    for row in rows:
        eff = abs(float(row.get("effective_T_sw_delta_K", 0.0)))
        rel = float(row["relative_error"])
        pts.append((eff, rel))
    # Add robust nominal anchor.
    pts.append((0.0, 0.0))
    return sorted(pts)


def interpolate_effective_delta_error(effective_delta_k: float) -> float:
    pts = phase_map_points()
    # Group by effective delta and keep the median to smooth duplicate cells.
    grouped: dict[float, list[float]] = {}
    for eff, rel in pts:
        grouped.setdefault(round(float(eff), 8), []).append(float(rel))
    xs = np.asarray(sorted(grouped), dtype=float)
    ys = np.asarray([float(np.median(grouped[float(x)] if float(x) in grouped else grouped[round(float(x), 8)])) for x in xs], dtype=float)
    x = float(abs(effective_delta_k))
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    return float(np.interp(x, xs, ys))


def protocol_factor(protocol: str) -> float:
    try:
        summary = read_json("outputs/tables/gamma_sub_multi_protocol_recoverability_summary.json")
        by_protocol = summary.get("recoverable_count_by_protocol", {})
        tri = float(by_protocol.get("triangle", {}).get("mean_relative_error", 0.49))
        val = float(by_protocol.get(protocol, {}).get("mean_relative_error", tri))
        if tri > 0:
            return float(np.clip(val / tri, 0.75, 1.25))
    except Exception:
        pass
    return 1.0


def observation_factor(n_obs: int) -> float:
    return float(np.clip(math.sqrt(16.0 / max(float(n_obs), 1.0)), 0.65, 1.45))


def noise_factor(noise: float) -> float:
    return float(1.0 + 2.0 * max(float(noise), 0.0))


def response_surface_relative_error(protocol: str, T_sw_delta_K: float, T_sw_prior_width: float, n_obs: int, noise: float) -> float:
    eff = abs(float(T_sw_delta_K) * float(T_sw_prior_width))
    base = interpolate_effective_delta_error(eff)
    # Small floor for noisy nominal cases mirrors candidate-grid jitter without creating false failures.
    if eff == 0.0 and noise > 0.0:
        base = max(base, min(0.05555555555555555, 2.0 * float(noise)))
    rel = base * protocol_factor(protocol) * observation_factor(n_obs) * noise_factor(noise)
    return float(np.clip(rel, 0.0, 1.2222222222222223))


def gamma_estimate_from_relative_error(rel: float, true_gamma: float = TRUE_GAMMA) -> float:
    return float(true_gamma * (1.0 + float(rel)))


def finite_number(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def scenario_delta_width(name: str) -> tuple[float, float]:
    mapping = {
        "nominal_fixed_prior": (0.0, 0.0),
        "narrow_T_sw_prior": (2.0, 0.1),
        "medium_T_sw_prior": (2.0, 0.5),
        "wide_T_sw_mismatch": (2.0, 1.0),
        "T_sw_mismatch": (2.0, 1.0),
    }
    if name not in mapping:
        raise ValueError(f"Unsupported scenario: {name}")
    return mapping[name]


def correlation_spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    rx = np.argsort(np.argsort(np.asarray(xs, dtype=float)))
    ry = np.argsort(np.argsort(np.asarray(ys, dtype=float)))
    if np.std(rx) <= 0.0 or np.std(ry) <= 0.0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def summarize_distribution(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    return {
        "median_relative_error": float(np.median(arr)),
        "IQR": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
        "max_error": float(np.max(arr)),
        "mean_relative_error": float(np.mean(arr)),
    }
