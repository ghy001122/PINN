"""Qiu-2024 source-equation-constrained lumped thermal-neuristor model.

This module implements Supporting Information equations S1--S7 from
Qiu et al. (Advanced Materials, 2024, DOI 10.1002/adma.202306818).  The
published paper does not provide executable source code, numerical initial
conditions, an integrator, or an event deadband.  Consequently this module
implements the reported equations and keeps the repository's explicit LLP
reversal assumptions visible; it is not an exact author-code reproduction.

The model is intentionally independent of the M40/M40R local 2-D closure.
There is no local conductivity, rate-smoothed history state, or contact model
here.  All quantities use SI units.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import numpy as np
import yaml


ModelVariant = Literal["hysteresis", "no_hysteresis", "fixed_heating"]


@dataclass(frozen=True)
class QiuAuthorCompactParameters:
    """Source-fitted lumped parameters plus declared implementation inputs."""

    resistance_prefactor_ohm: float
    metallic_resistance_ohm: float
    activation_temperature_K: float
    beta_per_K: float
    hysteresis_width_K: float
    critical_temperature_K: float
    proximity_gamma_dimensionless: float
    dynamic_metallic_factor: float
    parallel_capacitance_F: float
    thermal_conductance_W_per_K: float
    thermal_capacitance_J_per_K: float
    load_resistance_ohm: float
    ambient_temperature_K: float
    initial_capacitor_voltage_V: float = 0.0
    initial_device_temperature_K: float = 325.0
    initial_branch_delta: int = 1

    def validate(self) -> None:
        positive = {
            "resistance_prefactor_ohm": self.resistance_prefactor_ohm,
            "metallic_resistance_ohm": self.metallic_resistance_ohm,
            "activation_temperature_K": self.activation_temperature_K,
            "beta_per_K": self.beta_per_K,
            "hysteresis_width_K": self.hysteresis_width_K,
            "critical_temperature_K": self.critical_temperature_K,
            "proximity_gamma_dimensionless": self.proximity_gamma_dimensionless,
            "dynamic_metallic_factor": self.dynamic_metallic_factor,
            "parallel_capacitance_F": self.parallel_capacitance_F,
            "thermal_conductance_W_per_K": self.thermal_conductance_W_per_K,
            "thermal_capacitance_J_per_K": self.thermal_capacitance_J_per_K,
            "load_resistance_ohm": self.load_resistance_ohm,
            "ambient_temperature_K": self.ambient_temperature_K,
            "initial_device_temperature_K": self.initial_device_temperature_K,
        }
        for name, value in positive.items():
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not np.isfinite(self.initial_capacitor_voltage_V):
            raise ValueError("initial_capacitor_voltage_V must be finite")
        if self.initial_branch_delta not in (-1, 1):
            raise ValueError("initial_branch_delta must be +1 or -1")

    @property
    def thermal_time_constant_s(self) -> float:
        return self.thermal_capacitance_J_per_K / self.thermal_conductance_W_per_K

    @property
    def circuit_time_constant_s(self) -> float:
        return self.load_resistance_ohm * self.parallel_capacitance_F

    def to_dict(self) -> dict[str, float | int]:
        return dict(asdict(self))


@dataclass(frozen=True)
class LLPReversalLedger:
    """Limiting-loop-proximity branch state used by equations S2--S4."""

    delta: int
    reversed_once: bool
    reversal_temperature_K: float
    reversal_fraction: float
    proximity_temperature_K: float

    def to_dict(self) -> dict[str, float | int | bool]:
        return dict(asdict(self))


def default_parameters() -> QiuAuthorCompactParameters:
    """Return the locked source-fitted values and declared E1F initial inputs."""

    result = QiuAuthorCompactParameters(
        resistance_prefactor_ohm=5.359e-3,
        metallic_resistance_ohm=262.5,
        activation_temperature_K=5220.0,
        beta_per_K=0.253,
        hysteresis_width_K=7.193,
        critical_temperature_K=332.8,
        proximity_gamma_dimensionless=0.956,
        dynamic_metallic_factor=4.90,
        parallel_capacitance_F=145.0e-12,
        thermal_conductance_W_per_K=0.206e-3,
        thermal_capacitance_J_per_K=49.6e-12,
        load_resistance_ohm=12000.0,
        ambient_temperature_K=325.0,
        initial_capacitor_voltage_V=0.0,
        initial_device_temperature_K=325.0,
        initial_branch_delta=1,
    )
    result.validate()
    return result


def load_parameters(config: Mapping[str, Any] | str | Path) -> QiuAuthorCompactParameters:
    """Load parameters from the locked E1F YAML mapping or path."""

    if isinstance(config, (str, Path)):
        payload = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    else:
        payload = config
    author = payload["author_parameters"]
    setting = payload["source"]["setting_curve"]
    initial = payload["initial_conditions"]
    result = QiuAuthorCompactParameters(
        **{name: float(author[name]) for name in (
            "resistance_prefactor_ohm",
            "metallic_resistance_ohm",
            "activation_temperature_K",
            "beta_per_K",
            "hysteresis_width_K",
            "critical_temperature_K",
            "proximity_gamma_dimensionless",
            "dynamic_metallic_factor",
            "parallel_capacitance_F",
            "thermal_conductance_W_per_K",
            "thermal_capacitance_J_per_K",
        )},
        load_resistance_ohm=float(setting["load_resistance_ohm"]),
        ambient_temperature_K=float(setting["ambient_temperature_K"]),
        initial_capacitor_voltage_V=float(initial["capacitor_voltage_V"]),
        initial_device_temperature_K=float(initial["device_temperature_K"]),
        initial_branch_delta=int(initial["initial_branch_delta"]),
    )
    result.validate()
    return result


def initialize_ledger(params: QiuAuthorCompactParameters) -> LLPReversalLedger:
    """Initialize on a source-declared major branch; proximity is inactive."""

    fraction = float(
        major_branch_insulating_fraction(
            params.initial_device_temperature_K,
            params.initial_branch_delta,
            params,
        )
    )
    return LLPReversalLedger(
        delta=params.initial_branch_delta,
        reversed_once=False,
        reversal_temperature_K=params.initial_device_temperature_K,
        reversal_fraction=fraction,
        proximity_temperature_K=0.0,
    )


def proximity_function(
    x: float | np.ndarray, gamma_dimensionless: float
) -> float | np.ndarray:
    """Equation S4."""

    values = np.asarray(x, dtype=np.float64)
    result = 0.5 * (1.0 - np.sin(gamma_dimensionless * values)) * (
        1.0 + np.tanh(np.pi**2 - 2.0 * np.pi * values)
    )
    return float(result) if result.ndim == 0 else result


def major_branch_insulating_fraction(
    temperature_K: float | np.ndarray,
    delta: int,
    params: QiuAuthorCompactParameters,
) -> float | np.ndarray:
    """Equation S2 on a heating or cooling major branch."""

    if delta not in (-1, 1):
        raise ValueError("major-loop delta must be +1 or -1")
    temperature = _positive_temperature(temperature_K)
    argument = params.beta_per_K * (
        delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - temperature
    )
    fraction = 0.5 + 0.5 * np.tanh(argument)
    return float(fraction) if fraction.ndim == 0 else fraction


def proximity_temperature_from_reversal(
    delta: int,
    reversal_fraction: float,
    reversal_temperature_K: float,
    params: QiuAuthorCompactParameters,
) -> float:
    """Equation S3 exactly as printed in the Qiu Supporting Information."""

    if delta not in (-1, 1):
        raise ValueError("reversal delta must be +1 or -1")
    fraction = float(reversal_fraction)
    argument = 2.0 * fraction - 1.0
    if not np.isfinite(argument) or not 0.0 <= fraction <= 1.0:
        raise ValueError("Equation S3 requires a finite fraction in [0, 1]")
    temperature = float(_positive_temperature(reversal_temperature_K))
    value = (
        delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - argument / params.beta_per_K
        - temperature
    )
    if not np.isfinite(value):
        raise ValueError("Equation S3 produced a non-finite proximity temperature")
    return float(value)


def insulating_fraction(
    temperature_K: float | np.ndarray,
    ledger: LLPReversalLedger,
    params: QiuAuthorCompactParameters,
    *,
    variant: ModelVariant = "hysteresis",
) -> float | np.ndarray:
    """Equation S2 under the selected preregistered baseline variant."""

    temperature = _positive_temperature(temperature_K)
    if variant == "no_hysteresis":
        argument = params.beta_per_K * (
            params.critical_temperature_K - temperature
        )
    elif variant == "fixed_heating":
        return major_branch_insulating_fraction(temperature, 1, params)
    elif variant == "hysteresis":
        if not ledger.reversed_once:
            return major_branch_insulating_fraction(temperature, ledger.delta, params)
        t_pr = float(ledger.proximity_temperature_K)
        if not np.isfinite(t_pr) or t_pr == 0.0:
            raise ValueError("Equation S2 requires a finite, nonzero T_pr after reversal")
        x = (temperature - ledger.reversal_temperature_K) / t_pr
        shifted_temperature = temperature + t_pr * proximity_function(
            x, params.proximity_gamma_dimensionless
        )
        argument = params.beta_per_K * (
            ledger.delta * params.hysteresis_width_K / 2.0
            + params.critical_temperature_K
            - shifted_temperature
        )
    else:
        raise ValueError(f"unsupported Qiu compact-model variant: {variant}")
    fraction = 0.5 + 0.5 * np.tanh(argument)
    return float(fraction) if np.ndim(fraction) == 0 else np.asarray(fraction)


def update_ledger_at_reversal(
    reversal_temperature_K: float,
    ledger: LLPReversalLedger,
    params: QiuAuthorCompactParameters,
) -> LLPReversalLedger:
    """Apply the LLP rule only at a localized temperature-derivative reversal."""

    temperature = float(_positive_temperature(reversal_temperature_K))
    fraction = float(insulating_fraction(temperature, ledger, params))
    new_delta = -ledger.delta
    t_pr = proximity_temperature_from_reversal(
        new_delta, fraction, temperature, params
    )
    return LLPReversalLedger(
        delta=new_delta,
        reversed_once=True,
        reversal_temperature_K=temperature,
        reversal_fraction=fraction,
        proximity_temperature_K=t_pr,
    )


def quasistatic_resistance_ohm(
    temperature_K: float | np.ndarray,
    ledger: LLPReversalLedger,
    params: QiuAuthorCompactParameters,
    *,
    variant: ModelVariant = "hysteresis",
) -> float | np.ndarray:
    """Equation S1."""

    temperature = _positive_temperature(temperature_K)
    fraction = insulating_fraction(temperature, ledger, params, variant=variant)
    result = (
        params.resistance_prefactor_ohm
        * np.exp(params.activation_temperature_K / temperature)
        * fraction
        + params.metallic_resistance_ohm
    )
    return _finite_positive_result(result, "Equation S1 resistance")


def dynamic_resistance_ohm(
    temperature_K: float | np.ndarray,
    ledger: LLPReversalLedger,
    params: QiuAuthorCompactParameters,
    *,
    variant: ModelVariant = "hysteresis",
) -> float | np.ndarray:
    """Equation S7, including the source-fitted thin-channel factor k."""

    temperature = _positive_temperature(temperature_K)
    fraction = insulating_fraction(temperature, ledger, params, variant=variant)
    result = (
        params.resistance_prefactor_ohm
        * np.exp(params.activation_temperature_K / temperature)
        * fraction
        + params.dynamic_metallic_factor * params.metallic_resistance_ohm
    )
    return _finite_positive_result(result, "Equation S7 resistance")


def compact_rhs(
    _time_s: float,
    state: np.ndarray,
    *,
    params: QiuAuthorCompactParameters,
    input_voltage_V: float,
    ledger: LLPReversalLedger,
    variant: ModelVariant = "hysteresis",
) -> np.ndarray:
    """Pure within-segment RHS for equations S5 and S6."""

    values = np.asarray(state, dtype=np.float64)
    if values.shape != (2,) or not np.isfinite(values).all():
        raise ValueError("Qiu compact state must be two finite values [V1, T]")
    voltage = float(values[0])
    temperature = float(_positive_temperature(values[1]))
    if not np.isfinite(input_voltage_V):
        raise ValueError("input_voltage_V must be finite")
    resistance = float(
        dynamic_resistance_ohm(temperature, ledger, params, variant=variant)
    )
    d_voltage_dt = (
        input_voltage_V / (params.load_resistance_ohm * params.parallel_capacitance_F)
        - voltage
        * (
            1.0 / (resistance * params.parallel_capacitance_F)
            + 1.0
            / (params.load_resistance_ohm * params.parallel_capacitance_F)
        )
    )
    d_temperature_dt = (
        voltage**2 / (resistance * params.thermal_capacitance_J_per_K)
        - params.thermal_conductance_W_per_K
        * (temperature - params.ambient_temperature_K)
        / params.thermal_capacitance_J_per_K
    )
    result = np.asarray([d_voltage_dt, d_temperature_dt], dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError("Equations S5-S6 produced a non-finite derivative")
    return result


def _positive_temperature(value: float | np.ndarray) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if not np.isfinite(result).all() or np.any(result <= 0.0):
        raise ValueError("temperature must be finite and strictly positive")
    return result


def _finite_positive_result(value: float | np.ndarray, name: str) -> float | np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if not np.isfinite(result).all() or np.any(result <= 0.0):
        raise ValueError(f"{name} must be finite and positive")
    return float(result) if result.ndim == 0 else result
