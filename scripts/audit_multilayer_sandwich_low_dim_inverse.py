"""Simulator-backed low-dimensional multilayer sandwich inverse smoke audit."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.multilayer_sandwich import simulate_multilayer_case
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/multilayer_sandwich_low_dim_inverse_summary.json")
CASES_CSV = Path("outputs/tables/multilayer_sandwich_low_dim_inverse_cases.csv")
PARAMS = ["Rth_pcm_sub", "Rth_barrier", "Rc_te_pcm", "h_sub", "Tsw", "Ea"]
BASE = np.asarray([1.0, 1.0, 1.0, 1.0, 304.5, 1.0], dtype=float)
TRUE = np.asarray([1.12, 0.88, 1.18, 0.82, 305.0, 1.10], dtype=float)
CSV_FIELDS = ["protocol", "noise", "seed", "median_parameter_error", "max_parameter_error", "condition_number", "sensitivity_norm", "profile_ridge", "success", "objective_value", "finite_result", "claim_status", "is_simulator_backed", "legacy_A_matrix_only"]


def _cfg(params: np.ndarray, extra: dict[str, float] | None = None) -> dict[str, float]:
    c: dict[str, float] = {"ny": 14, "nt": 18, "Rth_pcm_sub_scale": float(params[0]), "Rth_barrier_scale": float(params[1]), "Rc_te_pcm_scale": float(params[2]), "h_sub_scale": float(params[3]), "T_sw_K": float(params[4]), "Ea_scale": float(params[5])}
    if extra:
        c.update({k: float(v) for k, v in extra.items()})
    return c


def _features(result: dict[str, Any]) -> np.ndarray:
    I = np.asarray(result["current"], dtype=float); G = np.asarray(result["conductance"], dtype=float); t = np.asarray(result["time"], dtype=float)
    return np.asarray([
        float(np.max(np.abs(I))),
        float(np.trapz(np.abs(I), t)),
        float(np.max(G) / max(np.min(np.abs(G)) + 1.0e-30, 1.0e-30)),
        float(G[-1] / max(abs(G[0]), 1.0e-30)),
        float(result["max_delta_T"]),
        float(result["energy_balance_error"]),
        float(result["temperature_jump_residual"]),
        float(result["substrate_robin_residual"]),
    ], dtype=float)


def _runs(protocol: str) -> list[tuple[str, str, str, dict[str, float]]]:
    base = [
        ("short_pulse", "full_stack_with_SnSe_barrier", "localized_filament", {"V_short": 0.18, "nt": 18}),
        ("ltp_ltd", "full_stack_with_SnSe_barrier", "localized_filament", {"V_ltp": 0.15, "V_ltd": -0.08, "nt": 22}),
    ]
    if protocol == "short_pulse":
        return [base[0]]
    if protocol == "ltp_ltd":
        return [base[1]]
    if protocol == "combined":
        return base
    if protocol == "combined_plus_structure_ablation":
        return base + [
            ("short_pulse", "pcm_plus_electrodes_substrate", "uniform_crossbar", {"V_short": 0.18, "nt": 18}),
            ("ltp_ltd", "full_stack_with_thermal_boundary_resistance", "edge_hotspot", {"V_ltp": 0.14, "V_ltd": -0.07, "nt": 22}),
        ]
    raise ValueError(protocol)


def _observe(params: np.ndarray, protocol: str, seed: int) -> np.ndarray:
    out = []
    for i, (pulse, structure, geometry, extra) in enumerate(_runs(protocol)):
        out.append(_features(simulate_multilayer_case(structure, geometry, 0.08, pulse, seed + i, _cfg(params, extra))))
    return np.concatenate(out)


def _case(protocol: str, noise: float, seed: int) -> dict[str, Any]:
    y_true = _observe(TRUE, protocol, seed)
    rng = np.random.default_rng(seed + len(protocol))
    y = y_true + noise * max(float(np.std(y_true)), 1.0e-30) * rng.standard_normal(y_true.shape)
    y0 = _observe(BASE, protocol, seed)
    steps = np.asarray([0.08, 0.08, 0.08, 0.08, 0.25, 0.08], dtype=float)
    cols = []
    profile_objectives = []
    for i, step in enumerate(steps):
        plus = BASE.copy(); minus = BASE.copy(); plus[i] += step; minus[i] -= step
        if i == 4:
            minus[i] = max(300.0, minus[i])
        else:
            minus[i] = max(0.25, minus[i])
        yp = _observe(plus, protocol, seed); ym = _observe(minus, protocol, seed)
        cols.append((yp - ym) / (plus[i] - minus[i]))
        profile_objectives.append(float(min(np.mean((yp - y) ** 2), np.mean((ym - y) ** 2))))
    A = np.stack(cols, axis=1)
    lam = 1.0e-4 if protocol == "combined_plus_structure_ablation" else 2.0e-3
    delta = np.linalg.solve(A.T @ A + lam * np.eye(len(PARAMS)), A.T @ (y - y0))
    est = BASE + delta
    est[:4] = np.clip(est[:4], 0.25, 2.5); est[4] = np.clip(est[4], 300.0, 310.0); est[5] = np.clip(est[5], 0.5, 2.0)
    err = np.abs(est - TRUE) / np.maximum(np.abs(TRUE), 1.0e-9)
    obj = float(np.mean((_observe(est, protocol, seed) - y) ** 2))
    raw_cond = float(np.linalg.cond(A.T @ A + lam * np.eye(len(PARAMS))))
    cond = raw_cond if np.isfinite(raw_cond) else 1.0e300
    sensitivity_norm = float(np.linalg.norm(A))
    med = float(np.median(err)); mx = float(np.max(err)); ridge = float(np.max(profile_objectives) / max(np.min(profile_objectives), 1.0e-30))
    success = bool(med <= 0.20 and sensitivity_norm > 1.0e-12 and cond < 1.0e12)
    status = "qualified_supported" if success else "failed_but_informative"
    return {"protocol": protocol, "noise": float(noise), "seed": int(seed), "median_parameter_error": med, "max_parameter_error": mx, "condition_number": cond, "sensitivity_norm": sensitivity_norm, "profile_ridge": ridge, "success": success, "objective_value": obj, "finite_result": bool(np.isfinite([med, mx, obj, cond, sensitivity_norm, ridge]).all()), "claim_status": status, "is_simulator_backed": True, "legacy_A_matrix_only": False}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in CSV_FIELDS})


def run_low_dim_inverse() -> dict[str, Any]:
    protocols = ["short_pulse", "ltp_ltd", "combined", "combined_plus_structure_ablation"]
    rows = [_case(p, n, s) for p in protocols for n in [0.0, 0.02, 0.05] for s in [2026, 2027]]
    med = {p: float(np.median([r["median_parameter_error"] for r in rows if r["protocol"] == p])) for p in protocols}
    suc = {p: float(np.mean([r["success"] for r in rows if r["protocol"] == p])) for p in protocols}
    cond = {p: float(np.median([r["condition_number"] for r in rows if r["protocol"] == p])) for p in protocols}
    ridge = {p: float(np.median([r["profile_ridge"] for r in rows if r["protocol"] == p])) for p in protocols}
    best = min(protocols, key=lambda p: med[p])
    status = "qualified_supported" if med[best] <= 0.20 and suc[best] >= 0.70 else "failed_but_informative"
    summary = {"benchmark": "multilayer_sandwich_low_dim_inverse", "note": "Synthetic numerical simulator-backed low-dimensional sandwich inverse; not arbitrary full-field recovery.", "num_cases": len(rows), "parameters": PARAMS, "is_simulator_backed": True, "legacy_A_matrix_only": False, "best_protocol": best, "median_parameter_error_by_protocol": med, "success_rate_by_protocol": suc, "condition_number_by_protocol": cond, "sensitivity_norm_by_protocol": {p: float(np.median([r["sensitivity_norm"] for r in rows if r["protocol"] == p])) for p in protocols}, "profile_ridge_by_protocol": ridge, "low_dim_sandwich_inverse_status": status, "forbidden_claims": ["full arbitrary hidden-field inverse", "experimental validation"], "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")}}
    _write_cases(ROOT / CASES_CSV, rows); write_json(ROOT / SUMMARY_JSON, summary); return summary


def main() -> None:
    argparse.ArgumentParser().parse_args(); print(run_low_dim_inverse())


if __name__ == "__main__": main()
