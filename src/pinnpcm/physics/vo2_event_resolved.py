"""Independent root-located reference for the Zhang VO2 compact model.

The source-compatible implementation updates its hysteresis ledger on a
sampled explicit-Euler grid.  This module deliberately uses a different,
continuous event convention: it root-locates a thermal extremum, waits for the
same configured temperature reversal distance, and only then updates the
history ledger.  The two conventions share the physical branch RHS but are
not called the same numerical model; M36 must demonstrate their limiting
agreement instead of assuming it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.integrate import solve_ivp

from pinnpcm.physics.vo2_thermal_neuristor import (
    HysteresisLedger,
    NeuristorTrace,
    VO2ThermalNeuristorParameters,
    _phase_insulating_fraction,
    _t_pr,
    initialize_ledger,
    resistance_ohm,
    simulate_source_compat_si,
)


@dataclass(frozen=True)
class EventResolvedResult:
    """A trace plus an explicit hybrid-event ledger."""

    trace: NeuristorTrace
    event_records: tuple[dict[str, Any], ...]
    method: str
    event_semantics: str
    solver_statistics: Mapping[str, int]


def _copy_ledger(ledger: HysteresisLedger) -> HysteresisLedger:
    return HysteresisLedger(
        delta=float(ledger.delta),
        reversed_flag=float(ledger.reversed_flag),
        T_r_K=float(ledger.T_r_K),
        g_r=float(ledger.g_r),
        T_pr_K=float(ledger.T_pr_K),
        T_last_K=float(ledger.T_last_K),
    )


def _rhs(
    _time_s: float,
    state: np.ndarray,
    *,
    input_voltage_V: float,
    params: VO2ThermalNeuristorParameters,
    ledger: HysteresisLedger,
) -> np.ndarray:
    voltage_V = float(state[0])
    temperature_K = float(state[1])
    resistance = resistance_ohm(temperature_K, ledger, params)
    dV_dt = (
        input_voltage_V / (params.R_load_ohm * params.C_F)
        - voltage_V / (params.R_load_ohm * params.C_F)
        - voltage_V / (resistance * params.C_F)
    )
    joule_power_W = voltage_V * voltage_V / resistance
    dT_dt = (
        (joule_power_W - params.S_th_W_per_K * (temperature_K - params.T_base_K))
        / params.C_th_J_per_K
    ) / params.Cth_factor
    return np.asarray([dV_dt, dT_dt], dtype=np.float64)


def _apply_continuous_reversal(
    temperature_K: float,
    ledger: HysteresisLedger,
    params: VO2ThermalNeuristorParameters,
) -> tuple[float, float]:
    """Apply one root-located branch update and return old/new branch."""

    clipped = float(np.clip(temperature_K, *params.temperature_clip_K))
    old_delta = float(ledger.delta)
    new_delta = -old_delta
    ledger.g_r = _phase_insulating_fraction(clipped, ledger, params)
    ledger.delta = new_delta
    ledger.reversed_flag = 1.0
    ledger.T_r_K = clipped
    ledger.T_pr_K = _t_pr(new_delta, ledger.g_r, clipped, params)
    ledger.T_last_K = clipped
    return old_delta, new_delta


def _deduplicate_event_records(
    records: list[dict[str, Any]], *, time_tolerance_s: float
) -> tuple[dict[str, Any], ...]:
    ordered = sorted(records, key=lambda row: (float(row["time_s"]), str(row["event_type"])))
    result: list[dict[str, Any]] = []
    for row in ordered:
        if result and row["event_type"] == result[-1]["event_type"]:
            if abs(float(row["time_s"]) - float(result[-1]["time_s"])) <= time_tolerance_s:
                continue
        result.append(row)
    return tuple(result)


def simulate_event_resolved_si(
    params: VO2ThermalNeuristorParameters,
    *,
    input_voltage_V: float,
    evaluation_times_s: Sequence[float],
    method: str,
    reference_config: Mapping[str, Any],
) -> EventResolvedResult:
    """Integrate the continuous-event reference with DOP853 or Radau.

    Reversal order is fixed: branch integration -> extremum root -> exact
    temperature-delay root -> old-branch phase evaluation -> ledger update.
    Temperature clip-boundary roots are recorded but do not alter the physical
    state, matching the fact that clipping applies to the constitutive law.
    """

    if method not in {"DOP853", "Radau"}:
        raise ValueError(f"Unsupported independent reference method: {method}")
    times = np.asarray(evaluation_times_s, dtype=np.float64)
    if times.ndim != 1 or times.size < 2 or np.any(np.diff(times) <= 0.0):
        raise ValueError("evaluation_times_s must be a strictly increasing vector.")
    if times[0] < 0.0:
        raise ValueError("The event-resolved solver only accepts nonnegative times.")

    rtol = float(reference_config["rtol"])
    atol = np.asarray(
        [
            float(reference_config["atol_voltage_V"]),
            float(reference_config["atol_temperature_K"]),
        ],
        dtype=np.float64,
    )
    max_step = float(reference_config["max_step_s"])
    epsilon = float(reference_config["event_time_epsilon_s"])
    reversal_delay = float(reference_config["reversal_delay_K"])
    low_boundary, high_boundary = (
        float(value) for value in reference_config["temperature_boundaries_K"]
    )
    maximum_segments = int(reference_config["maximum_event_segments"])

    ledger = initialize_ledger(params)
    state = np.asarray([0.0, params.T_base_K], dtype=np.float64)
    start_s = 0.0
    end_s = float(times[-1])
    mode = "seek_extremum"
    reversal_target_K: float | None = None
    voltage = np.full(times.shape, np.nan, dtype=np.float64)
    temperature = np.full(times.shape, np.nan, dtype=np.float64)
    branch = np.full(times.shape, np.nan, dtype=np.float64)
    filled = np.zeros(times.shape, dtype=bool)
    event_records: list[dict[str, Any]] = []
    statistics = {"nfev": 0, "njev": 0, "nlu": 0, "segments": 0}

    while start_s < end_s - epsilon:
        if statistics["segments"] >= maximum_segments:
            raise RuntimeError("Independent reference exceeded the event-segment budget.")
        segment_start = start_s
        segment_ledger = _copy_ledger(ledger)

        if mode == "seek_extremum":
            def primary_event(time_s: float, values: np.ndarray) -> float:
                if time_s <= segment_start + epsilon:
                    return 1.0
                derivative = _rhs(
                    time_s,
                    values,
                    input_voltage_V=input_voltage_V,
                    params=params,
                    ledger=segment_ledger,
                )
                return float(segment_ledger.delta * derivative[1])

            primary_event.direction = -1.0
            primary_event.terminal = True
        else:
            if reversal_target_K is None:
                raise RuntimeError("Missing reversal target in delay-root mode.")

            def primary_event(time_s: float, values: np.ndarray) -> float:
                if time_s <= segment_start + epsilon:
                    return reversal_delay
                return float(segment_ledger.delta * (values[1] - reversal_target_K))

            primary_event.direction = -1.0
            primary_event.terminal = True

        def lower_boundary_event(_time_s: float, values: np.ndarray) -> float:
            return float(values[1] - low_boundary)

        def upper_boundary_event(_time_s: float, values: np.ndarray) -> float:
            return float(values[1] - high_boundary)

        lower_boundary_event.direction = 0.0
        lower_boundary_event.terminal = False
        upper_boundary_event.direction = 0.0
        upper_boundary_event.terminal = False

        solution = solve_ivp(
            lambda t, y: _rhs(
                t,
                y,
                input_voltage_V=input_voltage_V,
                params=params,
                ledger=segment_ledger,
            ),
            (segment_start, end_s),
            state,
            method=method,
            rtol=rtol,
            atol=atol,
            max_step=max_step,
            dense_output=True,
            events=(primary_event, lower_boundary_event, upper_boundary_event),
        )
        if not solution.success or solution.sol is None:
            raise RuntimeError(f"{method} event-resolved integration failed: {solution.message}")
        statistics["segments"] += 1
        statistics["nfev"] += int(solution.nfev)
        statistics["njev"] += int(getattr(solution, "njev", 0) or 0)
        statistics["nlu"] += int(getattr(solution, "nlu", 0) or 0)

        segment_end = float(solution.t[-1])
        mask = (~filled) & (times >= segment_start - epsilon) & (times <= segment_end + epsilon)
        if np.any(mask):
            evaluated = solution.sol(times[mask])
            voltage[mask] = evaluated[0]
            temperature[mask] = evaluated[1]
            branch[mask] = float(segment_ledger.delta)
            filled[mask] = True

        for boundary_index, event_type in ((1, "temperature_boundary_low"), (2, "temperature_boundary_high")):
            for event_time, event_state in zip(
                solution.t_events[boundary_index], solution.y_events[boundary_index]
            ):
                event_records.append(
                    {
                        "event_type": event_type,
                        "time_s": float(event_time),
                        "temperature_K": float(event_state[1]),
                        "branch_before": float(segment_ledger.delta),
                        "branch_after": float(segment_ledger.delta),
                    }
                )

        if solution.t_events[0].size == 0:
            state = np.asarray(solution.y[:, -1], dtype=np.float64)
            start_s = end_s
            break

        event_time = float(solution.t_events[0][-1])
        event_state = np.asarray(solution.y_events[0][-1], dtype=np.float64)
        if event_time <= segment_start:
            raise RuntimeError("Independent event solver made no temporal progress.")
        if mode == "seek_extremum":
            event_type = "thermal_extremum_high" if ledger.delta > 0.0 else "thermal_extremum_low"
            event_records.append(
                {
                    "event_type": event_type,
                    "time_s": event_time,
                    "temperature_K": float(event_state[1]),
                    "branch_before": float(ledger.delta),
                    "branch_after": float(ledger.delta),
                }
            )
            reversal_target_K = float(event_state[1] - ledger.delta * reversal_delay)
            mode = "seek_reversal_delay"
        else:
            old_delta, new_delta = _apply_continuous_reversal(
                float(event_state[1]), ledger, params
            )
            event_records.append(
                {
                    "event_type": "reversal_to_cooling" if new_delta < 0.0 else "reversal_to_heating",
                    "time_s": event_time,
                    "temperature_K": float(event_state[1]),
                    "branch_before": old_delta,
                    "branch_after": new_delta,
                }
            )
            reversal_target_K = None
            mode = "seek_extremum"
        state = event_state
        start_s = event_time

    if not np.all(filled):
        missing = np.flatnonzero(~filled)
        if missing.size and abs(times[missing[-1]] - end_s) <= 10.0 * epsilon:
            voltage[missing] = state[0]
            temperature[missing] = state[1]
            branch[missing] = ledger.delta
            filled[missing] = True
    if not np.all(filled) or not np.isfinite(voltage).all() or not np.isfinite(temperature).all():
        raise RuntimeError("Independent reference did not populate every requested output time.")

    resistance = np.empty_like(temperature)
    current = np.empty_like(temperature)
    records = _deduplicate_event_records(event_records, time_tolerance_s=10.0 * epsilon)
    reversal_records = [row for row in records if str(row["event_type"]).startswith("reversal_")]
    current_ledger = initialize_ledger(params)
    reversal_index = 0
    for index, (time_s, temp, value) in enumerate(zip(times, temperature, voltage)):
        while (
            reversal_index < len(reversal_records)
            and float(reversal_records[reversal_index]["time_s"]) <= float(time_s) + epsilon
        ):
            row = reversal_records[reversal_index]
            _apply_continuous_reversal(float(row["temperature_K"]), current_ledger, params)
            reversal_index += 1
        resistance[index] = resistance_ohm(float(temp), current_ledger, params)
        current[index] = float(value) / resistance[index]

    trace = NeuristorTrace(
        time_s=times.copy(),
        current_A=current,
        voltage_V=voltage,
        temperature_K=temperature,
        resistance_ohm=resistance,
        event_times_s=np.asarray(
            [float(row["time_s"]) for row in reversal_records], dtype=np.float64
        ),
        branch=branch,
        source_kind=f"independent_{method.lower()}_continuous_event_reference",
    )
    return EventResolvedResult(
        trace=trace,
        event_records=records,
        method=method,
        event_semantics="continuous_extremum_root_located_hysteresis_reference",
        solver_statistics=statistics,
    )


def simulate_source_compatible_family_member(
    params: VO2ThermalNeuristorParameters,
    *,
    input_voltage_V: float,
    t_max_s: float,
    dt_s: float,
) -> EventResolvedResult:
    """Run the unchanged sampled-Euler source family and label its events."""

    trace = simulate_source_compat_si(
        params,
        input_voltage_V=input_voltage_V,
        t_max_s=t_max_s,
        dt_s=dt_s,
        noise_strength=0.0,
        seed=0,
    )
    records: list[dict[str, Any]] = []
    for index, time_s in enumerate(trace.event_times_s):
        new_delta = -1.0 if index % 2 == 0 else 1.0
        records.append(
            {
                "event_type": "reversal_to_cooling" if new_delta < 0.0 else "reversal_to_heating",
                "time_s": float(time_s),
                "temperature_K": float(np.interp(time_s, trace.time_s, trace.temperature_K)),
                "branch_before": -new_delta,
                "branch_after": new_delta,
            }
        )
    return EventResolvedResult(
        trace=trace,
        event_records=tuple(records),
        method="explicit_Euler",
        event_semantics="source_compatible_threshold_sampled_explicit_euler",
        solver_statistics={"steps": int(trace.time_s.size), "segments": 1},
    )


def event_sequence_signature(
    records: Sequence[Mapping[str, Any]], *, include_extrema: bool = False
) -> tuple[str, ...]:
    allowed_prefixes = ("reversal_", "temperature_boundary_")
    if include_extrema:
        allowed_prefixes = allowed_prefixes + ("thermal_extremum_",)
    return tuple(
        str(row["event_type"])
        for row in records
        if str(row["event_type"]).startswith(allowed_prefixes)
    )
