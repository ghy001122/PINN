"""Task-scoped provenance journal and sample publication for Phase 1-v2 readiness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any, Mapping


JOURNAL_STATES = frozenset({"SCHEDULED", "STARTED", "COMPLETED", "FAILED"})
JOURNAL_FIELDS = (
    "state",
    "sequence",
    "previous_record_sha256",
    "record_sha256",
    "plan_index",
    "sample_id",
    "PID",
    "timestamp_utc",
    "input_sha256",
    "output_sha256",
    "error_classification",
)
JOURNAL_GENESIS_SHA256 = "0" * 64
SAMPLE_SCHEMA_VERSION = (
    "geophase_phase1_v2_source_corrected_readiness_sample_v1"
)
SAMPLE_FIELDS = frozenset(
    {
        "schema_version",
        "completion_state",
        "plan_index",
        "sample_id",
        "input_sha256",
        "output_sha256",
        "finite",
        "formal_execution_count",
        "formal_artifact_count",
        "payload",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_TRANSITIONS = {
    None: frozenset({"SCHEDULED"}),
    "SCHEDULED": frozenset({"STARTED", "FAILED"}),
    "STARTED": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
}


class ReadinessJournalError(ValueError):
    """Raised when task-scoped readiness provenance is invalid."""


class SampleArtifactError(ValueError):
    """Raised when a completed-sample artifact cannot vote."""


@dataclass(frozen=True)
class PublishedSample:
    path: Path
    plan_index: int
    sample_id: str
    input_sha256: str
    output_sha256: str


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise SampleArtifactError("readiness evidence is not canonical finite JSON") from error
    return text.encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_sha256(value: Any, field: str, *, allow_none: bool = False) -> None:
    if allow_none and value is None:
        return
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ReadinessJournalError(f"{field} must be a lowercase SHA-256")


def _require_identity(plan_index: Any, sample_id: Any, PID: Any) -> None:
    if not isinstance(plan_index, int) or isinstance(plan_index, bool) or plan_index < 0:
        raise ReadinessJournalError("plan_index must be a nonnegative integer")
    if not isinstance(sample_id, str) or not sample_id or sample_id.strip() != sample_id:
        raise ReadinessJournalError("sample_id must be a nonempty normalized string")
    if not isinstance(PID, int) or isinstance(PID, bool) or PID <= 0:
        raise ReadinessJournalError("PID must be a positive integer")


def _require_utc_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise ReadinessJournalError("timestamp_utc must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReadinessJournalError("timestamp_utc is not ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ReadinessJournalError("timestamp_utc must carry an explicit UTC offset")


def _record_hash(record: Mapping[str, Any]) -> str:
    hashed = {key: value for key, value in record.items() if key != "record_sha256"}
    return _sha256_bytes(_canonical_json_bytes(hashed))


def _validate_state_fields(record: Mapping[str, Any]) -> None:
    state = record["state"]
    output_hash = record["output_sha256"]
    error = record["error_classification"]
    if state not in JOURNAL_STATES:
        raise ReadinessJournalError("journal state is not registered")
    _require_sha256(record["input_sha256"], "input_sha256")
    _require_sha256(output_hash, "output_sha256", allow_none=True)
    if state == "COMPLETED":
        if output_hash is None or error is not None:
            raise ReadinessJournalError(
                "COMPLETED requires output_sha256 and forbids an error classification"
            )
    elif state == "FAILED":
        if not isinstance(error, str) or not error:
            raise ReadinessJournalError("FAILED requires an error classification")
    elif output_hash is not None or error is not None:
        raise ReadinessJournalError(
            "SCHEDULED and STARTED forbid output and error classifications"
        )


def validate_journal(path: Path) -> tuple[dict[str, Any], ...]:
    """Validate the complete append-only hash chain and per-sample transitions."""

    path = Path(path)
    if not path.is_file():
        raise ReadinessJournalError("readiness journal does not exist")
    records: list[dict[str, Any]] = []
    prior_hash = JOURNAL_GENESIS_SHA256
    sample_states: dict[tuple[int, str], str] = {}
    plan_samples: dict[int, str] = {}
    sample_plans: dict[str, int] = {}
    sample_inputs: dict[tuple[int, str], str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for expected_sequence, line in enumerate(handle):
            if not line.endswith("\n") or not line.strip():
                raise ReadinessJournalError("journal has a partial or blank record")
            try:
                record = json.loads(
                    line,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(value)
                    ),
                )
            except (json.JSONDecodeError, ValueError) as error:
                raise ReadinessJournalError("journal record is not strict JSON") from error
            if not isinstance(record, dict) or tuple(sorted(record)) != tuple(
                sorted(JOURNAL_FIELDS)
            ):
                raise ReadinessJournalError("journal record schema mismatch")
            if record["sequence"] != expected_sequence:
                raise ReadinessJournalError("journal sequence is not contiguous")
            if record["previous_record_sha256"] != prior_hash:
                raise ReadinessJournalError("journal previous-record hash mismatch")
            _require_sha256(record["record_sha256"], "record_sha256")
            if record["record_sha256"] != _record_hash(record):
                raise ReadinessJournalError("journal record hash mismatch")
            _require_identity(record["plan_index"], record["sample_id"], record["PID"])
            _require_utc_timestamp(record["timestamp_utc"])
            _validate_state_fields(record)

            key = (record["plan_index"], record["sample_id"])
            previous_state = sample_states.get(key)
            if record["state"] not in _ALLOWED_TRANSITIONS[previous_state]:
                raise ReadinessJournalError("journal sample-state transition is invalid")
            if plan_samples.setdefault(record["plan_index"], record["sample_id"]) != record[
                "sample_id"
            ]:
                raise ReadinessJournalError("one plan_index maps to multiple sample IDs")
            if sample_plans.setdefault(record["sample_id"], record["plan_index"]) != record[
                "plan_index"
            ]:
                raise ReadinessJournalError("one sample ID maps to multiple plan indices")
            if sample_inputs.setdefault(key, record["input_sha256"]) != record[
                "input_sha256"
            ]:
                raise ReadinessJournalError("sample input hash changed within the journal")
            sample_states[key] = record["state"]
            prior_hash = record["record_sha256"]
            records.append(record)
    return tuple(records)


class ReadinessProvenanceJournal:
    """Single-parent writer for the bounded source-corrected readiness task."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._owner_pid = os.getpid()
        self._lock = Lock()
        if not self.path.exists():
            with self.path.open("xb") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        records = validate_journal(self.path)
        self._sequence = len(records)
        self._previous_hash = (
            records[-1]["record_sha256"] if records else JOURNAL_GENESIS_SHA256
        )

    def append(
        self,
        state: str,
        *,
        plan_index: int,
        sample_id: str,
        PID: int,
        input_sha256: str,
        output_sha256: str | None = None,
        error_classification: str | None = None,
        timestamp_utc: str | None = None,
    ) -> dict[str, Any]:
        if os.getpid() != self._owner_pid:
            raise ReadinessJournalError("only the creating parent process may write")
        with self._lock:
            records = validate_journal(self.path)
            disk_previous = (
                records[-1]["record_sha256"] if records else JOURNAL_GENESIS_SHA256
            )
            if len(records) != self._sequence or disk_previous != self._previous_hash:
                raise ReadinessJournalError("journal changed outside the single writer")
            record: dict[str, Any] = {
                "state": state,
                "sequence": self._sequence,
                "previous_record_sha256": self._previous_hash,
                "record_sha256": "",
                "plan_index": plan_index,
                "sample_id": sample_id,
                "PID": PID,
                "timestamp_utc": timestamp_utc
                or datetime.now(timezone.utc).isoformat(),
                "input_sha256": input_sha256,
                "output_sha256": output_sha256,
                "error_classification": error_classification,
            }
            _require_identity(plan_index, sample_id, PID)
            _require_utc_timestamp(record["timestamp_utc"])
            _validate_state_fields(record)
            previous_state = None
            for prior in reversed(records):
                if (
                    prior["plan_index"] == plan_index
                    and prior["sample_id"] == sample_id
                ):
                    previous_state = prior["state"]
                    if prior["input_sha256"] != input_sha256:
                        raise ReadinessJournalError("sample input hash changed")
                    break
                if prior["plan_index"] == plan_index or prior["sample_id"] == sample_id:
                    raise ReadinessJournalError("plan/sample identity collision")
            if state not in _ALLOWED_TRANSITIONS[previous_state]:
                raise ReadinessJournalError("journal sample-state transition is invalid")
            record["record_sha256"] = _record_hash(record)
            line = _canonical_json_bytes(record) + b"\n"
            with self.path.open("ab") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            self._sequence += 1
            self._previous_hash = record["record_sha256"]
            return dict(record)


