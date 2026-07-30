from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import yaml

from src.pinnpcm.solvers.geophase_phase1_v2_performance_equivalence import (
    EXPECTED_EXACT_VOTES,
    build_equivalence_plan,
    canonical_sha256,
    load_equivalence_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_equivalence_v2_audit.yaml"
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "research_strategy"
    / "phase1_v2_equivalence_v2_audit_contract.md"
)
PREREG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_v2_audit"
    / "preregistration.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config() -> dict:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_equivalence_v2_authority_and_frozen_hashes_are_exact() -> None:
    config = _config()
    authority = config["authority_lock"]

    assert config["status"] == "preregistered_not_authorized_not_executed"
    assert authority["PR11_merge_commit"] == (
        "2da569e0bdb902ff665dcfce2ee019a6d36986d5"
    )
    strict_v1 = authority["strict_equivalence_v1"]
    assert strict_v1["disposition"] == "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    assert (strict_v1["completed_rows"], strict_v1["expected_rows"]) == (12, 57)
    assert authority["metric_validity"]["disposition"] == (
        "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
    )
    assert authority["coverage_correction"]["disposition"] == (
        "COVERAGE_CORRECTION_PASS"
    )
    for item in authority["frozen_files"].values():
        assert _sha256(ROOT / item["path"]) == item["sha256"]
    assert _sha256(ROOT / authority["frozen_candidate"]["identity"]["path"]) == (
        authority["frozen_candidate"]["identity"]["sha256"]
    )


def test_equivalence_v2_locks_original_order_and_data_partitions() -> None:
    config = _config()
    lock = config["ordered_plan_lock"]
    plan = build_equivalence_plan(load_equivalence_contract())

    assert len(plan) == 57
    assert canonical_sha256([asdict(row) for row in plan]) == (
        lock["canonical_ordered_plan_sha256"]
    )
    assert {family: sum(row.family == family for row in plan) for family in lock["expected_counts"]} == lock["expected_counts"]
    assert asdict(plan[0])["sample_id"] == lock["first_row"]["sample_id"]
    assert asdict(plan[11])["sample_id"] == (
        lock["last_metric_development_row"]["sample_id"]
    )
    assert asdict(plan[12])["sample_id"] == lock["first_held_out_row"]["sample_id"]
    assert asdict(plan[56])["sample_id"] == lock["final_row"]["sample_id"]
    assert lock["development_partition"] == {
        "label": "metric-development",
        "plan_indices": [0, 11],
        "count": 12,
        "provenance": "observed_under_strict_equivalence_v1_not_a_v2_result",
    }
    assert lock["held_out_partition"]["plan_indices"] == [12, 56]
    assert lock["held_out_partition"]["count"] == 45


def test_equivalence_v2_A_B_C_rules_remain_fail_closed() -> None:
    rules = _config()["field_rules"]

    primary = rules["A_primary_physical"]
    assert primary["threshold"] == 1.0e-12
    assert primary["threshold_change"] == "forbidden"
    assert primary["missing_extra_or_nonfinite"] == "VALID_FAIL"

    topology = rules["B_topology_and_state_machine"]
    assert topology["comparator"] == "exact_match"
    assert tuple(topology["fields"]) == EXPECTED_EXACT_VOTES
    assert topology["missing_extra_or_validation_error"] == "VALID_FAIL"

    lateral = rules["C_lateral_conservation_and_flux"]
    assert lateral["physical_fluxes"]["voting"] is True
    assert lateral["physical_fluxes"]["threshold_ratio"] == 1.0
    assert lateral["physical_fluxes"]["empirical_multiplier"] == "forbidden"
    assert "delta_T_inf" in lateral["physical_fluxes"]["x_face_bound"]
    assert "L_infinity_norm" in lateral["physical_fluxes"]["net_cell_bound"]
    assert lateral["hard_gate"]["required"] == (
        "candidate_and_oracle_each_pass_and_dispositions_match"
    )
    assert lateral["cancellation_roundoff"]["voting"] is True
    assert lateral["observed_difference_derived_threshold"] == "forbidden"
    complete = rules["complete_field_contract"]
    assert set(complete.values()) >= {
        "VALID_FAIL",
        "mechanically_derived_638_family_qualified_parameterized_templates",
    }


def test_equivalence_v2_execution_is_dormant_one_shot_and_atomic() -> None:
    config = _config()
    control = config["execution_control"]
    counts = config["execution_counts"]

    assert control["authorization_required"] == "fresh_explicit_user_authorization"
    assert control["execution_attempt_limit"] == 1
    assert control["equivalence_v2_execution_count"] == 0
    assert control["execution_now"] == "forbidden"
    assert control["fail_fast_on_first_valid_comparison_failure"] is True
    assert control["automatic_retry"] == "forbidden"
    assert control["manual_retry_under_same_contract"] == "forbidden"
    assert control["atomic_journal"]["format"] == "append_only_JSONL_hash_chain"
    assert control["atomic_journal"]["partial_row_counts_as_completed"] is False
    assert set(config["terminal_states"]) == {"PASS", "VALID_FAIL", "INVALID_INFRA"}
    assert counts == {
        "equivalence_v2_execution_count": 0,
        "equivalence_v2_completed_rows": 0,
        "equivalence_v2_result_artifact_count": 0,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def test_equivalence_v2_machine_preregistration_is_content_addressed_and_zero() -> None:
    record = json.loads(PREREG_PATH.read_text(encoding="utf-8"))

    assert record["config_sha256"] == _sha256(CONFIG_PATH)
    assert record["contract_document_sha256"] == _sha256(CONTRACT_PATH)
    assert record["ordered_plan_sha256"] == (
        _config()["ordered_plan_lock"]["canonical_ordered_plan_sha256"]
    )
    assert record["numerical_audit_execution_performed"] is False
    assert record["held_out_execution_performed"] is False
    assert record["equivalence_v2_execution_count"] == 0
    assert record["equivalence_v2_completed_rows"] == 0
    assert record["equivalence_v2_result_artifact_count"] == 0
    assert record["formal_execution_count"] == 0
    assert record["formal_artifact_count"] == 0


def test_equivalence_v2_current_route_and_fast_CI_are_contract_only() -> None:
    checkpoint = "PHASE1_V2_EQUIVALENCE_V2_CONTRACT_EXECUTABLE_READY"
    for path in (
        ROOT / "CODEX_CONTEXT.md",
        ROOT / "PROJECT_STATE.md",
        ROOT / "NEXT_ACTIONS.md",
        ROOT / "docs" / "research_strategy" / "active_phase.md",
    ):
        assert checkpoint in path.read_text(encoding="utf-8")

    workflow = (ROOT / ".github" / "workflows" / "read_only_validation.yml").read_text(
        encoding="utf-8"
    )
    assert "tests/test_geophase_phase1_v2_equivalence_v2_preregistration.py" in workflow
    assert "tests/test_geophase_phase1_v2_equivalence_v2_executability.py" in workflow
    assert "run_geophase_phase1_v2_equivalence" not in workflow
