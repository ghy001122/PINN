"""Active terminal-protocol identifiability audit for conservative OASIS-PINN v8."""
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

from pinnpcm.physics.multilayer_sandwich import simulate_conservative_multilayer_case
from scripts.gamma_sub_validation_common import write_json

ACTIVE_SUMMARY_JSON = Path("outputs/tables/active_protocol_identifiability_summary.json")
SEQUENTIAL_SUMMARY_JSON = Path("outputs/tables/sequential_terminal_inverse_summary.json")
CASES_CSV = Path("outputs/tables/active_protocol_identifiability_cases.csv")
PARAMS = ["Rc", "Ea", "Rth", "h_sub", "Tsw", "width"]
BASE = np.asarray([1.0, 1.0, 1.0, 1.0, 304.5, 0.08], dtype=float)
TRUE = np.asarray([1.18, 1.10, 0.82, 0.76, 305.1, 0.065], dtype=float)
STEPS = np.asarray([0.08, 0.08, 0.08, 0.08, 0.20, 0.01], dtype=float)
CSV_FIELDS = ["protocol", "parameter", "column_norm", "rank", "condition_number", "logdet", "gate_passed"]


def _cfg(theta: np.ndarray, extra: dict[str, float] | None = None) -> tuple[float, dict[str, float]]:
    c = {
        "ny": 10,
        "nt": 10,
        "material_family": "vo2",
        "Rc_te_pcm_scale": float(theta[0]),
        "Ea_scale": float(theta[1]),
        "Rth_pcm_sub_scale": float(theta[2]),
        "h_sub_scale": float(theta[3]),
        "T_sw_K": float(theta[4]),
    }
    if extra:
        c.update({k: float(v) for k, v in extra.items()})
    return float(theta[5]), c


def _terminal_features(result: dict[str, Any]) -> np.ndarray:
    I = np.asarray(result["current"], dtype=float)
    G = np.asarray(result["conductance"], dtype=float)
    t = np.asarray(result["time"], dtype=float)
    absI = np.abs(I)
    dG = np.gradient(G) if G.size > 2 else np.zeros_like(G)
    g0 = max(abs(float(G[0])), 1.0e-30)
    duration = max(float(t[-1] - t[0]) if t.size else 0.0, 1.0e-12)
    return np.asarray([
        float(np.max(absI)),
        float(np.trapz(absI, t)),
        float(np.max(np.abs(G))),
        float(G[-1] / g0),
        float(np.max(np.abs(dG)) / max(np.max(np.abs(G)), 1.0e-30)),
        float(t[int(np.argmax(absI))] if t.size else 0.0),
        float(t[int(np.argmax(np.abs(dG)))] if t.size else 0.0),
        float(np.sum(np.diff(np.signbit(dG)) != 0) / duration if dG.size > 3 else 0.0),
    ], dtype=float)


def _protocol_runs(protocol: str) -> list[tuple[str, dict[str, float], str, str]]:
    if protocol == "near_threshold_amplitude_width_sweep":
        return [("short_pulse", {"V_short": v, "nt": nt}, "full_stack_with_contact_resistance", "localized_filament") for v in [0.18, 0.26, 0.34] for nt in [10, 14]]
    if protocol == "branch_memory_minor_loop":
        return [("ltp_ltd", {"V_ltp": 0.26, "V_ltd": -0.12, "nt": 14}, "full_stack_with_contact_resistance", "localized_filament")]
    if protocol == "rc_oscillator_frequency_readout":
        return [("ltp_ltd", {"V_ltp": 0.30, "V_ltd": -0.14, "R_load_ohm": rl, "nt": 16}, "full_stack_with_thermal_boundary_resistance", "edge_hotspot") for rl in [5.0e4, 1.0e5, 2.0e5]]
    if protocol == "combined_d_optimal_candidate":
        runs: list[tuple[str, dict[str, float], str, str]] = []
        for p in ["near_threshold_amplitude_width_sweep", "branch_memory_minor_loop", "rc_oscillator_frequency_readout"]:
            runs.extend(_protocol_runs(p))
        return runs
    raise ValueError(protocol)


def _observe(theta: np.ndarray, protocol: str, seed: int = 2026) -> np.ndarray:
    width, base_cfg = _cfg(theta)
    feats: list[np.ndarray] = []
    for i, (pulse, extra, structure, geometry) in enumerate(_protocol_runs(protocol)):
        cfg = {**base_cfg, **extra}
        result = simulate_conservative_multilayer_case(structure, geometry, width, pulse, seed + i, cfg)
        feats.append(_terminal_features(result))
    return np.concatenate(feats)


def _normalized_jacobian(protocol: str) -> tuple[np.ndarray, np.ndarray]:
    y0 = _observe(BASE, protocol)
    cols = []
    for j, step in enumerate(STEPS):
        plus = BASE.copy(); minus = BASE.copy()
        plus[j] += step; minus[j] -= step
        if j < 4:
            minus[j] = max(0.25, minus[j])
        if j == 4:
            minus[j] = max(300.0, minus[j])
        if j == 5:
            minus[j] = max(0.025, minus[j])
        yp = _observe(plus, protocol)
        ym = _observe(minus, protocol)
        dy = (yp - ym) / (plus[j] - minus[j])
        scale = np.maximum(np.abs(y0), np.maximum(float(np.std(y0)), 1.0e-18))
        cols.append(dy * BASE[j] / scale)
    return np.stack(cols, axis=1), y0


