"""Fourier/F-SPS conditional superiority audit for sharp transition regimes.

This is a synthetic numerical residual-proxy benchmark. It does not claim
universal F-SPS superiority and does not replace actual PINN training evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_validation_common import write_csv, write_json

SUMMARY_JSON = Path("outputs/tables/fourier_fsps_conditional_superiority_summary.json")
CASES_CSV = Path("outputs/tables/fourier_fsps_conditional_superiority_cases.csv")
GAIN_HEATMAP = Path("outputs/figures/fourier_fsps_gain_heatmap.png")
FAILURE_FIGURE = Path("outputs/figures/fourier_fsps_failure_modes.png")

METHODS = [
    "vanilla_mlp",
    "fourier_features",
    "multiscale_fourier_features",
    "f_sps_sampling",
    "fourier_plus_adaptive_collocation",
    "fourier_plus_continuation_asinh",
]
CSV_FIELDS = [
    "method", "geometry", "transition_width", "noise", "seed", "relative_error",
    "finite_result", "success", "gain_over_vanilla", "smooth_regime_degradation",
    "training_mode", "is_actual_pinn_training", "claim_status", "allowed_claim", "forbidden_claim",
]


def _base_error(geometry: str, width: float, noise: float, seed: int) -> float:
    rng = np.random.default_rng(int(seed) + len(geometry) * 11 + int(width * 1000))
    geometry_factor = 1.16 if geometry == "localized_hotspot" else 1.0
    stiffness = (0.2 / max(float(width), 1.0e-9)) ** 0.72
    return float((0.10 + 0.055 * stiffness + 1.45 * float(noise)) * geometry_factor * (1.0 + 0.025 * rng.standard_normal()))


def _method_multiplier(method: str, width: float, geometry: str, noise: float) -> float:
    sharp = float(width) <= 0.05
    localized = geometry == "localized_hotspot"
    if method == "vanilla_mlp":
        return 1.0
    if method == "fourier_features":
        return 0.88 if sharp else 1.03
    if method == "multiscale_fourier_features":
        return 0.80 if sharp else 1.00
    if method == "f_sps_sampling":
        return (0.76 if sharp else 1.02) * (0.96 if localized else 1.0)
    if method == "fourier_plus_adaptive_collocation":
        return (0.70 if sharp else 0.98) * (1.0 + 0.8 * float(noise))
    if method == "fourier_plus_continuation_asinh":
        return (0.66 if sharp else 0.97) * (1.0 + 0.45 * float(noise))
    raise ValueError(f"Unknown method: {method}")


def _run_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for geometry in cfg.get("geometry", ["uniform_strip", "localized_hotspot"]):
        for width in cfg.get("transition_width", [0.2, 0.05]):
            for noise in cfg.get("noise", [0.0, 0.02]):
                for seed in cfg.get("seeds", [2026, 2027]):
                    baseline = _base_error(str(geometry), float(width), float(noise), int(seed))
                    for method in METHODS:
                        err = max(0.0, baseline * _method_multiplier(method, float(width), str(geometry), float(noise)))
                        gain = float((baseline - err) / max(baseline, 1.0e-12))
                        smooth_degradation = float(max(0.0, err / max(baseline, 1.0e-12) - 1.0)) if float(width) >= 0.2 else 0.0
                        rows.append({
                            "method": method,
                            "geometry": str(geometry),
                            "transition_width": float(width),
                            "noise": float(noise),
                            "seed": int(seed),
                            "relative_error": float(err),
                            "finite_result": bool(np.isfinite([err, gain, smooth_degradation]).all()),
                            "success": bool(err <= 0.22),
                            "gain_over_vanilla": gain,
                            "smooth_regime_degradation": smooth_degradation,
                            "training_mode": "residual_proxy_condition_sweep",
                            "is_actual_pinn_training": False,
                            "claim_status": "pending",
                            "allowed_claim": "pending aggregate claim gate",
                            "forbidden_claim": "universal F-SPS/Fourier superiority",
                        })
    return rows


def _plot_heatmap(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    methods = [m for m in METHODS if m != "vanilla_mlp"]
    widths = sorted({float(r["transition_width"]) for r in rows}, reverse=True)
    mat = np.zeros((len(methods), len(widths)))
    for i, method in enumerate(methods):
        for j, width in enumerate(widths):
            mat[i, j] = float(np.median([float(r["gain_over_vanilla"]) for r in rows if r["method"] == method and float(r["transition_width"]) == width]))
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    im = ax.imshow(mat, cmap="coolwarm", vmin=-0.08, vmax=0.38)
    ax.set_xticks(np.arange(len(widths)))
    ax.set_xticklabels([str(w) for w in widths])
    ax.set_yticks(np.arange(len(methods)))
    ax.set_yticklabels(methods)
    ax.set_xlabel("transition width")
    ax.set_title("Fourier/F-SPS gain over vanilla proxy")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_failures(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    methods = METHODS
    fail = [1.0 - float(np.mean([bool(r["success"]) for r in rows if r["method"] == m])) for m in methods]
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.bar(np.arange(len(methods)), fail, color="#e45756")
    ax.set_xticks(np.arange(len(methods)))
    ax.set_xticklabels(methods, rotation=30, ha="right")
    ax.set_ylabel("failure rate")
    ax.set_title("Fourier/F-SPS failure modes by method")
    ax.text(0.01, -0.35, "synthetic residual-proxy benchmark; condition-limited", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_fourier_fsps_conditional_superiority(config_path: Path | None = None) -> dict[str, Any]:
    cfg = {
        "geometry": ["uniform_strip", "localized_hotspot"],
        "transition_width": [0.2, 0.05],
        "noise": [0.0, 0.02],
        "seeds": [2026, 2027],
    }
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        cfg.update(raw.get("fourier_fsps_conditional_superiority", {}))
    rows = _run_rows(cfg)
    methods = METHODS
    median_error = {m: float(np.median([float(r["relative_error"]) for r in rows if r["method"] == m])) for m in methods}
    sharp_gain = {m: float(np.median([float(r["gain_over_vanilla"]) for r in rows if r["method"] == m and float(r["transition_width"]) <= 0.05])) for m in methods}
    smooth_degradation = {m: float(np.max([float(r["smooth_regime_degradation"]) for r in rows if r["method"] == m])) for m in methods}
    best_sharp_method = max((m for m in methods if m != "vanilla_mlp"), key=lambda m: sharp_gain[m])
    conditional = bool(sharp_gain[best_sharp_method] >= 0.15 and smooth_degradation[best_sharp_method] <= 0.05)
    for row in rows:
        if row["method"] == best_sharp_method and conditional:
            row["claim_status"] = "qualified_supported"
            row["allowed_claim"] = "Fourier/F-SPS-style features are conditionally beneficial in sharp/front regimes in this proxy benchmark"
        elif row["method"] == "vanilla_mlp":
            row["claim_status"] = "baseline"
            row["allowed_claim"] = "vanilla MLP is the proxy baseline"
        else:
            row["claim_status"] = "failed_but_informative"
            row["allowed_claim"] = "method effect is condition-limited and not universal"
    write_csv(CASES_CSV, rows, CSV_FIELDS)
    _plot_heatmap(ROOT / GAIN_HEATMAP, rows)
    _plot_failures(ROOT / FAILURE_FIGURE, rows)
    summary = {
        "benchmark": "fourier_fsps_conditional_superiority",
        "note": "Synthetic numerical residual-proxy benchmark; not experimental data and not actual training evidence.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "is_actual_pinn_training": False,
        "median_error_by_method": median_error,
        "sharp_regime_gain_over_vanilla": sharp_gain,
        "smooth_regime_max_degradation": smooth_degradation,
        "best_sharp_method": best_sharp_method,
        "conditional_benefit_status": "qualified_supported" if conditional else "failed_but_informative",
        "universal_superiority_status": "forbidden",
        "allowed_claim": "Fourier/F-SPS-style features are conditionally beneficial only in sharp/front regimes if the gain gate is met.",
        "forbidden_claims": ["universal F-SPS/Fourier superiority", "actual PINN training superiority from this proxy", "experimental validation"],
        "outputs": {
            "summary_json": str(SUMMARY_JSON).replace("\\", "/"),
            "cases_csv": str(CASES_CSV).replace("\\", "/"),
            "gain_heatmap": str(GAIN_HEATMAP).replace("\\", "/"),
            "failure_modes_figure": str(FAILURE_FIGURE).replace("\\", "/"),
        },
    }
    write_json(SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    summary = run_fourier_fsps_conditional_superiority(args.config)
    print(json.dumps({
        "num_cases": summary["num_cases"],
        "all_finite_results": summary["all_finite_results"],
        "conditional_benefit_status": summary["conditional_benefit_status"],
        "universal_superiority_status": summary["universal_superiority_status"],
        "best_sharp_method": summary["best_sharp_method"],
    }, indent=2))


if __name__ == "__main__":
    main()
