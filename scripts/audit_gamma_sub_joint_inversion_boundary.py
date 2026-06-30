"""Joint inversion boundary audit for constrained gamma_sub recovery.

The audit compares candidate-grid releases of nuisance parameters while the
reported inverse target remains `gamma_sub`. It is intended to show conditional
recoverability boundaries, not arbitrary joint identifiability.
"""

from __future__ import annotations

import argparse
import itertools
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
        observation_times,
        port_series,
        relative_error,
        resolve,
        simulate_with_overrides,
        write_csv,
        write_json,
    )

DEFAULT_CONFIG = Path("configs/gamma_sub_joint_inversion_boundary.yaml")
CSV_FIELDS = [
    "case_name",
    "released_parameters",
    "gamma_true",
    "gamma_est",
    "relative_error",
    "nuisance_true",
    "nuisance_est",
    "objective",
    "G_loss",
    "I_loss",
    "number_of_near_equivalent_solutions",
    "ambiguity_score",
    "recoverable_le_0p1",
    "recoverable_le_0p2",
    "finite_result",
    "frozen_inputs_unchanged",
]


def _loss(pred_g: np.ndarray, pred_i: np.ndarray, target_g: np.ndarray, target_i: np.ndarray, weights: dict[str, Any]) -> dict[str, float]:
    denom_g = max(float(np.sqrt(np.mean(target_g**2))), 1.0e-30)
    denom_i = max(float(np.sqrt(np.mean(target_i**2))), 1.0e-30)
    g_loss = float(np.sqrt(np.mean((pred_g - target_g) ** 2)) / denom_g) ** 2
    i_loss = float(np.sqrt(np.mean((pred_i - target_i) ** 2)) / denom_i) ** 2
    return {"objective": float(weights.get("w_g", 1.0)) * g_loss + float(weights.get("w_i", 0.5)) * i_loss, "G_loss": float(g_loss), "I_loss": float(i_loss)}


def _released_params(case_name: str) -> list[str]:
    mapping = {
        "gamma_only": [],
        "gamma_plus_T_sw": ["T_sw"],
        "gamma_plus_tau_m": ["tau_m"],
        "gamma_plus_sigma_on0": ["sigma_on0"],
        "gamma_plus_eta_A": ["eta_A"],
        "gamma_plus_T_sw_plus_tau_m": ["T_sw", "tau_m"],
        "gamma_plus_T_sw_plus_sigma_on0": ["T_sw", "sigma_on0"],
    }
    if case_name not in mapping:
        raise ValueError(f"Unsupported case: {case_name}")
    return mapping[case_name]


def _parameter_options(config: dict[str, Any], base_params: dict[str, Any], released: list[str]) -> list[dict[str, Any]]:
    grids = config["released_parameter_grids"]
    options: list[list[dict[str, Any]]] = []
    for name in released:
        if name == "T_sw":
            options.append([{"T_sw_offset_K": float(offset), "T_sw": float(base_params["T_sw"]) + float(offset)} for offset in grids["T_sw_offset_K"]])
        elif name == "tau_m":
            options.append([{"tau_m_scale": float(scale), "tau_m": float(base_params["tau_m"]) * float(scale)} for scale in grids["tau_m_scale"]])
        elif name == "sigma_on0":
            opts = []
            for scale in grids["sigma_on0_scale"]:
                scale = float(scale)
                opts.append({"sigma_on0_scale": scale, "sigma_on0": float(base_params["sigma_on0"]) * scale, "nb_oxide_sigma_on0": float(base_params.get("nb_oxide_sigma_on0", base_params["sigma_on0"])) * scale, "v2o5_sigma_on0": float(base_params.get("v2o5_sigma_on0", base_params["sigma_on0"])) * scale})
            options.append(opts)
        elif name == "eta_A":
            options.append([{"eta_A_scale": float(scale), "eta_A": float(base_params["eta_A"]) * float(scale)} for scale in grids["eta_A_scale"]])
        else:
            raise ValueError(f"Unsupported released parameter: {name}")
    if not options:
        return [{}]
    combos = []
    for product in itertools.product(*options):
        merged: dict[str, Any] = {}
        for item in product:
            merged.update(item)
        combos.append(merged)
    return combos


def _nuisance_true(base_params: dict[str, Any], released: list[str]) -> dict[str, float]:
    return {name: float(base_params[name]) for name in released}


def _nuisance_est(best_overrides: dict[str, Any], released: list[str]) -> dict[str, float]:
    out = {}
    for name in released:
        if name in best_overrides:
            out[name] = float(best_overrides[name])
        elif name == "T_sw" and "T_sw_offset_K" in best_overrides:
            out[name] = float(best_overrides["T_sw_offset_K"])
        elif name == "tau_m" and "tau_m_scale" in best_overrides:
            out[name] = float(best_overrides["tau_m_scale"])
        elif name == "sigma_on0" and "sigma_on0_scale" in best_overrides:
            out[name] = float(best_overrides["sigma_on0_scale"])
        elif name == "eta_A" and "eta_A_scale" in best_overrides:
            out[name] = float(best_overrides["eta_A_scale"])
    return out


