from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_tsw_calibration_tolerance_sweep import run_tolerance_sweep


def test_tolerance_sweep_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/gamma_sub_tsw_calibration_tolerance_sweep.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["calibration_error_K"] = [0.0, 0.1, 0.2]
    cfg["T_sw_prior_width_after_calibration"] = [0.0, 0.05, 0.1]
    cfg["noise"] = [0.0]
    cfg["seeds"] = [2026]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_tolerance_sweep(path)
    assert summary["all_finite_results"] is True
    assert summary["maximum_tolerable_calibration_error_for_le_0p15"] is not None
    assert summary["maximum_tolerable_prior_width_for_le_0p15"] is not None
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()


def test_tolerance_sweep_official_summary_schema() -> None:
    summary = json.loads(Path("outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json").read_text(encoding="utf-8"))
    for key in ["success_rate_by_error_bin", "median_error_by_error_bin", "calibrated_protocol_advantage", "manuscript_sentence_for_calibration_requirement"]:
        assert key in summary
    assert bool(np.isfinite(float(summary["calibrated_protocol_advantage"])))
