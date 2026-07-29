from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_source_corrected_performance_repair.yaml"
)
PREREG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "performance_repair"
    / "preregistration.json"
)
HARNESS_ERRATUM_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_equivalence_audit_harness_erratum_v1.yaml"
)
CANDIDATE_IDENTITY_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "performance_repair"
    / "optimized_candidate_identity.json"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config() -> dict:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _harness_erratum() -> dict:
    payload = yaml.safe_load(HARNESS_ERRATUM_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_performance_preregistration_locks_the_pushed_v3_authority() -> None:
    config = _config()
    authority = config["authority_lock"]

    assert authority["source_corrected_bundle"] == {
        "commit": "0ebe037ef707a56750c5db0c52f7a312ee251b6c",
        "tree": "4fc400a0dff50d598319be0bde540120c966f602",
    }
    assert authority["active_routing"] == {
        "commit": "b7d47c9dbb29611ab07abc85fae7bcdbf18d8a58",
        "tree": "0a462f979abf99be750035604aa269b8cc781b90",
    }
    v3 = authority["source_corrected_v3"]
    for name in (
        "source_contract",
        "S2_config",
        "formal_manifest",
        "execution_addendum",
        "controller_v2_overlay",
        "expanded_manifest_CSV",
        "expanded_manifest_JSON",
        "execution_DAG_CSV",
        "execution_DAG_JSON",
    ):
        item = v3[name]
        assert _sha256(ROOT / item["path"]) == item["sha256"]
    identity = v3["resolved_runtime_identity"]
    assert _sha256(ROOT / identity["path"]) == identity["file_sha256"]
    assert identity["identity_sha256"] == (
        "d6d75b0101152593599f53438718cba68c6c382e2650779de2c83ffbcee44977"
    )
    assert v3["counts"] == {
        "evaluations": 63,
        "unique_executions": 60,
        "legal_reuses": 3,
    }


def test_performance_preregistration_freezes_science_and_allows_one_repair() -> None:
    config = _config()
    boundary = config["execution_boundary"]
    frozen = config["frozen_scientific_semantics"]

    assert boundary["performance_repair_limit"] == 1
    assert boundary["authorized_repair_ordinal"] == 1
    assert boundary["second_performance_repair"] == "forbidden"
    assert boundary["formal_execution_count"] == 0
    assert boundary["formal_artifact_count"] == 0
    assert boundary["formal_campaign"] == "forbidden"
    assert boundary["new_dependency"] == "forbidden"
    assert boundary["preregistration_commit_must_be_pushed_before_implementation"]
    assert boundary["preregistration_commit_must_be_pushed_before_microbenchmark_or_numerics"]
    assert frozen["S2_equations_and_physical_parameters"] == "immutable"
    assert frozen["full_step_two_half_step_controller"] == "immutable"
    assert frozen["complete_3N_plus_1_residual"] == "immutable"
    assert frozen["active_high_bias_protocol"] == "high_bias_lock_15p8V"
    assert frozen["active_high_bias_voltage_V"] == 15.8
    assert frozen["high_bias_role"] == "qualitative_source_trend_probe"


def test_legacy_oracle_is_test_only_exact_pr8_bytes() -> None:
    oracle = _config()["legacy_oracle"]

    assert oracle["role"] == (
        "test_only_implementation_equivalence_oracle_not_scientific_truth"
    )
    assert oracle["PR8"]["commit"] == (
        "85e4257fc01af2e0bf706ef9001f263b1420ecaa"
    )
    assert oracle["PR8"]["tree"] == "50ef2214b19f98c6cada0f5f40c682de9eb16bee"
    assert oracle["source"]["git_blob"] == (
        "fd0e0773255181b037c4d6b6be4e482b735d1eff"
    )
    assert oracle["source"]["sha256"] == (
        "e1a349ca0275021508cd07da02576adafbbcdae81e122659274769f329016a37"
    )
    requirements = oracle["implementation_requirements"]
    assert requirements["scalar_LIL_assembly"] == "required"
    assert requirements["Python_face_loops"] == "required"
    assert requirements["independent_spsolve_per_RHS"] == "required"
    assert requirements["optimized_assembly_cache_factorization_or_postprocess"] == (
        "forbidden"
    )
    assert requirements["production_import_or_CLI_mode"] == "forbidden"
    snapshot = ROOT / oracle["future_snapshot"]["path"]
    if snapshot.exists():
        assert _sha256(snapshot) == oracle["future_snapshot"]["expected_sha256"]


def test_whitelist_forbids_scaling_retry_reuse_and_solver_changes() -> None:
    config = _config()
    whitelist = set(config["optimization_whitelist"])

    assert whitelist == {
        "atomic_per_C3_sample_journal",
        "staged_timing_telemetry",
        "precomputed_fixed_CSR_row_column_topology_and_face_geometry",
        "vectorized_face_conductance",
        "vectorized_terminal_flux",
        "vectorized_cell_Joule_kernel",
        "one_assembly_and_one_factorization_per_frozen_conductivity",
        "separate_direct_unit_and_actual_voltage_RHS_solves",
        "RAM_aware_C3_process_parallelism",
        "one_BLAS_and_OpenMP_thread_per_worker",
        "plan_ordered_atomic_result_publication",
    }
    forbidden = config["forbidden_optimizations"]
    assert all(value == "forbidden" for value in forbidden.values())
    scope = config["frozen_conductivity_scope"]
    assert scope["unit_voltage_RHS"] == "independent_direct_solve"
    assert scope["actual_voltage_RHS"] == "independent_direct_solve"
    assert scope["actual_solution_from_unit_scaling"] == "forbidden"
    assert scope["ephemeral_lifetime"] == "one_frozen_conductivity_evaluation_only"


def test_equivalence_matrix_and_votes_are_locked_without_iteration_count_vote() -> None:
    audit = _config()["equivalence_audit"]

    assert audit["frozen_candidate_audit_attempts"] == 1
    assert audit["normalized_relative_difference_max"] == pytest.approx(1.0e-12)
    assert audit["electrical_matrix"]["count"] == 9
    assert audit["interval_matrix"]["count"] == 18
    assert audit["short_progression_matrix"]["count"] == 9
    assert audit["failure_injection_matrix"]["count"] == 21
    assert audit["interval_matrix"]["paths"] == [
        "full_step",
        "first_half_step",
        "second_half_step",
    ]
    exact = set(audit["exact_votes"])
    assert {
        "nonlinear_method",
        "converged_disposition",
        "fallback_disposition",
        "accepted_rejected_sequence",
        "failure_classification",
        "event_count_direction_and_order",
        "reversal_count_direction_and_order",
    } == exact
    telemetry = set(audit["telemetry_only_nonvoting"])
    assert "Newton_iterations" in telemetry
    assert "Krylov_matvecs" in telemetry
    assert not exact.intersection(telemetry)
    assert audit["terminal_failure_disposition"] == (
        "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    )


def test_one_shot_readiness_pool_journal_and_budget_are_machine_locked() -> None:
    config = _config()
    readiness = config["readiness_execution"]
    pool = config["C3_pool"]
    journal = config["journal"]

    assert readiness["attempts"] == 1
    assert readiness["order"] == [
        "C1_serial",
        "C2_serial",
        "C3_persistent_Windows_spawn_pool",
    ]
    assert readiness["global_wall_clock_s_from_C1_start"] == 900
    assert readiness["worker_backstop_from_C1_start_s"] == 880
    assert readiness["parent_atomic_finalization_reserve_s"] == 20
    assert readiness["C3"]["single_interval_samples"] == 18
    assert readiness["C3"]["short_trajectory_plans"] == 9
    assert readiness["C3"]["C2_reused_trajectory_plans"] == 1
    assert readiness["C3"]["independently_submitted_pool_samples"] == 26
    assert readiness["C3"]["high_conductive_protocol"] == (
        "high_bias_lock_15p8V"
    )
    assert pool["start_method"] == "Windows_spawn"
    assert pool["worker_count_frozen_once_at_pool_launch"] is True
    assert pool["sample_retry"] == "forbidden"
    assert pool["migrate_failed_sample_to_another_worker"] == "forbidden"
    assert journal["states"] == ["SCHEDULED", "STARTED", "COMPLETED", "FAILED"]
    assert journal["SCHEDULED_before_pool_submission"] is True
    assert journal["STARTED_before_worker_numerics"] is True
    assert journal["completed_sample_artifact"]["publish_by_atomic_rename"] is True


def test_machine_preregistration_hashes_config_and_has_no_execution() -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))

    assert prereg["performance_repair_yaml_sha256"] == _sha256(CONFIG_PATH)
    assert prereg["status"] == (
        "preregistered_no_performance_implementation_or_numerics"
    )
    assert prereg["performance_implementation_started"] is False
    assert prereg["new_numerical_execution_before_preregistration_push"] is False
    assert prereg["candidate_implementation_frozen"] is False
    assert prereg["formal_execution_count"] == 0
    assert prereg["formal_artifact_count"] == 0
    assert set(prereg["allowed_final_dispositions"]) == {
        "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR",
        "NO_GO_RUNTIME",
        "INVALID_PREFLIGHT_INFRASTRUCTURE",
    }
    namespace = PREREG_PATH.parent.parent
    assert not (namespace / "formal_summary.json").exists()
    assert not (namespace / "formal_convergence.csv").exists()


