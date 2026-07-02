"""Disentangle T_sw calibration gain from protocol-identity gain."""

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

DEFAULT_CONFIG = Path("configs/gamma_sub_calibration_protocol_disentanglement.yaml")
FIELDS = ["protocol", "response_protocol", "T_sw_prior_width_after_calibration", "calibration_error_K", "effective_prior_width", "noise", "seed", "relative_error", "gamma_est", "success_flag", "finite_result"]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in FIELDS})


def _median(rows: list[dict[str, Any]], **flt: Any) -> float:
    vals = [float(r["relative_error"]) for r in rows if all(r[k] == v for k, v in flt.items())]
    if not vals:
        return float("nan")
    return float(np.median(vals))


def _best_protocol(rows: list[dict[str, Any]], width: float, cal_error: float) -> tuple[str, float]:
    vals = []
    for protocol in sorted({r["protocol"] for r in rows}):
        vals.append((protocol, _median(rows, protocol=protocol, T_sw_prior_width_after_calibration=width, calibration_error_K=cal_error)))
    return min(vals, key=lambda item: item[1])


def run_disentanglement(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    true_gamma = float(cfg["true_gamma_sub"])
    delta = max(abs(float(cfg["T_sw_delta_K"])), 1.0e-30)
    threshold = float(cfg.get("success_threshold", 0.15))
    rows: list[dict[str, Any]] = []
    for spec in cfg["protocols"]:
        protocol = str(spec["protocol"])
        response_protocol = str(spec.get("response_protocol", protocol))
        factor = float(spec.get("relative_protocol_factor", 1.0))
        for width in [float(v) for v in cfg["T_sw_prior_width_after_calibration"]]:
            for cal_error in [float(v) for v in cfg["calibration_error_K"]]:
                effective_width = max(width, cal_error / delta)
                for noise in [float(v) for v in cfg["noise"]]:
                    for seed in [int(v) for v in cfg["seeds"]]:
                        rel = response_surface_relative_error(response_protocol, float(cfg["T_sw_delta_K"]), effective_width, int(cfg["observation_count"]), noise)
                        rel = float(np.clip(rel * factor * (1.0 + 0.03 * noise * np.cos(seed % 997)), 0.0, 1.2222222222222223))
                        rows.append({
                            "protocol": protocol,
                            "response_protocol": response_protocol,
                            "T_sw_prior_width_after_calibration": width,
                            "calibration_error_K": cal_error,
                            "effective_prior_width": effective_width,
                            "noise": noise,
                            "seed": seed,
                            "relative_error": rel,
                            "gamma_est": gamma_estimate_from_relative_error(rel, true_gamma),
                            "success_flag": bool(rel <= threshold),
                            "finite_result": bool(np.isfinite(rel)),
                        })
    baseline = _median(rows, protocol="ltp_ltd_only", T_sw_prior_width_after_calibration=1.0, calibration_error_K=0.4)
    calibrated_same_protocol = _median(rows, protocol="ltp_ltd_only", T_sw_prior_width_after_calibration=0.02, calibration_error_K=0.04)
    best_protocol, best_equal = _best_protocol(rows, width=0.02, cal_error=0.04)
    best_overall = min(float(r["relative_error"]) for r in rows)
    total_gain = baseline - best_overall
    calibration_gain = baseline - calibrated_same_protocol
    protocol_gain = calibrated_same_protocol - best_equal
    interaction_gain = total_gain - calibration_gain - protocol_gain
    survives = bool(best_protocol != "ltp_ltd_only" and protocol_gain > 0.01)
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic response-surface calibration-vs-protocol disentanglement audit; not experimental data.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "baseline_error": baseline,
        "best_overall_error": best_overall,
        "total_gain": float(total_gain),
        "calibration_gain": float(calibration_gain),
        "protocol_gain": float(protocol_gain),
        "interaction_gain": float(interaction_gain),
        "best_protocol_under_equal_prior": best_protocol,
        "best_equal_prior_error": best_equal,
        "whether_protocol_advantage_survives_equal_prior_control": survives,
        "whether_previous_protocol_claim_needs_qualification": bool(not survives or calibration_gain > protocol_gain),
        "manuscript_claim_update": "Protocol advantage survives equal-prior control but most improvement is still driven by T_sw calibration." if survives else "Most improvement is driven by T_sw calibration rather than protocol identity.",
        "limitation": "The decomposition uses response-surface evidence and equal-prior controls; it is not an experimental protocol proof.",
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    _write_csv(cfg["cases_csv"], rows)
    out = _resolve(cfg["summary_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_disentanglement(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
