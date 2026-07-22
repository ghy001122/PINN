from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from scripts.fit_literature_phase_change_curves_v2 import run_curve_fit_v2
from scripts.ingest_literature_digitized_curves import run_ingestion


def test_curve_fit_v2_blocked_official_config(tmp_path: Path) -> None:
    # Official repository state currently has no provenance-backed digitized curves.
    ingest_cfg = yaml.safe_load(
        Path("configs/literature_curve_ingestion.yaml").read_text(encoding="utf-8")
    )
    ingest_cfg.update(
        {
            "curve_data_dir": str(tmp_path / "curves"),
            "registry_csv": str(tmp_path / "registry.csv"),
            "summary_json": str(tmp_path / "ingest.json"),
            "cases_csv": str(tmp_path / "ingest_cases.csv"),
            "notes_md": str(tmp_path / "notes.md"),
        }
    )
    ingest_path = tmp_path / "ingest.yaml"
    ingest_path.write_text(yaml.safe_dump(ingest_cfg, sort_keys=False), encoding="utf-8")
    run_ingestion(ingest_path)
    fit_cfg = yaml.safe_load(
        Path("configs/literature_curve_fit_external_anchor_v2.yaml").read_text(
            encoding="utf-8"
        )
    )
    fit_cfg.update(
        {
            "ingestion_summary_json": str(tmp_path / "ingest.json"),
            "ingestion_cases_csv": str(tmp_path / "ingest_cases.csv"),
            "summary_json": str(tmp_path / "fit.json"),
            "cases_csv": str(tmp_path / "fit_cases.csv"),
            "overlay_png": str(tmp_path / "fit.png"),
        }
    )
    fit_path = tmp_path / "fit.yaml"
    fit_path.write_text(yaml.safe_dump(fit_cfg, sort_keys=False), encoding="utf-8")
    summary = run_curve_fit_v2(fit_path)
    assert summary["num_curves_fit"] == 0
    assert summary["whether_literature_curves_support_model_plausibility"] is False
    assert "blocked" in summary["limitation"]


def test_curve_fit_v2_fits_sample_curve(tmp_path: Path) -> None:
    ingest_cfg = yaml.safe_load(Path("configs/literature_curve_ingestion.yaml").read_text(encoding="utf-8"))
    curve_dir = tmp_path / "curves"
    curve_dir.mkdir()
    ingest_cfg.update({"curve_data_dir": str(curve_dir), "registry_csv": str(tmp_path / "registry.csv"), "summary_json": str(tmp_path / "ingest.json"), "cases_csv": str(tmp_path / "ingest_cases.csv"), "notes_md": str(tmp_path / "notes.md")})
    fields = ingest_cfg["required_columns"] + ["x_normalized", "y_normalized"]
    with (curve_dir / "sample.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for x, y in [(0, 0.02), (0.5, 0.5), (1, 0.98)]:
            writer.writerow({"source_id": "sample", "source_title": "Sample", "source_year": 2026, "material_family": "test", "curve_type": "sigma_T", "x_raw": x, "y_raw": y, "x_unit": "norm", "y_unit": "norm", "x_normalized": x, "y_normalized": y, "provenance": "unit-test", "extraction_method": "unit-test", "figure_or_table_id": "Fig", "notes": "test"})
    ingest_path = tmp_path / "ingest.yaml"
    ingest_path.write_text(yaml.safe_dump(ingest_cfg, sort_keys=False), encoding="utf-8")
    run_ingestion(ingest_path)
    fit_cfg = yaml.safe_load(Path("configs/literature_curve_fit_external_anchor_v2.yaml").read_text(encoding="utf-8"))
    fit_cfg.update({"ingestion_summary_json": str(tmp_path / "ingest.json"), "ingestion_cases_csv": str(tmp_path / "ingest_cases.csv"), "summary_json": str(tmp_path / "fit.json"), "cases_csv": str(tmp_path / "fit_cases.csv"), "overlay_png": str(tmp_path / "fit.png")})
    fit_path = tmp_path / "fit.yaml"
    fit_path.write_text(yaml.safe_dump(fit_cfg, sort_keys=False), encoding="utf-8")
    summary = run_curve_fit_v2(fit_path)
    assert summary["num_curves_fit"] == 1
    assert summary["whether_literature_curves_support_model_plausibility"] is True
    assert Path(fit_cfg["overlay_png"]).exists()
