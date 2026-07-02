from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from scripts.ingest_literature_digitized_curves import run_ingestion


def test_curve_ingestion_blocked_without_curves(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/literature_curve_ingestion.yaml").read_text(encoding="utf-8"))
    cfg["curve_data_dir"] = str(tmp_path / "curves")
    cfg["registry_csv"] = str(tmp_path / "registry.csv")
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["notes_md"] = str(tmp_path / "notes.md")
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_ingestion(path)
    assert summary["num_curve_files_found"] == 0
    assert summary["whether_ready_for_external_curve_fit"] is False
    assert summary["blocked_reason_if_any"]


def test_curve_ingestion_normalizes_valid_curve(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/literature_curve_ingestion.yaml").read_text(encoding="utf-8"))
    curve_dir = tmp_path / "curves"
    curve_dir.mkdir()
    cfg["curve_data_dir"] = str(curve_dir)
    cfg["registry_csv"] = str(tmp_path / "registry.csv")
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["notes_md"] = str(tmp_path / "notes.md")
    with (curve_dir / "sample.csv").open("w", newline="", encoding="utf-8") as f:
        fields = cfg["required_columns"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for x, y in [(300, 10), (320, 5), (340, 1)]:
            writer.writerow({"source_id": "sample", "source_title": "Synthetic digitized test curve", "source_year": 2026, "material_family": "test", "curve_type": "R_T", "x_raw": x, "y_raw": y, "x_unit": "K", "y_unit": "a.u.", "provenance": "unit-test provenance", "extraction_method": "unit-test", "figure_or_table_id": "Fig. X", "notes": "test"})
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_ingestion(path)
    assert summary["num_valid_curve_files"] == 1
    assert summary["num_total_points"] == 3
    assert summary["curve_types_available"] == ["R_T"]
    assert summary["normalized_rows"][0]["x_normalized"] == 0.0
