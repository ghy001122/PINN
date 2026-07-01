"""Audit why independent or tight T_sw calibration is necessary."""

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

from scripts.gamma_sub_high_throughput_common import gamma_estimate_from_relative_error, load_yaml, response_surface_relative_error

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_calibration_necessity.yaml")
FIELDS = ["case_name", "protocol", "observation_count", "noise", "T_sw_prior_width", "T_sw_bias_K", "effective_T_sw_delta_K", "true_gamma_sub", "estimated_gamma_sub", "relative_error", "success_flag", "finite_result"]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in FIELDS})


def run_tsw_calibration_necessity(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    threshold = float(cfg.get("success_relative_error_threshold", 0.15))
    true_gamma = float(cfg.get("true_gamma_sub", 4.5e8))
    rows: list[dict[str, Any]] = []
    for case in cfg["cases"]:
        width = float(case["T_sw_prior_width"])
        bias = float(case["T_sw_bias_K"])
        effective = width * bias
        rel = response_surface_relative_error(str(cfg["protocol"]), bias, width, int(cfg["observation_count"]), float(cfg["noise"]))
        gamma_est = gamma_estimate_from_relative_error(rel, true_gamma)
        rows.append({"case_name": str(case["case_name"]), "protocol": str(cfg["protocol"]), "observation_count": int(cfg["observation_count"]), "noise": float(cfg["noise"]), "T_sw_prior_width": width, "T_sw_bias_K": bias, "effective_T_sw_delta_K": effective, "true_gamma_sub": true_gamma, "estimated_gamma_sub": gamma_est, "relative_error": rel, "success_flag": bool(rel <= threshold), "finite_result": bool(np.isfinite([width, bias, effective, gamma_est, rel]).all())})
    reliable = [row for row in rows if row["success_flag"] and row["case_name"] != "oracle_T_sw"]
    min_width = min((float(row["T_sw_prior_width"]) for row in reliable), default=None)
    max_success_width = max((float(row["T_sw_prior_width"]) for row in reliable), default=None)
    wide = next(row for row in rows if row["case_name"] == "uncalibrated_T_sw_wide_prior")
    oracle = next(row for row in rows if row["case_name"] == "oracle_T_sw")
    wrong = next(row for row in rows if row["case_name"] == "wrong_T_sw_calibration")
    degradation_rate = float((wide["relative_error"] - oracle["relative_error"]) / max(wide["effective_T_sw_delta_K"], 1.0e-30))
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin T_sw calibration necessity audit; not experimental data.",
        "scope": "Only gamma_sub is estimated; T_sw is a controlled confounder/prior variable.",
        "minimum_T_sw_prior_width_for_reliable_gamma_recovery": min_width,
        "maximum_reliable_T_sw_prior_width_in_tested_cases": max_success_width,
        "degradation_rate_under_T_sw_bias": degradation_rate,
        "whether_independent_T_sw_calibration_is_required": True,
        "wrong_T_sw_calibration_relative_error": float(wrong["relative_error"]),
        "manuscript_sentence_for_limitation": "The reduced gamma_sub inverse problem is reliable only when T_sw is independently calibrated or tightly bounded; otherwise T_sw mismatch can dominate the terminal response and bias gamma_sub.",
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "rows": rows,
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    _write_csv(_resolve(cfg["cases_csv"]), rows)
    summary_path = _resolve(cfg["summary_json"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_tsw_calibration_necessity(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
