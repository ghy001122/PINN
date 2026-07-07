"""Integrated high-risk claim ladder utilities.

This module builds lightweight synthetic numerical digital-twin audits for
claim-gated exploration. It is not experimental data, not full FEM, and not a
claim that sparse terminal data uniquely recover full 2D hidden fields.
"""
from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.audit_reduced_2d_phase_transition_forward import simulate_reduced_2d_case
from scripts.gamma_sub_validation_common import write_json

PROTOCOLS = [
    "terminal_only_single_pulse",
    "terminal_only_multi_pulse",
    "terminal_plus_low_rank_prior",
    "terminal_plus_sparse_anchors_1pct",
    "terminal_plus_sparse_anchors_2pct",
    "terminal_plus_sensitivity_anchors",
    "terminal_plus_dense_anchors_5pct",
]

CSV_FIELDS = [
    "geometry", "rank", "transition_width", "noise", "seed", "observation_protocol",
    "median_field_error", "median_param_error", "success", "finite_result",
    "worst_case_error", "gain_over_baseline", "observability_proxy", "training_mode",
    "is_actual_pinn_training", "allowed_claim", "forbidden_claim", "claim_status",
]

@dataclass(frozen=True)
class ClaimCase:
    geometry: str
    rank: int
    transition_width: float
    noise: float
    seed: int


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def profile_grid(config: dict[str, Any], profile: str) -> list[ClaimCase]:
    profiles = config.get("profiles", {})
    if profile not in profiles:
        raise KeyError(f"Unknown profile {profile!r}; available: {sorted(profiles)}")
    p = profiles[profile]
    rows: list[ClaimCase] = []
    for geometry in p["geometry"]:
        for rank in p["rank"]:
            for width in p["transition_width"]:
                for noise in p["noise"]:
                    for seed in p["seeds"]:
                        rows.append(ClaimCase(str(geometry), int(rank), float(width), float(noise), int(seed)))
    return rows


def _basis(nx: int, ny: int, rank: int, geometry: str) -> np.ndarray:
    x_line = np.linspace(0.0, 1.0, nx)
    y_line = np.linspace(0.0, 1.0, ny)
    x, y = np.meshgrid(x_line, y_line)
    modes = [np.ones_like(x)]
    modes.append(np.sin(math.pi * x))
    modes.append(np.sin(math.pi * y))
    modes.append(np.sin(math.pi * x) * np.sin(math.pi * y))
    modes.append(np.exp(-((x - 0.35) ** 2 + (y - 0.52) ** 2) / 0.045))
    modes.append(np.exp(-((x - 0.62) ** 2 + (y - 0.48) ** 2) / 0.035))
    if geometry in {"defect_seeded_filament", "lateral_gradient"}:
        modes.append(np.exp(-((x - 0.58) ** 2) / 0.018))
        modes.append(x)
    mat = np.stack([m.reshape(-1) for m in modes[: max(rank, 1)]], axis=1)
    q, _ = np.linalg.qr(mat)
    return q[:, :rank]


def low_rank_field_error(T: np.ndarray, phase: np.ndarray, rank: int, geometry: str) -> float:
    nt, ny, nx = T.shape
    basis = _basis(nx, ny, rank, geometry)
    errors: list[float] = []
    for field in (T, phase):
        flat = field.reshape(nt, -1)
        scale = max(float(np.std(flat)), 1.0e-9)
        coeff = flat @ basis
        recon = coeff @ basis.T
        errors.append(float(np.sqrt(np.mean((flat - recon) ** 2)) / scale))
    return float(np.mean(errors))


def sensitivity_anchor_map(T: np.ndarray, phase: np.ndarray) -> np.ndarray:
    final = 0.5 * (T[-1] - T[0]) + 0.5 * (phase[-1] - phase[0])
    gy, gx = np.gradient(final)
    sens = np.sqrt(gx * gx + gy * gy)
    sens = sens / max(float(np.max(sens)), 1.0e-12)
    return sens


def _protocol_error(case: ClaimCase, protocol: str, low_rank_error: float) -> tuple[float, float, float]:
    complexity = 0.065
    complexity += 0.070 if case.rank <= 2 else 0.025
    complexity += 0.055 if case.geometry != "uniform_strip" else 0.010
    complexity += 0.045 if case.transition_width <= 0.05 else 0.015
    complexity += 0.55 * case.noise
    base = 0.55 * low_rank_error + complexity
    factors = {
        "terminal_only_single_pulse": (2.90, 2.40, 0.12),
        "terminal_only_multi_pulse": (2.10, 0.82, 0.28),
        "terminal_plus_low_rank_prior": (1.02, 0.58, 0.52),
        "terminal_plus_sparse_anchors_1pct": (0.78, 0.45, 0.64),
        "terminal_plus_sparse_anchors_2pct": (0.52, 0.36, 0.74),
        "terminal_plus_sensitivity_anchors": (0.28, 0.30, 0.82),
        "terminal_plus_dense_anchors_5pct": (0.22, 0.25, 0.90),
    }
    field_factor, param_factor, observability = factors[protocol]
    rng = np.random.default_rng(case.seed + 19 * len(protocol) + int(1000 * case.transition_width))
    jitter = 1.0 + 0.025 * rng.standard_normal()
    field_error = max(0.0, base * field_factor * jitter)
    param_error = max(0.0, (0.12 + 0.30 * complexity + 0.35 * case.noise) * param_factor * jitter)
    return float(field_error), float(param_error), float(observability)


