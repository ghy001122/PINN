"""Source-scale port-equivalent mapping for the later 2.5-D route.

Batch 1 only certifies the algebraic mapping and its claim boundary.  It does
not execute a two-dimensional equilibrium or validate local current/Joule
distributions.
"""

from __future__ import annotations

import math


class SourceMappingError(ValueError):
    """Invalid geometry or resistance in the frozen port-equivalent mapping."""


def analytic_geometry_factor_m(
    *, length_m: float, width_m: float, thickness_m: float
) -> float:
    """Return ``W*t/L`` for a uniform rectangular conductor, in metres."""

    values = (length_m, width_m, thickness_m)
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise SourceMappingError("geometry dimensions must be finite and positive")
    return width_m * thickness_m / length_m


def device_effective_conductivity_S_m(
    *, device_resistance_ohm: float, geometry_factor_m: float
) -> float:
    """Map a device-effective S1 resistance to a distributed proxy."""

    values = (device_resistance_ohm, geometry_factor_m)
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise SourceMappingError(
            "resistance and geometry factor must be finite and positive"
        )
    return 1.0 / (geometry_factor_m * device_resistance_ohm)


def uniform_port_resistance_ohm(
    *, conductivity_S_m: float, geometry_factor_m: float
) -> float:
    """Return the exact uniform-conductor port resistance."""

    values = (conductivity_S_m, geometry_factor_m)
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise SourceMappingError(
            "conductivity and geometry factor must be finite and positive"
        )
    return 1.0 / (geometry_factor_m * conductivity_S_m)
