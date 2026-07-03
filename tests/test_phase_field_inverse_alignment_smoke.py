from __future__ import annotations

import math
from pathlib import Path

import yaml

from scripts.audit_phase_field_inverse_alignment_smoke import run_phase_field_alignment


def test_phase_field_inverse_alignment_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/phase_field_inverse_alignment_smoke.yaml").read_text(encoding="utf-8"))
    cfg["grid"].update({"nx": 16, "ny": 16, "nt": 10, "dt": 0.025})
    cfg["M_true"] = [0.5, 1.0]
    cfg["noise"] = [0.0, 0.01]
    cfg["seeds"] = [2026]
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_phase_field_alignment(path)
    assert summary["all_finite_results"] is True
    assert summary["num_cases"] == 4
    assert math.isfinite(summary["median_relative_error_M"])
    assert "0.0" in summary["noise_sensitivity"]
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert "phase-field smoke is a main-text core experiment" in summary["forbidden_claims"]
