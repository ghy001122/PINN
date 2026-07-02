"""ODE-backed T_sw tolerance spot-check for constrained gamma_sub inversion."""
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

from scripts.gamma_sub_validation_common import (
    best_gamma_from_candidates,
    candidate_values,
    ensure_frozen_inputs,
    load_sparse_obs,
    load_target,
    load_yaml,
    make_noisy,
    observation_times,
    port_series,
    relative_error,
    target_from_params,
    write_csv,
    write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_tolerance_ode_spotcheck.yaml")
FIELDS = ["protocol", "calibration_error_K", "T_sw_prior_width_after_calibration", "effective_T_sw_delta_K", "noise", "seed", "true_gamma_sub", "estimated_gamma_sub", "relative_error", "success_flag", "objective_value", "G_loss", "I_loss", "heat_residual_loss", "simulator_backed", "finite_result"]


def _overrides(spec: dict[str, Any]) -> dict[str, float]:
    return {key: float(spec[key]) for key in ("ltp_v_pos", "ltp_v_neg", "triangle_v_peak") if key in spec}


def _sort_key(value: str) -> float | str:
    try:
        return float(value)
    except ValueError:
        return value


def _group_median(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(float(row["relative_error"]))
    return {k: float(np.median(v)) for k, v in sorted(grouped.items(), key=lambda item: _sort_key(item[0]))}


def _group_success(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    grouped: dict[str, list[bool]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(bool(row["success_flag"]))
    return {k: float(np.mean(v)) for k, v in sorted(grouped.items(), key=lambda item: _sort_key(item[0]))}


def _best_from_cached_profiles(
    profiles: list[dict[str, Any]],
    base_params: dict[str, Any],
    obs_time: np.ndarray,
    target_g: np.ndarray,
    target_i: np.ndarray,
    weights: dict[str, Any],
) -> dict[str, Any]:
    from scripts.gamma_sub_validation_common import objective_components

    rows = []
    for item in profiles:
        comps = objective_components(item["gt"], base_params, float(item["gamma_sub"]), obs_time, target_g, target_i, weights)
        rows.append({"gamma_sub": float(item["gamma_sub"]), **comps})
    return min(rows, key=lambda row: float(row["objective"]))


def run_ode_spotcheck(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    target_path = ROOT / cfg["target_npz"]
    obs_path = ROOT / cfg["sparse_obs_npz"]
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    base_params = dict(target["params"])
    true_gamma = float(base_params["gamma_sub"])
    threshold = float(cfg["inverse"].get("success_relative_error_threshold", 0.15))
    gamma_grid = candidate_values(cfg, true_gamma=true_gamma, include_true=True)
    rows: list[dict[str, Any]] = []
    target_cache: dict[tuple[str, float], dict[str, Any]] = {}

    for spec in cfg["protocols"]:
        protocol_name = str(spec["protocol"])
        sim_cfg = dict(cfg["simulation"])
        sim_cfg["protocol"] = str(spec.get("simulator_protocol", protocol_name))
        t_max = float(spec.get("t_max", 0.015))
        protocol_overrides = _overrides(spec)
        nominal = target_from_params(base_params=base_params, sim_config=sim_cfg, true_gamma=true_gamma, t_max=t_max, target_overrides=protocol_overrides)
        obs_time = observation_times(np.asarray(nominal["t"], dtype=float), int(cfg["observation_count"]))
        profiles = [
            {
                "gamma_sub": float(gamma),
                "gt": target_from_params(base_params=base_params, sim_config=sim_cfg, true_gamma=float(gamma), t_max=t_max, target_overrides=protocol_overrides),
            }
            for gamma in gamma_grid
        ]
        for cal_error in [float(v) for v in cfg["calibration_error_K"]]:
            for width in [float(v) for v in cfg["T_sw_prior_width_after_calibration"]]:
                effective_delta = max(cal_error, float(cfg.get("T_sw_reference_delta_K", 2.0)) * width)
                cache_key = (protocol_name, round(effective_delta, 12))
                if cache_key not in target_cache:
                    target_overrides = dict(protocol_overrides)
                    target_overrides["T_sw"] = float(base_params["T_sw"]) + effective_delta
                    target_cache[cache_key] = target_from_params(base_params=base_params, sim_config=sim_cfg, true_gamma=true_gamma, t_max=t_max, target_overrides=target_overrides)
                clean_g, clean_i = port_series(target_cache[cache_key], obs_time)
                for noise in [float(v) for v in cfg["noise"]]:
                    for seed in [int(v) for v in cfg["seeds"]]:
                        rng = np.random.default_rng(seed)
                        best = _best_from_cached_profiles(profiles, base_params, obs_time, make_noisy(clean_g, noise, rng), make_noisy(clean_i, noise, rng), cfg.get("loss", {}))
                        est = float(best["gamma_sub"])
                        rel = relative_error(est, true_gamma)
                        finite = bool(np.isfinite([rel, best["objective"], best["G_loss"], best["I_loss"], best["heat_residual_loss"]]).all())
                        rows.append({
                            "protocol": protocol_name,
                            "calibration_error_K": cal_error,
                            "T_sw_prior_width_after_calibration": width,
                            "effective_T_sw_delta_K": float(effective_delta),
                            "noise": noise,
                            "seed": seed,
                            "true_gamma_sub": true_gamma,
                            "estimated_gamma_sub": est,
                            "relative_error": rel,
                            "success_flag": bool(rel <= threshold),
                            "objective_value": float(best["objective"]),
                            "G_loss": float(best["G_loss"]),
                            "I_loss": float(best["I_loss"]),
                            "heat_residual_loss": float(best["heat_residual_loss"]),
                            "simulator_backed": True,
                            "finite_result": finite,
                        })
    after = ensure_frozen_inputs(target_path, obs_path)
    med_by_error = _group_median(rows, "calibration_error_K")
    succ_by_error = _group_success(rows, "calibration_error_K")
    med_by_width = _group_median(rows, "T_sw_prior_width_after_calibration")
    med_by_effective = _group_median(rows, "effective_T_sw_delta_K")
    supported_0p1 = bool(float(med_by_error.get("0.1", np.inf)) <= threshold)
    larger_0p2_supported = bool(float(med_by_error.get("0.2", np.inf)) <= threshold)
    needs_qualification = bool((not supported_0p1) or larger_0p2_supported)
    sentence = (
        "The ODE-backed synthetic spot-check supports the 0.1 K tolerance threshold under the configured <=15% median-error criterion, but it remains a benchmark-specific audit threshold rather than an experimental calibration requirement."
        if supported_0p1
        else "The ODE-backed synthetic spot-check does not support the 0.1 K tolerance threshold under the configured <=15% median-error criterion; the tolerance claim must be downgraded."
    )
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic ODE-backed T_sw tolerance spot-check; not experimental calibration evidence.",
        "num_ode_backed_cases": len(rows),
        "all_cases_simulator_backed": bool(all(r["simulator_backed"] for r in rows)),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "median_error_by_calibration_error": med_by_error,
        "success_rate_by_calibration_error": succ_by_error,
        "median_error_by_prior_width": med_by_width,
        "median_error_by_effective_T_sw_delta_K": med_by_effective,
        "whether_0p1K_threshold_supported_by_ode_spotcheck": supported_0p1,
        "whether_response_surface_tolerance_claim_needs_qualification": needs_qualification,
        "manuscript_sentence_for_ode_spotcheck": sentence,
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": before == after,
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    write_csv(cfg["cases_csv"], rows, FIELDS)
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_ode_spotcheck(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
