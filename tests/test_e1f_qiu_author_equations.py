"""Equation-contract tests for the Qiu-2024 source-constrained model."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

import pinnpcm.physics.qiu_author_compact_model as qiu_model
from pinnpcm.physics.qiu_author_compact_model import (
    compact_rhs,
    default_parameters,
    dynamic_resistance_ohm,
    initialize_ledger,
    insulating_fraction,
    load_parameters,
    major_branch_insulating_fraction,
    proximity_temperature_from_reversal,
    quasistatic_resistance_ohm,
    update_ledger_at_reversal,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "e1f_qiu_author_external_anchor.yaml"


def test_locked_source_parameters_load_from_preregistration() -> None:
    params = load_parameters(CONFIG)
    defaults = default_parameters()

    assert params == defaults
    assert params.resistance_prefactor_ohm == pytest.approx(5.359e-3)
    assert params.metallic_resistance_ohm == pytest.approx(262.5)
    assert params.activation_temperature_K == pytest.approx(5220.0)
    assert params.beta_per_K == pytest.approx(0.253)
    assert params.hysteresis_width_K == pytest.approx(7.193)
    assert params.critical_temperature_K == pytest.approx(332.8)
    assert params.proximity_gamma_dimensionless == pytest.approx(0.956)
    assert params.dynamic_metallic_factor == pytest.approx(4.90)
    assert params.parallel_capacitance_F == pytest.approx(145.0e-12)
    assert params.thermal_conductance_W_per_K == pytest.approx(0.206e-3)
    assert params.thermal_capacitance_J_per_K == pytest.approx(49.6e-12)
    assert params.thermal_time_constant_s == pytest.approx(240.776699e-9)


def test_equations_s1_s2_and_s7_match_direct_major_branch_evaluation() -> None:
    params = default_parameters()
    ledger = initialize_ledger(params)
    temperature = np.asarray([325.0, params.critical_temperature_K, 345.0])

    heating = np.asarray(major_branch_insulating_fraction(temperature, 1, params))
    cooling = np.asarray(major_branch_insulating_fraction(temperature, -1, params))
    expected_heating = 0.5 + 0.5 * np.tanh(
        params.beta_per_K
        * (
            params.hysteresis_width_K / 2.0
            + params.critical_temperature_K
            - temperature
        )
    )
    assert np.allclose(heating, expected_heating, rtol=0.0, atol=1.0e-15)
    assert np.all(heating > cooling)

    static_resistance = np.asarray(quasistatic_resistance_ohm(temperature, ledger, params))
    dynamic_resistance = np.asarray(dynamic_resistance_ohm(temperature, ledger, params))
    assert np.allclose(
        dynamic_resistance - static_resistance,
        (params.dynamic_metallic_factor - 1.0) * params.metallic_resistance_ohm,
        rtol=1.0e-13,
        atol=1.0e-10,
    )


def test_llp_reversal_updates_only_the_ledger_with_literal_equation_s3() -> None:
    params = default_parameters()
    before = initialize_ledger(params)
    reversal_temperature = 340.0
    fraction_before = float(insulating_fraction(reversal_temperature, before, params))

    after = update_ledger_at_reversal(reversal_temperature, before, params)
    assert before.delta == 1
    assert not before.reversed_once
    assert after.delta == -1
    assert after.reversed_once
    assert after.reversal_temperature_K == pytest.approx(reversal_temperature)
    assert after.reversal_fraction == pytest.approx(fraction_before)
    expected_t_pr = (
        -params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - (2.0 * fraction_before - 1.0) / params.beta_per_K
        - reversal_temperature
    )
    assert after.proximity_temperature_K == pytest.approx(expected_t_pr)
    # The frozen source ledger remains unchanged.
    assert before == initialize_ledger(params)


def test_equations_s5_s6_rhs_is_pure_and_matches_manual_formula() -> None:
    params = default_parameters()
    ledger = initialize_ledger(params)
    state = np.asarray([5.0, 335.0])
    ledger_before = ledger.to_dict()

    first = compact_rhs(
        1.0e-6,
        state,
        params=params,
        input_voltage_V=12.0,
        ledger=ledger,
    )
    second = compact_rhs(
        2.0e-6,
        state,
        params=params,
        input_voltage_V=12.0,
        ledger=ledger,
    )
    resistance = float(dynamic_resistance_ohm(state[1], ledger, params))
    expected_voltage = 12.0 / (
        params.load_resistance_ohm * params.parallel_capacitance_F
    ) - state[0] * (
        1.0 / (resistance * params.parallel_capacitance_F)
        + 1.0 / (params.load_resistance_ohm * params.parallel_capacitance_F)
    )
    expected_temperature = state[0] ** 2 / (
        resistance * params.thermal_capacitance_J_per_K
    ) - params.thermal_conductance_W_per_K * (
        state[1] - params.ambient_temperature_K
    ) / params.thermal_capacitance_J_per_K

    assert np.array_equal(first, second)
    assert first[0] == pytest.approx(expected_voltage)
    assert first[1] == pytest.approx(expected_temperature)
    assert ledger.to_dict() == ledger_before


@pytest.mark.parametrize("fraction", [-0.1, 1.1, np.nan])
def test_equation_s3_rejects_nonphysical_fraction_without_clipping(
    fraction: float,
) -> None:
    params = default_parameters()
    with pytest.raises(ValueError, match="fraction in"):
        proximity_temperature_from_reversal(1, fraction, 335.0, params)


@pytest.mark.parametrize("fraction", [0.0, 0.5, 1.0])
def test_equation_s3_accepts_source_domain_endpoints(fraction: float) -> None:
    params = default_parameters()
    value = proximity_temperature_from_reversal(1, fraction, 335.0, params)
    expected = (
        params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - (2.0 * fraction - 1.0) / params.beta_per_K
        - 335.0
    )
    assert value == pytest.approx(expected)


def test_invalid_temperature_is_rejected_instead_of_silently_clipped() -> None:
    params = default_parameters()
    ledger = initialize_ledger(params)
    with pytest.raises(ValueError, match="strictly positive"):
        dynamic_resistance_ohm(0.0, ledger, params)
    with pytest.raises(ValueError, match="strictly positive"):
        compact_rhs(
            0.0,
            np.asarray([0.0, -1.0]),
            params=params,
            input_voltage_V=12.0,
            ledger=ledger,
        )


def test_qiu_author_model_has_no_m40_or_local_conductivity_import() -> None:
    source_path = Path(qiu_model.__file__).resolve()
    syntax = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden = ("qiu_vo2_device", "m40", "m40r", "local_conductivity")
    assert not any(
        token in module.lower() for module in imported_modules for token in forbidden
    )
