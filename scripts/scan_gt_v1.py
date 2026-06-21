"""Small Ground Truth v1.1 calibration scan."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.gt_solver import simulate_ground_truth
from pinnpcm.utils.io import ensure_dir


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Scan compact Ground Truth v1.1 calibration candidates.")
    parser.add_argument("--protocol", choices=["triangle", "ltp_ltd"], default="triangle")
    parser.add_argument("--nx", type=int, default=21)
    parser.add_argument("--nt", type=int, default=160)
    parser.add_argument("--t-max", type=float, default=None)
    parser.add_argument("--outdir", type=Path, default=Path("outputs/tables/gt_v1_scan"))
    parser.add_argument("--rtol", type=float, default=2.0e-5)
    parser.add_argument("--atol", type=float, default=1.0e-7)
    return parser


def scan_candidates() -> list[tuple[str, dict[str, Any]]]:
    """Return a compact set of literature-guided synthetic calibration candidates."""

    return [
        ("default_v11", {}),
        ("conservative_drive", {"triangle_v_peak": 0.18}),
        ("higher_drive", {"triangle_v_peak": 0.22}),
        (
            "mobile_interface",
            {
                "nb_oxide_mu_v0": 1.5e-15,
                "v2o5_mu_v0": 6.0e-16,
                "nb_oxide_D_v0": 3.0e-15,
                "v2o5_D_v0": 1.0e-15,
            },
        ),
        (
            "warm_switch",
            {
                "T_sw": 312.0,
                "dT_sw": 4.5,
                "tau_m": 3.5e-4,
            },
        ),
        (
            "balanced_story",
            {
                "triangle_v_peak": 0.21,
                "gamma_sub": 4.0e8,
                "T_sw": 313.0,
                "dT_sw": 4.6,
                "tau_m": 3.5e-4,
                "gaussian_delta_c": 0.030,
            },
        ),
    ]


def compute_metrics(gt: dict[str, Any]) -> dict[str, float]:
    """Compute compact calibration metrics for a Ground Truth run."""

    voltage = np.asarray(gt["V"], dtype=float)
    current = np.asarray(gt["I"], dtype=float)
    conductance = np.asarray(gt["G"], dtype=float)
    temperature = np.asarray(gt["T"], dtype=float)
    defect = np.asarray(gt["c_v"], dtype=float)
    m_state = np.asarray(gt["m"], dtype=float)
    params = json.loads(str(gt["params_json"]))

    voltage_threshold = 0.05 * max(float(np.max(np.abs(voltage))), 1.0e-30)
    conductance_mask = np.abs(voltage) > voltage_threshold
    conductance_abs = np.abs(conductance[conductance_mask])
    if conductance_abs.size == 0:
        conductance_ratio = 1.0
    else:
        g_low = max(float(np.percentile(conductance_abs, 5.0)), 1.0e-30)
        g_high = float(np.percentile(conductance_abs, 95.0))
        conductance_ratio = g_high / g_low

    return {
        "iv_loop_area": float(abs(np.trapz(current, voltage))),
        "max_delta_T": float(np.max(temperature - float(params["T0"]))),
        "max_delta_m": float(np.max(np.abs(m_state - m_state[0:1, :]))),
        "max_abs_delta_c_v": float(np.max(np.abs(defect - defect[0:1, :]))),
        "conductance_modulation_ratio": conductance_ratio,
    }


def score_metrics(metrics: dict[str, float]) -> float:
    """Rank candidates by visible but not extreme synthetic dynamics."""

    delta_t_score = min(metrics["max_delta_T"] / 8.0, 2.0)
    delta_m_score = min(metrics["max_delta_m"] / 0.08, 2.0)
    delta_c_score = min(metrics["max_abs_delta_c_v"] / 2.0e-4, 2.0)
    g_score = min(np.log10(max(metrics["conductance_modulation_ratio"], 1.0)), 2.0)
    area_score = min(metrics["iv_loop_area"] / 1.0e-11, 2.0)
    return float(delta_t_score + delta_m_score + delta_c_score + g_score + area_score)


def main() -> None:
    """Run the calibration scan and write a CSV table."""

    args = build_parser().parse_args()
    outdir = ensure_dir(args.outdir)
    rows: list[dict[str, Any]] = []

    for name, overrides in scan_candidates():
        gt = simulate_ground_truth(
            protocol=args.protocol,
            params=overrides,
            nx=args.nx,
            nt=args.nt,
            t_max=args.t_max,
            rtol=args.rtol,
            atol=args.atol,
        )
        metrics = compute_metrics(gt)
        row = {"name": name, "score": score_metrics(metrics), **metrics}
        rows.append(row)
        print(
            f"{name:18s} score={row['score']:.3f} "
            f"area={metrics['iv_loop_area']:.3e} "
            f"max_dT={metrics['max_delta_T']:.3f} K "
            f"max_dm={metrics['max_delta_m']:.3e} "
            f"max_abs_dc={metrics['max_abs_delta_c_v']:.3e} "
            f"G_ratio={metrics['conductance_modulation_ratio']:.3f}"
        )

    rows.sort(key=lambda item: float(item["score"]), reverse=True)
    csv_path = outdir / "scan_gt_v1_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    best = rows[0]
    print(f"Best candidate: {best['name']} (score={best['score']:.3f})")
    print(f"Saved scan metrics: {csv_path}")


if __name__ == "__main__":
    main()
