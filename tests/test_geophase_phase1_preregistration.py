from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml"
SOURCE_PATH = ROOT / "configs" / "qiu_vo2_phase1_source_contract.yaml"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _source() -> dict:
    return yaml.safe_load(SOURCE_PATH.read_text(encoding="utf-8"))


def test_geophase_phase1_identity_and_fail_closed_scope() -> None:
    cfg = _config()
    assert cfg["task_id"] == "Q2_PHASE1_2P5D_REFERENCE"
    assert cfg["schema_version"] == "geophase_phase1_2p5d_reference_v2"
    assert cfg["phase_id"] == "Q2_PHASE1_2P5D_REFERENCE_SOLVER"
    assert cfg["status"] == "preregistered_contract_hardened_pending_implementation"
    assert cfg["evidence_type"] == (
        "literature_guided_solver_generated_synthetic_numerical_digital_twin"
    )

    execution = cfg["execution_contract"]
    assert execution["formal_execution_limit"] == 1
    assert execution["formal_run_eligibility"].startswith("blocked_until_")
    assert execution["maximum_solver_cases"] == 96
    assert execution["pinn_training"] == "forbidden"
    assert execution["inverse"] == "forbidden"
    assert execution["device_or_literature_parameter_fit"] == "forbidden"
    assert execution["passive_k_state_reduction_fit"] == (
        "required_and_not_device_calibration"
    )
    assert execution["frozen_gt_write"] == "forbidden"
    assert execution["m44_repair"] == "forbidden"
    assert execution["full_3d"] == "forbidden"


def test_phase1_is_single_device_xy_with_explicit_region_topology() -> None:
    cfg = _config()
    coordinates = cfg["coordinate_contract"]
    assert coordinates["resolved_plane"] == ["x", "y"]
    assert coordinates["x_role"] == "current_path"
    assert coordinates["y_role"] == "single_device_width"
    assert coordinates["vertical_role"] == (
        "region_specific_reduced_passive_thermal_memory"
    )
    assert coordinates["full_vertical_mesh"] is False
    assert coordinates["interdevice_substrate_resolved"] is False
    assert coordinates["nonzero_dual_device_coupling_in_phase1"] == "forbidden"

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

    masks = cfg["geometry"]["region_masks"]
    assert masks["resolved_domain"] == "vo2_footprint_only"
    assert masks["background_al2o3_between_devices"].startswith("excluded_")
    assert masks["mask_edges_must_align_with_fvm_faces"] is True

    dual = cfg["geometry"]["dual_device_limit_fixture"]
    assert dual["coupling_conductance_W_m2K"] == 0.0
    assert dual["nonzero_coupling_kernel"] == "forbidden"
    assert "substrate_surface_heat_field" in dual["later_unlock_requirement"]


def test_source_only_contract_separates_facts_priors_and_history() -> None:
    cfg = _config()
    primary = cfg["source_contract"]["primary_device"]
    source_path = ROOT / primary["source_only_config"]
    manifest_path = ROOT / primary["source_manifest"]
    assert source_path == SOURCE_PATH
    assert source_path.is_file()
    assert manifest_path.is_file()
    assert "inherited_provenance_config" not in primary

    source = _source()
    assert source["contract_id"] == "QIU_VO2_PHASE1_SOURCE_ONLY"
    assert source["primary_source"]["doi"] == "10.1002/adma.202306818"
    assert source["literature_reported"]["geometry"]["vo2_width_m"]["value"] > 0.0
    assert source["source_author_fitted_lumped_quantities"]["parallel_capacitance_F"]["value"] > 0.0
    assert source["phase1_engineering_priors"]["contact_overlap_nominal_m"] > 0.0
    assert source["unresolved_semantics"]
    assert source["withheld_curve_boundary"]["numeric_access_in_phase1"] == "forbidden"

    history = source["historical_reuse_boundary"]
    assert (ROOT / history["m40_config"]).is_file()
    assert history["m40_m40r_m44_allowed_role"] == (
        "source_locator_and_failure_lesson_only"
    )
    assert history["inherit_parameter_numeric_vote"] is False
    assert history["inherit_field_or_convergence_vote"] is False
    assert history["inherit_claim_status"] is False


