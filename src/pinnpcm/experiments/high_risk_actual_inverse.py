"""Actual low-rank 2D inverse audit for the high-risk claim ladder.

Synthetic numerical digital-twin benchmark only. This optimizes low-rank field
coefficients from generated terminal and anchor observations. It is not full
arbitrary 2D hidden-field recovery and not experimental validation.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from scripts.audit_reduced_2d_phase_transition_forward import simulate_reduced_2d_case
from scripts.gamma_sub_validation_common import write_json
from pinnpcm.experiments.high_risk_claim_ladder import ClaimCase, _basis, load_config, profile_grid, sensitivity_anchor_map

ROOT = Path(__file__).resolve().parents[3]

ACTUAL_PROTOCOLS = [
    "terminal_only_multi_pulse",
    "terminal_plus_sparse_anchors_2pct",
    "terminal_plus_sensitivity_anchors",
    "terminal_plus_dense_anchors_5pct",
]

ACTUAL_CSV_FIELDS = [
    "geometry", "rank", "transition_width", "noise", "seed", "observation_protocol",
    "actual_inverse_mode", "field_error", "param_error", "terminal_loss", "anchor_loss",
    "rank_prior_loss", "smooth_time_loss", "field_success", "param_success", "finite_result",
    "training_mode", "is_actual_pinn_training", "field_recovery_status",
    "low_dim_parameter_status", "allowed_claim", "forbidden_claim",
]


def _anchor_cells(protocol: str, T: np.ndarray, phase: np.ndarray, case: ClaimCase) -> np.ndarray:
    _, ny, nx = T.shape
    n_cells = ny * nx
    if protocol == "terminal_only_multi_pulse":
        return np.asarray([], dtype=int)
    sens = sensitivity_anchor_map(T, phase).reshape(-1)
    basis = _basis(nx, ny, case.rank, case.geometry)
    leverage = np.linalg.norm(basis, axis=1)
    leverage = leverage / max(float(np.max(leverage)), 1.0e-12)
    if protocol == "terminal_plus_dense_anchors_5pct":
        count = max(case.rank + 2, int(round(0.05 * n_cells)))
        score = 0.55 * sens + 0.45 * leverage
        return np.argsort(score)[-count:]
    if protocol == "terminal_plus_sensitivity_anchors":
        count = max(case.rank, int(round(0.02 * n_cells)))
        score = 0.75 * sens + 0.25 * leverage
        return np.argsort(score)[-count:]
    if protocol == "terminal_plus_sparse_anchors_2pct":
        count = max(case.rank, int(round(0.02 * n_cells)))
        rng = np.random.default_rng(case.seed + 1009)
        return np.sort(rng.choice(n_cells, size=count, replace=False))
    raise ValueError(f"Unknown actual protocol: {protocol}")


def _project_initial(field0: np.ndarray, basis: np.ndarray) -> np.ndarray:
    return field0.reshape(-1) @ basis


def _solve_low_rank_coefficients(
    *,
    field: np.ndarray,
    basis: np.ndarray,
    anchor_cells: np.ndarray,
    terminal_mean: np.ndarray | None,
    noise: float,
    rng: np.random.Generator,
    weights: dict[str, float],
) -> tuple[np.ndarray, dict[str, float]]:
    nt = field.shape[0]
    rank = basis.shape[1]
    n_unknown = nt * rank
    rows: list[np.ndarray] = []
    targets: list[float] = []
    tags: list[str] = []

    def add_row(t: int, vec: np.ndarray, target: float, weight: float, tag: str) -> None:
        row = np.zeros(n_unknown, dtype=float)
        row[t * rank : (t + 1) * rank] = math.sqrt(weight) * vec
        rows.append(row)
        targets.append(math.sqrt(weight) * float(target))
        tags.append(tag)

    if terminal_mean is not None:
        mean_vec = basis.mean(axis=0)
        terminal_obs = np.asarray(terminal_mean, dtype=float).copy()
        if noise > 0.0:
            terminal_obs += noise * max(float(np.std(terminal_obs)), 1.0e-8) * rng.standard_normal(terminal_obs.shape)
        for t, value in enumerate(terminal_obs):
            add_row(t, mean_vec, float(value), weights.get("terminal", 1.0), "terminal")

    if anchor_cells.size:
        for t in range(nt):
            obs = field[t].reshape(-1)[anchor_cells].astype(float).copy()
            if noise > 0.0:
                obs += noise * max(float(np.std(obs)), 1.0e-8) * rng.standard_normal(obs.shape)
            for cell, target in zip(anchor_cells, obs):
                add_row(t, basis[int(cell)], float(target), weights.get("anchor", 1.0), "anchor")

    coeff0 = _project_initial(field[0], basis)
    for r in range(rank):
        unit = np.zeros(rank, dtype=float)
        unit[r] = 1.0
        add_row(0, unit, float(coeff0[r]), weights.get("rank_prior", 0.02), "rank_prior")

    if weights.get("smooth_time", 0.0) > 0.0:
        for t in range(1, nt):
            for r in range(rank):
                row = np.zeros(n_unknown, dtype=float)
                w = math.sqrt(weights["smooth_time"])
                row[t * rank + r] = w
                row[(t - 1) * rank + r] = -w
                rows.append(row)
                targets.append(0.0)
                tags.append("smooth_time")

    A = np.vstack(rows) if rows else np.eye(n_unknown)
    y = np.asarray(targets, dtype=float) if targets else np.zeros(n_unknown)
    coeff_vec, *_ = np.linalg.lstsq(A, y, rcond=None)
    residual = A @ coeff_vec - y
    losses: dict[str, float] = {}
    for tag in {"terminal", "anchor", "rank_prior", "smooth_time"}:
        idx = [i for i, value in enumerate(tags) if value == tag]
        losses[f"{tag}_loss"] = float(np.mean(residual[idx] ** 2)) if idx else 0.0
    return coeff_vec.reshape(nt, rank) @ basis.T, losses


def evaluate_actual_inverse_case(case: ClaimCase, protocol: str, *, nx: int, ny: int, nt: int) -> dict[str, Any]:
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
    T = np.asarray(sim["T"], dtype=float)
    phase = np.asarray(sim["phase"], dtype=float)
    basis = _basis(nx, ny, case.rank, case.geometry)
    anchors = _anchor_cells(protocol, T, phase, case)
    rng = np.random.default_rng(case.seed + len(protocol) * 31 + int(10000 * case.transition_width))
    weights = {"terminal": 8.0, "anchor": 12.0, "rank_prior": 0.03, "smooth_time": 0.015}
    T_pred_flat, T_losses = _solve_low_rank_coefficients(
        field=T,
        basis=basis,
        anchor_cells=anchors,
        terminal_mean=None,
        noise=case.noise,
        rng=rng,
        weights=weights,
    )
    phase_pred_flat, phase_losses = _solve_low_rank_coefficients(
        field=phase,
        basis=basis,
        anchor_cells=anchors,
        terminal_mean=phase.reshape(nt, -1).mean(axis=1),
        noise=case.noise,
        rng=rng,
        weights=weights,
    )
    T_pred = T_pred_flat.reshape(nt, ny, nx)
    phase_pred = np.clip(phase_pred_flat.reshape(nt, ny, nx), 0.0, 1.0)
    # Claim gate is for recovery inside the configured low-rank subspace.
    # Full arbitrary-grid recovery remains explicitly forbidden in the summary.
    T_lr = ((T.reshape(nt, -1) @ basis) @ basis.T).reshape(nt, ny, nx)
    phase_lr = ((phase.reshape(nt, -1) @ basis) @ basis.T).reshape(nt, ny, nx)
    T_err = float(np.sqrt(np.mean((T_pred - T_lr) ** 2)) / max(float(np.std(T_lr)), 1.0e-8))
    phase_err = float(np.sqrt(np.mean((phase_pred - phase_lr) ** 2)) / max(float(np.std(phase_lr)), 1.0e-8))
    field_error = float(0.5 * (T_err + phase_err))
    true_mean = phase.reshape(nt, -1).mean(axis=1)
    pred_mean = phase_pred.reshape(nt, -1).mean(axis=1)
    param_error = float(np.sqrt(np.mean((pred_mean - true_mean) ** 2)) / max(float(np.std(true_mean)), 1.0e-8))
    field_success = bool(field_error <= 0.20)
    param_success = bool(param_error <= 0.20)
    if protocol == "terminal_only_multi_pulse":
        field_status = "failed_but_informative" if not field_success else "qualified_supported"
        param_status = "qualified_supported" if param_success else "failed_but_informative"
        allowed = "terminal-only multi-pulse supports only low-dimensional parameter recovery under strong priors" if param_success else "terminal-only multi-pulse remains an observability boundary"
    elif field_success:
        field_status = "qualified_supported"
        param_status = "qualified_supported" if param_success else "failed_but_informative"
        allowed = "actual low-rank 2D inverse is protocol-limited and requires augmented observations"
    else:
        field_status = "forbidden"
        param_status = "qualified_supported" if param_success else "failed_but_informative"
        allowed = "actual inverse result is negative for field recovery under this protocol"
    return {
        "geometry": case.geometry,
        "rank": case.rank,
        "transition_width": case.transition_width,
        "noise": case.noise,
        "seed": case.seed,
        "observation_protocol": protocol,
        "actual_inverse_mode": True,
        "field_error": field_error,
        "param_error": param_error,
        "terminal_loss": phase_losses.get("terminal_loss", 0.0),
        "anchor_loss": float(0.5 * (T_losses.get("anchor_loss", 0.0) + phase_losses.get("anchor_loss", 0.0))),
        "rank_prior_loss": float(0.5 * (T_losses.get("rank_prior_loss", 0.0) + phase_losses.get("rank_prior_loss", 0.0))),
        "smooth_time_loss": float(0.5 * (T_losses.get("smooth_time_loss", 0.0) + phase_losses.get("smooth_time_loss", 0.0))),
        "field_success": field_success,
        "param_success": param_success,
        "finite_result": bool(np.isfinite([field_error, param_error]).all()),
        "training_mode": "actual_weighted_low_rank_inverse",
        "is_actual_pinn_training": False,
        "field_recovery_status": field_status,
        "low_dim_parameter_status": param_status,
        "allowed_claim": allowed,
        "forbidden_claim": "full-grid arbitrary 2D recovery or terminal-only full hidden-field recovery",
    }


def _write_actual_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ACTUAL_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in ACTUAL_CSV_FIELDS})


def _aggregate_actual(rows: list[dict[str, Any]], protocol: str) -> dict[str, Any]:
    sub = [row for row in rows if row["observation_protocol"] == protocol]
    median_field = float(np.median([float(row["field_error"]) for row in sub]))
    median_param = float(np.median([float(row["param_error"]) for row in sub]))
    field_success = float(np.mean([bool(row["field_success"]) for row in sub]))
    param_success = float(np.mean([bool(row["param_success"]) for row in sub]))
    if protocol == "terminal_only_multi_pulse":
        field_status = "failed_but_informative" if field_success == 0.0 else "qualified_supported"
        param_status = "qualified_supported" if median_param <= 0.20 and param_success >= 0.70 else "failed_but_informative"
    else:
        field_status = "qualified_supported" if median_field <= 0.20 and field_success >= 0.70 else "forbidden"
        param_status = "qualified_supported" if median_param <= 0.20 and param_success >= 0.70 else "failed_but_informative"
    return {
        "median_field_error": median_field,
        "median_param_error": median_param,
        "field_success_rate": field_success,
        "param_success_rate": param_success,
        "worst_case_field_error": float(np.max([float(row["field_error"]) for row in sub])),
        "finite_rate": float(np.mean([bool(row["finite_result"]) for row in sub])),
        "actual_inverse_mode": True,
        "training_mode": "actual_weighted_low_rank_inverse",
        "field_recovery_status": field_status,
        "low_dim_parameter_status": param_status,
    }


def _plot_actual_inverse_error(path: Path, by_protocol: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    protocols = list(by_protocol)
    x = np.arange(len(protocols))
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(x - 0.18, [by_protocol[p]["median_field_error"] for p in protocols], width=0.36, label="field", color="#4c78a8")
    ax.bar(x + 0.18, [by_protocol[p]["median_param_error"] for p in protocols], width=0.36, label="parameter", color="#f58518")
    ax.axhline(0.20, color="black", linestyle="--", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(protocols, rotation=30, ha="right")
    ax.set_ylabel("normalized error")
    ax.set_title("Actual low-rank inverse error by protocol")
    ax.legend(fontsize=8)
    ax.text(0.01, -0.34, "synthetic / numerical / digital-twin benchmark; low-rank inverse only", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_high_risk_claim_ladder_actual_inverse(config_path: Path, profile: str = "quick") -> dict[str, Any]:
    cfg = load_config(config_path)
    actual_output = cfg.get("actual_inverse_outputs") or {
        "summary_json": "outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json",
        "cases_csv": "outputs/tables/high_risk_claim_ladder_actual_inverse_cases.csv",
        "error_by_protocol_figure": "outputs/figures/high_risk_actual_inverse_error_by_protocol.png",
    }
    rows: list[dict[str, Any]] = []
    for case in profile_grid(cfg, profile):
        for protocol in ACTUAL_PROTOCOLS:
            rows.append(evaluate_actual_inverse_case(case, protocol, nx=int(cfg.get("nx", 24)), ny=int(cfg.get("ny", 16)), nt=int(cfg.get("nt", 24))))
    by_protocol = {protocol: _aggregate_actual(rows, protocol) for protocol in ACTUAL_PROTOCOLS}
    best = min((p for p in ACTUAL_PROTOCOLS if not p.startswith("terminal_only")), key=lambda p: by_protocol[p]["median_field_error"])
    terminal = by_protocol["terminal_only_multi_pulse"]
    summary = {
        "benchmark": "high_risk_claim_ladder_actual_inverse",
        "profile": profile,
        "note": "Synthetic numerical digital-twin actual low-rank inverse audit; not experimental data and not full arbitrary 2D recovery.",
        "actual_inverse_mode": True,
        "num_cases": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "by_observation_protocol": by_protocol,
        "best_augmented_protocol": best,
        "field_recovery_status": by_protocol[best]["field_recovery_status"],
        "low_dim_parameter_status": by_protocol[best]["low_dim_parameter_status"],
        "terminal_only_field_status": terminal["field_recovery_status"],
        "terminal_only_parameter_status": terminal["low_dim_parameter_status"],
        "full_grid_arbitrary_recovery_status": "forbidden",
        "loss_terms": ["L_terminal", "L_anchor", "L_rank_prior", "L_smooth_time"],
        "allowed_claim": "Actual low-rank 2D inverse is only protocol-limited and qualified when augmented observations clear the claim gate.",
        "forbidden_claims": ["full-grid arbitrary 2D recovery", "terminal-only full hidden-field recovery", "experimental validation"],
        "outputs": actual_output,
    }
    _write_actual_cases(ROOT / actual_output["cases_csv"], rows)
    write_json(ROOT / actual_output["summary_json"], summary)
    _plot_actual_inverse_error(ROOT / actual_output["error_by_protocol_figure"], by_protocol)
    return summary
