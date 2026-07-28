from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
)
ADDENDUM_PATH = ROOT / "configs" / "geophase_phase1_v2_execution_addendum.yaml"
MANIFEST_CSV_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "formal_evaluation_manifest.csv"
)
CODE_PATHS = (
    Path("src/pinnpcm/solvers/geophase_phase1_v2_fvm.py"),
    Path("src/pinnpcm/solvers/geophase_phase1_v2_implicit.py"),
    Path("src/pinnpcm/solvers/geophase_phase1_v2_streaming.py"),
    Path("src/pinnpcm/solvers/geophase_phase1_v2_formal_runner.py"),
    Path("src/pinnpcm/solvers/geophase_phase1_v2_runtime.py"),
    Path("scripts/run_geophase_phase1_v2_runtime_readiness.py"),
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json(name: str) -> dict:
    return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def test_runtime_readiness_stops_on_one_locked_critical_state_failure() -> None:
    readiness = _json("readiness_summary.json")
    preflight = _json("preflight_summary.json")
    cause = "RuntimeError: S2 transition increment failed at locked floor"

    assert readiness["disposition"] == "NO_GO_RUNTIME"
    assert readiness["unique_primary_cause"] == cause
    assert readiness["all_runtime_gate_failures"] == [cause]
    assert readiness["claim_status"] == "forbidden"
    assert readiness["campaign_cost_forecast"] == {}
    assert readiness["campaign_cost_forecast_status"] == (
        "not_computed_because_required_critical_stability_gate_failed"
    )
    assert readiness["performance_only_failure"] is False
    assert readiness["performance_repair_consumed"] is False
    assert readiness["performance_repair_opportunity_remaining"] is True
    assert readiness["unit_voltage_scaling_active"] is False
    assert readiness["validation_status"] == (
        "focused_validation_pass_after_fail_closed_stop"
    )
    assert readiness["validation"] == {
        "frozen_gt_hashes": "8_of_8_unchanged",
        "focused_CI_equivalent_pytest": "184_passed_1_expected_S1_skip",
        "full_regression": "not_run_by_fail_closed_scope",
        "governance_audit": "pass_with_no_failed_checks",
        "historical_evidence_manifest": "pass",
        "phase1v2_focused_pytest": "53_passed",
        "tracked_json": "222_valid_0_failures",
    }

    assert preflight["status"] == "fail"
    assert preflight["failures"] == [
        {"cause": cause, "sample_id": "PRE-PARITY-STREAM"}
    ]
    assert preflight["required_single_step_completed"] == 0
    assert preflight["required_short_trajectory_completed"] == 0
    assert preflight["partial_telemetry_status"].startswith(
        "accepted_rejected_Newton_Krylov_Armijo"
    )
    assert preflight["wall_clock_s"] is None
    assert preflight["peak_rss_bytes"] is None


def test_runtime_rows_are_pre_only_and_do_not_invent_missing_telemetry() -> None:
    with (OUTPUT_DIR / "preflight_samples.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    with (OUTPUT_DIR / "campaign_cost_forecast.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        cost_rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    row = rows[0]
    assert row["sample_id"] == "PRE-PARITY-STREAM"
    assert row["state_id"] == "legal_critical"
    assert row["protocol_id"] == "transition_probe_12p5V"
    assert row["status"] == "fail"
    assert row["error_message"] == (
        "S2 transition increment failed at locked floor"
    )
    for field in (
        "accepted_steps",
        "rejected_steps",
        "newton_iterations",
        "krylov_matvecs",
        "armijo_backtracks",
        "thermal_relative_residual_max",
        "peak_rss_bytes",
    ):
        assert row[field] == ""
    assert cost_rows == []


def test_runtime_evidence_keeps_contract_formal_count_and_artifacts_unchanged() -> None:
    readiness = _json("readiness_summary.json")
    preflight = _json("preflight_summary.json")
    prereg = _json("preregistration.json")
    dag = _json("execution_dag.json")
    manifest_rows = list(
        csv.DictReader(MANIFEST_CSV_PATH.read_text(encoding="utf-8").splitlines())
    )

    assert readiness["execution_addendum_sha256"] == _sha256(ADDENDUM_PATH)
    assert readiness["execution_dag_sha256"] == _sha256(
        OUTPUT_DIR / "execution_dag.json"
    )
    assert readiness["execution_addendum_preregistration_commit"] == (
        "b830d4f3f45f634883de906972a7712f311cfa93"
    )
    assert prereg["runtime_preflight_executed"] is False
    assert prereg["new_runtime_numerical_work_before_addendum_push"] is False
    assert dag["evaluation_item_count"] == 63
    assert dag["unique_execution_unit_count"] == 60
    assert dag["reused_evaluation_count"] == 3
    assert len(manifest_rows) == 63
    assert all(row["status"] == "planned_not_executed" for row in manifest_rows)
    for payload in (readiness, preflight, prereg, dag):
        assert payload["formal_execution_count"] == 0
    assert readiness["formal_execution_consumed"] is False
    assert readiness["formal_artifact_count"] == 0
    assert not (OUTPUT_DIR.parent / "formal_summary.json").exists()
    assert not (OUTPUT_DIR.parent / "formal_convergence.csv").exists()


def test_environment_and_code_tree_hashes_are_self_consistent() -> None:
    readiness = _json("readiness_summary.json")
    environment = _json("environment.json")
    recorded_environment_hash = environment.pop("environment_sha256")
    assert recorded_environment_hash == _canonical_hash(environment)
    assert readiness["environment_sha256"] == recorded_environment_hash
    assert environment["physical_core_measurement_available"] is True
    assert environment["physical_core_count"] > 0
    assert environment["logical_core_count"] >= environment["physical_core_count"]
    assert environment["all_worker_math_thread_limits_equal_one"] is True
    assert set(environment["thread_environment"].values()) == {"1"}
    assert environment["measurement_role"].startswith(
        "post_failure_evidence_recorder_environment"
    )

    file_hashes = {path.as_posix(): _sha256(ROOT / path) for path in CODE_PATHS}
    assert readiness["code_tree_sha256"] == _canonical_hash(file_hashes)


def test_dormant_runner_passes_without_enabling_formal_dispatch() -> None:
    runner = _json("runner_dry_run.json")
    assert runner["status"] == "pass"
    assert runner["registry_location"] == "temporary_directory_only"
    assert runner["run_id_prefix"] == "PRE-"
    assert runner["formal_execution_count"] == 0
    assert runner["formal_artifact_count"] == 0
    assert runner["checks"]
    assert all(runner["checks"].values())
    assert runner["checks"]["coverage_63_60_3"] is True
    assert runner["checks"]["real_formal_dispatch_disabled"] is True
    assert runner["checks"]["same_run_id_resume"] is True
    assert runner["checks"]["hash_mismatch_rejected"] is True
    assert runner["checks"]["foundation_fail_fast_blocks_remaining"] is True
    assert runner["checks"]["scientific_and_infrastructure_failure_separated"] is True
