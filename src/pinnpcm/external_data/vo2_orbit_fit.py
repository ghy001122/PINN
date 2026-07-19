"""Conditional event-aware Jacobian and open-voltage fit utilities for M36."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from pinnpcm.external_data.vo2_multivoltage import (
    activity_metrics,
    coordinate_dispersion,
    parameters_from_coordinates,
    physical_coordinate_record,
    trace_metrics,
)
from pinnpcm.identifiability import principal_angles_deg, svd_geometry
from pinnpcm.physics.vo2_event_resolved import (
    EventResolvedResult,
    simulate_event_resolved_si,
)
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


class EventForwardCache:
    """Deterministic cache with an explicit M36 forward-evaluation ceiling."""

    def __init__(
        self,
        *,
        reference_config: Mapping[str, Any],
        maximum_evaluations: int,
        method: str = "DOP853",
    ) -> None:
        self.reference_config = reference_config
        self.maximum_evaluations = int(maximum_evaluations)
        self.method = method
        self.forward_evaluations = 0
        self._cache: dict[tuple[Any, ...], EventResolvedResult] = {}

    def simulate(
        self,
        params: VO2ThermalNeuristorParameters,
        *,
        voltage_V: float,
        evaluation_times_s: np.ndarray,
    ) -> EventResolvedResult:
        key = (
            round(params.C_th_J_per_K, 22),
            round(params.S_th_W_per_K, 16),
            round(float(voltage_V), 8),
            int(evaluation_times_s.size),
            round(float(evaluation_times_s[0]), 15),
            round(float(evaluation_times_s[-1]), 15),
            self.method,
        )
        if key not in self._cache:
            if self.forward_evaluations >= self.maximum_evaluations:
                raise RuntimeError("M36 conditional forward-evaluation budget exhausted.")
            self._cache[key] = simulate_event_resolved_si(
                params,
                input_voltage_V=float(voltage_V),
                evaluation_times_s=evaluation_times_s,
                method=self.method,
                reference_config=self.reference_config,
            )
            self.forward_evaluations += 1
        return self._cache[key]


def _activity_peaks(
    time_s: np.ndarray,
    current_A: np.ndarray,
    config: Mapping[str, Any],
    *,
    noise_scale_A: float,
) -> np.ndarray:
    initial_count = max(3, int(math.ceil(float(config["baseline_fraction"]) * time_s.size)))
    baseline = float(np.median(current_A[:initial_count]))
    mad = float(
        float(config["noise_mad_multiplier"])
        * np.median(np.abs(current_A[:initial_count] - baseline))
    )
    noise = max(noise_scale_A, mad, 1.0e-12)
    amplitude_range = max(
        float(np.quantile(current_A, 0.95) - np.quantile(current_A, 0.05)), noise
    )
    prominence = max(
        float(config["prominence_noise_multiplier"]) * noise,
        float(config["prominence_range_fraction"]) * amplitude_range,
    )
    dt = float(np.median(np.diff(time_s)))
    distance = max(1, int(round(float(config["minimum_peak_distance_s"]) / dt)))
    peaks, _ = find_peaks(current_A, prominence=prominence, distance=distance)
    transient = int(float(config["transient_fraction"]) * time_s.size)
    return peaks[peaks >= transient]


def _median_phase_cycle(
    time_s: np.ndarray,
    current_A: np.ndarray,
    voltage_V: np.ndarray,
    peaks: np.ndarray,
    *,
    phase_points: int,
) -> tuple[np.ndarray, np.ndarray, float, float, float, float, float]:
    phase = np.linspace(0.0, 1.0, phase_points, dtype=np.float64)
    current_cycles: list[np.ndarray] = []
    voltage_cycles: list[np.ndarray] = []
    periods: list[float] = []
    charges: list[float] = []
    energies: list[float] = []
    duties: list[float] = []
    amplitudes: list[float] = []
    for left, right in zip(peaks[:-1], peaks[1:]):
        t0, t1 = float(time_s[left]), float(time_s[right])
        query = t0 + phase * (t1 - t0)
        current = np.interp(query, time_s, current_A)
        voltage = np.interp(query, time_s, voltage_V)
        current_cycles.append(current)
        voltage_cycles.append(voltage)
        period = t1 - t0
        periods.append(period)
        charges.append(float(period * np.trapz(np.maximum(current, 0.0), phase)))
        energies.append(float(period * np.trapz(np.maximum(current * voltage, 0.0), phase)))
        amplitude = float(np.max(current) - np.min(current))
        amplitudes.append(amplitude)
        duties.append(float(np.mean(current >= np.min(current) + 0.5 * amplitude)))
    if not current_cycles:
        zeros = np.zeros(phase_points, dtype=np.float64)
        return zeros, zeros, 0.0, 0.0, 0.0, 0.0, 0.0
    return (
        np.median(np.vstack(current_cycles), axis=0),
        np.median(np.vstack(voltage_cycles), axis=0),
        float(np.median(periods)),
        float(np.median(amplitudes)),
        float(np.median(duties)),
        float(np.median(charges)),
        float(np.median(energies)),
    )


def _trace_arrays(payload: Mapping[str, Any] | EventResolvedResult) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if isinstance(payload, EventResolvedResult):
        return payload.trace.time_s, payload.trace.current_A, payload.trace.voltage_V
    return (
        np.asarray(payload["time_s"], dtype=np.float64),
        np.asarray(payload["current_A"], dtype=np.float64),
        np.asarray(payload["device_voltage_V"], dtype=np.float64),
    )


def regime_feature_vector(
    payload: Mapping[str, Any] | EventResolvedResult,
    *,
    regime: str,
    event_config: Mapping[str, Any],
    current_noise_A: float,
    voltage_noise_V: float,
    feature_points: int = 32,
) -> np.ndarray:
    """Fixed-dimensional, no-DTW feature vector for Jacobians and fitting."""

    time_s, current_A, voltage_V = _trace_arrays(payload)
    current_scale = max(
        float(np.quantile(current_A, 0.95) - np.quantile(current_A, 0.05)),
        current_noise_A,
    )
    voltage_scale = max(
        float(np.quantile(voltage_V, 0.95) - np.quantile(voltage_V, 0.05)),
        voltage_noise_V,
    )
    if regime == "static":
        indices = np.linspace(0, time_s.size - 1, feature_points, dtype=int)
        tail = max(1, int(0.2 * time_s.size))
        charge = float(np.trapz(np.maximum(current_A, 0.0), time_s))
        energy = float(np.trapz(np.maximum(current_A * voltage_V, 0.0), time_s))
        duration = max(float(time_s[-1] - time_s[0]), 1.0e-30)
        return np.concatenate(
            (
                current_A[indices] / current_scale,
                voltage_V[indices] / voltage_scale,
                np.asarray(
                    [
                        float(np.median(current_A[-tail:])) / current_scale,
                        float(np.median(voltage_V[-tail:])) / voltage_scale,
                        charge / max(current_scale * duration, 1.0e-30),
                        energy / max(current_scale * voltage_scale * duration, 1.0e-30),
                    ]
                ),
            )
        )

    peaks = _activity_peaks(
        time_s, current_A, event_config, noise_scale_A=current_noise_A
    )
    cycle_current, cycle_voltage, period, amplitude, duty, charge, energy = _median_phase_cycle(
        time_s,
        current_A,
        voltage_V,
        peaks,
        phase_points=feature_points,
    )
    short_end = min(time_s[-1], time_s[0] + float(event_config["short_raw_window_s"]))
    short_indices_available = np.flatnonzero(time_s <= short_end)
    if short_indices_available.size < 2:
        short_indices_available = np.arange(time_s.size)
    short_indices = short_indices_available[
        np.linspace(0, short_indices_available.size - 1, 16, dtype=int)
    ]
    duration = max(float(time_s[-1] - time_s[0]), 1.0e-30)
    activity = activity_metrics(
        time_s,
        current_A,
        voltage_V,
        event_config,
        noise_scale_A=current_noise_A,
    )
    return np.concatenate(
        (
            current_A[short_indices] / current_scale,
            voltage_V[short_indices] / voltage_scale,
            cycle_current / current_scale,
            cycle_voltage / voltage_scale,
            np.asarray(
                [
                    math.log(max(period, 1.0e-30) / duration),
                    amplitude / current_scale,
                    duty,
                    charge / max(current_scale * max(period, 1.0e-30), 1.0e-30),
                    energy
                    / max(
                        current_scale * voltage_scale * max(period, 1.0e-30),
                        1.0e-30,
                    ),
                    float(activity["spike_count"]) / max(float(time_s.size), 1.0),
                ]
            ),
        )
    )


def _raw_time_residual(
    model: EventResolvedResult,
    observation: Mapping[str, Any],
    *,
    points: int,
    weights: Mapping[str, float],
) -> np.ndarray:
    indices = np.linspace(0, observation["time_s"].size - 1, points, dtype=int)
    current_scale = max(
        float(np.quantile(observation["current_A"], 0.95) - np.quantile(observation["current_A"], 0.05)),
        float(observation["current_noise_scale_A"]),
    )
    voltage_scale = max(
        float(
            np.quantile(observation["device_voltage_V"], 0.95)
            - np.quantile(observation["device_voltage_V"], 0.05)
        ),
        float(observation["device_voltage_noise_scale_V"]),
    )
    return np.concatenate(
        (
            math.sqrt(float(weights["current"]))
            * (model.trace.current_A[indices] - observation["current_A"][indices])
            / current_scale,
            math.sqrt(float(weights["device_voltage"]))
            * (model.trace.voltage_V[indices] - observation["device_voltage_V"][indices])
            / voltage_scale,
        )
    )


def _objective_residual(
    coordinates: np.ndarray,
    *,
    objective: str,
    coordinate_system: str,
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    regimes: Mapping[float, str],
    fit_voltages: Sequence[float],
    event_config: Mapping[str, Any],
    cache: EventForwardCache,
    raw_bound: float,
) -> np.ndarray:
    params = parameters_from_coordinates(base, coordinates, coordinate_system)
    residuals: list[np.ndarray] = []
    for voltage in fit_voltages:
        observation = observations[float(voltage)]
        model = cache.simulate(
            params,
            voltage_V=float(voltage),
            evaluation_times_s=np.asarray(observation["time_s"], dtype=np.float64),
        )
        if objective == "raw_time_m35_baseline":
            residuals.append(
                _raw_time_residual(
                    model,
                    observation,
                    points=64,
                    weights={"current": 0.7, "device_voltage": 0.3},
                )
            )
        elif objective == "regime_aware_orbit":
            observed = regime_feature_vector(
                observation,
                regime=regimes[float(voltage)],
                event_config=event_config,
                current_noise_A=float(observation["current_noise_scale_A"]),
                voltage_noise_V=float(observation["device_voltage_noise_scale_V"]),
            )
            predicted = regime_feature_vector(
                model,
                regime=regimes[float(voltage)],
                event_config=event_config,
                current_noise_A=float(observation["current_noise_scale_A"]),
                voltage_noise_V=float(observation["device_voltage_noise_scale_V"]),
            )
            scale = np.maximum(np.abs(observed), 1.0)
            residuals.append((predicted - observed) / scale)
        else:
            raise ValueError(f"Unsupported M36 objective: {objective}")
    raw_coordinates = (
        np.asarray(coordinates, dtype=np.float64)
        if coordinate_system == "raw_Cth_Sth"
        else np.asarray([coordinates[0] + coordinates[1], coordinates[1]])
    )
    residuals.append(100.0 * np.maximum(np.abs(raw_coordinates) - raw_bound, 0.0))
    return np.concatenate(residuals)


def event_aware_jacobian_audit(
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    regimes: Mapping[float, str],
    config: Mapping[str, Any],
    event_config: Mapping[str, Any],
    cache: EventForwardCache,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Central FD through root-located event times; no rank novelty is inferred."""

    groups = {
        "static_only": [9.0, 17.0],
        "oscillatory_only": [11.0, 15.0],
        "joint": [9.0, 11.0, 15.0, 17.0],
    }
    base_vectors: dict[float, np.ndarray] = {}
    for voltage, observation in observations.items():
        result = cache.simulate(
            base,
            voltage_V=voltage,
            evaluation_times_s=np.asarray(observation["time_s"], dtype=np.float64),
        )
        base_vectors[voltage] = regime_feature_vector(
            result,
            regime=regimes[voltage],
            event_config=event_config,
            current_noise_A=float(observation["current_noise_scale_A"]),
            voltage_noise_V=float(observation["device_voltage_noise_scale_V"]),
        )
    rows: list[dict[str, Any]] = []
    matrices: dict[tuple[str, str], list[np.ndarray]] = {}
    geometries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    systems: dict[str, Any] = {}
    for coordinate_system in config["coordinate_systems"]:
        systems[str(coordinate_system)] = {}
        for group_name, voltages in groups.items():
            scales = np.concatenate(
                [np.maximum(np.abs(base_vectors[voltage]), 1.0) for voltage in voltages]
            )
            key = (str(coordinate_system), group_name)
            matrices[key] = []
            geometries[key] = []
            for step in [float(value) for value in config["relative_steps"]]:
                columns: list[np.ndarray] = []
                for coordinate_index in range(2):
                    plus = np.zeros(2, dtype=np.float64)
                    minus = np.zeros(2, dtype=np.float64)
                    plus[coordinate_index] = step
                    minus[coordinate_index] = -step
                    parameter_pairs = (
                        parameters_from_coordinates(base, plus, str(coordinate_system)),
                        parameters_from_coordinates(base, minus, str(coordinate_system)),
                    )
                    vectors: list[np.ndarray] = []
                    for params in parameter_pairs:
                        vector_parts: list[np.ndarray] = []
                        for voltage in voltages:
                            observation = observations[voltage]
                            result = cache.simulate(
                                params,
                                voltage_V=voltage,
                                evaluation_times_s=np.asarray(observation["time_s"], dtype=np.float64),
                            )
                            vector_parts.append(
                                regime_feature_vector(
                                    result,
                                    regime=regimes[voltage],
                                    event_config=event_config,
                                    current_noise_A=float(observation["current_noise_scale_A"]),
                                    voltage_noise_V=float(observation["device_voltage_noise_scale_V"]),
                                )
                            )
                        vectors.append(np.concatenate(vector_parts) / scales)
                    columns.append((vectors[0] - vectors[1]) / (2.0 * step))
                matrix = np.column_stack(columns)
                geometry = svd_geometry(
                    matrix,
                    relative_rank_threshold=float(config["relative_rank_threshold"]),
                )
                matrices[key].append(matrix)
                geometries[key].append(geometry)
                for index, singular_value in enumerate(geometry["singular_values"]):
                    rows.append(
                        {
                            "coordinate_system": str(coordinate_system),
                            "observation_group": group_name,
                            "relative_step": step,
                            "singular_index": int(index),
                            "singular_value": float(singular_value),
                            "threshold_rank": int(geometry["threshold_rank"]),
                            "effective_rank": float(geometry["effective_rank"]),
                            "retained_condition_number": float(
                                geometry["retained_condition_number"]
                            ),
                        }
                    )
            coarse, fine = geometries[key][-2], geometries[key][-1]
            rank = int(fine["threshold_rank"])
            retained = max(rank, 1)
            singular_change = float(
                np.max(
                    np.abs(
                        coarse["singular_values"][:retained]
                        - fine["singular_values"][:retained]
                    )
                    / np.maximum(np.abs(fine["singular_values"][:retained]), 1.0e-30)
                )
            )
            _, _, coarse_vt = np.linalg.svd(matrices[key][-2], full_matrices=False)
            _, _, fine_vt = np.linalg.svd(matrices[key][-1], full_matrices=False)
            direction_angle = float(
                np.max(principal_angles_deg(coarse_vt[:1].T, fine_vt[:1].T))
            )
            checks = {
                "rank_consistent": int(coarse["threshold_rank"]) == rank,
                "singular_values_stable": singular_change
                <= float(config["retained_singular_value_relative_change_max"]),
                "top_direction_stable": direction_angle
                <= float(config["principal_angle_deg_max"]),
                "condition_bounded": float(fine["retained_condition_number"])
                <= float(config["retained_condition_number_max"]),
            }
            systems[str(coordinate_system)][group_name] = {
                "threshold_rank": rank,
                "effective_rank": float(fine["effective_rank"]),
                "retained_condition_number": float(fine["retained_condition_number"]),
                "retained_singular_value_relative_change": singular_change,
                "top_direction_step_angle_deg": direction_angle,
                "checks": checks,
                "all_numerical_checks_pass": bool(all(checks.values())),
            }

    raw_static = matrices[("raw_Cth_Sth", "static_only")][-1]
    raw_oscillatory = matrices[("raw_Cth_Sth", "oscillatory_only")][-1]
    _, _, static_vt = np.linalg.svd(raw_static, full_matrices=False)
    _, _, oscillatory_vt = np.linalg.svd(raw_oscillatory, full_matrices=False)
    complementary_angle = float(
        np.max(principal_angles_deg(static_vt[:1].T, oscillatory_vt[:1].T))
    )
    rank_invariant = all(
        systems["raw_Cth_Sth"][group]["threshold_rank"]
        == systems["quotient_tau_th_Sth"][group]["threshold_rank"]
        for group in groups
    )
    numerical_pass = all(
        systems[system][group]["all_numerical_checks_pass"]
        for system in systems
        for group in groups
    )
    joint_rank_pass = all(
        systems[system]["joint"]["threshold_rank"] == int(config["joint_required_rank"])
        for system in systems
    )
    complementarity_pass = complementary_angle >= float(
        config["complementary_top_direction_angle_deg_min"]
    )
    return rows, {
        "schema_version": "m36_event_aware_jacobian_v1",
        "event_sensitivity_method": config["event_sensitivity_method"],
        "coordinate_systems": systems,
        "static_oscillatory_top_direction_angle_deg": complementary_angle,
        "complementarity_gate_passed": complementarity_pass,
        "joint_rank_gate_passed": joint_rank_pass,
        "reversible_coordinate_transform_rank_invariant": rank_invariant,
        "rank_increase_from_reparameterization_claim": "forbidden",
        "all_numerical_gates_pass": numerical_pass,
        "conditional_fit_authorized": bool(
            numerical_pass and joint_rank_pass and complementarity_pass and rank_invariant
        ),
        "forward_evaluations": cache.forward_evaluations,
    }


