"""Event-resolved integration of the Qiu-2024 lumped thermal neuristor.

The ODE right-hand side is pure within each integration segment.  For the
LLP hysteresis variant, a segment terminates when ``dT/dt`` changes sign; only
then is the immutable reversal ledger replaced.  This is an explicit
repository implementation assumption because Qiu et al. report equations
S1--S7 but do not publish an executable event-update algorithm or integrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.integrate import solve_ivp

from pinnpcm.physics.qiu_author_compact_model import (
    LLPReversalLedger,
    ModelVariant,
    QiuAuthorCompactParameters,
    compact_rhs,
    dynamic_resistance_ohm,
    initialize_ledger,
    update_ledger_at_reversal,
)


@dataclass(frozen=True)
class QiuAuthorSimulation:
    """A scored trajectory with explicit event and conservation evidence."""

    time_s: np.ndarray
    current_A: np.ndarray
    voltage_V: np.ndarray
    temperature_K: np.ndarray
    resistance_ohm: np.ndarray
    branch_delta: np.ndarray
    event_records: tuple[dict[str, Any], ...]
    metrics: dict[str, Any]
    method: str
    variant: ModelVariant
    solver_statistics: dict[str, int | float | str]

    def to_dict(self) -> dict[str, Any]:
        """Return a strict-JSON-ready representation (all arrays become lists)."""

        return {
            "time_s": self.time_s.tolist(),
            "current_A": self.current_A.tolist(),
            "voltage_V": self.voltage_V.tolist(),
            "temperature_K": self.temperature_K.tolist(),
            "resistance_ohm": self.resistance_ohm.tolist(),
            "branch_delta": self.branch_delta.astype(int).tolist(),
            "event_records": [dict(record) for record in self.event_records],
            "metrics": dict(self.metrics),
            "method": self.method,
            "variant": self.variant,
            "solver_statistics": dict(self.solver_statistics),
        }


def simulate(
    params: QiuAuthorCompactParameters,
    input_voltage_V: float,
    evaluation_times_s: Sequence[float] | np.ndarray,
    method: str,
    solver_config: Mapping[str, Any],
    *,
    variant: ModelVariant = "hysteresis",
) -> QiuAuthorSimulation:
    """Integrate equations S5--S7 with event-localized LLP reversals.

    Parameters are intentionally explicit.  ``solver_config`` may be either
    the full preregistration mapping (containing ``solvers``) or that nested
    solver mapping itself.  The first evaluation time must be zero because the
    preregistered initial state is defined at ``t=0``.
    """

    params.validate()
    if method not in {"DOP853", "Radau"}:
        raise ValueError("method must be DOP853 or Radau")
    if variant not in {"hysteresis", "no_hysteresis", "fixed_heating"}:
        raise ValueError(f"unsupported Qiu compact-model variant: {variant}")
    voltage_input = float(input_voltage_V)
    if not np.isfinite(voltage_input):
        raise ValueError("input_voltage_V must be finite")

    times = np.asarray(evaluation_times_s, dtype=np.float64)
    if times.ndim != 1 or times.size < 2 or not np.isfinite(times).all():
        raise ValueError("evaluation_times_s must contain at least two finite values")
    if times[0] != 0.0 or np.any(np.diff(times) <= 0.0):
        raise ValueError("evaluation_times_s must start at zero and increase strictly")

    options = _solver_options(solver_config)
    ledger = initialize_ledger(params)
    state = np.asarray(
        [params.initial_capacitor_voltage_V, params.initial_device_temperature_K],
        dtype=np.float64,
    )
    voltage = np.full(times.shape, np.nan, dtype=np.float64)
    temperature = np.full(times.shape, np.nan, dtype=np.float64)
    resistance = np.full(times.shape, np.nan, dtype=np.float64)
    branch_delta = np.zeros(times.shape, dtype=np.int8)
    event_records: list[dict[str, Any]] = []

    segment_start = float(times[0])
    final_time = float(times[-1])
    segment_count = 0
    totals = {"nfev": 0, "njev": 0, "nlu": 0}
    last_event_time = -np.inf

    while segment_start < final_time:
        segment_count += 1
        if segment_count > options["maximum_reversal_restarts"] + 1:
            raise RuntimeError("maximum LLP reversal restarts exceeded")

        fixed_ledger = ledger

        def rhs(time_s: float, values: np.ndarray) -> np.ndarray:
            return compact_rhs(
                time_s,
                values,
                params=params,
                input_voltage_V=voltage_input,
                ledger=fixed_ledger,
                variant=variant,
            )

        events = None
        if variant == "hysteresis":
            # This epsilon only prevents solve_ivp from immediately re-detecting
            # the terminal zero at a segment restart.  It is neither a physical
            # direction deadband nor a temperature hysteresis parameter.
            restart_epsilon_s = max(
                1.0e-15,
                64.0 * np.finfo(np.float64).eps * max(1.0, abs(segment_start)),
            )

            def temperature_reversal(time_s: float, values: np.ndarray) -> float:
                if time_s <= segment_start + restart_epsilon_s:
                    return 1.0
                derivative = rhs(time_s, values)
                return float(fixed_ledger.delta * derivative[1])

            temperature_reversal.terminal = True
            temperature_reversal.direction = -1.0
            events = temperature_reversal

        solution = solve_ivp(
            rhs,
            (segment_start, final_time),
            state,
            method=method,
            rtol=options["rtol"],
            atol=np.asarray(
                [options["atol_voltage_V"], options["atol_temperature_K"]],
                dtype=np.float64,
            ),
            max_step=options["maximum_step_s"],
            dense_output=True,
            events=events,
        )
        if not solution.success or solution.sol is None:
            raise RuntimeError(f"{method} integration failed: {solution.message}")
        for name in totals:
            totals[name] += int(getattr(solution, name, 0) or 0)

        segment_stop = float(solution.t[-1])
        pending = np.isnan(voltage)
        in_segment = pending & (times >= segment_start) & (
            times <= segment_stop + 8.0 * np.finfo(np.float64).eps
        )
        if np.any(in_segment):
            values = np.asarray(solution.sol(times[in_segment]), dtype=np.float64)
            voltage[in_segment] = values[0]
            temperature[in_segment] = values[1]
            resistance[in_segment] = np.asarray(
                dynamic_resistance_ohm(
                    values[1], fixed_ledger, params, variant=variant
                ),
                dtype=np.float64,
            )
            branch_delta[in_segment] = fixed_ledger.delta

        event_occurred = (
            variant == "hysteresis"
            and solution.t_events is not None
            and len(solution.t_events) == 1
            and solution.t_events[0].size == 1
        )
        if not event_occurred:
            if segment_stop < final_time:
                raise RuntimeError("integration stopped before the requested final time")
            break

        event_time = float(solution.t_events[0][0])
        event_state = np.asarray(solution.y_events[0][0], dtype=np.float64)
        if event_time <= segment_start or event_time <= last_event_time:
            raise RuntimeError("LLP event localization made no forward-time progress")
        new_ledger = update_ledger_at_reversal(event_state[1], fixed_ledger, params)
        event_records.append(
            {
                "event_index": len(event_records),
                "event_type": (
                    "heating_to_cooling"
                    if fixed_ledger.delta == 1
                    else "cooling_to_heating"
                ),
                "time_s": event_time,
                "voltage_V": float(event_state[0]),
                "temperature_K": float(event_state[1]),
                "delta_before": int(fixed_ledger.delta),
                "delta_after": int(new_ledger.delta),
                "reversal_fraction": float(new_ledger.reversal_fraction),
                "proximity_temperature_K": float(
                    new_ledger.proximity_temperature_K
                ),
            }
        )
        last_event_time = event_time
        segment_start = event_time
        state = event_state
        ledger = new_ledger

    if not (
        np.isfinite(voltage).all()
        and np.isfinite(temperature).all()
        and np.isfinite(resistance).all()
    ):
        raise RuntimeError("event-resolved solver did not populate the full output grid")
    if np.any(temperature <= 0.0) or np.any(resistance <= 0.0):
        raise RuntimeError("event-resolved solver produced a nonphysical state")

    current = voltage / resistance
    metrics = _trajectory_metrics(
        times,
        voltage,
        current,
        temperature,
        event_records,
        params,
    )
    statistics: dict[str, int | float | str] = {
        "method": method,
        "segments": segment_count,
        "nfev": totals["nfev"],
        "njev": totals["njev"],
        "nlu": totals["nlu"],
        "maximum_step_s": options["maximum_step_s"],
        "rtol": options["rtol"],
    }
    return QiuAuthorSimulation(
        time_s=times.copy(),
        current_A=current,
        voltage_V=voltage,
        temperature_K=temperature,
        resistance_ohm=resistance,
        branch_delta=branch_delta,
        event_records=tuple(event_records),
        metrics=metrics,
        method=method,
        variant=variant,
        solver_statistics=statistics,
    )


def _solver_options(config: Mapping[str, Any]) -> dict[str, float | int]:
    raw = config["solvers"] if "solvers" in config else config
    options: dict[str, float | int] = {
        "rtol": float(raw["rtol"]),
        "atol_voltage_V": float(raw["atol_voltage_V"]),
        "atol_temperature_K": float(raw["atol_temperature_K"]),
        "maximum_step_s": float(raw["maximum_step_s"]),
        "maximum_reversal_restarts": int(raw["maximum_reversal_restarts"]),
    }
    for name in (
        "rtol",
        "atol_voltage_V",
        "atol_temperature_K",
        "maximum_step_s",
    ):
        if not np.isfinite(options[name]) or float(options[name]) <= 0.0:
            raise ValueError(f"solver option {name} must be finite and positive")
    if int(options["maximum_reversal_restarts"]) < 0:
        raise ValueError("maximum_reversal_restarts must be nonnegative")
    return options


def _trajectory_metrics(
    times: np.ndarray,
    voltage: np.ndarray,
    current: np.ndarray,
    temperature: np.ndarray,
    events: list[dict[str, Any]],
    params: QiuAuthorCompactParameters,
) -> dict[str, Any]:
    joule_power = voltage * current
    outward_power = params.thermal_conductance_W_per_K * (
        temperature - params.ambient_temperature_K
    )
    charge = float(np.trapz(current, times))
    joule_energy = float(np.trapz(joule_power, times))
    outward_heat = float(np.trapz(outward_power, times))
    storage_change = float(
        params.thermal_capacitance_J_per_K
        * (temperature[-1] - temperature[0])
    )
    ledger_residual = storage_change + outward_heat - joule_energy
    ledger_scale = max(
        abs(storage_change) + abs(outward_heat) + abs(joule_energy),
        np.finfo(np.float64).tiny,
    )

    maxima_times = np.asarray(
        [
            record["time_s"]
            for record in events
            if record["event_type"] == "heating_to_cooling"
        ],
        dtype=np.float64,
    )
    periods = np.diff(maxima_times)
    if maxima_times.size >= 3:
        activity_class = "sustained_oscillation"
    elif events:
        activity_class = "transient_or_irregular"
    else:
        activity_class = "nonoscillatory"

    cycle_charge = None
    cycle_energy = None
    if maxima_times.size >= 2:
        last_start, last_stop = maxima_times[-2:]
        mask = (times >= last_start) & (times <= last_stop)
        if np.count_nonzero(mask) >= 2:
            cycle_charge = float(np.trapz(current[mask], times[mask]))
            cycle_energy = float(np.trapz(joule_power[mask], times[mask]))

    return {
        "activity_class": activity_class,
        "event_count": len(events),
        "heating_to_cooling_event_count": int(maxima_times.size),
        "cooling_to_heating_event_count": int(len(events) - maxima_times.size),
        "period_count": int(periods.size),
        "median_period_s": float(np.median(periods)) if periods.size else None,
        "charge_C": charge,
        "joule_energy_J": joule_energy,
        "outward_heat_J": outward_heat,
        "thermal_storage_change_J": storage_change,
        "energy_ledger_residual_J": float(ledger_residual),
        "energy_ledger_relative_imbalance": float(abs(ledger_residual) / ledger_scale),
        "charge_per_last_cycle_C": cycle_charge,
        "energy_per_last_cycle_J": cycle_energy,
        "peak_current_A": float(np.max(current)),
        "minimum_current_A": float(np.min(current)),
        "peak_temperature_K": float(np.max(temperature)),
        "minimum_temperature_K": float(np.min(temperature)),
        "minimum_joule_power_W": float(np.min(joule_power)),
    }
