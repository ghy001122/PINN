"""Record-only comparator for the dormant Phase 1-v2 equivalence-v2 audit.

The module deliberately has no dependency on a candidate, oracle, controller,
solver, runtime-readiness entry point, or formal runner.  It consumes only
plain normalized observation records, a content-addressed contract, and the
mechanically derived field manifest.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_equivalence_v2_executability_closure.yaml"
)
DEFAULT_PREREGISTRATION_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_v2_contract_executability"
    / "preregistration.json"
)
CONTRACT_SCHEMA_VERSION = (
    "geophase_phase1_v2_equivalence_v2_executability_closure_v2"
)
RECORD_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_observation_record_v2"

MANIFEST_COLUMNS = (
    "family",
    "value_kind",
    "field_pattern",
    "denominator_key",
    "category",
    "comparator",
    "minimum_cardinality",
    "maximum_cardinality",
    "required_when",
    "static_cardinality_rule",
    "production_extractors",
    "field_name_origin",
    "raw_schema_origin",
)
ALLOWED_CATEGORY_COMPARATORS = {
    "A_primary_physical": "strict_v1_1e-12",
    "B_exact_topology": "canonical_exact_equality",
    "C_physical_lateral_flux": "parent_analytic_mixed_bound_unchanged",
    "C_lateral_hard_gate": "original_hard_gate_disposition_exact",
    "C_cancellation_roundoff": "parent_backward_error_bound_unchanged",
    "telemetry_nonvoting": "recorded_nonvoting_exact_field_set",
}
ALLOWED_CARDINALITY_RULES = {
    "one_per_observation_when_required_when_condition_holds",
    "one_mapping_entry; contained_sequence_length_is_runtime_contractual",
    "one_per_plan_maximum_accepted_interval; frozen_plan_value=4",
    "trajectory_dependent_fixed-sample records; nonempty required by "
    "_progression_validation_errors; candidate/oracle field sets exact",
    "fixed-time/protocol-discontinuity/event selection dependent; "
    "candidate/oracle field sets exact",
    "zero_or_one_per_path according to path presence and, for failure rows, "
    "integrity-passed-prefix filtering",
}
ALLOWED_PROFILES = {
    "electrical": {"electrical_full"},
    "interval": {"interval_full_accepted", "interval_minimal_rejected"},
    "failure": {
        "failure_at_full_step",
        "failure_at_first_half_step",
        "failure_at_second_half_step",
    },
    "progression": {"progression_full", "progression_NA_no_event_or_reversal"},
}
MANIFEST_HANDLER_BY_CATEGORY = {
    "A_primary_physical": "strict_primary_physical_vote",
    "B_exact_topology": "exact_topology_vote",
    "C_physical_lateral_flux": "analytic_mixed_flux_vote",
    "C_lateral_hard_gate": "lateral_hard_gate_disposition_vote",
    "C_cancellation_roundoff": "analytic_cancellation_vote",
    "telemetry_nonvoting": "nonvoting_structural_validation",
}


class TerminalState(str, Enum):
    PASS = "PASS"
    VALID_FAIL = "VALID_FAIL"
    INVALID_INFRA = "INVALID_INFRA"


class TerminalEvent(str, Enum):
    AUTHORITY_FAILURE = "AUTHORITY_FAILURE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    MANIFEST_IO_FAILURE = "MANIFEST_IO_FAILURE"
    MANIFEST_HASH_FAILURE = "MANIFEST_HASH_FAILURE"
    MANIFEST_PARSE_FAILURE = "MANIFEST_PARSE_FAILURE"
    CONTRACT_FAILURE = "CONTRACT_FAILURE"
    CANONICAL_SERIALIZATION_FAILURE = "CANONICAL_SERIALIZATION_FAILURE"
    EXECUTION_INTEGRITY_FAILURE = "EXECUTION_INTEGRITY_FAILURE"
    RECORD_VALIDATION_FAILURE = "RECORD_VALIDATION_FAILURE"
    FIELD_VOTE_FAILURE = "FIELD_VOTE_FAILURE"
    COMPLETE_PASS = "COMPLETE_PASS"


INFRA_EVENTS = frozenset(
    {
        TerminalEvent.AUTHORITY_FAILURE,
        TerminalEvent.ENVIRONMENT_FAILURE,
        TerminalEvent.MANIFEST_IO_FAILURE,
        TerminalEvent.MANIFEST_HASH_FAILURE,
        TerminalEvent.MANIFEST_PARSE_FAILURE,
        TerminalEvent.CONTRACT_FAILURE,
        TerminalEvent.CANONICAL_SERIALIZATION_FAILURE,
        TerminalEvent.EXECUTION_INTEGRITY_FAILURE,
    }
)
VALID_FAIL_EVENTS = frozenset(
    {TerminalEvent.RECORD_VALIDATION_FAILURE, TerminalEvent.FIELD_VOTE_FAILURE}
)


class ContractInfrastructureError(RuntimeError):
    """Typed pre-record failure; terminal routing never inspects its text."""

    def __init__(self, event: TerminalEvent, message: str) -> None:
        if event not in INFRA_EVENTS:
            raise ValueError("ContractInfrastructureError requires an infra event")
        super().__init__(message)
        self.event = event


@dataclass(frozen=True)
class ManifestTemplate:
    family: str
    value_kind: str
    field_pattern: str
    denominator_key: str
    category: str
    comparator: str
    minimum_cardinality: int
    maximum_cardinality: int
    required_when: str
    static_cardinality_rule: str
    production_extractors: str
    field_name_origin: str
    raw_schema_origin: str
    template_id: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.family, self.value_kind, self.field_pattern)


@dataclass(frozen=True)
class LoadedContract:
    payload: Mapping[str, Any]
    templates: Mapping[tuple[str, str, str], ManifestTemplate]
    template_ids_sha256: str
    plan_rows: Mapping[int, Mapping[str, str]]
    plan_rows_sha256: str


def manifest_handler_assignments(
    contract: LoadedContract,
) -> dict[str, str]:
    """Map every frozen template exactly once to its executable handler."""

    assignments = {
        template.template_id: MANIFEST_HANDLER_BY_CATEGORY[template.category]
        for template in contract.templates.values()
    }
    if len(assignments) != len(contract.templates):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "manifest templates do not have a one-to-one handler assignment",
        )
    return assignments


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        label = "nan" if math.isnan(value) else ("inf" if value > 0.0 else "-inf")
        return {"__nonfinite__": label}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    try:
        payload = _jsonable(value)
        return (
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CANONICAL_SERIALIZATION_FAILURE,
            f"canonical serialization failed: {exc}",
        ) from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_path(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_IO_FAILURE, f"cannot read {path}: {exc}"
        ) from exc


def classify_terminal(event: TerminalEvent) -> TerminalState:
    """Exhaustive, non-overlapping terminal truth table."""

    if event in INFRA_EVENTS:
        return TerminalState.INVALID_INFRA
    if event in VALID_FAIL_EVENTS:
        return TerminalState.VALID_FAIL
    if event is TerminalEvent.COMPLETE_PASS:
        return TerminalState.PASS
    raise AssertionError(f"unclassified terminal event: {event}")


def finalise_plan_terminal(
    *,
    completed_rows: int,
    expected_rows: int,
    all_rows_pass: bool,
    valid_failure_event: TerminalEvent | None = None,
) -> TerminalState:
    if valid_failure_event is not None:
        if valid_failure_event not in VALID_FAIL_EVENTS:
            raise ValueError("valid_failure_event must be a valid-record failure")
        return classify_terminal(valid_failure_event)
    if expected_rows != 57:
        return classify_terminal(TerminalEvent.EXECUTION_INTEGRITY_FAILURE)
    if completed_rows != expected_rows:
        return classify_terminal(TerminalEvent.EXECUTION_INTEGRITY_FAILURE)
    return classify_terminal(
        TerminalEvent.COMPLETE_PASS
        if all_rows_pass
        else TerminalEvent.FIELD_VOTE_FAILURE
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, f"cannot read contract: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, f"cannot parse contract: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "contract must contain a mapping"
        )
    return payload


def _manifest_template_id(row: Mapping[str, str]) -> str:
    return canonical_sha256(
        [row["family"], row["value_kind"], row["field_pattern"]]
    )


def load_field_manifest(
    path: Path, *, expected_sha256: str, expected_rows: int
) -> tuple[dict[tuple[str, str, str], ManifestTemplate], str]:
    if not path.is_file():
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_IO_FAILURE, f"manifest is absent: {path}"
        )
    observed_sha = sha256_path(path)
    if observed_sha != expected_sha256:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_HASH_FAILURE, "manifest SHA-256 mismatch"
        )
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
                raise ValueError("manifest columns differ from the frozen schema")
            raw_rows = list(reader)
    except (OSError, csv.Error, ValueError) as exc:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_PARSE_FAILURE, f"manifest parse failed: {exc}"
        ) from exc
    if len(raw_rows) != expected_rows:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_PARSE_FAILURE,
            f"manifest has {len(raw_rows)} templates, expected {expected_rows}",
        )

    templates: dict[tuple[str, str, str], ManifestTemplate] = {}
    template_ids: list[str] = []
    for index, row in enumerate(raw_rows):
        if None in row or any(row.get(column) is None for column in MANIFEST_COLUMNS):
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"manifest row {index} is structurally invalid",
            )
        family = row["family"]
        kind = row["value_kind"]
        category = row["category"]
        comparator = row["comparator"]
        if family not in ALLOWED_PROFILES or kind not in {"numeric", "exact", "telemetry"}:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"manifest row {index} has an unknown family or kind",
            )
        if ALLOWED_CATEGORY_COMPARATORS.get(category) != comparator:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"manifest row {index} has an unknown category/comparator",
            )
        if row["static_cardinality_rule"] not in ALLOWED_CARDINALITY_RULES:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"manifest row {index} has an unknown cardinality rule",
            )
        required_when = row["required_when"]
        if required_when != "always_in_family":
            if not required_when.startswith("scenario_in:"):
                raise ContractInfrastructureError(
                    TerminalEvent.MANIFEST_PARSE_FAILURE,
                    f"manifest row {index} has an unknown required_when rule",
                )
            profiles = set(required_when.split(":", 1)[1].split("|"))
            if not profiles or not profiles.issubset(ALLOWED_PROFILES[family]):
                raise ContractInfrastructureError(
                    TerminalEvent.MANIFEST_PARSE_FAILURE,
                    f"manifest row {index} names an invalid profile",
                )
        try:
            minimum = int(row["minimum_cardinality"])
            maximum = int(row["maximum_cardinality"])
        except ValueError as exc:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"manifest row {index} has invalid cardinality",
            ) from exc
        if minimum < 0 or maximum < minimum:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"manifest row {index} has inconsistent cardinality",
            )
        template_id = _manifest_template_id(row)
        template = ManifestTemplate(
            family=family,
            value_kind=kind,
            field_pattern=row["field_pattern"],
            denominator_key=row["denominator_key"],
            category=category,
            comparator=comparator,
            minimum_cardinality=minimum,
            maximum_cardinality=maximum,
            required_when=required_when,
            static_cardinality_rule=row["static_cardinality_rule"],
            production_extractors=row["production_extractors"],
            field_name_origin=row["field_name_origin"],
            raw_schema_origin=row["raw_schema_origin"],
            template_id=template_id,
        )
        if template.key in templates:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"duplicate manifest composite key: {template.key}",
            )
        templates[template.key] = template
        template_ids.append(template_id)
    if len(set(template_ids)) != len(template_ids):
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_PARSE_FAILURE, "manifest template IDs are not unique"
        )
    return templates, canonical_sha256(template_ids)


PLAN_MANIFEST_COLUMNS = (
    "plan_index",
    "sample_id",
    "family",
    "state",
    "grid",
    "candidate_paths",
    "failure_class",
    "maximum_accepted_intervals",
    "production_scenarios",
    "mechanical_field_template_count",
    "plan_sha256",
    "execution_dag_sha256",
    "execution_status",
)


def load_plan_manifest(
    path: Path, *, expected_sha256: str, expected_rows: int
) -> tuple[dict[int, dict[str, str]], str]:
    if not path.is_file():
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_IO_FAILURE, f"plan manifest is absent: {path}"
        )
    if sha256_path(path) != expected_sha256:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_HASH_FAILURE, "plan manifest SHA-256 mismatch"
        )
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != PLAN_MANIFEST_COLUMNS:
                raise ValueError("plan manifest columns differ from the frozen schema")
            raw_rows = list(reader)
    except (OSError, csv.Error, ValueError) as exc:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_PARSE_FAILURE,
            f"plan manifest parse failed: {exc}",
        ) from exc
    if len(raw_rows) != expected_rows:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_PARSE_FAILURE,
            f"plan manifest has {len(raw_rows)} rows, expected {expected_rows}",
        )
    rows: dict[int, dict[str, str]] = {}
    for position, row in enumerate(raw_rows):
        try:
            index = int(row["plan_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"plan row {position} has an invalid index",
            ) from exc
        if index != position or index in rows:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                "plan rows are duplicated, missing, or reordered",
            )
        if row["family"] not in ALLOWED_PROFILES:
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"plan row {index} has an unknown family",
            )
        if row["execution_status"] != "static_only_not_executed":
            raise ContractInfrastructureError(
                TerminalEvent.MANIFEST_PARSE_FAILURE,
                f"plan row {index} does not retain static-only status",
            )
        rows[index] = {str(key): str(value) for key, value in row.items()}
    return rows, canonical_sha256(raw_rows)


def _verify_file_record(record: Mapping[str, Any], *, event: TerminalEvent) -> None:
    if not isinstance(record, Mapping):
        raise ContractInfrastructureError(event, "frozen file record is not a mapping")
    path_token = record.get("path")
    expected_sha = record.get("sha256")
    if not isinstance(path_token, str) or not path_token:
        raise ContractInfrastructureError(event, "frozen file path is invalid")
    if (
        not isinstance(expected_sha, str)
        or len(expected_sha) != 64
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None
    ):
        raise ContractInfrastructureError(event, "frozen file SHA-256 is invalid")
    path = ROOT / path_token
    try:
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractInfrastructureError(event, f"cannot read frozen file: {path}") from exc
    if observed != expected_sha:
        raise ContractInfrastructureError(event, f"frozen file drifted: {path}")


def _validate_contract_schema(payload: Mapping[str, Any]) -> None:
    try:
        threshold = float(payload["A_primary_physical"]["threshold"])
        denominators = payload["A_primary_physical"]["normalized_denominators"]
        c_rules = payload["C_lateral_rules"]
        contexts = payload["operator_contexts"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "contract numerical schema is incomplete"
        ) from exc
    expected_denominators = {
        "time_s": 1.0e-9,
        "temperature_K": 7.19,
        "conductive_state": 1.0,
        "branch_memory": 1.0,
        "device_voltage_V": "fixed_protocol_V_scale",
        "potential_V": "fixed_protocol_V_scale",
        "terminal_current_A": 1.0e-12,
        "power_W": 1.0e-30,
        "relative_residual": 1.0,
        "ledger_power_terms": "max_of_all_signed_terms_and_1e-30",
    }
    if threshold != 1.0e-12 or denominators != expected_denominators:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "A-class threshold or denominator identities drifted",
        )
    expected_c_rules = {
        "roundoff_multiplier": 64.0,
        "face_state_factor": 2.0,
        "hard_relative_threshold": 1.0e-10,
        "hard_roundoff_threshold": 1.0,
        "vote_ratio_threshold": 1.0,
    }
    if c_rules != expected_c_rules:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "C-class constants drifted"
        )
    if set(contexts) != {"L1", "L2", "L4"}:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "operator contexts must cover L1/L2/L4"
        )
    expected_context_keys = {
        "shape",
        "g_x_max_W_K",
        "g_y_max_W_K",
        "L_infinity_norm_W_K",
        "n_x_faces",
        "n_y_faces",
    }
    for grid, context in contexts.items():
        if not isinstance(context, Mapping) or set(context) != expected_context_keys:
            raise ContractInfrastructureError(
                TerminalEvent.CONTRACT_FAILURE,
                f"operator context schema differs for {grid}",
            )
        shape = context["shape"]
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or any(not isinstance(item, int) or item <= 0 for item in shape)
        ):
            raise ContractInfrastructureError(
                TerminalEvent.CONTRACT_FAILURE, f"operator shape is invalid for {grid}"
            )
        for key in ("g_x_max_W_K", "g_y_max_W_K", "L_infinity_norm_W_K"):
            value = context[key]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ContractInfrastructureError(
                    TerminalEvent.CONTRACT_FAILURE,
                    f"operator coefficient is invalid for {grid}:{key}",
                )
        for key in ("n_x_faces", "n_y_faces"):
            value = context[key]
            if not isinstance(value, int) or value <= 0:
                raise ContractInfrastructureError(
                    TerminalEvent.CONTRACT_FAILURE,
                    f"operator face count is invalid for {grid}:{key}",
                )


def _load_contract_bundle_from_yaml(path: Path) -> LoadedContract:
    payload = _load_yaml(path)
    if payload.get("task_id") != "Q2_PHASE1_V2_EQUIVALENCE_V2_EXECUTABILITY_CLOSURE":
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "unexpected executability task_id"
        )
    if payload.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "unexpected executability schema"
        )
    if payload.get("status") != "superseding_preregistered_not_authorized_not_executed":
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "executability status is not frozen"
        )
    _validate_contract_schema(payload)
    for record in payload["supersedes"]["immutable_predecessors"].values():
        _verify_file_record(record, event=TerminalEvent.AUTHORITY_FAILURE)
    engine = payload["comparison_engine"]
    _verify_file_record(engine, event=TerminalEvent.AUTHORITY_FAILURE)
    manifest_record = payload["field_manifest"]
    templates, identity_root = load_field_manifest(
        ROOT / manifest_record["path"],
        expected_sha256=manifest_record["sha256"],
        expected_rows=int(manifest_record["parsed_template_count"]),
    )
    if identity_root != manifest_record["composite_identity_root_sha256"]:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_HASH_FAILURE,
            "manifest composite identity root mismatch",
        )
    plan_record = payload["plan_manifest"]
    plan_rows, plan_root = load_plan_manifest(
        ROOT / plan_record["path"],
        expected_sha256=plan_record["sha256"],
        expected_rows=int(plan_record["parsed_plan_count"]),
    )
    if plan_root != plan_record["ordered_rows_identity_sha256"]:
        raise ContractInfrastructureError(
            TerminalEvent.MANIFEST_HASH_FAILURE,
            "plan manifest ordered identity mismatch",
        )
    _validate_partition(payload["ordered_plan_partition"])
    if int(payload["execution_counts"]["equivalence_v2_execution_count"]) != 0:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "equivalence-v2 execution count changed"
        )
    if int(payload["execution_counts"]["formal_execution_count"]) != 0:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "formal execution count changed"
        )
    loaded = LoadedContract(
        payload=payload,
        templates=templates,
        template_ids_sha256=identity_root,
        plan_rows=plan_rows,
        plan_rows_sha256=plan_root,
    )
    assignments = manifest_handler_assignments(loaded)
    if len(assignments) != int(manifest_record["parsed_template_count"]):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "not every manifest template has exactly one handler",
        )
    return loaded


def _load_contract_bundle(path: Path) -> LoadedContract:
    """Private YAML loader used only after external preregistration binding."""

    try:
        return _load_contract_bundle_from_yaml(path)
    except ContractInfrastructureError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            f"contract structure is invalid: {type(exc).__name__}",
        ) from exc


def load_preregistered_contract_bundle(
    path: Path = DEFAULT_PREREGISTRATION_PATH,
) -> LoadedContract:
    """Load the externally content-addressed contract authority envelope.

    The machine preregistration is committed with the contract and pins the
    contract bytes before any future audit may consume its internal records.
    This closes the otherwise circular trust path in which a modified contract
    could simply rewrite its own internal hashes.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            f"cannot read machine preregistration: {exc}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            f"cannot parse machine preregistration: {exc}",
        ) from exc
    if not isinstance(payload, Mapping):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "machine preregistration must contain a mapping",
        )
    expected_schema = (
        "geophase_phase1_v2_equivalence_v2_executability_preregistration_v2"
    )
    if payload.get("schema_version") != expected_schema:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "unexpected machine preregistration schema",
        )
    if payload.get("task_id") != "Q2_PHASE1_V2_EQUIVALENCE_V2_EXECUTABILITY_CLOSURE":
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "unexpected machine preregistration task",
        )
    if payload.get("status") != "ready_contract_only_future_execution_not_authorized":
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "machine preregistration status is not frozen",
        )
    for key in (
        "equivalence_v2_execution_count",
        "equivalence_v2_completed_rows",
        "equivalence_v2_result_artifact_count",
        "formal_execution_count",
        "formal_artifact_count",
    ):
        if payload.get(key) != 0:
            raise ContractInfrastructureError(
                TerminalEvent.CONTRACT_FAILURE,
                f"machine preregistration count changed: {key}",
            )
    if payload.get("numerical_audit_execution_performed") is not False:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "machine preregistration claims a numerical audit execution",
        )
    if payload.get("held_out_execution_performed") is not False:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "machine preregistration claims held-out execution",
        )

    config_record = {
        "path": payload.get("config_path"),
        "sha256": payload.get("config_sha256"),
    }
    _verify_file_record(config_record, event=TerminalEvent.CONTRACT_FAILURE)
    loaded = _load_contract_bundle(ROOT / str(config_record["path"]))

    bindings = {
        "comparison_engine": loaded.payload["comparison_engine"],
        "field_manifest": loaded.payload["field_manifest"],
        "plan_manifest": loaded.payload["plan_manifest"],
    }
    for prefix, record in bindings.items():
        if payload.get(f"{prefix}_path") != record["path"]:
            raise ContractInfrastructureError(
                TerminalEvent.CONTRACT_FAILURE,
                f"machine preregistration path differs: {prefix}",
            )
        if payload.get(f"{prefix}_sha256") != record["sha256"]:
            raise ContractInfrastructureError(
                TerminalEvent.CONTRACT_FAILURE,
                f"machine preregistration SHA differs: {prefix}",
            )
    if payload.get("field_manifest_parsed_template_count") != len(loaded.templates):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "machine preregistration field cardinality differs",
        )
    if payload.get("plan_manifest_parsed_plan_count") != len(loaded.plan_rows):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE,
            "machine preregistration plan cardinality differs",
        )
    return loaded


