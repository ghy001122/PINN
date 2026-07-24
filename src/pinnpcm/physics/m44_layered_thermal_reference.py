"""Independent one-dimensional layered thermal reference for M44.

This module deliberately shares no grid, matrix assembly, or time integrator
with the M44 three-dimensional finite-volume solver.  It assembles a linear
one-dimensional finite-element method-of-lines model with lumped capacity and
uses a symmetric modal decomposition for exact-in-time propagation of the
resulting semidiscrete system.

The coordinate runs from the heated top surface to a fixed-temperature bottom
surface.  The top is driven by a spatially uniform step heat flux.  All public
quantities use SI units and the returned temperature response is normalized by
the total applied power, so it is a thermal impedance in K/W.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class LayeredModalResponse:
    """Exact modal response of the independent semidiscrete reference."""

    times_s: np.ndarray
    node_positions_m: np.ndarray
    temperature_impedance_K_W: np.ndarray
    top_impedance_K_W: np.ndarray
    steady_top_resistance_K_W: float
    eigenvalues_s_inv: np.ndarray
    lumped_capacities_J_K: np.ndarray


def _positive_finite_array(name: str, values: object) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
        raise ValueError(f"{name} must contain only finite positive values")
    return array


def _positive_finite_scalar(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _validated_elements_per_layer(
    elements_per_layer: object,
    number_of_layers: int,
) -> np.ndarray:
    raw = np.asarray(elements_per_layer)
    if raw.ndim != 1 or raw.size != number_of_layers:
        raise ValueError("elements_per_layer must have one entry per layer")
    if not np.issubdtype(raw.dtype, np.integer):
        as_float = np.asarray(raw, dtype=float)
        if not np.all(np.isfinite(as_float)) or not np.all(
            as_float == np.floor(as_float)
        ):
            raise ValueError("elements_per_layer must contain integers")
        raw = as_float.astype(int)
    counts = np.asarray(raw, dtype=int)
    if np.any(counts <= 0):
        raise ValueError("elements_per_layer must contain positive integers")
    return counts


def steady_series_resistance_K_W(
    layer_thicknesses_m: object,
    thermal_conductivities_W_mK: object,
    *,
    area_m2: float = 1.0,
) -> float:
    """Return the exact steady one-dimensional series resistance in K/W."""

    thicknesses = _positive_finite_array(
        "layer_thicknesses_m", layer_thicknesses_m
    )
    conductivities = _positive_finite_array(
        "thermal_conductivities_W_mK", thermal_conductivities_W_mK
    )
    if thicknesses.size != conductivities.size:
        raise ValueError("thickness and conductivity arrays must have equal length")
    area = _positive_finite_scalar("area_m2", area_m2)
    return float(np.sum(thicknesses / conductivities) / area)


def single_slab_surface_step_impedance_K_W(
    thickness_m: float,
    thermal_conductivity_W_mK: float,
    volumetric_heat_capacity_J_m3K: float,
    times_s: object,
    *,
    area_m2: float = 1.0,
    series_terms: int = 400,
) -> np.ndarray:
    r"""Return the analytic fixed-bottom single-slab surface step response.

    For a slab with an insulated-flux top and fixed-temperature bottom,

    .. math::

       Z(t)=\frac{L}{kA}\left[1-\frac{8}{\pi^2}
       \sum_{n=0}^{\infty}\frac{\exp[-(2n+1)^2\pi^2\alpha t/(4L^2)]}
       {(2n+1)^2}\right].

    This series is independent of the finite-element modal implementation and
    is used only as a manufactured analytic limit.
    """

    thickness = _positive_finite_scalar("thickness_m", thickness_m)
    conductivity = _positive_finite_scalar(
        "thermal_conductivity_W_mK", thermal_conductivity_W_mK
    )
    capacity = _positive_finite_scalar(
        "volumetric_heat_capacity_J_m3K",
        volumetric_heat_capacity_J_m3K,
    )
    area = _positive_finite_scalar("area_m2", area_m2)
    times = _positive_finite_array("times_s", times_s)
    if not isinstance(series_terms, int) or series_terms <= 0:
        raise ValueError("series_terms must be a positive integer")

    alpha = conductivity / capacity
    odd = 2.0 * np.arange(series_terms, dtype=float) + 1.0
    decay = np.exp(
        -np.outer(
            times,
            odd**2 * math.pi**2 * alpha / (4.0 * thickness**2),
        )
    )
    normalized = 1.0 - 8.0 / math.pi**2 * np.sum(
        decay / odd[None, :] ** 2,
        axis=1,
    )
    resistance = thickness / (conductivity * area)
    return resistance * normalized


def _assemble_layered_matrices(
    thicknesses: np.ndarray,
    conductivities: np.ndarray,
    capacities: np.ndarray,
    counts: np.ndarray,
    area_m2: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Assemble independent 1D FE stiffness and lumped capacity matrices."""

    number_of_nodes = int(np.sum(counts)) + 1
    stiffness = np.zeros((number_of_nodes, number_of_nodes), dtype=float)
    lumped_capacity = np.zeros(number_of_nodes, dtype=float)
    positions = np.empty(number_of_nodes, dtype=float)
    positions[0] = 0.0

    node = 0
    coordinate = 0.0
    for thickness, conductivity, capacity, count in zip(
        thicknesses,
        conductivities,
        capacities,
        counts,
        strict=True,
    ):
        element_thickness = float(thickness / count)
        element_conductance = float(conductivity * area_m2 / element_thickness)
        half_capacity = float(capacity * area_m2 * element_thickness / 2.0)
        for _ in range(int(count)):
            left = node
            right = node + 1
            stiffness[left, left] += element_conductance
            stiffness[left, right] -= element_conductance
            stiffness[right, left] -= element_conductance
            stiffness[right, right] += element_conductance
            lumped_capacity[left] += half_capacity
            lumped_capacity[right] += half_capacity
            coordinate += element_thickness
            positions[right] = coordinate
            node = right

    return positions, stiffness, lumped_capacity


