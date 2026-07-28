"""Closed-schema resolver for the preregistered Phase 1-v2 controller overlay.

This module performs no numerical solve.  It exists so the overlay contract is
machine-enforced before the controller-v2 implementation or any new numerical
execution is allowed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


RESOLUTION_SCHEMA_VERSION = "geophase_phase1_v2_controller_overlay_resolution_v1"
DOCUMENT_KEYS = {
    "task_id",
    "schema_version",
    "status",
    "evidence_type",
    "manuscript_use",
    "authority_lock",
    "execution_boundary",
    "deterministic_resolution",
    "overlay_schema",
    "controller_overlay",
    "readiness_validation",
    "outcomes",
    "claim_boundary",
    "outputs",
}
REFERENCE_SOLVER_KEYS = {"time_discretization", "active_time_controller"}
ACTIVE_CONTROLLER_KEYS = {
    "controller_id",
    "candidate_paths",
    "embedded_error",
    "voltage_scale",
    "outer_interval",
    "growth",
    "integrity",
    "aggregate_ledgers",
    "event_output_isolation",
    "telemetry",
}
CONTROLLER_SECTION_KEYS = {
    "candidate_paths": {"full_step", "two_half_steps"},
    "embedded_error": {
        "temperature_scale_K",
        "e_T",
        "e_s",
        "e_b",
        "e_V",
        "e_max",
        "acceptance_max",
        "legacy_max_delta_s_delta_b_role",
    },
    "voltage_scale": {
        "formula",
        "runtime_or_device_voltage_dependent_denominator",
        "missing_protocol_mapping",
        "protocol_V_scale_V",
        "multi_device_or_multi_input_rule",
        "DUAL0_fixture_device_channel_V_scale_V",
    },
    "outer_interval": {
        "symbol",
        "base_maximum_s",
        "emergency_floor_base_s",
        "formal_time_divisors",
        "divisor_rule",
        "emergency_floor_applies_to",
        "half_steps_below_outer_floor",
        "initial_H",
        "rejection_action_above_floor",
        "outer_rejection_cap",
        "rejection_count_unit",
        "floor_ladder",
        "floor_candidate_failure",
        "proposal_below_floor",
        "endpoint_or_forced_landing_remainder",
    },
    "growth": {
        "accepted_interval_policy",
        "easy_error_max",
        "required_consecutive_easy_intervals",
        "each_easy_interval_requires",
        "action",
        "PID_or_safety_factor",
    },
    "integrity": {
        "required_for_each_path",
        "hard_gates",
        "path_failure_above_floor",
        "path_failure_at_floor_or_remainder",
        "lateral_audit_formula",
        "third_lateral_acceptance_criterion",
    },
    "aggregate_ledgers": {
        "hard_gate_for_accepted_two_half_path",
        "ledgers",
        "recompute_from_signed_energy_terms",
        "relative_residual_averaging",
        "storage",
        "midpoint_storage",
        "accumulated_terms",
        "device_power_identity",
        "thresholds",
    },
    "event_output_isolation": {
        "protocol_discontinuity_and_fixed_output_times",
        "each_half_uses_its_own_time_interval_voltage",
        "events_streaming_QoI_and_snapshots_source",
        "full_step_pollution",
    },
    "telemetry": {
        "legacy_max_absolute_delta_s",
        "legacy_max_absolute_delta_b",
        "embedded_components",
        "path_integrity",
        "coupled_solve_count_per_successful_outer_candidate",
    },
}
EXACT_OPERATIONS = (
    ("REPLACE", "/reference_solver/time_discretization"),
    ("ADD", "/reference_solver/active_time_controller"),
)
AUTHORITY_KEYS = {
    "merged_pr7_main_commit",
    "merged_pr7_main_tree",
    "base_S2_config",
    "source_contract",
    "execution_addendum",
    "formal_manifest",
    "execution_DAG",
    "historical_controller_v1",
}
EXECUTION_BOUNDARY_KEYS = {
    "preregistration_commit_must_be_pushed_before_controller_implementation",
    "preregistration_commit_must_be_pushed_before_new_numerical_execution",
    "formal_execution_count",
    "formal_artifact_count",
    "formal_campaign",
    "controller_v1_replay",
    "controller_parameter_scan",
    "S2_equation_parameter_or_tolerance_change",
    "phase2_PINN_MoE_homotopy_inverse_S1_material_stack_FEM3D_NbO2",
    "performance_repair_consumed",
    "implementation_diff_contract",
}
RESOLUTION_KEYS = {
    "schema_version",
    "algorithm",
    "whitelisted_base_paths",
    "exact_operations",
    "DELETE_operation",
    "additional_overlay_paths",
    "top_level_overlay_key",
    "resolved_runtime_identity_fields",
    "resolved_runtime_identity_formula",
    "canonical_JSON",
    "current_overlay_must_match_preregistration_commit_bytes",
    "base_config_must_match_preregistration_commit_bytes",
    "forbidden_override_namespaces",
}
READINESS_KEYS = {
    "formal",
    "id_prefix",
    "temporary_directory_only",
    "formal_execution_count",
    "formal_artifact_count",
    "sequential_gates",
    "C1",
    "C2",
    "C3",
}
OUTPUT_KEYS = {
    "namespace",
    "machine_preregistration",
    "C1_summary",
    "C2_summary",
    "preflight_samples",
    "preflight_summary",
    "campaign_cost_forecast",
    "dormant_runner_dry_run",
    "readiness_summary",
    "report",
    "publish_order",
    "overwrite_historical_runtime_readiness_or_PR7_evidence",
}


@dataclass(frozen=True)
class ResolvedControllerV2:
    base_config: dict[str, Any]
    overlay_document: dict[str, Any]
    resolved_config: dict[str, Any]
    base_sha256: str
    overlay_sha256: str
    identity_payload: dict[str, str]
    identity_sha256: str


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a mapping")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValueError(f"{label} schema mismatch; missing={missing}, extra={extra}")


def _protocol_scale(protocol: dict[str, Any]) -> float:
    voltage_keys = ("input_voltage_V", "baseline_voltage_V", "pulse_voltage_V")
    declared = [abs(float(protocol[key])) for key in voltage_keys if key in protocol]
    if not declared:
        raise ValueError("protocol has no declared voltage for V_scale resolution")
    return max(1.0, max(declared))


def _validate_path_hash_record(record: Any, label: str) -> dict[str, Any]:
    value = _mapping(record, label)
    _exact_keys(value, {"path", "sha256"}, label)
    if not isinstance(value["path"], str) or not value["path"]:
        raise ValueError(f"{label} path must be nonempty")
    digest = str(value["sha256"])
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError(f"{label} SHA-256 is invalid")
    return value


def validate_controller_overlay_document(
    overlay: dict[str, Any], base_config: dict[str, Any]
) -> None:
    _exact_keys(overlay, DOCUMENT_KEYS, "controller-v2 document")
    if overlay["task_id"] != "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION":
        raise ValueError("unexpected controller-v2 task id")

    authority = _mapping(overlay["authority_lock"], "authority lock")
    _exact_keys(authority, AUTHORITY_KEYS, "authority lock")
    if authority["merged_pr7_main_commit"] != (
        "8a8541f19ab5b5baeda5102a70e593f996c59224"
    ):
        raise ValueError("PR #7 merge commit lock changed")
    if authority["merged_pr7_main_tree"] != (
        "5ab294e8048ec04da1d4ad2cbc8cb8f4b0eb6c5d"
    ):
        raise ValueError("PR #7 merge tree lock changed")
    base_lock = _mapping(authority["base_S2_config"], "base S2 lock")
    _exact_keys(base_lock, {"path", "sha256", "base_file_bytes_mutable"}, "base S2 lock")
    if base_lock["base_file_bytes_mutable"] is not False:
        raise ValueError("base S2 YAML must remain immutable")
    _validate_path_hash_record(
        {"path": base_lock["path"], "sha256": base_lock["sha256"]},
        "base S2 path/hash",
    )
    _validate_path_hash_record(authority["source_contract"], "source contract")
    addendum = _mapping(authority["execution_addendum"], "execution addendum")
    _exact_keys(
        addendum,
        {
            "path",
            "sha256",
            "historical_immutable_adaptive_controller_clause",
            "all_non_controller_execution_semantics_remain_locked",
        },
        "execution addendum",
    )
    _validate_path_hash_record(
        {"path": addendum["path"], "sha256": addendum["sha256"]},
        "execution addendum path/hash",
    )
    if addendum["all_non_controller_execution_semantics_remain_locked"] is not True:
        raise ValueError("non-controller addendum semantics were unlocked")
    manifest = _mapping(authority["formal_manifest"], "formal manifest")
    _exact_keys(
        manifest,
        {
            "path",
            "sha256",
            "evaluation_item_count",
            "unique_execution_unit_count",
            "legal_reuse_count",
            "expanded_CSV",
            "expanded_JSON",
        },
        "formal manifest",
    )
    _validate_path_hash_record(
        {"path": manifest["path"], "sha256": manifest["sha256"]},
        "formal manifest path/hash",
    )
    _validate_path_hash_record(manifest["expanded_CSV"], "expanded manifest CSV")
    _validate_path_hash_record(manifest["expanded_JSON"], "expanded manifest JSON")
    if (
        int(manifest["evaluation_item_count"]),
        int(manifest["unique_execution_unit_count"]),
        int(manifest["legal_reuse_count"]),
    ) != (63, 60, 3):
        raise ValueError("formal 63/60/3 identity changed")
    dag = _mapping(authority["execution_DAG"], "execution DAG")
    _exact_keys(dag, {"path", "sha256", "CSV_path", "CSV_sha256"}, "execution DAG")
    _validate_path_hash_record(
        {"path": dag["path"], "sha256": dag["sha256"]}, "execution DAG JSON"
    )
    _validate_path_hash_record(
        {"path": dag["CSV_path"], "sha256": dag["CSV_sha256"]},
        "execution DAG CSV",
    )
    historical = _mapping(authority["historical_controller_v1"], "historical controller v1")
    _exact_keys(
        historical,
        {
            "active_runtime_selection",
            "reproducibility_source",
            "solver_blob_at_merged_PR7_main",
            "rejection_cap",
            "PR7_head",
            "audit_config",
            "failure_telemetry",
            "attempted_step_CSV",
            "diagnosis",
            "report",
            "evidence_mutation",
        },
        "historical controller v1",
    )
    for key in (
        "audit_config",
        "failure_telemetry",
        "attempted_step_CSV",
        "diagnosis",
        "report",
    ):
        _validate_path_hash_record(historical[key], f"historical v1 {key}")
    if historical["active_runtime_selection"] != "forbidden":
        raise ValueError("historical controller v1 became selectable")
    if int(historical["rejection_cap"]) != 6 or historical["evidence_mutation"] != "forbidden":
        raise ValueError("historical controller v1 semantics changed")

    boundary = _mapping(overlay["execution_boundary"], "execution boundary")
    _exact_keys(boundary, EXECUTION_BOUNDARY_KEYS, "execution boundary")
    if boundary["preregistration_commit_must_be_pushed_before_controller_implementation"] is not True:
        raise ValueError("controller implementation must remain push-gated")
    if boundary["preregistration_commit_must_be_pushed_before_new_numerical_execution"] is not True:
        raise ValueError("controller numerical work must remain push-gated")
    if int(boundary["formal_execution_count"]) != 0:
        raise ValueError("controller overlay cannot consume formal execution")
    if int(boundary["formal_artifact_count"]) != 0:
        raise ValueError("controller overlay cannot create formal artifacts")
    forbidden_boundary_values = (
        "formal_campaign",
        "controller_v1_replay",
        "controller_parameter_scan",
        "S2_equation_parameter_or_tolerance_change",
        "phase2_PINN_MoE_homotopy_inverse_S1_material_stack_FEM3D_NbO2",
    )
    if any(boundary[key] != "forbidden" for key in forbidden_boundary_values):
        raise ValueError("execution boundary was weakened")
    if boundary["performance_repair_consumed"] is not False:
        raise ValueError("performance repair state changed")
    diff_contract = _mapping(
        boundary["implementation_diff_contract"], "implementation diff contract"
    )
    _exact_keys(diff_contract, {"allowed_paths", "forbidden_paths"}, "implementation diff contract")
    allowed_paths = set(diff_contract["allowed_paths"])
    forbidden_paths = set(diff_contract["forbidden_paths"])
    if allowed_paths & forbidden_paths:
        raise ValueError("implementation paths cannot be both allowed and forbidden")
    required_immutable = {
        "configs/geophase_phase1_v2_embedded_time_controller_v2.yaml",
        "configs/geophase_phase1_v2_s2_reference.yaml",
        "configs/geophase_phase1_v2_execution_addendum.yaml",
        "configs/geophase_phase1_v2_formal_manifest.yaml",
        "configs/qiu_vo2_phase1_source_contract.yaml",
        "docs/method_equations.md",
        "src/pinnpcm/solvers/geophase_phase1_v2_controller_overlay.py",
        "src/pinnpcm/solvers/geophase_phase1_v2_implicit.py",
        "src/pinnpcm/solvers/geophase_phase1_v2_fvm.py",
    }
    if not required_immutable <= forbidden_paths:
        raise ValueError("post-anchor immutable path set was weakened")

    resolution = _mapping(overlay["deterministic_resolution"], "resolution")
    _exact_keys(resolution, RESOLUTION_KEYS, "resolution")
    if resolution["schema_version"] != RESOLUTION_SCHEMA_VERSION:
        raise ValueError("unsupported controller overlay resolution schema")
    operations = tuple(
        (str(item["operation"]), str(item["path"]))
        for item in resolution["exact_operations"]
    )
    if operations != EXACT_OPERATIONS or resolution["DELETE_operation"] != "forbidden":
        raise ValueError("controller overlay operations are not the exact closed set")
    if resolution["whitelisted_base_paths"] != [
        "reference_solver.time_discretization",
        "reference_solver.active_time_controller",
    ]:
        raise ValueError("controller overlay whitelist changed")
    if resolution["additional_overlay_paths"] != "forbidden":
        raise ValueError("additional overlay paths must fail closed")
    if resolution["top_level_overlay_key"] != "controller_overlay":
        raise ValueError("controller overlay root changed")
    if resolution["resolved_runtime_identity_fields"] != [
        "base_S2_config_sha256",
        "controller_v2_overlay_sha256",
        "resolution_schema_version",
    ]:
        raise ValueError("resolved runtime identity fields changed")

    schema = _mapping(overlay["overlay_schema"], "overlay schema")
    _exact_keys(
        schema,
        {
            "additional_properties",
            "controller_overlay_required_keys",
            "reference_solver_allowed_keys",
            "active_time_controller_allowed_keys",
        },
        "overlay schema",
    )
    if schema["additional_properties"] != "forbidden":
        raise ValueError("overlay additional properties must fail closed")
    if set(schema["reference_solver_allowed_keys"]) != REFERENCE_SOLVER_KEYS:
        raise ValueError("reference-solver overlay schema changed")
    if set(schema["active_time_controller_allowed_keys"]) != ACTIVE_CONTROLLER_KEYS:
        raise ValueError("active-controller overlay schema changed")

    payload = _mapping(overlay["controller_overlay"], "controller overlay")
    _exact_keys(payload, {"reference_solver"}, "controller overlay")
    reference = _mapping(payload["reference_solver"], "reference-solver overlay")
    _exact_keys(reference, REFERENCE_SOLVER_KEYS, "reference-solver overlay")
    controller = _mapping(reference["active_time_controller"], "active controller")
    _exact_keys(controller, ACTIVE_CONTROLLER_KEYS, "active controller")
    for section_name, expected_keys in CONTROLLER_SECTION_KEYS.items():
        _exact_keys(
            _mapping(controller[section_name], f"controller {section_name}"),
            expected_keys,
            f"controller {section_name}",
        )
    candidate_paths = _mapping(controller["candidate_paths"], "candidate paths")
    _exact_keys(
        _mapping(candidate_paths["full_step"], "full-step path"),
        {
            "backward_euler_steps",
            "step_fraction_of_outer_interval",
            "role",
            "may_commit_state_or_QoI",
        },
        "full-step path",
    )
    _exact_keys(
        _mapping(candidate_paths["two_half_steps"], "two-half-step path"),
        {
            "backward_euler_steps",
            "ordered_step_fractions_of_outer_interval",
            "role",
            "second_half_starts_from_first_half_state",
        },
        "two-half-step path",
    )
    outer = _mapping(controller["outer_interval"], "outer interval")
    _exact_keys(
        _mapping(outer["divisor_rule"], "outer divisor rule"),
        {"maximum", "emergency_floor"},
        "outer divisor rule",
    )
    _exact_keys(
        _mapping(
            outer["endpoint_or_forced_landing_remainder"],
            "forced-landing remainder",
        ),
        {
            "allowed_targets",
            "adaptive_floor_search",
            "failed_integrity_or_embedded_gate",
        },
        "forced-landing remainder",
    )
    voltage_scale = _mapping(controller["voltage_scale"], "voltage scale")
    dual_scales = _mapping(
        voltage_scale["DUAL0_fixture_device_channel_V_scale_V"],
        "DUAL0 voltage scales",
    )
    _exact_keys(
        dual_scales,
        {
            "A_only_drive",
            "B_only_drive",
            "equal_drive_symmetry",
            "swapped_label_invariance",
        },
        "DUAL0 voltage scales",
    )
    for name, per_device in dual_scales.items():
        _exact_keys(
            _mapping(per_device, f"DUAL0 {name}"),
            {"A", "B"},
            f"DUAL0 {name}",
        )
    if controller["controller_id"] != "embedded_time_consistency_v2_only":
        raise ValueError("controller-v1 or unknown controller cannot be active")
    embedded = _mapping(controller["embedded_error"], "embedded error")
    if float(embedded["temperature_scale_K"]) != 7.19:
        raise ValueError("embedded temperature scale changed")
    if float(embedded["acceptance_max"]) != 0.02:
        raise ValueError("embedded acceptance gate changed")
    if embedded["legacy_max_delta_s_delta_b_role"] != "telemetry_only_nonvoting":
        raise ValueError("legacy state increment regained voting power")
    outer = _mapping(controller["outer_interval"], "outer interval")
    if float(outer["base_maximum_s"]) != 1.0e-8:
        raise ValueError("outer interval maximum changed")
    if float(outer["emergency_floor_base_s"]) != 9.765625e-12:
        raise ValueError("outer interval floor changed")
    if outer["formal_time_divisors"] != [1, 2, 4]:
        raise ValueError("time divisor schedule changed")
    if int(outer["outer_rejection_cap"]) != 10:
        raise ValueError("outer rejection cap changed")
    growth = _mapping(controller["growth"], "growth")
    if float(growth["easy_error_max"]) != 0.005:
        raise ValueError("easy-error growth gate changed")
    if int(growth["required_consecutive_easy_intervals"]) != 2:
        raise ValueError("growth streak changed")

    base_time_grid = _mapping(
        _mapping(base_config["reference_solver"], "base reference solver")["time_grid"],
        "base time grid",
    )
    if int(base_time_grid["maximum_rejected_steps_per_accepted_step"]) != 6:
        raise ValueError("historical controller-v1 rejection cap changed")
    if float(base_time_grid["transition_increment_threshold"]) != 0.02:
        raise ValueError("historical controller-v1 transition threshold changed")

    protocols = _mapping(
        _mapping(base_config["formal_protocols"], "formal protocols")["protocols"],
        "protocol map",
    )
    mapped = _mapping(
        _mapping(controller["voltage_scale"], "voltage-scale contract")[
            "protocol_V_scale_V"
        ],
        "protocol V_scale map",
    )
    if set(mapped) != set(protocols):
        raise ValueError("every and only declared protocol must have a V_scale")
    for name, protocol in protocols.items():
        expected = _protocol_scale(_mapping(protocol, f"protocol {name}"))
        if float(mapped[name]) != expected:
            raise ValueError(f"V_scale mismatch for protocol {name}")

    readiness = _mapping(overlay["readiness_validation"], "readiness validation")
    _exact_keys(readiness, READINESS_KEYS, "readiness validation")
    if readiness["formal"] is not False or readiness["temporary_directory_only"] is not True:
        raise ValueError("readiness must remain temporary and non-formal")
    if readiness["id_prefix"] != "PRE-CTRL-":
        raise ValueError("readiness ID namespace changed")
    if readiness["sequential_gates"] != ["C1", "C2", "C3"]:
        raise ValueError("readiness gate order changed")
    if int(readiness["formal_execution_count"]) != 0 or int(readiness["formal_artifact_count"]) != 0:
        raise ValueError("readiness cannot consume formal execution or artifacts")
    c1 = _mapping(readiness["C1"], "C1")
    _exact_keys(
        c1,
        {"id", "fixture_source", "fixture", "required", "floor_failure_disposition"},
        "C1",
    )
    fixture = _mapping(c1["fixture"], "C1 fixture")
    _exact_keys(
        fixture,
        {"spatial_level", "grid", "time_divisor", "initial_state", "protocol", "final_time_s", "forced_landing_times_s"},
        "C1 fixture",
    )
    if c1["id"] != "PRE-CTRL-LEGAL-CRITICAL" or c1["floor_failure_disposition"] != "NO_GO_TIME_CONTROLLER_REVISION":
        raise ValueError("C1 identity or failure disposition changed")
    if fixture != {
        "spatial_level": 1,
        "grid": {"nx": 10, "ny": 25},
        "time_divisor": 1,
        "initial_state": {
            "temperature_K": 336.4,
            "branch_memory_b": 1.0,
            "conductive_state_s": 0.5,
            "device_voltage_V": 0.0,
        },
        "protocol": "transition_probe_12p5V",
        "final_time_s": 2.0e-8,
        "forced_landing_times_s": [0.0, 5.0e-9, 1.0e-8, 1.5e-8, 2.0e-8],
    }:
        raise ValueError("C1 fixture changed")
    c2 = _mapping(readiness["C2"], "C2")
    _exact_keys(
        c2,
        {
            "fixture",
            "maximum_accepted_intervals",
            "maximum_simulated_time_s",
            "wall_clock_scope",
            "stop_at_first_limit",
            "missing_reversal_or_event",
            "event_or_reversal_if_present_requires_full_history_streaming_parity",
            "wall_clock_truncation",
            "insufficient_samples_for_C3",
            "formal_event_or_trend_vote",
        },
        "C2",
    )
    if c2["missing_reversal_or_event"] != "NA_not_observed_within_bounded_C2_window":
        raise ValueError("C2 event-absence disposition changed")
    if c2["insufficient_samples_for_C3"] != "NO_GO_RUNTIME_PERFORMANCE_ONLY":
        raise ValueError("C2 insufficient-evidence outcome changed")
    c3 = _mapping(readiness["C3"], "C3")
    _exact_keys(
        c3,
        {
            "inherit_execution_addendum_runtime_preflight",
            "wall_clock_s_max_for_C1_C2_C3_runtime_preflight",
            "grids",
            "deterministic_states",
            "campaign_cost_unique_units",
            "scheduler",
            "coupled_solve_cost_multiplier_must_be_measured_not_assumed",
            "dormant_formal_runner_only",
            "formal_registry_or_ID",
            "GO_gates",
        },
        "C3",
    )
    if int(c3["wall_clock_s_max_for_C1_C2_C3_runtime_preflight"]) != 900:
        raise ValueError("runtime preflight budget changed")
    if c3["grids"] != ["L1", "L2", "L4"] or c3["deterministic_states"] != [
        "equilibrium",
        "legal_critical",
        "high_conductive",
    ]:
        raise ValueError("C3 grid/state coverage changed")
    go_gates = _mapping(c3["GO_gates"], "C3 GO gates")
    _exact_keys(
        go_gates,
        {
            "predicted_p95_makespan_s_max",
            "hard_makespan_s_max",
            "formal_execution_count",
            "formal_artifact_count",
        },
        "C3 GO gates",
    )
    if (
        float(go_gates["predicted_p95_makespan_s_max"]),
        float(go_gates["hard_makespan_s_max"]),
        int(go_gates["formal_execution_count"]),
        int(go_gates["formal_artifact_count"]),
    ) != (11520.0, 14400.0, 0, 0):
        raise ValueError("C3 GO gates changed")

    outcomes = _mapping(overlay["outcomes"], "outcomes")
    expected_outcomes = {
        "all_C1_C2_C3_readiness_gates_pass": "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "controller_integrity_ledger_parity_or_critical_trajectory_failure": "NO_GO_TIME_CONTROLLER_REVISION",
        "only_cost_or_memory_failure": "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        "performance_only_repair_in_this_task": "forbidden",
        "second_controller_revision": "forbidden",
        "automatic_formal_campaign_after_GO": "forbidden",
    }
    if outcomes != expected_outcomes:
        raise ValueError("controller-v2 outcome map changed")
    claim = _mapping(overlay["claim_boundary"], "claim boundary")
    _exact_keys(claim, {"maximum_GO_claim", "forbidden"}, "claim boundary")
    outputs = _mapping(overlay["outputs"], "outputs")
    _exact_keys(outputs, OUTPUT_KEYS, "outputs")
    namespace = "outputs/tables/geophase_phase1_v2/controller_v2_readiness"
    if outputs["namespace"] != namespace:
        raise ValueError("controller readiness output namespace changed")
    for key, value in outputs.items():
        if key in {"namespace", "report", "publish_order", "overwrite_historical_runtime_readiness_or_PR7_evidence"}:
            continue
        if not str(value).startswith(namespace + "/"):
            raise ValueError(f"controller output {key} escaped its namespace")
    if outputs["overwrite_historical_runtime_readiness_or_PR7_evidence"] != "forbidden":
        raise ValueError("historical readiness overwrite was enabled")


def _load_yaml(path: Path) -> dict[str, Any]:
    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), str(path))


def resolve_controller_v2(base_path: Path, overlay_path: Path) -> ResolvedControllerV2:
    base = _load_yaml(base_path)
    overlay = _load_yaml(overlay_path)
    authority = _mapping(overlay["authority_lock"], "authority lock")
    locked_base = _mapping(authority["base_S2_config"], "base S2 lock")
    base_hash = sha256_path(base_path)
    if base_hash != str(locked_base["sha256"]):
        raise ValueError("base S2 YAML hash differs from preregistration")
    if locked_base["base_file_bytes_mutable"] is not False:
        raise ValueError("base S2 YAML bytes must remain immutable")

    validate_controller_overlay_document(overlay, base)
    root = base_path.resolve().parent.parent
    authority = _mapping(overlay["authority_lock"], "authority lock")
    path_hash_records = [
        authority["source_contract"],
        authority["formal_manifest"],
        authority["formal_manifest"]["expanded_CSV"],
        authority["formal_manifest"]["expanded_JSON"],
        authority["execution_DAG"],
        {
            "path": authority["execution_DAG"]["CSV_path"],
            "sha256": authority["execution_DAG"]["CSV_sha256"],
        },
        {
            "path": authority["execution_addendum"]["path"],
            "sha256": authority["execution_addendum"]["sha256"],
        },
    ]
    historical = authority["historical_controller_v1"]
    path_hash_records.extend(
        historical[key]
        for key in (
            "audit_config",
            "failure_telemetry",
            "attempted_step_CSV",
            "diagnosis",
            "report",
        )
    )
    for record in path_hash_records:
        path = root / str(record["path"])
        if sha256_path(path) != str(record["sha256"]):
            raise ValueError(f"authority hash mismatch: {record['path']}")
    resolved = copy.deepcopy(base)
    reference = overlay["controller_overlay"]["reference_solver"]
    resolved["reference_solver"]["time_discretization"] = reference[
        "time_discretization"
    ]
    if "active_time_controller" in resolved["reference_solver"]:
        raise ValueError("ADD operation target already exists in base S2 YAML")
    resolved["reference_solver"]["active_time_controller"] = copy.deepcopy(
        reference["active_time_controller"]
    )

    overlay_hash = sha256_path(overlay_path)
    identity_payload = {
        "base_S2_config_sha256": base_hash,
        "controller_v2_overlay_sha256": overlay_hash,
        "resolution_schema_version": RESOLUTION_SCHEMA_VERSION,
    }
    canonical = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    identity_hash = hashlib.sha256(canonical).hexdigest()
    return ResolvedControllerV2(
        base_config=base,
        overlay_document=overlay,
        resolved_config=resolved,
        base_sha256=base_hash,
        overlay_sha256=overlay_hash,
        identity_payload=identity_payload,
        identity_sha256=identity_hash,
    )


__all__ = [
    "ACTIVE_CONTROLLER_KEYS",
    "DOCUMENT_KEYS",
    "EXACT_OPERATIONS",
    "REFERENCE_SOLVER_KEYS",
    "RESOLUTION_SCHEMA_VERSION",
    "ResolvedControllerV2",
    "resolve_controller_v2",
    "sha256_path",
    "validate_controller_overlay_document",
]
