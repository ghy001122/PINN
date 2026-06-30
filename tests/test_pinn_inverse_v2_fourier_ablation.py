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


def test_fourier_ablation_config_can_load() -> None:
    path = Path("configs/pinn_inverse_v2_fourier_ablation.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert config["train_data"] == "data/processed/gt_v1_acceptance/gt_triangle.npz"
    assert config["sparse_obs"] == "data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"
    assert config["epochs"] <= 50
    assert config["stress_case"] == "sharp_transition"
    assert config["loss_weights"]["w_dynamic_gate"] == 0.0
    assert config["loss_weights"]["w_frequency"] == 0.0
    runs = {run["run_name"]: run for run in config["runs"]}
    assert set(runs) == {"vo2_sigma_fourier_off", "vo2_sigma_fourier_on"}
    assert runs["vo2_sigma_fourier_off"]["conductivity_mode"] == "white_box_vo2_sigma"
    assert runs["vo2_sigma_fourier_on"]["conductivity_mode"] == "white_box_vo2_sigma"
    assert runs["vo2_sigma_fourier_off"]["fourier_enabled"] is False
    assert runs["vo2_sigma_fourier_on"]["fourier_enabled"] is True


def test_fourier_ablation_script_runs_and_preserves_frozen_inputs(tmp_path: Path) -> None:
    before_hash = {str(path): _sha256(path) for path in FROZEN_FILES}
    before_mtime = {str(path): path.stat().st_mtime_ns for path in FROZEN_FILES}
    output_root = tmp_path / "fourier_outputs"
    summary_path = tmp_path / "fourier_summary.json"
    runs_csv = tmp_path / "fourier_runs.csv"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_pinn_inverse_v2_fourier_ablation.py",
            "--config",
            "configs/pinn_inverse_v2_fourier_ablation.yaml",
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
    assert "all_finite_loss" in result.stdout
    assert summary_path.exists()
    assert runs_csv.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    after_hash = {str(path): _sha256(path) for path in FROZEN_FILES}
    after_mtime = {str(path): path.stat().st_mtime_ns for path in FROZEN_FILES}

    assert before_hash == after_hash
    assert before_mtime == after_mtime
    assert summary["frozen_inputs_unchanged"] is True
    assert summary["all_finite_loss"] is True
    assert summary["all_used_vo2_sigma"] is True
    assert summary["all_frozen_inputs_unchanged"] is True
    assert summary["num_runs"] == 2
    assert summary["claim_boundary"] == "small-run Fourier ablation only; no F-SPS-PINN superiority claim unless supported by results"
    assert "multiscale features alone" in summary["recommended_interpretation"]
    rows = {row["run_name"]: row for row in summary["runs"]}
    assert set(rows) == {"vo2_sigma_fourier_off", "vo2_sigma_fourier_on"}
    assert rows["vo2_sigma_fourier_off"]["fourier_enabled"] is False
    assert rows["vo2_sigma_fourier_on"]["fourier_enabled"] is True

    required = [
        "T_c",
        "transition_width",
        "sigma_ins0",
        "sigma_met0",
        "sigma_contrast",
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
        "sigma_dynamic_range",
    ]
    for row in rows.values():
        assert row["conductivity_mode"] == "white_box_vo2_sigma"
        assert row["stress_case"] == "sharp_transition"
        assert row["used_vo2_sigma"] is True
        assert row["used_free_log_sigma"] is False
        assert row["frozen_inputs_unchanged"] is True
        assert row["finite_loss"] is True
        assert isinstance(row["fourier_scales"], list)
        for key in required:
            assert np.isfinite(float(row[key]))
        assert float(row["sigma_min"]) > 0.0
        assert float(row["sigma_max"]) >= float(row["sigma_min"])
        assert float(row["sigma_dynamic_range"]) >= 1.0