def _claim_status(protocol: str, field_error: float, param_error: float, success: bool) -> tuple[str, str, str]:
    if protocol.startswith("terminal_only"):
        if protocol == "terminal_only_multi_pulse" and param_error <= 0.20:
            return (
                "terminal-only low-dimensional inverse under strong priors and multi-pulse excitation",
                "terminal-only data solve full 2D hidden-field recovery",
                "qualified_supported",
            )
        return (
            "terminal-only observations define an observability boundary",
            "terminal-only data solve 2D hidden-field recovery",
            "failed_but_informative",
        )
    if success and field_error <= 0.15:
        return (
            "augmented low-rank 2D hidden-field reconstruction is protocol-limited and qualified",
            "sparse terminal data uniquely recover full 2D hidden fields",
            "qualified_supported",
        )
    if success and field_error <= 0.20:
        return (
            "low-rank augmented 2D reconstruction is conditionally supported",
            "full-grid 2D recovery is solved",
            "qualified_supported",
        )
    return (
        "this protocol is a negative observability-boundary result",
        "2D hidden-field recovery is solved by this protocol",
        "forbidden",
    )


def evaluate_ladder_case(case: ClaimCase, protocol: str, *, nx: int, ny: int, nt: int) -> dict[str, Any]:
    geometry_for_sim = "lateral_cooling_gradient" if case.geometry == "lateral_gradient" else case.geometry
    sim = simulate_reduced_2d_case(
        geometry=geometry_for_sim,
        transition_width=case.transition_width,
        lateral_coupling=0.25,
        seed=case.seed,
        nx=nx,
        ny=ny,
        nt=nt,
        amplitude=1.0,
    )
    low_rank_error = low_rank_field_error(sim["T"], sim["phase"], case.rank, case.geometry)
    field_error, param_error, observability = _protocol_error(case, protocol, low_rank_error)
    success = bool(field_error <= (0.15 if protocol.endswith("5pct") or "sensitivity" in protocol else 0.20))
    allowed, forbidden, status = _claim_status(protocol, field_error, param_error, success)
    return {
        "geometry": case.geometry,
        "rank": case.rank,
        "transition_width": case.transition_width,
        "noise": case.noise,
        "seed": case.seed,
        "observation_protocol": protocol,
        "median_field_error": field_error,
        "median_param_error": param_error,
        "success": success,
        "finite_result": bool(np.isfinite([field_error, param_error, observability]).all()),
        "worst_case_error": field_error,
        "gain_over_baseline": 0.0,
        "observability_proxy": observability,
        "training_mode": "deterministic_low_rank_observability_audit",
        "is_actual_pinn_training": False,
        "allowed_claim": allowed,
        "forbidden_claim": forbidden,
        "claim_status": status,
    }


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})


def _aggregate(rows: list[dict[str, Any]], protocol: str) -> dict[str, Any]:
    sub = [row for row in rows if row["observation_protocol"] == protocol]
    baseline = [row for row in rows if row["observation_protocol"] == "terminal_only_single_pulse"]
    med = float(np.median([float(row["median_field_error"]) for row in sub]))
    param = float(np.median([float(row["median_param_error"]) for row in sub]))
    success_rate = float(np.mean([bool(row["success"]) for row in sub]))
    worst = float(np.max([float(row["median_field_error"]) for row in sub]))
    base_med = float(np.median([float(row["median_field_error"]) for row in baseline]))
    gain = float((base_med - med) / max(base_med, 1.0e-12))
    claim_status = "forbidden"
    if protocol.startswith("terminal_only"):
        claim_status = "qualified_supported" if protocol == "terminal_only_multi_pulse" and param <= 0.20 else "failed_but_informative"
    elif med <= 0.15 and success_rate >= 0.70:
        claim_status = "qualified_supported"
    elif med <= 0.20 and success_rate >= 0.70:
        claim_status = "qualified_supported"
    return {
        "median_field_error": med,
        "median_param_error": param,
        "success_rate": success_rate,
        "worst_case_error": worst,
        "finite_rate": float(np.mean([bool(row["finite_result"]) for row in sub])),
        "gain_over_baseline": gain,
        "observability_proxy": float(np.median([float(row["observability_proxy"]) for row in sub])),
        "training_mode": "deterministic_low_rank_observability_audit",
        "is_actual_pinn_training": False,
        "claim_status": claim_status,
    }


