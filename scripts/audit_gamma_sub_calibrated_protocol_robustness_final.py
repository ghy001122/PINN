"""Final ODE-backed calibrated protocol robustness audit."""

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

DEFAULT_CONFIG = Path("configs/gamma_sub_calibrated_protocol_robustness_final.yaml")
FIELDS = ["candidate_name", "noise", "observation_count", "seed", "T_sw_delta_K", "effective_T_sw_delta_K", "simulator_protocol", "true_gamma_sub", "estimated_gamma_sub", "relative_error", "success_flag", "objective_value", "G_loss", "I_loss", "heat_residual_loss", "protocol_cost_proxy", "simulator_backed", "finite_result"]


def _resolve(path_text: str | Path) -> Path:
    p = Path(path_text)
    return p if p.is_absolute() else ROOT / p


def _overrides(spec: dict[str, Any]) -> dict[str, float]:
    out = {}
    for key in ("ltp_v_pos", "ltp_v_neg", "triangle_v_peak"):
        if key in spec:
            out[key] = float(spec[key])
    return out


def _profiles(base_params: dict[str, Any], spec: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    sim_cfg = dict(cfg["simulation"])
    sim_cfg["protocol"] = str(spec["simulator_protocol"])
    rows = []
    for gamma in [float(v) for v in cfg["inverse"]["gamma_candidates"]]:
        gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=gamma, t_max=float(spec.get("t_max", 0.015)), param_overrides=_overrides(spec))
        rows.append({"gamma_sub": gamma, "gt": gt})
    return rows


def _best(profiles: list[dict[str, Any]], base_params: dict[str, Any], obs_time: np.ndarray, target_g: np.ndarray, target_i: np.ndarray, weights: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in profiles:
        comps = objective_components(item["gt"], base_params, float(item["gamma_sub"]), obs_time, target_g, target_i, weights)
        rows.append({"gamma_sub": float(item["gamma_sub"]), **comps})
    return min(rows, key=lambda row: float(row["objective"]))


def _summary_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for name in sorted({r["candidate_name"] for r in rows}):
        subset = [r for r in rows if r["candidate_name"] == name]
        errors = np.asarray([float(r["relative_error"]) for r in subset], dtype=float)
        out[name] = {
            "success_rate": float(np.mean([bool(r["success_flag"]) for r in subset])),
            "median_error": float(np.median(errors)),
            "IQR_error": float(np.percentile(errors, 75) - np.percentile(errors, 25)),
            "worst_case": float(np.max(errors)),
            "mean_error": float(np.mean(errors)),
            "num_cases": len(subset),
        }
    return out


def run_robustness_final(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    target_path = _resolve(cfg["target_npz"])
    obs_path = _resolve(cfg["sparse_obs_npz"])
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    base_params = dict(target["params"])
    true_gamma = float(base_params["gamma_sub"])
    threshold = float(cfg["inverse"].get("success_relative_error_threshold", 0.15))
    profiles = {str(spec["candidate_name"]): _profiles(base_params, spec, cfg) for spec in cfg["protocol_candidates"]}
    rows: list[dict[str, Any]] = []
    for spec in cfg["protocol_candidates"]:
        name = str(spec["candidate_name"])
        sim_cfg = dict(cfg["simulation"])
        sim_cfg["protocol"] = str(spec["simulator_protocol"])
        nominal = profiles[name][0]["gt"]
        for obs_count in [int(v) for v in cfg["observation_count"]]:
            obs_time = observation_times(np.asarray(nominal["t"], dtype=float), obs_count)
            for delta in [float(v) for v in cfg["T_sw_delta_K"]]:
                target_overrides = _overrides(spec)
                effective = delta * float(spec["calibration_error_factor"])
                target_overrides["T_sw"] = float(base_params["T_sw"]) + effective
                target_gt = simulate_with_overrides(base_params, sim_cfg, gamma_sub=true_gamma, t_max=float(spec.get("t_max", 0.015)), param_overrides=target_overrides)
                clean_g, clean_i = port_series(target_gt, obs_time)
                for noise in [float(v) for v in cfg["noise"]]:
                    for seed in [int(v) for v in cfg["seeds"]]:
                        rng = np.random.default_rng(seed)
                        best = _best(profiles[name], base_params, obs_time, make_noisy(clean_g, noise, rng), make_noisy(clean_i, noise, rng), cfg.get("loss", {}))
                        gamma_est = float(best["gamma_sub"])
                        rel = relative_error(gamma_est, true_gamma)
                        rows.append({
                            "candidate_name": name,
                            "noise": noise,
                            "observation_count": obs_count,
                            "seed": seed,
                            "T_sw_delta_K": delta,
                            "effective_T_sw_delta_K": effective,
                            "simulator_protocol": str(spec["simulator_protocol"]),
                            "true_gamma_sub": true_gamma,
                            "estimated_gamma_sub": gamma_est,
                            "relative_error": rel,
                            "success_flag": bool(rel <= threshold),
                            "objective_value": float(best["objective"]),
                            "G_loss": float(best["G_loss"]),
                            "I_loss": float(best["I_loss"]),
                            "heat_residual_loss": float(best["heat_residual_loss"]),
                            "protocol_cost_proxy": float(spec["protocol_cost_proxy"]),
                            "simulator_backed": True,
                            "finite_result": bool(np.isfinite([rel, best["objective"], best["G_loss"], best["I_loss"]]).all()),
                        })
    after = ensure_frozen_inputs(target_path, obs_path)
    by_protocol = _summary_stats(rows)
    best_name = min(by_protocol, key=lambda k: (by_protocol[k]["median_error"], -by_protocol[k]["success_rate"], by_protocol[k]["worst_case"]))
    uncal = by_protocol["no_calibration_ltp_ltd_only"]
    multi = by_protocol["calibrated_multi_pulse_to_ltp_ltd"]
    wrong = by_protocol["wrong_calibration_multi_pulse_to_ltp_ltd"]
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic ODE-backed calibrated protocol robustness audit; not experimental data.",
        "num_simulator_backed_cases": len(rows),
        "all_cases_simulator_backed": bool(all(r["simulator_backed"] for r in rows)),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "best_protocol": best_name,
        "success_rate_by_protocol": {k: v["success_rate"] for k, v in by_protocol.items()},
        "median_error_by_protocol": {k: v["median_error"] for k, v in by_protocol.items()},
        "IQR_error_by_protocol": {k: v["IQR_error"] for k, v in by_protocol.items()},
        "worst_case_by_protocol": {k: v["worst_case"] for k, v in by_protocol.items()},
        "calibrated_multi_pulse_gain_over_uncalibrated": float(uncal["median_error"] - multi["median_error"]),
        "calibrated_multi_pulse_success_gain_over_uncalibrated": float(multi["success_rate"] - uncal["success_rate"]),
        "wrong_calibration_penalty": float(wrong["mean_error"] - multi["mean_error"]),
        "whether_ready_as_main_figure": bool(best_name == "calibrated_multi_pulse_to_ltp_ltd" and multi["success_rate"] >= 0.8 and multi["worst_case"] <= 0.2),
        "required_claim_qualification": "Use as a synthetic ODE-backed main-figure candidate only under calibrated or tightly bounded T_sw priors; not an experimental protocol claim.",
        "by_protocol": by_protocol,
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
    print(json.dumps(run_robustness_final(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
