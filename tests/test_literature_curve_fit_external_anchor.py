from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from scripts.fit_literature_phase_change_curves import run_curve_fit


def test_literature_curve_fit_config_boundary() -> None:
    cfg = yaml.safe_load(Path("configs/literature_curve_fit_external_anchor.yaml").read_text(encoding="utf-8"))
    assert "fabricating" in cfg["claim_boundary"]
    assert cfg["curve_data_dir"] == "data/literature/curves"


def test_literature_curve_fit_blocked_without_digitized_data(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/literature_curve_fit_external_anchor.yaml").read_text(encoding="utf-8"))
    cfg["curve_data_dir"] = str(tmp_path / "curves")
    cfg["curve_registry_csv"] = str(tmp_path / "registry.csv")
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["notes_md"] = str(tmp_path / "notes.md")
    cfg["template_readme"] = str(tmp_path / "README.md")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_curve_fit(path)
    assert summary["num_sources_found"] >= 2
    assert summary["num_curves_fit"] == 0
    assert summary["whether_external_anchor_supports_model_plausibility"] is False
    with Path(cfg["curve_registry_csv"]).open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and rows[0]["fit_status"] == "blocked_no_digitized_curve"
    saved = json.loads(Path(cfg["summary_json"]).read_text(encoding="utf-8"))
    assert "No provenance-backed" in saved["limitation"]
