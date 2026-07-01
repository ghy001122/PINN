from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_response_surface_anchor_verification import run_anchor_verification


def test_anchor_verification_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_response_surface_anchor_verification.yaml").read_text(encoding="utf-8"))
    assert int(config["num_anchor_cases"]) >= 60
    assert config["profile_source_csv"] == "outputs/tables/gamma_sub_tsw_profile_likelihood_grid.csv"
    assert "not convert every dense-grid point" in config["claim_boundary"]


def test_anchor_verification_smoke(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_response_surface_anchor_verification.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["num_anchor_cases"] = 12
    config["sampling"] = {
        "objective_minimum": 2,
        "ridge_valley": 2,
        "recoverability_boundary": 2,
        "wide_T_sw_mismatch_failure_zone": 2,
        "high_confidence_recoverable_zone": 2,
        "random_control_zone": 2,
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_anchor_verification(path)
    assert summary["num_anchor_cases"] == 12
    assert np.isfinite(float(summary["mean_absolute_discrepancy"]))
    assert 0.0 <= float(summary["classification_agreement_rate"]) <= 1.0
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()
    saved = json.loads(Path(config["summary_json"]).read_text(encoding="utf-8"))
    assert "Synthetic numerical digital-twin" in saved["note"]