def _partition_indices(record: Mapping[str, Any]) -> set[int]:
    start = int(record["inclusive_start"])
    end = int(record["inclusive_end"])
    if start < 0 or end < start:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "invalid inclusive plan partition"
        )
    return set(range(start, end + 1))


def _validate_partition(partition: Mapping[str, Any]) -> None:
    development = _partition_indices(partition["metric_development"])
    held_out = _partition_indices(partition["held_out"])
    if len(development) != 12 or len(held_out) != 45:
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "partition cardinality differs"
        )
    if development & held_out or development | held_out != set(range(57)):
        raise ContractInfrastructureError(
            TerminalEvent.CONTRACT_FAILURE, "partition is not an exact disjoint 0..56 cover"
        )


def validate_environment(
    contract: LoadedContract, observed: Mapping[str, Any]
) -> None:
    expected = contract.payload["environment_lock"]
    if _jsonable(observed) != _jsonable(expected):
        raise ContractInfrastructureError(
            TerminalEvent.ENVIRONMENT_FAILURE, "execution environment differs"
        )


def observation_to_record(
    observation: Any,
    *,
    plan_index: int,
    sample_id: str,
    family: str,
    profile_id: str,
    grid_id: str,
    protocol_voltage_scale_V: float,
    maximum_accepted_intervals: int | None = None,
    validation_errors: Sequence[str] = (),
) -> dict[str, Any]:
    """Convert a frozen production observation to a plain canonical envelope."""

    numeric = {
        str(name): {
            "value": _jsonable(field.value),
            "denominator_key": str(field.denominator_key),
            "scale_group": None if field.scale_group is None else str(field.scale_group),
            "is_na": False,
        }
        for name, field in observation.numeric.items()
    }
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "plan_index": int(plan_index),
        "sample_id": str(sample_id),
        "family": str(family),
        "profile_id": str(profile_id),
        "grid_id": str(grid_id),
        "protocol_voltage_scale_V": float(protocol_voltage_scale_V),
        "maximum_accepted_intervals": (
            None
            if maximum_accepted_intervals is None
            else int(maximum_accepted_intervals)
        ),
        "numeric": numeric,
        "exact_votes": _jsonable(observation.exact_votes),
        "telemetry": _jsonable(observation.telemetry),
        "validation_errors": [str(item) for item in validation_errors],
    }


