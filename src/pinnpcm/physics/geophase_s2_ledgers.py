"""S2-specific energy ledgers for the Phase 1-v2 reference solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_ledgers import (
    LedgerBalance,
    circuit_ledger,
    device_power_identity,
)
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields


class S2ElectricalLedgerInput(Protocol):
    source_current_A: float
    terminal_device_power_W: float
    joule_power_W: float


@dataclass(frozen=True)
class S2StorageRates:
    explicit_plane_storage_rate_W: float
    closure_storage_rate_W: float
    effective_storage_rate_W: float
    vertical_sink_power_W: float
    lateral_boundary_outflow_W: float


@dataclass(frozen=True)
class S2LedgerBundle:
    storage: S2StorageRates
    thermal: LedgerBalance
    circuit: LedgerBalance
    combined: LedgerBalance
    device_power: LedgerBalance


def _balance(name: str, input_power_W: float, terms_W: dict[str, float]) -> LedgerBalance:
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


def s2_storage_rates(
    *,
    grid: GeoPhaseGrid,
    fields: S2ThermalFields,
    old_temperature_K: np.ndarray,
    new_temperature_K: np.ndarray,
    dt_s: float,
    lateral_boundary_outflow_W: float,
) -> S2StorageRates:
    """Evaluate actual S2 state storage exactly once, with a diagnostic split."""

    fields.validate_grid(grid)
    old = np.asarray(old_temperature_K, dtype=float)
    new = np.asarray(new_temperature_K, dtype=float)
    if old.shape != grid.shape or new.shape != grid.shape:
        raise ValueError("S2 ledger temperature arrays must match the grid")
    if not np.isfinite(old).all() or not np.isfinite(new).all():
        raise ValueError("S2 ledger temperatures must be finite")
    if not np.isfinite(dt_s) or dt_s <= 0.0:
        raise ValueError("S2 ledger dt must be finite and positive")
    delta_rate = (new - old) / dt_s
    area = grid.cell_area_m2
    explicit = float(
        np.sum(fields.explicit_areal_capacity_J_m2K * area * delta_rate)
    )
    closure = float(
        np.sum(fields.memory_areal_coefficient_J_m2K * area * delta_rate)
    )
    effective = float(
        np.sum(fields.effective_areal_capacity_J_m2K * area * delta_rate)
    )
    if not np.isclose(effective, explicit + closure, rtol=1.0e-12, atol=1.0e-18):
        raise ValueError("S2 storage decomposition double-counted or omitted capacity")
    sink = float(
        np.sum(
            fields.vertical_conductance_W_m2K
            * area
            * (new - fields.ambient_temperature_K)
        )
    )
    return S2StorageRates(
        explicit_plane_storage_rate_W=explicit,
        closure_storage_rate_W=closure,
        effective_storage_rate_W=effective,
        vertical_sink_power_W=sink,
        lateral_boundary_outflow_W=float(lateral_boundary_outflow_W),
    )


def build_s2_ledgers(
    *,
    grid: GeoPhaseGrid,
    fields: S2ThermalFields,
    old_temperature_K: np.ndarray,
    new_temperature_K: np.ndarray,
    old_device_voltage_V: float,
    new_device_voltage_V: float,
    input_voltage_V: float,
    load_resistance_ohm: float,
    capacitance_F: float,
    dt_s: float,
    electrical: S2ElectricalLedgerInput,
    lateral_boundary_outflow_W: float,
) -> S2LedgerBundle:
    """Build thermal, circuit, combined, and device-power S2 ledgers."""

    storage = s2_storage_rates(
        grid=grid,
        fields=fields,
        old_temperature_K=old_temperature_K,
        new_temperature_K=new_temperature_K,
        dt_s=dt_s,
        lateral_boundary_outflow_W=lateral_boundary_outflow_W,
    )
    thermal = _balance(
        "s2_thermal",
        electrical.joule_power_W,
        {
            "explicit_plane_storage_rate_W": storage.explicit_plane_storage_rate_W,
            "s2_closure_storage_rate_W": storage.closure_storage_rate_W,
            "vertical_sink_power_W": storage.vertical_sink_power_W,
            "lateral_boundary_outflow_W": storage.lateral_boundary_outflow_W,
        },
    )
    circuit = circuit_ledger(
        input_voltage_V=input_voltage_V,
        old_device_voltage_V=old_device_voltage_V,
        new_device_voltage_V=new_device_voltage_V,
        load_resistance_ohm=load_resistance_ohm,
        capacitance_F=capacitance_F,
        device_current_A=electrical.source_current_A,
        dt_s=dt_s,
    )
    source_current = (input_voltage_V - new_device_voltage_V) / load_resistance_ohm
    source_power = input_voltage_V * source_current
    voltage_increment = new_device_voltage_V - old_device_voltage_V
    combined = _balance(
        "s2_combined_electrothermal",
        source_power,
        {
            "load_resistor_power_W": source_current**2 * load_resistance_ohm,
            "capacitor_physical_energy_rate_W": 0.5
            * capacitance_F
            * (new_device_voltage_V**2 - old_device_voltage_V**2)
            / dt_s,
            "capacitor_backward_euler_dissipation_W": 0.5
            * capacitance_F
            * voltage_increment**2
            / dt_s,
            "explicit_plane_storage_rate_W": storage.explicit_plane_storage_rate_W,
            "s2_closure_storage_rate_W": storage.closure_storage_rate_W,
            "vertical_sink_power_W": storage.vertical_sink_power_W,
            "lateral_boundary_outflow_W": storage.lateral_boundary_outflow_W,
        },
    )
    power = device_power_identity(
        terminal_device_power_W=electrical.terminal_device_power_W,
        field_joule_power_W=electrical.joule_power_W,
    )
    return S2LedgerBundle(
        storage=storage,
        thermal=thermal,
        circuit=circuit,
        combined=combined,
        device_power=power,
    )
