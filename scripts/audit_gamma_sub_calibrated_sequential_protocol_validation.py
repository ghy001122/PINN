"""Calibrated sequential protocol validation with ODE-backed port profiles."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_validation_common import ensure_frozen_inputs, load_sparse_obs, load_target, load_yaml, make_noisy, objective_components, observation_times, port_series, relative_error, simulate_with_overrides, write_csv, write_json

DEFAULT_CONFIG = Path("configs/gamma_sub_calibrated_sequential_protocol_validation.yaml")
CASE_FIELDS = ["candidate_name", "scenario", "noise_level", "seed", "simulator_protocol", "effective_T_sw_delta_K", "calibration_error_K", "observation_count", "true_gamma_sub", "estimated_gamma_sub", "relative_error", "success_flag", "recoverable_le_0p1", "recoverable_le_0p2", "objective_value", "G_loss", "I_loss", "heat_residual_loss", "protocol_cost_proxy", "simulator_backed", "finite_result"]


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _overrides(spec: dict[str, Any]) -> dict[str, float]:
    out = {}
    for key in ("ltp_v_pos", "ltp_v_neg", "triangle_v_peak"):
        if key in spec:
            out[key] = float(spec[key])
    return out


def _profiles(base_params: dict[str, Any], spec: dict[str, Any], config: dict[str, Any], obs_time: np.ndarray) -> list[dict[str, Any]]:
    sim_cfg = dict(config["simulation"])
    sim_cfg["protocol"] = str(spec["simulator_protocol"])
    rows = []
    for gamma in [float(v) for v in config["inverse"]["gamma_candidates"]]:
        gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=gamma, t_max=float(spec.get("t_max", 0.015)), param_overrides=_overrides(spec))
        rows.append({"gamma_sub": gamma, "gt": gt})
    return rows


def _best(profiles: list[dict[str, Any]], base_params: dict[str, Any], obs_time: np.ndarray, target_g: np.ndarray, target_i: np.ndarray, weights: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in profiles:
        comps = objective_components(item["gt"], base_params, float(item["gamma_sub"]), obs_time, target_g, target_i, weights)
        rows.append({"gamma_sub": float(item["gamma_sub"]), **comps})
    return min(rows, key=lambda row: float(row["objective"]))


def run_calibrated_sequential_validation(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    target_path = _resolve(cfg["target_npz"])
    obs_path = _resolve(cfg["sparse_obs_npz"])
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    base_params = dict(target["params"])
    true_gamma = float(base_params["gamma_sub"])
    threshold = float(cfg["inverse"].get("success_relative_error_threshold", 0.15))
    profile_cache = {}
    for spec in cfg["protocol_candidates"]:
        key = str(spec["candidate_name"])
        sim_cfg = dict(cfg["simulation"])
        sim_cfg["protocol"] = str(spec["simulator_protocol"])
        nominal = simulate_with_overrides(base_params, sim_cfg, gamma_sub=true_gamma, t_max=float(spec.get("t_max", 0.015)), param_overrides=_overrides(spec))
        obs_time = observation_times(np.asarray(nominal["t"], dtype=float), int(cfg["observation_count"]))
        profile_cache[key] = (obs_time, _profiles(base_params, spec, cfg, obs_time))
    rows: list[dict[str, Any]] = []
    for spec in cfg["protocol_candidates"]:
        key = str(spec["candidate_name"])
        obs_time, profiles = profile_cache[key]
        for scenario in cfg["scenarios"]:
            raw_delta = float(scenario["T_sw_delta_K"]) * float(scenario["T_sw_prior_width"])
            effective = raw_delta * float(spec["calibration_error_factor"])
            target_overrides = _overrides(spec)
            target_overrides["T_sw"] = float(base_params["T_sw"]) + effective
            sim_cfg = dict(cfg["simulation"])
            sim_cfg["protocol"] = str(spec["simulator_protocol"])
            target_gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=true_gamma, t_max=float(spec.get("t_max", 0.015)), param_overrides=target_overrides)
            clean_g, clean_i = port_series(target_gt, obs_time)
            for noise in [float(v) for v in cfg["noise_levels"]]:
                for seed in [int(v) for v in cfg["seeds"]]:
                    rng = np.random.default_rng(seed)
                    best = _best(profiles, base_params, obs_time, make_noisy(clean_g, noise, rng), make_noisy(clean_i, noise, rng), cfg.get("loss", {}))
                    gamma_est = float(best["gamma_sub"])
                    rel = relative_error(gamma_est, true_gamma)
                    rows.append({"candidate_name": key, "scenario": str(scenario["scenario"]), "noise_level": noise, "seed": seed, "simulator_protocol": str(spec["simulator_protocol"]), "effective_T_sw_delta_K": effective, "calibration_error_K": effective, "observation_count": int(cfg["observation_count"]), "true_gamma_sub": true_gamma, "estimated_gamma_sub": gamma_est, "relative_error": rel, "success_flag": bool(rel <= threshold), "recoverable_le_0p1": bool(rel <= 0.1), "recoverable_le_0p2": bool(rel <= 0.2), "objective_value": float(best["objective"]), "G_loss": float(best["G_loss"]), "I_loss": float(best["I_loss"]), "heat_residual_loss": float(best["heat_residual_loss"]), "protocol_cost_proxy": float(spec["protocol_cost_proxy"]), "simulator_backed": True, "finite_result": bool(np.isfinite([rel, best["objective"], best["G_loss"], best["I_loss"]]).all())})
    after = ensure_frozen_inputs(target_path, obs_path)
    by_protocol = {}
    for name in sorted({r["candidate_name"] for r in rows}):
        subset = [r for r in rows if r["candidate_name"] == name]
        errors = np.asarray([float(r["relative_error"]) for r in subset], dtype=float)
        by_protocol[name] = {"num_cases": len(subset), "success_rate": float(np.mean([bool(r["success_flag"]) for r in subset])), "median_error": float(np.median(errors)), "mean_error": float(np.mean(errors)), "max_error": float(np.max(errors))}
    best_name = min(by_protocol, key=lambda k: (by_protocol[k]["median_error"], -by_protocol[k]["success_rate"], by_protocol[k]["max_error"], by_protocol[k]["mean_error"]))
    uncal = by_protocol["no_calibration_ltp_ltd_only"]
    best = by_protocol[best_name]
    wrong = by_protocol["wrong_calibration_multi_pulse_to_ltp_ltd"]
    summary = {"benchmark": cfg.get("benchmark"), "note": "Synthetic numerical digital-twin calibrated sequential protocol validation; not experimental data.", "num_simulator_backed_cases": len(rows), "all_cases_simulator_backed": bool(all(r["simulator_backed"] for r in rows)), "all_finite_results": bool(all(r["finite_result"] for r in rows)), "best_calibrated_protocol": best_name, "success_rate_by_protocol": {k: v["success_rate"] for k, v in by_protocol.items()}, "median_error_by_protocol": {k: v["median_error"] for k, v in by_protocol.items()}, "improvement_over_uncalibrated": float(uncal["median_error"] - best["median_error"]), "success_rate_gain_over_uncalibrated": float(best["success_rate"] - uncal["success_rate"]), "degradation_under_wrong_calibration": float(wrong["mean_error"] - best["mean_error"]), "wrong_calibration_success_rate_drop": float(best["success_rate"] - wrong["success_rate"]), "whether_calibrated_sequential_design_is_manuscript_main_result": bool(best_name != "no_calibration_ltp_ltd_only" and best["median_error"] < uncal["median_error"]), "by_protocol": by_protocol, "frozen_gt_hashes_before": before, "frozen_gt_hashes_after": after, "frozen_gt_unchanged": before == after, "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]}}
    write_csv(cfg["cases_csv"], rows, CASE_FIELDS)
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_calibrated_sequential_validation(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
