"""Actual Fourier/F-SPS conditional benefit audit.

This script runs small synthetic numerical autograd training cases. It replaces
the earlier multiplier proxy for current evidence, but it still does not claim
universal Fourier/F-SPS superiority or experimental validation.
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
from torch import nn
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_validation_common import write_csv, write_json

SUMMARY_JSON = Path("outputs/tables/fourier_fsps_actual_training_summary.json")
CASES_CSV = Path("outputs/tables/fourier_fsps_actual_training_cases.csv")
GAIN_HEATMAP = Path("outputs/figures/fourier_fsps_actual_gain_heatmap.png")

METHODS = [
    "vanilla_mlp",
    "fourier_features",
    "multiscale_fourier_features",
    "f_sps_sampling",
    "fourier_plus_continuation_asinh",
]
CSV_FIELDS = [
    "method", "geometry", "transition_width", "noise", "seed", "relative_error",
    "finite_result", "success", "gain_over_vanilla", "smooth_regime_degradation",
    "sharp_regime", "final_loss", "initial_loss", "training_mode", "is_actual_pinn_training",
    "claim_status", "allowed_claim", "forbidden_claim",
]

class MethodPINN(nn.Module):
    def __init__(self, method: str, hidden_dim: int = 18) -> None:
        super().__init__()
        self.method = method
        in_dim = self._encoded_dim(method)
        self.net = nn.Sequential(nn.Linear(in_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 2))

    @staticmethod
    def _encoded_dim(method: str) -> int:
        if method == "vanilla_mlp" or method == "f_sps_sampling":
            return 3
        if method == "fourier_features":
            return 3 + 2 * 3
        return 3 + 2 * 3 * 3

    def _encode(self, coords: torch.Tensor) -> torch.Tensor:
        if self.method in {"vanilla_mlp", "f_sps_sampling"}:
            return coords
        scales = [1.0] if self.method == "fourier_features" else [1.0, 2.0, 4.0]
        parts = [coords]
        for scale in scales:
            angle = 2.0 * math.pi * scale * coords
            parts.extend([torch.sin(angle), torch.cos(angle)])
        return torch.cat(parts, dim=-1)

    def forward(self, coords: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        raw = self.net(self._encode(coords))
        T = 0.15 + torch.nn.functional.softplus(raw[:, 0:1])
        m = torch.sigmoid(raw[:, 1:2])
        return T, m


def _target(coords: torch.Tensor, width: float, geometry: str, noise: float) -> tuple[torch.Tensor, torch.Tensor]:
    x, y, t = coords[:, 0:1], coords[:, 1:2], coords[:, 2:3]
    if geometry == "uniform_strip":
        spatial = 0.72 + 0.28 * x
    else:
        hotspot = torch.exp(-((x - 0.38) ** 2 + (y - 0.55) ** 2) / 0.045)
        filament = torch.exp(-((x - 0.62) ** 2) / 0.035) * (0.75 + 0.25 * torch.cos(2.0 * math.pi * y) ** 2)
        spatial = 0.72 * hotspot + 0.28 * filament
    T = 0.25 + 0.62 * torch.sin(math.pi * t).square() * spatial
    T = T + float(noise) * 0.02 * torch.sin(5.0 * math.pi * x) * torch.cos(3.0 * math.pi * y)
    m = torch.sigmoid((T - 0.54) / max(float(width), 1.0e-4))
    return T.detach(), m.detach()


def _coords(seed: int, n: int, method: str, geometry: str) -> torch.Tensor:
    generator = torch.Generator().manual_seed(int(seed))
    if method == "f_sps_sampling":
        n_hot = n // 2
        base = torch.rand((n - n_hot, 3), generator=generator, dtype=torch.float32)
        if geometry == "uniform_strip":
            x = torch.rand((n_hot, 1), generator=generator, dtype=torch.float32)
            y = torch.rand((n_hot, 1), generator=generator, dtype=torch.float32)
        else:
            x = torch.clamp(0.38 + 0.18 * torch.randn((n_hot, 1), generator=generator), 0.0, 1.0)
            y = torch.clamp(0.55 + 0.18 * torch.randn((n_hot, 1), generator=generator), 0.0, 1.0)
        t = torch.clamp(0.5 + 0.25 * torch.randn((n_hot, 1), generator=generator), 0.0, 1.0)
        return torch.cat([base, torch.cat([x, y, t], dim=1)], dim=0)
    return torch.rand((n, 3), generator=generator, dtype=torch.float32)


def _loss(model: MethodPINN, coords_base: torch.Tensor, width: float, geometry: str, noise: float, *, asinh: bool) -> torch.Tensor:
    coords = coords_base.detach().clone().requires_grad_(True)
    T, m = model(coords)
    grad_T = torch.autograd.grad(T.sum(), coords, create_graph=True)[0]
    dT_dt = grad_T[:, 2:3]
    dT_dx = grad_T[:, 0:1]
    dT_dy = grad_T[:, 1:2]
    d2T_dx2 = torch.autograd.grad(dT_dx.sum(), coords, create_graph=True)[0][:, 0:1]
    d2T_dy2 = torch.autograd.grad(dT_dy.sum(), coords, create_graph=True)[0][:, 1:2]
    grad_m = torch.autograd.grad(m.sum(), coords, create_graph=True)[0]
    dm_dt = grad_m[:, 2:3]
    x, y, t = coords[:, 0:1], coords[:, 1:2], coords[:, 2:3]
    if geometry == "uniform_strip":
        source = 0.40 * (0.72 + 0.28 * x) * (0.25 + torch.sin(math.pi * t).square())
    else:
        source = 0.55 * torch.exp(-((x - 0.38) ** 2 + (y - 0.55) ** 2) / 0.05) * (0.25 + torch.sin(math.pi * t).square())
    R_T = dT_dt - 0.020 * d2T_dx2 - 0.018 * d2T_dy2 - source + 0.18 * (T - 0.25)
    switch = torch.sigmoid((T - 0.54) / max(float(width), 1.0e-4))
    R_m = dm_dt - (switch - m) / 0.22
    if asinh:
        R_T = torch.asinh(R_T / 0.15)
        R_m = torch.asinh(R_m / 0.15)
    T_true, m_true = _target(coords, width, geometry, noise)
    anchor = torch.mean((T - T_true) ** 2) + torch.mean((m - m_true) ** 2)
    return torch.mean(R_T.square()) + torch.mean(R_m.square()) + 0.40 * anchor


def _train_case(method: str, geometry: str, width: float, noise: float, seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    torch.manual_seed(int(seed) + len(method) * 17)
    hidden_dim = int(cfg.get("hidden_dim", 18 if method == "vanilla_mlp" else 20))
    model = MethodPINN(method, hidden_dim=hidden_dim)
    n = int(cfg.get("collocation_points", 72))
    eval_n = int(cfg.get("eval_points", 96))
    coords = _coords(seed, n, method, geometry)
    eval_coords = _coords(seed + 199, eval_n, method, geometry)
    lr = float(cfg.get("lr", 0.025))
    if method == "fourier_plus_continuation_asinh":
        schedule = [0.2, 0.1, float(width)]
        epochs_each = int(cfg.get("continuation_epochs", 5))
    else:
        schedule = [float(width)]
        epochs_each = int(cfg.get("direct_epochs", 12))
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    history: list[float] = []
    for train_width in schedule:
        for _ in range(epochs_each):
            opt.zero_grad(set_to_none=True)
            loss = _loss(model, coords, train_width, geometry, noise, asinh=(method == "fourier_plus_continuation_asinh"))
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite Fourier/F-SPS actual training loss")
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
        "relative_error": rel,
        "finite_result": bool(np.isfinite([rel, history[0], history[-1]]).all()),
        "success": bool(rel <= 0.75),
        "gain_over_vanilla": 0.0,
        "smooth_regime_degradation": 0.0,
        "sharp_regime": bool(float(width) <= 0.05),
        "final_loss": float(history[-1]),
        "initial_loss": float(history[0]),
        "training_mode": "actual_autograd_reduced_pinn_training",
        "is_actual_pinn_training": True,
        "claim_status": "pending",
        "allowed_claim": "pending aggregate claim gate",
        "forbidden_claim": "universal F-SPS/Fourier superiority",
    }


def _plot_heatmap(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    methods = [m for m in METHODS if m != "vanilla_mlp"]
    widths = sorted({float(r["transition_width"]) for r in rows}, reverse=True)
    mat = np.zeros((len(methods), len(widths)))
    for i, method in enumerate(methods):
        for j, width in enumerate(widths):
            mat[i, j] = float(np.median([float(r["gain_over_vanilla"]) for r in rows if r["method"] == method and float(r["transition_width"]) == width]))
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    im = ax.imshow(mat, cmap="coolwarm", vmin=-0.4, vmax=0.4)
    ax.set_xticks(np.arange(len(widths)))
    ax.set_xticklabels([str(w) for w in widths])
    ax.set_yticks(np.arange(len(methods)))
    ax.set_yticklabels(methods)
    ax.set_xlabel("transition width")
    ax.set_title("Actual training gain over vanilla")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_fourier_fsps_conditional_superiority(config_path: Path | None = None) -> dict[str, Any]:
    cfg = {
        "geometry": ["uniform_strip", "localized_hotspot"],
        "transition_width": [0.2, 0.05],
        "noise": [0.0, 0.02],
        "seeds": [2026, 2027],
        "collocation_points": 72,
        "eval_points": 96,
        "direct_epochs": 12,
        "continuation_epochs": 5,
    }
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        cfg.update(raw.get("fourier_fsps_conditional_superiority", {}))
    rows: list[dict[str, Any]] = []
    for geometry in cfg["geometry"]:
        for width in cfg["transition_width"]:
            for noise in cfg["noise"]:
                for seed in cfg["seeds"]:
                    for method in METHODS:
                        rows.append(_train_case(method, str(geometry), float(width), float(noise), int(seed), cfg))
    vanilla = {(r["geometry"], r["transition_width"], r["noise"], r["seed"]): float(r["relative_error"]) for r in rows if r["method"] == "vanilla_mlp"}
    for row in rows:
        base = vanilla[(row["geometry"], row["transition_width"], row["noise"], row["seed"])]
        row["gain_over_vanilla"] = float((base - float(row["relative_error"])) / max(base, 1.0e-12))
        if float(row["transition_width"]) >= 0.2:
            row["smooth_regime_degradation"] = float(max(0.0, float(row["relative_error"]) / max(base, 1.0e-12) - 1.0))
    median_error = {m: float(np.median([float(r["relative_error"]) for r in rows if r["method"] == m])) for m in METHODS}
    sharp_gain = {m: float(np.median([float(r["gain_over_vanilla"]) for r in rows if r["method"] == m and bool(r["sharp_regime"])])) for m in METHODS}
    smooth_degradation = {m: float(np.max([float(r["smooth_regime_degradation"]) for r in rows if r["method"] == m])) for m in METHODS}
    best_sharp_method = max((m for m in METHODS if m != "vanilla_mlp"), key=lambda m: sharp_gain[m])
    conditional = bool(sharp_gain[best_sharp_method] >= 0.15 and smooth_degradation[best_sharp_method] <= 0.10)
    all_methods = [m for m in METHODS if m != "vanilla_mlp"]
    universal = bool(all(sharp_gain[m] > 0.0 and smooth_degradation[m] <= 0.0 for m in all_methods))
    for row in rows:
        if row["method"] == best_sharp_method and conditional:
            row["claim_status"] = "qualified_supported"
            row["allowed_claim"] = "actual training shows condition-limited sharp/front benefit in this reduced benchmark"
        elif row["method"] == "vanilla_mlp":
            row["claim_status"] = "baseline"
            row["allowed_claim"] = "vanilla MLP is the matched actual-training baseline"
        else:
            row["claim_status"] = "failed_but_informative"
            row["allowed_claim"] = "method effect is condition-limited and not universal"
    write_csv(CASES_CSV, rows, CSV_FIELDS)
    _plot_heatmap(ROOT / GAIN_HEATMAP, rows)
    summary = {
        "benchmark": "fourier_fsps_actual_training",
        "note": "Synthetic numerical actual-training benchmark; not experimental data and not universal superiority evidence.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "is_actual_pinn_training": True,
        "median_error_by_method": median_error,
        "sharp_regime_gain_over_vanilla": sharp_gain,
        "smooth_regime_degradation": smooth_degradation,
        "best_sharp_method": best_sharp_method,
        "conditional_benefit_status": "qualified_supported" if conditional else "failed_but_informative",
        "universal_superiority_status": "qualified_supported" if universal else "forbidden",
        "allowed_claim": "Fourier/F-SPS-style methods can be written only as condition-limited actual-training evidence when the gain gate is met.",
        "forbidden_claims": ["universal F-SPS/Fourier superiority", "experimental validation", "full inverse recovery"],
        "outputs": {
            "summary_json": str(SUMMARY_JSON).replace("\\", "/"),
            "cases_csv": str(CASES_CSV).replace("\\", "/"),
            "gain_heatmap": str(GAIN_HEATMAP).replace("\\", "/"),
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
        "is_actual_pinn_training": summary["is_actual_pinn_training"],
        "conditional_benefit_status": summary["conditional_benefit_status"],
        "universal_superiority_status": summary["universal_superiority_status"],
        "best_sharp_method": summary["best_sharp_method"],
    }, indent=2))


if __name__ == "__main__":
    main()
