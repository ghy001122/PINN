from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml


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


def test_v2_smoke_config_can_load() -> None:
    path = Path("configs/pinn_inverse_v2_f_sps_smoke.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert config["train_data"] == "data/processed/gt_v1_acceptance/gt_triangle.npz"
    assert config["sparse_obs"] == "data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"
    assert config["epochs"] <= 5
    assert config["loss_weights"]["w_dynamic_gate"] == 0.0
    assert config["loss_weights"]["w_frequency"] == 0.0
    assert config["vo2_params"]["mixing_mode"] == "linear"


def test_v2_smoke_script_runs_and_preserves_frozen_inputs(tmp_path: Path) -> None:
    before_hash = {str(path): _sha256(path) for path in FROZEN_FILES}
    before_mtime = {str(path): path.stat().st_mtime_ns for path in FROZEN_FILES}
    output_dir = tmp_path / "f_sps_smoke"
    summary_path = tmp_path / "summary.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_pinn_inverse_v2_smoke.py",
            "--config",
            "configs/pinn_inverse_v2_f_sps_smoke.yaml",
            "--epochs",
            "2",
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
        ],
        cwd=Path.cwd(),
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert "used_vo2_sigma" in result.stdout
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    after_hash = {str(path): _sha256(path) for path in FROZEN_FILES}
    after_mtime = {str(path): path.stat().st_mtime_ns for path in FROZEN_FILES}

    assert before_hash == after_hash
    assert before_mtime == after_mtime
    assert summary["frozen_inputs_unchanged"] is True
    assert summary["used_vo2_sigma"] is True
    assert summary["used_free_log_sigma"] is False
    assert summary["epochs"] == 2
    assert summary["finite_loss"] is True
    assert np.isfinite(float(summary["initial_loss"]))
    assert np.isfinite(float(summary["final_loss"]))
    assert np.isfinite(float(summary["sigma_min"]))
    assert np.isfinite(float(summary["sigma_max"]))
    assert float(summary["sigma_min"]) > 0.0
    assert float(summary["sigma_max"]) >= float(summary["sigma_min"])