def run_fit_start(
    *,
    job_id: str,
    objective: str,
    coordinate_system: str,
    fit_voltages: Sequence[float],
    observations: Mapping[float, Mapping[str, Any]],
    regimes: Mapping[float, str],
    base: VO2ThermalNeuristorParameters,
    fit_config: Mapping[str, Any],
    event_config: Mapping[str, Any],
    start_id: int,
    start_offset: Sequence[float],
    cache: EventForwardCache,
    task_started: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if time.perf_counter() - task_started > 3600.0 * float(
        fit_config["cpu_wall_clock_hours_max"]
    ):
        raise RuntimeError("M36 CPU wall-clock budget exhausted before fit start.")
    raw_bound = math.log(float(fit_config["raw_parameter_factor_bounds"][1]))
    raw_start = raw_bound * np.asarray(start_offset, dtype=np.float64)
    if coordinate_system == "raw_Cth_Sth":
        x0 = raw_start
        lower = np.asarray([-raw_bound, -raw_bound])
        upper = np.asarray([raw_bound, raw_bound])
    else:
        x0 = np.asarray([raw_start[0] - raw_start[1], raw_start[1]])
        lower = np.asarray([-2.0 * raw_bound, -raw_bound])
        upper = np.asarray([2.0 * raw_bound, raw_bound])
    before = cache.forward_evaluations
    result = least_squares(
        _objective_residual,
        x0=x0,
        bounds=(lower, upper),
        method="trf",
        loss=str(fit_config["loss"]),
        max_nfev=int(fit_config["max_nfev_per_start_per_objective"]),
        ftol=float(fit_config["ftol"]),
        xtol=float(fit_config["xtol"]),
        gtol=float(fit_config["gtol"]),
        x_scale=1.0,
        kwargs={
            "objective": objective,
            "coordinate_system": coordinate_system,
            "base": base,
            "observations": observations,
            "regimes": regimes,
            "fit_voltages": fit_voltages,
            "event_config": event_config,
            "cache": cache,
            "raw_bound": raw_bound,
        },
    )
    params = parameters_from_coordinates(base, result.x, coordinate_system)
    physical = physical_coordinate_record(params)
    finite = bool(
        np.isfinite(result.x).all()
        and math.isfinite(float(result.cost))
        and all(math.isfinite(value) and value > 0.0 for value in physical.values())
    )
    start = {
        "job_id": job_id,
        "objective": objective,
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
    metric_rows: list[dict[str, Any]] = []
    for voltage, observation in sorted(observations.items()):
        model = cache.simulate(
            params,
            voltage_V=voltage,
            evaluation_times_s=np.asarray(observation["time_s"], dtype=np.float64),
        )
        metrics = trace_metrics(
            observation,
            model.trace.time_s,
            model.trace.current_A,
            model.trace.voltage_V,
            event_config,
        )
        metric_rows.append(
            {
                "job_id": job_id,
                "objective": objective,
                "coordinate_system": coordinate_system,
                "start_id": int(start_id),
                "voltage_V": float(voltage),
                "regime": regimes[voltage],
                "role": "fit" if voltage in set(float(value) for value in fit_voltages) else "holdout",
                **metrics,
            }
        )
    return start, metric_rows


def aggregate_conditional_fit(
    starts: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    combinations: dict[str, Any] = {}
    for objective in config["objectives"]:
        for coordinate_system in config["coordinate_systems"]:
            key = f"{objective}::{coordinate_system}"
            selected_starts = [
                row
                for row in starts
                if row["objective"] == objective
                and row["coordinate_system"] == coordinate_system
            ]
            selected_metrics = [
                row
                for row in metrics
                if row["objective"] == objective
                and row["coordinate_system"] == coordinate_system
                and row["role"] == "holdout"
            ]
            fold_finite = {
                fold["fold_id"]: sum(
                    bool(row["finite"])
                    for row in selected_starts
                    if row["job_id"] == fold["fold_id"]
                )
                for fold in config["folds"]
            }
            nrmse = [float(row["combined_nrmse95"]) for row in selected_metrics]
            activity = [bool(row["activity_class_match"]) for row in selected_metrics]
            dispersion = coordinate_dispersion(
                selected_starts, coordinate_system=str(coordinate_system)
            )
            combinations[key] = {
                "fold_finite_start_counts": fold_finite,
                "finite_start_gate": all(
                    count >= int(config["minimum_finite_starts_per_fold"])
                    for count in fold_finite.values()
                ),
                "holdout_row_count": len(selected_metrics),
                "median_holdout_combined_nrmse95": float(np.median(nrmse))
                if nrmse
                else float("inf"),
                "activity_class_accuracy": float(np.mean(activity)) if activity else 0.0,
                "coordinate_dispersion": dispersion,
            }
    raw = combinations["raw_time_m35_baseline::quotient_tau_th_Sth"]
    orbit = combinations["regime_aware_orbit::quotient_tau_th_Sth"]
    raw_dispersion = float(raw["coordinate_dispersion"]["median_max_log_coordinate_std"])
    orbit_dispersion = float(orbit["coordinate_dispersion"]["median_max_log_coordinate_std"])
    checks = {
        "all_finite_start_gates": all(
            row["finite_start_gate"] for row in combinations.values()
        ),
        "all_lovo_rows_reported": all(
            row["holdout_row_count"] == 32 for row in combinations.values()
        ),
        "orbit_operational_nrmse": orbit["median_holdout_combined_nrmse95"]
        <= float(config["repository_operational_holdout_combined_nrmse95_max"]),
        "orbit_activity": orbit["activity_class_accuracy"]
        >= float(config["activity_class_accuracy_min"]),
        "orbit_nrmse_noninferior": orbit["median_holdout_combined_nrmse95"]
        <= raw["median_holdout_combined_nrmse95"]
        + float(config["orbit_noninferiority_margin"]),
        "orbit_dispersion_noninferior": orbit_dispersion
        <= raw_dispersion
        * (1.0 + float(config["orbit_parameter_dispersion_noninferiority_fraction"])),
    }
    return {
        "combinations": combinations,
        "same_max_nfev_budget_per_objective": True,
        "best_start_only_reporting": False,
        "checks": checks,
        "fit_lock_gate_passed": bool(all(checks.values())),
        "claim_status": "qualified_supported"
        if all(checks.values())
        else "failed_but_informative",
    }
