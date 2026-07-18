"""Behavioral physics tests for the preregistered M33 mixed-flux contract."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import yaml

from pinnpcm.physics.gt_solver import equilibrium_m
from pinnpcm.pinn.full_pinn_n0_cv_e import torch_cv_rhs
from pinnpcm.pinn.mixed_flux_pinn import (
    MixedStateFluxPINN,
    grouped_constraint_tensors,
    mixed_operator_residuals,
    rms,
)
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt


def _config() -> dict:
    return yaml.safe_load(Path("configs/m33_feasibility_first_mixed_flux.yaml").read_text(encoding="utf-8"))


def _model(*, dtype: torch.dtype = torch.float64, hidden_dim: int | None = None) -> tuple[MixedStateFluxPINN, dict, dict]:
    config = _config()
    gt, params = load_frozen_gt(Path(config["frozen_inputs"]["gt_path"]))
    architecture = config["architecture"]
    model = MixedStateFluxPINN(
        params=params,
        nx=architecture["nx"],
        t_max_s=float(gt["t"][-1]),
        hidden_dim=architecture["hidden_dim"] if hidden_dim is None else hidden_dim,
        hidden_layers=architecture["hidden_layers"],
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=architecture["temperature_min_K"],
        temperature_max_k=architecture["temperature_max_K"],
        registry=config["dimensionless_registry"],
        seed=config["training"]["seed"],
    ).to(dtype=dtype)
    return model, gt, params


def test_matched_parameter_budget_and_complete_outputs() -> None:
    model, _, _ = _model()
    contract = model.contract()
    assert contract["parameter_count"] == 5632
    assert abs(contract["relative_parameter_difference"]) <= 0.10
    time = torch.linspace(0.0, 1.0, 7, dtype=torch.float64).reshape(-1, 1)
    output = model(time)
    assert set(output) >= {"phi", "c_v", "T", "m", "sigma", "E", "J", "I", "G", "q_c", "q_T"}
    assert output["q_c"].shape == (7, 32)
    assert output["q_T"].shape == (7, 32)
    assert torch.max(torch.abs(output["q_c"][:, [0, -1]])) == 0.0
    assert torch.max(torch.abs(output["q_T"][:, [0, -1]])) == 0.0
    assert torch.all((output["c_v"] >= 0.0) & (output["c_v"] <= 1.0))
    assert torch.all((output["m"] >= 0.0) & (output["m"] <= 1.0))


def test_initial_flux_heads_equal_frozen_face_fluxes() -> None:
    model, _, _ = _model()
    time = torch.zeros((1, 1), dtype=torch.float64)
    output = model(time)
    frozen = torch_cv_rhs(model, time, output["c_v"], output["T"], output["m"])
    torch.testing.assert_close(output["q_c"], frozen["defect_flux"], rtol=1.0e-12, atol=1.0e-20)
    torch.testing.assert_close(output["q_T"], frozen["heat_flux"], rtol=1.0e-12, atol=1.0e-20)


def test_constant_equilibrium_manufactured_residual_is_zero() -> None:
    config = _config()
    _, _, params = _model()
    local = dict(params)
    local.update({"layer_profile": "uniform", "initial_defect_mode": "uniform", "triangle_v_peak": 0.0})
    model = MixedStateFluxPINN(
        params=local,
        nx=31,
        hidden_dim=8,
        hidden_layers=1,
        registry=config["dimensionless_registry"],
        seed=9,
    ).double()
    time = torch.tensor([[0.2], [0.8]], dtype=torch.float64)
    c = torch.full((2, 31), float(local["c_v0"]), dtype=torch.float64)
    temperature = torch.full_like(c, float(local["T0"]))
    m = torch.as_tensor(equilibrium_m(c.numpy(), temperature.numpy(), local), dtype=torch.float64)
    zero = torch.zeros_like(c)
    zero_flux = torch.zeros((2, 32), dtype=torch.float64)
    result = mixed_operator_residuals(model, time, c, temperature, m, zero, zero, zero, zero_flux, zero_flux)
    for name in ("q_c_constitutive", "q_T_constitutive", "r_c", "r_T", "r_m", "discrete_electrical"):
        assert float(rms(result[name])) <= 1.0e-12


def test_nontrivial_frozen_fvm_trace_has_first_order_parity() -> None:
    model, gt, _ = _model()
    indices = np.asarray([57, 171, 285])
    time = torch.as_tensor(gt["t"][indices, None] / gt["t"][-1], dtype=torch.float64)
    c = torch.as_tensor(gt["c_v"][indices], dtype=torch.float64)
    temperature = torch.as_tensor(gt["T"][indices], dtype=torch.float64)
    m = torch.as_tensor(gt["m"][indices], dtype=torch.float64)
    frozen = torch_cv_rhs(model, time, c, temperature, m)
    result = mixed_operator_residuals(
        model, time, c, temperature, m,
        frozen["dc_dt"], frozen["dT_dt"], frozen["dm_dt"],
        frozen["defect_flux"], frozen["heat_flux"],
    )
    for name in ("q_c_constitutive", "q_T_constitutive", "r_c", "r_T", "r_m", "discrete_electrical"):
        assert float(rms(result[name])) <= 1.0e-8


def test_grouped_constraints_have_finite_gradients_and_detect_flux_tamper() -> None:
    model, gt, _ = _model(dtype=torch.float32, hidden_dim=8)
    train_t = torch.linspace(0.02, 0.20, 6).reshape(-1, 1)
    ledger_t = torch.linspace(0.0, 0.20, 6).reshape(-1, 1)
    groups = grouped_constraint_tensors(model, train_t, ledger_t)
    assert set(groups) == {"constitutive", "conservation", "phase_current", "ic_bc", "interface", "ledgers"}
    loss = sum(rms(value).square() for value in groups.values())
    loss.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    assert gradients and all(torch.isfinite(value).all() for value in gradients)
    assert sum(float(torch.linalg.vector_norm(value)) for value in gradients) > 0.0

    index = 171
    time = torch.tensor([[gt["t"][index] / gt["t"][-1]]], dtype=torch.float32)
    c = torch.as_tensor(gt["c_v"][index : index + 1], dtype=torch.float32)
    temperature = torch.as_tensor(gt["T"][index : index + 1], dtype=torch.float32)
    m = torch.as_tensor(gt["m"][index : index + 1], dtype=torch.float32)
    frozen = torch_cv_rhs(model, time, c, temperature, m)
    clean = mixed_operator_residuals(model, time, c, temperature, m, frozen["dc_dt"], frozen["dT_dt"], frozen["dm_dt"], frozen["defect_flux"], frozen["heat_flux"])
    tampered = mixed_operator_residuals(model, time, c, temperature, m, frozen["dc_dt"], frozen["dT_dt"], frozen["dm_dt"], -frozen["defect_flux"], -frozen["heat_flux"])
    clean_max = max(float(rms(clean[name])) for name in ("q_c_constitutive", "q_T_constitutive", "r_c", "r_T"))
    tampered_max = max(float(rms(tampered[name])) for name in ("q_c_constitutive", "q_T_constitutive", "r_c", "r_T"))
    assert tampered_max > max(10.0 * clean_max, 1.0e-6)