def test_material_kernels_and_state_semantics_cannot_be_blended() -> None:
    cfg = _config()
    primary = cfg["source_contract"]["primary_device"]
    auxiliary = cfg["source_contract"]["auxiliary_device"]
    assert primary["family"] == "VO2"
    assert auxiliary["family"] == "SnSe_NbO2"
    assert auxiliary["execution_in_phase1"] == "forbidden"
    assert auxiliary["zero_shot_transfer"] == "forbidden"

    state = cfg["state_contract"]
    assert state["conductive_state_semantics"] == (
        "effective_conductive_state_coordinate_not_measured_phase_fraction"
    )
    assert state["free_log_conductivity_head"] == "forbidden"
    assert state["oxygen_vacancy_field"] == "forbidden"
    assert "project_engineering_closure" in state["branch_closure"]["equation_role"]


def test_k_state_selection_is_region_specific_passive_and_predeclared() -> None:
    cfg = _config()
    reduction = cfg["vertical_reduction"]
    assert reduction["region_ids"] == ["bare_vo2", "electrode_covered_vo2"]
    assert reduction["candidate_orders"] == [2, 3]
    assert reduction["ablation_order"] == 1
    assert reduction["reference_order"] > max(reduction["candidate_orders"])
    assert reduction["positive_capacities_required"] is True
    assert reduction["positive_conductances_required"] is True
    assert reduction["stable_real_poles_required"] is True
    assert reduction["if_no_candidate_passes"] == "fail_phase1_and_block_phase2"

    reference = cfg["vertical_reference"]
    assert reference["kind"].startswith("independent_region_specific")
    assert reference["active_vo2_storage_in_memory_fit"].startswith("excluded_")
    assert set(reference["region_contracts"]) == {
        "bare_vo2",
        "electrode_covered_vo2",
    }
    assert reference["substrate_depth_audit_m"][1] > reference["substrate_depth_audit_m"][0]

    fit = reference["reduction_fit_contract"]
    assert fit["method"] == "nonnegative_passive_least_squares"
    assert fit["step_window_s"] == [0.0, 2.0e-5]
    assert fit["frequency_fit_grid_Hz"]["points"] >= 32
    assert sum(fit["response_weights"].values()) == pytest.approx(1.0)
    assert fit["optimizer_relative_objective_tolerance"] <= 1.0e-10
    assert fit["gates_vote_on_validation_grids_not_fit_grids"] is True


def test_solver_grid_time_protocol_and_tolerances_are_frozen() -> None:
    cfg = _config()
    solver = cfg["reference_solver"]
    geometry = cfg["geometry"]["primary_single_device"]
    grid = solver["base_grid"]
    assert grid["nx"] * grid["dx_m"] == pytest.approx(geometry["vo2_length_m"])
    assert grid["ny"] * grid["dy_m"] == pytest.approx(geometry["vo2_width_m"])
    assert solver["formal_spatial_refinement_levels"] == [1, 2, 4]
    assert solver["formal_time_step_divisors"] == [1, 2, 4]
    assert solver["pinn_residual_code_reuse"] == "forbidden"

    time_grid = solver["time_grid"]
    assert time_grid["final_time_s"] == pytest.approx(2.0e-5)
    assert time_grid["transition_max_step_s"] < time_grid["base_max_step_s"]
    comparison = solver["fixed_physical_comparison_time_grid"]
    expected_points = round(
        (comparison["stop_s"] - comparison["start_s"]) / comparison["interval_s"]
    ) + 1
    assert comparison["points"] == expected_points == 4001
    assert "without_event_alignment" in comparison["method"]

    nonlinear = solver["nonlinear_tolerances"]
    assert nonlinear["maximum_newton_iterations"] == 30
    assert 0.0 < nonlinear["minimum_damping"] < nonlinear["initial_damping"] <= 1.0
    assert nonlinear["fallback_must_meet_same_residual_tolerances"] is True
    assert nonlinear["nonconvergence"] == "fail_closed"

    protocols = cfg["formal_protocols"]
    assert protocols["common_initial_state"]["device_voltage_V"] == 0.0
    assert protocols["common_initial_state"]["branch_memory_b"] == 1.0
    assert set(protocols["protocols"]) == {
        "zero_drive",
        "quiescent_9V",
        "nominal_12V",
        "transition_probe_12p5V",
        "high_bias_15V",
        "pulse_12p5V",
    }


def test_metric_denominators_and_zero_signal_policy_are_explicit() -> None:
    metric = _config()["metric_contract"]
    assert metric["comparison_window_s"] == [0.0, 2.0e-5]
    assert metric["denominator_floors"]["terminal_current_A"] > 0.0
    assert metric["denominator_floors"]["temperature_rise_K"] > 0.0
    assert metric["denominator_floors"]["conductive_state_change"] > 0.0
    assert "nonvoting" in metric["zero_signal_policy"]
    assert "absolute_analytic_limit_gate" in metric["zero_signal_policy"]
    assert metric["nonfinite_policy"] == "fail_closed"
    assert "without_post_hoc_time_warping" in metric["event_time_matching"]


