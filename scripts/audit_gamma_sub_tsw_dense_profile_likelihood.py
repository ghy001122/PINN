"""Dense gamma_sub x T_sw profile-likelihood response-surface audit."""

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

from scripts.gamma_sub_high_throughput_common import load_yaml, read_csv, resolve, write_csv, write_json

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_dense_profile_likelihood.yaml")
GRID_FIELDS = ["gamma_sub", "T_sw_offset_K", "objective", "G_loss", "I_loss", "heat_residual_loss", "finite_result", "source"]
PROFILE_FIELDS = ["profile_type", "fixed_value", "profiled_value", "min_objective", "G_loss", "I_loss"]


def _idw(x: np.ndarray, y: np.ndarray, z: np.ndarray, xi: float, yi: float, power: float) -> float:
    d = np.sqrt((x - xi) ** 2 + (y - yi) ** 2)
    idx = np.argmin(d)
    if d[idx] < 1.0e-12:
        return float(z[idx])
    w = 1.0 / np.maximum(d, 1.0e-12) ** power
    return float(np.sum(w * z) / np.sum(w))


def _profiles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for gamma in sorted({float(row["gamma_sub"]) for row in rows}):
        sel = [row for row in rows if float(row["gamma_sub"]) == gamma]
        best = min(sel, key=lambda row: float(row["objective"]))
        out.append({"profile_type": "min_over_T_sw_for_gamma", "fixed_value": gamma, "profiled_value": float(best["T_sw_offset_K"]), "min_objective": float(best["objective"]), "G_loss": float(best["G_loss"]), "I_loss": float(best["I_loss"])})
    for off in sorted({float(row["T_sw_offset_K"]) for row in rows}):
        sel = [row for row in rows if float(row["T_sw_offset_K"]) == off]
        best = min(sel, key=lambda row: float(row["objective"]))
        out.append({"profile_type": "min_over_gamma_for_T_sw", "fixed_value": off, "profiled_value": float(best["gamma_sub"]), "min_objective": float(best["objective"]), "G_loss": float(best["G_loss"]), "I_loss": float(best["I_loss"])})
    return out


def _metrics(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    objectives = np.asarray([float(row["objective"]) for row in rows], dtype=float)
    best = min(rows, key=lambda row: float(row["objective"]))
    obj_min = float(np.min(objectives))
    true_gamma = float(cfg["truth"]["gamma_sub"])
    true_off = float(cfg["truth"]["T_sw_offset_K"])
    sorted_rows = sorted(rows, key=lambda row: float(row["objective"]))
    true_idx = min(range(len(sorted_rows)), key=lambda i: abs(float(sorted_rows[i]["gamma_sub"]) - true_gamma) + abs(float(sorted_rows[i]["T_sw_offset_K"]) - true_off))
    low_rows = [row for row in rows if float(row["objective"]) <= obj_min * 1.20 + 1.0e-12]
    xy = np.asarray([[np.log(float(row["gamma_sub"])), float(row["T_sw_offset_K"])] for row in low_rows], dtype=float)
    cov = np.cov(xy.T) + 1.0e-12 * np.eye(2) if len(low_rows) > 2 else np.eye(2)
    curvature = np.linalg.pinv(cov)
    eig = np.linalg.eigvalsh(curvature)
    condition = float(np.max(eig) / max(float(np.min(eig)), 1.0e-30))
    profiles = [row for row in _profiles(rows) if row["profile_type"] == "min_over_T_sw_for_gamma"]
    slope = float(np.polyfit([np.log(float(row["fixed_value"]) / true_gamma) for row in profiles], [float(row["profiled_value"]) for row in profiles], 1)[0])
    widths: dict[str, Any] = {}
    for th in cfg["grid"].get("low_objective_thresholds", [0.01, 0.05, 0.1, 0.2]):
        cutoff = obj_min * (1.0 + float(th)) + 1.0e-12
        selected = [row for row in rows if float(row["objective"]) <= cutoff]
        gammas = [float(row["gamma_sub"]) for row in selected]
        offs = [float(row["T_sw_offset_K"]) for row in selected]
        widths[f"threshold_{th:g}"] = {
            "count": len(selected),
            "ridge_width_fraction": float(len(selected) / max(len(rows), 1)),
            "gamma_sub_uncertainty_interval": [float(min(gammas)), float(max(gammas))] if gammas else [],
            "T_sw_uncertainty_interval": [float(min(offs)), float(max(offs))] if offs else [],
        }
    return {
        "best_pair": {"gamma_sub": float(best["gamma_sub"]), "T_sw_offset_K": float(best["T_sw_offset_K"]), "objective": float(best["objective"])},
        "true_pair_rank": int(true_idx + 1),
        "condition_number": condition,
        "curvature_eigenvalues": [float(v) for v in eig],
        "ridge_slope": slope,
        "low_objective_fraction_20pct": float(len(low_rows) / max(len(rows), 1)),
        "ridge_widths": widths,
    }


def run_dense_profile(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    source = read_csv(cfg["source_grid_csv"])
    sx = np.asarray([np.log(float(row["gamma_sub"])) for row in source], dtype=float)
    sy = np.asarray([float(row["T_sw_offset_K"]) for row in source], dtype=float)
    sobj = np.asarray([float(row["objective"]) for row in source], dtype=float)
    sg = np.asarray([float(row["G_loss"]) for row in source], dtype=float)
    si = np.asarray([float(row["I_loss"]) for row in source], dtype=float)
    grid = cfg["grid"]
    gammas = np.geomspace(float(grid["gamma_min"]), float(grid["gamma_max"]), int(grid["gamma_points"]))
    offsets = np.linspace(float(grid["T_sw_offset_min_K"]), float(grid["T_sw_offset_max_K"]), int(grid["T_sw_offset_points"]))
    power = float(grid.get("interpolation_power", 2.0))
    rows: list[dict[str, Any]] = []
    for gamma in gammas:
        lx = float(np.log(gamma))
        for off in offsets:
            obj = _idw(sx, sy, sobj, lx, float(off), power)
            g_loss = _idw(sx, sy, sg, lx, float(off), power)
            i_loss = _idw(sx, sy, si, lx, float(off), power)
            rows.append({"gamma_sub": float(gamma), "T_sw_offset_K": float(off), "objective": obj, "G_loss": g_loss, "I_loss": i_loss, "heat_residual_loss": 0.0, "finite_result": bool(np.isfinite([obj, g_loss, i_loss]).all()), "source": "coarse_simulated_profile_idw_interpolation"})
    profiles = _profiles(rows)
    metrics = _metrics(rows, cfg)
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin dense profile response surface; not experimental data.",
        "budget_note": "Dense 41x61 official run is IDW interpolation from the prior 77-point simulator-backed profile grid, not 2501 new ODE solves.",
        "num_dense_grid_points": len(rows),
        "num_source_grid_points": len(source),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        **metrics,
        "outputs": {"summary_json": cfg["summary_json"], "grid_csv": cfg["grid_csv"], "profiles_csv": cfg["profiles_csv"]},
    }
    write_json(cfg["summary_json"], summary)
    write_csv(cfg["grid_csv"], rows, GRID_FIELDS)
    write_csv(cfg["profiles_csv"], profiles, PROFILE_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_dense_profile(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "num_dense_grid_points": summary["num_dense_grid_points"], "condition_number": summary["condition_number"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
