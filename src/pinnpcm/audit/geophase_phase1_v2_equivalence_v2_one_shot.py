"""Control plane for the single authorised equivalence-v2 audit attempt.

This module contains no scientific row implementation.  A caller injects one
production row executor which returns candidate/oracle observations; this
control plane binds those observations to the frozen 57-row plan and delegates
all record construction and A/B/C voting to comparator closure v3.

The module deliberately owns the irreversible execution mechanics: a durable
registry transition from zero to one, exact plan order, no retry, fail-fast,
an append-only hash-chain journal, and atomically published result snapshots.
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
import re
from threading import Lock
from typing import Any, Callable, Mapping, Sequence
import uuid

from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_v2_comparator_v3 as _closure_v3,
)


TASK_ID = "Q2_PHASE1_V2_EQUIVALENCE_V2_ONE_SHOT_AUDIT"
REGISTRY_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v2_execution_registry_v1"
JOURNAL_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v2_audit_journal_v1"
SUMMARY_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v2_summary_v1"
EXPECTED_PLAN_COUNT = 57
EXPECTED_PLAN_INDICES = tuple(range(EXPECTED_PLAN_COUNT))
EXPECTED_PLAN_INDICES_SHA256 = (
    "b8407db67660b6b982b3f3458c694bc62f2bdeade733d25279acdcf476a7e1b4"
)
GENESIS_SHA256 = "0" * 64
FAMILIES = ("electrical", "interval", "progression", "failure")
PARTITION_BY_INDEX = {
    index: "metric-development" if index <= 11 else "held-out"
    for index in EXPECTED_PLAN_INDICES
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_REGISTRY_STATES = frozenset({"AUTHORIZED_NOT_STARTED", "RUNNING", "TERMINAL"})
_TERMINAL_STATES = frozenset({"PASS", "VALID_FAIL", "INVALID_INFRA"})
_JOURNAL_EVENTS = frozenset(
    {
        "ATTEMPT_STARTED",
        "ROW_STARTED",
        "ROW_COMPLETED",
        "ROW_INFRA_FAILURE",
        "ATTEMPT_TERMINATED",
    }
)
_REGISTRY_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "attempt_id",
        "state",
        "execution_attempt_limit",
        "equivalence_v2_execution_count",
        "formal_execution_count",
        "automatic_retry",
        "manual_retry",
        "expected_plan_count",
        "expected_plan_indices_sha256",
        "plan_manifest_sha256",
        "contract_bundle_sha256",
        "runner_source_sha256",
        "remote_anchor_commit",
        "started_at_utc",
        "owner_pid",
        "completed_rows",
        "terminal_state",
        "terminal_event",
        "final_journal_sha256",
        "registry_sha256",
    }
)
_JOURNAL_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "previous_record_sha256",
        "record_sha256",
        "event",
        "attempt_id",
        "plan_index",
        "sample_id",
        "family",
        "partition_label",
        "timestamp_utc",
        "input_sha256",
        "candidate_record_sha256",
        "oracle_record_sha256",
        "comparison_sha256",
        "row_pass",
        "terminal_state",
        "failure_event",
        "detail",
    }
)
_TABLE_FIELDS = (
    "plan_index",
    "sample_id",
    "partition_label",
    "family",
    "input_sha256",
    "candidate_record_sha256",
    "oracle_record_sha256",
    "comparison_sha256",
    "row_pass",
    "failure_event",
    "failed_fields",
    "failed_categories",
    "issues",
)


class OneShotExecutionError(RuntimeError):
    """Raised for control-plane or immutable execution-integrity failures."""


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
    candidate_validation_errors: tuple[str, ...] = ()
    oracle_validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutputPaths:
    registry: Path
    journal: Path
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


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OneShotExecutionError("payload is not canonical finite JSON") from exc
    return payload.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise OneShotExecutionError(f"cannot hash {path}") from exc


def _require_sha256(value: Any, field: str, *, allow_none: bool = False) -> None:
    if allow_none and value is None:
        return
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise OneShotExecutionError(f"{field} must be a lowercase SHA-256")


def _require_utc(value: Any, field: str, *, allow_none: bool = False) -> None:
    if allow_none and value is None:
        return
    if not isinstance(value, str):
        raise OneShotExecutionError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise OneShotExecutionError(f"{field} is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise OneShotExecutionError(f"{field} must have an explicit UTC offset")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite_tree(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _finite_tree(item)
            for key, item in value.items()
        )
    return False


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_replace_bytes(path: Path, payload: bytes, *, allow_replace: bool) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not allow_replace:
        raise OneShotExecutionError(f"immutable output already exists: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.read_bytes() != payload:
            raise OneShotExecutionError(f"temporary write verification failed: {path}")
        os.replace(temporary, path)
        with path.open("r+b") as handle:
            if handle.read() != payload:
                raise OneShotExecutionError(f"published write verification failed: {path}")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: Mapping[str, Any], *, allow_replace: bool) -> None:
    _atomic_replace_bytes(
        Path(path), _canonical_json_bytes(dict(payload)) + b"\n", allow_replace=allow_replace
    )


def _registry_hash(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("registry_sha256", None)
    return canonical_sha256(body)


def _validate_registry(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or frozenset(payload) != _REGISTRY_FIELDS:
        raise OneShotExecutionError("execution registry schema differs")
    if payload["schema_version"] != REGISTRY_SCHEMA_VERSION or payload["task_id"] != TASK_ID:
        raise OneShotExecutionError("execution registry identity differs")
    if payload["state"] not in _REGISTRY_STATES:
        raise OneShotExecutionError("execution registry state is invalid")
    if payload["execution_attempt_limit"] != 1:
        raise OneShotExecutionError("execution attempt limit is not one")
    if payload["automatic_retry"] is not False or payload["manual_retry"] is not False:
        raise OneShotExecutionError("retry is not frozen off")
    if payload["expected_plan_count"] != EXPECTED_PLAN_COUNT:
        raise OneShotExecutionError("registry plan cardinality differs")
    if payload["expected_plan_indices_sha256"] != EXPECTED_PLAN_INDICES_SHA256:
        raise OneShotExecutionError("registry plan-index identity differs")
    for key in (
        "plan_manifest_sha256",
        "contract_bundle_sha256",
        "runner_source_sha256",
        "registry_sha256",
    ):
        _require_sha256(payload[key], key)
    if (
        not isinstance(payload["remote_anchor_commit"], str)
        or _GIT_COMMIT_RE.fullmatch(payload["remote_anchor_commit"]) is None
    ):
        raise OneShotExecutionError("remote_anchor_commit must be a 40-hex Git commit")
    _require_sha256(payload["final_journal_sha256"], "final_journal_sha256", allow_none=True)
    if payload["registry_sha256"] != _registry_hash(payload):
        raise OneShotExecutionError("execution registry hash differs")
    if payload["formal_execution_count"] != 0:
        raise OneShotExecutionError("formal_execution_count changed")
    if payload["equivalence_v2_execution_count"] not in {0, 1}:
        raise OneShotExecutionError("equivalence execution count is invalid")
    if not isinstance(payload["completed_rows"], int) or not 0 <= payload["completed_rows"] <= 57:
        raise OneShotExecutionError("completed row count is invalid")
    _require_utc(payload["started_at_utc"], "started_at_utc", allow_none=True)
    state = payload["state"]
    if state == "AUTHORIZED_NOT_STARTED":
        if any(
            (
                payload["equivalence_v2_execution_count"] != 0,
                payload["started_at_utc"] is not None,
                payload["owner_pid"] is not None,
                payload["completed_rows"] != 0,
                payload["terminal_state"] is not None,
                payload["terminal_event"] is not None,
                payload["final_journal_sha256"] is not None,
            )
        ):
            raise OneShotExecutionError("not-started registry contains execution state")
    elif state == "RUNNING":
        if (
            payload["equivalence_v2_execution_count"] != 1
            or payload["started_at_utc"] is None
            or not isinstance(payload["owner_pid"], int)
            or payload["owner_pid"] <= 0
            or payload["terminal_state"] is not None
            or payload["terminal_event"] is not None
            or payload["final_journal_sha256"] is not None
        ):
            raise OneShotExecutionError("running registry is inconsistent")
    else:
        if (
            payload["equivalence_v2_execution_count"] != 1
            or payload["terminal_state"] not in _TERMINAL_STATES
            or not isinstance(payload["terminal_event"], str)
            or not payload["terminal_event"]
            or payload["final_journal_sha256"] is None
        ):
            raise OneShotExecutionError("terminal registry is inconsistent")
    return dict(payload)


def load_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OneShotExecutionError("execution registry is unreadable") from exc
    return _validate_registry(payload)


def build_initial_registry(
    *,
    attempt_id: str,
    plan_manifest_sha256: str,
    contract_bundle_sha256: str,
    runner_source_sha256: str,
    remote_anchor_commit: str,
) -> dict[str, Any]:
    if not isinstance(attempt_id, str) or not attempt_id.strip() or attempt_id != attempt_id.strip():
        raise OneShotExecutionError("attempt_id must be a normalized nonempty string")
    payload: dict[str, Any] = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "attempt_id": attempt_id,
        "state": "AUTHORIZED_NOT_STARTED",
        "execution_attempt_limit": 1,
        "equivalence_v2_execution_count": 0,
        "formal_execution_count": 0,
        "automatic_retry": False,
        "manual_retry": False,
        "expected_plan_count": EXPECTED_PLAN_COUNT,
        "expected_plan_indices_sha256": EXPECTED_PLAN_INDICES_SHA256,
        "plan_manifest_sha256": plan_manifest_sha256,
        "contract_bundle_sha256": contract_bundle_sha256,
        "runner_source_sha256": runner_source_sha256,
        "remote_anchor_commit": remote_anchor_commit,
        "started_at_utc": None,
        "owner_pid": None,
        "completed_rows": 0,
        "terminal_state": None,
        "terminal_event": None,
        "final_journal_sha256": None,
        "registry_sha256": "",
    }
    for key in (
        "plan_manifest_sha256",
        "contract_bundle_sha256",
        "runner_source_sha256",
    ):
        _require_sha256(payload[key], key)
    if _GIT_COMMIT_RE.fullmatch(remote_anchor_commit) is None:
        raise OneShotExecutionError("remote_anchor_commit must be a 40-hex Git commit")
    payload["registry_sha256"] = _registry_hash(payload)
    return _validate_registry(payload)


def write_initial_registry(path: Path, payload: Mapping[str, Any]) -> None:
    validated = _validate_registry(dict(payload))
    if validated["state"] != "AUTHORIZED_NOT_STARTED":
        raise OneShotExecutionError("only a not-started registry may be initially written")
    _atomic_write_json(Path(path), validated, allow_replace=False)


def _registry_lock(path: Path) -> Path:
    return Path(path).with_name(f".{Path(path).name}.transition.lock")


def _acquire_transition_lock(path: Path) -> Path:
    lock_path = _registry_lock(path)
    try:
        with lock_path.open("xb") as handle:
            handle.write(f"{os.getpid()}\n".encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise OneShotExecutionError("another registry transition is active") from exc
    return lock_path


def activate_registry_once(path: Path, *, expected_registry_sha256: str) -> dict[str, Any]:
    """Atomically consume the sole attempt immediately before row zero."""

    _require_sha256(expected_registry_sha256, "expected_registry_sha256")
    lock_path = _acquire_transition_lock(path)
    try:
        payload = load_registry(path)
        if payload["registry_sha256"] != expected_registry_sha256:
            raise OneShotExecutionError("not-started registry identity drifted")
        if payload["state"] != "AUTHORIZED_NOT_STARTED" or payload[
            "equivalence_v2_execution_count"
        ] != 0:
            raise OneShotExecutionError("one-shot execution attempt is already consumed")
        payload.update(
            {
                "state": "RUNNING",
                "equivalence_v2_execution_count": 1,
                "started_at_utc": _utc_now(),
                "owner_pid": os.getpid(),
            }
        )
        payload["registry_sha256"] = _registry_hash(payload)
        validated = _validate_registry(payload)
        _atomic_write_json(Path(path), validated, allow_replace=True)
        return load_registry(path)
    finally:
        if lock_path.exists():
            lock_path.unlink()


def finalise_registry(
    path: Path,
    *,
    completed_rows: int,
    terminal_state: str,
    terminal_event: str,
    final_journal_sha256: str,
) -> dict[str, Any]:
    if terminal_state not in _TERMINAL_STATES:
        raise OneShotExecutionError("unknown terminal state")
    _require_sha256(final_journal_sha256, "final_journal_sha256")
    lock_path = _acquire_transition_lock(path)
    try:
        payload = load_registry(path)
        if payload["state"] != "RUNNING" or payload["owner_pid"] != os.getpid():
            raise OneShotExecutionError("only the active one-shot process may finalise")
        payload.update(
            {
                "state": "TERMINAL",
                "completed_rows": int(completed_rows),
                "terminal_state": terminal_state,
                "terminal_event": str(terminal_event),
                "final_journal_sha256": final_journal_sha256,
            }
        )
        payload["registry_sha256"] = _registry_hash(payload)
        validated = _validate_registry(payload)
        _atomic_write_json(Path(path), validated, allow_replace=True)
        return load_registry(path)
    finally:
        if lock_path.exists():
            lock_path.unlink()


def plan_rows_from_contract(contract: _closure_v3.V3LoadedContract) -> tuple[PlanRow, ...]:
    if tuple(sorted(contract.plan_rows)) != EXPECTED_PLAN_INDICES:
        raise OneShotExecutionError("frozen plan is not exactly 0..56")
    rows: list[PlanRow] = []
    seen_samples: set[str] = set()
    for index in EXPECTED_PLAN_INDICES:
        frozen = contract.plan_rows[index]
        family = str(frozen["family"])
        sample_id = str(frozen["sample_id"])
        input_sha256 = str(frozen["plan_sha256"])
        if family not in FAMILIES:
            raise OneShotExecutionError(f"plan row {index} has an unknown family")
        if not sample_id or sample_id in seen_samples:
            raise OneShotExecutionError("plan sample IDs are empty or duplicated")
        _require_sha256(input_sha256, f"plan[{index}].input_sha256")
        seen_samples.add(sample_id)
        rows.append(
            PlanRow(
                plan_index=index,
                sample_id=sample_id,
                family=family,
                grid_id=str(frozen["grid"] or "L1"),
                input_sha256=input_sha256,
                frozen_row=dict(frozen),
            )
        )
    if canonical_sha256([row.plan_index for row in rows]) != EXPECTED_PLAN_INDICES_SHA256:
        raise OneShotExecutionError("ordered plan index hash differs")
    return tuple(rows)


def _journal_record_hash(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("record_sha256", None)
    return canonical_sha256(payload)


def _validate_journal_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict) or frozenset(record) != _JOURNAL_FIELDS:
        raise OneShotExecutionError("journal record schema differs")
    if record["schema_version"] != JOURNAL_SCHEMA_VERSION:
        raise OneShotExecutionError("journal record version differs")
    if record["event"] not in _JOURNAL_EVENTS:
        raise OneShotExecutionError("journal event is unregistered")
    if not isinstance(record["sequence"], int) or record["sequence"] < 0:
        raise OneShotExecutionError("journal sequence is invalid")
    for key in (
        "previous_record_sha256",
        "record_sha256",
    ):
        _require_sha256(record[key], key)
    for key in (
        "input_sha256",
        "candidate_record_sha256",
        "oracle_record_sha256",
        "comparison_sha256",
    ):
        _require_sha256(record[key], key, allow_none=True)
    _require_utc(record["timestamp_utc"], "timestamp_utc")
    if record["record_sha256"] != _journal_record_hash(record):
        raise OneShotExecutionError("journal record hash differs")
    if record["terminal_state"] is not None and record["terminal_state"] not in _TERMINAL_STATES:
        raise OneShotExecutionError("journal terminal state is invalid")
    if not isinstance(record["detail"], dict) or not _finite_tree(record["detail"]):
        raise OneShotExecutionError("journal detail is not finite JSON")
    return dict(record)


def validate_journal(path: Path) -> tuple[dict[str, Any], ...]:
    path = Path(path)
    if not path.is_file():
        raise OneShotExecutionError("journal is absent")
    records: list[dict[str, Any]] = []
    previous = GENESIS_SHA256
    active_row: int | None = None
    active_identity: tuple[Any, ...] | None = None
    completed_indices: list[int] = []
    terminated = False
    pending_terminal: str | None = None
    attempt_id: str | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        for sequence, line in enumerate(handle):
            if not line.endswith("\n") or not line.strip():
                raise OneShotExecutionError("journal contains a partial or blank line")
            try:
                record = json.loads(
                    line,
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                )
            except (json.JSONDecodeError, ValueError) as exc:
                raise OneShotExecutionError("journal is not strict JSON") from exc
            record = _validate_journal_record(record)
            if terminated:
                raise OneShotExecutionError("journal continues after terminal record")
            if record["sequence"] != sequence or record["previous_record_sha256"] != previous:
                raise OneShotExecutionError("journal sequence/hash chain differs")
            if attempt_id is None:
                attempt_id = record["attempt_id"]
            elif record["attempt_id"] != attempt_id:
                raise OneShotExecutionError("journal attempt identity changed")
            event = record["event"]
            if pending_terminal is not None and event != "ATTEMPT_TERMINATED":
                raise OneShotExecutionError("journal continues after a row terminal vote")
            if sequence == 0 and event != "ATTEMPT_STARTED":
                raise OneShotExecutionError("journal does not start with ATTEMPT_STARTED")
            if event == "ATTEMPT_STARTED":
                if (
                    sequence != 0
                    or record["plan_index"] is not None
                    or any(
                        record[key] is not None
                        for key in (
                            "sample_id",
                            "family",
                            "partition_label",
                            "input_sha256",
                            "candidate_record_sha256",
                            "oracle_record_sha256",
                            "comparison_sha256",
                            "row_pass",
                            "terminal_state",
                            "failure_event",
                        )
                    )
                ):
                    raise OneShotExecutionError("ATTEMPT_STARTED position is invalid")
            elif event == "ROW_STARTED":
                expected = len(completed_indices)
                if active_row is not None or record["plan_index"] != expected:
                    raise OneShotExecutionError("row scheduling skipped, repeated, or reordered")
                if (
                    not isinstance(record["sample_id"], str)
                    or record["family"] not in FAMILIES
                    or record["partition_label"] != PARTITION_BY_INDEX[expected]
                    or any(
                        record[key] is not None
                        for key in (
                            "candidate_record_sha256",
                            "oracle_record_sha256",
                            "comparison_sha256",
                            "row_pass",
                            "terminal_state",
                            "failure_event",
                        )
                    )
                ):
                    raise OneShotExecutionError("ROW_STARTED identity/state is invalid")
                active_row = expected
                active_identity = tuple(
                    record[key]
                    for key in (
                        "plan_index",
                        "sample_id",
                        "family",
                        "partition_label",
                        "input_sha256",
                    )
                )
            elif event in {"ROW_COMPLETED", "ROW_INFRA_FAILURE"}:
                if active_row is None or record["plan_index"] != active_row:
                    raise OneShotExecutionError("row terminal event lacks its exact start")
                observed_identity = tuple(
                    record[key]
                    for key in (
                        "plan_index",
                        "sample_id",
                        "family",
                        "partition_label",
                        "input_sha256",
                    )
                )
                if observed_identity != active_identity:
                    raise OneShotExecutionError("row identity changed between start and terminal")
                if event == "ROW_COMPLETED":
                    for key in (
                        "candidate_record_sha256",
                        "oracle_record_sha256",
                        "comparison_sha256",
                    ):
                        _require_sha256(record[key], key)
                    if not isinstance(record["row_pass"], bool):
                        raise OneShotExecutionError("completed row lacks a boolean vote")
                    if record["row_pass"]:
                        if record["terminal_state"] is not None or record["failure_event"] is not None:
                            raise OneShotExecutionError("passing row carries a terminal failure")
                    elif record["terminal_state"] != "VALID_FAIL" or not isinstance(
                        record["failure_event"], str
                    ):
                        raise OneShotExecutionError("failing row lacks VALID_FAIL identity")
                    completed_indices.append(active_row)
                else:
                    if (
                        record["terminal_state"] != "INVALID_INFRA"
                        or record["failure_event"] != "EXECUTION_INTEGRITY_FAILURE"
                        or record["row_pass"] is not None
                    ):
                        raise OneShotExecutionError("infrastructure row failure is malformed")
                pending_terminal = record["terminal_state"]
                active_row = None
                active_identity = None
            elif event == "ATTEMPT_TERMINATED":
                if active_row is not None or record["terminal_state"] not in _TERMINAL_STATES:
                    raise OneShotExecutionError("attempt terminated with an active row")
                if any(
                    record[key] is not None
                    for key in (
                        "plan_index",
                        "sample_id",
                        "family",
                        "partition_label",
                        "input_sha256",
                        "candidate_record_sha256",
                        "oracle_record_sha256",
                        "comparison_sha256",
                        "row_pass",
                    )
                ):
                    raise OneShotExecutionError("attempt terminal carries row identity")
                if pending_terminal is not None and record["terminal_state"] != pending_terminal:
                    raise OneShotExecutionError("attempt terminal differs from row terminal")
                if record["terminal_state"] == "PASS" and completed_indices != list(
                    EXPECTED_PLAN_INDICES
                ):
                    raise OneShotExecutionError("PASS lacks all 57 explicit rows")
                terminated = True
            previous = record["record_sha256"]
            records.append(record)
    return tuple(records)


class AuditHashChainJournal:
    """Single-process durable writer for the one irrevocable attempt."""

    def __init__(self, path: Path, *, attempt_id: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise OneShotExecutionError("journal already exists; retry/resume is forbidden")
        with self.path.open("xb") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        self._attempt_id = attempt_id
        self._owner_pid = os.getpid()
        self._sequence = 0
        self._previous_hash = GENESIS_SHA256
        self._lock = Lock()

    @property
    def final_record_sha256(self) -> str:
        return self._previous_hash

    def append(
        self,
        event: str,
        *,
        row: PlanRow | None = None,
        candidate_record_sha256: str | None = None,
        oracle_record_sha256: str | None = None,
        comparison_sha256: str | None = None,
        row_pass: bool | None = None,
        terminal_state: str | None = None,
        failure_event: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if os.getpid() != self._owner_pid:
            raise OneShotExecutionError("only the creating process may append the journal")
        with self._lock:
            records = validate_journal(self.path) if self._sequence else ()
            disk_hash = records[-1]["record_sha256"] if records else GENESIS_SHA256
            if len(records) != self._sequence or disk_hash != self._previous_hash:
                raise OneShotExecutionError("journal changed outside its single writer")
            record: dict[str, Any] = {
                "schema_version": JOURNAL_SCHEMA_VERSION,
                "sequence": self._sequence,
                "previous_record_sha256": self._previous_hash,
                "record_sha256": "",
                "event": event,
                "attempt_id": self._attempt_id,
                "plan_index": None if row is None else row.plan_index,
                "sample_id": None if row is None else row.sample_id,
                "family": None if row is None else row.family,
                "partition_label": None
                if row is None
                else PARTITION_BY_INDEX[row.plan_index],
                "timestamp_utc": _utc_now(),
                "input_sha256": None if row is None else row.input_sha256,
                "candidate_record_sha256": candidate_record_sha256,
                "oracle_record_sha256": oracle_record_sha256,
                "comparison_sha256": comparison_sha256,
                "row_pass": row_pass,
                "terminal_state": terminal_state,
                "failure_event": failure_event,
                "detail": dict(detail or {}),
            }
            record["record_sha256"] = _journal_record_hash(record)
            _validate_journal_record(record)
            line = _canonical_json_bytes(record) + b"\n"
            # The semantic operation is append-only, but the durable publication
            # is a same-directory temp write plus atomic replacement of the exact
            # previous byte prefix followed by this one new line.  A crash can
            # therefore expose either the previous valid journal or the complete
            # next journal, never a torn JSONL record.
            previous_bytes = self.path.read_bytes()
            if len(previous_bytes.splitlines()) != self._sequence:
                raise OneShotExecutionError("journal byte prefix changed outside its writer")
            published_bytes = previous_bytes + line
            _atomic_replace_bytes(self.path, published_bytes, allow_replace=True)
            if not self.path.read_bytes().startswith(previous_bytes):
                raise OneShotExecutionError("journal publication was not append-only")
            verified = validate_journal(self.path)
            if len(verified) != self._sequence + 1 or verified[-1] != record:
                raise OneShotExecutionError("appended journal record verification failed")
            self._sequence += 1
            self._previous_hash = record["record_sha256"]
            return dict(record)


def _table_row(row: PlanRow, comparison: Mapping[str, Any]) -> dict[str, Any]:
    failed_votes = [
        vote
        for vote in comparison.get("votes", ())
        if isinstance(vote, Mapping) and vote.get("passed") is not True
    ]
    return {
        "plan_index": row.plan_index,
        "sample_id": row.sample_id,
        "partition_label": PARTITION_BY_INDEX[row.plan_index],
        "family": row.family,
        "input_sha256": row.input_sha256,
        "candidate_record_sha256": comparison.get("candidate_record_sha256"),
        "oracle_record_sha256": comparison.get("oracle_record_sha256"),
        "comparison_sha256": comparison.get("comparison_sha256"),
        "row_pass": bool(comparison.get("row_pass") is True),
        "failure_event": comparison.get("failure_event"),
        "failed_fields": json.dumps(
            sorted({str(vote.get("field")) for vote in failed_votes}), separators=(",", ":")
        ),
        "failed_categories": json.dumps(
            sorted({str(vote.get("category")) for vote in failed_votes}),
            separators=(",", ":"),
        ),
        "issues": json.dumps(
            sorted(str(value) for value in comparison.get("issues", ())),
            separators=(",", ":"),
        ),
    }


def _publish_family_tables(
    rows: Sequence[Mapping[str, Any]], paths: Mapping[str, Path]
) -> None:
    if set(paths) != set(FAMILIES):
        raise OneShotExecutionError("family-table output map differs")
    for family in FAMILIES:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=_TABLE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            if row["family"] == family:
                writer.writerow({key: row[key] for key in _TABLE_FIELDS})
        _atomic_replace_bytes(
            Path(paths[family]), stream.getvalue().encode("utf-8"), allow_replace=True
        )


def _first_failure(comparison: Mapping[str, Any], row: PlanRow) -> dict[str, Any] | None:
    if comparison.get("row_pass") is True:
        return None
    failed = [
        vote
        for vote in comparison.get("votes", ())
        if isinstance(vote, Mapping) and vote.get("passed") is not True
    ]
    first = failed[0] if failed else {}
    return {
        "plan_index": row.plan_index,
        "sample_id": row.sample_id,
        "field": first.get("field"),
        "category": first.get("category"),
        "failure_event": comparison.get("failure_event")
        or "FIELD_VOTE_FAILURE",
        "issues": sorted(str(value) for value in comparison.get("issues", ())),
    }


def _summary_document(
    *,
    registry: Mapping[str, Any],
    terminal_state: str,
    terminal_event: str,
    outcomes: Sequence[Mapping[str, Any]],
    first_failure: Mapping[str, Any] | None,
    journal_path: Path,
    family_paths: Mapping[str, Path],
) -> dict[str, Any]:
    completed = len(outcomes)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "attempt_id": registry["attempt_id"],
        "terminal_state": terminal_state,
        "terminal_event": terminal_event,
        "strict_equivalence_v1": {
            "disposition": "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR",
            "completed_rows": 12,
            "expected_rows": 57,
        },
        "equivalence_v2_execution_count": 1,
        "completed_rows": completed,
        "expected_rows": 57,
        "first_failure": None if first_failure is None else dict(first_failure),
        "unassessed_plan_indices": list(range(completed, 57)),
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "Phase1_S2_PINN_claim_status": "forbidden_unassessed",
        "journal_file_sha256": _sha256_path(journal_path),
        "journal_final_record_sha256": validate_journal(journal_path)[-1][
            "record_sha256"
        ],
        "family_table_sha256": {
            family: _sha256_path(path) for family, path in sorted(family_paths.items())
        },
    }


def _terminal_for_comparison(comparison: Mapping[str, Any]) -> str | None:
    if comparison.get("row_pass") is True and comparison.get("failure_event") is None:
        return None
    event = comparison.get("failure_event")
    if event is None:
        return "VALID_FAIL"
    try:
        return _closure_v3._core.classify_terminal(
            _closure_v3._core.TerminalEvent(str(event))
        ).value
    except (ValueError, AssertionError) as exc:
        raise OneShotExecutionError("comparison emitted an unknown terminal event") from exc


def run_one_shot_audit(
    *,
    contract: _closure_v3.V3LoadedContract,
    row_executor: RowExecutor,
    paths: OutputPaths,
    expected_registry_sha256: str,
) -> AuditOutcome:
    """Consume and execute exactly one attempt; never retries or resumes it."""

    rows = plan_rows_from_contract(contract)
    family_paths = paths.family_tables
    for result_path in (paths.journal, *family_paths.values(), paths.summary):
        if Path(result_path).exists():
            raise OneShotExecutionError(
                f"one-shot result path already exists; retry is forbidden: {result_path}"
            )
    registry = activate_registry_once(
        paths.registry, expected_registry_sha256=expected_registry_sha256
    )
    journal: AuditHashChainJournal | None = None
    comparisons: list[Mapping[str, Any]] = []
    table_rows: list[Mapping[str, Any]] = []
    first_failure: Mapping[str, Any] | None = None
    active_row: PlanRow | None = None
    try:
        journal = AuditHashChainJournal(paths.journal, attempt_id=registry["attempt_id"])
        journal.append("ATTEMPT_STARTED", detail={"owner_pid": os.getpid()})
        for row in rows:
            active_row = row
            journal.append("ROW_STARTED", row=row)
            pair = row_executor(row)
            if not isinstance(pair, RowObservationPair):
                raise OneShotExecutionError("row executor did not return RowObservationPair")
            candidate = _closure_v3.observation_to_record(
                pair.candidate_observation,
                plan_index=row.plan_index,
                input_sha256=row.input_sha256,
                contract=contract.core,
                validation_errors=pair.candidate_validation_errors,
            )
            oracle = _closure_v3.observation_to_record(
                pair.oracle_observation,
                plan_index=row.plan_index,
                input_sha256=row.input_sha256,
                contract=contract.core,
                validation_errors=pair.oracle_validation_errors,
            )
            comparison = _closure_v3.compare_record_pair(candidate, oracle, contract.core)
            comparisons.append(comparison)
            table_rows.append(_table_row(row, comparison))
            terminal = _terminal_for_comparison(comparison)
            journal.append(
                "ROW_COMPLETED",
                row=row,
                candidate_record_sha256=comparison["candidate_record_sha256"],
                oracle_record_sha256=comparison["oracle_record_sha256"],
                comparison_sha256=comparison["comparison_sha256"],
                row_pass=bool(comparison.get("row_pass") is True),
                terminal_state=terminal,
                failure_event=comparison.get("failure_event"),
            )
            active_row = None
            _publish_family_tables(table_rows, family_paths)
            if terminal is not None:
                first_failure = _first_failure(comparison, row)
                if terminal != "VALID_FAIL":
                    raise OneShotExecutionError(
                        "a completed comparison produced infrastructure terminal state"
                    )
                return _publish_terminal(
                    registry=registry,
                    paths=paths,
                    journal=journal,
                    comparisons=comparisons,
                    family_paths=family_paths,
                    terminal_state="VALID_FAIL",
                    terminal_event=str(
                        comparison.get("failure_event") or "FIELD_VOTE_FAILURE"
                    ),
                    first_failure=first_failure,
                )
        terminal = _closure_v3.finalise_plan_terminal(comparisons, contract.core).value
        if terminal != "PASS":
            raise OneShotExecutionError("57 completed rows did not reduce to exact PASS")
        return _publish_terminal(
            registry=registry,
            paths=paths,
            journal=journal,
            comparisons=comparisons,
            family_paths=family_paths,
            terminal_state="PASS",
            terminal_event="COMPLETE_PASS",
            first_failure=None,
        )
    except Exception as exc:
        if journal is None:
            raise
        failed_row = active_row
        detail = {"error_class": type(exc).__name__, "message": str(exc)}
        try:
            if failed_row is not None:
                journal.append(
                    "ROW_INFRA_FAILURE",
                    row=failed_row,
                    terminal_state="INVALID_INFRA",
                    failure_event="EXECUTION_INTEGRITY_FAILURE",
                    detail=detail,
                )
                active_row = None
            _publish_family_tables(table_rows, family_paths)
            return _publish_terminal(
                registry=registry,
                paths=paths,
                journal=journal,
                comparisons=comparisons,
                family_paths=family_paths,
                terminal_state="INVALID_INFRA",
                terminal_event="EXECUTION_INTEGRITY_FAILURE",
                first_failure={
                    "plan_index": None if failed_row is None else failed_row.plan_index,
                    "sample_id": None if failed_row is None else failed_row.sample_id,
                    "field": None,
                    "category": "execution_integrity",
                    "failure_event": "EXECUTION_INTEGRITY_FAILURE",
                    "issues": [f"{type(exc).__name__}: {exc}"],
                },
            )
        except Exception as publication_exc:
            raise OneShotExecutionError(
                "INVALID_INFRA could not be fully published after the attempt was consumed"
            ) from publication_exc


def _publish_terminal(
    *,
    registry: Mapping[str, Any],
    paths: OutputPaths,
    journal: AuditHashChainJournal,
    comparisons: Sequence[Mapping[str, Any]],
    family_paths: Mapping[str, Path],
    terminal_state: str,
    terminal_event: str,
    first_failure: Mapping[str, Any] | None,
) -> AuditOutcome:
    journal.append(
        "ATTEMPT_TERMINATED",
        terminal_state=terminal_state,
        failure_event=terminal_event,
        detail={"completed_rows": len(comparisons)},
    )
    records = validate_journal(paths.journal)
    if not records or records[-1]["terminal_state"] != terminal_state:
        raise OneShotExecutionError("journal terminal verification failed")
    summary = _summary_document(
        registry=registry,
        terminal_state=terminal_state,
        terminal_event=terminal_event,
        outcomes=comparisons,
        first_failure=first_failure,
        journal_path=paths.journal,
        family_paths=family_paths,
    )
    _atomic_write_json(paths.summary, summary, allow_replace=False)
    finalise_registry(
        paths.registry,
        completed_rows=len(comparisons),
        terminal_state=terminal_state,
        terminal_event=terminal_event,
        final_journal_sha256=journal.final_record_sha256,
    )
    return AuditOutcome(
        terminal_state=terminal_state,
        terminal_event=terminal_event,
        completed_rows=len(comparisons),
        first_failure=first_failure,
        summary_path=Path(paths.summary),
        final_journal_sha256=journal.final_record_sha256,
    )


__all__ = [
    "AuditHashChainJournal",
    "AuditOutcome",
    "EXPECTED_PLAN_COUNT",
    "EXPECTED_PLAN_INDICES",
    "EXPECTED_PLAN_INDICES_SHA256",
    "FAMILIES",
    "JOURNAL_SCHEMA_VERSION",
    "OneShotExecutionError",
    "OutputPaths",
    "PARTITION_BY_INDEX",
    "PlanRow",
    "REGISTRY_SCHEMA_VERSION",
    "RowExecutor",
    "RowObservationPair",
    "SUMMARY_SCHEMA_VERSION",
    "TASK_ID",
    "activate_registry_once",
    "build_initial_registry",
    "canonical_sha256",
    "finalise_registry",
    "load_registry",
    "plan_rows_from_contract",
    "run_one_shot_audit",
    "validate_journal",
    "write_initial_registry",
]
