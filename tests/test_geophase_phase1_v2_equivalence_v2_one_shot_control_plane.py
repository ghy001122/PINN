from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_one_shot as one_shot


def _row(index: int = 0) -> one_shot.PlanRow:
    return one_shot.PlanRow(
        plan_index=index,
        sample_id=f"EQ-SYNTHETIC-{index}",
        family="electrical",
        grid_id="L1",
        input_sha256="a" * 64,
        frozen_row={},
    )


def test_registry_consumes_the_only_attempt_atomically(tmp_path: Path) -> None:
    path = tmp_path / "execution_registry.json"
    initial = one_shot.build_initial_registry(
        attempt_id="PRE-EQUIVALENCE-V2-ATTEMPT-001",
        plan_manifest_sha256="a" * 64,
        contract_bundle_sha256="b" * 64,
        runner_source_sha256="c" * 64,
        remote_anchor_commit="d" * 40,
    )
    one_shot.write_initial_registry(path, initial)

    running = one_shot.activate_registry_once(
        path, expected_registry_sha256=initial["registry_sha256"]
    )

    assert running["state"] == "RUNNING"
    assert running["equivalence_v2_execution_count"] == 1
    assert running["formal_execution_count"] == 0
    with pytest.raises(one_shot.OneShotExecutionError, match="identity drifted|consumed"):
        one_shot.activate_registry_once(
            path, expected_registry_sha256=initial["registry_sha256"]
        )


