"""Strict implementation-equivalence support for the Phase 1-v2 repair.

This module contains only the deterministic plan, comparison, hashing, and
per-file atomic publication primitives needed by the separately authorized
performance-equivalence audit.  It deliberately does not import the historical
PR8 oracle or expose a production ``legacy`` execution mode.  Tests (and only
tests) may inject that oracle as a low-level electrical callable.
"""

from __future__ import annotations

import csv
from contextlib import ExitStack, contextmanager
import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, is_dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_source_corrected_performance_repair.yaml"
)
SCHEMA_VERSION = "geophase_phase1_v2_performance_equivalence_v1"

EXPECTED_DENOMINATORS = {
    "time_s",
    "temperature_K",
    "conductive_state",
    "branch_memory",
    "device_voltage_V",
    "potential_V",
    "terminal_current_A",
    "power_W",
    "relative_residual",
    "ledger_power_terms",
}
EXPECTED_EXACT_VOTES = (
    "nonlinear_method",
    "converged_disposition",
    "fallback_disposition",
    "accepted_rejected_sequence",
    "failure_classification",
    "event_count_direction_and_order",
    "reversal_count_direction_and_order",
)
EXPECTED_TELEMETRY = (
    "Newton_iterations",
    "Krylov_matvecs",
    "Armijo_backtracks",
    "Picard_iterations",
    "fallback_iterations",
)
EXPECTED_FAILURE_CLASSES = (
    "nonfinite",
    "nonlinear_convergence",
    "lateral_audit",
    "thermal_ledger",
    "circuit_ledger",
    "combined_ledger",
    "device_power_identity",
)
EXPECTED_PATHS = ("full_step", "first_half_step", "second_half_step")
FAMILY_ORDER = ("electrical", "interval", "progression", "failure")


@dataclass(frozen=True)
class EquivalenceContract:
    """Machine-checked subset of the performance preregistration."""

    config_path: Path
    config_sha256: str
    normalized_relative_difference_max: float
    denominators: Mapping[str, float | str]
    exact_votes: tuple[str, ...]
    telemetry_only: tuple[str, ...]
    electrical_states: tuple[str, ...]
    electrical_grids: tuple[str, ...]
    interval_states: tuple[str, ...]
    interval_grids: tuple[str, ...]
    interval_classes: tuple[str, ...]
    interval_paths: tuple[str, ...]
    progression_states: tuple[str, ...]
    progression_grids: tuple[str, ...]
    progression_maximum_accepted_intervals: int
    failure_paths: tuple[str, ...]
    failure_classes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    terminal_failure_disposition: str

    @property
    def expected_total(self) -> int:
        return int(sum(self.expected_counts.values()))


@dataclass(frozen=True)
class EquivalencePlanRow:
    """One deterministic comparison plan row, not an executed sample."""

    plan_index: int
    sample_id: str
    family: str
    state: str | None
    grid: str | None
    interval_class: str | None
    candidate_paths: tuple[str, ...]
    failure_class: str | None
    maximum_accepted_intervals: int | None
    input_sha256: str


@dataclass(frozen=True)
class NumericField:
    """A numeric comparison value and its preregistered scale identity."""

    value: Any
    denominator_key: str
    scale_group: str | None = None


@dataclass(frozen=True)
class EquivalenceObservation:
    """Implementation output normalized to numeric, exact, and telemetry data."""

    numeric: Mapping[str, NumericField]
    exact_votes: Mapping[str, Any]
    telemetry: Mapping[str, Any]


@dataclass(frozen=True)
class NumericComparison:
    field: str
    denominator_key: str
    denominator: float
    maximum_absolute_difference: float
    maximum_normalized_difference: float
    passed: bool
    reason: str | None


@dataclass(frozen=True)
class EquivalenceComparison:
    passed: bool
    tolerance: float
    maximum_normalized_difference: float
    worst_field: str | None
    numeric: tuple[NumericComparison, ...]
    exact_mismatches: Mapping[str, Mapping[str, Any]]
    telemetry: Mapping[str, Mapping[str, Any]]
    validation_errors: tuple[str, ...]


@dataclass(frozen=True)
class ElectricalPairResult:
    """Independent candidate/oracle electrical outputs and their comparison."""

    candidate: Any
    oracle: Any
    comparison: EquivalenceComparison


@dataclass(frozen=True)
class EquivalenceEvidenceRow:
    plan_index: int
    sample_id: str
    family: str
    plan_sha256: str
    input_sha256: str
    output_sha256: str
    passed: bool
    maximum_normalized_difference: float
    worst_field: str | None
    exact_mismatch_count: int
    numeric_details: tuple[Mapping[str, Any], ...]
    exact_mismatches: Mapping[str, Mapping[str, Any]]
    telemetry: Mapping[str, Any]
    validation_errors: tuple[str, ...]


@dataclass(frozen=True)
class DeterministicAuditCase:
    """One source-corrected state/grid/protocol input for a real audit row."""

    state_id: str
    grid_id: str
    grid: Any
    closure: Any
    fields: Any
    initial_state: Any
    protocol_id: str
    protocol: Mapping[str, Any]
    protocol_voltage_scale_V: float


