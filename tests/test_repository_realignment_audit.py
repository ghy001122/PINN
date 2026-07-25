from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_repository_realignment",
    ROOT / "scripts" / "audit_repository_realignment.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_disposition_vocabulary_and_frozen_precedence() -> None:
    assert MODULE.ALLOWED_DISPOSITIONS == {
        "KEEP_CURRENT",
        "KEEP_EVERGREEN",
        "UPDATE",
        "MERGE",
        "ARCHIVE",
        "DELETE_DUPLICATE",
        "DELETE_GENERATED",
        "LEAVE_IN_PLACE_FROZEN",
        "REVIEW_BLOCKED",
    }
    disposition, _ = MODULE.disposition_for(
        "configs/gt_v1_acceptance_triangle.yaml",
        {"configs/gt_v1_acceptance_triangle.yaml": "M"},
    )
    assert disposition == "LEAVE_IN_PLACE_FROZEN"


def test_archive_and_canonical_guide_classification() -> None:
    archived, _ = MODULE.disposition_for(
        "docs/archive/superseded_strategy/example.md",
        {"docs/archive/superseded_strategy/example.md": "A"},
    )
    guide, _ = MODULE.disposition_for(
        "docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md",
        {"docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md": "A"},
    )
    assert archived == "ARCHIVE"
    assert guide == "MERGE"


def test_generated_inventory_schema_and_coverage() -> None:
    path = ROOT / "outputs" / "tables" / "repository_file_disposition.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 1000
    assert set(MODULE.CSV_FIELDS) <= set(rows[0])
    assert {row["disposition"] for row in rows} <= MODULE.ALLOWED_DISPOSITIONS
    assert not [
        row for row in rows
        if row["frozen_evidence"] == "yes"
        and row["disposition"] != "LEAVE_IN_PLACE_FROZEN"
    ]
    assert {
        "outputs/tables/repository_file_disposition.csv",
        "outputs/tables/repository_realign_phase0_summary.json",
    } <= {row["path"] for row in rows}


def test_generated_summary_has_no_unrecorded_deletion() -> None:
    path = ROOT / "outputs" / "tables" / "repository_realign_phase0_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["task_id"] == "Q2_REPOSITORY_REALIGNMENT_AND_PHASE0_GOVERNANCE"
    assert summary["inventory"]["row_count"] >= 1000
    assert summary["inventory"]["deleted_file_count"] == 0
    assert summary["frozen_gt_modified"] is False
    assert summary["scientific_experiment_executed"] is False
