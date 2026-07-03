from __future__ import annotations

import math
from pathlib import Path

import yaml

from scripts.audit_reduced_2d_phase_transition_forward import run_forward_benchmark


def test_reduced_2d_forward_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/reduced_2d_phase_transition_forward.yaml").read_text(encoding="utf-8"))
    cfg["nx"] = 12
    cfg["ny"] = 8
    cfg["nt"] = 10
    cfg["geometries"] = ["uniform_strip", "localized_hotspot"]
    cfg["transition_width"] = [0.1]
    cfg["lateral_coupling"] = [0.0, 0.5]
    cfg["seeds"] = [2026]
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["snapshot_figure"] = str(tmp_path / "snapshots.png")
    cfg["port_figure"] = str(tmp_path / "ports.png")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_forward_benchmark(path)
    assert summary["num_cases"] == 4
    assert summary["all_fields_finite"] is True
    assert summary["all_residuals_finite"] is True
    assert isinstance(summary["geometry_effect_detected"], bool)
    assert isinstance(summary["whether_reduced_2d_forward_supported"], bool)
    assert math.isfinite(summary["geometry_effect_range"])
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert "full 2D inverse recovery" in summary["forbidden_overclaim"]