def _contains_invalid_na(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().upper() in {"NA", "N/A", "NOT_APPLICABLE"}
    if isinstance(value, Mapping):
        return any(_contains_invalid_na(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_contains_invalid_na(item) for item in value)
    return False


def _contains_nonfinite(value: Any) -> bool:
    if isinstance(value, Mapping):
        if "__nonfinite__" in value:
            return True
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_contains_nonfinite(item) for item in value)
    if isinstance(value, (float, np.floating)):
        return not math.isfinite(float(value))
    return False


def _validate_exact_semantics(
    name: str, value: Any, *, profile_id: str
) -> list[str]:
    issues: list[str] = []
    if name == "accepted_rejected_sequence":
        if not isinstance(value, list) or not value or any(
            item not in {"accepted", "rejected"} for item in value
        ):
            issues.append("accepted/rejected sequence is malformed")
    elif name in {
        "event_count_direction_and_order",
        "reversal_count_direction_and_order",
    }:
        allowed = (
            {"upward", "downward"}
            if name.startswith("event_")
            else {"heating_to_cooling", "cooling_to_heating"}
        )
        if isinstance(value, list) and any(_contains_invalid_na(item) for item in value):
            issues.append(f"{name} contains invalid NA")
        elif not isinstance(value, list) or any(item not in allowed for item in value):
            issues.append(f"{name} is malformed")
    elif name in {
        "nonlinear_method",
        "converged_disposition",
        "fallback_disposition",
    }:
        if not isinstance(value, list) or not value:
            issues.append(f"{name} must be a nonempty ordered sequence")
        else:
            expected_type = str if name == "nonlinear_method" else bool
            for entry in value:
                if not isinstance(entry, list) or len(entry) not in {2, 3}:
                    issues.append(f"{name} contains a malformed entry")
                    break
                path_index = 1 if len(entry) == 3 else 0
                if len(entry) == 3 and (
                    not isinstance(entry[0], int) or entry[0] < 0
                ):
                    issues.append(f"{name} contains an invalid attempt index")
                    break
                if entry[path_index] not in {
                    "full_step",
                    "first_half_step",
                    "second_half_step",
                }:
                    issues.append(f"{name} contains an invalid path")
                    break
                disposition = entry[path_index + 1]
                allowed_absent = (
                    profile_id == "interval_minimal_rejected"
                    and entry[path_index] in {"first_half_step", "second_half_step"}
                    and disposition is None
                )
                if not allowed_absent and not isinstance(disposition, expected_type):
                    issues.append(f"{name} contains an invalid disposition")
                    break
    elif name == "failure_classification":
        valid = isinstance(value, str) and bool(value)
        if isinstance(value, list):
            valid = (
                len(value) == 3
                and isinstance(value[0], str)
                and isinstance(value[1], bool)
                and isinstance(value[2], list)
                and all(isinstance(item, str) and item for item in value[2])
            )
        if not valid:
            issues.append("failure classification is malformed")
    return issues


def _validate_telemetry_semantics(name: str, value: Any) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not math.isfinite(float(item))
        for item in value
    ):
        return [f"telemetry sequence is malformed: {name}"]
    return []


