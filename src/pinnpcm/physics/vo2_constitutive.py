"""Torch differentiable VO2-like constitutive conductivity closures.

These functions are isolated architecture-MVP utilities for synthetic numerical
digital-twin benchmarks. They are literature-guided engineering priors, not
measured VO2/NbO2 device parameters and not a replacement for the frozen Ground
Truth v1.1 conductivity model.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import torch

K_B_EV_PER_K = 8.617333262145e-5

DEFAULT_VO2_PARAMS: dict[str, float | str] = {
    "T_c": 340.0,
    "transition_width": 2.0,
    "transition_width_min": 0.25,
    "T_ref": 300.0,
    "c_v_ref": 0.08,
    "sigma_ins0": 1.0e-2,
    "sigma_met0": 1.0e4,
    "E_ins_eV": 0.12,
    "beta_c": 4.0,
    "metal_temp_coeff": 1.0e-3,
    "mixing_mode": "linear",
    "smooth_power": 0.25,
    "eps_sigma": 1.0e-12,
    "eps": 1.0e-12,
    "sigma_max": 1.0e8,
}


def _params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = dict(DEFAULT_VO2_PARAMS)
    if params:
        merged.update(dict(params))
    return merged


def _tensor_param(params: Mapping[str, Any], key: str, like: torch.Tensor) -> torch.Tensor:
    return torch.as_tensor(params[key], dtype=like.dtype, device=like.device)


def _positive_param(params: Mapping[str, Any], key: str, like: torch.Tensor, min_key: str | None = None) -> torch.Tensor:
    value = torch.abs(_tensor_param(params, key, like))
    floor_key = min_key or "eps"
    floor = torch.as_tensor(float(params.get(floor_key, params.get("eps", 1.0e-12))), dtype=like.dtype, device=like.device)
    return torch.clamp(value, min=floor)


def _safe_temperature(temperature: torch.Tensor) -> torch.Tensor:
    return torch.clamp(temperature, min=1.0, max=5000.0)


def _safe_sigma(sigma: torch.Tensor, params: Mapping[str, Any]) -> torch.Tensor:
    eps = torch.as_tensor(float(params.get("eps_sigma", 1.0e-12)), dtype=sigma.dtype, device=sigma.device)
    sigma_max = torch.as_tensor(float(params.get("sigma_max", 1.0e8)), dtype=sigma.dtype, device=sigma.device)
    return torch.clamp(sigma, min=eps, max=sigma_max)


def phase_fraction_from_temperature(
    T: torch.Tensor | float,
    params: Mapping[str, Any] | None = None,
) -> torch.Tensor:
    """Return a stable differentiable phase fraction in `[0, 1]`.

    The transition uses `torch.sigmoid((T - T_c) / transition_width)` with a
    protected lower bound on `transition_width` and a finite argument clamp.
    """

    temperature = torch.as_tensor(T) if not isinstance(T, torch.Tensor) else T
    p = _params(params)
    t_c = _tensor_param(p, "T_c", temperature)
    width = _positive_param(p, "transition_width", temperature, "transition_width_min")
    argument = torch.clamp((temperature - t_c) / width, min=-80.0, max=80.0)
    return torch.sigmoid(argument)


def insulating_sigma(
    T: torch.Tensor | float,
    c_v: torch.Tensor | float,
    params: Mapping[str, Any] | None = None,
) -> torch.Tensor:
    """Return the positive insulating-branch conductivity.

    The Arrhenius-like term is evaluated in log space with exponent clipping so
    extreme temperatures remain finite and differentiable with respect to `T`.
    """

    temperature = torch.as_tensor(T) if not isinstance(T, torch.Tensor) else T
    defect = torch.as_tensor(c_v, dtype=temperature.dtype, device=temperature.device) if not isinstance(c_v, torch.Tensor) else c_v.to(dtype=temperature.dtype, device=temperature.device)
    p = _params(params)
    safe_t = _safe_temperature(temperature)
    sigma0 = _positive_param(p, "sigma_ins0", temperature)
    t_ref = _positive_param(p, "T_ref", temperature)
    e_ins = _tensor_param(p, "E_ins_eV", temperature)
    beta_c = _tensor_param(p, "beta_c", temperature)
    c_ref = _tensor_param(p, "c_v_ref", temperature)
    log_sigma = torch.log(sigma0) - e_ins / K_B_EV_PER_K * (1.0 / safe_t - 1.0 / t_ref)
    log_sigma = log_sigma + beta_c * (defect - c_ref)
    log_sigma = torch.clamp(log_sigma, min=-80.0, max=80.0)
    return _safe_sigma(torch.exp(log_sigma), p)


def metallic_sigma(
    T: torch.Tensor | float,
    params: Mapping[str, Any] | None = None,
) -> torch.Tensor:
    """Return the positive metallic-branch conductivity."""

    temperature = torch.as_tensor(T) if not isinstance(T, torch.Tensor) else T
    p = _params(params)
    sigma0 = _positive_param(p, "sigma_met0", temperature)
    t_ref = _positive_param(p, "T_ref", temperature)
    alpha = _tensor_param(p, "metal_temp_coeff", temperature)
    log_sigma = torch.log(sigma0) - alpha * (temperature - t_ref)
    log_sigma = torch.clamp(log_sigma, min=-80.0, max=80.0)
    return _safe_sigma(torch.exp(log_sigma), p)


def _smooth_power_mix(sigma_ins: torch.Tensor, sigma_met: torch.Tensor, m: torch.Tensor, params: Mapping[str, Any]) -> torch.Tensor:
    power = _tensor_param(params, "smooth_power", sigma_ins)
    eps = _tensor_param(params, "eps", sigma_ins)
    m_safe = torch.clamp(m, min=eps, max=1.0 - eps)
    log_ins = torch.log(_safe_sigma(sigma_ins, params))
    log_met = torch.log(_safe_sigma(sigma_met, params))
    if torch.all(torch.abs(power) < 1.0e-6):
        return torch.exp((1.0 - m_safe) * log_ins + m_safe * log_met)
    terms = torch.stack(
        [torch.log1p(-m_safe) + power * log_ins, torch.log(m_safe) + power * log_met],
        dim=0,
    )
    return torch.exp(torch.logsumexp(terms, dim=0) / power)


def _bruggeman_mix(sigma_ins: torch.Tensor, sigma_met: torch.Tensor, m: torch.Tensor, params: Mapping[str, Any]) -> torch.Tensor:
    eps = torch.as_tensor(float(params.get("eps", 1.0e-12)), dtype=sigma_ins.dtype, device=sigma_ins.device)
    si = _safe_sigma(sigma_ins, params)
    sm = _safe_sigma(sigma_met, params)
    f = torch.clamp(m, min=1.0e-6, max=1.0 - 1.0e-6)
    b_term = (3.0 * f - 1.0) * sm + (2.0 - 3.0 * f) * si
    discriminant = torch.clamp(b_term.square() + 8.0 * si * sm, min=eps)
    sigma_eff = 0.25 * (b_term + torch.sqrt(discriminant))
    return _safe_sigma(sigma_eff, params)


def effective_medium_sigma(
    sigma_ins: torch.Tensor | float,
    sigma_met: torch.Tensor | float,
    m: torch.Tensor | float,
    params: Mapping[str, Any] | None = None,
) -> torch.Tensor:
    """Mix insulating and metallic conductivities with a stable default mode."""

    si = torch.as_tensor(sigma_ins) if not isinstance(sigma_ins, torch.Tensor) else sigma_ins
    sm = torch.as_tensor(sigma_met, dtype=si.dtype, device=si.device) if not isinstance(sigma_met, torch.Tensor) else sigma_met.to(dtype=si.dtype, device=si.device)
    phase = torch.as_tensor(m, dtype=si.dtype, device=si.device) if not isinstance(m, torch.Tensor) else m.to(dtype=si.dtype, device=si.device)
    p = _params(params)
    si, sm, phase = torch.broadcast_tensors(si, sm, phase)
    phase = torch.clamp(phase, min=0.0, max=1.0)
    mode = str(p.get("mixing_mode", "linear")).lower()

    if mode == "linear":
        return _safe_sigma((1.0 - phase) * _safe_sigma(si, p) + phase * _safe_sigma(sm, p), p)
    if mode == "smooth_power":
        return _safe_sigma(_smooth_power_mix(si, sm, phase, p), p)
    if mode == "bruggeman":
        return _bruggeman_mix(si, sm, phase, p)
    raise ValueError(f"Unsupported VO2 mixing_mode: {mode}")


def vo2_sigma(
    T: torch.Tensor | float,
    c_v: torch.Tensor | float,
    m: torch.Tensor | float | None = None,
    params: Mapping[str, Any] | None = None,
) -> torch.Tensor:
    """Return a positive VO2-like conductivity closure `sigma(T, c_v, m)`.

    If `m` is omitted, it is computed from temperature with
    `phase_fraction_from_temperature`. This is a white-box MVP closure and does
    not use the old free `log_sigma` regression path.
    """

    temperature = torch.as_tensor(T) if not isinstance(T, torch.Tensor) else T
    defect = torch.as_tensor(c_v, dtype=temperature.dtype, device=temperature.device) if not isinstance(c_v, torch.Tensor) else c_v.to(dtype=temperature.dtype, device=temperature.device)
    p = _params(params)
    phase = phase_fraction_from_temperature(temperature, p) if m is None else torch.as_tensor(m, dtype=temperature.dtype, device=temperature.device) if not isinstance(m, torch.Tensor) else m.to(dtype=temperature.dtype, device=temperature.device)
    si = insulating_sigma(temperature, defect, p)
    sm = metallic_sigma(temperature, p)
    return effective_medium_sigma(si, sm, phase, p)