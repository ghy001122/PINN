"""Mechanism-routed active protocol design and noisy local terminal inverse."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pinnpcm.physics.multilayer_sandwich import simulate_phase_activated_multilayer_case
from scripts.gamma_sub_validation_common import write_json

DESIGN_JSON = Path("outputs/tables/active_protocol_design_v3_summary.json")
INVERSE_JSON = Path("outputs/tables/sequential_terminal_inverse_v3_summary.json")

FAMILIES = {
    "nbo2": {
        "names": ["Rc_scale", "Ea_scale", "Rth_eff_scale", "tau_th_scale"],
        "base": np.asarray([1.0, 1.0, 1.0, 1.0]),
        "true": np.asarray([1.12, 1.08, 0.85, 1.15]),
        "steps": np.asarray([0.06, 0.05, 0.08, 0.08]),
        "blocks": {"Rc_Ea": [0, 1], "Rth_eff_tau_th": [2, 3]},
    },
    "vo2": {
        "names": ["Rth_eff_scale", "tau_th_scale", "Tc_up_K", "Tc_down_K", "width_K"],
        "base": np.asarray([1.0, 1.0, 336.4, 329.2, 7.19]),
        "true": np.asarray([0.86, 1.12, 337.2, 328.7, 6.7]),
        "steps": np.asarray([0.08, 0.08, 0.8, 0.8, 0.5]),
        "blocks": {"Rth_eff_tau_th": [0, 1], "Tc_up_Tc_down_width": [2, 3, 4]},
    },
}


def _candidate_protocols(family: str) -> list[dict[str, Any]]:
    peaks = [1.8, 2.1] if family == "nbo2" else [10.0, 12.0]
    rows = []
    for peak in peaks:
        for fraction in [0.55, 0.75]:
            rows.append({"name": f"triangle_V{peak:g}_f{fraction:g}", "pulse": "activation_triangle", "V_peak": peak, "pulse_active_fraction": fraction, "R_load_ohm": 4.0e4 if family == "nbo2" else 8.0e3, "C_circuit_F": 145e-12})
    rows.extend([
        {"name": "minor_loop", "pulse": "minor_loop", "V_pos": peaks[-1], "V_neg": -0.45 * peaks[-1], "R_load_ohm": 4.0e4 if family == "nbo2" else 8.0e3, "C_circuit_F": 145e-12},
        {"name": "autonomous_rc", "pulse": "rc_oscillator", "V_bias": peaks[-1], "R_load_ohm": 12.0e3, "C_circuit_F": 145e-12},
    ])
    return rows


def _config(family: str, theta: np.ndarray, protocol: dict[str, Any]) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "ny": 6, "nt": 28, "dt": 1.0e-7, "substeps": 3,
        "activation_min_delta_T_K": 1.0, "activation_min_G_ratio": 1.01,
        **{key: value for key, value in protocol.items() if key not in {"name", "pulse"}},
    }
    if family == "nbo2":
        cfg.update({
            "Rc_TE_PCM_ohm_m2": 1.2e-10 * theta[0],
            "Rc_PCM_SnSe_barrier_ohm_m2": 2.4e-10 * theta[0],
            "Ea_scale": theta[1],
            "Rth_PCM_SnSe_barrier_m2K_W": 3.4e-8 * theta[2],
            "Rth_BE_substrate_m2K_W": 4.0e-8 * theta[2],
            "h_sub_W_m2K": 2.0e5 / theta[2],
            "thermal_capacitance_scale": theta[3],
            "nbo2_Ea_eV": 0.215,
            "nbo2_epsr": 45.0,
            "nbo2_effective_fraction_ablation": False,
        })
    else:
        cfg.update({
            "vo2_profile": "literature_anchored", "T0_K": 325.0,
            "Rth_PCM_SnSe_barrier_m2K_W": 3.4e-8 * theta[0],
            "Rth_BE_substrate_m2K_W": 4.0e-8 * theta[0],
            "h_sub_W_m2K": 2.0e5 / theta[0],
            "thermal_capacitance_scale": theta[1],
            "vo2_Tc_up_K": theta[2], "vo2_Tc_down_K": theta[3], "vo2_width_K": theta[4],
            "vo2_sigma_ins": 25.0, "vo2_sigma_met": 5.0e4,
        })
    return cfg


def _simulate(family: str, theta: np.ndarray, protocol: dict[str, Any], seed: int = 2026) -> dict[str, Any]:
    return simulate_phase_activated_multilayer_case(
        "full_stack_with_SnSe_barrier", "localized_filament", family, protocol["pulse"], seed,
        _config(family, theta, protocol),
    )


def _frequency(result: dict[str, Any]) -> float:
    signal = np.asarray(result["current"], dtype=float)
    time = np.asarray(result["time"], dtype=float)
    if signal.size < 4 or np.ptp(signal) <= 1.0e-20:
        return 0.0
    centered = signal - np.mean(signal)
    power = np.abs(np.fft.rfft(centered)) ** 2
    frequencies = np.fft.rfftfreq(signal.size, d=max(float(np.median(np.diff(time))), 1.0e-30))
    if power.size <= 1 or np.sum(power[1:]) <= 0.0:
        return 0.0
    return float(np.sum(frequencies[1:] * power[1:]) / np.sum(power[1:]))


def _observe(family: str, theta: np.ndarray, protocol: dict[str, Any], seed: int = 2026) -> tuple[np.ndarray, dict[str, Any]]:
    result = _simulate(family, theta, protocol, seed)
    I = np.asarray(result["current"], dtype=float)
    G = np.asarray(result["conductance"], dtype=float)
    V = np.asarray(result["voltage_device"], dtype=float)
    cooling = np.gradient(G)
    features = np.concatenate([I, G, V, cooling, np.asarray([_frequency(result)])])
    return features, result


def _jacobian(family: str, theta: np.ndarray, protocol: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    spec = FAMILIES[family]
    y0, result = _observe(family, theta, protocol)
    scale = np.maximum(np.abs(y0), max(float(np.std(y0)), 1.0e-15))
    columns = []
    for index, step in enumerate(spec["steps"]):
        plus = theta.copy(); minus = theta.copy()
        plus[index] += step; minus[index] -= step
        if index < 2:
            minus[index] = max(0.4, minus[index])
        yp, _ = _observe(family, plus, protocol)
        ym, _ = _observe(family, minus, protocol)
        columns.append((yp - ym) / (plus[index] - minus[index]) / scale)
    return np.stack(columns, axis=1), y0, scale


def _design(family: str) -> dict[str, Any]:
    spec = FAMILIES[family]
    candidates = []
    for protocol in _candidate_protocols(family):
        J, _, _ = _jacobian(family, spec["base"], protocol)
        singular = np.linalg.svd(J, compute_uv=False)
        gram = J.T @ J + 1.0e-10 * np.eye(J.shape[1])
        sign, logdet = np.linalg.slogdet(gram)
        _, result = _observe(family, spec["base"], protocol)
        safe = bool(result["finite_result"] and result["max_delta_T"] <= 250.0)
        candidates.append({
            "protocol": protocol, "activated": bool(result["activated"]), "safe": safe,
            "logdet": float(logdet if sign > 0 else -np.inf), "e_optimal": float(singular[-1]),
            "rank": int(np.sum(singular > 1.0e-6)), "condition_number": float(singular[0] / max(singular[-1], 1.0e-15)),
            "max_delta_T": float(result["max_delta_T"]), "energy_proxy": float(np.trapz(np.abs(result["voltage_device"] * result["current"]), result["time"])),
        })
    eligible = [row for row in candidates if row["safe"] and row["activated"]]
    pool = eligible or [row for row in candidates if row["safe"]] or candidates
    best = max(pool, key=lambda row: (row["logdet"], row["e_optimal"]))
    full_rank = bool(best["rank"] == len(spec["names"]) and best["condition_number"] < 1.0e8)
    return {
        "family": family, "candidate_count": len(candidates), "candidates": candidates, "selected": best,
        "searches_protocol_parameters": True, "selected_full_rank": full_rank,
        "design_gate_passed": full_rank,
    }


def _linearized_inverse(family: str, protocol: dict[str, Any], noise: float, seed: int) -> dict[str, Any]:
    spec = FAMILIES[family]
    base = spec["base"]
    true = spec["true"]
    J, y_base, scale = _jacobian(family, base, protocol)
    y_true, _ = _observe(family, true, protocol, 2030)
    rng = np.random.default_rng(seed)
    noisy = y_true + float(noise) * np.maximum(np.abs(y_true), np.std(y_true) + 1.0e-15) * rng.standard_normal(y_true.shape)
    target = (noisy - y_base) / scale
    estimate = base.copy()
    block_rows: dict[str, Any] = {}
    for name, indices in spec["blocks"].items():
        idx = np.asarray(indices, dtype=int)
        Jb = J[:, idx]
        delta = np.linalg.solve(Jb.T @ Jb + 1.0e-4 * np.eye(idx.size), Jb.T @ target)
        estimate[idx] = base[idx] + delta
        covariance = np.linalg.pinv(Jb.T @ Jb + 1.0e-4 * np.eye(idx.size)) * max(noise**2, 1.0e-6)
        half_width = 1.645 * np.sqrt(np.maximum(np.diag(covariance), 0.0))
        errors = np.abs(estimate[idx] - true[idx]) / np.maximum(np.abs(true[idx]), 1.0e-12)
        coverage = np.mean((true[idx] >= estimate[idx] - half_width) & (true[idx] <= estimate[idx] + half_width))
        block_rows[name] = {"median_error": float(np.median(errors)), "coverage_90": float(coverage), "success": bool(np.median(errors) <= 0.20)}
    relative = np.abs(estimate - true) / np.maximum(np.abs(true), 1.0e-12)
    return {
        "family": family, "noise": float(noise), "seed": int(seed), "estimate": estimate.tolist(), "true": true.tolist(),
        "bias": (estimate - true).tolist(), "median_error": float(np.median(relative)), "blocks": block_rows,
        "re_inverted_noisy_target": True,
    }


def run_active_protocol_design_v3(noise_seeds: int = 10) -> tuple[dict[str, Any], dict[str, Any]]:
    designs = {family: _design(family) for family in FAMILIES}
    runs = []
    for family, design in designs.items():
        protocol = design["selected"]["protocol"]
        for noise in [0.0, 0.02, 0.05]:
            for seed in range(noise_seeds):
                runs.append(_linearized_inverse(family, protocol, noise, 3000 + seed))
    aggregates: dict[str, Any] = {}
    for family, spec in FAMILIES.items():
        family_runs = [row for row in runs if row["family"] == family]
        block_summary = {}
        for block in spec["blocks"]:
            errors = [row["blocks"][block]["median_error"] for row in family_runs]
            coverages = [row["blocks"][block]["coverage_90"] for row in family_runs]
            successes = [row["blocks"][block]["success"] for row in family_runs]
            block_summary[block] = {"median_error": float(np.median(errors)), "success_rate": float(np.mean(successes)), "coverage_90": float(np.mean(coverages))}
        aggregates[family] = {"blocks": block_summary, "gate_passed": bool(all(v["median_error"] <= 0.20 and v["success_rate"] >= 0.70 and v["coverage_90"] >= 0.80 for v in block_summary.values()))}
    design_summary = {
        "benchmark": "active_protocol_design_v3", "synthetic_not_experimental": True, "families": designs,
        "uses_actual_rc_ode": True, "uses_full_terminal_traces": True, "uses_cooling_tail": True,
        "optimization": "finite candidate D/E-optimal search under Tmax and energy reporting; not continuous global optimum",
        "outputs": {"summary_json": str(DESIGN_JSON).replace("\\", "/")},
    }
    inverse_summary = {
        "benchmark": "sequential_terminal_inverse_v3", "synthetic_not_experimental": True, "noise_seeds": int(noise_seeds),
        "noise_levels": [0.0, 0.02, 0.05], "mechanism_routed_families": True, "re_inverts_each_noisy_target": True,
        "aggregates": aggregates, "gate_passed": bool(all(value["gate_passed"] for value in aggregates.values())),
        "status": "qualified_supported" if all(value["gate_passed"] for value in aggregates.values()) else "failed_but_informative",
        "runs": runs, "outputs": {"summary_json": str(INVERSE_JSON).replace("\\", "/")},
    }
    write_json(ROOT / DESIGN_JSON, design_summary); write_json(ROOT / INVERSE_JSON, inverse_summary)
    return design_summary, inverse_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noise-seeds", type=int, default=10)
    args = parser.parse_args()
    design, inverse = run_active_protocol_design_v3(args.noise_seeds)
    print(json.dumps({"selected": {key: value["selected"]["protocol"]["name"] for key, value in design["families"].items()}, "inverse_status": inverse["status"]}, indent=2))


if __name__ == "__main__":
    main()
