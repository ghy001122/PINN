"""Calibration-before-inversion workflow audit for gamma_sub."""

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

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_calibration_workflow.yaml")
FIELDS = ["workflow", "estimated_T_sw_offset", "T_sw_prior_width_after_calibration", "gamma_true", "gamma_est", "relative_error", "recoverable_le_0p1", "recoverable_le_0p2", "calibration_error_K", "calibration_cost_proxy", "total_protocol_cost_proxy", "finite_result"]


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


def run_tsw_calibration_workflow(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    true_gamma = float(cfg["true_gamma_sub"])
    rows = []
    for item in cfg["workflows"]:
        width = float(item["T_sw_prior_width_after_calibration"])
        calibration_error = float(item["calibration_error_K"])
        delta_scale = max(abs(float(cfg["T_sw_delta_K"])), 1.0e-30)
        effective_width = max(width, calibration_error / delta_scale)
        rel = response_surface_relative_error(str(cfg["protocol"]), float(cfg["T_sw_delta_K"]), effective_width, int(cfg["observation_count"]), float(cfg["noise"]))
        gamma_est = gamma_estimate_from_relative_error(rel, true_gamma)
        row = {"workflow": str(item["workflow"]), "estimated_T_sw_offset": float(item["estimated_T_sw_offset"]), "T_sw_prior_width_after_calibration": width, "gamma_true": true_gamma, "gamma_est": gamma_est, "relative_error": rel, "recoverable_le_0p1": bool(rel <= 0.1), "recoverable_le_0p2": bool(rel <= 0.2), "calibration_error_K": calibration_error, "calibration_cost_proxy": float(item["calibration_cost_proxy"]), "total_protocol_cost_proxy": float(item["calibration_cost_proxy"]) + float(item["protocol_cost_proxy"]), "finite_result": bool(np.isfinite([rel, gamma_est, width, calibration_error]).all())}
        rows.append(row)
    no_cal = next(row for row in rows if row["workflow"] == "no_calibration_direct_gamma")
    calibrated = [row for row in rows if row["workflow"] not in {"no_calibration_direct_gamma", "oracle_T_sw", "wrong_calibration_control"}]
    best = min(calibrated, key=lambda row: float(row["relative_error"]))
    oracle = next(row for row in rows if row["workflow"] == "oracle_T_sw")
    reliable = [row for row in rows if row["recoverable_le_0p1"] and row["workflow"] not in {"oracle_T_sw", "wrong_calibration_control"}]
    min_acc = min((float(row["calibration_error_K"]) for row in reliable), default=None)
    summary = {"benchmark": cfg.get("benchmark"), "note": "Synthetic numerical digital-twin calibration-before-inversion workflow; not experimental data.", "whether_calibration_before_inversion_improves_recovery": bool(best["relative_error"] < no_cal["relative_error"]), "best_workflow": best["workflow"], "minimum_calibration_accuracy_needed": min_acc, "improvement_over_no_calibration": float(no_cal["relative_error"] - best["relative_error"]), "oracle_relative_error": float(oracle["relative_error"]), "manuscript_method_sentence": "A low-disturbance T_sw calibration/probe step should precede gamma_sub inversion; otherwise switching-temperature mismatch dominates the terminal response.", "limitation": "Workflow evidence is synthetic response-surface evidence and estimates only gamma_sub after T_sw constraint.", "all_finite_results": bool(all(row["finite_result"] for row in rows)), "rows": rows, "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]}}
    _write_csv(_resolve(cfg["cases_csv"]), rows)
    out = _resolve(cfg["summary_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_tsw_calibration_workflow(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

