"""Verify response-surface gamma_sub evidence against anchor cases.

This audit is synthetic numerical digital-twin evidence. It uses prior
simulator-backed source grids and phase-map cases as anchors; it does not claim
that every dense response-surface point is a fresh ODE solve.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_high_throughput_common import (
    load_yaml,
    read_csv,
    response_surface_relative_error,
    write_csv,
    write_json,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_response_surface_anchor_verification.yaml")
CASE_FIELDS = [
    "anchor_region",
    "anchor_source",
    "gamma_sub",
    "T_sw_offset_K",
    "protocol",
    "T_sw_prior_width",
    "observation_count",
    "noise",
    "response_surface_predicted_error",
    "simulator_backed_error",
    "absolute_discrepancy",
    "relative_discrepancy",
    "predicted_recoverable_le_0p1",
    "simulator_recoverable_le_0p1",
    "classification_agreement",
    "finite_result",
]


def _as_bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _objective_error(value: float, max_objective: float) -> float:
    return float(np.clip(math.log1p(max(float(value), 0.0)) / max(math.log1p(max_objective), 1.0e-30), 0.0, 1.0))


def _idw_predict(rows: list[dict[str, Any]], gamma: float, offset: float, power: float) -> float:
    xs = np.asarray([math.log(float(row["gamma_sub"])) for row in rows], dtype=float)
    ys = np.asarray([float(row["T_sw_offset_K"]) for row in rows], dtype=float)
    zs = np.asarray([float(row["objective"]) for row in rows], dtype=float)
    d = np.sqrt((xs - math.log(float(gamma))) ** 2 + (ys - float(offset)) ** 2)
    idx = int(np.argmin(d))
    if float(d[idx]) < 1.0e-12:
        return float(zs[idx])
    w = 1.0 / np.maximum(d, 1.0e-12) ** float(power)
    return float(np.sum(w * zs) / np.sum(w))


def _take(rows: list[dict[str, Any]], n: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    if n <= 0 or not rows:
        return []
    if len(rows) <= n:
        return list(rows)
    idx = rng.choice(len(rows), size=n, replace=False)
    return [rows[int(i)] for i in idx]


def _profile_anchor(
    row: dict[str, str],
    *,
    all_rows: list[dict[str, str]],
    region: str,
    threshold: float,
    max_objective: float,
    power: float,
) -> dict[str, Any]:
    gamma = float(row["gamma_sub"])
    offset = float(row["T_sw_offset_K"])
    holdout = [other for other in all_rows if other is not row]
    pred_obj = _idw_predict(holdout, gamma, offset, power)
    sim_obj = float(row["objective"])
    pred = _objective_error(pred_obj, max_objective)
    sim = _objective_error(sim_obj, max_objective)
    abs_disc = abs(pred - sim)
    rel_disc = abs_disc / max(abs(sim), 1.0e-12)
    pred_ok = bool(pred <= threshold)
    sim_ok = bool(sim <= threshold)
    return {
        "anchor_region": region,
        "anchor_source": "leave_one_out_profile_likelihood_source_grid",
        "gamma_sub": gamma,
        "T_sw_offset_K": offset,
        "protocol": "triangle",
        "T_sw_prior_width": 1.0,
        "observation_count": 16,
        "noise": 0.0,
        "response_surface_predicted_error": pred,
        "simulator_backed_error": sim,
        "absolute_discrepancy": abs_disc,
        "relative_discrepancy": rel_disc,
        "predicted_recoverable_le_0p1": pred_ok,
        "simulator_recoverable_le_0p1": sim_ok,
        "classification_agreement": bool(pred_ok == sim_ok),
        "finite_result": bool(np.isfinite([pred, sim, abs_disc, rel_disc]).all() and _as_bool(row["finite_result"])),
    }


def _phase_anchor(row: dict[str, str], *, region: str, threshold: float) -> dict[str, Any]:
    protocol = str(row.get("protocol", "ltp_ltd"))
    delta = float(row.get("T_sw_delta_K", 0.0))
    width = float(row.get("T_sw_prior_width", 1.0))
    n_obs = int(float(row.get("observation_count", 16)))
    noise = float(row.get("noise", 0.0))
    pred = response_surface_relative_error(protocol, delta, width, n_obs, noise)
    sim = float(row["relative_error"])
    abs_disc = abs(pred - sim)
    rel_disc = abs_disc / max(abs(sim), 1.0e-12)
    pred_ok = bool(pred <= threshold)
    sim_ok = bool(sim <= threshold)
    return {
        "anchor_region": region,
        "anchor_source": "phase_diagram_or_confounding_phase_map_case",
        "gamma_sub": float(row.get("gamma_true", 4.5e8)),
        "T_sw_offset_K": delta,
        "protocol": protocol,
        "T_sw_prior_width": width,
        "observation_count": n_obs,
        "noise": noise,
        "response_surface_predicted_error": pred,
        "simulator_backed_error": sim,
        "absolute_discrepancy": abs_disc,
        "relative_discrepancy": rel_disc,
        "predicted_recoverable_le_0p1": pred_ok,
        "simulator_recoverable_le_0p1": sim_ok,
        "classification_agreement": bool(pred_ok == sim_ok),
        "finite_result": bool(np.isfinite([pred, sim, abs_disc, rel_disc]).all() and _as_bool(row["finite_result"])),
    }


def _select_profile_rows(rows: list[dict[str, str]], sampling: dict[str, int], rng: np.random.Generator) -> list[dict[str, Any]]:
    objectives = np.asarray([float(row["objective"]) for row in rows], dtype=float)
    max_objective = float(np.max(objectives))
    sorted_rows = sorted(rows, key=lambda row: float(row["objective"]))
    offsets = np.asarray([abs(float(row["T_sw_offset_K"])) for row in rows], dtype=float)
    near_ridge = [row for row in sorted_rows if float(row["objective"]) <= np.percentile(objectives, 35) and abs(float(row["T_sw_offset_K"])) >= float(np.median(offsets))]
    random_rows = _take(rows, int(sampling.get("random_control_zone", 0)) // 2, rng)
    selected: list[tuple[str, dict[str, str]]] = []
    selected.extend(("objective_minimum", row) for row in sorted_rows[: int(sampling.get("objective_minimum", 0))])
    selected.extend(("ridge_valley", row) for row in _take(near_ridge, int(sampling.get("ridge_valley", 0)), rng))
    selected.extend(("random_control_zone", row) for row in random_rows)
    out = []
    for region, row in selected:
        out.append(
            _profile_anchor(
                row,
                all_rows=rows,
                region=region,
                threshold=0.1,
                max_objective=max_objective,
                power=2.0,
            )
        )
    return out


def _select_phase_rows(rows: list[dict[str, str]], sampling: dict[str, int], rng: np.random.Generator, threshold: float) -> list[dict[str, Any]]:
    finite_rows = [row for row in rows if _as_bool(row["finite_result"])]
    boundary = [row for row in finite_rows if abs(float(row["relative_error"]) - threshold) <= 0.035]
    failure = [row for row in finite_rows if float(row["relative_error"]) >= 0.5]
    recoverable = [row for row in finite_rows if float(row["relative_error"]) <= 0.05]
    random_rows = _take(finite_rows, int(math.ceil(int(sampling.get("random_control_zone", 0)) / 2)), rng)
    selected: list[tuple[str, dict[str, str]]] = []
    selected.extend(("recoverability_boundary", row) for row in _take(boundary, int(sampling.get("recoverability_boundary", 0)), rng))
    selected.extend(("wide_T_sw_mismatch_failure_zone", row) for row in _take(failure, int(sampling.get("wide_T_sw_mismatch_failure_zone", 0)), rng))
    selected.extend(("high_confidence_recoverable_zone", row) for row in _take(recoverable, int(sampling.get("high_confidence_recoverable_zone", 0)), rng))
    selected.extend(("random_control_zone", row) for row in random_rows)
    return [_phase_anchor(row, region=region, threshold=threshold) for region, row in selected]


def run_anchor_verification(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    rng = np.random.default_rng(int(cfg.get("random_seed", 2026)))
    threshold = float(cfg.get("recoverability_threshold", 0.1))
    sampling = dict(cfg.get("sampling", {}))
    profile_rows = read_csv(cfg["profile_source_csv"])
    phase_rows = read_csv(cfg["phase_map_cases_csv"])
    anchors = _select_profile_rows(profile_rows, sampling, rng)
    anchors.extend(_select_phase_rows(phase_rows, sampling, rng, threshold))
    target = int(cfg.get("num_anchor_cases", len(anchors)))
    if len(anchors) < target:
        max_objective = float(np.max([float(row["objective"]) for row in profile_rows]))
        extra_needed = target - len(anchors)
        for row in _take(profile_rows, extra_needed, rng):
            anchors.append(
                _profile_anchor(
                    row,
                    all_rows=profile_rows,
                    region="random_control_zone_extra",
                    threshold=threshold,
                    max_objective=max_objective,
                    power=float(cfg.get("interpolation_power", 2.0)),
                )
            )
    if len(anchors) > target:
        anchors = _take(anchors, target, rng)

    abs_values = [float(row["absolute_discrepancy"]) for row in anchors]
    finite_rows = [row for row in anchors if bool(row["finite_result"])]
    boundary_disagreements = [
        row
        for row in anchors
        if row["anchor_region"] == "recoverability_boundary" and not bool(row["classification_agreement"])
    ]
    agreement_rate = float(np.mean([bool(row["classification_agreement"]) for row in anchors])) if anchors else 0.0
    mean_abs = float(np.mean(abs_values)) if abs_values else float("nan")
    max_disc = float(np.max(abs_values)) if abs_values else float("nan")
    acceptable = bool(len(anchors) >= min(target, 30) and agreement_rate >= 0.80 and mean_abs <= 0.15)
    qualification = (
        "Response-surface phase diagrams are acceptable as manuscript evidence only with explicit qualification: "
        "dense points are interpolated from simulator-backed source grids, and boundary regions should be described as "
        "screening evidence rather than exhaustive ODE re-solves."
        if acceptable
        else "Response-surface evidence needs stronger simulator-backed validation before being used as a main manuscript claim."
    )
    summary = {
        "benchmark": cfg.get("benchmark", "gamma_sub_response_surface_anchor_verification"),
        "note": "Synthetic numerical digital-twin response-surface anchor verification; not experimental data.",
        "num_anchor_cases": len(anchors),
        "num_finite_anchor_cases": len(finite_rows),
        "mean_absolute_discrepancy": mean_abs,
        "median_absolute_discrepancy": float(np.median(abs_values)) if abs_values else float("nan"),
        "max_discrepancy": max_disc,
        "classification_agreement_rate": agreement_rate,
        "boundary_disagreement_cases": len(boundary_disagreements),
        "whether_response_surface_is_acceptable_for_manuscript": acceptable,
        "required_claim_qualification": qualification,
        "source_boundary": cfg.get("claim_boundary", ""),
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"]},
    }
    write_csv(cfg["cases_csv"], anchors, CASE_FIELDS)
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_anchor_verification(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "cases_csv": summary["outputs"]["cases_csv"],
                "num_anchor_cases": summary["num_anchor_cases"],
                "classification_agreement_rate": summary["classification_agreement_rate"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