def _expanded_indices(names: Sequence[str], prefix: str) -> tuple[list[int], bool]:
    indices: list[int] = []
    canonical = True
    expression = re.compile(rf"^{re.escape(prefix)}(\d+)\.")
    for name in names:
        match = expression.match(name)
        if match is None:
            continue
        token = match.group(1)
        if token != str(int(token)):
            canonical = False
        indices.append(int(token))
    return indices, canonical


def _canonical_ledger_scale_group(field_name: str) -> str | None:
    """Derive the only valid ledger denominator group from a field path."""

    match = re.match(
        r"^(?P<prefix>(?:.*\.ledgers|(?:.*\.)?aggregate_ledgers)\."
        r"(?P<ledger>thermal|circuit|combined|device_power))(?:\.|$)",
        field_name,
    )
    if match is None:
        return None
    return f"{match.group('prefix')}:{match.group('ledger')}"


def _validate_record_plan_binding(
    record: Mapping[str, Any], contract: LoadedContract
) -> list[str]:
    issues: list[str] = []
    index = record.get("plan_index")
    if not isinstance(index, int) or index not in contract.plan_rows:
        return ["plan index is not bound to the frozen plan"]
    row = contract.plan_rows[index]
    expected_grid = row["grid"] or "L1"
    expected_maximum = (
        None
        if row["maximum_accepted_intervals"] == ""
        else int(row["maximum_accepted_intervals"])
    )
    for key, expected in (
        ("sample_id", row["sample_id"]),
        ("family", row["family"]),
        ("grid_id", expected_grid),
        ("maximum_accepted_intervals", expected_maximum),
    ):
        if record.get(key) != expected:
            issues.append(f"record {key} differs from frozen plan row")
    if record.get("protocol_voltage_scale_V") != float(
        contract.payload["protocol_voltage_scale_V"]
    ):
        issues.append("record voltage scale differs from frozen contract")
    family = row["family"]
    if family == "failure":
        expected_profile = f"failure_at_{row['candidate_paths']}"
        if record.get("profile_id") != expected_profile:
            issues.append("failure profile differs from frozen plan path")
    return issues


