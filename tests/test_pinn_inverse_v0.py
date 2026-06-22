"""PINN inverse v0 smoke tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch

from pinnpcm.pinn.data import load_inverse_v0_data
from pinnpcm.pinn.losses import reconstruct_port_from_sigma
from pinnpcm.pinn.models import InverseV0Net
from pinnpcm.utils.config import load_yaml


ABLATION_CONFIGS = [
    Path("configs/pinn_inverse_v0_triangle_full_anchor.yaml"),
    Path("configs/pinn_inverse_v0_triangle_weak_anchor.yaml"),
    Path("configs/pinn_inverse_v0_triangle_port_only.yaml"),
]


def test_inverse_v0_data_loader_reads_frozen_acceptance_data() -> None:
    """Data loader should read frozen GT, sparse observations, and manifest."""

    data = load_inverse_v0_data("configs/pinn_inverse_v0_triangle.yaml", root=Path.cwd())

    assert {"x", "t", "c_v", "T", "m", "sigma", "params_json"}.issubset(data.gt_keys)
    assert {"t_idx", "t", "V", "I", "G"}.issubset(data.obs_keys)
    assert np.asarray(data.gt["c_v"]).shape == (data.nt, data.nx)
    assert np.asarray(data.obs["t_idx"]).ndim == 1
    assert data.manifest["datasets"][0]["protocol"] == "triangle"


def test_inverse_v0_model_forward_shapes_and_ranges() -> None:
    """InverseV0Net should produce constrained field tensors."""

    model = InverseV0Net(hidden_dim=8, num_layers=1, fourier_features=4)
    coords = torch.rand(6, 2)
    pred = model(coords)

    for key in ("c_v", "delta_T", "m", "log_sigma", "sigma"):
        assert pred[key].shape == (6, 1)
        assert torch.all(torch.isfinite(pred[key]))
    assert torch.all((pred["c_v"] >= 0.0) & (pred["c_v"] <= 0.2))
    assert torch.all(pred["delta_T"] >= 0.0)
    assert torch.all((pred["m"] >= 0.0) & (pred["m"] <= 1.0))
    assert torch.all(pred["sigma"] > 0.0)


def test_conductance_reconstruction_is_finite() -> None:
    """Series conductance reconstruction should not produce NaN or Inf."""

    sigma = torch.full((4, 5), 1.0e-2)
    voltage = torch.tensor([0.0, 0.1, -0.1, 0.05])
    params = {
        "eps_sigma": 1.0e-30,
        "eps_R": 1.0e-30,
        "eps_V": 1.0e-12,
        "eta_A": 1.0e-6,
        "A_contact": 7.853981633974483e-9,
    }
    port = reconstruct_port_from_sigma(sigma, voltage, 1.0e-8, params)

    assert torch.all(torch.isfinite(port["I"]))
    assert torch.all(torch.isfinite(port["G"]))
    assert port["I"].shape == (4,)
    assert port["G"].shape == (4,)


def test_train_pinn_inverse_v0_smoke(tmp_path: Path) -> None:
    """The v0 training entrypoint should run a two-epoch smoke test."""

    output_dir = tmp_path / "pinn_inverse_v0_smoke"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_pinn_inverse_v0.py",
            "--config",
            "configs/pinn_inverse_v0_triangle.yaml",
            "--epochs",
            "2",
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path.cwd(),
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )

    assert "Ground Truth keys" in result.stdout
    metrics_path = output_dir / "metrics.json"
    history_path = output_dir / "train_history.json"
    assert metrics_path.exists()
    assert history_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert np.isfinite(metrics["final_total_loss"])
    assert np.isfinite(metrics["relative_G_error"])
    for key in ("nrmse_delta_T", "nrmse_delta_c_v", "nrmse_delta_m", "nrmse_sigma"):
        assert key in metrics
        assert np.isfinite(metrics[key])


def test_ablation_configs_are_readable_and_port_only_disables_anchor() -> None:
    """Ablation configs should be readable and encode the intended weights."""

    configs = {path.name: load_yaml(path) for path in ABLATION_CONFIGS}

    assert configs["pinn_inverse_v0_triangle_full_anchor.yaml"]["loss_weights"]["w_field_anchor"] == 1.0
    assert configs["pinn_inverse_v0_triangle_weak_anchor.yaml"]["loss_weights"]["w_field_anchor"] == 0.1
    assert configs["pinn_inverse_v0_triangle_port_only.yaml"]["loss_weights"]["w_field_anchor"] == 0.0
    for cfg in configs.values():
        data = load_inverse_v0_data(cfg, root=Path.cwd())
        assert data.train_data_path.exists()
        assert data.sparse_obs_path.exists()


def test_ablation_script_smoke(tmp_path: Path) -> None:
    """The ablation runner should support a small smoke test."""

    output_root = tmp_path / "pinn_inverse_v0_ablation"
    summary_path = tmp_path / "pinn_inverse_v0_ablation_summary.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_pinn_inverse_v0_ablation.py",
            "--smoke-test",
            "--output-root",
            str(output_root),
            "--summary",
            str(summary_path),
        ],
        cwd=Path.cwd(),
        check=True,
        text=True,
        capture_output=True,
        timeout=180,
    )

    assert "triangle_port_only" in result.stdout
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(summary["experiments"]) == 3
    for experiment in summary["experiments"]:
        metrics = experiment["metrics"]
        for key in ("nrmse_delta_T", "nrmse_delta_c_v", "nrmse_delta_m", "nrmse_sigma"):
            assert key in metrics
            assert np.isfinite(metrics[key])
