"""Supersede CPCF scientific semantics while preserving every historic artifact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pinnpcm.physics.voltage_protocols import ltp_ltd_voltage, triangle_voltage
from scripts.audit_gamma_sub_calibration_protocol_cost_frontier import _nondominated, _summarize_operating_points
from scripts.audit_gamma_sub_multi_protocol_recoverability import _loss_from_series
from scripts.gamma_sub_high_throughput_common import response_surface_relative_error

DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "prompt31_cpcf_semantic_audit.json"
DEFAULT_CLAIM_RECORD = ROOT / "outputs" / "tables" / "gamma_sub_cpcf_superseding_claim_record.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping: {path}")
    return payload


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _array_sha256(values: np.ndarray) -> str:
    canonical = np.asarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _waveform_registry(cpcf: dict[str, Any]) -> dict[str, Any]:
    common_t = np.linspace(0.0, 15.0e-3, 1501, dtype=float)
    arrays = {
        "triangle": triangle_voltage(common_t, 3.0e-3, v_peak=0.20),
        "ltp_ltd": ltp_ltd_voltage(common_t, 15.0e-3, v_pos=0.08, v_neg=-0.02),
        "multi_amplitude_synthetic": triangle_voltage(common_t, 3.0e-3, v_peak=0.26),
        "short_pulse_to_ltp_ltd": ltp_ltd_voltage(common_t, 12.0e-3, v_pos=0.08, v_neg=-0.02),
        "multi_pulse_to_ltp_ltd": ltp_ltd_voltage(common_t, 15.0e-3, v_pos=0.10, v_neg=-0.03),
    }
    records: dict[str, Any] = {}
    for name, values in arrays.items():
        records[name] = {
            "semantic_kind": "single_voltage_waveform",
            "common_time_grid_points": int(common_t.size),
            "common_time_grid_start_s": float(common_t[0]),
            "common_time_grid_stop_s": float(common_t[-1]),
            "common_time_grid_sha256": _array_sha256(common_t),
            "voltage_array_sha256": _array_sha256(values),
            "voltage_min_V": float(np.min(values)),
            "voltage_max_V": float(np.max(values)),
        }
    mixed_components = [records["triangle"]["voltage_array_sha256"], records["ltp_ltd"]["voltage_array_sha256"]]
    records["mixed_protocol"] = {
        "semantic_kind": "mean_objective_over_two_separate_waveforms",
        "component_protocols": ["triangle", "ltp_ltd"],
        "component_voltage_array_sha256": mixed_components,
        "composite_bundle_sha256": _canonical_json_sha256(mixed_components),
        "voltage_array_sha256": None,
        "reason": "The historical mixed objective has no single interchangeable V(t) array.",
    }
    comparisons: list[dict[str, Any]] = []
    for cpcf_name, spec in cpcf["protocols"].items():
        response_name = str(spec["response_surface_protocol"])
        simulator_name = cpcf_name
        response = records[response_name]
        simulator = records[simulator_name]
        equivalent = bool(
            response["semantic_kind"] == "single_voltage_waveform"
            and response["voltage_array_sha256"] == simulator["voltage_array_sha256"]
        )
        comparisons.append(
            {
                "cpcf_protocol": cpcf_name,
                "response_surface_protocol": response_name,
                "simulator_protocol": str(spec["simulator_protocol"]),
                "response_surface_waveform_sha256": response.get("voltage_array_sha256"),
                "response_surface_bundle_sha256": response.get("composite_bundle_sha256"),
                "fresh_anchor_waveform_sha256": simulator.get("voltage_array_sha256"),
                "same_sampled_V_t": equivalent,
                "contract_status": "equivalent" if equivalent else "protocol_contract_mismatch",
            }
        )
    return {"common_grid": records["triangle"] | {"voltage_array_sha256": None}, "waveforms": records, "comparisons": comparisons}


def build_semantic_audit(
    output: Path = DEFAULT_OUTPUT,
    claim_record_output: Path = DEFAULT_CLAIM_RECORD,
) -> dict[str, Any]:
    cpcf_path = ROOT / "configs" / "gamma_sub_calibration_protocol_cost_frontier.yaml"
    historical_path = ROOT / "configs" / "gamma_sub_multi_protocol_recoverability.yaml"
    cpcf = _load_yaml(cpcf_path)
    historical = _load_yaml(historical_path)
    case_rows = _csv_rows(ROOT / "outputs" / "tables" / "gamma_sub_cpcf_pilot_cases.csv")
    operating_rows = _csv_rows(ROOT / "outputs" / "tables" / "gamma_sub_cpcf_pilot_operating_points.csv")
    cpcf_source = (ROOT / "scripts" / "audit_gamma_sub_calibration_protocol_cost_frontier.py").read_text(encoding="utf-8")

    waveform = _waveform_registry(cpcf)
    protocol_mismatches = [row for row in waveform["comparisons"] if row["contract_status"] == "protocol_contract_mismatch"]

    fresh_cases = [row for row in case_rows if _truth(row["fresh_solver_anchor"])]
    proxy_only_cases = [row for row in case_rows if not _truth(row["fresh_solver_anchor"])]
    solver_diagnostic_cases = [row for row in case_rows if int(float(row["solver_forward_evaluations"])) > 0]
    proxy_prediction_cases = [row for row in case_rows if row.get("predicted_relative_error", "") != ""]
    aggregation_source = inspect.getsource(_summarize_operating_points)
    voting_uses_solver = "solver_relative_error" in aggregation_source

    stable_unqualified = sorted(
        row["operating_point_id"]
        for row in operating_rows
        if _truth(row["stable_nondominated"]) and not _truth(row["locked_risk_qualified"])
    )
    qualified_count = sum(_truth(row["locked_risk_qualified"]) for row in operating_rows)
    stable_count = sum(_truth(row["stable_nondominated"]) for row in operating_rows)

    replicate_noise_seed = [
        {"replicate_id": item["id"], "noise": float(item["noise"]), "seed": int(item["seed"])}
        for item in cpcf["replicates"]
    ]
    seeds_per_noise: dict[str, set[int]] = {}
    for item in replicate_noise_seed:
        seeds_per_noise.setdefault(str(item["noise"]), set()).add(item["seed"])
    same_distribution_seed_replication = all(len(values) >= 2 for values in seeds_per_noise.values())

    historical_solver = historical["simulation"]
    cpcf_solver = cpcf["solver_anchor"]["simulation"]
    historical_grid = [float(value) for value in historical["inverse"]["gamma_candidates"]]
    cpcf_grid = [float(value) for value in cpcf["solver_anchor"]["gamma_candidates"]]
    historical_loss_source = inspect.getsource(_loss_from_series)
    historical_implementation_uses_heat = "w_heat" in historical_loss_source
    cpcf_anchor_uses_heat = "objective_components" in cpcf_source and float(cpcf["solver_anchor"]["loss"].get("w_heat", 0.0)) != 0.0

    proxy_signature = str(inspect.signature(response_surface_relative_error))
    proxy_uses_seed = "seed" in proxy_signature
    effective_width_expression_present = 'float(config["solver_anchor"]["T_sw_reference_delta_K"]) * width' in cpcf_source
    historical_effective_width_expression_present = 'float(scenario["T_sw_delta_K"]) * float(scenario["T_sw_prior_width"])' in (
        ROOT / "scripts" / "audit_gamma_sub_multi_protocol_recoverability.py"
    ).read_text(encoding="utf-8")

    failed_contracts = {
        "protocol_equivalence": bool(protocol_mismatches),
        "solver_grid_equivalence": historical_solver != cpcf_solver,
        "candidate_grid_equivalence": historical_grid != cpcf_grid,
        "objective_equivalence": historical_implementation_uses_heat != cpcf_anchor_uses_heat,
        "T_sw_prior_width_unit_semantics": bool(effective_width_expression_present and historical_effective_width_expression_present),
        "iid_seed_replication": not same_distribution_seed_replication,
        "bootstrap_semantics": True,
        "direct_solver_scientific_voting": not voting_uses_solver,
        "pareto_qualification_filter": bool(stable_unqualified),
    }
    implementation_invalid = any(failed_contracts.values())

    audit = {
        "schema_version": "prompt31_cpcf_semantic_audit_v1",
        "stage_id": "M31_CPCF_SEMANTIC_SUPERSEDE_AND_CEBA_PARITY",
        "audited_commits": [
            "3cd714cb91bd2c700881584391f3b9ab66027b3c",
            "4f55e482fca4e332d009b209772e4c56f5fb96ee",
            "16427d7d20b32c8d25fc7967b43657f0588ba8b2",
        ],
        "historical_artifacts_modified": False,
        "scientific_vote": False,
        "status": "implementation_contract_invalid" if implementation_invalid else "contract_valid",
        "claim_status": "failed_but_informative" if implementation_invalid else "qualified_supported",
        "valid_scope": "software/proxy mismatch diagnosis only" if implementation_invalid else "configured CPCF audit",
        "forbidden_inference": "no conclusion about existence or absence of a calibration-protocol resource frontier",
        "supersedes_scientific_interpretation_of_prompt30_cpcf": implementation_invalid,
        "failed_contracts": failed_contracts,
        "protocol_contract": waveform,
        "solver_contract": {
            "historical": historical_solver,
            "cpcf_fresh_anchor": cpcf_solver,
            "equivalent": historical_solver == cpcf_solver,
        },
        "candidate_grid_contract": {
            "historical_count": len(historical_grid),
            "historical_gamma_sub": historical_grid,
            "cpcf_fresh_anchor_count": len(cpcf_grid),
            "cpcf_fresh_anchor_gamma_sub": cpcf_grid,
            "equivalent": historical_grid == cpcf_grid,
        },
        "objective_contract": {
            "historical_declared_weights": historical["loss"],
            "historical_implementation_weights": {"w_g": historical["loss"]["w_g"], "w_i": historical["loss"]["w_i"], "w_heat": 0.0},
            "historical_implementation_uses_heat": historical_implementation_uses_heat,
            "cpcf_fresh_anchor_weights": cpcf["solver_anchor"]["loss"],
            "cpcf_fresh_anchor_uses_heat": cpcf_anchor_uses_heat,
            "equivalent": historical_implementation_uses_heat == cpcf_anchor_uses_heat,
        },
        "T_sw_prior_width_contract": {
            "historical_semantics": "dimensionless multiplier applied to T_sw_delta_K",
            "cpcf_semantics": "dimensionless multiplier applied to T_sw_reference_delta_K",
            "cpcf_output_label": "T_sw_prior_width_K",
            "cpcf_resource_range_label": "calibration_width_range_K",
            "unit_contract_mismatch": True,
        },
        "noise_seed_contract": {
            "replicates": replicate_noise_seed,
            "independent_seeds_per_same_noise": {key: len(value) for key, value in seeds_per_noise.items()},
            "same_distribution_seed_replication": same_distribution_seed_replication,
            "proxy_function_signature": proxy_signature,
            "proxy_prediction_uses_seed": proxy_uses_seed,
            "noise_and_seed_confounded": True,
        },
        "bootstrap_contract": {
            "sample_count_per_operating_point": len(cpcf["replicates"]),
            "sample_semantics": "four different noise levels with one seed each",
            "implementation": "case bootstrap over predicted_relative_error",
            "iid_seed_bootstrap": False,
            "valid_scope": "heuristic scenario resampling only",
        },
        "case_accounting": {
            "total_case_rows": len(case_rows),
            "proxy_prediction_rows": len(proxy_prediction_cases),
            "proxy_only_rows": len(proxy_only_cases),
            "proxy_plus_fresh_solver_diagnostic_rows": len(fresh_cases),
            "fresh_solver_diagnostic_rows": len(solver_diagnostic_cases),
            "fresh_solver_trajectory_evaluations": sum(int(float(row["solver_forward_evaluations"])) for row in solver_diagnostic_cases),
            "fully_direct_solver_voting_rows": 0 if not voting_uses_solver else len(solver_diagnostic_cases),
            "operating_point_vote_source": "predicted_relative_error",
        },
        "pareto_contract": {
            "operating_point_count": len(operating_rows),
            "locked_risk_qualified_count": qualified_count,
            "locked_risk_unqualified_count": len(operating_rows) - qualified_count,
            "stable_nondominated_count": stable_count,
            "stable_but_locked_risk_unqualified_ids": stable_unqualified,
            "nondominated_filter_uses_locked_risk_qualified": False,
            "scientific_figure_disposition": "NON-VOTING PROXY-CONTRACT DIAGNOSTIC",
        },
        "allowed_wording": "The CPCF artifact diagnoses proxy/implementation contract mismatches and is retained as historical failed_but_informative software evidence.",
        "forbidden_wording": [
            "CPCF establishes that no calibration-protocol resource frontier exists.",
            "CPCF establishes a Pareto-optimal scientific resource frontier.",
            "CPCF fresh anchors validate the 48 proxy cases as equivalent direct-solver cases.",
        ],
        "no_new_solver_run": True,
        "full_pinn_run": False,
        "external_13v_accessed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    claim_record = {
        "schema_version": "gamma_sub_cpcf_superseding_claim_record_v1",
        "superseded_artifact": "outputs/tables/gamma_sub_cpcf_pilot_summary.json",
        "superseding_audit": _display_path(output),
        "scientific_vote": False,
        "status": audit["status"],
        "claim_status": audit["claim_status"],
        "valid_scope": audit["valid_scope"],
        "forbidden_inference": audit["forbidden_inference"],
        "historical_files_retained_unchanged": True,
    }
    claim_record_output.parent.mkdir(parents=True, exist_ok=True)
    claim_record_output.write_text(json.dumps(claim_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--claim-record", type=Path, default=DEFAULT_CLAIM_RECORD)
    args = parser.parse_args()
    result = build_semantic_audit(args.output, args.claim_record)
    print(json.dumps({key: result[key] for key in ("status", "claim_status", "scientific_vote", "failed_contracts")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
