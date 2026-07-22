from __future__ import annotations

import numpy as np
import pytest
from scipy.special import erfc, roots_legendre

from pinnpcm.physics.m43_thermal_spreading_reference import (
    steady_dimensionless_theta,
    transient_dimensionless_theta,
)


@pytest.mark.parametrize("rho", [1.0, 5.0])
def test_m43_green_reference_has_locked_early_and_long_limits(rho: float) -> None:
    early_Fo = 1.0e-8
    long_Fo = 1218.0
    early = transient_dimensionless_theta(rho, early_Fo)
    early_limit = 2.0 * np.sqrt(early_Fo / np.pi)
    assert early == pytest.approx(early_limit, rel=0.01)

    long = transient_dimensionless_theta(rho, long_Fo)
    steady = steady_dimensionless_theta(rho)
    assert long == pytest.approx(steady, rel=0.01)


@pytest.mark.parametrize("rho", [1.0, 5.0])
def test_m43_green_response_is_finite_monotone_nonnegative_and_bounded(
    rho: float,
) -> None:
    Fo_values = np.logspace(-8.0, np.log10(1218.0), 21)
    values = transient_dimensionless_theta(rho, Fo_values)
    assert isinstance(values, np.ndarray)
    assert np.all(np.isfinite(values))
    assert np.all(values >= 0.0)
    assert np.all(np.diff(values) >= -1.0e-12)
    assert np.all(values <= steady_dimensionless_theta(rho) * (1.0 + 1.0e-12))


@pytest.mark.parametrize("rho", [1.0, 5.0])
def test_m43_green_quadrature_refinement_is_below_preregistered_gate(
    rho: float,
) -> None:
    Fo_values = np.asarray([1.0e-8, 0.1, 1.0, 1218.0])
    base = transient_dimensionless_theta(
        rho, Fo_values, epsabs=1.0e-9, epsrel=1.0e-9
    )
    fine = transient_dimensionless_theta(
        rho, Fo_values, epsabs=1.0e-11, epsrel=1.0e-11
    )
    denominator = steady_dimensionless_theta(rho)
    assert np.max(np.abs(base - fine)) / denominator <= 1.0e-4


def test_m43_green_reference_is_transpose_invariant() -> None:
    Fo_values = np.asarray([1.0e-8, 0.1, 1.0, 1218.0])
    assert transient_dimensionless_theta(5.0, Fo_values) == pytest.approx(
        transient_dimensionless_theta(0.2, Fo_values), rel=1.0e-13
    )


@pytest.mark.parametrize(
    "Fo_A", [0.0, -1.0, np.nan, np.asarray([]), np.asarray([[1.0]])]
)
def test_m43_green_reference_rejects_invalid_fourier_inputs(Fo_A: object) -> None:
    with pytest.raises(ValueError):
        transient_dimensionless_theta(1.0, Fo_A)  # type: ignore[arg-type]



def _independent_tensor_gauss_green(rho: float, Fo_A: float, order: int = 240) -> float:
    """Cartesian overlap quadrature independent of the polar production path."""
    lx = 1.0 / np.sqrt(rho)
    ly = np.sqrt(rho)
    nodes, weights = roots_legendre(order)
    x = 0.5 * lx * (nodes + 1.0)
    y = 0.5 * ly * (nodes + 1.0)
    wx = 0.5 * lx * weights
    wy = 0.5 * ly * weights
    radius = np.sqrt(x[None, :] ** 2 + y[:, None] ** 2)
    overlap = (lx - x[None, :]) * (ly - y[:, None])
    kernel = erfc(radius / (2.0 * np.sqrt(Fo_A))) / radius
    return float(2.0 / np.pi * np.sum(wy[:, None] * wx[None, :] * overlap * kernel))


@pytest.mark.parametrize("Fo_A", [0.1, 1.0, 10.0])
def test_m43_green_midrange_matches_independent_cartesian_gauss(Fo_A: float) -> None:
    production = transient_dimensionless_theta(5.0, Fo_A, epsabs=1.0e-11, epsrel=1.0e-11)
    independent = _independent_tensor_gauss_green(5.0, Fo_A)
    assert production == pytest.approx(independent, rel=2.0e-4)
