from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from scripts.audit_prompt32_semantics import build_ceba_audit, build_figure5_audit

ROOT = Path(__file__).resolve().parents[1]


def test_ceba_audit_separates_point_success_from_oracle_abstention() -> None:
    audit = build_ceba_audit()
    assert audit["historical_ceba_modified"] is False
    assert audit["profile_cutoff"]["matches_requested_formula"] is True
    assert audit["truth_leakage"]["score_trace_accepts_true_gamma"] is True
    assert audit["truth_leakage"]["retained_class_uses_true_gamma"] is True
    assert audit["truth_leakage"]["abstention_is_oracle_diagnostic_not_deployable_inference"] is True
    assert audit["threshold"]["hardcoded_local_assignment_detected"] is True
    assert set(audit["n32_noise0p02_conditions"]) == {
        "triangle|delta=0.0|n=32|noise=0.02",
        "triangle|delta=0.2|n=32|noise=0.02",
        "triangle|delta=2.0|n=32|noise=0.02",
        "ltp_ltd|delta=0.0|n=32|noise=0.02",
        "ltp_ltd|delta=0.2|n=32|noise=0.02",
        "ltp_ltd|delta=2.0|n=32|noise=0.02",
    }
    assert audit["new_ode_evaluations"] == 0


def test_figure5_audit_has_complete_semantic_fields_and_downgrade() -> None:
    audit = build_figure5_audit()
    assert audit["solver"] == {"nx": 7, "nt": 48, "method": "Radau", "rtol": 1.0e-4, "atol": 1.0e-6}
    assert len(audit["gamma_candidate_grid"]) == 7
    assert len(audit["candidate_contracts"]) == 6
    required = {
        "candidate_name",
        "simulator_protocol",
        "t_max_s",
        "ltp_v_pos_V",
        "ltp_v_neg_V",
        "time_grid_sha256",
        "voltage_waveform_sha256",
        "prior_width_factor",
        "calibration_error_factor",
    }
    assert all(required <= set(record) for record in audit["candidate_contracts"])
    assert audit["objective"]["weights"] == {"w_g": 1.0, "w_i": 0.5, "w_heat": 0.01}
    assert audit["objective"]["heat_residual_implemented"] is True
    findings = audit["semantic_findings"]
    assert findings["unique_simulator_protocol_count"] == 1
    assert findings["prior_width_factor_consumed_by_implementation"] is False
    assert findings["calibration_error_factor_consumed_by_implementation"] is True
    assert findings["calibration_and_protocol_effects_are_confounded"] is True
    assert findings["720_case_count_verified"] is True
    assert audit["claim_resolution"]["protocol_gain_claim_eligible"] is False
    assert audit["claim_resolution"]["bundled_configuration_performance_status"] == "qualified_supported"
    assert audit["new_ode_evaluations"] == 0


def test_scis_schema_requires_zero_new_solver_and_pinn_runs() -> None:
    schema = json.loads((ROOT / "docs/schemas/gamma_sub_scis_summary_v1.schema.json").read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert {"gates", "new_ode_evaluations", "pinn_training_runs", "external_13v_accessed"} <= required
    assert schema["properties"]["new_ode_evaluations"]["const"] == 0
    assert schema["properties"]["pinn_training_runs"]["const"] == 0
    assert schema["properties"]["external_13v_accessed"]["const"] is False


def test_scis_zero_noise_rows_are_deterministic_sanity_only() -> None:
    with (ROOT / "outputs/tables/gamma_sub_scis_cases.csv").open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if float(row["noise"]) == 0.0]
    groups: defaultdict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    for row in rows:
        group = (
            row["scope"],
            row["protocol"],
            row["observation_count"],
            row["delta_T_sw_K"],
            row["true_gamma_sub"],
        )
        decision = (
            row["gamma_hat"],
            row["set_members"],
            row["certificate_acceptance"],
            row["point_success"],
            row["set_contains_true"],
        )
        groups[group].add(decision)
    assert len(rows) == 3400
    assert len(groups) == 68
    assert all(len(decisions) == 1 for decisions in groups.values())
