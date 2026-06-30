from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_temperature_anchor_placement import run_temperature_anchor_placement_audit

FROZEN_FILES = [Path("data/processed/gt_v1_acceptance/gt_triangle.npz"), Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz")]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_temperature_anchor_placement_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_temperature_anchor_placement.yaml").read_text(encoding="utf-8"))
    assert config["inverse"]["primary_parameter"] == "gamma_sub"
    assert config["placement"]["n_temperature_anchors"] > 0
    assert len(config["placement"]["random_seeds"]) >= 2


def test_temperature_anchor_placement_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/gamma_sub_temperature_anchor_placement.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["report_md"] = str(tmp_path / "report.md")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt"] = 24
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["inverse"]["gamma_candidates"] = [3.0e8, 4.5e8, 7.0e8]
    config["placement"]["n_temperature_anchors"] = 4
    config["placement"]["random_seeds"] = [2026, 2027]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_temperature_anchor_placement_audit(path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    modes = {row["placement_mode"] for row in summary["rows"]}
    assert {"none", "uniform", "random", "high_gradient"}.issubset(modes)
    for row in summary["rows"]:
        assert np.isfinite(float(row["gamma_relative_error"]))
        assert row["frozen_inputs_unchanged"] is True
    saved = json.loads(Path(summary["outputs"]["summary_json"]).read_text(encoding="utf-8"))
    assert saved["scope"].startswith("Only gamma_sub")