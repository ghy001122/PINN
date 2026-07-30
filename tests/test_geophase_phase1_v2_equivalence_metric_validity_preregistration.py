from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_equivalence_metric_validity_audit.yaml"
)
PREREG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_metric_validity"
    / "preregistration.json"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config() -> dict:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_metric_validity_preregistration_preserves_strict_v1_and_hashes() -> None:
    config = _config()
    lock = config["authority_lock"]
    v1 = lock["strict_equivalence_v1"]

    assert config["status"] == "preregistered_solver_free_not_executed"
    assert lock["merged_PR10_commit"] == (
        "f40cce457269787f579430ec30d59c46fea08765"
    )
    assert v1["disposition"] == "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    assert (v1["completed_rows"], v1["expected_rows"]) == (12, 57)
    assert v1["failing_plan_index"] == 11
    assert v1["formal_execution_count"] == 0
    assert v1["formal_artifact_count"] == 0
    assert lock["frozen_candidate"]["commit"] == (
        "1ae2704f6d84a3733d9de58aa23d992aa0c471a5"
    )
    assert lock["frozen_candidate"]["tree"] == (
        "d3833a4a5dd067dab72c84f15fe2f8e726bd9512"
    )
    for item in lock["frozen_files"].values():
        assert _sha256(ROOT / item["path"]) == item["sha256"]


def test_metric_categories_keep_physical_lateral_flux_voting() -> None:
    categories = _config()["field_categories"]

    assert categories["primary_strict"]["threshold"] == pytest.approx(1.0e-12)
    physical = categories["physical_lateral_flux"]
    assert physical["voting"] is True
    assert set(physical["suffixes"]) == {
        "lateral.x_face_flux_W",
        "lateral.y_face_flux_W",
        "lateral.net_cell_outflow_W",
    }
    assert physical["threshold_ratio"] == pytest.approx(1.0)
    assert physical["empirical_multiplier"] == "forbidden"
    assert "delta_T_inf" in physical["x_face_bound"]
    assert "delta_T_inf" in physical["y_face_bound"]
    assert "L_infinity_norm" in physical["net_cell_bound"]
    hard = categories["lateral_hard_gate_diagnostics"]
    assert hard["voting"] is True
    assert hard["comparator"] == "exact_hard_gate_disposition"
    assert hard["required"] == (
        "candidate_and_oracle_each_pass_and_dispositions_match"
    )
    cancellation = categories["cancellation_roundoff_diagnostics"]
    assert cancellation["voting"] is True
    assert cancellation["raw_values_preserved"] is True


def test_metric_validity_boundary_is_solver_free_and_fail_closed() -> None:
    config = _config()
    boundary = config["execution_boundary"]
    controls = config["negative_controls"]

    for key in (
        "numerical_solver_execution",
        "frozen_candidate_or_oracle_import",
        "strict_equivalence_57_row_rerun",
        "runtime_readiness",
        "formal_campaign",
        "performance_code_change",
        "comparator_v1_change",
        "physical_equations_parameters_or_tolerances_change",
        "scientific_gate_change",
        "automatic_retry",
    ):
        assert boundary[key] == "forbidden"
    assert boundary["static_audit_attempts"] == 1
    assert boundary["maximum_solver_execution_count"] == 0
    assert boundary["formal_execution_count"] == 0
    assert boundary["formal_artifact_count"] == 0
    assert all(value is True for value in controls.values())
    assert set(config["allowed_final_dispositions"]) == {
        "GO_VERSIONED_EQUIVALENCE_V2_AUDIT",
        "STOP_S2_ACTIVATE_GAMMA_SUB",
    }


def test_metric_validity_preregistration_machine_record_has_no_execution() -> None:
    payload = json.loads(PREREG_PATH.read_text(encoding="utf-8"))

    assert payload["task_id"] == "Q2_PHASE1_V2_EQUIVALENCE_METRIC_VALIDITY_AUDIT"
    assert payload["schema_version"] == (
        "geophase_phase1_v2_equivalence_metric_validity_preregistration_v1"
    )
    assert payload["config_sha256"] == _sha256(CONFIG_PATH)
    assert payload["strict_equivalence_v1_disposition"] == (
        "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    )
    assert payload["strict_equivalence_v1_completed_rows"] == 12
    assert payload["strict_equivalence_v1_expected_rows"] == 57
    assert payload["metric_validity_audit_executed"] is False
    assert payload["numerical_solver_execution_count"] == 0
    assert payload["formal_execution_count"] == 0
    assert payload["formal_artifact_count"] == 0
    assert set(payload["allowed_final_dispositions"]) == {
        "GO_VERSIONED_EQUIVALENCE_V2_AUDIT",
        "STOP_S2_ACTIVATE_GAMMA_SUB",
    }