def test_formal_case_inventory_is_exactly_96() -> None:
    cfg = _config()
    inventory = cfg["formal_case_inventory"]
    computed = {
        "vertical_reference_and_reduction": (
            len(inventory["vertical_reference_and_reduction"]["region_ids"])
            * len(inventory["vertical_reference_and_reduction"]["model_orders"])
            * len(inventory["vertical_reference_and_reduction"]["response_types"])
        ),
        "manufactured_solutions": (
            len(inventory["manufactured_solutions"]["problem_ids"])
            * len(inventory["manufactured_solutions"]["refinement_levels"])
        ),
        "single_device_refinement": (
            len(inventory["single_device_refinement"]["protocol_ids"])
            * len(inventory["single_device_refinement"]["grid_time_pairs"])
        ),
        "topology_and_prior_audits": (
            len(inventory["topology_and_prior_audits"]["audit_ids"])
            * len(inventory["topology_and_prior_audits"]["protocol_ids"])
        ),
        "decoupled_dual_copy_limits": len(
            inventory["decoupled_dual_copy_limits"]["case_ids"]
        ),
        "fail_closed_negative_controls": len(
            inventory["fail_closed_negative_controls"]["case_ids"]
        ),
        "analytic_limits": len(inventory["analytic_limits"]["case_ids"]),
    }
    for name, count in computed.items():
        assert inventory[name]["expected_count"] == count
    assert sum(computed.values()) == inventory["total_expected_count"] == 96
    assert cfg["execution_contract"]["formal_case_inventory_total"] == 96
    assert cfg["execution_contract"]["maximum_solver_cases"] == 96


def test_synthetic_parameter_lock_is_explicit_and_not_qiu_calibration() -> None:
    cfg = _config()
    params = cfg["parameter_contract"]
    assert params["lock_status"] == "locked_for_synthetic_phase1_not_device_calibration"
    assert params["vo2_phase_shape"]["T_c_up_K"] > params["vo2_phase_shape"]["T_c_down_K"]
    assert params["vo2_phase_shape"]["transition_width_K"] > 0.0
    assert params["vo2_conductivity"]["sigma_met_ref_S_m"] > params["vo2_conductivity"]["sigma_ins_ref_S_m"]
    assert "not_Qiu_local_measurement" in params["vo2_conductivity"]["provenance"]
    assert params["passive_region_materials"]["ideal_thermal_interfaces"] is True
    assert params["validity"]["extrapolation_outside_range"] == "forbidden"


def test_phase1_gates_and_unlock_do_not_accept_finite_only_success() -> None:
    cfg = _config()
    gates = cfg["gates"]
    assert gates["all_required_gates_must_pass"] is True
    assert gates["terminal_current_relative_imbalance_max"] <= 1.0e-6
    assert gates["energy_ledger_relative_residual_max"] <= 1.0e-2
    assert gates["spatial_terminal_fine_pair_nrmse_max"] <= 1.0e-2
    assert gates["temporal_terminal_fine_pair_nrmse_max"] <= 1.0e-2
    assert gates["k_state_step_response_nrmse_max"] <= 5.0e-2
    assert gates["k_state_impulse_response_nrmse_max"] <= 5.0e-2
    assert gates["literature_trend"]["failure_interpretation"].startswith(
        "failed_but_informative"
    )

    assert cfg["unlock"]["phase2_dataset_generation"] == "all_required_phase1_gates_pass"
    assert cfg["unlock"]["nonzero_dual_device_coupling"].startswith("forbidden_until_")


def test_active_equation_and_output_contracts_are_routed() -> None:
    cfg = _config()
    equations = (ROOT / "docs" / "method_equations.md").read_text(encoding="utf-8")
    for marker in (
        "Active Phase 1 and R1-R3 2.5D Contract",
        r"\mathbf K=-t_{\mathrm{pcm}}",
        "region-specific",
        "effective conductive-state coordinate",
        "independent FVM judge",
        "without post-hoc time warping",
    ):
        assert marker in equations

    for relative in cfg["outputs"].values():
        path = Path(relative)
        assert not path.is_absolute()
        assert ".." not in path.parts
