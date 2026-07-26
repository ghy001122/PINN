from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPAIR_PATH = ROOT / "configs" / "geophase_phase1_vertical_repair_v7.yaml"
FORMAL_V6_PATH = ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml"
SOURCE_PATH = ROOT / "configs" / "qiu_vo2_phase1_source_contract.yaml"
INVENTORY_PATH = ROOT / "outputs" / "tables" / "geophase_phase1" / "formal_case_inventory.csv"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repair() -> dict:
    return yaml.safe_load(REPAIR_PATH.read_text(encoding="utf-8"))


def test_v7_repair_is_nonvoting_and_preserves_checkpoint_b_boundary() -> None:
    repair = _repair()
    execution = repair["execution_boundary"]
    assert repair["schema_version"] == "geophase_phase1_vertical_repair_v7"
    assert repair["status"] == "preregistered_bounded_repair_not_executed"
    assert execution["repair_protocol_commit_required_before_candidate_screening"] is True
    assert execution["formal_execution_count"] == 0
    assert execution["formal_case_results_generated"] == 0
    assert execution["formal_campaign_executed"] is False
    assert execution["all_repair_results_voting"] is False
    assert execution["phase1_scientific_claim"] == "forbidden_pending_formal_campaign"


def test_v7_repair_locks_exact_warning_and_closed_depth_pairs() -> None:
    repair = _repair()
    reproduction = repair["v6_warning_reproduction"]
    assert reproduction["expected_value"] == 0.12312709438789984
    assert reproduction["relative_error_max"] == 1.0e-10
    assert reproduction["failure_status"] == "NO_GO_V6_WARNING_NOT_REPRODUCED"

    candidates = [float(value) for value in repair["candidate_space"]["production_depths_m"]]
    comparator = float(repair["candidate_space"]["comparator_only_depth_m"])
    assert candidates == [
        4.0e-7,
        8.0e-7,
        1.6e-6,
        3.2e-6,
        6.4e-6,
        1.28e-5,
        2.56e-5,
        5.12e-5,
        1.024e-4,
    ]
    available_depths = {*candidates, comparator}
    assert all(2.0 * depth in available_depths for depth in candidates)
    assert comparator == 2.048e-4
    assert repair["candidate_space"]["comparator_only_depth_is_production_candidate"] is False


def test_v7_repair_build_budget_reuses_substrate_and_overlay_branches() -> None:
    repair = _repair()
    budget = repair["raw_numerical_build_budget"]
    expected = (
        int(budget["substrate_builds"])
        + int(budget["overlay_builds"])
        + int(budget["v6_reproduction_builds"])
        + int(budget["analytic_semi_infinite_fvm_builds"])
    )
    assert expected == int(budget["total_raw_numerical_builds"]) == 26
    assert expected <= int(budget["maximum_raw_numerical_builds"]) == 32
    assert int(budget["substrate_depth_count_including_comparator"]) * len(
        budget["substrate_grid_levels"]
    ) == int(budget["substrate_builds"])
    assert len(budget["overlay_build_ids"]) == int(budget["overlay_builds"])
    assert len(budget["v6_reproduction_build_ids"]) == int(
        budget["v6_reproduction_builds"]
    )
    assert budget["actual_unique_build_manifest_required"] is True
    assert budget["regions_do_not_duplicate_substrate_builds"] is True
    assert repair["normalization_contract"]["per_candidate_pair"]["comparator_reanchored"] is False


def test_v7_repair_locks_v6_source_and_inventory_bytes() -> None:
    repair = _repair()
    authority = repair["authority"]
    assert _sha256(FORMAL_V6_PATH) == authority["formal_v6_config_sha256"]
    assert _sha256(SOURCE_PATH) == authority["source_contract_sha256"]
    assert _sha256(INVENTORY_PATH) == authority["formal_inventory_sha256"]
    assert authority["source_contract_must_remain_byte_identical"] is True
    immutable = repair["immutable_scientific_contract"]
    assert immutable["substrate_depth_frequency_log_magnitude_gate"] == 5.0e-2
    assert immutable["substrate_depth_step_response_gate"] == 5.0e-2
    assert immutable["formal_evaluation_item_count"] == 96
    assert immutable["formal_case_ids_and_physical_axes_unchanged"] is True
    assert immutable["qiu_R_G_C_unchanged"] is True
    assert immutable["frozen_ground_truth_unchanged"] is True
    assert immutable["nonzero_dual_device_coupling"] == "forbidden"


def test_v7_repair_locks_metric_anchor_and_deterministic_grid_semantics() -> None:
    repair = _repair()
    response = repair["locked_response_contract"]
    assert response["time_window_s"] == 2.0e-5
    assert response["frequency_band_Hz"] == [1.0e3, 1.0e10]
    assert response["response_weights"] == {
        "step": 0.4,
        "impulse": 0.2,
        "frequency_log_magnitude": 0.4,
    }
    assert "reference_at_zero" in response["step_error_formula"]
    assert "1e_minus_300" in response["frequency_error_formula"]

    selection = repair["selection_gates"]
    assert selection["global_anchor_voting_scope"] == "production_D_fine_only"
    assert selection["comparator_2D_anchor_role"].startswith("reported_nonvoting")
    assert set(selection["identity_relative_tolerances"].values()) == {1.0e-10}

    grid = repair["nonuniform_grid"]
    generator = grid["deterministic_substrate_generator"]
    assert grid["coarse_first_substrate_cell_rule"] == "exact_surface_cell_rule_value"
    assert generator["bisection_iterations"] == 80
    assert generator["residual_terminal_cell"] == "forbidden"
    assert grid["fine_grid_rule"] == "bisect_every_coarse_cell"
