"""Passive areal K-state thermal-memory operators for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class PassiveThermalLadder:
    """One passive Cauer ladder per unit active-plane area.

    ``capacities_J_m2K`` contains K storage nodes and
    ``conductances_W_m2K`` contains the K+1 links from active plane to
    ambient. The active-plane capacity is deliberately excluded.
    """

    region_id: str
    capacities_J_m2K: np.ndarray
    conductances_W_m2K: np.ndarray

    def __post_init__(self) -> None:
        capacities = np.asarray(self.capacities_J_m2K, dtype=float)
        conductances = np.asarray(self.conductances_W_m2K, dtype=float)
        if capacities.ndim != 1 or conductances.ndim != 1:
            raise ValueError("thermal ladder parameters must be one-dimensional")
        if conductances.size != capacities.size + 1:
            raise ValueError("a K-state ladder requires K+1 conductances")
        if not np.isfinite(capacities).all() or not np.isfinite(conductances).all():
            raise ValueError("thermal ladder parameters must be finite")
        if np.any(capacities <= 0.0) or np.any(conductances <= 0.0):
            raise ValueError("thermal ladder capacities and conductances must be positive")
        object.__setattr__(self, "capacities_J_m2K", capacities)
        object.__setattr__(self, "conductances_W_m2K", conductances)
        if np.any(self.poles_per_s() >= 0.0):
            raise ValueError("thermal ladder must have strictly stable real poles")

    @property
    def order(self) -> int:
        return int(self.capacities_J_m2K.size)

    @property
    def dc_conductance_W_m2K(self) -> float:
        return float(1.0 / np.sum(1.0 / self.conductances_W_m2K))

    @property
    def total_capacity_J_m2K(self) -> float:
        return float(np.sum(self.capacities_J_m2K))

    def conductance_matrix(self) -> np.ndarray:
        order = self.order
        links = self.conductances_W_m2K
        matrix = np.zeros((order, order), dtype=float)
        for index in range(order):
            matrix[index, index] = links[index] + links[index + 1]
            if index:
                matrix[index, index - 1] = -links[index]
            if index + 1 < order:
                matrix[index, index + 1] = -links[index + 1]
        return matrix

    def state_matrix_per_s(self) -> np.ndarray:
        return -self.conductance_matrix() / self.capacities_J_m2K[:, None]

    def input_vector_K_per_J(self) -> np.ndarray:
        vector = np.zeros(self.order, dtype=float)
        vector[0] = self.conductances_W_m2K[0] / self.capacities_J_m2K[0]
        return vector

    def poles_per_s(self) -> np.ndarray:
        poles = np.linalg.eigvals(self.state_matrix_per_s())
        if np.max(np.abs(np.imag(poles))) > 1.0e-9 * max(
            np.max(np.abs(np.real(poles))), 1.0
        ):
            raise ValueError("passive thermal ladder produced complex poles")
        return np.sort(np.real(poles))

    def driving_admittance_W_m2K(self, angular_frequency_rad_s: np.ndarray) -> np.ndarray:
        omega = np.atleast_1d(np.asarray(angular_frequency_rad_s, dtype=float))
        if np.any(omega < 0.0) or not np.isfinite(omega).all():
            raise ValueError("angular frequencies must be finite and nonnegative")
        matrix = self.state_matrix_per_s()
        input_vector = self.input_vector_K_per_J()
        identity = np.eye(self.order)
        response = np.empty(omega.size, dtype=complex)
        g0 = self.conductances_W_m2K[0]
        for index, value in enumerate(omega):
            state = np.linalg.solve(1j * value * identity - matrix, input_vector)
            response[index] = g0 * (1.0 - state[0])
        return response

    def step_heat_flux_W_m2(
        self, time_s: np.ndarray, step_temperature_K: float = 1.0
    ) -> np.ndarray:
        time = np.atleast_1d(np.asarray(time_s, dtype=float))
        if np.any(time < 0.0) or not np.isfinite(time).all():
            raise ValueError("step-response times must be finite and nonnegative")
        matrix = self.state_matrix_per_s()
        input_vector = self.input_vector_K_per_J()
        steady = -np.linalg.solve(matrix, input_vector) * float(step_temperature_K)
        g0 = self.conductances_W_m2K[0]
        flux = np.empty(time.size, dtype=float)
        for index, value in enumerate(time):
            state = steady - expm(matrix * value) @ steady
            flux[index] = g0 * (float(step_temperature_K) - state[0])
        return flux

    def impulse_tail_W_m2K_s(
        self, time_s: np.ndarray, impulse_temperature_K_s: float = 1.0
    ) -> np.ndarray:
        """Return the finite dynamic tail; the instantaneous D delta is separate."""

        time = np.atleast_1d(np.asarray(time_s, dtype=float))
        if np.any(time < 0.0) or not np.isfinite(time).all():
            raise ValueError("impulse-response times must be finite and nonnegative")
        matrix = self.state_matrix_per_s()
        input_vector = self.input_vector_K_per_J()
        g0 = self.conductances_W_m2K[0]
        return np.asarray(
            [
                -g0
                * float((expm(matrix * value) @ input_vector)[0])
                * float(impulse_temperature_K_s)
                for value in time
            ],
            dtype=float,
        )


def initial_passive_ladder(
    *,
    region_id: str,
    order: int,
    total_capacity_J_m2K: float,
    dc_conductance_W_m2K: float,
) -> PassiveThermalLadder:
    """Construct a positive, stable initial ladder for later locked fitting."""

    if order <= 0:
        raise ValueError("order must be positive")
    if total_capacity_J_m2K <= 0.0 or dc_conductance_W_m2K <= 0.0:
        raise ValueError("capacity and conductance scales must be positive")
    capacities = np.full(order, total_capacity_J_m2K / order, dtype=float)
    # Equal series links recover the requested total DC conductance exactly.
    conductances = np.full(order + 1, (order + 1) * dc_conductance_W_m2K)
    return PassiveThermalLadder(region_id, capacities, conductances)
