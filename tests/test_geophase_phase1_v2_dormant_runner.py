from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pinnpcm.solvers import geophase_phase1_v2_formal_runner as runner


ROOT = Path(__file__).resolve().parents[1]
DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
    / "execution_dag.json"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256(name.encode("utf-8")).hexdigest()
        for name in runner.REQUIRED_IDENTITY_HASHES
    }


def _dag() -> dict:
    return json.loads(DAG_PATH.read_text(encoding="utf-8"))


def _create(tmp_path: Path, run_id: str = "PRE-RUNNER-DRY"):
    return runner.create_prepared_registry(
        tmp_path,
        run_id=run_id,
        identity_hashes=_hashes(),
        execution_dag=_dag(),
        environment_summary={"physical_cores": 4, "formal_machine": False},
    )


def test_pre_registry_resume_and_case_completion_are_atomic_and_count_zero(
    tmp_path: Path,
) -> None:
    prepared = _create(tmp_path)
    assert prepared.state == "PREPARED"
    assert prepared.identity["formal_execution_count"] == 0
    assert prepared.identity["formal_unit_dispatch_enabled"] is False
    identity_hashes = prepared.identity["identity_hashes_sha256"]
    assert identity_hashes["controller_v2_overlay"] == _hashes()[
        "controller_v2_overlay"
    ]
    assert identity_hashes["resolved_runtime_identity"] == _hashes()[
        "resolved_runtime_identity"
    ]

    running = runner.begin_running(prepared.path)
    assert running.state == "RUNNING"
    partial = runner.create_partial_case_work(
        running.path, "PRE-UNIT-A", {"accepted_steps": 1}
    )
    interrupted = runner.interrupt_resumable(
        running.path, reason="synthetic injected interruption", partial_case_id="PRE-UNIT-A"
    )
    assert interrupted.state == "INTERRUPTED_RESUMABLE"
    assert partial.exists()
    assert not (running.path / "cases" / "PRE-UNIT-A.json").exists()

    resumed = runner.resume_same_run(
        running.path,
        run_id="PRE-RUNNER-DRY",
        expected_identity_hashes=_hashes(),
    )
    assert resumed.state == "RUNNING"
    completed_case = runner.publish_synthetic_case(
        resumed.path,
        case_id="PRE-UNIT-A",
        outcome="pass",
        classification="synthetic_case_pass",
        payload={"accepted_steps": 2},
    )
    assert completed_case.exists()
    assert not partial.exists()
    with pytest.raises(FileExistsError, match="immutable"):
        runner.publish_synthetic_case(
            resumed.path,
            case_id="PRE-UNIT-A",
            outcome="pass",
            classification="duplicate",
            payload={},
        )
    complete = runner.complete_pass(resumed.path)
    assert complete.state == "COMPLETED_PASS"
    assert complete.published_case_ids == ("PRE-UNIT-A",)
    assert all(event["state"] in runner.RUNNER_STATES for event in complete.events)
    assert complete.identity["formal_execution_count"] == 0


@pytest.mark.parametrize(
    "changed_identity",
    ("environment", "controller_v2_overlay", "resolved_runtime_identity"),
)
def test_resume_hash_mismatch_is_rejected_and_invalidates_registry(
    tmp_path: Path, changed_identity: str
) -> None:
    suffix = {
        "environment": "ENV",
        "controller_v2_overlay": "CTRL",
        "resolved_runtime_identity": "RESOLVED",
    }[changed_identity]
    run_id = f"PRE-HASH-MISMATCH-{suffix}"
    prepared = _create(tmp_path, run_id)
    runner.begin_running(prepared.path)
    runner.interrupt_resumable(prepared.path, reason="synthetic interruption")
    changed = _hashes()
    changed[changed_identity] = "f" * 64

    with pytest.raises(runner.InvalidContractError, match="hash mismatch"):
        runner.resume_same_run(
            prepared.path,
            run_id=run_id,
            expected_identity_hashes=changed,
        )
    assert runner.load_registry(prepared.path).state == "INVALID_CONTRACT"


