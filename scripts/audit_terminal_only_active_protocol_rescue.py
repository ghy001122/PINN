"""Active terminal-only multi-protocol rescue audit.

The audit targets low-dimensional parameter recovery from synthetic terminal
protocols. It does not claim arbitrary full-field recovery.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/terminal_only_active_protocol_rescue_summary.json")
CASES_CSV = Path("outputs/tables/terminal_only_active_protocol_rescue_cases.csv")
FIG_GAIN = Path("outputs/figures/terminal_only_active_protocol_gain.png")
PROTOCOLS = ["single_pulse", "multi_amplitude", "multi_width", "hysteresis_minor_loop", "oscillation_frequency_readout", "combined_terminal_protocol"]
PARAMS = ["Rth", "Rc", "Tsw", "Ea", "h_sub", "latent_field_code"]
TRUE = np.asarray([1.0, 0.6, 0.4, 0.7, 0.5, 0.35], dtype=float)
CSV_FIELDS = ["protocol", "noise", "seed", "parameter_median_error", "latent_field_error", "success", "latent_success", "objective_value", "finite_result", "claim_status"]


def _feature_matrix(protocol: str) -> np.ndarray:
    rows = []
    if protocol == "single_pulse":
        rows = [[0.8, 0.2, 0.7, 0.1, 0.2, 0.0], [0.4, 0.6, 0.2, 0.5, 0.1, 0.0]]
    elif protocol == "multi_amplitude":
        rows = [[0.9, 0.2, 0.3, 0.2, 0.2, 0.0], [0.5, 0.7, 0.5, 0.4, 0.1, 0.0], [0.2, 0.8, 0.7, 0.1, 0.3, 0.0]]
    elif protocol == "multi_width":
        rows = [[0.7, 0.1, 0.8, 0.1, 0.5, 0.0], [0.6, 0.2, 0.2, 0.6, 0.6, 0.0], [0.5, 0.3, 0.5, 0.4, 0.4, 0.0]]
    elif protocol == "hysteresis_minor_loop":
        rows = [[0.2, 0.4, 0.9, 0.6, 0.2, 0.0], [0.3, 0.5, 0.7, 0.8, 0.3, 0.0], [0.4, 0.3, 0.6, 0.5, 0.2, 0.0]]
    elif protocol == "oscillation_frequency_readout":
        rows = [[0.9, 0.1, 0.5, 0.3, 0.8, 0.2], [0.7, 0.2, 0.4, 0.5, 0.9, 0.3], [0.5, 0.3, 0.2, 0.4, 0.7, 0.4]]
    elif protocol == "combined_terminal_protocol":
        for p in PROTOCOLS[:-1]:
            rows.extend(_feature_matrix(p).tolist())
        rows.extend([[0.1, 0.1, 0.2, 0.2, 0.1, 0.8], [0.2, 0.3, 0.1, 0.1, 0.2, 1.0]])
    else:
        raise ValueError(protocol)
    return np.asarray(rows, dtype=float)


def _observe(params: np.ndarray, protocol: str) -> np.ndarray:
    A = _feature_matrix(protocol)
    linear = A @ params
    nonlinear = 0.08 * np.sin(A @ (params * np.asarray([1.1, 0.7, 1.3, 0.9, 1.2, 0.6])))
    return linear + nonlinear


def _invert(protocol: str, noise: float, seed: int) -> dict[str, Any]:
    y_true = _observe(TRUE, protocol)
    rng = np.random.default_rng(seed + len(protocol))
    y = y_true + noise * max(float(np.std(y_true)), 1.0e-9) * rng.standard_normal(y_true.shape)
    A = _feature_matrix(protocol)
    # Linearized inversion. Low-dimensional terminal parameters only.
    lam = 0.02 if protocol != "combined_terminal_protocol" else 0.004
    est = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ y)
    obj = float(np.mean((_observe(est, protocol) - y) ** 2))
    rel = np.abs(est[:5] - TRUE[:5]) / np.maximum(np.abs(TRUE[:5]), 1.0e-9)
    latent = float(abs(est[5] - TRUE[5]) / max(abs(TRUE[5]), 1.0e-9))
    param_med = float(np.median(rel))
    success = bool(param_med <= 0.20)
    latent_success = bool(latent <= 0.30)
    status = "qualified_supported" if success else ("failed_but_informative" if param_med <= 0.45 else "forbidden")
    return {"protocol": protocol, "noise": float(noise), "seed": int(seed), "parameter_median_error": param_med, "latent_field_error": latent, "success": success, "latent_success": latent_success, "objective_value": obj, "finite_result": bool(np.isfinite([param_med, latent, obj]).all()), "claim_status": status}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in CSV_FIELDS})


def _plot(summary: dict[str, Any]) -> None:
    FIG_GAIN.parent.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(PROTOCOLS)); vals = [summary["median_parameter_error_by_protocol"][p] for p in PROTOCOLS]
    fig, ax = plt.subplots(figsize=(8.5, 4.0)); ax.bar(x, vals); ax.axhline(0.20, color="black", linestyle="--")
    ax.set_xticks(x); ax.set_xticklabels(PROTOCOLS, rotation=35, ha="right")
    ax.set_ylabel("median parameter error"); ax.set_title("Active terminal-only protocol rescue")
    fig.tight_layout(); fig.savefig(ROOT / FIG_GAIN, dpi=150); plt.close(fig)


def run_terminal_only_active_protocol_rescue() -> dict[str, Any]:
    rows = [_invert(protocol, noise, seed) for protocol in PROTOCOLS for noise in [0.0, 0.02, 0.05] for seed in [2026, 2027]]
    median_error = {p: float(np.median([r["parameter_median_error"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    success_rate = {p: float(np.mean([r["success"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    latent_error = {p: float(np.median([r["latent_field_error"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    best = min(PROTOCOLS, key=lambda p: median_error[p])
    status = "qualified_supported" if median_error[best] <= 0.20 and success_rate[best] >= 0.70 else "failed_but_informative"
    summary = {"benchmark": "terminal_only_active_protocol_rescue", "note": "Synthetic numerical terminal-protocol audit; supports only low-dimensional diagnosis if gates clear.", "num_cases": len(rows), "best_protocol": best, "median_parameter_error_by_protocol": median_error, "success_rate_by_protocol": success_rate, "median_latent_field_error_by_protocol": latent_error, "parameter_recovery_status": status, "single_trace_arbitrary_full_field_status": "forbidden", "forbidden_claims": ["single-trace arbitrary full-field recovery", "experimental validation"], "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/"), "gain_figure": str(FIG_GAIN).replace("\\", "/")}}
    _write_cases(ROOT / CASES_CSV, rows); _plot(summary); write_json(ROOT / SUMMARY_JSON, summary); return summary


def main() -> None:
    argparse.ArgumentParser().parse_args(); print(run_terminal_only_active_protocol_rescue())


if __name__ == "__main__":
    main()
