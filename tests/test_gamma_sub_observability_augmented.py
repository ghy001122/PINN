from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_observability_augmented import run_observability_augmented_audit


FROZEN_FILES = [
    Path("data/processed/gt_v1_acceptance/gt_triangle.npz"),
    Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_observability_augmented_config_scope() -> None:
    config = yaml.safe_load(Path("configs/gamma_sub_observability_augmented.yaml").read_text(encoding="utf-8"))
    assert config["inverse"]["primary_parameter"] == "gamma_sub"
    assert config["observability"]["wide_tsw_prior_width"] > config["observability"]["narrow_tsw_prior_width"]
    assert config["loss"]["w_temperature_anchor"] > 0.0
    assert "D_v0" in config["frozen_microphysics"]
    assert "mu_v0" in config["frozen_microphysics"]


def test_observability_augmented_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/gamma_sub_observability_augmented.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["report_md"] = str(tmp_path / "report.md")
    config["codex_report_md"] = str(tmp_path / "codex_report.md")
    config["simulation"]["nx"] = 7
    config["simulation"]["nt"] = 24
    config["simulation"]["rtol"] = 1.0e-4
    config["simulation"]["atol"] = 1.0e-6
    config["inverse"]["gamma_candidates"] = [3.0e8, 4.5e8, 7.0e8]
    config["observability"]["temperature_anchor_counts"] = [2, 4]
    config["observability"]["wide_tsw_prior_width"] = 1.0
    config["observability"]["narrow_tsw_prior_width"] = 0.1
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    summary = run_observability_augmented_audit(config_path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert Path(summary["outputs"]["report_md"]).exists()
    assert Path(summary["outputs"]["codex_report_md"]).exists()
    assert summary["num_cases"] >= 6

    modes = {row["observation_mode"] for row in summary["rows"]}
    assert "port_only" in modes
    assert "port_plus_temperature_anchor" in modes
    assert "port_plus_tsw_prior" in modes
    assert "port_plus_temperature_anchor_and_tsw_prior" in modes

    for row in summary["rows"]:
        for key in ["gamma_est", "gamma_relative_error", "objective_value"]:
            assert np.isfinite(float(row[key]))
        assert row["finite_result"] is True
        assert row["frozen_inputs_unchanged"] is True
        assert row["interpretation"]

    saved = json.loads(Path(summary["outputs"]["summary_json"]).read_text(encoding="utf-8"))
    assert saved["scope"].startswith("Only gamma_sub is estimated")
    assert saved["frozen_gt_hashes_before"] == saved["frozen_gt_hashes_after"]
    assert "synthetic numerical" in saved["note"].lower()