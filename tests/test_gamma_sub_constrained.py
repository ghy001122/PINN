from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from scripts.invert_gamma_sub_constrained import run_constrained_inversion


def test_gamma_sub_constrained_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_constrained_inversion.yaml").read_text(encoding="utf-8"))
    assert config["inverse"]["primary_parameter"] == "gamma_sub"
    confounders = set(config["prior_width_sweep"]["confounders"])
    assert confounders == {"T_sw", "tau_m", "sigma_on0", "eta_A"}
    assert "gamma_sub" not in confounders
    assert {"D_v0", "mu_v0"}.issubset(set(config["frozen_microphysics"]))


def test_gamma_sub_constrained_smoke(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_constrained_inversion.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["prior_width_csv"] = str(tmp_path / "prior_width.csv")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt"] = 24
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["inverse"]["gamma_candidates"] = [3.0e8, 4.5e8, 7.0e8]
    config["inverse"]["multistart_initials"] = [3.0e8, 4.5e8]
    config["noise"]["levels"] = [0.0]
    config["prior_width_sweep"]["widths"] = [0.0, 0.25]
    config["prior_width_sweep"]["confounders"] = {"T_sw": config["prior_width_sweep"]["confounders"]["T_sw"]}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    summary = run_constrained_inversion(config_path)
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["prior_width_csv"]).exists()
    for key in [
        "true_gamma_sub",
        "estimated_gamma_sub",
        "relative_error",
        "noise_level",
        "prior_width",
        "worst_confounder",
        "success_flag",
        "objective_value",
        "num_multistarts",
    ]:
        assert key in summary
    assert np.isfinite(summary["relative_error"])
    assert np.isfinite(summary["objective_value"])
    assert summary["num_multistarts"] == 2
    saved = json.loads(Path(summary["outputs"]["summary_json"]).read_text(encoding="utf-8"))
    assert saved["scope"].startswith("Constrained reduced inverse target")
