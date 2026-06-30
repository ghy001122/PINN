from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_tsw_profile_likelihood import run_tsw_profile_likelihood

FROZEN_FILES = [Path("data/processed/gt_v1_acceptance/gt_triangle.npz"), Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz")]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_tsw_profile_likelihood_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_tsw_profile_likelihood.yaml").read_text(encoding="utf-8"))
    assert config["inverse"]["primary_parameter"] == "gamma_sub"
    gamma_grid = [float(value) for value in config["inverse"]["gamma_grid"]]
    assert min(gamma_grid) <= 3.0e8
    assert max(gamma_grid) >= 1.0e9
    assert min(config["inverse"]["T_sw_offset_grid_K"]) <= -2.0
    assert max(config["inverse"]["T_sw_offset_grid_K"]) >= 2.0


def test_tsw_profile_likelihood_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/gamma_sub_tsw_profile_likelihood.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["grid_csv"] = str(tmp_path / "grid.csv")
    config["profiles_csv"] = str(tmp_path / "profiles.csv")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt"] = 22
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["inverse"]["gamma_grid"] = [3.0e8, 4.5e8, 7.0e8]
    config["inverse"]["T_sw_offset_grid_K"] = [-1.0, 0.0, 1.0]
    config["inverse"]["observation_count"] = 8
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_tsw_profile_likelihood(path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["grid_csv"]).exists()
    assert Path(summary["outputs"]["profiles_csv"]).exists()
    assert np.isfinite(float(summary["condition_number"]))
    assert "gamma_sub_T_sw_coupling_coefficient" in summary["ridge_metrics"]

