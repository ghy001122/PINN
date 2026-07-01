"""Sequential protocol design preflight for constrained gamma_sub inversion.

The scoring is response-surface based and synthetic numerical digital-twin
evidence only. It is intended to rank protocol-design hypotheses, not to claim
new experimental protocol optimization.
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

from scripts.gamma_sub_high_throughput_common import (
    load_yaml,
    read_json,
    response_surface_relative_error,
    write_csv,
    write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_sequential_protocol_design.yaml")
CASE_FIELDS = [
    "candidate_name",
    "stage1_protocol",
    "stage2_protocol",
    "stage1_ridge_width_reduction",
    "effective_T_sw_prior_width",
    "stage2_gamma_error",
    "final_recoverable_le_0p1",
    "final_recoverable_le_0p2",
    "value_of_information_score",
    "cost_normalized_score",
    "improvement_over_best_single",
    "improvement_over_ltp_ltd_only",
    "protocol_cost",
    "finite_result",
]


def _protocol_for_surface(protocol: str) -> str:
    mapping = {
        "short_pulse": "ltp_ltd",
        "long_pulse": "ltp_ltd",
        "multi_pulse": "mixed_protocol",
        "mixed_amplitude_pulse": "mixed_protocol",
        "triangle_high_amplitude": "triangle",
        "triangle_low_amplitude": "triangle",
        "best_single_protocol": "ltp_ltd",
    }
    return mapping.get(protocol, protocol)


def _stage1_reduction(stage1: str | None, proxy_scores: dict[str, float]) -> float:
    if not stage1:
        return 0.0
    max_proxy = max(max(proxy_scores.values()), 1.0e-12)
    score = float(proxy_scores.get(stage1, 0.0)) / max_proxy
    # Conservative preflight model: a strong first protocol can shrink the
    # gamma_sub/T_sw ridge, but never fully removes prior ambiguity.
    return float(np.clip(0.10 + 0.45 * score, 0.0, 0.55))


def _cost(stage1: str | None, stage2: str, costs: dict[str, float]) -> float:
    total = float(costs.get(stage2, 1.0))
    if stage1:
        total += float(costs.get(stage1, 1.0))
    return total


def run_sequential_protocol_design(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    actual = read_json(cfg["protocol_actual_summary"])
    weighted = read_json(cfg["weighted_objective_summary"])
    by_protocol = dict(actual["by_protocol"])
    proxy_scores = {name: float(stats.get("proxy_distinguishability_score", 0.0)) for name, stats in by_protocol.items()}
    best_actual_protocol = str(actual.get("best_protocol_by_actual_error", "short_pulse"))
    best_single_error = float(weighted["best_single_protocol_case"]["relative_error"])
    ltp_ltd_error = float(weighted["best_single_protocol_case"]["relative_error"])
    base_width = float(cfg["base_T_sw_prior_width"])
    base_delta = float(cfg["base_T_sw_delta_K"])
    n_obs = int(cfg["observation_count"])
    noise = float(cfg["noise"])
    costs = {str(key): float(value) for key, value in dict(cfg.get("costs", {})).items()}

    rows: list[dict[str, Any]] = []
    for item in cfg["candidates"]:
        name = str(item["name"])
        stage1 = item.get("stage1")
        stage2 = str(item["stage2"])
        if stage2 == "best_single_protocol":
            stage2 = best_actual_protocol
        reduction = _stage1_reduction(stage1, proxy_scores)
        effective_width = float(base_width * (1.0 - reduction))
        surface_protocol = _protocol_for_surface(stage2)
        stage2_error = response_surface_relative_error(surface_protocol, base_delta, effective_width, n_obs, noise)
        # Keep single-protocol references anchored to the prior weighted audit.
        if item.get("stage1") is None and str(item["stage2"]) == "ltp_ltd":
            stage2_error = ltp_ltd_error
        if item.get("stage1") is None and str(item["stage2"]) == "best_single_protocol":
            stage2_error = best_single_error
        voi = float(max(ltp_ltd_error - stage2_error, 0.0))
        protocol_cost = _cost(stage1, stage2, costs)
        rows.append(
            {
                "candidate_name": name,
                "stage1_protocol": "" if stage1 is None else str(stage1),
                "stage2_protocol": stage2,
                "stage1_ridge_width_reduction": reduction,
                "effective_T_sw_prior_width": effective_width,
                "stage2_gamma_error": stage2_error,
                "final_recoverable_le_0p1": bool(stage2_error <= 0.1),
                "final_recoverable_le_0p2": bool(stage2_error <= 0.2),
                "value_of_information_score": voi,
                "cost_normalized_score": float(voi / max(protocol_cost, 1.0e-12)),
                "improvement_over_best_single": bool(stage2_error < best_single_error),
                "improvement_over_ltp_ltd_only": bool(stage2_error < ltp_ltd_error),
                "protocol_cost": protocol_cost,
                "finite_result": bool(np.isfinite([reduction, effective_width, stage2_error, voi, protocol_cost]).all()),
            }
        )

    finite_rows = [row for row in rows if row["finite_result"]]
    best_by_error = min(finite_rows, key=lambda row: float(row["stage2_gamma_error"])) if finite_rows else None
    best_by_cost = max(finite_rows, key=lambda row: float(row["cost_normalized_score"])) if finite_rows else None
    improves_best_single = bool(best_by_error and float(best_by_error["stage2_gamma_error"]) < best_single_error)
    improves_ltp_ltd = bool(best_by_error and float(best_by_error["stage2_gamma_error"]) < ltp_ltd_error)
    if improves_best_single or improves_ltp_ltd:
        interpretation = (
            "Sequential protocol design improves the response-surface preflight score in the current bounded model, "
            "but it remains a protocol-design hypothesis that needs simulator-backed validation before a strong claim."
        )
    else:
        interpretation = (
            "Sequential protocol design did not improve recovery under the current response surface, suggesting "
            "calibration quality dominates protocol order."
        )

    summary = {
        "benchmark": cfg.get("benchmark", "gamma_sub_sequential_protocol_design"),
        "note": "Synthetic numerical digital-twin sequential protocol design preflight; not experimental data.",
        "num_candidates": len(rows),
        "best_single_protocol_reference": best_actual_protocol,
        "best_single_protocol_relative_error": best_single_error,
        "ltp_ltd_only_relative_error": ltp_ltd_error,
        "best_candidate_by_gamma_error": best_by_error,
        "best_candidate_by_cost_normalized_score": best_by_cost,
        "whether_sequential_design_improves_over_best_single": improves_best_single,
        "whether_sequential_design_improves_over_ltp_ltd_only": improves_ltp_ltd,
        "interpretation": interpretation,
        "claim_boundary": cfg.get("claim_boundary", ""),
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    write_csv(cfg["cases_csv"], rows, CASE_FIELDS)
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_sequential_protocol_design(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "cases_csv": summary["outputs"]["cases_csv"],
                "best_candidate": summary["best_candidate_by_gamma_error"]["candidate_name"],
                "improves_over_best_single": summary["whether_sequential_design_improves_over_best_single"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
