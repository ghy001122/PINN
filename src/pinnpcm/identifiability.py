"""Solver-first event-window identifiability utilities.

The functions in this module operate on terminal observations and numerical
Jacobians.  They do not consume PINN predictions as physical truth.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np


WINDOW_NAMES = ("pre_switch", "switch", "post_switch", "cooling_recovery")


def event_window_indices(
    t: np.ndarray,
    current: np.ndarray,
    phase: np.ndarray,
    temperature: np.ndarray,
    *,
    switch_threshold_fraction: float,
    cooling_temperature_rate_fraction: float,
    minimum_points: int,
    fallback_half_width_points: int,
) -> dict[str, np.ndarray]:
    """Create immutable event windows from phase/current and cooling rates."""

    t = np.asarray(t, dtype=float)
    current = np.asarray(current, dtype=float)
    phase_mean = np.mean(np.asarray(phase, dtype=float), axis=1)
    temperature_mean = np.mean(np.asarray(temperature, dtype=float), axis=1)
    if t.ndim != 1 or t.size < 4 * minimum_points or np.any(np.diff(t) <= 0.0):
        raise ValueError("Event-window traces require ordered time and four nonempty windows.")
    phase_rate = np.abs(np.gradient(phase_mean, t, edge_order=2))
    current_rate = np.abs(np.gradient(current, t, edge_order=2))
    phase_score = phase_rate / max(float(np.max(phase_rate)), 1.0e-30)
    current_score = current_rate / max(float(np.max(current_rate)), 1.0e-30)
    switch_score = np.maximum(phase_score, current_score)
    switch = np.flatnonzero(switch_score >= float(switch_threshold_fraction))
    if switch.size < minimum_points:
        center = int(np.argmax(switch_score))
        half = max(int(fallback_half_width_points), (minimum_points + 1) // 2)
        switch = np.arange(max(0, center - half), min(t.size, center + half + 1))
    start, stop = int(switch[0]), int(switch[-1])
    width = max(int(switch.size), int(minimum_points))
    pre = np.arange(max(0, start - width), start)
    post = np.arange(stop + 1, min(t.size, stop + 1 + width))
    if pre.size < minimum_points:
        pre = np.arange(0, minimum_points)
    if post.size < minimum_points:
        post = np.arange(max(0, t.size - 2 * minimum_points), max(0, t.size - minimum_points))
    temperature_rate = np.gradient(temperature_mean, t, edge_order=2)
    threshold = float(cooling_temperature_rate_fraction) * max(
        float(np.max(np.abs(temperature_rate))), 1.0e-30
    )
    cooling = np.flatnonzero((np.arange(t.size) > stop) & (temperature_rate <= threshold))
    if cooling.size < minimum_points:
        cooling = np.arange(t.size - minimum_points, t.size)
    windows = {
        "pre_switch": np.unique(pre.astype(int)),
        "switch": np.unique(switch.astype(int)),
        "post_switch": np.unique(post.astype(int)),
        "cooling_recovery": np.unique(cooling.astype(int)),
    }
    if set(windows) != set(WINDOW_NAMES) or any(values.size < minimum_points for values in windows.values()):
        raise RuntimeError("Preregistered event-window construction failed closed.")
    return windows


def derivative_convergence(
    jacobian_h: np.ndarray, jacobian_h_over_2: np.ndarray, *, maximum_relative_difference: float
) -> dict[str, Any]:
    """Audit two central-difference steps and a second-order Richardson limit."""

    j_h = np.asarray(jacobian_h, dtype=float)
    j_h2 = np.asarray(jacobian_h_over_2, dtype=float)
    if j_h.shape != j_h2.shape or j_h.size == 0:
        raise ValueError("Jacobian audits require equal, nonempty arrays.")
    richardson = (4.0 * j_h2 - j_h) / 3.0
    scale = max(float(np.linalg.norm(richardson)), 1.0e-30)
    h_vs_half = float(np.linalg.norm(j_h - j_h2) / scale)
    half_vs_richardson = float(np.linalg.norm(j_h2 - richardson) / scale)
    finite = bool(np.isfinite(j_h).all() and np.isfinite(j_h2).all() and np.isfinite(richardson).all())
    return {
        "central_h_vs_h_over_2_relative_difference": h_vs_half,
        "central_h_over_2_vs_richardson_relative_difference": half_vs_richardson,
        "maximum_relative_difference": max(h_vs_half, half_vs_richardson),
        "gate": float(maximum_relative_difference),
        "finite": finite,
        "pass": bool(finite and max(h_vs_half, half_vs_richardson) <= maximum_relative_difference),
        "richardson_jacobian": richardson,
    }


def svd_geometry(jacobian: np.ndarray, *, relative_rank_threshold: float = 0.05) -> dict[str, Any]:
    matrix = np.asarray(jacobian, dtype=float)
    if matrix.ndim != 2 or min(matrix.shape) == 0 or not np.isfinite(matrix).all():
        raise ValueError("SVD geometry requires a finite nonempty matrix.")
    _, singular, right_t = np.linalg.svd(matrix, full_matrices=False)
    threshold = float(relative_rank_threshold) * max(float(singular[0]), 1.0e-30)
    rank = int(np.sum(singular >= threshold))
    energy = singular**2
    probability = energy / max(float(np.sum(energy)), 1.0e-30)
    nonzero = probability[probability > 0.0]
    effective_rank = float(np.exp(-np.sum(nonzero * np.log(nonzero))))
    gaps = singular[:-1] / np.maximum(singular[1:], 1.0e-30)
    retained = singular[: max(rank, 1)]
    condition = float(retained[0] / max(retained[-1], 1.0e-30))
    return {
        "singular_values": singular,
        "threshold_rank": rank,
        "effective_rank": effective_rank,
        "spectral_gap": float(np.max(gaps)) if gaps.size else math.inf,
        "retained_condition_number": condition,
        "right_subspace": right_t[: max(rank, 1)].T,
        "information_trace": float(np.sum(energy)),
    }


def principal_angles_deg(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    q_first, _ = np.linalg.qr(np.asarray(first, dtype=float))
    q_second, _ = np.linalg.qr(np.asarray(second, dtype=float))
    singular = np.linalg.svd(q_first.T @ q_second, compute_uv=False)
    return np.degrees(np.arccos(np.clip(singular, -1.0, 1.0)))


def bootstrap_switch_geometry(
    switch_jacobian: np.ndarray,
    ordinary_jacobian: np.ndarray,
    *,
    replicates: int,
    seed: int,
    relative_rank_threshold: float,
) -> dict[str, Any]:
    switch = np.asarray(switch_jacobian, dtype=float)
    ordinary = np.asarray(ordinary_jacobian, dtype=float)
    if switch.ndim != 2 or ordinary.ndim != 2 or switch.shape[1] != ordinary.shape[1]:
        raise ValueError("Bootstrap Jacobians require matching parameter dimensions.")
    rng = np.random.default_rng(int(seed))
    angles: list[float] = []
    rank_change: list[bool] = []
    switch_rank: list[int] = []
    ordinary_rank: list[int] = []
    for _ in range(int(replicates)):
        switch_sample = switch[rng.integers(0, switch.shape[0], switch.shape[0])]
        ordinary_sample = ordinary[rng.integers(0, ordinary.shape[0], ordinary.shape[0])]
        switch_geo = svd_geometry(switch_sample, relative_rank_threshold=relative_rank_threshold)
        ordinary_geo = svd_geometry(ordinary_sample, relative_rank_threshold=relative_rank_threshold)
        angle = principal_angles_deg(switch_geo["right_subspace"], ordinary_geo["right_subspace"])
        angles.append(float(np.max(angle)) if angle.size else 0.0)
        switch_rank.append(int(switch_geo["threshold_rank"]))
        ordinary_rank.append(int(ordinary_geo["threshold_rank"]))
        rank_change.append(switch_rank[-1] != ordinary_rank[-1])
    return {
        "maximum_principal_angle_deg": np.asarray(angles),
        "angle_ci_95": [float(np.quantile(angles, 0.025)), float(np.quantile(angles, 0.975))],
        "rank_change_consistency": float(np.mean(rank_change)),
        "switch_rank": np.asarray(switch_rank),
        "ordinary_rank": np.asarray(ordinary_rank),
    }


def sid_decision(metrics: Mapping[str, Any], gates: Mapping[str, Any]) -> dict[str, Any]:
    derivative = bool(metrics["derivative_pass"])
    angle_vote = float(metrics["angle_ci_lower_deg"]) > float(gates["ec_oq_angle_bootstrap_lower_deg_min"])
    rank_vote = float(metrics["rank_change_consistency"]) >= float(
        gates["ec_oq_rank_change_bootstrap_consistency_min"]
    )
    subspace_vote = bool(derivative and (angle_vote or rank_vote))
    information_vote = float(metrics["switch_information_ratio"]) >= float(
        gates["switch_information_ratio_min"]
    )
    condition_vote = bool(
        metrics.get("training_geometry_available", False)
        and float(metrics.get("switch_training_condition_ratio", 0.0))
        >= float(gates["switch_training_condition_ratio_min"])
    )
    stability_vote = bool(
        int(metrics["stable_protocol_count"]) >= int(gates["direction_stability_min_protocols"])
        and bool(metrics["neighborhood_direction_stable"])
    )
    ec_oq = bool(subspace_vote and information_vote)
    sid = bool(ec_oq and condition_vote and stability_vote)
    if sid:
        disposition = "retain_sid_and_ec_oq_as_qualified_candidates"
    elif ec_oq:
        disposition = "delete_sid_retain_ec_oq_candidate"
    elif not subspace_vote:
        disposition = "fallback_fixed_rank1_gamma_sub_delete_sid_and_ec_oq"
    else:
        disposition = "delete_sid_and_ec_oq"
    return {
        "checks": {
            "derivative": derivative,
            "angle_vote": angle_vote,
            "rank_vote": rank_vote,
            "subspace_or_rank": subspace_vote,
            "switch_information": information_vote,
            "switch_training_condition": condition_vote,
            "protocol_and_neighborhood_stability": stability_vote,
        },
        "ec_oq_retained": ec_oq,
        "sid_retained": sid,
        "disposition": disposition,
        "claim_status": "qualified_supported" if sid else "failed_but_informative",
    }
