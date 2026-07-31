from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from pinnpcm.audit import geophase_phase1_v2_equivalence_v3_one_shot as one_shot


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_equivalence_v3_independent_audit.yaml"
)
PLAN_MANIFEST = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_metric_validity"
    / "coverage_correction"
    / "mechanical_plan_contract.csv"
)


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_contract() -> SimpleNamespace:
    rows: dict[int, dict[str, str]] = {}
    for index in range(57):
        if index < 9:
            family = "electrical"
        elif index < 27:
            family = "interval"
        elif index < 36:
            family = "progression"
        else:
            family = "failure"
        rows[index] = {
            "sample_id": f"EQ-V3-SYNTHETIC-{index:02d}",
            "family": family,
            "grid": "L1",
            "plan_sha256": f"{index + 1:064x}",
        }
    return SimpleNamespace(core=SimpleNamespace(plan_rows=rows))


def _paths(tmp_path: Path) -> one_shot.OutputPaths:
    return one_shot.OutputPaths(
        registry=tmp_path / "execution_registry.json",
        journal=tmp_path / "audit_journal.jsonl",
        normalized_records=tmp_path / "normalized_records",
        electrical_table=tmp_path / "electrical_equivalence_v3.csv",
        interval_table=tmp_path / "interval_equivalence_v3.csv",
        progression_table=tmp_path / "progression_equivalence_v3.csv",
        failure_table=tmp_path / "failure_equivalence_v3.csv",
        summary=tmp_path / "equivalence_v3_summary.json",
    )


def _initialise(paths: one_shot.OutputPaths) -> dict:
    initial = one_shot.build_initial_registry(
        attempt_id="equivalence-v3-synthetic-attempt-1",
        plan_manifest_sha256="a" * 64,
        ledger_manifest_sha256="b" * 64,
        contract_bundle_sha256="c" * 64,
        runner_source_sha256="d" * 64,
        remote_anchor_commit="e" * 40,
    )
    one_shot.write_initial_registry(paths.registry, initial)
    return initial


def _install_synthetic_comparator(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_at: int | None,
    invalid_at: int | None = None,
) -> None:
    def observation_to_record(
        observation: dict,
        *,
        plan_index: int,
        input_sha256: str,
        contract: SimpleNamespace,
        runtime_input_sha256: str,
        validation_errors: tuple[str, ...],
    ) -> dict:
        return {
            "plan_index": plan_index,
            "input_sha256": input_sha256,
            "runtime_input_sha256": runtime_input_sha256,
            "observation": observation,
            "validation_errors": list(validation_errors),
        }

    def compare_record_pair(candidate: dict, oracle: dict, contract: SimpleNamespace) -> dict:
        index = int(candidate["plan_index"])
        invalid = index == invalid_at
        passed = index != fail_at and not invalid
        terminal = "INVALID_INFRA" if invalid else ("PASS" if passed else "VALID_FAIL")
        payload = {
            "schema_version": "synthetic_equivalence_v3",
            "terminal_state": terminal,
            "row_pass": passed,
            "failure_stage": (
                "normalization" if invalid else ("row_complete" if passed else "record_comparison")
            ),
            "failure_category": (
                "schema_or_producer_identity"
                if invalid
                else ("all_fields_and_votes_pass" if passed else "A_vote_failure")
            ),
            "issues": [],
            "votes": [
                {
                    "field": "temperature_K",
                    "category": "A_primary_physical",
                    "passed": passed,
                }
            ],
            "candidate_record_sha256": one_shot._v3._schema.canonical_sha256(candidate),
            "oracle_record_sha256": one_shot._v3._schema.canonical_sha256(oracle),
            "predecessor_comparison": {"synthetic_plan_index": index},
        }
        payload["comparison_sha256"] = one_shot._v3._schema.canonical_sha256(payload)
        return payload

    def finalise_plan_terminal(comparisons: list[dict], contract: SimpleNamespace) -> SimpleNamespace:
        return SimpleNamespace(value="PASS" if len(comparisons) == 57 else "INVALID_INFRA")

    monkeypatch.setattr(one_shot._v3, "observation_to_record", observation_to_record)
    monkeypatch.setattr(one_shot._v3, "compare_record_pair", compare_record_pair)
    monkeypatch.setattr(one_shot._v3, "finalise_plan_terminal", finalise_plan_terminal)


