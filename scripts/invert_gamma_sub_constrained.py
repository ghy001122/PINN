"""Constrained gamma_sub inversion under literature-guided confounder priors.

This script treats gamma_sub as the only primary inverse parameter. Switching,
conductivity, and defect-migration parameters are fixed at the frozen Ground
Truth v1.1 values except for bounded confounder stress targets used in the
prior-width sweep.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
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
    from scripts.invert_gamma_sub_v0 import _heat_residual_loss
    from scripts.scan_gamma_sub_identifiability import _load_target, _relative_rmse, simulate_for_gamma
except ModuleNotFoundError:  # pragma: no cover - script-dir fallback.
    from invert_gamma_sub_v0 import _heat_residual_loss  # type: ignore
    from scan_gamma_sub_identifiability import _load_target, _relative_rmse, simulate_for_gamma  # type: ignore


DEFAULT_CONFIG = Path("configs/gamma_sub_constrained_inversion.yaml")
REQUIRED_TARGET_KEYS = ("x", "t", "V", "I", "G", "T", "params_json")
REQUIRED_OBS_KEYS = ("t", "V", "I", "G")


@dataclass(frozen=True)
class CandidateRun:
    gamma_sub: float
    gt: dict[str, Any]
    g_obs: np.ndarray
    i_obs: np.ndarray
    heat_residual: float


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _ensure_inputs(target_path: Path, obs_path: Path) -> None:
    missing = [str(path) for path in (target_path, obs_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing frozen Ground Truth input(s). This script will not regenerate frozen GT: "
            + ", ".join(missing)
        )
    with np.load(target_path) as data:
        missing_keys = [key for key in REQUIRED_TARGET_KEYS if key not in data.files]
    if missing_keys:
        raise KeyError(f"Frozen target is missing required keys: {missing_keys}")
    with np.load(obs_path) as data:
        missing_keys = [key for key in REQUIRED_OBS_KEYS if key not in data.files]
    if missing_keys:
        raise KeyError(f"Sparse observation file is missing required keys: {missing_keys}")


def _load_sparse_obs(path: Path) -> dict[str, Any]:
    with np.load(path) as data:
        return {
            "path": _display_path(path),
            "keys": list(data.files),
            "t": np.asarray(data["t"], dtype=float),
            "V": np.asarray(data["V"], dtype=float),
            "I": np.asarray(data["I"], dtype=float),
            "G": np.asarray(data["G"], dtype=float),
            "noise_level": float(data["noise_level"]) if "noise_level" in data.files else None,
        }


def _series_at(time: np.ndarray, series_time: np.ndarray, values: np.ndarray) -> np.ndarray:
    return np.interp(np.asarray(time, dtype=float), np.asarray(series_time, dtype=float), np.asarray(values, dtype=float))


def _sample_port(gt: dict[str, Any], obs_time: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    time = np.asarray(gt["t"], dtype=float)
    return _series_at(obs_time, time, gt["G"]), _series_at(obs_time, time, gt["I"])


def _make_noisy(values: np.ndarray, noise_level: float, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if noise_level <= 0.0:
        return values.copy()
    scale = max(float(np.max(np.abs(values))), 1.0e-30)
    return values + float(noise_level) * scale * rng.standard_normal(values.shape)


def _candidate_values(config: dict[str, Any], true_gamma: float) -> list[float]:
    inverse = config["inverse"]
    candidates = [float(value) for value in inverse.get("gamma_candidates", [])]
    if not candidates:
        lo, hi, count = inverse.get("gamma_range", [1.5e8, 1.0e9, 15])
        candidates = np.geomspace(float(lo), float(hi), int(count)).tolist()
    candidates.append(float(true_gamma))
    return sorted({round(float(value), 9) for value in candidates})


def _scale_layer_sigma_on(params: dict[str, Any], ratio: float) -> None:
    for key in ("nb_oxide_sigma_on0", "v2o5_sigma_on0"):
        if key in params:
            params[key] = float(params[key]) * ratio


def _apply_confounder(
    params: dict[str, Any],
    name: str,
    spec: dict[str, Any],
    prior_width: float,
    direction: int,
) -> tuple[dict[str, Any], float]:
    updated = dict(params)
    base = float(params[name])
    if spec["mode"] == "additive":
        delta = float(direction) * float(prior_width) * float(spec["max_delta"])
        updated[name] = base + delta
        return updated, delta
    if spec["mode"] == "relative":
        fraction = float(direction) * float(prior_width) * float(spec["max_fraction"])
        updated[name] = base * (1.0 + fraction)
        if name == "sigma_on0":
            _scale_layer_sigma_on(updated, 1.0 + fraction)
        return updated, fraction
    raise ValueError(f"Unsupported confounder mode for {name}: {spec['mode']}")


def _simulate_with_params(
    params: dict[str, Any],
    sim: dict[str, Any],
    *,
    gamma_sub: float,
    t_max: float,
) -> dict[str, Any]:
    run_params = dict(params)
    run_params["gamma_sub"] = float(gamma_sub)
    return simulate_for_gamma(
        float(gamma_sub),
        run_params,
        nx=int(sim["nx"]),
        nt=int(sim["nt"]),
        protocol=str(sim.get("protocol", "triangle")),
        t_max=t_max,
        rtol=float(sim.get("rtol", 1.0e-5)),
        atol=float(sim.get("atol", 1.0e-7)),
        method=str(sim.get("method", "Radau")),
    )


def _precompute_candidates(
    target: dict[str, Any],
    obs_time: np.ndarray,
    config: dict[str, Any],
) -> list[CandidateRun]:
    sim = config["simulation"]
    params = dict(target["params"])
    t_max = float(target["t"][-1])
    candidates = []
    for gamma_sub in _candidate_values(config, float(params["gamma_sub"])):
        gt = _simulate_with_params(params, sim, gamma_sub=gamma_sub, t_max=t_max)
        g_obs, i_obs = _sample_port(gt, obs_time)
        candidates.append(
            CandidateRun(
                gamma_sub=float(gamma_sub),
                gt=gt,
                g_obs=g_obs,
                i_obs=i_obs,
                heat_residual=float(_heat_residual_loss(gt, params, float(gamma_sub))),
            )
        )
    return candidates


def _start_windows(config: dict[str, Any]) -> list[tuple[float, float, float]]:
    inverse = config["inverse"]
    radius = float(inverse.get("start_window_log_radius", 0.75))
    windows = []
    for initial in inverse.get("multistart_initials", [4.5e8]):
        initial = float(initial)
        windows.append((initial, math.exp(math.log(initial) - radius), math.exp(math.log(initial) + radius)))
    return windows


def _estimate_gamma(
    target_g: np.ndarray,
    target_i: np.ndarray,
    candidates: list[CandidateRun],
    config: dict[str, Any],
) -> dict[str, Any]:
    weights = config["loss"]
    rows = []
    for candidate in candidates:
        g_loss = _relative_rmse(candidate.g_obs, target_g) ** 2
        i_loss = _relative_rmse(candidate.i_obs, target_i) ** 2
        total = (
            float(weights.get("w_g", 1.0)) * g_loss
            + float(weights.get("w_i", 0.5)) * i_loss
            + float(weights.get("w_heat", 0.01)) * candidate.heat_residual
        )
        rows.append(
            {
                "gamma_sub": candidate.gamma_sub,
                "objective_value": float(total),
                "G_loss": float(g_loss),
                "I_loss": float(i_loss),
                "heat_residual_loss": float(candidate.heat_residual),
            }
        )

    windows = _start_windows(config)
    start_results = []
    for initial, lo, hi in windows:
        in_window = [row for row in rows if lo <= float(row["gamma_sub"]) <= hi]
        if not in_window:
            in_window = rows
        best = min(in_window, key=lambda row: float(row["objective_value"]))
        start_results.append({"initial_gamma_sub": initial, **best})
    best = min(start_results, key=lambda row: float(row["objective_value"]))
    return {
        "estimated_gamma_sub": float(best["gamma_sub"]),
        "objective_value": float(best["objective_value"]),
        "G_loss": float(best["G_loss"]),
        "I_loss": float(best["I_loss"]),
        "heat_residual_loss": float(best["heat_residual_loss"]),
        "num_multistarts": len(windows),
        "multistart_results": start_results,
        "candidate_profile": rows,
    }


def _case_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    sweep = config["prior_width_sweep"]
    widths = [float(value) for value in sweep.get("widths", [0.0])]
    confounders = sweep.get("confounders", {})
    cases: list[dict[str, Any]] = [
        {
            "case_name": "nominal",
            "prior_width": 0.0,
            "confounder": "none",
            "direction": 0,
            "perturbation": 0.0,
            "params": None,
        }
    ]
    for width in widths:
        if width <= 0.0:
            continue
        for name, spec in confounders.items():
            for direction in (-1, 1):
                cases.append(
                    {
                        "case_name": f"{name}_{'minus' if direction < 0 else 'plus'}_{width:g}",
                        "prior_width": width,
                        "confounder": name,
                        "confounder_spec": spec,
                        "direction": direction,
                    }
                )
    return cases


def _target_case(
    case: dict[str, Any],
    base_target: dict[str, Any],
    obs_time: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    true_gamma = float(base_target["params"]["gamma_sub"])
    if case["confounder"] == "none":
        g_obs = _series_at(obs_time, np.asarray(base_target["t"], dtype=float), np.asarray(base_target["G"], dtype=float))
        i_obs = _series_at(obs_time, np.asarray(base_target["t"], dtype=float), np.asarray(base_target["I"], dtype=float))
        return {**case, "target_g_clean": g_obs, "target_i_clean": i_obs, "target_params": dict(base_target["params"])}

    params, perturbation = _apply_confounder(
        dict(base_target["params"]),
        str(case["confounder"]),
        dict(case["confounder_spec"]),
        float(case["prior_width"]),
        int(case["direction"]),
    )
    gt = _simulate_with_params(params, config["simulation"], gamma_sub=true_gamma, t_max=float(base_target["t"][-1]))
    g_obs, i_obs = _sample_port(gt, obs_time)
    return {
        **case,
        "perturbation": float(perturbation),
        "target_g_clean": g_obs,
        "target_i_clean": i_obs,
        "target_params": params,
    }


def _summarize_prior_width(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    by_width: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_width.setdefault(str(row["prior_width"]), []).append(row)
    out = []
    unstable_threshold: float | None = None
    for width_text, width_rows in sorted(by_width.items(), key=lambda item: float(item[0])):
        max_error = max(float(row["relative_error"]) for row in width_rows)
        worst = max(width_rows, key=lambda row: float(row["relative_error"]))
        stable = bool(max_error <= threshold)
        if not stable and unstable_threshold is None:
            unstable_threshold = float(width_text)
        out.append(
            {
                "prior_width": float(width_text),
                "max_relative_error": max_error,
                "worst_confounder": worst["worst_confounder"],
                "stable_under_threshold": stable,
            }
        )
    return {"rows": out, "unstable_prior_width_threshold": unstable_threshold}


def _write_prior_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_name",
        "noise_level",
        "prior_width",
        "worst_confounder",
        "direction",
        "perturbation",
        "true_gamma_sub",
        "estimated_gamma_sub",
        "relative_error",
        "success_flag",
        "objective_value",
        "G_loss",
        "I_loss",
        "heat_residual_loss",
        "num_multistarts",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def run_constrained_inversion(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = _resolve(config_path)
    config = _load_yaml(config_path)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    summary_path = _resolve(config["summary_json"])
    csv_path = _resolve(config["prior_width_csv"])
    _ensure_inputs(target_path, obs_path)

    target = _load_target(target_path)
    obs = _load_sparse_obs(obs_path)
    obs_time = np.asarray(obs["t"], dtype=float)
    true_gamma = float(target["params"]["gamma_sub"])
    success_threshold = float(config["inverse"].get("success_relative_error_threshold", 0.15))

    candidates = _precompute_candidates(target, obs_time, config)
    noise_cfg = config.get("noise", {})
    noise_levels = [float(value) for value in noise_cfg.get("levels", [0.0])]
    seed = int(noise_cfg.get("seed", 2026))

    rows: list[dict[str, Any]] = []
    for case_index, case in enumerate(_case_specs(config)):
        target_case = _target_case(case, target, obs_time, config)
        for noise_index, noise_level in enumerate(noise_levels):
            rng = np.random.default_rng(seed + 1000 * case_index + noise_index)
            noisy_g = _make_noisy(target_case["target_g_clean"], noise_level, rng)
            noisy_i = _make_noisy(target_case["target_i_clean"], noise_level, rng)
            estimate = _estimate_gamma(noisy_g, noisy_i, candidates, config)
            relative_error = abs(float(estimate["estimated_gamma_sub"]) - true_gamma) / true_gamma
            rows.append(
                {
                    "case_name": target_case["case_name"],
                    "noise_level": float(noise_level),
                    "prior_width": float(target_case["prior_width"]),
                    "worst_confounder": target_case["confounder"],
                    "direction": int(target_case["direction"]),
                    "perturbation": float(target_case.get("perturbation", 0.0)),
                    "true_gamma_sub": true_gamma,
                    "estimated_gamma_sub": float(estimate["estimated_gamma_sub"]),
                    "relative_error": float(relative_error),
                    "success_flag": bool(relative_error <= success_threshold),
                    "objective_value": float(estimate["objective_value"]),
                    "G_loss": float(estimate["G_loss"]),
                    "I_loss": float(estimate["I_loss"]),
                    "heat_residual_loss": float(estimate["heat_residual_loss"]),
                    "num_multistarts": int(estimate["num_multistarts"]),
                }
            )

    nominal_rows = [row for row in rows if row["worst_confounder"] == "none"]
    clean_nominal = next(row for row in nominal_rows if row["noise_level"] == min(noise_levels))
    max_row = max(rows, key=lambda row: float(row["relative_error"]))
    confounder_rows = [row for row in rows if row["worst_confounder"] != "none"]
    dangerous = max(confounder_rows, key=lambda row: float(row["relative_error"])) if confounder_rows else max_row
    prior_summary = _summarize_prior_width(rows, success_threshold)

    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin benchmark; not measured experimental data.",
        "scope": "Constrained reduced inverse target: gamma_sub only. This does not prove port-only full hidden-field recovery.",
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "target_keys": target["keys"],
        "sparse_obs_keys": obs["keys"],
        "true_gamma_sub": true_gamma,
        "estimated_gamma_sub": float(clean_nominal["estimated_gamma_sub"]),
        "relative_error": float(clean_nominal["relative_error"]),
        "noise_level": float(clean_nominal["noise_level"]),
        "prior_width": float(clean_nominal["prior_width"]),
        "worst_confounder": dangerous["worst_confounder"],
        "success_flag": bool(clean_nominal["success_flag"]),
        "objective_value": float(clean_nominal["objective_value"]),
        "num_multistarts": int(clean_nominal["num_multistarts"]),
        "max_relative_error": float(max_row["relative_error"]),
        "max_relative_error_case": max_row,
        "most_dangerous_confounder": dangerous["worst_confounder"],
        "prior_width_summary": prior_summary,
        "fixed_microphysics": config.get("frozen_microphysics", []),
        "bounded_confounders": list(config["prior_width_sweep"].get("confounders", {}).keys()),
        "loss": config.get("loss", {}),
        "rows": rows,
        "outputs": {
            "summary_json": _display_path(summary_path),
            "prior_width_csv": _display_path(csv_path),
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_prior_csv(csv_path, rows)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_constrained_inversion(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "prior_width_csv": summary["outputs"]["prior_width_csv"],
                "max_relative_error": summary["max_relative_error"],
                "most_dangerous_confounder": summary["most_dangerous_confounder"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
