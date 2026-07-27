from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
SUMMARY_PATH = OUTPUT_DIR / "s2_smoke_summary.json"
LEDGER_PATH = OUTPUT_DIR / "s2_smoke_ledgers.csv"
REPAIR_PATH = OUTPUT_DIR / "s2_smoke_implementation_repair.json"
REPORT_PATH = ROOT / "docs" / "codex_reports" / "geophase_phase1_v2_s2_readiness.md"
RUNNER_PATH = ROOT / "scripts" / "run_geophase_phase1_v2_smoke.py"
FVM_PATH = ROOT / "src" / "pinnpcm" / "solvers" / "geophase_phase1_v2_fvm.py"
TEST_PATH = Path(__file__).resolve()

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s2_smoke_is_complete_nonvoting_and_formal_count_zero() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    assert summary["status"] == "completed_nonvoting_smoke_pass"
    assert summary["evidence_type"] == "nonvoting_implementation_smoke"
    assert summary["all_smoke_cases_pass"] is True
    assert summary["scientific_gate_vote"] is False
    assert summary["formal_execution_count"] == 0
    assert summary["formal_execution_consumed"] is False
    assert summary["formal_case_artifacts_generated"] is False
    assert summary["S2_nominal_unchanged"] is True
    assert len(summary["cases"]) == 7
    assert all(case["case_id"].startswith("SMOKE-") for case in summary["cases"])
    assert all(case["implementation_smoke_pass"] for case in summary["cases"])


def test_s2_smoke_ledgers_and_face_backward_error_pass_without_hiding_attempt_one() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    repair = json.loads(REPAIR_PATH.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(LEDGER_PATH.read_text(encoding="utf-8").splitlines()))

    assert rows
    assert all(row["case_id"].startswith("SMOKE-") for row in rows)
    assert summary["implementation_repair_count"] == 1
    assert repair["repair_count"] == repair["repair_limit"] == 1
    assert repair["status"] == "repair_applied_and_identical_smoke_rerun_passed"
    assert repair["identical_smoke_rerun_passed"] is True
    assert repair["scientific_or_physics_gate_changed"] is False
    assert repair["formal_execution_count"] == 0
    assert "near-zero" in repair["defect"]
    criterion = repair["registered_parity_criterion"]
    assert criterion["formula_id"] == "lateral_matrix_face_parity_v1"
    assert criterion["relative_mismatch_max"] == 1.0e-10
    assert criterion["roundoff_ratio_max"] == 1.0
    assert criterion["roundoff_multiplier"] == 64.0
    assert criterion["machine_epsilon_float64"] == pytest.approx(2.220446049250313e-16)
    hashes = repair["implementation_hashes_sha256"]
    assert hashes[RUNNER_PATH.relative_to(ROOT).as_posix()] == _sha256(RUNNER_PATH)
    assert hashes[FVM_PATH.relative_to(ROOT).as_posix()] == _sha256(FVM_PATH)
    assert hashes[TEST_PATH.relative_to(ROOT).as_posix()] == _sha256(TEST_PATH)
    for case in summary["cases"]:
        maxima = case.get("maximum_ledger_residuals")
        if maxima is None:
            continue
        assert maxima["thermal"] <= 1.0e-2
        assert maxima["circuit"] <= 1.0e-2
        assert maxima["combined"] <= 1.0e-2
        assert maxima["device_power"] <= 1.0e-8
        assert (
            maxima["lateral_matrix_face"] <= 1.0e-10
            or maxima["lateral_matrix_face_roundoff"] <= 1.0
        )


def test_s2_smoke_did_not_create_or_upgrade_formal_evidence() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert not (OUTPUT_DIR / "formal_summary.json").exists()
    assert not (OUTPUT_DIR / "formal_convergence.csv").exists()
    assert "formal 63-item campaign remains blocked" in report
    assert "Phase 1-v2 formal gates passed" in summary["forbidden_claims"]
    assert "experimental validation completed" in summary["forbidden_claims"]