def layered_modal_step_response_K_W(
    layer_thicknesses_m: object,
    thermal_conductivities_W_mK: object,
    volumetric_heat_capacities_J_m3K: object,
    elements_per_layer: object,
    times_s: object,
    *,
    area_m2: float = 1.0,
) -> LayeredModalResponse:
    """Return the independent exact-modal layered step response in K/W.

    The bottom node is eliminated as a fixed-temperature Dirichlet boundary.
    A unit total power is applied at the top node, equivalent to a uniform heat
    flux of ``1/area_m2``.  The generalized symmetric eigenproblem is formed by
    scaling the stiffness with the diagonal lumped-capacity matrix.
    """

    thicknesses = _positive_finite_array(
        "layer_thicknesses_m", layer_thicknesses_m
    )
    conductivities = _positive_finite_array(
        "thermal_conductivities_W_mK", thermal_conductivities_W_mK
    )
    capacities = _positive_finite_array(
        "volumetric_heat_capacities_J_m3K",
        volumetric_heat_capacities_J_m3K,
    )
    if not (
        thicknesses.size == conductivities.size == capacities.size
    ):
        raise ValueError("all layer-property arrays must have equal length")
    counts = _validated_elements_per_layer(
        elements_per_layer,
        int(thicknesses.size),
    )
    times = _positive_finite_array("times_s", times_s)
    if np.any(np.diff(times) <= 0.0):
        raise ValueError("times_s must be strictly increasing")
    area = _positive_finite_scalar("area_m2", area_m2)

    positions, stiffness_full, capacity_full = _assemble_layered_matrices(
        thicknesses,
        conductivities,
        capacities,
        counts,
        area,
    )

    # Eliminate the fixed-temperature bottom node.  The initial temperature
    # rise and the eliminated boundary temperature are both zero.
    stiffness = stiffness_full[:-1, :-1]
    lumped_capacity = capacity_full[:-1]
    inverse_sqrt_capacity = 1.0 / np.sqrt(lumped_capacity)
    symmetric_operator = (
        inverse_sqrt_capacity[:, None]
        * stiffness
        * inverse_sqrt_capacity[None, :]
    )
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric_operator)
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise RuntimeError("modal operator must have finite positive eigenvalues")

    unit_power_load = np.zeros(stiffness.shape[0], dtype=float)
    unit_power_load[0] = 1.0
    steady_temperature = np.linalg.solve(stiffness, unit_power_load)
    transformed_steady = np.sqrt(lumped_capacity) * steady_temperature
    modal_coefficients = eigenvectors.T @ transformed_steady

    growth = -np.expm1(-np.outer(times, eigenvalues))
    transformed_temperature = (
        growth * modal_coefficients[None, :]
    ) @ eigenvectors.T
    unknown_temperature = (
        transformed_temperature * inverse_sqrt_capacity[None, :]
    )
    temperature = np.zeros((times.size, positions.size), dtype=float)
    temperature[:, :-1] = unknown_temperature

    steady_resistance = steady_series_resistance_K_W(
        thicknesses,
        conductivities,
        area_m2=area,
    )
    return LayeredModalResponse(
        times_s=times.copy(),
        node_positions_m=positions,
        temperature_impedance_K_W=temperature,
        top_impedance_K_W=temperature[:, 0].copy(),
        steady_top_resistance_K_W=steady_resistance,
        eigenvalues_s_inv=eigenvalues,
        lumped_capacities_J_K=lumped_capacity.copy(),
    )


def max_normalized_response_change(
    first_impedance_K_W: object,
    second_impedance_K_W: object,
    normalization_resistance_K_W: float,
) -> float:
    """Return a fail-fast max absolute response change normalized by steady R."""

    first = np.asarray(first_impedance_K_W, dtype=float)
    second = np.asarray(second_impedance_K_W, dtype=float)
    if first.ndim != 1 or second.ndim != 1 or first.shape != second.shape:
        raise ValueError("impedance arrays must be one-dimensional and shape matched")
    if first.size == 0 or not np.all(np.isfinite(first)) or not np.all(
        np.isfinite(second)
    ):
        raise ValueError("impedance arrays must be non-empty and finite")
    normalization = _positive_finite_scalar(
        "normalization_resistance_K_W",
        normalization_resistance_K_W,
    )
    return float(np.max(np.abs(first - second)) / normalization)
