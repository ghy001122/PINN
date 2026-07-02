from __future__ import annotations

from pathlib import Path

import yaml

from scripts.run_gt_quasi_2d_phase_transition_preflight import run_quasi_2d_preflight


def test_quasi_2d_gt_preflight_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/gt_quasi_2d_phase_transition_preflight.yaml").read_text(encoding="utf-8"))
    cfg["output_dir"] = str(tmp_path / "data")
    cfg["figure_dir"] = str(tmp_path / "figures")
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["grid"].update({"nx": 8, "ny": 6, "nt": 6})
    cfg["cases"] = ["uniform_strip", "localized_hotspot"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_quasi_2d_preflight(path)
    assert summary["all_fields_finite"] is True
    assert summary["all_observables_finite"] is True
    assert summary["synthetic_not_experimental"] is True
    assert summary["ready_for_residual_preflight"] is True
    assert summary["num_cases"] == 2
