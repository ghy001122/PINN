"""Final solver-free integrity closure for the equivalence-v2 comparator.

This module deliberately performs no numerical execution.  It adds record
integrity checks in front of the frozen v2 A/B/C vote engine and an exact
57-row terminal reducer behind it.  The mathematical voting rules remain in
``geophase_phase1_v2_equivalence_v2_comparator`` and are not copied here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import numpy as np
import yaml

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator as _core


RECORD_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_observation_record_v3"
COMPARISON_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_comparison_v3"
CONTRACT_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v2_comparator_closure_v3"
PREREGISTRATION_SCHEMA_VERSION = (
    "geophase_phase1_v2_equivalence_v2_comparator_closure_preregistration_v3"
)
TASK_ID = "Q2_PHASE1_V2_EQUIVALENCE_V2_COMPARATOR_CLOSURE_V3"
DEFAULT_CONTRACT_PATH = (
    _core.ROOT
    / "configs"
    / "geophase_phase1_v2_equivalence_v2_comparator_closure_v3.yaml"
)
DEFAULT_PREREGISTRATION_PATH = (
    _core.ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_v2_comparator_closure_v3"
    / "preregistration.json"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FAILURE_RE = re.compile(
    r"^injected:(?P<location>full_step|first_half_step|second_half_step):"
    r"(?P<failure_type>[a-z0-9_]+)\|observed:"
    r"(?P<error_class>[A-Za-z_][A-Za-z0-9_]*):(?P<message>.+)$"
)


@dataclass(frozen=True)
class V3LoadedContract:
    """V3 authority envelope with ergonomic access to the frozen v2 math core."""

    closure_payload: Mapping[str, Any]
    preregistration_payload: Mapping[str, Any]
    core: _core.LoadedContract

    @property
    def payload(self) -> Mapping[str, Any]:
        return self.core.payload

    @property
    def templates(self) -> Mapping[tuple[str, str, str], _core.ManifestTemplate]:
        return self.core.templates

    @property
    def plan_rows(self) -> Mapping[int, Mapping[str, str]]:
        return self.core.plan_rows

    @property
    def template_ids_sha256(self) -> str:
        return self.core.template_ids_sha256

    @property
    def plan_rows_sha256(self) -> str:
        return self.core.plan_rows_sha256


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            f"cannot load v3 preregistration: {type(exc).__name__}",
        ) from exc
    if not isinstance(payload, Mapping):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 preregistration is not a mapping",
        )
    return payload


def _read_yaml(path: Path) -> Mapping[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            f"cannot load v3 closure: {type(exc).__name__}",
        ) from exc
    if not isinstance(payload, Mapping):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 closure is not a mapping",
        )
    return payload


def _resolve_path(token: Any) -> Path:
    if not isinstance(token, str) or not token:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, "v3 frozen path is invalid"
        )
    path = Path(token)
    return path if path.is_absolute() else _core.ROOT / path


def _verify_path_sha(path_token: Any, expected: Any, *, label: str) -> Path:
    path = _resolve_path(path_token)
    if not isinstance(expected, str) or _SHA256_RE.fullmatch(expected) is None:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, f"{label} SHA-256 is invalid"
        )
    try:
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.AUTHORITY_FAILURE, f"cannot read {label}"
        ) from exc
    if observed != expected:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.AUTHORITY_FAILURE, f"{label} identity drifted"
        )
    return path


def _require_zero_counts(payload: Mapping[str, Any], *, label: str) -> None:
    counts = payload.get("execution_counts", payload)
    if not isinstance(counts, Mapping):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, f"{label} counts are absent"
        )
    for key in (
        "equivalence_v2_execution_count",
        "equivalence_v2_completed_rows",
        "equivalence_v2_result_artifact_count",
        "formal_execution_count",
        "formal_artifact_count",
    ):
        if counts.get(key) != 0:
            raise _core.ContractInfrastructureError(
                _core.TerminalEvent.CONTRACT_FAILURE,
                f"{label} count changed: {key}",
            )


def load_preregistered_contract_bundle(
    path: Path = DEFAULT_PREREGISTRATION_PATH,
) -> V3LoadedContract:
    """Load v3 authority, then its immutable PR12 field/plan/math predecessor."""

    preregistration = _read_json(path)
    if preregistration.get("task_id") != TASK_ID or preregistration.get(
        "schema_version"
    ) != PREREGISTRATION_SCHEMA_VERSION:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "unexpected v3 preregistration identity",
        )
    if preregistration.get("status") != "ready_contract_only_future_execution_not_authorized":
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, "v3 preregistration status differs"
        )
    _require_zero_counts(preregistration, label="v3 preregistration")
    contract_path = _verify_path_sha(
        preregistration.get("config_path"),
        preregistration.get("config_sha256"),
        label="v3 closure config",
    )
    closure = _read_yaml(contract_path)
    if closure.get("task_id") != TASK_ID or closure.get(
        "schema_version"
    ) != CONTRACT_SCHEMA_VERSION:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, "unexpected v3 closure identity"
        )
    if closure.get("status") != "superseding_preregistered_not_authorized_not_executed":
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, "v3 closure status differs"
        )
    _require_zero_counts(closure, label="v3 closure")
    engine = closure.get("comparison_engine")
    if not isinstance(engine, Mapping):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE, "v3 comparison engine lock is absent"
        )
    engine_path = _verify_path_sha(
        engine.get("path"), engine.get("sha256"), label="v3 comparison engine"
    )
    if engine_path.resolve() != Path(__file__).resolve():
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 comparison engine path does not identify this module",
        )
    if preregistration.get("comparison_engine_path") != engine.get("path") or preregistration.get(
        "comparison_engine_sha256"
    ) != engine.get("sha256"):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 preregistration/comparison engine identity differs",
        )
    supersedes = closure.get("supersedes")
    predecessors = (
        supersedes.get("immutable_predecessors")
        if isinstance(supersedes, Mapping)
        else None
    )
    required_predecessors = {
        "parent_closure_config",
        "parent_closure_preregistration",
        "parent_comparator",
        "field_manifest",
        "plan_manifest",
    }
    if not isinstance(predecessors, Mapping) or set(predecessors) != required_predecessors:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 immutable predecessor set differs",
        )
    for label, record in predecessors.items():
        if not isinstance(record, Mapping):
            raise _core.ContractInfrastructureError(
                _core.TerminalEvent.CONTRACT_FAILURE,
                f"v3 predecessor record is invalid: {label}",
            )
        _verify_path_sha(record.get("path"), record.get("sha256"), label=label)
    fixture = closure.get("sealed_synthetic_fixtures")
    if not isinstance(fixture, Mapping):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 sealed fixture lock is absent",
        )
    _verify_path_sha(
        fixture.get("definitions_path"),
        fixture.get("definitions_sha256"),
        label="v3 sealed fixture definitions",
    )
    if (
        fixture.get("evidence_type") != "synthetic_contract_evidence_nonvoting"
        or fixture.get("audit_row_count") != 0
    ):
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 sealed fixture evidence boundary differs",
        )
    core_prereg = _resolve_path(predecessors["parent_closure_preregistration"]["path"])
    frozen_core = _core.load_preregistered_contract_bundle(core_prereg)
    if len(frozen_core.templates) != 638 or len(frozen_core.plan_rows) != 57:
        raise _core.ContractInfrastructureError(
            _core.TerminalEvent.CONTRACT_FAILURE,
            "v3 predecessor field/plan cardinality differs",
        )
    return V3LoadedContract(
        closure_payload=closure,
        preregistration_payload=preregistration,
        core=frozen_core,
    )


def _expected_grid_id(row: Mapping[str, str]) -> str:
    return str(row["grid"] or "L1")


def _profile_from_observation(observation: Any, family: str, row: Mapping[str, str]) -> str:
    exact = getattr(observation, "exact_votes", None)
    if not isinstance(exact, Mapping):
        return ""
    if family == "electrical":
        return "electrical_full"
    if family == "failure":
        return f"failure_at_{row['candidate_paths']}"
    accepted = list(exact.get("accepted_rejected_sequence", ()))
    if family == "interval":
        if accepted == ["accepted"]:
            return "interval_full_accepted"
        if accepted == ["rejected"]:
            return "interval_minimal_rejected"
        return ""
    if family == "progression":
        events = list(exact.get("event_count_direction_and_order", ()))
        reversals = list(exact.get("reversal_count_direction_and_order", ()))
        return (
            "progression_NA_no_event_or_reversal"
            if not events and not reversals
            else "progression_full"
        )
    return ""


def _failure_identity(
    observation: Any, family: str, row: Mapping[str, str]
) -> dict[str, Any]:
    exact = getattr(observation, "exact_votes", None)
    classification = (
        None if not isinstance(exact, Mapping) else exact.get("failure_classification")
    )
    if family != "failure":
        return {
            "expected_disposition": "success_or_bounded_progression",
            "expected_failure_type": None,
            "expected_failure_location": None,
            "extracted_failure_classification": _core._jsonable(classification),
        }
    match = _FAILURE_RE.fullmatch(classification) if isinstance(classification, str) else None
    parsed = None
    if match is not None:
        parsed = {
            "failure_type": match.group("failure_type"),
            "failure_location": match.group("location"),
            "error_class": match.group("error_class"),
            "error_message": match.group("message"),
        }
    return {
        "expected_disposition": "failure",
        "expected_failure_type": str(row["failure_class"]),
        "expected_failure_location": str(row["candidate_paths"]),
        "extracted_failure_classification": _core._jsonable(classification),
        "parsed_failure": parsed,
    }


def observation_to_record(
    observation: Any,
    *,
    plan_index: int,
    input_sha256: str,
    contract: _core.LoadedContract,
    validation_errors: Sequence[str] = (),
) -> dict[str, Any]:
    """Bind one production observation to its frozen row without caller labels."""

    row = contract.plan_rows.get(plan_index)
    if row is None:
        # Preserve a canonical invalid record rather than letting a caller attach
        # an out-of-plan identity to otherwise valid observation content.
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "plan_identity": {
                "plan_index": int(plan_index),
                "sample_id": None,
                "family": None,
                "grid_id": None,
                "input_sha256": str(input_sha256),
            },
            "failure_contract": None,
            "observation": None,
            "construction_errors": ["plan index is not in the frozen manifest"],
        }
    family = str(row["family"])
    profile = _profile_from_observation(observation, family, row)
    maximum = (
        None
        if row["maximum_accepted_intervals"] == ""
        else int(row["maximum_accepted_intervals"])
    )
    core_record = _core.observation_to_record(
        observation,
        plan_index=int(plan_index),
        sample_id=str(row["sample_id"]),
        family=family,
        profile_id=profile,
        grid_id=_expected_grid_id(row),
        protocol_voltage_scale_V=float(contract.payload["protocol_voltage_scale_V"]),
        maximum_accepted_intervals=maximum,
        validation_errors=validation_errors,
    )
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "plan_identity": {
            "plan_index": int(plan_index),
            "sample_id": str(row["sample_id"]),
            "family": family,
            "grid_id": _expected_grid_id(row),
            "input_sha256": str(input_sha256),
        },
        "failure_contract": _failure_identity(observation, family, row),
        "observation": core_record,
        "construction_errors": [],
    }


def _expected_shape(pattern: str, context: Mapping[str, Any]) -> tuple[int, ...]:
    ny, nx = (int(value) for value in context["shape"])
    if pattern in {"phi", "cell_Joule_power"}:
        return (ny, nx)
    if pattern.endswith(".lateral.x_face_flux_W"):
        return (ny, nx - 1)
    if pattern.endswith(".lateral.y_face_flux_W"):
        return (ny - 1, nx)
    if pattern.endswith(".lateral.net_cell_outflow_W"):
        return (ny, nx)
    if pattern.endswith(".lateral.boundary_face_flux_W"):
        return (2 * ny + 2 * nx,)
    if pattern.startswith("streaming.scalar."):
        return ()
    cell_suffixes = (
        ".state.temperature_K",
        ".state.conductive_state",
        ".state.branch_memory",
        ".electrical.potential_V",
        ".electrical.cell_joule_power_W",
        ".final_state.temperature_K",
        ".final_state.conductive_state",
        ".final_state.branch_memory",
        ".snapshot.{snapshot_index}.temperature_K",
        ".snapshot.{snapshot_index}.conductive_state",
        ".snapshot.{snapshot_index}.branch_memory",
        ".snapshot.{snapshot_index}.potential_V",
        ".snapshot.{snapshot_index}.cell_joule_power_W",
    )
    if pattern.endswith(cell_suffixes):
        return (ny, nx)
    return ()


def _actual_shape(field: Mapping[str, Any]) -> tuple[int, ...] | None:
    try:
        array = _core._value_array(field["value"])
    except (KeyError, TypeError, ValueError):
        return None
    return tuple(int(value) for value in array.shape)


def _template_names(
    record: Mapping[str, Any], contract: _core.LoadedContract
) -> dict[tuple[str, str, str], list[str]]:
    payload = record.get("observation")
    if not isinstance(payload, Mapping):
        return {}
    family = payload.get("family")
    output: dict[tuple[str, str, str], list[str]] = {}
    for kind, key in (("numeric", "numeric"), ("exact", "exact_votes"), ("telemetry", "telemetry")):
        mapping = payload.get(key)
        if not isinstance(mapping, Mapping):
            continue
        for name in mapping:
            if not isinstance(name, str):
                continue
            manifest_key = (str(family), kind, _core._normalise_field(name))
            if manifest_key in contract.templates:
                output.setdefault(manifest_key, []).append(name)
    return output


def _indices(names: Sequence[str], expression: re.Pattern[str]) -> tuple[set[int], bool]:
    values: set[int] = set()
    canonical = True
    for name in names:
        match = expression.fullmatch(name)
        if match is None:
            canonical = False
            continue
        token = match.group("index")
        canonical = canonical and token == str(int(token))
        values.add(int(token))
    return values, canonical


def _dynamic_domain_issues(
    record: Mapping[str, Any], contract: _core.LoadedContract
) -> list[str]:
    payload = record.get("observation")
    if not isinstance(payload, Mapping) or payload.get("family") != "progression":
        return []
    profile = str(payload.get("profile_id"))
    names_by_template = _template_names(record, contract)
    issues: list[str] = []
    anchor_patterns = {
        "record_index": "streaming.scalar.{record_index}.time_s",
        "snapshot_index": "streaming.snapshot.{snapshot_index}.time_s",
    }
    domains: dict[str, set[int]] = {"interval_index": set(range(4))}
    expressions = {
        "interval_index": re.compile(r"^history\.(?P<index>\d+)\..+$"),
        "record_index": re.compile(r"^streaming\.scalar\.(?P<index>\d+)\..+$"),
        "snapshot_index": re.compile(r"^streaming\.snapshot\.(?P<index>\d+)\..+$"),
    }
    for label, pattern in anchor_patterns.items():
        key = ("progression", "numeric", pattern)
        names = names_by_template.get(key, [])
        domain, canonical = _indices(names, expressions[label])
        if not canonical or not domain or domain != set(range(max(domain) + 1)):
            issues.append(f"{label} anchor domain is absent, noncanonical, or gapped")
        domains[label] = domain
    for template in contract.templates.values():
        if template.family != "progression" or not _core._required(template, profile):
            continue
        placeholder = next(
            (
                label
                for label in ("interval_index", "record_index", "snapshot_index")
                if "{" + label + "}" in template.field_pattern
            ),
            None,
        )
        if placeholder is None:
            continue
        actual, canonical = _indices(
            names_by_template.get(template.key, []), expressions[placeholder]
        )
        if not canonical or actual != domains[placeholder]:
            issues.append(
                "dynamic template index cover differs: "
                f"{template.template_id}:{placeholder}"
            )
    return issues


def _shape_issues(record: Mapping[str, Any], contract: _core.LoadedContract) -> list[str]:
    payload = record.get("observation")
    if not isinstance(payload, Mapping):
        return []
    grid_id = payload.get("grid_id")
    if grid_id not in contract.payload["operator_contexts"]:
        return ["record grid has no frozen topology"]
    context = contract.payload["operator_contexts"][grid_id]
    numeric = payload.get("numeric")
    if not isinstance(numeric, Mapping):
        return []
    issues: list[str] = []
    for name, field in numeric.items():
        if not isinstance(name, str) or not isinstance(field, Mapping):
            continue
        template = contract.templates.get(
            (str(payload.get("family")), "numeric", _core._normalise_field(name))
        )
        if template is None:
            continue
        expected = _expected_shape(template.field_pattern, context)
        actual = _actual_shape(field)
        if actual != expected:
            issues.append(
                f"numeric topology differs: {name}:observed={actual},expected={expected}"
            )
    return issues


def _failure_contract_issues(record: Mapping[str, Any]) -> list[str]:
    identity = record.get("failure_contract")
    if not isinstance(identity, Mapping):
        return ["failure contract is absent"]
    expected = identity.get("expected_disposition")
    classification = identity.get("extracted_failure_classification")
    payload = record.get("observation")
    exact_votes = payload.get("exact_votes") if isinstance(payload, Mapping) else None
    nested_classification = (
        exact_votes.get("failure_classification")
        if isinstance(exact_votes, Mapping)
        else None
    )
    issues: list[str] = []
    if classification != nested_classification:
        issues.append(
            "derived failure classification differs from nested production exact vote"
        )
    if expected == "failure":
        parsed = identity.get("parsed_failure")
        if not isinstance(parsed, Mapping):
            return issues + ["failure classification is not structurally parseable"]
        if parsed.get("failure_type") != identity.get("expected_failure_type"):
            issues.append("failure type differs from frozen plan")
        if parsed.get("failure_location") != identity.get("expected_failure_location"):
            issues.append("failure location differs from frozen plan")
        if not isinstance(parsed.get("error_class"), str) or not parsed.get("error_class"):
            issues.append("failure error class is absent")
        if not isinstance(parsed.get("error_message"), str) or not parsed.get("error_message"):
            issues.append("failure error message is absent")
        return issues
    family = payload.get("family") if isinstance(payload, Mapping) else None
    if family == "interval" and classification != "none":
        issues.append("nominal interval row was relabelled as a failure")
    if family == "progression":
        progression_success = (
            isinstance(classification, (list, tuple))
            and len(classification) == 3
            and isinstance(classification[0], str)
            and isinstance(classification[1], bool)
            and isinstance(classification[2], (list, tuple))
            and all(value == "none" for value in classification[2])
        )
        if not progression_success:
            issues.append("nominal progression row was relabelled as a failure")
    if family == "electrical" and classification is not None:
        issues.append("electrical row has an unexpected failure classification")
    return issues


def _record_integrity_issues(
    record: Mapping[str, Any], contract: _core.LoadedContract
) -> list[str]:
    expected_keys = {
        "schema_version",
        "plan_identity",
        "failure_contract",
        "observation",
        "construction_errors",
    }
    if set(record) != expected_keys:
        return ["v3 record envelope differs"]
    issues = [str(value) for value in record.get("construction_errors", ())]
    if record.get("schema_version") != RECORD_SCHEMA_VERSION:
        issues.append("v3 record schema differs")
    identity = record.get("plan_identity")
    if not isinstance(identity, Mapping):
        return issues + ["plan identity is absent"]
    index = identity.get("plan_index")
    if not isinstance(index, int) or index not in contract.plan_rows:
        return issues + ["plan identity index is not frozen"]
    row = contract.plan_rows[index]
    expected_identity = {
        "plan_index": index,
        "sample_id": row["sample_id"],
        "family": row["family"],
        "grid_id": _expected_grid_id(row),
        "input_sha256": row["plan_sha256"],
    }
    if dict(identity) != expected_identity:
        issues.append("plan/sample/family/grid/input identity differs from frozen row")
    payload = record.get("observation")
    if isinstance(payload, Mapping):
        for key in ("plan_index", "sample_id", "family", "grid_id"):
            if payload.get(key) != expected_identity[key]:
                issues.append(f"nested observation identity differs: {key}")
    else:
        issues.append("nested observation is absent")
    issues.extend(_failure_contract_issues(record))
    issues.extend(_dynamic_domain_issues(record, contract))
    issues.extend(_shape_issues(record, contract))
    return issues


def _invalid_comparison(
    candidate: Mapping[str, Any], oracle: Mapping[str, Any], issues: Sequence[str]
) -> dict[str, Any]:
    payload = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "record_status": "invalid_content",
        "row_pass": False,
        "failure_event": _core.TerminalEvent.RECORD_VALIDATION_FAILURE.value,
        "issues": sorted(set(str(value) for value in issues)),
        "votes": [],
        "plan_identity": copy.deepcopy(candidate.get("plan_identity")),
        "candidate_record_sha256": _core.canonical_sha256(candidate),
        "oracle_record_sha256": _core.canonical_sha256(oracle),
        "core_comparison": None,
    }
    payload["comparison_sha256"] = _core.canonical_sha256(payload)
    return payload


def compare_record_pair(
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    contract: _core.LoadedContract,
) -> dict[str, Any]:
    """Apply v3 integrity gates, then delegate unchanged A/B/C votes to v2."""

    candidate_issues = _record_integrity_issues(candidate, contract)
    oracle_issues = _record_integrity_issues(oracle, contract)
    if candidate.get("plan_identity") != oracle.get("plan_identity"):
        candidate_issues.append("candidate/oracle v3 plan identities differ")
    if candidate_issues or oracle_issues:
        return _invalid_comparison(candidate, oracle, candidate_issues + oracle_issues)
    core_result = _core.compare_record_pair(
        candidate["observation"], oracle["observation"], contract
    )
    payload = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "record_status": core_result["record_status"],
        "row_pass": bool(core_result["row_pass"]),
        "failure_event": core_result["failure_event"],
        "issues": list(core_result["issues"]),
        "votes": copy.deepcopy(core_result["votes"]),
        "plan_identity": copy.deepcopy(candidate["plan_identity"]),
        "candidate_record_sha256": _core.canonical_sha256(candidate),
        "oracle_record_sha256": _core.canonical_sha256(oracle),
        "core_comparison": core_result,
    }
    payload["comparison_sha256"] = _core.canonical_sha256(payload)
    return payload


def _comparison_hash_valid(comparison: Mapping[str, Any]) -> bool:
    expected = comparison.get("comparison_sha256")
    if not isinstance(expected, str) or _SHA256_RE.fullmatch(expected) is None:
        return False
    payload = dict(comparison)
    payload.pop("comparison_sha256", None)
    return _core.canonical_sha256(payload) == expected


def finalise_plan_terminal(
    outcomes: Sequence[Mapping[str, Any]], contract: _core.LoadedContract
) -> _core.TerminalState:
    """Return PASS only for the exact, ordered, content-addressed 0..56 plan."""

    if not outcomes:
        return _core.TerminalState.INVALID_INFRA
    for position, comparison in enumerate(outcomes):
        if not isinstance(comparison, Mapping) or not _comparison_hash_valid(comparison):
            return _core.TerminalState.INVALID_INFRA
        identity = comparison.get("plan_identity")
        if not isinstance(identity, Mapping) or position not in contract.plan_rows:
            return _core.TerminalState.INVALID_INFRA
        row = contract.plan_rows[position]
        expected = {
            "plan_index": position,
            "sample_id": row["sample_id"],
            "family": row["family"],
            "grid_id": _expected_grid_id(row),
            "input_sha256": row["plan_sha256"],
        }
        if dict(identity) != expected:
            return _core.TerminalState.INVALID_INFRA
        for hash_key in ("candidate_record_sha256", "oracle_record_sha256"):
            value = comparison.get(hash_key)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                return _core.TerminalState.INVALID_INFRA
        event = comparison.get("failure_event")
        if event is not None:
            try:
                terminal = _core.classify_terminal(_core.TerminalEvent(str(event)))
            except ValueError:
                return _core.TerminalState.INVALID_INFRA
            return (
                terminal
                if position == len(outcomes) - 1
                else _core.TerminalState.INVALID_INFRA
            )
        if comparison.get("row_pass") is not True:
            return (
                _core.TerminalState.VALID_FAIL
                if position == len(outcomes) - 1
                else _core.TerminalState.INVALID_INFRA
            )
    if len(outcomes) != len(contract.plan_rows) or len(outcomes) != 57:
        return _core.TerminalState.INVALID_INFRA
    return _core.TerminalState.PASS


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "CONTRACT_SCHEMA_VERSION",
    "DEFAULT_CONTRACT_PATH",
    "DEFAULT_PREREGISTRATION_PATH",
    "PREREGISTRATION_SCHEMA_VERSION",
    "RECORD_SCHEMA_VERSION",
    "TASK_ID",
    "V3LoadedContract",
    "compare_record_pair",
    "finalise_plan_terminal",
    "load_preregistered_contract_bundle",
    "observation_to_record",
]
