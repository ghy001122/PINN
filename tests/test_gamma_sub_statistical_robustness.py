from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_protocol_actual_inversion_validation import run_protocol_actual_validation
from scripts.audit_gamma_sub_statistical_robustness import run_statistical_robustness


def _protocol_summary(tmp_path: Path) -> Path:
    config = yaml.safe_load(Path("configs/gamma_sub_protocol_actual_inversion_validation.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "protocol_summary.json")
    config["cases_csv"] = str(tmp_path / "protocol_cases.csv")
    config["protocols"] = ["triangle_low_amplitude", "long_pulse"]
    config["scenarios"] = ["nominal_fixed_prior", "wide_T_sw_mismatch"]
    path = tmp_path / "protocol_config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    run_protocol_actual_validation(path)
    return Path(config["summary_json"])


def test_statistical_robustness_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_statistical_robustness.yaml").read_text(encoding="utf-8"))
    assert len(config["seeds"]) >= 10
    assert set(config["noise"]) == {0.0, 0.01, 0.02, 0.05}


def test_statistical_robustness_smoke(tmp_path: Path) -> None:
    protocol_summary = _protocol_summary(tmp_path)
    config = yaml.safe_load(Path("configs/gamma_sub_statistical_robustness.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["protocol_actual_summary_json"] = str(protocol_summary)
    config["protocols"] = ["triangle", "best_actual_protocol"]
    config["scenarios"] = ["nominal_fixed_prior", "wide_T_sw_mismatch"]
    config["noise"] = [0.0, 0.02]
    config["seeds"] = [2026, 2027]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_statistical_robustness(path)
    assert summary["num_cases"] == 16
    assert summary["all_finite_results"] is True
    assert np.isfinite(float(summary["overall"]["median_relative_error"]))
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()
