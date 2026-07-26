from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
V8_PATH = ROOT / "configs" / "geophase_phase1_vertical_shape_scale_v8.yaml"
FORMAL_V6_PATH = ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml"
V7_PATH = ROOT / "configs" / "geophase_phase1_vertical_repair_v7.yaml"
SOURCE_PATH = ROOT / "configs" / "qiu_vo2_phase1_source_contract.yaml"
INVENTORY_PATH = ROOT / "outputs" / "tables" / "geophase_phase1" / "formal_case_inventory.csv"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config() -> dict:
    return yaml.safe_load(V8_PATH.read_text(encoding="utf-8"))


def test_v8_preregistration_locks_authority_and_zero_formal_execution() -> None:
    config = _config()
    authority = config["authority"]
    execution = config["execution_boundary"]
    assert config["task_id"] == "Q2_PHASE1_VERTICAL_SHAPE_SCALE_SEMANTICS_V8"
    assert config["schema_version"] == "geophase_phase1_vertical_shape_scale_v8"
    assert config["status"] == "preregistered_bounded_shape_scale_repair_not_executed"
    assert authority["starting_main_sha"] == "61da2c41b9895ed3d0d7380907d0a8eecbedded6"
    assert authority["required_branch"] == "codex/phase1-vertical-shape-scale-v8"
    assert _sha256(FORMAL_V6_PATH) == authority["formal_v6_config_sha256"]
    assert _sha256(V7_PATH) == authority["v7_repair_config_sha256"]
    assert _sha256(SOURCE_PATH) == authority["source_contract_sha256"]
    assert _sha256(INVENTORY_PATH) == authority["formal_inventory_sha256"]
    assert authority["formal_v6_must_remain_byte_identical"] is True
    assert authority["source_contract_must_remain_byte_identical"] is True
    assert authority["formal_evaluation_item_count"] == 96
    assert execution["repair_protocol_commit_required_before_any_new_numerical_build"] is True
    assert execution["repair_protocol_commit_must_be_pushed_before_any_new_numerical_build"] is True
    assert execution["formal_execution_count"] == 0
    assert execution["formal_case_results_generated"] == 0
    assert execution["formal_campaign_executed"] is False


def test_v8_preregistration_has_two_closed_conditional_depth_pairs() -> None:
    config = _config()
    protocol = config["candidate_protocol"]
    pairs = protocol["pairs"]
    assert list(pairs) == [
        "primary_51p2um_vs_102p4um",
        "conditional_maximum_102p4um_vs_204p8um",
    ]
    assert pairs["primary_51p2um_vs_102p4um"] == {
        "production_depth_m": 5.12e-5,
        "comparator_depth_m": 1.024e-4,
    }
    assert pairs["conditional_maximum_102p4um_vs_204p8um"] == {
        "production_depth_m": 1.024e-4,
        "comparator_depth_m": 2.048e-4,
    }
    trigger = protocol["fallback_pair_trigger"]
    assert trigger["all_primary_mesh_passivity_identity_and_finite_checks_pass"] is True
    assert trigger["any_region_fails_either_separate_raw_depth_grid_family"] is True
    assert trigger["mesh_passivity_identity_or_nonfinite_failure_triggers_fallback"] is False
    assert protocol["primary_pair_pass_action"].endswith("do_not_build_204p8um")
    assert protocol["foundational_failure_action"] == "NO_GO_VERTICAL_REFERENCE"
    assert protocol["maximum_pair_any_required_failure_action"] == "NO_GO_VERTICAL_REFERENCE"
    assert protocol["deeper_pair_or_full_depth_scan_without_new_authorization"] == "forbidden"

    budget = config["raw_build_budget"]
    assert budget["primary_unique_numerical_builds"] == 6
    assert budget["conditional_additional_numerical_builds"] == 2
    assert budget["maximum_unique_numerical_builds"] == 8
    assert budget["full_depth_scan"] == "forbidden"
    assert budget["regions_do_not_duplicate_substrate_builds"] is True


def test_v8_raw_vote_separates_inherited_and_pullback_grids() -> None:
    config = _config()
    vote = config["raw_shape_vote"]
    assert vote["depth_and_mesh_vote_object"] == "unnormalized_raw_material_stack_reference_only"
    assert vote["normalized_comparator_vote"] == "forbidden"
    assert vote["comparator_reanchoring"] == "forbidden"
    assert vote["temporary_scale_role"] == "coordinate_mapping_only"
    assert vote["temporary_scale_must_not_modify_raw_coefficients_or_amplitudes"] is True
    assert vote["formal_to_raw_coordinate_map"] == {
        "frequency": "f_raw_equals_r_times_f_effective",
        "time": "t_raw_equals_t_effective_divided_by_r",
    }
    assert set(vote["grid_families"]) == {"inherited_raw", "formal_window_pullback"}
    assert vote["grid_families_must_be_evaluated_and_gated_separately"] is True
    assert vote["concatenated_or_weighted_cross_family_RMSE"] == "forbidden"
    assert vote["voting_responses_for_depth_and_mesh"] == ["step", "frequency"]
    assert vote["impulse_depth_selection_role"] == "reported_nonvoting_diagnostic"

    gates = config["vertical_gates"]
    assert gates["each_grid_family_mesh_step_error_max"] == 1.0e-2
    assert gates["each_grid_family_mesh_frequency_error_max"] == 1.0e-2
    assert gates["each_grid_family_depth_step_error_max"] == 5.0e-2
    assert gates["each_grid_family_depth_frequency_error_max"] == 5.0e-2
    assert gates["every_region_and_each_grid_family_must_pass_separately"] is True


