"""Solution-level B3v2 qualification and single-GT routing.

The adaptive accepted-path reversal list is preserved as supplemental
telemetry.  Voting comparisons use common physical output times and the
passively reconstructed full fields on those times.
"""

from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter, process_time
from typing import Any, Iterable, Mapping

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_controller_relevance_b3 import (
    _B3StreamingRecorder,
    _load_state,
    _pin_process_to_one_cpu,
    _trajectory_nrmse,
    _window_integrity,
    _window_sample_times,
)
from pinnpcm.evaluation.geophase_controller_relevance_final_rescue import (
    _atomic_bytes,
    _atomic_json,
    _canonical_bytes,
    _payload_sha256,
    _sha256,
    _state_payload,
    _to_builtin,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_exact_condensed_anderson_controller_v2 import (
    simulate_exact_condensed_anderson_protocol_v2,
)
from pinnpcm.solvers.geophase_nls_v1 import simulate_s2_protocol_nls_v1
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import protocol_voltage_scale
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    initial_s2_state,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import (
    _ControllerV2AttemptAccumulator,
)


SCHEMA_VERSION = "geophase_b3v2_solution_level_v1"
WORKER_SCHEMA_VERSION = "geophase_b3v2_solution_worker_v1"
FINITE_REJECTION_PENALTY = 1.0e300
IMPLEMENTATION_FILES = (
    "configs/geophase_b3v2_solution_level.yaml",
    "src/pinnpcm/evaluation/geophase_b3v2_solution_level.py",
    "scripts/run_geophase_b3v2_solution_level.py",
)


def load_contract(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected B3v2 solution-level contract")
    return payload


def verify_frozen_inputs(contract: Mapping[str, Any]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in contract["frozen_inputs"]:
        relative = Path(str(item["path"]))
        observed = _sha256(ROOT / relative)
        expected = str(item["sha256"])
        if observed != expected:
            raise ValueError(f"frozen B3v2 input drifted: {relative}")
        verified.append({"path": relative.as_posix(), "sha256": observed})
    return verified


def _implementation_hashes() -> dict[str, str]:
    return {path: _sha256(ROOT / path) for path in IMPLEMENTATION_FILES}


def _worker_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        environment[name] = "1"
    return environment


def _thread_environment(values: Mapping[str, str] | None = None) -> dict[str, str | None]:
    source = os.environ if values is None else values
    return {
        name: source.get(name)
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        )
    }


def _atomic_npz(path: Path, **arrays: np.ndarray) -> str:
    buffer = BytesIO()
    np.savez_compressed(buffer, **arrays)
    _atomic_bytes(path, buffer.getvalue())
    return _sha256(path)


def _published_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _trajectory_signature(payload: Mapping[str, Any]) -> str:
    diagnostics = {
        key: value
        for key, value in dict(payload["diagnostics"]).items()
        if "wall_time" not in key and "cpu_time" not in key
    }
    return _payload_sha256(
        {
            "final_state": payload["final_state"],
            "diagnostics": diagnostics,
            "accepted_path_step_count": payload["accepted_path_step_count"],
            "scalar_records": payload["scalar_records"],
            "event_records": payload["event_records"],
            "reversal_records": payload["reversal_records"],
        }
    )


def _run_solution_window(
    spec: Mapping[str, Any], scientific: dict[str, Any], field_path: Path | None
) -> dict[str, Any]:
    level = int(spec["spatial_level"])
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    fields.validate_grid(grid)
    if spec.get("initial_state_mode") == "equilibrium":
        initial = initial_s2_state(grid, closure, fields, scientific)
    else:
        initial = _load_state(spec["initial_state"])
        if np.asarray(initial.temperature_K).shape != grid.shape:
            raise ValueError("B3v2 initial state does not match its spatial grid")
    protocol_id = str(spec["protocol_id"])
    protocol = scientific["formal_protocols"]["protocols"][protocol_id]
    stop = float(spec["final_time_s"])
    sample_times = _window_sample_times(
        float(initial.time_s), stop, float(spec["sample_interval_s"])
    )
    capture = bool(spec.get("capture_full_fields", False))
    recorder = _B3StreamingRecorder(
        case_id=str(spec["case_id"]),
        grid=grid,
        fields=fields,
        protocol=protocol,
        config=scientific,
        sample_times_s=sample_times,
        fixed_snapshot_times_s=tuple(float(value) for value in sample_times) if capture else (),
        initial_state=initial,
        voltage_scale_V=protocol_voltage_scale(scientific, protocol_id),
        closure=closure,
    )
    attempts = _ControllerV2AttemptAccumulator()

    def accepted(previous: S2State, step: Any, H: float, voltage: float, wall: float) -> None:
        recorder.record_accepted_interval(
            previous,
            step,
            H,
            voltage,
            wall,
            coupled_solve_count=attempts.consume(step),
        )

    common = {
        "protocol": protocol,
        "protocol_id": protocol_id,
        "grid": grid,
        "closure": closure,
        "fields": fields,
        "config": scientific,
        "time_divisor": int(spec["time_divisor"]),
        "final_time_s": stop,
        "maximum_wall_clock_s": float(spec["maximum_wall_clock_s"]),
        "retain_full_history": False,
        "accepted_step_callback": accepted,
        "attempted_candidate_callback": attempts,
        "cache": build_s2_solver_cache(grid, fields),
    }
    started_wall = perf_counter()
    started_cpu = process_time()
    solver = str(spec["solver"])
    if solver == "nls_v1":
        result = simulate_s2_protocol_nls_v1(
            initial,
            case_id=str(spec["case_id"]),
            use_equivalent_optimizations=True,
            use_unit_voltage_scaling=True,
            **common,
        )
    elif solver == "anderson_v1":
        result = simulate_exact_condensed_anderson_protocol_v2(initial, **common)
    else:
        raise ValueError(f"unsupported B3v2 solver: {solver}")
    wall_time = perf_counter() - started_wall
    cpu_time = process_time() - started_cpu
    records = list(recorder.scalar_records)
    record_times = np.asarray([float(row["time_s"]) for row in records], dtype=float)
    output_complete = bool(
        len(records) == len(sample_times)
        and recorder._sample_index == len(sample_times)
        and np.all(np.diff(record_times) > 0.0)
        and np.allclose(record_times, sample_times, rtol=0.0, atol=1.0e-17)
    )
    integrity = _window_integrity(records, bool(result.completed))
    diagnostics = asdict(result.diagnostics)
    payload: dict[str, Any] = {
        "schema_version": WORKER_SCHEMA_VERSION,
        "case_id": str(spec["case_id"]),
        "role": str(spec["role"]),
        "solver": solver,
        "protocol_id": protocol_id,
        "spatial_level": level,
        "time_divisor": int(spec["time_divisor"]),
        "initial_time_s": float(initial.time_s),
        "final_time_s": stop,
        "completed": bool(result.completed),
        "stop_reason": str(result.stop_reason),
        "achieved_final_time_s": float(result.achieved_final_time_s),
        "output_complete": output_complete,
        "integrity_pass": integrity,
        "local_pass": bool(result.completed and output_complete and integrity),
        "wall_time_s": float(wall_time),
        "cpu_time_s": float(cpu_time),
        "diagnostics": diagnostics,
        "scalar_records": records,
        "event_records": list(recorder.event_records),
        "reversal_records": list(recorder.reversal_records),
        "raw_reversal_role": "supplemental_nonvoting_adaptive_path_telemetry",
        "sample_count": len(records),
        "accepted_path_step_count": int(diagnostics.get("accepted_steps", 0)),
        "final_state": _state_payload(recorder.final_state),
        "field_capture_enabled": capture,
        "field_artifact": None,
    }
    if capture:
        snapshots = list(recorder.fixed_snapshots)
        if len(snapshots) != len(sample_times):
            raise RuntimeError("passive full-field recorder missed a fixed output")
        if field_path is None:
            raise ValueError("field capture requires an NPZ output path")
        arrays = {
            "times_s": np.asarray([item.time_s for item in snapshots], dtype=float),
            "temperature_K": np.stack([item.temperature_K for item in snapshots]),
            "conductive_state": np.stack([item.conductive_state for item in snapshots]),
            "branch_memory": np.stack([item.branch_memory for item in snapshots]),
            "cell_area_m2": np.asarray([grid.cell_area_m2], dtype=float),
            "active_vo2_mask": np.ones(grid.shape, dtype=np.uint8),
        }
        sha = _atomic_npz(field_path, **arrays)
        payload["field_artifact"] = {
            "path": _published_path(field_path),
            "sha256": sha,
            "shape": list(arrays["temperature_K"].shape),
            "lossless": True,
        }
    payload["trajectory_signature_sha256"] = _trajectory_signature(payload)
    return payload


def run_worker(
    *, spec_path: Path, output_path: Path, field_path: Path | None = None
) -> dict[str, Any]:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    affinity = _pin_process_to_one_cpu()
    started_wall = perf_counter()
    started_cpu = process_time()
    try:
        payload = _run_solution_window(spec, resolved_s2_config(), field_path)
        payload.update(validity="valid", error_class=None, error_message=None)
    except Exception as error:
        payload = {
            "schema_version": WORKER_SCHEMA_VERSION,
            "case_id": str(spec.get("case_id", "unknown")),
            "role": str(spec.get("role", "unknown")),
            "solver": str(spec.get("solver", "unknown")),
            "validity": "invalid",
            "local_pass": False,
            "error_class": type(error).__name__,
            "error_message": str(error),
            "wall_time_s": float(perf_counter() - started_wall),
            "cpu_time_s": float(process_time() - started_cpu),
        }
    payload["affinity"] = affinity
    payload["thread_environment"] = _thread_environment()
    _atomic_json(output_path, payload)
    return payload


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    flat = np.asarray(values, dtype=float).reshape(-1)
    weight = np.asarray(weights, dtype=float).reshape(-1)
    if flat.shape != weight.shape or not np.isfinite(flat).all():
        return FINITE_REJECTION_PENALTY
    if not np.isfinite(weight).all() or np.any(weight < 0.0) or np.sum(weight) <= 0.0:
        return FINITE_REJECTION_PENALTY
    order = np.argsort(flat, kind="mergesort")
    ordered_values = flat[order]
    cumulative = np.cumsum(weight[order])
    target = min(max(float(q), 0.0), 1.0) * cumulative[-1]
    index = min(int(np.searchsorted(cumulative, target, side="left")), len(flat) - 1)
    return float(ordered_values[index])


def field_error_metrics(
    reference: np.ndarray, candidate: np.ndarray, cell_weights: np.ndarray
) -> dict[str, float]:
    ref = np.asarray(reference, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    weights = np.asarray(cell_weights, dtype=float)
    if ref.shape != cand.shape or ref.ndim != 3 or weights.shape != ref.shape[1:]:
        return {name: FINITE_REJECTION_PENALTY for name in ("rmse", "p95", "terminal_p95", "maximum")}
    if not np.isfinite(ref).all() or not np.isfinite(cand).all():
        return {name: FINITE_REJECTION_PENALTY for name in ("rmse", "p95", "terminal_p95", "maximum")}
    errors = np.abs(cand - ref)
    repeated = np.broadcast_to(weights, errors.shape)
    denominator = float(np.sum(repeated))
    rmse = math.sqrt(float(np.sum(repeated * errors**2)) / denominator)
    return {
        "rmse": float(rmse),
        "p95": _weighted_quantile(errors, repeated, 0.95),
        "terminal_p95": _weighted_quantile(errors[-1], weights, 0.95),
        "maximum": float(np.max(errors)),
    }


def _weighted_mean_trajectory(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    weight = np.asarray(weights, dtype=float)
    if array.ndim != 3 or weight.shape != array.shape[1:]:
        raise ValueError("field and area weights have incompatible shapes")
    denominator = float(np.sum(weight))
    if denominator <= 0.0 or not np.isfinite(array).all():
        raise ValueError("field trajectory or weights are invalid")
    return np.sum(array * weight[None, :, :], axis=(1, 2)) / denominator


def _total_variation(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.isfinite(array).all():
        return FINITE_REJECTION_PENALTY
    return float(np.sum(np.abs(np.diff(array))))


def _macro_events(times: np.ndarray, signal: np.ndarray, threshold: float) -> list[dict[str, Any]]:
    values = np.asarray(signal, dtype=float)
    grid = np.asarray(times, dtype=float)
    if values.shape != grid.shape or not np.isfinite(values).all() or not np.isfinite(grid).all():
        raise ValueError("macro-event signal is invalid")
    events: list[dict[str, Any]] = []
    for index in range(1, len(values)):
        direction: str | None = None
        if values[index - 1] < threshold <= values[index]:
            direction = "upward"
        elif values[index - 1] > threshold >= values[index]:
            direction = "downward"
        if direction is None:
            continue
        denominator = values[index] - values[index - 1]
        if denominator == 0.0:
            continue
        fraction = (threshold - values[index - 1]) / denominator
        events.append(
            {
                "direction": direction,
                "crossing_time_s": float(grid[index - 1] + fraction * (grid[index] - grid[index - 1])),
            }
        )
    return events


def _event_comparison(candidate: list[dict[str, Any]], reference: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_directions = [str(item["direction"]) for item in candidate]
    reference_directions = [str(item["direction"]) for item in reference]
    if candidate_directions != reference_directions:
        return {"sequence_equal": False, "maximum_absolute_error_s": FINITE_REJECTION_PENALTY, "maximum_relative_error": FINITE_REJECTION_PENALTY}
    absolute: list[float] = []
    relative: list[float] = []
    for observed, expected in zip(candidate, reference, strict=True):
        error = abs(float(observed["crossing_time_s"]) - float(expected["crossing_time_s"]))
        absolute.append(error)
        relative.append(error / max(abs(float(expected["crossing_time_s"])), 5.0e-9))
    return {"sequence_equal": True, "maximum_absolute_error_s": max(absolute, default=0.0), "maximum_relative_error": max(relative, default=0.0)}


def _closed_loop_area(x: np.ndarray, y: np.ndarray) -> float:
    left = np.asarray(x, dtype=float)
    right = np.asarray(y, dtype=float)
    if left.shape != right.shape or left.ndim != 1 or left.size < 3:
        return FINITE_REJECTION_PENALTY
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        return FINITE_REJECTION_PENALTY
    return float(0.5 * abs(np.dot(left, np.roll(right, -1)) - np.dot(right, np.roll(left, -1))))


def _normalize(values: np.ndarray, minimum: float, maximum: float) -> np.ndarray:
    span = float(maximum - minimum)
    if not np.isfinite(span) or span <= 0.0:
        raise ValueError("reference normalization span must be positive")
    return (np.asarray(values, dtype=float) - minimum) / span


def _load_fields(worker: Mapping[str, Any]) -> dict[str, np.ndarray]:
    artifact = worker.get("field_artifact")
    if not isinstance(artifact, Mapping):
        raise ValueError("solution worker is missing its field artifact")
    path = ROOT / str(artifact["path"])
    if _sha256(path) != str(artifact["sha256"]):
        raise ValueError("solution field artifact hash mismatch")
    with np.load(path, allow_pickle=False) as bundle:
        return {name: np.asarray(bundle[name]) for name in bundle.files}


def compare_solution_runs(
    reference: Mapping[str, Any], candidate: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    ref_fields = _load_fields(reference)
    cand_fields = _load_fields(candidate)
    ref_times = np.asarray(ref_fields["times_s"], dtype=float)
    cand_times = np.asarray(cand_fields["times_s"], dtype=float)
    tolerance = max(1.0e-18, float(np.max(np.abs(ref_times), initial=0.0)) * 1.0e-12)
    time_grid_equal = bool(ref_times.shape == cand_times.shape and np.allclose(ref_times, cand_times, rtol=0.0, atol=tolerance))
    if not time_grid_equal:
        return {"passed": False, "time_grid_equal": False, "failure": "COMMON_PHYSICAL_TIME_GRID_MISMATCH"}
    cell_area = float(np.asarray(ref_fields["cell_area_m2"]).reshape(-1)[0])
    full_weights = np.full(ref_fields["temperature_K"].shape[1:], cell_area, dtype=float)
    active_mask = np.asarray(ref_fields["active_vo2_mask"], dtype=bool)
    active_weights = np.where(active_mask, cell_area, 0.0)
    field_names = ("temperature_K", "conductive_state", "branch_memory")
    metrics: dict[str, dict[str, float]] = {}
    means: dict[str, dict[str, list[float]]] = {}
    tv: dict[str, dict[str, float]] = {}
    for name in field_names:
        weights = full_weights if name == "temperature_K" else active_weights
        metrics[name] = field_error_metrics(ref_fields[name], cand_fields[name], weights)
        ref_mean = _weighted_mean_trajectory(ref_fields[name], weights)
        cand_mean = _weighted_mean_trajectory(cand_fields[name], weights)
        means[name] = {"reference": ref_mean.tolist(), "candidate": cand_mean.tolist()}
        tv[name] = {"reference": _total_variation(ref_mean), "candidate": _total_variation(cand_mean)}
    ref_records = list(reference["scalar_records"])
    cand_records = list(candidate["scalar_records"])
    current = _trajectory_nrmse(
        np.asarray([row["terminal_current_A"] for row in cand_records]),
        np.asarray([row["terminal_current_A"] for row in ref_records]),
        1.0e-12,
    )
    voltage = _trajectory_nrmse(
        np.asarray([row["device_voltage_V"] for row in cand_records]),
        np.asarray([row["device_voltage_V"] for row in ref_records]),
        1.0e-12,
    )
    threshold = float(contract["solution_gates"]["quiescent_mean_s_threshold"])
    ref_events = _macro_events(ref_times, np.asarray(means["conductive_state"]["reference"]), threshold)
    cand_events = _macro_events(ref_times, np.asarray(means["conductive_state"]["candidate"]), threshold)
    event = _event_comparison(cand_events, ref_events)
    current_values = np.asarray([row["terminal_current_A"] for row in ref_records], dtype=float)
    voltage_values = np.asarray([row["device_voltage_V"] for row in ref_records], dtype=float)
    ref_s = np.asarray(means["conductive_state"]["reference"])
    ref_t = np.asarray(means["temperature_K"]["reference"])
    cand_current = np.asarray([row["terminal_current_A"] for row in cand_records], dtype=float)
    cand_voltage = np.asarray([row["device_voltage_V"] for row in cand_records], dtype=float)
    cand_s = np.asarray(means["conductive_state"]["candidate"])
    cand_t = np.asarray(means["temperature_K"]["candidate"])
    ranges = {
        "current": [float(np.min(current_values)), float(np.max(current_values))],
        "voltage": [float(np.min(voltage_values)), float(np.max(voltage_values))],
        "s": [float(np.min(ref_s)), float(np.max(ref_s))],
        "temperature": [float(np.min(ref_t)), float(np.max(ref_t))],
    }
    loops: dict[str, Any]
    try:
        loops = {
            "reference_ranges": ranges,
            "reference_I_Vd": _closed_loop_area(_normalize(voltage_values, *ranges["voltage"]), _normalize(current_values, *ranges["current"])),
            "candidate_I_Vd": _closed_loop_area(_normalize(cand_voltage, *ranges["voltage"]), _normalize(cand_current, *ranges["current"])),
            "reference_s_T": _closed_loop_area(_normalize(ref_t, *ranges["temperature"]), _normalize(ref_s, *ranges["s"])),
            "candidate_s_T": _closed_loop_area(_normalize(cand_t, *ranges["temperature"]), _normalize(cand_s, *ranges["s"])),
        }
    except ValueError as error:
        loops = {"failure": str(error)}
    return {
        "passed": True,
        "time_grid_equal": True,
        "maximum_time_grid_difference_s": float(np.max(np.abs(ref_times - cand_times), initial=0.0)),
        "fields": metrics,
        "mean_trajectories": means,
        "total_variation": tv,
        "terminal_current_nrmse": current,
        "device_voltage_nrmse": voltage,
        "macro_events": {"reference": ref_events, "candidate": cand_events, "comparison": event},
        "loops": loops,
        "reference_local_pass": bool(reference.get("local_pass")),
        "candidate_local_pass": bool(candidate.get("local_pass")),
        "raw_reversal_voting": False,
    }


def _field_gate_pass(comparison: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    for field, limits in contract["field_gates"].items():
        observed = comparison["fields"][field]
        for metric in ("rmse", "p95", "terminal_p95"):
            if float(observed[metric]) > float(limits[metric]):
                return False
    return True


def _event_gate_pass(comparison: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    observed = comparison["macro_events"]["comparison"]
    gates = contract["solution_gates"]
    return bool(
        observed["sequence_equal"]
        and float(observed["maximum_absolute_error_s"])
        <= float(gates["event_absolute_error_s_max"])
        and float(observed["maximum_relative_error"])
        <= float(gates["event_relative_error_max"])
    )


def assess_reference_refinement(
    comparisons: Mapping[str, Mapping[str, Any]], contract: Mapping[str, Any]
) -> dict[str, Any]:
    gates = contract["solution_gates"]
    regime_results: dict[str, Any] = {}
    passed = True
    for regime, comparison in comparisons.items():
        local = bool(
            comparison.get("passed")
            and comparison.get("reference_local_pass")
            and comparison.get("candidate_local_pass")
        )
        field_pass = _field_gate_pass(comparison, contract)
        port_pass = bool(
            float(comparison["terminal_current_nrmse"])
            <= float(gates["terminal_current_nrmse_max"])
            and float(comparison["device_voltage_nrmse"])
            <= float(gates["device_voltage_nrmse_max"])
        )
        event_gate_applicable = regime != "quiescent_9V"
        event_pass = (
            _event_gate_pass(comparison, contract) if event_gate_applicable else True
        )
        regime_pass = bool(local and field_pass and port_pass and event_pass)
        regime_results[regime] = {
            "passed": regime_pass,
            "local_integrity_pass": local,
            "field_pass": field_pass,
            "port_pass": port_pass,
            "event_pass": event_pass,
            "event_gate_applicable": event_gate_applicable,
            "macro_crossing_counts": {
                "reference": len(comparison["macro_events"]["reference"]),
                "candidate": len(comparison["macro_events"]["candidate"]),
            },
            "comparison": comparison,
        }
        passed = passed and regime_pass
    return {"passed": bool(passed), "regimes": regime_results}


def _relative_difference(value: float, reference: float, floor: float = 1.0e-15) -> float:
    return abs(float(value) - float(reference)) / max(abs(float(reference)), float(floor))


def _reference_envelope(
    assessment: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    multiplier = float(contract["solution_gates"]["anderson_envelope_multiplier"])
    regimes: dict[str, Any] = {}
    for regime, result in assessment["regimes"].items():
        comparison = result["comparison"]
        thresholds: dict[str, dict[str, float]] = {}
        for field, floors in contract["field_gates"].items():
            thresholds[field] = {
                metric: max(float(floors[metric]), multiplier * float(comparison["fields"][field][metric]))
                for metric in ("rmse", "p95", "terminal_p95")
            }
        tv_envelope = {
            field: max(
                float(contract["field_gates"][field]["tv_floor"]),
                multiplier
                * abs(
                    float(comparison["total_variation"][field]["candidate"])
                    - float(comparison["total_variation"][field]["reference"])
                ),
            )
            for field in contract["field_gates"]
        }
        loops = comparison["loops"]
        if "failure" in loops:
            loop_errors = {"I_Vd": FINITE_REJECTION_PENALTY, "s_T": FINITE_REJECTION_PENALTY}
        else:
            loop_errors = {
                "I_Vd": _relative_difference(loops["candidate_I_Vd"], loops["reference_I_Vd"]),
                "s_T": _relative_difference(loops["candidate_s_T"], loops["reference_s_T"]),
            }
        loop_thresholds = {
            key: max(float(contract["solution_gates"]["loop_relative_floor"]), multiplier * value)
            for key, value in loop_errors.items()
        }
        regimes[regime] = {
            "field_thresholds": thresholds,
            "tv_excess_thresholds": tv_envelope,
            "loop_refinement_relative_errors": loop_errors,
            "loop_relative_thresholds": loop_thresholds,
            "nls_refinement": comparison,
        }
    return {"schema_version": "geophase_b3v2_reference_envelope_v1", "passed": bool(assessment["passed"]), "regimes": regimes}


def assess_anderson(
    *,
    self_comparisons: Mapping[str, Mapping[str, Any]],
    cross_comparisons: Mapping[str, Mapping[str, Any]],
    envelope: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    gates = contract["solution_gates"]
    results: dict[str, Any] = {}
    all_pass = True
    for regime in ("quiescent_9V", "transition_12p5V"):
        self_comparison = self_comparisons[regime]
        cross = cross_comparisons[regime]
        limits = envelope["regimes"][regime]
        field_checks: dict[str, Any] = {}
        field_pass = True
        for field in contract["field_gates"]:
            checks: dict[str, bool] = {}
            for metric in ("rmse", "p95", "terminal_p95"):
                threshold = float(limits["field_thresholds"][field][metric])
                checks[f"self_{metric}"] = float(self_comparison["fields"][field][metric]) <= threshold
                checks[f"cross_{metric}"] = float(cross["fields"][field][metric]) <= threshold
            field_checks[field] = checks
            field_pass = field_pass and all(checks.values())
        local_pass = bool(
            self_comparison.get("reference_local_pass")
            and self_comparison.get("candidate_local_pass")
            and cross.get("reference_local_pass")
            and cross.get("candidate_local_pass")
        )
        port_pass = all(
            float(item[metric]) <= float(gates[limit])
            for item in (self_comparison, cross)
            for metric, limit in (
                ("terminal_current_nrmse", "terminal_current_nrmse_max"),
                ("device_voltage_nrmse", "device_voltage_nrmse_max"),
            )
        )
        tv_checks: dict[str, bool] = {}
        event_pass = True
        loop_pass = True
        loop_errors: dict[str, float] = {}
        if regime == "quiescent_9V":
            expected = int(gates["quiescent_crossing_count"])
            event_pass = all(
                len(item["macro_events"][side]) == expected
                for item in (self_comparison, cross)
                for side in ("reference", "candidate")
            )
            for field in contract["field_gates"]:
                reference_tv = float(cross["total_variation"][field]["reference"])
                excess = max(
                    0.0,
                    float(self_comparison["total_variation"][field]["reference"]) - reference_tv,
                    float(self_comparison["total_variation"][field]["candidate"]) - reference_tv,
                    float(cross["total_variation"][field]["candidate"]) - reference_tv,
                )
                tv_checks[field] = excess <= float(limits["tv_excess_thresholds"][field])
        else:
            event_pass = _event_gate_pass(self_comparison, contract) and _event_gate_pass(cross, contract)
            for key, candidate_key, reference_key in (
                ("I_Vd", "candidate_I_Vd", "reference_I_Vd"),
                ("s_T", "candidate_s_T", "reference_s_T"),
            ):
                loop_errors[f"self_{key}"] = _relative_difference(
                    self_comparison["loops"]["candidate_" + key],
                    self_comparison["loops"]["reference_" + key],
                )
                loop_errors[f"cross_{key}"] = _relative_difference(
                    cross["loops"][candidate_key], cross["loops"][reference_key]
                )
                threshold = float(limits["loop_relative_thresholds"][key])
                loop_pass = loop_pass and loop_errors[f"self_{key}"] <= threshold and loop_errors[f"cross_{key}"] <= threshold
        regime_pass = bool(
            self_comparison.get("passed")
            and cross.get("passed")
            and local_pass
            and field_pass
            and port_pass
            and event_pass
            and loop_pass
            and all(tv_checks.values())
        )
        results[regime] = {
            "passed": regime_pass,
            "local_integrity_pass": local_pass,
            "field_checks": field_checks,
            "port_pass": port_pass,
            "event_pass": event_pass,
            "tv_checks": tv_checks,
            "loop_pass": loop_pass,
            "loop_relative_errors": loop_errors,
            "self_refinement": self_comparison,
            "cross_solver_t2": cross,
        }
        all_pass = all_pass and regime_pass
    return {
        "passed": bool(all_pass),
        "claim_status": "qualified_supported" if all_pass else "failed_but_informative",
        "speed_acceleration_claim": "eligible_for_cost_gate" if all_pass else "forbidden",
        "route": "ANDERSON_HELDOUT_AND_COST" if all_pass else "NLS_ONLY_HELDOUT_AND_COST",
        "regimes": results,
    }


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    records = [_to_builtin(dict(row)) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        _atomic_bytes(path, b"\n")
        return
    fieldnames = sorted({key for row in records for key in row})
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in records:
        writer.writerow(
            {
                key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            }
        )
    _atomic_bytes(path, buffer.getvalue().encode("utf-8"))


def _invoke_worker(
    *,
    spec: Mapping[str, Any],
    output_path: Path,
    field_path: Path | None,
    config_path: Path,
    timeout_s: float,
) -> dict[str, Any]:
    spec_path = output_path.with_suffix(".spec.json")
    _atomic_json(spec_path, dict(spec))
    command = [
        str(ROOT / ".venv/Scripts/python.exe"),
        str(ROOT / "scripts/run_geophase_b3v2_solution_level.py"),
        "--stage",
        "worker",
        "--config",
        str(config_path),
        "--output-root",
        str(ROOT / str(load_contract(config_path)["outputs"]["namespace"])),
        "--worker-spec",
        str(spec_path),
        "--worker-output",
        str(output_path),
    ]
    if field_path is not None:
        command.extend(("--field-output", str(field_path)))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=_worker_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=float(timeout_s),
        check=False,
    )
    if not output_path.exists():
        return {
            "schema_version": WORKER_SCHEMA_VERSION,
            "case_id": str(spec["case_id"]),
            "validity": "invalid",
            "local_pass": False,
            "error_class": "WorkerDidNotPublish",
            "error_message": completed.stderr[-4000:],
            "cpu_time_s": 0.0,
            "wall_time_s": float(timeout_s),
        }
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    payload["worker_command"] = command
    payload["worker_returncode"] = int(completed.returncode)
    payload["worker_stdout"] = completed.stdout[-4000:]
    payload["worker_stderr"] = completed.stderr[-4000:]
    _atomic_json(output_path, payload)
    return payload


def _base_output_root(contract: Mapping[str, Any]) -> Path:
    return ROOT / str(contract["outputs"]["namespace"])


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _state_from_path(path: Path) -> dict[str, Any]:
    return _load_json(path)


def _development_specs(contract: Mapping[str, Any], solver: str) -> list[tuple[str, dict[str, Any]]]:
    specs: list[tuple[str, dict[str, Any]]] = []
    for regime in ("quiescent_9V", "transition_12p5V"):
        definition = contract["development"]["regimes"][regime]
        initial = _state_from_path(ROOT / str(definition["initial_state"]))
        start = float(initial["time_s"])
        stop = (
            start + float(definition["relative_window_s"])
            if "relative_window_s" in definition
            else float(definition["frozen_window_stop_s"])
        )
        if "frozen_window_start_s" in definition and abs(start - float(definition["frozen_window_start_s"])) > 1.0e-15:
            raise ValueError("frozen transition development window start drifted")
        for divisor in definition["time_divisors"]:
            label = f"{regime}_{solver}_T{int(divisor)}"
            specs.append(
                (
                    label,
                    {
                        "case_id": f"B3V2-DEV-{regime.upper()}-{solver.upper()}-T{int(divisor)}",
                        "role": "development",
                        "solver": solver,
                        "protocol_id": str(definition["protocol_id"]),
                        "spatial_level": int(definition["spatial_level"]),
                        "time_divisor": int(divisor),
                        "initial_state": initial,
                        "final_time_s": stop,
                        "sample_interval_s": float(contract["recording"]["sample_interval_s"]),
                        "capture_full_fields": True,
                        "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_time_s_max"]),
                    },
                )
            )
    return specs


def _run_specs(
    *,
    specs: list[tuple[str, dict[str, Any]]],
    directory: Path,
    config_path: Path,
    contract: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], float, float]:
    directory.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    aggregate_cpu = 0.0
    started = perf_counter()
    for label, spec in specs:
        if aggregate_cpu >= float(contract["runtime"]["aggregate_cpu_time_s_max"]):
            raise RuntimeError("B3v2 aggregate CPU timebox exhausted")
        output = directory / f"{label}.json"
        field = directory / f"{label}.fields.npz" if spec.get("capture_full_fields") else None
        result = _invoke_worker(
            spec=spec,
            output_path=output,
            field_path=field,
            config_path=config_path,
            timeout_s=float(contract["runtime"]["worker_wall_time_s_max"]) + 60.0,
        )
        results[label] = result
        aggregate_cpu += float(result.get("cpu_time_s", 0.0))
        if result.get("validity") != "valid" or not result.get("local_pass", False):
            break
    return results, aggregate_cpu, perf_counter() - started


def _pair_comparisons(
    workers: Mapping[str, Mapping[str, Any]], solver: str, contract: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    return {
        regime: compare_solution_runs(
            workers[f"{regime}_{solver}_T1"],
            workers[f"{regime}_{solver}_T2"],
            contract,
        )
        for regime in ("quiescent_9V", "transition_12p5V")
    }


def _metrics_rows(kind: str, comparisons: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for regime, comparison in comparisons.items():
        for field, metrics in comparison.get("fields", {}).items():
            rows.append({"comparison": kind, "regime": regime, "field": field, **metrics})
    return rows


def run_development_nls(config_path: Path, output_root: Path) -> dict[str, Any]:
    contract = load_contract(config_path)
    verified = verify_frozen_inputs(contract)
    expected = _base_output_root(contract).resolve()
    output_root = Path(output_root).resolve()
    if output_root != expected:
        raise ValueError(f"B3v2 output root must be {expected}")
    development = output_root / str(contract["outputs"]["development_directory"])
    workers_root = development / "workers"
    specs = _development_specs(contract, "nls_v1")
    workers, aggregate_cpu, wall = _run_specs(
        specs=specs,
        directory=workers_root,
        config_path=config_path,
        contract=contract,
    )
    expected_labels = {label for label, _ in specs}
    execution_complete = set(workers) == expected_labels and all(
        item.get("validity") == "valid" and item.get("local_pass") for item in workers.values()
    )
    comparisons = _pair_comparisons(workers, "nls_v1", contract) if execution_complete else {}
    assessment = assess_reference_refinement(comparisons, contract) if execution_complete else {"passed": False, "regimes": {}}
    envelope = _reference_envelope(assessment, contract) if execution_complete else {"schema_version": "geophase_b3v2_reference_envelope_v1", "passed": False, "regimes": {}}
    envelope.update(
        {
            "task_id": contract["task_id"],
            "run_id": contract["identity"]["run_id"],
            "implementation_hashes": _implementation_hashes(),
            "frozen_input_hashes": verified,
            "raw_reversal_voting": False,
            "created_before_anderson_development": True,
        }
    )
    envelope_path = development / "reference_envelope.json"
    _atomic_json(envelope_path, envelope)
    envelope_hash = _sha256(envelope_path)
    _atomic_bytes(development / "reference_envelope.sha256", (envelope_hash + "\n").encode("ascii"))
    metrics_path = development / "nls_refinement_metrics.csv"
    _write_csv(metrics_path, _metrics_rows("nls_self_refinement", comparisons))
    if not execution_complete:
        disposition = "INVALID_NLS_DEVELOPMENT_EXECUTION"
        validity = "invalid"
        claim_status = "forbidden"
    elif not assessment["passed"]:
        disposition = str(contract["routes"]["reference_not_refined"])
        validity = "valid"
        claim_status = "failed_but_informative"
    else:
        disposition = "NLS_REFERENCE_ENVELOPE_FROZEN"
        validity = "valid"
        claim_status = "qualified_supported"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "stage": "development_nls",
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["run_id"],
        "validity": validity,
        "disposition": disposition,
        "route": "ANDERSON_DEVELOPMENT" if disposition == "NLS_REFERENCE_ENVELOPE_FROZEN" else "STOP",
        "lifecycle_state": "numerically_validated" if validity == "valid" else "executed",
        "claim_status": claim_status,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "execution_complete": execution_complete,
        "assessment": assessment,
        "worker_paths": {label: (workers_root / f"{label}.json").relative_to(ROOT).as_posix() for label in workers},
        "reference_envelope": envelope_path.relative_to(ROOT).as_posix(),
        "reference_envelope_sha256": envelope_hash,
        "metrics_csv": metrics_path.relative_to(ROOT).as_posix(),
        "aggregate_cpu_time_s": aggregate_cpu,
        "wall_time_s": wall,
        "verified_frozen_inputs": verified,
        "implementation_hashes": _implementation_hashes(),
        "evidence_type": contract["evidence_type"],
    }
    _atomic_json(development / "nls_development_summary.json", summary)
    return summary


def recompute_development_nls_evidence(
    config_path: Path, output_root: Path
) -> dict[str, Any]:
    """Repair only the NLS aggregation contract without rerunning a solver.

    The B3v2 contract applies event gates to the transition reference pair, not
    to the quiescent NLS self-refinement pair.  This routine preserves the
    original aggregate artifacts, reloads the immutable worker payloads, and
    republishes the corrected aggregate evidence.  Raw trajectories and field
    arrays are never modified.
    """

    contract = load_contract(config_path)
    verified = verify_frozen_inputs(contract)
    expected = _base_output_root(contract).resolve()
    output_root = Path(output_root).resolve()
    if output_root != expected:
        raise ValueError(f"B3v2 output root must be {expected}")
    development = output_root / str(contract["outputs"]["development_directory"])
    summary_path = development / "nls_development_summary.json"
    original_summary = _load_json(summary_path)
    if original_summary.get("stage") != "development_nls":
        raise ValueError("missing completed NLS development aggregate")

    preserved_root = development / "pre_contract_repair"
    preserved: dict[str, dict[str, str]] = {}
    for name in (
        "nls_development_summary.json",
        "nls_refinement_metrics.csv",
        "reference_envelope.json",
        "reference_envelope.sha256",
    ):
        source = development / name
        target = preserved_root / name
        if not target.exists():
            _atomic_bytes(target, source.read_bytes())
        preserved[name] = {
            "path": target.relative_to(ROOT).as_posix(),
            "sha256": _sha256(target),
        }

    workers_root = development / "workers"
    specs = _development_specs(contract, "nls_v1")
    workers = {
        label: _load_json(workers_root / f"{label}.json") for label, _ in specs
    }
    execution_complete = all(
        item.get("validity") == "valid" and item.get("local_pass")
        for item in workers.values()
    )
    if not execution_complete:
        raise ValueError("cannot repair an incomplete NLS development aggregate")

    comparisons = _pair_comparisons(workers, "nls_v1", contract)
    assessment = assess_reference_refinement(comparisons, contract)
    envelope = _reference_envelope(assessment, contract)
    execution_implementation_hashes = original_summary["implementation_hashes"]
    aggregation_implementation_hashes = _implementation_hashes()
    repair = {
        "kind": "aggregation_contract_repair_only",
        "reason": "quiescent_9V_macro_crossing_is_not_an_nls_reference_self_refinement_gate",
        "solver_rerun": False,
        "worker_or_field_artifacts_modified": False,
        "terminal_disposition_changed": False,
        "preserved_pre_repair_artifacts": preserved,
    }
    envelope.update(
        {
            "task_id": contract["task_id"],
            "run_id": contract["identity"]["run_id"],
            "implementation_hashes": execution_implementation_hashes,
            "aggregation_implementation_hashes": aggregation_implementation_hashes,
            "frozen_input_hashes": verified,
            "raw_reversal_voting": False,
            "created_before_anderson_development": True,
            "contract_repair": repair,
        }
    )
    envelope_path = development / "reference_envelope.json"
    _atomic_json(envelope_path, envelope)
    envelope_hash = _sha256(envelope_path)
    _atomic_bytes(
        development / "reference_envelope.sha256",
        (envelope_hash + "\n").encode("ascii"),
    )
    metrics_path = development / "nls_refinement_metrics.csv"
    _write_csv(metrics_path, _metrics_rows("nls_self_refinement", comparisons))

    disposition = (
        "NLS_REFERENCE_ENVELOPE_FROZEN"
        if assessment["passed"]
        else str(contract["routes"]["reference_not_refined"])
    )
    summary = dict(original_summary)
    summary.update(
        {
            "validity": "valid",
            "disposition": disposition,
            "route": (
                "ANDERSON_DEVELOPMENT"
                if disposition == "NLS_REFERENCE_ENVELOPE_FROZEN"
                else "STOP"
            ),
            "lifecycle_state": "numerically_validated",
            "claim_status": (
                "qualified_supported"
                if assessment["passed"]
                else "failed_but_informative"
            ),
            "assessment": assessment,
            "reference_envelope_sha256": envelope_hash,
            "verified_frozen_inputs": verified,
            "implementation_hashes": execution_implementation_hashes,
            "aggregation_implementation_hashes": aggregation_implementation_hashes,
            "contract_repair": repair,
        }
    )
    _atomic_json(summary_path, summary)
    return summary


def _verify_reference_anchor(contract: Mapping[str, Any], development: Path) -> tuple[dict[str, Any], str]:
    envelope_path = development / "reference_envelope.json"
    expected_hash = (development / "reference_envelope.sha256").read_text(encoding="ascii").strip()
    observed_hash = _sha256(envelope_path)
    if observed_hash != expected_hash:
        raise ValueError("reference envelope hash drifted")
    envelope = _load_json(envelope_path)
    if not envelope.get("passed"):
        raise ValueError("reference envelope did not pass")
    if envelope.get("implementation_hashes") != _implementation_hashes():
        raise ValueError("B3v2 implementation changed after reference-envelope freeze")
    return envelope, observed_hash


def run_development_anderson(config_path: Path, output_root: Path) -> dict[str, Any]:
    contract = load_contract(config_path)
    verify_frozen_inputs(contract)
    output_root = Path(output_root).resolve()
    development = output_root / str(contract["outputs"]["development_directory"])
    envelope, envelope_hash = _verify_reference_anchor(contract, development)
    nls_summary = _load_json(development / "nls_development_summary.json")
    if nls_summary.get("disposition") != "NLS_REFERENCE_ENVELOPE_FROZEN":
        raise ValueError("Anderson development requires a valid frozen NLS envelope")
    workers_root = development / "workers"
    specs = _development_specs(contract, "anderson_v1")
    workers, aggregate_cpu, wall = _run_specs(
        specs=specs,
        directory=workers_root,
        config_path=config_path,
        contract=contract,
    )
    expected_labels = {label for label, _ in specs}
    execution_complete = set(workers) == expected_labels and all(
        item.get("validity") == "valid" and item.get("local_pass") for item in workers.values()
    )
    nls_workers = {
        label: _load_json(workers_root / f"{label}.json")
        for label, _ in _development_specs(contract, "nls_v1")
    }
    if execution_complete:
        self_comparisons = _pair_comparisons(workers, "anderson_v1", contract)
        cross_comparisons = {
            regime: compare_solution_runs(
                nls_workers[f"{regime}_nls_v1_T2"],
                workers[f"{regime}_anderson_v1_T2"],
                contract,
            )
            for regime in ("quiescent_9V", "transition_12p5V")
        }
        assessment = assess_anderson(
            self_comparisons=self_comparisons,
            cross_comparisons=cross_comparisons,
            envelope=envelope,
            contract=contract,
        )
    else:
        self_comparisons = {}
        cross_comparisons = {}
        assessment = {"passed": False, "claim_status": "forbidden", "route": "NLS_ONLY_HELDOUT_AND_COST", "regimes": {}}
    rows = _metrics_rows("anderson_self_refinement", self_comparisons)
    rows.extend(_metrics_rows("anderson_t2_vs_nls_t2", cross_comparisons))
    metrics_path = development / "anderson_solution_metrics.csv"
    _write_csv(metrics_path, rows)
    if not execution_complete:
        disposition = "INVALID_ANDERSON_DEVELOPMENT_EXECUTION"
        validity = "invalid"
    elif assessment["passed"]:
        disposition = "ANDERSON_DEVELOPMENT_SOLUTION_LEVEL_PASS"
        validity = "valid"
    else:
        disposition = "ANDERSON_DEVELOPMENT_SOLUTION_LEVEL_VALID_FAIL"
        validity = "valid"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "stage": "development_anderson",
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["run_id"],
        "validity": validity,
        "disposition": disposition,
        "route": assessment["route"],
        "lifecycle_state": "numerically_validated" if validity == "valid" else "executed",
        "claim_status": assessment["claim_status"],
        "scientific_vote": False,
        "formal_execution_count": 0,
        "assessment": assessment,
        "reference_envelope_sha256": envelope_hash,
        "worker_paths": {label: (workers_root / f"{label}.json").relative_to(ROOT).as_posix() for label in workers},
        "metrics_csv": metrics_path.relative_to(ROOT).as_posix(),
        "aggregate_cpu_time_s": aggregate_cpu,
        "wall_time_s": wall,
        "raw_reversal_voting": False,
        "evidence_type": contract["evidence_type"],
    }
    _atomic_json(development / "anderson_development_summary.json", summary)
    return summary


def _heldout_specs(
    contract: Mapping[str, Any], solver: str, development: Path
) -> list[tuple[str, dict[str, Any]]]:
    workers = development / "workers"
    specs: list[tuple[str, dict[str, Any]]] = []
    for regime in ("quiescent_9V", "transition_12p5V"):
        nls_t2 = _load_json(workers / f"{regime}_nls_v1_T2.json")
        initial = dict(nls_t2["final_state"])
        definition = contract["heldout"]["regimes"][regime]
        stop = float(initial["time_s"]) + float(definition["relative_window_s"])
        for divisor in definition["time_divisors"]:
            label = f"{regime}_{solver}_T{int(divisor)}"
            specs.append(
                (
                    label,
                    {
                        "case_id": f"B3V2-HELDOUT-{regime.upper()}-{solver.upper()}-T{int(divisor)}",
                        "role": "heldout",
                        "solver": solver,
                        "protocol_id": str(definition["protocol_id"]),
                        "spatial_level": int(definition["spatial_level"]),
                        "time_divisor": int(divisor),
                        "initial_state": initial,
                        "final_time_s": stop,
                        "sample_interval_s": float(contract["recording"]["sample_interval_s"]),
                        "capture_full_fields": True,
                        "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_time_s_max"]),
                    },
                )
            )
    return specs


def _complete_up_down(events: list[dict[str, Any]]) -> bool:
    directions = [str(item["direction"]) for item in events]
    return any(
        directions[index] == "upward" and "downward" in directions[index + 1 :]
        for index in range(len(directions))
    )


def run_heldout(config_path: Path, output_root: Path) -> dict[str, Any]:
    contract = load_contract(config_path)
    verify_frozen_inputs(contract)
    output_root = Path(output_root).resolve()
    development = output_root / str(contract["outputs"]["development_directory"])
    heldout = output_root / str(contract["outputs"]["heldout_directory"])
    envelope, envelope_hash = _verify_reference_anchor(contract, development)
    aa_development = _load_json(development / "anderson_development_summary.json")
    unlock_marker = heldout / "heldout_unlock.json"
    if unlock_marker.exists():
        raise ValueError("the one-shot held-out has already been unlocked")
    _atomic_json(
        unlock_marker,
        {
            "unlock_count": 1,
            "reference_envelope_sha256": envelope_hash,
            "implementation_hashes": _implementation_hashes(),
            "metric_contract_sha256": _sha256(config_path),
        },
    )
    workers_root = heldout / "workers"
    nls_specs = _heldout_specs(contract, "nls_v1", development)
    nls_workers, nls_cpu, nls_wall = _run_specs(
        specs=nls_specs,
        directory=workers_root,
        config_path=config_path,
        contract=contract,
    )
    nls_complete = len(nls_workers) == 4 and all(
        item.get("validity") == "valid" and item.get("local_pass") for item in nls_workers.values()
    )
    nls_comparisons = _pair_comparisons(nls_workers, "nls_v1", contract) if nls_complete else {}
    nls_assessment = assess_reference_refinement(nls_comparisons, contract) if nls_complete else {"passed": False, "regimes": {}}
    coverage = False
    if nls_complete:
        transition_t2 = nls_workers["transition_12p5V_nls_v1_T2"]
        fields = _load_fields(transition_t2)
        weights = np.ones(fields["conductive_state"].shape[1:], dtype=float)
        mean_s = _weighted_mean_trajectory(fields["conductive_state"], weights)
        events = _macro_events(
            fields["times_s"], mean_s, float(contract["solution_gates"]["quiescent_mean_s_threshold"])
        )
        coverage = _complete_up_down(events)
    aa_allowed = bool(aa_development.get("assessment", {}).get("passed", False))
    aa_workers: dict[str, dict[str, Any]] = {}
    aa_assessment: dict[str, Any] = {"passed": False, "route": "NLS_ONLY_HELDOUT_AND_COST", "regimes": {}}
    aa_cpu = aa_wall = 0.0
    if nls_assessment["passed"] and coverage and aa_allowed:
        aa_specs = _heldout_specs(contract, "anderson_v1", development)
        aa_workers, aa_cpu, aa_wall = _run_specs(
            specs=aa_specs,
            directory=workers_root,
            config_path=config_path,
            contract=contract,
        )
        aa_complete = len(aa_workers) == 4 and all(
            item.get("validity") == "valid" and item.get("local_pass") for item in aa_workers.values()
        )
        if aa_complete:
            self_comparisons = _pair_comparisons(aa_workers, "anderson_v1", contract)
            cross_comparisons = {
                regime: compare_solution_runs(
                    nls_workers[f"{regime}_nls_v1_T2"],
                    aa_workers[f"{regime}_anderson_v1_T2"],
                    contract,
                )
                for regime in ("quiescent_9V", "transition_12p5V")
            }
            heldout_envelope = _reference_envelope(nls_assessment, contract)
            aa_assessment = assess_anderson(
                self_comparisons=self_comparisons,
                cross_comparisons=cross_comparisons,
                envelope=heldout_envelope,
                contract=contract,
            )
        else:
            self_comparisons = cross_comparisons = {}
    else:
        self_comparisons = cross_comparisons = {}
    rows = _metrics_rows("heldout_nls_self_refinement", nls_comparisons)
    rows.extend(_metrics_rows("heldout_anderson_self_refinement", self_comparisons))
    rows.extend(_metrics_rows("heldout_anderson_t2_vs_nls_t2", cross_comparisons))
    metrics_path = heldout / "heldout_solution_metrics.csv"
    _write_csv(metrics_path, rows)
    if not nls_complete:
        disposition, validity, route = "INVALID_HELDOUT_EXECUTION", "invalid", "STOP"
    elif not coverage:
        disposition, validity, route = str(contract["routes"]["heldout_noninformative"]), "invalid", "STOP"
    elif not nls_assessment["passed"]:
        disposition, validity, route = str(contract["routes"]["stop"]), "valid", "STOP"
    elif aa_allowed and aa_assessment["passed"]:
        disposition, validity, route = "HELDOUT_NLS_AND_ANDERSON_PASS", "valid", "B4A_NLS_AND_ANDERSON"
    else:
        disposition, validity, route = "HELDOUT_NLS_PASS_ANDERSON_NOT_ELIGIBLE", "valid", "B4A_NLS_ONLY"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "stage": "heldout",
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["run_id"],
        "validity": validity,
        "disposition": disposition,
        "route": route,
        "lifecycle_state": "numerically_validated" if validity == "valid" else "executed",
        "claim_status": "qualified_supported" if validity == "valid" and nls_assessment["passed"] else "forbidden" if validity == "invalid" else "failed_but_informative",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "reference_coverage_up_down_pair": coverage,
        "nls_assessment": nls_assessment,
        "anderson_development_eligible": aa_allowed,
        "anderson_assessment": aa_assessment,
        "aggregate_cpu_time_s": nls_cpu + aa_cpu,
        "wall_time_s": nls_wall + aa_wall,
        "metrics_csv": metrics_path.relative_to(ROOT).as_posix(),
        "reference_envelope_sha256": envelope_hash,
        "evidence_type": contract["evidence_type"],
    }
    _atomic_json(heldout / "heldout_summary.json", summary)
    return summary


def _profile_specs(
    contract: Mapping[str, Any], solver: str, repetition: int
) -> list[tuple[str, dict[str, Any]]]:
    b4a = contract["b4a"]
    specs: list[tuple[str, dict[str, Any]]] = []
    for level in b4a["spatial_levels"]:
        for protocol_id in b4a["protocols"]:
            label = f"{solver}_{protocol_id}_L{int(level)}_R{repetition}"
            specs.append(
                (
                    label,
                    {
                        "case_id": f"B3V2-B4A-{solver.upper()}-{str(protocol_id).upper()}-L{int(level)}-R{repetition}",
                        "role": "b4a_profile",
                        "solver": solver,
                        "protocol_id": str(protocol_id),
                        "spatial_level": int(level),
                        "time_divisor": int(b4a["time_divisor"]),
                        "initial_state_mode": "equilibrium",
                        "final_time_s": float(b4a["physical_duration_s"]),
                        "sample_interval_s": float(b4a["physical_duration_s"]),
                        "capture_full_fields": False,
                        "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_time_s_max"]),
                    },
                )
            )
    return specs


def _lpt_makespan(costs: Iterable[float], worker_count: int) -> float:
    loads = [0.0] * int(worker_count)
    for cost in sorted((float(value) for value in costs), reverse=True):
        index = min(range(len(loads)), key=loads.__getitem__)
        loads[index] += cost
    return max(loads, default=0.0)


def _cost_projection(
    medians: Mapping[str, Mapping[str, Mapping[str, float]]],
    solver: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    b4a = contract["b4a"]
    factor = float(b4a["projection_safety_factor"])
    scale = float(b4a["single_trajectory_horizon_s"]) / float(b4a["physical_duration_s"])

    def projected(level: int, protocol: str, clock: str) -> float:
        return factor * scale * float(medians[solver][f"L{level}"][protocol][clock])

    protocols = [str(item) for item in b4a["protocols"]]
    q, t = protocols
    single_wall = {
        f"{protocol}_L{level}": projected(int(level), protocol, "wall_time_s")
        for level in b4a["spatial_levels"]
        for protocol in protocols
    }
    single_cpu = {
        f"{protocol}_L{level}": projected(int(level), protocol, "cpu_time_s")
        for level in b4a["spatial_levels"]
        for protocol in protocols
    }
    single_pass = all(
        value <= float(b4a["single_trajectory_wall_s_max"])
        for value in single_wall.values()
    )
    b4b_cpu = 2.0 * (single_cpu[f"{q}_L1"] + single_cpu[f"{t}_L1"])
    worst_by_level = {
        level: max(single_cpu[f"{q}_L{level}"], single_cpu[f"{t}_L{level}"])
        for level in (1, 2, 4)
    }
    s0_unit_costs: list[float] = []
    # REF: six protocols, one L1, one L2 and three L4 grid/time combinations.
    for protocol_index in range(6):
        selected = q if protocol_index == 1 else t if protocol_index == 3 else None
        costs = (
            {
                level: single_cpu[f"{selected}_L{level}"]
                for level in (1, 2, 4)
            }
            if selected is not None
            else worst_by_level
        )
        s0_unit_costs.extend((costs[1], costs[2], costs[4], costs[4], costs[4]))
    # Six non-reused topology trajectories are S4T4; four DUAL0 units run two L1 paths.
    s0_unit_costs.extend([worst_by_level[4]] * 6)
    s0_unit_costs.extend([2.0 * worst_by_level[1]] * 4)
    # One zero-drive LIM trajectory plus nineteen analytic/fail-closed fixed-cost units.
    s0_unit_costs.append(worst_by_level[1])
    fixed_cost = factor * max(
        value[clock]
        for level in medians[solver].values()
        for value in level.values()
        for clock in ("cpu_time_s",)
    )
    s0_unit_costs.extend([fixed_cost] * 19)
    if len(s0_unit_costs) != 60:
        raise RuntimeError("fresh-S0 projection did not preserve 60 execution units")
    s0_cpu = float(sum(s0_unit_costs))
    s0_calendar = _lpt_makespan(s0_unit_costs, int(b4a["fresh_s0_worker_count"]))
    phase2_cpu = float(b4a["phase2_projection_trajectory_equivalents"]) * worst_by_level[4]
    gates = {
        "single_trajectory": single_pass,
        "b4b_aggregate_cpu": b4b_cpu <= float(b4a["b4b_aggregate_cpu_s_max"]),
        "fresh_s0_aggregate_cpu": s0_cpu <= float(b4a["fresh_s0_aggregate_cpu_s_max"]),
        "fresh_s0_calendar": s0_calendar <= float(b4a["fresh_s0_calendar_s_max"]),
        "phase2_aggregate_cpu": phase2_cpu <= float(b4a["phase2_aggregate_cpu_s_max"]),
    }
    return {
        "single_20us_wall_s": single_wall,
        "single_20us_cpu_s": single_cpu,
        "b4b_aggregate_cpu_s": b4b_cpu,
        "fresh_s0_aggregate_cpu_s": s0_cpu,
        "fresh_s0_four_worker_calendar_s": s0_calendar,
        "phase2_minimal_aggregate_cpu_s": phase2_cpu,
        "phase2_projection_trajectory_equivalents": int(b4a["phase2_projection_trajectory_equivalents"]),
        "gates": gates,
        "passed": all(gates.values()),
        "projection_semantics": "strict_div4_20ns_linear_rate_with_1p10_safety; non-profiled protocols use worst same-level rate",
    }


def run_b4a(config_path: Path, output_root: Path) -> dict[str, Any]:
    contract = load_contract(config_path)
    verify_frozen_inputs(contract)
    output_root = Path(output_root).resolve()
    heldout_root = output_root / str(contract["outputs"]["heldout_directory"])
    heldout = _load_json(heldout_root / "heldout_summary.json")
    if heldout.get("validity") != "valid" or not heldout.get("nls_assessment", {}).get("passed"):
        raise ValueError("B4a requires a valid held-out NLS route")
    solvers = ["nls_v1"]
    if heldout.get("anderson_assessment", {}).get("passed"):
        solvers.append("anderson_v1")
    b4a_root = output_root / str(contract["outputs"]["b4a_directory"])
    workers_root = b4a_root / "workers"
    workers_root.mkdir(parents=True, exist_ok=True)
    repetitions = int(contract["b4a"]["alternating_repetitions"])
    rows: list[dict[str, Any]] = []
    aggregate_cpu = 0.0
    started = perf_counter()
    invalid = False
    for repetition in range(1, repetitions + 1):
        order = list(solvers if repetition % 2 else reversed(solvers))
        for solver in order:
            for label, spec in _profile_specs(contract, solver, repetition):
                result = _invoke_worker(
                    spec=spec,
                    output_path=workers_root / f"{label}.json",
                    field_path=None,
                    config_path=config_path,
                    timeout_s=float(contract["runtime"]["worker_wall_time_s_max"]) + 60.0,
                )
                aggregate_cpu += float(result.get("cpu_time_s", 0.0))
                local_pass = bool(result.get("validity") == "valid" and result.get("local_pass"))
                invalid = invalid or not local_pass
                rows.append(
                    {
                        "solver": solver,
                        "repetition": repetition,
                        "protocol_id": spec["protocol_id"],
                        "spatial_level": spec["spatial_level"],
                        "wall_time_s": float(result.get("wall_time_s", FINITE_REJECTION_PENALTY)),
                        "cpu_time_s": float(result.get("cpu_time_s", FINITE_REJECTION_PENALTY)),
                        "peak_rss_bytes": result.get("peak_rss_bytes"),
                        "local_pass": local_pass,
                    }
                )
                if invalid:
                    break
            if invalid:
                break
        if invalid:
            break
    timing_path = b4a_root / "b4a_timings.csv"
    _write_csv(timing_path, rows)
    medians: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    projections: dict[str, Any] = {}
    if not invalid:
        for solver in solvers:
            medians[solver] = {}
            for level in contract["b4a"]["spatial_levels"]:
                medians[solver][f"L{int(level)}"] = {}
                for protocol in contract["b4a"]["protocols"]:
                    subset = [
                        row
                        for row in rows
                        if row["solver"] == solver
                        and int(row["spatial_level"]) == int(level)
                        and row["protocol_id"] == protocol
                        and row["local_pass"]
                    ]
                    if len(subset) != repetitions:
                        invalid = True
                        break
                    medians[solver][f"L{int(level)}"][str(protocol)] = {
                        "wall_time_s": statistics.median(row["wall_time_s"] for row in subset),
                        "cpu_time_s": statistics.median(row["cpu_time_s"] for row in subset),
                    }
        if not invalid:
            projections = {
                solver: _cost_projection(medians, solver, contract) for solver in solvers
            }
    selected: str | None = None
    if not invalid and projections["nls_v1"]["passed"]:
        if "anderson_v1" in projections and projections["anderson_v1"]["passed"]:
            nls_cost = float(projections["nls_v1"]["fresh_s0_aggregate_cpu_s"])
            aa_cost = float(projections["anderson_v1"]["fresh_s0_aggregate_cpu_s"])
            reduction = 1.0 - aa_cost / nls_cost
            if reduction >= float(contract["b4a"]["anderson_minimum_cost_reduction_fraction"]):
                selected = "anderson_v1"
        if selected is None:
            selected = "nls_v1"
    if invalid:
        disposition, validity = "INVALID_B4A_EXECUTION", "invalid"
    elif selected == "anderson_v1":
        disposition, validity = str(contract["routes"]["anderson_selected"]), "valid"
    elif selected == "nls_v1":
        disposition, validity = str(contract["routes"]["nls_selected"]), "valid"
    else:
        disposition, validity = str(contract["routes"]["stop"]), "valid"
    selected_id = {
        "anderson_v1": "exact_condensed_temperature_safeguarded_anderson_v1",
        "nls_v1": "full_state_nls_v1_dual_gate",
    }.get(selected)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "stage": "b4a",
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["run_id"],
        "validity": validity,
        "disposition": disposition,
        "route": disposition,
        "selected_gt_solver": selected_id,
        "lifecycle_state": "numerically_validated" if validity == "valid" else "executed",
        "claim_status": "qualified_supported" if selected_id else "failed_but_informative" if validity == "valid" else "forbidden",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "eligible_solvers": solvers,
        "median_profiles": medians,
        "cost_projections": projections,
        "aggregate_cpu_time_s": aggregate_cpu,
        "wall_time_s": perf_counter() - started,
        "timing_csv": timing_path.relative_to(ROOT).as_posix(),
        "evidence_type": contract["evidence_type"],
    }
    _atomic_json(b4a_root / "b4a_summary.json", summary)
    return summary


__all__ = [
    "SCHEMA_VERSION",
    "WORKER_SCHEMA_VERSION",
    "assess_anderson",
    "assess_reference_refinement",
    "compare_solution_runs",
    "field_error_metrics",
    "load_contract",
    "run_b4a",
    "run_development_anderson",
    "run_development_nls",
    "run_heldout",
    "run_worker",
]
