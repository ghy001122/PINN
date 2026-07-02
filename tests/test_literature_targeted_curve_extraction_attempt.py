from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from scripts.attempt_literature_curve_extraction_from_sources import run_extraction_attempt


def test_targeted_extraction_blocks_pdf_only(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/literature_targeted_curve_extraction_attempt.yaml").read_text(encoding="utf-8"))
    cfg.update({
        "search_roots": [str(tmp_path / "missing")],
        "summary_json": str(tmp_path / "summary.json"),
        "cases_csv": str(tmp_path / "cases.csv"),
        "manual_queue_csv": str(tmp_path / "queue.csv"),
        "protocol_md": str(tmp_path / "protocol.md"),
        "drive_candidates": [{"title": "VO2 R(T) hysteresis PDF", "mime_type": "application/pdf", "url": "https://example.invalid/file.pdf"}],
    })
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_extraction_attempt(path)
    assert summary["num_valid_digitized_curve_tables"] == 0
    assert summary["blocked_reason_if_any"] == "no_provenance_backed_digitized_curve_tables_found"
    assert Path(cfg["manual_queue_csv"]).exists()


def test_targeted_extraction_accepts_required_csv(tmp_path: Path) -> None:
    root = tmp_path / "lit"
    root.mkdir()
    fields = ["source_id", "source_title", "source_year", "material_family", "curve_type", "x_raw", "y_raw", "x_unit", "y_unit", "provenance", "extraction_method", "figure_or_table_id", "notes"]
    with (root / "curve.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"source_id": "s", "source_title": "t", "source_year": 2026, "material_family": "VO2", "curve_type": "R(T)", "x_raw": 1, "y_raw": 2, "x_unit": "K", "y_unit": "ohm", "provenance": "unit", "extraction_method": "table", "figure_or_table_id": "T1", "notes": "n"})
    cfg = yaml.safe_load(Path("configs/literature_targeted_curve_extraction_attempt.yaml").read_text(encoding="utf-8"))
    cfg.update({"search_roots": [str(root)], "summary_json": str(tmp_path / "summary.json"), "cases_csv": str(tmp_path / "cases.csv"), "manual_queue_csv": str(tmp_path / "queue.csv"), "protocol_md": str(tmp_path / "protocol.md"), "drive_candidates": []})
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_extraction_attempt(path)
    assert summary["num_valid_digitized_curve_tables"] == 1
    assert summary["num_accepted_points"] == 1
    assert summary["whether_ready_for_literature_curve_ingestion_rerun"] is True


def test_targeted_extraction_official_summary_schema() -> None:
    summary = json.loads(Path("outputs/tables/literature_targeted_curve_extraction_attempt_summary.json").read_text(encoding="utf-8"))
    for key in ["num_sources_scanned", "num_manual_digitization_queue_items", "status_counts", "blocked_reason_if_any"]:
        assert key in summary
    assert summary["num_valid_digitized_curve_tables"] == 0
