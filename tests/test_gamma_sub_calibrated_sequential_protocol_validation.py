from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_calibrated_sequential_protocol_validation import run_calibrated_sequential_validation


def _small_config(tmp_path: Path) -> Path:
    cfg = yaml.safe_load(Path("configs/gamma_sub_calibrated_sequential_protocol_validation.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["simulation"].update({"nx": 5, "nt": 20, "rtol": 1.0e-3, "atol": 1.0e-5})
    cfg["inverse"]["gamma_candidates"] = [4.5e8, 5.0e8]
    cfg["noise_levels"] = [0.0]
    cfg["seeds"] = [2026]
    cfg["observation_count"] = 8
    cfg["scenarios"] = [{"scenario": "narrow_T_sw_prior", "T_sw_delta_K": 2.0, "T_sw_prior_width": 0.1}]
    keep = {"no_calibration_ltp_ltd_only", "calibrated_multi_pulse_to_ltp_ltd", "wrong_calibration_multi_pulse_to_ltp_ltd"}
    cfg["protocol_candidates"] = [item for item in cfg["protocol_candidates"] if item["candidate_name"] in keep]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def test_calibrated_sequential_validation_smoke(tmp_path: Path) -> None:
    summary = run_calibrated_sequential_validation(_small_config(tmp_path))
    assert summary["all_cases_simulator_backed"] is True
    assert summary["all_finite_results"] is True
    assert summary["frozen_gt_unchanged"] is True
    assert summary["num_simulator_backed_cases"] == 3
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()


def test_calibrated_sequential_official_summary_schema() -> None:
    path = Path("outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json")
    assert path.exists()
    summary = json.loads(path.read_text(encoding="utf-8"))
    for key in [
        "best_calibrated_protocol",
        "success_rate_by_protocol",
        "median_error_by_protocol",
        "success_rate_gain_over_uncalibrated",
        "wrong_calibration_success_rate_drop",
    ]:
        assert key in summary
    assert summary["frozen_gt_unchanged"] is True
    numeric = [summary["improvement_over_uncalibrated"], summary["degradation_under_wrong_calibration"]]
    assert bool(np.isfinite(numeric).all())
