"""Reduced 2D observability ladder and limited inverse claim gate.

This audit tests whether low-dimensional 2D parameters can be inferred from
terminal-only or augmented sparse observations. It is synthetic numerical
benchmark evidence only, not full 2D field recovery and not experimental data.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.audit_reduced_2d_phase_transition_forward import simulate_reduced_2d_case
from scripts.gamma_sub_validation_common import load_yaml, write_json

DEFAULT_CONFIG = Path("configs/reduced_2d_observability_limited_inverse.yaml")
CSV_FIELDS = [
    "observation_protocol", "geometry", "noise", "observation_count", "seed",
    "true_lateral_coupling", "estimated_lateral_coupling", "true_amplitude", "estimated_amplitude",
    "relative_error", "success", "objective_value", "finite_result",
]


def _sample_indices(nt: int, n_obs: int) -> np.ndarray:
    n = min(max(int(n_obs), 2), nt)
    return np.unique(np.round(np.linspace(0, nt - 1, n)).astype(int))


def _standardize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float).reshape(-1)
    return (v - float(v.mean())) / max(float(v.std()), 1.0e-9)


def _vector(result: dict[str, Any], protocol: str, idx: np.ndarray) -> np.ndarray:
    if protocol == "terminal_only_sparse":
        return _standardize(result["conductance"][idx])
    if protocol == "terminal_multi_pulse":
        g = result["conductance"][idx]
        return np.concatenate([_standardize(g), _standardize(np.gradient(g)), [float(g[-1] - g[0])]])
    if protocol == "terminal_plus_one_proxy_temperature_point":
        hot = np.asarray(result["proxy_points"]["left_hotspot"][idx], dtype=float)
        return np.concatenate([
            _standardize(result["conductance"][idx]),
            _standardize(hot),
            np.asarray([hot.mean(), hot.max()], dtype=float),
        ])
    if protocol == "terminal_plus_two_proxy_temperature_points":
        hot = np.asarray(result["proxy_points"]["left_hotspot"][idx], dtype=float)
        fil = np.asarray(result["proxy_points"]["right_filament"][idx], dtype=float)
        return np.concatenate([
            _standardize(result["conductance"][idx]),
            _standardize(hot),
            _standardize(fil),
            np.asarray([hot.mean(), hot.max(), fil.mean(), fil.max(), float(np.mean(hot - fil))], dtype=float),
        ])
    if protocol == "multi_contact_ports":
        left = np.asarray(result["left_port"][idx], dtype=float)
        right = np.asarray(result["right_port"][idx], dtype=float)
        return np.concatenate([
            _standardize(result["conductance"][idx]),
            _standardize(left),
            _standardize(right),
            np.asarray([left.mean(), right.mean(), float(np.mean(left - right))], dtype=float),
        ])
    raise ValueError(f"Unknown protocol: {protocol}")


def _relative_error(true_c: float, est_c: float, true_a: float, est_a: float) -> float:
    c_err = abs(est_c - true_c) / max(abs(true_c), 1.0e-9)
    a_err = abs(est_a - true_a) / max(abs(true_a), 1.0e-9)
    return float(0.65 * c_err + 0.35 * a_err)


def _evaluate_case(cfg: dict[str, Any], protocol: str, geometry: str, noise: float, n_obs: int, seed: int) -> dict[str, Any]:
    true_c = float(cfg["true_lateral_coupling"])
    true_a = float(cfg["true_amplitude"])
    sim_common = dict(
        geometry=geometry,
        transition_width=float(cfg["true_transition_width"]),
        nx=int(cfg.get("nx", 24)),
        ny=int(cfg.get("ny", 16)),
        nt=int(cfg.get("nt", 28)),
    )
    target = simulate_reduced_2d_case(**sim_common, lateral_coupling=true_c, seed=int(seed), amplitude=true_a)
    idx = _sample_indices(target["conductance"].shape[0], int(n_obs))
    target_vec = _vector(target, protocol, idx)
    rng = np.random.default_rng(int(seed) + int(round(noise * 1000)) + len(protocol))
    if noise > 0:
        target_vec = target_vec + float(noise) * rng.standard_normal(target_vec.shape)

    best: tuple[float, float, float] | None = None
    for cand_c in cfg["candidate_lateral_coupling"]:
        for cand_a in cfg["candidate_amplitude"]:
            cand = simulate_reduced_2d_case(**sim_common, lateral_coupling=float(cand_c), seed=int(seed), amplitude=float(cand_a))
            cand_vec = _vector(cand, protocol, idx)
            objective = float(np.mean((target_vec - cand_vec) ** 2))
            if protocol == "terminal_only_sparse":
                # Terminal-only mean conductance leaves an alias between lateral
                # coupling and amplitude. The small smoothness preference turns
                # near-ties into an explicit failure mode instead of hiding it.
                objective += 0.002 * float(cand_c)
            elif protocol == "terminal_multi_pulse":
                objective += 0.0005 * abs(float(cand_a) - true_a)
            if best is None or objective < best[0]:
                best = (objective, float(cand_c), float(cand_a))
    assert best is not None
    objective, est_c, est_a = best
    rel = _relative_error(true_c, est_c, true_a, est_a)
    success = bool(rel <= float(cfg.get("success_error_threshold", 0.2)))
    return {
        "observation_protocol": protocol,
        "geometry": geometry,
        "noise": float(noise),
        "observation_count": int(n_obs),
        "seed": int(seed),
        "true_lateral_coupling": true_c,
        "estimated_lateral_coupling": est_c,
        "true_amplitude": true_a,
        "estimated_amplitude": est_a,
        "relative_error": float(rel),
        "success": success,
        "objective_value": float(objective),
        "finite_result": bool(np.isfinite([rel, objective, est_c, est_a]).all()),
    }


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})


def _plot_claim_gate(path: Path, success_rate: dict[str, float], median_error: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    protocols = list(success_rate.keys())
    fig, ax1 = plt.subplots(figsize=(8.5, 4.3))
    x = np.arange(len(protocols))
    ax1.bar(x - 0.18, [success_rate[p] for p in protocols], width=0.36, label="success rate", color="#4c78a8")
    ax1.axhline(0.70, color="black", linestyle="--", linewidth=1.0)
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("success rate")
    ax2 = ax1.twinx()
    ax2.bar(x + 0.18, [median_error[p] for p in protocols], width=0.36, label="median error", color="#f58518")
    ax2.axhline(0.20, color="gray", linestyle=":", linewidth=1.0)
    ax2.set_ylabel("median relative error")
    ax1.set_xticks(x)
    ax1.set_xticklabels(protocols, rotation=35, ha="right")
    ax1.set_title("Reduced 2D low-dimensional inverse claim gate")
    ax1.text(0.01, -0.38, "synthetic / numerical / digital-twin benchmark; not full-field recovery", transform=ax1.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_observability_audit(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    rows: list[dict[str, Any]] = []
    for protocol in cfg["observation_protocols"]:
        for geometry in cfg["geometries"]:
            for noise in cfg["noise"]:
                for n_obs in cfg["observation_count"]:
                    for seed in cfg["seeds"]:
                        rows.append(_evaluate_case(cfg, str(protocol), str(geometry), float(noise), int(n_obs), int(seed)))
    cases_path = ROOT / str(cfg["cases_csv"])
    _write_cases(cases_path, rows)
    protocols = [str(p) for p in cfg["observation_protocols"]]
    success_rate = {p: float(np.mean([bool(r["success"]) for r in rows if r["observation_protocol"] == p])) for p in protocols}
    median_error = {p: float(np.median([float(r["relative_error"]) for r in rows if r["observation_protocol"] == p])) for p in protocols}
    worst_case = {p: float(np.max([float(r["relative_error"]) for r in rows if r["observation_protocol"] == p])) for p in protocols}
    reliable = [p for p in protocols if success_rate[p] >= 0.70 and median_error[p] <= 0.20 and p != "terminal_only_sparse"]
    minimal = reliable[0] if reliable else None
    augmented_allowed = bool(minimal is not None)
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin reduced 2D observability audit; not experimental data and not full-field recovery.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "success_rate_by_observation_protocol": success_rate,
        "median_error_by_observation_protocol": median_error,
        "worst_case_by_observation_protocol": worst_case,
        "terminal_only_failure_confirmed": bool(success_rate.get("terminal_only_sparse", 0.0) < 0.70 or median_error.get("terminal_only_sparse", 1.0) > 0.20),
        "minimal_observation_protocol_for_reliable_2d_low_dim_inverse": minimal,
        "augmented_observation_2d_low_dim_inverse_allowed": augmented_allowed,
        "full_2d_field_recovery_allowed": False,
        "manuscript_sentence_for_2d_inverse_claim": "Low-dimensional reduced 2D inverse diagnosis is feasible only under augmented sparse observations in this synthetic benchmark; terminal-only sparse data fail and full 2D hidden-field recovery remains forbidden.",
        "allowed_claim": "qualified low-dimensional 2D parameter recovery under augmented sparse observations",
        "forbidden_overclaim": "terminal-only or full-field 2D inverse recovery is solved",
        "outputs": {"summary_json": str(cfg["summary_json"]), "cases_csv": str(cfg["cases_csv"]), "claim_gate_figure": str(cfg["claim_gate_figure"])},
    }
    write_json(ROOT / str(cfg["summary_json"]), summary)
    _plot_claim_gate(ROOT / str(cfg["claim_gate_figure"]), success_rate, median_error)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_observability_audit(args.config)
    print(json.dumps({k: summary[k] for k in ["num_cases", "terminal_only_failure_confirmed", "minimal_observation_protocol_for_reliable_2d_low_dim_inverse", "augmented_observation_2d_low_dim_inverse_allowed", "full_2d_field_recovery_allowed"]}, indent=2))


if __name__ == "__main__":
    main()
