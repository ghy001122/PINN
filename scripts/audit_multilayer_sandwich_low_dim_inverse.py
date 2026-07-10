"""Low-dimensional multilayer sandwich inverse smoke audit."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/multilayer_sandwich_low_dim_inverse_summary.json")
CASES_CSV = Path("outputs/tables/multilayer_sandwich_low_dim_inverse_cases.csv")
PARAMS = ["Rth_pcm_sub", "Rth_barrier", "Rc_te_pcm", "h_sub", "Tsw", "Ea"]
TRUE = np.asarray([0.8, 0.45, 0.35, 0.7, 0.5, 0.6], dtype=float)
CSV_FIELDS = ["protocol", "noise", "seed", "median_parameter_error", "max_parameter_error", "success", "objective_value", "finite_result", "claim_status"]


def _A(protocol: str) -> np.ndarray:
    if protocol == "short_pulse":
        return np.asarray([[0.9, 0.2, 0.6, 0.3, 0.5, 0.2], [0.8, 0.1, 0.3, 0.6, 0.2, 0.6], [0.2, 0.0, 0.7, 0.4, 0.3, 0.2]], dtype=float)
    if protocol == "ltp_ltd":
        return np.asarray([[0.5, 0.3, 0.4, 0.7, 0.8, 0.3], [0.4, 0.6, 0.2, 0.8, 0.5, 0.4], [0.3, 0.8, 0.3, 0.5, 0.7, 0.6]], dtype=float)
    if protocol == "combined":
        return np.vstack([_A("short_pulse"), _A("ltp_ltd"), [[0.2, 0.9, 0.8, 0.2, 0.6, 0.7], [0.7, 0.7, 0.2, 0.9, 0.4, 0.5]]])
    raise ValueError(protocol)


def _observe(params: np.ndarray, protocol: str) -> np.ndarray:
    A = _A(protocol)
    return A @ params + 0.05 * np.cos(A @ (params * 1.3))


def _case(protocol: str, noise: float, seed: int) -> dict[str, Any]:
    y_true = _observe(TRUE, protocol)
    rng = np.random.default_rng(seed + len(protocol))
    y = y_true + noise * max(float(np.std(y_true)), 1.0e-9) * rng.standard_normal(y_true.shape)
    A = _A(protocol)
    lam = 0.010 if protocol == "combined" else 0.055
    est = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ y)
    err = np.abs(est - TRUE) / np.maximum(np.abs(TRUE), 1.0e-9)
    med = float(np.median(err)); mx = float(np.max(err)); obj = float(np.mean((_observe(est, protocol) - y) ** 2))
    success = bool(med <= 0.20)
    status = "qualified_supported" if success else ("failed_but_informative" if med <= 0.45 else "failed_but_informative")
    return {"protocol": protocol, "noise": float(noise), "seed": int(seed), "median_parameter_error": med, "max_parameter_error": mx, "success": success, "objective_value": obj, "finite_result": bool(np.isfinite([med, mx, obj]).all()), "claim_status": status}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows: w.writerow({k: row.get(k) for k in CSV_FIELDS})


def run_low_dim_inverse() -> dict[str, Any]:
    protocols = ["short_pulse", "ltp_ltd", "combined"]
    rows = [_case(p, n, s) for p in protocols for n in [0.0, 0.02, 0.05] for s in [2026, 2027]]
    med = {p: float(np.median([r["median_parameter_error"] for r in rows if r["protocol"] == p])) for p in protocols}
    suc = {p: float(np.mean([r["success"] for r in rows if r["protocol"] == p])) for p in protocols}
    best = min(protocols, key=lambda p: med[p])
    status = "qualified_supported" if med[best] <= 0.20 and suc[best] >= 0.70 else "failed_but_informative"
    summary = {"benchmark": "multilayer_sandwich_low_dim_inverse", "note": "Synthetic numerical low-dimensional sandwich inverse smoke; not arbitrary full-field recovery.", "num_cases": len(rows), "parameters": PARAMS, "best_protocol": best, "median_parameter_error_by_protocol": med, "success_rate_by_protocol": suc, "low_dim_sandwich_inverse_status": status, "forbidden_claims": ["full arbitrary hidden-field inverse", "experimental validation"], "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")}}
    _write_cases(ROOT / CASES_CSV, rows); write_json(ROOT / SUMMARY_JSON, summary); return summary


def main() -> None:
    argparse.ArgumentParser().parse_args(); print(run_low_dim_inverse())


if __name__ == "__main__": main()
