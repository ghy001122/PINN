"""Fail-closed integrity checks for generated M40 preregistration/evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


CONFIG_PATH = Path("configs/m40_qiu_vo2_real_device_2d.yaml")
SUMMARY_PATH = Path("outputs/tables/m40_qiu_e0_summary.json")


def _config() -> dict:
    if not CONFIG_PATH.exists():
        pytest.skip("M40 preregistration config not generated")
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _gate_block(config: dict) -> dict:
    for key in ("gates", "e0_gates", "result_gates"):
        if key in config:
            return config[key]
    pytest.fail("M40 config must expose one explicit E0 gate block")


def test_m40_hard_gates_are_preregistered_at_the_user_locked_values() -> None:
    gates = _gate_block(_config())
    assert gates["relative_current_imbalance_max"] == 1.0e-6
    assert gates["smooth_window_energy_imbalance_max"] == 1.0e-4
    assert gates["switching_window_energy_imbalance_max"] == 1.0e-3
    assert gates["main_qoi_mesh_change_max"] == 0.01
    assert gates["peak_field_mesh_change_max"] == 0.02
    assert gates["uniform_2d_to_reduced_error_max"] == 0.01


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M40 formal E0 result not generated")
def test_m40_result_is_formal_single_run_and_fail_closed_for_m41() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "task_id",
        "formal_execution_attempt",
        "gate_thresholds",
        "gate_values",
        "gate_results",
        "e0_all_gates_pass",
        "m41_conservative_reduction_authorized",
        "frozen_gt_unchanged",
        "forbidden_actions",
        "status",
    }
    assert required <= set(summary)
    assert summary["task_id"] == "Q2_M40_QIU_VO2_REAL_DEVICE_2D_BRIDGE_E0"
    assert summary["formal_execution_attempt"] == 1
    assert summary["frozen_gt_unchanged"] is True
    assert summary["gate_results"]
    assert all(isinstance(value, bool) for value in summary["gate_results"].values())
    all_gates_and_integrity = all(summary["gate_results"].values()) and summary[
        "frozen_gt_unchanged"
    ]
    assert summary["e0_all_gates_pass"] is all_gates_and_integrity
    assert summary["m41_conservative_reduction_authorized"] is all_gates_and_integrity

    locked = _gate_block(_config())
    for name, threshold in locked.items():
        if name.endswith("_max"):
            assert summary["gate_thresholds"][name] == threshold
    if not all_gates_and_integrity:
        assert summary["status"] == "failed_but_informative"
        assert summary["m41_conservative_reduction_authorized"] is False
    else:
        assert summary["status"] == "qualified_supported"


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M40 formal E0 result not generated")
def test_m40_result_keeps_forbidden_actions_and_real_device_claims_closed() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert {
        "inverse",
        "PINN training",
        "parameter search",
        "M38",
        "Zhang sealed 13 V access",
        "frozen GT modification",
        "real-device calibrated wording",
        "experimental validation wording",
    } <= set(summary["forbidden_actions"])
    for key in (
        "inverse_executed",
        "pinn_training_performed",
        "parameter_search_performed",
        "m38_executed",
        "sealed_13v_access",
        "frozen_gt_modified",
    ):
        assert summary[key] is False
    assert summary["real_device_calibrated_claim_allowed"] is False
    assert summary["experimental_validation_claim_allowed"] is False
    assert summary["inverse_claim_allowed"] is False