def test_contract_freezes_new_identity_and_immutable_historical_counts() -> None:
    config = _config()
    assert config["authority_lock"]["base_main"] == (
        "3110b85d0931a36394b302f0df2d11b04a0959a8"
    )
    assert config["authority_lock"]["strict_equivalence_v1"]["completed_rows"] == 12
    assert config["authority_lock"]["equivalence_v2"] == {
        "terminal_state": "VALID_FAIL",
        "terminal_event": "RECORD_VALIDATION_FAILURE",
        "completed_rows": 10,
        "expected_rows": 57,
        "equivalence_v2_execution_count": 1,
        "immutable": True,
    }
    assert config["execution_counts"]["equivalence_v2_execution_count"] == 1
    assert config["execution_counts"]["equivalence_v3_execution_count"] == 0
    assert config["execution_counts"]["formal_execution_count"] == 0


def test_contract_hashes_closure_manifests_candidate_and_oracle() -> None:
    config = _config()
    closure = config["frozen_schema_closure_v4"]
    for key in (
        "config",
        "report",
        "preregistration",
        "comparator",
        "ledger_schema",
        "ledger_group_manifest",
        "field_manifest",
        "plan_manifest",
    ):
        record = closure[key]
        assert _sha(ROOT / record["path"]) == record["sha256"]
    numerical = config["frozen_numerical_identity"]
    assert _sha(ROOT / numerical["candidate"]["identity_path"]) == numerical["candidate"][
        "identity_sha256"
    ]
    assert _sha(ROOT / numerical["oracle"]["source_path"]) == numerical["oracle"][
        "source_sha256"
    ]


def test_frozen_plan_is_exact_0_through_56_without_partition_overlap() -> None:
    with PLAN_MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indices = [int(row["plan_index"]) for row in rows]
    assert indices == list(range(57))
    assert len({row["sample_id"] for row in rows}) == 57
    execution = _config()["execution_control"]
    assert execution["exact_plan_order"] == {
        "inclusive_start": 0,
        "inclusive_end": 56,
        "sequence": "ascending_without_skip_reorder_or_retry",
    }
    development = set(range(0, 12))
    held_out = set(range(12, 57))
    assert development.isdisjoint(held_out)
    assert development | held_out == set(indices)
    assert execution["preview_or_partial_trial_before_attempt"] == "forbidden"
    assert execution["stitch_or_resume_historical_rows"] == "forbidden"