def test_journal_atomic_publication_preserves_the_exact_prior_prefix(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit_journal.jsonl"
    journal = one_shot.AuditHashChainJournal(path, attempt_id="PRE-ATTEMPT-001")
    journal.append("ATTEMPT_STARTED")
    prefix = path.read_bytes()

    journal.append("ROW_STARTED", row=_row())

    assert path.read_bytes().startswith(prefix)
    records = one_shot.validate_journal(path)
    assert [record["event"] for record in records] == [
        "ATTEMPT_STARTED",
        "ROW_STARTED",
    ]
    assert records[1]["previous_record_sha256"] == records[0]["record_sha256"]


@pytest.mark.parametrize("damage", ["truncate", "tamper"])
def test_journal_rejects_torn_or_tampered_records(
    tmp_path: Path, damage: str
) -> None:
    path = tmp_path / "audit_journal.jsonl"
    journal = one_shot.AuditHashChainJournal(path, attempt_id="PRE-ATTEMPT-001")
    journal.append("ATTEMPT_STARTED")
    payload = path.read_bytes()
    if damage == "truncate":
        path.write_bytes(payload[:-1])
    else:
        path.write_bytes(payload.replace(b"ATTEMPT_STARTED", b"ATTEMPT_STOPPED", 1))

    with pytest.raises(one_shot.OneShotExecutionError):
        one_shot.validate_journal(path)


def test_control_plane_has_no_historical_v1_comparator_or_runner_call() -> None:
    source = inspect.getsource(one_shot)

    forbidden_call_names = (
        "run_" + "equivalence_audit",
        "compare_" + "observations",
        "run_" + "electrical_pair",
    )
    assert all(name not in source for name in forbidden_call_names)
    assert "geophase_phase1_v2_performance_equivalence" not in source


def _fake_contract() -> SimpleNamespace:
    plan_rows: dict[int, dict[str, str]] = {}
    for index in range(57):
        if index < 9:
            family = "electrical"
        elif index < 27:
            family = "interval"
        elif index < 36:
            family = "progression"
        else:
            family = "failure"
        plan_rows[index] = {
            "sample_id": f"EQ-SYNTHETIC-{index:02d}",
            "family": family,
            "grid": "L1",
            "plan_sha256": f"{index + 1:064x}",
        }
    return SimpleNamespace(
        plan_rows=plan_rows,
        core=SimpleNamespace(plan_rows=plan_rows),
    )


def _output_paths(tmp_path: Path) -> one_shot.OutputPaths:
    return one_shot.OutputPaths(
        registry=tmp_path / "execution_registry.json",
        journal=tmp_path / "audit_journal.jsonl",
        electrical_table=tmp_path / "electrical_equivalence_v2.csv",
        interval_table=tmp_path / "interval_equivalence_v2.csv",
        progression_table=tmp_path / "progression_equivalence_v2.csv",
        failure_table=tmp_path / "failure_equivalence_v2.csv",
        summary=tmp_path / "equivalence_v2_summary.json",
    )


def _initialise_registry(paths: one_shot.OutputPaths) -> dict:
    initial = one_shot.build_initial_registry(
        attempt_id="PRE-EQUIVALENCE-V2-ATTEMPT-001",
        plan_manifest_sha256="a" * 64,
        contract_bundle_sha256="b" * 64,
        runner_source_sha256="c" * 64,
        remote_anchor_commit="d" * 40,
    )
    one_shot.write_initial_registry(paths.registry, initial)
    return initial


def _install_synthetic_comparator(monkeypatch: pytest.MonkeyPatch, *, fail_at: int | None) -> None:
    def observation_to_record(
        observation: dict,
        *,
        plan_index: int,
        input_sha256: str,
        contract: SimpleNamespace,
        validation_errors: tuple[str, ...],
    ) -> dict:
        return {
            "plan_index": plan_index,
            "input_sha256": input_sha256,
            "observation": observation,
            "validation_errors": list(validation_errors),
        }

    def compare_record_pair(candidate: dict, oracle: dict, contract: SimpleNamespace) -> dict:
        index = candidate["plan_index"]
        row = contract.plan_rows[index]
        passed = index != fail_at
        payload = {
            "schema_version": "synthetic_v3_comparison",
            "record_status": "valid_content",
            "row_pass": passed,
            "failure_event": None if passed else "FIELD_VOTE_FAILURE",
            "issues": [],
            "votes": [
                {
                    "field": "temperature_K",
                    "category": "A_primary_physical",
                    "passed": passed,
                }
            ],
            "plan_identity": {
                "plan_index": index,
                "sample_id": row["sample_id"],
                "family": row["family"],
                "grid_id": row["grid"],
                "input_sha256": row["plan_sha256"],
            },
            "candidate_record_sha256": one_shot.canonical_sha256(candidate),
            "oracle_record_sha256": one_shot.canonical_sha256(oracle),
            "core_comparison": None,
        }
        payload["comparison_sha256"] = one_shot._closure_v3._core.canonical_sha256(
            payload
        )
        return payload

    monkeypatch.setattr(one_shot._closure_v3, "observation_to_record", observation_to_record)
    monkeypatch.setattr(one_shot._closure_v3, "compare_record_pair", compare_record_pair)


def test_stubbed_one_shot_pass_requires_exact_0_through_56_and_atomic_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _fake_contract()
    paths = _output_paths(tmp_path)
    initial = _initialise_registry(paths)
    _install_synthetic_comparator(monkeypatch, fail_at=None)
    executed: list[int] = []

    def row_executor(row: one_shot.PlanRow) -> one_shot.RowObservationPair:
        executed.append(row.plan_index)
        return one_shot.RowObservationPair(
            candidate_observation={"side": "candidate", "index": row.plan_index},
            oracle_observation={"side": "oracle", "index": row.plan_index},
        )

    outcome = one_shot.run_one_shot_audit(
        contract=contract,
        row_executor=row_executor,
        paths=paths,
        expected_registry_sha256=initial["registry_sha256"],
    )

    assert outcome.terminal_state == "PASS"
    assert outcome.completed_rows == 57
    assert executed == list(range(57))
    assert one_shot.load_registry(paths.registry)["equivalence_v2_execution_count"] == 1
    assert one_shot.load_registry(paths.registry)["formal_execution_count"] == 0
    assert all(path.is_file() for path in paths.family_tables.values())
    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    assert summary["terminal_state"] == "PASS"
    assert summary["completed_rows"] == 57
    assert summary["unassessed_plan_indices"] == []
    assert one_shot.validate_journal(paths.journal)[-1]["terminal_state"] == "PASS"
    with pytest.raises(one_shot.OneShotExecutionError):
        one_shot.activate_registry_once(
            paths.registry, expected_registry_sha256=initial["registry_sha256"]
        )


def test_stubbed_valid_failure_is_fail_fast_and_never_schedules_next_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _fake_contract()
    paths = _output_paths(tmp_path)
    initial = _initialise_registry(paths)
    _install_synthetic_comparator(monkeypatch, fail_at=3)
    executed: list[int] = []

    def row_executor(row: one_shot.PlanRow) -> one_shot.RowObservationPair:
        executed.append(row.plan_index)
        return one_shot.RowObservationPair({}, {})

    outcome = one_shot.run_one_shot_audit(
        contract=contract,
        row_executor=row_executor,
        paths=paths,
        expected_registry_sha256=initial["registry_sha256"],
    )

    assert outcome.terminal_state == "VALID_FAIL"
    assert outcome.completed_rows == 4
    assert executed == [0, 1, 2, 3]
    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    assert summary["unassessed_plan_indices"] == list(range(4, 57))
    events = one_shot.validate_journal(paths.journal)
    assert not any(record["plan_index"] == 4 for record in events)


def test_plan_guard_rejects_skip_or_duplicate_before_execution() -> None:
    contract = _fake_contract()
    del contract.plan_rows[12]
    with pytest.raises(one_shot.OneShotExecutionError, match="exactly 0..56"):
        one_shot.plan_rows_from_contract(contract)

    contract = _fake_contract()
    contract.plan_rows[1]["sample_id"] = contract.plan_rows[0]["sample_id"]
    with pytest.raises(one_shot.OneShotExecutionError, match="duplicated"):
        one_shot.plan_rows_from_contract(contract)
