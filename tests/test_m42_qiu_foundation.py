from __future__ import annotations

import pytest

from pinnpcm.physics.m42_qiu_foundation import (
    run_fixed_resistance_rc,
    series_electrical_ledger,
    source_resistance_mapping_error,
    thermal_diffusion_length_m,
)


def test_m42_scale_and_electrical_ledgers_are_dimensionally_consistent() -> None:
    length = thermal_diffusion_length_m(35.0, 3.0e6, 5.22e-6)
    assert length == pytest.approx(7.803845206050667e-6, rel=1.0e-12)
    ledger = series_electrical_ledger(1.0, 51771.43320189423, 260.0)
    assert ledger.relative_current_imbalance == 0.0
    assert ledger.relative_power_imbalance <= 1.0e-15
    assert source_resistance_mapping_error(120639.51284927833, 51771.43320189423) > 1.0


def test_m42_fixed_resistance_circuit_closes_without_device_claim() -> None:
    result = run_fixed_resistance_rc(
        input_voltage_V=12.0,
        load_resistance_ohm=1.2e4,
        device_resistance_ohm=51771.43320189423,
        capacitance_F=1.45e-10,
        duration_s=3.0 * 1.2e4 * 1.45e-10,
        dt_s=1.2e4 * 1.45e-10 / 20.0,
    )
    assert result["finite"] is True
    assert result["maximum_current_residual_A"] <= 1.0e-15
    assert result["relative_circuit_energy_imbalance"] <= 0.03
