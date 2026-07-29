from __future__ import annotations

import json
from pathlib import Path

import pytest

import pinnpcm.solvers.geophase_phase1_v2_readiness_journal as journal_module
from pinnpcm.solvers.geophase_phase1_v2_readiness_journal import (
    JOURNAL_FIELDS,
    JOURNAL_STATES,
    ReadinessJournalError,
    ReadinessProvenanceJournal,
    SampleArtifactError,
    build_completed_sample_document,
    publish_completed_sample,
    published_sample_is_voting,
    validate_journal,
    write_completed_sample_temp,
)


pytestmark = [pytest.mark.phase1, pytest.mark.current]

INPUT_A = "a" * 64
INPUT_B = "b" * 64
OUTPUT_A = "c" * 64


def test_parent_writer_emits_the_four_locked_states_and_a_valid_hash_chain(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provenance.jsonl"
    writer = ReadinessProvenanceJournal(path)

    writer.append(
        "SCHEDULED", plan_index=0, sample_id="PRE-C3-A", PID=100, input_sha256=INPUT_A
    )
    writer.append(
        "STARTED", plan_index=0, sample_id="PRE-C3-A", PID=101, input_sha256=INPUT_A
    )
    writer.append(
        "COMPLETED",
        plan_index=0,
        sample_id="PRE-C3-A",
        PID=101,
        input_sha256=INPUT_A,
        output_sha256=OUTPUT_A,
    )
    writer.append(
        "SCHEDULED", plan_index=1, sample_id="PRE-C3-B", PID=100, input_sha256=INPUT_B
    )
    writer.append(
        "FAILED",
        plan_index=1,
        sample_id="PRE-C3-B",
        PID=100,
        input_sha256=INPUT_B,
        error_classification="performance_budget_never_started",
    )

    records = validate_journal(path)
    assert {record["state"] for record in records} == JOURNAL_STATES
    assert [record["sequence"] for record in records] == list(range(5))
    assert all(set(record) == set(JOURNAL_FIELDS) for record in records)
    assert records[0]["previous_record_sha256"] == "0" * 64
    for previous, current in zip(records, records[1:]):
        assert current["previous_record_sha256"] == previous["record_sha256"]
    assert records[-1]["error_classification"] == (
        "performance_budget_never_started"
    )


def test_journal_flushes_and_fsyncs_every_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real_fsync = journal_module.os.fsync

    def recording_fsync(file_descriptor: int) -> None:
        calls.append(file_descriptor)
        real_fsync(file_descriptor)

    monkeypatch.setattr(journal_module.os, "fsync", recording_fsync)
    writer = ReadinessProvenanceJournal(tmp_path / "provenance.jsonl")
    creation_calls = len(calls)
    writer.append(
        "SCHEDULED", plan_index=0, sample_id="PRE-C3-A", PID=100, input_sha256=INPUT_A
    )
    writer.append(
        "FAILED",
        plan_index=0,
        sample_id="PRE-C3-A",
        PID=100,
        input_sha256=INPUT_A,
        error_classification="parent_budget_stop",
    )

    assert creation_calls == 1
    assert len(calls) == creation_calls + 2


def test_journal_rejects_tamper_unknown_state_and_invalid_transition(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provenance.jsonl"
    writer = ReadinessProvenanceJournal(path)
    writer.append(
        "SCHEDULED", plan_index=0, sample_id="PRE-C3-A", PID=100, input_sha256=INPUT_A
    )

    with pytest.raises(ReadinessJournalError, match="transition"):
        writer.append(
            "COMPLETED",
            plan_index=0,
            sample_id="PRE-C3-A",
            PID=101,
            input_sha256=INPUT_A,
            output_sha256=OUTPUT_A,
        )
    with pytest.raises(ReadinessJournalError, match="state"):
        writer.append(
            "CANCELLED", plan_index=1, sample_id="PRE-C3-B", PID=100, input_sha256=INPUT_B
        )

    record = json.loads(path.read_text(encoding="utf-8"))
    record["sample_id"] = "PRE-TAMPERED"
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ReadinessJournalError, match="hash mismatch"):
        validate_journal(path)


def test_completed_sample_is_nonvoting_until_atomic_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = build_completed_sample_document(
        plan_index=4,
        sample_id="PRE-C3-L2-LEGAL",
        input_sha256=INPUT_A,
        payload={"finite_metric": 1.25, "ledger_pass": True, "events": []},
    )
    temporary = tmp_path / "sample.json.tmp"
    published = tmp_path / "sample.json"
    write_completed_sample_temp(temporary, document)
    assert not published_sample_is_voting(
        temporary,
        expected_plan_index=4,
        expected_sample_id="PRE-C3-L2-LEGAL",
        expected_input_sha256=INPUT_A,
    )

    replace_calls: list[tuple[Path, Path]] = []
    real_replace = journal_module.os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(journal_module.os, "replace", recording_replace)
    result = publish_completed_sample(
        temporary,
        published,
        expected_plan_index=4,
        expected_sample_id="PRE-C3-L2-LEGAL",
        expected_input_sha256=INPUT_A,
    )

    assert replace_calls == [(temporary, published)]
    assert not temporary.exists()
    assert published.is_file()
    assert result.output_sha256 == document["output_sha256"]
    assert published_sample_is_voting(
        published,
        expected_plan_index=4,
        expected_sample_id="PRE-C3-L2-LEGAL",
        expected_input_sha256=INPUT_A,
    )


@pytest.mark.parametrize("defect", ["schema", "hash", "nonfinite", "incomplete"])
def test_invalid_or_incomplete_sample_cannot_be_published(
    tmp_path: Path, defect: str
) -> None:
    document = build_completed_sample_document(
        plan_index=5,
        sample_id="PRE-C3-L2-HIGH",
        input_sha256=INPUT_B,
        payload={"metric": 2.5, "finite": True},
    )
    if defect == "schema":
        document["unexpected"] = "forbidden"
    elif defect == "hash":
        document["payload"]["metric"] = 3.5
    elif defect == "incomplete":
        document["completion_state"] = "STARTED"

    temporary = tmp_path / f"{defect}.json.tmp"
    destination = tmp_path / f"{defect}.json"
    if defect == "nonfinite":
        temporary.write_text(
            json.dumps(document).replace('"metric": 2.5', '"metric": NaN') + "\n",
            encoding="utf-8",
        )
    else:
        write_completed_sample_temp(temporary, document)

    with pytest.raises(SampleArtifactError):
        publish_completed_sample(
            temporary,
            destination,
            expected_plan_index=5,
            expected_sample_id="PRE-C3-L2-HIGH",
            expected_input_sha256=INPUT_B,
        )
    assert temporary.is_file()
    assert not destination.exists()
    assert not published_sample_is_voting(
        destination,
        expected_plan_index=5,
        expected_sample_id="PRE-C3-L2-HIGH",
        expected_input_sha256=INPUT_B,
    )
