"""Actual segmented-electrode y-z finite-volume forward/observability audit."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pinnpcm.physics.multiterminal_yz import ElectrodeSegment, solve_multiterminal_yz, uniform_series_current
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/multiterminal_yz_forward_summary.json")


def _field(theta: np.ndarray, nz: int = 4, ny: int = 12) -> np.ndarray:
    center, width, contrast = theta
    y = np.linspace(0.0, 1.0, ny)
    profile = 1.0 + contrast * np.exp(-((y - center) ** 2) / max(width**2, 1.0e-6))
    base = np.repeat(np.asarray([5.0e5, 20.0, 1.0e4, 6.0e5])[:, None], ny, axis=1)
    base[1] = base[1] * profile
    return base


def _electrodes(ny: int, segmented: bool) -> list[ElectrodeSegment]:
    if not segmented:
        return [ElectrodeSegment("top", "top", 0, ny, 1.0), ElectrodeSegment("bottom", "bottom", 0, ny, 0.0)]
    third = ny // 3
    return [
        ElectrodeSegment("top_left", "top", 0, third, 1.0),
        ElectrodeSegment("top_center", "top", third, 2 * third, 0.65),
        ElectrodeSegment("top_right", "top", 2 * third, ny, 0.3),
        ElectrodeSegment("bottom", "bottom", 0, ny, 0.0),
        ElectrodeSegment("side", "right", 1, 3, 0.15),
    ]


def _observe(theta: np.ndarray, segmented: bool) -> tuple[np.ndarray, dict[str, Any]]:
    sigma = _field(theta)
    dz = np.asarray([18e-9, 30e-9, 15e-9, 18e-9])
    result = solve_multiterminal_yz(sigma, dz, 8.0e-7 / sigma.shape[1], _electrodes(sigma.shape[1], segmented), contact_resistance_ohm_m2=np.asarray([1.2e-10, 2.4e-10, 0.9e-10]), depth_m=8.0e-7)
    currents = result["terminal_currents_a"]
    return np.asarray([currents[key] for key in sorted(currents)]), result


def run_multiterminal_yz_forward_v10() -> dict[str, Any]:
    theta = np.asarray([0.52, 0.14, 12.0])
    uniform_sigma = np.repeat(np.asarray([5.0e5, 20.0, 1.0e4, 6.0e5])[:, None], 12, axis=1)
    dz = np.asarray([18e-9, 30e-9, 15e-9, 18e-9])
    area = 8.0e-7 * 8.0e-7
    uniform = solve_multiterminal_yz(uniform_sigma, dz, 8.0e-7 / 12, _electrodes(12, False), contact_resistance_ohm_m2=np.asarray([1.2e-10, 2.4e-10, 0.9e-10]), depth_m=8.0e-7)
    reference = uniform_series_current(uniform_sigma[:, 0], dz, 1.0, area, np.asarray([1.2e-10, 2.4e-10, 0.9e-10]))
    regression = abs(uniform["terminal_currents_a"]["top"] - reference) / max(abs(reference), 1.0e-30)
    observations = {}
    ranks = {}
    for segmented in [False, True]:
        name = "segmented" if segmented else "single_terminal"
        y0, result = _observe(theta, segmented)
        columns = []
        for index, step in enumerate([0.03, 0.02, 1.0]):
            plus = theta.copy(); minus = theta.copy(); plus[index] += step; minus[index] -= step
            yp, _ = _observe(plus, segmented); ym, _ = _observe(minus, segmented)
            columns.append((yp - ym) / (2.0 * step) / np.maximum(np.abs(y0), 1.0e-15))
        J = np.stack(columns, axis=1)
        singular = np.linalg.svd(J, compute_uv=False)
        rank = int(np.sum(singular > 1.0e-6))
        ranks[name] = rank
        observations[name] = {"terminal_currents_a": result["terminal_currents_a"], "current_balance_error": result["current_balance_error"], "rank": rank, "condition_number": float(singular[0] / max(singular[-1], 1.0e-15))}
    summary = {
        "benchmark": "multiterminal_yz_forward_v10", "synthetic_not_experimental": True,
        "solves_div_sigma_grad_phi": True, "segmented_top_and_side_electrodes": True, "bottom_ground": True,
        "insulating_unassigned_boundaries": True, "terminal_currents_from_boundary_flux": True,
        "uniform_limit_relative_error": float(regression), "uniform_limit_gate_passed": bool(regression <= 0.05),
        "observability": observations, "segmented_rank_gain": int(ranks["segmented"] - ranks["single_terminal"]),
        "status": "qualified_supported" if regression <= 0.05 else "failed_but_informative",
        "claim_boundary": "forward/observability implementation only; no positive hidden-field recovery claim",
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_multiterminal_yz_forward_v10(), indent=2))


if __name__ == "__main__":
    main()
