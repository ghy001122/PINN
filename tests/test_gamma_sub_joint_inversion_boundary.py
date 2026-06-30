from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_joint_inversion_boundary import run_joint_inversion_boundary

FROZEN_FILES = [Path("data/processed/gt_v1_acceptance/gt_triangle.npz"), Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz")]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_joint_inversion_boundary_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_joint_inversion_boundary.yaml").read_text(encoding="utf-8"))
    assert config["inverse"]["primary_parameter"] == "gamma_sub"
    assert "gamma_plus_T_sw" in config["cases"]
    assert "gamma_plus_T_sw_plus_tau_m" in config["cases"]


def test_joint_inversion_boundary_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/gamma_sub_joint_inversion_boundary.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt"] = 22
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["inverse"]["gamma_candidates"] = [3.0e8, 4.5e8, 7.0e8]
    config["inverse"]["observation_count"] = 8
    config["released_parameter_grids"]["T_sw_offset_K"] = [-1.0, 0.0, 1.0]
    config["released_parameter_grids"]["tau_m_scale"] = [0.8, 1.0, 1.2]
    config["cases"] = ["gamma_only", "gamma_plus_T_sw", "gamma_plus_T_sw_plus_tau_m"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_joint_inversion_boundary(path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    for row in summary["rows"]:
        assert np.isfinite(float(row["relative_error"]))
        assert np.isfinite(float(row["ambiguity_score"]))
        assert row["frozen_inputs_unchanged"] is True
