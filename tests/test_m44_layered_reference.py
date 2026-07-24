from __future__ import annotations

import numpy as np
import pytest

from pinnpcm.physics.m44_layered_thermal_reference import (
    layered_modal_step_response_K_W,
    max_normalized_response_change,
    single_slab_surface_step_impedance_K_W,
    steady_series_resistance_K_W,
)


def test_m44_layered_steady_series_resistance_and_scaling() -> None:
    thicknesses = np.asarray([2.0e-7, 5.0e-7])
    conductivities = np.asarray([4.0, 20.0])
    area = 3.0e-12
    expected = (2.0e-7 / 4.0 + 5.0e-7 / 20.0) / area
    resistance = steady_series_resistance_K_W(
        thicknesses,
        conductivities,
        area_m2=area,
    )
    assert resistance == pytest.approx(expected, rel=1.0e-14)
    assert steady_series_resistance_K_W(
        2.0 * thicknesses,
        conductivities,
        area_m2=4.0 * area,
    ) == pytest.approx(0.5 * resistance, rel=1.0e-14)


def test_m44_single_slab_modal_response_recovers_analytic_series() -> None:
    thickness = 2.0e-6
    conductivity = 7.0
    capacity = 2.8e6
    area = 4.0e-10
    diffusivity = conductivity / capacity
    fourier_times = np.logspace(-3.0, 1.0, 13)
    times = fourier_times * thickness**2 / diffusivity

    analytic = single_slab_surface_step_impedance_K_W(
        thickness,
        conductivity,
        capacity,
        times,
        area_m2=area,
        series_terms=800,
    )
    modal = layered_modal_step_response_K_W(
        [thickness],
        [conductivity],
        [capacity],
        [320],
        times,
        area_m2=area,
    )
    steady = thickness / (conductivity * area)
    normalized_error = np.max(np.abs(modal.top_impedance_K_W - analytic)) / steady
    assert normalized_error <= 2.0e-3
    assert modal.steady_top_resistance_K_W == pytest.approx(steady, rel=1.0e-12)


def test_m44_layered_modal_response_is_physical_and_exact_at_steady_limit() -> None:
    thicknesses = np.asarray([4.0e-8, 1.5e-8, 1.0e-7, 3.0e-6])
    conductivities = np.asarray([317.0, 21.9, 4.0, 35.0])
    capacities = np.asarray([2.49e6, 2.35e6, 3.07e6, 3.0e6])
    times = np.logspace(-12.0, -3.0, 25)
    response = layered_modal_step_response_K_W(
        thicknesses,
        conductivities,
        capacities,
        [8, 4, 8, 64],
        times,
        area_m2=5.0e-14,
    )

    assert np.all(np.isfinite(response.temperature_impedance_K_W))
    assert np.all(response.eigenvalues_s_inv > 0.0)
    assert np.all(response.top_impedance_K_W >= 0.0)
    assert np.all(np.diff(response.top_impedance_K_W) >= -1.0e-9)
    assert np.all(response.top_impedance_K_W <= response.steady_top_resistance_K_W)
    assert response.top_impedance_K_W[-1] == pytest.approx(
        response.steady_top_resistance_K_W,
        rel=1.0e-10,
    )
    assert np.all(response.temperature_impedance_K_W[:, -1] == 0.0)


def test_m44_preregistered_layered_reference_self_refines_below_gate() -> None:
    thicknesses = np.asarray([4.0e-8, 1.5e-8, 1.0e-7, 3.121538082420267e-5])
    conductivities = np.asarray([317.0, 21.9, 4.0, 35.0])
    capacities = np.asarray([2.49e6, 2.35e6, 3.07e6, 3.0e6])
    times = np.asarray(
        [1.0e-10, 3.0e-10, 1.0e-9, 3.0e-9, 1.0e-8, 3.0e-8, 1.0e-7,
         3.0e-7, 1.0e-6]
    )
    area = 5.0e-14
    base = layered_modal_step_response_K_W(
        thicknesses,
        conductivities,
        capacities,
        [16, 8, 8, 96],
        times,
        area_m2=area,
    )
    fine = layered_modal_step_response_K_W(
        thicknesses,
        conductivities,
        capacities,
        [32, 16, 16, 192],
        times,
        area_m2=area,
    )
    change = max_normalized_response_change(
        base.top_impedance_K_W,
        fine.top_impedance_K_W,
        fine.steady_top_resistance_K_W,
    )
    assert change <= 0.002


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (([1.0], [1.0, 2.0], [1.0], [2], [1.0]), "equal length"),
        (([1.0], [-1.0], [1.0], [2], [1.0]), "positive"),
        (([1.0], [1.0], [1.0], [0], [1.0]), "positive integers"),
        (([1.0], [1.0], [1.0], [2], [1.0, 1.0]), "strictly increasing"),
    ],
)
def test_m44_layered_reference_rejects_invalid_contract_inputs(
    arguments: tuple[object, object, object, object, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        layered_modal_step_response_K_W(*arguments)


def test_m44_response_change_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="shape matched"):
        max_normalized_response_change([1.0, 2.0], [1.0], 3.0)
