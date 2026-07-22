from __future__ import annotations

import numpy as np
import pytest

from pinnpcm.physics.m43_thermal_spreading_reference import (
    spreading_resistance_K_W,
    steady_dimensionless_theta,
    transient_impedance_K_W,
)


def test_m43_eq21_golden_values_and_rectangle_transpose() -> None:
    assert steady_dimensionless_theta(1.0) == pytest.approx(
        0.47320100440933854, rel=1.0e-14
    )
    assert steady_dimensionless_theta(5.0) == pytest.approx(
        0.4082084030088908, rel=1.0e-14
    )
    assert steady_dimensionless_theta(0.2) == pytest.approx(
        steady_dimensionless_theta(5.0), rel=1.0e-15
    )


def test_m43_spreading_resistance_has_required_si_scaling() -> None:
    base = spreading_resistance_K_W(5.0, 5.0e-14, 35.0)
    assert base > 0.0
    assert spreading_resistance_K_W(5.0, 20.0e-14, 35.0) == pytest.approx(
        base / 2.0, rel=1.0e-14
    )
    assert spreading_resistance_K_W(5.0, 5.0e-14, 70.0) == pytest.approx(
        base / 2.0, rel=1.0e-14
    )
    for power in (0.25, 3.0):
        temperature_rise = power * base
        assert temperature_rise / power == pytest.approx(base, rel=1.0e-15)


def test_m43_dimensional_early_time_limit_uses_full_area_and_power() -> None:
    rho = 5.0
    area = 5.0e-14
    conductivity = 35.0
    diffusivity = 35.0 / 3.0e6
    power = 1.7
    Fo_A = 1.0e-8
    time = Fo_A * area / diffusivity
    impedance = transient_impedance_K_W(
        rho, area, conductivity, diffusivity, time
    )
    heat_flux = power / area
    expected_delta_T = (
        2.0
        * heat_flux
        * np.sqrt(diffusivity * time / np.pi)
        / conductivity
    )
    assert power * impedance == pytest.approx(expected_delta_T, rel=0.01)


def test_m43_transient_impedance_respects_geometric_similarity() -> None:
    rho = 5.0
    area = 5.0e-14
    conductivity = 35.0
    diffusivity = 35.0 / 3.0e6
    time = 1.0e-8
    base = transient_impedance_K_W(
        rho, area, conductivity, diffusivity, time
    )
    scaled = transient_impedance_K_W(
        rho, 4.0 * area, conductivity, diffusivity, 4.0 * time
    )
    assert scaled == pytest.approx(base / 2.0, rel=1.0e-12)

    vector = transient_impedance_K_W(
        rho,
        area,
        conductivity,
        diffusivity,
        np.asarray([time, 2.0 * time]),
    )
    assert isinstance(vector, np.ndarray)
    assert vector.shape == (2,)
    assert vector[0] == pytest.approx(base, rel=1.0e-13)


@pytest.mark.parametrize(
    ("rho", "area", "conductivity"),
    [(0.0, 1.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, -1.0)],
)
def test_m43_steady_reference_rejects_nonphysical_inputs(
    rho: float, area: float, conductivity: float
) -> None:
    with pytest.raises(ValueError):
        spreading_resistance_K_W(rho, area, conductivity)


def test_m43_reference_rejects_overflowing_canonical_aspect_ratio() -> None:
    with pytest.raises(ValueError):
        steady_dimensionless_theta(1.0e-320)