def _normalise_field(name: str) -> str:
    name = re.sub(r"^history\.\d+\.", "history.{interval_index}.", name)
    name = re.sub(
        r"^streaming\.scalar\.\d+\.", "streaming.scalar.{record_index}.", name
    )
    name = re.sub(
        r"^streaming\.snapshot\.\d+\.",
        "streaming.snapshot.{snapshot_index}.",
        name,
    )
    return name


def _required(template: ManifestTemplate, profile_id: str) -> bool:
    if template.required_when == "always_in_family":
        return True
    return profile_id in template.required_when.split(":", 1)[1].split("|")


def _derive_profile(record: Mapping[str, Any]) -> str | None:
    family = record.get("family")
    exact = record.get("exact_votes")
    if not isinstance(exact, Mapping):
        return None
    if family == "electrical":
        return "electrical_full"
    accepted = exact.get("accepted_rejected_sequence")
    failure = exact.get("failure_classification")
    if family == "interval":
        if accepted == ["accepted"]:
            return "interval_full_accepted"
        if accepted == ["rejected"]:
            return "interval_minimal_rejected"
        return None
    if family == "failure":
        if not isinstance(failure, str):
            return None
        for path in ("full_step", "first_half_step", "second_half_step"):
            if failure.startswith(f"injected:{path}:"):
                return f"failure_at_{path}"
        return None
    if family == "progression":
        events = exact.get("event_count_direction_and_order")
        reversals = exact.get("reversal_count_direction_and_order")
        if events == [] and reversals == []:
            return "progression_NA_no_event_or_reversal"
        if isinstance(events, list) and isinstance(reversals, list):
            return "progression_full"
    return None


def _value_array(value: Any) -> np.ndarray:
    if isinstance(value, Mapping) and "__nonfinite__" in value:
        return np.asarray([math.nan], dtype=float)
    try:
        return np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"numeric value is not array-like: {exc}") from exc


def _record_fields(
    record: Mapping[str, Any], contract: LoadedContract
) -> tuple[dict[tuple[str, str, str], list[str]], list[str]]:
    issues: list[str] = []
    allowed_keys = {
        "schema_version",
        "plan_index",
        "sample_id",
        "family",
        "profile_id",
        "grid_id",
        "protocol_voltage_scale_V",
        "maximum_accepted_intervals",
        "numeric",
        "exact_votes",
        "telemetry",
        "validation_errors",
    }
    actual_keys = set(record)
    if actual_keys != allowed_keys:
        issues.append(
            "record envelope differs: "
            f"missing={sorted(allowed_keys-actual_keys)},extra={sorted(actual_keys-allowed_keys)}"
        )
        return {}, issues
    if not isinstance(record.get("exact_votes"), Mapping):
        issues.append("exact_votes must be a mapping")
    if not isinstance(record.get("numeric"), Mapping):
        issues.append("numeric must be a mapping")
    if not isinstance(record.get("telemetry"), Mapping):
        issues.append("telemetry must be a mapping")
    if not isinstance(record.get("validation_errors"), list) or any(
        not isinstance(item, str) for item in record.get("validation_errors", ())
    ):
        issues.append("validation_errors must be a list of strings")
    if issues:
        return {}, issues
    if record["schema_version"] != RECORD_SCHEMA_VERSION:
        issues.append("record schema version differs")
    family = record["family"]
    profile = record["profile_id"]
    if not isinstance(family, str) or not isinstance(profile, str):
        issues.append("family/profile metadata must be strings")
        return {}, issues
    if family not in ALLOWED_PROFILES or profile not in ALLOWED_PROFILES[family]:
        issues.append("family/profile is not registered")
    if _derive_profile(record) != profile:
        issues.append("profile does not match extracted topology")
    if (
        not isinstance(record["plan_index"], int)
        or isinstance(record["plan_index"], bool)
        or not 0 <= record["plan_index"] <= 56
    ):
        issues.append("plan index is outside 0..56")
    if not isinstance(record["sample_id"], str) or not record["sample_id"]:
        issues.append("sample_id is absent")
    grid_id = record["grid_id"]
    if not isinstance(grid_id, str) or grid_id not in contract.payload["operator_contexts"]:
        issues.append("grid_id is not registered")
    if family == "failure" and grid_id != "L1":
        issues.append("failure rows must use frozen L1 operator context")
    if family == "progression" and record["maximum_accepted_intervals"] != 4:
        issues.append("progression maximum accepted intervals must equal four")
    if family != "progression" and record["maximum_accepted_intervals"] is not None:
        issues.append("maximum accepted intervals is only valid for progression")
    scale = record["protocol_voltage_scale_V"]
    if (
        not isinstance(scale, (int, float))
        or isinstance(scale, bool)
        or not math.isfinite(scale)
        or scale <= 0.0
    ):
        issues.append("protocol voltage scale must be positive and finite")
    if record["validation_errors"]:
        issues.append("record contains validation errors")
    issues.extend(_validate_record_plan_binding(record, contract))

    observed: dict[tuple[str, str, str], list[str]] = {}
    for kind, key in (
        ("numeric", "numeric"),
        ("exact", "exact_votes"),
        ("telemetry", "telemetry"),
    ):
        mapping = record[key]
        if not isinstance(mapping, Mapping):
            issues.append(f"{key} must be a mapping")
            continue
        for actual_name, value in mapping.items():
            if not isinstance(actual_name, str) or not actual_name:
                issues.append(f"{kind} field name must be a nonempty string")
                continue
            pattern = _normalise_field(str(actual_name))
            manifest_key = (family, kind, pattern)
            template = contract.templates.get(manifest_key)
            if template is None:
                issues.append(f"unregistered {kind} field: {actual_name}")
                continue
            observed.setdefault(manifest_key, []).append(str(actual_name))
            if kind == "numeric":
                if not isinstance(value, Mapping):
                    issues.append(f"numeric field is not a mapping: {actual_name}")
                    continue
                expected_numeric_keys = {
                    "value",
                    "denominator_key",
                    "scale_group",
                    "is_na",
                }
                if set(value) != expected_numeric_keys:
                    issues.append(f"numeric field schema differs: {actual_name}")
                    continue
                if value["is_na"] is not False:
                    issues.append(f"numeric NA is invalid: {actual_name}")
                if not isinstance(value["denominator_key"], str):
                    issues.append(f"numeric denominator is invalid: {actual_name}")
                if value["scale_group"] is not None and not isinstance(
                    value["scale_group"], str
                ):
                    issues.append(f"numeric scale_group is invalid: {actual_name}")
                if value["denominator_key"] != template.denominator_key:
                    issues.append(f"denominator identity differs: {actual_name}")
                expected_group = (
                    _canonical_ledger_scale_group(actual_name)
                    if template.denominator_key == "ledger_power_terms"
                    else None
                )
                if value["scale_group"] != expected_group:
                    issues.append(f"canonical scale_group differs: {actual_name}")
                try:
                    array = _value_array(value["value"])
                    if array.size == 0 or not np.isfinite(array).all():
                        issues.append(f"numeric field is empty or nonfinite: {actual_name}")
                except ValueError:
                    issues.append(f"numeric field is not valid: {actual_name}")
            elif kind == "exact":
                if _contains_nonfinite(value):
                    issues.append(f"exact topology contains nonfinite value: {actual_name}")
                issues.extend(
                    _validate_exact_semantics(
                        actual_name, value, profile_id=str(profile)
                    )
                )
            else:
                if _contains_invalid_na(value):
                    issues.append(f"telemetry contains invalid NA: {actual_name}")
                if _contains_nonfinite(value):
                    issues.append(f"telemetry contains nonfinite value: {actual_name}")
                issues.extend(_validate_telemetry_semantics(actual_name, value))

    if family in ALLOWED_PROFILES:
        for template in contract.templates.values():
            if template.family != family:
                continue
            names = observed.get(template.key, [])
            active = _required(template, profile)
            rule = template.static_cardinality_rule
            if not active:
                expected_ok = len(names) == 0
            elif rule == "one_per_plan_maximum_accepted_interval; frozen_plan_value=4":
                expected_ok = len(names) == 4
            elif rule.startswith("trajectory_dependent_fixed-sample records"):
                expected_ok = len(names) >= 1
            elif rule.startswith("fixed-time/protocol-discontinuity/event selection dependent"):
                expected_ok = len(names) >= template.minimum_cardinality
            else:
                expected_ok = len(names) == template.maximum_cardinality
            if not expected_ok:
                issues.append(
                    f"cardinality differs for {template.template_id}: observed={len(names)}"
                )
        history_names = [
            name
            for names in observed.values()
            for name in names
            if name.startswith("history.")
        ]
        history_indices, history_canonical = _expanded_indices(history_names, "history.")
        if history_names:
            expected_history = set(range(int(record["maximum_accepted_intervals"])))
            if not history_canonical or set(history_indices) != expected_history:
                issues.append("history indices are noncanonical, gapped, or incomplete")
        for prefix in ("streaming.scalar.", "streaming.snapshot."):
            expanded = [
                name
                for names in observed.values()
                for name in names
                if name.startswith(prefix)
            ]
            indices, canonical = _expanded_indices(expanded, prefix)
            if expanded and (
                not canonical
                or set(indices) != set(range(max(indices) + 1))
            ):
                issues.append(f"{prefix} indices are noncanonical or gapped")
    return observed, issues


