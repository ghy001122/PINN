from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_calibrated_protocol_robustness_final import run_robustness_final


def _small_config(tmp_path: Path) -> Path:
    cfg = yaml.safe_load(Path("configs/gamma_sub_calibrated_protocol_robustness_final.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["simulation"].update({"nx": 5, "nt": 18, "rtol": 1.0e-3, "atol": 1.0e-5})
    cfg["inverse"]["gamma_candidates"] = [4.5e8, 5.0e8]
    cfg["noise"] = [0.0]
    cfg["observation_count"] = [8]
    cfg["seeds"] = [2026]
    cfg["T_sw_delta_K"] = [0.4]
    keep = {"no_calibration_ltp_ltd_only", "calibrated_multi_pulse_to_ltp_ltd", "wrong_calibration_multi_pulse_to_ltp_ltd"}
    cfg["protocol_candidates"] = [item for item in cfg["protocol_candidates"] if item["candidate_name"] in keep]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def test_robustness_final_smoke(tmp_path: Path) -> None:
    summary = run_robustness_final(_small_config(tmp_path))
    assert summary["all_cases_simulator_backed"] is True
    assert summary["all_finite_results"] is True
    assert summary["frozen_gt_unchanged"] is True
    assert summary["num_simulator_backed_cases"] == 3


def test_robustness_final_official_summary_schema() -> None:
    summary = json.loads(Path("outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json").read_text(encoding="utf-8"))
    for key in ["success_rate_by_protocol", "median_error_by_protocol", "IQR_error_by_protocol", "worst_case_by_protocol", "whether_ready_as_main_figure"]:
        assert key in summary
    assert summary["all_cases_simulator_backed"] is True
    assert bool(np.isfinite(float(summary["wrong_calibration_penalty"])))
