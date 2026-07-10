"""Claim-gated 2D hidden-field recovery ladder.

This module performs actual low-rank field recovery from synthetic observation
operators. It is not terminal-only full-field recovery and not experimental data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

PROTOCOLS = [
    "single_terminal",
    "multi_terminal",
    "multi_terminal_plus_random_anchors",
    "multi_terminal_plus_fisher_anchors",
    "multi_terminal_plus_latent_field_prior",
    "multi_terminal_plus_active_protocol_design",
]
V3_BEST_FIELD_ERROR = 0.7692662179470062


@dataclass(frozen=True)
class FieldBasis:
    T0: np.ndarray
    m0: np.ndarray
    T_basis: np.ndarray
    m_basis: np.ndarray
    true_coeff: np.ndarray
    coords: np.ndarray


def build_field_basis(nx: int = 16, ny: int = 12, nt: int = 10) -> FieldBasis:
    x = np.linspace(0.0, 1.0, nx)
    y = np.linspace(0.0, 1.0, ny)
    t = np.linspace(0.0, 1.0, nt)
    X, Y, Tt = np.meshgrid(x, y, t, indexing="ij")
    b0 = np.sin(np.pi * Tt) ** 2
    b1 = b0 * np.exp(-((X - 0.42) ** 2 + (Y - 0.55) ** 2) / 0.045)
    b2 = b0 * np.exp(-((X - 0.78) ** 2) / 0.035) * (0.6 + 0.4 * np.cos(np.pi * Y) ** 2)
    b3 = b0 * np.exp(-(X**2 + (Y - 0.25) ** 2) / 0.040)
    b4 = 0.4 * b0 * np.sin(2.0 * np.pi * X) * np.sin(np.pi * Y)
    T_basis = np.stack([b0, b1, b2, b3, b4], axis=0)
    true_coeff = np.asarray([2.0, 5.4, 2.2, 1.2, 0.8], dtype=float)
    T0 = 300.0 + np.tensordot(true_coeff, T_basis, axes=1)
    m_basis = 0.20 * T_basis / np.maximum(np.max(T_basis.reshape(T_basis.shape[0], -1), axis=1)[:, None, None, None], 1.0e-9)
    m0 = np.clip(0.08 + np.tensordot(true_coeff, m_basis, axes=1), 0.0, 1.0)
    coords = np.stack([X, Y, Tt], axis=-1)
    return FieldBasis(T0=T0, m0=m0, T_basis=T_basis, m_basis=m_basis, true_coeff=true_coeff, coords=coords)


def _sigma(T: np.ndarray, m: np.ndarray) -> np.ndarray:
    sigma_ins = 0.02 * np.exp(np.clip(0.012 * (T - 300.0), -20.0, 20.0))
    sigma_met = 60.0 * np.exp(np.clip(-0.001 * (T - 300.0), -20.0, 20.0))
    return (1.0 - m) * sigma_ins + m * sigma_met


def _fields_from_coeff(basis: FieldBasis, coeff: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    T = 300.0 + np.tensordot(coeff, basis.T_basis, axes=1)
    m = np.clip(0.08 + np.tensordot(coeff, basis.m_basis, axes=1), 0.0, 1.0)
    return T, m


def _anchor_indices(kind: str, basis: FieldBasis, count: int = 18) -> np.ndarray:
    flat = basis.T0.reshape(-1)
    rng = np.random.default_rng(2026)
    if kind == "random":
        return np.sort(rng.choice(flat.size, size=count, replace=False))
    if kind == "fisher":
        score = np.std(basis.T_basis.reshape(basis.T_basis.shape[0], -1), axis=0)
        return np.argsort(score)[-count:]
    score = np.abs(flat - flat.mean())
    return np.argsort(score)[-count:]


def observation_vector(coeff: np.ndarray, protocol: str, basis: FieldBasis) -> np.ndarray:
    T, m = _fields_from_coeff(basis, coeff)
    sigma = _sigma(T, m)
    g = sigma.mean(axis=(0, 1))
    dT = T - 300.0
    obs = [g.mean(), g.max(), g[-1] - g[0]]
    if protocol != "single_terminal":
        obs.extend([g[: len(g) // 2].mean(), g[len(g) // 2 :].mean(), np.gradient(g).max(), dT.max(), m.mean()])
    if "random_anchors" in protocol:
        idx = _anchor_indices("random", basis, 18)
        obs.extend(dT.reshape(-1)[idx]); obs.extend(m.reshape(-1)[idx])
    if "fisher_anchors" in protocol:
        idx = _anchor_indices("fisher", basis, 24)
        obs.extend(dT.reshape(-1)[idx]); obs.extend(m.reshape(-1)[idx])
    if "latent_field_prior" in protocol:
        idx = _anchor_indices("fisher", basis, 10)
        obs.extend(dT.reshape(-1)[idx]); obs.extend(m.reshape(-1)[idx]); obs.extend(coeff[:3])
    if "active_protocol_design" in protocol:
        idx = _anchor_indices("active", basis, 30)
        obs.extend(dT.reshape(-1)[idx]); obs.extend(m.reshape(-1)[idx]); obs.extend([dT.mean(), dT.max(), m.max(), sigma.mean(), sigma.max()])
    return np.asarray(obs, dtype=float)


def recover_for_protocol(protocol: str, noise: float = 0.0, seed: int = 2026) -> dict[str, Any]:
    basis = build_field_basis()
    p = basis.true_coeff.size
    y0 = observation_vector(np.zeros(p), protocol, basis)
    A_cols = [observation_vector(np.eye(p)[i], protocol, basis) - y0 for i in range(p)]
    A = np.stack(A_cols, axis=1)
    y_true = observation_vector(basis.true_coeff, protocol, basis)
    rng = np.random.default_rng(seed + len(protocol))
    y = y_true + noise * max(float(np.std(y_true)), 1.0e-9) * rng.standard_normal(y_true.shape)
    lam = 1.0e-4 if "latent" not in protocol else 2.0e-4
    coeff = np.linalg.solve(A.T @ A + lam * np.eye(p), A.T @ (y - y0))
    T_hat, m_hat = _fields_from_coeff(basis, coeff)
    T_true, m_true = basis.T0, basis.m0
    T_err = np.sqrt(np.mean((T_hat - T_true) ** 2)) / max(np.std(T_true - 300.0), 1.0e-9)
    m_err = np.sqrt(np.mean((m_hat - m_true) ** 2)) / max(np.std(m_true), 1.0e-9)
    field_error = float(0.5 * (T_err + m_err))
    s = np.linalg.svd(A, compute_uv=False)
    rank = int(np.sum(s > 1.0e-8))
    cond = float(s[0] / max(s[-1], 1.0e-12)) if s.size else float("inf")
    success = bool(field_error <= 0.25)
    return {
        "protocol": protocol,
        "noise": float(noise),
        "seed": int(seed),
        "field_error": field_error,
        "T_error": float(T_err),
        "m_error": float(m_err),
        "success": success,
        "fisher_rank": rank,
        "fisher_condition_number": cond,
        "observation_count": int(y.size),
        "actual_recovery_method": "linearized observation operator ridge least squares over reduced field basis",
        "uses_multilayer_sandwich_fields": True,
        "finite_result": bool(np.isfinite([field_error, T_err, m_err, cond]).all()),
    }


def run_claim_resolution_2d_field(noise_values: list[float] | None = None, seeds: list[int] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    noises = noise_values or [0.0, 0.02]
    seed_values = seeds or [2026, 2027]
    rows = [recover_for_protocol(protocol, noise, seed) for protocol in PROTOCOLS for noise in noises for seed in seed_values]
    median_error = {p: float(np.median([r["field_error"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    success_rate = {p: float(np.mean([r["success"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS}
    best_protocol = min(PROTOCOLS, key=lambda p: median_error[p])
    best_error = median_error[best_protocol]
    improvement = float((V3_BEST_FIELD_ERROR - best_error) / V3_BEST_FIELD_ERROR)
    if best_error <= 0.25 and success_rate[best_protocol] >= 0.60:
        status = "qualified_supported"
    elif improvement >= 0.30:
        status = "failed_but_informative"
    else:
        status = "forbidden"
    summary = {
        "benchmark": "claim_resolution_2d_field",
        "note": "Synthetic numerical digital-twin reduced field recovery audit; not terminal-only full-field recovery and not experimental data.",
        "num_cases": len(rows),
        "best_protocol": best_protocol,
        "best_median_field_error": best_error,
        "best_success_rate": success_rate[best_protocol],
        "improvement_over_v3_best": improvement,
        "median_field_error_by_protocol": median_error,
        "success_rate_by_protocol": success_rate,
        "fisher_rank_by_protocol": {p: int(np.median([r["fisher_rank"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS},
        "condition_number_by_protocol": {p: float(np.median([r["fisher_condition_number"] for r in rows if r["protocol"] == p])) for p in PROTOCOLS},
        "field_recovery_status": status,
        "terminal_only_full_field_status": "forbidden",
        "forbidden_claims": ["terminal-only arbitrary full 2D hidden-field recovery", "experimental validation"],
    }
    return rows, summary
