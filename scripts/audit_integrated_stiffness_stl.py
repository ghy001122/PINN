"""Actual reduced PINN stiffness and Seiler-style STL quick audit.

The benchmark is synthetic numerical digital-twin evidence only. It implements
small autograd residual training to separate actual PINN training from older
residual-proxy results, but it is not a full STL-PINN reproduction on device data.
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

DEFAULT_CONFIG = Path("configs/high_risk_claim_ladder.yaml")
SUMMARY_JSON = Path("outputs/tables/integrated_stiffness_stl_summary.json")
CASES_CSV = Path("outputs/tables/integrated_stiffness_stl_cases.csv")
ERROR_FIGURE = Path("outputs/figures/integrated_stiffness_error_by_algorithm.png")
CONVERGENCE_FIGURE = Path("outputs/figures/integrated_stiffness_convergence.png")
TRANSFER_FIGURE = Path("outputs/figures/integrated_stl_transfer_gain.png")

ALGORITHMS = [
    "direct_sharp_training",
    "continuation_plus_asinh",
    "continuation_plus_asinh_plus_adaptive",
    "Seiler_style_multi_head_STL_frozen_trunk",
    "Seiler_style_multi_head_STL_unfrozen_tail",
]
CSV_FIELDS = [
    "algorithm", "seed", "noise", "target_transition_width", "relative_error", "success",
    "finite_result", "final_loss", "initial_loss", "gain_over_direct", "training_mode",
    "is_actual_pinn_training", "heads_used", "trunk_frozen_during_transfer", "transfer_protocol",
    "claim_status", "allowed_claim", "forbidden_claim",
]

class MultiHeadPINN(nn.Module):
    def __init__(self, heads: list[str], hidden_dim: int = 18) -> None:
        super().__init__()
        self.trunk = nn.Sequential(nn.Linear(3, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, hidden_dim), nn.Tanh())
        self.heads = nn.ModuleDict({head: nn.Linear(hidden_dim, 2) for head in heads})

    def forward(self, coords: torch.Tensor, head: str) -> tuple[torch.Tensor, torch.Tensor]:
        raw = self.heads[head](self.trunk(coords))
        T = 0.15 + torch.nn.functional.softplus(raw[:, 0:1])
        m = torch.sigmoid(raw[:, 1:2])
        return T, m


def _target(coords: torch.Tensor, width: float, noise: float = 0.0) -> tuple[torch.Tensor, torch.Tensor]:
    x, y, t = coords[:, 0:1], coords[:, 1:2], coords[:, 2:3]
    hotspot = torch.exp(-((x - 0.38) ** 2 + (y - 0.55) ** 2) / 0.045)
    filament = torch.exp(-((x - 0.62) ** 2) / 0.035) * (0.75 + 0.25 * torch.cos(2.0 * math.pi * y) ** 2)
    T = 0.25 + 0.62 * torch.sin(math.pi * t).square() * (0.72 * hotspot + 0.28 * filament)
    T = T + float(noise) * 0.02 * torch.sin(5.0 * math.pi * x) * torch.cos(3.0 * math.pi * y)
    m = torch.sigmoid((T - 0.54) / max(float(width), 1.0e-4))
    return T.detach(), m.detach()


def _residual_loss(model: MultiHeadPINN, coords_base: torch.Tensor, head: str, width: float, *, asinh: bool, adaptive: bool, noise: float) -> torch.Tensor:
    coords = coords_base.detach().clone().requires_grad_(True)
    T, m = model(coords, head)
    grad_T = torch.autograd.grad(T.sum(), coords, create_graph=True)[0]
    dT_dt = grad_T[:, 2:3]
    dT_dx = grad_T[:, 0:1]
    dT_dy = grad_T[:, 1:2]
    d2T_dx2 = torch.autograd.grad(dT_dx.sum(), coords, create_graph=True)[0][:, 0:1]
    d2T_dy2 = torch.autograd.grad(dT_dy.sum(), coords, create_graph=True)[0][:, 1:2]
    grad_m = torch.autograd.grad(m.sum(), coords, create_graph=True)[0]
    dm_dt = grad_m[:, 2:3]
    x, y, t = coords[:, 0:1], coords[:, 1:2], coords[:, 2:3]
    source = 0.55 * torch.exp(-((x - 0.38) ** 2 + (y - 0.55) ** 2) / 0.05) * (0.25 + torch.sin(math.pi * t).square())
    R_T = dT_dt - 0.020 * d2T_dx2 - 0.018 * d2T_dy2 - source + 0.18 * (T - 0.25)
    switch = torch.sigmoid((T - 0.54) / max(float(width), 1.0e-4))
    R_m = dm_dt - (switch - m) / 0.22
    if asinh:
        R_T = torch.asinh(R_T / 0.15)
        R_m = torch.asinh(R_m / 0.15)
    if adaptive:
        wT = 1.0 / (R_T.detach().abs().mean() + 0.05)
        wm = 1.0 / (R_m.detach().abs().mean() + 0.05)
    else:
        wT = torch.tensor(1.0, dtype=coords.dtype, device=coords.device)
        wm = torch.tensor(1.0, dtype=coords.dtype, device=coords.device)
    T_true, m_true = _target(coords, width, noise)
    anchor = torch.mean((T - T_true) ** 2) + torch.mean((m - m_true) ** 2)
    return wT * torch.mean(R_T.square()) + wm * torch.mean(R_m.square()) + 0.35 * anchor


def _eval_error(model: MultiHeadPINN, coords: torch.Tensor, head: str, width: float, noise: float) -> float:
    with torch.no_grad():
        T, m = model(coords, head)
        T_true, m_true = _target(coords, width, noise)
        T_err = torch.sqrt(torch.mean((T - T_true) ** 2)) / torch.clamp(torch.std(T_true), min=1.0e-6)
        m_err = torch.sqrt(torch.mean((m - m_true) ** 2)) / torch.clamp(torch.std(m_true), min=1.0e-6)
        return float(0.5 * (T_err + m_err))


def _coords(seed: int, n: int = 42) -> torch.Tensor:
    generator = torch.Generator().manual_seed(int(seed))
    return torch.rand((n, 3), generator=generator, dtype=torch.float32)


def _train_steps(model: MultiHeadPINN, coords: torch.Tensor, head: str, width: float, epochs: int, *, lr: float, asinh: bool, adaptive: bool, noise: float) -> list[float]:
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    history: list[float] = []
    for _ in range(int(epochs)):
        opt.zero_grad(set_to_none=True)
        loss = _residual_loss(model, coords, head, width, asinh=asinh, adaptive=adaptive, noise=noise)
        if not torch.isfinite(loss):
            raise FloatingPointError("non-finite stiffness residual loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 10.0)
        opt.step()
        history.append(float(loss.detach().cpu()))
    return history


def _run_algorithm(algorithm: str, seed: int, noise: float, target_width: float, cfg: dict[str, Any]) -> dict[str, Any]:
    torch.manual_seed(int(seed))
    coords = _coords(seed, int(cfg.get("collocation_points", 42)))
    eval_coords = _coords(seed + 103, int(cfg.get("eval_points", 72)))
    low_widths = [0.4, 0.2, 0.1]
    target_head = "w005"
    lr = float(cfg.get("lr", 0.025))
    hist: list[float] = []
    trunk_frozen = False
    transfer_protocol = "none"
    if algorithm.startswith("Seiler_style"):
        heads = ["w04", "w02", "w01"] + [target_head]
        model = MultiHeadPINN(heads, hidden_dim=int(cfg.get("hidden_dim", 18)))
        for head_key, width in zip(["w04", "w02", "w01"], low_widths):
            hist.extend(_train_steps(model, coords, head_key, width, int(cfg.get("stl_low_epochs", 10)), lr=lr, asinh=True, adaptive=True, noise=noise))
        model.heads[target_head].load_state_dict(model.heads["w01"].state_dict())
        for p in model.trunk.parameters():
            p.requires_grad_(False)
        trunk_frozen = True
        transfer_protocol = "low_width_multi_head_pretrain_then_high_width_head_transfer"
        hist.extend(_train_steps(model, coords, target_head, target_width, int(cfg.get("stl_transfer_epochs", 22)), lr=lr, asinh=True, adaptive=True, noise=noise))
        if algorithm.endswith("unfrozen_tail"):
            for p in model.trunk.parameters():
                p.requires_grad_(True)
            hist.extend(_train_steps(model, coords, target_head, target_width, int(cfg.get("stl_unfreeze_epochs", 12)), lr=lr * 0.35, asinh=True, adaptive=True, noise=noise))
    else:
        model = MultiHeadPINN([target_head], hidden_dim=int(cfg.get("hidden_dim", 18)))
        if algorithm == "direct_sharp_training":
            hist.extend(_train_steps(model, coords, target_head, target_width, int(cfg.get("direct_epochs", 16)), lr=lr, asinh=False, adaptive=False, noise=noise))
        elif algorithm == "continuation_plus_asinh":
            for width in [0.2, 0.1, target_width]:
                hist.extend(_train_steps(model, coords, target_head, width, int(cfg.get("continuation_epochs", 12)), lr=lr, asinh=True, adaptive=False, noise=noise))
        elif algorithm == "continuation_plus_asinh_plus_adaptive":
            for width in [0.2, 0.1, target_width]:
                hist.extend(_train_steps(model, coords, target_head, width, int(cfg.get("continuation_epochs", 12)), lr=lr, asinh=True, adaptive=True, noise=noise))
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    rel_error = _eval_error(model, eval_coords, target_head, target_width, noise)
    finite = bool(np.isfinite([rel_error, hist[0], hist[-1]]).all())
    heads_used = ";".join(["w04", "w02", "w01", target_head]) if algorithm.startswith("Seiler_style") else target_head
    return {
        "algorithm": algorithm,
        "seed": int(seed),
        "noise": float(noise),
        "target_transition_width": float(target_width),
        "relative_error": float(rel_error),
        "success": bool(rel_error <= 0.55),
        "finite_result": finite,
        "final_loss": float(hist[-1]),
        "initial_loss": float(hist[0]),
        "gain_over_direct": 0.0,
        "training_mode": "actual_autograd_reduced_pinn_training",
        "is_actual_pinn_training": True,
        "heads_used": heads_used,
        "trunk_frozen_during_transfer": bool(trunk_frozen),
        "transfer_protocol": transfer_protocol,
        "claim_status": "forbidden",
        "allowed_claim": "pending aggregate claim gate",
        "forbidden_claim": "full STL-PINN reproduction or solved stiff PINN training",
        "history": hist,
    }


def _plot_error(path: Path, median_error: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    algs = list(median_error)
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    ax.bar(np.arange(len(algs)), [median_error[a] for a in algs], color="#4c78a8")
    ax.set_xticks(np.arange(len(algs)))
    ax.set_xticklabels(algs, rotation=30, ha="right")
    ax.set_ylabel("median relative field error")
    ax.set_title("Actual reduced PINN stiffness quick audit")
    ax.text(0.01, -0.35, "synthetic / numerical / digital-twin benchmark; not experimental data", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_convergence(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    seen: set[str] = set()
    for row in rows:
        if row["algorithm"] in seen:
            continue
        seen.add(row["algorithm"])
        hist = row.get("history", [])
        ax.plot(hist, label=row["algorithm"])
    ax.set_yscale("log")
    ax.set_xlabel("optimizer step")
    ax.set_ylabel("training loss")
    ax.set_title("Convergence traces")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_transfer(path: Path, gains: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    keys = [k for k in gains if "Seiler_style" in k or "continuation" in k]
    ax.bar(np.arange(len(keys)), [gains[k] for k in keys], color="#54a24b")
    ax.axhline(0.20, color="black", linestyle="--", linewidth=1.0)
    ax.set_xticks(np.arange(len(keys)))
    ax.set_xticklabels(keys, rotation=30, ha="right")
    ax.set_ylabel("gain over direct")
    ax.set_title("Transfer and continuation gain")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_integrated_stiffness_stl(config_path: Path | None = None) -> dict[str, Any]:
    cfg = {
        "seeds": [2026, 2027],
        "noise": [0.0, 0.02],
        "target_transition_width": 0.05,
        "hidden_dim": 18,
        "collocation_points": 42,
        "eval_points": 72,
    }
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        cfg.update(raw.get("integrated_stiffness_stl", {}))
    rows: list[dict[str, Any]] = []
    for seed in cfg["seeds"]:
        for noise in cfg["noise"]:
            for algorithm in ALGORITHMS:
                rows.append(_run_algorithm(algorithm, int(seed), float(noise), float(cfg["target_transition_width"]), cfg))
    direct_by_key = {(r["seed"], r["noise"]): float(r["relative_error"]) for r in rows if r["algorithm"] == "direct_sharp_training"}
    for row in rows:
        direct = direct_by_key[(row["seed"], row["noise"])]
        row["gain_over_direct"] = float((direct - float(row["relative_error"])) / max(direct, 1.0e-12))
    median_error = {a: float(np.median([float(r["relative_error"]) for r in rows if r["algorithm"] == a])) for a in ALGORITHMS}
    gains = {a: float(np.median([float(r["gain_over_direct"]) for r in rows if r["algorithm"] == a])) for a in ALGORITHMS}
    for row in rows:
        gain = gains[row["algorithm"]]
        if row["algorithm"] == "direct_sharp_training":
            status = "failed_but_informative"
            allowed = "direct sharp training provides the stiffness baseline"
        elif "Seiler_style" in row["algorithm"] and gain >= 0.20:
            status = "qualified_supported"
            allowed = "Seiler-style multi-head transfer is supported in a reduced synthetic benchmark"
        elif gain >= 0.20:
            status = "qualified_supported"
            allowed = "continuation/asinh/adaptive residual handling mitigates stiffness-induced degradation"
        else:
            status = "failed_but_informative"
            allowed = "this algorithm does not clear the 20 percent gain gate in this run"
        row["claim_status"] = status
        row["allowed_claim"] = allowed
    clean_rows = [{k: v for k, v in row.items() if k != "history"} for row in rows]
    write_csv(CASES_CSV, clean_rows, CSV_FIELDS)
    _plot_error(ROOT / ERROR_FIGURE, median_error)
    _plot_convergence(ROOT / CONVERGENCE_FIGURE, rows)
    _plot_transfer(ROOT / TRANSFER_FIGURE, gains)
    summary = {
        "benchmark": "integrated_stiffness_stl",
        "note": "Synthetic numerical reduced PINN autograd-residual audit; not experimental data and not a full STL-PINN reproduction.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(r["finite_result"] for r in rows)),
        "actual_stiffness_pinn_training_completed": True,
        "seiler_style_multi_head_transfer_implemented": True,
        "residuals": {
            "R_T": "C_T dT/dt - k_x d2T/dx2 - k_y d2T/dy2 - Q_Joule + gamma_sub(T-T0)",
            "R_m": "dm/dt - (s(T;T_sw,w)-m)/tau_m",
        },
        "median_error_by_algorithm": median_error,
        "gain_over_direct_by_algorithm": gains,
        "continuation_asinh_adaptive_status": "qualified_supported" if gains["continuation_plus_asinh_plus_adaptive"] >= 0.20 else "failed_but_informative",
        "seiler_style_multi_head_stl_status": "qualified_supported" if max(gains["Seiler_style_multi_head_STL_frozen_trunk"], gains["Seiler_style_multi_head_STL_unfrozen_tail"]) >= 0.20 else "failed_but_informative",
        "full_stl_pinn_reproduction_status": "forbidden",
        "allowed_claim": "Reduced actual PINN training supports only condition-limited stiffness-mitigation wording if gains clear the gate.",
        "forbidden_claims": ["full STL-PINN reproduction", "stiff PINN training is solved generally", "experimental validation"],
        "outputs": {
            "summary_json": str(SUMMARY_JSON).replace("\\", "/"),
            "cases_csv": str(CASES_CSV).replace("\\", "/"),
            "error_figure": str(ERROR_FIGURE).replace("\\", "/"),
            "convergence_figure": str(CONVERGENCE_FIGURE).replace("\\", "/"),
            "transfer_figure": str(TRANSFER_FIGURE).replace("\\", "/"),
        },
    }
    write_json(SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    summary = run_integrated_stiffness_stl(args.config)
    print(json.dumps({
        "num_cases": summary["num_cases"],
        "all_finite_results": summary["all_finite_results"],
        "actual_stiffness_pinn_training_completed": summary["actual_stiffness_pinn_training_completed"],
        "seiler_style_multi_head_transfer_implemented": summary["seiler_style_multi_head_transfer_implemented"],
        "seiler_style_multi_head_stl_status": summary["seiler_style_multi_head_stl_status"],
    }, indent=2))


if __name__ == "__main__":
    main()
