from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.solvers.geophase_phase1_v2_controller_overlay import (
    RESOLUTION_SCHEMA_VERSION,
    resolve_controller_v2,
    validate_controller_overlay_document,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
OVERLAY_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_embedded_time_controller_v2.yaml"
)
STAGE_PATH = ROOT / "configs" / "geo2p5d_stage.yaml"
METHOD_PATH = ROOT / "docs" / "method_equations.md"
PREREGISTRATION_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "controller_v2_readiness"
    / "preregistration.json"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _controller() -> dict:
    return _yaml(OVERLAY_PATH)["controller_overlay"]["reference_solver"][
        "active_time_controller"
    ]


def test_controller_v2_overlay_locks_all_authoritative_inputs() -> None:
    cfg = _yaml(OVERLAY_PATH)
    lock = cfg["authority_lock"]
    expected = {
        "base_S2_config": "0600498590a8c100ec8dee95621719ea655354ec118015868cb07fedf89f85d5",
        "source_contract": "857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252",
        "execution_addendum": "9d477b79a6a598b5032f104bea5b92290026b798e6599c2e9813c9ba11083640",
        "formal_manifest": "54823e83d813ec4acd8df25354b62c38d58be158548414e637282383d1dc14a5",
        "execution_DAG": "1f8a5ef122898974224c2208a0b41af0f776b5ef07bca444f5f0a727b5c9c87a",
    }
    for key, digest in expected.items():
        relative = lock[key]["path"]
        assert _sha256(ROOT / relative) == digest == lock[key]["sha256"]

    manifest = lock["formal_manifest"]
    assert _sha256(ROOT / manifest["expanded_CSV"]["path"]) == (
        manifest["expanded_CSV"]["sha256"]
    )
    assert _sha256(ROOT / manifest["expanded_JSON"]["path"]) == (
        manifest["expanded_JSON"]["sha256"]
    )
    dag = lock["execution_DAG"]
    assert _sha256(ROOT / dag["CSV_path"]) == dag["CSV_sha256"]
    assert lock["merged_pr7_main_commit"] == (
        "8a8541f19ab5b5baeda5102a70e593f996c59224"
    )
    assert lock["merged_pr7_main_tree"] == (
        "5ab294e8048ec04da1d4ad2cbc8cb8f4b0eb6c5d"
    )
    assert manifest["evaluation_item_count"] == 63
    assert manifest["unique_execution_unit_count"] == 60
    assert manifest["legal_reuse_count"] == 3
    historical = lock["historical_controller_v1"]
    for key in (
        "audit_config",
        "failure_telemetry",
        "attempted_step_CSV",
        "diagnosis",
        "report",
    ):
        record = historical[key]
        assert _sha256(ROOT / record["path"]) == record["sha256"]


def test_resolution_changes_only_the_two_preregistered_controller_paths() -> None:
    resolved = resolve_controller_v2(BASE_PATH, OVERLAY_PATH)
    expected = copy.deepcopy(resolved.base_config)
    reference = resolved.overlay_document["controller_overlay"]["reference_solver"]
    expected["reference_solver"]["time_discretization"] = reference[
        "time_discretization"
    ]
    expected["reference_solver"]["active_time_controller"] = reference[
        "active_time_controller"
    ]

    assert resolved.resolved_config == expected
    assert resolved.base_sha256 == _sha256(BASE_PATH)
    assert resolved.overlay_sha256 == _sha256(OVERLAY_PATH)
    assert resolved.identity_payload == {
        "base_S2_config_sha256": resolved.base_sha256,
        "controller_v2_overlay_sha256": resolved.overlay_sha256,
        "resolution_schema_version": RESOLUTION_SCHEMA_VERSION,
    }
    assert len(resolved.identity_sha256) == 64
    assert _sha256(BASE_PATH) == (
        "0600498590a8c100ec8dee95621719ea655354ec118015868cb07fedf89f85d5"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document.update({"physical_model": {"tau_s": 2.0}}),
        lambda document: document["controller_overlay"]["reference_solver"].update(
            {"gates": {"acceptance": 1.0}}
        ),
        lambda document: document["controller_overlay"]["reference_solver"][
            "active_time_controller"
        ].update({"formal_protocols": {"transition_probe_12p5V": 9.0}}),
        lambda document: document["controller_overlay"]["reference_solver"][
            "active_time_controller"
        ]["embedded_error"].update({"instantaneous_runtime_denominator": True}),
        lambda document: document["execution_boundary"].update(
            {"S2_equation_parameter_or_tolerance_change": "allowed"}
        ),
        lambda document: document["readiness_validation"]["C1"]["fixture"].update(
            {"protocol": "quiescent_9V"}
        ),
        lambda document: document["outcomes"].update(
            {"all_C1_C2_C3_readiness_gates_pass": "PHASE1_PASSED"}
        ),
    ],
)
def test_closed_schema_rejects_any_nonwhitelisted_override(mutation) -> None:
    document = _yaml(OVERLAY_PATH)
    mutation(document)
    with pytest.raises(ValueError):
        validate_controller_overlay_document(document, _yaml(BASE_PATH))


