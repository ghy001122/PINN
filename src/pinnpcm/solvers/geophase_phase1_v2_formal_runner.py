"""Dormant, PRE-only Phase 1-v2 formal-runner state machinery.

This module validates the future execution semantics without exposing a path
that can create a real formal run identifier or schedule a formal unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4


RUNNER_STATES = (
    "PREPARED",
    "RUNNING",
    "INTERRUPTED_RESUMABLE",
    "COMPLETED_PASS",
    "COMPLETED_SCIENTIFIC_FAIL",
    "INVALID_CONTRACT",
    "BUDGET_EXHAUSTED",
)

REQUIRED_IDENTITY_HASHES = (
    "code_tree",
    "S2_config",
    "controller_v2_overlay",
    "resolved_runtime_identity",
    "formal_manifest_contract",
    "expanded_manifest",
    "execution_addendum",
    "execution_DAG",
    "environment",
)

_TRANSITIONS = {
    "PREPARED": {"RUNNING", "INVALID_CONTRACT", "BUDGET_EXHAUSTED"},
    "RUNNING": {
        "INTERRUPTED_RESUMABLE",
        "COMPLETED_PASS",
        "COMPLETED_SCIENTIFIC_FAIL",
        "INVALID_CONTRACT",
        "BUDGET_EXHAUSTED",
    },
    "INTERRUPTED_RESUMABLE": {
        "RUNNING",
        "INVALID_CONTRACT",
        "BUDGET_EXHAUSTED",
    },
    "COMPLETED_PASS": set(),
    "COMPLETED_SCIENTIFIC_FAIL": set(),
    "INVALID_CONTRACT": set(),
    "BUDGET_EXHAUSTED": set(),
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_PRE_ID = re.compile(r"^PRE-[A-Za-z0-9_.-]+$")


class InvalidContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class DormantRegistryView:
    path: Path
    identity: dict[str, Any]
    state: str
    events: tuple[dict[str, Any], ...]
    published_case_ids: tuple[str, ...]


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_pre_id(value: str, label: str) -> None:
    if not _SAFE_PRE_ID.fullmatch(value):
        raise ValueError(f"{label} must be a synthetic PRE identifier")


def validate_execution_dag_coverage(dag: dict[str, Any]) -> None:
    if int(dag.get("evaluation_item_count", -1)) != 63:
        raise InvalidContractError("execution DAG does not cover 63 evaluations")
    if int(dag.get("unique_execution_unit_count", -1)) != 60:
        raise InvalidContractError("execution DAG does not contain 60 units")
    if int(dag.get("reused_evaluation_count", -1)) != 3:
        raise InvalidContractError("execution DAG does not contain three legal reuses")
    units = dag.get("execution_units")
    reuses = dag.get("reuse_map")
    if not isinstance(units, list) or len(units) != 60:
        raise InvalidContractError("execution DAG unit list is invalid")
    if not isinstance(reuses, dict) or len(reuses) != 3:
        raise InvalidContractError("execution DAG reuse list is invalid")
    unit_ids = [unit.get("execution_unit_id") for unit in units]
    if len(set(unit_ids)) != 60 or any(not value for value in unit_ids):
        raise InvalidContractError("execution DAG unit IDs are missing or duplicated")
    consumers = [
        evaluation_id
        for unit in units
        for evaluation_id in unit.get("consumer_evaluation_ids", [])
    ]
    if len(consumers) != 63 or len(set(consumers)) != 63 or any(not item for item in consumers):
        raise InvalidContractError("execution DAG evaluation coverage is not one-to-one")


def _validate_identity_hashes(hashes: dict[str, str]) -> None:
    if set(hashes) != set(REQUIRED_IDENTITY_HASHES):
        raise InvalidContractError("runner identity hash set is incomplete")
    if any(not isinstance(value, str) or not _HEX64.fullmatch(value) for value in hashes.values()):
        raise InvalidContractError("runner identity contains an invalid SHA-256")


def _event_filename(sequence: int, state: str, digest: str) -> str:
    return f"{sequence:06d}-{state}-{digest}.json"


def _append_event_unchecked(
    registry: Path,
    *,
    sequence: int,
    previous_event_sha256: str | None,
    state: str,
    classification: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "schema_version": "geophase_phase1_v2_runner_event_v1",
        "sequence": int(sequence),
        "state": state,
        "classification": classification,
        "previous_event_sha256": previous_event_sha256,
        "created_utc": _utc_now(),
        "details": {} if details is None else details,
    }
    content = _canonical_bytes(event)
    digest = _sha256_bytes(content)
    journal = registry / "journal"
    journal.mkdir(parents=True, exist_ok=True)
    destination = journal / _event_filename(sequence, state, digest)
    temporary = journal / f".e{sequence:06d}-{uuid4().hex[:8]}.tmp"
    temporary.write_bytes(content)
    os.replace(temporary, destination)
    return {**event, "event_sha256": digest, "path": destination.name}


def create_prepared_registry(
    parent: Path,
    *,
    run_id: str,
    identity_hashes: dict[str, str],
    execution_dag: dict[str, Any],
    environment_summary: dict[str, Any],
) -> DormantRegistryView:
    """Atomically create a synthetic dormant-runner registry in PREPARED."""

    _validate_pre_id(run_id, "run_id")
    _validate_identity_hashes(identity_hashes)
    validate_execution_dag_coverage(execution_dag)
    root = Path(parent)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / run_id
    if destination.exists():
        raise FileExistsError("dormant registry is immutable and already exists")
    temporary = root / f".{run_id}.tmp-{uuid4().hex}"
    temporary.mkdir()
    try:
        identity = {
            "schema_version": "geophase_phase1_v2_dormant_registry_v1",
            "run_id": run_id,
            "formal": False,
            "formal_execution_count": 0,
            "formal_execution_consumed": False,
            "formal_unit_dispatch_enabled": False,
            "identity_hashes_sha256": dict(sorted(identity_hashes.items())),
            "coverage": {
                "evaluation_items": 63,
                "execution_units": 60,
                "legal_reuses": 3,
            },
            "environment_summary": environment_summary,
            "created_utc": _utc_now(),
        }
        identity_content = _canonical_bytes(identity)
        identity_digest = _sha256_bytes(identity_content)
        (temporary / f"identity-{identity_digest}.json").write_bytes(identity_content)
        (temporary / "cases").mkdir()
        (temporary / "work").mkdir()
        (temporary / "blocked").mkdir()
        _append_event_unchecked(
            temporary,
            sequence=0,
            previous_event_sha256=None,
            state="PREPARED",
            classification="synthetic_registry_prepared",
            details={"formal_dispatch": False},
        )
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return load_registry(destination)


def load_registry(path: Path) -> DormantRegistryView:
    registry = Path(path)
    identities = list(registry.glob("identity-*.json"))
    if len(identities) != 1:
        raise InvalidContractError("registry must contain one content-addressed identity")
    identity_path = identities[0]
    identity_digest = identity_path.stem.removeprefix("identity-")
    if not _HEX64.fullmatch(identity_digest) or _sha256_file(identity_path) != identity_digest:
        raise InvalidContractError("registry identity hash mismatch")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    _validate_pre_id(str(identity.get("run_id", "")), "registry run_id")
    _validate_identity_hashes(identity.get("identity_hashes_sha256", {}))
    if identity.get("formal") is not False or identity.get("formal_execution_count") != 0:
        raise InvalidContractError("dormant registry cannot carry formal execution")
    coverage = identity.get("coverage", {})
    if coverage != {"evaluation_items": 63, "execution_units": 60, "legal_reuses": 3}:
        raise InvalidContractError("dormant registry coverage changed")

    event_paths = sorted((registry / "journal").glob("*.json"))
    if not event_paths:
        raise InvalidContractError("registry journal is empty")
    events: list[dict[str, Any]] = []
    previous_digest: str | None = None
    previous_state: str | None = None
    for expected_sequence, event_path in enumerate(event_paths):
        event = json.loads(event_path.read_text(encoding="utf-8"))
        digest = _sha256_file(event_path)
        expected_name = _event_filename(expected_sequence, str(event.get("state")), digest)
        if event_path.name != expected_name:
            raise InvalidContractError("registry journal filename or ordering mismatch")
        if event.get("sequence") != expected_sequence:
            raise InvalidContractError("registry journal sequence mismatch")
        if event.get("previous_event_sha256") != previous_digest:
            raise InvalidContractError("registry journal hash chain mismatch")
        state = str(event.get("state"))
        if state not in RUNNER_STATES:
            raise InvalidContractError("registry journal contains an unknown state")
        if expected_sequence == 0:
            if state != "PREPARED":
                raise InvalidContractError("registry must begin in PREPARED")
        elif state not in _TRANSITIONS[str(previous_state)]:
            raise InvalidContractError("registry journal contains an invalid transition")
        events.append({**event, "event_sha256": digest, "path": event_path.name})
        previous_digest = digest
        previous_state = state
    cases = tuple(
        sorted(item.stem for item in (registry / "cases").glob("PRE-*.json"))
    )
    return DormantRegistryView(
        path=registry,
        identity=identity,
        state=str(previous_state),
        events=tuple(events),
        published_case_ids=cases,
    )


def append_state(
    path: Path,
    state: str,
    *,
    classification: str,
    details: dict[str, Any] | None = None,
) -> DormantRegistryView:
    view = load_registry(path)
    if state not in _TRANSITIONS[view.state]:
        raise InvalidContractError(f"invalid dormant-runner transition {view.state}->{state}")
    previous = view.events[-1]
    _append_event_unchecked(
        view.path,
        sequence=len(view.events),
        previous_event_sha256=previous["event_sha256"],
        state=state,
        classification=classification,
        details=details,
    )
    return load_registry(view.path)


def begin_running(path: Path) -> DormantRegistryView:
    return append_state(
        path,
        "RUNNING",
        classification="synthetic_dry_run_started",
        details={"formal_unit_dispatch": False},
    )


def interrupt_resumable(
    path: Path, *, reason: str, partial_case_id: str | None = None
) -> DormantRegistryView:
    if partial_case_id is not None:
        _validate_pre_id(partial_case_id, "partial case_id")
    return append_state(
        path,
        "INTERRUPTED_RESUMABLE",
        classification="infrastructure_interruption",
        details={"reason": reason, "partial_case_id": partial_case_id},
    )


def resume_same_run(
    path: Path, *, run_id: str, expected_identity_hashes: dict[str, str]
) -> DormantRegistryView:
    view = load_registry(path)
    if view.identity["run_id"] != run_id:
        raise InvalidContractError("resume attempted with a different run ID")
    _validate_identity_hashes(expected_identity_hashes)
    if view.identity["identity_hashes_sha256"] != dict(
        sorted(expected_identity_hashes.items())
    ):
        append_state(
            path,
            "INVALID_CONTRACT",
            classification="resume_identity_hash_mismatch",
        )
        raise InvalidContractError("resume identity hash mismatch")
    if view.state != "INTERRUPTED_RESUMABLE":
        raise InvalidContractError("only an interrupted registry can resume")
    return begin_running(path)


def create_partial_case_work(path: Path, case_id: str, payload: dict[str, Any]) -> Path:
    view = load_registry(path)
    if view.state != "RUNNING":
        raise InvalidContractError("partial case work requires RUNNING")
    _validate_pre_id(case_id, "case_id")
    partial = view.path / "work" / f".{case_id}.partial.json"
    if (view.path / "cases" / f"{case_id}.json").exists():
        raise FileExistsError("completed PRE case is immutable")
    partial.write_bytes(_canonical_bytes({"case_id": case_id, "payload": payload}))
    return partial


def publish_synthetic_case(
    path: Path,
    *,
    case_id: str,
    outcome: str,
    classification: str,
    payload: dict[str, Any],
) -> Path:
    view = load_registry(path)
    if view.state != "RUNNING":
        raise InvalidContractError("synthetic case publication requires RUNNING")
    _validate_pre_id(case_id, "case_id")
    if outcome not in {"pass", "scientific_fail", "infrastructure_fail"}:
        raise ValueError("synthetic PRE case outcome is invalid")
    destination = view.path / "cases" / f"{case_id}.json"
    if destination.exists():
        raise FileExistsError("completed PRE case is immutable")
    record = {
        "schema_version": "geophase_phase1_v2_synthetic_case_v1",
        "case_id": case_id,
        "formal": False,
        "formal_execution_count": 0,
        "outcome": outcome,
        "classification": classification,
        "payload": payload,
    }
    content = _canonical_bytes(record)
    temporary = view.path / "work" / f".{case_id}.complete-{uuid4().hex}.tmp"
    temporary.write_bytes(content)
    if json.loads(temporary.read_text(encoding="utf-8"))["case_id"] != case_id:
        raise RuntimeError("synthetic case schema validation failed")
    os.replace(temporary, destination)
    partial = view.path / "work" / f".{case_id}.partial.json"
    if partial.exists():
        partial.unlink()
    return destination


def record_foundation_failure(
    path: Path,
    *,
    failing_case_id: str,
    remaining_case_ids: list[str],
    reason: str,
) -> DormantRegistryView:
    publish_synthetic_case(
        path,
        case_id=failing_case_id,
        outcome="scientific_fail",
        classification="foundation_scientific_failure",
        payload={"reason": reason},
    )
    for case_id in remaining_case_ids:
        _validate_pre_id(case_id, "blocked case_id")
    blocked = {
        "schema_version": "geophase_phase1_v2_blocked_units_v1",
        "foundation_failure": failing_case_id,
        "blocked_case_ids": remaining_case_ids,
        "reason": reason,
    }
    destination = Path(path) / "blocked" / "foundation_fail_fast.json"
    temporary = destination.with_name(f".{destination.name}.tmp-{uuid4().hex}")
    temporary.write_bytes(_canonical_bytes(blocked))
    os.replace(temporary, destination)
    return append_state(
        path,
        "COMPLETED_SCIENTIFIC_FAIL",
        classification="foundation_fail_fast",
        details={
            "failing_case_id": failing_case_id,
            "blocked_case_count": len(remaining_case_ids),
        },
    )


def complete_pass(path: Path) -> DormantRegistryView:
    return append_state(
        path,
        "COMPLETED_PASS",
        classification="synthetic_dry_run_completed",
        details={"formal_scientific_vote": False},
    )


def complete_scientific_fail(path: Path, *, reason: str) -> DormantRegistryView:
    return append_state(
        path,
        "COMPLETED_SCIENTIFIC_FAIL",
        classification="nonfoundation_scientific_failure",
        details={"reason": reason},
    )


def mark_budget_exhausted(path: Path, *, reason: str) -> DormantRegistryView:
    return append_state(
        path,
        "BUDGET_EXHAUSTED",
        classification="infrastructure_budget_exhaustion",
        details={"reason": reason},
    )


__all__ = [
    "DormantRegistryView",
    "InvalidContractError",
    "REQUIRED_IDENTITY_HASHES",
    "RUNNER_STATES",
    "append_state",
    "begin_running",
    "complete_pass",
    "complete_scientific_fail",
    "create_partial_case_work",
    "create_prepared_registry",
    "interrupt_resumable",
    "load_registry",
    "mark_budget_exhausted",
    "publish_synthetic_case",
    "record_foundation_failure",
    "resume_same_run",
    "validate_execution_dag_coverage",
]
