"""Build a high-throughput recoverability phase diagram for gamma_sub.

This audit uses a response surface derived from already validated synthetic
digital-twin gamma_sub audits. It does not create experimental evidence and it
does not claim sparse-port full hidden-field recovery.
"""

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
    gamma_estimate_from_relative_error,
    load_yaml,
    response_surface_relative_error,
    write_csv,
    write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_recoverability_phase_diagram.yaml")
CASE_FIELDS = [
    "protocol",
    "T_sw_delta_K",
    "T_sw_prior_width",
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


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return float(sum(bool(row[key]) for row in rows) / len(rows))


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return dict(grouped)


def _critical_by_protocol(rows: list[dict[str, Any]], by: str, threshold_key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for protocol, group in _group(rows, "protocol").items():
        values = sorted({float(row[by]) for row in group})
        accepted: list[float] = []
        for value in values:
            sub = [row for row in group if float(row[by]) == value]
            if _rate(sub, threshold_key) >= 0.5:
                accepted.append(value)
        out[protocol] = max(accepted) if accepted else None
    return out


def run_recoverability_phase_diagram(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    sweep = dict(cfg["sweep"])
    rows: list[dict[str, Any]] = []
    for protocol in sweep["protocols"]:
        for delta in sweep["T_sw_delta_K"]:
            for width in sweep["T_sw_prior_width"]:
                for n_obs in sweep["observation_count"]:
                    for noise in sweep["noise"]:
                        rel = response_surface_relative_error(protocol, delta, width, int(n_obs), noise)
                        gamma_est = gamma_estimate_from_relative_error(rel, TRUE_GAMMA)
                        rows.append(
                            {
                                "protocol": protocol,
                                "T_sw_delta_K": float(delta),
                                "T_sw_prior_width": float(width),
                                "observation_count": int(n_obs),
                                "noise": float(noise),
                                "gamma_true": TRUE_GAMMA,
                                "gamma_est": gamma_est,
                                "relative_error": rel,
                                "recoverable_le_0p1": bool(rel <= 0.1),
                                "recoverable_le_0p2": bool(rel <= 0.2),
                                "finite_result": bool(np.isfinite([rel, gamma_est]).all()),
                                "source": "response_surface_from_validated_audits",
                            }
                        )

    by_protocol = {}
    for protocol, group in _group(rows, "protocol").items():
        errors = [float(row["relative_error"]) for row in group]
        by_protocol[protocol] = {
            "num_cases": len(group),
            "mean_relative_error": float(np.mean(errors)),
            "median_relative_error": float(np.median(errors)),
            "max_relative_error": float(np.max(errors)),
            "recoverable_rate_le_0p1": _rate(group, "recoverable_le_0p1"),
            "recoverable_rate_le_0p2": _rate(group, "recoverable_le_0p2"),
        }
    best_protocol = min(by_protocol, key=lambda key: by_protocol[key]["mean_relative_error"])
    worst_protocol = max(by_protocol, key=lambda key: by_protocol[key]["mean_relative_error"])
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin recoverability phase diagram; not experimental data.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "overall_recoverable_rate_le_0p1": _rate(rows, "recoverable_le_0p1"),
        "overall_recoverable_rate_le_0p2": _rate(rows, "recoverable_le_0p2"),
        "by_protocol": by_protocol,
        "best_protocol": best_protocol,
        "worst_protocol": worst_protocol,
        "critical_T_sw_prior_width_by_protocol_le_0p2": _critical_by_protocol(rows, "T_sw_prior_width", "recoverable_le_0p2"),
        "critical_noise_by_protocol_le_0p2": _critical_by_protocol(rows, "noise", "recoverable_le_0p2"),
        "manuscript_boundary": "Supports conditional gamma_sub recoverability under fixed or tightly bounded T_sw priors; does not support unconstrained joint inverse claims.",
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    write_json(cfg["summary_json"], summary)
    write_csv(cfg["cases_csv"], rows, CASE_FIELDS)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_recoverability_phase_diagram(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "num_cases": summary["num_cases"], "best_protocol": summary["best_protocol"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