def test_harness_erratum_preserves_candidate_and_authorizes_one_valid_audit() -> None:
    erratum = _harness_erratum()
    invalid = erratum["invalid_launch"]
    candidate = erratum["frozen_candidate"]
    audit = erratum["valid_audit"]

    assert invalid["disposition"] == (
        "INVALID_EQUIVALENCE_AUDIT_INFRASTRUCTURE_BEFORE_EXECUTION"
    )
    assert invalid["completed_rows"] == invalid["votes_cast"] == 0
    assert invalid["consumes_valid_frozen_audit"] is False
    assert candidate["commit"] == "1ae2704f6d84a3733d9de58aa23d992aa0c471a5"
    assert candidate["tree"] == "d3833a4a5dd067dab72c84f15fe2f8e726bd9512"
    assert candidate["identity"]["sha256"] == _sha256(CANDIDATE_IDENTITY_PATH)
    assert candidate["identity"]["byte_change"] == "forbidden"
    assert audit["permitted_valid_attempts"] == 1
    assert audit["automatic_retry"] == "forbidden"
    assert audit["exclusive_attempt_provenance"].endswith(
        "equivalence_valid_attempt_provenance.jsonl"
    )
    assert audit["provenance_events"] == [
        "SCHEDULED",
        "STARTED",
        "NUMERIC_DISPOSITION",
        "COMPLETED",
        "FAILED",
    ]
    assert audit["preexisting_attempt_provenance"] == (
        "refuse_before_numerical_execution"
    )
    assert audit["flush_and_fsync_each_event"] is True
    assert audit["matrix"] == {
        "electrical": 9,
        "single_interval": 18,
        "progression": 9,
        "failure_topology": 21,
        "total": 57,
    }
    assert audit["normalized_relative_difference_max"] == pytest.approx(1.0e-12)
    assert audit["valid_mismatch_fail_fast"] is True
    assert audit["mismatch_precedes_later_infrastructure_state"] is True


