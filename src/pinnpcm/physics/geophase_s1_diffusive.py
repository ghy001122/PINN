"""Bounded S1 positive-real diffusive thermal sensitivity model.

This module implements only the preregistered S1 model-form sensitivity.
It is deliberately independent of the nominal Phase1-v2 S2 closure and it
does not provide a production-model selection path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.linalg import expm
from scipy.optimize import minimize


_TINY = 1.0e-300
_NEGATIVE_LOG_MIN_SUBNORMAL = -float(np.log(np.nextafter(0.0, 1.0)))


def _as_1d_nonnegative(values: np.ndarray | Iterable[float], name: str) -> np.ndarray:
    array = np.atleast_1d(np.asarray(values, dtype=float))
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(array).all() or np.any(array < 0.0):
        raise ValueError(f"{name} must be finite and nonnegative")
    return array


@dataclass(frozen=True)
class DiffusiveThermalImpedance:
    """Source-moment anchored positive-real diffusive engineering prior."""

    gtheta_A_W_m2K: float
    cm_A_J_m2K: float
    modal_terms: int = 16384
    modal_chunk_terms: int = 2048

    def __post_init__(self) -> None:
        if not np.isfinite(self.gtheta_A_W_m2K) or self.gtheta_A_W_m2K <= 0.0:
            raise ValueError("gtheta_A_W_m2K must be finite and positive")
        if not np.isfinite(self.cm_A_J_m2K) or self.cm_A_J_m2K <= 0.0:
            raise ValueError("cm_A_J_m2K must be finite and positive")
        if self.modal_terms < 1024:
            raise ValueError("modal_terms must be at least 1024")
        if self.modal_chunk_terms < 1 or self.modal_chunk_terms > self.modal_terms:
            raise ValueError("modal_chunk_terms must lie in [1, modal_terms]")

    @property
    def resistance_m2K_W(self) -> float:
        return 1.0 / self.gtheta_A_W_m2K

    @property
    def mean_time_s(self) -> float:
        return self.cm_A_J_m2K / self.gtheta_A_W_m2K

    @property
    def tau_s(self) -> float:
        return 3.0 * self.mean_time_s

    @property
    def first_impedance_moment_m2K_s_W(self) -> float:
        return self.cm_A_J_m2K / self.gtheta_A_W_m2K**2

    def impedance(self, complex_frequency_per_s: np.ndarray | complex) -> np.ndarray:
        s = np.atleast_1d(np.asarray(complex_frequency_per_s, dtype=complex))
        if not np.isfinite(s.real).all() or not np.isfinite(s.imag).all():
            raise ValueError("complex frequency must be finite")
        x = np.sqrt(s * self.tau_s)
        ratio = np.ones_like(x)
        nonzero = np.abs(x) > 1.0e-8
        ratio[nonzero] = np.tanh(x[nonzero]) / x[nonzero]
        # Avoid cancellation at the DC limit.
        xs = x[~nonzero]
        ratio[~nonzero] = 1.0 - xs**2 / 3.0 + 2.0 * xs**4 / 15.0
        return self.resistance_m2K_W * ratio

    def admittance(self, complex_frequency_per_s: np.ndarray | complex) -> np.ndarray:
        return 1.0 / self.impedance(complex_frequency_per_s)

    def _modal_weights_and_times(self) -> tuple[np.ndarray, np.ndarray]:
        odd = 2.0 * np.arange(self.modal_terms, dtype=float) + 1.0
        weights = 8.0 / (np.pi**2 * odd**2)
        times = 4.0 * self.tau_s / (np.pi**2 * odd**2)
        return weights, times

    @staticmethod
    def _finite_step_fraction(
        time: np.ndarray,
        weights: np.ndarray,
        times: np.ndarray,
        chunk_terms: int,
    ) -> np.ndarray:
        """Evaluate the same finite modal sum without subnormal exponent calls."""

        response = np.zeros(time.size, dtype=float)
        positive = time > 0.0
        if not np.any(positive):
            return response
        local_time = time[positive]
        minimum_time = float(np.min(local_time))
        active_count = int(
            np.count_nonzero(
                minimum_time / times <= _NEGATIVE_LOG_MIN_SUBNORMAL
            )
        )
        for start in range(0, active_count, chunk_terms):
            stop = min(start + chunk_terms, active_count)
            arguments = local_time[:, None] / times[None, start:stop]
            values = np.ones_like(arguments)
            active = arguments <= _NEGATIVE_LOG_MIN_SUBNORMAL
            values[active] = -np.expm1(-arguments[active])
            response[positive] += np.sum(
                weights[None, start:stop] * values,
                axis=1,
            )
        if active_count < weights.size:
            response[positive] += float(np.sum(weights[active_count:]))
        return response

    @staticmethod
    def _finite_pulse_fraction(
        time: np.ndarray,
        weights: np.ndarray,
        times: np.ndarray,
        chunk_terms: int,
        pulse_width_s: float,
    ) -> np.ndarray:
        response = np.zeros(time.size, dtype=float)
        before = time <= pulse_width_s
        if np.any(before):
            response[before] = DiffusiveThermalImpedance._finite_step_fraction(
                time[before], weights, times, chunk_terms
            )
        after = ~before
        if not np.any(after):
            return response
        elapsed = time[after] - pulse_width_s
        minimum_elapsed = float(np.min(elapsed))
        active_count = int(
            np.count_nonzero(
                minimum_elapsed / times <= _NEGATIVE_LOG_MIN_SUBNORMAL
            )
        )
        for start in range(0, active_count, chunk_terms):
            stop = min(start + chunk_terms, active_count)
            local_times = times[start:stop]
            local_weights = weights[start:stop]
            charge_arguments = pulse_width_s / local_times
            charged = np.ones_like(charge_arguments)
            charge_active = charge_arguments <= _NEGATIVE_LOG_MIN_SUBNORMAL
            charged[charge_active] = -np.expm1(-charge_arguments[charge_active])
            decay_arguments = elapsed[:, None] / local_times[None, :]
            decay = np.zeros_like(decay_arguments)
            decay_active = decay_arguments <= _NEGATIVE_LOG_MIN_SUBNORMAL
            decay[decay_active] = np.exp(-decay_arguments[decay_active])
            response[after] += np.sum(
                local_weights[None, :] * charged[None, :] * decay,
                axis=1,
            )
        return response

    def step_temperature_K(
        self,
        time_s: np.ndarray | Iterable[float],
        amplitude_W_m2: float = 1.0,
    ) -> np.ndarray:
        time = _as_1d_nonnegative(time_s, "time_s")
        weights, times = self._modal_weights_and_times()
        response = self._finite_step_fraction(
            time, weights, times, self.modal_chunk_terms
        )
        return float(amplitude_W_m2) * self.resistance_m2K_W * response

    def rectangular_pulse_temperature_K(
        self,
        time_s: np.ndarray | Iterable[float],
        *,
        pulse_width_s: float,
        pulse_amplitude_W_m2: float,
    ) -> np.ndarray:
        time = _as_1d_nonnegative(time_s, "time_s")
        if not np.isfinite(pulse_width_s) or pulse_width_s <= 0.0:
            raise ValueError("pulse_width_s must be finite and positive")
        if not np.isfinite(pulse_amplitude_W_m2):
            raise ValueError("pulse_amplitude_W_m2 must be finite")
        weights, times = self._modal_weights_and_times()
        response = self._finite_pulse_fraction(
            time,
            weights,
            times,
            self.modal_chunk_terms,
            pulse_width_s,
        )
        return (
            float(pulse_amplitude_W_m2)
            * self.resistance_m2K_W
            * response
        )


@dataclass(frozen=True)
class FosterThermalImpedance:
    """Finite positive Foster approximation of an areal thermal impedance."""

    resistances_m2K_W: np.ndarray
    time_constants_s: np.ndarray

    def __post_init__(self) -> None:
        resistances = np.asarray(self.resistances_m2K_W, dtype=float)
        times = np.asarray(self.time_constants_s, dtype=float)
        if resistances.ndim != 1 or times.ndim != 1 or resistances.size != times.size:
            raise ValueError("Foster R and tau arrays must be one-dimensional and equal")
        if resistances.size < 1:
            raise ValueError("Foster model must contain at least one mode")
        if not np.isfinite(resistances).all() or not np.isfinite(times).all():
            raise ValueError("Foster parameters must be finite")
        if np.any(resistances <= 0.0) or np.any(times <= 0.0):
            raise ValueError("Foster parameters must be positive")
        object.__setattr__(self, "resistances_m2K_W", resistances)
        object.__setattr__(self, "time_constants_s", times)

    @property
    def order(self) -> int:
        return int(self.resistances_m2K_W.size)

    @property
    def dc_resistance_m2K_W(self) -> float:
        return float(np.sum(self.resistances_m2K_W))

    @property
    def first_moment_m2K_s_W(self) -> float:
        return float(np.dot(self.resistances_m2K_W, self.time_constants_s))

    def poles_per_s(self) -> np.ndarray:
        return np.sort(-1.0 / self.time_constants_s)

    def impedance(self, complex_frequency_per_s: np.ndarray | complex) -> np.ndarray:
        s = np.atleast_1d(np.asarray(complex_frequency_per_s, dtype=complex))
        return np.sum(
            self.resistances_m2K_W[None, :]
            / (1.0 + s[:, None] * self.time_constants_s[None, :]),
            axis=1,
        )

    def step_temperature_K(
        self,
        time_s: np.ndarray | Iterable[float],
        amplitude_W_m2: float = 1.0,
    ) -> np.ndarray:
        time = _as_1d_nonnegative(time_s, "time_s")
        return float(amplitude_W_m2) * np.sum(
            self.resistances_m2K_W[None, :]
            * (-np.expm1(-time[:, None] / self.time_constants_s[None, :])),
            axis=1,
        )

    def rectangular_pulse_temperature_K(
        self,
        time_s: np.ndarray | Iterable[float],
        *,
        pulse_width_s: float,
        pulse_amplitude_W_m2: float,
    ) -> np.ndarray:
        time = _as_1d_nonnegative(time_s, "time_s")
        response = np.empty(time.size, dtype=float)
        before = time <= pulse_width_s
        response[before] = self.step_temperature_K(
            time[before], pulse_amplitude_W_m2
        )
        if np.any(~before):
            charged = -np.expm1(-pulse_width_s / self.time_constants_s)
            response[~before] = float(pulse_amplitude_W_m2) * np.sum(
                self.resistances_m2K_W[None, :]
                * charged[None, :]
                * np.exp(
                    -(time[~before, None] - pulse_width_s)
                    / self.time_constants_s[None, :]
                ),
                axis=1,
            )
        return response


@dataclass(frozen=True)
class CauerIIThermalNetwork:
    """Cauer-II network reconstructed from the selected Foster impedance."""

    capacities_J_m2K: np.ndarray
    series_resistances_m2K_W: np.ndarray
    terminal_conductance_W_m2K: float

    def __post_init__(self) -> None:
        capacities = np.asarray(self.capacities_J_m2K, dtype=float)
        resistances = np.asarray(self.series_resistances_m2K_W, dtype=float)
        if capacities.ndim != 1 or resistances.ndim != 1:
            raise ValueError("Cauer elements must be one-dimensional")
        if resistances.size != max(capacities.size - 1, 0):
            raise ValueError("K-node Cauer-II network requires K-1 series resistors")
        values = np.concatenate(
            [capacities, resistances, [float(self.terminal_conductance_W_m2K)]]
        )
        if not np.isfinite(values).all() or np.any(values <= 0.0):
            raise ValueError("all Cauer-II elements must be finite and positive")
        object.__setattr__(self, "capacities_J_m2K", capacities)
        object.__setattr__(self, "series_resistances_m2K_W", resistances)

    @property
    def order(self) -> int:
        return int(self.capacities_J_m2K.size)

    @property
    def independent_vertical_state_count(self) -> int:
        """Number of states added when node zero is the resolved plane temperature."""

        return self.order - 1

    @property
    def port_capacity_J_m2K(self) -> float:
        return float(self.capacities_J_m2K[0])

    def admittance(self, complex_frequency_per_s: np.ndarray | complex) -> np.ndarray:
        s = np.atleast_1d(np.asarray(complex_frequency_per_s, dtype=complex))
        response = s * self.capacities_J_m2K[-1] + self.terminal_conductance_W_m2K
        for index in range(self.order - 2, -1, -1):
            response = (
                s * self.capacities_J_m2K[index]
                + 1.0
                / (
                    self.series_resistances_m2K_W[index]
                    + 1.0 / response
                )
            )
        return response

    def impedance(self, complex_frequency_per_s: np.ndarray | complex) -> np.ndarray:
        return 1.0 / self.admittance(complex_frequency_per_s)

    def conductance_matrix_W_m2K(self) -> np.ndarray:
        """Return the nodal conductance matrix without using transfer recursion."""

        order = self.order
        conductance = np.zeros((order, order), dtype=float)
        for index, resistance in enumerate(self.series_resistances_m2K_W):
            link = 1.0 / resistance
            conductance[index, index] += link
            conductance[index + 1, index + 1] += link
            conductance[index, index + 1] -= link
            conductance[index + 1, index] -= link
        conductance[-1, -1] += self.terminal_conductance_W_m2K
        return conductance

    def state_matrix_per_s(self) -> np.ndarray:
        return -self.conductance_matrix_W_m2K() / self.capacities_J_m2K[:, None]

    def state_space_impedance(
        self, complex_frequency_per_s: np.ndarray | complex
    ) -> np.ndarray:
        """Compute the driving-point impedance from an independent nodal solve."""

        frequencies = np.atleast_1d(
            np.asarray(complex_frequency_per_s, dtype=complex)
        )
        if frequencies.ndim != 1:
            raise ValueError("complex_frequency_per_s must be one-dimensional")
        if not np.isfinite(frequencies.real).all() or not np.isfinite(
            frequencies.imag
        ).all():
            raise ValueError("complex_frequency_per_s must be finite")
        conductance = self.conductance_matrix_W_m2K().astype(complex)
        capacity = np.diag(self.capacities_J_m2K).astype(complex)
        port = np.zeros(self.order, dtype=complex)
        port[0] = 1.0
        response = np.empty(frequencies.size, dtype=complex)
        for index, frequency in enumerate(frequencies):
            response[index] = np.linalg.solve(
                conductance + frequency * capacity, port
            )[0]
        return response

    @property
    def dc_resistance_m2K_W(self) -> float:
        return float(self.state_space_impedance(np.asarray([0.0j]))[0].real)

    @property
    def first_impedance_moment_m2K_s_W(self) -> float:
        conductance = self.conductance_matrix_W_m2K()
        port = np.zeros(self.order, dtype=float)
        port[0] = 1.0
        static_temperature = np.linalg.solve(conductance, port)
        return float(
            static_temperature
            @ (self.capacities_J_m2K * static_temperature)
        )

    def step_temperature_K(
        self,
        time_s: np.ndarray | Iterable[float],
        amplitude_W_m2: float = 1.0,
    ) -> np.ndarray:
        """Port temperature for a heat-flux step from an independent state solve."""

        time = _as_1d_nonnegative(time_s, "time_s")
        if not np.isfinite(amplitude_W_m2):
            raise ValueError("amplitude_W_m2 must be finite")
        conductance = self.conductance_matrix_W_m2K()
        port = np.zeros(self.order, dtype=float)
        port[0] = float(amplitude_W_m2)
        steady = np.linalg.solve(conductance, port)
        state_matrix = self.state_matrix_per_s()
        response = np.empty(time.size, dtype=float)
        for index, value in enumerate(time):
            state = steady - expm(state_matrix * value) @ steady
            response[index] = state[0]
        return response

    def rectangular_pulse_temperature_K(
        self,
        time_s: np.ndarray | Iterable[float],
        *,
        pulse_width_s: float,
        pulse_amplitude_W_m2: float,
    ) -> np.ndarray:
        """Port temperature for a finite rectangular heat-flux pulse."""

        time = _as_1d_nonnegative(time_s, "time_s")
        if not np.isfinite(pulse_width_s) or pulse_width_s <= 0.0:
            raise ValueError("pulse_width_s must be finite and positive")
        response = self.step_temperature_K(time, pulse_amplitude_W_m2)
        after = time > pulse_width_s
        if np.any(after):
            response[after] -= self.step_temperature_K(
                time[after] - pulse_width_s, pulse_amplitude_W_m2
            )
        return response

    def poles_per_s(self) -> np.ndarray:
        poles = np.linalg.eigvals(self.state_matrix_per_s())
        if np.max(np.abs(poles.imag)) > 1.0e-10 * max(np.max(np.abs(poles.real)), 1.0):
            raise ValueError("Cauer-II poles are not real within tolerance")
        return np.sort(poles.real)

    def backward_euler_ledger(
        self,
        *,
        time_step_s: float,
        steps: int,
        port_heat_flux_W_m2: float,
        initial_temperature_rise_K: float = 0.0,
        storage_tamper_W_m2: float = 0.0,
        sink_tamper_W_m2: float = 0.0,
    ) -> dict[str, float]:
        """Solve first, then independently audit finite-difference storage/sink."""

        if not np.isfinite(time_step_s) or time_step_s <= 0.0:
            raise ValueError("time_step_s must be finite and positive")
        if int(steps) != steps or steps < 1:
            raise ValueError("steps must be a positive integer")
        values = np.asarray(
            [
                port_heat_flux_W_m2,
                initial_temperature_rise_K,
                storage_tamper_W_m2,
                sink_tamper_W_m2,
            ],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("backward-Euler ledger inputs must be finite")
        capacity = np.diag(self.capacities_J_m2K)
        conductance = self.conductance_matrix_W_m2K()
        system = capacity / float(time_step_s) + conductance
        state = np.full(self.order, float(initial_temperature_rise_K))
        port = np.zeros(self.order, dtype=float)
        port[0] = float(port_heat_flux_W_m2)
        maximum = 0.0
        final_storage = 0.0
        final_sink = 0.0
        for _ in range(int(steps)):
            previous = state.copy()
            state = np.linalg.solve(
                system, capacity @ previous / float(time_step_s) + port
            )
            storage = float(
                np.dot(self.capacities_J_m2K, state - previous)
                / float(time_step_s)
            ) + float(storage_tamper_W_m2)
            sink = float(
                self.terminal_conductance_W_m2K * state[-1]
            ) + float(sink_tamper_W_m2)
            residual = float(port_heat_flux_W_m2) - storage - sink
            scale = max(
                abs(float(port_heat_flux_W_m2)), abs(storage) + abs(sink), _TINY
            )
            maximum = max(maximum, abs(residual) / scale)
            final_storage = storage
            final_sink = sink
        return {
            "maximum_relative_residual": float(maximum),
            "final_storage_rate_W_m2": float(final_storage),
            "final_terminal_sink_W_m2": float(final_sink),
            "final_port_temperature_rise_K": float(state[0]),
            "independent_vertical_state_count": float(
                self.independent_vertical_state_count
            ),
        }


def _trim_polynomial(coefficients: np.ndarray, tolerance: float = 1.0e-11) -> np.ndarray:
    result = np.asarray(coefficients, dtype=float).copy()
    while result.size > 1 and abs(result[-1]) <= tolerance * max(np.max(np.abs(result)), 1.0e-300):
        result = result[:-1]
    return result


def _subtract_polynomials(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    size = max(left.size, right.size)
    result = np.zeros(size, dtype=float)
    result[: left.size] += left
    result[: right.size] -= right
    return _trim_polynomial(result)


def foster_to_cauer_ii(
    foster: FosterThermalImpedance,
    *,
    gtheta_A_W_m2K: float,
    cm_A_J_m2K: float,
) -> CauerIIThermalNetwork:
    """Convert Foster Z to Cauer-II Y using a dimensionless Euclidean fraction."""

    resistance_scale = 1.0 / float(gtheta_A_W_m2K)
    time_scale = float(cm_A_J_m2K) / float(gtheta_A_W_m2K)
    weights = foster.resistances_m2K_W / resistance_scale
    multipliers = foster.time_constants_s / time_scale
    denominator = np.asarray([1.0], dtype=float)
    for multiplier in multipliers:
        denominator = np.polynomial.polynomial.polymul(
            denominator, np.asarray([1.0, multiplier])
        )
    numerator = np.zeros(foster.order, dtype=float)
    for index, weight in enumerate(weights):
        local = np.asarray([1.0], dtype=float)
        for other, multiplier in enumerate(multipliers):
            if other != index:
                local = np.polynomial.polynomial.polymul(
                    local, np.asarray([1.0, multiplier])
                )
        numerator[: local.size] += weight * local

    # Dimensionless Y=P/Q where P is the Foster denominator and Q numerator.
    p = _trim_polynomial(denominator)
    q = _trim_polynomial(numerator)
    c_dimensionless: list[float] = []
    r_dimensionless: list[float] = []
    for _ in range(foster.order - 1):
        if p.size != q.size + 1:
            raise ValueError("Cauer Euclidean fraction lost the required polynomial degree")
        capacity = p[-1] / q[-1]
        c_dimensionless.append(float(capacity))
        h_numerator = _subtract_polynomials(
            p, capacity * np.concatenate(([0.0], q))
        )
        if h_numerator.size != q.size:
            raise ValueError("Cauer extraction produced an invalid remainder degree")
        resistance = q[-1] / h_numerator[-1]
        r_dimensionless.append(float(resistance))
        next_denominator = _subtract_polynomials(q, resistance * h_numerator)
        p, q = h_numerator, next_denominator
        scale = max(np.max(np.abs(p)), np.max(np.abs(q)), _TINY)
        p = p / scale
        q = q / scale

    if p.size != q.size + 1:
        raise ValueError("terminal Cauer extraction has invalid polynomial degree")
    last_capacity = p[-1] / q[-1]
    residual = _subtract_polynomials(
        p, last_capacity * np.concatenate(([0.0], q))
    )
    if residual.size != q.size:
        raise ValueError("terminal Cauer conductance has invalid degree")
    conductance_ratios = residual / q
    terminal_conductance = float(np.mean(conductance_ratios))
    if np.max(np.abs(conductance_ratios - terminal_conductance)) > 1.0e-9 * max(
        abs(terminal_conductance), 1.0
    ):
        raise ValueError("terminal Cauer remainder is not a constant conductance")
    c_dimensionless.append(float(last_capacity))

    return CauerIIThermalNetwork(
        capacities_J_m2K=cm_A_J_m2K * np.asarray(c_dimensionless),
        series_resistances_m2K_W=resistance_scale
        * np.asarray(r_dimensionless),
        terminal_conductance_W_m2K=gtheta_A_W_m2K * terminal_conductance,
    )


def minimum_l2_start_weights(multipliers: np.ndarray, lower_bound: float) -> np.ndarray:
    """Locked minimum-distance start weights under the two moment constraints."""

    multipliers = np.asarray(multipliers, dtype=float)
    uniform = np.full(multipliers.size, 1.0 / multipliers.size)
    result = minimize(
        lambda weights: float(np.sum((weights - uniform) ** 2)),
        uniform,
        method="SLSQP",
        bounds=[(float(lower_bound), None)] * multipliers.size,
        constraints=[
            {"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1.0)},
            {
                "type": "eq",
                "fun": lambda weights: float(np.dot(weights, multipliers) - 1.0),
            },
        ],
        options={"maxiter": 1000, "ftol": 1.0e-14},
    )
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError("failed to construct a deterministic feasible start")
    if np.max(np.abs([np.sum(result.x) - 1.0, np.dot(result.x, multipliers) - 1.0])) > 1.0e-12:
        raise RuntimeError("deterministic start violates moment constraints")
    return np.asarray(result.x, dtype=float)


def fit_foster_candidate(
    *,
    start_id: str,
    multipliers: np.ndarray,
    analytic: DiffusiveThermalImpedance,
    fit_frequency_Hz: np.ndarray,
    fit_time_s: np.ndarray,
    pulse_width_s: float,
    pulse_amplitude_W_m2: float,
    weights: dict[str, float],
    maximum_iterations: int,
    ftol: float,
    equality_tolerance: float,
    log_weight_bounds: tuple[float, float],
    log_multiplier_bounds: tuple[float, float],
    finite_penalty: float,
    boundary_hit_tolerance: float,
) -> tuple[FosterThermalImpedance | None, dict[str, object]]:
    """Run one locked SLSQP start in normalized moment coordinates."""

    initial_multipliers = np.asarray(multipliers, dtype=float)
    initial_weights = minimum_l2_start_weights(initial_multipliers, 1.0e-6)
    x0 = np.log(np.concatenate([initial_weights, initial_multipliers]))
    order = initial_weights.size
    tbar = analytic.mean_time_s
    fit_s = 1j * 2.0 * np.pi * np.asarray(fit_frequency_Hz, dtype=float)
    reference_frequency = analytic.impedance(fit_s)
    reference_step = analytic.step_temperature_K(fit_time_s)
    reference_pulse = analytic.rectangular_pulse_temperature_K(
        fit_time_s,
        pulse_width_s=pulse_width_s,
        pulse_amplitude_W_m2=pulse_amplitude_W_m2,
    )
    step_scale = analytic.resistance_m2K_W
    pulse_scale = max(float(np.sqrt(np.mean(reference_pulse**2))), 1.0e-30)

    def unpack(log_parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if not np.isfinite(log_parameters).all():
            raise FloatingPointError("nonfinite log parameter")
        with np.errstate(over="raise", invalid="raise", under="ignore"):
            parameters = np.exp(log_parameters)
        if not np.isfinite(parameters).all() or np.any(parameters <= 0.0):
            raise FloatingPointError("decoded Foster parameter is nonfinite")
        return parameters[:order], parameters[order:]

    def objective(log_parameters: np.ndarray) -> float:
        try:
            local_weights, local_multipliers = unpack(log_parameters)
            model = FosterThermalImpedance(
                local_weights * analytic.resistance_m2K_W,
                local_multipliers * tbar,
            )
            candidate_frequency = model.impedance(fit_s)
            frequency_error = np.log(
                np.maximum(np.abs(candidate_frequency), _TINY)
            ) - np.log(np.maximum(np.abs(reference_frequency), _TINY))
            step_error = (
                model.step_temperature_K(fit_time_s) - reference_step
            ) / step_scale
            pulse_error = (
                model.rectangular_pulse_temperature_K(
                    fit_time_s,
                    pulse_width_s=pulse_width_s,
                    pulse_amplitude_W_m2=pulse_amplitude_W_m2,
                )
                - reference_pulse
            ) / pulse_scale
            value = float(
                weights["frequency_log_magnitude"]
                * np.mean(frequency_error**2)
                + weights["unit_heat_flux_step_temperature"]
                * np.mean(step_error**2)
                + weights["unit_area_pulse_temperature"]
                * np.mean(pulse_error**2)
            )
            return value if np.isfinite(value) else float(finite_penalty)
        except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
            return float(finite_penalty)

    def dc_constraint(log_parameters: np.ndarray) -> float:
        try:
            local_weights, _ = unpack(log_parameters)
            return float(np.sum(local_weights) - 1.0)
        except (FloatingPointError, OverflowError, ValueError):
            return float(finite_penalty)

    def moment_constraint(log_parameters: np.ndarray) -> float:
        try:
            local_weights, local_multipliers = unpack(log_parameters)
            return float(np.dot(local_weights, local_multipliers) - 1.0)
        except (FloatingPointError, OverflowError, ValueError):
            return float(finite_penalty)

    bounds = [tuple(map(float, log_weight_bounds))] * order + [
        tuple(map(float, log_multiplier_bounds))
    ] * order
    optimizer_exception = ""
    try:
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=[
                {"type": "eq", "fun": dc_constraint},
                {"type": "eq", "fun": moment_constraint},
            ],
            options={
                "maxiter": int(maximum_iterations),
                "ftol": float(ftol),
                "disp": False,
            },
        )
    except Exception as error:  # one failed start must not abort the bounded MVE
        optimizer_exception = f"{type(error).__name__}: {error}"
        return None, {
            "start_id": start_id,
            "order": int(order),
            "optimizer_success": False,
            "optimizer_status": -1,
            "optimizer_message": "optimizer raised an isolated exception",
            "optimizer_exception": optimizer_exception,
            "no_optimizer_exception": False,
            "iterations": 0,
            "function_evaluations": 0,
            "fit_objective": float(finite_penalty),
            "finite_objective": False,
            "finite_parameters": False,
            "constraint_absolute_max": float("inf"),
            "constraint_feasible": False,
            "equality_constraints_feasible": False,
            "parameter_bound_hit": False,
            "no_parameter_bound_hit": True,
            "positive_foster_elements": False,
            "candidate_eligible": False,
        }
    feasible = False
    model: FosterThermalImpedance | None = None
    constraint_max = float("inf")
    finite_parameters = False
    positive_elements = False
    boundary_hit = False
    if np.isfinite(result.x).all():
        try:
            local_weights, local_multipliers = unpack(result.x)
            constraint_max = float(
                max(
                    abs(np.sum(local_weights) - 1.0),
                    abs(np.dot(local_weights, local_multipliers) - 1.0),
                )
            )
            feasible = bool(constraint_max <= float(equality_tolerance))
            finite_parameters = bool(
                np.isfinite(local_weights).all()
                and np.isfinite(local_multipliers).all()
            )
            positive_elements = bool(
                finite_parameters
                and np.all(local_weights > 0.0)
                and np.all(local_multipliers > 0.0)
            )
            boundary_hit = any(
                abs(float(value) - lower) <= float(boundary_hit_tolerance)
                or abs(float(value) - upper) <= float(boundary_hit_tolerance)
                for value, (lower, upper) in zip(result.x, bounds, strict=True)
            )
            if finite_parameters and positive_elements:
                model = FosterThermalImpedance(
                    local_weights * analytic.resistance_m2K_W,
                    local_multipliers * tbar,
                )
        except (FloatingPointError, OverflowError, ValueError):
            model = None
    finite_objective = bool(np.isfinite(result.fun) and result.fun < finite_penalty)
    metadata: dict[str, object] = {
        "start_id": start_id,
        "order": int(order),
        "optimizer_success": bool(result.success),
        "optimizer_status": int(result.status),
        "optimizer_message": str(result.message),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "optimizer_exception": optimizer_exception,
        "no_optimizer_exception": not bool(optimizer_exception),
        "fit_objective": float(result.fun)
        if np.isfinite(result.fun)
        else float(finite_penalty),
        "finite_objective": finite_objective,
        "finite_parameters": finite_parameters,
        "constraint_absolute_max": constraint_max,
        "constraint_feasible": feasible,
        "equality_constraints_feasible": feasible,
        "parameter_bound_hit": boundary_hit,
        "no_parameter_bound_hit": not boundary_hit,
        "positive_foster_elements": positive_elements,
    }
    eligible = candidate_eligible(metadata)
    metadata["candidate_eligible"] = eligible
    if not eligible:
        model = None
    return model, metadata


def candidate_eligible(metadata: dict[str, object]) -> bool:
    """Single authoritative v2 candidate-eligibility aggregator."""

    return bool(
        metadata.get("optimizer_success") is True
        and metadata.get("finite_objective") is True
        and metadata.get("finite_parameters") is True
        and metadata.get("equality_constraints_feasible") is True
        and metadata.get("no_optimizer_exception") is True
        and metadata.get("no_parameter_bound_hit") is True
        and metadata.get("positive_foster_elements") is True
    )


def select_training_candidate(
    candidates: Iterable[
        tuple[FosterThermalImpedance | None, dict[str, object]]
    ],
) -> tuple[FosterThermalImpedance, dict[str, object]] | None:
    """Select once by training objective; validation data is not an input."""

    eligible = [
        (model, metadata)
        for model, metadata in candidates
        if model is not None and candidate_eligible(metadata)
    ]
    if not eligible:
        return None
    model, metadata = min(
        eligible,
        key=lambda item: (
            float(item[1]["fit_objective"]),
            str(item[1]["start_id"]),
        ),
    )
    if model is None:  # narrowed above; retained for static/runtime fail-closed safety
        raise RuntimeError("selected Foster candidate unexpectedly has no model")
    return model, metadata


def fit_grids(response_contract: dict) -> tuple[np.ndarray, np.ndarray]:
    """Build the preregistered fit grids."""

    frequency = response_contract["frequency_fit_grid_Hz"]
    fit_frequency = np.geomspace(
        float(frequency["start"]), float(frequency["stop"]), int(frequency["points"])
    )
    time = response_contract["time_fit_grid_s"]
    fit_positive = np.geomspace(
        float(time["positive_start"]), float(time["stop"]), int(time["positive_points"])
    )
    return fit_frequency, np.concatenate(([0.0], fit_positive))


def validation_grids(response_contract: dict) -> tuple[np.ndarray, np.ndarray]:
    fit_frequency, fit_time = fit_grids(response_contract)
    validation_frequency = np.concatenate(
        (
            [fit_frequency[0]],
            np.sqrt(fit_frequency[:-1] * fit_frequency[1:]),
            [fit_frequency[-1]],
        )
    )
    fit_positive = fit_time[1:]
    validation_time = np.concatenate(
        ([0.0], np.sqrt(fit_positive[:-1] * fit_positive[1:]), [fit_positive[-1]])
    )
    return validation_frequency, validation_time


def pulse_event_times(
    pulse_width_s: float, relative_times: Iterable[float]
) -> np.ndarray:
    factors = _as_1d_nonnegative(relative_times, "pulse event relative times")
    if pulse_width_s <= 0.0 or not np.isfinite(pulse_width_s):
        raise ValueError("pulse_width_s must be finite and positive")
    return np.unique(float(pulse_width_s) * factors)


def analytic_reference_discrepancy(
    *,
    production: DiffusiveThermalImpedance,
    comparator: DiffusiveThermalImpedance,
    fit_time_s: np.ndarray,
    validation_time_s: np.ndarray,
    pulse_width_s: float,
    pulse_amplitude_W_m2: float,
    response_cache: dict[str, np.ndarray] | None = None,
) -> dict[str, float]:
    """Certify modal truncation on all preregistered time-response domains."""

    cache = response_cache
    if cache is None:
        cache = analytic_reference_response_cache(
            production=production,
            comparator=comparator,
            fit_time_s=fit_time_s,
            validation_time_s=validation_time_s,
            pulse_width_s=pulse_width_s,
            pulse_amplitude_W_m2=pulse_amplitude_W_m2,
        )
    metrics: dict[str, float] = {}
    for split, time in (("fit", fit_time_s), ("validation", validation_time_s)):
        production_step = cache[f"{split}_step_production"]
        comparator_step = cache[f"{split}_step_comparator"]
        metrics[f"step_{split}_discrepancy"] = float(
            np.sqrt(np.mean((production_step - comparator_step) ** 2))
            / production.resistance_m2K_W
        )
        production_pulse = cache[f"{split}_pulse_production"]
        comparator_pulse = cache[f"{split}_pulse_comparator"]
        pulse_scale = max(
            float(np.sqrt(np.mean(comparator_pulse**2))), 1.0e-30
        )
        metrics[f"pulse_{split}_discrepancy"] = float(
            np.sqrt(np.mean((production_pulse - comparator_pulse) ** 2))
            / pulse_scale
        )
    metrics["maximum_reference_discrepancy"] = max(metrics.values())
    return metrics


def analytic_reference_response_cache(
    *,
    production: DiffusiveThermalImpedance,
    comparator: DiffusiveThermalImpedance,
    fit_time_s: np.ndarray,
    validation_time_s: np.ndarray,
    pulse_width_s: float,
    pulse_amplitude_W_m2: float,
) -> dict[str, np.ndarray]:
    """Evaluate each registered modal response exactly once for evidence reuse."""

    cache: dict[str, np.ndarray] = {}
    for split, time in (("fit", fit_time_s), ("validation", validation_time_s)):
        cache[f"{split}_step_production"] = production.step_temperature_K(time)
        cache[f"{split}_step_comparator"] = comparator.step_temperature_K(time)
        cache[f"{split}_pulse_production"] = (
            production.rectangular_pulse_temperature_K(
                time,
                pulse_width_s=pulse_width_s,
                pulse_amplitude_W_m2=pulse_amplitude_W_m2,
            )
        )
        cache[f"{split}_pulse_comparator"] = (
            comparator.rectangular_pulse_temperature_K(
                time,
                pulse_width_s=pulse_width_s,
                pulse_amplitude_W_m2=pulse_amplitude_W_m2,
            )
        )
    return cache


def validation_metrics(
    *,
    analytic: DiffusiveThermalImpedance,
    foster: FosterThermalImpedance,
    cauer: CauerIIThermalNetwork,
    validation_frequency_Hz: np.ndarray,
    validation_time_s: np.ndarray,
    pulse_width_s: float,
    pulse_amplitude_W_m2: float,
    ledger_contract: dict,
) -> dict[str, float]:
    s = 1j * 2.0 * np.pi * np.asarray(validation_frequency_Hz, dtype=float)
    reference_frequency = analytic.impedance(s)
    foster_frequency = foster.impedance(s)
    cauer_frequency = cauer.impedance(s)
    cauer_state_frequency = cauer.state_space_impedance(s)
    reference_step = analytic.step_temperature_K(validation_time_s)
    foster_step = foster.step_temperature_K(validation_time_s)
    reference_pulse = analytic.rectangular_pulse_temperature_K(
        validation_time_s,
        pulse_width_s=pulse_width_s,
        pulse_amplitude_W_m2=pulse_amplitude_W_m2,
    )
    foster_pulse = foster.rectangular_pulse_temperature_K(
        validation_time_s,
        pulse_width_s=pulse_width_s,
        pulse_amplitude_W_m2=pulse_amplitude_W_m2,
    )
    cauer_step = cauer.step_temperature_K(validation_time_s)
    cauer_pulse = cauer.rectangular_pulse_temperature_K(
        validation_time_s,
        pulse_width_s=pulse_width_s,
        pulse_amplitude_W_m2=pulse_amplitude_W_m2,
    )
    step_nrmse = float(
        np.sqrt(np.mean((foster_step - reference_step) ** 2))
        / analytic.resistance_m2K_W
    )
    pulse_scale = max(float(np.sqrt(np.mean(reference_pulse**2))), 1.0e-30)
    pulse_nrmse = float(np.sqrt(np.mean((foster_pulse - reference_pulse) ** 2)) / pulse_scale)
    frequency_rmse = float(
        np.sqrt(
            np.mean(
                (
                    np.log(np.maximum(np.abs(foster_frequency), _TINY))
                    - np.log(np.maximum(np.abs(reference_frequency), _TINY))
                )
                ** 2
            )
        )
    )
    dc_error = abs(foster.dc_resistance_m2K_W - analytic.resistance_m2K_W) / analytic.resistance_m2K_W
    moment_error = abs(foster.first_moment_m2K_s_W - analytic.first_impedance_moment_m2K_s_W) / analytic.first_impedance_moment_m2K_s_W
    reconstruction = float(
        np.max(np.abs(cauer_frequency - foster_frequency) / np.maximum(np.abs(foster_frequency), _TINY))
    )
    state_reconstruction = float(
        np.max(
            np.abs(cauer_state_frequency - cauer_frequency)
            / np.maximum(np.abs(cauer_frequency), _TINY)
        )
    )
    cauer_dc_error = float(
        abs(cauer.dc_resistance_m2K_W - foster.dc_resistance_m2K_W)
        / foster.dc_resistance_m2K_W
    )
    cauer_moment_error = float(
        abs(
            cauer.first_impedance_moment_m2K_s_W
            - foster.first_moment_m2K_s_W
        )
        / foster.first_moment_m2K_s_W
    )
    cauer_step_error = float(
        np.max(np.abs(cauer_step - foster_step)) / analytic.resistance_m2K_W
    )
    cauer_pulse_error = float(
        np.max(np.abs(cauer_pulse - foster_pulse)) / pulse_scale
    )
    dc_s = np.asarray([0.0j])
    analytic_z_samples = np.concatenate(
        [analytic.impedance(dc_s), reference_frequency]
    )
    analytic_y_samples = np.concatenate(
        [analytic.admittance(dc_s), analytic.admittance(s)]
    )
    z_samples = np.concatenate([foster.impedance(dc_s), foster_frequency])
    y_samples = np.concatenate([cauer.admittance(dc_s), cauer.admittance(s)])
    ledger = cauer.backward_euler_ledger(
        time_step_s=float(ledger_contract["time_step_s"]),
        steps=int(ledger_contract["steps"]),
        port_heat_flux_W_m2=float(ledger_contract["port_heat_flux_W_m2"]),
        initial_temperature_rise_K=float(
            ledger_contract["initial_temperature_rise_K"]
        ),
    )
    tamper = 0.01 * abs(float(ledger_contract["port_heat_flux_W_m2"]))
    storage_tamper = cauer.backward_euler_ledger(
        time_step_s=float(ledger_contract["time_step_s"]),
        steps=int(ledger_contract["steps"]),
        port_heat_flux_W_m2=float(ledger_contract["port_heat_flux_W_m2"]),
        initial_temperature_rise_K=float(
            ledger_contract["initial_temperature_rise_K"]
        ),
        storage_tamper_W_m2=tamper,
    )
    sink_tamper = cauer.backward_euler_ledger(
        time_step_s=float(ledger_contract["time_step_s"]),
        steps=int(ledger_contract["steps"]),
        port_heat_flux_W_m2=float(ledger_contract["port_heat_flux_W_m2"]),
        initial_temperature_rise_K=float(
            ledger_contract["initial_temperature_rise_K"]
        ),
        sink_tamper_W_m2=tamper,
    )
    return {
        "dc_moment_relative_error": float(dc_error),
        "first_dynamic_moment_relative_error": float(moment_error),
        "step_nrmse": step_nrmse,
        "regularized_impulse_nrmse": pulse_nrmse,
        "frequency_log_magnitude_rmse": frequency_rmse,
        "cauer_reconstruction_relative_error_max": reconstruction,
        "cauer_state_space_reconstruction_relative_error_max": state_reconstruction,
        "cauer_dc_impedance_relative_error": cauer_dc_error,
        "cauer_first_moment_relative_error": cauer_moment_error,
        "cauer_step_reconstruction_relative_error_max": cauer_step_error,
        "cauer_pulse_reconstruction_relative_error_max": cauer_pulse_error,
        "minimum_analytic_Z_real_relative_to_DC": float(
            np.min(analytic_z_samples.real) / analytic.resistance_m2K_W
        ),
        "minimum_analytic_Y_real_relative_to_DC": float(
            np.min(analytic_y_samples.real) / analytic.gtheta_A_W_m2K
        ),
        "minimum_foster_Z_real_relative_to_DC": float(np.min(z_samples.real) / analytic.resistance_m2K_W),
        "minimum_cauer_Y_real_relative_to_DC": float(np.min(y_samples.real) / analytic.gtheta_A_W_m2K),
        "maximum_foster_pole_real_per_s": float(np.max(foster.poles_per_s())),
        "maximum_cauer_pole_real_per_s": float(np.max(cauer.poles_per_s())),
        "minimum_foster_resistance_m2K_W": float(np.min(foster.resistances_m2K_W)),
        "minimum_foster_time_constant_s": float(np.min(foster.time_constants_s)),
        "minimum_foster_capacity_J_m2K": float(
            np.min(foster.time_constants_s / foster.resistances_m2K_W)
        ),
        "minimum_cauer_capacity_J_m2K": float(np.min(cauer.capacities_J_m2K)),
        "minimum_cauer_series_resistance_m2K_W": float(np.min(cauer.series_resistances_m2K_W)) if cauer.series_resistances_m2K_W.size else float("inf"),
        "terminal_cauer_conductance_W_m2K": float(cauer.terminal_conductance_W_m2K),
        "independent_cauer_ledger_relative_residual": float(
            ledger["maximum_relative_residual"]
        ),
        "tampered_storage_ledger_relative_residual": float(
            storage_tamper["maximum_relative_residual"]
        ),
        "tampered_sink_ledger_relative_residual": float(
            sink_tamper["maximum_relative_residual"]
        ),
        "cauer_independent_vertical_state_count": float(
            cauer.independent_vertical_state_count
        ),
    }


def metrics_pass(
    metrics: dict[str, float],
    gates: dict,
    *,
    cauer_reconstruction_tolerance: float,
    ledger_tolerance: float,
) -> bool:
    positive_real_floor = float(
        gates["positive_real_check"]["minimum_real_part_relative_to_DC_scale"]
    )
    return bool(
        metrics["dc_moment_relative_error"] <= float(gates["dc_moment_relative_error_max"])
        and metrics["first_dynamic_moment_relative_error"] <= float(gates["first_dynamic_moment_relative_error_max"])
        and metrics["step_nrmse"] <= float(gates["step_nrmse_max"])
        and metrics["regularized_impulse_nrmse"] <= float(gates["regularized_impulse_nrmse_max"])
        and metrics["frequency_log_magnitude_rmse"] <= float(gates["frequency_log_magnitude_rmse_max"])
        and metrics["cauer_reconstruction_relative_error_max"]
        <= float(cauer_reconstruction_tolerance)
        and metrics["cauer_state_space_reconstruction_relative_error_max"]
        <= float(cauer_reconstruction_tolerance)
        and metrics["cauer_dc_impedance_relative_error"]
        <= float(cauer_reconstruction_tolerance)
        and metrics["cauer_first_moment_relative_error"]
        <= float(cauer_reconstruction_tolerance)
        and metrics["cauer_step_reconstruction_relative_error_max"]
        <= float(cauer_reconstruction_tolerance)
        and metrics["cauer_pulse_reconstruction_relative_error_max"]
        <= float(cauer_reconstruction_tolerance)
        and metrics["minimum_analytic_Z_real_relative_to_DC"] >= positive_real_floor
        and metrics["minimum_analytic_Y_real_relative_to_DC"] >= positive_real_floor
        and metrics["minimum_foster_Z_real_relative_to_DC"] >= positive_real_floor
        and metrics["minimum_cauer_Y_real_relative_to_DC"] >= positive_real_floor
        and metrics["maximum_foster_pole_real_per_s"] < 0.0
        and metrics["maximum_cauer_pole_real_per_s"] < 0.0
        and metrics["minimum_foster_resistance_m2K_W"] > 0.0
        and metrics["minimum_foster_time_constant_s"] > 0.0
        and metrics["minimum_foster_capacity_J_m2K"] > 0.0
        and metrics["minimum_cauer_capacity_J_m2K"] > 0.0
        and metrics["minimum_cauer_series_resistance_m2K_W"] > 0.0
        and metrics["terminal_cauer_conductance_W_m2K"] > 0.0
        and metrics["independent_cauer_ledger_relative_residual"]
        <= float(ledger_tolerance)
        and metrics["tampered_storage_ledger_relative_residual"]
        > float(ledger_tolerance)
        and metrics["tampered_sink_ledger_relative_residual"]
        > float(ledger_tolerance)
    )
