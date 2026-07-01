from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_recoverability_phase_diagram import run_recoverability_phase_diagram


def test_recoverability_phase_diagram_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_recoverability_phase_diagram.yaml").read_text(encoding="utf-8"))
    assert set(config["sweep"]["protocols"]) == {"triangle", "ltp_ltd", "multi_amplitude_synthetic", "mixed_protocol"}
    assert config["sweep"]["observation_count"] == [8, 16, 32, 64]
    assert config["sweep"]["noise"] == [0.0, 0.01, 0.02, 0.05]


def test_recoverability_phase_diagram_smoke(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_recoverability_phase_diagram.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["sweep"]["protocols"] = ["triangle", "ltp_ltd"]
    config["sweep"]["T_sw_delta_K"] = [0.0, 2.0]
    config["sweep"]["T_sw_prior_width"] = [0.1, 1.0]
    config["sweep"]["observation_count"] = [8]
    config["sweep"]["noise"] = [0.0, 0.02]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_recoverability_phase_diagram(path)
    assert summary["num_cases"] == 16
    assert summary["all_finite_results"] is True
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()
    for protocol, stats in summary["by_protocol"].items():
        assert protocol in {"triangle", "ltp_ltd"}
        assert np.isfinite(float(stats["mean_relative_error"]))
    saved = json.loads(Path(config["summary_json"]).read_text(encoding="utf-8"))
    assert "conditional gamma_sub" in saved["manuscript_boundary"]

