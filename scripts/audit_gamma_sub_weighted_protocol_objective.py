"""Audit weighted protocol objectives for constrained gamma_sub inversion."""

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
    TRUE_GAMMA,
    gamma_estimate_from_relative_error,
    load_yaml,
    read_json,
    response_surface_relative_error,
    scenario_delta_width,
    write_csv,
    write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_weighted_protocol_objective.yaml")
CASE_FIELDS = [
    "combination_name",
    "protocol_weights",
    "resolved_protocols",
    "scenario",
    "observation_count",
    "noise",
    "gamma_true",
    "gamma_est",
    "relative_error",
    "recoverable_le_0p1",
    "recoverable_le_0p2",
    "finite_result",
    "source",
]


def _resolve_protocol_name(name: str, actual_summary: dict[str, Any]) -> str:
    if name == "best_actual_protocol":
        return str(actual_summary["best_protocol_by_actual_error"])
    aliases = {
        "triangle": "triangle",
        "ltp_ltd": "ltp_ltd",
        "multi_pulse": "ltp_ltd",
        "long_pulse": "ltp_ltd",
        "short_pulse": "ltp_ltd",
    }
    return aliases.get(name, name)


def run_weighted_protocol_objective(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    actual_summary = read_json(cfg["protocol_actual_summary_json"])
    delta, width = scenario_delta_width(str(cfg["scenario"]))
    rows: list[dict[str, Any]] = []
    for combo_name, weights in dict(cfg["combinations"]).items():
        total_w = float(sum(float(v) for v in weights.values()))
        resolved: dict[str, float] = {}
        weighted_error = 0.0
        for protocol_name, raw_weight in weights.items():
            family = _resolve_protocol_name(str(protocol_name), actual_summary)
            weight = float(raw_weight) / max(total_w, 1.0e-30)
            resolved[family] = resolved.get(family, 0.0) + weight
            weighted_error += weight * response_surface_relative_error(family, delta, width, int(cfg["observation_count"]), float(cfg["noise"]))
        rel = float(np.clip(weighted_error, 0.0, 1.2222222222222223))
        rows.append(
            {
                "combination_name": combo_name,
                "protocol_weights": json.dumps(weights, sort_keys=True),
                "resolved_protocols": json.dumps(resolved, sort_keys=True),
                "scenario": cfg["scenario"],
                "observation_count": int(cfg["observation_count"]),
                "noise": float(cfg["noise"]),
                "gamma_true": TRUE_GAMMA,
                "gamma_est": gamma_estimate_from_relative_error(rel, TRUE_GAMMA),
                "relative_error": rel,
                "recoverable_le_0p1": bool(rel <= 0.1),
                "recoverable_le_0p2": bool(rel <= 0.2),
                "finite_result": bool(np.isfinite(rel)),
                "source": "weighted_response_surface_objective",
            }
        )

    single_rows = [row for row in rows if row["combination_name"].endswith("_only")]
    best_single = min(single_rows, key=lambda row: float(row["relative_error"])) if single_rows else min(rows, key=lambda row: float(row["relative_error"]))
    best_combo = min(rows, key=lambda row: float(row["relative_error"]))
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin weighted-protocol audit; not experimental data.",
        "num_combinations": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "best_single_protocol_case": best_single,
        "best_weighted_case": best_combo,
        "improves_over_best_single": bool(float(best_combo["relative_error"]) < float(best_single["relative_error"])),
        "improvement_relative_error": float(float(best_single["relative_error"]) - float(best_combo["relative_error"])),
        "claim_boundary": "Weighted objectives are only justified if they improve or stabilize constrained gamma_sub recovery without widening unknown priors.",
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    write_json(cfg["summary_json"], summary)
    write_csv(cfg["cases_csv"], rows, CASE_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_weighted_protocol_objective(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "best_weighted_case": summary["best_weighted_case"]["combination_name"], "improves_over_best_single": summary["improves_over_best_single"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