def test_v8_raw_topology_and_one_device_global_scale_are_locked() -> None:
    config = _config()
    topology = config["region_topology"]
    assert topology["active_vo2_storage_in_raw_reference"] == "forbidden"
    assert topology["bare_vo2"]["branches"] == ["al2o3_fixed_bottom_substrate"]
    assert topology["electrode_covered_vo2"]["branches_in_parallel"] == [
        "al2o3_fixed_bottom_substrate",
        "ti_au_no_flux_overlay",
    ]
    assert topology["ti_au_series_between_vo2_and_al2o3"] == "forbidden"

    normalization = config["production_normalization"]
    assert normalization["compute_only_after_raw_production_depth_is_selected"] is True
    assert normalization["raw_device_conductance"] == "sum_over_regions_A_r_times_G_r"
    assert normalization["raw_device_memory_capacity"] == "sum_over_regions_A_r_times_C_r"
    assert normalization["region_branch_or_comparator_specific_normalization"] == "forbidden"
    assert normalization["normalized_deeper_comparator_construction"] == "forbidden"
    assert normalization["required_equivalence"].startswith("Y_eff_of_s_equals_a_G")
    assert "scaled_depth_invariance" in normalization["forbidden_claims"]


def test_v8_common_K_multistart_and_fail_closed_selection_are_preregistered() -> None:
    config = _config()
    contract = config["k_state_contract"]
    assert contract["truth_reference"].endswith("full_state_space_kernel")
    assert contract["regions"] == ["bare_vo2", "electrode_covered_vo2"]
    assert contract["ablation_order"] == 1
    assert contract["candidate_orders"] == [2, 3]
    assert contract["high_order_benchmark"] == 8
    assert contract["common_production_order_required"] is True
    assert contract["mixed_region_production_orders"] == "forbidden"
    assert contract["evaluation_order"] == [
        "fit_K2_for_both_regions",
        "fit_K3_for_both_regions_only_if_K2_not_jointly_passing",
        "after_common_candidate_selected_fit_K1_ablation_and_K8_benchmark",
    ]
    assert contract["K1_or_K8_may_select_or_change_common_production_order"] is False
    assert contract["K8_validation_role"].startswith(
        "required_high_order_reduced_benchmark"
    )
    assert contract["K8_must_pass_full_kernel_validation"] is True
    assert contract["evaluation_order"][1].endswith("only_if_K2_not_jointly_passing")

    starts = contract["deterministic_initializations"]
    assert starts["maximum_initializations_per_order_region"] == 3
    assert [entry["id"] for entry in starts["starts"]] == [
        "equal_capacity_equal_resistance",
        "increasing_capacity_increasing_resistance",
        "decreasing_capacity_decreasing_resistance",
    ]
    assert starts["selection_before_validation"].startswith("minimum_fitting_objective")
    assert starts["validation_result_may_not_select_or_retry_start"] is True
    assert contract["optimizer"]["optimizer_success_required"] is True
    assert contract["all_required_optimizer_results_absent_status"] == "NO_GO_K_STATE_OPTIMIZATION"
    assert contract["K8_or_K3_required_metric_failure_status"] == "NO_GO_K_STATE"


def test_v8_runtime_is_conditional_nonformal_and_dispositions_are_closed() -> None:
    config = _config()
    runtime = config["runtime_readiness"]
    runner = config["dormant_formal_runner_readiness"]
    assert runtime["enabled_only_after_vertical_and_K_state_pass"] is True
    assert runtime["cpu_only"] is True
    assert runtime["maximum_preflight_wall_clock_s"] == 900
    assert runtime["formal_case_solver_invocation"] == "forbidden"
    assert runtime["formal_case_artifact_generation"] == "forbidden"
    assert runtime["formal_run_id_creation"] == "forbidden"
    assert runtime["four_hour_formal_budget_s"] == 14400
    assert runner["real_formal_registry_creation"] == "forbidden"
    assert runner["future_authorized_start_semantics"][
        "formal_execution_count_changes_from_zero_to_one"
    ] == "atomic_real_registry_creation"
    assert runner["future_authorized_start_semantics"]["same_run_id_resume_count_increment"] == 0

    stop = config["stop_and_disposition"]
    assert stop["allowed_final_dispositions"] == [
        "GO_FOR_CHECKPOINT_B_AUTHORIZATION",
        "NO_GO_VERTICAL_REFERENCE",
        "NO_GO_K_STATE_OPTIMIZATION",
        "NO_GO_K_STATE",
        "NO_GO_RUNTIME",
    ]
    assert stop["automatic_formal_campaign_after_GO"] == "forbidden"
    assert stop["NO_GO_RUNTIME_allows_one_versioned_engineering_only_repair"] is True


def test_v8_immutable_scientific_contract_preserves_gates_inventory_and_scope() -> None:
    immutable = _config()["immutable_scientific_contract"]
    assert immutable["mesh_gate"] == 1.0e-2
    assert immutable["depth_gate"] == 5.0e-2
    assert immutable["k_state_response_gates"] == 5.0e-2
    assert immutable["formal_evaluation_item_count"] == 96
    assert immutable["formal_case_ids_and_physical_axes_unchanged"] is True
    assert immutable["qiu_source_only_contract_unchanged"] is True
    assert immutable["qiu_R_G_C_unchanged"] is True
    assert immutable["frozen_ground_truth_unchanged"] is True
    assert immutable["nonzero_dual_device_coupling"] == "forbidden"
    assert immutable["PINN_training"] == "forbidden"
    assert immutable["phase2_dataset_generation"] == "forbidden"
