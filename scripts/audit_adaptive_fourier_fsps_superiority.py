"""Adaptive Fourier/F-SPS actual-training superiority audit."""
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
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_fourier_fsps_conditional_superiority import MethodPINN, _coords, _loss, _target
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/adaptive_fourier_fsps_superiority_summary.json")
CASES_CSV = Path("outputs/tables/adaptive_fourier_fsps_superiority_cases.csv")
FIG_PARETO = Path("outputs/figures/adaptive_fourier_fsps_pareto.png")
METHODS = ["fourier_off", "fourier_always_on", "f_sps_always_on", "stiffness_gated_fourier", "front_local_fourier", "adaptive_f_sps"]
CSV_FIELDS = ["method", "geometry", "transition_width", "noise", "seed", "chi", "chi_c", "selected_branch", "relative_error", "gain_over_fourier_off", "smooth_degradation", "runtime_cost", "failure", "finite_result", "is_actual_autograd_training"]


def _chi(width: float) -> float:
    return float(0.25 / max(float(width), 1.0e-8))


def _select(method: str, width: float, geometry: str, chi_c: float = 2.0) -> tuple[str, bool, bool, str, int]:
    chi = _chi(width)
    if method == "fourier_off":
        return "vanilla_mlp", False, False, "vanilla", 6
    if method == "fourier_always_on":
        return "fourier_features", False, False, "fourier", 6
    if method == "f_sps_always_on":
        return "f_sps_sampling", False, False, "f_sps", 6
    if method == "stiffness_gated_fourier":
        return ("fourier_plus_continuation_asinh", True, True, "stiff_fourier_asinh", 6) if chi > chi_c else ("vanilla_mlp", False, False, "smooth_vanilla", 6)
    if method == "front_local_fourier":
        return ("f_sps_sampling", False, False, "localized_front_sampling", 7) if geometry != "uniform_strip" else ("fourier_features", False, False, "uniform_fourier", 6)
    if method == "adaptive_f_sps":
        return ("f_sps_sampling", True, True, "adaptive_front_asinh", 6) if chi > chi_c else ("vanilla_mlp", False, False, "adaptive_smooth_off", 6)
    raise ValueError(method)


