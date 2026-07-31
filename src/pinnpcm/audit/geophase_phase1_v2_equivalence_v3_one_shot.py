"""Single-attempt control plane for the independent equivalence-v3 audit.

This module contains orchestration and durable publication only.  Numerical
observations are supplied by an injected row executor; normalization,
record publication, A/B/C voting, and terminal reduction are delegated to the
frozen schema-corrected comparator.  No historical audit runner or historical
comparison entry point is imported.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping, Sequence
import uuid

from pinnpcm.audit import geophase_phase1_v2_equivalence_v3_comparator as _v3


TASK_ID = "Q2_PHASE1_V2_EQUIVALENCE_V3_INDEPENDENT_AUDIT"
REGISTRY_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v3_execution_registry_v1"
JOURNAL_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v3_journal_v1"
SUMMARY_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v3_summary_v1"
EXPECTED_PLAN_COUNT = 57
EXPECTED_PLAN_INDICES = tuple(range(EXPECTED_PLAN_COUNT))
EXPECTED_PLAN_INDICES_SHA256 = hashlib.sha256(
    json.dumps(EXPECTED_PLAN_INDICES, separators=(",", ":")).encode("ascii")
).hexdigest()
FAMILIES = ("electrical", "interval", "progression", "failure")
GENESIS_SHA256 = "0" * 64
_HEX64 = frozenset("0123456789abcdef")


class IndependentAuditError(RuntimeError):
    """Control-plane or durable-publication failure after no implicit retry."""


@dataclass(frozen=True)
class PlanRow:
    plan_index: int
    sample_id: str
    family: str
    grid_id: str
    input_sha256: str
    frozen_row: Mapping[str, str]


@dataclass(frozen=True)
class RowObservationPair:
    candidate_observation: Any
    oracle_observation: Any
    runtime_input_sha256: str
    candidate_validation_errors: tuple[str, ...] = ()
    oracle_validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutputPaths:
    registry: Path
    journal: Path
    normalized_records: Path
    electrical_table: Path
    interval_table: Path
    progression_table: Path
    failure_table: Path
    summary: Path

    @property
    def family_tables(self) -> Mapping[str, Path]:
        return {
            "electrical": Path(self.electrical_table),
            "interval": Path(self.interval_table),
            "progression": Path(self.progression_table),
            "failure": Path(self.failure_table),
        }


@dataclass(frozen=True)
class AuditOutcome:
    terminal_state: str
    terminal_event: str
    completed_rows: int
    first_failure: Mapping[str, Any] | None
    summary_path: Path
    final_journal_sha256: str


RowExecutor = Callable[[PlanRow], RowObservationPair]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX64


def _finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _finite_tree(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return value is None or isinstance(value, (str, int, bool))


def _fsync_directory(path: Path) -> None:
    if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_bytes(path: Path, payload: bytes, *, replace: bool) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise IndependentAuditError(f"immutable output already exists: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.read_bytes() != payload:
            raise IndependentAuditError(f"temporary publication verification failed: {path}")
        os.replace(temporary, path)
        if path.read_bytes() != payload:
            raise IndependentAuditError(f"atomic publication verification failed: {path}")
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, payload: Mapping[str, Any], *, replace: bool) -> None:
    _atomic_bytes(path, canonical_json_bytes(dict(payload)) + b"\n", replace=replace)


def _registry_sha(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("registry_sha256", None)
    return canonical_sha256(body)


def _validate_registry(payload: Any) -> dict[str, Any]:
    required = {
        "schema_version",
        "task_id",
        "attempt_id",
        "state",
        "execution_attempt_limit",
        "automatic_retry",
        "manual_retry",
        "equivalence_v2_execution_count",
        "equivalence_v3_execution_count",
        "formal_execution_count",
        "expected_plan_count",
        "expected_plan_indices_sha256",
        "plan_manifest_sha256",
        "ledger_manifest_sha256",
        "contract_bundle_sha256",
        "runner_source_sha256",
        "remote_anchor_commit",
        "started_at_utc",
        "owner_pid",
        "completed_rows",
        "terminal_state",
        "final_journal_sha256",
        "registry_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise IndependentAuditError("registry schema differs")
    if payload["schema_version"] != REGISTRY_SCHEMA_VERSION or payload["task_id"] != TASK_ID:
        raise IndependentAuditError("registry identity differs")
    if payload["execution_attempt_limit"] != 1 or payload["automatic_retry"] is not False or payload["manual_retry"] is not False:
        raise IndependentAuditError("registry retry/attempt boundary differs")
    if payload["equivalence_v2_execution_count"] != 1 or payload["formal_execution_count"] != 0:
        raise IndependentAuditError("historical/formal count drifted")
    if payload["expected_plan_count"] != 57 or payload["expected_plan_indices_sha256"] != EXPECTED_PLAN_INDICES_SHA256:
        raise IndependentAuditError("registry plan identity differs")
    for key in (
        "plan_manifest_sha256",
        "ledger_manifest_sha256",
        "contract_bundle_sha256",
        "runner_source_sha256",
        "final_journal_sha256",
    ):
        if payload[key] is not None and not _is_sha(payload[key]):
            raise IndependentAuditError(f"registry hash is invalid: {key}")
    state = payload["state"]
    count = payload["equivalence_v3_execution_count"]
    if state == "AUTHORIZED_NOT_STARTED":
        if count != 0 or payload["started_at_utc"] is not None or payload["owner_pid"] is not None or payload["completed_rows"] != 0 or payload["terminal_state"] is not None or payload["final_journal_sha256"] is not None:
            raise IndependentAuditError("not-started registry contains attempt state")
    elif state == "RUNNING":
        if count != 1 or not isinstance(payload["owner_pid"], int) or payload["started_at_utc"] is None or payload["terminal_state"] is not None:
            raise IndependentAuditError("running registry state is inconsistent")
    elif state == "TERMINAL":
        terminal = payload["terminal_state"]
        journal_identity_valid = _is_sha(payload["final_journal_sha256"])
        if terminal == "INVALID_INFRA" and payload["final_journal_sha256"] is None:
            journal_identity_valid = True
        if count != 1 or terminal not in {"PASS", "VALID_FAIL", "INVALID_INFRA"} or not journal_identity_valid:
            raise IndependentAuditError("terminal registry state is inconsistent")
    else:
        raise IndependentAuditError("registry state is unknown")
    if not isinstance(payload["completed_rows"], int) or not 0 <= payload["completed_rows"] <= 57:
        raise IndependentAuditError("registry completed_rows is invalid")
    if payload["registry_sha256"] != _registry_sha(payload):
        raise IndependentAuditError("registry hash differs")
    return dict(payload)


def build_initial_registry(
    *,
    plan_manifest_sha256: str,
    ledger_manifest_sha256: str,
    contract_bundle_sha256: str,
    runner_source_sha256: str,
    remote_anchor_commit: str,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    for value in (
        plan_manifest_sha256,
        ledger_manifest_sha256,
        contract_bundle_sha256,
        runner_source_sha256,
    ):
        if not _is_sha(value):
            raise IndependentAuditError("initial registry received an invalid SHA-256")
    if not isinstance(remote_anchor_commit, str) or len(remote_anchor_commit) != 40 or not set(remote_anchor_commit) <= _HEX64:
        raise IndependentAuditError("remote anchor commit is invalid")
    payload: dict[str, Any] = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "attempt_id": attempt_id or f"equivalence-v3-{uuid.uuid4().hex}",
        "state": "AUTHORIZED_NOT_STARTED",
        "execution_attempt_limit": 1,
        "automatic_retry": False,
        "manual_retry": False,
        "equivalence_v2_execution_count": 1,
        "equivalence_v3_execution_count": 0,
        "formal_execution_count": 0,
        "expected_plan_count": 57,
        "expected_plan_indices_sha256": EXPECTED_PLAN_INDICES_SHA256,
        "plan_manifest_sha256": plan_manifest_sha256,
        "ledger_manifest_sha256": ledger_manifest_sha256,
        "contract_bundle_sha256": contract_bundle_sha256,
        "runner_source_sha256": runner_source_sha256,
        "remote_anchor_commit": remote_anchor_commit,
        "started_at_utc": None,
        "owner_pid": None,
        "completed_rows": 0,
        "terminal_state": None,
        "final_journal_sha256": None,
        "registry_sha256": "",
    }
    payload["registry_sha256"] = _registry_sha(payload)
    return _validate_registry(payload)


def write_initial_registry(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_json(path, _validate_registry(dict(payload)), replace=False)


def load_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentAuditError("registry cannot be loaded") from exc
    return _validate_registry(payload)


def activate_registry_once(path: Path, *, expected_registry_sha256: str) -> dict[str, Any]:
    payload = load_registry(path)
    if payload["registry_sha256"] != expected_registry_sha256 or payload["state"] != "AUTHORIZED_NOT_STARTED":
        raise IndependentAuditError("registry is not the authorized unconsumed identity")
    lock = Path(path).with_suffix(Path(path).suffix + ".activation.lock")
    try:
        with lock.open("xb") as handle:
            handle.write(str(os.getpid()).encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise IndependentAuditError("attempt transition lock already exists") from exc
    try:
        payload.update(
            state="RUNNING",
            equivalence_v3_execution_count=1,
            started_at_utc=_utc_now(),
            owner_pid=os.getpid(),
        )
        payload["registry_sha256"] = _registry_sha(payload)
        _atomic_json(path, _validate_registry(payload), replace=True)
        return load_registry(path)
    finally:
        lock.unlink(missing_ok=True)


def finalise_registry(
    path: Path,
    *,
    completed_rows: int,
    terminal_state: str,
    final_journal_sha256: str | None,
) -> dict[str, Any]:
    payload = load_registry(path)
    if payload["state"] != "RUNNING" or payload["owner_pid"] != os.getpid():
        raise IndependentAuditError("only the active owner may finalise the registry")
    payload.update(
        state="TERMINAL",
        completed_rows=int(completed_rows),
        terminal_state=str(terminal_state),
        final_journal_sha256=str(final_journal_sha256),
    )
    payload["registry_sha256"] = _registry_sha(payload)
    _atomic_json(path, _validate_registry(payload), replace=True)
    return load_registry(path)


def plan_rows_from_contract(contract: _v3.LoadedContract) -> tuple[PlanRow, ...]:
    rows: list[PlanRow] = []
    for index in EXPECTED_PLAN_INDICES:
        frozen = contract.core.plan_rows.get(index)
        if frozen is None:
            raise IndependentAuditError("contract lacks the exact 0..56 plan")
        rows.append(
            PlanRow(
                plan_index=index,
                sample_id=str(frozen["sample_id"]),
                family=str(frozen["family"]),
                grid_id=str(frozen["grid"] or "L1"),
                input_sha256=str(frozen["plan_sha256"]),
                frozen_row=dict(frozen),
            )
        )
    if tuple(row.plan_index for row in rows) != EXPECTED_PLAN_INDICES:
        raise IndependentAuditError("plan order differs")
    return tuple(rows)


def _journal_hash(record: Mapping[str, Any]) -> str:
    body = dict(record)
    body.pop("record_sha256", None)
    return canonical_sha256(body)


def validate_journal(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    previous = GENESIS_SHA256
    expected_keys = {
        "schema_version",
        "sequence",
        "previous_record_sha256",
        "record_sha256",
        "event",
        "attempt_id",
        "plan_index",
        "sample_id",
        "family",
        "input_sha256",
        "runtime_input_sha256",
        "candidate_record_sha256",
        "oracle_record_sha256",
        "comparison_sha256",
        "terminal_state",
        "timestamp_utc",
        "detail",
    }
    attempt_id: str | None = None
    active_row: tuple[int, str, str, str] | None = None
    completed_indices: list[int] = []
    terminal_expected: str | None = None
    terminated = False
    try:
        lines = Path(path).read_bytes().splitlines()
    except OSError as exc:
        raise IndependentAuditError("journal cannot be read") from exc
    for sequence, raw in enumerate(lines):
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IndependentAuditError("journal record is not valid JSON") from exc
        if (
            not isinstance(record, dict)
            or set(record) != expected_keys
            or record.get("schema_version") != JOURNAL_SCHEMA_VERSION
            or record.get("sequence") != sequence
            or record.get("previous_record_sha256") != previous
            or record.get("record_sha256") != _journal_hash(record)
        ):
            raise IndependentAuditError("journal hash chain differs")
        if not _finite_tree(record):
            raise IndependentAuditError("journal contains nonfinite content")
        if terminated:
            raise IndependentAuditError("journal contains records after its terminal event")
        if not isinstance(record["attempt_id"], str) or not record["attempt_id"]:
            raise IndependentAuditError("journal attempt identity is invalid")
        if attempt_id is None:
            attempt_id = record["attempt_id"]
        elif record["attempt_id"] != attempt_id:
            raise IndependentAuditError("journal attempt identity changed")

        event = record["event"]
        row_identity = (
            record["plan_index"],
            record["sample_id"],
            record["family"],
            record["input_sha256"],
        )
        if event == "ATTEMPT_STARTED":
            if sequence != 0 or active_row is not None or completed_indices:
                raise IndependentAuditError("attempt-start event is not first")
            if any(value is not None for value in row_identity) or any(
                record[key] is not None
                for key in (
                    "runtime_input_sha256",
                    "candidate_record_sha256",
                    "oracle_record_sha256",
                    "comparison_sha256",
                    "terminal_state",
                )
            ):
                raise IndependentAuditError("attempt-start event contains row state")
        elif event == "ROW_STARTED":
            if sequence == 0 or active_row is not None or terminal_expected is not None:
                raise IndependentAuditError("row-start event is out of sequence")
            expected_index = len(completed_indices)
            if (
                row_identity[0] != expected_index
                or not isinstance(row_identity[1], str)
                or not row_identity[1]
                or row_identity[2] not in FAMILIES
                or not _is_sha(row_identity[3])
            ):
                raise IndependentAuditError("row-start identity differs from exact plan order")
            if any(
                record[key] is not None
                for key in (
                    "runtime_input_sha256",
                    "candidate_record_sha256",
                    "oracle_record_sha256",
                    "comparison_sha256",
                    "terminal_state",
                )
            ):
                raise IndependentAuditError("row-start event contains completed-row state")
            active_row = row_identity
        elif event == "ROW_COMPLETED":
            if active_row is None or row_identity != active_row or terminal_expected is not None:
                raise IndependentAuditError("row-completed identity differs from active row")
            if not _is_sha(record["runtime_input_sha256"]):
                raise IndependentAuditError("row-completed runtime input identity is invalid")
            if not all(
                _is_sha(record[key])
                for key in (
                    "candidate_record_sha256",
                    "oracle_record_sha256",
                    "comparison_sha256",
                )
            ):
                raise IndependentAuditError("row-completed record identity is invalid")
            if record["terminal_state"] not in {None, "VALID_FAIL"}:
                raise IndependentAuditError("row-completed terminal state is invalid")
            completed_indices.append(int(row_identity[0]))
            active_row = None
            if record["terminal_state"] == "VALID_FAIL":
                terminal_expected = "VALID_FAIL"
        elif event == "ROW_INFRA_FAILURE":
            if active_row is None or row_identity != active_row or terminal_expected is not None:
                raise IndependentAuditError("row-infra identity differs from active row")
            runtime_sha = record["runtime_input_sha256"]
            if runtime_sha is not None and not _is_sha(runtime_sha):
                raise IndependentAuditError("row-infra runtime input identity is invalid")
            published_hashes = tuple(
                record[key]
                for key in (
                    "candidate_record_sha256",
                    "oracle_record_sha256",
                    "comparison_sha256",
                )
            )
            if any(value is not None and not _is_sha(value) for value in published_hashes):
                raise IndependentAuditError("row-infra published record identity is invalid")
            if any(value is not None for value in published_hashes) and not _is_sha(runtime_sha):
                raise IndependentAuditError("published row-infra records lack runtime input identity")
            if record["comparison_sha256"] is not None and (
                record["candidate_record_sha256"] is None
                or record["oracle_record_sha256"] is None
            ):
                raise IndependentAuditError("row-infra comparison lacks both published records")
            if record["terminal_state"] != "INVALID_INFRA":
                raise IndependentAuditError("row-infra terminal state is invalid")
            active_row = None
            terminal_expected = "INVALID_INFRA"
        elif event == "ATTEMPT_INFRA_FAILURE":
            if active_row is not None or terminal_expected is not None:
                raise IndependentAuditError("attempt-infra event is out of sequence")
            if any(value is not None for value in row_identity) or any(
                record[key] is not None
                for key in (
                    "runtime_input_sha256",
                    "candidate_record_sha256",
                    "oracle_record_sha256",
                    "comparison_sha256",
                )
            ):
                raise IndependentAuditError("attempt-infra event contains row state")
            if record["terminal_state"] != "INVALID_INFRA":
                raise IndependentAuditError("attempt-infra terminal state is invalid")
            terminal_expected = "INVALID_INFRA"
        elif event == "ATTEMPT_TERMINATED":
            if active_row is not None or sequence == 0:
                raise IndependentAuditError("attempt terminated with an active row")
            terminal = record["terminal_state"]
            if terminal not in {"PASS", "VALID_FAIL", "INVALID_INFRA"}:
                raise IndependentAuditError("attempt terminal state is invalid")
            if terminal_expected is not None and terminal != terminal_expected:
                raise IndependentAuditError("attempt terminal state contradicts row outcome")
            if terminal_expected is None:
                if terminal != "PASS" or completed_indices != list(EXPECTED_PLAN_INDICES):
                    raise IndependentAuditError("PASS lacks 57 explicit ordered rows")
            if any(value is not None for value in row_identity) or any(
                record[key] is not None
                for key in (
                    "runtime_input_sha256",
                    "candidate_record_sha256",
                    "oracle_record_sha256",
                    "comparison_sha256",
                )
            ):
                raise IndependentAuditError("attempt-terminal event contains row state")
            detail = record["detail"]
            if not isinstance(detail, dict) or detail.get("completed_rows") != len(completed_indices):
                raise IndependentAuditError("attempt terminal completed-row count differs")
            terminated = True
        else:
            raise IndependentAuditError("journal event is unknown")
        previous = record["record_sha256"]
        records.append(record)
    return tuple(records)


class AuditHashChainJournal:
    def __init__(self, path: Path, *, attempt_id: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise IndependentAuditError("journal already exists; retry/resume is forbidden")
        _atomic_bytes(self.path, b"", replace=False)
        self.attempt_id = attempt_id
        self.sequence = 0
        self.previous = GENESIS_SHA256
        self.owner_pid = os.getpid()
        self.lock = Lock()

    @property
    def final_record_sha256(self) -> str:
        return self.previous

    def append(
        self,
        event: str,
        *,
        row: PlanRow | None = None,
        runtime_input_sha256: str | None = None,
        candidate_record_sha256: str | None = None,
        oracle_record_sha256: str | None = None,
        comparison_sha256: str | None = None,
        terminal_state: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if os.getpid() != self.owner_pid:
            raise IndependentAuditError("journal has more than one process writer")
        with self.lock:
            disk = validate_journal(self.path)
            if len(disk) != self.sequence or (disk[-1]["record_sha256"] if disk else GENESIS_SHA256) != self.previous:
                raise IndependentAuditError("journal changed outside its writer")
            record: dict[str, Any] = {
                "schema_version": JOURNAL_SCHEMA_VERSION,
                "sequence": self.sequence,
                "previous_record_sha256": self.previous,
                "record_sha256": "",
                "event": str(event),
                "attempt_id": self.attempt_id,
                "plan_index": None if row is None else row.plan_index,
                "sample_id": None if row is None else row.sample_id,
                "family": None if row is None else row.family,
                "input_sha256": None if row is None else row.input_sha256,
                "runtime_input_sha256": runtime_input_sha256,
                "candidate_record_sha256": candidate_record_sha256,
                "oracle_record_sha256": oracle_record_sha256,
                "comparison_sha256": comparison_sha256,
                "terminal_state": terminal_state,
                "timestamp_utc": _utc_now(),
                "detail": dict(detail or {}),
            }
            record["record_sha256"] = _journal_hash(record)
            prior = self.path.read_bytes()
            _atomic_bytes(
                self.path,
                prior + canonical_json_bytes(record) + b"\n",
                replace=True,
            )
            verified = validate_journal(self.path)
            if len(verified) != self.sequence + 1 or verified[-1] != record:
                raise IndependentAuditError("journal append verification failed")
            self.sequence += 1
            self.previous = record["record_sha256"]
            return record


_TABLE_FIELDS = (
    "plan_index",
    "sample_id",
    "partition_label",
    "family",
    "input_sha256",
    "runtime_input_sha256",
    "candidate_record_sha256",
    "oracle_record_sha256",
    "comparison_sha256",
    "row_pass",
    "terminal_state",
    "failure_stage",
    "failure_category",
    "failed_fields",
    "failed_categories",
    "issues",
)


def _partition(index: int) -> str:
    return "metric-development" if index <= 11 else "held-out"


def _table_row(
    row: PlanRow, runtime_input_sha256: str, comparison: Mapping[str, Any]
) -> dict[str, Any]:
    failed = [
        vote
        for vote in comparison.get("votes", ())
        if isinstance(vote, Mapping) and vote.get("passed") is False
    ]
    return {
        "plan_index": row.plan_index,
        "sample_id": row.sample_id,
        "partition_label": _partition(row.plan_index),
        "family": row.family,
        "input_sha256": row.input_sha256,
        "runtime_input_sha256": runtime_input_sha256,
        "candidate_record_sha256": comparison.get("candidate_record_sha256"),
        "oracle_record_sha256": comparison.get("oracle_record_sha256"),
        "comparison_sha256": comparison.get("comparison_sha256"),
        "row_pass": comparison.get("row_pass") is True,
        "terminal_state": comparison.get("terminal_state"),
        "failure_stage": comparison.get("failure_stage"),
        "failure_category": comparison.get("failure_category"),
        "failed_fields": json.dumps(sorted({str(vote.get("field")) for vote in failed}), separators=(",", ":")),
        "failed_categories": json.dumps(sorted({str(vote.get("category")) for vote in failed}), separators=(",", ":")),
        "issues": json.dumps(comparison.get("issues", []), sort_keys=True, separators=(",", ":")),
    }


def _publish_tables(rows: Sequence[Mapping[str, Any]], paths: Mapping[str, Path]) -> None:
    if set(paths) != set(FAMILIES):
        raise IndependentAuditError("family table map differs")
    for family in FAMILIES:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=_TABLE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            if row["family"] == family:
                writer.writerow({key: row[key] for key in _TABLE_FIELDS})
        _atomic_bytes(Path(paths[family]), stream.getvalue().encode("utf-8"), replace=True)


def _first_failure(row: PlanRow, comparison: Mapping[str, Any]) -> dict[str, Any]:
    failed = [vote for vote in comparison.get("votes", ()) if isinstance(vote, Mapping) and vote.get("passed") is False]
    vote = failed[0] if failed else {}
    return {
        "plan_index": row.plan_index,
        "sample_id": row.sample_id,
        "stage": comparison.get("failure_stage"),
        "field": vote.get("field"),
        "category": vote.get("category") or comparison.get("failure_category"),
        "issues": comparison.get("issues", []),
    }


def _summary(
    *,
    registry: Mapping[str, Any],
    terminal_state: str,
    rows: Sequence[Mapping[str, Any]],
    first_failure: Mapping[str, Any] | None,
    journal: Path,
    family_tables: Mapping[str, Path],
) -> dict[str, Any]:
    completed = len(rows)
    passed = sum(row["row_pass"] is True for row in rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "attempt_id": registry["attempt_id"],
        "terminal_state": terminal_state,
        "strict_equivalence_v1": {"disposition": "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR", "completed_rows": 12, "expected_rows": 57},
        "historical_equivalence_v2": {"terminal_state": "VALID_FAIL", "completed_rows": 10, "expected_rows": 57, "execution_count": 1},
        "equivalence_v3_execution_count": 1,
        "completed_rows": completed,
        "passed_rows": passed,
        "failed_rows": completed - passed,
        "unassessed_plan_indices": list(range(completed, 57)),
        "first_failure": None if first_failure is None else dict(first_failure),
        "implementation_equivalence": "supported_under_superseding_schema_corrected_contract" if terminal_state == "PASS" else "not_supported",
        "S2_physics_claim_status": "forbidden_unassessed",
        "Phase1_PINN_claim_status": "forbidden_unassessed",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "journal_file_sha256": sha256_path(journal),
        "journal_final_record_sha256": validate_journal(journal)[-1]["record_sha256"],
        "family_table_sha256": {family: sha256_path(path) for family, path in sorted(family_tables.items())},
    }


def _publish_terminal(
    *,
    registry: Mapping[str, Any],
    paths: OutputPaths,
    journal: AuditHashChainJournal,
    table_rows: Sequence[Mapping[str, Any]],
    terminal_state: str,
    first_failure: Mapping[str, Any] | None,
) -> AuditOutcome:
    terminal_event = (
        "COMPLETE_PASS"
        if terminal_state == "PASS"
        else (
            "VALID_RECORD_OR_FIELD_FAILURE"
            if terminal_state == "VALID_FAIL"
            else "EXECUTION_INTEGRITY_FAILURE"
        )
    )
    journal.append(
        "ATTEMPT_TERMINATED",
        terminal_state=terminal_state,
        detail={"completed_rows": len(table_rows), "terminal_event": terminal_event},
    )
    _publish_tables(table_rows, paths.family_tables)
    summary = _summary(
        registry=registry,
        terminal_state=terminal_state,
        rows=table_rows,
        first_failure=first_failure,
        journal=paths.journal,
        family_tables=paths.family_tables,
    )
    _atomic_json(paths.summary, summary, replace=False)
    finalise_registry(
        paths.registry,
        completed_rows=len(table_rows),
        terminal_state=terminal_state,
        final_journal_sha256=journal.final_record_sha256,
    )
    return AuditOutcome(
        terminal_state=terminal_state,
        terminal_event=terminal_event,
        completed_rows=len(table_rows),
        first_failure=first_failure,
        summary_path=Path(paths.summary),
        final_journal_sha256=journal.final_record_sha256,
    )


def run_independent_audit(
    *,
    contract: _v3.LoadedContract,
    row_executor: RowExecutor,
    paths: OutputPaths,
    expected_registry_sha256: str,
) -> AuditOutcome:
    """Consume the sole v3 attempt and execute rows in exact order, fail-fast."""

    rows = plan_rows_from_contract(contract)
    for path in (paths.journal, paths.summary, *paths.family_tables.values()):
        if Path(path).exists():
            raise IndependentAuditError(f"result path already exists: {path}")
    registry = activate_registry_once(
        paths.registry, expected_registry_sha256=expected_registry_sha256
    )
    try:
        journal = AuditHashChainJournal(paths.journal, attempt_id=registry["attempt_id"])
    except Exception:
        # The 0->1 transition has already consumed the sole attempt.  When the
        # journal itself cannot be created there is, by definition, no durable
        # journal hash to cite; preserve that fact explicitly in the registry.
        finalise_registry(
            paths.registry,
            completed_rows=0,
            terminal_state="INVALID_INFRA",
            final_journal_sha256=None,
        )
        raise
    table_rows: list[Mapping[str, Any]] = []
    comparisons: list[Mapping[str, Any]] = []
    active_row: PlanRow | None = None
    active_runtime_input_sha256: str | None = None
    active_candidate_record_sha256: str | None = None
    active_oracle_record_sha256: str | None = None
    active_comparison_sha256: str | None = None
    terminal_publication_started = False
    journal.append("ATTEMPT_STARTED", detail={"owner_pid": os.getpid()})
    try:
        for row in rows:
            active_row = row
            active_runtime_input_sha256 = None
            active_candidate_record_sha256 = None
            active_oracle_record_sha256 = None
            active_comparison_sha256 = None
            journal.append("ROW_STARTED", row=row)
            pair = row_executor(row)
            if not isinstance(pair, RowObservationPair):
                # A structurally identical adapter dataclass is accepted without
                # importing it, but all fields remain mandatory.
                required = {
                    "candidate_observation",
                    "oracle_observation",
                    "runtime_input_sha256",
                    "candidate_validation_errors",
                    "oracle_validation_errors",
                }
                if not all(hasattr(pair, name) for name in required):
                    raise IndependentAuditError("row executor result schema differs")
            runtime_sha = str(pair.runtime_input_sha256)
            if not _is_sha(runtime_sha):
                raise IndependentAuditError("runtime input SHA-256 is invalid")
            active_runtime_input_sha256 = runtime_sha
            candidate = _v3.observation_to_record(
                pair.candidate_observation,
                plan_index=row.plan_index,
                input_sha256=row.input_sha256,
                contract=contract,
                runtime_input_sha256=runtime_sha,
                validation_errors=tuple(pair.candidate_validation_errors),
            )
            oracle = _v3.observation_to_record(
                pair.oracle_observation,
                plan_index=row.plan_index,
                input_sha256=row.input_sha256,
                contract=contract,
                runtime_input_sha256=runtime_sha,
                validation_errors=tuple(pair.oracle_validation_errors),
            )
            candidate_path, candidate_sha = _v3.publish_normalized_record(candidate, paths.normalized_records, side="candidate")
            active_candidate_record_sha256 = candidate_sha
            oracle_path, oracle_sha = _v3.publish_normalized_record(oracle, paths.normalized_records, side="oracle")
            active_oracle_record_sha256 = oracle_sha
            candidate_loaded = _v3.load_normalized_record(candidate_path, expected_sha256=candidate_sha)
            oracle_loaded = _v3.load_normalized_record(oracle_path, expected_sha256=oracle_sha)
            comparison = _v3.compare_record_pair(candidate_loaded, oracle_loaded, contract)
            active_comparison_sha256 = str(comparison.get("comparison_sha256"))
            if comparison.get("candidate_record_sha256") != candidate_sha or comparison.get("oracle_record_sha256") != oracle_sha:
                raise IndependentAuditError("comparison does not reference published records")
            terminal = str(comparison.get("terminal_state"))
            if terminal == "INVALID_INFRA":
                journal.append(
                    "ROW_INFRA_FAILURE",
                    row=row,
                    runtime_input_sha256=runtime_sha,
                    candidate_record_sha256=candidate_sha,
                    oracle_record_sha256=oracle_sha,
                    comparison_sha256=str(comparison.get("comparison_sha256")),
                    terminal_state="INVALID_INFRA",
                    detail={
                        "failure_stage": comparison.get("failure_stage"),
                        "failure_category": comparison.get("failure_category"),
                    },
                )
                active_row = None
                terminal_publication_started = True
                return _publish_terminal(
                    registry=registry,
                    paths=paths,
                    journal=journal,
                    table_rows=table_rows,
                    terminal_state="INVALID_INFRA",
                    first_failure=_first_failure(row, comparison),
                )
            table = _table_row(row, runtime_sha, comparison)
            comparisons.append(comparison)
            table_rows.append(table)
            _publish_tables(table_rows, paths.family_tables)
            journal.append(
                "ROW_COMPLETED",
                row=row,
                runtime_input_sha256=runtime_sha,
                candidate_record_sha256=candidate_sha,
                oracle_record_sha256=oracle_sha,
                comparison_sha256=str(comparison.get("comparison_sha256")),
                terminal_state=None if terminal == "PASS" else terminal,
                detail={"row_pass": comparison.get("row_pass") is True},
            )
            active_row = None
            active_runtime_input_sha256 = None
            active_candidate_record_sha256 = None
            active_oracle_record_sha256 = None
            active_comparison_sha256 = None
            if terminal != "PASS":
                if terminal != "VALID_FAIL":
                    raise IndependentAuditError("comparator emitted an unknown terminal")
                terminal_publication_started = True
                return _publish_terminal(
                    registry=registry,
                    paths=paths,
                    journal=journal,
                    table_rows=table_rows,
                    terminal_state=terminal,
                    first_failure=_first_failure(row, comparison),
                )
        terminal = _v3.finalise_plan_terminal(comparisons, contract).value
        if terminal != "PASS" or len(comparisons) != 57:
            raise IndependentAuditError("57 explicit rows did not reduce to exact PASS")
        terminal_publication_started = True
        return _publish_terminal(
            registry=registry,
            paths=paths,
            journal=journal,
            table_rows=table_rows,
            terminal_state="PASS",
            first_failure=None,
        )
    except Exception as exc:
        if terminal_publication_started:
            # Never append a second terminal record or attempt a second result
            # publication after terminal publication itself has failed.
            raise IndependentAuditError(
                "terminal publication failed after the non-retryable attempt was consumed"
            ) from exc
        failed = active_row
        journal.append(
            "ROW_INFRA_FAILURE" if failed is not None else "ATTEMPT_INFRA_FAILURE",
            row=failed,
            runtime_input_sha256=(
                active_runtime_input_sha256 if failed is not None else None
            ),
            candidate_record_sha256=(
                active_candidate_record_sha256 if failed is not None else None
            ),
            oracle_record_sha256=(
                active_oracle_record_sha256 if failed is not None else None
            ),
            comparison_sha256=(
                active_comparison_sha256 if failed is not None else None
            ),
            terminal_state="INVALID_INFRA",
            detail={"error_class": type(exc).__name__, "message": str(exc)},
        )
        terminal_publication_started = True
        return _publish_terminal(
            registry=registry,
            paths=paths,
            journal=journal,
            table_rows=table_rows,
            terminal_state="INVALID_INFRA",
            first_failure={
                "plan_index": None if failed is None else failed.plan_index,
                "sample_id": None if failed is None else failed.sample_id,
                "stage": "execution_integrity",
                "field": None,
                "category": type(exc).__name__,
                "issues": [str(exc)],
            },
        )
__all__ = [
    "AuditHashChainJournal",
    "AuditOutcome",
    "EXPECTED_PLAN_COUNT",
    "EXPECTED_PLAN_INDICES",
    "IndependentAuditError",
    "OutputPaths",
    "PlanRow",
    "REGISTRY_SCHEMA_VERSION",
    "RowObservationPair",
    "TASK_ID",
    "activate_registry_once",
    "build_initial_registry",
    "canonical_sha256",
    "finalise_registry",
    "load_registry",
    "plan_rows_from_contract",
    "run_independent_audit",
    "sha256_path",
    "validate_journal",
    "write_initial_registry",
]
