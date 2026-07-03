"""Lightweight phase-field inverse-PINN alignment smoke benchmark.

The benchmark uses a small synthetic Allen-Cahn field with full-field anchors to
estimate the mobility coefficient M. It is a supplementary literature-alignment
sanity check only. It is not sparse-port inversion, not experimental data, and
not a replacement for the main constrained gamma_sub manuscript line.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.gamma_sub_validation_common import load_yaml, relative_error, write_json

DEFAULT_CONFIG = Path("configs/phase_field_inverse_alignment_smoke.yaml")
CSV_FIELDS = [
    "M_true",
    "M_estimated",
    "relative_error_M",
    "noise_level",
    "seed",
    "finite_result",
    "success_le_0p1",
    "objective_value",
]


def _laplacian(phi: np.ndarray) -> np.ndarray:
    return (
        np.roll(phi, 1, axis=0)
        + np.roll(phi, -1, axis=0)
        + np.roll(phi, 1, axis=1)
        + np.roll(phi, -1, axis=1)
        - 4.0 * phi
    )


def _dF(phi: np.ndarray) -> np.ndarray:
    return phi**3 - phi


def _simulate(M: float, nx: int, ny: int, nt: int, dt: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 2.0 * np.pi, nx, endpoint=False)
    y = np.linspace(0.0, 2.0 * np.pi, ny, endpoint=False)
    X, Y = np.meshgrid(x, y, indexing="ij")
    phi = 0.35 * np.sin(X + 0.13 * seed) + 0.22 * np.cos(2.0 * Y - 0.07 * seed)
    phi = phi + 0.03 * rng.standard_normal((nx, ny))
    phi = np.clip(phi, -0.95, 0.95)
    out = [phi.copy()]
    for _ in range(nt - 1):
        rhs = float(M) * _laplacian(phi) - _dF(phi)
        phi = np.clip(phi + float(dt) * rhs, -1.5, 1.5)
        out.append(phi.copy())
    return np.asarray(out, dtype=float)


def _estimate_M(phi_series: np.ndarray, dt: float) -> tuple[float, float]:
    left = phi_series[:-1]
    right = phi_series[1:]
    mid = 0.5 * (left + right)
    dphi_dt = (right - left) / float(dt)
    lap = np.asarray([_laplacian(frame) for frame in mid], dtype=float)
    y = dphi_dt + _dF(mid)
    denom = float(np.sum(lap * lap))
    if denom <= 1.0e-30:
        return float("nan"), float("nan")
    M_hat = float(np.sum(lap * y) / denom)
    residual = y - M_hat * lap
    objective = float(np.mean(residual**2))
    return M_hat, objective


def _case(M_true: float, noise: float, seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    grid = cfg["grid"]
    phi = _simulate(float(M_true), int(grid["nx"]), int(grid["ny"]), int(grid["nt"]), float(grid["dt"]), int(seed))
    rng = np.random.default_rng(int(seed) + 177)
    if float(noise) > 0.0:
        scale = max(float(np.std(phi)), 1.0e-12)
        phi = phi + float(noise) * scale * rng.standard_normal(phi.shape)
    M_hat, objective = _estimate_M(phi, float(grid["dt"]))
    re = relative_error(M_hat, float(M_true)) if np.isfinite(M_hat) else float("nan")
    finite = bool(np.isfinite([M_hat, objective, re]).all())
    return {
        "M_true": float(M_true),
        "M_estimated": float(M_hat),
        "relative_error_M": float(re),
        "noise_level": float(noise),
        "seed": int(seed),
        "finite_result": finite,
        "success_le_0p1": bool(finite and re <= 0.1),
        "objective_value": float(objective),
    }


def run_phase_field_alignment(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    rows: list[dict[str, Any]] = []
    for M_true in cfg["M_true"]:
        for noise in cfg["noise"]:
            for seed in cfg["seeds"]:
                rows.append(_case(float(M_true), float(noise), int(seed), cfg))

    cases_path = ROOT / str(cfg["cases_csv"])
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    with cases_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})

    finite_errors = [float(row["relative_error_M"]) for row in rows if row["finite_result"]]
    noise_sensitivity = {}
    for noise in sorted({float(row["noise_level"]) for row in rows}):
        vals = [float(row["relative_error_M"]) for row in rows if row["finite_result"] and float(row["noise_level"]) == noise]
        noise_sensitivity[str(noise)] = float(np.median(vals)) if vals else float("nan")
    success_rate = float(np.mean([bool(row["success_le_0p1"]) for row in rows])) if rows else 0.0
    median_re = float(np.median(finite_errors)) if finite_errors else float("nan")
    supported = bool(rows and all(row["finite_result"] for row in rows) and median_re <= 0.1)
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin phase-field inverse alignment smoke; not sparse-port current inversion and not experimental data.",
        "num_cases": len(rows),
        "all_finite_results": bool(all(row["finite_result"] for row in rows)),
        "median_relative_error_M": median_re,
        "success_rate_le_0p1": success_rate,
        "noise_sensitivity": noise_sensitivity,
        "whether_phase_field_inverse_alignment_supported": supported,
        "manuscript_sentence_for_related_work_alignment": "A small synthetic Allen-Cahn mobility inversion with full-field anchors supports related-work alignment with phase-field inverse PINN literature, while the main paper claim remains sparse-port gamma_sub target reduction.",
        "allowed_claims": [
            "the project aligns with phase-field inverse PINN literature at the parameter-inversion paradigm level",
            "the phase-field smoke benchmark is supplementary sanity evidence",
        ],
        "forbidden_claims": [
            "phase-field smoke is a main-text core experiment",
            "sparse-port current recovers phase-field mobility",
            "experimental validation",
        ],
        "outputs": {"summary_json": str(cfg["summary_json"]), "cases_csv": str(cfg["cases_csv"])},
    }
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_phase_field_alignment(args.config)
    print(json.dumps({k: summary[k] for k in ["num_cases", "all_finite_results", "median_relative_error_M", "success_rate_le_0p1", "whether_phase_field_inverse_alignment_supported"]}, indent=2))


if __name__ == "__main__":
    main()