def test_voltage_scales_are_fixed_by_declared_protocols_and_dual_channels() -> None:
    base = _yaml(BASE_PATH)
    voltage = _controller()["voltage_scale"]
    mapped = voltage["protocol_V_scale_V"]
    expected = {
        "zero_drive": 1.0,
        "quiescent_9V": 9.0,
        "nominal_12V": 12.0,
        "transition_probe_12p5V": 12.5,
        "high_bias_15V": 15.0,
        "pulse_12p5V": 12.5,
    }
    assert mapped == expected
    for name, protocol in base["formal_protocols"]["protocols"].items():
        declared = [
            abs(float(protocol[key]))
            for key in ("input_voltage_V", "baseline_voltage_V", "pulse_voltage_V")
            if key in protocol
        ]
        assert mapped[name] == max(1.0, max(declared))
    assert voltage["runtime_or_device_voltage_dependent_denominator"] == "forbidden"
    assert voltage["missing_protocol_mapping"] == "fail_closed"
    dual = voltage["DUAL0_fixture_device_channel_V_scale_V"]
    assert dual["A_only_drive"] == {"A": 12.5, "B": 1.0}
    assert dual["B_only_drive"] == {"A": 1.0, "B": 12.5}


def test_outer_interval_floor_ladder_and_ledger_semantics_are_exact() -> None:
    controller = _controller()
    outer = controller["outer_interval"]
    assert outer["base_maximum_s"] == pytest.approx(1.0e-8)
    assert outer["emergency_floor_base_s"] == pytest.approx(9.765625e-12)
    assert outer["formal_time_divisors"] == [1, 2, 4]
    assert outer["emergency_floor_applies_to"] == "outer_interval_H_only"
    assert outer["half_steps_below_outer_floor"] == "allowed"
    assert outer["outer_rejection_cap"] == 10
    assert outer["floor_ladder"].startswith("evaluate_Hmax_then_at_most_10")
    assert outer["floor_candidate_failure"].startswith("locked_floor_failure")
    remainder = outer["endpoint_or_forced_landing_remainder"]
    assert remainder["adaptive_floor_search"] == "forbidden"
    assert remainder["allowed_targets"] == [
        "final_time",
        "fixed_output_time",
        "protocol_discontinuity",
    ]

    embedded = controller["embedded_error"]
    assert embedded["acceptance_max"] == pytest.approx(0.02)
    assert embedded["legacy_max_delta_s_delta_b_role"] == (
        "telemetry_only_nonvoting"
    )
    aggregate = controller["aggregate_ledgers"]
    assert aggregate["ledgers"] == [
        "thermal",
        "circuit",
        "combined",
        "device_power_identity",
    ]
    assert aggregate["recompute_from_signed_energy_terms"] is True
    assert aggregate["relative_residual_averaging"] == "forbidden"
    assert (
        "circuit_capacitor_backward_euler_numerical_dissipation_each_half_once"
        in aggregate["accumulated_terms"]
    )


