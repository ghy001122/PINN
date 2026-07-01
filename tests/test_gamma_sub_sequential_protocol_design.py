from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_sequential_protocol_design import run_sequential_protocol_design


def test_sequential_protocol_design_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_sequential_protocol_design.yaml").read_text(encoding="utf-8"))
    names = {row["name"] for row in config["candidates"]}
    assert "short_pulse_to_ltp_ltd" in names
    assert "ltp_ltd_only" in names
    assert config["observation_count"] == 32


def test_sequential_protocol_design_smoke(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_sequential_protocol_design.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_sequential_protocol_design(path)
    assert summary["num_candidates"] == len(config["candidates"])
    assert summary["best_candidate_by_gamma_error"] is not None
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()
    for row in summary["best_candidate_by_gamma_error"], summary["best_candidate_by_cost_normalized_score"]:
        assert np.isfinite(float(row["stage2_gamma_error"]))
    saved = json.loads(Path(config["summary_json"]).read_text(encoding="utf-8"))
    assert "synthetic numerical digital-twin" in saved["note"].lower()

