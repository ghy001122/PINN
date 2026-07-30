"""Solver-free static coverage addendum for the Phase 1-v2 metric audit.

This module inventories the frozen 57-row comparator contract and exercises
only synthetic comparator records.  It never imports or executes the frozen
candidate, oracle, controller, scientific solver, readiness path, or runner.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

import numpy as np
import yaml

from pinnpcm.audit.geophase_phase1_v2_equivalence_metric_validity import (
    _cancellation_bound,
    _physical_bound,
)
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as strict_v1


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_equivalence_metric_validity_coverage_addendum.yaml"
)
RESULT_SCHEMA_VERSION = (
    "geophase_phase1_v2_equivalence_metric_validity_coverage_result_v1"
)

_PHYSICAL_SUFFIXES = {
    "lateral.x_face_flux_W",
    "lateral.y_face_flux_W",
    "lateral.net_cell_outflow_W",
}
_BOUNDARY_SUFFIXES = {
    "lateral.boundary_face_flux_W",
    "lateral.boundary_outflow_W",
}
_CANCELLATION_SUFFIXES = {
    "lateral.internal_pair_cancellation_W",
    "lateral.face_to_cell_global_residual_W",
}
_HARD_GATE_SUFFIXES = {
    "lateral.matrix_face_relative_mismatch",
    "lateral.matrix_face_roundoff_ratio",
}

_DIAGNOSTIC_FIELDS = {
    "diagnostics.outer_interval_s": "time_s",
    "diagnostics.half_interval_s": "time_s",
    "diagnostics.legacy_conductive_increment": "relative_residual",
    "diagnostics.legacy_branch_increment": "relative_residual",
    "embedded_error.e_T": "relative_residual",
    "embedded_error.e_s": "relative_residual",
    "embedded_error.e_b": "relative_residual",
    "embedded_error.e_V": "relative_residual",
    "embedded_error.e_max": "relative_residual",
}

_PROGRESSION_FINAL_STATE_FIELDS = {
    "streaming.final_state.time_s": "time_s",
    "streaming.final_state.temperature_K": "temperature_K",
    "streaming.final_state.conductive_state": "conductive_state",
    "streaming.final_state.branch_memory": "branch_memory",
    "streaming.final_state.device_voltage_V": "device_voltage_V",
}

_PROGRESSION_SNAPSHOT_FIELDS = {
    "streaming.snapshot.{snapshot_index}.time_s": "time_s",
    "streaming.snapshot.{snapshot_index}.temperature_K": "temperature_K",
    "streaming.snapshot.{snapshot_index}.conductive_state": "conductive_state",
    "streaming.snapshot.{snapshot_index}.branch_memory": "branch_memory",
    "streaming.snapshot.{snapshot_index}.potential_V": "potential_V",
    "streaming.snapshot.{snapshot_index}.cell_joule_power_W": "power_W",
}

_BASE_SCALAR_FIELDS = {
    "time_s": "time_s",
    "input_voltage_V": "device_voltage_V",
    "device_voltage_V": "device_voltage_V",
    "terminal_current_A": "terminal_current_A",
    "terminal_device_power_W": "power_W",
    "maximum_temperature_K": "temperature_K",
    "minimum_temperature_K": "temperature_K",
    "mean_temperature_K": "temperature_K",
    "mean_conductive_state": "conductive_state",
    "mean_branch_memory": "branch_memory",
    "last_event_time_s": "time_s",
    "lateral_matrix_face_relative_mismatch": "relative_residual",
    "lateral_matrix_face_roundoff_ratio": "relative_residual",
    "lateral_face_to_cell_global_residual_W": "power_W",
}
for _ledger in ("thermal", "circuit", "combined", "device_power"):
    for _field in (
        "input_power_W",
        "accounted_power_W",
        "signed_residual_W",
        "relative_residual",
    ):
        _BASE_SCALAR_FIELDS[f"{_ledger}_{_field}"] = (
            "relative_residual" if _field == "relative_residual" else "power_W"
        )

_CONTROLLER_SCALAR_FIELDS = {
    "voltage_scale_V": "device_voltage_V",
    "outer_interval_s": "time_s",
    "e_T": "relative_residual",
    "e_s": "relative_residual",
    "e_b": "relative_residual",
    "e_V": "relative_residual",
    "e_max": "relative_residual",
    "legacy_max_absolute_delta_s": "conductive_state",
    "legacy_max_absolute_delta_b": "branch_memory",
}
for _path in ("full", "first_half", "second_half"):
    for _field in (
        "lateral_relative_mismatch",
        "lateral_roundoff_ratio",
        "scaled_residual_inf",
    ):
        _CONTROLLER_SCALAR_FIELDS[f"{_path}_{_field}"] = "relative_residual"
    for _ledger in ("thermal", "circuit", "combined", "device_power"):
        _CONTROLLER_SCALAR_FIELDS[
            f"{_path}_{_ledger}_relative_residual"
        ] = "relative_residual"
for _ledger in ("thermal", "circuit", "combined", "device_power"):
    _CONTROLLER_SCALAR_FIELDS[
        f"aggregate_{_ledger}_relative_residual"
    ] = "relative_residual"


@dataclass(frozen=True)
class _SyntheticStorage:
    explicit_plane_storage_rate_W: float = 0.0
    closure_storage_rate_W: float = 0.0
    effective_storage_rate_W: float = 0.0
    vertical_sink_power_W: float = 0.0
    lateral_boundary_outflow_W: float = 0.0


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


def load_coverage_contract(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("coverage addendum must contain a mapping")
    if payload.get("task_id") != (
        "Q2_PHASE1_V2_EQUIVALENCE_METRIC_VALIDITY_COVERAGE_ADDENDUM"
    ):
        raise ValueError("unexpected coverage addendum task_id")
    if payload.get("schema_version") != (
        "geophase_phase1_v2_equivalence_metric_validity_coverage_addendum_v1"
    ):
        raise ValueError("unexpected coverage addendum schema")
    return payload


def verify_coverage_authority(config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    sections = (
        config["parent_metric_validity"]["immutable_files"],
        config["frozen_static_authority"],
    )
    for section in sections:
        for identity, record in section.items():
            path = ROOT / record["path"]
            digest = _sha256(path)
            if digest != record["sha256"]:
                raise ValueError(f"coverage authority drifted: {identity}")
            observed[identity] = digest
    return observed


def _balance(name: str, terms: Mapping[str, float]) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        input_power_W=0.0,
        accounted_power_W=0.0,
        signed_residual_W=0.0,
        relative_residual=0.0,
        terms_W=dict(terms),
    )


def _synthetic_step() -> SimpleNamespace:
    terms = {
        "thermal": {
            "explicit_plane_storage_rate_W": 0.0,
            "s2_closure_storage_rate_W": 0.0,
            "vertical_sink_power_W": 0.0,
            "lateral_boundary_outflow_W": 0.0,
        },
        "circuit": {
            "load_resistor_power_W": 0.0,
            "capacitor_physical_energy_rate_W": 0.0,
            "capacitor_backward_euler_dissipation_W": 0.0,
            "terminal_device_power_W": 0.0,
        },
        "combined": {
            "load_resistor_power_W": 0.0,
            "capacitor_physical_energy_rate_W": 0.0,
            "capacitor_backward_euler_dissipation_W": 0.0,
            "explicit_plane_storage_rate_W": 0.0,
            "s2_closure_storage_rate_W": 0.0,
            "vertical_sink_power_W": 0.0,
            "lateral_boundary_outflow_W": 0.0,
        },
        "device_power": {"field_joule_power_W": 0.0},
    }
    ledgers = SimpleNamespace(
        storage=_SyntheticStorage(),
        **{name: _balance(name, values) for name, values in terms.items()},
    )
    return SimpleNamespace(
        state=SimpleNamespace(
            time_s=0.0,
            temperature_K=np.zeros((1, 1)),
            conductive_state=np.zeros((1, 1)),
            branch_memory=np.zeros((1, 1)),
            device_voltage_V=0.0,
        ),
        electrical=SimpleNamespace(
            potential_V=np.zeros((1, 1)),
            source_current_A=0.0,
            ground_current_A=0.0,
            cell_joule_power_W=np.zeros((1, 1)),
            joule_power_W=0.0,
            terminal_device_power_W=0.0,
            relative_current_imbalance=0.0,
            relative_power_imbalance=0.0,
        ),
        lateral_flux=SimpleNamespace(
            net_cell_outflow_W=0.0,
            x_face_flux_W=0.0,
            y_face_flux_W=0.0,
            boundary_face_flux_W=0.0,
            boundary_outflow_W=0.0,
            internal_pair_cancellation_W=0.0,
            face_to_cell_global_residual_W=0.0,
            matrix_face_relative_mismatch=0.0,
            matrix_face_roundoff_ratio=0.0,
        ),
        nonlinear=SimpleNamespace(
            scaled_residual_inf=0.0,
            scaled_update_inf=0.0,
        ),
        ledgers=ledgers,
    )


def _category_for_field(name: str) -> tuple[str, str, str]:
    suffix = name.split("{step_prefix}.", 1)[-1]
    if suffix in _PHYSICAL_SUFFIXES:
        return (
            "C_physical_lateral_flux",
            "parent_analytic_mixed_bound_unchanged",
            "ratio<=1; voting",
        )
    if suffix in _BOUNDARY_SUFFIXES:
        return (
            "C_no_flux_boundary",
            "unchanged_strict_v1_normalized_relative_difference",
            "<=1e-12",
        )
    if suffix in _CANCELLATION_SUFFIXES:
        return (
            "C_cancellation_roundoff",
            "parent_analytic_backward_error_bound_unchanged",
            "ratio<=1; signed raw value retained",
        )
    if suffix in _HARD_GATE_SUFFIXES:
        return (
            "C_lateral_hard_gate",
            "exact_original_hard_gate_disposition",
            "both pass and dispositions match",
        )
    return (
        "A_primary_physical",
        "unchanged_strict_v1_normalized_relative_difference",
        "<=1e-12",
    )


def _field_row(
    *,
    component: str,
    families: str,
    field_pattern: str,
    value_kind: str,
    denominator_key: str,
    category: str,
    comparator: str,
    vote_rule: str,
    cardinality: str,
    required_when: str,
    source: str,
) -> dict[str, str]:
    return {
        "component_contract": component,
        "families": families,
        "field_pattern": field_pattern,
        "value_kind": value_kind,
        "denominator_key": denominator_key,
        "category": category,
        "comparator": comparator,
        "vote_rule": vote_rule,
        "cardinality": cardinality,
        "required_when": required_when,
        "source": source,
    }


def build_static_field_contract() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    electrical = strict_v1.electrical_observation(
        _synthetic_step().electrical
    ).numeric
    for name, field in sorted(electrical.items()):
        rows.append(
            _field_row(
                component="electrical_observation_v1",
                families="electrical",
                field_pattern=name,
                value_kind="numeric",
                denominator_key=field.denominator_key,
                category="A_primary_physical",
                comparator="unchanged_strict_v1_normalized_relative_difference",
                vote_rule="<=1e-12",
                cardinality="one",
                required_when="every electrical row",
                source="strict_v1.electrical_observation",
            )
        )

    step_fields: dict[str, strict_v1.NumericField] = {}
    strict_v1._add_step_numeric(step_fields, "{step_prefix}", _synthetic_step())
    for name, field in sorted(step_fields.items()):
        category, comparator, rule = _category_for_field(name)
        rows.append(
            _field_row(
                component="step_bundle_v1",
                families="interval|progression|failure",
                field_pattern=name,
                value_kind="numeric",
                denominator_key=field.denominator_key,
                category=category,
                comparator=comparator,
                vote_rule=rule,
                cardinality="one per materialized path",
                required_when=(
                    "normal interval: all three paths; progression: accepted and "
                    "accepted_first_half per interval; failure: only integrity-passed "
                    "paths before the declared failing path"
                ),
                source="strict_v1._add_step_numeric",
            )
        )

    aggregate_fields: dict[str, strict_v1.NumericField] = {}
    strict_v1._add_ledger_bundle_numeric(
        aggregate_fields, "{aggregate_prefix}", _synthetic_step().ledgers
    )
    for name, field in sorted(aggregate_fields.items()):
        rows.append(
            _field_row(
                component="aggregate_ledger_bundle_v1",
                families="interval",
                field_pattern=name,
                value_kind="numeric",
                denominator_key=field.denominator_key,
                category="A_primary_physical",
                comparator="unchanged_strict_v1_normalized_relative_difference",
                vote_rule="<=1e-12",
                cardinality="one",
                required_when="successful three-path embedded interval",
                source="strict_v1._add_ledger_bundle_numeric",
            )
        )

    for name, denominator in sorted(_DIAGNOSTIC_FIELDS.items()):
        rows.append(
            _field_row(
                component="embedded_attempt_diagnostics_v1",
                families="interval|failure",
                field_pattern=name,
                value_kind="numeric",
                denominator_key=denominator,
                category="A_primary_physical",
                comparator="unchanged_strict_v1_normalized_relative_difference",
                vote_rule="<=1e-12",
                cardinality="zero_or_one",
                required_when="field is defined by the frozen attempt diagnostics",
                source="strict_v1._attempt_observation",
            )
        )

    for name in strict_v1.EXPECTED_EXACT_VOTES:
        rows.append(
            _field_row(
                component="exact_topology_v1",
                families="interval|progression|failure",
                field_pattern=name,
                value_kind="exact",
                denominator_key="none",
                category="B_exact_topology",
                comparator="canonical_exact_equality",
                vote_rule="exact field set and exact value equality",
                cardinality="one",
                required_when="every non-electrical row",
                source="strict_v1.EXPECTED_EXACT_VOTES",
            )
        )
    for name in strict_v1.EXPECTED_TELEMETRY:
        rows.append(
            _field_row(
                component="telemetry_v1",
                families="interval|progression|failure",
                field_pattern=name,
                value_kind="telemetry",
                denominator_key="none",
                category="telemetry_nonvoting",
                comparator="recorded_but_nonvoting",
                vote_rule="field set exact; value nonvoting",
                cardinality="one",
                required_when="every non-electrical row",
                source="strict_v1.EXPECTED_TELEMETRY",
            )
        )

    for name, denominator in sorted(_PROGRESSION_FINAL_STATE_FIELDS.items()):
        rows.append(
            _field_row(
                component="progression_final_state_v1",
                families="progression",
                field_pattern=name,
                value_kind="numeric",
                denominator_key=denominator,
                category="A_primary_physical",
                comparator="unchanged_strict_v1_normalized_relative_difference",
                vote_rule="<=1e-12",
                cardinality="one",
                required_when="every progression row",
                source="strict_v1._progression_observation",
            )
        )
    scalar_fields = {**_BASE_SCALAR_FIELDS, **_CONTROLLER_SCALAR_FIELDS}
    for name, denominator in sorted(scalar_fields.items()):
        category = (
            "C_lateral_hard_gate"
            if name
            in {
                "lateral_matrix_face_relative_mismatch",
                "lateral_matrix_face_roundoff_ratio",
            }
            else "C_cancellation_roundoff"
            if name == "lateral_face_to_cell_global_residual_W"
            else "A_primary_physical"
        )
        comparator = (
            "exact_original_hard_gate_disposition"
            if category == "C_lateral_hard_gate"
            else "parent_analytic_backward_error_bound_unchanged"
            if category == "C_cancellation_roundoff"
            else "unchanged_strict_v1_normalized_relative_difference"
        )
        rule = (
            "both pass and dispositions match"
            if category == "C_lateral_hard_gate"
            else "ratio<=1; signed raw value retained"
            if category == "C_cancellation_roundoff"
            else "<=1e-12"
        )
        rows.append(
            _field_row(
                component="progression_scalar_v1",
                families="progression",
                field_pattern=f"streaming.scalar.{{record_index}}.{name}",
                value_kind="numeric",
                denominator_key=denominator,
                category=category,
                comparator=comparator,
                vote_rule=rule,
                cardinality="repeated by fixed scalar record index",
                required_when="value is numeric in the fixed streaming schema",
                source="streaming scalar schema plus strict_v1._streaming_denominator",
            )
        )
    for name, denominator in sorted(_PROGRESSION_SNAPSHOT_FIELDS.items()):
        rows.append(
            _field_row(
                component="progression_snapshot_v1",
                families="progression",
                field_pattern=name,
                value_kind="numeric",
                denominator_key=denominator,
                category="A_primary_physical",
                comparator="unchanged_strict_v1_normalized_relative_difference",
                vote_rule="<=1e-12",
                cardinality="repeated by retained snapshot index",
                required_when="snapshot is present under the frozen streaming schema",
                source="strict_v1._progression_observation",
            )
        )

    for guard in (
        "numeric_field_sets_exact",
        "exact_vote_field_sets_exact",
        "telemetry_field_sets_exact",
        "validation_errors_empty",
        "denominator_identities_exact",
        "array_shapes_exact",
        "numeric_values_finite",
    ):
        rows.append(
            _field_row(
                component="structural_guards_v1",
                families="electrical|interval|progression|failure",
                field_pattern=guard,
                value_kind="structural",
                denominator_key="none",
                category="structural_fail_closed",
                comparator="exact_schema_validation",
                vote_rule="must pass",
                cardinality="one",
                required_when="every comparison row",
                source="strict_v1.compare_observations and row validation",
            )
        )
    identities = {
        (row["component_contract"], row["field_pattern"]) for row in rows
    }
    if len(identities) != len(rows):
        raise RuntimeError("static field contract contains duplicate identities")
    return rows


def build_plan_output_contract() -> list[dict[str, Any]]:
    contract = strict_v1.load_equivalence_contract()
    plan = strict_v1.build_equivalence_plan(contract)
    output: list[dict[str, Any]] = []
    for row in plan:
        components = {
            "electrical": (
                "electrical_observation_v1",
                "structural_guards_v1",
            ),
            "interval": (
                "step_bundle_v1",
                "aggregate_ledger_bundle_v1",
                "embedded_attempt_diagnostics_v1",
                "exact_topology_v1",
                "telemetry_v1",
                "structural_guards_v1",
            ),
            "progression": (
                "step_bundle_v1",
                "progression_final_state_v1",
                "progression_scalar_v1",
                "progression_snapshot_v1",
                "exact_topology_v1",
                "telemetry_v1",
                "structural_guards_v1",
            ),
            "failure": (
                "step_bundle_v1",
                "embedded_attempt_diagnostics_v1",
                "exact_topology_v1",
                "telemetry_v1",
                "structural_guards_v1",
            ),
        }[row.family]
        output.append(
            {
                "plan_index": row.plan_index,
                "sample_id": row.sample_id,
                "family": row.family,
                "state": row.state or "",
                "grid": row.grid or "",
                "interval_class": row.interval_class or "",
                "candidate_paths": "|".join(row.candidate_paths),
                "failure_class": row.failure_class or "",
                "maximum_accepted_intervals": (
                    ""
                    if row.maximum_accepted_intervals is None
                    else row.maximum_accepted_intervals
                ),
                "component_contracts": "|".join(components),
                "plan_sha256": row.input_sha256,
                "execution_status": "static_contract_only_not_executed",
            }
        )
    return output


def _baseline_exact_votes() -> dict[str, Any]:
    return {
        "nonlinear_method": (
            ("full_step", "damped_newton_krylov"),
            ("first_half_step", "damped_newton_krylov"),
            ("second_half_step", "damped_newton_krylov"),
        ),
        "converged_disposition": (
            ("full_step", True),
            ("first_half_step", True),
            ("second_half_step", True),
        ),
        "fallback_disposition": (
            ("full_step", False),
            ("first_half_step", False),
            ("second_half_step", False),
        ),
        "accepted_rejected_sequence": ("rejected", "accepted"),
        "failure_classification": "none",
        "event_count_direction_and_order": ("upward", "downward"),
        "reversal_count_direction_and_order": (
            "heating_to_cooling",
            "cooling_to_heating",
        ),
    }


def _baseline_telemetry() -> dict[str, Any]:
    return {name: (0,) for name in strict_v1.EXPECTED_TELEMETRY}


def _baseline_observation() -> strict_v1.EquivalenceObservation:
    return strict_v1.EquivalenceObservation(
        numeric={
            "full_step.state.temperature_K": strict_v1.NumericField(
                np.array([336.0, 336.5]), "temperature_K"
            ),
            "full_step.state.conductive_state": strict_v1.NumericField(
                np.array([0.4, 0.6]), "conductive_state"
            ),
            "full_step.state.branch_memory": strict_v1.NumericField(
                np.array([0.9, 0.8]), "branch_memory"
            ),
            "full_step.state.device_voltage_V": strict_v1.NumericField(
                12.5, "device_voltage_V"
            ),
            "full_step.electrical.potential_V": strict_v1.NumericField(
                np.array([12.5, 0.0]), "potential_V"
            ),
            "full_step.electrical.source_current_A": strict_v1.NumericField(
                2.0e-6, "terminal_current_A"
            ),
            "full_step.electrical.joule_power_W": strict_v1.NumericField(
                2.5e-5, "power_W"
            ),
            "full_step.ledgers.thermal.input_power_W": strict_v1.NumericField(
                2.5e-5,
                "ledger_power_terms",
                scale_group="full_step:s2_thermal",
            ),
            "full_step.ledgers.thermal.accounted_power_W": strict_v1.NumericField(
                2.5e-5,
                "ledger_power_terms",
                scale_group="full_step:s2_thermal",
            ),
            "full_step.ledgers.thermal.signed_residual_W": strict_v1.NumericField(
                0.0,
                "ledger_power_terms",
                scale_group="full_step:s2_thermal",
            ),
            "full_step.ledgers.thermal.relative_residual": strict_v1.NumericField(
                0.0, "relative_residual"
            ),
            "full_step.lateral.x_face_flux_W": strict_v1.NumericField(
                np.array([2.0e-6, -1.0e-6]), "power_W"
            ),
            "full_step.lateral.y_face_flux_W": strict_v1.NumericField(
                np.array([5.0e-7, -5.0e-7]), "power_W"
            ),
            "full_step.lateral.net_cell_outflow_W": strict_v1.NumericField(
                np.array([2.5e-6, -1.5e-6]), "power_W"
            ),
            "full_step.lateral.boundary_face_flux_W": strict_v1.NumericField(
                np.zeros(2), "power_W"
            ),
            "full_step.lateral.boundary_outflow_W": strict_v1.NumericField(
                0.0, "power_W"
            ),
            "full_step.lateral.internal_pair_cancellation_W": (
                strict_v1.NumericField(0.0, "power_W")
            ),
            "full_step.lateral.face_to_cell_global_residual_W": (
                strict_v1.NumericField(0.0, "power_W")
            ),
            "full_step.lateral.matrix_face_relative_mismatch": (
                strict_v1.NumericField(1.0e-12, "relative_residual")
            ),
            "full_step.lateral.matrix_face_roundoff_ratio": (
                strict_v1.NumericField(0.25, "relative_residual")
            ),
            "embedded_error.e_max": strict_v1.NumericField(
                1.0e-3, "relative_residual"
            ),
        },
        exact_votes=_baseline_exact_votes(),
        telemetry=_baseline_telemetry(),
    )


def _replace_numeric(
    observation: strict_v1.EquivalenceObservation,
    field: str,
    value: Any,
    *,
    denominator_key: str | None = None,
) -> strict_v1.EquivalenceObservation:
    numeric = dict(observation.numeric)
    prior = numeric[field]
    numeric[field] = strict_v1.NumericField(
        value,
        prior.denominator_key if denominator_key is None else denominator_key,
        scale_group=prior.scale_group,
    )
    return strict_v1.EquivalenceObservation(
        numeric=numeric,
        exact_votes=dict(observation.exact_votes),
        telemetry=dict(observation.telemetry),
    )


def _replace_exact(
    observation: strict_v1.EquivalenceObservation, field: str, value: Any
) -> strict_v1.EquivalenceObservation:
    exact = dict(observation.exact_votes)
    exact[field] = value
    return strict_v1.EquivalenceObservation(
        numeric=dict(observation.numeric),
        exact_votes=exact,
        telemetry=dict(observation.telemetry),
    )


def _is_custom_lateral(field: str) -> bool:
    return any(
        field.endswith(suffix)
        for suffix in _PHYSICAL_SUFFIXES
        | _CANCELLATION_SUFFIXES
        | _HARD_GATE_SUFFIXES
    )


def _maximum_absolute(value: Any) -> float:
    array = np.asarray(value, dtype=float)
    if array.size == 0 or not np.isfinite(array).all():
        return math.inf
    return float(np.max(np.abs(array)))


def _maximum_difference(left: Any, right: Any) -> float:
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if left_array.shape != right_array.shape or left_array.size == 0:
        return math.inf
    if not np.isfinite(left_array).all() or not np.isfinite(right_array).all():
        return math.inf
    return float(np.max(np.abs(left_array - right_array)))


def _coverage_accepts(
    candidate: strict_v1.EquivalenceObservation,
    oracle: strict_v1.EquivalenceObservation,
    coefficients: Mapping[str, Any],
    *,
    validation_errors: tuple[str, ...] = (),
) -> tuple[bool, tuple[str, ...]]:
    failures: list[str] = []
    if set(candidate.numeric) != set(oracle.numeric):
        failures.append("numeric_field_sets_differ")
    candidate_primary = {
        name: field
        for name, field in candidate.numeric.items()
        if not _is_custom_lateral(name)
    }
    oracle_primary = {
        name: field
        for name, field in oracle.numeric.items()
        if not _is_custom_lateral(name)
    }
    primary = strict_v1.compare_observations(
        strict_v1.EquivalenceObservation(
            numeric=candidate_primary,
            exact_votes=candidate.exact_votes,
            telemetry=candidate.telemetry,
        ),
        strict_v1.EquivalenceObservation(
            numeric=oracle_primary,
            exact_votes=oracle.exact_votes,
            telemetry=oracle.telemetry,
        ),
        strict_v1.load_equivalence_contract(),
        protocol_voltage_scale_V=15.8,
    )
    if not primary.passed:
        failures.append("A_or_B_or_structural_v1_gate_failed")

    paths = {
        name.split(".lateral.", 1)[0]
        for name in set(candidate.numeric) | set(oracle.numeric)
        if ".lateral." in name
    }
    for path in sorted(paths):
        temperature_name = f"{path}.state.temperature_K"
        if temperature_name not in candidate.numeric or temperature_name not in oracle.numeric:
            failures.append(f"{path}:missing_temperature_for_lateral_bound")
            continue
        candidate_temperature = candidate.numeric[temperature_name].value
        oracle_temperature = oracle.numeric[temperature_name].value
        delta_temperature = _maximum_difference(
            candidate_temperature, oracle_temperature
        )
        temperature_scale = max(
            1.0,
            _maximum_absolute(candidate_temperature),
            _maximum_absolute(oracle_temperature),
        )
        for suffix in sorted(_PHYSICAL_SUFFIXES):
            name = f"{path}.{suffix}"
            if name not in candidate.numeric or name not in oracle.numeric:
                failures.append(f"{name}:missing")
                continue
            candidate_value = candidate.numeric[name].value
            oracle_value = oracle.numeric[name].value
            difference = _maximum_difference(candidate_value, oracle_value)
            flux_scale = max(
                1.0e-30,
                _maximum_absolute(candidate_value),
                _maximum_absolute(oracle_value),
            )
            bound, _, _ = _physical_bound(
                suffix,
                delta_temperature_K=delta_temperature,
                temperature_scale_K=temperature_scale,
                flux_scale_W=flux_scale,
                coefficients=coefficients,
            )
            if not math.isfinite(difference) or difference > bound:
                failures.append(f"{name}:physical_bound_failed")

        x_name = f"{path}.lateral.x_face_flux_W"
        y_name = f"{path}.lateral.y_face_flux_W"
        x_scale = max(
            1.0e-30,
            _maximum_absolute(candidate.numeric[x_name].value),
            _maximum_absolute(oracle.numeric[x_name].value),
        )
        y_scale = max(
            1.0e-30,
            _maximum_absolute(candidate.numeric[y_name].value),
            _maximum_absolute(oracle.numeric[y_name].value),
        )
        cancellation_limit = _cancellation_bound(
            x_flux_scale_W=x_scale,
            y_flux_scale_W=y_scale,
            coefficients=coefficients,
        )
        for suffix in sorted(_CANCELLATION_SUFFIXES):
            name = f"{path}.{suffix}"
            if name not in candidate.numeric or name not in oracle.numeric:
                failures.append(f"{name}:missing")
                continue
            difference = _maximum_difference(
                candidate.numeric[name].value, oracle.numeric[name].value
            )
            if not math.isfinite(difference) or difference > cancellation_limit:
                failures.append(f"{name}:cancellation_bound_failed")

        def hard_gate(observation: strict_v1.EquivalenceObservation) -> bool:
            relative = float(
                observation.numeric[
                    f"{path}.lateral.matrix_face_relative_mismatch"
                ].value
            )
            roundoff = float(
                observation.numeric[
                    f"{path}.lateral.matrix_face_roundoff_ratio"
                ].value
            )
            return bool(relative <= 1.0e-10 or roundoff <= 1.0)

        candidate_gate = hard_gate(candidate)
        oracle_gate = hard_gate(oracle)
        if not candidate_gate or not oracle_gate or candidate_gate != oracle_gate:
            failures.append(f"{path}:lateral_hard_gate_disposition_failed")

    if validation_errors:
        failures.append("validation_errors_nonempty")
    return not failures, tuple(failures)


def run_synthetic_coverage_controls(
    config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    parent = json.loads(
        (
            ROOT
            / config["parent_metric_validity"]["immutable_files"]["summary"][
                "path"
            ]
        ).read_text(encoding="utf-8")
    )
    coefficients = parent["static_coefficients"]
    baseline = _baseline_observation()
    controls: list[dict[str, Any]] = []

    def record(
        control_id: str,
        candidate: strict_v1.EquivalenceObservation,
        oracle: strict_v1.EquivalenceObservation = baseline,
        *,
        expected_accept: bool = False,
        validation_errors: tuple[str, ...] = (),
    ) -> None:
        observed, reasons = _coverage_accepts(
            candidate,
            oracle,
            coefficients,
            validation_errors=validation_errors,
        )
        controls.append(
            {
                "control_id": control_id,
                "expected_accept": expected_accept,
                "observed_accept": observed,
                "passed": bool(expected_accept) == bool(observed),
                "failure_reasons": "|".join(reasons),
                "execution_type": "synthetic_comparator_only",
            }
        )

    record("baseline_valid_pair", baseline, expected_accept=True)
    record(
        "finite_temperature_field_perturbation",
        _replace_numeric(
            baseline,
            "full_step.state.temperature_K",
            np.array([336.0 + 1.0e-6, 336.5]),
        ),
    )
    record(
        "internal_x_face_flux_sign_flip",
        _replace_numeric(
            baseline,
            "full_step.lateral.x_face_flux_W",
            np.array([-2.0e-6, -1.0e-6]),
        ),
    )
    record(
        "terminal_current_tamper",
        _replace_numeric(
            baseline, "full_step.electrical.source_current_A", 2.1e-6
        ),
    )
    record(
        "Joule_power_tamper",
        _replace_numeric(
            baseline, "full_step.electrical.joule_power_W", 2.6e-5
        ),
    )
    record(
        "global_net_outflow_leak",
        _replace_numeric(
            baseline,
            "full_step.lateral.net_cell_outflow_W",
            np.array([3.5e-6, -1.5e-6]),
        ),
    )
    record(
        "ledger_tamper",
        _replace_numeric(
            baseline, "full_step.ledgers.thermal.accounted_power_W", 2.4e-5
        ),
    )
    record(
        "accepted_rejected_sequence_change",
        _replace_exact(
            baseline, "accepted_rejected_sequence", ("accepted", "accepted")
        ),
    )
    record(
        "event_count_change",
        _replace_exact(baseline, "event_count_direction_and_order", ("upward",)),
    )
    record(
        "event_direction_change",
        _replace_exact(
            baseline,
            "event_count_direction_and_order",
            ("downward", "downward"),
        ),
    )
    record(
        "event_chronology_change",
        _replace_exact(
            baseline,
            "event_count_direction_and_order",
            ("downward", "upward"),
        ),
    )
    record(
        "reversal_count_change",
        _replace_exact(
            baseline,
            "reversal_count_direction_and_order",
            ("heating_to_cooling",),
        ),
    )
    record(
        "reversal_direction_change",
        _replace_exact(
            baseline,
            "reversal_count_direction_and_order",
            ("heating_to_cooling", "heating_to_cooling"),
        ),
    )
    record(
        "reversal_order_change",
        _replace_exact(
            baseline,
            "reversal_count_direction_and_order",
            ("cooling_to_heating", "heating_to_cooling"),
        ),
    )
    methods = list(baseline.exact_votes["nonlinear_method"])
    methods[1] = ("first_half_step", "fail_closed_fixed_point_fallback")
    record(
        "nonlinear_method_change",
        _replace_exact(baseline, "nonlinear_method", tuple(methods)),
    )
    converged = list(baseline.exact_votes["converged_disposition"])
    converged[0] = ("full_step", False)
    record(
        "converged_disposition_change",
        _replace_exact(baseline, "converged_disposition", tuple(converged)),
    )
    fallbacks = list(baseline.exact_votes["fallback_disposition"])
    fallbacks[2] = ("second_half_step", True)
    record(
        "fallback_disposition_change",
        _replace_exact(baseline, "fallback_disposition", tuple(fallbacks)),
    )

    failure_oracle = _replace_exact(
        baseline,
        "failure_classification",
        "injected:full_step:nonfinite|observed:nonfinite:synthetic",
    )
    record(
        "expected_failure_type_change",
        _replace_exact(
            failure_oracle,
            "failure_classification",
            "injected:full_step:thermal_ledger|observed:thermal_ledger:synthetic",
        ),
        failure_oracle,
    )
    record(
        "expected_failure_location_change",
        _replace_exact(
            failure_oracle,
            "failure_classification",
            "injected:first_half_step:nonfinite|observed:nonfinite:synthetic",
        ),
        failure_oracle,
    )
    record(
        "failure_changed_to_success",
        _replace_exact(failure_oracle, "failure_classification", "none"),
        failure_oracle,
    )
    record(
        "success_changed_to_failure",
        _replace_exact(
            baseline,
            "failure_classification",
            "injected:full_step:nonfinite|observed:nonfinite:synthetic",
        ),
    )

    numeric = dict(baseline.numeric)
    numeric.pop("full_step.state.conductive_state")
    record(
        "required_numeric_field_missing",
        strict_v1.EquivalenceObservation(
            numeric=numeric,
            exact_votes=dict(baseline.exact_votes),
            telemetry=dict(baseline.telemetry),
        ),
    )
    numeric = dict(baseline.numeric)
    numeric["unregistered.extra_numeric"] = strict_v1.NumericField(
        0.0, "relative_residual"
    )
    record(
        "unregistered_numeric_field_extra",
        strict_v1.EquivalenceObservation(
            numeric=numeric,
            exact_votes=dict(baseline.exact_votes),
            telemetry=dict(baseline.telemetry),
        ),
    )
    exact = dict(baseline.exact_votes)
    exact.pop("event_count_direction_and_order")
    record(
        "required_topology_field_missing",
        strict_v1.EquivalenceObservation(
            numeric=dict(baseline.numeric),
            exact_votes=exact,
            telemetry=dict(baseline.telemetry),
        ),
    )
    exact = dict(baseline.exact_votes)
    exact["unregistered_topology"] = "unexpected"
    record(
        "unregistered_topology_field_extra",
        strict_v1.EquivalenceObservation(
            numeric=dict(baseline.numeric),
            exact_votes=exact,
            telemetry=dict(baseline.telemetry),
        ),
    )
    telemetry = dict(baseline.telemetry)
    telemetry.pop("Krylov_matvecs")
    record(
        "required_telemetry_field_missing",
        strict_v1.EquivalenceObservation(
            numeric=dict(baseline.numeric),
            exact_votes=dict(baseline.exact_votes),
            telemetry=telemetry,
        ),
    )
    telemetry = dict(baseline.telemetry)
    telemetry["unregistered_telemetry"] = (0,)
    record(
        "unregistered_telemetry_field_extra",
        strict_v1.EquivalenceObservation(
            numeric=dict(baseline.numeric),
            exact_votes=dict(baseline.exact_votes),
            telemetry=telemetry,
        ),
    )
    record(
        "validation_error_injected",
        baseline,
        validation_errors=("synthetic schema validation error",),
    )
    return controls


def build_coverage_result(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config = load_coverage_contract(config_path)
    hashes = verify_coverage_authority(config)
    field_contract = build_static_field_contract()
    plan_contract = build_plan_output_contract()
    controls = run_synthetic_coverage_controls(config)

    components = {row["component_contract"] for row in field_contract}
    mapped = all(
        set(str(row["component_contracts"]).split("|")).issubset(components)
        for row in plan_contract
    )
    counts = {
        family: sum(row["family"] == family for row in plan_contract)
        for family in ("electrical", "interval", "progression", "failure")
    }
    expected_counts = dict(config["static_plan_contract"]["families"])
    required_controls = set(config["required_new_synthetic_controls"])
    observed_controls = {row["control_id"] for row in controls}
    controls_complete = required_controls.issubset(observed_controls)
    controls_pass = controls_complete and all(row["passed"] for row in controls)
    fields_classified = bool(
        field_contract
        and all(row["category"] and row["comparator"] for row in field_contract)
    )
    exact_rows = [
        row for row in field_contract if row["category"] == "B_exact_topology"
    ]
    B_exact = bool(
        {row["field_pattern"] for row in exact_rows}
        == set(strict_v1.EXPECTED_EXACT_VOTES)
        and all(row["comparator"] == "canonical_exact_equality" for row in exact_rows)
    )
    pass_addendum = bool(
        len(plan_contract) == 57
        and counts == expected_counts
        and mapped
        and fields_classified
        and B_exact
        and controls_pass
    )
    summary = {
        "task_id": config["task_id"],
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "completed_solver_free_pre_merge_coverage_addendum",
        "validity": "valid",
        "lifecycle_state": "numerically_validated",
        "claim_status": "qualified_supported" if pass_addendum else "forbidden",
        "coverage_addendum_disposition": (
            "COVERAGE_ADDENDUM_PASS" if pass_addendum else "COVERAGE_ADDENDUM_FAIL"
        ),
        "final_metric_route": (
            "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
            if pass_addendum
            else "STOP_S2_ACTIVATE_GAMMA_SUB"
        ),
        "strict_equivalence_v1_disposition": (
            "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
        ),
        "strict_equivalence_v1_completed_rows": 12,
        "strict_equivalence_v1_expected_rows": 57,
        "parent_metric_validity_disposition": "GO_VERSIONED_EQUIVALENCE_V2_AUDIT",
        "parent_metric_validity_result_regenerated": False,
        "plan_rows_static_mapped": len(plan_contract),
        "plan_family_counts": counts,
        "field_template_count": len(field_contract),
        "component_contract_count": len(components),
        "all_plan_rows_map_to_static_contract": mapped,
        "all_field_templates_classified": fields_classified,
        "B_exact_field_count": len(exact_rows),
        "B_exact_contract_unchanged": B_exact,
        "required_new_control_count": len(required_controls),
        "synthetic_control_count_including_positive_baseline": len(controls),
        "synthetic_controls_complete": controls_complete,
        "synthetic_controls_pass": controls_pass,
        "authority_hashes": hashes,
        "existing_observed_physical_bounds_recomputed": False,
        "existing_observed_cancellation_bounds_recomputed": False,
        "existing_observed_negative_controls_regenerated": False,
        "candidate_or_oracle_execution_count": 0,
        "strict_equivalence_row_execution_count": 0,
        "remaining_45_row_execution_count": 0,
        "runtime_readiness_executed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "equivalence_v2_57_row_authorized": False,
        "optimized_solver_equivalence_status": "forbidden_unassessed",
        "S2_scientific_claim_status": "forbidden_unassessed",
    }
    return {
        "config": config,
        "field_contract": field_contract,
        "plan_contract": plan_contract,
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
        raise FileExistsError(f"refusing to overwrite coverage evidence: {path}")
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


def publish_coverage_result(result: Mapping[str, Any]) -> dict[str, str]:
    outputs = result["config"]["outputs"]
    field_path = ROOT / outputs["static_field_contract"]
    plan_path = ROOT / outputs["plan_output_contract"]
    controls_path = ROOT / outputs["synthetic_controls"]
    summary_path = ROOT / outputs["summary"]
    field_rows = result["field_contract"]
    plan_rows = result["plan_contract"]
    controls = result["controls"]
    _atomic_write(field_path, _csv_bytes(field_rows, list(field_rows[0])))
    _atomic_write(plan_path, _csv_bytes(plan_rows, list(plan_rows[0])))
    _atomic_write(controls_path, _csv_bytes(controls, list(controls[0])))
    summary = dict(result["summary"])
    summary["evidence_sha256"] = {
        field_path.name: _sha256(field_path),
        plan_path.name: _sha256(plan_path),
        controls_path.name: _sha256(controls_path),
    }
    _atomic_write(summary_path, _canonical_json_bytes(summary) + b"\n")
    return {
        "static_field_contract": str(field_path),
        "plan_output_contract": str(plan_path),
        "synthetic_controls": str(controls_path),
        "summary": str(summary_path),
    }


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "build_coverage_result",
    "build_plan_output_contract",
    "build_static_field_contract",
    "load_coverage_contract",
    "publish_coverage_result",
    "run_synthetic_coverage_controls",
    "verify_coverage_authority",
]