def _finite_tree(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _finite_tree(item) for key, item in value.items())
    return False


def _sample_output_hash(document: Mapping[str, Any]) -> str:
    hashed = {key: value for key, value in document.items() if key != "output_sha256"}
    return _sha256_bytes(_canonical_json_bytes(hashed))


def build_completed_sample_document(
    *, plan_index: int, sample_id: str, input_sha256: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    _require_identity(plan_index, sample_id, os.getpid())
    _require_sha256(input_sha256, "input_sha256")
    if not isinstance(payload, Mapping) or not _finite_tree(dict(payload)):
        raise SampleArtifactError("completed sample payload must be a finite JSON mapping")
    document: dict[str, Any] = {
        "schema_version": SAMPLE_SCHEMA_VERSION,
        "completion_state": "COMPLETED",
        "plan_index": plan_index,
        "sample_id": sample_id,
        "input_sha256": input_sha256,
        "output_sha256": "",
        "finite": True,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "payload": dict(payload),
    }
    document["output_sha256"] = _sample_output_hash(document)
    return document


def write_completed_sample_temp(path: Path, document: Mapping[str, Any]) -> None:
    path = Path(path)
    if path.suffix != ".tmp":
        raise SampleArtifactError("completed sample temporary path must end in .tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json_bytes(dict(document)) + b"\n"
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def validate_completed_sample_document(
    document: Any,
    *,
    expected_plan_index: int,
    expected_sample_id: str,
    expected_input_sha256: str,
) -> dict[str, Any]:
    if not isinstance(document, dict) or frozenset(document) != SAMPLE_FIELDS:
        raise SampleArtifactError("completed sample schema mismatch")
    if document["schema_version"] != SAMPLE_SCHEMA_VERSION:
        raise SampleArtifactError("completed sample schema version mismatch")
    if document["completion_state"] != "COMPLETED":
        raise SampleArtifactError("incomplete sample is nonvoting")
    if document["plan_index"] != expected_plan_index:
        raise SampleArtifactError("completed sample plan_index mismatch")
    if document["sample_id"] != expected_sample_id:
        raise SampleArtifactError("completed sample ID mismatch")
    if document["input_sha256"] != expected_input_sha256:
        raise SampleArtifactError("completed sample input hash mismatch")
    _require_sha256(document["input_sha256"], "input_sha256")
    _require_sha256(document["output_sha256"], "output_sha256")
    if document["formal_execution_count"] != 0 or document["formal_artifact_count"] != 0:
        raise SampleArtifactError("readiness sample cannot be formal")
    if document["finite"] is not True or not _finite_tree(document["payload"]):
        raise SampleArtifactError("completed sample contains a nonfinite value")
    if document["output_sha256"] != _sample_output_hash(document):
        raise SampleArtifactError("completed sample output hash mismatch")
    return dict(document)


def _load_strict_json(path: Path) -> Any:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(
                handle,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SampleArtifactError("sample artifact is not strict readable JSON") from error


def publish_completed_sample(
    temporary_path: Path,
    destination_path: Path,
    *,
    expected_plan_index: int,
    expected_sample_id: str,
    expected_input_sha256: str,
) -> PublishedSample:
    temporary_path = Path(temporary_path)
    destination_path = Path(destination_path)
    if temporary_path.suffix != ".tmp" or not temporary_path.is_file():
        raise SampleArtifactError("completed sample temporary file is missing")
    if temporary_path.parent.resolve() != destination_path.parent.resolve():
        raise SampleArtifactError("atomic sample publication requires one directory")
    if destination_path.exists():
        raise SampleArtifactError("published sample is immutable and already exists")
    document = validate_completed_sample_document(
        _load_strict_json(temporary_path),
        expected_plan_index=expected_plan_index,
        expected_sample_id=expected_sample_id,
        expected_input_sha256=expected_input_sha256,
    )
    with temporary_path.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary_path, destination_path)
    return PublishedSample(
        path=destination_path,
        plan_index=expected_plan_index,
        sample_id=expected_sample_id,
        input_sha256=expected_input_sha256,
        output_sha256=document["output_sha256"],
    )


def published_sample_is_voting(
    path: Path,
    *,
    expected_plan_index: int,
    expected_sample_id: str,
    expected_input_sha256: str,
) -> bool:
    path = Path(path)
    if not path.is_file() or path.suffix == ".tmp":
        return False
    validate_completed_sample_document(
        _load_strict_json(path),
        expected_plan_index=expected_plan_index,
        expected_sample_id=expected_sample_id,
        expected_input_sha256=expected_input_sha256,
    )
    return True


__all__ = [
    "JOURNAL_FIELDS",
    "JOURNAL_STATES",
    "PublishedSample",
    "ReadinessJournalError",
    "ReadinessProvenanceJournal",
    "SAMPLE_FIELDS",
    "SAMPLE_SCHEMA_VERSION",
    "SampleArtifactError",
    "build_completed_sample_document",
    "publish_completed_sample",
    "published_sample_is_voting",
    "validate_completed_sample_document",
    "validate_journal",
    "write_completed_sample_temp",
]
