"""Independent thermal, circuit, and combined Phase 1 ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class LedgerBalance:
    name: str
    input_power_W: float
    accounted_power_W: float
    signed_residual_W: float
    relative_residual: float
    terms_W: dict[str, float]


def _balance(name: str, input_power_W: float, terms_W: Mapping[str, float]) -> LedgerBalance:
    values = {key: float(value) for key, value in terms_W.items()}
    all_values = np.asarray([input_power_W, *values.values()], dtype=float)
    if not np.isfinite(all_values).all():
        raise ValueError(f"{name} ledger contains a nonfinite value")
    accounted = float(sum(values.values()))
    residual = float(input_power_W - accounted)
    denominator = max(
        abs(float(input_power_W)) + sum(abs(value) for value in values.values()),
        1.0e-30,
    )
    return LedgerBalance(
        name=name,
        input_power_W=float(input_power_W),
        accounted_power_W=accounted,
        signed_residual_W=residual,
        relative_residual=abs(residual) / denominator,
        terms_W=values,
    )


def thermal_ledger(
    *,
    joule_power_W: float,
    active_storage_rate_W: float,
    memory_storage_rate_W: float,
    vertical_sink_power_W: float,
    lateral_outflow_power_W: float,
) -> LedgerBalance:
    return _balance(
        "thermal",
        joule_power_W,
        {
            "active_storage_rate_W": active_storage_rate_W,
            "memory_storage_rate_W": memory_storage_rate_W,
            "vertical_sink_power_W": vertical_sink_power_W,
            "lateral_outflow_power_W": lateral_outflow_power_W,
        },
    )


def circuit_ledger(
    *,
    input_voltage_V: float,
    old_device_voltage_V: float,
    new_device_voltage_V: float,
    load_resistance_ohm: float,
    capacitance_F: float,
    device_current_A: float,
    dt_s: float,
) -> LedgerBalance:
    if load_resistance_ohm <= 0.0 or capacitance_F <= 0.0 or dt_s <= 0.0:
        raise ValueError("circuit ledger requires positive R, C, and dt")
    source_current = (input_voltage_V - new_device_voltage_V) / load_resistance_ohm
    source_power = input_voltage_V * source_current
    load_power = source_current**2 * load_resistance_ohm
    voltage_increment = new_device_voltage_V - old_device_voltage_V
    capacitor_physical = (
        0.5
        * capacitance_F
        * (new_device_voltage_V**2 - old_device_voltage_V**2)
        / dt_s
    )
    capacitor_be_dissipation = 0.5 * capacitance_F * voltage_increment**2 / dt_s
    device_power = new_device_voltage_V * device_current_A
    return _balance(
        "circuit",
        source_power,
        {
            "load_resistor_power_W": load_power,
            "capacitor_physical_energy_rate_W": capacitor_physical,
            "capacitor_backward_euler_dissipation_W": capacitor_be_dissipation,
            "terminal_device_power_W": device_power,
        },
    )


def combined_electrothermal_ledger(
    *,
    input_voltage_V: float,
    old_device_voltage_V: float,
    new_device_voltage_V: float,
    load_resistance_ohm: float,
    capacitance_F: float,
    dt_s: float,
    active_storage_rate_W: float,
    memory_storage_rate_W: float,
    vertical_sink_power_W: float,
    lateral_outflow_power_W: float,
) -> LedgerBalance:
    if load_resistance_ohm <= 0.0 or capacitance_F <= 0.0 or dt_s <= 0.0:
        raise ValueError("combined ledger requires positive R, C, and dt")
    source_current = (input_voltage_V - new_device_voltage_V) / load_resistance_ohm
    source_power = input_voltage_V * source_current
    load_power = source_current**2 * load_resistance_ohm
    voltage_increment = new_device_voltage_V - old_device_voltage_V
    capacitor_physical = (
        0.5
        * capacitance_F
        * (new_device_voltage_V**2 - old_device_voltage_V**2)
        / dt_s
    )
    capacitor_be_dissipation = 0.5 * capacitance_F * voltage_increment**2 / dt_s
    return _balance(
        "combined_electrothermal",
        source_power,
        {
            "load_resistor_power_W": load_power,
            "capacitor_physical_energy_rate_W": capacitor_physical,
            "capacitor_backward_euler_dissipation_W": capacitor_be_dissipation,
            "active_storage_rate_W": active_storage_rate_W,
            "memory_storage_rate_W": memory_storage_rate_W,
            "vertical_sink_power_W": vertical_sink_power_W,
            "lateral_outflow_power_W": lateral_outflow_power_W,
        },
    )


def device_power_identity(
    *, terminal_device_power_W: float, field_joule_power_W: float
) -> LedgerBalance:
    return _balance(
        "device_power_identity",
        terminal_device_power_W,
        {"field_joule_power_W": field_joule_power_W},
    )


def require_ledger_gate(balance: LedgerBalance, maximum_relative_residual: float) -> None:
    if maximum_relative_residual < 0.0:
        raise ValueError("ledger threshold must be nonnegative")
    if not np.isfinite(balance.relative_residual):
        raise ValueError(f"{balance.name} ledger residual is nonfinite")
    if balance.relative_residual > maximum_relative_residual:
        raise ValueError(
            f"{balance.name} ledger failed: {balance.relative_residual:.6e} > "
            f"{maximum_relative_residual:.6e}"
        )
