"""Evidence-lock tests for the single E1F-R formal corrective audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "outputs/tables/e1fr_qiu_source_equation_correction.json"
ORIGINAL = ROOT / "outputs/tables/e1f_qiu_author_validation.json"
AMENDMENT = ROOT / "outputs/tables/e1f_semantic_amendment.json"
CSV = ROOT / "outputs/tables/e1fr_qiu_source_equation_correction.csv"
COORDINATE = ROOT / "outputs/tables/e1fr_effective_coordinate_preflight.json"
FIGURE = ROOT / "outputs/figures/e1fr/qiu_setting_correction.png"
REPORT = ROOT / "docs/codex_reports/e1fr_qiu_source_equation_correction_results.md"


def test_e1fr_result_fails_closed_without_a_holdout_vote() -> None:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    assert payload["status"] == "failed_but_informative"
    assert payload["formal_execution_attempt"] == 1
    assert payload["post_lock_corrective_audit"] is True
    assert payload["original_e1f_status"] == "implementation_contract_invalid"
    assert payload["original_e1f_scientific_vote"] is False
    assert payload["gates"]["solver_parity_all_pass"] is True
    assert payload["gates"]["setting_curve_pass"] is False
    assert payload["gates"]["all_authorized_positive_gates_pass"] is False
    assert payload["setting_curve"]["current"]["range_normalized_rmse"] == pytest.approx(
        0.35315398662125713, rel=1.0e-10
    )
    assert payload["setting_curve"]["voltage"]["range_normalized_rmse"] == pytest.approx(
        0.8156427211418511, rel=1.0e-10
    )
    assert payload["solver_parity_worst_nrmse"] <= 1.0e-3
    assert payload["main_fig2b"] == {
        "independent_holdout": False,
        "scored": False,
        "simulated": False,
        "status": "implementation_contract_invalid_unassessed",
    }
    assert payload["effective_coordinate_preflight"]["status"] == (
        "not_run_upstream_gate_failed"
    )
    assert payload["m41_authorized"] is False
    assert payload["inverse_network_run"] is False
    assert payload["pinn_training_run"] is False
    assert payload["sealed_zhang_13v_access"] is False
    assert payload["forward_integrations"] == 2
    assert payload["formal_budget_respected"] is True
    assert CSV.stat().st_size > 0
    assert FIGURE.stat().st_size > 0
    assert REPORT.stat().st_size > 0
    coordinate = json.loads(COORDINATE.read_text(encoding="utf-8"))
    assert coordinate["status"] == "not_run_upstream_gate_failed"


def test_e1fr_preserves_the_invalid_original_vote_and_semantic_amendment() -> None:
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    assert original["formal_execution_attempt"] == 1
    assert amendment["original_formal_status_superseded_by"] == (
        "implementation_contract_invalid"
    )
    assert amendment["scientific_vote_from_original_run"] is False
    assert amendment["holdout_digitization_defect"][
        "formal_holdout_nrmse_scientific_vote"
    ] is False