def test_registry_atomically_consumes_only_v3_and_never_formal(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initial = _initialise(paths)
    running = one_shot.activate_registry_once(
        paths.registry, expected_registry_sha256=initial["registry_sha256"]
    )
    assert running["equivalence_v2_execution_count"] == 1
    assert running["equivalence_v3_execution_count"] == 1
    assert running["formal_execution_count"] == 0
    with pytest.raises(one_shot.IndependentAuditError):
        one_shot.activate_registry_once(
            paths.registry, expected_registry_sha256=initial["registry_sha256"]
        )


def test_hash_chain_is_append_only_and_detects_tamper(tmp_path: Path) -> None:
    path = tmp_path / "audit_journal.jsonl"
    journal = one_shot.AuditHashChainJournal(path, attempt_id="synthetic-v3")
    journal.append("ATTEMPT_STARTED")
    prefix = path.read_bytes()
    row = one_shot.PlanRow(0, "EQ-SYNTHETIC-0", "electrical", "L1", "a" * 64, {})
    journal.append("ROW_STARTED", row=row)
    assert path.read_bytes().startswith(prefix)
    records = one_shot.validate_journal(path)
    assert records[1]["previous_record_sha256"] == records[0]["record_sha256"]
    path.write_bytes(path.read_bytes().replace(b"ROW_STARTED", b"ROW_STOPPED", 1))
    with pytest.raises(one_shot.IndependentAuditError):
        one_shot.validate_journal(path)


def test_stub_pass_requires_all_57_explicit_ordered_rows_and_published_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    initial = _initialise(paths)
    contract = _fake_contract()
    _install_synthetic_comparator(monkeypatch, fail_at=None)
    executed: list[int] = []

    def executor(row: one_shot.PlanRow) -> one_shot.RowObservationPair:
        executed.append(row.plan_index)
        return one_shot.RowObservationPair(
            candidate_observation={"side": "candidate", "index": row.plan_index},
            oracle_observation={"side": "oracle", "index": row.plan_index},
            runtime_input_sha256=f"{1000 + row.plan_index:064x}",
        )

    result = one_shot.run_independent_audit(
        contract=contract,
        row_executor=executor,
        paths=paths,
        expected_registry_sha256=initial["registry_sha256"],
    )

    assert result.terminal_state == "PASS"
    assert result.completed_rows == 57
    assert executed == list(range(57))
    assert len(list((paths.normalized_records / "candidate").glob("*.json"))) == 57
    assert len(list((paths.normalized_records / "oracle").glob("*.json"))) == 57
    completed = [
        record for record in one_shot.validate_journal(paths.journal)
        if record["event"] == "ROW_COMPLETED"
    ]
    assert [record["plan_index"] for record in completed] == list(range(57))
    assert all(record["candidate_record_sha256"] for record in completed)
    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    assert summary["terminal_state"] == "PASS"
    assert summary["completed_rows"] == summary["passed_rows"] == 57
    assert summary["unassessed_plan_indices"] == []
    assert summary["equivalence_v3_execution_count"] == 1
    assert summary["formal_execution_count"] == 0


def test_stub_valid_failure_is_fail_fast_without_skip_or_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    initial = _initialise(paths)
    contract = _fake_contract()
    _install_synthetic_comparator(monkeypatch, fail_at=4)
    executed: list[int] = []

    def executor(row: one_shot.PlanRow) -> one_shot.RowObservationPair:
        executed.append(row.plan_index)
        return one_shot.RowObservationPair({}, {}, f"{2000 + row.plan_index:064x}")

    result = one_shot.run_independent_audit(
        contract=contract,
        row_executor=executor,
        paths=paths,
        expected_registry_sha256=initial["registry_sha256"],
    )
    assert result.terminal_state == "VALID_FAIL"
    assert result.completed_rows == 5
    assert executed == [0, 1, 2, 3, 4]
    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    assert summary["unassessed_plan_indices"] == list(range(5, 57))
    with pytest.raises(one_shot.IndependentAuditError):
        one_shot.activate_registry_once(
            paths.registry, expected_registry_sha256=initial["registry_sha256"]
        )


def test_stub_invalid_infrastructure_casts_no_row_vote_or_completed_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    initial = _initialise(paths)
    contract = _fake_contract()
    _install_synthetic_comparator(monkeypatch, fail_at=None, invalid_at=2)
    executed: list[int] = []

    def executor(row: one_shot.PlanRow) -> one_shot.RowObservationPair:
        executed.append(row.plan_index)
        return one_shot.RowObservationPair({}, {}, f"{3000 + row.plan_index:064x}")

    result = one_shot.run_independent_audit(
        contract=contract,
        row_executor=executor,
        paths=paths,
        expected_registry_sha256=initial["registry_sha256"],
    )
    assert result.terminal_state == "INVALID_INFRA"
    assert result.completed_rows == 2
    assert executed == [0, 1, 2]
    journal = one_shot.validate_journal(paths.journal)
    completed = [record for record in journal if record["event"] == "ROW_COMPLETED"]
    assert [record["plan_index"] for record in completed] == [0, 1]
    assert any(
        record["event"] == "ROW_INFRA_FAILURE" and record["plan_index"] == 2
        for record in journal
    )
    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    assert summary["completed_rows"] == 2
    assert summary["unassessed_plan_indices"] == list(range(2, 57))


def test_plan_guard_rejects_missing_row_before_attempt() -> None:
    contract = _fake_contract()
    del contract.core.plan_rows[12]
    with pytest.raises(one_shot.IndependentAuditError, match="exact 0..56"):
        one_shot.plan_rows_from_contract(contract)


def test_runner_cli_and_adapter_have_no_historical_comparator_or_runner_call() -> None:
    forbidden = {
        "run_equivalence_audit",
        "compare_observations",
        "run_one_shot_audit",
    }
    paths = (
        ROOT / "src" / "pinnpcm" / "audit" / "geophase_phase1_v2_equivalence_v3_one_shot.py",
        ROOT / "src" / "pinnpcm" / "audit" / "geophase_phase1_v2_equivalence_v3_production_adapter.py",
        ROOT / "scripts" / "run_geophase_phase1_v2_equivalence_v3_independent_audit.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        assert forbidden.isdisjoint(calls), f"historical call in {path.name}"


def test_synthetic_control_plane_never_imports_numerical_adapter() -> None:
    source = (
        ROOT
        / "src"
        / "pinnpcm"
        / "audit"
        / "geophase_phase1_v2_equivalence_v3_one_shot.py"
    ).read_text(encoding="utf-8")
    assert "geophase_phase1_v2_equivalence_v3_production_adapter" not in source
    assert "geophase_2p5d_fvm" not in source
    assert "source_corrected_controller_overlay" not in source
