from __future__ import annotations

import inspect

import torch

from pinnpcm.physics import oscillation_metrics
from pinnpcm.physics.oscillation_metrics import (
    differentiable_pulse_width,
    differentiable_spectral_frequency,
    oscillation_signature_loss,
)


def test_spectral_frequency_estimates_sine_frequency() -> None:
    n = 256
    t = torch.arange(n, dtype=torch.float32) / n
    freq = 5.0
    signal = torch.sin(2.0 * torch.pi * freq * t)
    estimated = differentiable_spectral_frequency(t, signal, sharpness=5.0)
    assert torch.isfinite(estimated)
    assert abs(float(estimated) - freq) < 0.5


def test_soft_pulse_width_estimate_is_reasonable() -> None:
    n = 512
    t = torch.arange(n, dtype=torch.float32) / n
    signal = torch.sigmoid((t - 0.25) / 0.01) * torch.sigmoid((0.55 - t) / 0.01)
    width = differentiable_pulse_width(t, signal)
    assert torch.isfinite(width)
    assert 0.2 < float(width) < 0.4


def test_oscillation_signature_loss_backward_is_finite() -> None:
    n = 256
    t = torch.arange(n, dtype=torch.float32) / n
    target = torch.sin(2.0 * torch.pi * 4.0 * t)
    pred = (0.9 * torch.sin(2.0 * torch.pi * 4.3 * t)).requires_grad_(True)
    loss = oscillation_signature_loss(pred, target, t)
    assert torch.isfinite(loss)
    loss.backward()
    assert pred.grad is not None
    assert torch.all(torch.isfinite(pred.grad))


def test_zero_signal_frequency_loss_backward_is_finite() -> None:
    n = 128
    t = torch.arange(n, dtype=torch.float32) / n
    target = torch.zeros(n)
    pred = torch.zeros(n, requires_grad=True)
    loss = oscillation_signature_loss(pred, target, t)
    assert torch.isfinite(loss)
    loss.backward()
    assert pred.grad is not None
    assert torch.all(torch.isfinite(pred.grad))


def test_frequency_loss_source_avoids_forbidden_main_path_ops() -> None:
    source = inspect.getsource(oscillation_metrics)
    assert "torch.argmax" not in source
    assert "torch.abs" not in source