@dataclass(frozen=True)
class PairExecution:
    """Raw candidate/oracle observations returned by one real row executor."""

    candidate_observation: EquivalenceObservation
    oracle_observation: EquivalenceObservation
    candidate_raw: Any
    oracle_raw: Any
    protocol_voltage_scale_V: float
    validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class EquivalenceAuditResult:
    """In-memory four-table audit result; publication is explicit and optional."""

    rows: tuple[EquivalenceEvidenceRow, ...]
    tables: Mapping[str, str]
    summary: Mapping[str, Any]
    published_paths: Mapping[str, str]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _jsonable(value: Any) -> Any:
    """Return a stable JSON representation, including explicit nonfinite tags."""

    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NONFINITE_NAN"
        return "NONFINITE_POSITIVE_INFINITY" if value > 0.0 else "NONFINITE_NEGATIVE_INFINITY"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Hash a stable JSON representation of an input or output payload."""

    return _sha256_bytes(canonical_json_bytes(value))


def _require_tuple(mapping: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{key} must be a non-empty list of strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{key} contains duplicates")
    return tuple(value)


def load_equivalence_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> EquivalenceContract:
    """Load and fail closed on drift in the preregistered audit semantics."""

    payload_bytes = path.read_bytes()
    payload = yaml.safe_load(payload_bytes.decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("performance preregistration must contain a mapping")
    if payload.get("task_id") != "PHASE1_V2_SOURCE_CORRECTED_PERFORMANCE_CLOSURE":
        raise ValueError("unexpected performance preregistration task_id")
    if payload.get("schema_version") != (
        "geophase_phase1_v2_source_corrected_performance_repair_v1"
    ):
        raise ValueError("unexpected performance preregistration schema_version")

    audit = payload.get("equivalence_audit")
    if not isinstance(audit, dict):
        raise TypeError("equivalence_audit must contain a mapping")
    tolerance = float(audit.get("normalized_relative_difference_max", math.nan))
    if tolerance != 1.0e-12:
        raise ValueError("equivalence tolerance must remain exactly 1e-12")

    denominators = audit.get("normalized_denominators")
    if not isinstance(denominators, dict) or set(denominators) != EXPECTED_DENOMINATORS:
        raise ValueError("normalized denominator keys no longer match the contract")
    for key, value in denominators.items():
        if key in {"device_voltage_V", "potential_V"}:
            if value != "fixed_protocol_V_scale":
                raise ValueError(f"{key} must use fixed_protocol_V_scale")
        elif key == "ledger_power_terms":
            if value != "max_of_all_signed_terms_and_1e-30":
                raise ValueError("ledger scale expression changed")
        elif not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"{key} must be a positive finite SI floor")

    exact_votes = _require_tuple(audit, "exact_votes")
    telemetry_only = _require_tuple(audit, "telemetry_only_nonvoting")
    if exact_votes != EXPECTED_EXACT_VOTES:
        raise ValueError("exact-vote list or ordering changed")
    if telemetry_only != EXPECTED_TELEMETRY:
        raise ValueError("telemetry-only list or ordering changed")
    if set(exact_votes).intersection(telemetry_only):
        raise ValueError("exact votes and telemetry-only fields must be disjoint")

    electrical = audit["electrical_matrix"]
    interval = audit["interval_matrix"]
    progression = audit["short_progression_matrix"]
    failure = audit["failure_injection_matrix"]
    electrical_states = _require_tuple(electrical, "states")
    electrical_grids = _require_tuple(electrical, "grids")
    interval_states = _require_tuple(interval, "states")
    interval_grids = _require_tuple(interval, "grids")
    interval_classes = _require_tuple(interval, "interval_classes")
    interval_paths = _require_tuple(interval, "paths")
    progression_states = _require_tuple(progression, "states")
    progression_grids = _require_tuple(progression, "grids")
    failure_paths = _require_tuple(failure, "paths")
    failure_classes = _require_tuple(failure, "failure_classes")
    if interval_paths != EXPECTED_PATHS or failure_paths != EXPECTED_PATHS:
        raise ValueError("full/two-half path identity changed")
    if failure_classes != EXPECTED_FAILURE_CLASSES:
        raise ValueError("failure-injection classification changed")

    expected_counts = {
        "electrical": int(electrical["count"]),
        "interval": int(interval["count"]),
        "progression": int(progression["count"]),
        "failure": int(failure["count"]),
    }
    computed_counts = {
        "electrical": len(electrical_states) * len(electrical_grids),
        "interval": len(interval_states) * len(interval_grids) * len(interval_classes),
        "progression": len(progression_states) * len(progression_grids),
        "failure": len(failure_paths) * len(failure_classes),
    }
    if expected_counts != computed_counts or expected_counts != {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }:
        raise ValueError("equivalence matrix counts no longer equal 9/18/9/21")
    if audit.get("terminal_failure_disposition") != (
        "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
    ):
        raise ValueError("terminal equivalence disposition changed")

    maximum_intervals = int(progression["maximum_accepted_intervals"])
    if maximum_intervals != 4:
        raise ValueError("short progression maximum must remain four intervals")
    return EquivalenceContract(
        config_path=path.resolve(),
        config_sha256=_sha256_bytes(payload_bytes),
        normalized_relative_difference_max=tolerance,
        denominators=dict(denominators),
        exact_votes=exact_votes,
        telemetry_only=telemetry_only,
        electrical_states=electrical_states,
        electrical_grids=electrical_grids,
        interval_states=interval_states,
        interval_grids=interval_grids,
        interval_classes=interval_classes,
        interval_paths=interval_paths,
        progression_states=progression_states,
        progression_grids=progression_grids,
        progression_maximum_accepted_intervals=maximum_intervals,
        failure_paths=failure_paths,
        failure_classes=failure_classes,
        expected_counts=expected_counts,
        terminal_failure_disposition=str(audit["terminal_failure_disposition"]),
    )


def _make_plan_row(
    *,
    contract: EquivalenceContract,
    plan_index: int,
    sample_id: str,
    family: str,
    state: str | None = None,
    grid: str | None = None,
    interval_class: str | None = None,
    candidate_paths: tuple[str, ...] = (),
    failure_class: str | None = None,
    maximum_accepted_intervals: int | None = None,
) -> EquivalencePlanRow:
    locked_input = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract.config_sha256,
        "plan_index": plan_index,
        "sample_id": sample_id,
        "family": family,
        "state": state,
        "grid": grid,
        "interval_class": interval_class,
        "candidate_paths": candidate_paths,
        "failure_class": failure_class,
        "maximum_accepted_intervals": maximum_accepted_intervals,
    }
    return EquivalencePlanRow(
        plan_index=plan_index,
        sample_id=sample_id,
        family=family,
        state=state,
        grid=grid,
        interval_class=interval_class,
        candidate_paths=candidate_paths,
        failure_class=failure_class,
        maximum_accepted_intervals=maximum_accepted_intervals,
        input_sha256=canonical_sha256(locked_input),
    )


def build_equivalence_plan(
    contract: EquivalenceContract,
) -> tuple[EquivalencePlanRow, ...]:
    """Build the locked 57-row audit plan without executing any numerics."""

    rows: list[EquivalencePlanRow] = []

    def append(**kwargs: Any) -> None:
        rows.append(
            _make_plan_row(contract=contract, plan_index=len(rows), **kwargs)
        )

    for grid in contract.electrical_grids:
        for state in contract.electrical_states:
            append(
                sample_id=f"EQ-ELECTRICAL-{grid}-{state}",
                family="electrical",
                grid=grid,
                state=state,
            )
    for grid in contract.interval_grids:
        for state in contract.interval_states:
            for interval_class in contract.interval_classes:
                append(
                    sample_id=f"EQ-INTERVAL-{grid}-{state}-{interval_class}",
                    family="interval",
                    grid=grid,
                    state=state,
                    interval_class=interval_class,
                    candidate_paths=contract.interval_paths,
                )
    for grid in contract.progression_grids:
        for state in contract.progression_states:
            append(
                sample_id=f"EQ-PROGRESSION-{grid}-{state}",
                family="progression",
                grid=grid,
                state=state,
                maximum_accepted_intervals=(
                    contract.progression_maximum_accepted_intervals
                ),
            )
    for path in contract.failure_paths:
        for failure_class in contract.failure_classes:
            append(
                sample_id=f"EQ-FAILURE-{path}-{failure_class}",
                family="failure",
                candidate_paths=(path,),
                failure_class=failure_class,
            )

    counts = {
        family: sum(row.family == family for row in rows) for family in FAMILY_ORDER
    }
    if counts != dict(contract.expected_counts) or len(rows) != contract.expected_total:
        raise RuntimeError("constructed equivalence plan violates the preregistration")
    if len({row.sample_id for row in rows}) != len(rows):
        raise RuntimeError("equivalence sample IDs are not unique")
    if len({row.input_sha256 for row in rows}) != len(rows):
        raise RuntimeError("equivalence plan input hashes are not unique")
    return tuple(rows)


def hash_equivalence_input(
    plan_row: EquivalencePlanRow,
    runtime_input: Any,
    contract: EquivalenceContract,
) -> str:
    """Bind a plan row to its concrete runtime input before execution."""

    return canonical_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "contract_sha256": contract.config_sha256,
            "locked_plan_input_sha256": plan_row.input_sha256,
            "runtime_input": runtime_input,
        }
    )


def _array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float)


def _maximum_absolute(value: np.ndarray) -> float:
    if value.size == 0:
        raise ValueError("numeric comparison arrays cannot be empty")
    return float(np.max(np.abs(value)))


def _fixed_denominator(
    field: NumericField,
    contract: EquivalenceContract,
    protocol_voltage_scale_V: float,
) -> float:
    configured = contract.denominators[field.denominator_key]
    if configured == "fixed_protocol_V_scale":
        if not math.isfinite(protocol_voltage_scale_V) or protocol_voltage_scale_V <= 0.0:
            raise ValueError("protocol_voltage_scale_V must be positive and finite")
        return float(protocol_voltage_scale_V)
    if configured == "max_of_all_signed_terms_and_1e-30":
        raise ValueError("ledger_power_terms requires a shared scale group")
    return float(configured)


def _ledger_group_scales(
    candidate: EquivalenceObservation,
    oracle: EquivalenceObservation,
) -> dict[str, float]:
    scales: dict[str, float] = {}
    for name in candidate.numeric:
        candidate_field = candidate.numeric[name]
        if candidate_field.denominator_key != "ledger_power_terms":
            continue
        oracle_field = oracle.numeric.get(name)
        if oracle_field is None:
            continue
        group = candidate_field.scale_group
        if not group or oracle_field.scale_group != group:
            continue
        values = (_array(candidate_field.value), _array(oracle_field.value))
        if any(array.size == 0 or not np.isfinite(array).all() for array in values):
            scales[group] = math.nan
            continue
        maximum = max(_maximum_absolute(array) for array in values)
        scales[group] = max(scales.get(group, 1.0e-30), maximum, 1.0e-30)
    return scales


def _exact_equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def compare_observations(
    candidate: EquivalenceObservation,
    oracle: EquivalenceObservation,
    contract: EquivalenceContract,
    *,
    protocol_voltage_scale_V: float,
    required_exact_votes: Sequence[str] | None = None,
    required_telemetry_fields: Sequence[str] | None = None,
) -> EquivalenceComparison:
    """Compare two outputs using the locked SI floors and exact-vote topology."""

    tolerance = contract.normalized_relative_difference_max
    exact_required = tuple(
        contract.exact_votes if required_exact_votes is None else required_exact_votes
    )
    telemetry_required = tuple(
        contract.telemetry_only
        if required_telemetry_fields is None
        else required_telemetry_fields
    )
    if not set(exact_required).issubset(contract.exact_votes):
        raise ValueError("required exact vote is not preregistered")
    if not set(telemetry_required).issubset(contract.telemetry_only):
        raise ValueError("required telemetry field is not preregistered")
    if not math.isfinite(protocol_voltage_scale_V) or protocol_voltage_scale_V <= 0.0:
        raise ValueError("protocol_voltage_scale_V must be positive and finite")

    errors: list[str] = []
    candidate_numeric = set(candidate.numeric)
    oracle_numeric = set(oracle.numeric)
    if candidate_numeric != oracle_numeric:
        errors.append(
            "numeric field sets differ: "
            f"candidate_only={sorted(candidate_numeric - oracle_numeric)}, "
            f"oracle_only={sorted(oracle_numeric - candidate_numeric)}"
        )
    ledger_scales = _ledger_group_scales(candidate, oracle)
    numeric_results: list[NumericComparison] = []
    for name in sorted(candidate_numeric | oracle_numeric):
        candidate_field = candidate.numeric.get(name)
        oracle_field = oracle.numeric.get(name)
        if candidate_field is None or oracle_field is None:
            numeric_results.append(
                NumericComparison(
                    field=name,
                    denominator_key="missing",
                    denominator=math.nan,
                    maximum_absolute_difference=math.inf,
                    maximum_normalized_difference=math.inf,
                    passed=False,
                    reason="field missing from one implementation",
                )
            )
            continue
        if candidate_field.denominator_key != oracle_field.denominator_key:
            reason = "denominator identities differ"
            errors.append(f"{name}: {reason}")
            numeric_results.append(
                NumericComparison(
                    field=name,
                    denominator_key=candidate_field.denominator_key,
                    denominator=math.nan,
                    maximum_absolute_difference=math.inf,
                    maximum_normalized_difference=math.inf,
                    passed=False,
                    reason=reason,
                )
            )
            continue
        denominator_key = candidate_field.denominator_key
        if denominator_key not in contract.denominators:
            reason = "unregistered denominator identity"
            errors.append(f"{name}: {reason}")
            numeric_results.append(
                NumericComparison(
                    field=name,
                    denominator_key=denominator_key,
                    denominator=math.nan,
                    maximum_absolute_difference=math.inf,
                    maximum_normalized_difference=math.inf,
                    passed=False,
                    reason=reason,
                )
            )
            continue
        candidate_array = _array(candidate_field.value)
        oracle_array = _array(oracle_field.value)
        reason: str | None = None
        if candidate_array.shape != oracle_array.shape:
            reason = "array shapes differ"
        elif candidate_array.size == 0:
            reason = "empty comparison array"
        elif not np.isfinite(candidate_array).all() or not np.isfinite(oracle_array).all():
            reason = "nonfinite numeric value"
        if reason is not None:
            errors.append(f"{name}: {reason}")
            numeric_results.append(
                NumericComparison(
                    field=name,
                    denominator_key=denominator_key,
                    denominator=math.nan,
                    maximum_absolute_difference=math.inf,
                    maximum_normalized_difference=math.inf,
                    passed=False,
                    reason=reason,
                )
            )
            continue

        if denominator_key == "ledger_power_terms":
            group = candidate_field.scale_group
            if not group or oracle_field.scale_group != group:
                reason = "ledger scale group is absent or differs"
                denominator = math.nan
            else:
                denominator = ledger_scales.get(group, math.nan)
                if not math.isfinite(denominator) or denominator <= 0.0:
                    reason = "ledger scale group is nonfinite or empty"
        else:
            denominator_floor = _fixed_denominator(
                candidate_field, contract, protocol_voltage_scale_V
            )
            denominator = max(
                denominator_floor,
                _maximum_absolute(candidate_array),
                _maximum_absolute(oracle_array),
            )
        if reason is not None:
            errors.append(f"{name}: {reason}")
            maximum_absolute = math.inf
            normalized = math.inf
        else:
            maximum_absolute = _maximum_absolute(candidate_array - oracle_array)
            normalized = maximum_absolute / denominator
        numeric_results.append(
            NumericComparison(
                field=name,
                denominator_key=denominator_key,
                denominator=denominator,
                maximum_absolute_difference=maximum_absolute,
                maximum_normalized_difference=normalized,
                passed=bool(math.isfinite(normalized) and normalized <= tolerance),
                reason=reason,
            )
        )

    exact_mismatches: dict[str, Mapping[str, Any]] = {}
    expected_exact = set(exact_required)
    candidate_exact = set(candidate.exact_votes)
    oracle_exact = set(oracle.exact_votes)
    if candidate_exact != expected_exact or oracle_exact != expected_exact:
        errors.append(
            "exact-vote fields must equal the requested preregistered set"
        )
    for vote in sorted(expected_exact | candidate_exact | oracle_exact):
        candidate_value = candidate.exact_votes.get(vote, "MISSING")
        oracle_value = oracle.exact_votes.get(vote, "MISSING")
        if vote not in contract.exact_votes or not _exact_equal(candidate_value, oracle_value):
            exact_mismatches[vote] = {
                "candidate": _jsonable(candidate_value),
                "oracle": _jsonable(oracle_value),
            }

    telemetry_result: dict[str, Mapping[str, Any]] = {}
    expected_telemetry = set(telemetry_required)
    candidate_telemetry = set(candidate.telemetry)
    oracle_telemetry = set(oracle.telemetry)
    if candidate_telemetry != expected_telemetry or oracle_telemetry != expected_telemetry:
        errors.append(
            "telemetry fields must equal the requested preregistered set"
        )
    for field in sorted(expected_telemetry | candidate_telemetry | oracle_telemetry):
        candidate_value = candidate.telemetry.get(field, "MISSING")
        oracle_value = oracle.telemetry.get(field, "MISSING")
        telemetry_result[field] = {
            "candidate": _jsonable(candidate_value),
            "oracle": _jsonable(oracle_value),
            "equal": _exact_equal(candidate_value, oracle_value),
            "voting": False,
        }

    maximum = max(
        (result.maximum_normalized_difference for result in numeric_results),
        default=0.0,
    )
    worst = None
    if numeric_results:
        worst = max(
            numeric_results, key=lambda result: result.maximum_normalized_difference
        ).field
    passed = bool(
        not errors
        and not exact_mismatches
        and all(result.passed for result in numeric_results)
    )
    return EquivalenceComparison(
        passed=passed,
        tolerance=tolerance,
        maximum_normalized_difference=maximum,
        worst_field=worst,
        numeric=tuple(numeric_results),
        exact_mismatches=exact_mismatches,
        telemetry=telemetry_result,
        validation_errors=tuple(errors),
    )


def electrical_observation(solution: Any) -> EquivalenceObservation:
    """Convert the shared low-level electrical interface to audit fields."""

    return EquivalenceObservation(
        numeric={
            "phi": NumericField(solution.potential_V, "potential_V"),
            "source_current": NumericField(
                solution.source_current_A, "terminal_current_A"
            ),
            "ground_current": NumericField(
                solution.ground_current_A, "terminal_current_A"
            ),
            "cell_Joule_power": NumericField(
                solution.cell_joule_power_W, "power_W"
            ),
            "Joule_power": NumericField(solution.joule_power_W, "power_W"),
            "terminal_power": NumericField(
                solution.terminal_device_power_W, "power_W"
            ),
            "relative_current_imbalance": NumericField(
                solution.relative_current_imbalance, "relative_residual"
            ),
            "relative_power_imbalance": NumericField(
                solution.relative_power_imbalance, "relative_residual"
            ),
        },
        exact_votes={},
        telemetry={},
    )


ElectricalSolver = Callable[[Any, np.ndarray, float, float], Any]


def run_electrical_pair(
    *,
    candidate_solver: ElectricalSolver,
    comparison_solver: ElectricalSolver,
    grid: Any,
    conductivity_S_m: np.ndarray,
    source_voltage_V: float,
    ground_voltage_V: float = 0.0,
    protocol_voltage_scale_V: float,
    contract: EquivalenceContract,
) -> ElectricalPairResult:
    """Run injected low-level callables; no oracle is imported by production."""

    candidate = candidate_solver(
        grid, conductivity_S_m, source_voltage_V, ground_voltage_V
    )
    oracle = comparison_solver(
        grid, conductivity_S_m, source_voltage_V, ground_voltage_V
    )
    comparison = compare_observations(
        electrical_observation(candidate),
        electrical_observation(oracle),
        contract,
        protocol_voltage_scale_V=protocol_voltage_scale_V,
        required_exact_votes=(),
        required_telemetry_fields=(),
    )
    return ElectricalPairResult(
        candidate=candidate,
        oracle=oracle,
        comparison=comparison,
    )


_INJECTION_LOCK = RLock()


def _resolved_source_corrected_config(
    source_config: Mapping[str, Any], resolved_controller: Any
) -> dict[str, Any]:
    """Validate the source-corrected base and return the resolved v3 config."""

    if source_config.get("schema_version") != (
        "geophase_phase1_v2_s2_reference_source_corrected_v3"
    ):
        raise ValueError("equivalence audit requires the source-corrected v3 S2 config")
    resolved = getattr(resolved_controller, "resolved_config", resolved_controller)
    base = getattr(resolved_controller, "base_config", source_config)
    if not isinstance(resolved, Mapping) or not isinstance(base, Mapping):
        raise TypeError("resolved_controller must expose mapping-valued resolved config")
    if dict(base) != dict(source_config):
        raise ValueError("resolved controller is not derived from the supplied v3 base")
    config = dict(resolved)
    protocols = config["formal_protocols"]["protocols"]
    if "high_bias_15V" in protocols:
        raise ValueError("active source-corrected config retains forbidden 15 V alias")
    high = protocols.get("high_bias_lock_15p8V")
    if not isinstance(high, Mapping) or float(high["input_voltage_V"]) != 15.8:
        raise ValueError("active source-corrected high-bias protocol is not 15.8 V")
    controller = config["reference_solver"].get("active_time_controller")
    if not isinstance(controller, Mapping) or controller.get("controller_id") != (
        "embedded_time_consistency_v2_only"
    ):
        raise ValueError("equivalence audit requires the resolved controller-v2")
    return config


def _grid_level(grid_id: str) -> int:
    if not grid_id.startswith("L"):
        raise ValueError(f"invalid equivalence grid ID: {grid_id}")
    level = int(grid_id[1:])
    if level not in (1, 2, 4):
        raise ValueError(f"undeclared equivalence spatial level: {grid_id}")
    return level


def build_deterministic_audit_cases(
    source_config: Mapping[str, Any], resolved_controller: Any
) -> Mapping[tuple[str, str], DeterministicAuditCase]:
    """Construct the three locked states on L1/L2/L4 without a numerical solve."""

    from pinnpcm.physics.geophase_geometry import build_geophase_grid
    from pinnpcm.physics.geophase_s2_thermal import (
        build_s2_thermal_fields,
        effective_vo2_closure_from_v2_config,
    )
    from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
        protocol_voltage_scale,
    )
    from pinnpcm.solvers.geophase_phase1_v2_implicit import S2State

    config = _resolved_source_corrected_config(source_config, resolved_controller)
    closure = effective_vo2_closure_from_v2_config(config)
    protocol_ids = {
        "equilibrium": "zero_drive",
        "legal_critical": "transition_probe_12p5V",
        "high_conductive": "high_bias_lock_15p8V",
    }
    cases: dict[tuple[str, str], DeterministicAuditCase] = {}
    for grid_id in ("L1", "L2", "L4"):
        grid = build_geophase_grid(config, spatial_level=_grid_level(grid_id))
        fields = build_s2_thermal_fields(grid, config)
        for state_id, protocol_id in protocol_ids.items():
            if state_id == "equilibrium":
                temperature = float(fields.ambient_temperature_K)
                branch = 1.0
                conductive = float(
                    np.asarray(
                        closure.equilibrium_state(
                            np.asarray(temperature), np.asarray(branch)
                        )
                    ).item()
                )
            elif state_id == "legal_critical":
                temperature = float(closure.T_c_up_K)
                branch = 1.0
                conductive = 0.5
            else:
                temperature = 380.0
                branch = 1.0
                conductive = float(
                    np.asarray(
                        closure.equilibrium_state(
                            np.asarray(temperature), np.asarray(branch)
                        )
                    ).item()
                )
            initial = S2State(
                time_s=0.0,
                temperature_K=np.full(grid.shape, temperature, dtype=float),
                conductive_state=np.full(grid.shape, conductive, dtype=float),
                branch_memory=np.full(grid.shape, branch, dtype=float),
                device_voltage_V=0.0,
            )
            protocol = config["formal_protocols"]["protocols"][protocol_id]
            cases[(grid_id, state_id)] = DeterministicAuditCase(
                state_id=state_id,
                grid_id=grid_id,
                grid=grid,
                closure=closure,
                fields=fields,
                initial_state=initial,
                protocol_id=protocol_id,
                protocol=protocol,
                protocol_voltage_scale_V=protocol_voltage_scale(config, protocol_id),
            )
    high = cases[("L1", "high_conductive")]
    if (
        not np.all(high.initial_state.temperature_K == 380.0)
        or high.protocol_id != "high_bias_lock_15p8V"
        or high.protocol_voltage_scale_V != 15.8
    ):
        raise RuntimeError("high-conductive source-corrected fixture drifted")
    legal = cases[("L1", "legal_critical")]
    if (
        not np.all(legal.initial_state.temperature_K == closure.T_c_up_K)
        or not np.all(legal.initial_state.conductive_state == 0.5)
        or legal.protocol_voltage_scale_V != 12.5
    ):
        raise RuntimeError("legal-critical fixture drifted")
    return cases


@contextmanager
def _inject_legacy_electrical_solver(oracle_solver: ElectricalSolver):
    """Temporarily route only the unoptimized implicit electrical call to PR8."""

    if not callable(oracle_solver):
        raise TypeError("oracle_solver must be callable")
    from pinnpcm.solvers import geophase_phase1_v2_implicit as implicit

    trace = {"calls": 0}

    def counted_oracle(
        grid: Any,
        conductivity_S_m: np.ndarray,
        source_voltage_V: float,
        ground_voltage_V: float = 0.0,
    ) -> Any:
        trace["calls"] += 1
        return oracle_solver(
            grid, conductivity_S_m, source_voltage_V, ground_voltage_V
        )

    with _INJECTION_LOCK:
        original = implicit.solve_sheet_electrical
        implicit.solve_sheet_electrical = counted_oracle
        try:
            yield trace
        finally:
            implicit.solve_sheet_electrical = original


def _injected_failure_step(step: Any, failure_class: str) -> Any:
    """Return one deliberately corrupted negative-control step."""

    if failure_class == "nonfinite":
        temperature = np.asarray(step.state.temperature_K, dtype=float).copy()
        temperature.reshape(-1)[0] = np.nan
        return replace(step, state=replace(step.state, temperature_K=temperature))
    if failure_class == "nonlinear_convergence":
        nonlinear = replace(
            step.nonlinear,
            converged=False,
            scaled_residual_inf=1.0,
            scaled_update_inf=1.0,
        )
        return replace(step, nonlinear=nonlinear)
    if failure_class == "lateral_audit":
        lateral = replace(
            step.lateral_flux,
            matrix_face_relative_mismatch=1.0,
            matrix_face_roundoff_ratio=2.0,
        )
        return replace(step, lateral_flux=lateral)
    ledger_name = {
        "thermal_ledger": "thermal",
        "circuit_ledger": "circuit",
        "combined_ledger": "combined",
        "device_power_identity": "device_power",
    }.get(failure_class)
    if ledger_name is None:
        raise ValueError(f"unsupported failure injection: {failure_class}")
    balance = getattr(step.ledgers, ledger_name)
    ledgers = replace(
        step.ledgers,
        **{ledger_name: replace(balance, relative_residual=1.0)},
    )
    return replace(step, ledgers=ledgers)


@contextmanager
def _inject_controller_failure(path: str, failure_class: str):
    """Inject after a real coupled solve at the named full/two-half path."""

    from pinnpcm.solvers import geophase_phase1_v2_controller_v2 as controller

    target = {
        "full_step": 1,
        "first_half_step": 2,
        "second_half_step": 3,
    }[path]
    trace: dict[str, Any] = {
        "target_path": path,
        "failure_class": failure_class,
        "advance_calls": 0,
        "injected": False,
    }
    with _INJECTION_LOCK:
        original = controller.advance_s2_backward_euler

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            step = original(*args, **kwargs)
            trace["advance_calls"] += 1
            if trace["advance_calls"] == target:
                trace["injected"] = True
                return _injected_failure_step(step, failure_class)
            return step

        controller.advance_s2_backward_euler = wrapped
        try:
            yield trace
        finally:
            controller.advance_s2_backward_euler = original


@contextmanager
def _capture_controller_attempts():
    """Capture the real adaptive accept/reject sequence without altering it."""

    from pinnpcm.solvers import geophase_phase1_v2_controller_v2 as controller

    attempts: list[Any] = []
    with _INJECTION_LOCK:
        original = controller.attempt_s2_embedded_interval

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            observation = original(*args, **kwargs)
            attempts.append(observation)
            return observation

        controller.attempt_s2_embedded_interval = wrapped
        try:
            yield attempts
        finally:
            controller.attempt_s2_embedded_interval = original


def _add_balance_numeric(
    output: dict[str, NumericField], prefix: str, balance: Any
) -> None:
    group = f"{prefix}:{balance.name}"
    for name in ("input_power_W", "accounted_power_W", "signed_residual_W"):
        output[f"{prefix}.{name}"] = NumericField(
            getattr(balance, name), "ledger_power_terms", scale_group=group
        )
    output[f"{prefix}.relative_residual"] = NumericField(
        balance.relative_residual, "relative_residual"
    )
    for name, value in sorted(balance.terms_W.items()):
        output[f"{prefix}.terms.{name}"] = NumericField(
            value, "ledger_power_terms", scale_group=group
        )


def _add_ledger_bundle_numeric(
    output: dict[str, NumericField], prefix: str, bundle: Any
) -> None:
    if bundle is None:
        return
    for name in bundle.storage.__dataclass_fields__:
        output[f"{prefix}.storage.{name}"] = NumericField(
            getattr(bundle.storage, name), "power_W"
        )
    for ledger_name in ("thermal", "circuit", "combined", "device_power"):
        _add_balance_numeric(
            output, f"{prefix}.{ledger_name}", getattr(bundle, ledger_name)
        )


def _add_step_numeric(
    output: dict[str, NumericField], prefix: str, step: Any
) -> None:
    if step is None:
        return
    for name, denominator in (
        ("time_s", "time_s"),
        ("temperature_K", "temperature_K"),
        ("conductive_state", "conductive_state"),
        ("branch_memory", "branch_memory"),
        ("device_voltage_V", "device_voltage_V"),
    ):
        output[f"{prefix}.state.{name}"] = NumericField(
            getattr(step.state, name), denominator
        )
    for name, denominator in (
        ("potential_V", "potential_V"),
        ("source_current_A", "terminal_current_A"),
        ("ground_current_A", "terminal_current_A"),
        ("cell_joule_power_W", "power_W"),
        ("joule_power_W", "power_W"),
        ("terminal_device_power_W", "power_W"),
        ("relative_current_imbalance", "relative_residual"),
        ("relative_power_imbalance", "relative_residual"),
    ):
        output[f"{prefix}.electrical.{name}"] = NumericField(
            getattr(step.electrical, name), denominator
        )
    for name in (
        "net_cell_outflow_W",
        "x_face_flux_W",
        "y_face_flux_W",
        "boundary_face_flux_W",
        "boundary_outflow_W",
        "internal_pair_cancellation_W",
        "face_to_cell_global_residual_W",
    ):
        output[f"{prefix}.lateral.{name}"] = NumericField(
            getattr(step.lateral_flux, name), "power_W"
        )
    for name in ("matrix_face_relative_mismatch", "matrix_face_roundoff_ratio"):
        output[f"{prefix}.lateral.{name}"] = NumericField(
            getattr(step.lateral_flux, name), "relative_residual"
        )
    output[f"{prefix}.nonlinear.scaled_residual_inf"] = NumericField(
        step.nonlinear.scaled_residual_inf, "relative_residual"
    )
    output[f"{prefix}.nonlinear.scaled_update_inf"] = NumericField(
        step.nonlinear.scaled_update_inf, "relative_residual"
    )
    _add_ledger_bundle_numeric(output, f"{prefix}.ledgers", step.ledgers)


def _attempt_failure_classification(observation: Any) -> str:
    if observation.error_class is None:
        return "none"
    return f"{observation.error_class}:{observation.error_message}"


def _attempt_observation(
    observation: Any,
    *,
    include_only_integrity_passed_steps: bool = False,
    declared_failure: str | None = None,
) -> EquivalenceObservation:
    numeric: dict[str, NumericField] = {}
    path_records = (
        ("full_step", observation.full_candidate, observation.diagnostics.full_step),
        (
            "first_half_step",
            observation.first_half_candidate,
            observation.diagnostics.first_half_step,
        ),
        (
            "second_half_step",
            observation.second_half_candidate,
            observation.diagnostics.second_half_step,
        ),
    )
    for name, step, integrity in path_records:
        if (
            step is not None
            and (
                not include_only_integrity_passed_steps
                or (integrity is not None and integrity.overall_pass)
            )
        ):
            _add_step_numeric(numeric, name, step)
    if observation.aggregate_ledgers is not None:
        _add_ledger_bundle_numeric(
            numeric, "aggregate_ledgers", observation.aggregate_ledgers
        )
    diagnostics = observation.diagnostics
    for name in (
        "outer_interval_s",
        "half_interval_s",
        "legacy_conductive_increment",
        "legacy_branch_increment",
    ):
        value = getattr(diagnostics, name)
        if value is not None:
            numeric[f"diagnostics.{name}"] = NumericField(
                value,
                "time_s" if "interval_s" in name else "relative_residual",
            )
    if diagnostics.embedded_error is not None:
        for name in ("e_T", "e_s", "e_b", "e_V", "e_max"):
            numeric[f"embedded_error.{name}"] = NumericField(
                getattr(diagnostics.embedded_error, name), "relative_residual"
            )
    nonlinear = tuple(
        (name, None if step is None else step.nonlinear)
        for name, step, _ in path_records
    )
    methods = tuple(
        (name, None if item is None else item.method) for name, item in nonlinear
    )
    converged = tuple(
        (name, None if item is None else bool(item.converged))
        for name, item in nonlinear
    )
    fallbacks = tuple(
        (
            name,
            None
            if item is None
            else item.method == "fail_closed_fixed_point_fallback",
        )
        for name, item in nonlinear
    )
    failure = _attempt_failure_classification(observation)
    if declared_failure is not None:
        failure = f"injected:{declared_failure}|observed:{failure}"
    telemetry = {
        "Newton_iterations": tuple(
            0 if item is None else int(item.iterations) for _, item in nonlinear
        ),
        "Krylov_matvecs": tuple(
            0 if item is None else int(item.krylov_matvecs) for _, item in nonlinear
        ),
        "Armijo_backtracks": tuple(
            0 if item is None else int(item.armijo_backtracks)
            for _, item in nonlinear
        ),
        "Picard_iterations": tuple(
            0 if item is None else int(item.predictor_picard_iterations)
            for _, item in nonlinear
        ),
        "fallback_iterations": tuple(
            0 if item is None else int(item.fallback_picard_iterations)
            for _, item in nonlinear
        ),
    }
    return EquivalenceObservation(
        numeric=numeric,
        exact_votes={
            "nonlinear_method": methods,
            "converged_disposition": converged,
            "fallback_disposition": fallbacks,
            "accepted_rejected_sequence": (
                "accepted" if observation.step is not None else "rejected",
            ),
            "failure_classification": failure,
            "event_count_direction_and_order": (),
            "reversal_count_direction_and_order": (),
        },
        telemetry=telemetry,
    )


def _streaming_denominator(name: str) -> str | None:
    lowered = name.lower()
    if name in {
        "sample_index",
        "event_count_to_date",
        "newton_iterations",
        "krylov_matvecs",
        "armijo_backtracks",
        "fallback_picard_iterations",
        "outer_rejections",
        "coupled_solve_count",
        "accepted_bundle_coupled_solve_count",
    }:
        return None
    if "time_s" in lowered or "interval_s" in lowered:
        return "time_s"
    if "temperature" in lowered:
        return "temperature_K"
    if "conductive" in lowered or lowered.endswith("delta_s"):
        return "conductive_state"
    if "branch" in lowered or lowered.endswith("delta_b"):
        return "branch_memory"
    if "voltage" in lowered:
        return "device_voltage_V"
    if "current" in lowered:
        return "terminal_current_A"
    if "power" in lowered or lowered.endswith("_w"):
        return "power_W"
    if any(
        token in lowered
        for token in ("residual", "mismatch", "roundoff", "e_t", "e_s", "e_b", "e_v", "e_max")
    ):
        return "relative_residual"
    return None


def _progression_observation(result: Any, attempts: Sequence[Any]) -> EquivalenceObservation:
    numeric: dict[str, NumericField] = {}
    history = tuple(result.protocol_result.steps)
    for index, step in enumerate(history):
        _add_step_numeric(numeric, f"history.{index}.accepted", step)
        _add_step_numeric(
            numeric, f"history.{index}.accepted_first_half", step.accepted_first_half
        )
    for name, denominator in (
        ("time_s", "time_s"),
        ("temperature_K", "temperature_K"),
        ("conductive_state", "conductive_state"),
        ("branch_memory", "branch_memory"),
        ("device_voltage_V", "device_voltage_V"),
    ):
        numeric[f"streaming.final_state.{name}"] = NumericField(
            getattr(result.final_state, name), denominator
        )
    for row_index, scalar in enumerate(result.scalar_records):
        for name, value in sorted(scalar.items()):
            if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
                continue
            denominator = _streaming_denominator(name)
            if denominator is not None:
                numeric[f"streaming.scalar.{row_index}.{name}"] = NumericField(
                    value, denominator
                )
    for index, snapshot in enumerate(result.field_snapshots):
        numeric[f"streaming.snapshot.{index}.time_s"] = NumericField(
            snapshot.time_s, "time_s"
        )
        for name, denominator in (
            ("temperature_K", "temperature_K"),
            ("conductive_state", "conductive_state"),
            ("branch_memory", "branch_memory"),
            ("potential_V", "potential_V"),
            ("cell_joule_power_W", "power_W"),
        ):
            numeric[f"streaming.snapshot.{index}.{name}"] = NumericField(
                getattr(snapshot, name), denominator
            )
    attempted_paths = []
    for attempt_index, attempt in enumerate(attempts):
        for path_name, step in (
            ("full_step", attempt.full_candidate),
            ("first_half_step", attempt.first_half_candidate),
            ("second_half_step", attempt.second_half_candidate),
        ):
            attempted_paths.append((attempt_index, path_name, step))
    methods = tuple(
        (index, path, None if step is None else step.nonlinear.method)
        for index, path, step in attempted_paths
    )
    converged = tuple(
        (index, path, None if step is None else bool(step.nonlinear.converged))
        for index, path, step in attempted_paths
    )
    fallbacks = tuple(
        (
            index,
            path,
            None
            if step is None
            else step.nonlinear.method == "fail_closed_fixed_point_fallback",
        )
        for index, path, step in attempted_paths
    )
    telemetry = {
        "Newton_iterations": tuple(
            0 if step is None else int(step.nonlinear.iterations)
            for _, _, step in attempted_paths
        ),
        "Krylov_matvecs": tuple(
            0 if step is None else int(step.nonlinear.krylov_matvecs)
            for _, _, step in attempted_paths
        ),
        "Armijo_backtracks": tuple(
            0 if step is None else int(step.nonlinear.armijo_backtracks)
            for _, _, step in attempted_paths
        ),
        "Picard_iterations": tuple(
            0 if step is None else int(step.nonlinear.predictor_picard_iterations)
            for _, _, step in attempted_paths
        ),
        "fallback_iterations": tuple(
            0 if step is None else int(step.nonlinear.fallback_picard_iterations)
            for _, _, step in attempted_paths
        ),
    }
    failure_sequence = tuple(
        _attempt_failure_classification(attempt) for attempt in attempts
    )
    return EquivalenceObservation(
        numeric=numeric,
        exact_votes={
            "nonlinear_method": methods,
            "converged_disposition": converged,
            "fallback_disposition": fallbacks,
            "accepted_rejected_sequence": tuple(
                "accepted" if attempt.step is not None else "rejected"
                for attempt in attempts
            ),
            "failure_classification": (
                result.protocol_result.stop_reason,
                bool(result.protocol_result.completed),
                failure_sequence,
            ),
            "event_count_direction_and_order": tuple(
                str(record["direction"]) for record in result.event_records
            ),
            "reversal_count_direction_and_order": tuple(
                str(record["direction"]) for record in result.reversal_records
            ),
        },
        telemetry=telemetry,
    )


def _progression_validation_errors(
    result: Any, attempts: Sequence[Any], maximum_accepted: int
) -> tuple[str, ...]:
    errors: list[str] = []
    history = tuple(result.protocol_result.steps)
    accepted = int(result.protocol_result.diagnostics.accepted_steps)
    if accepted != maximum_accepted:
        errors.append(
            f"progression accepted {accepted}, expected {maximum_accepted} intervals"
        )
    if len(history) != maximum_accepted:
        errors.append("full-history retention does not contain every accepted interval")
    if not attempts:
        errors.append("adaptive accept/reject sequence was not captured")
    if not result.scalar_records:
        errors.append("streaming scalar summary is empty")
    if history:
        final = history[-1].state
        for name in (
            "temperature_K",
            "conductive_state",
            "branch_memory",
            "device_voltage_V",
        ):
            left = np.asarray(getattr(result.final_state, name), dtype=float)
            right = np.asarray(getattr(final, name), dtype=float)
            if left.shape != right.shape or not np.array_equal(left, right):
                errors.append(f"full-history/streaming final {name} differs")
    return tuple(errors)


def _comparison_with_validation_errors(
    comparison: EquivalenceComparison, errors: Sequence[str]
) -> EquivalenceComparison:
    combined = tuple(comparison.validation_errors) + tuple(errors)
    if not combined:
        return comparison
    return replace(comparison, passed=False, validation_errors=combined)


def _run_embedded_attempt_once(
    case: DeterministicAuditCase,
    config: dict[str, Any],
    *,
    outer_interval_s: float,
    optimized: bool,
    oracle_solver: ElectricalSolver | None,
    failure_path: str | None = None,
    failure_class: str | None = None,
) -> tuple[Any, Mapping[str, Any], Mapping[str, Any]]:
    from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
        attempt_s2_embedded_interval,
        controller_v2_limits,
    )
    from pinnpcm.solvers.geophase_phase1_v2_implicit import build_s2_solver_cache

    _, floor = controller_v2_limits(config, 1)
    legacy_trace: Mapping[str, Any] = {"calls": 0}
    injection_trace: Mapping[str, Any] = {
        "injected": False,
        "advance_calls": 0,
    }
    with ExitStack() as stack:
        if not optimized:
            if oracle_solver is None:
                raise ValueError("legacy interval execution requires oracle_solver")
            legacy_trace = stack.enter_context(
                _inject_legacy_electrical_solver(oracle_solver)
            )
        if failure_path is not None:
            if failure_class is None:
                raise ValueError("failure path requires a failure class")
            injection_trace = stack.enter_context(
                _inject_controller_failure(failure_path, failure_class)
            )
        observation = attempt_s2_embedded_interval(
            case.initial_state,
            protocol=dict(case.protocol),
            protocol_id=case.protocol_id,
            outer_interval_s=outer_interval_s,
            grid=case.grid,
            closure=case.closure,
            fields=case.fields,
            config=config,
            rejection_index=0,
            below_floor_remainder=False,
            at_outer_floor=bool(
                outer_interval_s <= floor * (1.0 + 1.0e-12)
            ),
            cache=(
                build_s2_solver_cache(case.grid, case.fields) if optimized else None
            ),
            use_equivalent_optimizations=optimized,
            use_unit_voltage_scaling=False,
        )
    return observation, dict(legacy_trace), dict(injection_trace)


def _execute_electrical_row(
    row: EquivalencePlanRow,
    case: DeterministicAuditCase,
    config: dict[str, Any],
    contract: EquivalenceContract,
    oracle_solver: ElectricalSolver,
    candidate_solver: ElectricalSolver,
) -> PairExecution:
    from pinnpcm.solvers.geophase_phase1_v2_implicit import protocol_voltage

    conductivity = case.closure.conductivity_S_m(
        case.initial_state.temperature_K, case.initial_state.conductive_state
    )
    voltage = float(protocol_voltage(dict(case.protocol), case.initial_state.time_s))
    pair = run_electrical_pair(
        candidate_solver=candidate_solver,
        comparison_solver=oracle_solver,
        grid=case.grid,
        conductivity_S_m=conductivity,
        source_voltage_V=voltage,
        ground_voltage_V=0.0,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
        contract=contract,
    )
    return PairExecution(
        candidate_observation=electrical_observation(pair.candidate),
        oracle_observation=electrical_observation(pair.oracle),
        candidate_raw=pair.candidate,
        oracle_raw=pair.oracle,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
    )


def _execute_interval_row(
    row: EquivalencePlanRow,
    case: DeterministicAuditCase,
    config: dict[str, Any],
    oracle_solver: ElectricalSolver,
) -> PairExecution:
    from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import controller_v2_limits

    maximum, floor = controller_v2_limits(config, 1)
    outer = maximum if row.interval_class == "base" else floor
    candidate, _, _ = _run_embedded_attempt_once(
        case,
        config,
        outer_interval_s=outer,
        optimized=True,
        oracle_solver=None,
    )
    oracle, oracle_trace, _ = _run_embedded_attempt_once(
        case,
        config,
        outer_interval_s=outer,
        optimized=False,
        oracle_solver=oracle_solver,
    )
    errors: list[str] = []
    for label, observation in (("candidate", candidate), ("oracle", oracle)):
        if any(
            item is None
            for item in (
                observation.full_candidate,
                observation.first_half_candidate,
                observation.second_half_candidate,
                observation.diagnostics.embedded_error,
            )
        ):
            errors.append(f"{label} did not return all full/two-half candidates")
    if int(oracle_trace["calls"]) <= 0:
        errors.append("legacy interval path never called the injected PR8 oracle")
    return PairExecution(
        candidate_observation=_attempt_observation(candidate),
        oracle_observation=_attempt_observation(oracle),
        candidate_raw=candidate,
        oracle_raw=oracle,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
        validation_errors=tuple(errors),
    )


def _failure_trace_errors(
    observation: Any,
    trace: Mapping[str, Any],
    path: str,
    failure_class: str,
    implementation: str,
) -> list[str]:
    errors: list[str] = []
    if trace.get("injected") is not True:
        errors.append(f"{implementation} failure injection did not reach {path}")
        return errors
    integrity = getattr(observation.diagnostics, path)
    if integrity is None:
        errors.append(f"{implementation} {path} has no integrity result")
        return errors
    expected_failed = (
        not integrity.finite
        if failure_class == "nonfinite"
        else not integrity.nonlinear_pass
        if failure_class == "nonlinear_convergence"
        else not integrity.lateral_pass
        if failure_class == "lateral_audit"
        else not integrity.ledger_pass
    )
    if not expected_failed:
        errors.append(
            f"{implementation} {path} did not expose injected {failure_class}"
        )
    message_fragment = {
        "full_step": "full-step",
        "first_half_step": "first-half",
        "second_half_step": "second-half",
    }[path]
    if message_fragment not in str(observation.error_message):
        errors.append(f"{implementation} failure classification lost target path")
    return errors


def _execute_failure_row(
    row: EquivalencePlanRow,
    case: DeterministicAuditCase,
    config: dict[str, Any],
    oracle_solver: ElectricalSolver,
) -> PairExecution:
    from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import controller_v2_limits

    path = row.candidate_paths[0]
    assert row.failure_class is not None
    maximum, _ = controller_v2_limits(config, 1)
    candidate, _, candidate_trace = _run_embedded_attempt_once(
        case,
        config,
        outer_interval_s=maximum,
        optimized=True,
        oracle_solver=None,
        failure_path=path,
        failure_class=row.failure_class,
    )
    oracle, oracle_trace, oracle_injection = _run_embedded_attempt_once(
        case,
        config,
        outer_interval_s=maximum,
        optimized=False,
        oracle_solver=oracle_solver,
        failure_path=path,
        failure_class=row.failure_class,
    )
    errors = _failure_trace_errors(
        candidate, candidate_trace, path, row.failure_class, "candidate"
    )
    errors.extend(
        _failure_trace_errors(
            oracle, oracle_injection, path, row.failure_class, "oracle"
        )
    )
    if int(oracle_trace["calls"]) <= 0:
        errors.append("legacy failure path never called the injected PR8 oracle")
    declared = f"{path}:{row.failure_class}"
    return PairExecution(
        candidate_observation=_attempt_observation(
            candidate,
            include_only_integrity_passed_steps=True,
            declared_failure=declared,
        ),
        oracle_observation=_attempt_observation(
            oracle,
            include_only_integrity_passed_steps=True,
            declared_failure=declared,
        ),
        candidate_raw=candidate,
        oracle_raw=oracle,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
        validation_errors=tuple(errors),
    )


def _run_progression_once(
    case: DeterministicAuditCase,
    config: dict[str, Any],
    *,
    maximum_accepted_intervals: int,
    optimized: bool,
    oracle_solver: ElectricalSolver | None,
) -> tuple[Any, tuple[Any, ...], Mapping[str, Any]]:
    from pinnpcm.solvers.geophase_phase1_v2_streaming import (
        run_s2_streaming_protocol_v2,
    )

    legacy_trace: Mapping[str, Any] = {"calls": 0}
    with ExitStack() as stack:
        if not optimized:
            if oracle_solver is None:
                raise ValueError("legacy progression requires oracle_solver")
            legacy_trace = stack.enter_context(
                _inject_legacy_electrical_solver(oracle_solver)
            )
        attempts = stack.enter_context(_capture_controller_attempts())
        result = run_s2_streaming_protocol_v2(
            f"EQ-PROGRESSION-{case.grid_id}-{case.state_id}",
            case.initial_state,
            protocol=dict(case.protocol),
            protocol_id=case.protocol_id,
            grid=case.grid,
            closure=case.closure,
            fields=case.fields,
            config=config,
            time_divisor=1,
            final_time_s=float(config["reference_solver"]["time_grid"]["final_time_s"]),
            maximum_accepted_steps=maximum_accepted_intervals,
            retain_full_history=True,
            retained_step_limit=maximum_accepted_intervals,
            cache=None,
            use_equivalent_optimizations=optimized,
            use_unit_voltage_scaling=False,
        )
    return result, tuple(attempts), dict(legacy_trace)


def _execute_progression_row(
    row: EquivalencePlanRow,
    case: DeterministicAuditCase,
    config: dict[str, Any],
    oracle_solver: ElectricalSolver,
) -> PairExecution:
    maximum = int(row.maximum_accepted_intervals or 0)
    candidate, candidate_attempts, _ = _run_progression_once(
        case,
        config,
        maximum_accepted_intervals=maximum,
        optimized=True,
        oracle_solver=None,
    )
    oracle, oracle_attempts, oracle_trace = _run_progression_once(
        case,
        config,
        maximum_accepted_intervals=maximum,
        optimized=False,
        oracle_solver=oracle_solver,
    )
    errors = list(
        _progression_validation_errors(candidate, candidate_attempts, maximum)
    )
    errors.extend(_progression_validation_errors(oracle, oracle_attempts, maximum))
    if int(oracle_trace["calls"]) <= 0:
        errors.append("legacy progression never called the injected PR8 oracle")
    return PairExecution(
        candidate_observation=_progression_observation(
            candidate, candidate_attempts
        ),
        oracle_observation=_progression_observation(oracle, oracle_attempts),
        candidate_raw=candidate,
        oracle_raw=oracle,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
        validation_errors=tuple(errors),
    )


def _runtime_input_payload(
    row: EquivalencePlanRow,
    case: DeterministicAuditCase | None,
    config: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload: dict[str, Any] = {
        "plan": {
            "sample_id": row.sample_id,
            "family": row.family,
            "state": row.state,
            "grid": row.grid,
            "interval_class": row.interval_class,
            "candidate_paths": row.candidate_paths,
            "failure_class": row.failure_class,
            "maximum_accepted_intervals": row.maximum_accepted_intervals,
        },
        "resolved_controller_id": config["reference_solver"][
            "active_time_controller"
        ]["controller_id"],
        "source_corrected_schema": config["schema_version"],
    }
    if case is not None:
        payload["case"] = {
            "state_id": case.state_id,
            "grid_id": case.grid_id,
            "x_edges_m": case.grid.x_edges_m,
            "y_edges_m": case.grid.y_edges_m,
            "initial_state": case.initial_state,
            "protocol_id": case.protocol_id,
            "protocol": case.protocol,
            "protocol_voltage_scale_V": case.protocol_voltage_scale_V,
        }
    return payload


def _real_row_executor(
    row: EquivalencePlanRow,
    cases: Mapping[tuple[str, str], DeterministicAuditCase],
    config: dict[str, Any],
    contract: EquivalenceContract,
    oracle_solver: ElectricalSolver,
    candidate_solver: ElectricalSolver,
) -> PairExecution:
    if row.family in {"electrical", "interval", "progression"}:
        if row.grid is None or row.state is None:
            raise ValueError(f"{row.family} row lacks state/grid identity")
        case = cases[(row.grid, row.state)]
    else:
        # Failure topology is controller-path specific and uses the legal
        # critical L1 fixture for every injected class.
        case = cases[("L1", "legal_critical")]
    if row.family == "electrical":
        return _execute_electrical_row(
            row, case, config, contract, oracle_solver, candidate_solver
        )
    if row.family == "interval":
        return _execute_interval_row(row, case, config, oracle_solver)
    if row.family == "progression":
        return _execute_progression_row(row, case, config, oracle_solver)
    if row.family == "failure":
        return _execute_failure_row(row, case, config, oracle_solver)
    raise ValueError(f"unknown equivalence family: {row.family}")


def _publish_audit_tables(
    tables: Mapping[str, str], summary: Mapping[str, Any], output_dir: Path
) -> Mapping[str, str]:
    filenames = {
        "electrical": "electrical_equivalence.csv",
        "interval": "interval_equivalence.csv",
        "progression": "progression_equivalence.csv",
        "failure": "failure_equivalence.csv",
    }
    targets = {
        family: output_dir / filename for family, filename in filenames.items()
    }
    targets["summary"] = output_dir / "equivalence_summary.json"
    existing = [path for path in targets.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite equivalence evidence: "
            + ", ".join(str(path) for path in existing)
        )
    for family in FAMILY_ORDER:
        atomic_write_text(targets[family], tables[family])
    atomic_write_json(targets["summary"], summary)
    return {name: str(path) for name, path in targets.items()}


def run_equivalence_audit(
    *,
    oracle_solver: ElectricalSolver,
    source_config: Mapping[str, Any],
    resolved_controller: Any,
    contract: EquivalenceContract | None = None,
    candidate_solver: ElectricalSolver | None = None,
    publish: bool = False,
    output_dir: Path | None = None,
    _test_row_executor: Callable[..., PairExecution] | None = None,
) -> EquivalenceAuditResult:
    """Execute the locked matrix in memory and optionally publish once.

    The default performs the real 57-row audit.  ``_test_row_executor`` exists
    only so focused tests can exercise orchestration without executing that
    matrix; test-injected results cannot be published.
    """

    if not callable(oracle_solver):
        raise TypeError("oracle_solver must be a dynamically injected callable")
    active_contract = load_equivalence_contract() if contract is None else contract
    config = _resolved_source_corrected_config(source_config, resolved_controller)
    if candidate_solver is None:
        from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical

        candidate_solver = solve_sheet_electrical
    if candidate_solver is oracle_solver:
        raise ValueError("candidate and test-only oracle callables must be independent")
    if _test_row_executor is not None and publish:
        raise ValueError("focused-test row executors can never publish evidence")
    if publish and output_dir is None:
        raise ValueError("explicit publication requires output_dir")

    plan = build_equivalence_plan(active_contract)
    cases = build_deterministic_audit_cases(source_config, resolved_controller)
    executor = _real_row_executor if _test_row_executor is None else _test_row_executor
    rows: list[EquivalenceEvidenceRow] = []
    failure_plan_index: int | None = None
    for row in plan:
        pair = executor(
            row,
            cases,
            config,
            active_contract,
            oracle_solver,
            candidate_solver,
        )
        required_exact = () if row.family == "electrical" else active_contract.exact_votes
        required_telemetry = (
            () if row.family == "electrical" else active_contract.telemetry_only
        )
        comparison = compare_observations(
            pair.candidate_observation,
            pair.oracle_observation,
            active_contract,
            protocol_voltage_scale_V=pair.protocol_voltage_scale_V,
            required_exact_votes=required_exact,
            required_telemetry_fields=required_telemetry,
        )
        comparison = _comparison_with_validation_errors(
            comparison, pair.validation_errors
        )
        case = (
            cases[(row.grid, row.state)]
            if row.grid is not None and row.state is not None
            else cases[("L1", "legal_critical")]
        )
        input_sha256 = hash_equivalence_input(
            row, _runtime_input_payload(row, case, config), active_contract
        )
        output_payload = {
            "candidate_observation": pair.candidate_observation,
            "oracle_observation": pair.oracle_observation,
            "comparison": comparison,
        }
        rows.append(
            make_evidence_row(
                row,
                comparison,
                input_sha256=input_sha256,
                output_payload=output_payload,
            )
        )
        if not comparison.passed:
            failure_plan_index = row.plan_index
            break

    tables = {
        family: build_equivalence_csv(
            [row for row in rows if row.family == family]
        )
        for family in FAMILY_ORDER
    }
    summary = build_equivalence_summary(rows, active_contract)
    if failure_plan_index is not None:
        summary.update(
            {
                "status": "strict_equivalence_failed_fail_fast",
                "disposition": active_contract.terminal_failure_disposition,
                "all_equivalence_votes_pass": False,
                "fail_fast_triggered": True,
                "failing_plan_index": failure_plan_index,
                "failing_sample_id": rows[-1].sample_id,
            }
        )
    else:
        summary["fail_fast_triggered"] = False
    published: Mapping[str, str] = {}
    if publish:
        assert output_dir is not None
        published = _publish_audit_tables(tables, summary, output_dir)
    return EquivalenceAuditResult(
        rows=tuple(rows),
        tables=tables,
        summary=summary,
        published_paths=published,
    )


def make_evidence_row(
    plan_row: EquivalencePlanRow,
    comparison: EquivalenceComparison,
    *,
    input_sha256: str | None = None,
    output_payload: Any | None = None,
) -> EquivalenceEvidenceRow:
    """Bind a completed comparison to stable input/output hashes."""

    resolved_input = plan_row.input_sha256 if input_sha256 is None else input_sha256
    if len(resolved_input) != 64:
        raise ValueError("input_sha256 must be a 64-character SHA-256 hex digest")
    try:
        bytes.fromhex(resolved_input)
    except ValueError as error:
        raise ValueError("input_sha256 is not hexadecimal") from error
    output = comparison if output_payload is None else output_payload
    return EquivalenceEvidenceRow(
        plan_index=plan_row.plan_index,
        sample_id=plan_row.sample_id,
        family=plan_row.family,
        plan_sha256=plan_row.input_sha256,
        input_sha256=resolved_input,
        output_sha256=canonical_sha256(output),
        passed=comparison.passed,
        maximum_normalized_difference=comparison.maximum_normalized_difference,
        worst_field=comparison.worst_field,
        exact_mismatch_count=len(comparison.exact_mismatches),
        numeric_details=tuple(_jsonable(item) for item in comparison.numeric),
        exact_mismatches=comparison.exact_mismatches,
        telemetry=comparison.telemetry,
        validation_errors=comparison.validation_errors,
    )


def build_equivalence_csv(rows: Sequence[EquivalenceEvidenceRow]) -> str:
    """Build deterministic CSV text; callers choose the task-specific path."""

    stream = io.StringIO(newline="")
    fieldnames = [
        "plan_index",
        "sample_id",
        "family",
        "plan_sha256",
        "input_sha256",
        "output_sha256",
        "passed",
        "maximum_normalized_difference",
        "worst_field",
        "exact_mismatch_count",
        "numeric_details_json",
        "exact_mismatches_json",
        "telemetry_json",
        "validation_errors_json",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=lambda item: item.plan_index):
        writer.writerow(
            {
                "plan_index": row.plan_index,
                "sample_id": row.sample_id,
                "family": row.family,
                "plan_sha256": row.plan_sha256,
                "input_sha256": row.input_sha256,
                "output_sha256": row.output_sha256,
                "passed": str(row.passed).lower(),
                "maximum_normalized_difference": format(
                    row.maximum_normalized_difference, ".17g"
                ),
                "worst_field": row.worst_field or "",
                "exact_mismatch_count": row.exact_mismatch_count,
                "numeric_details_json": canonical_json_bytes(
                    row.numeric_details
                ).decode("utf-8"),
                "exact_mismatches_json": canonical_json_bytes(
                    row.exact_mismatches
                ).decode("utf-8"),
                "telemetry_json": canonical_json_bytes(row.telemetry).decode("utf-8"),
                "validation_errors_json": canonical_json_bytes(
                    row.validation_errors
                ).decode("utf-8"),
            }
        )
    return stream.getvalue()


def build_equivalence_summary(
    rows: Sequence[EquivalenceEvidenceRow],
    contract: EquivalenceContract,
) -> dict[str, Any]:
    """Build a fail-closed summary; incomplete plans can never pass."""

    ordered = sorted(rows, key=lambda row: row.plan_index)
    expected_plan = build_equivalence_plan(contract)
    expected_by_index = {row.plan_index: row for row in expected_plan}
    indexes = [row.plan_index for row in ordered]
    sample_ids = [row.sample_id for row in ordered]
    duplicate_or_missing_identity = bool(
        len(indexes) != len(set(indexes))
        or len(sample_ids) != len(set(sample_ids))
    )
    counts = {
        family: sum(row.family == family for row in ordered)
        for family in FAMILY_ORDER
    }
    identities_valid = all(
        row.plan_index in expected_by_index
        and row.sample_id == expected_by_index[row.plan_index].sample_id
        and row.family == expected_by_index[row.plan_index].family
        and row.plan_sha256 == expected_by_index[row.plan_index].input_sha256
        for row in ordered
    )
    hashes_valid = all(
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        for row in ordered
        for value in (row.plan_sha256, row.input_sha256, row.output_sha256)
    )
    complete = bool(
        not duplicate_or_missing_identity
        and identities_valid
        and hashes_valid
        and counts == dict(contract.expected_counts)
        and indexes == list(range(contract.expected_total))
    )
    all_pass = bool(complete and all(row.passed for row in ordered))
    if all_pass:
        status = "strict_equivalence_pass_pending_runtime_readiness"
        disposition = "PASS_PENDING_RUNTIME_READINESS"
    elif complete:
        status = "strict_equivalence_failed"
        disposition = contract.terminal_failure_disposition
    else:
        status = "incomplete_nonvoting_equivalence_evidence"
        disposition = "INCOMPLETE_NONVOTING"
    return {
        "task_id": "PHASE1_V2_SOURCE_CORRECTED_PERFORMANCE_CLOSURE",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "disposition": disposition,
        "contract_sha256": contract.config_sha256,
        "normalized_relative_difference_max": (
            contract.normalized_relative_difference_max
        ),
        "expected_counts": dict(contract.expected_counts),
        "completed_counts": counts,
        "expected_total": contract.expected_total,
        "completed_total": len(ordered),
        "complete": complete,
        "plan_identities_valid": identities_valid,
        "hash_fields_valid": hashes_valid,
        "all_equivalence_votes_pass": all_pass,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "rows_sha256": canonical_sha256(ordered),
    }


def atomic_write_text(path: Path, text: str, *, overwrite: bool = False) -> None:
    """Publish one validated text artifact with flush/fsync and atomic replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite immutable artifact: {path}")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: Path, payload: Any, *, overwrite: bool = False) -> None:
    """Publish deterministic pretty JSON using the same atomic primitive."""

    text = json.dumps(
        _jsonable(payload),
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, text, overwrite=overwrite)


__all__ = [
    "DEFAULT_CONTRACT_PATH",
    "EXPECTED_EXACT_VOTES",
    "EXPECTED_FAILURE_CLASSES",
    "EXPECTED_TELEMETRY",
    "EquivalenceComparison",
    "EquivalenceContract",
    "EquivalenceAuditResult",
    "EquivalenceEvidenceRow",
    "EquivalenceObservation",
    "EquivalencePlanRow",
    "DeterministicAuditCase",
    "ElectricalPairResult",
    "NumericComparison",
    "NumericField",
    "atomic_write_json",
    "atomic_write_text",
    "build_equivalence_csv",
    "build_deterministic_audit_cases",
    "build_equivalence_plan",
    "build_equivalence_summary",
    "canonical_json_bytes",
    "canonical_sha256",
    "compare_observations",
    "electrical_observation",
    "hash_equivalence_input",
    "load_equivalence_contract",
    "make_evidence_row",
    "PairExecution",
    "run_equivalence_audit",
    "run_electrical_pair",
]
