from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_protocol_observability_design import run_protocol_observability_design

FROZEN_FILES = [Path("data/processed/gt_v1_acceptance/gt_triangle.npz"), Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz")]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_protocol_observability_design_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_protocol_observability_design.yaml").read_text(encoding="utf-8"))
    names = {item["name"] for item in config["protocols"]}
    assert {"triangle_low_amplitude", "triangle_high_amplitude", "short_pulse", "long_pulse", "multi_pulse", "mixed_amplitude_pulse"}.issubset(names)
    assert config["sensitivity"]["gamma_fraction"] > 0
    assert config["sensitivity"]["T_sw_delta_K"] > 0


def test_protocol_observability_design_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/gamma_sub_protocol_observability_design.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt"] = 22
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["sensitivity"]["observation_count"] = 8
    config["protocols"] = config["protocols"][:3]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_protocol_observability_design(path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    for row in summary["rows"]:
        assert np.isfinite(float(row["sensitivity_norm_gamma_sub"]))
        assert np.isfinite(float(row["sensitivity_angle_or_cosine"]))
        assert row["frozen_inputs_unchanged"] is True
