"""Behavioral tests for M40R history, thermal ledger, and multirate transient."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.physics.qiu_vo2_device import (
    QiuCircuit,
    QiuGeometry,
    QiuHysteresis,
    build_qiu_domain_masks,
    major_loop_targets,
    material_property_fields,
)
from pinnpcm.solvers.m40r_qiu_e0_repair import (
    ExcessTemperatureIntegrator,
    advance_history_zero_drive_invariant,
    compare_active_transients,
    run_active_transient,
)
from scripts.run_m40r_qiu_e0_repair import _transient_gate_results


def _configs() -> tuple[dict, dict]:
    repair = yaml.safe_load(Path("configs/m40r_qiu_e0_repair.yaml").read_text(encoding="utf-8"))
    parent = yaml.safe_load(Path(repair["parent_m40_config"]).read_text(encoding="utf-8"))
    return repair, parent


def test_history_is_exactly_invariant_without_temperature_drive() -> None:
    _, parent = _configs()
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    temperature = np.array([325.0, 332.8, 345.0])
    history = np.array([0.1, 0.5, 0.9])
    updated = advance_history_zero_drive_invariant(
        temperature, temperature.copy(), history, 2.0e-9, hysteresis
    )

    assert np.array_equal(updated, history)


def test_history_update_is_bounded_and_directional() -> None:
    _, parent = _configs()
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    old_temperature = np.array([332.8, 332.8])
    old_history = np.array([0.5, 0.5])
    heating = advance_history_zero_drive_invariant(
        old_temperature, old_temperature + 2.0, old_history, 1.0e-9, hysteresis
    )
    cooling = advance_history_zero_drive_invariant(
        old_temperature, old_temperature - 2.0, old_history, 1.0e-9, hysteresis
    )

    assert np.all((0.0 <= heating) & (heating <= 1.0))
    assert np.all((0.0 <= cooling) & (cooling <= 1.0))
    assert np.all(heating > cooling)


def test_excess_temperature_ledger_closes_at_zero_and_small_source() -> None:
    _, parent = _configs()
    geometry = QiuGeometry.from_mapping(parent["geometry"])
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    circuit = QiuCircuit.from_mapping(parent["circuit"])
    mesh = build_qiu_domain_masks(geometry, 1)
    temperature = np.full(mesh.shape, circuit.ambient_temperature_K)
    history, _ = major_loop_targets(temperature, hysteresis)
    _, k, rho_cp = material_property_fields(
        mesh, temperature, history, geometry, hysteresis, parent["materials"]
    )
    thermal = ExcessTemperatureIntegrator(
        mesh,
        k,
        rho_cp,
        circuit.ambient_temperature_K,
        parent["interfaces"]["bottom_conductance_W_K"],
    )
    zero = thermal.step(temperature, np.zeros(mesh.shape), 1.0e-9)
    heat = np.zeros(mesh.shape)
    heat[mesh.material == "vo2"] = 1.0e-12 / np.count_nonzero(mesh.material == "vo2")
    small = thermal.step(temperature, heat, 1.0e-9)

    assert np.nanmax(abs(zero.temperature_K - circuit.ambient_temperature_K)) <= 1.0e-12
    assert zero.relative_energy_imbalance == 0.0
    assert small.relative_energy_imbalance <= 1.0e-8


def test_shortened_rc_fixture_runs_to_exact_three_time_constants() -> None:
    repair, parent = _configs()
    geometry = QiuGeometry.from_mapping(parent["geometry"])
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    circuit = replace(
        QiuCircuit.from_mapping(parent["circuit"]),
        parallel_capacitance_F=1.0e-14,
        input_voltage_V=0.1,
    )
    profile = {
        "refinement": 1,
        "smooth_dt_max_s": 5.0e-11,
        "switching_dt_max_s": 2.5e-11,
        "history_substep_max_s": 2.5e-11,
    }
    active = repair["active_transient"]
    controls = {**active, **active["activity"]}
    controls["minimum_dt_s"] = 5.0e-12
    controls["picard_max_iterations"] = 6
    result = run_active_transient(
        geometry=geometry,
        hysteresis=hysteresis,
        circuit=circuit,
        materials=parent["materials"],
        electrical_contacts={
            ("vo2", "ti"): parent["interfaces"]["electrical_contact_resistance_m2_ohm"]["vo2_ti"]
        },
        thermal_contacts={},
        bottom_conductance_W_K=parent["interfaces"]["bottom_conductance_W_K"],
        profile=profile,
        controls=controls,
        maximum_steps=1000,
        maximum_reject_fraction=0.25,
    )
    metrics = result["metrics"]

    assert metrics["finite"] is True
    assert metrics["duration_Rload_C_multiple"] == pytest.approx(3.0, rel=1.0e-12)
    assert metrics["maximum_rc_residual_A"] <= 1.0e-12
    assert metrics["nominal_smooth_max_energy_imbalance"] <= 1.0e-4


def test_raw_time_fine_pair_metrics_use_locked_qoi_definitions() -> None:
    fine = {
        "time_s": np.array([0.0, 1.0, 2.0]),
        "current_A": np.array([0.0, 1.0, 0.0]),
        "metrics": {
            "Tmax_K": 335.0,
            "Tmean_time_average_K": 330.0,
            "cumulative_outward_heat_J": 2.0,
        },
    }
    coarse = {
        "time_s": np.array([0.0, 1.0, 2.0]),
        "current_A": np.array([0.0, 0.9, 0.0]),
        "metrics": {
            "Tmax_K": 334.0,
            "Tmean_time_average_K": 329.5,
            "cumulative_outward_heat_J": 1.9,
        },
    }
    metrics = compare_active_transients(
        coarse, fine, ambient_temperature_K=325.0, comparison_grid_points=3
    )

    assert metrics["current_raw_time_rms_nrmse"] == pytest.approx(0.1)
    assert metrics["Tmax_rise_relative_change"] == pytest.approx(0.1)
    assert metrics["Tmean_rise_relative_change"] == pytest.approx(0.1)
    assert metrics["cumulative_outward_heat_relative_change"] == pytest.approx(0.05)


def test_source_R_T_domain_extrapolation_fails_closed() -> None:
    repair, _ = _configs()
    values = {
        "nominal_transient_finite": True,
        "nominal_duration_Rload_C_multiple": 3.0,
        "nominal_Tmax_K": 361.0,
        "critical_temperature_K": 332.8,
        "source_R_T_domain_max_K": 360.0,
        "nominal_h_range": 0.2,
        "transient_current_nrmse": 0.0,
        "transient_Tmax_relative_change": 0.0,
        "transient_Tmean_relative_change": 0.0,
        "transient_outward_heat_relative_change": 0.0,
        "nominal_smooth_energy_imbalance": 0.0,
        "nominal_switching_energy_imbalance": 0.0,
        "nominal_switching_window_exercised": True,
    }
    gates = _transient_gate_results(values, repair["gates"])

    assert gates["nominal_within_source_R_T_domain"] is False
    assert all(
        passed
        for name, passed in gates.items()
        if name != "nominal_within_source_R_T_domain"
    )
