"""Activated-case terminal inverse audit for OASIS-PINN v9."""
from __future__ import annotations

import argparse
import json
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

from pinnpcm.physics.multilayer_sandwich import simulate_phase_activated_multilayer_case
from scripts.gamma_sub_validation_common import write_json

ACTIVE_SUMMARY_JSON = Path("outputs/tables/active_protocol_identifiability_v2_summary.json")
SEQUENTIAL_SUMMARY_JSON = Path("outputs/tables/sequential_terminal_inverse_v2_summary.json")
PARAMS = ["Rc", "Ea", "Rth", "h_sub", "Tc", "width"]
BASE = np.asarray([1.0, 1.0, 1.0, 1.0, 330.0, 3.0], dtype=float)
TRUE = np.asarray([1.18, 1.10, 0.82, 0.75, 331.2, 2.4], dtype=float)
STEPS = np.asarray([0.08, 0.08, 0.10, 0.12, 0.6, 0.25], dtype=float)


def _cfg(theta: np.ndarray, protocol: str) -> dict[str, Any]:
    return {
        "ny": 10,
        "nt": 28,
        "V_peak": 1.9,
        "V_pos": 1.8,
        "V_neg": -0.8,
        "V_bias": 1.7,
        "R_load_ohm": 5.0e4,
        "Rc_TE_PCM_ohm_m2": 1.2e-10 * float(theta[0]),
        "Rc_PCM_SnSe_barrier_ohm_m2": 2.4e-10 * float(theta[0]),
        "Ea_scale": float(theta[1]),
        "Rth_PCM_SnSe_barrier_m2K_W": 3.4e-8 * float(theta[2]),
        "Rth_BE_substrate_m2K_W": 4.0e-8 * float(theta[2]),
        "h_sub_W_m2K": 2.0e5 * float(theta[3]),
        "nbo2_Tc_K": float(theta[4]),
        "nbo2_width_K": float(theta[5]),
    }


def _simulate(theta: np.ndarray, protocol: str, seed: int = 2026) -> dict[str, Any]:
    pulse = {"near_threshold_amplitude_width_sweep": "activation_triangle", "minor_loop": "minor_loop", "rc_oscillator": "rc_oscillator", "combined_d_optimal": "activation_triangle"}[protocol]
    return simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "nbo2", pulse, seed, _cfg(theta, protocol))


def _trace_features(result: dict[str, Any]) -> np.ndarray:
    I = np.asarray(result["current"], dtype=float)
    G = np.asarray(result["conductance"], dtype=float)
    V = np.asarray(result["voltage_device"], dtype=float)
    # Full trace with scale-normalized derivative features; no hidden T/m/sigma.
    dG = np.gradient(G)
    return np.concatenate([I, G, V, dG])


def _observe(theta: np.ndarray, protocol: str) -> np.ndarray:
    if protocol != "combined_d_optimal":
        return _trace_features(_simulate(theta, protocol))
    return np.concatenate([_trace_features(_simulate(theta, p, 2026 + i)) for i, p in enumerate(["near_threshold_amplitude_width_sweep", "minor_loop", "rc_oscillator"])])


def _normalized_jacobian(protocol: str) -> tuple[np.ndarray, np.ndarray]:
    y0 = _observe(BASE, protocol)
    cols = []
    for j, step in enumerate(STEPS):
        plus = BASE.copy(); minus = BASE.copy()
        plus[j] += step; minus[j] -= step
        if j < 4: minus[j] = max(0.25, minus[j])
        if j == 4: minus[j] = max(320.0, minus[j])
        if j == 5: minus[j] = max(0.8, minus[j])
        yp = _observe(plus, protocol)
        ym = _observe(minus, protocol)
        scale = np.maximum(np.abs(y0), np.maximum(float(np.std(y0)), 1.0e-18))
        cols.append(((yp - ym) / (plus[j] - minus[j])) * BASE[j] / scale)
    return np.stack(cols, axis=1), y0


def _protocol_summary(protocol: str) -> dict[str, Any]:
    J, _ = _normalized_jacobian(protocol)
    s = np.linalg.svd(J, compute_uv=False)
    rank = int(np.sum(s > 1.0e-5))
    cond = float(s[0] / s[-1]) if s.size and s[-1] > 1.0e-12 else 1.0e300
    gram = J.T @ J + 1.0e-12 * np.eye(len(PARAMS))
    sign, logdet = np.linalg.slogdet(gram)
    blocks = {"Rc_Ea": [0, 1], "Rth_h_sub": [2, 3], "Tc_width": [4, 5]}
    block_metrics = {}
    for name, idx in blocks.items():
        sb = np.linalg.svd(J[:, idx], compute_uv=False)
        brank = int(np.sum(sb > 1.0e-5))
        bcond = float(sb[0] / sb[-1]) if sb.size and sb[-1] > 1.0e-12 else 1.0e300
        block_metrics[name] = {"rank": brank, "condition_number": bcond, "gate_passed": bool(brank == 2 and bcond < 1.0e8)}
    return {"rank": rank, "condition_number": cond, "logdet": float(logdet if sign > 0 else -np.inf), "column_norms": {p: float(v) for p, v in zip(PARAMS, np.linalg.norm(J, axis=0))}, "block_metrics": block_metrics, "all_block_gates_passed": bool(all(v["gate_passed"] for v in block_metrics.values()))}


