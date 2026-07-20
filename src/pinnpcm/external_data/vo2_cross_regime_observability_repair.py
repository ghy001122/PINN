"""M37R repair for the post-transient event-window observability vote.

M37R changes exactly one scientific implementation contract from M37: every
event signature used for M36 count reproduction or perturbation topology is
cropped to the same inclusive post-transient interval.  Full-horizon counts
remain diagnostic only.  No fit, optimization, bootstrap, PINN training, or
13 V data access is implemented here.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np

from pinnpcm.external_data.vo2_cross_regime_observability import (
    GROUP_VOLTAGES,
    PARAMETER_NAMES,
    acute_vector_angle_deg,
    analytic_quotient_jacobian,
    column_direction_cosines,
    event_topology_compatible,
    group_feature_vector,
    perturbed_parameters,
    subspace_angle_deg,
    svd_geometry,
)
from pinnpcm.external_data.vo2_multivoltage import activity_metrics
from pinnpcm.physics.vo2_event_resolved import (
    EventResolvedResult,
    simulate_event_resolved_si,
)
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


M37R_SCHEMA_VERSION = "m37r_continuous_event_observability_evidence_v1"
M37R_STAGE_ID = "M37R_CONTINUOUS_EVENT_CROSS_REGIME_OBSERVABILITY_REPAIR"
EVENT_WINDOW_CONTRACT_ID = "m37r_post_transient_reversal_signature_v1"


def _signature_sha256(signature: Sequence[str]) -> str:
    encoded = json.dumps(list(signature), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def post_transient_event_signature(
    event_records: Sequence[Mapping[str, Any]],
    *,
    trace_start_s: float,
    trace_end_s: float,
    transient_fraction: float,
) -> dict[str, Any]:
    """Return full and post-transient reversal signatures under one rule.

    The scientific gate interval is exactly
    ``[t0 + transient_fraction * (T - t0), T]``.  Both boundaries are
    inclusive and no floating tolerance is applied.  Events outside the
    trace horizon are excluded from both signatures.
    """

    start = float(trace_start_s)
    end = float(trace_end_s)
    fraction = float(transient_fraction)
    if not (math.isfinite(start) and math.isfinite(end) and end >= start):
        raise ValueError("M37R event-window bounds must be finite and ordered.")
    if not (0.0 <= fraction < 1.0):
        raise ValueError("M37R transient_fraction must lie in [0, 1).")
    window_start = start + fraction * (end - start)
    full: list[str] = []
    post: list[str] = []
    full_times: list[float] = []
    post_times: list[float] = []
    for row in event_records:
        event_type = str(row["event_type"])
        if not event_type.startswith("reversal_"):
            continue
        event_time = float(row["time_s"])
        if start <= event_time <= end:
            full.append(event_type)
            full_times.append(event_time)
            if window_start <= event_time <= end:
                post.append(event_type)
                post_times.append(event_time)
    return {
        "contract_id": EVENT_WINDOW_CONTRACT_ID,
        "interval": "[t0 + transient_fraction * (T - t0), T]",
        "trace_start_s": start,
        "trace_end_s": end,
        "window_start_s": window_start,
        "transient_fraction": fraction,
        "lower_boundary": "inclusive",
        "upper_boundary": "inclusive",
        "floating_tolerance_s": 0.0,
        "full_horizon_signature": tuple(full),
        "post_transient_signature": tuple(post),
        "full_horizon_event_times_s": tuple(full_times),
        "post_transient_event_times_s": tuple(post_times),
        "full_horizon_event_count": len(full),
        "post_transient_event_count": len(post),
        "full_horizon_signature_sha256": _signature_sha256(full),
        "post_transient_signature_sha256": _signature_sha256(post),
    }


def event_topology_diagnostics(
    reference: Sequence[str], candidate: Sequence[str]
) -> dict[str, Any]:
    reference_tuple = tuple(reference)
    candidate_tuple = tuple(candidate)
    common = 0
    for left, right in zip(reference_tuple, candidate_tuple):
        if left != right:
            break
        common += 1
    return {
        "event_topology_compatible": event_topology_compatible(
            reference_tuple, candidate_tuple
        ),
        "reference_post_transient_event_count": len(reference_tuple),
        "candidate_post_transient_event_count": len(candidate_tuple),
        "post_transient_event_count_difference": len(candidate_tuple)
        - len(reference_tuple),
        "common_prefix_length": common,
        "reference_signature_sha256": _signature_sha256(reference_tuple),
        "candidate_signature_sha256": _signature_sha256(candidate_tuple),
    }


def forward_cache_key(
    params: VO2ThermalNeuristorParameters,
    *,
    voltage_V: float,
    evaluation_times_s: np.ndarray,
    method: str,
    event_window_contract_id: str,
) -> tuple[Any, ...]:
    """Build the deterministic cache key, including the event-window contract."""

    return (
        str(event_window_contract_id),
        str(method),
        round(float(voltage_V), 8),
        round(float(params.C_th_J_per_K), 24),
        round(float(params.S_th_W_per_K), 18),
        int(evaluation_times_s.size),
        round(float(evaluation_times_s[0]), 15),
        round(float(evaluation_times_s[-1]), 15),
    )


class M37RForwardCache:
    """Deterministic solver cache with hard forward and wall-clock limits."""

    def __init__(
        self,
        *,
        reference_config: Mapping[str, Any],
        maximum_evaluations: int,
        maximum_wall_seconds: float,
        event_window_contract_id: str,
    ) -> None:
        self.reference_config = reference_config
        self.maximum_evaluations = int(maximum_evaluations)
        self.maximum_wall_seconds = float(maximum_wall_seconds)
        self.event_window_contract_id = str(event_window_contract_id)
        self.started = time.perf_counter()
        self._cache: dict[tuple[Any, ...], EventResolvedResult] = {}
        self.counts = {"DOP853": 0, "Radau": 0}
        self.cache_hits = 0

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
        key = forward_cache_key(
            params,
            voltage_V=voltage_V,
            evaluation_times_s=evaluation_times_s,
            method=method,
            event_window_contract_id=self.event_window_contract_id,
        )
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        if self.total_evaluations >= self.maximum_evaluations:
            raise RuntimeError("M37R forward-evaluation budget exhausted.")
        if self.elapsed_seconds >= self.maximum_wall_seconds:
            raise RuntimeError("M37R CPU wall-clock budget exhausted.")
        result = simulate_event_resolved_si(
            params,
            input_voltage_V=float(voltage_V),
            evaluation_times_s=evaluation_times_s,
            method=str(method),
            reference_config=self.reference_config,
        )
        self._cache[key] = result
        self.counts[str(method)] += 1
        return result


def build_m36_reference_window_audit(
    event_rows: Sequence[Mapping[str, Any]],
    observations: Mapping[float, Mapping[str, Any]],
    expected_counts: Mapping[float, int],
    *,
    transient_fraction: float,
) -> dict[str, Any]:
    """Reapply the M37R helper to the M36 post-transient reference rows."""

    by_voltage: dict[str, Any] = {}
    for voltage in (9.0, 11.0, 15.0, 17.0):
        reference_records: list[dict[str, Any]] = []
        for row in event_rows:
            if float(row["voltage_V"]) != voltage or str(row["candidate"]) != "Radau":
                continue
            if row.get("reference_event_type") in (None, ""):
                continue
            reference_records.append(
                {
                    "event_type": str(row["reference_event_type"]),
                    "time_s": float(row["reference_time_s"]),
                }
            )
        times = np.asarray(observations[voltage]["time_s"], dtype=np.float64)
        signature = post_transient_event_signature(
            reference_records,
            trace_start_s=float(times[0]),
            trace_end_s=float(times[-1]),
            transient_fraction=transient_fraction,
        )
        count = int(signature["post_transient_event_count"])
        expected = int(expected_counts[voltage])
        by_voltage[f"{voltage:g}"] = {
            "source": "m36_event_times_reference_rows_for_Radau_comparison",
            "source_rows_are_already_post_transient": True,
            "available_event_row_count": len(reference_records),
            "post_transient_event_count": count,
            "expected_m36_summary_count": expected,
            "count_matches_m36_summary": count == expected,
            "post_transient_signature_sha256": signature[
                "post_transient_signature_sha256"
            ],
            "window_start_s": signature["window_start_s"],
            "trace_end_s": signature["trace_end_s"],
        }
    return {
        "event_window_contract_id": EVENT_WINDOW_CONTRACT_ID,
        "transient_fraction": float(transient_fraction),
        "boundary_rule": "inclusive_lower_and_upper_without_tolerance",
        "by_voltage": by_voltage,
        "all_counts_match": all(
            record["count_matches_m36_summary"] for record in by_voltage.values()
        ),
    }


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


def _result_audit(
    result: EventResolvedResult,
    reference_post_signature: Sequence[str],
    *,
    expected_activity: str,
    event_config: Mapping[str, Any],
    current_noise_A: float,
    transient_fraction: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    finite = bool(
        np.isfinite(result.trace.current_A).all()
        and np.isfinite(result.trace.voltage_V).all()
        and np.isfinite(result.trace.temperature_K).all()
        and np.isfinite(result.trace.resistance_ohm).all()
    )
    activity = _activity_class(
        result, event_config=event_config, current_noise_A=current_noise_A
    )
    signature = post_transient_event_signature(
        result.event_records,
        trace_start_s=float(result.trace.time_s[0]),
        trace_end_s=float(result.trace.time_s[-1]),
        transient_fraction=transient_fraction,
    )
    topology = event_topology_diagnostics(
        reference_post_signature, signature["post_transient_signature"]
    )
    checks = {
        "finite_state": finite,
        "activity_class": activity,
        "activity_class_exact": activity == expected_activity,
        **topology,
    }
    return checks, signature


def _gate_template() -> dict[str, bool]:
    return {
        "nominal_window_reproduction": False,
        "all_states_finite": False,
        "all_activity_classes_exact": False,
        "all_post_transient_event_topologies_compatible": False,
        "two_finest_white_jacobian_stability": False,
        "two_finest_retained_left_subspace_stability": False,
        "dop853_radau_column_direction_consistency": False,
        "dop853_radau_retained_singular_value_consistency": False,
        "dop853_radau_rank_consistency": False,
        "joint_rank": False,
        "joint_condition": False,
        "static_oscillatory_complementarity": False,
        "analytic_rank_invariance": False,
        "forward_budget": False,
        "wall_clock_budget": False,
        "all": False,
    }


def _base_result(
    *,
    status: str,
    cache: M37RForwardCache,
    nominal_checks: Mapping[str, Any],
    simulation_checks: Sequence[Mapping[str, Any]],
    m36_reference_window_audit: Mapping[str, Any],
    gate_results: Mapping[str, bool],
) -> dict[str, Any]:
    return {
        "schema_version": M37R_SCHEMA_VERSION,
        "stage_id": M37R_STAGE_ID,
        "status": status,
        "claim_status": "failed_but_informative",
        "m37r_all_gates_pass": False,
        "gate_results": dict(gate_results),
        "event_window_contract": {
            "contract_id": EVENT_WINDOW_CONTRACT_ID,
            "interval": "[t0 + 0.1 * (T - t0), T]",
            "transient_fraction": 0.1,
            "lower_boundary": "inclusive",
            "upper_boundary": "inclusive",
            "floating_tolerance_s": 0.0,
            "full_horizon_role": "diagnostic_only_not_a_gate",
            "post_transient_role": "m36_reproduction_and_topology_gate",
        },
        "m36_reference_window_audit": dict(m36_reference_window_audit),
        "nominal_checks": dict(nominal_checks),
        "simulation_checks": list(simulation_checks),
        "groups": {},
        "whitened_jacobians": {},
        "dop853_radau_crosscheck": {},
        "analytic_quotient_transform": {
            "resimulation_performed": False,
            "rank_increase_claim": "forbidden",
        },
        "forward_evaluations": {**cache.counts, "total": cache.total_evaluations},
        "cache_hits": cache.cache_hits,
        "elapsed_seconds": cache.elapsed_seconds,
        "sealed_13v_access": False,
        "fit_executed": False,
        "fit_lock_created": False,
        "pinn_training_performed": False,
        "m38_executed": False,
        "m38_preregistration_eligible_after_human_review": False,
        "next_single_action": "Q2_MANUSCRIPT_EVIDENCE_COMPRESSION",
    }


def _event_audit_row(
    *,
    method: str,
    run_role: str,
    voltage: float,
    signature: Mapping[str, Any],
    checks: Mapping[str, Any],
    coordinate: str | None = None,
    sign: int | None = None,
    relative_step: float | None = None,
    expected_m36_post_count: int | None = None,
) -> dict[str, Any]:
    return {
        "method": method,
        "run_role": run_role,
        "voltage_V": voltage,
        "coordinate": coordinate,
        "sign": sign,
        "relative_step": relative_step,
        "event_window_contract_id": EVENT_WINDOW_CONTRACT_ID,
        "window_start_s": signature["window_start_s"],
        "window_end_s": signature["trace_end_s"],
        "lower_boundary": "inclusive",
        "upper_boundary": "inclusive",
        "full_horizon_event_count": signature["full_horizon_event_count"],
        "post_transient_event_count": signature["post_transient_event_count"],
        "expected_m36_post_transient_event_count": expected_m36_post_count,
        "full_horizon_signature_sha256": signature[
            "full_horizon_signature_sha256"
        ],
        "post_transient_signature_sha256": signature[
            "post_transient_signature_sha256"
        ],
        "reference_post_transient_event_count": checks[
            "reference_post_transient_event_count"
        ],
        "post_transient_event_count_difference": checks[
            "post_transient_event_count_difference"
        ],
        "common_prefix_length": checks["common_prefix_length"],
        "finite_state": checks["finite_state"],
        "activity_class": checks["activity_class"],
        "activity_class_exact": checks["activity_class_exact"],
        "event_topology_compatible": checks["event_topology_compatible"],
        "cross_solver_post_transient_signature_exact": None,
        "full_horizon_is_gate": False,
        "post_transient_is_gate": True,
    }


def run_cross_regime_observability_repair(
    base: VO2ThermalNeuristorParameters,
    observations: Mapping[float, Mapping[str, Any]],
    regimes: Mapping[float, str],
    expected_activity: Mapping[float, str],
    config: Mapping[str, Any],
    m36_config: Mapping[str, Any],
    whitening: Mapping[str, Any],
    m36_expected_event_counts: Mapping[float, int],
    m36_reference_window_audit: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Execute the single preregistered M37R finite-difference vote."""

    steps = [float(value) for value in config["parameters"]["relative_steps"]]
    fine_step = steps[-1]
    gates = config["gates"]
    threshold = float(gates["relative_singular_value_rank_threshold"])
    transient_fraction = float(config["event_window"]["transient_fraction"])
    cache = M37RForwardCache(
        reference_config=m36_config["independent_reference"],
        maximum_evaluations=int(config["solvers"]["maximum_total_forward_evaluations"]),
        maximum_wall_seconds=float(config["budget"]["maximum_incremental_cpu_wall_hours"])
        * 3600.0,
        event_window_contract_id=str(config["event_window"]["contract_id"]),
    )
    event_config = m36_config["event_metrics"]
    nominal: dict[str, dict[float, EventResolvedResult]] = {
        "DOP853": {},
        "Radau": {},
    }
    nominal_signatures: dict[str, dict[float, tuple[str, ...]]] = {
        "DOP853": {},
        "Radau": {},
    }
    nominal_checks: dict[str, Any] = {"DOP853": {}, "Radau": {}}
    event_rows: list[dict[str, Any]] = []
    simulation_checks: list[dict[str, Any]] = []
    gate_results = _gate_template()

    for method in ("DOP853", "Radau"):
        for voltage in (9.0, 11.0, 15.0, 17.0):
            result = cache.simulate(
                base,
                voltage_V=voltage,
                evaluation_times_s=np.asarray(
                    observations[voltage]["time_s"], dtype=np.float64
                ),
                method=method,
            )
            nominal[method][voltage] = result
            preliminary = post_transient_event_signature(
                result.event_records,
                trace_start_s=float(result.trace.time_s[0]),
                trace_end_s=float(result.trace.time_s[-1]),
                transient_fraction=transient_fraction,
            )
            post_signature = tuple(preliminary["post_transient_signature"])
            nominal_signatures[method][voltage] = post_signature
            checks, signature = _result_audit(
                result,
                post_signature,
                expected_activity=expected_activity[voltage],
                event_config=event_config,
                current_noise_A=float(
                    observations[voltage]["current_noise_scale_A"]
                ),
                transient_fraction=transient_fraction,
            )
            expected_post = int(m36_expected_event_counts[voltage])
            checks["m36_post_transient_event_count_reproduced"] = (
                int(signature["post_transient_event_count"]) == expected_post
            )
            expected_record = config["event_window"]["expected_nominal_counts"][
                f"{voltage:g}"
            ]
            checks["full_horizon_matches_registered_diagnostic"] = (
                int(signature["full_horizon_event_count"])
                == int(expected_record["full_horizon"])
            )
            nominal_checks[method][f"{voltage:g}"] = {
                **checks,
                "full_horizon_event_count": int(
                    signature["full_horizon_event_count"]
                ),
                "post_transient_event_count": int(
                    signature["post_transient_event_count"]
                ),
                "expected_m36_post_transient_event_count": expected_post,
                "full_horizon_is_gate": False,
                "post_transient_is_gate": True,
            }
            event_rows.append(
                _event_audit_row(
                    method=method,
                    run_role="nominal",
                    voltage=voltage,
                    signature=signature,
                    checks=checks,
                    expected_m36_post_count=expected_post,
                )
            )

    for voltage in (9.0, 11.0, 15.0, 17.0):
        exact = (
            nominal_signatures["DOP853"][voltage]
            == nominal_signatures["Radau"][voltage]
        )
        nominal_checks["DOP853"][f"{voltage:g}"][
            "radau_post_transient_signature_exact"
        ] = exact
        nominal_checks["Radau"][f"{voltage:g}"][
            "dop853_post_transient_signature_exact"
        ] = exact
        for row in event_rows:
            if row["run_role"] == "nominal" and row["voltage_V"] == voltage:
                row["cross_solver_post_transient_signature_exact"] = exact

    nominal_records = [
        record for method in nominal_checks.values() for record in method.values()
    ]
    gate_results["nominal_window_reproduction"] = bool(
        m36_reference_window_audit["all_counts_match"]
        and all(
            record["m36_post_transient_event_count_reproduced"]
            and (
                record.get("radau_post_transient_signature_exact", True)
                if "radau_post_transient_signature_exact" in record
                else record.get("dop853_post_transient_signature_exact", True)
            )
            for record in nominal_records
        )
    )
    gate_results["all_states_finite"] = all(
        record["finite_state"] for record in nominal_records
    )
    gate_results["all_activity_classes_exact"] = all(
        record["activity_class_exact"] for record in nominal_records
    )
    gate_results["all_post_transient_event_topologies_compatible"] = all(
        record["event_topology_compatible"] for record in nominal_records
    )
    if not (
        gate_results["nominal_window_reproduction"]
        and gate_results["all_states_finite"]
        and gate_results["all_activity_classes_exact"]
        and gate_results["all_post_transient_event_topologies_compatible"]
    ):
        return [], event_rows, _base_result(
            status="stopped_at_nominal_post_transient_event_gate",
            cache=cache,
            nominal_checks=nominal_checks,
            simulation_checks=simulation_checks,
            m36_reference_window_audit=m36_reference_window_audit,
            gate_results=gate_results,
        )

    matrices: dict[tuple[str, float, str], np.ndarray] = {}
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
                    checks, signature = _result_audit(
                        result,
                        nominal_signatures["DOP853"][voltage],
                        expected_activity=expected_activity[voltage],
                        event_config=event_config,
                        current_noise_A=float(
                            observations[voltage]["current_noise_scale_A"]
                        ),
                        transient_fraction=transient_fraction,
                    )
                    record = {
                        "method": "DOP853",
                        "relative_step": step,
                        "coordinate": PARAMETER_NAMES[coordinate_index],
                        "sign": sign,
                        "voltage_V": voltage,
                        "full_horizon_event_count": int(
                            signature["full_horizon_event_count"]
                        ),
                        "post_transient_event_count": int(
                            signature["post_transient_event_count"]
                        ),
                        **checks,
                    }
                    simulation_checks.append(record)
                    event_rows.append(
                        _event_audit_row(
                            method="DOP853",
                            run_role="perturbation",
                            voltage=voltage,
                            signature=signature,
                            checks=checks,
                            coordinate=PARAMETER_NAMES[coordinate_index],
                            sign=sign,
                            relative_step=step,
                        )
                    )
                    if not (
                        checks["finite_state"]
                        and checks["activity_class_exact"]
                        and checks["event_topology_compatible"]
                    ):
                        gate_results["all_states_finite"] = all(
                            row["finite_state"] for row in simulation_checks
                        )
                        gate_results["all_activity_classes_exact"] = all(
                            row["activity_class_exact"] for row in simulation_checks
                        )
                        gate_results[
                            "all_post_transient_event_topologies_compatible"
                        ] = all(
                            row["event_topology_compatible"]
                            for row in simulation_checks
                        )
                        return [], event_rows, _base_result(
                            status="stopped_at_dop853_perturbation_post_transient_event_gate",
                            cache=cache,
                            nominal_checks=nominal_checks,
                            simulation_checks=simulation_checks,
                            m36_reference_window_audit=m36_reference_window_audit,
                            gate_results=gate_results,
                        )
                dop_by_step[step][(coordinate_index, sign)] = results
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
            results: dict[float, EventResolvedResult] = {}
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
                checks, signature = _result_audit(
                    result,
                    nominal_signatures["Radau"][voltage],
                    expected_activity=expected_activity[voltage],
                    event_config=event_config,
                    current_noise_A=float(
                        observations[voltage]["current_noise_scale_A"]
                    ),
                    transient_fraction=transient_fraction,
                )
                record = {
                    "method": "Radau",
                    "relative_step": fine_step,
                    "coordinate": PARAMETER_NAMES[coordinate_index],
                    "sign": sign,
                    "voltage_V": voltage,
                    "full_horizon_event_count": int(
                        signature["full_horizon_event_count"]
                    ),
                    "post_transient_event_count": int(
                        signature["post_transient_event_count"]
                    ),
                    **checks,
                }
                simulation_checks.append(record)
                event_rows.append(
                    _event_audit_row(
                        method="Radau",
                        run_role="perturbation",
                        voltage=voltage,
                        signature=signature,
                        checks=checks,
                        coordinate=PARAMETER_NAMES[coordinate_index],
                        sign=sign,
                        relative_step=fine_step,
                    )
                )
                if not (
                    checks["finite_state"]
                    and checks["activity_class_exact"]
                    and checks["event_topology_compatible"]
                ):
                    gate_results["all_states_finite"] = all(
                        row["finite_state"] for row in simulation_checks
                    )
                    gate_results["all_activity_classes_exact"] = all(
                        row["activity_class_exact"] for row in simulation_checks
                    )
                    gate_results[
                        "all_post_transient_event_topologies_compatible"
                    ] = all(
                        row["event_topology_compatible"] for row in simulation_checks
                    )
                    return [], event_rows, _base_result(
                        status="stopped_at_radau_perturbation_post_transient_event_gate",
                        cache=cache,
                        nominal_checks=nominal_checks,
                        simulation_checks=simulation_checks,
                        m36_reference_window_audit=m36_reference_window_audit,
                        gate_results=gate_results,
                    )
            radau_fine[(coordinate_index, sign)] = results
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

    gate_results["all_states_finite"] = all(
        row["finite_state"] for row in simulation_checks
    )
    gate_results["all_activity_classes_exact"] = all(
        row["activity_class_exact"] for row in simulation_checks
    )
    gate_results["all_post_transient_event_topologies_compatible"] = all(
        row["event_topology_compatible"] for row in simulation_checks
    )

    spectra_rows: list[dict[str, Any]] = []
    geometries: dict[tuple[str, float, str], dict[str, Any]] = {}
    for (method, step, group), matrix in matrices.items():
        geometry = svd_geometry(matrix, relative_threshold=threshold)
        geometries[(method, step, group)] = geometry
        for singular_index, singular_value in enumerate(geometry["singular_values"]):
            spectra_rows.append(
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
        rank = int(fine_geometry["threshold_rank"])
        ranks_match = int(coarse_geometry["threshold_rank"]) == rank
        jacobian_change = float(
            np.linalg.norm(coarse_matrix - fine_matrix)
            / max(np.linalg.norm(fine_matrix), 1.0e-30)
        )
        left_angle = (
            subspace_angle_deg(
                coarse_geometry["u"][:, :rank], fine_geometry["u"][:, :rank]
            )
            if ranks_match and rank > 0
            else float("inf")
        )
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
        retained = max(rank, int(radau_geometry["threshold_rank"]), 1)
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
            "rank_consistent": rank == int(radau_geometry["threshold_rank"]),
        }
        crosscheck[group] = {
            "column_direction_cosines": cosines,
            "minimum_column_direction_cosine": min(cosines),
            "retained_singular_value_relative_difference": singular_difference,
            "dop853_rank": rank,
            "radau_rank": int(radau_geometry["threshold_rank"]),
            "checks": cross_checks,
            "all_crosscheck_gates_pass": bool(all(cross_checks.values())),
        }

    static_direction = geometries[("DOP853", fine_step, "static_only")]["vt"][0]
    oscillatory_direction = geometries[
        ("DOP853", fine_step, "oscillatory_only")
    ]["vt"][0]
    complementary_angle = acute_vector_angle_deg(
        static_direction, oscillatory_direction
    )
    joint = group_results["joint"]

    quotient: dict[str, Any] = {}
    rank_invariant = True
    for group in GROUP_VOLTAGES:
        raw = matrices[("DOP853", fine_step, group)]
        transformed = analytic_quotient_jacobian(raw)
        geometry = svd_geometry(transformed, relative_threshold=threshold)
        raw_algebraic_rank = int(np.linalg.matrix_rank(raw))
        transformed_algebraic_rank = int(np.linalg.matrix_rank(transformed))
        rank_invariant = rank_invariant and (
            raw_algebraic_rank == transformed_algebraic_rank
        )
        quotient[group] = {
            "threshold_rank": int(geometry["threshold_rank"]),
            "raw_threshold_rank": int(group_results[group]["threshold_rank"]),
            "raw_algebraic_rank": raw_algebraic_rank,
            "transformed_algebraic_rank": transformed_algebraic_rank,
            "singular_values": [
                float(value) for value in geometry["singular_values"]
            ],
            "retained_condition_number": float(
                geometry["retained_condition_number"]
            ),
            "algebraic_rank_matches_raw": raw_algebraic_rank
            == transformed_algebraic_rank,
            "threshold_rank_is_coordinate_scale_dependent": True,
        }
        for singular_index, singular_value in enumerate(geometry["singular_values"]):
            spectra_rows.append(
                {
                    "method": "DOP853_analytic_transform",
                    "coordinate_system": "quotient_log_tau_th_log_S_e",
                    "observation_group": group,
                    "relative_step": fine_step,
                    "singular_index": singular_index,
                    "singular_value": float(singular_value),
                    "threshold_rank": int(geometry["threshold_rank"]),
                    "effective_rank": float(geometry["effective_rank"]),
                    "retained_condition_number": float(
                        geometry["retained_condition_number"]
                    ),
                    "top_right_log_C_th": None,
                    "top_right_log_S_e": None,
                }
            )

    gate_results["two_finest_white_jacobian_stability"] = all(
        row["step_checks"]["white_jacobian_stable"]
        and row["step_checks"]["rank_consistent"]
        for row in group_results.values()
    )
    gate_results["two_finest_retained_left_subspace_stability"] = all(
        row["step_checks"]["retained_left_subspace_stable"]
        for row in group_results.values()
    )
    gate_results["dop853_radau_column_direction_consistency"] = all(
        row["checks"]["column_direction_cosines_pass"]
        for row in crosscheck.values()
    )
    gate_results["dop853_radau_retained_singular_value_consistency"] = all(
        row["checks"]["retained_singular_values_pass"]
        for row in crosscheck.values()
    )
    gate_results["dop853_radau_rank_consistency"] = all(
        row["checks"]["rank_consistent"] for row in crosscheck.values()
    )
    gate_results["joint_rank"] = int(joint["threshold_rank"]) == int(
        gates["joint_required_rank"]
    )
    gate_results["joint_condition"] = float(
        joint["retained_condition_number"]
    ) <= float(gates["joint_retained_condition_number_max"])
    gate_results["static_oscillatory_complementarity"] = complementary_angle >= float(
        gates["static_oscillatory_top_right_direction_angle_deg_min"]
    )
    gate_results["analytic_rank_invariance"] = bool(rank_invariant)
    gate_results["forward_budget"] = cache.total_evaluations <= int(
        config["solvers"]["maximum_total_forward_evaluations"]
    )
    gate_results["wall_clock_budget"] = cache.elapsed_seconds <= float(
        config["budget"]["maximum_incremental_cpu_wall_hours"]
    ) * 3600.0
    gate_results["all"] = bool(
        all(value for key, value in gate_results.items() if key != "all")
    )

    jacobians: dict[str, Any] = {"DOP853": {}, "Radau": {}}
    for (method, step, group), matrix in matrices.items():
        step_key = f"{step:.10g}"
        jacobians.setdefault(method, {}).setdefault(step_key, {})[group] = matrix.tolist()

    all_gates = gate_results["all"]
    result = {
        "schema_version": M37R_SCHEMA_VERSION,
        "stage_id": M37R_STAGE_ID,
        "status": "all_m37r_gates_passed"
        if all_gates
        else "m37r_observability_gate_failed",
        "claim_status": "qualified_supported"
        if all_gates
        else "failed_but_informative",
        "m37r_all_gates_pass": all_gates,
        "gate_results": gate_results,
        "event_window_contract": {
            "contract_id": EVENT_WINDOW_CONTRACT_ID,
            "interval": "[t0 + 0.1 * (T - t0), T]",
            "transient_fraction": transient_fraction,
            "lower_boundary": "inclusive",
            "upper_boundary": "inclusive",
            "floating_tolerance_s": 0.0,
            "full_horizon_role": "diagnostic_only_not_a_gate",
            "post_transient_role": "m36_reproduction_and_topology_gate",
        },
        "m36_reference_window_audit": dict(m36_reference_window_audit),
        "nominal_checks": nominal_checks,
        "simulation_checks": simulation_checks,
        "simulation_check_count": len(simulation_checks),
        "groups": group_results,
        "whitened_jacobians": jacobians,
        "dop853_radau_crosscheck": crosscheck,
        "static_oscillatory_top_direction_angle_deg": complementary_angle,
        "analytic_quotient_transform": {
            "raw_to_quotient_matrix": [[1.0, -1.0], [0.0, 1.0]],
            "quotient_to_raw_matrix": [[1.0, 1.0], [0.0, 1.0]],
            "resimulation_performed": False,
            "rank_invariant": rank_invariant,
            "rank_increase_claim": "forbidden",
            "groups": quotient,
        },
        "forward_evaluations": {**cache.counts, "total": cache.total_evaluations},
        "cache_hits": cache.cache_hits,
        "elapsed_seconds": cache.elapsed_seconds,
        "sealed_13v_access": False,
        "fit_executed": False,
        "fit_lock_created": False,
        "pinn_training_performed": False,
        "m38_executed": False,
        "m38_preregistration_eligible_after_human_review": all_gates,
        "next_single_action": "Q2_MANUSCRIPT_EVIDENCE_COMPRESSION",
    }
    return spectra_rows, event_rows, result


