"""M37 continuous-event cross-regime observability utilities.

This module does not fit parameters.  It computes a local, whitened central-
difference Jacobian of the independently integrated continuous-event compact
model at the source parameter anchor.  Public curves define timestamps,
regimes, and locked noise scales; solver outputs remain solver-generated.
"""

from __future__ import annotations

import math
import time
from dataclasses import replace
from typing import Any, Mapping, Sequence

import numpy as np

from pinnpcm.external_data.vo2_multivoltage import activity_metrics
from pinnpcm.external_data.vo2_orbit_convergence import convergence_loglog_slope
from pinnpcm.physics.vo2_event_resolved import (
    EventResolvedResult,
    simulate_event_resolved_si,
)
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


GROUP_VOLTAGES: dict[str, tuple[float, ...]] = {
    "static_only": (9.0, 17.0),
    "oscillatory_only": (11.0, 15.0),
    "joint": (9.0, 11.0, 15.0, 17.0),
}
PARAMETER_NAMES = ("log_C_th", "log_S_e")


def _safe_float(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite value encountered: {value!r}")
    return result


def m36_semantic_audit(
    summary: Mapping[str, Any],
    metric_rows: Sequence[Mapping[str, Any]],
    *,
    execution_script_text: str,
    summary_sha256: str,
    metrics_sha256: str,
    execution_script_sha256: str,
) -> dict[str, Any]:
    """Supersede broad M36 wording without changing its historical vote."""

    broad_rule = (
        'elif not primary_pass:' in execution_script_text
        and 'classification = "true_numerical_nonconvergence"'
        in execution_script_text
    )
    by_voltage: dict[str, Any] = {}
    for voltage in (9.0, 11.0, 15.0, 17.0):
        key = f"{voltage:g}"
        source = dict(summary["voltage_results"][key])
        rows = [
            row
            for row in metric_rows
            if float(row["voltage_V"]) == voltage
            and str(row.get("solver_family", ""))
            == "source_compatible_explicit_euler"
        ]
        dt_values: list[float] = []
        scores: list[float] = []
        for row in rows:
            value = row.get("normalized_primary_score")
            if value in (None, ""):
                continue
            score = float(value)
            if not math.isfinite(score) or score <= 0.0:
                continue
            dt_values.append(float(row["dt_s"]))
            scores.append(score)
        slope = convergence_loglog_slope(dt_values, scores)
        pairwise_decrease = [
            bool(right < left) for left, right in zip(scores[:-1], scores[1:])
        ]
        overall_trend = bool(
            len(scores) >= 3
            and math.isfinite(slope)
            and slope >= 0.25
            and scores[-1] < scores[0]
        )
        source_classification = str(source["classification"])
        if voltage == 9.0:
            superseding = source_classification
        elif voltage == 11.0:
            superseding = (
                "finite_step_accuracy_gate_failed_with_observed_overall_"
                "but_nonmonotone_fine_scale_convergence_trend"
            )
        elif voltage == 15.0:
            superseding = (
                "finite_step_accuracy_gate_failed_after_event_sequence_"
                "stabilization_with_observed_convergence_trend"
            )
        else:
            superseding = (
                "finite_step_accuracy_gate_failed_with_observed_convergence_trend"
            )
        by_voltage[key] = {
            "source_m36_classification": source_classification,
            "superseding_semantic_wording": superseding,
            "m36_primary_gate_passed": bool(source["primary_gate_passed"]),
            "finite_score_count": len(scores),
            "dt_values_s": dt_values,
            "normalized_scores": scores,
            "loglog_slope": float(slope),
            "strict_pairwise_decrease": bool(all(pairwise_decrease)),
            "pairwise_decrease_checks": pairwise_decrease,
            "finest_less_than_coarsest": bool(scores and scores[-1] < scores[0]),
            "observed_convergence_trend": overall_trend,
        }
    return {
        "schema_version": "m37_m36_superseding_semantic_audit_v1",
        "source_stage": "M36_EVENT_RESOLVED_ORBIT_CONVERGENCE_AND_CONDITIONAL_PUBLIC_FIT",
        "source_summary_sha256": summary_sha256,
        "source_metrics_sha256": metrics_sha256,
        "source_execution_script_sha256": execution_script_sha256,
        "broad_primary_failure_classifier_detected": broad_rule,
        "source_m36_outputs_modified": False,
        "source_m36_failure_vote_unchanged": True,
        "m36_primary_gates_pass": bool(summary["m36_primary_gates_pass"]),
        "semantic_scope": "wording_correction_only_not_gate_relaxation",
        "voltage_audit": by_voltage,
        "claim_status": "supported",
    }


def build_whitening_record(
    observations: Mapping[float, Mapping[str, Any]],
    m36_summary: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Lock noise/physical scales before any M37 solver evaluation."""

    result: dict[str, Any] = {}
    for item in config["data"]["open_voltage_curves"]:
        voltage = float(item["voltage_V"])
        observation = observations[voltage]
        time_s = np.asarray(observation["time_s"], dtype=np.float64)
        duration = float(time_s[-1] - time_s[0])
        current_noise = float(observation["current_noise_scale_A"])
        voltage_noise = float(observation["device_voltage_noise_scale_V"])
        record: dict[str, Any] = {
            "regime": str(item["regime"]),
            "sample_count": int(time_s.size),
            "duration_s": duration,
            "current_noise_A": current_noise,
            "voltage_noise_V": voltage_noise,
        }
        if item["regime"] == "static":
            record["feature_scales"] = {
                "steady_current_A": current_noise,
                "steady_voltage_V": voltage_noise,
                "total_charge_C": max(current_noise * duration, 1.0e-30),
                "total_energy_J": max(
                    current_noise * voltage * duration, 1.0e-30
                ),
            }
        else:
            reference = m36_summary["voltage_results"][f"{voltage:g}"][
                "reference_parity_metrics"
            ]
            period = float(reference["reference_period_s"])
            record["locked_nominal_period_s"] = period
            record["feature_scales"] = {
                "log_frequency": float(
                    config["observations"].get("frequency_relative_scale", 0.005)
                ),
                "peak_to_trough_current_A": current_noise,
                "duty_cycle": 0.02,
                "cycle_charge_C": max(current_noise * period, 1.0e-30),
                "cycle_energy_J": max(
                    current_noise * voltage * period, 1.0e-30
                ),
                "phase_current_A": current_noise,
                "phase_voltage_V": voltage_noise,
            }
        result[f"{voltage:g}"] = record
    return {
        "scale_source": "m36_locked_noise_and_nominal_period_plus_preregistered_physical_integration_scales",
        "feature_family_equal_weight": True,
        "voltage_equal_weight": True,
        "joint_regime_equal_weight": True,
        "by_voltage": result,
    }


class M37ForwardCache:
    """Deterministic event-resolved cache with hard count and wall limits."""

    def __init__(
        self,
        *,
        reference_config: Mapping[str, Any],
        maximum_evaluations: int,
        maximum_wall_seconds: float,
    ) -> None:
        self.reference_config = reference_config
        self.maximum_evaluations = int(maximum_evaluations)
        self.maximum_wall_seconds = float(maximum_wall_seconds)
        self.started = time.perf_counter()
        self._cache: dict[tuple[Any, ...], EventResolvedResult] = {}
        self.counts = {"DOP853": 0, "Radau": 0}

    @property
    def total_evaluations(self) -> int:
        return int(sum(self.counts.values()))

    @property
    def elapsed_seconds(self) -> float:
        return float(time.perf_counter() - self.started)

    def simulate(
        self,
        params: VO2ThermalNeuristorParameters,
        *,
        voltage_V: float,
        evaluation_times_s: np.ndarray,
        method: str,
    ) -> EventResolvedResult:
        key = (
            round(float(params.C_th_J_per_K), 24),
            round(float(params.S_th_W_per_K), 18),
            round(float(voltage_V), 8),
            int(evaluation_times_s.size),
            round(float(evaluation_times_s[0]), 15),
            round(float(evaluation_times_s[-1]), 15),
            str(method),
        )
        if key not in self._cache:
            if self.total_evaluations >= self.maximum_evaluations:
                raise RuntimeError("M37 forward-evaluation budget exhausted.")
            if self.elapsed_seconds >= self.maximum_wall_seconds:
                raise RuntimeError("M37 CPU wall-clock budget exhausted.")
            self._cache[key] = simulate_event_resolved_si(
                params,
                input_voltage_V=float(voltage_V),
                evaluation_times_s=evaluation_times_s,
                method=str(method),
                reference_config=self.reference_config,
            )
            self.counts[str(method)] += 1
        return self._cache[key]


def perturbed_parameters(
    base: VO2ThermalNeuristorParameters,
    *,
    coordinate_index: int,
    log_offset: float,
) -> VO2ThermalNeuristorParameters:
    """Apply a signed perturbation in [log(C_th), log(S_e)]."""

    if coordinate_index == 0:
        return replace(
            base,
            C_th_J_per_K=float(base.C_th_J_per_K * math.exp(log_offset)),
        )
    if coordinate_index == 1:
        return replace(
            base,
            S_th_W_per_K=float(base.S_th_W_per_K * math.exp(log_offset)),
        )
    raise IndexError("M37 has exactly two registered coordinates.")


def reversal_type_signature(result: EventResolvedResult) -> tuple[str, ...]:
    return tuple(
        str(row["event_type"])
        for row in result.event_records
        if str(row["event_type"]).startswith("reversal_")
    )


def event_topology_compatible(
    reference: Sequence[str], candidate: Sequence[str]
) -> bool:
    """Require an exact common prefix and at most one terminal event difference."""

    reference_tuple = tuple(reference)
    candidate_tuple = tuple(candidate)
    if abs(len(reference_tuple) - len(candidate_tuple)) > 1:
        return False
    common = min(len(reference_tuple), len(candidate_tuple))
    return reference_tuple[:common] == candidate_tuple[:common]


def _activity_class(
    result: EventResolvedResult,
    *,
    event_config: Mapping[str, Any],
    current_noise_A: float,
) -> str:
    metrics = activity_metrics(
        result.trace.time_s,
        result.trace.current_A,
        result.trace.voltage_V,
        event_config,
        noise_scale_A=current_noise_A,
    )
    return str(metrics["activity_class"])


def _static_raw_features(
    result: EventResolvedResult, *, tail_fraction: float
) -> dict[str, Any]:
    time_s = result.trace.time_s
    current = result.trace.current_A
    voltage = result.trace.voltage_V
    tail = max(1, int(math.ceil(float(tail_fraction) * time_s.size)))
    return {
        "steady_current_A": float(np.median(current[-tail:])),
        "steady_voltage_V": float(np.median(voltage[-tail:])),
        "total_charge_C": float(np.trapz(np.maximum(current, 0.0), time_s)),
        "total_energy_J": float(
            np.trapz(np.maximum(current * voltage, 0.0), time_s)
        ),
    }


def _oscillatory_raw_features(
    result: EventResolvedResult,
    *,
    transient_fraction: float,
    phase_points: int,
) -> dict[str, Any]:
    time_s = result.trace.time_s
    current = result.trace.current_A
    voltage = result.trace.voltage_V
    transient_start = float(
        time_s[0] + float(transient_fraction) * (time_s[-1] - time_s[0])
    )
    anchors = np.asarray(
        [
            float(row["time_s"])
            for row in result.event_records
            if row["event_type"] == "reversal_to_cooling"
            and float(row["time_s"]) >= transient_start
        ],
        dtype=np.float64,
    )
    if anchors.size < 3:
        raise RuntimeError("M37 oscillatory feature extraction needs at least two cycles.")
    phase = np.linspace(0.0, 1.0, int(phase_points), dtype=np.float64)
    cycle_currents: list[np.ndarray] = []
    cycle_voltages: list[np.ndarray] = []
    periods: list[float] = []
    peaks: list[float] = []
    duties: list[float] = []
    charges: list[float] = []
    energies: list[float] = []
    for left, right in zip(anchors[:-1], anchors[1:]):
        query = left + phase * (right - left)
        cycle_current = np.interp(query, time_s, current)
        cycle_voltage = np.interp(query, time_s, voltage)
        period = float(right - left)
        amplitude = float(np.max(cycle_current) - np.min(cycle_current))
        threshold = float(np.min(cycle_current) + 0.5 * amplitude)
        cycle_currents.append(cycle_current)
        cycle_voltages.append(cycle_voltage)
        periods.append(period)
        peaks.append(amplitude)
        duties.append(float(np.mean(cycle_current >= threshold)))
        charges.append(
            float(period * np.trapz(np.maximum(cycle_current, 0.0), phase))
        )
        energies.append(
            float(
                period
                * np.trapz(
                    np.maximum(cycle_current * cycle_voltage, 0.0), phase
                )
            )
        )
    period = float(np.median(periods))
    return {
        "log_frequency": float(math.log(1.0 / period)),
        "peak_to_trough_current_A": float(np.median(peaks)),
        "duty_cycle": float(np.median(duties)),
        "cycle_charge_C": float(np.median(charges)),
        "cycle_energy_J": float(np.median(energies)),
        "phase_current_A": np.median(np.vstack(cycle_currents), axis=0),
        "phase_voltage_V": np.median(np.vstack(cycle_voltages), axis=0),
        "cycle_count": int(len(periods)),
        "period_s": period,
    }


def whitened_feature_vector(
    result: EventResolvedResult,
    *,
    regime: str,
    scale_record: Mapping[str, Any],
    observation_config: Mapping[str, Any],
) -> tuple[np.ndarray, tuple[str, ...], dict[str, Any]]:
    """Return a fixed, block-balanced feature vector and its raw QoIs."""

    scales = scale_record["feature_scales"]
    if regime == "static":
        raw = _static_raw_features(
            result, tail_fraction=float(observation_config["tail_fraction"])
        )
        names = (
            "steady_current_A",
            "steady_voltage_V",
            "total_charge_C",
            "total_energy_J",
        )
        family_weight = 1.0 / math.sqrt(len(names))
        vector = np.asarray(
            [raw[name] / float(scales[name]) * family_weight for name in names],
            dtype=np.float64,
        )
        return vector, names, raw

    phase_points = int(observation_config["phase_grid_points"])
    raw = _oscillatory_raw_features(
        result,
        transient_fraction=float(observation_config["transient_fraction"]),
        phase_points=phase_points,
    )
    family_count = 7.0
    scalar_weight = 1.0 / math.sqrt(family_count)
    waveform_weight = 1.0 / math.sqrt(family_count * phase_points)
    scalar_names = (
        "log_frequency",
        "peak_to_trough_current_A",
        "duty_cycle",
        "cycle_charge_C",
        "cycle_energy_J",
    )
    values = [
        float(raw[name]) / float(scales[name]) * scalar_weight
        for name in scalar_names
    ]
    labels = list(scalar_names)
    for family, scale_name in (
        ("phase_current_A", "phase_current_A"),
        ("phase_voltage_V", "phase_voltage_V"),
    ):
        array = np.asarray(raw[family], dtype=np.float64)
        values.extend(
            (array / float(scales[scale_name]) * waveform_weight).tolist()
        )
        labels.extend(f"{family}[{index}]" for index in range(array.size))
    return np.asarray(values, dtype=np.float64), tuple(labels), raw


def group_feature_vector(
    results: Mapping[float, EventResolvedResult],
    *,
    group: str,
    regimes: Mapping[float, str],
    whitening: Mapping[str, Any],
    observation_config: Mapping[str, Any],
) -> np.ndarray:
    if group == "joint":
        static = group_feature_vector(
            results,
            group="static_only",
            regimes=regimes,
            whitening=whitening,
            observation_config=observation_config,
        )
        oscillatory = group_feature_vector(
            results,
            group="oscillatory_only",
            regimes=regimes,
            whitening=whitening,
            observation_config=observation_config,
        )
        return np.concatenate((static, oscillatory)) / math.sqrt(2.0)
    parts: list[np.ndarray] = []
    for voltage in GROUP_VOLTAGES[group]:
        vector, _, _ = whitened_feature_vector(
            results[voltage],
            regime=regimes[voltage],
            scale_record=whitening["by_voltage"][f"{voltage:g}"],
            observation_config=observation_config,
        )
        parts.append(vector)
    return np.concatenate(parts) / math.sqrt(len(parts))


def svd_geometry(matrix: np.ndarray, *, relative_threshold: float) -> dict[str, Any]:
    u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    if singular.size == 0 or singular[0] <= 0.0:
        rank = 0
        condition = float("inf")
        effective = 0.0
    else:
        rank = int(np.sum(singular / singular[0] >= float(relative_threshold)))
        condition = float(singular[0] / singular[rank - 1]) if rank else float("inf")
        probability = singular**2 / np.sum(singular**2)
        effective = float(np.exp(-np.sum(probability * np.log(probability + 1.0e-300))))
    return {
        "u": u,
        "singular_values": singular,
        "vt": vt,
        "threshold_rank": rank,
        "effective_rank": effective,
        "retained_condition_number": condition,
    }


def subspace_angle_deg(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape[1] == 0 or right.shape[1] == 0:
        return float("inf")
    q_left, _ = np.linalg.qr(left)
    q_right, _ = np.linalg.qr(right)
    cosines = np.linalg.svd(q_left.T @ q_right, compute_uv=False)
    smallest = float(np.clip(np.min(cosines), 0.0, 1.0))
    return float(np.degrees(np.arccos(smallest)))


def acute_vector_angle_deg(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 0.0:
        return float("inf")
    cosine = float(np.clip(abs(float(np.dot(left, right))) / denominator, 0.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def column_direction_cosines(left: np.ndarray, right: np.ndarray) -> list[float]:
    values: list[float] = []
    for index in range(left.shape[1]):
        denominator = float(
            np.linalg.norm(left[:, index]) * np.linalg.norm(right[:, index])
        )
        values.append(
            0.0
            if denominator <= 0.0
            else float(abs(np.dot(left[:, index], right[:, index])) / denominator)
        )
    return values


def analytic_quotient_jacobian(raw_jacobian: np.ndarray) -> np.ndarray:
    """Transform J_theta to J_q with theta=[q1+q2,q2], without simulation."""

    quotient_to_raw = np.asarray([[1.0, 1.0], [0.0, 1.0]], dtype=np.float64)
    return raw_jacobian @ quotient_to_raw


def _result_checks(
    result: EventResolvedResult,
    nominal_signature: Sequence[str],
    *,
    expected_activity: str,
    event_config: Mapping[str, Any],
    current_noise_A: float,
) -> dict[str, bool]:
    finite = bool(
        np.isfinite(result.trace.current_A).all()
        and np.isfinite(result.trace.voltage_V).all()
        and np.isfinite(result.trace.temperature_K).all()
        and np.isfinite(result.trace.resistance_ohm).all()
    )
    activity = _activity_class(
        result, event_config=event_config, current_noise_A=current_noise_A
    )
    signature = reversal_type_signature(result)
    return {
        "finite_state": finite,
        "activity_class_exact": activity == expected_activity,
        "event_topology_compatible": event_topology_compatible(
            nominal_signature, signature
        ),
    }


def run_cross_regime_observability(
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    regimes: Mapping[float, str],
    expected_activity: Mapping[float, str],
    config: Mapping[str, Any],
    m36_config: Mapping[str, Any],
    whitening: Mapping[str, Any],
    m36_expected_event_counts: Mapping[float, int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute the exact preregistered M37 finite-difference matrix."""

    steps = [float(value) for value in config["parameters"]["relative_steps"]]
    fine_step = steps[-1]
    gates = config["gates"]
    threshold = float(gates["relative_singular_value_rank_threshold"])
    cache = M37ForwardCache(
        reference_config=m36_config["independent_reference"],
        maximum_evaluations=int(config["solvers"]["maximum_total_forward_evaluations"]),
        maximum_wall_seconds=float(config["budget"]["maximum_incremental_cpu_wall_hours"])
        * 3600.0,
    )
    event_config = m36_config["event_metrics"]
    nominal: dict[str, dict[float, EventResolvedResult]] = {"DOP853": {}, "Radau": {}}
    nominal_checks: dict[str, Any] = {}
    for method in ("DOP853", "Radau"):
        nominal_checks[method] = {}
        for voltage in (9.0, 11.0, 15.0, 17.0):
            result = cache.simulate(
                base,
                voltage_V=voltage,
                evaluation_times_s=np.asarray(observations[voltage]["time_s"], dtype=np.float64),
                method=method,
            )
            nominal[method][voltage] = result
            signature = reversal_type_signature(result)
            checks = _result_checks(
                result,
                signature,
                expected_activity=expected_activity[voltage],
                event_config=event_config,
                current_noise_A=float(observations[voltage]["current_noise_scale_A"]),
            )
            checks["m36_event_count_reproduced"] = (
                len(signature) == int(m36_expected_event_counts[voltage])
            )
            nominal_checks[method][f"{voltage:g}"] = {
                **checks,
                "event_count": len(signature),
            }
    for voltage in (9.0, 11.0, 15.0, 17.0):
        dop_signature = reversal_type_signature(nominal["DOP853"][voltage])
        radau_signature = reversal_type_signature(nominal["Radau"][voltage])
        nominal_checks["DOP853"][f"{voltage:g}"]["radau_sequence_exact"] = (
            dop_signature == radau_signature
        )
        nominal_checks["Radau"][f"{voltage:g}"]["dop853_sequence_exact"] = (
            dop_signature == radau_signature
        )
    nominal_gate = bool(
        all(
            all(value is True for key, value in record.items() if isinstance(value, bool))
            for method in nominal_checks.values()
            for record in method.values()
        )
    )

    rows: list[dict[str, Any]] = []
    matrices: dict[tuple[str, float, str], np.ndarray] = {}
    simulation_checks: list[dict[str, Any]] = []
    if not nominal_gate:
        return rows, {
            "status": "stopped_at_nominal_solver_event_gate",
            "nominal_checks": nominal_checks,
            "m37_all_gates_pass": False,
            "m38_authorized": False,
            "forward_evaluations": {**cache.counts, "total": cache.total_evaluations},
            "elapsed_seconds": cache.elapsed_seconds,
        }

    dop_by_step: dict[float, dict[tuple[int, int], dict[float, EventResolvedResult]]] = {}
    for step in steps:
        dop_by_step[step] = {}
        for coordinate_index in range(2):
            for sign in (-1, 1):
                params = perturbed_parameters(
                    base,
                    coordinate_index=coordinate_index,
                    log_offset=float(sign) * step,
                )
                results: dict[float, EventResolvedResult] = {}
                for voltage in (9.0, 11.0, 15.0, 17.0):
                    result = cache.simulate(
                        params,
                        voltage_V=voltage,
                        evaluation_times_s=np.asarray(
                            observations[voltage]["time_s"], dtype=np.float64
                        ),
                        method="DOP853",
                    )
                    results[voltage] = result
                    checks = _result_checks(
                        result,
                        reversal_type_signature(nominal["DOP853"][voltage]),
                        expected_activity=expected_activity[voltage],
                        event_config=event_config,
                        current_noise_A=float(
                            observations[voltage]["current_noise_scale_A"]
                        ),
                    )
                    simulation_checks.append(
                        {
                            "method": "DOP853",
                            "relative_step": step,
                            "coordinate": PARAMETER_NAMES[coordinate_index],
                            "sign": sign,
                            "voltage_V": voltage,
                            **checks,
                        }
                    )
                dop_by_step[step][(coordinate_index, sign)] = results
        current_step_checks = [
            row
            for row in simulation_checks
            if row["method"] == "DOP853" and row["relative_step"] == step
        ]
        if not all(
            row["finite_state"]
            and row["activity_class_exact"]
            and row["event_topology_compatible"]
            for row in current_step_checks
        ):
            return rows, {
                "status": "stopped_at_dop853_perturbation_event_gate",
                "nominal_checks": nominal_checks,
                "simulation_checks": simulation_checks,
                "m37_all_gates_pass": False,
                "m38_authorized": False,
                "forward_evaluations": {**cache.counts, "total": cache.total_evaluations},
                "elapsed_seconds": cache.elapsed_seconds,
            }
        for group in GROUP_VOLTAGES:
            columns: list[np.ndarray] = []
            for coordinate_index in range(2):
                plus = group_feature_vector(
                    dop_by_step[step][(coordinate_index, 1)],
                    group=group,
                    regimes=regimes,
                    whitening=whitening,
                    observation_config=config["observations"],
                )
                minus = group_feature_vector(
                    dop_by_step[step][(coordinate_index, -1)],
                    group=group,
                    regimes=regimes,
                    whitening=whitening,
                    observation_config=config["observations"],
                )
                columns.append((plus - minus) / (2.0 * step))
            matrices[("DOP853", step, group)] = np.column_stack(columns)

    radau_fine: dict[tuple[int, int], dict[float, EventResolvedResult]] = {}
    for coordinate_index in range(2):
        for sign in (-1, 1):
            params = perturbed_parameters(
                base,
                coordinate_index=coordinate_index,
                log_offset=float(sign) * fine_step,
            )
            results = {}
            for voltage in (9.0, 11.0, 15.0, 17.0):
                result = cache.simulate(
                    params,
                    voltage_V=voltage,
                    evaluation_times_s=np.asarray(
                        observations[voltage]["time_s"], dtype=np.float64
                    ),
                    method="Radau",
                )
                results[voltage] = result
                checks = _result_checks(
                    result,
                    reversal_type_signature(nominal["Radau"][voltage]),
                    expected_activity=expected_activity[voltage],
                    event_config=event_config,
                    current_noise_A=float(observations[voltage]["current_noise_scale_A"]),
                )
                simulation_checks.append(
                    {
                        "method": "Radau",
                        "relative_step": fine_step,
                        "coordinate": PARAMETER_NAMES[coordinate_index],
                        "sign": sign,
                        "voltage_V": voltage,
                        **checks,
                    }
                )
            radau_fine[(coordinate_index, sign)] = results
    radau_checks = [row for row in simulation_checks if row["method"] == "Radau"]
    if not all(
        row["finite_state"]
        and row["activity_class_exact"]
        and row["event_topology_compatible"]
        for row in radau_checks
    ):
        return rows, {
            "status": "stopped_at_radau_perturbation_event_gate",
            "nominal_checks": nominal_checks,
            "simulation_checks": simulation_checks,
            "m37_all_gates_pass": False,
            "m38_authorized": False,
            "forward_evaluations": {**cache.counts, "total": cache.total_evaluations},
            "elapsed_seconds": cache.elapsed_seconds,
        }
    for group in GROUP_VOLTAGES:
        columns = []
        for coordinate_index in range(2):
            plus = group_feature_vector(
                radau_fine[(coordinate_index, 1)],
                group=group,
                regimes=regimes,
                whitening=whitening,
                observation_config=config["observations"],
            )
            minus = group_feature_vector(
                radau_fine[(coordinate_index, -1)],
                group=group,
                regimes=regimes,
                whitening=whitening,
                observation_config=config["observations"],
            )
            columns.append((plus - minus) / (2.0 * fine_step))
        matrices[("Radau", fine_step, group)] = np.column_stack(columns)

    geometries: dict[tuple[str, float, str], dict[str, Any]] = {}
    for (method, step, group), matrix in matrices.items():
        geometry = svd_geometry(matrix, relative_threshold=threshold)
        geometries[(method, step, group)] = geometry
        for singular_index, singular_value in enumerate(geometry["singular_values"]):
            rows.append(
                {
                    "method": method,
                    "coordinate_system": "raw_log_C_th_log_S_e",
                    "observation_group": group,
                    "relative_step": step,
                    "singular_index": singular_index,
                    "singular_value": float(singular_value),
                    "threshold_rank": int(geometry["threshold_rank"]),
                    "effective_rank": float(geometry["effective_rank"]),
                    "retained_condition_number": float(
                        geometry["retained_condition_number"]
                    ),
                    "top_right_log_C_th": float(geometry["vt"][0, 0]),
                    "top_right_log_S_e": float(geometry["vt"][0, 1]),
                }
            )

    group_results: dict[str, Any] = {}
    crosscheck: dict[str, Any] = {}
    for group in GROUP_VOLTAGES:
        coarse_matrix = matrices[("DOP853", steps[-2], group)]
        fine_matrix = matrices[("DOP853", fine_step, group)]
        coarse_geometry = geometries[("DOP853", steps[-2], group)]
        fine_geometry = geometries[("DOP853", fine_step, group)]
        ranks_match = int(coarse_geometry["threshold_rank"]) == int(
            fine_geometry["threshold_rank"]
        )
        rank = int(fine_geometry["threshold_rank"])
        jacobian_change = float(
            np.linalg.norm(coarse_matrix - fine_matrix)
            / max(np.linalg.norm(fine_matrix), 1.0e-30)
        )
        if ranks_match and rank > 0:
            left_angle = subspace_angle_deg(
                coarse_geometry["u"][:, :rank], fine_geometry["u"][:, :rank]
            )
        else:
            left_angle = float("inf")
        step_checks = {
            "rank_consistent": ranks_match,
            "white_jacobian_stable": jacobian_change
            <= float(gates["two_finest_white_jacobian_relative_change_max"]),
            "retained_left_subspace_stable": left_angle
            <= float(gates["two_finest_retained_left_subspace_angle_deg_max"]),
        }
        group_results[group] = {
            "threshold_rank": rank,
            "effective_rank": float(fine_geometry["effective_rank"]),
            "singular_values": [
                float(value) for value in fine_geometry["singular_values"]
            ],
            "retained_condition_number": float(
                fine_geometry["retained_condition_number"]
            ),
            "top_right_singular_vector": [
                float(value) for value in fine_geometry["vt"][0]
            ],
            "two_finest_white_jacobian_relative_change": jacobian_change,
            "two_finest_retained_left_subspace_angle_deg": left_angle,
            "step_checks": step_checks,
            "all_step_gates_pass": bool(all(step_checks.values())),
        }

        radau_matrix = matrices[("Radau", fine_step, group)]
        radau_geometry = geometries[("Radau", fine_step, group)]
        cosines = column_direction_cosines(fine_matrix, radau_matrix)
        retained = max(
            int(fine_geometry["threshold_rank"]),
            int(radau_geometry["threshold_rank"]),
            1,
        )
        singular_difference = float(
            np.max(
                np.abs(
                    fine_geometry["singular_values"][:retained]
                    - radau_geometry["singular_values"][:retained]
                )
                / np.maximum(
                    np.abs(fine_geometry["singular_values"][:retained]), 1.0e-30
                )
            )
        )
        cross_checks = {
            "column_direction_cosines_pass": min(cosines)
            >= float(gates["dop853_radau_column_direction_cosine_min"]),
            "retained_singular_values_pass": singular_difference
            <= float(
                gates[
                    "dop853_radau_retained_singular_value_relative_difference_max"
                ]
            ),
            "rank_consistent": int(fine_geometry["threshold_rank"])
            == int(radau_geometry["threshold_rank"]),
        }
        crosscheck[group] = {
            "column_direction_cosines": cosines,
            "minimum_column_direction_cosine": min(cosines),
            "retained_singular_value_relative_difference": singular_difference,
            "dop853_rank": int(fine_geometry["threshold_rank"]),
            "radau_rank": int(radau_geometry["threshold_rank"]),
            "checks": cross_checks,
            "all_crosscheck_gates_pass": bool(all(cross_checks.values())),
        }

    static_direction = geometries[("DOP853", fine_step, "static_only")]["vt"][0]
    oscillatory_direction = geometries[("DOP853", fine_step, "oscillatory_only")][
        "vt"
    ][0]
    complementary_angle = acute_vector_angle_deg(
        static_direction, oscillatory_direction
    )
    joint = group_results["joint"]
    joint_rank_pass = int(joint["threshold_rank"]) == int(
        gates["joint_required_rank"]
    )
    joint_condition_pass = float(joint["retained_condition_number"]) <= float(
        gates["joint_retained_condition_number_max"]
    )
    complementarity_pass = complementary_angle >= float(
        gates["static_oscillatory_top_right_direction_angle_deg_min"]
    )

    quotient: dict[str, Any] = {}
    rank_invariant = True
    for group in GROUP_VOLTAGES:
        raw = matrices[("DOP853", fine_step, group)]
        transformed = analytic_quotient_jacobian(raw)
        geometry = svd_geometry(transformed, relative_threshold=threshold)
        raw_algebraic_rank = int(np.linalg.matrix_rank(raw))
        transformed_algebraic_rank = int(np.linalg.matrix_rank(transformed))
        transformed_threshold_rank = int(geometry["threshold_rank"])
        rank_invariant = (
            rank_invariant and raw_algebraic_rank == transformed_algebraic_rank
        )
        quotient[group] = {
            "threshold_rank": transformed_threshold_rank,
            "raw_threshold_rank": int(group_results[group]["threshold_rank"]),
            "raw_algebraic_rank": raw_algebraic_rank,
            "transformed_algebraic_rank": transformed_algebraic_rank,
            "singular_values": [float(value) for value in geometry["singular_values"]],
            "retained_condition_number": float(
                geometry["retained_condition_number"]
            ),
            "algebraic_rank_matches_raw": raw_algebraic_rank
            == transformed_algebraic_rank,
            "threshold_rank_is_coordinate_scale_dependent": True,
        }
        for singular_index, singular_value in enumerate(geometry["singular_values"]):
            rows.append(
                {
                    "method": "DOP853_analytic_transform",
                    "coordinate_system": "quotient_log_tau_th_log_S_e",
                    "observation_group": group,
                    "relative_step": fine_step,
                    "singular_index": singular_index,
                    "singular_value": float(singular_value),
                    "threshold_rank": transformed_threshold_rank,
                    "effective_rank": float(geometry["effective_rank"]),
                    "retained_condition_number": float(
                        geometry["retained_condition_number"]
                    ),
                    "top_right_log_C_th": None,
                    "top_right_log_S_e": None,
                }
            )

    simulation_gate = bool(
        nominal_gate
        and all(
            row["finite_state"]
            and row["activity_class_exact"]
            and row["event_topology_compatible"]
            for row in simulation_checks
        )
    )
    step_gate = bool(all(group["all_step_gates_pass"] for group in group_results.values()))
    cross_gate = bool(
        all(record["all_crosscheck_gates_pass"] for record in crosscheck.values())
    )
    all_gates = bool(
        simulation_gate
        and step_gate
        and cross_gate
        and joint_rank_pass
        and joint_condition_pass
        and complementarity_pass
        and rank_invariant
    )
    return rows, {
        "status": "all_m37_gates_passed" if all_gates else "m37_observability_gate_failed",
        "nominal_checks": nominal_checks,
        "simulation_check_count": len(simulation_checks),
        "simulation_gate_passed": simulation_gate,
        "groups": group_results,
        "dop853_radau_crosscheck": crosscheck,
        "static_oscillatory_top_direction_angle_deg": complementary_angle,
        "complementarity_gate_passed": complementarity_pass,
        "joint_rank_gate_passed": joint_rank_pass,
        "joint_condition_gate_passed": joint_condition_pass,
        "analytic_quotient_transform": {
            "raw_to_quotient_matrix": [[1.0, -1.0], [0.0, 1.0]],
            "quotient_to_raw_matrix": [[1.0, 1.0], [0.0, 1.0]],
            "resimulation_performed": False,
            "rank_invariant": rank_invariant,
            "rank_increase_claim": "forbidden",
            "groups": quotient,
        },
        "m37_all_gates_pass": all_gates,
        "m38_authorized": all_gates,
        "forward_evaluations": {**cache.counts, "total": cache.total_evaluations},
        "elapsed_seconds": cache.elapsed_seconds,
        "simulation_checks": simulation_checks,
    }
