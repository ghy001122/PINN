"""Gamma_sub x T_sw profile-likelihood landscape audit.

This script scans a two-dimensional candidate grid on the frozen triangle
benchmark and extracts profile-likelihood and ridge diagnostics. It is synthetic
numerical digital-twin benchmark evidence only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.gamma_sub_validation_common import (
        display_path,
        ensure_frozen_inputs,
        finite_row,
        load_sparse_obs,
        load_target,
        load_yaml,
        observation_times,
        port_series,
        resolve,
        simulate_with_overrides,
        write_csv,
        write_json,
    )
except ModuleNotFoundError:  # pragma: no cover
    from gamma_sub_validation_common import (  # type: ignore
        display_path,
        ensure_frozen_inputs,
        finite_row,
        load_sparse_obs,
        load_target,
        load_yaml,
        observation_times,
        port_series,
        resolve,
        simulate_with_overrides,
        write_csv,
        write_json,
    )

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_profile_likelihood.yaml")
GRID_FIELDS = ["gamma_sub", "T_sw_offset_K", "objective", "G_loss", "I_loss", "finite_result", "is_true_pair"]
PROFILE_FIELDS = ["profile_type", "fixed_value", "profiled_value", "min_objective", "G_loss", "I_loss"]


def _loss(pred_g: np.ndarray, pred_i: np.ndarray, target_g: np.ndarray, target_i: np.ndarray, weights: dict[str, Any]) -> dict[str, float]:
    denom_g = max(float(np.sqrt(np.mean(target_g**2))), 1.0e-30)
    denom_i = max(float(np.sqrt(np.mean(target_i**2))), 1.0e-30)
    g_loss = float(np.sqrt(np.mean((pred_g - target_g) ** 2)) / denom_g) ** 2
    i_loss = float(np.sqrt(np.mean((pred_i - target_i) ** 2)) / denom_i) ** 2
    objective = float(weights.get("w_g", 1.0)) * g_loss + float(weights.get("w_i", 0.5)) * i_loss
    return {"objective": float(objective), "G_loss": float(g_loss), "I_loss": float(i_loss)}


def _profile_rows(grid_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gamma in sorted({float(row["gamma_sub"]) for row in grid_rows}):
        selected = [row for row in grid_rows if float(row["gamma_sub"]) == gamma]
        best = min(selected, key=lambda row: float(row["objective"]))
        rows.append({"profile_type": "min_over_T_sw_for_gamma", "fixed_value": gamma, "profiled_value": float(best["T_sw_offset_K"]), "min_objective": float(best["objective"]), "G_loss": float(best["G_loss"]), "I_loss": float(best["I_loss"])})
    for offset in sorted({float(row["T_sw_offset_K"]) for row in grid_rows}):
        selected = [row for row in grid_rows if float(row["T_sw_offset_K"]) == offset]
        best = min(selected, key=lambda row: float(row["objective"]))
        rows.append({"profile_type": "min_over_gamma_for_T_sw", "fixed_value": offset, "profiled_value": float(best["gamma_sub"]), "min_objective": float(best["objective"]), "G_loss": float(best["G_loss"]), "I_loss": float(best["I_loss"])})
    return rows


def _ridge_metrics(grid_rows: list[dict[str, Any]], true_gamma: float) -> dict[str, Any]:
    best = min(grid_rows, key=lambda row: float(row["objective"]))
    objectives = np.asarray([float(row["objective"]) for row in grid_rows], dtype=float)
    obj_min = float(np.min(objectives))
    obj_span = max(float(np.max(objectives) - obj_min), 1.0e-30)
    cutoff = obj_min + 0.25 * obj_span
    low = [row for row in grid_rows if float(row["objective"]) <= cutoff]
    if len(low) < 3:
        low = sorted(grid_rows, key=lambda row: float(row["objective"]))[: min(5, len(grid_rows))]
    x = np.asarray([[np.log(float(row["gamma_sub"])), float(row["T_sw_offset_K"])] for row in low], dtype=float)
    weights = np.asarray([np.exp(-(float(row["objective"]) - obj_min) / max(obj_span, 1.0e-30)) for row in low], dtype=float)
    weights = weights / max(float(np.sum(weights)), 1.0e-30)
    center = np.sum(x * weights[:, None], axis=0)
    cov = (x - center).T @ ((x - center) * weights[:, None]) + 1.0e-12 * np.eye(2)
    curvature = np.linalg.pinv(cov)
    eigvals = np.linalg.eigvalsh(curvature)
    condition = float(np.max(eigvals) / max(float(np.min(eigvals)), 1.0e-30))
    coupling = float(curvature[0, 1] / max(np.sqrt(abs(curvature[0, 0] * curvature[1, 1])), 1.0e-30))
    profile = [row for row in _profile_rows(grid_rows) if row["profile_type"] == "min_over_T_sw_for_gamma"]
    gam = np.asarray([np.log(float(row["fixed_value"]) / true_gamma) for row in profile], dtype=float)
    tsw = np.asarray([float(row["profiled_value"]) for row in profile], dtype=float)
    slope = float(np.polyfit(gam, tsw, 1)[0]) if len(profile) >= 2 and np.std(gam) > 0 else 0.0
    sorted_rows = sorted(grid_rows, key=lambda row: float(row["objective"]))
    true_rows = [row for row in sorted_rows if bool(row["is_true_pair"])]
    true_rank = sorted_rows.index(true_rows[0]) + 1 if true_rows else None
    return {
        "best_pair": {"gamma_sub": float(best["gamma_sub"]), "T_sw_offset_K": float(best["T_sw_offset_K"]), "objective": float(best["objective"])},
        "true_pair_rank": true_rank,
        "ridge_slope_Tsw_offset_per_log_gamma": slope,
        "fisher_like_curvature_matrix": curvature.tolist(),
        "condition_number": condition,
        "gamma_sub_T_sw_coupling_coefficient": coupling,
        "objective_has_elongated_ridge": bool(condition > 10.0),
        "gamma_sub_and_T_sw_locally_confounded": bool(abs(coupling) > 0.5 or condition > 10.0),
        "low_objective_point_count": len(low),
    }


def run_tsw_profile_likelihood(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = resolve(config_path)
    config = load_yaml(config_path)
    target_path = resolve(config["target_npz"])
    obs_path = resolve(config["sparse_obs_npz"])
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    true_gamma = float(target["params"]["gamma_sub"])
    true_tsw = float(target["params"]["T_sw"])
    obs_time = observation_times(np.asarray(target["t"], dtype=float), int(config["inverse"].get("observation_count", 32)))
    target_g, target_i = port_series(target, obs_time)
    rows: list[dict[str, Any]] = []
    gamma_grid = [float(value) for value in config["inverse"]["gamma_grid"]]
    offset_grid = [float(value) for value in config["inverse"]["T_sw_offset_grid_K"]]
    for gamma in gamma_grid:
        for offset in offset_grid:
            gt = simulate_with_overrides(dict(target["params"]), config["simulation"], gamma_sub=gamma, t_max=float(target["t"][-1]), param_overrides={"T_sw": true_tsw + offset})
            pred_g, pred_i = port_series(gt, obs_time)
            loss = _loss(pred_g, pred_i, target_g, target_i, config["loss"])
            row = {"gamma_sub": gamma, "T_sw_offset_K": offset, **loss, "is_true_pair": bool(abs(gamma - true_gamma) <= 1.0 and abs(offset) <= 1.0e-12)}
            row["finite_result"] = finite_row(row, ["gamma_sub", "T_sw_offset_K", "objective", "G_loss", "I_loss"])
            rows.append(row)
    rows = sorted(rows, key=lambda row: (float(row["gamma_sub"]), float(row["T_sw_offset_K"])))
    profiles = _profile_rows(rows)
    ridge = _ridge_metrics(rows, true_gamma)
    after = ensure_frozen_inputs(target_path, obs_path)
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin profile likelihood; not experimental data.",
        "scope": "Two-dimensional gamma_sub x T_sw objective landscape using port G/I objective on the frozen triangle benchmark.",
        "config_path": display_path(config_path),
        "target_npz": display_path(target_path),
        "sparse_obs_npz": display_path(obs_path),
        "true_gamma_sub": true_gamma,
        "true_T_sw": true_tsw,
        "num_grid_points": len(rows),
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "whether_objective_has_elongated_ridge": ridge["objective_has_elongated_ridge"],
        "whether_gamma_sub_and_T_sw_are_locally_confounded": ridge["gamma_sub_and_T_sw_locally_confounded"],
        "condition_number": ridge["condition_number"],
        "ridge_metrics": ridge,
        "interpretation_for_manuscript": "The port objective contains a gamma_sub/T_sw valley, so gamma_sub recovery must be claimed as conditional on fixed or tightly bounded switching-temperature prior.",
        "forbidden_overclaim": "Do not claim unconstrained joint identifiability of gamma_sub and T_sw from sparse ports.",
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": before == after,
        "outputs": {"summary_json": config["summary_json"], "grid_csv": config["grid_csv"], "profiles_csv": config["profiles_csv"]},
    }
    write_json(config["summary_json"], summary)
    write_csv(config["grid_csv"], rows, GRID_FIELDS)
    write_csv(config["profiles_csv"], profiles, PROFILE_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_tsw_profile_likelihood(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "grid_csv": summary["outputs"]["grid_csv"], "profiles_csv": summary["outputs"]["profiles_csv"], "condition_number": summary["condition_number"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
