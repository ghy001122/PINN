from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from scripts.audit_literature_phase_change_parameter_sanity import FIELDS, run_parameter_sanity


def test_literature_parameter_sanity_config() -> None:
    cfg = yaml.safe_load(Path("configs/literature_phase_change_parameter_sanity.yaml").read_text(encoding="utf-8"))
    assert "synthetic" in cfg["claim_boundary"].lower()
    assert cfg["parameter_table_csv"].startswith("data/literature/")


def test_literature_parameter_sanity_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/literature_phase_change_parameter_sanity.yaml").read_text(encoding="utf-8"))
    cfg["parameter_table_csv"] = str(tmp_path / "table.csv")
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["notes_md"] = str(tmp_path / "notes.md")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_parameter_sanity(path)
    assert summary["num_parameters_checked"] >= 7
    assert "synthetic" in summary["note"].lower()
    with Path(cfg["parameter_table_csv"]).open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert set(FIELDS).issubset(rows[0].keys())
    saved = json.loads(Path(cfg["summary_json"]).read_text(encoding="utf-8"))
    assert saved["dominant_open_risk"].startswith("T_sw")