def _maximum_absolute(array: np.ndarray) -> float:
    return float(np.max(np.abs(array)))


def _numeric_denominator(
    candidate_field: Mapping[str, Any],
    oracle_field: Mapping[str, Any],
    *,
    contract: LoadedContract,
    protocol_voltage_scale_V: float,
    ledger_scales: Mapping[str, float],
) -> float:
    key = candidate_field["denominator_key"]
    configured = contract.payload["A_primary_physical"]["normalized_denominators"][key]
    if configured == "fixed_protocol_V_scale":
        floor = protocol_voltage_scale_V
    elif configured == "max_of_all_signed_terms_and_1e-30":
        group = candidate_field["scale_group"]
        if not group or oracle_field["scale_group"] != group:
            return math.nan
        return float(ledger_scales.get(str(group), math.nan))
    else:
        floor = float(configured)
    candidate = _value_array(candidate_field["value"])
    oracle = _value_array(oracle_field["value"])
    return max(floor, _maximum_absolute(candidate), _maximum_absolute(oracle))


def _ledger_scales(
    candidate: Mapping[str, Any], oracle: Mapping[str, Any]
) -> dict[str, float]:
    scales: dict[str, float] = {}
    for name, field in candidate["numeric"].items():
        if field["denominator_key"] != "ledger_power_terms" or name not in oracle["numeric"]:
            continue
        other = oracle["numeric"][name]
        group = field["scale_group"]
        if not group or other["scale_group"] != group:
            continue
        maximum = max(
            _maximum_absolute(_value_array(field["value"])),
            _maximum_absolute(_value_array(other["value"])),
            1.0e-30,
        )
        scales[str(group)] = max(scales.get(str(group), 1.0e-30), maximum)
    return scales


def _field_difference(
    candidate_field: Mapping[str, Any], oracle_field: Mapping[str, Any]
) -> float:
    candidate = _value_array(candidate_field["value"])
    oracle = _value_array(oracle_field["value"])
    if candidate.shape != oracle.shape or candidate.size == 0:
        return math.inf
    return _maximum_absolute(candidate - oracle)


def _strict_vote(
    name: str,
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    contract: LoadedContract,
    ledger_scales: Mapping[str, float],
) -> dict[str, Any]:
    candidate_field = candidate["numeric"][name]
    oracle_field = oracle["numeric"][name]
    denominator = _numeric_denominator(
        candidate_field,
        oracle_field,
        contract=contract,
        protocol_voltage_scale_V=float(candidate["protocol_voltage_scale_V"]),
        ledger_scales=ledger_scales,
    )
    difference = _field_difference(candidate_field, oracle_field)
    ratio = difference / denominator if denominator > 0.0 else math.inf
    threshold = float(contract.payload["A_primary_physical"]["threshold"])
    return {
        "field": name,
        "category": "A_primary_physical",
        "maximum_absolute_difference": difference,
        "bound": denominator * threshold,
        "ratio": ratio / threshold,
        "passed": bool(math.isfinite(ratio) and ratio <= threshold),
    }


def _temperature_name_for_lateral(name: str) -> str:
    return name.split(".lateral.", 1)[0] + ".state.temperature_K"


def _q_scale(
    name: str, candidate: Mapping[str, Any], oracle: Mapping[str, Any]
) -> float:
    return max(
        1.0e-30,
        _maximum_absolute(_value_array(candidate["numeric"][name]["value"])),
        _maximum_absolute(_value_array(oracle["numeric"][name]["value"])),
    )


