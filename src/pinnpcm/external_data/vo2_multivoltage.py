"""Public 9/11/15/17 V VO2 fitting utilities with a sealed 13 V boundary.

The module only loads explicitly supplied open-voltage paths.  It uses the
repository SI implementation of the Zhang et al. compact model and never
labels solver output as measured data or as a PINN prediction.
"""

from __future__ import annotations

import math
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from pinnpcm.external_data.vo2_zhang import (
    load_rt_curve,
    load_tektronix_trace,
)
from pinnpcm.identifiability import principal_angles_deg, svd_geometry
from pinnpcm.physics.vo2_thermal_neuristor import (
    VO2ThermalNeuristorParameters,
    resistance_path_ohm,
    simulate_source_compat_si,
)


def nrmse95(prediction: np.ndarray, target: np.ndarray, *, floor: float = 1.0e-12) -> float:
    prediction = np.asarray(prediction, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    scale = max(float(np.quantile(target, 0.95) - np.quantile(target, 0.05)), float(floor))
    return float(np.sqrt(np.mean((prediction - target) ** 2)) / scale)


def _relative_error(value: float, reference: float, *, floor: float = 1.0e-30) -> float:
    return float(abs(value - reference) / max(abs(reference), floor))


def preprocess_experiment(
    path: Path,
    *,
    voltage_V: float,
    current_sense_ohm: float,
) -> dict[str, Any]:
    """Apply the preregistered time-zero and pretrigger baseline rules."""

    loaded = load_tektronix_trace(path, current_sense_ohm=current_sense_ohm)
    time_s = np.asarray(loaded["time_s"], dtype=np.float64)
    current_A = np.asarray(loaded["current_A"], dtype=np.float64)
    device_voltage_V = np.asarray(loaded["device_voltage_V"], dtype=np.float64)
    pretrigger = time_s < 0.0
    if not np.any(pretrigger):
        raise ValueError(f"{path} has no preregistered pretrigger baseline.")
    current_baseline = float(np.median(current_A[pretrigger]))
    voltage_baseline = float(np.median(device_voltage_V[pretrigger]))
    current_noise = float(1.4826 * np.median(np.abs(current_A[pretrigger] - current_baseline)))
    voltage_noise = float(
        1.4826 * np.median(np.abs(device_voltage_V[pretrigger] - voltage_baseline))
    )
    evaluation = time_s >= 0.0
    result = {
        "time_s": time_s[evaluation],
        "current_A": current_A[evaluation] - current_baseline,
        "device_voltage_V": device_voltage_V[evaluation] - voltage_baseline,
        "input_voltage_V": float(voltage_V),
        "current_baseline_A": current_baseline,
        "device_voltage_baseline_V": voltage_baseline,
        "current_noise_scale_A": max(current_noise, 1.0e-12),
        "device_voltage_noise_scale_V": max(voltage_noise, 1.0e-9),
        "curve_id": loaded["curve_id"],
        "source_kind": "public_external_raw_with_preregistered_instrument_zeroing",
        "raw_sample_count": int(time_s.size),
        "evaluation_sample_count": int(np.sum(evaluation)),
    }
    if result["time_s"].size < 10 or np.any(np.diff(result["time_s"]) <= 0.0):
        raise ValueError(f"{path} has an invalid nonnegative-time evaluation trace.")
    if not all(
        np.isfinite(result[name]).all()
        for name in ("time_s", "current_A", "device_voltage_V")
    ):
        raise ValueError(f"{path} contains non-finite values.")
    return result


def activity_metrics(
    time_s: np.ndarray,
    current_A: np.ndarray,
    device_voltage_V: np.ndarray,
    config: Mapping[str, Any],
    *,
    noise_scale_A: float | None = None,
) -> dict[str, Any]:
    """Return executable event/QoI metrics under the locked classifier."""

    time_s = np.asarray(time_s, dtype=np.float64)
    current_A = np.asarray(current_A, dtype=np.float64)
    device_voltage_V = np.asarray(device_voltage_V, dtype=np.float64)
    initial_count = max(3, int(math.ceil(float(config["baseline_fraction"]) * time_s.size)))
    baseline = float(np.median(current_A[:initial_count]))
    mad = float(
        float(config["noise_mad_multiplier"])
        * np.median(np.abs(current_A[:initial_count] - baseline))
    )
    noise = max(float(noise_scale_A or 0.0), mad, 1.0e-12)
    amplitude_range = max(
        float(np.quantile(current_A, 0.95) - np.quantile(current_A, 0.05)),
        noise,
    )
    prominence = max(
        float(config["prominence_noise_multiplier"]) * noise,
        float(config["prominence_range_fraction"]) * amplitude_range,
    )
    dt = float(np.median(np.diff(time_s)))
    distance = max(1, int(round(float(config["minimum_peak_distance_s"]) / dt)))
    peaks, _ = find_peaks(current_A, prominence=prominence, distance=distance)
    transient_index = int(float(config["transient_fraction"]) * time_s.size)
    retained = peaks[peaks >= transient_index]
    isi = np.diff(time_s[retained]) if retained.size >= 2 else np.asarray([], dtype=np.float64)
    median_isi = float(np.median(isi)) if isi.size else 0.0
    frequency = 1.0 / median_isi if median_isi > 0.0 else 0.0
    isi_cv = float(np.std(isi) / max(float(np.mean(isi)), 1.0e-30)) if isi.size >= 2 else 0.0
    peak_values = current_A[retained] if retained.size else np.asarray([], dtype=np.float64)
    peak_amplitude = float(np.median(peak_values) - baseline) if peak_values.size else 0.0
    peak_cv = (
        float(np.std(peak_values) / max(abs(float(np.mean(peak_values))), 1.0e-30))
        if peak_values.size >= 2
        else 0.0
    )
    evaluation_span = float(time_s[-1] - time_s[transient_index])
    peak_span = float(time_s[retained[-1]] - time_s[retained[0]]) if retained.size >= 2 else 0.0
    if (
        retained.size >= int(config["sustained_min_peaks"])
        and peak_span >= float(config["sustained_span_fraction"]) * evaluation_span
        and isi_cv <= float(config["sustained_isi_cv_max"])
    ):
        activity_class = "sustained_spiking"
    elif retained.size >= int(config["irregular_min_peaks"]):
        activity_class = "irregular_or_transient"
    else:
        tail_count = max(1, int(float(config["latched_tail_fraction"]) * time_s.size))
        if float(np.median(current_A[-tail_count:])) >= baseline + prominence:
            activity_class = "latched_high"
        else:
            activity_class = "quiescent"
    half_level = baseline + 0.5 * max(float(np.quantile(current_A, 0.95)) - baseline, 0.0)
    duty_cycle = float(np.mean(current_A >= half_level))
    positive_current = np.maximum(current_A, 0.0)
    positive_power = np.maximum(device_voltage_V * current_A, 0.0)
    charge_C = float(np.trapz(positive_current, time_s))
    energy_J = float(np.trapz(positive_power, time_s))
    return {
        "activity_class": activity_class,
        "spike_count": int(retained.size),
        "frequency_Hz": frequency,
        "median_isi_s": median_isi,
        "isi_cv": isi_cv,
        "peak_amplitude_A": peak_amplitude,
        "peak_amplitude_cv": peak_cv,
        "onset_s": float(time_s[retained[0]]) if retained.size else 0.0,
        "duty_cycle": duty_cycle,
        "integrated_charge_C": charge_C,
        "integrated_energy_J": energy_J,
        "baseline_A": baseline,
        "noise_scale_A": noise,
        "peak_prominence_A": prominence,
    }


def trace_metrics(
    observation: Mapping[str, Any],
    prediction_time_s: np.ndarray,
    prediction_current_A: np.ndarray,
    prediction_voltage_V: np.ndarray,
    event_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Score a solver trace on native observation times without shifting it."""

    time_s = np.asarray(observation["time_s"], dtype=np.float64)
    current = np.interp(time_s, prediction_time_s, prediction_current_A)
    voltage = np.interp(time_s, prediction_time_s, prediction_voltage_V)
    current_nrmse = nrmse95(
        current,
        np.asarray(observation["current_A"]),
        floor=float(observation.get("current_noise_scale_A", 1.0e-12)),
    )
    voltage_nrmse = nrmse95(
        voltage,
        np.asarray(observation["device_voltage_V"]),
        floor=float(observation.get("device_voltage_noise_scale_V", 1.0e-9)),
    )
    observed_event = activity_metrics(
        time_s,
        np.asarray(observation["current_A"]),
        np.asarray(observation["device_voltage_V"]),
        event_config,
        noise_scale_A=float(observation.get("current_noise_scale_A", 1.0e-12)),
    )
    predicted_event = activity_metrics(
        time_s,
        current,
        voltage,
        event_config,
        noise_scale_A=float(observation.get("current_noise_scale_A", 1.0e-12)),
    )
    return {
        "current_nrmse95": current_nrmse,
        "device_voltage_nrmse95": voltage_nrmse,
        "combined_nrmse95": 0.7 * current_nrmse + 0.3 * voltage_nrmse,
        "observed_activity_class": observed_event["activity_class"],
        "predicted_activity_class": predicted_event["activity_class"],
        "activity_class_match": bool(
            observed_event["activity_class"] == predicted_event["activity_class"]
        ),
        "observed_spike_count": observed_event["spike_count"],
        "predicted_spike_count": predicted_event["spike_count"],
        "spike_count_abs_error": abs(
            predicted_event["spike_count"] - observed_event["spike_count"]
        ),
        "frequency_relative_error": _relative_error(
            predicted_event["frequency_Hz"],
            observed_event["frequency_Hz"],
            floor=1.0 if observed_event["frequency_Hz"] == 0.0 else 1.0e-30,
        ),
        "peak_amplitude_relative_error": _relative_error(
            predicted_event["peak_amplitude_A"],
            observed_event["peak_amplitude_A"],
            floor=float(observation.get("current_noise_scale_A", 1.0e-12)),
        ),
        "onset_abs_error_s": abs(
            predicted_event["onset_s"] - observed_event["onset_s"]
        ),
        "duty_cycle_abs_error": abs(
            predicted_event["duty_cycle"] - observed_event["duty_cycle"]
        ),
        "charge_relative_error": _relative_error(
            predicted_event["integrated_charge_C"],
            observed_event["integrated_charge_C"],
        ),
        "energy_relative_error": _relative_error(
            predicted_event["integrated_energy_J"],
            observed_event["integrated_energy_J"],
        ),
        "observed_frequency_Hz": observed_event["frequency_Hz"],
        "predicted_frequency_Hz": predicted_event["frequency_Hz"],
        "observed_duty_cycle": observed_event["duty_cycle"],
        "predicted_duty_cycle": predicted_event["duty_cycle"],
        "observed_charge_C": observed_event["integrated_charge_C"],
        "predicted_charge_C": predicted_event["integrated_charge_C"],
        "observed_energy_J": observed_event["integrated_energy_J"],
        "predicted_energy_J": predicted_event["integrated_energy_J"],
    }


def parameters_from_coordinates(
    base: VO2ThermalNeuristorParameters,
    coordinates: Sequence[float],
    coordinate_system: str,
) -> VO2ThermalNeuristorParameters:
    """Map log coordinates to the two fitted physical parameters."""

    first, second = (float(value) for value in coordinates)
    if coordinate_system == "raw_Cth_Sth":
        log_Cth_factor, log_Sth_factor = first, second
    elif coordinate_system == "quotient_tau_th_Sth":
        log_tau_factor, log_Sth_factor = first, second
        log_Cth_factor = log_tau_factor + log_Sth_factor
    else:
        raise ValueError(f"Unsupported coordinate system: {coordinate_system}")
    return replace(
        base,
        C_th_J_per_K=base.C_th_J_per_K * math.exp(log_Cth_factor),
        S_th_W_per_K=base.S_th_W_per_K * math.exp(log_Sth_factor),
    )


def physical_coordinate_record(params: VO2ThermalNeuristorParameters) -> dict[str, float]:
    return {
        "C_th_J_per_K": float(params.C_th_J_per_K),
        "S_e_W_per_K": float(params.S_th_W_per_K),
        "tau_th_s": float(params.C_th_J_per_K / params.S_th_W_per_K),
    }


class ForwardCache:
    """Task-local deterministic cache with an explicit forward-evaluation count."""

    def __init__(self, *, maximum_evaluations: int):
        self.maximum_evaluations = int(maximum_evaluations)
        self.forward_evaluations = 0
        self._cache: dict[tuple[float, ...], Any] = {}

    def simulate(
        self,
        params: VO2ThermalNeuristorParameters,
        *,
        voltage_V: float,
        t_max_s: float,
        dt_s: float,
    ) -> Any:
        key = (
            round(params.C_th_J_per_K, 22),
            round(params.S_th_W_per_K, 16),
            round(float(voltage_V), 8),
            round(float(t_max_s), 15),
            round(float(dt_s), 15),
        )
        if key not in self._cache:
            if self.forward_evaluations >= self.maximum_evaluations:
                raise RuntimeError("Preregistered forward-evaluation budget exhausted.")
            self._cache[key] = simulate_source_compat_si(
                params,
                input_voltage_V=float(voltage_V),
                t_max_s=float(t_max_s),
                dt_s=float(dt_s),
                noise_strength=0.0,
                seed=0,
            )
            self.forward_evaluations += 1
        return self._cache[key]


def solver_convergence_audit(
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    convergence_config: Mapping[str, Any],
    event_config: Mapping[str, Any],
    cache: ForwardCache,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare the two finest locked time steps while preserving D0a."""

    dt_values = [float(value) for value in convergence_config["dt_values_s"]]
    medium_dt, fine_dt = dt_values[-2], dt_values[-1]
    rows: list[dict[str, Any]] = []
    for voltage in convergence_config["voltages_V"]:
        observation = observations[float(voltage)]
        t_max = float(observation["time_s"][-1] + fine_dt)
        medium = cache.simulate(
            base, voltage_V=float(voltage), t_max_s=t_max, dt_s=medium_dt
        )
        fine = cache.simulate(
            base, voltage_V=float(voltage), t_max_s=t_max, dt_s=fine_dt
        )
        comparison_observation = {
            "time_s": medium.time_s,
            "current_A": medium.current_A,
            "device_voltage_V": medium.voltage_V,
            "current_noise_scale_A": 1.0e-12,
            "device_voltage_noise_scale_V": 1.0e-9,
        }
        metrics = trace_metrics(
            comparison_observation,
            fine.time_s,
            fine.current_A,
            fine.voltage_V,
            event_config,
        )
        checks = {
            "raw_current_nrmse95": metrics["current_nrmse95"]
            <= float(convergence_config["raw_current_nrmse95_max"]),
            "raw_voltage_nrmse95": metrics["device_voltage_nrmse95"]
            <= float(convergence_config["raw_voltage_nrmse95_max"]),
            "frequency": metrics["frequency_relative_error"]
            <= float(convergence_config["frequency_relative_error_max"]),
            "charge": metrics["charge_relative_error"]
            <= float(convergence_config["charge_relative_error_max"]),
            "energy": metrics["energy_relative_error"]
            <= float(convergence_config["energy_relative_error_max"]),
            "activity_class": metrics["activity_class_match"]
            if bool(convergence_config["activity_class_exact"])
            else True,
        }
        rows.append(
            {
                "voltage_V": float(voltage),
                "coarse_dt_s": medium_dt,
                "fine_dt_s": fine_dt,
                **metrics,
                **{f"gate_{name}": bool(value) for name, value in checks.items()},
                "all_operational_convergence_gates_pass": bool(all(checks.values())),
                "historical_d0a_nrmse95": float(
                    convergence_config["d0a_medium_vs_fine_current_nrmse95"]
                )
                if float(voltage) == 11.0
                else None,
                "historical_d0a_gate_passed": False
                if float(voltage) == 11.0
                else None,
            }
        )
    return rows, {
        "all_operational_gates_pass": bool(
            rows and all(row["all_operational_convergence_gates_pass"] for row in rows)
        ),
        "historical_d0a_gate_preserved": True,
        "historical_d0a_gate_passed": False,
        "historical_d0a_metric": float(
            convergence_config["d0a_medium_vs_fine_current_nrmse95"]
        ),
        "historical_d0a_gate": float(convergence_config["d0a_gate_max"]),
        "operational_gate_is_parallel_not_replacement": True,
    }


def _model_observation_vector(
    params: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    *,
    points_per_trace: int,
    dt_s: float,
    cache: ForwardCache,
    scale_reference: Mapping[float, tuple[float, float]] | None = None,
) -> tuple[np.ndarray, dict[float, tuple[float, float]]]:
    values: list[np.ndarray] = []
    scales: dict[float, tuple[float, float]] = {} if scale_reference is None else dict(scale_reference)
    for voltage in sorted(observations):
        observation = observations[voltage]
        trace = cache.simulate(
            params,
            voltage_V=voltage,
            t_max_s=float(observation["time_s"][-1] + dt_s),
            dt_s=dt_s,
        )
        indices = np.linspace(0, trace.time_s.size - 1, int(points_per_trace), dtype=int)
        current = trace.current_A[indices]
        device_voltage = trace.voltage_V[indices]
        if scale_reference is None:
            current_scale = max(
                float(np.quantile(current, 0.95) - np.quantile(current, 0.05)),
                1.0e-12,
            )
            voltage_scale = max(
                float(np.quantile(device_voltage, 0.95) - np.quantile(device_voltage, 0.05)),
                1.0e-9,
            )
            scales[voltage] = (current_scale, voltage_scale)
        current_scale, voltage_scale = scales[voltage]
        values.extend((current / current_scale, device_voltage / voltage_scale))
    return np.concatenate(values), scales


def jacobian_stability_audit(
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    dt_s: float,
    cache: ForwardCache,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the locked multi-step Jacobian/SVD audit before fitting."""

    _, scales = _model_observation_vector(
        base,
        observations,
        points_per_trace=int(config["observation_points_per_trace"]),
        dt_s=dt_s,
        cache=cache,
    )
    steps = [float(value) for value in config["relative_steps"]]
    matrices: dict[str, list[np.ndarray]] = {}
    rows: list[dict[str, Any]] = []
    systems: dict[str, Any] = {}
    for system in config["coordinate_systems"]:
        matrices[system] = []
        geometries = []
        for step in steps:
            columns = []
            for coordinate_index in range(2):
                plus = np.zeros(2, dtype=np.float64)
                minus = np.zeros(2, dtype=np.float64)
                plus[coordinate_index] = step
                minus[coordinate_index] = -step
                plus_vector, _ = _model_observation_vector(
                    parameters_from_coordinates(base, plus, system),
                    observations,
                    points_per_trace=int(config["observation_points_per_trace"]),
                    dt_s=dt_s,
                    cache=cache,
                    scale_reference=scales,
                )
                minus_vector, _ = _model_observation_vector(
                    parameters_from_coordinates(base, minus, system),
                    observations,
                    points_per_trace=int(config["observation_points_per_trace"]),
                    dt_s=dt_s,
                    cache=cache,
                    scale_reference=scales,
                )
                columns.append((plus_vector - minus_vector) / (2.0 * step))
            matrix = np.column_stack(columns)
            geometry = svd_geometry(
                matrix,
                relative_rank_threshold=float(config["relative_rank_threshold"]),
            )
            matrices[system].append(matrix)
            geometries.append(geometry)
            for singular_index, singular_value in enumerate(geometry["singular_values"]):
                rows.append(
                    {
                        "coordinate_system": system,
                        "relative_step": step,
                        "singular_index": singular_index,
                        "singular_value": float(singular_value),
                        "threshold_rank": int(geometry["threshold_rank"]),
                        "effective_rank": float(geometry["effective_rank"]),
                        "retained_condition_number": float(
                            geometry["retained_condition_number"]
                        ),
                    }
                )
        coarse_geometry, fine_geometry = geometries[-2], geometries[-1]
        rank = int(fine_geometry["threshold_rank"])
        retained = max(rank, 1)
        singular_change = float(
            np.max(
                np.abs(
                    coarse_geometry["singular_values"][:retained]
                    - fine_geometry["singular_values"][:retained]
                )
                / np.maximum(
                    np.abs(fine_geometry["singular_values"][:retained]), 1.0e-30
                )
            )
        )
        _, _, coarse_vt = np.linalg.svd(matrices[system][-2], full_matrices=False)
        _, _, fine_vt = np.linalg.svd(matrices[system][-1], full_matrices=False)
        top_angle = float(
            np.max(principal_angles_deg(coarse_vt[:1].T, fine_vt[:1].T))
        )
        checks = {
            "rank": rank == int(config["required_rank"]),
            "rank_consistent": int(coarse_geometry["threshold_rank"]) == rank,
            "singular_values": singular_change
            <= float(config["retained_singular_value_relative_change_max"]),
            "top_direction": top_angle <= float(config["principal_angle_deg_max"]),
            "condition": float(fine_geometry["retained_condition_number"])
            <= float(config["retained_condition_number_max"]),
        }
        systems[system] = {
            "threshold_rank": rank,
            "effective_rank": float(fine_geometry["effective_rank"]),
            "retained_condition_number": float(
                fine_geometry["retained_condition_number"]
            ),
            "retained_singular_value_relative_change": singular_change,
            "top_direction_angle_deg": top_angle,
            "checks": checks,
            "all_checks_pass": bool(all(checks.values())),
        }
    return rows, {
        "coordinate_systems": systems,
        "all_coordinate_systems_stable": bool(
            systems and all(value["all_checks_pass"] for value in systems.values())
        ),
        "fit_dimension": 2
        if systems and all(value["all_checks_pass"] for value in systems.values())
        else 0,
        "fit_only_stable_identifiable_coordinates": True,
    }


def rt_sanity_metric(
    base: VO2ThermalNeuristorParameters, rt_path: Path
) -> dict[str, Any]:
    curve = load_rt_curve(rt_path)
    prediction, branch, events = resistance_path_ohm(curve["temperature_K"], base)
    return {
        "nrmse95": nrmse95(prediction, curve["resistance_ohm"], floor=1.0),
        "point_count": int(prediction.size),
        "event_count": int(events.size),
        "branch_values": sorted(float(value) for value in np.unique(branch)),
        "role": "fixed_constitutive_sanity_not_dynamic_fit_target",
    }


def _objective_residual(
    coordinates: np.ndarray,
    *,
    coordinate_system: str,
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    fit_voltages: Sequence[float],
    dt_s: float,
    points_per_trace: int,
    weights: Mapping[str, float],
    raw_bound: float,
    cache: ForwardCache,
) -> np.ndarray:
    params = parameters_from_coordinates(base, coordinates, coordinate_system)
    residuals: list[np.ndarray] = []
    for voltage in fit_voltages:
        observation = observations[float(voltage)]
        trace = cache.simulate(
            params,
            voltage_V=float(voltage),
            t_max_s=float(observation["time_s"][-1] + dt_s),
            dt_s=dt_s,
        )
        indices = np.linspace(
            0, observation["time_s"].size - 1, int(points_per_trace), dtype=int
        )
        time = observation["time_s"][indices]
        predicted_current = np.interp(time, trace.time_s, trace.current_A)
        predicted_voltage = np.interp(time, trace.time_s, trace.voltage_V)
        observed_current = observation["current_A"][indices]
        observed_voltage = observation["device_voltage_V"][indices]
        current_scale = max(
            float(np.quantile(observation["current_A"], 0.95) - np.quantile(observation["current_A"], 0.05)),
            float(observation["current_noise_scale_A"]),
        )
        voltage_scale = max(
            float(np.quantile(observation["device_voltage_V"], 0.95) - np.quantile(observation["device_voltage_V"], 0.05)),
            float(observation["device_voltage_noise_scale_V"]),
        )
        residuals.append(
            math.sqrt(float(weights["current"]))
            * (predicted_current - observed_current)
            / current_scale
        )
        residuals.append(
            math.sqrt(float(weights["device_voltage"]))
            * (predicted_voltage - observed_voltage)
            / voltage_scale
        )
    if coordinate_system == "raw_Cth_Sth":
        raw_coordinates = np.asarray(coordinates, dtype=np.float64)
    else:
        raw_coordinates = np.asarray(
            [coordinates[0] + coordinates[1], coordinates[1]], dtype=np.float64
        )
    violation = np.maximum(np.abs(raw_coordinates) - raw_bound, 0.0)
    residuals.append(100.0 * violation)
    return np.concatenate(residuals)


def run_multistart_job(
    *,
    job_id: str,
    coordinate_system: str,
    fit_voltages: Sequence[float],
    observations: Mapping[float, Mapping[str, Any]],
    base: VO2ThermalNeuristorParameters,
    fit_config: Mapping[str, Any],
    preprocessing: Mapping[str, Any],
    event_config: Mapping[str, Any],
    start_id: int,
    start_offset: Sequence[float],
    dt_s: float,
    cache: ForwardCache,
    task_started: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Execute one bounded start and return all open-voltage metrics."""

    if time.perf_counter() - task_started > 3600.0 * float(
        fit_config["cpu_wall_clock_hours_max"]
    ):
        raise RuntimeError("M35 CPU wall-clock budget exhausted before job start.")
    raw_bound = math.log(float(fit_config["raw_parameter_factor_bounds"][1]))
    raw_start = raw_bound * np.asarray(start_offset, dtype=np.float64)
    if coordinate_system == "raw_Cth_Sth":
        x0 = raw_start
        lower = np.asarray([-raw_bound, -raw_bound])
        upper = np.asarray([raw_bound, raw_bound])
    elif coordinate_system == "quotient_tau_th_Sth":
        x0 = np.asarray([raw_start[0] - raw_start[1], raw_start[1]])
        lower = np.asarray([-2.0 * raw_bound, -raw_bound])
        upper = np.asarray([2.0 * raw_bound, raw_bound])
    else:
        raise ValueError(coordinate_system)
    before = cache.forward_evaluations
    result = least_squares(
        _objective_residual,
        x0=x0,
        bounds=(lower, upper),
        method="trf",
        loss=str(fit_config["loss"]),
        max_nfev=int(fit_config["max_nfev_per_start"]),
        ftol=float(fit_config["ftol"]),
        xtol=float(fit_config["xtol"]),
        gtol=float(fit_config["gtol"]),
        x_scale=1.0,
        kwargs={
            "coordinate_system": coordinate_system,
            "base": base,
            "observations": observations,
            "fit_voltages": fit_voltages,
            "dt_s": dt_s,
            "points_per_trace": int(preprocessing["objective_points_per_trace"]),
            "weights": preprocessing["objective_weights"],
            "raw_bound": raw_bound,
            "cache": cache,
        },
    )
    params = parameters_from_coordinates(base, result.x, coordinate_system)
    physical = physical_coordinate_record(params)
    finite = bool(
        np.isfinite(result.x).all()
        and math.isfinite(float(result.cost))
        and all(math.isfinite(value) and value > 0.0 for value in physical.values())
    )
    start_record = {
        "job_id": job_id,
        "coordinate_system": coordinate_system,
        "start_id": int(start_id),
        "start_offset_0": float(start_offset[0]),
        "start_offset_1": float(start_offset[1]),
        "optimizer_success": bool(result.success),
        "finite": finite,
        "status_code": int(result.status),
        "nfev": int(result.nfev),
        "cost": float(result.cost),
        "optimality": float(result.optimality),
        "coordinate_0": float(result.x[0]),
        "coordinate_1": float(result.x[1]),
        **physical,
        "forward_evaluations_increment": cache.forward_evaluations - before,
    }
    metrics_rows: list[dict[str, Any]] = []
    for voltage, observation in sorted(observations.items()):
        trace = cache.simulate(
            params,
            voltage_V=float(voltage),
            t_max_s=float(observation["time_s"][-1] + dt_s),
            dt_s=dt_s,
        )
        metrics = trace_metrics(
            observation,
            trace.time_s,
            trace.current_A,
            trace.voltage_V,
            event_config,
        )
        metrics_rows.append(
            {
                "job_id": job_id,
                "coordinate_system": coordinate_system,
                "start_id": int(start_id),
                "voltage_V": float(voltage),
                "role": "fit" if float(voltage) in set(float(v) for v in fit_voltages) else "holdout",
                **metrics,
            }
        )
    return start_record, metrics_rows


def coordinate_dispersion(
    start_rows: Sequence[Mapping[str, Any]], *, coordinate_system: str
) -> dict[str, float]:
    """Compute across-fold dispersion without selecting the best start."""

    per_start: list[float] = []
    for start_id in sorted({int(row["start_id"]) for row in start_rows}):
        rows = [
            row
            for row in start_rows
            if int(row["start_id"]) == start_id and str(row["job_id"]).startswith("holdout_")
        ]
        if len(rows) != 4:
            continue
        if coordinate_system == "raw_Cth_Sth":
            arrays = (
                np.log([float(row["C_th_J_per_K"]) for row in rows]),
                np.log([float(row["S_e_W_per_K"]) for row in rows]),
            )
        else:
            arrays = (
                np.log([float(row["tau_th_s"]) for row in rows]),
                np.log([float(row["S_e_W_per_K"]) for row in rows]),
            )
        per_start.append(max(float(np.std(values)) for values in arrays))
    return {
        "median_max_log_coordinate_std": float(np.median(per_start))
        if per_start
        else math.inf,
        "maximum_max_log_coordinate_std": float(np.max(per_start))
        if per_start
        else math.inf,
        "complete_start_count": len(per_start),
    }
