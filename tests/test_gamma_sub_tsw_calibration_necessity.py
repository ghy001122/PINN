from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_tsw_calibration_necessity import run_tsw_calibration_necessity


def test_tsw_calibration_necessity_config_cases() -> None:
    cfg = yaml.safe_load(Path("configs/gamma_sub_tsw_calibration_necessity.yaml").read_text(encoding="utf-8"))
    names = {case["case_name"] for case in cfg["cases"]}
    assert "oracle_T_sw" in names
    assert "wrong_T_sw_calibration" in names
    assert cfg["protocol"] == "ltp_ltd"


def test_tsw_calibration_necessity_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/gamma_sub_tsw_calibration_necessity.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_tsw_calibration_necessity(path)
    assert summary["whether_independent_T_sw_calibration_is_required"] is True
    assert summary["all_finite_results"] is True
    with Path(cfg["cases_csv"]).open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(cfg["cases"])
    assert all(np.isfinite(float(row["relative_error"])) for row in rows)
    saved = json.loads(Path(cfg["summary_json"]).read_text(encoding="utf-8"))
    assert "T_sw" in saved["manuscript_sentence_for_limitation"]
