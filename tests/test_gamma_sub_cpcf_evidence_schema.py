from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs" / "schemas" / "gamma_sub_cpcf_summary_v1.schema.json"
SUMMARY = ROOT / "outputs" / "tables" / "gamma_sub_cpcf_pilot_summary.json"


def test_cpcf_summary_matches_locked_schema_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(summary)
    assert summary["schema_version"] == schema["properties"]["schema_version"]["const"]
    assert summary["stage_id"] == schema["properties"]["stage_id"]["const"]
    assert summary["claim_status"] in schema["properties"]["claim_status"]["enum"]
    assert 1 <= int(summary["case_count"]) <= 50
    assert set(schema["properties"]["gates"]["required"]) == set(summary["gates"])
    assert all(isinstance(value, bool) for value in summary["gates"].values())
    assert isinstance(summary["full_sweep_triggered"], bool)
    assert isinstance(summary["full_sweep_executed"], bool)
    assert isinstance(summary["cpcf_main_claim_eligible"], bool)