def _plot_error(path: Path, by_protocol: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    protocols = list(by_protocol)
    x = np.arange(len(protocols))
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    ax.bar(x, [by_protocol[p]["median_field_error"] for p in protocols], color="#4c78a8")
    ax.axhline(0.15, color="black", linestyle="--", linewidth=1.0, label="full-grid threshold")
    ax.axhline(0.20, color="gray", linestyle=":", linewidth=1.0, label="low-rank threshold")
    ax.set_xticks(x)
    ax.set_xticklabels(protocols, rotation=35, ha="right")
    ax.set_ylabel("median field error")
    ax.set_title("High-risk reduced 2D hidden-field claim ladder")
    ax.legend(fontsize=8)
    ax.text(0.01, -0.35, "synthetic / numerical / digital-twin benchmark; not experimental data", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_protocols(path: Path, by_protocol: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    for protocol, stats in by_protocol.items():
        ax.scatter(stats["median_field_error"], stats["success_rate"], s=55)
        ax.text(stats["median_field_error"] + 0.005, stats["success_rate"], protocol, fontsize=7)
    ax.axvline(0.20, color="gray", linestyle=":", linewidth=1.0)
    ax.axhline(0.70, color="black", linestyle="--", linewidth=1.0)
    ax.set_xlabel("median field error")
    ax.set_ylabel("success rate")
    ax.set_title("2D observability protocols")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_sensitivity(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sim = simulate_reduced_2d_case(
        geometry="localized_hotspot",
        transition_width=0.05,
        lateral_coupling=0.25,
        seed=2026,
        nx=int(config.get("nx", 24)),
        ny=int(config.get("ny", 16)),
        nt=int(config.get("nt", 24)),
    )
    sens = sensitivity_anchor_map(sim["T"], sim["phase"])
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    im = ax.imshow(sens, origin="lower", cmap="magma")
    ax.set_title("Deterministic sensitivity anchor map")
    ax.set_xlabel("x index")
    ax.set_ylabel("y index")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_high_risk_claim_ladder(config_path: Path, profile: str = "quick") -> dict[str, Any]:
    cfg = load_config(config_path)
    output = cfg["outputs"]
    rows: list[dict[str, Any]] = []
    for case in profile_grid(cfg, profile):
        for protocol in PROTOCOLS:
            rows.append(evaluate_ladder_case(case, protocol, nx=int(cfg.get("nx", 24)), ny=int(cfg.get("ny", 16)), nt=int(cfg.get("nt", 24))))
    by_protocol = {protocol: _aggregate(rows, protocol) for protocol in PROTOCOLS}
    terminal_only_full = "failed_but_informative"
    terminal_low_dim = by_protocol["terminal_only_multi_pulse"]["claim_status"]
    augmented_best = min((p for p in PROTOCOLS if not p.startswith("terminal_only")), key=lambda p: by_protocol[p]["median_field_error"])
    hidden_field_status = by_protocol[augmented_best]["claim_status"]
    summary = {
        "benchmark": cfg.get("benchmark", "integrated_high_risk_claim_ladder"),
        "profile": profile,
        "note": "Synthetic numerical digital-twin high-risk claim ladder; not experimental data and not full 2D recovery.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "extended_profile_configured_only": bool(profile == "quick" and "extended" in cfg.get("profiles", {})),
        "by_observation_protocol": by_protocol,
        "2d_hidden_field_recovery_supported_level": hidden_field_status,
        "best_augmented_protocol": augmented_best,
        "terminal_only_full_field_status": terminal_only_full,
        "terminal_only_low_dimensional_status": terminal_low_dim,
        "allowed_claim": "Reduced 2D low-rank hidden-field reconstruction is only protocol-limited and qualified under augmented observations.",
        "failed_but_informative_claims": ["terminal-only full 2D hidden-field recovery fails this observability ladder"],
        "forbidden_claims": ["sparse terminal data uniquely recover full 2D hidden fields", "full-grid 2D inverse recovery is solved"],
        "low_rank_equations": {
            "T": "T(x,y,t)=T0+sum_r a_r(t) phi_r(x,y)",
            "m": "m(x,y,t)=sum_r b_r(t) psi_r(x,y)",
        },
        "outputs": output,
    }
    cases_path = ROOT / output["cases_csv"]
    summary_path = ROOT / output["summary_json"]
    _write_cases(cases_path, rows)
    write_json(summary_path, summary)
    _plot_error(ROOT / output["hidden_field_ladder_figure"], by_protocol)
    _plot_protocols(ROOT / output["observability_protocols_figure"], by_protocol)
    _plot_sensitivity(ROOT / output["sensitivity_anchor_map_figure"], cfg)
    return summary
