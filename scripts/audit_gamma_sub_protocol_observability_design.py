"""Protocol observability design preflight for gamma_sub inversion.

This lightweight audit compares candidate stimulation protocols through finite
difference sensitivity vectors for `gamma_sub` and `T_sw`. It is synthetic
numerical digital-twin design evidence, not experimental validation.
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

DEFAULT_CONFIG = Path("configs/gamma_sub_protocol_observability_design.yaml")
CSV_FIELDS = [
    "protocol_name",
    "protocol",
    "sensitivity_norm_gamma_sub",
    "sensitivity_norm_T_sw",
    "sensitivity_angle_or_cosine",
    "distinguishability_score",
    "expected_gamma_error_proxy",
    "recommended_for_gamma_sub_inversion",
    "finite_result",
    "frozen_inputs_unchanged",
]


def _response_vector(gt: dict[str, Any], n_obs: int) -> np.ndarray:
    obs_time = observation_times(np.asarray(gt["t"], dtype=float), n_obs)
    g, i = port_series(gt, obs_time)
    g_scale = max(float(np.sqrt(np.mean(g**2))), 1.0e-30)
    i_scale = max(float(np.sqrt(np.mean(i**2))), 1.0e-30)
    return np.concatenate([g / g_scale, i / i_scale])


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = max(float(np.linalg.norm(a) * np.linalg.norm(b)), 1.0e-30)
    return float(np.dot(a, b) / denom)


def _protocol_sim_config(config: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    sim = dict(config["simulation"])
    sim["protocol"] = str(item["protocol"])
    return sim


def _run_protocol(config: dict[str, Any], target: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    params = dict(target["params"])
    true_gamma = float(params["gamma_sub"])
    true_tsw = float(params["T_sw"])
    sens = config["sensitivity"]
    frac = float(sens["gamma_fraction"])
    dt = float(sens["T_sw_delta_K"])
    n_obs = int(sens["observation_count"])
    t_max = float(item.get("t_max", target["t"][-1]))
    base_overrides = dict(item.get("params", {}))
    sim = _protocol_sim_config(config, item)
    gamma_hi = simulate_with_overrides(params, sim, gamma_sub=true_gamma * (1.0 + frac), t_max=t_max, param_overrides=base_overrides)
    gamma_lo = simulate_with_overrides(params, sim, gamma_sub=true_gamma * (1.0 - frac), t_max=t_max, param_overrides=base_overrides)
    tsw_hi = simulate_with_overrides(params, sim, gamma_sub=true_gamma, t_max=t_max, param_overrides={**base_overrides, "T_sw": true_tsw + dt})
    tsw_lo = simulate_with_overrides(params, sim, gamma_sub=true_gamma, t_max=t_max, param_overrides={**base_overrides, "T_sw": true_tsw - dt})
    gamma_sens = (_response_vector(gamma_hi, n_obs) - _response_vector(gamma_lo, n_obs)) / max(2.0 * frac, 1.0e-30)
    tsw_sens = (_response_vector(tsw_hi, n_obs) - _response_vector(tsw_lo, n_obs)) / max(2.0 * dt, 1.0e-30)
    norm_gamma = float(np.linalg.norm(gamma_sens))
    norm_tsw = float(np.linalg.norm(tsw_sens))
    cosine = _cosine(gamma_sens, tsw_sens)
    distinguish = float(norm_gamma * (1.0 - abs(cosine)))
    expected_error = float(1.0 / max(distinguish, 1.0e-12))
    recommended = bool(norm_gamma >= float(sens["recommendation_min_gamma_norm"]) and abs(cosine) <= float(sens["recommendation_max_abs_cosine"]))
    row = {
        "protocol_name": str(item["name"]),
        "protocol": str(item["protocol"]),
        "sensitivity_norm_gamma_sub": norm_gamma,
        "sensitivity_norm_T_sw": norm_tsw,
        "sensitivity_angle_or_cosine": cosine,
        "distinguishability_score": distinguish,
        "expected_gamma_error_proxy": expected_error,
        "recommended_for_gamma_sub_inversion": recommended,
    }
    row["finite_result"] = finite_row(row, ["sensitivity_norm_gamma_sub", "sensitivity_norm_T_sw", "sensitivity_angle_or_cosine", "distinguishability_score", "expected_gamma_error_proxy"])
    return row


def run_protocol_observability_design(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = resolve(config_path)
    config = load_yaml(config_path)
    target_path = resolve(config["base_target_npz"])
    obs_path = resolve(config["base_sparse_obs_npz"])
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    rows = [_run_protocol(config, target, dict(item)) for item in config["protocols"]]
    after = ensure_frozen_inputs(target_path, obs_path)
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = bool(frozen)
    rows = sorted(rows, key=lambda row: float(row["distinguishability_score"]), reverse=True)
    best = rows[0]
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin protocol observability design preflight; not experimental data.",
        "scope": "Finite-difference sensitivity design audit for candidate stimulation protocols; no frozen GT revision and no training.",
        "config_path": display_path(config_path),
        "num_protocols": len(rows),
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "frozen_gt_unchanged": bool(frozen),
        "best_protocol_by_distinguishability": best,
        "recommended_protocols": [row["protocol_name"] for row in rows if bool(row["recommended_for_gamma_sub_inversion"])],
        "key_interpretation": "Protocols with larger gamma_sub sensitivity and lower alignment with T_sw sensitivity are better candidates for constrained gamma_sub inversion.",
        "rows": rows,
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "outputs": {"summary_json": config["summary_json"], "cases_csv": config["cases_csv"]},
    }
    write_json(config["summary_json"], summary)
    write_csv(config["cases_csv"], rows, CSV_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_protocol_observability_design(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "cases_csv": summary["outputs"]["cases_csv"], "best_protocol": summary["best_protocol_by_distinguishability"]["protocol_name"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
