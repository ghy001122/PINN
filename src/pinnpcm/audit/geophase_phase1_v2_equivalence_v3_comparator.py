"""Superseding record comparator for the independent equivalence-v3 audit.

This is a pure record-level adapter.  It validates the v4 ledger identity
schema, projects the already-normalized structural group into the immutable
equivalence-v2 A/B/C engine, and preserves that engine's mathematics.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator as _core
from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator_v3 as _v3
from pinnpcm.audit import geophase_phase1_v2_ledger_record_schema_v4 as _schema


TASK_ID = "Q2_PHASE1_V2_LEDGER_RECORD_SCHEMA_CLOSURE_V4"
CONTRACT_SCHEMA_VERSION = "geophase_phase1_v2_ledger_record_schema_closure_v4"
PREREGISTRATION_SCHEMA_VERSION = (
    "geophase_phase1_v2_ledger_record_schema_closure_preregistration_v4"
)
COMPARISON_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v3_comparison_v1"
DEFAULT_CONTRACT_PATH = (
    _schema.ROOT / "configs" / "geophase_phase1_v2_ledger_record_schema_closure_v4.yaml"
)
DEFAULT_PREREGISTRATION_PATH = (
    _schema.ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "ledger_record_schema_closure_v4"
    / "preregistration.json"
)


class TerminalState(str, Enum):
    INVALID_INFRA = "INVALID_INFRA"
    VALID_FAIL = "VALID_FAIL"
    PASS = "PASS"


@dataclass(frozen=True)
class LoadedContract:
    payload: Mapping[str, Any]
    preregistration_payload: Mapping[str, Any]
    predecessor: _v3.V3LoadedContract
    ledger_manifest: _schema.LedgerManifest
    execution_counts: Mapping[str, int]

    @property
    def core(self) -> _core.LoadedContract:
        return self.predecessor.core

    @property
    def ledger_group_manifest_path(self) -> str:
        return str(self.payload["single_schema_source"]["ledger_group_manifest"]["path"])

    @property
    def ledger_group_manifest_sha256(self) -> str:
        return self.ledger_manifest.csv_sha256


def _read_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise _schema.LedgerSchemaError("schema_loading", "PREREGISTRATION_INVALID", str(path))
    return payload


def _read_yaml(path: Path) -> Mapping[str, Any]:
    payload = __import__("yaml").safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise _schema.LedgerSchemaError("schema_loading", "CONTRACT_INVALID", str(path))
    return payload


def _resolve(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else _schema.ROOT / value


def _verified_file(record: Mapping[str, Any], *, label: str) -> Path:
    path = _resolve(str(record.get("path", "")))
    expected = str(record.get("sha256", ""))
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise _schema.LedgerSchemaError("schema_loading", "AUTHORITY_HASH_MISMATCH", label)
    return path


def load_preregistered_contract_bundle(
    path: Path = DEFAULT_PREREGISTRATION_PATH,
) -> LoadedContract:
    prereg = _read_json(path)
    if prereg.get("task_id") != TASK_ID or prereg.get("schema_version") != PREREGISTRATION_SCHEMA_VERSION:
        raise _schema.LedgerSchemaError("schema_loading", "PREREGISTRATION_IDENTITY_INVALID", str(path))
    config_path = _verified_file(
        {"path": prereg["config_path"], "sha256": prereg["config_sha256"]},
        label="closure v4 config",
    )
    config = _read_yaml(config_path)
    if config.get("task_id") != TASK_ID or config.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise _schema.LedgerSchemaError("schema_loading", "CONTRACT_IDENTITY_INVALID", str(config_path))
    source = config["single_schema_source"]
    _verified_file(source["module"], label="ledger schema module")
    _verified_file(source["comparator"], label="equivalence-v3 comparator")
    manifest_path = _verified_file(source["ledger_group_manifest"], label="ledger group manifest")
    ledger_manifest = _schema.load_ledger_group_manifest(
        manifest_path, expected_sha256=source["ledger_group_manifest"]["sha256"]
    )
    predecessor_record = config["supersedes"]["predecessor_preregistration"]
    predecessor_path = _verified_file(predecessor_record, label="closure-v3 preregistration")
    predecessor = _v3.load_preregistered_contract_bundle(predecessor_path)
    counts = config["execution_counts"]
    if (
        counts.get("equivalence_v2_execution_count") != 1
        or counts.get("equivalence_v3_execution_count") != 0
        or counts.get("formal_execution_count") != 0
    ):
        raise _schema.LedgerSchemaError("schema_loading", "EXECUTION_COUNTS_INVALID", "closure counts drifted")
    return LoadedContract(
        payload=config,
        preregistration_payload=prereg,
        predecessor=predecessor,
        ledger_manifest=ledger_manifest,
        execution_counts={str(key): int(value) for key, value in counts.items()},
    )


def observation_to_record(
    observation: Any,
    *,
    plan_index: int,
    input_sha256: str,
    contract: LoadedContract,
    runtime_input_sha256: str | None = None,
    validation_errors: Sequence[str] = (),
) -> dict[str, Any]:
    return _schema.observation_to_record(
        observation,
        plan_index=plan_index,
        input_sha256=input_sha256,
        contract=contract.predecessor,
        ledger_manifest=contract.ledger_manifest,
        runtime_input_sha256=runtime_input_sha256,
        validation_errors=validation_errors,
    )


def classify_terminal(*, stage: str, category: str) -> TerminalState:
    """Classify from an explicit stage/category; message text is never read."""

    infra_stages = {
        "authority",
        "environment",
        "producer",
        "schema_loading",
        "normalization",
        "canonical_record_formation",
        "serialization",
        "IO",
        "execution_integrity",
    }
    valid_fail_categories = {
        "missing",
        "extra",
        "nonfinite",
        "invalid_NA",
        "validation_error",
        "A_vote_failure",
        "B_vote_failure",
        "C_vote_failure",
        "mixed_vote_failure",
    }
    if stage in infra_stages:
        return TerminalState.INVALID_INFRA
    if stage == "record_comparison" and category in valid_fail_categories:
        return TerminalState.VALID_FAIL
    if (
        (stage == "row_complete" and category == "all_fields_and_votes_pass")
        or (stage == "plan_complete" and category == "all_rows_and_votes_pass")
    ):
        return TerminalState.PASS
    return TerminalState.INVALID_INFRA


def _invalid_comparison(
    candidate: Mapping[str, Any], oracle: Mapping[str, Any], issues: Sequence[Mapping[str, str]]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "record_status": "invalid_infrastructure",
        "terminal_state": TerminalState.INVALID_INFRA.value,
        "row_pass": False,
        "failure_stage": "normalization",
        "failure_category": "schema_or_producer_identity",
        "issues": sorted(
            ({str(key): str(value) for key, value in issue.items()} for issue in issues),
            key=lambda value: json.dumps(value, sort_keys=True),
        ),
        "votes": [],
        "candidate_record_sha256": _schema.canonical_sha256(candidate),
        "oracle_record_sha256": _schema.canonical_sha256(oracle),
        "predecessor_comparison": None,
    }
    payload["comparison_sha256"] = _schema.canonical_sha256(payload)
    return payload


def _is_record_content_issue(issue: Mapping[str, str]) -> bool:
    """Return true only for content errors after the schema is valid.

    An unregistered field is a real extra-field record failure.  Producer
    identity, grouping, schema, and canonical-record errors remain
    infrastructure failures because an auditable normalized record was never
    formed.
    """

    return issue.get("code") == "LEDGER_TEMPLATE_ABSENT"


def _vote_failure_category(predecessor: Mapping[str, Any]) -> str:
    if predecessor.get("record_status") == "invalid_content":
        return "validation_error"
    classes: set[str] = set()
    for vote in predecessor.get("votes", ()):
        if not isinstance(vote, Mapping) or vote.get("passed") is not False:
            continue
        category = str(vote.get("category", ""))
        if category.startswith("A_"):
            classes.add("A")
        elif category.startswith("B_"):
            classes.add("B")
        elif category.startswith("C_"):
            classes.add("C")
    if len(classes) == 1:
        return f"{next(iter(classes))}_vote_failure"
    return "mixed_vote_failure"


def compare_record_pair(
    candidate: Mapping[str, Any], oracle: Mapping[str, Any], contract: LoadedContract
) -> dict[str, Any]:
    """Validate v4 identities, then delegate the unchanged A/B/C vote engine."""

    candidate_issues = _schema.validate_normalized_record(candidate, contract.ledger_manifest)
    oracle_issues = _schema.validate_normalized_record(oracle, contract.ledger_manifest)
    if candidate.get("plan_identity") != oracle.get("plan_identity"):
        candidate_issues.append(
            _schema.LedgerSchemaError(
                "canonical_record_formation",
                "BILATERAL_PLAN_IDENTITY_MISMATCH",
                "candidate/oracle plan identities differ",
            ).as_record()
        )
    all_issues = candidate_issues + oracle_issues
    infrastructure_issues = [
        issue for issue in all_issues if not _is_record_content_issue(issue)
    ]
    if infrastructure_issues:
        return _invalid_comparison(candidate, oracle, infrastructure_issues)
    candidate_projection = _schema.project_to_predecessor_record(candidate)
    oracle_projection = _schema.project_to_predecessor_record(oracle)
    predecessor = _v3.compare_record_pair(
        candidate_projection, oracle_projection, contract.predecessor.core
    )
    if predecessor.get("row_pass") is True:
        state = TerminalState.PASS
        stage = "row_complete"
        category = "all_fields_and_votes_pass"
    else:
        state = TerminalState.VALID_FAIL
        stage = "record_comparison"
        category = _vote_failure_category(predecessor)
    payload = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "record_status": predecessor.get("record_status"),
        "terminal_state": state.value,
        "row_pass": bool(predecessor.get("row_pass")),
        "failure_stage": stage,
        "failure_category": category,
        "issues": copy.deepcopy(predecessor.get("issues", [])),
        "votes": copy.deepcopy(predecessor.get("votes", [])),
        "candidate_record_sha256": _schema.canonical_sha256(candidate),
        "oracle_record_sha256": _schema.canonical_sha256(oracle),
        "predecessor_comparison": predecessor,
    }
    if classify_terminal(stage=stage, category=category) is not state:
        raise AssertionError("structured terminal stage/category is inconsistent")
    payload["comparison_sha256"] = _schema.canonical_sha256(payload)
    return payload


def finalise_plan_terminal(outcomes: Sequence[Mapping[str, Any]], contract: LoadedContract) -> TerminalState:
    predecessor_outcomes = [
        outcome.get("predecessor_comparison")
        for outcome in outcomes
        if isinstance(outcome, Mapping) and outcome.get("predecessor_comparison") is not None
    ]
    if len(predecessor_outcomes) != len(outcomes):
        return TerminalState.INVALID_INFRA
    state = _v3.finalise_plan_terminal(predecessor_outcomes, contract.predecessor.core)
    return TerminalState(state.value)


publish_normalized_record = _schema.publish_normalized_record
load_normalized_record = _schema.load_normalized_record


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "DEFAULT_CONTRACT_PATH",
    "DEFAULT_PREREGISTRATION_PATH",
    "LoadedContract",
    "PREREGISTRATION_SCHEMA_VERSION",
    "TASK_ID",
    "TerminalState",
    "classify_terminal",
    "compare_record_pair",
    "finalise_plan_terminal",
    "load_normalized_record",
    "load_preregistered_contract_bundle",
    "observation_to_record",
    "publish_normalized_record",
]
