"""Training-path safety tests for the bounded N0-R repair."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import torch
import yaml

from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.full_pinn_1d_split import DualDomainFullPINN1D
from pinnpcm.pinn.n0_diagnostics import generate_fixed_points


def _script_module():
    path = Path("scripts/train_full_pinn_n0_repair.py")
    spec = importlib.util.spec_from_file_location("train_full_pinn_n0_repair", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict[str, object]:
    with open("configs/full_pinn_n0_repair_v2.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_preregistered_loss_blocks_are_finite_and_use_no_labels() -> None:
    module = _script_module()
    config = _config()
    gt_config = yaml.safe_load(open("configs/gt_v1_acceptance_triangle.yaml", encoding="utf-8"))
    params = merge_params(gt_config.get("params"))
    model = DualDomainFullPINN1D(params=params, hidden_dim_per_domain=8, hidden_layers=1, seed=3)
    points = generate_fixed_points(config)
    reduced = {key: value[: min(len(value), 8)] for key, value in points.items()}
    tensor_points = module._tensor_points(reduced)
    total, blocks, _ = module._loss_blocks(model, tensor_points, "025", config["training"]["loss_weights"])
    assert torch.isfinite(total)
    assert set(blocks) == {"r_phi", "r_c", "r_T", "r_m", "endpoint_flux", "interface_state", "interface_flux"}
    assert config["training"]["full_field_training"] is False
    assert config["training"]["port_label_training"] is False


def test_anchor_route_requires_physics_interface_current_and_energy_pass() -> None:
    module = _script_module()
    checks = {
        "port": False,
        "fields": False,
        "heldout_residuals": True,
        "interface_flux": True,
        "current_conservation": True,
        "energy_conservation": True,
    }
    assert module._anchor_allowed({"checks": checks}) is True
    for key in ("heldout_residuals", "interface_flux", "current_conservation", "energy_conservation"):
        failed = checks.copy()
        failed[key] = False
        assert module._anchor_allowed({"checks": failed}) is False


def test_sparse_anchor_preregistration_forbids_hidden_fields() -> None:
    anchor = _config()["sparse_port_anchor_ablation"]
    assert set(anchor["allowed_labels"]) == {"I", "G"}
    assert set(anchor["forbidden_labels"]) == {"phi", "c_v", "T", "m", "sigma"}
    assert len(anchor["time_indices"]) == 16
    assert np.all(np.diff(anchor["time_indices"]) > 0)
