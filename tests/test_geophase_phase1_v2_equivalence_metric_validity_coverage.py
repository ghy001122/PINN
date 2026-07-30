from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pinnpcm.audit.geophase_phase1_v2_equivalence_metric_validity_coverage import (
    build_coverage_result,
    publish_coverage_result,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "src"
    / "pinnpcm"
    / "audit"
    / "geophase_phase1_v2_equivalence_metric_validity_coverage.py"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def result() -> dict:
    return build_coverage_result()


def test_addendum_is_solver_free_and_preserves_all_parent_evidence(result: dict) -> None:
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
    assert summary["parent_metric_validity_result_regenerated"] is False
    assert summary["existing_observed_physical_bounds_recomputed"] is False
    assert summary["existing_observed_cancellation_bounds_recomputed"] is False
    assert summary["existing_observed_negative_controls_regenerated"] is False
    assert summary["candidate_or_oracle_execution_count"] == 0
    assert summary["strict_equivalence_row_execution_count"] == 0
    assert summary["remaining_45_row_execution_count"] == 0
    assert summary["runtime_readiness_executed"] is False
    assert summary["formal_execution_count"] == 0
    assert summary["formal_artifact_count"] == 0

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "source_corrected_performance import",
        "controller_v2 import",
        "runtime_readiness import",
        "dormant_runner import",
        "run_equivalence",
        "run_c1",
        "run_c2",
        "run_c3",
    ):
        assert forbidden not in source


def test_all_57_rows_map_to_static_output_contracts(result: dict) -> None:
    summary = result["summary"]
    rows = result["plan_contract"]

    assert len(rows) == 57
    assert summary["plan_family_counts"] == {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }
    assert summary["all_plan_rows_map_to_static_contract"] is True
    assert all(row["execution_status"] == "static_contract_only_not_executed" for row in rows)
    assert all(row["plan_sha256"] for row in rows)
    assert len({row["plan_index"] for row in rows}) == 57
    assert any(row["family"] == "progression" for row in rows)
    assert {
        (row["candidate_paths"], row["failure_class"])
        for row in rows
        if row["family"] == "failure"
    }


def test_complete_field_templates_are_classified_without_hiding_flux(result: dict) -> None:
    summary = result["summary"]
    fields = result["field_contract"]

    assert len(fields) == summary["field_template_count"] == 209
    assert summary["all_field_templates_classified"] is True
    assert summary["component_contract_count"] == 10
    exact = [row for row in fields if row["category"] == "B_exact_topology"]
    assert len(exact) == summary["B_exact_field_count"] == 7
    assert {row["field_pattern"] for row in exact} == {
        "nonlinear_method",
        "converged_disposition",
        "fallback_disposition",
        "accepted_rejected_sequence",
        "failure_classification",
        "event_count_direction_and_order",
        "reversal_count_direction_and_order",
    }
    assert all(row["comparator"] == "canonical_exact_equality" for row in exact)

    physical = [row for row in fields if row["category"] == "C_physical_lateral_flux"]
    assert {row["field_pattern"].split(".lateral.", 1)[1] for row in physical} == {
        "x_face_flux_W",
        "y_face_flux_W",
        "net_cell_outflow_W",
    }
    assert all(row["vote_rule"] == "ratio<=1; voting" for row in physical)
    cancellation = [
        row for row in fields if row["category"] == "C_cancellation_roundoff"
    ]
    assert cancellation
    assert all("signed raw value retained" in row["vote_rule"] for row in cancellation)
    structural = [row for row in fields if row["category"] == "structural_fail_closed"]
    assert {row["field_pattern"] for row in structural} >= {
        "numeric_field_sets_exact",
        "exact_vote_field_sets_exact",
        "telemetry_field_sets_exact",
        "validation_errors_empty",
    }


def test_every_requested_topology_and_tamper_control_is_fail_closed(result: dict) -> None:
    config = result["config"]
    controls = result["controls"]
    by_id = {row["control_id"]: row for row in controls}
    required = set(config["required_new_synthetic_controls"])

    assert required.issubset(by_id)
    assert len(required) == 27
    assert len(controls) == 28
    assert by_id["baseline_valid_pair"]["observed_accept"] is True
    assert by_id["baseline_valid_pair"]["passed"] is True
    assert all(by_id[name]["expected_accept"] is False for name in required)
    assert all(by_id[name]["observed_accept"] is False for name in required)
    assert all(by_id[name]["passed"] is True for name in required)
    assert summary_pass(result)


def summary_pass(result: dict) -> bool:
    summary = result["summary"]
    return bool(
        summary["coverage_addendum_disposition"] == "COVERAGE_ADDENDUM_PASS"
        and summary["final_metric_route"] == "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
        and summary["synthetic_controls_complete"] is True
        and summary["synthetic_controls_pass"] is True
        and summary["equivalence_v2_57_row_authorized"] is False
    )


def test_atomic_publication_writes_only_four_addendum_files(
    result: dict, tmp_path: Path
) -> None:
    output = result["config"]["outputs"]
    original = dict(output)
    output.update(
        {
            "static_field_contract": str(tmp_path / "static_field_contract.csv"),
            "plan_output_contract": str(tmp_path / "plan_output_contract.csv"),
            "synthetic_controls": str(tmp_path / "synthetic_controls.csv"),
            "summary": str(tmp_path / "coverage_addendum_summary.json"),
        }
    )
    try:
        published = publish_coverage_result(result)
    finally:
        output.clear()
        output.update(original)

    assert len(published) == 4
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "coverage_addendum_summary.json",
        "plan_output_contract.csv",
        "static_field_contract.csv",
        "synthetic_controls.csv",
    ]
    with (tmp_path / "static_field_contract.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 209
    with (tmp_path / "plan_output_contract.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 57
    summary = json.loads(
        (tmp_path / "coverage_addendum_summary.json").read_text(encoding="utf-8")
    )
    assert summary["formal_execution_count"] == 0
    assert summary["formal_artifact_count"] == 0
    assert summary["remaining_45_row_execution_count"] == 0
