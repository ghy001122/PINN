"""Independent half-space thermal-spreading references for M43.

The routines in this module implement the source contract locked for M43.  In
particular, they do not import or call any finite-volume grid, matrix, boundary,
or ledger implementation.

For a rectangle with full side lengths ``Lx`` and ``Ly`` and area ``A``, the
double source-area average of the half-space surface Green function can be
written as an overlap integral.  Scaling separation by ``sqrt(A)`` and using
polar coordinates reduces that overlap integral to one angular quadrature.  Its
radial moments are evaluated analytically, including a small-argument series to
avoid cancellation at long Fourier times.

All public resistances/impedances use SI units.  ``rho`` is the rectangle aspect
ratio and is canonicalized as ``max(rho, 1/rho)`` so transposing the rectangle
does not change the answer.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
from scipy.integrate import quad
from scipy.special import erf, erfc


_SQRT_PI = math.sqrt(math.pi)
_SMALL_MOMENT_ARGUMENT = 0.5


def _canonical_aspect_ratio(rho: float) -> float:
    value = float(rho)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("rho must be finite and positive")
    ratio = max(value, 1.0 / value)
    if not math.isfinite(ratio):
        raise ValueError("canonical rho must remain finite")
    return ratio


def _positive_finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def steady_dimensionless_theta(rho: float) -> float:
    """Return Yovanovich--Muzychka--Culham Eq. (21).

    The returned quantity is ``Theta = k*sqrt(A)*Rs`` for a uniform-isoflux
    rectangular source on an isotropic half-space.  ``Rs`` already is the
    spreading resistance; no one-dimensional resistance is added.
    """

    ratio = _canonical_aspect_ratio(rho)
    bracket = (
        math.asinh(1.0 / ratio)
        + math.asinh(ratio) / ratio
        + ratio
        / 3.0
        * (
            1.0
            + ratio**-3
            - (1.0 + ratio**-2) ** 1.5
        )
    )
    return math.sqrt(ratio) * bracket / math.pi


def spreading_resistance_K_W(
    rho: float,
    area_m2: float,
    thermal_conductivity_W_mK: float,
) -> float:
    """Return the source-mean half-space spreading resistance in K/W."""

    area = _positive_finite("area_m2", area_m2)
    conductivity = _positive_finite(
        "thermal_conductivity_W_mK", thermal_conductivity_W_mK
    )
    return steady_dimensionless_theta(rho) / (conductivity * math.sqrt(area))


def _erfc_moment(order: int, upper: float) -> float:
    """Evaluate ``integral_0^upper u**order*erfc(u) du`` stably.

    Orders zero through two are the only moments in the rectangular overlap
    polynomial.  Direct closed forms cancel at small ``upper`` (the long-time
    limit), so that regime uses the integrated Maclaurin series of ``erfc``.
    """

    if order not in (0, 1, 2):
        raise ValueError("only erfc moments of order 0, 1, and 2 are defined")
    z = float(upper)
    if not math.isfinite(z) or z < 0.0:
        raise ValueError("moment upper bound must be finite and non-negative")
    if z == 0.0:
        return 0.0

    if z < _SMALL_MOMENT_ARGUMENT:
        # erfc(u) = 1 - 2/sqrt(pi) * sum_m
        #   (-1)^m u^(2m+1)/(m! (2m+1)).
        term = z ** (order + 2) / (order + 2)
        series = term
        for index in range(100):
            term *= (
                -z**2
                / (index + 1)
                * (2 * index + 1)
                / (2 * index + 3)
                * (order + 2 * index + 2)
                / (order + 2 * index + 4)
            )
            series += term
            if abs(term) <= 2.0e-16 * max(1.0, abs(series)):
                break
        return z ** (order + 1) / (order + 1) - 2.0 * series / _SQRT_PI

    gaussian = math.exp(-(z**2))
    if order == 0:
        return z * float(erfc(z)) - math.expm1(-(z**2)) / _SQRT_PI
    if order == 1:
        return (
            0.5 * z**2 * float(erfc(z))
            + 0.25 * float(erf(z))
            - z * gaussian / (2.0 * _SQRT_PI)
        )
    return (
        z**3 * float(erfc(z)) / 3.0
        - math.expm1(-(z**2)) / (3.0 * _SQRT_PI)
        - z**2 * gaussian / (3.0 * _SQRT_PI)
    )


def _radial_erfc_moment(order: int, radius: float, Fo_A: float) -> float:
    scale = 2.0 * math.sqrt(Fo_A)
    return scale ** (order + 1) * _erfc_moment(order, radius / scale)


def _scalar_transient_theta(
    rho: float,
    Fo_A: float,
    *,
    epsabs: float,
    epsrel: float,
) -> float:
    ratio = _canonical_aspect_ratio(rho)
    fourier = _positive_finite("Fo_A", Fo_A)
    absolute_tolerance = _positive_finite("epsabs", epsabs)
    relative_tolerance = _positive_finite("epsrel", epsrel)

    # Full dimensionless side lengths: lx*ly = 1 and ly/lx = rho.
    lx = 1.0 / math.sqrt(ratio)
    ly = math.sqrt(ratio)
    corner_angle = math.atan(ratio)

    def angular_integrand(angle: float) -> float:
        cosine = math.cos(angle)
        sine = math.sin(angle)
        radial_limit = (
            lx / cosine if angle <= corner_angle else ly / sine
        )
        moment_0 = _radial_erfc_moment(0, radial_limit, fourier)
        moment_1 = _radial_erfc_moment(1, radial_limit, fourier)
        moment_2 = _radial_erfc_moment(2, radial_limit, fourier)
        return (
            moment_0
            - (ly * cosine + lx * sine) * moment_1
            + sine * cosine * moment_2
        )

    integrate: Callable[[float, float], float] = lambda lower, upper: float(
        quad(
            angular_integrand,
            lower,
            upper,
            epsabs=absolute_tolerance,
            epsrel=relative_tolerance,
            limit=100,
        )[0]
    )
    overlap_integral = integrate(0.0, corner_angle) + integrate(
        corner_angle, math.pi / 2.0
    )
    return 2.0 * overlap_integral / math.pi


def transient_dimensionless_theta(
    rho: float,
    Fo_A: float | np.ndarray,
    *,
    epsabs: float = 1.0e-9,
    epsrel: float = 1.0e-9,
) -> float | np.ndarray:
    """Return the source-averaged dimensionless Green step response.

    ``Fo_A = alpha*t/A`` and ``Theta(t) = k*sqrt(A)*Zth(t)``.  A scalar input
    returns ``float``; a one-dimensional array-like input returns an ndarray.
    No second time integration is performed because the erfc kernel already is
    the surface-flux step response.
    """

    values = np.asarray(Fo_A, dtype=float)
    if values.ndim > 1:
        raise ValueError("Fo_A must be a scalar or one-dimensional array")
    if values.size == 0:
        raise ValueError("Fo_A must not be empty")
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("Fo_A must contain only finite positive values")

    if values.ndim == 0:
        return _scalar_transient_theta(
            rho,
            float(values),
            epsabs=epsabs,
            epsrel=epsrel,
        )
    return np.asarray(
        [
            _scalar_transient_theta(
                rho,
                float(value),
                epsabs=epsabs,
                epsrel=epsrel,
            )
            for value in values
        ],
        dtype=float,
    )


def transient_impedance_K_W(
    rho: float,
    area_m2: float,
    thermal_conductivity_W_mK: float,
    thermal_diffusivity_m2_s: float,
    time_s: float | np.ndarray,
    *,
    epsabs: float = 1.0e-9,
    epsrel: float = 1.0e-9,
) -> float | np.ndarray:
    """Return the half-space source-mean thermal step impedance in K/W."""

    area = _positive_finite("area_m2", area_m2)
    conductivity = _positive_finite(
        "thermal_conductivity_W_mK", thermal_conductivity_W_mK
    )
    diffusivity = _positive_finite(
        "thermal_diffusivity_m2_s", thermal_diffusivity_m2_s
    )
    times = np.asarray(time_s, dtype=float)
    if times.ndim > 1:
        raise ValueError("time_s must be a scalar or one-dimensional array")
    if times.size == 0:
        raise ValueError("time_s must not be empty")
    if not np.all(np.isfinite(times)) or np.any(times <= 0.0):
        raise ValueError("time_s must contain only finite positive values")

    theta = transient_dimensionless_theta(
        rho,
        diffusivity * times / area,
        epsabs=epsabs,
        epsrel=epsrel,
    )
    impedance = np.asarray(theta) / (conductivity * math.sqrt(area))
    if times.ndim == 0:
        return float(impedance)
    return np.asarray(impedance, dtype=float)
