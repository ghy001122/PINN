"""Formal leave-one-factor-out generalization preflight for v10 forward data."""
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

from pinnpcm.physics.multilayer_sandwich import simulate_phase_activated_multilayer_case
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/oasis_generalization_v10_summary.json")


def _rows() -> list[dict[str, Any]]:
    rows = []
    for family in ["vo2", "nbo2"]:
        for structure in ["pcm_plus_electrodes", "full_stack_with_SnSe_barrier"]:
            for geometry in ["uniform_crossbar", "localized_filament", "edge_hotspot"]:
                for pulse in ["activation_triangle", "minor_loop"]:
                    for interface_scale in [0.75, 1.25]:
                        cfg = {"ny": 5, "nt": 16, "V_peak": 10.0 if family == "vo2" else 2.0, "V_pos": 9.0 if family == "vo2" else 1.9, "V_neg": -4.0 if family == "vo2" else -0.8, "R_load_ohm": 8e3 if family == "vo2" else 4e4, "vo2_profile": "normalized_activated", "Rth_PCM_SnSe_barrier_m2K_W": 3.4e-8 * interface_scale, "Rth_BE_substrate_m2K_W": 4e-8 * interface_scale, "nbo2_effective_fraction_ablation": False}
                        result = simulate_phase_activated_multilayer_case(structure, geometry, family, pulse, 2026, cfg)
                        rows.append({"family": family, "structure": structure, "geometry": geometry, "pulse": pulse, "interface_scale": interface_scale, "finite": result["finite_result"], "target": np.asarray([result["max_delta_T"], result["conductance_ratio"], np.max(np.abs(result["current"]))])})
    return rows


def _features(row: dict[str, Any]) -> np.ndarray:
    return np.asarray([
        1.0,
        1.0 if row["family"] == "vo2" else 0.0,
        1.0 if "SnSe" in row["structure"] else 0.0,
        {"uniform_crossbar": 0.0, "localized_filament": 0.5, "edge_hotspot": 1.0}[row["geometry"]],
        1.0 if row["pulse"] == "minor_loop" else 0.0,
        row["interface_scale"],
    ])


def _evaluate_split(rows: list[dict[str, Any]], key: str, held: Any) -> dict[str, Any]:
    train = [row for row in rows if row[key] != held]
    test = [row for row in rows if row[key] == held]
    X = np.stack([_features(row) for row in train]); Y = np.stack([np.log1p(row["target"]) for row in train])
    Xt = np.stack([_features(row) for row in test]); Yt = np.stack([np.log1p(row["target"]) for row in test])
    weights = np.linalg.solve(X.T @ X + 1.0e-3 * np.eye(X.shape[1]), X.T @ Y)
    pred_train = X @ weights; pred = Xt @ weights
    scale = np.maximum(np.std(Y, axis=0), 1.0e-6)
    error = np.sqrt(np.mean(((pred - Yt) / scale) ** 2, axis=1))
    residual_std = np.maximum(np.std(Y - pred_train, axis=0), 1.0e-6)
    coverage = np.mean((Yt >= pred - 1.645 * residual_std) & (Yt <= pred + 1.645 * residual_std))
    return {"held_out": str(held), "n_train": len(train), "n_test": len(test), "median_normalized_error": float(np.median(error)), "coverage_90": float(coverage)}


def run_oasis_generalization_v10() -> dict[str, Any]:
    rows = _rows()
    splits = {}
    for key in ["geometry", "structure", "interface_scale", "pulse", "family"]:
        splits[key] = [_evaluate_split(rows, key, value) for value in sorted({row[key] for row in rows}, key=str)]
    summary = {
        "benchmark": "oasis_generalization_v10", "synthetic_not_experimental": True,
        "formal_splits": {"geometry": "leave-one-geometry-out", "structure": "leave-one-stack-configuration-out", "interface_scale": "leave-one-interface-BC-range-out", "pulse": "leave-one-pulse-family-out", "family": "cross-material exploratory transfer"},
        "results": splits, "finite_rate": float(np.mean([row["finite"] for row in rows])),
        "within_family_and_cross_family_reported_separately": True,
        "status": "preflight_only",
        "claim_boundary": "reduced forward-response ridge preflight; not OASIS neural-operator generalization evidence",
        "P1_dependency": "full neural generalization remains blocked because P1 gate failed",
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_oasis_generalization_v10(), indent=2))


if __name__ == "__main__":
    main()
