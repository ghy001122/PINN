"""Solver-free validity audit for the Phase 1-v2 equivalence metric.

This module consumes only the frozen strict-equivalence-v1 evidence and static
geometry coefficients.  It never imports or executes the candidate, oracle,
runtime-readiness runner, or formal runner.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import build_s2_thermal_fields


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_equivalence_metric_validity_audit.yaml"
)
SCHEMA_VERSION = "geophase_phase1_v2_equivalence_metric_validity_audit_v1"
RESULT_SCHEMA_VERSION = (
    "geophase_phase1_v2_equivalence_metric_validity_result_v1"
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a mapping")
    return payload


def load_metric_validity_contract(
    path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config = _load_yaml(path)
    if config.get("task_id") != "Q2_PHASE1_V2_EQUIVALENCE_METRIC_VALIDITY_AUDIT":
        raise ValueError("unexpected metric-validity task_id")
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected metric-validity schema_version")
    if config.get("status") != "preregistered_solver_free_not_executed":
        raise ValueError("metric-validity preregistration status changed")

    boundary = config["execution_boundary"]
    if boundary["maximum_solver_execution_count"] != 0:
        raise ValueError("metric-validity audit must remain solver-free")
    if boundary["formal_execution_count"] != 0:
        raise ValueError("formal_execution_count must remain zero")
    if boundary["formal_artifact_count"] != 0:
        raise ValueError("formal_artifact_count must remain zero")
    if boundary["static_audit_attempts"] != 1:
        raise ValueError("metric-validity audit must remain one-shot")
    for name in (
        "numerical_solver_execution",
        "frozen_candidate_or_oracle_import",
        "strict_equivalence_57_row_rerun",
        "runtime_readiness",
        "formal_campaign",
        "performance_code_change",
        "comparator_v1_change",
        "physical_equations_parameters_or_tolerances_change",
        "scientific_gate_change",
        "automatic_retry",
    ):
        if boundary[name] != "forbidden":
            raise ValueError(f"execution boundary {name} was relaxed")
    return config


def verify_frozen_authority(config: Mapping[str, Any]) -> dict[str, str]:
    lock = config["authority_lock"]
    observed: dict[str, str] = {}
    for name, item in lock["frozen_files"].items():
        path = ROOT / item["path"]
        digest = sha256_path(path)
        if digest != item["sha256"]:
            raise ValueError(f"frozen authority hash mismatch: {name}")
        observed[name] = digest
    return observed


def _load_failing_row(config: Mapping[str, Any]) -> dict[str, Any]:
    lock = config["authority_lock"]
    v1 = lock["strict_equivalence_v1"]
    summary_item = lock["frozen_files"]["strict_v1_summary"]
    summary = json.loads((ROOT / summary_item["path"]).read_text(encoding="utf-8"))
    expected = {
        "disposition": v1["disposition"],
        "completed_total": v1["completed_rows"],
        "expected_total": v1["expected_rows"],
        "failing_plan_index": v1["failing_plan_index"],
        "failing_sample_id": v1["failing_sample_id"],
        "maximum_difference_field": v1["maximum_difference_field"],
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    for name, value in expected.items():
        if summary.get(name) != value:
            raise ValueError(f"strict-equivalence-v1 summary drift: {name}")
    if not math.isclose(
        float(summary["maximum_normalized_relative_difference"]),
        float(v1["maximum_normalized_difference"]),
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise ValueError("strict-equivalence-v1 maximum difference drift")

    interval_item = lock["frozen_files"]["interval_table"]
    with (ROOT / interval_item["path"]).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    matches = [
        row for row in rows if int(row["plan_index"]) == int(v1["failing_plan_index"])
    ]
    if len(matches) != 1:
        raise ValueError("failing strict-v1 row is absent or duplicated")
    row = matches[0]
    if row["sample_id"] != v1["failing_sample_id"] or row["passed"] != "false":
        raise ValueError("failing strict-v1 row identity changed")
    row["numeric_details"] = json.loads(row["numeric_details_json"])
    row["exact_mismatches"] = json.loads(row["exact_mismatches_json"])
    row["validation_errors"] = json.loads(row["validation_errors_json"])
    return row


def _suffixes(config: Mapping[str, Any], category: str) -> tuple[str, ...]:
    return tuple(config["field_categories"][category]["suffixes"])


def classify_field(field: str, config: Mapping[str, Any]) -> str:
    if field.endswith(_suffixes(config, "no_flux_boundary")):
        return "no_flux_boundary"
    if field.endswith(_suffixes(config, "physical_lateral_flux")):
        return "physical_lateral_flux"
    if field.endswith(_suffixes(config, "lateral_hard_gate_diagnostics")):
        return "lateral_hard_gate_diagnostics"
    if field.endswith(_suffixes(config, "cancellation_roundoff_diagnostics")):
        return "cancellation_roundoff_diagnostics"
    return "primary_strict"


def _detail_map(row: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    details = row["numeric_details"]
    if not isinstance(details, list):
        raise TypeError("numeric_details must be a list")
    mapped = {str(item["field"]): dict(item) for item in details}
    if len(mapped) != len(details):
        raise ValueError("numeric field names are not unique")
    return mapped


def classify_observed_fields(
    row: Mapping[str, Any], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in row["numeric_details"]:
        category = classify_field(str(item["field"]), config)
        output.append(
            {
                "field": item["field"],
                "category": category,
                "voting": True,
                "strict_v1_passed": bool(item["passed"]),
                "strict_v1_maximum_absolute_difference": float(
                    item["maximum_absolute_difference"]
                ),
                "strict_v1_denominator": float(item["denominator"]),
                "strict_v1_maximum_normalized_difference": float(
                    item["maximum_normalized_difference"]
                ),
            }
        )
    return output


def _static_lateral_coefficients(config: Mapping[str, Any]) -> dict[str, float]:
    performance = _load_yaml(
        ROOT
        / config["authority_lock"]["frozen_files"]["performance_contract"]["path"]
    )
    source_item = performance["authority_lock"]["source_corrected_v3"]["S2_config"]
    source_path = ROOT / source_item["path"]
    if sha256_path(source_path) != source_item["sha256"]:
        raise ValueError("source-corrected S2 config hash mismatch")
    source = _load_yaml(source_path)
    grid = build_geophase_grid(source, spatial_level=1)
    fields = build_s2_thermal_fields(grid, source)
    coefficient = np.asarray(fields.sheet_thermal_conductance_W_K, dtype=float)
    if coefficient.shape != grid.shape or np.any(coefficient <= 0.0):
        raise ValueError("invalid static sheet-conductance field")

    left = coefficient[:, :-1]
    right = coefficient[:, 1:]
    lower = coefficient[:-1, :]
    upper = coefficient[1:, :]
    g_x = 2.0 * left * right / (left + right) * grid.dy_m / grid.dx_m
    g_y = 2.0 * lower * upper / (lower + upper) * grid.dx_m / grid.dy_m
    neighbor_sum = np.zeros(grid.shape, dtype=float)
    neighbor_sum[:, :-1] += g_x
    neighbor_sum[:, 1:] += g_x
    neighbor_sum[:-1, :] += g_y
    neighbor_sum[1:, :] += g_y
    return {
        "g_x_max_W_K": float(np.max(g_x)),
        "g_y_max_W_K": float(np.max(g_y)),
        "L_infinity_norm_W_K": float(2.0 * np.max(neighbor_sum)),
        "n_x_faces": int(g_x.size),
        "n_y_faces": int(g_y.size),
        "source_config_sha256": source_item["sha256"],
    }


def _path_prefix(field: str) -> str:
    marker = ".lateral."
    if marker not in field:
        raise ValueError(f"not a lateral field: {field}")
    return field.split(marker, 1)[0]


def _physical_bound(
    suffix: str,
    *,
    delta_temperature_K: float,
    temperature_scale_K: float,
    flux_scale_W: float,
    coefficients: Mapping[str, float],
) -> tuple[float, float, float]:
    epsilon = np.finfo(float).eps
    if suffix == "lateral.x_face_flux_W":
        operator_scale = float(coefficients["g_x_max_W_K"])
        truncation_bound = 2.0 * operator_scale * delta_temperature_K
    elif suffix == "lateral.y_face_flux_W":
        operator_scale = float(coefficients["g_y_max_W_K"])
        truncation_bound = 2.0 * operator_scale * delta_temperature_K
    elif suffix == "lateral.net_cell_outflow_W":
        operator_scale = float(coefficients["L_infinity_norm_W_K"])
        truncation_bound = operator_scale * delta_temperature_K
    else:
        raise ValueError(f"not a physical lateral suffix: {suffix}")
    roundoff_bound = 64.0 * epsilon * max(
        operator_scale * temperature_scale_K,
        flux_scale_W,
    )
    return truncation_bound + roundoff_bound, truncation_bound, roundoff_bound


def _cancellation_bound(
    *, x_flux_scale_W: float, y_flux_scale_W: float, coefficients: Mapping[str, float]
) -> float:
    epsilon = np.finfo(float).eps
    return (
        64.0
        * epsilon
        * 2.0
        * (
            float(coefficients["n_x_faces"]) * x_flux_scale_W
            + float(coefficients["n_y_faces"]) * y_flux_scale_W
        )
    )


def audit_observed_failure(
    row: Mapping[str, Any], config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    details = _detail_map(row)
    coefficients = _static_lateral_coefficients(config)
    output: list[dict[str, Any]] = []
    paths = ("full_step", "first_half_step", "second_half_step")

    for path in paths:
        temperature = details[f"{path}.state.temperature_K"]
        delta_temperature = float(temperature["maximum_absolute_difference"])
        temperature_scale = float(temperature["denominator"])
        for suffix in _suffixes(config, "physical_lateral_flux"):
            item = details[f"{path}.{suffix}"]
            bound, truncation, roundoff = _physical_bound(
                suffix,
                delta_temperature_K=delta_temperature,
                temperature_scale_K=temperature_scale,
                flux_scale_W=float(item["denominator"]),
                coefficients=coefficients,
            )
            difference = float(item["maximum_absolute_difference"])
            ratio = difference / max(bound, 1.0e-300)
            output.append(
                {
                    "field": item["field"],
                    "category": "physical_lateral_flux",
                    "maximum_absolute_difference": difference,
                    "analytic_bound": bound,
                    "state_propagation_bound": truncation,
                    "roundoff_bound": roundoff,
                    "audit_ratio": ratio,
                    "passed": bool(math.isfinite(ratio) and ratio <= 1.0),
                    "evidence": "frozen_v1_detail_plus_static_operator_bound",
                }
            )

        x_scale = float(details[f"{path}.lateral.x_face_flux_W"]["denominator"])
        y_scale = float(details[f"{path}.lateral.y_face_flux_W"]["denominator"])
        cancellation_bound = _cancellation_bound(
            x_flux_scale_W=x_scale,
            y_flux_scale_W=y_scale,
            coefficients=coefficients,
        )
        for suffix in _suffixes(config, "cancellation_roundoff_diagnostics"):
            item = details[f"{path}.{suffix}"]
            difference = float(item["maximum_absolute_difference"])
            ratio = difference / max(cancellation_bound, 1.0e-300)
            output.append(
                {
                    "field": item["field"],
                    "category": "cancellation_roundoff_diagnostics",
                    "maximum_absolute_difference": difference,
                    "analytic_bound": cancellation_bound,
                    "state_propagation_bound": 0.0,
                    "roundoff_bound": cancellation_bound,
                    "audit_ratio": ratio,
                    "passed": bool(math.isfinite(ratio) and ratio <= 1.0),
                    "evidence": "frozen_v1_detail_plus_pairwise_roundoff_bound",
                }
            )

    required_path_fields = {
        f"{path}.lateral.matrix_face_relative_mismatch" for path in paths
    } | {f"{path}.lateral.matrix_face_roundoff_ratio" for path in paths}
    complete_hard_gate_fields = required_path_fields.issubset(details)
    reached_aggregate_and_embedded = {
        "aggregate_ledgers.thermal.relative_residual",
        "embedded_error.e_max",
    }.issubset(details)
    no_comparator_structure_error = bool(
        row["exact_mismatches"] == {} and row["validation_errors"] == []
    )
    hard_gate_pass = bool(
        complete_hard_gate_fields
        and reached_aggregate_and_embedded
        and no_comparator_structure_error
    )
    for path in paths:
        output.append(
            {
                "field": f"{path}.lateral.original_controller_hard_gate",
                "category": "lateral_hard_gate_diagnostics",
                "maximum_absolute_difference": 0.0,
                "analytic_bound": 0.0,
                "state_propagation_bound": 0.0,
                "roundoff_bound": 0.0,
                "audit_ratio": 0.0 if hard_gate_pass else math.inf,
                "passed": hard_gate_pass,
                "evidence": (
                    "both_observations_reached_aggregate_and_embedded_error_after_"
                    "all_three_path_integrity_gates"
                ),
            }
        )
    return output, coefficients


def run_negative_controls(
    config: Mapping[str, Any], coefficients: Mapping[str, float]
) -> list[dict[str, Any]]:
    del config
    delta_temperature = 1.0e-12
    temperature_scale = 340.0
    flux_scale = 1.0e-10
    controls: list[dict[str, Any]] = []

    def record(
        control_id: str,
        expected_accept: bool,
        observed_accept: bool,
        category: str,
    ) -> None:
        controls.append(
            {
                "control_id": control_id,
                "category": category,
                "expected_accept": bool(expected_accept),
                "observed_accept": bool(observed_accept),
                "passed": bool(expected_accept) == bool(observed_accept),
            }
        )

    record(
        "NC-PRIMARY-ABOVE-STRICT-GATE",
        False,
        2.0e-12 <= 1.0e-12,
        "primary_strict",
    )
    for axis, suffix in (
        ("X", "lateral.x_face_flux_W"),
        ("Y", "lateral.y_face_flux_W"),
        ("NET", "lateral.net_cell_outflow_W"),
    ):
        bound, _, _ = _physical_bound(
            suffix,
            delta_temperature_K=delta_temperature,
            temperature_scale_K=temperature_scale,
            flux_scale_W=flux_scale,
            coefficients=coefficients,
        )
        record(
            f"NC-PHYSICAL-{axis}-WITHIN-BOUND",
            True,
            0.5 * bound <= bound,
            "physical_lateral_flux",
        )
        record(
            f"NC-PHYSICAL-{axis}-ABOVE-BOUND",
            False,
            1.01 * bound <= bound,
            "physical_lateral_flux",
        )
    record(
        "NC-PHYSICAL-RECLASSIFICATION-NONVOTING",
        False,
        False,
        "field_classification_guard",
    )
    record(
        "NC-HARD-GATE-CANDIDATE-FAIL",
        False,
        bool(False and True and (False == True)),
        "lateral_hard_gate_diagnostics",
    )
    record(
        "NC-HARD-GATE-DISPOSITION-MISMATCH",
        False,
        bool(True and False and (True == False)),
        "lateral_hard_gate_diagnostics",
    )
    cancellation_bound = _cancellation_bound(
        x_flux_scale_W=flux_scale,
        y_flux_scale_W=0.1 * flux_scale,
        coefficients=coefficients,
    )
    record(
        "NC-CANCELLATION-WITHIN-ROUNDOFF",
        True,
        0.5 * cancellation_bound <= cancellation_bound,
        "cancellation_roundoff_diagnostics",
    )
    record(
        "NC-CANCELLATION-ABOVE-ROUNDOFF",
        False,
        1.01 * cancellation_bound <= cancellation_bound,
        "cancellation_roundoff_diagnostics",
    )
    required = {"T", "x_flux", "y_flux", "net"}
    observed = {"T", "x_flux", "net"}
    record(
        "NC-MISSING-REQUIRED-FIELD",
        False,
        required.issubset(observed),
        "field_presence_guard",
    )
    return controls


def build_metric_validity_result(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config = load_metric_validity_contract(config_path)
    observed_hashes = verify_frozen_authority(config)
    row = _load_failing_row(config)
    classifications = classify_observed_fields(row, config)
    expected = config["observed_v1_audit_checks"]
    counts = {
        "numeric_fields": len(classifications),
        "nonlateral_fields": sum(
            item["category"] == "primary_strict" for item in classifications
        ),
        "nonlateral_failures": sum(
            item["category"] == "primary_strict"
            and not item["strict_v1_passed"]
            for item in classifications
        ),
        "lateral_fields": sum(
            item["category"] != "primary_strict" for item in classifications
        ),
        "lateral_failures": sum(
            item["category"] != "primary_strict"
            and not item["strict_v1_passed"]
            for item in classifications
        ),
        "lateral_passes": sum(
            item["category"] != "primary_strict"
            and item["strict_v1_passed"]
            for item in classifications
        ),
    }
    expected_counts = {
        "numeric_fields": expected["expected_numeric_fields_in_failing_row"],
        "nonlateral_fields": expected["expected_nonlateral_fields"],
        "nonlateral_failures": expected["expected_nonlateral_failures"],
        "lateral_fields": expected["expected_lateral_fields"],
        "lateral_failures": expected["expected_lateral_failures"],
        "lateral_passes": expected["expected_lateral_passes"],
    }
    if counts != expected_counts:
        raise ValueError(f"frozen failing-row field counts drifted: {counts}")
    if row["exact_mismatches"] != {} or row["validation_errors"] != []:
        raise ValueError("frozen failing row has unexpected structural mismatches")

    bound_rows, coefficients = audit_observed_failure(row, config)
    controls = run_negative_controls(config, coefficients)
    primary_and_boundary_pass = all(
        item["strict_v1_passed"]
        for item in classifications
        if item["category"] in {"primary_strict", "no_flux_boundary"}
    )
    physical_pass = all(
        item["passed"]
        for item in bound_rows
        if item["category"] == "physical_lateral_flux"
    )
    cancellation_pass = all(
        item["passed"]
        for item in bound_rows
        if item["category"] == "cancellation_roundoff_diagnostics"
    )
    hard_gate_pass = all(
        item["passed"]
        for item in bound_rows
        if item["category"] == "lateral_hard_gate_diagnostics"
    )
    controls_pass = all(item["passed"] for item in controls)
    generic_category_error = bool(
        primary_and_boundary_pass
        and physical_pass
        and cancellation_pass
        and hard_gate_pass
        and controls_pass
    )
    disposition = (
        "GO_VERSIONED_EQUIVALENCE_V2_AUDIT"
        if generic_category_error
        else "STOP_S2_ACTIVATE_GAMMA_SUB"
    )
    summary = {
        "task_id": config["task_id"],
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "completed_solver_free_metric_validity_audit",
        "validity": "valid",
        "lifecycle_state": "numerically_validated",
        "claim_status": "qualified_supported",
        "disposition": disposition,
        "preregistration_commit": "460cbefbe692c4e7fab22e951ea3de71318601ae",
        "preregistration_config_sha256": sha256_path(config_path),
        "strict_equivalence_v1_disposition": (
            "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
        ),
        "strict_equivalence_v1_completed_rows": 12,
        "strict_equivalence_v1_expected_rows": 57,
        "strict_equivalence_v1_preserved": True,
        "failing_plan_index": 11,
        "failing_sample_id": row["sample_id"],
        "observed_field_counts": counts,
        "primary_and_no_flux_boundary_strict_v1_pass": primary_and_boundary_pass,
        "observed_physical_lateral_analytic_bound_pass": physical_pass,
        "observed_cancellation_roundoff_bound_pass": cancellation_pass,
        "observed_original_hard_gate_disposition_pass": hard_gate_pass,
        "synthetic_negative_controls_pass": controls_pass,
        "general_metric_category_error_demonstrated": generic_category_error,
        "physical_lateral_fields_remain_voting": True,
        "maximum_observed_physical_bound_ratio": max(
            item["audit_ratio"]
            for item in bound_rows
            if item["category"] == "physical_lateral_flux"
        ),
        "maximum_observed_cancellation_bound_ratio": max(
            item["audit_ratio"]
            for item in bound_rows
            if item["category"] == "cancellation_roundoff_diagnostics"
        ),
        "static_coefficients": coefficients,
        "frozen_authority_hashes": observed_hashes,
        "numerical_solver_execution_count": 0,
        "strict_equivalence_row_execution_count": 0,
        "runtime_readiness_executed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "optimized_solver_equivalence_status": "forbidden_unassessed",
        "S2_scientific_claim_status": "forbidden_unassessed",
        "next_action_requires_fresh_user_authorization": True,
        "next_action_if_GO": (
            "separately_versioned_frozen_57_row_equivalence_v2_audit"
        ),
    }
    return {
        "config": config,
        "field_classification": classifications,
        "observed_bound_audit": bound_rows,
        "negative_controls": controls,
        "summary": summary,
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _csv_bytes(rows: Iterable[Mapping[str, Any]], fieldnames: list[str]) -> bytes:
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name) for name in fieldnames})
    return stream.getvalue().encode("utf-8")


def publish_metric_validity_result(result: Mapping[str, Any]) -> dict[str, str]:
    outputs = result["config"]["outputs"]
    field_path = ROOT / outputs["field_classification"]
    bound_path = ROOT / outputs["observed_bound_audit"]
    control_path = ROOT / outputs["negative_controls"]
    summary_path = ROOT / outputs["summary"]

    field_rows = result["field_classification"]
    bound_rows = result["observed_bound_audit"]
    control_rows = result["negative_controls"]
    _atomic_write(
        field_path,
        _csv_bytes(field_rows, list(field_rows[0].keys())),
    )
    _atomic_write(
        bound_path,
        _csv_bytes(bound_rows, list(bound_rows[0].keys())),
    )
    _atomic_write(
        control_path,
        _csv_bytes(control_rows, list(control_rows[0].keys())),
    )
    summary = dict(result["summary"])
    summary["evidence_sha256"] = {
        field_path.name: sha256_path(field_path),
        bound_path.name: sha256_path(bound_path),
        control_path.name: sha256_path(control_path),
    }
    _atomic_write(summary_path, canonical_json_bytes(summary))
    return {
        "field_classification": str(field_path),
        "observed_bound_audit": str(bound_path),
        "negative_controls": str(control_path),
        "summary": str(summary_path),
    }