def _physical_flux_vote(
    name: str,
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    contract: LoadedContract,
    ledger_scales: Mapping[str, float],
) -> dict[str, Any]:
    temperature_name = _temperature_name_for_lateral(name)
    if temperature_name not in candidate["numeric"] or temperature_name not in oracle["numeric"]:
        return {
            "field": name,
            "category": "C_physical_lateral_flux",
            "bound": 0.0,
            "ratio": math.inf,
            "passed": False,
            "reason": "paired temperature field is absent",
        }
    temperature_candidate = candidate["numeric"][temperature_name]
    temperature_oracle = oracle["numeric"][temperature_name]
    delta_temperature = _field_difference(temperature_candidate, temperature_oracle)
    temperature_scale = _numeric_denominator(
        temperature_candidate,
        temperature_oracle,
        contract=contract,
        protocol_voltage_scale_V=float(candidate["protocol_voltage_scale_V"]),
        ledger_scales=ledger_scales,
    )
    operators = contract.payload["operator_contexts"][candidate["grid_id"]]
    face_state_factor = float(
        contract.payload["C_lateral_rules"]["face_state_factor"]
    )
    if name.endswith(".lateral.x_face_flux_W"):
        operator = float(operators["g_x_max_W_K"])
        propagation = face_state_factor * operator * delta_temperature
    elif name.endswith(".lateral.y_face_flux_W"):
        operator = float(operators["g_y_max_W_K"])
        propagation = face_state_factor * operator * delta_temperature
    elif name.endswith(".lateral.net_cell_outflow_W"):
        operator = float(operators["L_infinity_norm_W_K"])
        propagation = operator * delta_temperature
    else:
        return {
            "field": name,
            "category": "C_physical_lateral_flux",
            "bound": 0.0,
            "ratio": math.inf,
            "passed": False,
            "reason": "unknown physical lateral suffix",
        }
    q_scale = _q_scale(name, candidate, oracle)
    roundoff = float(contract.payload["C_lateral_rules"]["roundoff_multiplier"]) * np.finfo(float).eps * max(
        operator * temperature_scale, q_scale
    )
    bound = propagation + roundoff
    difference = _field_difference(candidate["numeric"][name], oracle["numeric"][name])
    ratio = difference / max(bound, 1.0e-300)
    return {
        "field": name,
        "category": "C_physical_lateral_flux",
        "maximum_absolute_difference": difference,
        "state_propagation_bound": propagation,
        "roundoff_bound": roundoff,
        "bound": bound,
        "ratio": ratio,
        "passed": bool(math.isfinite(ratio) and ratio <= 1.0),
    }


def _row_flux_scales(
    candidate: Mapping[str, Any], oracle: Mapping[str, Any]
) -> tuple[float, float]:
    x_names = [name for name in candidate["numeric"] if name.endswith(".lateral.x_face_flux_W")]
    y_names = [name for name in candidate["numeric"] if name.endswith(".lateral.y_face_flux_W")]
    if not x_names or not y_names or set(x_names) != {
        name for name in oracle["numeric"] if name.endswith(".lateral.x_face_flux_W")
    } or set(y_names) != {
        name for name in oracle["numeric"] if name.endswith(".lateral.y_face_flux_W")
    }:
        return math.nan, math.nan
    return max(_q_scale(name, candidate, oracle) for name in x_names), max(
        _q_scale(name, candidate, oracle) for name in y_names
    )


def _cancellation_vote(
    name: str,
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    contract: LoadedContract,
) -> dict[str, Any]:
    if ".lateral." in name:
        prefix = name.split(".lateral.", 1)[0]
        x_name = prefix + ".lateral.x_face_flux_W"
        y_name = prefix + ".lateral.y_face_flux_W"
        if x_name not in candidate["numeric"] or y_name not in candidate["numeric"]:
            x_scale = y_scale = math.nan
        else:
            x_scale = _q_scale(x_name, candidate, oracle)
            y_scale = _q_scale(y_name, candidate, oracle)
    else:
        x_scale, y_scale = _row_flux_scales(candidate, oracle)
    operators = contract.payload["operator_contexts"][candidate["grid_id"]]
    bound = (
        float(contract.payload["C_lateral_rules"]["roundoff_multiplier"])
        * np.finfo(float).eps
        * float(contract.payload["C_lateral_rules"]["face_state_factor"])
        * (
            float(operators["n_x_faces"]) * x_scale
            + float(operators["n_y_faces"]) * y_scale
        )
    )
    difference = _field_difference(candidate["numeric"][name], oracle["numeric"][name])
    ratio = difference / max(bound, 1.0e-300)
    return {
        "field": name,
        "category": "C_cancellation_roundoff",
        "maximum_absolute_difference": difference,
        "bound": bound,
        "ratio": ratio,
        "passed": bool(math.isfinite(ratio) and ratio <= 1.0),
    }


def _hard_gate_groups(names: Sequence[str]) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {}
    pairs = (
        (
            ".lateral.matrix_face_relative_mismatch",
            ".lateral.matrix_face_roundoff_ratio",
            ".lateral.matrix_face",
        ),
        (
            ".lateral_matrix_face_relative_mismatch",
            ".lateral_matrix_face_roundoff_ratio",
            ".lateral_matrix_face",
        ),
        (
            ".full_lateral_relative_mismatch",
            ".full_lateral_roundoff_ratio",
            ".full_lateral",
        ),
        (
            ".first_half_lateral_relative_mismatch",
            ".first_half_lateral_roundoff_ratio",
            ".first_half_lateral",
        ),
        (
            ".second_half_lateral_relative_mismatch",
            ".second_half_lateral_roundoff_ratio",
            ".second_half_lateral",
        ),
    )
    for name in names:
        for relative, roundoff, group_suffix in pairs:
            if name.endswith(relative):
                prefix = name[: -len(relative)]
                groups.setdefault(prefix + group_suffix, {})["relative"] = name
            if name.endswith(roundoff):
                prefix = name[: -len(roundoff)]
                groups.setdefault(prefix + group_suffix, {})["roundoff"] = name
    return groups


def _hard_gate_votes(
    names: Sequence[str],
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    contract: LoadedContract,
) -> list[dict[str, Any]]:
    votes: list[dict[str, Any]] = []
    for group, fields in sorted(_hard_gate_groups(names).items()):
        if set(fields) != {"relative", "roundoff"}:
            votes.append(
                {
                    "field": group,
                    "category": "C_lateral_hard_gate",
                    "passed": False,
                    "reason": "hard-gate metric pair is incomplete",
                }
            )
            continue
        relative = fields["relative"]
        roundoff = fields["roundoff"]
        candidate_relative = _maximum_absolute(
            _value_array(candidate["numeric"][relative]["value"])
        )
        candidate_roundoff = _maximum_absolute(
            _value_array(candidate["numeric"][roundoff]["value"])
        )
        oracle_relative = _maximum_absolute(
            _value_array(oracle["numeric"][relative]["value"])
        )
        oracle_roundoff = _maximum_absolute(
            _value_array(oracle["numeric"][roundoff]["value"])
        )
        relative_threshold = float(
            contract.payload["C_lateral_rules"]["hard_relative_threshold"]
        )
        roundoff_threshold = float(
            contract.payload["C_lateral_rules"]["hard_roundoff_threshold"]
        )
        candidate_pass = (
            candidate_relative <= relative_threshold
            or candidate_roundoff <= roundoff_threshold
        )
        oracle_pass = (
            oracle_relative <= relative_threshold
            or oracle_roundoff <= roundoff_threshold
        )
        votes.append(
            {
                "field": group,
                "category": "C_lateral_hard_gate",
                "candidate_disposition": bool(candidate_pass),
                "oracle_disposition": bool(oracle_pass),
                "source_fields": [relative, roundoff],
                "passed": bool(
                    candidate_pass and oracle_pass and candidate_pass == oracle_pass
                ),
            }
        )
    return votes


