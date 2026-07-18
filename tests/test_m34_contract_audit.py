"""Behavioral tests for the preregistered M34 contract audit."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import yaml

from pinnpcm.pinn.m34_contract_audit import (
    GROUPS,
    build_m33_model,
    ledger_contract_audit,
    toy_alm_benchmark,
    vector_alm_loss,
)
from pinnpcm.pinn.mixed_flux_pinn import grouped_constraint_tensors


def _config() -> dict:
    return yaml.safe_load(Path("configs/m34_optimization_contract_audit.yaml").read_text(encoding="utf-8"))


def _m33_config() -> dict:
    return yaml.safe_load(Path("configs/m33_feasibility_first_mixed_flux.yaml").read_text(encoding="utf-8"))


def test_toy_signed_alm_recovers_signed_duals_and_rms_does_not() -> None:
    config = _config()
    rows = toy_alm_benchmark(config["alm_toy"])
    signed = [row for row in rows if row["method"] == "signed_vector_alm"]
    assert max(row["constraint_abs"] for row in signed) <= config["alm_toy"]["corrected_constraint_abs_max"]
    assert max(row["dual_abs_error"] for row in signed) <= config["alm_toy"]["corrected_dual_abs_error_max"]
    negative_norm = next(row for row in rows if row["case_id"] == "negative_dual" and row["method"] == "group_rms_scalar_multiplier")
    assert negative_norm["true_signed_dual"] < 0.0
    assert negative_norm["reported_multiplier"] >= 0.0
    assert negative_norm["dual_semantics"] == "nonnegative_norm_weight"


def test_vector_alm_uses_signed_constraint_elements() -> None:
    parameter = torch.tensor([0.25, -0.5], dtype=torch.float64, requires_grad=True)
    groups = {name: parameter if name == "constitutive" else torch.zeros_like(parameter) for name in GROUPS}
    multipliers = {name: torch.zeros_like(parameter) for name in GROUPS}
    multipliers["constitutive"] = torch.tensor([1.0, -2.0], dtype=torch.float64)
    penalties = {name: 0.1 for name in GROUPS}
    loss = vector_alm_loss(groups, multipliers, penalties)
    loss.backward()
    assert parameter.grad is not None
    assert parameter.grad[0] > 0.0
    assert parameter.grad[1] < 0.0


def test_ledger_training_and_independent_fixed_scale_implementations_match() -> None:
    config = _config()
    model, gt, params, _ = build_m33_model(
        _m33_config(), Path(config["frozen_inputs"]["m33_checkpoint"]), dtype=torch.float64
    )
    audit = dict(config["ledger_audit"])
    audit["time_grid_counts"] = [32]
    rows, summary = ledger_contract_audit(model, gt, params, audit)
    assert len(rows) == 2
    assert summary["maximum_training_independent_implementation_difference"] <= audit["implementation_parity_abs_max"]
    assert all(np.isfinite(row["fixed_scale_rms"]) for row in rows)


def test_audit_schema_separates_evidence_and_authorization() -> None:
    schema = json.loads(Path("docs/schemas/m34_contract_audit_v1.schema.json").read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert {"input_hashes", "checkpoint_raw_sha256", "dtype", "time_grids", "normalization"} <= required
    assert {"corrected_preflight", "authorization_conditions", "corrected_training_authorized"} <= required
