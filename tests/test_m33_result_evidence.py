"""Result-lock tests for the completed one-shot M33 experiment."""

from __future__ import annotations

import json
from pathlib import Path

from pinnpcm.pinn.n0_cv_evidence import raw_sha256


PREREG_COMMIT = "b3f7068223fcf618b212c1919bddddba05b0b7b8"


def _json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_preflight_is_complete_and_precedes_training() -> None:
    preflight = _json("outputs/tables/m33_mixed_flux_preflight.json")
    assert preflight["preregistration_commit"] == PREREG_COMMIT
    assert preflight["git_commit"] == PREREG_COMMIT
    assert len(preflight["checks"]) == 16
    assert preflight["all_pass"] is True
    assert preflight["training_authorized"] is True
    assert all(preflight["checks"].values())


def test_single_training_result_fails_closed_without_aggregation() -> None:
    result = _json("outputs/tables/m33_mixed_flux_final_summary.json")
    assert result["preregistration_commit"] == PREREG_COMMIT
    assert result["training_executed"] is True
    assert result["training_seed"] == 20260715
    assert result["training_steps"] == 1500
    assert result["training_budget_ratio_to_v3r"] == 1.25
    assert result["status"] == "failed_but_informative"
    assert result["positive_forward_claim_allowed"] is False
    assert result["gates"]["all_pass"] is False
    expected_failures = {
        "constitutive",
        "cv_residuals",
        "defect_ledger",
        "energy_ledger",
        "fields",
        "interface_flux",
        "port",
        "v3r_no_regression",
    }
    actual_failures = {name for name, passed in result["gates"]["checks"].items() if not passed}
    assert actual_failures == expected_failures
    assert result["comparison_to_v3r"]["required_metrics"] == 20
    assert result["comparison_to_v3r"]["no_worse_count"] == 10
    assert result["comparison_to_v3r"]["all_no_worse"] is False


def test_training_ledger_cannot_override_independent_trajectory_ledger() -> None:
    result = _json("outputs/tables/m33_mixed_flux_final_summary.json")
    metrics = result["metrics"]
    assert metrics["explicit_head_ledger_rms"]["energy_ledger"] <= 0.05
    assert metrics["explicit_head_ledger_rms"]["defect_mass_ledger"] <= 0.01
    assert metrics["global_energy_ledger"]["gate_value"] > 0.05
    assert metrics["defect_mass_ledger"]["gate_value"] > 0.01
    assert result["gates"]["checks"]["energy_ledger"] is False
    assert result["gates"]["checks"]["defect_ledger"] is False


def test_history_is_finite_and_records_no_post_result_change() -> None:
    history = _json("outputs/tables/m33_mixed_flux_training_history.json")
    assert history["seed"] == 20260715
    assert history["total_steps"] == 1500
    assert len(history["records"]) == 16
    assert all(record["finite"] for record in history["records"])
    assert history["post_result_changes"] == []


def test_frozen_gt_hash_and_checkpoint_manifest_are_consistent() -> None:
    prereg = _json("outputs/tables/m33_mixed_flux_preregistration.json")
    result = _json("outputs/tables/m33_mixed_flux_final_summary.json")
    assert raw_sha256(Path("data/processed/gt_v1_acceptance/gt_triangle.npz")) == prereg["frozen_gt_raw_sha256"]
    checkpoint = Path(result["checkpoint"])
    assert checkpoint.exists()
    assert raw_sha256(checkpoint) == result["checkpoint_sha256"]
