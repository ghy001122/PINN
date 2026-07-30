from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pinnpcm.audit.geophase_phase1_v2_equivalence_metric_validity import (
    build_metric_validity_result,
    publish_metric_validity_result,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "src"
    / "pinnpcm"
    / "audit"
    / "geophase_phase1_v2_equivalence_metric_validity.py"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def result() -> dict:
    return build_metric_validity_result()


def test_audit_is_solver_free_and_preserves_v1(result: dict) -> None:
    summary = result["summary"]

    assert summary["strict_equivalence_v1_disposition"] == (
        "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    )
    assert (
        summary["strict_equivalence_v1_completed_rows"],
        summary["strict_equivalence_v1_expected_rows"],
    ) == (12, 57)
    assert summary["strict_equivalence_v1_preserved"] is True
    assert summary["numerical_solver_execution_count"] == 0
    assert summary["strict_equivalence_row_execution_count"] == 0
    assert summary["runtime_readiness_executed"] is False
    assert summary["formal_execution_count"] == 0
    assert summary["formal_artifact_count"] == 0
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "source_corrected_performance" not in source
    assert "performance_equivalence import" not in source


def test_failing_row_classification_is_exact_and_physical_flux_stays_voting(
    result: dict,
) -> None:
    summary = result["summary"]
    fields = result["field_classification"]

    assert summary["observed_field_counts"] == {
        "numeric_fields": 229,
        "nonlateral_fields": 202,
        "nonlateral_failures": 0,
        "lateral_fields": 27,
        "lateral_failures": 21,
        "lateral_passes": 6,
    }
    physical = [row for row in fields if row["category"] == "physical_lateral_flux"]
    assert len(physical) == 9
    assert all(row["voting"] is True for row in physical)
    assert {row["field"].split(".lateral.", 1)[1] for row in physical} == {
        "x_face_flux_W",
        "y_face_flux_W",
        "net_cell_outflow_W",
    }


def test_observed_physical_and_roundoff_bounds_pass_without_threshold_tuning(
    result: dict,
) -> None:
    summary = result["summary"]
    rows = result["observed_bound_audit"]

    physical = [row for row in rows if row["category"] == "physical_lateral_flux"]
    cancellation = [
        row
        for row in rows
        if row["category"] == "cancellation_roundoff_diagnostics"
    ]
    hard = [
        row
        for row in rows
        if row["category"] == "lateral_hard_gate_diagnostics"
    ]
    assert (len(physical), len(cancellation), len(hard)) == (9, 6, 3)
    assert all(row["passed"] for row in physical + cancellation + hard)
    assert summary["maximum_observed_physical_bound_ratio"] <= 1.0
    assert summary["maximum_observed_cancellation_bound_ratio"] <= 1.0
    assert summary["physical_lateral_fields_remain_voting"] is True


def test_synthetic_tamper_controls_are_fail_closed(result: dict) -> None:
    controls = result["negative_controls"]

    assert len(controls) == 13
    assert all(row["passed"] for row in controls)
    above = [row for row in controls if "ABOVE" in row["control_id"]]
    assert above
    assert all(row["expected_accept"] is False for row in above)
    assert all(row["observed_accept"] is False for row in above)
    assert any(
        row["control_id"] == "NC-PHYSICAL-RECLASSIFICATION-NONVOTING"
        and row["observed_accept"] is False
        for row in controls
    )


def test_metric_validity_disposition_authorizes_only_a_versioned_audit(
    result: dict,
) -> None:
    summary = result["summary"]

    assert summary["general_metric_category_error_demonstrated"] is True
    assert summary["disposition"] == "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
    assert summary["optimized_solver_equivalence_status"] == "forbidden_unassessed"
    assert summary["S2_scientific_claim_status"] == "forbidden_unassessed"
    assert summary["next_action_requires_fresh_user_authorization"] is True


def test_atomic_publication_writes_only_the_four_nonformal_tables(
    result: dict, tmp_path: Path
) -> None:
    config = result["config"]
    output = config["outputs"]
    original = dict(output)
    output.update(
        {
            "field_classification": str(tmp_path / "field_classification.csv"),
            "observed_bound_audit": str(tmp_path / "observed_bound_audit.csv"),
            "negative_controls": str(tmp_path / "negative_controls.csv"),
            "summary": str(tmp_path / "metric_validity_summary.json"),
        }
    )
    try:
        published = publish_metric_validity_result(result)
    finally:
        output.clear()
        output.update(original)

    assert len(published) == 4
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "field_classification.csv",
        "metric_validity_summary.json",
        "negative_controls.csv",
        "observed_bound_audit.csv",
    ]
    with (tmp_path / "field_classification.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 229
    summary = json.loads(
        (tmp_path / "metric_validity_summary.json").read_text(encoding="utf-8")
    )
    assert summary["formal_execution_count"] == 0
    assert summary["formal_artifact_count"] == 0