def validate_evidence_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Perform a dependency-free structural validation used by mock and tests."""

    required = {
        "schema_version",
        "stage_id",
        "status",
        "claim_status",
        "m37r_all_gates_pass",
        "gate_results",
        "event_window_contract",
        "nominal_checks",
        "simulation_checks",
        "groups",
        "whitened_jacobians",
        "dop853_radau_crosscheck",
        "analytic_quotient_transform",
        "forward_evaluations",
        "cache_hits",
        "elapsed_seconds",
        "sealed_13v_access",
        "fit_executed",
        "fit_lock_created",
        "pinn_training_performed",
        "m38_executed",
    }
    missing = sorted(required - set(payload))
    checks = {
        "required_keys_present": not missing,
        "schema_version_exact": payload.get("schema_version")
        == M37R_SCHEMA_VERSION,
        "stage_id_exact": payload.get("stage_id") == M37R_STAGE_ID,
        "claim_status_allowed": payload.get("claim_status")
        in {"qualified_supported", "failed_but_informative"},
        "event_window_contract_exact": payload.get("event_window_contract", {}).get(
            "contract_id"
        )
        == EVENT_WINDOW_CONTRACT_ID,
        "forbidden_actions_false": all(
            payload.get(key) is False
            for key in (
                "sealed_13v_access",
                "fit_executed",
                "fit_lock_created",
                "pinn_training_performed",
                "m38_executed",
            )
        ),
    }
    return {"checks": checks, "missing_keys": missing, "all_pass": all(checks.values())}


def _mock_result(voltage: float, q0: float, q1: float) -> SimpleNamespace:
    time_s = np.linspace(0.0, 10.0, 1001, dtype=np.float64)
    if voltage in (11.0, 15.0):
        current = (
            2.0
            + 0.02 * voltage
            + (0.35 + 0.08 * q0) * np.sin(2.0 * np.pi * time_s)
            + 0.06 * q1 * np.cos(2.0 * np.pi * time_s)
        )
        device_voltage = (
            3.0
            + 0.01 * voltage
            + 0.15 * np.cos(2.0 * np.pi * time_s)
            + 0.04 * q0
            + 0.07 * q1 * np.sin(2.0 * np.pi * time_s)
        )
        event_times = np.arange(0.5, 10.0 + 0.25, 0.5)
        records = [
            {
                "event_type": "reversal_to_cooling"
                if index % 2 == 0
                else "reversal_to_heating",
                "time_s": float(value),
            }
            for index, value in enumerate(event_times)
        ]
    else:
        current = np.full_like(time_s, 1.0 + 0.01 * voltage + 0.12 * q0)
        device_voltage = np.full_like(time_s, 2.0 + 0.02 * voltage + 0.15 * q1)
        records = []
    trace = SimpleNamespace(
        time_s=time_s,
        current_A=current,
        voltage_V=device_voltage,
        temperature_K=np.full_like(time_s, 325.0),
        resistance_ohm=np.full_like(time_s, 1.0),
    )
    return SimpleNamespace(trace=trace, event_records=tuple(records))


def run_mock_contract_pipeline() -> dict[str, Any]:
    """Exercise crop -> feature -> central Jacobian -> SVD -> schema cheaply."""

    observation_config = {
        "tail_fraction": 0.2,
        "transient_fraction": 0.1,
        "phase_grid_points": 32,
    }
    regimes = {9.0: "static", 11.0: "oscillatory", 15.0: "oscillatory", 17.0: "static"}
    whitening = {"by_voltage": {}}
    for voltage, regime in regimes.items():
        if regime == "static":
            scales = {
                "steady_current_A": 1.0,
                "steady_voltage_V": 1.0,
                "total_charge_C": 1.0,
                "total_energy_J": 1.0,
            }
        else:
            scales = {
                "log_frequency": 1.0,
                "peak_to_trough_current_A": 1.0,
                "duty_cycle": 1.0,
                "cycle_charge_C": 1.0,
                "cycle_energy_J": 1.0,
                "phase_current_A": 1.0,
                "phase_voltage_V": 1.0,
            }
        whitening["by_voltage"][f"{voltage:g}"] = {"feature_scales": scales}
    h = 0.01
    matrices: dict[str, np.ndarray] = {}
    boundary_result = _mock_result(11.0, 0.0, 0.0)
    boundary_audit = post_transient_event_signature(
        boundary_result.event_records,
        trace_start_s=0.0,
        trace_end_s=10.0,
        transient_fraction=0.1,
    )
    for group in GROUP_VOLTAGES:
        columns: list[np.ndarray] = []
        for coordinate in range(2):
            plus_q = [0.0, 0.0]
            minus_q = [0.0, 0.0]
            plus_q[coordinate] = h
            minus_q[coordinate] = -h
            plus = {
                voltage: _mock_result(voltage, plus_q[0], plus_q[1])
                for voltage in regimes
            }
            minus = {
                voltage: _mock_result(voltage, minus_q[0], minus_q[1])
                for voltage in regimes
            }
            plus_features = group_feature_vector(
                plus,
                group=group,
                regimes=regimes,
                whitening=whitening,
                observation_config=observation_config,
            )
            minus_features = group_feature_vector(
                minus,
                group=group,
                regimes=regimes,
                whitening=whitening,
                observation_config=observation_config,
            )
            columns.append((plus_features - minus_features) / (2.0 * h))
        matrices[group] = np.column_stack(columns)
    geometries = {
        group: svd_geometry(matrix, relative_threshold=0.05)
        for group, matrix in matrices.items()
    }
    payload = {
        "schema_version": M37R_SCHEMA_VERSION,
        "stage_id": M37R_STAGE_ID,
        "status": "mock_contract_only",
        "claim_status": "failed_but_informative",
        "m37r_all_gates_pass": False,
        "gate_results": _gate_template(),
        "event_window_contract": {
            "contract_id": EVENT_WINDOW_CONTRACT_ID,
            "transient_fraction": 0.1,
            "lower_boundary": "inclusive",
            "upper_boundary": "inclusive",
        },
        "nominal_checks": {},
        "simulation_checks": [],
        "groups": {
            group: {
                "matrix_shape": list(matrices[group].shape),
                "threshold_rank": int(geometries[group]["threshold_rank"]),
                "singular_values": [
                    float(value) for value in geometries[group]["singular_values"]
                ],
            }
            for group in GROUP_VOLTAGES
        },
        "whitened_jacobians": {
            group: matrices[group].tolist() for group in GROUP_VOLTAGES
        },
        "dop853_radau_crosscheck": {},
        "analytic_quotient_transform": {
            "resimulation_performed": False,
            "rank_increase_claim": "forbidden",
        },
        "forward_evaluations": {"DOP853": 0, "Radau": 0, "total": 0},
        "cache_hits": 0,
        "elapsed_seconds": 0.0,
        "sealed_13v_access": False,
        "fit_executed": False,
        "fit_lock_created": False,
        "pinn_training_performed": False,
        "m38_executed": False,
    }
    schema_validation = validate_evidence_contract(payload)
    checks = {
        "boundary_event_included": 1.0
        in boundary_audit["post_transient_event_times_s"],
        "terminal_event_included": 10.0
        in boundary_audit["post_transient_event_times_s"],
        "all_feature_matrices_finite": all(
            np.isfinite(matrix).all() for matrix in matrices.values()
        ),
        "all_feature_matrices_have_two_columns": all(
            matrix.shape[1] == 2 for matrix in matrices.values()
        ),
        "joint_mock_rank_two": int(geometries["joint"]["threshold_rank"]) == 2,
        "schema_contract_passes": schema_validation["all_pass"],
    }
    return {
        "pipeline": "synthetic_mock_no_scientific_vote",
        "checks": checks,
        "all_pass": all(checks.values()),
        "schema_validation": schema_validation,
        "group_shapes": {
            group: list(matrix.shape) for group, matrix in matrices.items()
        },
        "group_threshold_ranks": {
            group: int(geometries[group]["threshold_rank"])
            for group in GROUP_VOLTAGES
        },
        "boundary_post_transient_event_count": int(
            boundary_audit["post_transient_event_count"]
        ),
    }
