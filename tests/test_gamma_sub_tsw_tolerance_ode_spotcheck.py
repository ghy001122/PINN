from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_tsw_tolerance_ode_spotcheck import run_ode_spotcheck


def test_ode_spotcheck_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/gamma_sub_tsw_tolerance_ode_spotcheck.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["calibration_error_K"] = [0.1]
    cfg["T_sw_prior_width_after_calibration"] = [0.05]
    cfg["noise"] = [0.0]
    cfg["seeds"] = [2026]
    cfg["protocols"] = cfg["protocols"][:1]
    cfg["inverse"]["gamma_candidates"] = [4.25e8, 4.5e8, 5.0e8]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_ode_spotcheck(path)
    assert summary["num_ode_backed_cases"] == 1
    assert summary["all_cases_simulator_backed"] is True
    assert summary["all_finite_results"] is True
    assert summary["frozen_gt_unchanged"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()


def test_ode_spotcheck_summary_schema_if_generated() -> None:
    path = Path("outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json")
    if not path.exists():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    for key in ["num_ode_backed_cases", "median_error_by_calibration_error", "whether_0p1K_threshold_supported_by_ode_spotcheck"]:
        assert key in summary
    assert bool(np.isfinite(float(summary["num_ode_backed_cases"])))
