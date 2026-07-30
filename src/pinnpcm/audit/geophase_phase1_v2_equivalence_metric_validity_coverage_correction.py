"""Mechanical, solver-free coverage correction for draft PR #11.

The original coverage addendum remains immutable.  This module checks its two
known blind spots without executing a candidate, oracle, controller, solver,
or any row of the frozen 57-row plan:

* comparison fields are derived from the frozen production extractors and the
  streaming source schema rather than a hand-written mirror; and
* topology controls start from synthetic raw records, pass through the frozen
  production extraction/normalization functions, and only then reach the
  frozen comparator.
"""

from __future__ import annotations

import ast
import copy
import csv
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_metric_validity_coverage as original_coverage,
)
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as strict_v1


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_equivalence_metric_validity_coverage_correction.yaml"
)
STREAMING_SOURCE = (
    ROOT / "src" / "pinnpcm" / "solvers" / "geophase_phase1_v2_streaming.py"
)
RESULT_SCHEMA_VERSION = (
    "geophase_phase1_v2_equivalence_metric_validity_coverage_correction_result_v1"
)


@dataclass(frozen=True)
class _Scenario:
    family: str
    scenario_id: str
    extractor: str
    observation: strict_v1.EquivalenceObservation


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def load_contract(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("coverage correction contract must be a mapping")
    if payload.get("task_id") != (
        "Q2_PHASE1_V2_EQUIVALENCE_METRIC_VALIDITY_COVERAGE_CORRECTION"
    ):
        raise ValueError("unexpected coverage correction task_id")
    if payload.get("schema_version") != (
        "geophase_phase1_v2_equivalence_metric_validity_coverage_correction_v1"
    ):
        raise ValueError("unexpected coverage correction schema")
    return payload


def verify_authority(config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for identity, record in config["authority"]["immutable_files"].items():
        path = ROOT / record["path"]
        digest = _sha256(path)
        if digest != record["sha256"]:
            raise ValueError(f"coverage correction authority drifted: {identity}")
        observed[identity] = digest
    return observed


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_level_assignment(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise KeyError(f"streaming schema constant not found: {name}")


def _class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise KeyError(name)


def _function_node(
    tree: ast.Module, name: str, *, class_name: str | None = None
) -> ast.FunctionDef:
    body: Sequence[ast.stmt] = (
        _class_node(tree, class_name).body if class_name is not None else tree.body
    )
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise KeyError(f"function not found: {class_name or '<module>'}.{name}")


def _bind(target: ast.expr, value: Any, env: dict[str, Any]) -> dict[str, Any]:
    result = dict(env)
    if isinstance(target, ast.Name):
        result[target.id] = value
        return result
    if isinstance(target, (ast.Tuple, ast.List)):
        values = tuple(value)
        if len(values) != len(target.elts):
            raise ValueError("AST synthetic schema binding length differs")
        for item, bound in zip(target.elts, values, strict=True):
            result = _bind(item, bound, result)
        return result
    raise TypeError(f"unsupported AST schema target: {ast.dump(target)}")


def _iter_values(
    node: ast.expr, env: Mapping[str, Any], ledger_names: tuple[str, ...]
) -> tuple[Any, ...]:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return tuple(ast.literal_eval(node))
    if isinstance(node, ast.Name) and node.id in env:
        value = env[node.id]
        return tuple(value if isinstance(value, (tuple, list, set)) else (value,))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "items"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "ledger_relative_residuals"
    ):
        return tuple((name, 0.0) for name in ledger_names)
    raise ValueError(f"non-static schema iterator: {ast.dump(node)}")


def _render_string(node: ast.expr, env: Mapping[str, Any]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if not isinstance(node, ast.JoinedStr):
        return None
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            if isinstance(value.value, ast.Name):
                key = value.value.id
                parts.append(str(env.get(key, "{" + key + "}")))
            else:
                parts.append("{" + ast.unparse(value.value) + "}")
        else:
            raise TypeError("unsupported f-string schema component")
    return "".join(parts)


def _dict_comp_keys(
    node: ast.DictComp,
    env: Mapping[str, Any],
    ledger_names: tuple[str, ...],
) -> set[str]:
    output: set[str] = set()

    def visit(index: int, current: dict[str, Any]) -> None:
        if index == len(node.generators):
            rendered = _render_string(node.key, current)
            if rendered is not None:
                output.add(rendered)
            return
        generator = node.generators[index]
        for value in _iter_values(generator.iter, current, ledger_names):
            visit(index + 1, _bind(generator.target, value, current))

    visit(0, dict(env))
    return output


def _schema_keys_from_node(
    node: ast.AST,
    env: Mapping[str, Any],
    ledger_names: tuple[str, ...],
) -> set[str]:
    output: set[str] = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        for statement in node.body:
            output.update(_schema_keys_from_node(statement, env, ledger_names))
        return output
    if isinstance(node, ast.For):
        for value in _iter_values(node.iter, env, ledger_names):
            bound = _bind(node.target, value, dict(env))
            for statement in node.body:
                output.update(_schema_keys_from_node(statement, bound, ledger_names))
        for statement in node.orelse:
            output.update(_schema_keys_from_node(statement, env, ledger_names))
        return output
    if isinstance(node, ast.DictComp):
        return _dict_comp_keys(node, env, ledger_names)
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                output.update(_schema_keys_from_node(value, env, ledger_names))
            else:
                rendered = _render_string(key, env)
                if rendered is not None:
                    output.add(rendered)
        return output
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        output.update(_schema_keys_from_node(child, env, ledger_names))
    return output


def _ledger_names_from_comparator_ast() -> tuple[str, ...]:
    tree = _parse(ROOT / "src" / "pinnpcm" / "solvers" / "geophase_phase1_v2_performance_equivalence.py")
    function = _function_node(tree, "_add_ledger_bundle_numeric")
    for node in ast.walk(function):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            if node.target.id == "ledger_name":
                return tuple(ast.literal_eval(node.iter))
    raise RuntimeError("frozen comparator no longer exposes ledger-name contract")


def derive_streaming_schema_from_source() -> dict[str, Any]:
    """Read schema names from source AST without importing the streaming module."""

    tree = _parse(STREAMING_SOURCE)
    ledger_names = _ledger_names_from_comparator_ast()
    event_fields = tuple(_top_level_assignment(tree, "_EVENT_FIELDS"))
    reversal_fields = tuple(_top_level_assignment(tree, "_REVERSAL_FIELDS"))

    scalar_keys: set[str] = set()
    scalar_keys.update(
        _schema_keys_from_node(
            _function_node(tree, "__init__", class_name="_StreamingRecorder"),
            {},
            ledger_names,
        )
    )
    scalar_keys.update(
        _schema_keys_from_node(
            _function_node(tree, "__call__", class_name="_StreamingRecorder"),
            {},
            ledger_names,
        )
    )
    for prefix in ledger_names:
        scalar_keys.update(
            _schema_keys_from_node(
                _function_node(tree, "_ledger_columns"),
                {"prefix": prefix},
                ledger_names,
            )
        )
    controller = _class_node(tree, "_ControllerV2StreamingRecorder")
    for node in controller.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if any(
                isinstance(target, ast.Name) and target.id == "_INITIAL_TELEMETRY"
                for target in targets
            ):
                scalar_keys.update(_schema_keys_from_node(node.value, {}, ledger_names))
    scalar_keys.update(
        _schema_keys_from_node(
            _function_node(
                tree, "_empty_path_telemetry", class_name="_ControllerV2StreamingRecorder"
            ),
            {},
            ledger_names,
        )
    )
    for prefix in ("full", "first_half", "second_half"):
        scalar_keys.update(
            _schema_keys_from_node(
                _function_node(
                    tree, "_path_telemetry", class_name="_ControllerV2StreamingRecorder"
                ),
                {"prefix": prefix},
                ledger_names,
            )
        )
    scalar_keys.update(
        _schema_keys_from_node(
            _function_node(
                tree, "_aggregate_telemetry", class_name="_ControllerV2StreamingRecorder"
            ),
            {},
            ledger_names,
        )
    )
    scalar_keys.update(
        _schema_keys_from_node(
            _function_node(
                tree, "record_accepted_interval", class_name="_ControllerV2StreamingRecorder"
            ),
            {},
            ledger_names,
        )
    )
    return {
        "scalar_fields": tuple(sorted(scalar_keys)),
        "event_fields": event_fields,
        "reversal_fields": reversal_fields,
        "ledger_names": ledger_names,
        "source_sha256": _sha256(STREAMING_SOURCE),
    }


def _nonlinear(
    *, method: str = "damped_newton_krylov", converged: bool = True
) -> SimpleNamespace:
    return SimpleNamespace(
        method=method,
        converged=converged,
        iterations=2,
        krylov_matvecs=5,
        armijo_backtracks=0,
        predictor_picard_iterations=1,
        fallback_picard_iterations=(1 if method == "fail_closed_fixed_point_fallback" else 0),
        scaled_residual_inf=0.0,
        scaled_update_inf=0.0,
    )


def _step(
    *, method: str = "damped_newton_krylov", converged: bool = True
) -> SimpleNamespace:
    step = copy.deepcopy(original_coverage._synthetic_step())
    step.nonlinear = _nonlinear(method=method, converged=converged)
    return step


def _integrity(overall_pass: bool) -> SimpleNamespace:
    return SimpleNamespace(overall_pass=overall_pass)


def _raw_attempt(
    *,
    accepted: bool = True,
    present_paths: tuple[str, ...] = (
        "full_step",
        "first_half_step",
        "second_half_step",
    ),
    failing_path: str | None = None,
    error_class: str | None = None,
    error_message: str | None = None,
    include_optional: bool = True,
) -> SimpleNamespace:
    path_order = ("full_step", "first_half_step", "second_half_step")
    steps = {path: (_step() if path in present_paths else None) for path in path_order}
    failure_index = None if failing_path is None else path_order.index(failing_path)
    integrities: dict[str, Any] = {}
    for index, path in enumerate(path_order):
        integrities[path] = (
            None
            if steps[path] is None
            else _integrity(failure_index is None or index < failure_index)
        )
    diagnostics = SimpleNamespace(
        full_step=integrities["full_step"],
        first_half_step=integrities["first_half_step"],
        second_half_step=integrities["second_half_step"],
        outer_interval_s=(1.0e-9 if include_optional else None),
        half_interval_s=(5.0e-10 if include_optional else None),
        legacy_conductive_increment=(0.0 if include_optional else None),
        legacy_branch_increment=(0.0 if include_optional else None),
        embedded_error=(
            SimpleNamespace(e_T=0.0, e_s=0.0, e_b=0.0, e_V=0.0, e_max=0.0)
            if include_optional
            else None
        ),
    )
    accepted_step = steps["second_half_step"] if accepted else None
    return SimpleNamespace(
        full_candidate=steps["full_step"],
        first_half_candidate=steps["first_half_step"],
        second_half_candidate=steps["second_half_step"],
        step=accepted_step,
        aggregate_ledgers=(
            copy.deepcopy(_step().ledgers) if include_optional else None
        ),
        diagnostics=diagnostics,
        error_class=error_class,
        error_message=error_message,
    )


def _accepted_history_step() -> SimpleNamespace:
    accepted = _step()
    accepted.accepted_first_half = _step()
    return accepted


def _schema_value(name: str, index: int = 0) -> Any:
    lower = name.lower()
    if name in {"case_id", "sample_kind", "last_event_direction", "nonlinear_method", "time_controller"}:
        return "synthetic"
    if any(token in lower for token in ("sha256", "time_semantics")):
        return "synthetic"
    if lower.endswith(("finite", "pass", "converged")):
        return True
    if any(
        token in lower
        for token in (
            "index",
            "count",
            "iterations",
            "matvecs",
            "backtracks",
            "rejections",
        )
    ):
        return int(index)
    return float(index + 1) * 1.0e-9


def _raw_schema_record(
    fields: Sequence[str], *, direction: str, index: int
) -> dict[str, Any]:
    record = {name: _schema_value(name, index) for name in fields}
    record["direction"] = direction
    if "event_index" in record:
        record["event_index"] = index
    if "reversal_index" in record:
        record["reversal_index"] = index
    if "crossing_time_s" in record:
        record["crossing_time_s"] = float(index) * 1.0e-9
    return record


def _raw_progression(
    schema: Mapping[str, Any],
    *,
    event_directions: tuple[str, ...] = ("upward", "downward"),
    reversal_directions: tuple[str, ...] = (
        "heating_to_cooling",
        "cooling_to_heating",
    ),
    completed: bool = True,
    stop_reason: str = "maximum_accepted_steps",
) -> tuple[SimpleNamespace, tuple[SimpleNamespace, ...]]:
    history = tuple(_accepted_history_step() for _ in range(4))
    scalar = {
        name: _schema_value(name)
        for name in schema["scalar_fields"]
        if "{" not in name
    }
    events = tuple(
        _raw_schema_record(schema["event_fields"], direction=direction, index=index)
        for index, direction in enumerate(event_directions, start=1)
    )
    reversals = tuple(
        _raw_schema_record(
            schema["reversal_fields"], direction=direction, index=index
        )
        for index, direction in enumerate(reversal_directions, start=1)
    )
    snapshot = SimpleNamespace(
        time_s=1.0e-9,
        temperature_K=np.zeros((1, 1)),
        conductive_state=np.zeros((1, 1)),
        branch_memory=np.zeros((1, 1)),
        potential_V=np.zeros((1, 1)),
        cell_joule_power_W=np.zeros((1, 1)),
    )
    result = SimpleNamespace(
        protocol_result=SimpleNamespace(
            steps=history,
            diagnostics=SimpleNamespace(accepted_steps=4),
            stop_reason=stop_reason,
            completed=completed,
        ),
        final_state=history[-1].state,
        scalar_records=(scalar,),
        event_records=events,
        reversal_records=reversals,
        field_snapshots=(snapshot,),
    )
    attempts = (_raw_attempt(accepted=False), _raw_attempt(accepted=True))
    return result, attempts


def _validate_streaming_raw_schema(
    result: Any, schema: Mapping[str, Any]
) -> tuple[str, ...]:
    errors: list[str] = []
    event_required = set(schema["event_fields"])
    reversal_required = set(schema["reversal_fields"])
    for index, record in enumerate(result.event_records):
        actual = set(record)
        if actual != event_required:
            errors.append(
                f"event[{index}] schema differs: missing={sorted(event_required-actual)}, "
                f"extra={sorted(actual-event_required)}"
            )
    for index, record in enumerate(result.reversal_records):
        actual = set(record)
        if actual != reversal_required:
            errors.append(
                f"reversal[{index}] schema differs: "
                f"missing={sorted(reversal_required-actual)}, "
                f"extra={sorted(actual-reversal_required)}"
            )
    return tuple(errors)


def _extract_progression(
    result: Any, attempts: Sequence[Any], schema: Mapping[str, Any]
) -> tuple[strict_v1.EquivalenceObservation | None, tuple[str, ...]]:
    schema_errors = _validate_streaming_raw_schema(result, schema)
    if schema_errors:
        return None, schema_errors
    try:
        return strict_v1._progression_observation(result, attempts), ()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return None, (f"production progression extractor rejected raw record: {exc}",)


def _extract_attempt(
    raw: Any,
    *,
    include_only_integrity_passed_steps: bool = False,
    declared_failure: str | None = None,
) -> tuple[strict_v1.EquivalenceObservation | None, tuple[str, ...]]:
    try:
        return (
            strict_v1._attempt_observation(
                raw,
                include_only_integrity_passed_steps=include_only_integrity_passed_steps,
                declared_failure=declared_failure,
            ),
            (),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return None, (f"production attempt extractor rejected raw record: {exc}",)


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


def _category(name: str, kind: str) -> tuple[str, str]:
    if kind == "exact":
        return "B_exact_topology", "canonical_exact_equality"
    if kind == "telemetry":
        return "telemetry_nonvoting", "recorded_nonvoting_exact_field_set"
    if name.endswith(
        (
            ".lateral.x_face_flux_W",
            ".lateral.y_face_flux_W",
            ".lateral.net_cell_outflow_W",
        )
    ):
        return "C_physical_lateral_flux", "parent_analytic_mixed_bound_unchanged"
    if name.endswith(
        (
            ".lateral.internal_pair_cancellation_W",
            ".lateral.face_to_cell_global_residual_W",
        )
    ) or name.endswith("lateral_face_to_cell_global_residual_W"):
        return "C_cancellation_roundoff", "parent_backward_error_bound_unchanged"
    if name.endswith(
        (
            ".lateral.matrix_face_relative_mismatch",
            ".lateral.matrix_face_roundoff_ratio",
        )
    ) or name.endswith(
        (
            "lateral_matrix_face_relative_mismatch",
            "lateral_matrix_face_roundoff_ratio",
            "_lateral_relative_mismatch",
            "_lateral_roundoff_ratio",
        )
    ):
        return "C_lateral_hard_gate", "original_hard_gate_disposition_exact"
    return "A_primary_physical", "strict_v1_1e-12"


def _cardinality_rule(family: str, name: str, kind: str) -> str:
    """Describe static multiplicity without treating a synthetic count as truth."""

    if kind in {"exact", "telemetry"}:
        return "one_mapping_entry; contained_sequence_length_is_runtime_contractual"
    if family == "progression" and name.startswith("history.{interval_index}."):
        return "one_per_plan_maximum_accepted_interval; frozen_plan_value=4"
    if family == "progression" and name.startswith(
        "streaming.scalar.{record_index}."
    ):
        return (
            "trajectory_dependent_fixed-sample records; nonempty required by "
            "_progression_validation_errors; candidate/oracle field sets exact"
        )
    if family == "progression" and name.startswith(
        "streaming.snapshot.{snapshot_index}."
    ):
        return (
            "fixed-time/protocol-discontinuity/event selection dependent; "
            "candidate/oracle field sets exact"
        )
    if family in {"interval", "failure"} and name.startswith(
        ("full_step.", "first_half_step.", "second_half_step.")
    ):
        return (
            "zero_or_one_per_path according to path presence and, for failure rows, "
            "integrity-passed-prefix filtering"
        )
    return "one_per_observation_when_required_when_condition_holds"


def build_production_scenarios(schema: Mapping[str, Any]) -> list[_Scenario]:
    electrical = strict_v1.electrical_observation(_step().electrical)
    scenarios = [
        _Scenario("electrical", "electrical_full", "electrical_observation", electrical)
    ]
    for scenario_id, raw in (
        ("interval_full_accepted", _raw_attempt(accepted=True)),
        (
            "interval_minimal_rejected",
            _raw_attempt(
                accepted=False,
                present_paths=("full_step",),
                include_optional=False,
            ),
        ),
    ):
        observation, errors = _extract_attempt(raw)
        if errors or observation is None:
            raise RuntimeError("; ".join(errors))
        scenarios.append(
            _Scenario("interval", scenario_id, "_attempt_observation", observation)
        )
    for path in ("full_step", "first_half_step", "second_half_step"):
        raw = _raw_attempt(
            accepted=False,
            failing_path=path,
            error_class="RuntimeError",
            error_message=f"{path} synthetic failure",
        )
        observation, errors = _extract_attempt(
            raw,
            include_only_integrity_passed_steps=True,
            declared_failure=f"{path}:nonfinite",
        )
        if errors or observation is None:
            raise RuntimeError("; ".join(errors))
        scenarios.append(
            _Scenario(
                "failure",
                f"failure_at_{path}",
                "_attempt_observation",
                observation,
            )
        )
    progression, attempts = _raw_progression(schema)
    observation, errors = _extract_progression(progression, attempts, schema)
    if errors or observation is None:
        raise RuntimeError("; ".join(errors))
    scenarios.append(
        _Scenario("progression", "progression_full", "_progression_observation", observation)
    )
    empty_progression, empty_attempts = _raw_progression(
        schema, event_directions=(), reversal_directions=()
    )
    observation, errors = _extract_progression(
        empty_progression, empty_attempts, schema
    )
    if errors or observation is None:
        raise RuntimeError("; ".join(errors))
    scenarios.append(
        _Scenario(
            "progression",
            "progression_NA_no_event_or_reversal",
            "_progression_observation",
            observation,
        )
    )
    return scenarios


def build_mechanical_field_contract(
    schema: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[_Scenario]]:
    scenarios = build_production_scenarios(schema)
    family_scenarios: dict[str, set[str]] = {}
    field_records: dict[tuple[str, str, str], dict[str, Any]] = {}
    for scenario in scenarios:
        family_scenarios.setdefault(scenario.family, set()).add(scenario.scenario_id)
        bundles = (
            ("numeric", scenario.observation.numeric),
            ("exact", scenario.observation.exact_votes),
            ("telemetry", scenario.observation.telemetry),
        )
        per_scenario_counts: dict[tuple[str, str], int] = {}
        for kind, mapping in bundles:
            for raw_name, value in mapping.items():
                name = _normalise_field(raw_name)
                key = (scenario.family, kind, name)
                record = field_records.setdefault(
                    key,
                    {
                        "family": scenario.family,
                        "value_kind": kind,
                        "field_pattern": name,
                        "denominator_key": (
                            value.denominator_key if kind == "numeric" else "none"
                        ),
                        "scenarios": set(),
                        "extractors": set(),
                        "counts": {},
                    },
                )
                record["scenarios"].add(scenario.scenario_id)
                record["extractors"].add(scenario.extractor)
                per_scenario_counts[(kind, name)] = (
                    per_scenario_counts.get((kind, name), 0) + 1
                )
        for (kind, name), count in per_scenario_counts.items():
            field_records[(scenario.family, kind, name)]["counts"][
                scenario.scenario_id
            ] = count

    output: list[dict[str, Any]] = []
    for key in sorted(field_records):
        record = field_records[key]
        all_scenarios = family_scenarios[record["family"]]
        present = set(record["scenarios"])
        counts = [record["counts"].get(name, 0) for name in sorted(all_scenarios)]
        category, comparator = _category(
            record["field_pattern"], record["value_kind"]
        )
        output.append(
            {
                "family": record["family"],
                "value_kind": record["value_kind"],
                "field_pattern": record["field_pattern"],
                "denominator_key": record["denominator_key"],
                "category": category,
                "comparator": comparator,
                "minimum_cardinality": min(counts),
                "maximum_cardinality": max(counts),
                "required_when": (
                    "always_in_family"
                    if present == all_scenarios
                    else "scenario_in:" + "|".join(sorted(present))
                ),
                "static_cardinality_rule": _cardinality_rule(
                    record["family"],
                    record["field_pattern"],
                    record["value_kind"],
                ),
                "production_extractors": "|".join(sorted(record["extractors"])),
                "field_name_origin": "production_extractor_output",
                "raw_schema_origin": (
                    "streaming_source_AST+production_extractor_output"
                    if record["family"] == "progression"
                    and record["field_pattern"].startswith("streaming.")
                    else "production_extractor_output"
                ),
            }
        )
    return output, scenarios


def _dag_facts(config: Mapping[str, Any]) -> dict[str, Any]:
    path = (
        ROOT
        / config["authority"]["immutable_files"]["source_corrected_execution_DAG"][
            "path"
        ]
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "evaluation_item_count": int(payload["evaluation_item_count"]),
        "unique_execution_unit_count": int(payload["unique_execution_unit_count"]),
        "reused_evaluation_count": int(payload["reused_evaluation_count"]),
        "formal_execution_count": int(payload["formal_execution_count"]),
        "execution_unit_count": len(payload["execution_units"]),
        "reuse_map_count": len(payload["reuse_map"]),
        "sha256": _sha256(path),
    }


def build_mechanical_plan_contract(
    config: Mapping[str, Any],
    fields: Sequence[Mapping[str, Any]],
    scenarios: Sequence[_Scenario],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contract = strict_v1.load_equivalence_contract()
    plan = strict_v1.build_equivalence_plan(contract)
    dag = _dag_facts(config)
    expected_dag = config["mechanical_coverage"]["execution_DAG_required"]
    dag_pass = all(dag[name] == int(value) for name, value in expected_dag.items())
    scenario_ids: dict[str, list[str]] = {}
    for scenario in scenarios:
        scenario_ids.setdefault(scenario.family, []).append(scenario.scenario_id)
    family_counts = {
        family: sum(field["family"] == family for field in fields)
        for family in strict_v1.FAMILY_ORDER
    }
    rows = [
        {
            "plan_index": row.plan_index,
            "sample_id": row.sample_id,
            "family": row.family,
            "state": row.state or "",
            "grid": row.grid or "",
            "candidate_paths": "|".join(row.candidate_paths),
            "failure_class": row.failure_class or "",
            "maximum_accepted_intervals": row.maximum_accepted_intervals or "",
            "production_scenarios": "|".join(sorted(scenario_ids[row.family])),
            "mechanical_field_template_count": family_counts[row.family],
            "plan_sha256": row.input_sha256,
            "execution_dag_sha256": dag["sha256"],
            "execution_status": "static_only_not_executed",
        }
        for row in plan
    ]
    dag["contract_pass"] = dag_pass
    return rows, dag


def _compare(
    candidate: strict_v1.EquivalenceObservation,
    oracle: strict_v1.EquivalenceObservation,
    *,
    validation_errors: Sequence[str] = (),
) -> strict_v1.EquivalenceComparison:
    comparison = strict_v1.compare_observations(
        candidate,
        oracle,
        strict_v1.load_equivalence_contract(),
        protocol_voltage_scale_V=15.8,
    )
    return strict_v1._comparison_with_validation_errors(comparison, validation_errors)


def run_raw_topology_controls(schema: Mapping[str, Any]) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []

    def record(
        control_id: str,
        candidate: strict_v1.EquivalenceObservation | None,
        oracle: strict_v1.EquivalenceObservation | None,
        *,
        candidate_errors: Sequence[str] = (),
        oracle_errors: Sequence[str] = (),
        validation_errors: Sequence[str] = (),
        expected_accept: bool = False,
        extractor: str,
    ) -> None:
        errors = tuple(candidate_errors) + tuple(oracle_errors)
        comparison = None
        if candidate is not None and oracle is not None and not errors:
            comparison = _compare(
                candidate, oracle, validation_errors=validation_errors
            )
            observed = comparison.passed
            reasons = tuple(comparison.validation_errors) + tuple(
                sorted(comparison.exact_mismatches)
            )
        else:
            observed = False
            reasons = errors
        controls.append(
            {
                "control_id": control_id,
                "expected_accept": expected_accept,
                "observed_accept": observed,
                "passed": bool(expected_accept) == bool(observed),
                "failure_reasons": "|".join(reasons),
                "raw_record_origin": "SimpleNamespace_or_dict",
                "production_extractor": extractor,
                "direct_exact_vote_mutation": False,
                "candidate_or_oracle_execution_count": 0,
            }
        )

    base_raw = _raw_attempt(accepted=True)
    base, base_errors = _extract_attempt(base_raw)
    record(
        "baseline_raw_attempt",
        base,
        base,
        candidate_errors=base_errors,
        oracle_errors=base_errors,
        expected_accept=True,
        extractor="_attempt_observation",
    )

    candidate, errors = _extract_attempt(_raw_attempt(accepted=False))
    record(
        "accepted_rejected_sequence_change",
        candidate,
        base,
        candidate_errors=errors,
        oracle_errors=base_errors,
        extractor="_attempt_observation",
    )

    raw = _raw_attempt(accepted=True)
    raw.full_candidate.nonlinear.method = "alternate_newton"
    candidate, errors = _extract_attempt(raw)
    record(
        "nonlinear_method_change",
        candidate,
        base,
        candidate_errors=errors,
        oracle_errors=base_errors,
        extractor="_attempt_observation",
    )

    raw = _raw_attempt(accepted=True)
    raw.full_candidate.nonlinear.converged = False
    candidate, errors = _extract_attempt(raw)
    record(
        "converged_disposition_change",
        candidate,
        base,
        candidate_errors=errors,
        oracle_errors=base_errors,
        extractor="_attempt_observation",
    )

    raw = _raw_attempt(accepted=True)
    raw.second_half_candidate.nonlinear.method = "fail_closed_fixed_point_fallback"
    candidate, errors = _extract_attempt(raw)
    record(
        "fallback_disposition_change",
        candidate,
        base,
        candidate_errors=errors,
        oracle_errors=base_errors,
        extractor="_attempt_observation",
    )

    failure_oracle_raw = _raw_attempt(
        accepted=False,
        failing_path="full_step",
        error_class="RuntimeError",
        error_message="full_step synthetic failure",
    )
    failure_oracle, failure_oracle_errors = _extract_attempt(
        failure_oracle_raw,
        include_only_integrity_passed_steps=True,
        declared_failure="full_step:nonfinite",
    )
    for control_id, raw in (
        (
            "expected_failure_type_change",
            _raw_attempt(
                accepted=False,
                failing_path="full_step",
                error_class="ValueError",
                error_message="full_step synthetic failure",
            ),
        ),
        (
            "expected_failure_location_change",
            _raw_attempt(
                accepted=False,
                failing_path="full_step",
                error_class="RuntimeError",
                error_message="first_half_step synthetic failure",
            ),
        ),
        (
            "failure_changed_to_success",
            _raw_attempt(
                accepted=False,
                failing_path="full_step",
                error_class=None,
                error_message=None,
            ),
        ),
    ):
        candidate, errors = _extract_attempt(
            raw,
            include_only_integrity_passed_steps=True,
            declared_failure="full_step:nonfinite",
        )
        record(
            control_id,
            candidate,
            failure_oracle,
            candidate_errors=errors,
            oracle_errors=failure_oracle_errors,
            extractor="_attempt_observation",
        )
    failure_candidate, failure_errors = _extract_attempt(
        _raw_attempt(
            accepted=True,
            error_class="RuntimeError",
            error_message="unexpected synthetic failure",
        )
    )
    record(
        "success_changed_to_failure",
        failure_candidate,
        base,
        candidate_errors=failure_errors,
        oracle_errors=base_errors,
        extractor="_attempt_observation",
    )

    progression_raw, progression_attempts = _raw_progression(schema)
    progression, progression_errors = _extract_progression(
        progression_raw, progression_attempts, schema
    )

    def progression_control(
        control_id: str,
        mutate: Any,
        *,
        validation: bool = False,
    ) -> None:
        raw = copy.deepcopy(progression_raw)
        attempts = copy.deepcopy(progression_attempts)
        mutate(raw, attempts)
        candidate, errors = _extract_progression(raw, attempts, schema)
        validation_errors: tuple[str, ...] = ()
        if validation and candidate is not None and not errors:
            validation_errors = strict_v1._progression_validation_errors(
                raw, attempts, 4
            )
        record(
            control_id,
            candidate,
            progression,
            candidate_errors=errors,
            oracle_errors=progression_errors,
            validation_errors=validation_errors,
            extractor=(
                "_progression_observation+_progression_validation_errors"
                if validation
                else "_progression_observation"
            ),
        )

    progression_control(
        "event_count_change",
        lambda raw, _attempts: setattr(raw, "event_records", raw.event_records[:1]),
    )
    progression_control(
        "event_direction_change",
        lambda raw, _attempts: raw.event_records[0].__setitem__("direction", "downward"),
    )
    progression_control(
        "event_chronology_change",
        lambda raw, _attempts: setattr(
            raw, "event_records", tuple(reversed(raw.event_records))
        ),
    )
    progression_control(
        "reversal_count_change",
        lambda raw, _attempts: setattr(
            raw, "reversal_records", raw.reversal_records[:1]
        ),
    )
    progression_control(
        "reversal_direction_change",
        lambda raw, _attempts: raw.reversal_records[0].__setitem__(
            "direction", "cooling_to_heating"
        ),
    )
    progression_control(
        "reversal_order_change",
        lambda raw, _attempts: setattr(
            raw, "reversal_records", tuple(reversed(raw.reversal_records))
        ),
    )

    def missing_topology(raw: Any, _attempts: Any) -> None:
        del raw.event_records[0]["direction"]

    progression_control("required_topology_field_missing", missing_topology)

    def extra_topology(raw: Any, _attempts: Any) -> None:
        raw.event_records[0]["unregistered_topology"] = "unexpected"

    progression_control("unregistered_topology_field_extra", extra_topology)

    def missing_numeric(raw: Any, _attempts: Any) -> None:
        del raw.scalar_records[0]["time_s"]

    progression_control("required_numeric_field_missing", missing_numeric)

    def extra_numeric(raw: Any, _attempts: Any) -> None:
        raw.scalar_records[0]["unregistered_power_W"] = 1.0

    progression_control("unregistered_numeric_field_extra", extra_numeric)

    def validation_error(raw: Any, _attempts: Any) -> None:
        raw.protocol_result.diagnostics.accepted_steps = 3

    progression_control("validation_error_injected", validation_error, validation=True)

    raw = _raw_attempt(accepted=True)
    del raw.full_candidate.nonlinear.krylov_matvecs
    candidate, errors = _extract_attempt(raw)
    record(
        "required_telemetry_source_field_missing",
        candidate,
        base,
        candidate_errors=errors,
        oracle_errors=base_errors,
        extractor="_attempt_observation",
    )
    return controls


def build_result(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config = load_contract(config_path)
    authority = verify_authority(config)
    schema = derive_streaming_schema_from_source()
    fields, scenarios = build_mechanical_field_contract(schema)
    plan, dag = build_mechanical_plan_contract(config, fields, scenarios)
    controls = run_raw_topology_controls(schema)

    plan_counts = {
        family: sum(row["family"] == family for row in plan)
        for family in strict_v1.FAMILY_ORDER
    }
    expected_plan_counts = {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }
    controls_pass = bool(controls and all(row["passed"] for row in controls))
    field_sources_pass = bool(
        fields
        and all(
            row["field_name_origin"] == "production_extractor_output"
            for row in fields
        )
    )
    exact_fields = {
        row["field_pattern"]
        for row in fields
        if row["value_kind"] == "exact"
    }
    exact_pass = exact_fields == set(strict_v1.EXPECTED_EXACT_VOTES)
    pass_correction = bool(
        len(plan) == 57
        and plan_counts == expected_plan_counts
        and dag["contract_pass"]
        and field_sources_pass
        and exact_pass
        and controls_pass
    )
    old_count = int(
        config["preserved_results"]["original_coverage_addendum"][
            "claimed_template_count"
        ]
    )
    summary = {
        "task_id": config["task_id"],
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "completed_solver_free_pre_merge_coverage_correction",
        "validity": "valid" if pass_correction else "invalid",
        "claim_status": "qualified_supported" if pass_correction else "forbidden",
        "coverage_correction_disposition": (
            "COVERAGE_CORRECTION_PASS"
            if pass_correction
            else "COVERAGE_ADDENDUM_FAIL"
        ),
        "final_route": (
            "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
            if pass_correction
            else "STOP_S2_ACTIVATE_GAMMA_SUB"
        ),
        "strict_equivalence_v1_disposition": "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR",
        "strict_equivalence_v1_completed_rows": 12,
        "strict_equivalence_v1_expected_rows": 57,
        "parent_metric_validity_disposition": "GO_VERSIONED_EQUIVALENCE_V2_AUDIT",
        "parent_metric_validity_scope_unchanged": True,
        "original_coverage_disposition_preserved": "COVERAGE_ADDENDUM_PASS",
        "original_coverage_claimed_template_count": old_count,
        "original_209_completeness_claim_superseded": True,
        "mechanical_field_template_count": len(fields),
        "mechanical_field_count_differs_from_original_claim": len(fields) != old_count,
        "mechanical_field_name_source_pass": field_sources_pass,
        "mechanical_field_family_counts": {
            family: sum(row["family"] == family for row in fields)
            for family in strict_v1.FAMILY_ORDER
        },
        "production_scenario_count": len(scenarios),
        "production_scenario_ids": [scenario.scenario_id for scenario in scenarios],
        "streaming_scalar_schema_field_count": len(schema["scalar_fields"]),
        "streaming_event_schema_field_count": len(schema["event_fields"]),
        "streaming_reversal_schema_field_count": len(schema["reversal_fields"]),
        "streaming_schema_source_sha256": schema["source_sha256"],
        "plan_rows_mechanically_mapped": len(plan),
        "plan_family_counts": plan_counts,
        "execution_DAG_facts": dag,
        "B_exact_fields": sorted(exact_fields),
        "B_exact_contract_pass": exact_pass,
        "raw_control_count_including_baseline": len(controls),
        "raw_controls_all_use_production_extractors": all(
            row["production_extractor"] for row in controls
        ),
        "raw_controls_direct_exact_vote_mutation_count": sum(
            bool(row["direct_exact_vote_mutation"]) for row in controls
        ),
        "raw_controls_pass": controls_pass,
        "authority_hashes": authority,
        "parent_metric_evidence_regenerated": False,
        "frozen_v1_row_execution_count": 0,
        "held_out_45_row_execution_count": 0,
        "equivalence_v2_execution_count": 0,
        "candidate_or_oracle_execution_count": 0,
        "controller_execution_count": 0,
        "runtime_readiness_executed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "optimized_solver_equivalence_status": "forbidden_unassessed",
        "S2_scientific_claim_status": "forbidden_unassessed",
    }
    return {
        "config": config,
        "schema": schema,
        "fields": fields,
        "plan": plan,
        "controls": controls,
        "summary": summary,
    }


def _csv_bytes(rows: Iterable[Mapping[str, Any]], fieldnames: list[str]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name) for name in fieldnames})
    return stream.getvalue().encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite coverage correction: {path}")
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def publish_result(result: Mapping[str, Any]) -> dict[str, str]:
    outputs = result["config"]["outputs"]
    field_path = ROOT / outputs["mechanical_field_contract"]
    plan_path = ROOT / outputs["mechanical_plan_contract"]
    controls_path = ROOT / outputs["raw_topology_controls"]
    summary_path = ROOT / outputs["summary"]
    fields = result["fields"]
    plan = result["plan"]
    controls = result["controls"]
    _atomic_write(field_path, _csv_bytes(fields, list(fields[0])))
    _atomic_write(plan_path, _csv_bytes(plan, list(plan[0])))
    _atomic_write(controls_path, _csv_bytes(controls, list(controls[0])))
    summary = dict(result["summary"])
    summary["evidence_sha256"] = {
        field_path.name: _sha256(field_path),
        plan_path.name: _sha256(plan_path),
        controls_path.name: _sha256(controls_path),
    }
    _atomic_write(summary_path, _canonical_json_bytes(summary) + b"\n")
    return {
        "mechanical_field_contract": str(field_path),
        "mechanical_plan_contract": str(plan_path),
        "raw_topology_controls": str(controls_path),
        "summary": str(summary_path),
    }


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "build_mechanical_field_contract",
    "build_mechanical_plan_contract",
    "build_production_scenarios",
    "build_result",
    "derive_streaming_schema_from_source",
    "load_contract",
    "publish_result",
    "run_raw_topology_controls",
    "verify_authority",
]