def test_readiness_sequence_is_nonformal_and_event_absence_is_NA() -> None:
    cfg = _yaml(OVERLAY_PATH)
    validation = cfg["readiness_validation"]
    assert validation["id_prefix"] == "PRE-CTRL-"
    assert validation["sequential_gates"] == ["C1", "C2", "C3"]
    assert validation["formal_execution_count"] == 0
    assert validation["formal_artifact_count"] == 0
    assert validation["C1"]["id"] == "PRE-CTRL-LEGAL-CRITICAL"
    assert validation["C2"]["missing_reversal_or_event"] == (
        "NA_not_observed_within_bounded_C2_window"
    )
    assert validation["C2"]["insufficient_samples_for_C3"] == (
        "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    )
    assert validation["C3"]["wall_clock_s_max_for_C1_C2_C3_runtime_preflight"] == 900
    assert cfg["outcomes"] == {
        "all_C1_C2_C3_readiness_gates_pass": "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "controller_integrity_ledger_parity_or_critical_trajectory_failure": "NO_GO_TIME_CONTROLLER_REVISION",
        "only_cost_or_memory_failure": "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        "performance_only_repair_in_this_task": "forbidden",
        "second_controller_revision": "forbidden",
        "automatic_formal_campaign_after_GO": "forbidden",
    }


def test_active_stage_selects_only_controller_v2_and_preserves_v1_history() -> None:
    stage = _yaml(STAGE_PATH)
    revision = stage["phase1_v2_controller_revision"]
    assert revision["active_controller"] == "embedded_time_consistency_v2_only"
    assert revision["historical_controller_v1_active_runtime_selection"] == (
        "forbidden"
    )
    assert revision["formal_execution_count"] == 0
    assert revision["formal_artifact_count"] == 0
    assert stage["formal_execution_count"] == 0

    method = METHOD_PATH.read_text(encoding="utf-8")
    assert "historical v1" in method
    assert "YAML rejection cap was six" in method
    assert "preregistered v2 candidate controller" in method
    assert "Ten halvings are permitted" in method
    assert "At most four rejections" not in method


def test_post_anchor_implementation_diff_contract_protects_science() -> None:
    boundary = _yaml(OVERLAY_PATH)["execution_boundary"]
    allowed = set(boundary["implementation_diff_contract"]["allowed_paths"])
    forbidden = set(boundary["implementation_diff_contract"]["forbidden_paths"])
    assert "src/pinnpcm/solvers/geophase_phase1_v2_controller_v2.py" in allowed
    assert "configs/geophase_phase1_v2_s2_reference.yaml" in forbidden
    assert "configs/geophase_phase1_v2_embedded_time_controller_v2.yaml" in forbidden
    assert "src/pinnpcm/solvers/geophase_phase1_v2_implicit.py" in forbidden
    assert "docs/method_equations.md" in forbidden
    assert allowed.isdisjoint(forbidden)


def test_machine_preregistration_binds_the_pushed_anchor_and_runtime_identity() -> None:
    payload = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    overlay = _yaml(OVERLAY_PATH)
    resolved = resolve_controller_v2(BASE_PATH, OVERLAY_PATH)

    assert payload["task_id"] == "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION"
    assert payload["schema_version"] == (
        "geophase_phase1_v2_controller_v2_preregistration_v1"
    )
    assert payload["status"] == "preregistered_not_executed"
    assert payload["preregistration_commit"] == (
        "406207b02adaa37953ff4d3813aaeee3235c004f"
    )
    assert payload["preregistration_tree"] == (
        "17bc0163a154a1778aa9109e719d019f4be11b5f"
    )
    assert payload["pr7_merge_commit"] == (
        overlay["authority_lock"]["merged_pr7_main_commit"]
    )
    assert payload["pr7_merge_tree"] == (
        overlay["authority_lock"]["merged_pr7_main_tree"]
    )

    assert payload["base_S2_config_sha256"] == _sha256(BASE_PATH)
    assert payload["controller_v2_overlay_sha256"] == _sha256(OVERLAY_PATH)
    assert payload["resolution_schema_version"] == RESOLUTION_SCHEMA_VERSION
    assert payload["resolved_runtime_identity"] == resolved.identity_payload
    assert payload["resolved_runtime_identity_sha256"] == resolved.identity_sha256

    assert payload["formal_execution_count"] == 0
    assert payload["formal_artifact_count"] == 0
    assert payload["formal_execution_consumed"] is False
    assert payload["formal_case_artifacts_generated"] is False
    assert payload["controller_v2_implementation_before_preregistration_push"] is False
    assert (
        payload["new_controller_v2_numerical_execution_before_preregistration_push"]
        is False
    )


def test_machine_preregistration_is_the_only_controller_v2_output_allowlisted() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    directory = "outputs/tables/geophase_phase1_v2/controller_v2_readiness/"
    assert f"!{directory}" in gitignore
    assert f"{directory}*" in gitignore
    assert f"!{directory}preregistration.json" in gitignore
    assert f"!{directory}**" not in gitignore
