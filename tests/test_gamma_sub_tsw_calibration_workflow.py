from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.audit_gamma_sub_tsw_calibration_workflow import run_tsw_calibration_workflow


def test_tsw_calibration_workflow_improves_recovery() -> None:
    summary = run_tsw_calibration_workflow(Path("configs/gamma_sub_tsw_calibration_workflow.yaml"))
    rows = {row["workflow"]: row for row in summary["rows"]}
    assert summary["all_finite_results"] is True
    assert summary["whether_calibration_before_inversion_improves_recovery"] is True
    assert rows["synthetic_probe_calibrated_T_sw"]["relative_error"] < rows["no_calibration_direct_gamma"]["relative_error"]
    assert rows["wrong_calibration_control"]["relative_error"] > rows["synthetic_probe_calibrated_T_sw"]["relative_error"]
    assert summary["minimum_calibration_accuracy_needed"] is not None


def test_tsw_calibration_summary_schema() -> None:
    path = Path("outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json")
    assert path.exists()
    summary = json.loads(path.read_text(encoding="utf-8"))
    for key in [
        "best_workflow",
        "improvement_over_no_calibration",
        "minimum_calibration_accuracy_needed",
        "manuscript_method_sentence",
    ]:
        assert key in summary
    assert "synthetic" in summary["note"].lower()
