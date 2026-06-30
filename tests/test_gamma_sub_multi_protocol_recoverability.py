from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_multi_protocol_recoverability import run_multi_protocol_recoverability

FROZEN_FILES = [
    Path("data/processed/gt_v1_acceptance/gt_triangle.npz"),
    Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"),
    Path("data/processed/gt_v1_acceptance/gt_ltp_ltd.npz"),
    Path("data/processed/gt_v1_acceptance/obs_ltp_ltd_sparse.npz"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_multi_protocol_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_multi_protocol_recoverability.yaml").read_text(encoding="utf-8"))
    assert config["inverse"]["primary_parameter"] == "gamma_sub"
    assert {"triangle", "ltp_ltd", "multi_amplitude_synthetic", "mixed_protocol"}.issubset(set(config["sweep"]["protocols"]))
    assert config["sweep"]["observation_counts"] == [8, 32]
    assert config["sweep"]["noise_levels"] == [0.0, 0.02]


def test_multi_protocol_recoverability_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/gamma_sub_multi_protocol_recoverability.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["report_md"] = str(tmp_path / "report.md")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt_triangle"] = 22
    config["simulation"]["nt_ltp_ltd"] = 24
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["inverse"]["gamma_candidates"] = [3.0e8, 4.5e8, 7.0e8]
    config["sweep"]["protocols"] = ["triangle", "ltp_ltd", "mixed_protocol"]
    config["sweep"]["observation_counts"] = [8]
    config["sweep"]["noise_levels"] = [0.0]
    config["sweep"]["scenarios"] = [config["sweep"]["scenarios"][0], config["sweep"]["scenarios"][1]]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_multi_protocol_recoverability(path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert {"triangle", "ltp_ltd", "mixed_protocol"}.issubset({row["protocol"] for row in summary["rows"]})
    for row in summary["rows"]:
        assert np.isfinite(float(row["relative_error"]))
        assert np.isfinite(float(row["objective"]))
        assert row["frozen_inputs_unchanged"] is True
    saved = json.loads(Path(summary["outputs"]["summary_json"]).read_text(encoding="utf-8"))
    assert saved["claim_boundary"].startswith("Supports synthetic")
