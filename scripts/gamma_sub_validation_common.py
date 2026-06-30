"""Shared helpers for lightweight gamma_sub validation audits.

These utilities keep the new SCI gap-closing scripts small and reuse the
existing frozen-benchmark simulation and port-objective functions. All callers
must treat the generated results as synthetic numerical digital-twin benchmark
outputs, not experimental data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params
    from scripts.invert_gamma_sub_v0 import _heat_residual_loss
    from scripts.scan_gamma_sub_identifiability import _load_target, _relative_rmse
except ModuleNotFoundError:  # pragma: no cover
    from invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params  # type: ignore
    from invert_gamma_sub_v0 import _heat_residual_loss  # type: ignore
    from scan_gamma_sub_identifiability import _load_target, _relative_rmse  # type: ignore

DEFAULT_GAMMA_CANDIDATES = [1.5e8, 2.0e8, 2.75e8, 3.25e8, 3.75e8, 4.0e8, 4.25e8, 4.5e8, 4.75e8, 5.0e8, 5.5e8, 6.5e8, 7.5e8, 9.0e8, 1.0e9]


def resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    return _display_path(path)


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved = resolve(path)
    with resolved.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {resolved}")
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_frozen_inputs(*paths: Path) -> dict[str, str]:
    if len(paths) % 2 == 0:
        for idx in range(0, len(paths), 2):
            _ensure_inputs(paths[idx], paths[idx + 1])
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing frozen input(s): " + ", ".join(missing))
    return {display_path(path): sha256(path) for path in paths}


def load_target(path: str | Path) -> dict[str, Any]:
    return _load_target(resolve(path))


def load_sparse_obs(path: str | Path) -> dict[str, Any]:
    return _load_sparse_obs(resolve(path))


def candidate_values(config: dict[str, Any], true_gamma: float | None = None, *, include_true: bool = True) -> list[float]:
    inverse = config.get("inverse", {})
    values = [float(value) for value in inverse.get("gamma_candidates", DEFAULT_GAMMA_CANDIDATES)]
    if include_true and true_gamma is not None:
        values.append(float(true_gamma))
    return sorted({round(float(value), 9) for value in values})


def observation_times(time: np.ndarray, count: int) -> np.ndarray:
    if count < 2:
        raise ValueError("observation count must be at least 2")
    idx = np.unique(np.linspace(0, len(time) - 1, min(int(count), len(time)), dtype=int))
    return np.asarray(time, dtype=float)[idx]


def make_noisy(values: np.ndarray, noise: float, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if noise <= 0.0:
        return values.copy()
    scale = max(float(np.max(np.abs(values))), 1.0e-30)
    return values + float(noise) * scale * rng.standard_normal(values.shape)


def simulate_with_overrides(
    base_params: dict[str, Any],
    sim_config: dict[str, Any],
    *,
    gamma_sub: float,
    t_max: float,
    param_overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    params = dict(base_params)
    if param_overrides:
        params.update({key: float(value) for key, value in param_overrides.items()})
    params["gamma_sub"] = float(gamma_sub)
    return _simulate_with_params(params, sim_config, gamma_sub=float(gamma_sub), t_max=float(t_max))


def port_series(gt: dict[str, Any], obs_time: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return _sample_port(gt, obs_time)


def objective_components(
    gt: dict[str, Any],
    params_for_heat: dict[str, Any],
    gamma_sub: float,
    obs_time: np.ndarray,
    target_g: np.ndarray,
    target_i: np.ndarray,
    weights: dict[str, Any],
) -> dict[str, float]:
    pred_g, pred_i = port_series(gt, obs_time)
    g_loss = _relative_rmse(pred_g, target_g) ** 2
    i_loss = _relative_rmse(pred_i, target_i) ** 2
    heat_loss = float(_heat_residual_loss(gt, params_for_heat, float(gamma_sub)))
    objective = float(weights.get("w_g", 1.0)) * g_loss + float(weights.get("w_i", 0.5)) * i_loss + float(weights.get("w_heat", 0.01)) * heat_loss
    return {
        "objective": float(objective),
        "G_loss": float(g_loss),
        "I_loss": float(i_loss),
        "heat_residual_loss": float(heat_loss),
    }


def best_gamma_from_candidates(
    *,
    gamma_grid: list[float],
    base_params: dict[str, Any],
    sim_config: dict[str, Any],
    t_max: float,
    obs_time: np.ndarray,
    target_g: np.ndarray,
    target_i: np.ndarray,
    weights: dict[str, Any],
    candidate_overrides: dict[str, float] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for gamma in gamma_grid:
        gt = simulate_with_overrides(base_params, sim_config, gamma_sub=float(gamma), t_max=t_max, param_overrides=candidate_overrides)
        comps = objective_components(gt, base_params, float(gamma), obs_time, target_g, target_i, weights)
        rows.append({"gamma_sub": float(gamma), **comps})
    best = min(rows, key=lambda row: float(row["objective"]))
    return best, rows


def target_from_params(
    *,
    base_params: dict[str, Any],
    sim_config: dict[str, Any],
    true_gamma: float,
    t_max: float,
    target_overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    return simulate_with_overrides(base_params, sim_config, gamma_sub=float(true_gamma), t_max=t_max, param_overrides=target_overrides)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    resolved = resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    resolved = resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def finite_row(row: dict[str, Any], keys: list[str]) -> bool:
    try:
        return bool(np.isfinite([float(row[key]) for key in keys]).all())
    except Exception:
        return False


def relative_error(value: float, truth: float) -> float:
    return float(abs(float(value) - float(truth)) / max(abs(float(truth)), 1.0e-30))
