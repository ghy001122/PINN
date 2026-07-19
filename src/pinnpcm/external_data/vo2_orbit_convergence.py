"""Branch-aware numerical metrics for M36 VO2 convergence audits."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from pinnpcm.external_data.vo2_multivoltage import activity_metrics, nrmse95
from pinnpcm.physics.vo2_event_resolved import EventResolvedResult
from pinnpcm.physics.vo2_thermal_neuristor import (
    NeuristorTrace,
    VO2ThermalNeuristorParameters,
)


def _relative_error(value: float, reference: float, floor: float = 1.0e-30) -> float:
    return float(abs(value - reference) / max(abs(reference), floor))


def _common_candidate(
    reference: NeuristorTrace, candidate: NeuristorTrace
) -> dict[str, np.ndarray]:
    time_s = reference.time_s
    return {
        "time_s": time_s,
        "current_A": np.interp(time_s, candidate.time_s, candidate.current_A),
        "voltage_V": np.interp(time_s, candidate.time_s, candidate.voltage_V),
        "temperature_K": np.interp(time_s, candidate.time_s, candidate.temperature_K),
        "resistance_ohm": np.interp(time_s, candidate.time_s, candidate.resistance_ohm),
    }


def _integrals(time_s: np.ndarray, current_A: np.ndarray, voltage_V: np.ndarray) -> tuple[float, float]:
    charge = float(np.trapz(np.maximum(current_A, 0.0), time_s))
    energy = float(np.trapz(np.maximum(current_A * voltage_V, 0.0), time_s))
    return charge, energy


def _reversal_records(
    result: EventResolvedResult, *, start_s: float
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in result.event_records
        if str(row["event_type"]).startswith("reversal_")
        and float(row["time_s"]) >= start_s
    ]


def _cooling_anchors(
    result: EventResolvedResult, *, start_s: float
) -> np.ndarray:
    return np.asarray(
        [
            float(row["time_s"])
            for row in result.event_records
            if row["event_type"] == "reversal_to_cooling"
            and float(row["time_s"]) >= start_s
        ],
        dtype=np.float64,
    )


def _event_comparison(
    reference: EventResolvedResult,
    candidate: EventResolvedResult,
    *,
    start_s: float,
    voltage_V: float,
    candidate_label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reference_events = _reversal_records(reference, start_s=start_s)
    candidate_events = _reversal_records(candidate, start_s=start_s)
    pair_count = min(len(reference_events), len(candidate_events))
    errors = np.asarray(
        [
            float(candidate_events[index]["time_s"])
            - float(reference_events[index]["time_s"])
            for index in range(pair_count)
        ],
        dtype=np.float64,
    )
    if pair_count >= 2:
        phase_drift = float(np.polyfit(np.arange(pair_count, dtype=np.float64), errors, 1)[0])
    else:
        phase_drift = float("inf")
    rows = [
        {
            "voltage_V": float(voltage_V),
            "candidate": candidate_label,
            "event_index": int(index),
            "reference_event_type": str(reference_events[index]["event_type"]),
            "candidate_event_type": str(candidate_events[index]["event_type"]),
            "reference_time_s": float(reference_events[index]["time_s"]),
            "candidate_time_s": float(candidate_events[index]["time_s"]),
            "event_time_error_s": float(errors[index]),
        }
        for index in range(pair_count)
    ]
    type_match = bool(
        len(reference_events) == len(candidate_events)
        and all(
            reference_events[index]["event_type"] == candidate_events[index]["event_type"]
            for index in range(pair_count)
        )
    )
    return (
        {
            "reference_reversal_event_count": len(reference_events),
            "candidate_reversal_event_count": len(candidate_events),
            "reversal_event_count_exact": len(reference_events) == len(candidate_events),
            "reversal_event_type_sequence_exact": type_match,
            "paired_reversal_event_count": pair_count,
            "maximum_event_time_error_s": float(np.max(np.abs(errors)))
            if errors.size
            else float("inf"),
            "median_event_time_error_s": float(np.median(np.abs(errors)))
            if errors.size
            else float("inf"),
            "phase_drift_s_per_event": phase_drift,
        },
        rows,
    )


def _cycle_shape_and_qoi(
    reference: EventResolvedResult,
    candidate: EventResolvedResult,
    *,
    start_s: float,
    phase_points: int,
    current_floor_A: float,
    voltage_floor_V: float,
) -> dict[str, Any]:
    reference_anchors = _cooling_anchors(reference, start_s=start_s)
    candidate_anchors = _cooling_anchors(candidate, start_s=start_s)
    cycle_count = min(reference_anchors.size, candidate_anchors.size) - 1
    if cycle_count < 1:
        return {
            "paired_cycle_count": 0,
            "period_relative_error": float("inf"),
            "frequency_relative_error": float("inf"),
            "cycle_shape_current_nrmse95": float("inf"),
            "cycle_shape_voltage_nrmse95": float("inf"),
            "cycle_shape_combined_nrmse95": float("inf"),
            "cycle_peak_relative_error": float("inf"),
            "cycle_duty_cycle_absolute_error": float("inf"),
            "cycle_charge_relative_error": float("inf"),
            "cycle_energy_relative_error": float("inf"),
        }

    phase = np.linspace(0.0, 1.0, int(phase_points), dtype=np.float64)
    current_errors: list[float] = []
    voltage_errors: list[float] = []
    peak_errors: list[float] = []
    duty_errors: list[float] = []
    charge_errors: list[float] = []
    energy_errors: list[float] = []
    reference_periods: list[float] = []
    candidate_periods: list[float] = []
    for index in range(cycle_count):
        r0, r1 = float(reference_anchors[index]), float(reference_anchors[index + 1])
        c0, c1 = float(candidate_anchors[index]), float(candidate_anchors[index + 1])
        r_time = r0 + phase * (r1 - r0)
        c_time = c0 + phase * (c1 - c0)
        r_current = np.interp(r_time, reference.trace.time_s, reference.trace.current_A)
        c_current = np.interp(c_time, candidate.trace.time_s, candidate.trace.current_A)
        r_voltage = np.interp(r_time, reference.trace.time_s, reference.trace.voltage_V)
        c_voltage = np.interp(c_time, candidate.trace.time_s, candidate.trace.voltage_V)
        current_errors.append(nrmse95(c_current, r_current, floor=current_floor_A))
        voltage_errors.append(nrmse95(c_voltage, r_voltage, floor=voltage_floor_V))
        r_peak = float(np.max(r_current) - np.min(r_current))
        c_peak = float(np.max(c_current) - np.min(c_current))
        peak_errors.append(_relative_error(c_peak, r_peak, current_floor_A))
        r_half = float(np.min(r_current) + 0.5 * r_peak)
        c_half = float(np.min(c_current) + 0.5 * c_peak)
        duty_errors.append(abs(float(np.mean(c_current >= c_half)) - float(np.mean(r_current >= r_half))))
        r_period = r1 - r0
        c_period = c1 - c0
        reference_periods.append(r_period)
        candidate_periods.append(c_period)
        r_charge = float(r_period * np.trapz(np.maximum(r_current, 0.0), phase))
        c_charge = float(c_period * np.trapz(np.maximum(c_current, 0.0), phase))
        r_energy = float(r_period * np.trapz(np.maximum(r_current * r_voltage, 0.0), phase))
        c_energy = float(c_period * np.trapz(np.maximum(c_current * c_voltage, 0.0), phase))
        charge_errors.append(_relative_error(c_charge, r_charge))
        energy_errors.append(_relative_error(c_energy, r_energy))

    reference_period = float(np.median(reference_periods))
    candidate_period = float(np.median(candidate_periods))
    period_error = _relative_error(candidate_period, reference_period)
    frequency_error = _relative_error(
        1.0 / candidate_period, 1.0 / reference_period
    )
    current_shape = float(np.median(current_errors))
    voltage_shape = float(np.median(voltage_errors))
    return {
        "paired_cycle_count": int(cycle_count),
        "reference_period_s": reference_period,
        "candidate_period_s": candidate_period,
        "period_relative_error": period_error,
        "frequency_relative_error": frequency_error,
        "cycle_shape_current_nrmse95": current_shape,
        "cycle_shape_voltage_nrmse95": voltage_shape,
        "cycle_shape_combined_nrmse95": 0.7 * current_shape + 0.3 * voltage_shape,
        "cycle_peak_relative_error": float(np.median(peak_errors)),
        "cycle_duty_cycle_absolute_error": float(np.median(duty_errors)),
        "cycle_charge_relative_error": float(np.median(charge_errors)),
        "cycle_energy_relative_error": float(np.median(energy_errors)),
    }


def cycle_energy_ledger(
    result: EventResolvedResult,
    params: VO2ThermalNeuristorParameters,
    *,
    input_voltage_V: float,
    start_s: float,
) -> dict[str, Any]:
    """Check electrical and thermal conservation over root-paired cycles."""

    anchors = _cooling_anchors(result, start_s=start_s)
    electrical: list[float] = []
    thermal: list[float] = []
    for left, right in zip(anchors[:-1], anchors[1:]):
        mask = (result.trace.time_s >= left) & (result.trace.time_s <= right)
        if np.count_nonzero(mask) < 4:
            continue
        time_s = result.trace.time_s[mask]
        voltage = result.trace.voltage_V[mask]
        temperature = result.trace.temperature_K[mask]
        resistance = result.trace.resistance_ohm[mask]
        source_power = input_voltage_V * (input_voltage_V - voltage) / params.R_load_ohm
        load_power = (input_voltage_V - voltage) ** 2 / params.R_load_ohm
        device_power = voltage**2 / resistance
        sink_power = params.S_th_W_per_K * (temperature - params.T_base_K)
        source_energy = float(np.trapz(source_power, time_s))
        load_energy = float(np.trapz(load_power, time_s))
        device_energy = float(np.trapz(device_power, time_s))
        sink_energy = float(np.trapz(sink_power, time_s))
        delta_cap = 0.5 * params.C_F * float(voltage[-1] ** 2 - voltage[0] ** 2)
        delta_thermal = params.C_th_J_per_K * params.Cth_factor * float(
            temperature[-1] - temperature[0]
        )
        electrical_residual = source_energy - load_energy - device_energy - delta_cap
        thermal_residual = device_energy - sink_energy - delta_thermal
        electrical_scale = max(
            abs(source_energy) + abs(load_energy) + abs(device_energy) + abs(delta_cap),
            1.0e-30,
        )
        thermal_scale = max(
            abs(device_energy) + abs(sink_energy) + abs(delta_thermal), 1.0e-30
        )
        electrical.append(abs(electrical_residual) / electrical_scale)
        thermal.append(abs(thermal_residual) / thermal_scale)
    return {
        "cycle_ledger_count": len(electrical),
        "electrical_cycle_ledger_relative_residual": float(np.median(electrical))
        if electrical
        else float("inf"),
        "thermal_cycle_ledger_relative_residual": float(np.median(thermal))
        if thermal
        else float("inf"),
        "cycle_ledger_relative_residual": max(
            float(np.median(electrical)) if electrical else float("inf"),
            float(np.median(thermal)) if thermal else float("inf"),
        ),
    }


def compare_solver_results(
    reference: EventResolvedResult,
    candidate: EventResolvedResult,
    *,
    voltage_V: float,
    regime: str,
    current_noise_A: float,
    voltage_noise_V: float,
    event_config: Mapping[str, Any],
    params: VO2ThermalNeuristorParameters,
    candidate_label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return static and oscillatory metrics without hidden time warping."""

    common = _common_candidate(reference.trace, candidate.trace)
    current_error = common["current_A"] - reference.trace.current_A
    voltage_error = common["voltage_V"] - reference.trace.voltage_V
    duration = float(reference.trace.time_s[-1] - reference.trace.time_s[0])
    transient_start = float(
        reference.trace.time_s[0] + float(event_config["transient_fraction"]) * duration
    )
    reference_activity = activity_metrics(
        reference.trace.time_s,
        reference.trace.current_A,
        reference.trace.voltage_V,
        event_config,
        noise_scale_A=current_noise_A,
    )
    candidate_activity = activity_metrics(
        reference.trace.time_s,
        common["current_A"],
        common["voltage_V"],
        event_config,
        noise_scale_A=current_noise_A,
    )
    reference_charge, reference_energy = _integrals(
        reference.trace.time_s, reference.trace.current_A, reference.trace.voltage_V
    )
    candidate_charge, candidate_energy = _integrals(
        reference.trace.time_s, common["current_A"], common["voltage_V"]
    )
    tail_start = int(0.8 * reference.trace.time_s.size)
    metrics: dict[str, Any] = {
        "voltage_V": float(voltage_V),
        "regime": regime,
        "candidate": candidate_label,
        "reference": reference.method,
        "reference_event_semantics": reference.event_semantics,
        "candidate_event_semantics": candidate.event_semantics,
        "current_absolute_rmse_A": float(np.sqrt(np.mean(current_error**2))),
        "current_absolute_max_error_A": float(np.max(np.abs(current_error))),
        "voltage_absolute_rmse_V": float(np.sqrt(np.mean(voltage_error**2))),
        "voltage_absolute_max_error_V": float(np.max(np.abs(voltage_error))),
        "current_absolute_rmse_noise_fraction": float(
            np.sqrt(np.mean(current_error**2)) / current_noise_A
        ),
        "current_max_error_noise_fraction": float(np.max(np.abs(current_error)) / current_noise_A),
        "voltage_absolute_rmse_noise_fraction": float(
            np.sqrt(np.mean(voltage_error**2)) / voltage_noise_V
        ),
        "voltage_max_error_noise_fraction": float(np.max(np.abs(voltage_error)) / voltage_noise_V),
        "full_horizon_current_nrmse95": nrmse95(
            common["current_A"], reference.trace.current_A, floor=current_noise_A
        ),
        "full_horizon_voltage_nrmse95": nrmse95(
            common["voltage_V"], reference.trace.voltage_V, floor=voltage_noise_V
        ),
        "steady_current_error_A": abs(
            float(np.median(common["current_A"][tail_start:]))
            - float(np.median(reference.trace.current_A[tail_start:]))
        ),
        "steady_voltage_error_V": abs(
            float(np.median(common["voltage_V"][tail_start:]))
            - float(np.median(reference.trace.voltage_V[tail_start:]))
        ),
        "steady_current_error_noise_fraction": abs(
            float(np.median(common["current_A"][tail_start:]))
            - float(np.median(reference.trace.current_A[tail_start:]))
        )
        / current_noise_A,
        "steady_voltage_error_noise_fraction": abs(
            float(np.median(common["voltage_V"][tail_start:]))
            - float(np.median(reference.trace.voltage_V[tail_start:]))
        )
        / voltage_noise_V,
        "reference_activity_class": reference_activity["activity_class"],
        "candidate_activity_class": candidate_activity["activity_class"],
        "activity_class_match": reference_activity["activity_class"]
        == candidate_activity["activity_class"],
        "reference_activity_peak_count": int(reference_activity["spike_count"]),
        "candidate_activity_peak_count": int(candidate_activity["spike_count"]),
        "charge_relative_error": _relative_error(candidate_charge, reference_charge),
        "energy_relative_error": _relative_error(candidate_energy, reference_energy),
    }
    event_metrics, event_rows = _event_comparison(
        reference,
        candidate,
        start_s=transient_start,
        voltage_V=voltage_V,
        candidate_label=candidate_label,
    )
    metrics.update(event_metrics)

    short_end = min(
        float(reference.trace.time_s[-1]),
        float(reference.trace.time_s[0]) + float(event_config["short_raw_window_s"]),
    )
    short = reference.trace.time_s <= short_end
    metrics["short_raw_current_nrmse95"] = nrmse95(
        common["current_A"][short], reference.trace.current_A[short], floor=current_noise_A
    )
    metrics["short_raw_voltage_nrmse95"] = nrmse95(
        common["voltage_V"][short], reference.trace.voltage_V[short], floor=voltage_noise_V
    )
    if regime == "oscillatory":
        metrics.update(
            _cycle_shape_and_qoi(
                reference,
                candidate,
                start_s=transient_start,
                phase_points=int(event_config["phase_grid_points"]),
                current_floor_A=current_noise_A,
                voltage_floor_V=voltage_noise_V,
            )
        )
        metrics.update(
            cycle_energy_ledger(
                candidate,
                params,
                input_voltage_V=voltage_V,
                start_s=transient_start,
            )
        )
    return metrics, event_rows


