"""Differentiable oscillation metrics for phase-transition PINN MVPs."""

from __future__ import annotations

import torch


def _as_batched(signal: torch.Tensor) -> tuple[torch.Tensor, bool]:
    if signal.ndim == 1:
        return signal.unsqueeze(0), True
    if signal.ndim < 1:
        raise ValueError("signal must have at least one dimension.")
    return signal.reshape(-1, signal.shape[-1]), False


def _time_info(t: torch.Tensor, n: int, like: torch.Tensor) -> tuple[float, torch.Tensor]:
    if t.ndim != 1 or t.numel() != n:
        raise ValueError("t must be one-dimensional and aligned with signal's last dimension.")
    dt = torch.mean(torch.diff(t.to(dtype=like.dtype, device=like.device)))
    dt_safe = torch.clamp(dt, min=torch.as_tensor(1.0e-12, dtype=like.dtype, device=like.device))
    duration = dt_safe * max(n - 1, 1)
    return float(dt_safe.detach().cpu()), duration


def differentiable_spectral_frequency(
    t: torch.Tensor,
    signal: torch.Tensor,
    *,
    sharpness: float = 4.0,
    eps: float = 1.0e-12,
) -> torch.Tensor:
    """Estimate dominant frequency with differentiable spectral soft weights."""

    sig, squeezed = _as_batched(signal)
    n = sig.shape[-1]
    if n < 3:
        raise ValueError("signal must contain at least three samples.")
    dt_float, _ = _time_info(t, n, sig)
    centered = sig - torch.mean(sig, dim=-1, keepdim=True)
    spectrum = torch.fft.rfft(centered, dim=-1)
    real = spectrum.real
    imag = spectrum.imag
    power = real.square() + imag.square() + eps
    freqs = torch.fft.rfftfreq(n, d=dt_float).to(dtype=sig.dtype, device=sig.device)
    if power.shape[-1] > 1:
        power = power[..., 1:]
        freqs = freqs[1:]
    log_power = torch.log(torch.clamp(power, min=eps))
    weights = torch.softmax(float(sharpness) * log_power, dim=-1)
    estimate = torch.sum(weights * freqs, dim=-1)
    return estimate.squeeze(0) if squeezed else estimate.reshape(signal.shape[:-1])


def differentiable_pulse_width(
    t: torch.Tensor,
    signal: torch.Tensor,
    threshold_mode: str = "soft",
    *,
    softness: float = 0.08,
    eps: float = 1.0e-12,
) -> torch.Tensor:
    """Estimate pulse width using a sigmoid soft mask."""

    if threshold_mode != "soft":
        raise ValueError("Only threshold_mode='soft' is differentiable in this MVP.")
    sig, squeezed = _as_batched(signal)
    n = sig.shape[-1]
    dt_float, duration = _time_info(t, n, sig)
    del dt_float
    sig_min = torch.amin(sig, dim=-1, keepdim=True)
    sig_max = torch.amax(sig, dim=-1, keepdim=True)
    amplitude = torch.clamp(sig_max - sig_min, min=eps)
    threshold = sig_min + 0.5 * amplitude
    width_scale = torch.clamp(float(softness) * amplitude, min=eps)
    mask = torch.sigmoid((sig - threshold) / width_scale)
    fraction = torch.mean(mask, dim=-1)
    width = fraction * duration
    return width.squeeze(0) if squeezed else width.reshape(signal.shape[:-1])


def oscillation_signature_loss(
    pred_signal: torch.Tensor,
    target_signal: torch.Tensor,
    t: torch.Tensor,
    *,
    eps: float = 1.0e-12,
) -> torch.Tensor:
    """Compare differentiable frequency, width, and waveform signatures."""

    pred = pred_signal
    target = target_signal.to(dtype=pred.dtype, device=pred.device)
    time = t.to(dtype=pred.dtype, device=pred.device)
    pred_freq = differentiable_spectral_frequency(time, pred, eps=eps)
    target_freq = differentiable_spectral_frequency(time, target, eps=eps).detach()
    pred_width = differentiable_pulse_width(time, pred, eps=eps)
    target_width = differentiable_pulse_width(time, target, eps=eps).detach()

    freq_scale = torch.clamp(target_freq.square(), min=torch.as_tensor(eps, dtype=pred.dtype, device=pred.device))
    width_scale = torch.clamp(target_width.square(), min=torch.as_tensor(eps, dtype=pred.dtype, device=pred.device))
    signal_scale = torch.clamp(torch.mean(target.square()), min=torch.as_tensor(eps, dtype=pred.dtype, device=pred.device))
    freq_loss = torch.mean((pred_freq - target_freq).square() / freq_scale)
    width_loss = torch.mean((pred_width - target_width).square() / width_scale)
    waveform_loss = torch.mean((pred - target).square()) / signal_scale
    return freq_loss + width_loss + waveform_loss