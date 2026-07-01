"""Validate protocol recommendations against actual-response-surface errors."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_high_throughput_common import (
    TRUE_GAMMA,
    correlation_spearman,
    gamma_estimate_from_relative_error,
    load_yaml,
    read_json,
    response_surface_relative_error,
    scenario_delta_width,
    write_csv,
    write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_protocol_actual_inversion_validation.yaml")
CASE_FIELDS = [
    "protocol_name",
    "protocol_family",
    "scenario",
    "T_sw_delta_K",
    "T_sw_prior_width",
    "observation_count",
    "noise",
    "gamma_true",
    "gamma_est",
    "relative_error",
    "recoverable_le_0p1",
    "recoverable_le_0p2",
    "proxy_distinguishability_score",
    "finite_result",
    "source",
]


def _proxy_scores(path: str) -> dict[str, float]:
    summary = read_json(path)
    scores = {}
    for row in summary.get("rows", []):
        scores[str(row["protocol_name"])] = float(row["distinguishability_score"])
    return scores


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return dict(grouped)


def run_protocol_actual_validation(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    proxy = _proxy_scores(cfg["protocol_design_summary_json"])
    family_map = dict(cfg.get("protocol_family_map", {}))
    rows: list[dict[str, Any]] = []
    for protocol_name in cfg["protocols"]:
        family = family_map.get(protocol_name, protocol_name)
        for scenario in cfg["scenarios"]:
            delta, width = scenario_delta_width(str(scenario))
            rel = response_surface_relative_error(family, delta, width, int(cfg["observation_count"]), float(cfg["noise"]))
            gamma_est = gamma_estimate_from_relative_error(rel, TRUE_GAMMA)
            rows.append(
                {
                    "protocol_name": protocol_name,
                    "protocol_family": family,
                    "scenario": scenario,
                    "T_sw_delta_K": delta,
                    "T_sw_prior_width": width,
                    "observation_count": int(cfg["observation_count"]),
                    "noise": float(cfg["noise"]),
                    "gamma_true": TRUE_GAMMA,
                    "gamma_est": gamma_est,
                    "relative_error": rel,
                    "recoverable_le_0p1": bool(rel <= 0.1),
                    "recoverable_le_0p2": bool(rel <= 0.2),
                    "proxy_distinguishability_score": float(proxy.get(protocol_name, 0.0)),
                    "finite_result": bool(np.isfinite([rel, gamma_est, proxy.get(protocol_name, 0.0)]).all()),
                    "source": "response_surface_protocol_validation",
                }
            )

    by_protocol: dict[str, Any] = {}
    for protocol, group in _group(rows, "protocol_name").items():
        errors = [float(row["relative_error"]) for row in group]
        by_protocol[protocol] = {
            "num_cases": len(group),
            "mean_relative_error": float(np.mean(errors)),
            "max_relative_error": float(np.max(errors)),
            "recoverable_rate_le_0p1": float(np.mean([bool(row["recoverable_le_0p1"]) for row in group])),
            "recoverable_rate_le_0p2": float(np.mean([bool(row["recoverable_le_0p2"]) for row in group])),
            "proxy_distinguishability_score": float(proxy.get(protocol, 0.0)),
        }
    proxy_values = [by_protocol[name]["proxy_distinguishability_score"] for name in by_protocol]
    actual_values = [-by_protocol[name]["mean_relative_error"] for name in by_protocol]
    ranking_corr = correlation_spearman(proxy_values, actual_values)
    best_actual = min(by_protocol, key=lambda key: by_protocol[key]["mean_relative_error"])
    best_proxy = max(by_protocol, key=lambda key: by_protocol[key]["proxy_distinguishability_score"])
    sorted_actual = sorted(by_protocol, key=lambda key: by_protocol[key]["mean_relative_error"])
    top_actual_half = set(sorted_actual[: max(1, len(sorted_actual) // 2)])
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin protocol validation; not experimental data.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "by_protocol": by_protocol,
        "best_protocol_by_actual_error": best_actual,
        "best_protocol_by_sensitivity_proxy": best_proxy,
        "ranking_correlation_between_proxy_and_actual": ranking_corr,
        "proxy_recommendation_validated_at_top_half": bool(best_proxy in top_actual_half),
        "corrected_recommended_protocols": [name for name, stats in by_protocol.items() if stats["recoverable_rate_le_0p2"] >= 0.5],
        "claim_boundary": "Protocol recommendations remain response-surface validation for constrained gamma_sub inversion only.",
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    write_json(cfg["summary_json"], summary)
    write_csv(cfg["cases_csv"], rows, CASE_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_protocol_actual_validation(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "best_protocol_by_actual_error": summary["best_protocol_by_actual_error"], "ranking_correlation": summary["ranking_correlation_between_proxy_and_actual"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
