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


@dataclass(frozen=True)
class S2IntervalEnergyTerms:
    """Signed two-half-step energy terms for one accepted outer interval.

    These are energies, not averages of the two half-step relative residuals.
    The midpoint storage cancels because storage is evaluated directly between
    the outer initial and final states.  The backward-Euler numerical
    dissipation term is the existing circuit-capacitor term; the S2 thermal
    ledger has no additional numerical-dissipation term.
    """

    duration_s: float
    thermal_input_J: float
    explicit_plane_storage_J: float
    closure_storage_J: float
    vertical_sink_J: float
    lateral_boundary_outflow_J: float
    circuit_source_J: float
    load_resistor_dissipation_J: float
    capacitor_physical_energy_change_J: float
    capacitor_backward_euler_dissipation_J: float
    terminal_device_energy_J: float
    field_joule_energy_J: float


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


def build_s2_two_half_interval_ledgers(
    *,
    grid: GeoPhaseGrid,
    fields: S2ThermalFields,
    outer_initial_temperature_K: np.ndarray,
    outer_initial_device_voltage_V: float,
    first_half: object,
    second_half: object,
    half_dt_s: float,
    capacitance_F: float,
) -> tuple[S2LedgerBundle, S2IntervalEnergyTerms]:
    """Recompute all four ledgers from signed two-half-step energy terms.

    ``first_half`` and ``second_half`` are deliberately structural inputs: the
    controller supplies ordinary :class:`S2StepResult` objects, while focused
    tests can supply equivalent immutable fixtures.  No relative residual is
    averaged and no midpoint storage is counted twice.
    """

    if not np.isfinite([half_dt_s, capacitance_F]).all():
        raise ValueError("aggregate S2 ledger dt and capacitance must be finite")
    if half_dt_s <= 0.0 or capacitance_F <= 0.0:
        raise ValueError("aggregate S2 ledger dt and capacitance must be positive")
    fields.validate_grid(grid)
    initial_temperature = np.asarray(outer_initial_temperature_K, dtype=float)
    midpoint_temperature = np.asarray(
        first_half.state.temperature_K, dtype=float
    )
    final_temperature = np.asarray(second_half.state.temperature_K, dtype=float)
    if any(
        value.shape != grid.shape
        for value in (initial_temperature, midpoint_temperature, final_temperature)
    ):
        raise ValueError("aggregate S2 ledger temperatures must match the grid")
    scalar_values = np.asarray(
        [
            outer_initial_device_voltage_V,
            first_half.state.device_voltage_V,
            second_half.state.device_voltage_V,
        ],
        dtype=float,
    )
    if (
        not np.isfinite(initial_temperature).all()
        or not np.isfinite(midpoint_temperature).all()
        or not np.isfinite(final_temperature).all()
        or not np.isfinite(scalar_values).all()
    ):
        raise ValueError("aggregate S2 ledger state is nonfinite")

    duration = 2.0 * float(half_dt_s)
    area = grid.cell_area_m2
    temperature_increment = final_temperature - initial_temperature
    explicit_storage_J = float(
        np.sum(
            fields.explicit_areal_capacity_J_m2K
            * area
            * temperature_increment
        )
    )
    closure_storage_J = float(
        np.sum(
            fields.memory_areal_coefficient_J_m2K
            * area
            * temperature_increment
        )
    )
    effective_storage_J = float(
        np.sum(
            fields.effective_areal_capacity_J_m2K
            * area
            * temperature_increment
        )
    )
    if not np.isclose(
        effective_storage_J,
        explicit_storage_J + closure_storage_J,
        rtol=1.0e-12,
        atol=1.0e-18,
    ):
        raise ValueError("aggregate S2 storage decomposition is inconsistent")

    def half_sum(value: callable) -> float:
        return float(half_dt_s) * (
            float(value(first_half)) + float(value(second_half))
        )

    thermal_input_J = half_sum(lambda step: step.electrical.joule_power_W)
    vertical_sink_J = half_sum(
        lambda step: step.ledgers.storage.vertical_sink_power_W
    )
    lateral_outflow_J = half_sum(
        lambda step: step.ledgers.storage.lateral_boundary_outflow_W
    )
    circuit_source_J = half_sum(lambda step: step.ledgers.circuit.input_power_W)
    load_dissipation_J = half_sum(
        lambda step: step.ledgers.circuit.terms_W["load_resistor_power_W"]
    )
    capacitor_be_dissipation_J = half_sum(
        lambda step: step.ledgers.circuit.terms_W[
            "capacitor_backward_euler_dissipation_W"
        ]
    )
    terminal_device_J = half_sum(
        lambda step: step.electrical.terminal_device_power_W
    )
    field_joule_J = half_sum(lambda step: step.electrical.joule_power_W)
    initial_voltage = float(outer_initial_device_voltage_V)
    final_voltage = float(second_half.state.device_voltage_V)
    capacitor_physical_J = float(
        0.5 * capacitance_F * (final_voltage**2 - initial_voltage**2)
    )

    energy = S2IntervalEnergyTerms(
        duration_s=duration,
        thermal_input_J=thermal_input_J,
        explicit_plane_storage_J=explicit_storage_J,
        closure_storage_J=closure_storage_J,
        vertical_sink_J=vertical_sink_J,
        lateral_boundary_outflow_J=lateral_outflow_J,
        circuit_source_J=circuit_source_J,
        load_resistor_dissipation_J=load_dissipation_J,
        capacitor_physical_energy_change_J=capacitor_physical_J,
        capacitor_backward_euler_dissipation_J=capacitor_be_dissipation_J,
        terminal_device_energy_J=terminal_device_J,
        field_joule_energy_J=field_joule_J,
    )
    energy_values = np.asarray(list(energy.__dict__.values()), dtype=float)
    if not np.isfinite(energy_values).all():
        raise ValueError("aggregate S2 ledger contains nonfinite energy")

    storage = S2StorageRates(
        explicit_plane_storage_rate_W=explicit_storage_J / duration,
        closure_storage_rate_W=closure_storage_J / duration,
        effective_storage_rate_W=effective_storage_J / duration,
        vertical_sink_power_W=vertical_sink_J / duration,
        lateral_boundary_outflow_W=lateral_outflow_J / duration,
    )
    thermal = _balance(
        "s2_thermal_two_half_aggregate",
        thermal_input_J / duration,
        {
            "explicit_plane_storage_rate_W": explicit_storage_J / duration,
            "s2_closure_storage_rate_W": closure_storage_J / duration,
            "vertical_sink_power_W": vertical_sink_J / duration,
            "lateral_boundary_outflow_W": lateral_outflow_J / duration,
        },
    )
    circuit = _balance(
        "s2_circuit_two_half_aggregate",
        circuit_source_J / duration,
        {
            "load_resistor_power_W": load_dissipation_J / duration,
            "capacitor_physical_energy_rate_W": capacitor_physical_J / duration,
            "capacitor_backward_euler_dissipation_W": (
                capacitor_be_dissipation_J / duration
            ),
            "terminal_device_power_W": terminal_device_J / duration,
        },
    )
    combined = _balance(
        "s2_combined_electrothermal_two_half_aggregate",
        circuit_source_J / duration,
        {
            "load_resistor_power_W": load_dissipation_J / duration,
            "capacitor_physical_energy_rate_W": capacitor_physical_J / duration,
            "capacitor_backward_euler_dissipation_W": (
                capacitor_be_dissipation_J / duration
            ),
            "explicit_plane_storage_rate_W": explicit_storage_J / duration,
            "s2_closure_storage_rate_W": closure_storage_J / duration,
            "vertical_sink_power_W": vertical_sink_J / duration,
            "lateral_boundary_outflow_W": lateral_outflow_J / duration,
        },
    )
    device_power = _balance(
        "s2_device_power_two_half_aggregate",
        terminal_device_J / duration,
        {"field_joule_power_W": field_joule_J / duration},
    )
    return (
        S2LedgerBundle(
            storage=storage,
            thermal=thermal,
            circuit=circuit,
            combined=combined,
            device_power=device_power,
        ),
        energy,
    )


__all__ = [
    "S2ElectricalLedgerInput",
    "S2IntervalEnergyTerms",
    "S2LedgerBundle",
    "S2StorageRates",
    "build_s2_ledgers",
    "build_s2_two_half_interval_ledgers",
    "s2_storage_rates",
]
