"""Fail-closed gate and no-label tests for N0-CV-E v3."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from pinnpcm.pinn.full_pinn_n0_cv_e import ControlVolumeFullPINN
from pinnpcm.pinn.n0_cv_evidence import gate_coverage_table, load_frozen_gt, valid_gate_value


def _load_script(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, Path(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return yaml.safe_load(Path("configs/full_pinn_n0_cv_e_v3.yaml").read_text(encoding="utf-8"))


def test_every_v3_gate_has_one_declared_result_key() -> None:
    coverage = gate_coverage_table(_config())
    assert coverage["mapping_complete"] is True
    assert coverage["mapped_gate_count"] == coverage["expected_gate_count"]
    assert coverage["extra_mappings"] == []


def test_missing_and_nan_gate_results_fail_closed() -> None:
    config = _config()
    payload = {"preflight": {"checks": {"phase_a_completed": True}}}
    coverage = gate_coverage_table(config, payload)
    assert coverage["execution_complete"] is False
    assert any(row["fail_closed"] for row in coverage["rows"])


def test_empty_and_nested_nonfinite_gate_payloads_fail_closed() -> None:
    assert valid_gate_value({}) is False
    assert valid_gate_value([]) is False
    assert valid_gate_value({"a": []}) is False
    assert valid_gate_value({"a": [1.0, float("nan")]}) is False
    assert valid_gate_value({"a": [1.0, 2.0], "b": True}) is True


def test_training_loss_uses_only_time_and_physics_no_labels() -> None:
    module = _load_script("train_n0_cv_e_v3", "scripts/train_n0_cv_e_v3.py")
    config = _config()
    gt, params = load_frozen_gt(Path(config["frozen_inputs"]["gt_path"]))
    architecture = config["architecture"]
    model = ControlVolumeFullPINN(
        params=params,
        nx=architecture["nx"],
        hidden_dim=8,
        hidden_layers=1,
        registry=config["dimensionless_registry"],
        seed=5,
    )
    train_t = torch.linspace(0.01, 0.20, 5).reshape(-1, 1)
    ledger_t = torch.linspace(0.0, 0.20, 5).reshape(-1, 1)
    blocks = module._loss_blocks(model, train_t, ledger_t)
    assert set(blocks) == {
        "r_c",
        "r_T",
        "r_m",
        "discrete_electrical",
        "defect_mass_ledger",
        "energy_ledger",
    }
    assert all(torch.isfinite(value) for value in blocks.values())
    assert config["training"]["full_field_training"] is False
    assert config["training"]["port_label_training"] is False


def test_generated_preflight_never_authorizes_training_on_a_failed_check() -> None:
    path = Path("outputs/tables/n0_cv_e_v3_preflight.json")
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["training_authorized"] == all(payload["checks"].values())
    assert payload["all_pass"] == all(payload["checks"].values())
