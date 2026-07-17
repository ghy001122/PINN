from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs/schemas/gamma_sub_ceba_summary_v1.schema.json"
PARITY = ROOT / "outputs/tables/gamma_sub_ceba_parity_summary.json"
PILOT = ROOT / "outputs/tables/gamma_sub_ceba_pilot_summary.json"


def _branch_for(schema: dict, schema_version: str) -> dict:
    return next(branch for branch in schema["oneOf"] if branch["properties"]["schema_version"]["const"] == schema_version)


def test_ceba_parity_summary_matches_locked_schema_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    summary = json.loads(PARITY.read_text(encoding="utf-8"))
    branch = _branch_for(schema, summary["schema_version"])
    assert set(branch["required"]) <= set(summary)
    assert summary["claim_status"] in branch["properties"]["claim_status"]["enum"]
    assert isinstance(summary["all_parity_gates_pass"], bool)
    assert isinstance(summary["pilot_authorized"], bool)
    assert summary["anchor_count"] <= branch["properties"]["anchor_count"]["maximum"]
    assert summary["unique_solver_trajectories"] <= branch["properties"]["unique_solver_trajectories"]["maximum"]


def test_ceba_pilot_summary_matches_locked_schema_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    summary = json.loads(PILOT.read_text(encoding="utf-8"))
    branch = _branch_for(schema, summary["schema_version"])
    assert set(branch["required"]) <= set(summary)
    assert summary["claim_status"] in branch["properties"]["claim_status"]["enum"]
    assert isinstance(summary["ceba_configuration_claim_eligible"], bool)
    assert summary["unique_solver_trajectories"] <= branch["properties"]["unique_solver_trajectories"]["maximum"]
    assert summary["protocol_results"]
    assert all(isinstance(value, bool) for value in summary["budget_gates"].values())
