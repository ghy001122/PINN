from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_metric_validity_coverage_correction as correction,
)
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as strict_v1


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "src"
    / "pinnpcm"
    / "audit"
    / "geophase_phase1_v2_equivalence_metric_validity_coverage_correction.py"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def result() -> dict:
    return correction.build_result()


def test_parent_results_are_immutable_and_no_numerical_execution_occurs(
    result: dict,
) -> None:
    summary = result["summary"]

    assert summary["strict_equivalence_v1_disposition"] == (
        "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    )
    assert (
        summary["strict_equivalence_v1_completed_rows"],
        summary["strict_equivalence_v1_expected_rows"],
    ) == (12, 57)
    assert summary["parent_metric_validity_disposition"] == (
        "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
    )
    assert summary["parent_metric_evidence_regenerated"] is False
    for name in (
        "frozen_v1_row_execution_count",
        "held_out_45_row_execution_count",
        "equivalence_v2_execution_count",
        "candidate_or_oracle_execution_count",
        "controller_execution_count",
        "formal_execution_count",
        "formal_artifact_count",
    ):
        assert summary[name] == 0
    assert summary["runtime_readiness_executed"] is False

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "_replace_exact" not in source
    assert "exact_votes=" not in source
    for forbidden_call in (
        "run_equivalence_audit(",
        "_execute_electrical_row(",
        "_execute_interval_row(",
        "_execute_progression_row(",
        "_execute_failure_row(",
        "run_c1(",
        "run_c2(",
        "run_c3(",
    ):
        assert forbidden_call not in source


def test_field_universe_is_mechanical_not_a_fixed_count_mirror(result: dict) -> None:
    fields = result["fields"]
    summary = result["summary"]
    schema = result["schema"]
    scenarios = correction.build_production_scenarios(schema)

    mechanically_observed = {
        (scenario.family, kind, correction._normalise_field(name))
        for scenario in scenarios
        for kind, mapping in (
            ("numeric", scenario.observation.numeric),
            ("exact", scenario.observation.exact_votes),
            ("telemetry", scenario.observation.telemetry),
        )
        for name in mapping
    }
    published_contract = {
        (row["family"], row["value_kind"], row["field_pattern"])
        for row in fields
    }

    assert published_contract == mechanically_observed
    assert len(fields) == summary["mechanical_field_template_count"]
    assert len(fields) != summary["original_coverage_claimed_template_count"]
    assert summary["original_209_completeness_claim_superseded"] is True
    assert all(row["field_name_origin"] == "production_extractor_output" for row in fields)
    assert all(row["required_when"] for row in fields)
    assert all(row["static_cardinality_rule"] for row in fields)
    assert any("trajectory_dependent" in row["static_cardinality_rule"] for row in fields)
    assert any(row["minimum_cardinality"] == 0 for row in fields)
    assert all(
        row["raw_schema_origin"] == "streaming_source_AST+production_extractor_output"
        for row in fields
        if row["family"] == "progression"
        and row["field_pattern"].startswith("streaming.")
    )


def test_all_57_plan_rows_use_the_mechanical_family_contract_and_frozen_dag(
    result: dict,
) -> None:
    plan = result["plan"]
    summary = result["summary"]
    family_field_counts = {
        family: sum(row["family"] == family for row in result["fields"])
        for family in strict_v1.FAMILY_ORDER
    }

    assert len(plan) == 57
    assert summary["plan_rows_mechanically_mapped"] == 57
    assert summary["plan_family_counts"] == {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }
    assert len({row["plan_index"] for row in plan}) == 57
    assert all(row["execution_status"] == "static_only_not_executed" for row in plan)
    assert all(
        row["mechanical_field_template_count"] == family_field_counts[row["family"]]
        for row in plan
    )
    dag = summary["execution_DAG_facts"]
    assert dag["contract_pass"] is True
    assert (
        dag["evaluation_item_count"],
        dag["unique_execution_unit_count"],
        dag["reused_evaluation_count"],
        dag["formal_execution_count"],
    ) == (63, 60, 3, 0)


def test_A_B_C_classification_keeps_primary_and_physical_flux_votes(result: dict) -> None:
    fields = result["fields"]
    exact = {row["field_pattern"] for row in fields if row["value_kind"] == "exact"}
    assert exact == set(strict_v1.EXPECTED_EXACT_VOTES)
    assert result["summary"]["B_exact_contract_pass"] is True
    assert all(
        row["comparator"] == "canonical_exact_equality"
        for row in fields
        if row["value_kind"] == "exact"
    )

    physical_flux = [
        row for row in fields if row["category"] == "C_physical_lateral_flux"
    ]
    assert physical_flux
    assert {
        row["field_pattern"].rsplit(".lateral.", 1)[-1]
        for row in physical_flux
    } == {"x_face_flux_W", "y_face_flux_W", "net_cell_outflow_W"}
    assert all(
        row["comparator"] == "parent_analytic_mixed_bound_unchanged"
        for row in physical_flux
    )
    hard_gate = [row for row in fields if row["category"] == "C_lateral_hard_gate"]
    assert hard_gate
    assert any("streaming.scalar" in row["field_pattern"] for row in hard_gate)
    assert all(
        row["comparator"] == "original_hard_gate_disposition_exact"
        for row in hard_gate
    )
    cancellation = [
        row for row in fields if row["category"] == "C_cancellation_roundoff"
    ]
    assert cancellation
    assert all(
        row["comparator"] == "parent_backward_error_bound_unchanged"
        for row in cancellation
    )
    assert any(row["category"] == "A_primary_physical" for row in fields)


def test_raw_B_controls_use_production_extractors_and_fail_closed(result: dict) -> None:
    controls = {row["control_id"]: row for row in result["controls"]}
    required = {
        "accepted_rejected_sequence_change",
        "event_count_change",
        "event_direction_change",
        "event_chronology_change",
        "reversal_count_change",
        "reversal_direction_change",
        "reversal_order_change",
        "nonlinear_method_change",
        "converged_disposition_change",
        "fallback_disposition_change",
        "expected_failure_type_change",
        "expected_failure_location_change",
        "failure_changed_to_success",
        "success_changed_to_failure",
        "required_topology_field_missing",
        "unregistered_topology_field_extra",
        "required_numeric_field_missing",
        "unregistered_numeric_field_extra",
        "validation_error_injected",
    }

    assert required.issubset(controls)
    assert controls["baseline_raw_attempt"]["observed_accept"] is True
    assert controls["baseline_raw_attempt"]["passed"] is True
    assert all(controls[name]["expected_accept"] is False for name in required)
    assert all(controls[name]["observed_accept"] is False for name in required)
    assert all(controls[name]["passed"] is True for name in required)
    assert all(
        row["production_extractor"].startswith("_attempt_observation")
        or row["production_extractor"].startswith("_progression_observation")
        for row in result["controls"]
    )
    assert all(row["direct_exact_vote_mutation"] is False for row in result["controls"])
    assert result["summary"]["raw_controls_direct_exact_vote_mutation_count"] == 0
    assert result["summary"]["raw_controls_pass"] is True


def test_atomic_publication_is_limited_to_four_new_correction_files(
    result: dict, tmp_path: Path
) -> None:
    output = result["config"]["outputs"]
    original = dict(output)
    output.update(
        {
            "mechanical_field_contract": str(tmp_path / "mechanical_field_contract.csv"),
            "mechanical_plan_contract": str(tmp_path / "mechanical_plan_contract.csv"),
            "raw_topology_controls": str(tmp_path / "raw_topology_controls.csv"),
            "summary": str(tmp_path / "coverage_correction_summary.json"),
        }
    )
    try:
        published = correction.publish_result(result)
    finally:
        output.clear()
        output.update(original)

    assert len(published) == 4
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "coverage_correction_summary.json",
        "mechanical_field_contract.csv",
        "mechanical_plan_contract.csv",
        "raw_topology_controls.csv",
    ]
    with (tmp_path / "mechanical_field_contract.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == len(result["fields"])
    with (tmp_path / "mechanical_plan_contract.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 57
    summary = json.loads(
        (tmp_path / "coverage_correction_summary.json").read_text(encoding="utf-8")
    )
    assert summary["coverage_correction_disposition"] == "COVERAGE_CORRECTION_PASS"
    assert summary["formal_execution_count"] == 0
    assert summary["equivalence_v2_execution_count"] == 0
