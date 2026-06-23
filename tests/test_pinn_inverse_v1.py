"""PINN inverse v1 physics-residual smoke tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch

from pinnpcm.pinn.data import load_inverse_v0_data
from pinnpcm.pinn.models import InverseV0Net
from pinnpcm.pinn.physics_residuals import compute_field_derivatives, compute_physics_residuals
from pinnpcm.utils.config import load_yaml


V1_CONFIGS = [
    Path("configs/pinn_inverse_v1_triangle_physics.yaml"),
    Path("configs/pinn_inverse_v1_triangle_weak_anchor.yaml"),
    Path("configs/pinn_inverse_v1_triangle_port_physics.yaml"),
]

V1_1_CONFIGS = [
    Path("configs/pinn_inverse_v1_1_triangle_physics_balanced.yaml"),
    Path("configs/pinn_inverse_v1_1_triangle_port_physics_balanced.yaml"),
]


def test_v1_configs_are_readable() -> None:
    """All v1 configs should load and expose required loss weights."""

    required_weights = {
        "w_port_data",
        "w_ic",
        "w_field_anchor",
        "w_smooth",
        "w_heat_residual",
        "w_state_residual",
        "w_defect_residual",
        "w_sigma_consistency",
        "w_boundary",
    }
    for path in V1_CONFIGS:
        cfg = load_yaml(path)
        assert required_weights.issubset(cfg["loss_weights"])
        data = load_inverse_v0_data(cfg, root=Path.cwd())
        assert data.train_data_path.exists()
        assert data.sparse_obs_path.exists()


def test_v1_physics_residuals_are_finite() -> None:
    """Physics residual forward pass should not create NaN or Inf."""

    cfg = load_yaml(V1_CONFIGS[0])
    data = load_inverse_v0_data(cfg, root=Path.cwd())
    model = InverseV0Net(hidden_dim=8, num_layers=1, fourier_features=4)
    coords = torch.rand(12, 2)
    residuals = compute_physics_residuals(
        model,
        coords,
        data.params,
        x_scale=float(data.params["L_eff"]),
        t_scale=float(data.t[-1] - data.t[0]),
        physics_scales=cfg["physics_scales"],
    )

    for key in ("heat_residual", "state_residual", "defect_residual", "sigma_consistency"):
        value = residuals[key]
        assert isinstance(value, torch.Tensor)
        assert torch.all(torch.isfinite(value))


def test_v1_autograd_derivatives_exist() -> None:
    """Autograd should compute dT/dt, dm/dt, and dc_v/dt."""

    cfg = load_yaml(V1_CONFIGS[0])
    data = load_inverse_v0_data(cfg, root=Path.cwd())
    model = InverseV0Net(hidden_dim=8, num_layers=1, fourier_features=4)
    coords = torch.rand(10, 2, requires_grad=True)
    fields = model(coords)
    derivatives = compute_field_derivatives(
        fields,
        coords,
        x_scale=float(data.params["L_eff"]),
        t_scale=float(data.t[-1] - data.t[0]),
    )

    for key in ("delta_T_t", "m_t", "c_v_t"):
        assert key in derivatives
        assert derivatives[key].shape == (10, 1)
        assert torch.all(torch.isfinite(derivatives[key]))


def test_train_pinn_inverse_v1_smoke(tmp_path: Path) -> None:
    """The v1 training script should run for two epochs and emit metrics."""

    output_dir = tmp_path / "pinn_inverse_v1_smoke"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_pinn_inverse_v1.py",
            "--config",
            "configs/pinn_inverse_v1_triangle_physics.yaml",
            "--epochs",
            "2",
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path.cwd(),
        check=True,
        text=True,
        capture_output=True,
        timeout=180,
    )

    assert "Training PINN inverse v1" in result.stdout
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    required_metrics = {
        "relative_G_error",
        "relative_I_error",
        "nrmse_delta_T",
        "nrmse_delta_c_v",
        "nrmse_delta_m",
        "nrmse_sigma",
        "final_heat_residual",
        "final_state_residual",
        "final_defect_residual",
        "final_sigma_consistency",
    }
    assert required_metrics.issubset(metrics)
    for key in required_metrics:
        assert np.isfinite(metrics[key])


def test_v1_1_configs_enable_balancing_and_schedule() -> None:
    """v1.1 configs should enable residual balancing and warmup scheduling."""

    for path in V1_1_CONFIGS:
        cfg = load_yaml(path)
        assert cfg["residual_balancing"]["enabled"] is True
        assert cfg["loss_schedule"]["enabled"] is True
        assert "w_sigma_initial" in cfg["loss_weights"]
        data = load_inverse_v0_data(cfg, root=Path.cwd())
        assert data.train_data_path.exists()
        assert data.sparse_obs_path.exists()
