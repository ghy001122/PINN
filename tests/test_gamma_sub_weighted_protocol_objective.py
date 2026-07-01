from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_protocol_actual_inversion_validation import run_protocol_actual_validation
from scripts.audit_gamma_sub_weighted_protocol_objective import run_weighted_protocol_objective


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


def test_weighted_protocol_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_weighted_protocol_objective.yaml").read_text(encoding="utf-8"))
    assert "equal_triangle_ltp" in config["combinations"]
    assert "best_actual_protocol_plus_triangle" in config["combinations"]


def test_weighted_protocol_objective_smoke(tmp_path: Path) -> None:
    protocol_summary = _protocol_summary(tmp_path)
    config = yaml.safe_load(Path("configs/gamma_sub_weighted_protocol_objective.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["protocol_actual_summary_json"] = str(protocol_summary)
    config["combinations"] = {
        "triangle_only": {"triangle": 1.0},
        "ltp_ltd_only": {"ltp_ltd": 1.0},
        "equal_triangle_ltp": {"triangle": 0.5, "ltp_ltd": 0.5},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_weighted_protocol_objective(path)
    assert summary["num_combinations"] == 3
    assert summary["all_finite_results"] is True
    assert np.isfinite(float(summary["best_weighted_case"]["relative_error"]))
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()
