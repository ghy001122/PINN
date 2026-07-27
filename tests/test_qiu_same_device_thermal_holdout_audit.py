from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
CSV_PATH = OUTPUT_DIR / "qiu_same_device_thermal_holdout_audit.csv"
JSON_PATH = OUTPUT_DIR / "qiu_same_device_thermal_holdout_audit.json"
REPORT_PATH = ROOT / "docs" / "codex_reports" / "qiu_same_device_thermal_holdout_audit.md"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def test_bounded_source_audit_found_no_eligible_same_device_holdout() -> None:
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(CSV_PATH.read_text(encoding="utf-8").splitlines()))

    assert payload["disposition"] == (
        "no_eligible_holdout_found_within_bounded_audit"
    )
    assert payload["eligible_holdout_count"] == 0
    assert payload["candidate_count"] == len(rows) == 8
    assert all(row["eligibility"] == "ineligible" for row in rows)
    assert all(row["exclusion_reason"] for row in rows)
    assert payload["nominal_phase1v2_closure"].startswith("S2_")
    assert payload["S1_role"] == "model_form_sensitivity_only"
    assert payload["formal_execution_count"] == 0


def test_source_audit_does_not_invent_unrecorded_timing_or_validation() -> None:
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert payload["timing_status"] == "not_instrumented"
    assert payload["audit_started_utc"] is None
    assert payload["audit_finished_utc"] is None
    assert payload["wall_clock_s"] is None
    assert "did not find" in payload["allowed_claim"]
    assert any("do not exist" in claim for claim in payload["forbidden_claims"])
    assert "Forbidden:" in report
    assert "independent thermal validation was completed" in report
    assert "S2 as its nominal closure" in report
