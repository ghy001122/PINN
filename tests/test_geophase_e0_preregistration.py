from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_e0_2p5d_reference.yaml"


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_geophase_e0_identity_and_fail_closed_scope() -> None:
    cfg = _config()
    assert cfg["task_id"] == "Q2_GEOPHASE_E0_2P5D_REFERENCE"
    assert cfg["phase_id"] == "Q2_GEOPHASE_E0_REFERENCE_SOLVER_FOUNDATION"
    assert cfg["status"] == "preregistered_pending_implementation"
    assert cfg["evidence_type"] == (
        "literature_guided_solver_generated_synthetic_numerical_digital_twin"
    )

    execution = cfg["execution_contract"]
    assert execution["formal_execution_limit"] == 1
    assert execution["pinn_training"] == "forbidden"
    assert execution["inverse"] == "forbidden"
    assert execution["parameter_fit"] == "forbidden"
    assert execution["frozen_gt_write"] == "forbidden"
    assert execution["m44_repair"] == "forbidden"
    assert execution["full_3d"] == "forbidden"


def test_geophase_e0_is_true_xy_with_reduced_vertical_memory() -> None:
    cfg = _config()
    coordinates = cfg["coordinate_contract"]
    assert coordinates["resolved_plane"] == ["x", "y"]
    assert coordinates["x_role"] == "current_path"
    assert coordinates["y_role"] == "device_width_and_interdevice_separation"
    assert coordinates["vertical_role"] == "reduced_passive_thermal_memory"
    assert coordinates["full_vertical_mesh"] is False

    geometry = cfg["geometry"]["primary_single_device"]
    for key in (
        "vo2_length_m",
        "vo2_width_m",
        "vo2_thickness_m",
        "ti_thickness_m",
        "au_thickness_m",
        "contact_overlap_nominal_m",
    ):
        assert geometry[key] > 0.0
    assert geometry["vo2_length_m"] != geometry["vo2_width_m"]


def test_material_kernels_and_state_semantics_cannot_be_blended() -> None:
    cfg = _config()
    primary = cfg["source_contract"]["primary_device"]
    auxiliary = cfg["source_contract"]["auxiliary_device"]
    assert primary["family"] == "VO2"
    assert auxiliary["family"] == "SnSe_NbO2"
    assert auxiliary["execution_in_e0"] == "forbidden"
    assert auxiliary["zero_shot_transfer"] == "forbidden"

    state = cfg["state_contract"]
    assert state["conductive_state_semantics"] == (
        "effective_conductive_state_coordinate_not_measured_phase_fraction"
    )
    assert state["free_log_conductivity_head"] == "forbidden"
    assert state["oxygen_vacancy_field"] == "forbidden"
    assert "project_engineering_closure" in state["branch_closure"]["equation_role"]


def test_k_state_selection_is_passive_bounded_and_predeclared() -> None:
    cfg = _config()
    reduction = cfg["vertical_reduction"]
    assert reduction["candidate_orders"] == [2, 3]
    assert reduction["ablation_order"] == 1
    assert reduction["reference_order"] > max(reduction["candidate_orders"])
    assert reduction["positive_capacities_required"] is True
    assert reduction["positive_conductances_required"] is True
    assert reduction["stable_real_poles_required"] is True
    assert reduction["if_no_candidate_passes"] == "fail_e0_and_block_e1"

    reference = cfg["vertical_reference"]
    assert reference["kind"] == "independent_1d_multilayer_finite_volume_diffusion"
    assert reference["substrate_depth_audit_m"][1] > reference["substrate_depth_audit_m"][0]
    assert reference["reduction_fit"].startswith("nonnegative_passive")


def test_synthetic_parameter_lock_is_explicit_and_not_qiu_calibration() -> None:
    cfg = _config()
    params = cfg["parameter_contract"]
    assert params["lock_status"] == "locked_for_synthetic_e0_not_device_calibration"
    assert params["vo2_phase_shape"]["T_c_up_K"] > params["vo2_phase_shape"]["T_c_down_K"]
    assert params["vo2_phase_shape"]["transition_width_K"] > 0.0
    assert params["vo2_conductivity"]["sigma_met_ref_S_m"] > params["vo2_conductivity"]["sigma_ins_ref_S_m"]
    assert "not_Qiu_local_measurement" in params["vo2_conductivity"]["provenance"]
    assert params["validity"]["extrapolation_outside_range"] == "forbidden"


def test_e0_gates_and_unlock_do_not_accept_finite_only_success() -> None:
    cfg = _config()
    gates = cfg["gates"]
    assert gates["all_required_gates_must_pass"] is True
    assert gates["terminal_current_relative_imbalance_max"] <= 1.0e-6
    assert gates["energy_ledger_relative_residual_max"] <= 1.0e-2
    assert gates["spatial_terminal_fine_pair_nrmse_max"] <= 1.0e-2
    assert gates["temporal_terminal_fine_pair_nrmse_max"] <= 1.0e-2
    assert gates["k_state_step_response_nrmse_max"] <= 5.0e-2
    assert gates["k_state_impulse_response_nrmse_max"] <= 5.0e-2

    assert cfg["unlock"]["e1_forward_pinn"] == "all_required_e0_gates_pass"
    assert cfg["reference_solver"]["pinn_residual_code_reuse"] == "forbidden"


def test_active_equation_and_provenance_contracts_are_routed() -> None:
    cfg = _config()
    inherited = ROOT / cfg["source_contract"]["primary_device"]["inherited_provenance_config"]
    assert inherited.is_file()

    equations = (ROOT / "docs" / "method_equations.md").read_text(encoding="utf-8")
    for marker in (
        "Active GeoPhase 2.5D Candidate Contract",
        r"\mathbf K=-t_{\mathrm{pcm}}",
        "K-state",
        "effective conductive-state coordinate",
        "independent FVM judge",
    ):
        assert marker in equations

    for relative in cfg["outputs"].values():
        assert not Path(relative).is_absolute()
        assert ".." not in Path(relative).parts
