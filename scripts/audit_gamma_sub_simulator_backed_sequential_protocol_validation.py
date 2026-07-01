"""Simulator-backed validation for sequential gamma_sub protocol hypotheses.

This script re-runs the existing ODE simulator for each candidate gamma_sub and
scenario. It avoids response-surface lookup for the official validation cases,
while keeping stage-one prior narrowing as an explicit synthetic assumption.
"""

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

from scripts.gamma_sub_validation_common import (
    ensure_frozen_inputs, load_sparse_obs, load_target, load_yaml, make_noisy,
    objective_components, observation_times, port_series, relative_error,
    simulate_with_overrides, write_csv, write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_simulator_backed_sequential_protocol_validation.yaml")
CASE_FIELDS = [
    "candidate_name", "scenario", "noise_level", "seed", "simulator_protocol",
    "T_sw_delta_K", "T_sw_prior_width", "prior_width_factor", "effective_T_sw_delta_K",
    "observation_count", "true_gamma_sub", "estimated_gamma_sub", "relative_error",
    "success_flag", "objective_value", "G_loss", "I_loss", "heat_residual_loss",
    "num_candidate_simulations", "simulator_backed", "finite_result",
]


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _protocol_overrides(spec: dict[str, Any]) -> dict[str, float]:
    overrides = {}
    for key in ("ltp_v_pos", "ltp_v_neg", "triangle_v_peak"):
        if key in spec:
            overrides[key] = float(spec[key])
    return overrides


def _candidate_profiles(base_params: dict[str, Any], spec: dict[str, Any], config: dict[str, Any], obs_time: np.ndarray) -> list[dict[str, Any]]:
    sim_cfg = dict(config["simulation"])
    sim_cfg["protocol"] = str(spec["simulator_protocol"])
    t_max = float(spec.get("t_max", 0.015))
    overrides = _protocol_overrides(spec)
    out = []
    for gamma in [float(value) for value in config["inverse"]["gamma_candidates"]]:
        gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=gamma, t_max=t_max, param_overrides=overrides)
        g_obs, i_obs = port_series(gt, obs_time)
        out.append({"gamma_sub": gamma, "gt": gt, "G": g_obs, "I": i_obs})
    return out


