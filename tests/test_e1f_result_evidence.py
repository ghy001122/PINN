"""Regression locks for the single consumed E1F formal evidence vote."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _json(path: str | Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_e1f_formal_vote_fails_closed_at_the_curve_gates() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/e1f_qiu_author_external_anchor.yaml").read_text(
            encoding="utf-8"
        )
    )
    result = _json(config["outputs"]["validation_json"])

    assert result["formal_execution_attempt"] == 1
    assert result["forward_integrations"] <= config["budget"][
        "maximum_total_forward_integrations"
    ]
    assert result["status"] == "failed_but_informative"
    assert result["gates"] == {
        "all_positive_anchor_gates_pass": False,
        "holdout_curve_pass": False,
        "setting_curve_pass": False,
        "solver_parity_all_pass": True,
    }
    assert result["solver_parity_worst_nrmse"] <= config["gates"][
        "dop853_radau_current_waveform_nrmse_max"
    ]
    assert result["setting_curve_max_nrmse"] > config["gates"][
        "setting_curve_nrmse_max"
    ]
    assert result["holdout_curve_nrmse"] > config["gates"][
        "holdout_curve_nrmse_max"
    ]
    assert result["setting_curve"]["current"][
        "digitization_envelope_score_min"
    ] > config["gates"]["setting_curve_nrmse_max"]
    assert result["setting_curve"]["voltage"][
        "digitization_envelope_score_min"
    ] > config["gates"]["setting_curve_nrmse_max"]
    assert result["holdout_curve"][
        "digitization_envelope_score_min"
    ] > config["gates"]["holdout_curve_nrmse_max"]


def test_e1f_protected_boundaries_and_conditional_stop_are_locked() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/e1f_qiu_author_external_anchor.yaml").read_text(
            encoding="utf-8"
        )
    )
    result = _json(config["outputs"]["validation_json"])
    preflight = _json(config["outputs"]["coordinate_preflight_json"])

    assert result["m40_m40r_and_frozen_gt_hashes_reverified"] is True
    assert result["m40_or_m40r_solver_rerun"] is False
    assert result["sealed_zhang_13v_access"] is False
    assert result["holdout_refit"] is False
    assert result["pinn_training_run"] is False
    assert result["inverse_network_run"] is False
    assert result["exact_author_code_reproduction_status"] == "forbidden"
    assert result["independent_external_holdout"] is False
    assert result["same_paper_development_contamination_risk"] is True
    assert result["m41_authorized"] is False
    assert preflight["status"] == "not_run_upstream_gate_failed"
    assert preflight["scientific_claim_authorized"] is False
    assert preflight["inverse_network_run"] is False


def test_e1f_machine_readable_outputs_and_bridge_refusal_exist() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/e1f_qiu_author_external_anchor.yaml").read_text(
            encoding="utf-8"
        )
    )
    for key in (
        "validation_json",
        "validation_csv",
        "bridge_mismatch_csv",
        "coordinate_preflight_json",
        "figure_validation",
        "figure_bridge",
        "report",
    ):
        assert (ROOT / config["outputs"][key]).is_file()

    result = _json(config["outputs"]["validation_json"])
    ratios = {row["quantity"]: row for row in result["bridge_audit"]}
    assert ratios["electrical_resistance"]["ratio_local_over_source"] == pytest.approx(
        2.3302332075455143
    )
    assert ratios["thermal_capacitance"]["ratio_source_over_local"] == pytest.approx(
        635.5144976744783
    )
    assert ratios["thermal_conductance"]["ratio_source_over_local"] == pytest.approx(
        206.0
    )
    assert ratios["thermal_time_constant"]["ratio_source_over_local"] == pytest.approx(
        3.085021833371254
    )
    assert all(row["m40_or_m40r_solver_called"] is False for row in ratios.values())
    assert all(row["scientific_vote"] is False for row in ratios.values())