def _run_case(config: dict[str, Any], target: dict[str, Any], case_name: str, obs_time: np.ndarray, target_g: np.ndarray, target_i: np.ndarray) -> dict[str, Any]:
    released = _released_params(case_name)
    true_gamma = float(target["params"]["gamma_sub"])
    rows: list[dict[str, Any]] = []
    for gamma in candidate_values(config, true_gamma):
        for overrides in _parameter_options(config, target["params"], released):
            candidate_overrides = {key: value for key, value in overrides.items() if key in {"T_sw", "tau_m", "sigma_on0", "nb_oxide_sigma_on0", "v2o5_sigma_on0", "eta_A"}}
            gt = simulate_with_overrides(dict(target["params"]), config["simulation"], gamma_sub=float(gamma), t_max=float(target["t"][-1]), param_overrides=candidate_overrides)
            pred_g, pred_i = port_series(gt, obs_time)
            loss = _loss(pred_g, pred_i, target_g, target_i, config["loss"])
            rows.append({"gamma_sub": float(gamma), "overrides": overrides, **loss})
    best = min(rows, key=lambda row: float(row["objective"]))
    objectives = [float(row["objective"]) for row in rows]
    min_obj = float(best["objective"])
    span = max(max(objectives) - min_obj, 1.0e-30)
    near_cut = min_obj + max(float(config["inverse"].get("near_equivalent_objective_ratio", 1.05)) - 1.0, 0.0) * max(min_obj, 1.0e-12) + 0.02 * span
    near = [row for row in rows if float(row["objective"]) <= near_cut]
    rel = relative_error(float(best["gamma_sub"]), true_gamma)
    row = {
        "case_name": case_name,
        "released_parameters": "+".join(released) if released else "none",
        "gamma_true": true_gamma,
        "gamma_est": float(best["gamma_sub"]),
        "relative_error": float(rel),
        "nuisance_true": json.dumps(_nuisance_true(target["params"], released), sort_keys=True),
        "nuisance_est": json.dumps(_nuisance_est(best["overrides"], released), sort_keys=True),
        "objective": float(best["objective"]),
        "G_loss": float(best["G_loss"]),
        "I_loss": float(best["I_loss"]),
        "number_of_near_equivalent_solutions": int(len(near)),
        "ambiguity_score": float(len(near) / max(len(rows), 1)),
        "recoverable_le_0p1": bool(rel <= 0.1 + 1.0e-15),
        "recoverable_le_0p2": bool(rel <= 0.2 + 1.0e-15),
    }
    row["finite_result"] = finite_row(row, ["gamma_est", "relative_error", "objective", "G_loss", "I_loss", "ambiguity_score"])
    return row


def run_joint_inversion_boundary(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = resolve(config_path)
    config = load_yaml(config_path)
    target_path = resolve(config["target_npz"])
    obs_path = resolve(config["sparse_obs_npz"])
    before = ensure_frozen_inputs(target_path, obs_path)
    target = load_target(target_path)
    _ = load_sparse_obs(obs_path)
    obs_time = observation_times(np.asarray(target["t"], dtype=float), int(config["inverse"].get("observation_count", 32)))
    target_g, target_i = port_series(target, obs_time)
    rows = [_run_case(config, target, str(case), obs_time, target_g, target_i) for case in config["cases"]]
    after = ensure_frozen_inputs(target_path, obs_path)
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = bool(frozen)
    worst_error = max(rows, key=lambda row: float(row["relative_error"]))
    most_ambiguous = max(rows, key=lambda row: float(row["ambiguity_score"]))
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin joint inversion boundary audit; not experimental data.",
        "scope": "Candidate-grid nuisance release while reporting only gamma_sub recoverability. This does not prove arbitrary joint identifiability.",
        "config_path": display_path(config_path),
        "target_npz": display_path(target_path),
        "sparse_obs_npz": display_path(obs_path),
        "num_cases": len(rows),
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "frozen_gt_unchanged": bool(frozen),
        "worst_relative_error_case": worst_error,
        "most_ambiguous_case": most_ambiguous,
        "key_interpretation": "Releasing nuisance parameters increases objective ambiguity; gamma_sub identifiability remains conditional on fixed or tightly bounded priors.",
        "forbidden_overclaim": "Do not claim arbitrary joint inverse identifiability of gamma_sub with switching, state, conductivity, or area parameters released.",
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
    summary = run_joint_inversion_boundary(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "cases_csv": summary["outputs"]["cases_csv"], "worst_case": summary["worst_relative_error_case"]["case_name"], "most_ambiguous_case": summary["most_ambiguous_case"]["case_name"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