def test_harness_erratum_is_loader_only_and_keeps_formal_boundary_zero() -> None:
    erratum = _harness_erratum()
    revision = erratum["harness_revision"]
    boundary = erratum["execution_boundary"]
    frozen = erratum["frozen_semantics"]

    assert revision["combination_rule"] == (
        "frozen_candidate_identity_plus_versioned_harness_identity"
    )
    assert revision["loader_semantics"] == {
        "module_registered_in_sys_modules_before_exec_module": True,
        "registration_scope": "complete_equivalence_audit_and_atomic_publication",
        "prior_module_restored_after_scope": True,
        "absent_prior_module_removed_after_scope": True,
        "cleanup_on_load_or_audit_failure": True,
    }
    assert revision["wrapper_semantics"]["readiness_modes_exposed"] is False
    assert boundary["C1_C2_C3_readiness"] == "forbidden"
    assert boundary["runtime_cost_forecast"] == "forbidden"
    assert boundary["formal_execution_count"] == 0
    assert boundary["formal_artifact_count"] == 0
    assert frozen["S2_equations_parameters_source_scale"] == "unchanged"
    assert frozen["full_3N_plus_1_residual"] == "unchanged"
    assert frozen["full_step_two_half_step_controller"] == "unchanged"
    assert frozen["tolerances_ledgers_failure_topology"] == "unchanged"
    assert frozen["evaluations_unique_executions_reuses"] == [63, 60, 3]
