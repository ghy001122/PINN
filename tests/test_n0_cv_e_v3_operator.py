"""Behavioral parity and gradient tests for N0-CV-E v3."""

from __future__ import annotations

import numpy as np
import torch
import yaml

from pinnpcm.physics.conductivity import mixed_conductivity
from pinnpcm.physics.electrostatics import solve_series_electrostatics
from pinnpcm.physics.gt_solver import _rhs_factory
from pinnpcm.physics.params import spatial_param_profiles
from pinnpcm.physics.voltage_protocols import get_voltage_protocol
from pinnpcm.pinn.full_pinn_n0_cv_e import (
    ControlVolumeFullPINN,
    control_volume_residuals,
    hard_constraint_metrics,
    torch_cv_rhs,
)
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt


def _config() -> dict[str, object]:
    return yaml.safe_load(open("configs/full_pinn_n0_cv_e_v3.yaml", encoding="utf-8"))


def _model(dtype: torch.dtype = torch.float64) -> tuple[ControlVolumeFullPINN, dict, dict]:
    config = _config()
    gt, params = load_frozen_gt(__import__("pathlib").Path(config["frozen_inputs"]["gt_path"]))
    architecture = config["architecture"]
    model = ControlVolumeFullPINN(
        params=params,
        nx=architecture["nx"],
        hidden_dim=8,
        hidden_layers=1,
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=architecture["temperature_min_K"],
        temperature_max_k=architecture["temperature_max_K"],
        registry=config["dimensionless_registry"],
        seed=3,
    ).to(dtype=dtype)
    return model, gt, params


def test_analytic_head_returns_complete_state_and_hard_constraints() -> None:
    model, _, _ = _model()
    time = torch.linspace(0.0, 1.0, 9, dtype=torch.float64).reshape(-1, 1)
    output = model(time)
    assert set(output) >= {"phi", "c_v", "T", "m", "sigma", "E", "J", "I", "G"}
    assert output["c_v"].shape == (9, 31)
    assert torch.all((output["c_v"] >= 0.0) & (output["c_v"] <= 1.0))
    assert torch.all((output["m"] >= 0.0) & (output["m"] <= 1.0))
    assert torch.all((output["T"] >= 300.0) & (output["T"] <= 350.0))
    constraints = hard_constraint_metrics(model, time)
    assert max(constraints.values()) < 1.0e-12


def test_torch_electrostatics_matches_numpy_float64() -> None:
    model, gt, params = _model()
    index = 171
    c = torch.tensor(gt["c_v"][index : index + 1], dtype=torch.float64)
    temperature = torch.tensor(gt["T"][index : index + 1], dtype=torch.float64)
    m = torch.tensor(gt["m"][index : index + 1], dtype=torch.float64)
    voltage = torch.tensor([[gt["V"][index]]], dtype=torch.float64)
    actual = model.analytic_electrostatics(c, temperature, m, voltage)
    profiles = {**params, **spatial_param_profiles(gt["x"], params)}
    sigma = mixed_conductivity(gt["c_v"][index], gt["T"][index], gt["m"][index], profiles)
    expected = solve_series_electrostatics(gt["V"][index], sigma, params, params["L_eff"] / 31)
    for key in ("sigma", "E", "phi"):
        np.testing.assert_allclose(actual[key].detach().numpy()[0], sigma if key == "sigma" else expected[key], rtol=1.0e-7, atol=1.0e-12)
    for key in ("J", "I", "G", "R_area"):
        assert float(actual[key]) == __import__("pytest").approx(float(expected[key]), rel=1.0e-7)


def test_torch_cv_rhs_matches_frozen_numpy_rhs() -> None:
    model, gt, params = _model()
    indices = np.asarray([57, 171, 285])
    time = torch.tensor(gt["t"][indices, None] / gt["t"][-1], dtype=torch.float64)
    c = torch.tensor(gt["c_v"][indices], dtype=torch.float64)
    temperature = torch.tensor(gt["T"][indices], dtype=torch.float64)
    m = torch.tensor(gt["m"][indices], dtype=torch.float64)
    actual = torch_cv_rhs(model, time, c, temperature, m)
    profiles = {**params, **spatial_param_profiles(gt["x"], params)}
    rhs = _rhs_factory(
        get_voltage_protocol("triangle", gt["t"][-1], params), params=profiles, nx=31, dx=params["L_eff"] / 31
    )
    expected = np.asarray(
        [
            rhs(gt["t"][idx], np.concatenate([gt["c_v"][idx], gt["T"][idx], gt["m"][idx]]))
            for idx in indices
        ]
    )
    np.testing.assert_allclose(actual["dc_dt"].detach().numpy(), expected[:, :31], rtol=1.0e-6, atol=1.0e-9)
    np.testing.assert_allclose(actual["dT_dt"].detach().numpy(), expected[:, 31:62], rtol=1.0e-6, atol=1.0e-5)
    np.testing.assert_allclose(actual["dm_dt"].detach().numpy(), expected[:, 62:], rtol=1.0e-6, atol=1.0e-7)


def test_cv_residual_has_finite_nonzero_parameter_gradients() -> None:
    model, _, _ = _model(torch.float32)
    time = torch.linspace(0.05, 0.25, 5).reshape(-1, 1)
    residuals = control_volume_residuals(model, time)
    loss = sum(torch.mean(residuals[key].square()) for key in ("r_c", "r_T", "r_m"))
    loss.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    assert gradients
    assert all(torch.isfinite(gradient).all() for gradient in gradients)
    assert sum(float(torch.linalg.vector_norm(gradient)) for gradient in gradients) > 0.0