@pytest.mark.parametrize(
    "missing_identity",
    ("controller_v2_overlay", "resolved_runtime_identity"),
)
def test_controller_v2_identity_is_required_before_dry_run_registry_creation(
    tmp_path: Path, missing_identity: str
) -> None:
    incomplete = _hashes()
    del incomplete[missing_identity]
    suffix = {
        "controller_v2_overlay": "CTRL",
        "resolved_runtime_identity": "RESOLVED",
    }[missing_identity]

    with pytest.raises(runner.InvalidContractError, match="hash set is incomplete"):
        runner.create_prepared_registry(
            tmp_path,
            run_id=f"PRE-MISSING-{suffix}",
            identity_hashes=incomplete,
            execution_dag=_dag(),
            environment_summary={"formal_machine": False},
        )


def test_foundation_fail_fast_blocks_remaining_and_separates_infrastructure(
    tmp_path: Path,
) -> None:
    scientific = _create(tmp_path, "PRE-FOUNDATION")
    runner.begin_running(scientific.path)
    failed = runner.record_foundation_failure(
        scientific.path,
        failing_case_id="PRE-FOUNDATION-FAIL",
        remaining_case_ids=["PRE-LATER-A", "PRE-LATER-B"],
        reason="injected ledger foundation failure",
    )
    assert failed.state == "COMPLETED_SCIENTIFIC_FAIL"
    assert failed.events[-1]["classification"] == "foundation_fail_fast"
    blocked = json.loads(
        (failed.path / "blocked" / "foundation_fail_fast.json").read_text(
            encoding="utf-8"
        )
    )
    assert blocked["blocked_case_ids"] == ["PRE-LATER-A", "PRE-LATER-B"]

    infrastructure = _create(tmp_path, "PRE-INFRASTRUCTURE")
    runner.begin_running(infrastructure.path)
    interrupted = runner.interrupt_resumable(
        infrastructure.path, reason="injected worker loss"
    )
    assert interrupted.state == "INTERRUPTED_RESUMABLE"
    assert interrupted.events[-1]["classification"] == "infrastructure_interruption"
    assert interrupted.state != failed.state


def test_identity_and_journal_tamper_are_detected(tmp_path: Path) -> None:
    identity_registry = _create(tmp_path, "PRE-TAMPER-IDENTITY")
    identity_path = next(identity_registry.path.glob("identity-*.json"))
    identity_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(runner.InvalidContractError, match="identity hash mismatch"):
        runner.load_registry(identity_registry.path)

    journal_registry = _create(tmp_path, "PRE-TAMPER-JOURNAL")
    event_path = next((journal_registry.path / "journal").glob("*.json"))
    event_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(runner.InvalidContractError, match="filename or ordering"):
        runner.load_registry(journal_registry.path)


def test_budget_state_and_contract_coverage_are_fail_closed(tmp_path: Path) -> None:
    prepared = _create(tmp_path, "PRE-BUDGET")
    exhausted = runner.mark_budget_exhausted(
        prepared.path, reason="synthetic 900 second limit"
    )
    assert exhausted.state == "BUDGET_EXHAUSTED"
    assert exhausted.events[-1]["classification"] == "infrastructure_budget_exhaustion"

    invalid = _dag()
    invalid["unique_execution_unit_count"] = 59
    with pytest.raises(runner.InvalidContractError, match="60 units"):
        runner.create_prepared_registry(
            tmp_path,
            run_id="PRE-BAD-COVERAGE",
            identity_hashes=_hashes(),
            execution_dag=invalid,
            environment_summary={},
        )
    with pytest.raises(ValueError, match="PRE identifier"):
        runner.create_prepared_registry(
            tmp_path,
            run_id="P1V2-FORMAL-001",
            identity_hashes=_hashes(),
            execution_dag=_dag(),
            environment_summary={},
        )
