"""SI implementation of the Zhang et al. single thermal-neuristor model.

The implementation preserves the v1.0.0 author-code event ordering while using
SI units internally. It is an independent repository implementation for source
reproduction and identifiability audits, not a project-generated experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VO2ThermalNeuristorParameters:
    """Physical and numerical parameters in SI units."""

    w_K: float
    T_c_K: float
    beta_per_K: float
    R0_ohm: float
    E_a_K: float
    gamma_per_K: float
    Rm0_ohm: float
    Rm_factor: float
    C_F: float
    C_th_J_per_K: float
    S_th_W_per_K: float
    T_base_K: float
    R_load_ohm: float
    noise_strength: float
    Cth_factor: float
    couple_factor: float
    temperature_clip_K: tuple[float, float]
    reversal_delta_T_threshold_K: float
    initial_temperature_offset_K: float

    @property
    def R_metal_ohm(self) -> float:
        return self.Rm0_ohm * self.Rm_factor

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "VO2ThermalNeuristorParameters":
        semantics = cfg["source_semantics"]
        values = semantics["parameters"]
        return cls(
            **{key: float(value) for key, value in values.items()},
            temperature_clip_K=tuple(float(x) for x in semantics["temperature_clip_K"]),
            reversal_delta_T_threshold_K=float(
                semantics["reversal_delta_T_threshold_K"]
            ),
            initial_temperature_offset_K=float(
                semantics["initial_temperature_offset_K"]
            ),
        )


@dataclass
class HysteresisLedger:
    """Piecewise history state matching the author-code reversal ledger."""

    delta: float
    reversed_flag: float
    T_r_K: float
    g_r: float
    T_pr_K: float
    T_last_K: float


@dataclass(frozen=True)
class NeuristorTrace:
    """Single-device source-compatibility trajectory."""

    time_s: np.ndarray
    current_A: np.ndarray
    voltage_V: np.ndarray
    temperature_K: np.ndarray
    resistance_ohm: np.ndarray
    event_times_s: np.ndarray
    branch: np.ndarray
    source_kind: str


def _p_kernel(x: float | np.ndarray, gamma: float) -> float | np.ndarray:
    return 0.5 * (1.0 - np.sin(gamma * x)) * (
        1.0 + np.tanh(np.pi**2 - 2.0 * np.pi * x)
    )


def _g_major(temperature_K: float, delta: float, params: VO2ThermalNeuristorParameters) -> float:
    return float(
        0.5
        + 0.5
        * np.tanh(
            params.beta_per_K
            * (delta * params.w_K / 2.0 + params.T_c_K - temperature_K)
        )
    )


def _t_pr(
    delta: float,
    g_r: float,
    T_r_K: float,
    params: VO2ThermalNeuristorParameters,
) -> float:
    return float(
        delta * params.w_K / 2.0
        + params.T_c_K
        - np.arctanh(2.0 * g_r - 1.0) / params.beta_per_K
        - T_r_K
    )


def initialize_ledger(params: VO2ThermalNeuristorParameters) -> HysteresisLedger:
    temperature = params.T_base_K + params.initial_temperature_offset_K
    delta = 1.0
    g_r = _g_major(temperature, delta, params)
    return HysteresisLedger(
        delta=delta,
        reversed_flag=0.0,
        T_r_K=temperature,
        g_r=g_r,
        T_pr_K=_t_pr(delta, g_r, temperature, params),
        T_last_K=temperature,
    )


def _phase_insulating_fraction(
    temperature_K: float,
    ledger: HysteresisLedger,
    params: VO2ThermalNeuristorParameters,
) -> float:
    denominator = ledger.T_pr_K + 1.0e-6
    x = (temperature_K - ledger.T_r_K) / denominator
    T_p = (
        ledger.T_pr_K
        * float(_p_kernel(x, params.gamma_per_K))
        * ledger.reversed_flag
    )
    argument = params.beta_per_K * (
        ledger.delta * params.w_K / 2.0
        + params.T_c_K
        - (temperature_K + T_p)
    )
    return float(0.5 + 0.5 * np.tanh(argument))


def _update_reversal(
    temperature_K: float,
    ledger: HysteresisLedger,
    params: VO2ThermalNeuristorParameters,
) -> bool:
    clipped = float(np.clip(temperature_K, *params.temperature_clip_K))
    delta_temperature = clipped - ledger.T_last_K
    changed = False
    if abs(delta_temperature) > params.reversal_delta_T_threshold_K:
        new_delta = float(np.sign(delta_temperature))
        if new_delta != ledger.delta and new_delta != 0.0:
            ledger.g_r = _phase_insulating_fraction(clipped, ledger, params)
            ledger.delta = new_delta
            ledger.reversed_flag = 1.0
            ledger.T_r_K = clipped
            ledger.T_pr_K = _t_pr(new_delta, ledger.g_r, clipped, params)
            changed = True
        ledger.T_last_K = clipped
    return changed


def resistance_ohm(
    temperature_K: float,
    ledger: HysteresisLedger,
    params: VO2ThermalNeuristorParameters,
) -> float:
    """Return source-model resistance in ohms."""

    clipped = float(np.clip(temperature_K, *params.temperature_clip_K))
    insulating_fraction = _phase_insulating_fraction(clipped, ledger, params)
    return float(
        params.R0_ohm * np.exp(params.E_a_K / clipped) * insulating_fraction
        + params.R_metal_ohm
    )


def resistance_path_ohm(
    temperature_K: np.ndarray,
    params: VO2ThermalNeuristorParameters,
    *,
    initialize_at_first_temperature: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate the source hysteresis model along a supplied temperature path."""

    values = np.asarray(temperature_K, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("temperature_K must be a non-empty one-dimensional array.")
    ledger = initialize_ledger(params)
    if initialize_at_first_temperature:
        first = float(values[0])
        ledger.T_r_K = first
        ledger.T_last_K = first
        ledger.g_r = _g_major(first, ledger.delta, params)
        ledger.T_pr_K = _t_pr(ledger.delta, ledger.g_r, first, params)
    result = np.empty_like(values)
    branches = np.empty_like(values)
    event_indices: list[int] = []
    for index, temperature in enumerate(values):
        if _update_reversal(float(temperature), ledger, params):
            event_indices.append(index)
        result[index] = resistance_ohm(float(temperature), ledger, params)
        branches[index] = ledger.delta
    return result, branches, np.asarray(event_indices, dtype=np.int64)


def simulate_source_compat_si(
    params: VO2ThermalNeuristorParameters,
    *,
    input_voltage_V: float,
    t_max_s: float,
    dt_s: float,
    noise_strength: float = 0.0,
    seed: int = 0,
) -> NeuristorTrace:
    """Integrate the author-equivalent single-device model in SI units."""

    if t_max_s <= 0.0 or dt_s <= 0.0:
        raise ValueError("t_max_s and dt_s must be positive.")
    n_steps = int(t_max_s / dt_s)
    if n_steps < 1:
        raise ValueError("The integration interval contains no time step.")
    rng = np.random.default_rng(seed)
    ledger = initialize_ledger(params)
    capacitor_voltage = 0.0
    temperature = params.T_base_K
    times = np.empty(n_steps, dtype=np.float64)
    current = np.empty(n_steps, dtype=np.float64)
    voltage = np.empty(n_steps, dtype=np.float64)
    temperatures = np.empty(n_steps, dtype=np.float64)
    resistances = np.empty(n_steps, dtype=np.float64)
    branches = np.empty(n_steps, dtype=np.float64)
    event_times: list[float] = []
    time_s = 0.0

    for index in range(n_steps):
        if _update_reversal(temperature, ledger, params):
            event_times.append(time_s)
        device_resistance = resistance_ohm(temperature, ledger, params)
        device_current = capacitor_voltage / device_resistance
        dV_dt = (
            input_voltage_V / (params.R_load_ohm * params.C_F)
            - capacitor_voltage / (params.R_load_ohm * params.C_F)
            - capacitor_voltage / (device_resistance * params.C_F)
        )
        joule_power = device_current**2 * device_resistance
        dT_dt = (
            (joule_power - params.S_th_W_per_K * (temperature - params.T_base_K))
            / params.C_th_J_per_K
            + noise_strength * 1.0e9 * rng.standard_normal()
        ) / params.Cth_factor

        time_s += dt_s
        times[index] = time_s
        current[index] = device_current
        voltage[index] = capacitor_voltage
        temperatures[index] = temperature
        resistances[index] = device_resistance
        branches[index] = ledger.delta
        capacitor_voltage += dV_dt * dt_s
        temperature += dT_dt * dt_s

    return NeuristorTrace(
        time_s=times,
        current_A=current,
        voltage_V=voltage,
        temperature_K=temperatures,
        resistance_ohm=resistances,
        event_times_s=np.asarray(event_times, dtype=np.float64),
        branch=branches,
        source_kind="repository_si_solver",
    )