def _best_from_profiles(profiles: list[dict[str, Any]], base_params: dict[str, Any], obs_time: np.ndarray, target_g: np.ndarray, target_i: np.ndarray, weights: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for profile in profiles:
        comps = objective_components(profile["gt"], base_params, float(profile["gamma_sub"]), obs_time, target_g, target_i, weights)
        rows.append({"gamma_sub": float(profile["gamma_sub"]), **comps})
    return min(rows, key=lambda row: float(row["objective"]))


def run_simulator_backed_sequential_validation(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_yaml(config_path)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    base_params = dict(target["params"])
    true_gamma = float(base_params["gamma_sub"])
    threshold = float(config["inverse"].get("success_relative_error_threshold", 0.15))
    rows: list[dict[str, Any]] = []
    profile_cache: dict[str, tuple[np.ndarray, list[dict[str, Any]]]] = {}

    for spec in config["protocol_candidates"]:
        spec_key = str(spec["candidate_name"])
        sim_cfg = dict(config["simulation"])
        sim_cfg["protocol"] = str(spec["simulator_protocol"])
        t_max = float(spec.get("t_max", 0.015))
        nominal_gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=true_gamma, t_max=t_max, param_overrides=_protocol_overrides(spec))
        obs_time = observation_times(np.asarray(nominal_gt["t"], dtype=float), int(config["observation_count"]))
        profile_cache[spec_key] = (obs_time, _candidate_profiles(base_params, spec, config, obs_time))

    for spec in config["protocol_candidates"]:
        spec_key = str(spec["candidate_name"])
        obs_time, profiles = profile_cache[spec_key]
        for scenario in config["scenarios"]:
            base_delta = float(scenario["T_sw_delta_K"]) * float(scenario["T_sw_prior_width"])
            effective_delta = base_delta * float(spec.get("prior_width_factor", 1.0))
            target_overrides = _protocol_overrides(spec)
            target_overrides["T_sw"] = float(base_params["T_sw"]) + effective_delta
            sim_cfg = dict(config["simulation"])
            sim_cfg["protocol"] = str(spec["simulator_protocol"])
            target_gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=true_gamma, t_max=float(spec.get("t_max", 0.015)), param_overrides=target_overrides)
            clean_g, clean_i = port_series(target_gt, obs_time)
            for noise in [float(value) for value in config["noise_levels"]]:
                for seed in [int(value) for value in config["seeds"]]:
                    rng = np.random.default_rng(seed)
                    target_g = make_noisy(clean_g, noise, rng)
                    target_i = make_noisy(clean_i, noise, rng)
                    best = _best_from_profiles(profiles, base_params, obs_time, target_g, target_i, config.get("loss", {}))
                    gamma_est = float(best["gamma_sub"])
                    rel = relative_error(gamma_est, true_gamma)
                    rows.append({
                        "candidate_name": spec_key,
                        "scenario": str(scenario["scenario"]),
                        "noise_level": noise,
                        "seed": seed,
                        "simulator_protocol": str(spec["simulator_protocol"]),
                        "T_sw_delta_K": float(scenario["T_sw_delta_K"]),
                        "T_sw_prior_width": float(scenario["T_sw_prior_width"]),
                        "prior_width_factor": float(spec.get("prior_width_factor", 1.0)),
                        "effective_T_sw_delta_K": effective_delta,
                        "observation_count": int(config["observation_count"]),
                        "true_gamma_sub": true_gamma,
                        "estimated_gamma_sub": gamma_est,
                        "relative_error": rel,
                        "success_flag": bool(rel <= threshold),
                        "objective_value": float(best["objective"]),
                        "G_loss": float(best["G_loss"]),
                        "I_loss": float(best["I_loss"]),
                        "heat_residual_loss": float(best["heat_residual_loss"]),
                        "num_candidate_simulations": len(profiles),
                        "simulator_backed": True,
                        "finite_result": bool(np.isfinite([rel, best["objective"], best["G_loss"], best["I_loss"]]).all()),
                    })

    after = ensure_frozen_inputs(target_path, obs_path)
    by_candidate = {}
    for name in sorted({row["candidate_name"] for row in rows}):
        subset = [row for row in rows if row["candidate_name"] == name]
        errors = np.asarray([float(row["relative_error"]) for row in subset], dtype=float)
        by_candidate[name] = {"num_cases": len(subset), "mean_relative_error": float(np.mean(errors)), "max_relative_error": float(np.max(errors)), "success_rate": float(np.mean([bool(row["success_flag"]) for row in subset]))}
    best_name = min(by_candidate, key=lambda key: by_candidate[key]["mean_relative_error"])
    reference_best = None
    ref_path = _resolve(config.get("reference_sequential_summary", ""))
    if ref_path.exists():
        reference_best = json.loads(ref_path.read_text(encoding="utf-8"))["best_candidate_by_gamma_error"]["candidate_name"]
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin simulator-backed protocol validation; not experimental data.",
        "scope": "Only gamma_sub is estimated. Stage-one prior narrowing remains a synthetic design assumption; target and candidate port profiles are ODE simulated.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "all_cases_simulator_backed": bool(all(row["simulator_backed"] for row in rows)),
        "by_candidate": by_candidate,
        "best_candidate_by_simulator_backed_mean_error": best_name,
        "response_surface_best_candidate_reference": reference_best,
        "whether_simulator_backed_validation_supports_response_surface_ranking": bool(reference_best == best_name),
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": before == after,
        "outputs": {"summary_json": config["summary_json"], "cases_csv": config["cases_csv"]},
        "case_rows_stored_in": config["cases_csv"],
    }
    write_csv(config["cases_csv"], rows, CASE_FIELDS)
    write_json(config["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_simulator_backed_sequential_validation(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "cases_csv": summary["outputs"]["cases_csv"], "best_candidate": summary["best_candidate_by_simulator_backed_mean_error"], "supports_response_surface_ranking": summary["whether_simulator_backed_validation_supports_response_surface_ranking"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
