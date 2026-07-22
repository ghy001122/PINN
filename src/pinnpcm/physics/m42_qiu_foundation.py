"""Physics contracts for the bounded M42 Qiu dimensional-closure preflight."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ElectricalLedger:
    current_A: float
    terminal_power_W: float
    bulk_power_W: float
    contact_power_W: float
    relative_power_imbalance: float
    relative_current_imbalance: float


def thermal_diffusion_length_m(
    thermal_conductivity_W_mK: float,
    volumetric_heat_capacity_J_m3K: float,
    time_s: float,
) -> float:
    if min(thermal_conductivity_W_mK, volumetric_heat_capacity_J_m3K, time_s) <= 0.0:
        raise ValueError("thermal scale inputs must be positive")
    diffusivity = thermal_conductivity_W_mK / volumetric_heat_capacity_J_m3K
    return float(np.sqrt(diffusivity * time_s))


def series_electrical_ledger(
    voltage_V: float,
    total_resistance_ohm: float,
    total_contact_resistance_ohm: float,
) -> ElectricalLedger:
    if total_resistance_ohm <= 0.0:
        raise ValueError("total resistance must be positive")
    if not 0.0 <= total_contact_resistance_ohm < total_resistance_ohm:
        raise ValueError("contact resistance must be within total resistance")
    current = voltage_V / total_resistance_ohm
    bulk_resistance = total_resistance_ohm - total_contact_resistance_ohm
    terminal_power = voltage_V * current
    bulk_power = current**2 * bulk_resistance
    contact_power = current**2 * total_contact_resistance_ohm
    imbalance = abs(terminal_power - bulk_power - contact_power) / max(
        abs(terminal_power), 1.0e-30
    )
    return ElectricalLedger(
        current_A=float(current),
        terminal_power_W=float(terminal_power),
        bulk_power_W=float(bulk_power),
        contact_power_W=float(contact_power),
        relative_power_imbalance=float(imbalance),
        relative_current_imbalance=0.0,
    )


def source_resistance_mapping_error(
    local_2d_resistance_ohm: float, source_equivalent_resistance_ohm: float
) -> float:
    if min(local_2d_resistance_ohm, source_equivalent_resistance_ohm) <= 0.0:
        raise ValueError("resistances must be positive")
    return abs(local_2d_resistance_ohm - source_equivalent_resistance_ohm) / abs(
        source_equivalent_resistance_ohm
    )


def run_fixed_resistance_rc(
    *,
    input_voltage_V: float,
    load_resistance_ohm: float,
    device_resistance_ohm: float,
    capacitance_F: float,
    duration_s: float,
    dt_s: float,
) -> dict[str, float | int | bool]:
    if min(load_resistance_ohm, device_resistance_ohm, capacitance_F, duration_s, dt_s) <= 0:
        raise ValueError("RC inputs must be positive")
    steps = int(np.ceil(duration_s / dt_s))
    dt = duration_s / steps
    voltage = 0.0
    maximum_residual = 0.0
    input_energy = 0.0
    device_energy = 0.0
    load_energy = 0.0
    for _ in range(steps):
        old_voltage = voltage
        voltage = (
            capacitance_F * old_voltage / dt
            + input_voltage_V / load_resistance_ohm
        ) / (
            capacitance_F / dt
            + 1.0 / load_resistance_ohm
            + 1.0 / device_resistance_ohm
        )
        device_current = voltage / device_resistance_ohm
        source_current = (input_voltage_V - voltage) / load_resistance_ohm
        residual = (
            capacitance_F * (voltage - old_voltage) / dt
            + device_current
            - source_current
        )
        maximum_residual = max(maximum_residual, abs(residual))
        input_energy += input_voltage_V * source_current * dt
        device_energy += voltage * device_current * dt
        load_energy += (input_voltage_V - voltage) * source_current * dt
    capacitor_energy = 0.5 * capacitance_F * voltage**2
    energy_residual = input_energy - device_energy - load_energy - capacitor_energy
    relative_energy_imbalance = abs(energy_residual) / max(
        abs(input_energy) + abs(device_energy) + abs(load_energy) + abs(capacitor_energy),
        1.0e-30,
    )
    return {
        "finite": bool(np.isfinite(voltage) and np.isfinite(relative_energy_imbalance)),
        "steps": steps,
        "dt_s": float(dt),
        "duration_s": float(duration_s),
        "final_voltage_V": float(voltage),
        "final_current_A": float(voltage / device_resistance_ohm),
        "maximum_current_residual_A": float(maximum_residual),
        "relative_circuit_energy_imbalance": float(relative_energy_imbalance),
    }
