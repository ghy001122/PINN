from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_tsw_dense_profile_likelihood import run_dense_profile


def test_dense_profile_config_budget() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_tsw_dense_profile_likelihood.yaml").read_text(encoding="utf-8"))
    assert int(config["grid"]["gamma_points"]) >= 41
    assert int(config["grid"]["T_sw_offset_points"]) >= 61
    assert config["source_grid_csv"] == "outputs/tables/gamma_sub_tsw_profile_likelihood_grid.csv"


def test_dense_profile_likelihood_smoke(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_tsw_dense_profile_likelihood.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["grid_csv"] = str(tmp_path / "grid.csv")
    config["profiles_csv"] = str(tmp_path / "profiles.csv")
    config["grid"]["gamma_points"] = 5
    config["grid"]["T_sw_offset_points"] = 7
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_dense_profile(path)
    assert summary["num_dense_grid_points"] == 35
    assert summary["all_finite_results"] is True
    assert np.isfinite(float(summary["condition_number"]))
    assert Path(config["summary_json"]).exists()
    saved = json.loads(Path(config["summary_json"]).read_text(encoding="utf-8"))
    assert "synthetic numerical digital-twin" in saved["note"].lower()

