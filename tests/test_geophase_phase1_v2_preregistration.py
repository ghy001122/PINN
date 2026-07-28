from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
MANIFEST_CONTRACT_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_formal_manifest.yaml"
)
S1_PATH = ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve.yaml"
AUDIT_PATH = ROOT / "configs" / "qiu_same_device_thermal_holdout_audit.yaml"
STAGE_PATH = ROOT / "configs" / "geo2p5d_stage.yaml"
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
PROJECT_STATE_PATH = ROOT / "PROJECT_STATE.md"
EVIDENCE_INDEX_PATH = ROOT / "docs" / "project_state" / "current_evidence_index.md"
CLAIM_MATRIX_PATH = ROOT / "docs" / "paper" / "final_claim_matrix.md"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase1v2_identity_authority_and_execution_boundary() -> None:
    cfg = _yaml(CONFIG_PATH)
    stage = _yaml(STAGE_PATH)

    assert cfg["task_id"] == "Q2_PHASE1_V2_S2_REFERENCE"
    assert cfg["schema_version"] == "geophase_phase1_v2_s2_reference_v1"
    assert cfg["status"] == "preregistered_pending_implementation_and_bounded_smoke"
    execution = cfg["execution_contract"]
    assert execution["preregistration_must_be_pushed_before_new_numerical_work"] is True
    assert execution["formal_execution_count"] == 0
    assert execution["formal_run_eligibility"].startswith("blocked_")
    assert execution["formal_campaign_requires_fresh_user_authorization"] is True
    assert execution["pinn_training"] == "forbidden"
    assert execution["inverse"] == "forbidden"
    assert execution["full_3d_or_fem"] == "forbidden"

    assert stage["schema_version"] == "geo2p5d_stage_v2"
    assert stage["current_checkpoint"] == (
        "PHASE1_V2_CONTROLLER_V2_NO_GO_RUNTIME_PERFORMANCE_ONLY"
    )
    assert stage["authority"]["current_contract"].endswith(
        "phase1_geophase_2p5d_reference_v2_contract.md"
    )
    assert stage["authority"]["phase1_config"] == str(
        CONFIG_PATH.relative_to(ROOT)
    ).replace("\\", "/")
    assert stage["formal_execution_count"] == 0
    assert stage["authority"]["nonblocking_S1_mve_amendment"].endswith(
        "geophase_phase1_s1_diffusive_sensitivity_mve_v2.yaml"
    )
    assert stage["authority"]["nonblocking_S1_disposition"].endswith(
        "s1_diffusive_mve_v2_interruption_disposition.json"
    )
    assert stage["nonblocking_S1_state"] == {
        "status": "closed_infrastructure_blocked_before_atomic_evidence",
        "rerun_authorization": "forbidden_without_fresh_user_authorization",
        "may_block_S2": False,
        "production_selected": False,
    }
    assert stage["phase1_v2_runtime_state"] == {
        "status": "NO_GO_RUNTIME",
        "controller": "historical_controller_v1",
        "unique_primary_cause": (
            "S2_transition_increment_failed_at_locked_floor_for_legal_critical_PRE_case"
        ),
        "scientific_phase1_result": "forbidden_unassessed",
        "performance_repair_consumed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "next_action": "retained_history_only",
    }
    assert stage["phase1_v2_critical_transition_audit"] == {
        "status": "GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION",
        "evidence_role": "supported_bounded_diagnostic_only",
        "real_numerical_replay_count": 1,
        "actual_trigger_component": "branch_memory_b",
        "conditional_frozen_activation_dt_max_b_s": pytest.approx(
            1.010415820055618e-11
        ),
        "production_floor_determined": False,
        "scientific_phase1_result": "forbidden_unassessed",
        "time_controller_revision_authorized": True,
        "time_controller_revision_execution_status": "consumed_by_controller_v2",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    controller = stage["phase1_v2_controller_revision"]
    assert controller["status"] == "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    assert controller["implementation_and_nonformal_readiness_authorized"] is False
    assert controller["implementation_and_nonformal_readiness_completed"] is True
    assert controller["readiness_rerun_authorized"] is False
    assert controller["performance_optimization_authorized"] is False
    assert controller["controller_revision_opportunity_remaining"] is False
    assert controller["C1_status"] == "pass"
    assert controller["C1_accepted_intervals"] == 23
    assert controller["C2_status"] == "pass"
    assert controller["C2_accepted_intervals"] == 128
    assert controller["C2_event_observation"] == (
        "NA_not_observed_within_bounded_C2_window"
    )
    assert controller["C3_status"] == "performance_only_fail"
    assert controller["C3_single_interval_samples_completed"] == 0
    assert controller["C3_single_interval_samples_expected"] == 18
    assert controller["C3_short_trajectories_completed"] == 1
    assert controller["C3_short_trajectories_expected"] == 9
    assert controller["campaign_cost_forecast"] == "not_eligible"
    assert controller["dormant_runner_status"] == "not_reached"
    assert controller["performance_repair_consumed"] is False
    assert controller["performance_repair_opportunity_remaining"] is True
    assert controller["formal_campaign_authorized"] is False
    assert controller["formal_execution_count"] == 0
    assert controller["formal_artifact_count"] == 0


def test_legacy_phase1_and_source_files_are_immutable() -> None:
    expected = {
        "configs/geophase_phase1_2p5d_reference.yaml": (
            "0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1"
        ),
        "configs/geophase_phase1_vertical_repair_v7.yaml": (
            "5ab66fb41b9af6fd605c351a86fa5928712528fcad8c9bc26cc55d18a0a92a18"
        ),
        "configs/geophase_phase1_vertical_shape_scale_v8.yaml": (
            "e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b"
        ),
        "configs/qiu_vo2_phase1_source_contract.yaml": (
            "857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252"
        ),
        "docs/research_strategy/phase1_geophase_2p5d_reference_contract.md": (
            "c36067b3c89ab809849ad31174e64b096c3c308882948319f55dba5034512299"
        ),
        "outputs/tables/geophase_phase1/formal_case_inventory.csv": (
            "a617284bd8890adcab105851095801b6067307e5c85acfeb9b8a84c8467be045"
        ),
    }
    for relative, digest in expected.items():
        assert _sha256(ROOT / relative) == digest

    history = _yaml(CONFIG_PATH)["route_revision"]
    assert history["v7_v8_repair_results"] == "failed_but_informative"
    assert history["old_96_item_campaign"] == "permanently_planned_not_executed"
    assert history["old_formal_execution_count"] == 0


def test_source_allowlist_excludes_retired_thermal_stack_mapping() -> None:
    source = _yaml(CONFIG_PATH)["source_contract"]
    allowlist = set(source["phase1v2_source_allowlist"])
    excluded = set(source["explicitly_excluded_retired_source_mappings"])
    assert "phase1_device_effective_normalization.electrical_uniform_limit" in allowlist
    assert "phase1_device_effective_normalization.thermal_global_scale" not in allowlist
    assert "phase1_device_effective_normalization.thermal_global_scale" in excluded
    assert "source_author_fitted_lumped_quantities.dynamic_metallic_factor" in excluded
    assert all("substrate_depth" not in item for item in allowlist)


def test_s2_nominal_algebra_and_mask_semantics() -> None:
    cfg = _yaml(CONFIG_PATH)
    geometry = cfg["geometry"]["primary_single_device"]
    materials = cfg["parameter_contract"]["areal_plane_materials"]
    moments = cfg["source_contract"]["thermal_moments"]

    length = geometry["vo2_length_m"]
    width = geometry["vo2_width_m"]
    area = length * width
    overlap = geometry["contact_overlap_nominal_m"]
    contact_area = 2.0 * overlap * width
    vo2 = materials["vo2"]
    ti = materials["ti"]
    au = materials["au"]
    explicit_capacity = (
        vo2["volumetric_heat_capacity_J_m3K"]
        * geometry["vo2_thickness_m"]
        * area
        + ti["volumetric_heat_capacity_J_m3K"]
        * geometry["ti_thickness_m"]
        * contact_area
        + au["volumetric_heat_capacity_J_m3K"]
        * geometry["au_thickness_m"]
        * contact_area
    )
    memory_coefficient = (
        moments["total_device_low_frequency_admittance_coefficient_J_K"]
        - explicit_capacity
    )
    cm_areal = memory_coefficient / area
    g_areal = moments["total_device_conductance_W_K"] / area

    assert area == pytest.approx(5.0e-14, rel=1.0e-14)
    assert contact_area == pytest.approx(2.0e-14, rel=1.0e-14)
    assert explicit_capacity == pytest.approx(1.8047e-14, rel=1.0e-12)
    assert memory_coefficient == pytest.approx(4.9581953e-11, rel=1.0e-12)
    assert memory_coefficient > 0.0
    assert cm_areal == pytest.approx(991.63906, rel=1.0e-8)
    assert g_areal == pytest.approx(4.12e9, rel=1.0e-14)
    assert explicit_capacity + cm_areal * area == pytest.approx(
        moments["total_device_low_frequency_admittance_coefficient_J_K"],
        rel=1.0e-14,
    )
    assert g_areal * area == pytest.approx(
        moments["total_device_conductance_W_K"], rel=1.0e-14
    )

    closure = cfg["S2_nominal_thermal_closure"]
    assert closure["kind"] == "local_uniform_parameter_area_normalized_single_rc"
    assert closure["normalization_geometry"] == "nominal_20nm_contact_overlap_only"
    assert closure["overlap_audit_memory_rule"].startswith("derive_cm_A_once")
    assert cfg["state_contract"]["nominal_vertical_memory_state_fields"] == []
    assert materials["vo2"]["support"] == "entire_active_plane"
    assert materials["ti"]["support"] == "electrode_mask_only"
    assert materials["au"]["support"] == "electrode_mask_only"


def test_s2_contract_removes_active_material_stack_and_k_state_gates() -> None:
    cfg = _yaml(CONFIG_PATH)
    assert "vertical_reference" not in cfg
    assert "vertical_reduction" not in cfg
    assert not any(key.startswith("substrate_depth") for key in cfg["gates"])
    assert not any(key.startswith("k_state") for key in cfg["gates"])
    assert cfg["physics_contract"]["thermal"]["vertical_memory_states"] == (
        "none_in_nominal_S2"
    )
    assert cfg["verification_matrix"]["manufactured"] == [
        "electrical_linear_field",
        "thermal_diffusion_with_source_and_sink",
        "S2_forced_uniform_temperature_response",
    ]
    assert cfg["physics_contract"]["ledger"]["thermal_storage_term"].startswith(
        "integral_Ceff"
    )


def test_time_controller_event_and_stop_rules_are_closed() -> None:
    cfg = _yaml(CONFIG_PATH)
    time_grid = cfg["reference_solver"]["time_grid"]
    assert time_grid["maximum_rejected_steps_per_accepted_step"] == 6
    assert time_grid["divisor_rule"]["base_max_step"].endswith(
        "divided_by_time_divisor"
    )
    assert time_grid["divisor_rule"]["transition_floor"].endswith(
        "divided_by_time_divisor"
    )
    assert time_grid["rejected_step_rule"] == (
        "next_dt_equals_max_current_dt_over_2_and_floor_dt"
    )
    assert time_grid["floor_retry_policy"] == (
        "exactly_one_clamped_floor_proposal_after_sixth_rejection_then_"
        "rejection_of_floor_proposal_fails_closed"
    )
    assert time_grid["endpoint_remainder_below_floor_only"] is True

    event = cfg["metric_contract"]["event_definition"]
    assert event["signal"] == "physical_area_weighted_domain_mean_conductive_state_s"
    assert event["threshold"] == pytest.approx(0.5)
    assert event["counted_directions"] == ["upward", "downward"]
    assert event["minimum_separation_s"] > 0.0

    smoke = cfg["smoke_contract"]
    assert smoke["implementation_defect_repair_limit"] == 1
    assert smoke["correct_implementation_physics_conservation_or_convergence_failure"].startswith(
        "stop_positive_2D_route"
    )


def test_formal_manifest_has_exact_63_unique_ids_and_three_reuses() -> None:
    contract = _yaml(MANIFEST_CONTRACT_PATH)
    assert contract["total_evaluation_items"] == 63
    assert contract["unique_execution_units"] == 60
    assert contract["reused_evaluation_items"] == 3
    assert contract["count_identity"] == "9_plus_30_plus_9_plus_4_plus_5_plus_6_equals_63"

    csv_path = OUTPUT_DIR / "formal_evaluation_manifest.csv"
    metadata_path = OUTPUT_DIR / "formal_evaluation_manifest.json"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    ids = [row["evaluation_id"] for row in rows]
    assert len(rows) == len(set(ids)) == 63
    assert all(identifier.startswith("P1V2-") for identifier in ids)
    assert all(row["status"] == "planned_not_executed" for row in rows)
    reused = [row for row in rows if row["dependency_ids"]]
    assert len(reused) == 3
    assert all(row["evaluation_group"] == "TOP" for row in reused)
    assert all("O20-" in row["evaluation_id"] for row in reused)
    assert metadata["evaluation_item_count"] == 63
    assert metadata["unique_execution_unit_count"] == 60
    assert metadata["formal_execution_count"] == 0


def test_s1_and_source_audit_are_bounded_nonblocking_and_not_formal() -> None:
    cfg = _yaml(CONFIG_PATH)
    s1 = _yaml(S1_PATH)
    audit = _yaml(AUDIT_PATH)
    manifest_text = MANIFEST_CONTRACT_PATH.read_text(encoding="utf-8")

    assert s1["budget"]["active_work_s_max"] == 86400
    assert s1["budget"]["natural_elapsed_s_max"] == 172800
    assert s1["budget"]["may_delay_or_block_S2"] is False
    assert s1["foster_reduction"]["order_schedule"] == [2, 3]
    assert s1["foster_reduction"]["mixed_orders"] == "forbidden"
    assert len(s1["foster_reduction"]["deterministic_multistarts"]["starts"]) == 3
    assert s1["production_selection"]["production_selection_during_current_mve"] == (
        "forbidden"
    )
    assert s1["production_selection"]["self_fit_success_is_not_selection_evidence"] is True
    assert s1["analytic_kernel"]["R_infinity"] == pytest.approx(0.0)
    assert s1["response_contract"]["regularized_impulse_response"][
        "ideal_t0_impulse_vote"
    ] == "forbidden"

    assert audit["budget"]["wall_clock_s_max"] == 14400
    assert audit["budget"]["may_delay_S2_nominal"] is False
    assert audit["allowed_actions"]
    assert "digitize_a_curve_in_this_audit" in audit["forbidden_actions"]
    assert "S1_items_in_formal_manifest: forbidden" in manifest_text
    assert cfg["S1_sensitivity_route"]["nominal_if_no_holdout"] is False


def test_s1_science_is_unassessed_while_interruption_provenance_is_supported() -> None:
    stage = _yaml(STAGE_PATH)
    project_state = PROJECT_STATE_PATH.read_text(encoding="utf-8")
    evidence_index = EVIDENCE_INDEX_PATH.read_text(encoding="utf-8")
    claim_matrix = CLAIM_MATRIX_PATH.read_text(encoding="utf-8")

    assert stage["nonblocking_S1_state"]["rerun_authorization"] == (
        "forbidden_without_fresh_user_authorization"
    )
    assert "| S1 diffusive model-form claim | `forbidden` / unassessed |" in project_state
    assert "| S1 interruption provenance | `supported` infrastructure provenance only |" in project_state
    assert "| S1 diffusive scientific claim | `forbidden`;" in evidence_index
    assert "| S1 interruption provenance | `supported` infrastructure provenance only;" in evidence_index
    s1_claim_row = next(
        line
        for line in claim_matrix.splitlines()
        if line.startswith("| P1v2_s1_model_form_sensitivity |")
    )
    assert "| `forbidden`; scientific result unassessed |" in s1_claim_row
    assert "infrastructure provenance is `supported`" in s1_claim_row
    assert "`failed_but_informative`" not in s1_claim_row


def test_preregistration_history_and_post_anchor_evidence_boundary() -> None:
    prereg = json.loads(
        (OUTPUT_DIR / "preregistration.json").read_text(encoding="utf-8")
    )
    assert prereg["schema_version"] == "geophase_phase1_v2_preregistration_v1"
    assert prereg["base_commit"] == "4234e4431a0358dca40f9d9c5b26993d12ce7846"
    assert prereg["config_sha256"] == _sha256(CONFIG_PATH)
    assert prereg["formal_execution_count"] == 0
    assert prereg["formal_execution_consumed"] is False
    assert prereg["new_numerical_work_before_preregistration_push"] is False
    assert prereg["evaluation_item_count"] == 63

    for forbidden in ("formal_summary.json", "formal_convergence.csv"):
        assert not (OUTPUT_DIR / forbidden).exists()

    optional_nonformal = {
        "s2_smoke_summary.json": "nonvoting_implementation_smoke",
        "qiu_same_device_thermal_holdout_audit.json": None,
        "s1_diffusive_mve_v2_summary.json": None,
    }
    for filename, evidence_type in optional_nonformal.items():
        path = OUTPUT_DIR / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["formal_execution_count"] == 0
        assert payload.get("formal_execution_consumed", False) is False
        if evidence_type is not None:
            assert payload["evidence_type"] == evidence_type
        assert payload.get("production_selected", False) is False
