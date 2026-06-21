"""Voltage protocols for Ground Truth generation."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike


def default_t_max(protocol: str) -> float:
    """Return the default duration for a voltage protocol."""

    if protocol == "triangle":
        return 3.0e-3
    if protocol == "ltp_ltd":
        return 15.0e-3
    raise ValueError(f"Unsupported protocol: {protocol}")


def triangle_voltage(t: ArrayLike, t_max: float, v_peak: float = 0.20) -> np.ndarray:
    """Smooth-free triangular sweep from -v_peak to +v_peak and back."""

    t_arr = np.asarray(t, dtype=float)
    phase = np.clip(t_arr / t_max, 0.0, 1.0)
    voltage = np.where(phase <= 0.5, -v_peak + 4.0 * v_peak * phase, 3.0 * v_peak - 4.0 * v_peak * phase)
    return voltage


def _smooth_window(t: np.ndarray, start: float, end: float, edge: float) -> np.ndarray:
    """Return a tanh-smoothed pulse window."""

    return 0.5 * (np.tanh((t - start) / edge) - np.tanh((t - end) / edge))


def ltp_ltd_voltage(
    t: ArrayLike,
    t_max: float,
    v_pos: float = 0.08,
    v_neg: float = -0.02,
    n_pos: int = 6,
    n_neg: int = 6,
) -> np.ndarray:
    """Return smoothed LTP/LTD pulse train with tanh pulse edges."""

    t_arr = np.asarray(t, dtype=float)
    total_pulses = n_pos + n_neg
    period = t_max / total_pulses
    width = 0.62 * period
    edge = max(0.04 * period, 1.0e-9)
    voltage = np.zeros_like(t_arr, dtype=float)

    for idx in range(total_pulses):
        center = (idx + 0.5) * period
        start = center - 0.5 * width
        end = center + 0.5 * width
        amp = v_pos if idx < n_pos else v_neg
        voltage = voltage + amp * _smooth_window(t_arr, start, end, edge)

    return voltage


def get_voltage_protocol(
    protocol: str,
    t_max: float | None = None,
    params: dict[str, float] | None = None,
) -> Callable[[ArrayLike], np.ndarray]:
    """Return a vectorized voltage function for a named protocol."""

    duration = default_t_max(protocol) if t_max is None else float(t_max)
    params = params or {}

    if protocol == "triangle":
        return lambda t: triangle_voltage(t, duration, v_peak=float(params.get("triangle_v_peak", 0.20)))
    if protocol == "ltp_ltd":
        return lambda t: ltp_ltd_voltage(
            t,
            duration,
            v_pos=float(params.get("ltp_v_pos", 0.08)),
            v_neg=float(params.get("ltp_v_neg", -0.02)),
        )
    raise ValueError(f"Unsupported protocol: {protocol}")
