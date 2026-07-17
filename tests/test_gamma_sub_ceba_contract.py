from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from scripts.audit_gamma_sub_multi_protocol_recoverability import _loss_from_series
from scripts.run_gamma_sub_ceba import (
    DEFAULT_CONFIG,
    _candidate_cache_key,
    _find_bracket,
    _load_config,
    _target_cache_key,
    ceba_objective,
    waveform_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_ceba_preregistered_scope_and_budget_are_bounded() -> None:
    config = _load_config(DEFAULT_CONFIG)
    assert list(config["protocols"]) == ["triangle", "ltp_ltd"]
    assert len(config["parity"]["anchors"]) == 6
    assert len(config["inverse"]["gamma_candidates"]) == 15
    assert config["inverse"]["objective"] == {"w_g": 1.0, "w_i": 0.5}
    assert float(config["inverse"]["heat_residual_weight"]) == 0.0
    assert int(config["budget"]["maximum_unique_solver_trajectories"]) == 60
    assert int(config["budget"]["maximum_workers"]) == 2
    assert float(config["budget"]["maximum_wall_time_minutes"]) == 30.0
    assert int(config["pilot"]["maximum_additional_base_target_trajectories"]) == 12
    assert int(config["pilot"]["refinement"]["maximum_additional_trajectories"]) == 10


def test_ceba_cache_keys_exclude_observation_noise_and_seed() -> None:
    candidate = _candidate_cache_key("wave", 4.5e8, "solver")
    target = _target_cache_key("wave", 0.2, "solver")
    assert candidate == "wave|gamma_sub=450000000|solver"
    assert target == "wave|delta_T_sw_K=0.20000000000000001|solver"
    for forbidden in ("observation", "noise", "seed"):
        assert forbidden not in candidate
        assert forbidden not in target


def test_ceba_objective_is_independent_but_numerically_equal_to_source() -> None:
    pred_g = np.asarray([1.0, 2.1, 2.9])
    pred_i = np.asarray([0.5, 0.7, 0.9])
    target_g = np.asarray([1.1, 2.0, 3.0])
    target_i = np.asarray([0.4, 0.8, 1.0])
    weights = {"w_g": 1.0, "w_i": 0.5}
    local = ceba_objective(pred_g, pred_i, target_g, target_i, weights)
    source = _loss_from_series(pred_g, pred_i, target_g, target_i, weights)
    assert local == source


def test_ceba_waveforms_are_exact_and_distinct() -> None:
    config = _load_config(DEFAULT_CONFIG)
    triangle = waveform_contract(config, "triangle")
    ltp_ltd = waveform_contract(config, "ltp_ltd")
    assert triangle["t_max_s"] == 3.0e-3
    assert ltp_ltd["t_max_s"] == 15.0e-3
    assert triangle["waveform_sha256"] != ltp_ltd["waveform_sha256"]
    assert ltp_ltd["pulse_count"] == 12


def test_ceba_bracket_requires_direct_pass_below_and_failure_above() -> None:
    bracket = _find_bracket(
        {
            0.0: {"passes_locked_gate": True},
            0.5: {"passes_locked_gate": True},
            1.0: {"passes_locked_gate": False},
            2.0: {"passes_locked_gate": False},
        }
    )
    assert bracket == (0.5, 1.0)
    assert _find_bracket({0.0: {"passes_locked_gate": True}, 2.0: {"passes_locked_gate": True}}) is None


def test_ceba_commit_ordered_registration_precedes_solver_results() -> None:
    payload = json.loads((ROOT / "outputs/tables/gamma_sub_ceba_preregistration.json").read_text(encoding="utf-8"))
    assert payload["definition_commit"] == "306f5c9fdc720c71cad18b7ab322d4d0ae73d938"
    assert payload["git_dirty_before_registration"] is False
    assert payload["no_solver_run"] is True
    assert payload["independent_remote_timestamp"] is False
    assert payload["registration_semantics"] == "internal commit-ordered preregistration; not an independent remote timestamp"


def test_ceba_locked_parity_results_pass_every_anchor_gate() -> None:
    summary = json.loads((ROOT / "outputs/tables/gamma_sub_ceba_parity_summary.json").read_text(encoding="utf-8"))
    assert summary["all_parity_gates_pass"] is True
    assert summary["anchor_count"] == summary["anchor_cap"] == 6
    assert summary["unique_solver_trajectories"] == 36
    assert summary["new_solver_trajectory_evaluations"] == 36
    assert summary["max_workers_used"] <= 2
    assert summary["external_13v_accessed"] is False
    assert set(summary["gate_pass_counts"].values()) == {6}
    with (ROOT / "outputs/tables/gamma_sub_ceba_parity_cases.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert all(row["all_core_gates_pass"] == "True" for row in rows)


def test_ceba_locked_pilot_fails_closed_without_boundary_or_refinement() -> None:
    summary = json.loads((ROOT / "outputs/tables/gamma_sub_ceba_pilot_summary.json").read_text(encoding="utf-8"))
    assert summary["claim_status"] == "failed_but_informative"
    assert summary["ceba_configuration_claim_eligible"] is False
    assert summary["scoring_case_count"] == 72
    assert summary["unique_solver_trajectories"] == 36
    assert summary["new_solver_trajectory_evaluations_this_process"] == 0
    assert summary["cache_hits_this_process"] == 36
    assert summary["additional_base_target_trajectories"] == 0
    assert summary["refinement_trajectory_count"] == 0
    assert summary["no_protocol_unit_or_source_mixing"] is True
    assert all(summary["budget_gates"].values())
    for record in summary["protocol_results"].values():
        assert record["delta_T_sw_star_K"] is None
        assert record["heldout_success_failure_bracket_K"] is None
        assert record["solver_refinement_consistent"] is False
    zero_error_conditions = [
        condition["discovery_delta_results"]["0.0"] for condition in summary["condition_results"].values()
    ]
    assert zero_error_conditions
    assert all(record["abstention_rate"] == 1.0 for record in zero_error_conditions)
    assert all(record["success_probability"] == 0.0 for record in zero_error_conditions)


def test_prompt31_final_validation_record_preserves_fail_closed_resolution() -> None:
    payload = json.loads((ROOT / "outputs/tables/prompt31_final_validation.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "prompt31_final_validation_v1"
    assert payload["frozen_gt_modified"] is False
    assert not any(payload["new_high_cost_experiments"].values())
    resolution = payload["scientific_resolution"]
    assert resolution["cpcf_scientific_vote"] is False
    assert resolution["cpcf_status"] == "implementation_contract_invalid"
    assert resolution["ceba_parity_all_passed"] is True
    assert resolution["ceba_configuration_claim_eligible"] is False
    assert resolution["delta_T_sw_star_available"] is False
    budget = payload["budget"]
    assert budget["parity_anchor_count"] <= 6
    assert budget["unique_solver_trajectories"] <= 60
    assert budget["maximum_workers_used"] <= 2
    assert budget["elapsed_seconds_total_parity_and_pilot"] <= 30.0 * 60.0
