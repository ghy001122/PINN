"""Build cache-only CEBA and static Figure-5 semantic audits for Prompt 32."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pinnpcm.physics.voltage_protocols import ltp_ltd_voltage
from scripts.gamma_sub_validation_common import objective_components
from scripts.run_gamma_sub_ceba import _score_trace
from scripts.run_gamma_sub_scis import (
    CEBA_IMMUTABLE_PATHS,
    CacheOnlyTrajectoryStore,
    _atomic_json,
    _load_yaml,
    _objective_vector,
    _relative_error,
    _resolve,
    _sha256_file,
)

DEFAULT_SCIS_CONFIG = ROOT / "configs" / "gamma_sub_scis_v1.yaml"
FIGURE5_CONFIG = ROOT / "configs" / "gamma_sub_calibrated_sequential_protocol_validation.yaml"
FIGURE5_SCRIPT = ROOT / "scripts" / "audit_gamma_sub_calibrated_sequential_protocol_validation.py"
FIGURE5_SUMMARY = ROOT / "outputs" / "tables" / "gamma_sub_calibrated_sequential_protocol_validation_summary.json"
CEBA_AUDIT_OUTPUT = ROOT / "outputs" / "tables" / "prompt32_ceba_semantic_audit.json"
FIGURE5_AUDIT_OUTPUT = ROOT / "outputs" / "tables" / "prompt32_figure5_semantic_audit.json"


def _array_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes(order="C")).hexdigest()


def _retained_set(objectives: list[float], candidates: list[float], fraction: float) -> list[float]:
    values = np.asarray(objectives, dtype=float)
    cutoff = float(np.min(values) + float(fraction) * (np.max(values) - np.min(values)))
    return [candidate for candidate, value in zip(candidates, values, strict=True) if value <= cutoff + 1.0e-18]


def build_ceba_audit(scis_config_path: Path = DEFAULT_SCIS_CONFIG) -> dict[str, Any]:
    scis = _load_yaml(scis_config_path)
    store = CacheOnlyTrajectoryStore(scis)
    ceba = store.ceba_config
    candidates = sorted(float(value) for value in ceba["inverse"]["gamma_candidates"])
    true_gamma = float(ceba["inverse"]["true_gamma_sub"])
    threshold = float(ceba["inverse"]["success_relative_error_threshold"])
    retention = float(ceba["pilot"]["profile_retention_span_fraction"])
    seeds = [int(value) for value in ceba["pilot"]["discovery_seeds"]]
    weights = dict(ceba["inverse"]["objective"])
    conditions: dict[str, Any] = {}
    endpoint_comparisons: list[dict[str, Any]] = []
    for protocol in ["triangle", "ltp_ltd"]:
        candidate_traces = {gamma: store.load("candidate", protocol, gamma) for gamma in candidates}
        for delta in [0.0, 0.2, 2.0]:
            target = store.load("target", protocol, delta)
            rows: list[dict[str, Any]] = []
            for seed in seeds:
                objectives = _objective_vector(
                    target=target,
                    candidates=candidate_traces,
                    observation_count=32,
                    noise=0.02,
                    seed=seed,
                    weights=weights,
                )
                best_index = int(np.argmin(objectives))
                gamma_hat = candidates[best_index]
                full_set = _retained_set(objectives, candidates, retention)
                oracle_classes = {_relative_error(value, true_gamma) <= threshold + 1.0e-15 for value in full_set}
                abstained = len(oracle_classes) > 1
                point_success = _relative_error(gamma_hat, true_gamma) <= threshold + 1.0e-15
                rows.append(
                    {
                        "seed": seed,
                        "gamma_hat": gamma_hat,
                        "point_success": point_success,
                        "abstention": abstained,
                        "historical_combined_success": bool(point_success and not abstained),
                        "retained_set": full_set,
                    }
                )
                for endpoint_label, reduced_candidates in (
                    ("remove_low_1p5e8", candidates[1:]),
                    ("remove_high_1e9", candidates[:-1]),
                ):
                    indexes = [candidates.index(value) for value in reduced_candidates]
                    reduced_objectives = [objectives[index] for index in indexes]
                    reduced_set = _retained_set(reduced_objectives, reduced_candidates, retention)
                    common_full = [value for value in full_set if value in reduced_candidates]
                    endpoint_comparisons.append(
                        {
                            "protocol": protocol,
                            "delta_T_sw_K": delta,
                            "seed": seed,
                            "endpoint_change": endpoint_label,
                            "full_retained_set": full_set,
                            "reduced_retained_set": reduced_set,
                            "common_grid_membership_changed": set(common_full) != set(reduced_set),
                        }
                    )
            conditions[f"{protocol}|delta={delta:.1f}|n=32|noise=0.02"] = {
                "case_count": len(rows),
                "point_success_rate": float(np.mean([row["point_success"] for row in rows])),
                "abstention_rate": float(np.mean([row["abstention"] for row in rows])),
                "historical_combined_success_rate": float(np.mean([row["historical_combined_success"] for row in rows])),
                "gamma_hat_values": sorted({row["gamma_hat"] for row in rows}),
                "retained_sets": [row["retained_set"] for row in rows],
            }
    source = inspect.getsource(_score_trace)
    low = [row for row in endpoint_comparisons if row["endpoint_change"] == "remove_low_1p5e8"]
    high = [row for row in endpoint_comparisons if row["endpoint_change"] == "remove_high_1e9"]
    immutable_hashes = {path: _sha256_file(_resolve(path)) for path in CEBA_IMMUTABLE_PATHS}
    payload = {
        "schema_version": "prompt32_ceba_semantic_audit_v1",
        "stage_id": "M32_SCIS",
        "evidence_type": "synthetic cached direct-solver semantic diagnostic",
        "historical_ceba_modified": False,
        "historical_ceba_hashes": immutable_hashes,
        "profile_cutoff": {
            "implemented_formula": "J_min + 0.05 * (J_max - J_min)",
            "retention_span_fraction": retention,
            "matches_requested_formula": retention == 0.05 and "cutoff = float(best[\"objective\"]) + float(retention_span_fraction) * span" in source,
        },
        "truth_leakage": {
            "score_trace_accepts_true_gamma": "true_gamma" in inspect.signature(_score_trace).parameters,
            "retained_class_uses_true_gamma": "retained_classes = {_relative_error(row[\"gamma_sub\"], true_gamma)" in source,
            "abstention_is_oracle_diagnostic_not_deployable_inference": True,
        },
        "threshold": {
            "config_value": threshold,
            "hardcoded_local_assignment_detected": "threshold = 0.15" in source,
        },
        "metric_separation": {
            "point_success": "relative point-estimate error only",
            "set_coverage": "not defined by historical CEBA",
            "certificate_acceptance": "not defined by historical CEBA",
            "conditional_accuracy_given_acceptance": "not defined by historical CEBA",
            "abstention_refusal": "historical oracle-class crossing diagnostic",
        },
        "n32_noise0p02_conditions": conditions,
        "candidate_endpoint_sensitivity": {
            "comparison_case_count": len(endpoint_comparisons),
            "remove_low_common_membership_change_rate": float(np.mean([row["common_grid_membership_changed"] for row in low])),
            "remove_high_common_membership_change_rate": float(np.mean([row["common_grid_membership_changed"] for row in high])),
            "any_retained_set_change": any(row["common_grid_membership_changed"] for row in endpoint_comparisons),
            "comparisons": endpoint_comparisons,
        },
        "scientific_resolution": {
            "ceba_parity_status": "supported",
            "ceba_boundary_status": "failed_but_informative",
            "ceba_abstention_is_runtime_certificate": False,
            "ceba_results_rewritten": False,
            "allowed": "Report point success and oracle abstention separately as a diagnostic of the locked CEBA implementation.",
            "forbidden": "Use the historical true-gamma-dependent abstention as a deployable uncertainty certificate or estimated calibration boundary.",
        },
        "new_ode_evaluations": 0,
        "pinn_training_runs": 0,
        "external_13v_accessed": False,
    }
    return payload


def build_figure5_audit() -> dict[str, Any]:
    config = _load_yaml(FIGURE5_CONFIG)
    script_text = FIGURE5_SCRIPT.read_text(encoding="utf-8")
    summary = json.loads(FIGURE5_SUMMARY.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    waveform_points = 2049
    for spec in config["protocol_candidates"]:
        t_max = float(spec["t_max"])
        time = np.linspace(0.0, t_max, waveform_points, dtype=float)
        voltage = ltp_ltd_voltage(
            time,
            t_max,
            v_pos=float(spec["ltp_v_pos"]),
            v_neg=float(spec["ltp_v_neg"]),
        )
        records.append(
            {
                "candidate_name": spec["candidate_name"],
                "simulator_protocol": spec["simulator_protocol"],
                "t_max_s": t_max,
                "ltp_v_pos_V": float(spec["ltp_v_pos"]),
                "ltp_v_neg_V": float(spec["ltp_v_neg"]),
                "waveform_grid_points": waveform_points,
                "time_grid_sha256": _array_sha256(time),
                "voltage_waveform_sha256": _array_sha256(voltage),
                "prior_width_factor": float(spec["prior_width_factor"]),
                "calibration_error_factor": float(spec["calibration_error_factor"]),
                "protocol_cost_proxy": float(spec["protocol_cost_proxy"]),
            }
        )
    objective_source = inspect.getsource(objective_components)
    unique_protocols = sorted({record["simulator_protocol"] for record in records})
    unique_waveforms = sorted({record["voltage_waveform_sha256"] for record in records})
    prior_width_occurrences = script_text.count("prior_width_factor")
    calibration_factor_occurrences = script_text.count("calibration_error_factor")
    payload = {
        "schema_version": "prompt32_figure5_semantic_audit_v1",
        "stage_id": "M32_SCIS",
        "source_hashes": {
            str(FIGURE5_CONFIG.relative_to(ROOT)).replace("\\", "/"): _sha256_file(FIGURE5_CONFIG),
            str(FIGURE5_SCRIPT.relative_to(ROOT)).replace("\\", "/"): _sha256_file(FIGURE5_SCRIPT),
            str(FIGURE5_SUMMARY.relative_to(ROOT)).replace("\\", "/"): _sha256_file(FIGURE5_SUMMARY),
        },
        "solver": {
            "nx": int(config["simulation"]["nx"]),
            "nt": int(config["simulation"]["nt"]),
            "method": config["simulation"]["method"],
            "rtol": float(config["simulation"]["rtol"]),
            "atol": float(config["simulation"]["atol"]),
        },
        "gamma_candidate_grid": [float(value) for value in config["inverse"]["gamma_candidates"]],
        "objective": {
            "weights": {key: float(value) for key, value in config["loss"].items()},
            "implemented_formula": "w_g*G_loss + w_i*I_loss + w_heat*heat_residual_loss",
            "heat_residual_implemented": "_heat_residual_loss" in objective_source and "w_heat" in objective_source,
            "heat_residual_semantics": "candidate-simulation internal finite-volume heat residual; not target-temperature supervision",
        },
        "candidate_contracts": records,
        "semantic_findings": {
            "candidate_count": len(records),
            "simulator_protocols": unique_protocols,
            "unique_simulator_protocol_count": len(unique_protocols),
            "unique_voltage_waveform_count": len(unique_waveforms),
            "candidate_name_is_not_simulator_protocol": True,
            "prior_width_factor_consumed_by_implementation": prior_width_occurrences > 0,
            "prior_width_factor_source_occurrences": prior_width_occurrences,
            "calibration_error_factor_consumed_by_implementation": calibration_factor_occurrences > 0,
            "calibration_error_factor_source_occurrences": calibration_factor_occurrences,
            "waveform_and_calibration_error_factor_vary_across_candidates": len(unique_waveforms) > 1 and len({record["calibration_error_factor"] for record in records}) > 1,
            "calibration_and_protocol_effects_are_confounded": True,
            "720_case_count_verified": int(summary["num_simulator_backed_cases"]) == 720,
            "all_cases_simulator_backed": bool(summary["all_cases_simulator_backed"]),
        },
        "claim_resolution": {
            "protocol_gain_claim_eligible": False,
            "bundled_configuration_performance_status": "qualified_supported",
            "figure5_title_required": "Bundled calibrated-configuration performance",
            "allowed": "Across 720 synthetic ODE-backed cases, the named bundled calibrated configuration has the reported conditional performance under its jointly varied waveform and calibration-error settings.",
            "forbidden": "Figure 5 isolates or causally establishes protocol gain, protocol optimality, or experimental protocol validation.",
        },
        "new_ode_evaluations": 0,
        "pinn_training_runs": 0,
        "external_13v_accessed": False,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["ceba", "figure5", "all"], default="all")
    args = parser.parse_args()
    outputs: dict[str, Any] = {}
    if args.mode in {"ceba", "all"}:
        outputs["ceba"] = build_ceba_audit()
        _atomic_json(CEBA_AUDIT_OUTPUT, outputs["ceba"])
    if args.mode in {"figure5", "all"}:
        outputs["figure5"] = build_figure5_audit()
        _atomic_json(FIGURE5_AUDIT_OUTPUT, outputs["figure5"])
    print(
        json.dumps(
            {
                key: {
                    "schema_version": value["schema_version"],
                    "new_ode_evaluations": value["new_ode_evaluations"],
                    "pinn_training_runs": value["pinn_training_runs"],
                }
                for key, value in outputs.items()
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
