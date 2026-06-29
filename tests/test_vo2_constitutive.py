from __future__ import annotations

import torch

from pinnpcm.physics.vo2_constitutive import (
    effective_medium_sigma,
    phase_fraction_from_temperature,
    vo2_sigma,
)


def test_vo2_sigma_positive_and_backward() -> None:
    T = torch.linspace(300.0, 380.0, 16, requires_grad=True)
    c_v = torch.full_like(T, 0.08)
    sigma = vo2_sigma(T, c_v)
    assert sigma.shape == T.shape
    assert torch.all(torch.isfinite(sigma))
    assert torch.all(sigma > 0.0)
    loss = torch.log(sigma).mean()
    loss.backward()
    assert T.grad is not None
    assert torch.all(torch.isfinite(T.grad))


def test_vo2_sigma_extreme_temperature_inputs_are_finite() -> None:
    T = torch.tensor([-1.0e6, 0.0, 1.0, 300.0, 340.0, 1.0e6], requires_grad=True)
    c_v = torch.full_like(T, 0.08)
    sigma = vo2_sigma(T, c_v)
    assert torch.all(torch.isfinite(sigma))
    assert torch.all(sigma > 0.0)
    sigma.sum().backward()
    assert T.grad is not None
    assert torch.all(torch.isfinite(T.grad))


def test_phase_transition_creates_sharp_continuous_sigma_jump() -> None:
    params = {"T_c": 340.0, "transition_width": 1.5, "sigma_ins0": 1.0e-2, "sigma_met0": 1.0e4}
    T = torch.tensor([330.0, 340.0, 350.0])
    c_v = torch.full_like(T, 0.08)
    phase = phase_fraction_from_temperature(T, params)
    sigma = vo2_sigma(T, c_v, params=params)
    assert torch.all(torch.isfinite(phase))
    assert phase[0] < phase[1] < phase[2]
    assert sigma[2] / sigma[0] > 100.0


def test_effective_medium_default_and_bruggeman_are_stable() -> None:
    sigma_ins = torch.tensor([1.0e-12, 1.0e-6, 1.0], requires_grad=True)
    sigma_met = torch.tensor([1.0e-12, 1.0e-5, 10.0], requires_grad=True)
    m = torch.tensor([1.0e-9, 0.5, 1.0 - 1.0e-9])
    linear = effective_medium_sigma(sigma_ins, sigma_met, m)
    brug = effective_medium_sigma(sigma_ins, sigma_met, m, {"mixing_mode": "bruggeman", "eps": 1.0e-18})
    assert torch.all(torch.isfinite(linear))
    assert torch.all(torch.isfinite(brug))
    assert torch.all(linear > 0.0)
    assert torch.all(brug > 0.0)
    (linear.sum() + brug.sum()).backward()
    assert sigma_ins.grad is not None
    assert sigma_met.grad is not None
    assert torch.all(torch.isfinite(sigma_ins.grad))
    assert torch.all(torch.isfinite(sigma_met.grad))