def normalized_primary_score(
    metrics: Mapping[str, Any], *, regime: str, gates: Mapping[str, Any]
) -> float:
    if regime == "static":
        pairs = (
            ("current_absolute_rmse_noise_fraction", "current_absolute_rmse_noise_fraction_max"),
            ("current_max_error_noise_fraction", "current_max_error_noise_fraction_max"),
            ("voltage_absolute_rmse_noise_fraction", "voltage_absolute_rmse_noise_fraction_max"),
            ("voltage_max_error_noise_fraction", "voltage_max_error_noise_fraction_max"),
            ("steady_current_error_noise_fraction", "steady_current_error_noise_fraction_max"),
            ("steady_voltage_error_noise_fraction", "steady_voltage_error_noise_fraction_max"),
            ("charge_relative_error", "charge_relative_error_max"),
            ("energy_relative_error", "energy_relative_error_max"),
        )
    else:
        pairs = (
            ("period_relative_error", "period_relative_error_max"),
            ("frequency_relative_error", "frequency_relative_error_max"),
            ("maximum_event_time_error_s", "maximum_event_time_error_s"),
            ("phase_drift_s_per_event", "phase_drift_s_per_event_max"),
            ("cycle_shape_combined_nrmse95", "cycle_shape_nrmse_max"),
            ("cycle_peak_relative_error", "peak_relative_error_max"),
            ("cycle_duty_cycle_absolute_error", "duty_cycle_absolute_error_max"),
            ("cycle_charge_relative_error", "cycle_charge_relative_error_max"),
            ("cycle_energy_relative_error", "cycle_energy_relative_error_max"),
            ("cycle_ledger_relative_residual", "cycle_ledger_relative_residual_max"),
            ("short_raw_current_nrmse95", "short_raw_current_nrmse95_max"),
            ("short_raw_voltage_nrmse95", "short_raw_voltage_nrmse95_max"),
        )
    ratios: list[float] = []
    for metric_name, threshold_name in pairs:
        value = abs(float(metrics.get(metric_name, float("inf"))))
        threshold = float(gates[threshold_name])
        ratios.append(value / max(threshold, 1.0e-30))
    if not bool(metrics.get("activity_class_match", False)):
        ratios.append(float("inf"))
    if regime == "oscillatory" and not bool(metrics.get("reversal_event_count_exact", False)):
        ratios.append(float("inf"))
    return float(max(ratios))


def convergence_loglog_slope(dt_values_s: Sequence[float], scores: Sequence[float]) -> float:
    dt = np.asarray(dt_values_s, dtype=np.float64)
    values = np.asarray(scores, dtype=np.float64)
    finite = np.isfinite(values) & (values > 0.0)
    if np.count_nonzero(finite) < 2:
        return float("-inf")
    return float(np.polyfit(np.log(dt[finite]), np.log(values[finite]), 1)[0])
