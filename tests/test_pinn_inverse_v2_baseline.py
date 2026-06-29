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


def test_v2_baseline_config_can_load() -> None:
    path = Path("configs/pinn_inverse_v2_f_sps_baseline.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert config["train_data"] == "data/processed/gt_v1_acceptance/gt_triangle.npz"
    assert config["sparse_obs"] == "data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"
    assert config["epochs"] <= 20
    assert config["loss_weights"]["w_dynamic_gate"] == 0.0
    assert config["loss_weights"]["w_frequency"] == 0.0
    modes = {run["conductivity_mode"] for run in config["runs"]}
    assert modes == {"free_log_sigma", "white_box_vo2_sigma"}


def test_v2_baseline_script_runs_and_preserves_frozen_inputs(tmp_path: Path) -> None:
    before_hash = {str(path): _sha256(path) for path in FROZEN_FILES}
    before_mtime = {str(path): path.stat().st_mtime_ns for path in FROZEN_FILES}
    output_root = tmp_path / "baseline_outputs"
    summary_path = tmp_path / "baseline_summary.json"
    runs_csv = tmp_path / "baseline_runs.csv"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_pinn_inverse_v2_baseline.py",
            "--config",
            "configs/pinn_inverse_v2_f_sps_baseline.yaml",
            "--epochs",
            "2",
            "--output-root",
            str(output_root),
            "--summary",
            str(summary_path),
            "--runs-csv",
            str(runs_csv),
        ],
        cwd=Path.cwd(),
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert "frozen_inputs_unchanged" in result.stdout
    assert summary_path.exists()
    assert runs_csv.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    after_hash = {str(path): _sha256(path) for path in FROZEN_FILES}
    after_mtime = {str(path): path.stat().st_mtime_ns for path in FROZEN_FILES}

    assert before_hash == after_hash
    assert before_mtime == after_mtime
    assert summary["frozen_inputs_unchanged"] is True
    assert summary["num_runs"] == 2
    rows = {row["run_name"]: row for row in summary["runs"]}
    assert set(rows) == {"free_log_sigma", "white_box_vo2_sigma"}
    assert rows["free_log_sigma"]["used_free_log_sigma"] is True
    assert rows["free_log_sigma"]["used_vo2_sigma"] is False
    assert rows["white_box_vo2_sigma"]["used_vo2_sigma"] is True
    assert rows["white_box_vo2_sigma"]["used_free_log_sigma"] is False
    required = [
        "initial_loss",
        "final_loss",
        "relative_G_error",
        "relative_I_error",
        "nrmse_delta_T",
        "nrmse_c_v",
        "nrmse_m",
        "nrmse_sigma",
        "sigma_min",
        "sigma_max",
    ]
    for row in rows.values():
        assert row["epochs"] == 2
        assert row["finite_loss"] is True
        for key in required:
            assert np.isfinite(float(row[key]))
        assert float(row["sigma_min"]) > 0.0
        assert float(row["sigma_max"]) >= float(row["sigma_min"])