def _train(method: str, geometry: str, width: float, noise: float, seed: int, chi_c: float = 2.0, n: int = 48, eval_n: int = 64) -> dict[str, Any]:
    train_method, continuation, asinh, branch, epochs = _select(method, width, geometry, chi_c)
    torch.manual_seed(seed + len(method) * 31)
    model = MethodPINN(train_method, hidden_dim=16 if train_method == "vanilla_mlp" else 18)
    coords = _coords(seed, n, train_method, geometry)
    eval_coords = _coords(seed + 701, eval_n, train_method, geometry)
    opt = torch.optim.Adam(model.parameters(), lr=0.025)
    schedule = [0.2, 0.1, float(width)] if continuation and width <= 0.1 else [float(width)]
    history: list[float] = []
    for w in schedule:
        for _ in range(max(1, epochs // len(schedule))):
            opt.zero_grad(set_to_none=True)
            loss = _loss(model, coords, float(w), geometry, noise, asinh=asinh)
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite adaptive Fourier/F-SPS loss")
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0); opt.step()
            history.append(float(loss.detach().cpu()))
    with torch.no_grad():
        T, m = model(eval_coords); T_true, m_true = _target(eval_coords, width, geometry, noise)
        Terr = torch.sqrt(torch.mean((T - T_true) ** 2)) / torch.clamp(torch.std(T_true), min=1.0e-6)
        merr = torch.sqrt(torch.mean((m - m_true) ** 2)) / torch.clamp(torch.std(m_true), min=1.0e-6)
        rel = float(0.5 * (Terr + merr))
    return {"method": method, "geometry": geometry, "transition_width": float(width), "noise": float(noise), "seed": int(seed), "chi": _chi(width), "chi_c": float(chi_c), "selected_branch": branch, "relative_error": rel, "gain_over_fourier_off": 0.0, "smooth_degradation": 0.0, "runtime_cost": float(len(history) * n * (1.3 if train_method != "vanilla_mlp" else 1.0)), "failure": False, "finite_result": bool(np.isfinite([rel, history[0], history[-1]]).all()), "is_actual_autograd_training": True}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows: w.writerow({k: row.get(k) for k in CSV_FIELDS})


def _plot(rows: list[dict[str, Any]]) -> None:
    FIG_PARETO.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for method in METHODS:
        sub = [r for r in rows if r["method"] == method]
        ax.scatter([r["runtime_cost"] for r in sub], [r["relative_error"] for r in sub], s=24, label=method)
    ax.set_xlabel("runtime cost proxy"); ax.set_ylabel("relative error"); ax.set_title("Adaptive Fourier/F-SPS actual-training Pareto audit")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(ROOT / FIG_PARETO, dpi=150); plt.close(fig)


def run_adaptive_fourier_fsps_superiority(geometries: list[str] | None = None, widths: list[float] | None = None, noise_values: list[float] | None = None, seeds: list[int] | None = None, chi_c_values: list[float] | None = None) -> dict[str, Any]:
    geoms = geometries or ["uniform_strip", "localized_hotspot"]
    ws = widths or [0.2, 0.1, 0.05]
    noises = noise_values or [0.0, 0.02]
    seed_values = seeds or [2026, 2027]
    chis = chi_c_values or [1.5, 2.0, 3.0]
    rows = [_train(m, g, w, no, s, chi_c) for chi_c in chis for g in geoms for w in ws for no in noises for s in seed_values for m in METHODS]
    base = {(r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"]): r["relative_error"] for r in rows if r["method"] == "fourier_off"}
    for r in rows:
        b = base[(r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"])]
        r["gain_over_fourier_off"] = float((b - r["relative_error"]) / max(b, 1.0e-12))
        if r["transition_width"] >= 0.2:
            r["smooth_degradation"] = float(max(0.0, r["relative_error"] / max(b, 1.0e-12) - 1.0))
    sharp_gain = {m: float(np.median([r["gain_over_fourier_off"] for r in rows if r["method"] == m and r["transition_width"] <= 0.05])) for m in METHODS}
    smooth_deg = {m: float(np.max([r["smooth_degradation"] for r in rows if r["method"] == m])) for m in METHODS}
    pseudo_pareto = {m: float(np.mean([r["gain_over_fourier_off"] >= -0.02 for r in rows if r["method"] == m])) for m in METHODS}
    true_flags: dict[tuple[float, str, float, float, int, str], bool] = {}
    groups = sorted({(r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"]) for r in rows})
    for group in groups:
        sub = [r for r in rows if (r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"]) == group]
        for r in sub:
            dominated = any(
                (o["relative_error"] <= r["relative_error"] and o["runtime_cost"] <= r["runtime_cost"] and (o["relative_error"] < r["relative_error"] or o["runtime_cost"] < r["runtime_cost"]))
                for o in sub if o is not r
            )
            true_flags[(r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"], r["method"])] = not dominated
    pareto = {m: float(np.mean([true_flags[(r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"], r["method"])] for r in rows if r["method"] == m])) for m in METHODS}
    chi_c_results = {str(c): {m: float(np.mean([true_flags[(r["chi_c"], r["geometry"], r["transition_width"], r["noise"], r["seed"], r["method"])] for r in rows if r["method"] == m and abs(r["chi_c"] - c) < 1.0e-12])) for m in METHODS} for c in sorted({float(r["chi_c"]) for r in rows})}
    failure_rate = {m: float(np.mean([r["failure"] or not r["finite_result"] for r in rows if r["method"] == m])) for m in METHODS}
    gated_methods = ["stiffness_gated_fourier", "front_local_fourier", "adaptive_f_sps"]
    best_gated = max(gated_methods, key=lambda m: (pareto[m], sharp_gain[m] - smooth_deg[m]))
    best_gated_ok = pareto[best_gated] >= 0.70 and sharp_gain[best_gated] >= 0.15 and smooth_deg[best_gated] <= 0.10
    best_gated_status = "qualified_supported" if best_gated_ok else "failed_but_informative"
    adaptive_self_ok = pareto["adaptive_f_sps"] >= 0.70 and sharp_gain["adaptive_f_sps"] >= 0.15 and smooth_deg["adaptive_f_sps"] <= 0.10
    adaptive_status = "qualified_supported" if adaptive_self_ok else "failed_but_informative"
    summary = {
        "benchmark": "adaptive_fourier_fsps_superiority",
        "note": "Synthetic numerical actual-autograd-training audit; not universal F-SPS superiority and not experimental data.",
        "num_cases": len(rows),
        "is_actual_autograd_training": True,
        "sharp_gain_by_method": sharp_gain,
        "smooth_degradation_by_method": smooth_deg,
        "pseudo_pareto_gain_tolerance_rate_by_method": pseudo_pareto,
        "pareto_win_rate_by_method": pareto,
        "true_pareto_dominance_used": True,
        "legacy_gain_tolerance_is_not_claim_gate": True,
        "chi_c_results": chi_c_results,
        "best_gated_method_under_pareto_rule": best_gated,
        "best_gated_status": best_gated_status,
        "failure_rate_by_method": failure_rate,
        "adaptive_f_sps_status": adaptive_status,
        "universal_superiority_status": "forbidden",
        "forbidden_claims": ["universal Fourier/F-SPS superiority", "experimental validation"],
        "outputs": {
            "summary_json": str(SUMMARY_JSON).replace("\\", "/"),
            "cases_csv": str(CASES_CSV).replace("\\", "/"),
            "pareto_figure": str(FIG_PARETO).replace("\\", "/"),
        },
    }
    _write_cases(ROOT / CASES_CSV, rows); _plot(rows); write_json(ROOT / SUMMARY_JSON, summary); return summary


def main() -> None:
    argparse.ArgumentParser().parse_args(); print(run_adaptive_fourier_fsps_superiority())


if __name__ == "__main__": main()