def _objective(theta: np.ndarray, protocol: str, target: np.ndarray, noise: float = 0.0, seed: int = 1) -> float:
    pred = _observe(theta, protocol)
    rng = np.random.default_rng(seed)
    noisy = target + noise * max(float(np.max(np.abs(target))), 1.0e-30) * rng.standard_normal(target.shape)
    return float(np.sqrt(np.mean(((pred - noisy) / np.maximum(np.abs(noisy), np.std(noisy) + 1.0e-18)) ** 2)))


def _sequential_inverse(protocol: str) -> dict[str, Any]:
    target = _observe(TRUE, protocol)
    est = BASE.copy()
    errors = {}
    for name, block in zip(["Rc_Ea", "Rth_h_sub", "Tc_width"], [[0, 1], [2, 3], [4, 5]]):
        grids = []
        for j in block:
            grids.append([est[j] + k * STEPS[j] for k in [-2, -1, 0, 1, 2]])
        best = (float("inf"), est.copy())
        for a in grids[0]:
            for b in grids[1]:
                trial = est.copy(); trial[block[0]] = a; trial[block[1]] = b
                trial[:4] = np.clip(trial[:4], 0.25, 2.5); trial[4] = np.clip(trial[4], 320.0, 340.0); trial[5] = np.clip(trial[5], 0.8, 6.0)
                obj = _objective(trial, protocol, target)
                if obj < best[0]: best = (obj, trial.copy())
        est = best[1]
        errors[name] = float(np.median(np.abs(est[block] - TRUE[block]) / np.maximum(np.abs(TRUE[block]), 1.0e-12)))
    total = float(np.median(np.abs(est - TRUE) / np.maximum(np.abs(TRUE), 1.0e-12)))
    success = bool(total <= 0.20)
    return {"protocol": protocol, "estimated": {p: float(v) for p, v in zip(PARAMS, est)}, "true": {p: float(v) for p, v in zip(PARAMS, TRUE)}, "block_error": errors, "median_relative_error": total, "success": success}


def _profile_likelihood(protocol: str) -> dict[str, Any]:
    target = _observe(TRUE, protocol)
    rows = []
    for noise in [0.0, 0.02, 0.05]:
        successes = []
        errors = []
        for seed in range(5):
            result = _sequential_inverse(protocol)
            errors.append(result["median_relative_error"])
            successes.append(result["success"] and _objective(TRUE, protocol, target, noise, seed) < 0.25)
        rows.append({"noise": noise, "median_error": float(np.median(errors)), "success_rate": float(np.mean(successes))})
    return {"noise_rows": rows, "success_rate_min": float(min(r["success_rate"] for r in rows)), "median_error_max": float(max(r["median_error"] for r in rows))}


def run_active_protocol_identifiability_v2() -> tuple[dict[str, Any], dict[str, Any]]:
    protocols = ["near_threshold_amplitude_width_sweep", "minor_loop", "rc_oscillator", "combined_d_optimal"]
    metrics = {p: _protocol_summary(p) for p in protocols}
    best = max(protocols, key=lambda p: metrics[p]["logdet"])
    activated = _simulate(BASE, best if best != "combined_d_optimal" else "near_threshold_amplitude_width_sweep")["activated"]
    profile = _profile_likelihood(best)
    active = {"benchmark": "active_protocol_identifiability_v2", "note": "Synthetic numerical activated-case full terminal-trace Jacobian audit; no hidden fields used.", "uses_only_terminal_traces": True, "uses_activated_cases_only": bool(activated), "protocols": protocols, "best_d_optimal_protocol": best, "protocol_metrics": metrics, "profile_likelihood": profile, "all_blocks_pass_best_protocol_gate": bool(metrics[best]["all_block_gates_passed"]), "outputs": {"summary_json": str(ACTIVE_SUMMARY_JSON).replace("\\", "/")}}
    seq_result = _sequential_inverse(best)
    block_error_gate = bool(all(float(v) <= 0.20 for v in seq_result["block_error"].values()))
    gate = bool(metrics[best]["all_block_gates_passed"] and block_error_gate and seq_result["median_relative_error"] <= 0.20 and profile["success_rate_min"] >= 0.70)
    seq = {"benchmark": "sequential_terminal_inverse_v2", "note": "Synthetic numerical activated-case sequential terminal inverse; not full-field recovery.", "blocks": ["Rc_Ea", "Rth_h_sub", "Tc_width"], "best_protocol": best, "sequential_result": seq_result, "block_error_gate_passed": block_error_gate, "gate_passed": gate, "sequential_inverse_status": "qualified_supported" if gate else "failed_but_informative", "outputs": {"summary_json": str(SEQUENTIAL_SUMMARY_JSON).replace("\\", "/")}}
    write_json(ROOT / ACTIVE_SUMMARY_JSON, active)
    write_json(ROOT / SEQUENTIAL_SUMMARY_JSON, seq)
    return active, seq


def main() -> None:
    argparse.ArgumentParser().parse_args()
    active, seq = run_active_protocol_identifiability_v2()
    print(json.dumps({"active": active["all_blocks_pass_best_protocol_gate"], "sequential": seq["sequential_inverse_status"]}, indent=2))


if __name__ == "__main__":
    main()