def compare_record_pair(
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    contract: LoadedContract,
) -> dict[str, Any]:
    """Return a content-addressed row decision without running any solver."""

    candidate_sha = canonical_sha256(candidate)
    oracle_sha = canonical_sha256(oracle)
    candidate_fields, candidate_issues = _record_fields(candidate, contract)
    oracle_fields, oracle_issues = _record_fields(oracle, contract)
    issues = list(candidate_issues) + list(oracle_issues)
    for key in (
        "plan_index",
        "sample_id",
        "family",
        "profile_id",
        "grid_id",
        "protocol_voltage_scale_V",
        "maximum_accepted_intervals",
    ):
        if candidate.get(key) != oracle.get(key):
            issues.append(f"candidate/oracle metadata differs: {key}")
    if set(candidate_fields) != set(oracle_fields):
        issues.append("candidate/oracle manifest template sets differ")
    for key in set(candidate_fields) & set(oracle_fields):
        if set(candidate_fields[key]) != set(oracle_fields[key]):
            issues.append(f"candidate/oracle expanded field sets differ: {key}")
    if issues:
        payload = {
            "record_status": "invalid_content",
            "row_pass": False,
            "failure_event": TerminalEvent.RECORD_VALIDATION_FAILURE.value,
            "issues": sorted(set(issues)),
            "votes": [],
            "candidate_record_sha256": candidate_sha,
            "oracle_record_sha256": oracle_sha,
        }
        payload["comparison_sha256"] = canonical_sha256(payload)
        return payload

    ledger_scales = _ledger_scales(candidate, oracle)
    votes: list[dict[str, Any]] = []
    hard_names: list[str] = []
    active_template_ids: set[str] = set()
    for name in sorted(candidate["numeric"]):
        template = contract.templates[
            (candidate["family"], "numeric", _normalise_field(name))
        ]
        active_template_ids.add(template.template_id)
        if template.category == "A_primary_physical":
            vote = _strict_vote(name, candidate, oracle, contract, ledger_scales)
            vote["template_ids"] = [template.template_id]
            votes.append(vote)
        elif template.category == "C_physical_lateral_flux":
            vote = _physical_flux_vote(
                name, candidate, oracle, contract, ledger_scales
            )
            vote["template_ids"] = [template.template_id]
            votes.append(vote)
        elif template.category == "C_cancellation_roundoff":
            vote = _cancellation_vote(name, candidate, oracle, contract)
            vote["template_ids"] = [template.template_id]
            votes.append(vote)
        elif template.category == "C_lateral_hard_gate":
            hard_names.append(name)
        else:
            raise AssertionError(f"numeric template is not executable: {template.category}")
    hard_votes = _hard_gate_votes(hard_names, candidate, oracle, contract)
    for vote in hard_votes:
        matched = sorted(
            contract.templates[
                (candidate["family"], "numeric", _normalise_field(name))
            ].template_id
            for name in vote.get("source_fields", ())
        )
        vote["template_ids"] = matched
    votes.extend(hard_votes)

    for name in sorted(candidate["exact_votes"]):
        template = contract.templates[
            (candidate["family"], "exact", _normalise_field(name))
        ]
        active_template_ids.add(template.template_id)
        passed = canonical_json_bytes(candidate["exact_votes"][name]) == canonical_json_bytes(
            oracle["exact_votes"][name]
        )
        votes.append(
            {
                "field": name,
                "category": "B_exact_topology",
                "template_ids": [template.template_id],
                "passed": bool(passed),
            }
        )
    telemetry_template_ids = sorted(
        {
            contract.templates[
                (candidate["family"], "telemetry", _normalise_field(name))
            ].template_id
            for name in candidate["telemetry"]
        }
    )
    active_template_ids.update(telemetry_template_ids)
    voted_template_ids = {
        template_id
        for vote in votes
        for template_id in vote.get("template_ids", ())
    }
    if not voted_template_ids.issubset(active_template_ids):
        raise AssertionError("a vote consumed a template outside the active record")
    row_pass = all(bool(vote["passed"]) for vote in votes)
    consumption_pass = bool(
        active_template_ids == voted_template_ids.union(telemetry_template_ids)
    )
    row_pass = bool(row_pass and consumption_pass)
    payload = {
        "record_status": "auditable",
        "row_pass": row_pass,
        "failure_event": (
            None if row_pass else TerminalEvent.FIELD_VOTE_FAILURE.value
        ),
        "issues": [],
        "votes": votes,
        "template_consumption": {
            "active_template_ids": sorted(active_template_ids),
            "voting_template_ids": sorted(voted_template_ids),
            "telemetry_template_ids": telemetry_template_ids,
            "all_active_templates_consumed_once": bool(
                consumption_pass
            ),
        },
        "candidate_record_sha256": candidate_sha,
        "oracle_record_sha256": oracle_sha,
    }
    payload["comparison_sha256"] = canonical_sha256(payload)
    return payload


def seal_synthetic_fixture(
    *,
    fixture_id: str,
    comparison: Mapping[str, Any],
    synthetic_plan_outcomes: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    event_value = comparison.get("failure_event")
    outcomes = list(synthetic_plan_outcomes or ())
    expected_outcome_keys = {"plan_index", "row_pass"}
    complete_index_cover = bool(
        len(outcomes) == 57
        and all(
            isinstance(outcome, Mapping)
            and set(outcome) == expected_outcome_keys
            and outcome.get("plan_index") == index
            and isinstance(outcome.get("row_pass"), bool)
            for index, outcome in enumerate(outcomes)
        )
    )
    all_rows_pass = bool(
        complete_index_cover
        and all(outcome["row_pass"] is True for outcome in outcomes)
    )
    if event_value is None:
        if not complete_index_cover:
            terminal = classify_terminal(TerminalEvent.EXECUTION_INTEGRITY_FAILURE)
        else:
            terminal = finalise_plan_terminal(
                completed_rows=len(outcomes),
                expected_rows=57,
                all_rows_pass=bool(comparison["row_pass"] and all_rows_pass),
            )
    else:
        terminal = classify_terminal(TerminalEvent(str(event_value)))
    failed_votes = [
        vote
        for vote in comparison.get("votes", ())
        if isinstance(vote, Mapping) and vote.get("passed") is False
    ]
    payload = {
        "fixture_id": fixture_id,
        "evidence_type": "synthetic_contract_evidence_nonvoting",
        "audit_row_count": 0,
        "synthetic_terminal_truth_table_count": len(outcomes),
        "synthetic_terminal_truth_table_sha256": (
            canonical_sha256(outcomes) if outcomes else None
        ),
        "synthetic_terminal_truth_table_complete_index_cover": complete_index_cover,
        "synthetic_terminal_truth_table_all_rows_pass": all_rows_pass,
        "failure_event": event_value,
        "failed_categories": sorted(
            {str(vote.get("category")) for vote in failed_votes}
        ),
        "failed_fields": sorted(
            {str(vote.get("field")) for vote in failed_votes}
        ),
        "issues": sorted(str(item) for item in comparison.get("issues", ())),
        "candidate_record_sha256": comparison.get("candidate_record_sha256"),
        "oracle_record_sha256": comparison.get("oracle_record_sha256"),
        "comparison_sha256": comparison.get("comparison_sha256"),
        "terminal_state": terminal.value,
    }
    payload["fixture_sha256"] = canonical_sha256(payload)
    return payload
