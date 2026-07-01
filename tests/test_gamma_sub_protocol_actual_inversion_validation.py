from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_protocol_actual_inversion_validation import run_protocol_actual_validation


def test_protocol_actual_validation_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_protocol_actual_inversion_validation.yaml").read_text(encoding="utf-8"))
    assert {"triangle_low_amplitude", "triangle_high_amplitude", "short_pulse", "long_pulse", "multi_pulse", "mixed_amplitude_pulse"}.issubset(set(config["protocols"]))
    assert config["observation_count"] == 32


def test_protocol_actual_validation_smoke(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_protocol_actual_inversion_validation.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["protocols"] = ["triangle_low_amplitude", "long_pulse"]
    config["scenarios"] = ["nominal_fixed_prior", "wide_T_sw_mismatch"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_protocol_actual_validation(path)
    assert summary["num_cases"] == 4
    assert summary["all_finite_results"] is True
    assert np.isfinite(float(summary["ranking_correlation_between_proxy_and_actual"]))
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()

