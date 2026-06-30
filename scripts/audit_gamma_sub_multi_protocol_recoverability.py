"""Multi-protocol recoverability audit for constrained gamma_sub inversion.

The audit estimates only `gamma_sub` and compares triangle, LTP/LTD,
lightweight derived multi-amplitude synthetic, and mixed-protocol objectives.
All results are synthetic numerical digital-twin benchmark evidence, not
experimental data and not sparse-port full hidden-field recovery.
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
        candidate_values,
        display_path,
        ensure_frozen_inputs,
        finite_row,
        load_sparse_obs,
        load_target,
        load_yaml,
        make_noisy,
        observation_times,
        port_series,
        relative_error,
        resolve,
        simulate_with_overrides,
        write_csv,
        write_json,
    )
except ModuleNotFoundError:  # pragma: no cover
    from gamma_sub_validation_common import (  # type: ignore
        candidate_values,
        display_path,
        ensure_frozen_inputs,
        finite_row,
        load_sparse_obs,
        load_target,
        load_yaml,
        make_noisy,
        observation_times,
        port_series,
        relative_error,
        resolve,
        simulate_with_overrides,
        write_csv,
        write_json,
    )

DEFAULT_CONFIG = Path("configs/gamma_sub_multi_protocol_recoverability.yaml")
GT_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}

CSV_FIELDS = [
    "protocol",
    "scenario",
    "observation_count",
    "noise",
    "gamma_true",
    "gamma_est",
    "relative_error",
    "objective",
    "G_loss",
    "I_loss",
    "T_sw_delta_K",
    "T_sw_prior_width",
    "recoverable_le_0p1",
    "recoverable_le_0p2",
    "finite_result",
    "frozen_inputs_unchanged",
]


def _sim_config(config: dict[str, Any], protocol: str) -> dict[str, Any]:
    sim = dict(config["simulation"])
    sim["protocol"] = "ltp_ltd" if protocol == "ltp_ltd" else "triangle"
    if protocol == "multi_amplitude_synthetic":
        sim["protocol"] = str(config["protocol_overrides"]["multi_amplitude_synthetic"].get("protocol", "triangle"))
    sim["nt"] = int(config["simulation"].get("nt_ltp_ltd" if sim["protocol"] == "ltp_ltd" else "nt_triangle", config["simulation"].get("nt", 160)))
    return sim


def _base_protocol_bundle(config: dict[str, Any], protocol: str) -> dict[str, Any]:
    inputs = config["inputs"]
    if protocol == "triangle":
        target = load_target(inputs["triangle_target_npz"])
        obs = load_sparse_obs(inputs["triangle_sparse_obs_npz"])
        return {"protocol_key": "triangle", "target": target, "obs": obs, "sim": _sim_config(config, "triangle"), "param_overrides": {}, "t_max": float(target["t"][-1])}
    if protocol == "ltp_ltd":
        target = load_target(inputs["ltp_ltd_target_npz"])
        obs = load_sparse_obs(inputs["ltp_ltd_sparse_obs_npz"])
        return {"protocol_key": "ltp_ltd", "target": target, "obs": obs, "sim": _sim_config(config, "ltp_ltd"), "param_overrides": {}, "t_max": float(target["t"][-1])}
    if protocol == "multi_amplitude_synthetic":
        tri = load_target(inputs["triangle_target_npz"])
        overrides = dict(config["protocol_overrides"]["multi_amplitude_synthetic"].get("params", {}))
        if "triangle_v_peak" in config["protocol_overrides"]["multi_amplitude_synthetic"]:
            overrides["triangle_v_peak"] = float(config["protocol_overrides"]["multi_amplitude_synthetic"]["triangle_v_peak"])
        t_max = float(config["protocol_overrides"]["multi_amplitude_synthetic"].get("t_max", tri["t"][-1]))
        return {"protocol_key": "multi_amplitude_synthetic", "target": tri, "obs": None, "sim": _sim_config(config, "multi_amplitude_synthetic"), "param_overrides": overrides, "t_max": t_max}
    raise ValueError(f"Unsupported base protocol: {protocol}")


def _cache_key(prefix: str, bundle: dict[str, Any], gamma: float, overrides: dict[str, Any]) -> tuple[Any, ...]:
    override_items = tuple(sorted((str(key), round(float(value), 12)) for key, value in overrides.items()))
    sim = bundle["sim"]
    return (prefix, bundle["protocol_key"], sim.get("protocol"), int(sim.get("nx", 0)), int(sim.get("nt", 0)), round(float(bundle["t_max"]), 12), round(float(gamma), 6), override_items)


def _target_gt(bundle: dict[str, Any], scenario: dict[str, Any], true_gamma: float) -> dict[str, Any]:
    params = dict(bundle["target"]["params"])
    overrides = dict(bundle["param_overrides"])
    effective_delta = float(scenario["T_sw_delta_K"]) * float(scenario["T_sw_prior_width"])
    if effective_delta:
        overrides["T_sw"] = float(params["T_sw"]) + effective_delta
    key = _cache_key("target", bundle, true_gamma, overrides)
    if key not in GT_CACHE:
        GT_CACHE[key] = simulate_with_overrides(params, bundle["sim"], gamma_sub=true_gamma, t_max=float(bundle["t_max"]), param_overrides=overrides)
    return GT_CACHE[key]


def _candidate_gt(bundle: dict[str, Any], gamma: float) -> dict[str, Any]:
    overrides = dict(bundle["param_overrides"])
    key = _cache_key("candidate", bundle, gamma, overrides)
    if key not in GT_CACHE:
        GT_CACHE[key] = simulate_with_overrides(dict(bundle["target"]["params"]), bundle["sim"], gamma_sub=float(gamma), t_max=float(bundle["t_max"]), param_overrides=overrides)
    return GT_CACHE[key]


def _loss_from_series(pred_g: np.ndarray, pred_i: np.ndarray, target_g: np.ndarray, target_i: np.ndarray, weights: dict[str, Any]) -> dict[str, float]:
    denom_g = max(float(np.sqrt(np.mean(target_g**2))), 1.0e-30)
    denom_i = max(float(np.sqrt(np.mean(target_i**2))), 1.0e-30)
    g_loss = float(np.sqrt(np.mean((pred_g - target_g) ** 2)) / denom_g) ** 2
    i_loss = float(np.sqrt(np.mean((pred_i - target_i) ** 2)) / denom_i) ** 2
    objective = float(weights.get("w_g", 1.0)) * g_loss + float(weights.get("w_i", 0.5)) * i_loss
    return {"objective": float(objective), "G_loss": float(g_loss), "I_loss": float(i_loss)}


def _single_protocol_case(config: dict[str, Any], protocol: str, scenario: dict[str, Any], n_obs: int, noise: float, seed: int) -> dict[str, Any]:
    bundle = _base_protocol_bundle(config, protocol)
    true_gamma = float(bundle["target"]["params"]["gamma_sub"])
    gt_target = _target_gt(bundle, scenario, true_gamma)
    obs_time = observation_times(np.asarray(gt_target["t"], dtype=float), n_obs)
    target_g_clean, target_i_clean = port_series(gt_target, obs_time)
    rng = np.random.default_rng(seed)
    target_g = make_noisy(target_g_clean, noise, rng)
    target_i = make_noisy(target_i_clean, noise, rng)
    best: dict[str, Any] | None = None
    for gamma in candidate_values(config, true_gamma):
        cand = _candidate_gt(bundle, gamma)
        pred_g, pred_i = port_series(cand, obs_time)
        row = {"gamma_sub": float(gamma), **_loss_from_series(pred_g, pred_i, target_g, target_i, config["loss"])}
        if best is None or float(row["objective"]) < float(best["objective"]):
            best = row
    if best is None:
        raise RuntimeError("No candidate rows evaluated")
    return _result_row(protocol, scenario, n_obs, noise, true_gamma, best)


def _mixed_case(config: dict[str, Any], scenario: dict[str, Any], n_obs: int, noise: float, seed: int) -> dict[str, Any]:
    bundles = [_base_protocol_bundle(config, "triangle"), _base_protocol_bundle(config, "ltp_ltd")]
    true_gamma = float(bundles[0]["target"]["params"]["gamma_sub"])
    rng = np.random.default_rng(seed)
    targets = []
    for bundle in bundles:
        gt_target = _target_gt(bundle, scenario, true_gamma)
        obs_time = observation_times(np.asarray(gt_target["t"], dtype=float), n_obs)
        g, i = port_series(gt_target, obs_time)
        targets.append((bundle, obs_time, make_noisy(g, noise, rng), make_noisy(i, noise, rng)))
    best: dict[str, Any] | None = None
    for gamma in candidate_values(config, true_gamma):
        objective = 0.0
        g_loss = 0.0
        i_loss = 0.0
        for bundle, obs_time, target_g, target_i in targets:
            cand = _candidate_gt(bundle, gamma)
            pred_g, pred_i = port_series(cand, obs_time)
            loss = _loss_from_series(pred_g, pred_i, target_g, target_i, config["loss"])
            objective += float(loss["objective"])
            g_loss += float(loss["G_loss"])
            i_loss += float(loss["I_loss"])
        row = {"gamma_sub": float(gamma), "objective": objective / len(targets), "G_loss": g_loss / len(targets), "I_loss": i_loss / len(targets)}
        if best is None or float(row["objective"]) < float(best["objective"]):
            best = row
    if best is None:
        raise RuntimeError("No mixed candidates evaluated")
    return _result_row("mixed_protocol", scenario, n_obs, noise, true_gamma, best)


def _result_row(protocol: str, scenario: dict[str, Any], n_obs: int, noise: float, true_gamma: float, best: dict[str, Any]) -> dict[str, Any]:
    rel = relative_error(float(best["gamma_sub"]), true_gamma)
    row = {
        "protocol": protocol,
        "scenario": scenario["name"],
        "observation_count": int(n_obs),
        "noise": float(noise),
        "gamma_true": true_gamma,
        "gamma_est": float(best["gamma_sub"]),
        "relative_error": float(rel),
        "objective": float(best["objective"]),
        "G_loss": float(best["G_loss"]),
        "I_loss": float(best["I_loss"]),
        "T_sw_delta_K": float(scenario["T_sw_delta_K"]),
        "T_sw_prior_width": float(scenario["T_sw_prior_width"]),
        "recoverable_le_0p1": bool(rel <= 0.1 + 1.0e-15),
        "recoverable_le_0p2": bool(rel <= 0.2 + 1.0e-15),
    }
    row["finite_result"] = finite_row(row, ["gamma_est", "relative_error", "objective", "G_loss", "I_loss"])
    return row


def _summarize(rows: list[dict[str, Any]], frozen: bool, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    by_protocol: dict[str, dict[str, Any]] = {}
    for protocol in sorted({str(row["protocol"]) for row in rows}):
        selected = [row for row in rows if row["protocol"] == protocol]
        by_protocol[protocol] = {
            "num_cases": len(selected),
            "mean_relative_error": float(np.mean([float(row["relative_error"]) for row in selected])),
            "max_relative_error": float(np.max([float(row["relative_error"]) for row in selected])),
            "recoverable_le_0p1": int(sum(bool(row["recoverable_le_0p1"]) for row in selected)),
            "recoverable_le_0p2": int(sum(bool(row["recoverable_le_0p2"]) for row in selected)),
        }
    best_protocol = min(by_protocol, key=lambda key: float(by_protocol[key]["mean_relative_error"]))
    worst_protocol = max(by_protocol, key=lambda key: float(by_protocol[key]["mean_relative_error"]))
    return {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin multi-protocol recoverability audit; not experimental data.",
        "scope": "Only gamma_sub is estimated. The audit tests conditional recoverability, not full hidden-field recovery.",
        "config_path": display_path(config_path),
        "num_cases": len(rows),
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "frozen_gt_unchanged": bool(frozen),
        "best_protocol": best_protocol,
        "worst_protocol": worst_protocol,
        "recoverable_count_by_protocol": by_protocol,
        "key_interpretation": "Multi-protocol evidence tests whether constrained gamma_sub recovery generalizes beyond the frozen triangle protocol; wide T_sw mismatch remains the main failure mode when priors are not narrowed.",
        "claim_boundary": "Supports synthetic numerical conditional identifiability/recoverability only under fixed or tightly bounded priors.",
        "rows": rows,
        "outputs": {"summary_json": config["summary_json"], "cases_csv": config["cases_csv"], "report_md": config["report_md"]},
    }


def run_multi_protocol_recoverability(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = resolve(config_path)
    config = load_yaml(config_path)
    GT_CACHE.clear()
    inputs = config["inputs"]
    frozen_paths = [
        resolve(inputs["triangle_target_npz"]),
        resolve(inputs["triangle_sparse_obs_npz"]),
        resolve(inputs["ltp_ltd_target_npz"]),
        resolve(inputs["ltp_ltd_sparse_obs_npz"]),
    ]
    before = ensure_frozen_inputs(*frozen_paths)
    _ = load_sparse_obs(inputs["triangle_sparse_obs_npz"])
    _ = load_sparse_obs(inputs["ltp_ltd_sparse_obs_npz"])
    rows: list[dict[str, Any]] = []
    protocols = [str(value) for value in config["sweep"]["protocols"]]
    scenarios = [dict(value) for value in config["sweep"]["scenarios"]]
    obs_counts = [int(value) for value in config["sweep"]["observation_counts"]]
    noises = [float(value) for value in config["sweep"].get("noise_levels", [0.0])]
    seed = int(config["sweep"].get("seed", 2026))
    idx = 0
    for protocol in protocols:
        for scenario in scenarios:
            for n_obs in obs_counts:
                for noise in noises:
                    if protocol == "mixed_protocol":
                        row = _mixed_case(config, scenario, n_obs, noise, seed + idx)
                    else:
                        row = _single_protocol_case(config, protocol, scenario, n_obs, noise, seed + idx)
                    rows.append(row)
                    idx += 1
    after = ensure_frozen_inputs(*frozen_paths)
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = bool(frozen)
    rows = sorted(rows, key=lambda row: (str(row["protocol"]), str(row["scenario"]), int(row["observation_count"]), float(row["noise"])))
    summary = _summarize(rows, frozen, config_path, config)
    summary["frozen_gt_hashes_before"] = before
    summary["frozen_gt_hashes_after"] = after
    write_json(config["summary_json"], summary)
    write_csv(config["cases_csv"], rows, CSV_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_multi_protocol_recoverability(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "cases_csv": summary["outputs"]["cases_csv"], "num_cases": summary["num_cases"], "best_protocol": summary["best_protocol"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

