"""Integrity and fail-closed tests for generated M37R evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.external_data.vo2_cross_regime_observability_repair import (
    validate_evidence_contract,
)
from pinnpcm.external_data.vo2_zhang import compute_sha256


CONFIG_PATH = Path("configs/m37r_continuous_event_observability_repair.yaml")
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
PREREG_PATH = Path(CONFIG["outputs"]["preregistration"])
SUMMARY_PATH = Path(CONFIG["outputs"]["jacobian_summary"])
SPECTRA_PATH = Path(CONFIG["outputs"]["jacobian_spectra"])
EVENT_AUDIT_PATH = Path(CONFIG["outputs"]["event_window_audit"])


@pytest.mark.skipif(not PREREG_PATH.exists(), reason="M37R preregistration not generated")
def test_m37r_preregistration_is_complete_hash_locked_and_sealed() -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert prereg["schema_version"] == "m37r_continuous_event_observability_preregistration_v1"
    assert prereg["all_preflight_checks_pass"] is True
    assert prereg["solver_authorized_after_preregistration_commit"] is True
    assert prereg["formal_execution_limit"] == 1
    assert prereg["fit_authorized"] is False
    assert prereg["fit_lock_authorized"] is False
    assert prereg["pinn_training_authorized"] is False
    assert prereg["m38_execution_authorized"] is False
    assert prereg["sealed_13v_access"] is False
    assert all(prereg["preflight_checks"].values())
    assert prereg["mock_end_to_end_contract"]["all_pass"] is True
    for path, expected in prereg["locked_files"].items():
        assert compute_sha256(Path(path)) == expected
    for path, expected in prereg["historical_read_only_files"].items():
        assert compute_sha256(Path(path)) == expected


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37R formal result not generated")
def test_m37r_result_is_single_run_fail_closed_and_forbidden_actions_absent() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert validate_evidence_contract(summary)["all_pass"] is True
    assert summary["formal_execution_attempt"] == 1
    assert summary["forward_evaluations"]["total"] <= 72
    assert summary["elapsed_seconds"] <= 2.0 * 3600.0
    assert summary["sealed_13v_access"] is False
    assert summary["fit_executed"] is False
    assert summary["fit_lock_created"] is False
    assert summary["pinn_training_performed"] is False
    assert summary["m38_executed"] is False
    assert summary["m35_or_m36_full_workflow_rerun"] is False
    assert summary["m35_m36_m37_artifacts_modified"] is False
    assert summary["next_single_action"] == "Q2_MANUSCRIPT_EVIDENCE_COMPRESSION"
    assert summary["m37r_all_gates_pass"] is summary["gate_results"]["all"]
    if summary["m37r_all_gates_pass"]:
        assert summary["claim_status"] == "qualified_supported"
        assert summary["decision_route"].startswith("D_")
        assert summary["m38_preregistration_eligible_after_human_review"] is True
    else:
        assert summary["claim_status"] == "failed_but_informative"
        assert summary["decision_route"][0] in {"A", "B", "C"}
        assert summary["m38_preregistration_eligible_after_human_review"] is False


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37R formal result not generated")
def test_nominal_full_and_post_counts_are_reported_with_only_post_count_voting() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    expected = CONFIG["event_window"]["expected_nominal_counts"]
    for method in ("DOP853", "Radau"):
        for voltage in (9.0, 11.0, 15.0, 17.0):
            key = f"{voltage:g}"
            record = summary["nominal_checks"][method][key]
            assert record["full_horizon_event_count"] == int(
                expected[key]["full_horizon"]
            )
            assert record["post_transient_event_count"] == int(
                expected[key]["post_transient"]
            )
            assert record["full_horizon_is_gate"] is False
            assert record["post_transient_is_gate"] is True
            assert record["m36_post_transient_event_count_reproduced"] is True
    assert summary["gate_results"]["nominal_window_reproduction"] is True


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37R formal result not generated")
def test_event_audit_has_one_row_per_forward_and_all_topology_votes() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    with EVENT_AUDIT_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == summary["forward_evaluations"]["total"]
    assert {row["run_role"] for row in rows} >= {"nominal"}
    assert all(row["event_window_contract_id"] == "m37r_post_transient_reversal_signature_v1" for row in rows)
    assert all(row["lower_boundary"] == row["upper_boundary"] == "inclusive" for row in rows)
    assert all(row["full_horizon_is_gate"] == "False" for row in rows)
    assert all(row["post_transient_is_gate"] == "True" for row in rows)
    if summary["simulation_checks"]:
        assert "perturbation" in {row["run_role"] for row in rows}
        assert len(summary["simulation_checks"]) == len(rows) - 8


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37R formal result not generated")
def test_spectra_jacobians_and_cross_solver_gates_are_complete_if_reached() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    with SPECTRA_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    if summary["groups"]:
        assert summary["forward_evaluations"] == {"DOP853": 52, "Radau": 20, "total": 72}
        assert set(summary["groups"]) == {"static_only", "oscillatory_only", "joint"}
        assert set(summary["dop853_radau_crosscheck"]) == {
            "static_only",
            "oscillatory_only",
            "joint",
        }
        assert set(summary["whitened_jacobians"]["DOP853"]) == {
            "0.01",
            "0.005",
            "0.0025",
        }
        assert set(summary["whitened_jacobians"]["Radau"]) == {"0.0025"}
        assert {row["observation_group"] for row in rows} >= {
            "static_only",
            "oscillatory_only",
            "joint",
        }
        assert summary["analytic_quotient_transform"]["resimulation_performed"] is False
        assert summary["analytic_quotient_transform"]["rank_increase_claim"] == "forbidden"
    else:
        assert rows == [{"status": "not_reached"}]


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37R formal result not generated")
def test_required_figure_report_and_strict_machine_artifacts_exist() -> None:
    json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert Path(CONFIG["outputs"]["figure"]).stat().st_size > 0
    report = Path(CONFIG["outputs"]["report"]).read_text(encoding="utf-8")
    assert "public-data fit" in report
    assert "trained-PINN" in report
    assert "experimental validation" in report
    assert "Full-horizon counts are diagnostics only" in report
