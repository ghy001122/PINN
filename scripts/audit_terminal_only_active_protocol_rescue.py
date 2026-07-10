"""Simulator-backed active terminal-only multi-protocol rescue audit.

The audit targets low-dimensional parameter recovery from multilayer simulator
terminal observables. It does not claim arbitrary full-field recovery.
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
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.multilayer_sandwich import simulate_multilayer_case
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/terminal_only_active_protocol_rescue_simulator_summary.json")
CASES_CSV = Path("outputs/tables/terminal_only_active_protocol_rescue_simulator_cases.csv")
LEGACY_SUMMARY_JSON = Path("outputs/tables/terminal_only_active_protocol_rescue_summary.json")
LEGACY_CASES_CSV = Path("outputs/tables/terminal_only_active_protocol_rescue_cases.csv")
FIG_GAIN = Path("outputs/figures/terminal_only_active_protocol_gain.png")
PROTOCOLS = ["single_pulse", "multi_amplitude", "multi_width", "hysteresis_minor_loop", "oscillation_frequency_readout", "combined_terminal_protocol"]
PARAMS = ["Rth_pcm_sub", "Rth_barrier", "Rc_te_pcm", "h_sub", "Tsw", "Ea"]
BASE = np.asarray([1.0, 1.0, 1.0, 1.0, 304.5, 1.0], dtype=float)
TRUE = np.asarray([1.18, 0.82, 1.22, 0.76, 305.2, 1.12], dtype=float)
CSV_FIELDS = ["protocol", "noise", "seed", "parameter_median_error", "max_parameter_error", "success", "objective_value", "condition_number", "sensitivity_norm", "finite_result", "claim_status", "is_simulator_backed", "legacy_feature_matrix_only"]


def _cfg_from_params(params: np.ndarray, extra: dict[str, float] | None = None) -> dict[str, float]:
    cfg: dict[str, float] = {
        "ny": 14,
        "nt": 18,
        "Rth_pcm_sub_scale": float(params[0]),
        "Rth_barrier_scale": float(params[1]),
        "Rc_te_pcm_scale": float(params[2]),
        "h_sub_scale": float(params[3]),
        "T_sw_K": float(params[4]),
        "Ea_scale": float(params[5]),
    }
    if extra:
        cfg.update({k: float(v) for k, v in extra.items()})
    return cfg


def _terminal_features(result: dict[str, Any]) -> np.ndarray:
    I = np.asarray(result["current"], dtype=float)
    G = np.asarray(result["conductance"], dtype=float)
    t = np.asarray(result["time"], dtype=float)
    absI = np.abs(I)
    g0 = max(abs(float(G[0])), 1.0e-30)
    peak_idx = int(np.argmax(absI))
    switch_idx = int(np.argmax(np.abs(np.gradient(G)))) if G.size > 2 else peak_idx
    sign_changes = int(np.sum(np.diff(np.signbit(np.gradient(G))) != 0)) if G.size > 3 else 0
    return np.asarray([
        float(np.max(absI)),
        float(np.trapz(absI, t)),
        float(np.max(G) / max(np.min(np.abs(G)) + 1.0e-30, 1.0e-30)),
        float(G[-1] / g0),
        float(t[peak_idx] if t.size else 0.0),
        float(t[switch_idx] if t.size else 0.0),
        float(sign_changes / max(t[-1] - t[0], 1.0e-12)),
    ], dtype=float)


def _runs_for_protocol(protocol: str) -> list[tuple[str, dict[str, float], str, str]]:
    if protocol == "single_pulse":
        return [("short_pulse", {"V_short": 0.18, "nt": 18}, "full_stack_with_SnSe_barrier", "localized_filament")]
    if protocol == "multi_amplitude":
        return [("short_pulse", {"V_short": v, "nt": 18}, "full_stack_with_SnSe_barrier", "localized_filament") for v in [0.12, 0.18, 0.24]]
    if protocol == "multi_width":
        return [("short_pulse", {"V_short": 0.18, "nt": nt}, "full_stack_with_SnSe_barrier", "localized_filament") for nt in [12, 18, 28]]
    if protocol == "hysteresis_minor_loop":
        return [("ltp_ltd", {"V_ltp": 0.12, "V_ltd": -0.06, "nt": 22}, "full_stack_with_SnSe_barrier", "localized_filament")]
    if protocol == "oscillation_frequency_readout":
        return [("ltp_ltd", {"V_ltp": 0.16, "V_ltd": -0.08, "nt": 28}, "full_stack_with_thermal_boundary_resistance", "edge_hotspot")]
    if protocol == "combined_terminal_protocol":
        runs: list[tuple[str, dict[str, float], str, str]] = []
        for p in PROTOCOLS[:-1]:
            runs.extend(_runs_for_protocol(p))
        return runs
    raise ValueError(protocol)


def _observe(params: np.ndarray, protocol: str, seed: int) -> np.ndarray:
    feats = []
    for idx, (pulse, extra, structure, geometry) in enumerate(_runs_for_protocol(protocol)):
        cfg = _cfg_from_params(params, extra)
        result = simulate_multilayer_case(structure, geometry, 0.08, pulse, seed + idx, cfg)
        feats.append(_terminal_features(result))
    return np.concatenate(feats)


def _linearized_inverse(protocol: str, noise: float, seed: int) -> dict[str, Any]:
    y_true = _observe(TRUE, protocol, seed)
    rng = np.random.default_rng(seed + len(protocol))
    y = y_true + noise * max(float(np.std(y_true)), 1.0e-30) * rng.standard_normal(y_true.shape)
    y0 = _observe(BASE, protocol, seed)
    A_cols = []
    steps = np.asarray([0.08, 0.08, 0.08, 0.08, 0.25, 0.08], dtype=float)
    for i, step in enumerate(steps):
        plus = BASE.copy(); plus[i] += step
        minus = BASE.copy(); minus[i] -= step
        if i == 4:
            minus[i] = max(300.0, minus[i])
        else:
            minus[i] = max(0.25, minus[i])
        A_cols.append((_observe(plus, protocol, seed) - _observe(minus, protocol, seed)) / (plus[i] - minus[i]))
    A = np.stack(A_cols, axis=1)
    lam = 1.0e-4 if protocol == "combined_terminal_protocol" else 5.0e-3
    delta = np.linalg.solve(A.T @ A + lam * np.eye(len(PARAMS)), A.T @ (y - y0))
    est = BASE + delta
    est[:4] = np.clip(est[:4], 0.25, 2.5)
    est[4] = np.clip(est[4], 300.0, 310.0)
    est[5] = np.clip(est[5], 0.5, 2.0)
    obj = float(np.mean((_observe(est, protocol, seed) - y) ** 2))
    denom = np.maximum(np.abs(TRUE), 1.0e-9)
    err = np.abs(est - TRUE) / denom
    med = float(np.median(err))
    mx = float(np.max(err))
    cond = float(np.linalg.cond(A.T @ A + lam * np.eye(len(PARAMS))))
    sensitivity_norm = float(np.linalg.norm(A))
    success = bool(med <= 0.20 and sensitivity_norm > 1.0e-12 and cond < 1.0e12)
    status = "qualified_supported" if success else "failed_but_informative"
    return {"protocol": protocol, "noise": float(noise), "seed": int(seed), "parameter_median_error": med, "max_parameter_error": mx, "success": success, "objective_value": obj, "condition_number": cond, "sensitivity_norm": sensitivity_norm, "finite_result": bool(np.isfinite([med, mx, obj, cond]).all()), "claim_status": status, "is_simulator_backed": True, "legacy_feature_matrix_only": False}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in CSV_FIELDS})


def _plot(summary: dict[str, Any]) -> None:
    FIG_GAIN.parent.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(PROTOCOLS)); vals = [summary["parameter_error_by_protocol"][p] for p in PROTOCOLS]
    fig, ax = plt.subplots(figsize=(8.5, 4.0)); ax.bar(x, vals); ax.axhline(0.20, color="black", linestyle="--")
    ax.set_xticks(x); ax.set_xticklabels(PROTOCOLS, rotation=35, ha="right")
    ax.set_ylabel("median parameter error"); ax.set_title("Simulator-backed active terminal protocol rescue")
    fig.tight_layout(); fig.savefig(ROOT / FIG_GAIN, dpi=150); plt.close(fig)


def run_terminal_only_active_protocol_rescue() -> dict[str, Any]:
    rows = [_linearized_inverse(protocol, noise, seed) for protocol in PROTOCOLS for noise in [0.0, 0.02, 0.05] for seed in [2026, 2027]]
    parameter_error = {p: float(np.median([r["parameter_median_error"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    success_rate = {p: float(np.mean([r["success"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    cond = {p: float(np.median([r["condition_number"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    best = min(PROTOCOLS, key=lambda p: parameter_error[p])
    status = "qualified_supported" if parameter_error[best] <= 0.20 and success_rate[best] >= 0.70 else "failed_but_informative"
    summary = {"benchmark": "terminal_only_active_protocol_rescue_simulator", "note": "Synthetic numerical simulator-backed terminal protocol audit; supports only low-dimensional diagnosis if gates clear.", "num_cases": len(rows), "is_simulator_backed": True, "legacy_feature_matrix_only": False, "legacy_ablation_available": str(LEGACY_SUMMARY_JSON).replace("\\", "/"), "best_protocol": best, "parameter_error_by_protocol": parameter_error, "success_rate_by_protocol": success_rate, "condition_number_by_protocol": cond, "sensitivity_norm_by_protocol": {p: float(np.median([r["sensitivity_norm"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}, "parameter_recovery_status": status, "single_trace_arbitrary_full_field_status": "forbidden", "forbidden_claims": ["single-trace arbitrary full-field recovery", "experimental validation"], "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/"), "legacy_summary_json": str(LEGACY_SUMMARY_JSON).replace("\\", "/"), "legacy_cases_csv": str(LEGACY_CASES_CSV).replace("\\", "/"), "gain_figure": str(FIG_GAIN).replace("\\", "/")}}
    _write_cases(ROOT / CASES_CSV, rows); _plot(summary); write_json(ROOT / SUMMARY_JSON, summary); return summary


def main() -> None:
    argparse.ArgumentParser().parse_args(); print(run_terminal_only_active_protocol_rescue())


if __name__ == "__main__":
    main()
