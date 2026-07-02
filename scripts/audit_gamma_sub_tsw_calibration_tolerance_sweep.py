"""T_sw calibration tolerance sweep for constrained gamma_sub inversion."""

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

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_calibration_tolerance_sweep.yaml")
FIELDS = ["protocol", "calibration_error_K", "T_sw_prior_width_after_calibration", "effective_prior_width", "noise", "seed", "relative_error", "gamma_est", "success_le_0p1", "success_le_0p15", "success_le_0p2", "finite_result"]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row[key]), []).append(row)
    return out


def _rates(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    return {k: float(np.mean([bool(r["success_le_0p15"]) for r in vals])) for k, vals in _group(rows, key).items()}


def _medians(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    return {k: float(np.median([float(r["relative_error"]) for r in vals])) for k, vals in _group(rows, key).items()}


def run_tolerance_sweep(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    true_gamma = float(cfg["true_gamma_sub"])
    delta = max(abs(float(cfg["T_sw_delta_K"])), 1.0e-30)
    rows: list[dict[str, Any]] = []
    for spec in cfg["protocols"]:
        protocol = str(spec["protocol"])
        factor = float(spec.get("relative_protocol_factor", 1.0))
        response_protocol = "ltp_ltd" if protocol != "ltp_ltd" else protocol
        for cal_error in [float(v) for v in cfg["calibration_error_K"]]:
            for width in [float(v) for v in cfg["T_sw_prior_width_after_calibration"]]:
                effective_width = max(width, cal_error / delta)
                for noise in [float(v) for v in cfg["noise"]]:
                    for seed in [int(v) for v in cfg["seeds"]]:
                        jitter = 1.0 + 0.03 * noise * np.sin(seed % 997)
                        rel = response_surface_relative_error(response_protocol, float(cfg["T_sw_delta_K"]), effective_width, int(cfg["observation_count"]), noise)
                        rel = float(np.clip(rel * factor * jitter, 0.0, 1.2222222222222223))
                        rows.append({
                            "protocol": protocol,
                            "calibration_error_K": cal_error,
                            "T_sw_prior_width_after_calibration": width,
                            "effective_prior_width": effective_width,
                            "noise": noise,
                            "seed": seed,
                            "relative_error": rel,
                            "gamma_est": gamma_estimate_from_relative_error(rel, true_gamma),
                            "success_le_0p1": bool(rel <= 0.1),
                            "success_le_0p15": bool(rel <= 0.15),
                            "success_le_0p2": bool(rel <= 0.2),
                            "finite_result": bool(np.isfinite(rel)),
                        })
    success_by_error = _rates(rows, "calibration_error_K")
    success_by_width = _rates(rows, "T_sw_prior_width_after_calibration")
    med_by_error = _medians(rows, "calibration_error_K")
    med_by_width = _medians(rows, "T_sw_prior_width_after_calibration")
    max_error_ok = max((float(k) for k, v in med_by_error.items() if float(v) <= 0.15), default=None)
    max_width_ok = max((float(k) for k, v in med_by_width.items() if float(v) <= 0.15), default=None)
    by_protocol = _medians(rows, "protocol")
    advantage = float(by_protocol.get("ltp_ltd", 0.0) - by_protocol.get("calibrated_multi_pulse_to_ltp_ltd", by_protocol.get("ltp_ltd", 0.0)))
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic response-surface T_sw calibration tolerance audit; not experimental data.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "maximum_tolerable_calibration_error_for_le_0p15": max_error_ok,
        "maximum_tolerable_prior_width_for_le_0p15": max_width_ok,
        "success_rate_by_error_bin": success_by_error,
        "success_rate_by_prior_width": success_by_width,
        "median_error_by_error_bin": med_by_error,
        "median_error_by_prior_width": med_by_width,
        "median_error_by_protocol": by_protocol,
        "calibrated_protocol_advantage": advantage,
        "manuscript_sentence_for_calibration_requirement": f"In the synthetic tolerance sweep, gamma_sub recovery stays reliable only when residual T_sw error is about {max_error_ok} K or the post-calibration prior width is about {max_width_ok} or narrower under the configured <=15% error criterion.",
        "limitation": "This is response-surface evidence for a reduced scalar inverse target; it does not prove unconstrained joint identifiability or experimental calibration.",
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    _write_csv(cfg["cases_csv"], rows, FIELDS)
    out = _resolve(cfg["summary_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_tolerance_sweep(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
