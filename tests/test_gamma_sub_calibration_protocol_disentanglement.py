from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_calibration_protocol_disentanglement import run_disentanglement


def test_disentanglement_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/gamma_sub_calibration_protocol_disentanglement.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["T_sw_prior_width_after_calibration"] = [1.0, 0.02]
    cfg["calibration_error_K"] = [0.04, 0.4]
    cfg["noise"] = [0.0]
    cfg["seeds"] = [2026]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_disentanglement(path)
    assert summary["all_finite_results"] is True
    assert summary["best_protocol_under_equal_prior"] in {"ltp_ltd_only", "short_pulse_to_ltp_ltd", "multi_pulse_to_ltp_ltd"}
    assert "manuscript_claim_update" in summary


def test_disentanglement_official_summary_schema() -> None:
    summary = json.loads(Path("outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json").read_text(encoding="utf-8"))
    for key in ["total_gain", "calibration_gain", "protocol_gain", "interaction_gain", "whether_protocol_advantage_survives_equal_prior_control"]:
        assert key in summary
        if key.endswith("gain"):
            assert bool(np.isfinite(float(summary[key])))
    assert summary["whether_previous_protocol_claim_needs_qualification"] is True
