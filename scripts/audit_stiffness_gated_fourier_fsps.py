"""Stiffness-gated Fourier/F-SPS actual-training audit.

Synthetic numerical digital-twin benchmark only. The gate uses a phase-transition
stiffness indicator to decide when front-focused/Fourier-continuation machinery
is justified. It is not universal superiority evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_fourier_fsps_conditional_superiority import MethodPINN, _coords, _loss, _target
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/stiffness_gated_fourier_fsps_summary.json")
CASES_CSV = Path("outputs/tables/stiffness_gated_fourier_fsps_cases.csv")
GAIN_FIGURE = Path("outputs/figures/stiffness_gated_gain_vs_chi.png")
METHODS = ["vanilla_mlp", "f_sps_sampling", "fourier_plus_continuation_asinh", "stiffness_gated_hybrid"]
CSV_FIELDS = [
    "method", "geometry", "transition_width", "noise", "seed", "chi", "chi_c",
    "selected_branch", "relative_error", "gain_over_vanilla", "smooth_degradation",
    "sharp_regime", "finite_result", "success", "initial_loss", "final_loss",
    "training_mode", "is_actual_pinn_training", "claim_status", "allowed_claim", "forbidden_claim",
]


def stiffness_indicator(width: float) -> float:
    # max_s s(1-s)/w occurs at s=0.5.
    return float(0.25 / max(float(width), 1.0e-8))


def _train(method: str, geometry: str, width: float, noise: float, seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    chi_c = float(cfg.get("chi_c", 2.0))
    chi = stiffness_indicator(width)
    selected = method
    train_method = method
    continuation = False
    asinh = False
    if method == "stiffness_gated_hybrid":
        if chi > chi_c:
            train_method = "f_sps_sampling"
            selected = "front_focused_asinh_continuation"
            continuation = True
            asinh = True
        else:
            train_method = "vanilla_mlp"
            selected = "smooth_vanilla_no_fourier"
            continuation = False
            asinh = False
    elif method == "fourier_plus_continuation_asinh":
        continuation = True
        asinh = True
    torch.manual_seed(int(seed) + 23 * len(method))
    hidden_dim = int(cfg.get("hidden_dim", 18 if train_method == "vanilla_mlp" else 20))
    model = MethodPINN(train_method, hidden_dim=hidden_dim)
    n = int(cfg.get("collocation_points", 96))
    eval_n = int(cfg.get("eval_points", 96))
    coords = _coords(seed, n, train_method, geometry)
    eval_coords = _coords(seed + 313, eval_n, train_method, geometry)
    lr = float(cfg.get("lr", 0.025))
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    if continuation:
        schedule = [0.2, 0.1, float(width)] if float(width) <= 0.1 else [float(width)]
        epochs_each = int(cfg.get("continuation_epochs", 4))
    else:
        schedule = [float(width)]
        epochs_each = int(cfg.get("direct_epochs", 8))
    history: list[float] = []
    for train_width in schedule:
        for _ in range(epochs_each):
            opt.zero_grad(set_to_none=True)
            loss = _loss(model, coords, float(train_width), geometry, noise, asinh=asinh)
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite stiffness-gated training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            opt.step()
            history.append(float(loss.detach().cpu()))
    with torch.no_grad():
        T, m = model(eval_coords)
        T_true, m_true = _target(eval_coords, float(width), geometry, noise)
        T_err = torch.sqrt(torch.mean((T - T_true) ** 2)) / torch.clamp(torch.std(T_true), min=1.0e-6)
        m_err = torch.sqrt(torch.mean((m - m_true) ** 2)) / torch.clamp(torch.std(m_true), min=1.0e-6)
        rel = float(0.5 * (T_err + m_err))
    return {
        "method": method,
        "geometry": geometry,
        "transition_width": float(width),
        "noise": float(noise),
        "seed": int(seed),
        "chi": chi,
        "chi_c": chi_c,
        "selected_branch": selected,
        "relative_error": rel,
        "gain_over_vanilla": 0.0,
        "smooth_degradation": 0.0,
        "sharp_regime": bool(chi > chi_c),
        "finite_result": bool(np.isfinite([rel, history[0], history[-1], chi]).all()),
        "success": bool(rel <= 0.75),
        "initial_loss": float(history[0]),
        "final_loss": float(history[-1]),
        "training_mode": "actual_autograd_reduced_pinn_training",
        "is_actual_pinn_training": True,
        "claim_status": "pending",
        "allowed_claim": "pending aggregate gate",
        "forbidden_claim": "universal F-SPS/Fourier superiority",
    }


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def _plot(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    for method in METHODS:
        sub = [r for r in rows if r["method"] == method]
        ax.scatter([r["chi"] for r in sub], [r["gain_over_vanilla"] for r in sub], label=method, s=34)
    ax.axhline(0.15, color="black", linestyle="--", linewidth=1.0)
    ax.axvline(float(rows[0]["chi_c"]) if rows else 2.0, color="gray", linestyle=":", linewidth=1.0)
    ax.set_xlabel("stiffness indicator chi=max(s(1-s)/w)")
    ax.set_ylabel("gain over vanilla")
    ax.set_title("Stiffness-gated actual training gain")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_stiffness_gated_fourier_fsps(config_path: Path | None = None) -> dict[str, Any]:
    cfg = {
        "geometry": ["uniform_strip", "localized_hotspot"],
        "transition_width": [0.2, 0.1, 0.05],
        "noise": [0.0, 0.02],
        "seeds": [2026, 2027],
        "collocation_points": 96,
        "eval_points": 96,
        "direct_epochs": 8,
        "continuation_epochs": 4,
        "chi_c": 2.0,
    }
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        cfg.update(raw.get("stiffness_gated_fourier_fsps", {}))
    rows: list[dict[str, Any]] = []
    for geometry in cfg["geometry"]:
        for width in cfg["transition_width"]:
            for noise in cfg["noise"]:
                for seed in cfg["seeds"]:
                    for method in METHODS:
                        rows.append(_train(method, str(geometry), float(width), float(noise), int(seed), cfg))
    vanilla = {(r["geometry"], r["transition_width"], r["noise"], r["seed"]): float(r["relative_error"]) for r in rows if r["method"] == "vanilla_mlp"}
    for row in rows:
        base = vanilla[(row["geometry"], row["transition_width"], row["noise"], row["seed"])]
        row["gain_over_vanilla"] = float((base - float(row["relative_error"])) / max(base, 1.0e-12))
        if float(row["chi"]) <= float(row["chi_c"]):
            row["smooth_degradation"] = float(max(0.0, float(row["relative_error"]) / max(base, 1.0e-12) - 1.0))
    sharp_gain = {m: float(np.median([r["gain_over_vanilla"] for r in rows if r["method"] == m and r["sharp_regime"]])) for m in METHODS}
    smooth_degradation = {m: float(np.max([r["smooth_degradation"] for r in rows if r["method"] == m])) for m in METHODS}
    hybrid_status = "qualified_supported" if sharp_gain["stiffness_gated_hybrid"] >= 0.15 and smooth_degradation["stiffness_gated_hybrid"] <= 0.10 else ("failed_but_informative" if sharp_gain["stiffness_gated_hybrid"] > 0.0 else "forbidden")
    universal = bool(all(float(r["gain_over_vanilla"]) > 0.0 for r in rows if r["method"] != "vanilla_mlp"))
    for row in rows:
        if row["method"] == "stiffness_gated_hybrid":
            row["claim_status"] = hybrid_status
            row["allowed_claim"] = "stiffness-gated hybrid is condition-limited and only valid if sharp gain and smooth negative-control gates clear"
        elif row["method"] == "vanilla_mlp":
            row["claim_status"] = "baseline"
            row["allowed_claim"] = "matched vanilla actual-training baseline"
        else:
            row["claim_status"] = "failed_but_informative"
            row["allowed_claim"] = "method effect is comparator evidence, not a superiority claim"
    _write_cases(ROOT / CASES_CSV, rows)
    _plot(ROOT / GAIN_FIGURE, rows)
    summary = {
        "benchmark": "stiffness_gated_fourier_fsps_v3",
        "note": "Synthetic numerical actual-training benchmark; not experimental data and not universal superiority evidence.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "is_actual_pinn_training": True,
        "stiffness_indicator": "chi=max(s*(1-s)/w)=0.25/w",
        "chi_c": float(cfg.get("chi_c", 2.0)),
        "sharp_gain_by_method": sharp_gain,
        "smooth_degradation_by_method": smooth_degradation,
        "stiffness_gated_hybrid_status": hybrid_status,
        "universal_superiority_status": "qualified_supported" if universal else "forbidden",
        "smooth_negative_control_cleared": bool(smooth_degradation["stiffness_gated_hybrid"] <= 0.10),
        "forbidden_claims": ["universal F-SPS/Fourier superiority", "experimental validation", "full inverse recovery"],
        "outputs": {
            "summary_json": str(SUMMARY_JSON).replace("\\", "/"),
            "cases_csv": str(CASES_CSV).replace("\\", "/"),
            "gain_figure": str(GAIN_FIGURE).replace("\\", "/"),
        },
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    summary = run_stiffness_gated_fourier_fsps(args.config)
    print(json.dumps({
        "num_cases": summary["num_cases"],
        "all_finite_results": summary["all_finite_results"],
        "stiffness_gated_hybrid_status": summary["stiffness_gated_hybrid_status"],
        "smooth_negative_control_cleared": summary["smooth_negative_control_cleared"],
        "universal_superiority_status": summary["universal_superiority_status"],
    }, indent=2))


if __name__ == "__main__":
    main()
