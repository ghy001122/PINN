from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_m42_result_fails_closed_to_decision_b_with_budget_and_provenance() -> None:
    summary = json.loads(
        (ROOT / "outputs/tables/m42_qiu_2d_preflight_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed_but_informative"
    assert summary["decision"] == "B"
    assert summary["hermetic_replay"]["passed"] is True
    assert summary["hermetic_replay"]["pytest_passed"] == 442
    assert summary["protected_evidence_unchanged"] is True
    assert summary["protected_evidence_mtime_unchanged"] is True
    assert summary["claim_bearing_device_forward_runs"] == 0
    assert summary["curve_fit_runs"] == 0
    assert summary["inverse_runs"] == 0
    assert summary["pinn_training_runs"] == 0
    accounting = summary["forward_accounting"]
    assert accounting["total_forward_solves"] == 22
    assert accounting["unique_preflight_case_count"] == 11
    assert accounting["total_forward_solves"] <= accounting["maximum_forward_solves"]
    gates = summary["gates"]
    assert gates["smooth_enthalpy_imbalance"]["passed"] is True
    assert gates["uniform_2d_source_resistance"]["passed"] is False
    assert gates["pure_2d_out_of_plane_closure"]["passed"] is False
    assert gates["switching_enthalpy_imbalance"]["passed"] is False


def test_m42_case_registry_contains_only_bounded_nonvoting_preflights() -> None:
    with (ROOT / "outputs/tables/m42_qiu_2d_preflight_cases.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12  # one analytic ledger plus eleven unique forward cases
    assert all(row["scientific_vote"] == "False" for row in rows)
    assert not any("13V" in row["case_id"] for row in rows)
    assert {
        "analytic_manufactured",
        "manufactured_circuit",
        "unit_load_linear_thermal_preflight",
    } == {row["forward_class"] for row in rows}