def _analyze_protocol(protocol: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    J, _ = _normalized_jacobian(protocol)
    s = np.linalg.svd(J, compute_uv=False)
    rank = int(np.sum(s > 1.0e-6))
    cond = (float(s[0] / s[-1]) if s.size and s[-1] > 1.0e-12 else 1.0e300)
    gram = J.T @ J + 1.0e-12 * np.eye(len(PARAMS))
    sign, logdet = np.linalg.slogdet(gram)
    col_norms = np.linalg.norm(J, axis=0)
    rows = []
    for p, norm in zip(PARAMS, col_norms):
        rows.append({"protocol": protocol, "parameter": p, "column_norm": float(norm), "rank": rank, "condition_number": cond, "logdet": float(logdet if sign > 0 else -np.inf), "gate_passed": bool(norm > 1.0e-5 and rank >= 3 and cond < 1.0e8)})
    summary = {"rank": rank, "condition_number": cond, "logdet": float(logdet if sign > 0 else -np.inf), "all_parameter_gates_passed": bool(all(r["gate_passed"] for r in rows)), "column_norms": {p: float(n) for p, n in zip(PARAMS, col_norms)}}
    return rows, summary


def _sequential_inverse(protocol: str) -> dict[str, Any]:
    y_target = _observe(TRUE, protocol)
    est = BASE.copy()
    blocks = [[0, 1], [2, 3], [4, 5]]
    block_names = ["Rc_Ea", "Rth_h_sub", "Tsw_width"]
    errors: dict[str, float] = {}
    for name, block in zip(block_names, blocks):
        y0 = _observe(est, protocol)
        cols = []
        for j in block:
            plus = est.copy(); minus = est.copy(); plus[j] += STEPS[j]; minus[j] -= STEPS[j]
            if j < 4: minus[j] = max(0.25, minus[j])
            if j == 4: minus[j] = max(300.0, minus[j])
            if j == 5: minus[j] = max(0.025, minus[j])
            cols.append((_observe(plus, protocol) - _observe(minus, protocol)) / (plus[j] - minus[j]))
        A = np.stack(cols, axis=1)
        delta = np.linalg.solve(A.T @ A + 1.0e-4 * np.eye(len(block)), A.T @ (y_target - y0))
        for local, j in enumerate(block):
            est[j] += delta[local]
        est[:4] = np.clip(est[:4], 0.25, 2.5); est[4] = np.clip(est[4], 300.0, 310.0); est[5] = np.clip(est[5], 0.025, 0.2)
        errors[name] = float(np.median(np.abs(est[block] - TRUE[block]) / np.maximum(np.abs(TRUE[block]), 1.0e-12)))
    total_error = float(np.median(np.abs(est - TRUE) / np.maximum(np.abs(TRUE), 1.0e-12)))
    return {"protocol": protocol, "estimated": {p: float(v) for p, v in zip(PARAMS, est)}, "true": {p: float(v) for p, v in zip(PARAMS, TRUE)}, "block_error": errors, "median_relative_error": total_error, "success": bool(total_error <= 0.20)}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in CSV_FIELDS})


def run_active_protocol_identifiability() -> tuple[dict[str, Any], dict[str, Any]]:
    protocols = ["near_threshold_amplitude_width_sweep", "branch_memory_minor_loop", "rc_oscillator_frequency_readout", "combined_d_optimal_candidate"]
    all_rows: list[dict[str, Any]] = []
    by_protocol: dict[str, Any] = {}
    for p in protocols:
        rows, summary = _analyze_protocol(p)
        all_rows.extend(rows)
        by_protocol[p] = summary
    best_protocol = max(protocols, key=lambda p: by_protocol[p]["logdet"])
    active_summary = {
        "benchmark": "active_protocol_identifiability",
        "note": "Synthetic numerical terminal-observable normalized-Jacobian audit; no hidden T/energy features are used as terminal-only observations.",
        "is_simulator_backed": True,
        "uses_only_terminal_features": True,
        "protocols": protocols,
        "parameter_order": PARAMS,
        "best_d_optimal_protocol": best_protocol,
        "protocol_metrics": by_protocol,
        "all_parameters_pass_best_protocol_gate": bool(by_protocol[best_protocol]["all_parameter_gates_passed"]),
        "outputs": {"summary_json": str(ACTIVE_SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")},
    }
    sequential = _sequential_inverse(best_protocol)
    if not by_protocol[best_protocol]["all_parameter_gates_passed"]:
        sequential["success"] = False
        sequential["blocked_by_identifiability_gate"] = True
    else:
        sequential["blocked_by_identifiability_gate"] = False
    sequential_summary = {
        "benchmark": "sequential_terminal_inverse",
        "note": "Synthetic numerical sequential block inverse using terminal observables only; not arbitrary full-field recovery.",
        "is_simulator_backed": True,
        "uses_only_terminal_features": True,
        "blocks": ["Rc_Ea", "Rth_h_sub", "Tsw_width"],
        "best_protocol": best_protocol,
        "sequential_result": sequential,
        "sequential_inverse_status": "qualified_supported" if sequential["success"] else "failed_but_informative",
        "outputs": {"summary_json": str(SEQUENTIAL_SUMMARY_JSON).replace("\\", "/")},
    }
    _write_cases(ROOT / CASES_CSV, all_rows)
    write_json(ROOT / ACTIVE_SUMMARY_JSON, active_summary)
    write_json(ROOT / SEQUENTIAL_SUMMARY_JSON, sequential_summary)
    return active_summary, sequential_summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    active, sequential = run_active_protocol_identifiability()
    print(active)
    print(sequential)


if __name__ == "__main__":
    main()
