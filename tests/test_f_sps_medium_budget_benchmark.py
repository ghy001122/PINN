from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import yaml

from scripts.train_f_sps_medium_budget_benchmark import run_medium_budget


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


def test_f_sps_medium_budget_config_scope() -> None:
    config = yaml.safe_load(Path("configs/f_sps_medium_budget_benchmark.yaml").read_text(encoding="utf-8"))
    assert config["epochs"] == [20, 100, 300]
    assert len(config["seeds"]) == 3
    names = {row["model_name"] for row in config["models"]}
    assert {"free_log_sigma_pinn", "white_box_vo2_sigma_pinn", "white_box_vo2_sigma_fourier", "f_sps_pinn", "f_sps_pinn_with_dynamic_gate"}.issubset(names)


def test_f_sps_medium_budget_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    config = yaml.safe_load(Path("configs/f_sps_medium_budget_benchmark.yaml").read_text(encoding="utf-8"))
    config["summary_json"] = str(tmp_path / "summary.json")
    config["cases_csv"] = str(tmp_path / "cases.csv")
    config["output_root"] = str(tmp_path / "train_outputs")
    config["epochs"] = [1]
    config["seeds"] = [2026]
    config["max_executed_cases"] = 2
    config["models"] = config["models"][:2]
    config["field_anchor_points"] = 8
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    summary = run_medium_budget(path)
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_inputs_unchanged"] is True
    assert summary["planned_cases"] == 2
    assert summary["executed_cases"] == 2
    assert summary["all_executed_finite"] is True
    for row in summary["runs"]:
        assert row["executed"] is True
        assert np.isfinite(float(row["final_loss"]))
        assert np.isfinite(float(row["gradient_norm_mean"]))
    assert Path(config["summary_json"]).exists()
    assert Path(config["cases_csv"]).exists()
