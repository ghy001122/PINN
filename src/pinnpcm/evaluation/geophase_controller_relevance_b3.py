"""B3 matched-window qualification for the sole controller-admissible solver.

This module compares the safeguarded exact-condensed solver with the frozen
NLS-v1 reference on identical states, protocols, controller settings, and
physical output grids.  The comparison is qualification evidence only; it is
not an oracle or truth claim.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter, process_time
from typing import Any, Mapping

import numpy as np

from pinnpcm.evaluation.geophase_controller_relevance_final_rescue import (
    _atomic_bytes,
    _atomic_json,
    _sha256,
    _state_payload,
    _to_builtin,
    _git_value,
    load_contract,
    validate_thread_environment,
    verify_frozen_inputs,
)
from pinnpcm.evaluation.geophase_exact_condensed_b2 import _hardest_state
from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
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
from pinnpcm.solvers.geophase_phase1_v2_streaming_v3 import (
    _ControllerV3StreamingRecorder,
    _interpolate_state,
)


SCHEMA_VERSION = "geophase_controller_relevance_b3_v1"
WORKER_SCHEMA_VERSION = "geophase_controller_relevance_b3_worker_v1"
CONTROLLER_ID = "embedded_time_consistency_v2_only"
FINITE_REJECTION_PENALTY = 1.0e300


class _B3StreamingRecorder(_ControllerV3StreamingRecorder):
    """Reuse production dense output while preserving controller-v2 identity."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.scalar_records[0]["time_controller"] = CONTROLLER_ID
        self.scalar_records[0]["qualification_stage"] = "B3"

    def _update_controller_telemetry(self, **kwargs: Any) -> None:
        super()._update_controller_telemetry(**kwargs)
        self.scalar_records[-1]["time_controller"] = CONTROLLER_ID
        self.scalar_records[-1]["qualification_stage"] = "B3"


def _window_sample_times(start_s: float, stop_s: float, interval_s: float) -> np.ndarray:
    start = float(start_s)
    stop = float(stop_s)
    interval = float(interval_s)
    if not (np.isfinite(start) and np.isfinite(stop) and np.isfinite(interval)):
        raise ValueError("B3 sample-grid inputs must be finite")
    if stop <= start or interval <= 0.0:
        raise ValueError("B3 sample window and interval must be positive")
    count = int(math.floor((stop - start) / interval + 1.0e-12))
    values = start + interval * np.arange(count + 1, dtype=float)
    tolerance = max(1.0e-18, abs(stop) * 1.0e-13)
    values = values[values <= stop + tolerance]
    if values.size == 0 or abs(values[0] - start) > tolerance:
        raise RuntimeError("B3 sample grid lost its initial time")
    if abs(values[-1] - stop) <= tolerance:
        values[-1] = stop
    else:
        values = np.concatenate((values, np.asarray([stop], dtype=float)))
    if np.any(np.diff(values) <= 0.0):
        raise RuntimeError("B3 sample grid is not strictly increasing")
    return values


def _load_state(payload: Mapping[str, Any]) -> S2State:
    return _state_from_replay(dict(payload))


def _pin_process_to_one_cpu() -> dict[str, Any]:
    """Pin the worker to the lowest CPU already allowed by the host."""

    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessAffinityMask.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel32.GetProcessAffinityMask.restype = ctypes.c_int
        kernel32.SetProcessAffinityMask.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        kernel32.SetProcessAffinityMask.restype = ctypes.c_int
        process = kernel32.GetCurrentProcess()
        process_mask = ctypes.c_size_t()
        system_mask = ctypes.c_size_t()
        if not kernel32.GetProcessAffinityMask(
            process, ctypes.byref(process_mask), ctypes.byref(system_mask)
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessAffinityMask failed")
        allowed = int(process_mask.value)
        chosen = allowed & -allowed
        if chosen == 0 or not kernel32.SetProcessAffinityMask(process, chosen):
            raise OSError(ctypes.get_last_error(), "SetProcessAffinityMask failed")
        return {
            "platform": "windows",
            "allowed_mask_before": allowed,
            "chosen_mask": chosen,
            "chosen_cpu_index": chosen.bit_length() - 1,
        }
    allowed = sorted(os.sched_getaffinity(0))
    if not allowed:
        raise RuntimeError("worker has no allowed CPU affinity")
    os.sched_setaffinity(0, {allowed[0]})
    return {
        "platform": "posix",
        "allowed_cpus_before": allowed,
        "chosen_cpu_index": allowed[0],
    }


def _finite_records(records: list[dict[str, Any]]) -> bool:
    keys = (
        "time_s",
        "device_voltage_V",
        "terminal_current_A",
        "terminal_device_power_W",
        "maximum_temperature_K",
        "minimum_temperature_K",
        "mean_temperature_K",
        "mean_conductive_state",
        "mean_branch_memory",
    )
    return all(
        np.isfinite([float(row[key]) for key in keys]).all() for row in records
    )


def _window_integrity(records: list[dict[str, Any]], completed: bool) -> bool:
    if not completed or len(records) < 2 or not _finite_records(records):
        return False
    for row in records[1:]:
        if not bool(row.get("aggregate_overall_pass", False)):
            return False
        for prefix in ("full", "first_half", "second_half"):
            if not bool(row.get(f"{prefix}_overall_pass", False)):
                return False
        if not bool(row.get("temperature_in_declared_range", False)):
            return False
        if not bool(row.get("conductive_state_in_declared_range", False)):
            return False
        if not bool(row.get("branch_memory_in_declared_range", False)):
            return False
    return True


def _run_window(spec: Mapping[str, Any], scientific: dict) -> dict[str, Any]:
    initial = _load_state(spec["initial_state"])
    level = int(spec.get("spatial_level", 1))
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    fields.validate_grid(grid)
    protocol_id = str(spec["protocol_id"])
    protocol = scientific["formal_protocols"]["protocols"][protocol_id]
    stop = float(spec["final_time_s"])
    sample_times = _window_sample_times(
        initial.time_s, stop, float(spec["sample_interval_s"])
    )
    recorder = _B3StreamingRecorder(
        case_id=str(spec["case_id"]),
        grid=grid,
        fields=fields,
        protocol=protocol,
        config=scientific,
        sample_times_s=sample_times,
        fixed_snapshot_times_s=(float(initial.time_s), stop),
        initial_state=initial,
        voltage_scale_V=protocol_voltage_scale(scientific, protocol_id),
        closure=closure,
    )
    attempts = _ControllerV2AttemptAccumulator()
    locator_segments: deque[tuple[S2State, S2State]] = deque()
    locator_window_state: S2State | None = None
    locator_padding = float(spec.get("window_padding_s", 0.0))
    locator_retention = locator_padding + 2.0 * float(spec["sample_interval_s"])

    def accepted(previous: S2State, step: Any, H: float, voltage: float, wall: float) -> None:
        nonlocal locator_window_state
        if str(spec["role"]) == "locator":
            locator_segments.append((previous, step.accepted_first_half.state))
            locator_segments.append((step.accepted_first_half.state, step.state))
        recorder.record_accepted_interval(
            previous,
            step,
            H,
            voltage,
            wall,
            coupled_solve_count=attempts.consume(step),
        )
        if str(spec["role"]) == "locator":
            if locator_window_state is None:
                upward = next(
                    (
                        item
                        for item in recorder.event_records
                        if item["direction"] == "upward"
                    ),
                    None,
                )
                if upward is not None:
                    target = max(
                        float(initial.time_s),
                        float(upward["crossing_time_s"]) - locator_padding,
                    )
                    tolerance = max(1.0e-18, abs(target) * 1.0e-12)
                    for left, right in locator_segments:
                        if left.time_s - tolerance <= target <= right.time_s + tolerance:
                            locator_window_state = _interpolate_state(left, right, target)
                            break
                    if locator_window_state is None:
                        raise RuntimeError(
                            "bounded locator history did not retain the event-window start"
                        )
            cutoff = float(step.state.time_s) - locator_retention
            while locator_segments and locator_segments[0][1].time_s < cutoff:
                locator_segments.popleft()

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
        "retain_full_history": bool(spec.get("retain_full_history", False)),
        "accepted_step_callback": accepted,
        "attempted_candidate_callback": attempts,
        "cache": build_s2_solver_cache(grid, fields),
    }
    solver = str(spec["solver"])
    started_wall = perf_counter()
    started_cpu = process_time()
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
        raise ValueError(f"unsupported B3 worker solver: {solver}")
    wall = perf_counter() - started_wall
    cpu = process_time() - started_cpu
    records = list(recorder.scalar_records)
    times = np.asarray([float(row["time_s"]) for row in records], dtype=float)
    output_complete = bool(
        recorder._sample_index == len(sample_times)
        and len(records) == len(sample_times)
        and len(times) == len(np.unique(times))
        and np.all(np.diff(times) > 0.0)
        and abs(times[-1] - stop) <= max(1.0e-18, abs(stop) * 1.0e-12)
    )
    integrity = _window_integrity(records, bool(result.completed))
    return {
        "schema_version": WORKER_SCHEMA_VERSION,
        "case_id": str(spec["case_id"]),
        "role": str(spec["role"]),
        "solver": solver,
        "protocol_id": protocol_id,
        "time_divisor": int(spec["time_divisor"]),
        "initial_time_s": float(initial.time_s),
        "final_time_s": stop,
        "completed": bool(result.completed),
        "stop_reason": str(result.stop_reason),
        "achieved_final_time_s": float(result.achieved_final_time_s),
        "output_complete": output_complete,
        "integrity_pass": integrity,
        "local_pass": bool(result.completed and output_complete and integrity),
        "wall_time_s": float(wall),
        "cpu_time_s": float(cpu),
        "diagnostics": asdict(result.diagnostics),
        "scalar_records": records,
        "event_records": list(recorder.event_records),
        "reversal_records": list(recorder.reversal_records),
        "sample_count": len(records),
        "accepted_path_step_count": len(result.steps),
        "final_state": _state_payload(recorder.final_state),
        "_locator_window_initial_state": locator_window_state,
    }


def _locator_result(spec: Mapping[str, Any], scientific: dict) -> dict[str, Any]:
    locator_spec = dict(spec)
    grid = build_geophase_grid(scientific, spatial_level=int(spec.get("spatial_level", 1)))
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    initial = initial_s2_state(grid, closure, fields, scientific)
    locator_spec["initial_state"] = _state_payload(initial)
    locator_spec["retain_full_history"] = False
    payload = _run_window(locator_spec, scientific)
    window_state = payload.pop("_locator_window_initial_state")
    events = list(payload["event_records"])
    up = next((item for item in events if item["direction"] == "upward"), None)
    down = None
    if up is not None:
        down = next(
            (
                item
                for item in events
                if item["direction"] == "downward"
                and float(item["crossing_time_s"]) > float(up["crossing_time_s"])
            ),
            None,
        )
    if up is None or down is None:
        payload.update(
            {
                "coverage_pass": False,
                "coverage_failure": "NO_COMPLETE_UP_DOWN_EVENT_PAIR_WITHIN_LOCATOR_HORIZON",
                "window_initial_state": None,
                "window_start_s": None,
                "window_stop_s": None,
            }
        )
        return payload
    padding = float(spec["window_padding_s"])
    window_start = max(float(initial.time_s), float(up["crossing_time_s"]) - padding)
    window_stop = min(float(spec["final_time_s"]), float(down["crossing_time_s"]) + padding)
    if window_state is None:
        raise RuntimeError("locator found an event pair without its bounded window state")
    payload.update(
        {
            "coverage_pass": True,
            "coverage_failure": None,
            "selected_upcrossing": up,
            "selected_downcrossing": down,
            "window_start_s": window_start,
            "window_stop_s": window_stop,
            "window_initial_state": _state_payload(window_state),
        }
    )
    return payload


def run_b3_worker(spec_path: Path, output_path: Path) -> dict[str, Any]:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    affinity = _pin_process_to_one_cpu()
    scientific = resolved_s2_config()
    started_wall = perf_counter()
    started_cpu = process_time()
    try:
        if str(spec["role"]) == "locator":
            payload = _locator_result(spec, scientific)
        else:
            payload = _run_window(spec, scientific)
            payload.pop("_locator_window_initial_state", None)
        payload["validity"] = "valid"
        payload["error_class"] = None
        payload["error_message"] = None
    except Exception as error:
        payload = {
            "schema_version": WORKER_SCHEMA_VERSION,
            "case_id": str(spec.get("case_id", "unknown")),
            "role": str(spec.get("role", "unknown")),
            "solver": str(spec.get("solver", "unknown")),
            "validity": "valid",
            "local_pass": False,
            "coverage_pass": False,
            "error_class": type(error).__name__,
            "error_message": str(error),
            "wall_time_s": float(perf_counter() - started_wall),
            "cpu_time_s": float(process_time() - started_cpu),
        }
    payload["affinity"] = affinity
    payload["thread_environment"] = {
        name: os.environ.get(name)
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        )
    }
    _atomic_json(Path(output_path), payload)
    return payload


def _trajectory_nrmse(
    candidate: np.ndarray, reference: np.ndarray, absolute_floor: float
) -> float:
    left = np.asarray(candidate, dtype=float)
    right = np.asarray(reference, dtype=float)
    if left.shape != right.shape or not np.isfinite(left).all() or not np.isfinite(right).all():
        return FINITE_REJECTION_PENALTY
    scale = max(float(np.sqrt(np.mean(right**2))), float(absolute_floor))
    return float(np.sqrt(np.mean((left - right) ** 2)) / scale)


def _event_comparison(
    candidate: list[dict[str, Any]],
    reference: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_directions = [str(item["direction"]) for item in candidate]
    reference_directions = [str(item["direction"]) for item in reference]
    sequence_equal = candidate_directions == reference_directions
    if not sequence_equal:
        return {
            "sequence_equal": False,
            "maximum_absolute_error_s": FINITE_REJECTION_PENALTY,
            "maximum_relative_error": FINITE_REJECTION_PENALTY,
        }
    absolute: list[float] = []
    relative: list[float] = []
    for observed, expected in zip(candidate, reference, strict=True):
        error = abs(float(observed["crossing_time_s"]) - float(expected["crossing_time_s"]))
        absolute.append(error)
        relative.append(error / max(abs(float(expected["crossing_time_s"])), 5.0e-9))
    return {
        "sequence_equal": True,
        "maximum_absolute_error_s": max(absolute, default=0.0),
        "maximum_relative_error": max(relative, default=0.0),
    }


def compare_window_payloads(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    reference_records = list(reference["scalar_records"])[1:]
    candidate_records = list(candidate["scalar_records"])[1:]
    reference_times = np.asarray([row["time_s"] for row in reference_records], dtype=float)
    candidate_times = np.asarray([row["time_s"] for row in candidate_records], dtype=float)
    time_tolerance = max(
        1.0e-18,
        max(
            float(np.max(np.abs(reference_times), initial=0.0)),
            float(np.max(np.abs(candidate_times), initial=0.0)),
        )
        * 1.0e-12,
    )
    time_grid_equal = bool(
        reference_times.shape == candidate_times.shape
        and np.allclose(reference_times, candidate_times, rtol=0.0, atol=time_tolerance)
    )
    if time_grid_equal:
        current_nrmse = _trajectory_nrmse(
            np.asarray([row["terminal_current_A"] for row in candidate_records]),
            np.asarray([row["terminal_current_A"] for row in reference_records]),
            float(contract["terminal_current_absolute_floor_A"]),
        )
        voltage_nrmse = _trajectory_nrmse(
            np.asarray([row["device_voltage_V"] for row in candidate_records]),
            np.asarray([row["device_voltage_V"] for row in reference_records]),
            float(contract["device_voltage_absolute_floor_V"]),
        )
    else:
        current_nrmse = voltage_nrmse = FINITE_REJECTION_PENALTY
    event = _event_comparison(
        list(candidate["event_records"]), list(reference["event_records"])
    )
    candidate_reversals = [item["direction"] for item in candidate["reversal_records"]]
    reference_reversals = [item["direction"] for item in reference["reversal_records"]]
    reversal_equal = candidate_reversals == reference_reversals
    gates = contract["correctness"]
    passed = bool(
        reference.get("local_pass")
        and candidate.get("local_pass")
        and time_grid_equal
        and current_nrmse <= float(gates["terminal_current_nrmse_max"])
        and voltage_nrmse <= float(gates["device_voltage_nrmse_max"])
        and event["sequence_equal"]
        and event["maximum_absolute_error_s"] <= float(gates["event_absolute_error_s_max"])
        and event["maximum_relative_error"] <= float(gates["event_relative_error_max"])
        and reversal_equal
        and int(candidate["diagnostics"]["fallback_steps"])
        == int(gates["exact_fallback_steps_required"])
    )
    return {
        "case_id": str(candidate["case_id"]),
        "time_grid_equal": time_grid_equal,
        "time_grid_tolerance_s": time_tolerance,
        "maximum_time_grid_difference_s": (
            float(np.max(np.abs(reference_times - candidate_times)))
            if reference_times.shape == candidate_times.shape
            else FINITE_REJECTION_PENALTY
        ),
        "terminal_current_nrmse": current_nrmse,
        "device_voltage_nrmse": voltage_nrmse,
        "event": event,
        "reversal_sequence_equal": reversal_equal,
        "reference_local_pass": bool(reference.get("local_pass")),
        "candidate_local_pass": bool(candidate.get("local_pass")),
        "candidate_growth_events": int(candidate["diagnostics"]["growth_events"]),
        "candidate_fallback_steps": int(candidate["diagnostics"]["fallback_steps"]),
        "passed": passed,
    }


def _safe_compare_window_payloads(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    required = ("scalar_records", "event_records", "reversal_records", "diagnostics")
    if all(key in reference and key in candidate for key in required):
        return compare_window_payloads(reference, candidate, contract)
    return {
        "case_id": str(candidate.get("case_id", "unknown")),
        "time_grid_equal": False,
        "terminal_current_nrmse": FINITE_REJECTION_PENALTY,
        "device_voltage_nrmse": FINITE_REJECTION_PENALTY,
        "event": {
            "sequence_equal": False,
            "maximum_absolute_error_s": FINITE_REJECTION_PENALTY,
            "maximum_relative_error": FINITE_REJECTION_PENALTY,
        },
        "reversal_sequence_equal": False,
        "reference_local_pass": bool(reference.get("local_pass", False)),
        "candidate_local_pass": bool(candidate.get("local_pass", False)),
        "candidate_growth_events": 0,
        "candidate_fallback_steps": 0,
        "passed": False,
        "worker_failure": {
            "reference": {
                "error_class": reference.get("error_class"),
                "error_message": reference.get("error_message"),
            },
            "candidate": {
                "error_class": candidate.get("error_class"),
                "error_message": candidate.get("error_message"),
            },
        },
    }


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


def _thread_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str | None]:
    values = os.environ if environment is None else environment
    return {
        name: values.get(name)
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        )
    }


def _invoke_worker(
    *,
    spec: Mapping[str, Any],
    spec_path: Path,
    output_path: Path,
    config_path: Path,
    output_root: Path,
    timeout_s: float,
) -> dict[str, Any]:
    _atomic_json(spec_path, spec)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_geophase_controller_relevance_final_rescue.py"),
        "--stage",
        "b3-worker",
        "--config",
        str(config_path),
        "--output-root",
        str(output_root),
        "--worker-spec",
        str(spec_path),
        "--worker-output",
        str(output_path),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=_worker_environment(),
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_s)),
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        payload = {
            "schema_version": WORKER_SCHEMA_VERSION,
            "case_id": str(spec.get("case_id", "unknown")),
            "role": str(spec.get("role", "unknown")),
            "solver": str(spec.get("solver", "unknown")),
            "validity": "valid",
            "local_pass": False,
            "coverage_pass": False,
            "error_class": "WorkerTimeout",
            "error_message": f"B3 worker exceeded {float(timeout_s)} wall seconds",
            "wall_time_s": float(timeout_s),
            "cpu_time_s": float(timeout_s),
            "worker_command": command,
            "worker_returncode": None,
            "worker_stdout": str(error.stdout or "")[-2000:],
            "worker_stderr": str(error.stderr or "")[-2000:],
        }
        _atomic_json(output_path, payload)
        return payload
    if completed.returncode != 0 and not output_path.exists():
        raise RuntimeError(
            f"B3 worker exited {completed.returncode}: {completed.stderr[-2000:]}"
        )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    payload["worker_command"] = command
    payload["worker_returncode"] = int(completed.returncode)
    payload["worker_stdout"] = completed.stdout[-2000:]
    payload["worker_stderr"] = completed.stderr[-2000:]
    _atomic_json(output_path, payload)
    return payload


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({str(key) for row in rows for key in row})
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _to_builtin(row.get(key)) for key in fields})
    temporary.replace(path)


def run_b3_qualification(config_path: Path, output_root: Path) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    contract = load_contract(config_path)
    verified = verify_frozen_inputs(contract)
    validate_thread_environment(contract)
    branch = _git_value("branch", "--show-current")
    if branch != str(contract["identity"]["branch"]):
        raise ValueError("B3 must run on the frozen stage branch")
    if _git_value("status", "--porcelain"):
        raise ValueError("B3 requires a clean anchored worktree")
    git_sha = _git_value("rev-parse", "HEAD")
    b3 = contract["b3"]
    parent_path = (ROOT / str(b3["parent_r2_summary"])).resolve()
    if _sha256(parent_path) != str(b3["parent_r2_summary_sha256"]):
        raise ValueError("B3 parent R2 summary hash drifted")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if parent.get("disposition") != str(b3["conditional_on"]):
        raise ValueError("B3 parent did not authorize matched-window qualification")
    expected_root = (
        ROOT
        / str(contract["outputs"]["namespace"])
        / str(contract["identity"]["b3_run_id"])
    ).resolve()
    output_root = Path(output_root).resolve()
    if output_root != expected_root:
        raise ValueError(f"B3 output root must be {expected_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot = output_root / str(b3["outputs"]["config_snapshot"])
    _atomic_bytes(snapshot, config_path.read_bytes())
    states_root = output_root / str(b3["outputs"]["states_directory"])
    workers_root = output_root / str(b3["outputs"]["worker_directory"])
    states_root.mkdir(parents=True, exist_ok=True)
    workers_root.mkdir(parents=True, exist_ok=True)

    budget = float(b3["aggregate_cpu_time_s_max"])
    aggregate_cpu = 0.0
    worker_results: list[dict[str, Any]] = []
    started = perf_counter()

    def run(spec: dict[str, Any], name: str) -> dict[str, Any]:
        nonlocal aggregate_cpu
        remaining = budget - aggregate_cpu
        if remaining <= 0.0:
            raise RuntimeError("B3 aggregate CPU budget exhausted")
        spec["maximum_wall_clock_s"] = min(
            float(spec.get("maximum_wall_clock_s", remaining)), remaining
        )
        result = _invoke_worker(
            spec=spec,
            spec_path=workers_root / f"{name}.spec.json",
            output_path=workers_root / f"{name}.json",
            config_path=config_path,
            output_root=output_root,
            timeout_s=remaining + 30.0,
        )
        aggregate_cpu += float(result.get("cpu_time_s", 0.0))
        worker_results.append(result)
        return result

    common = {
        "spatial_level": 1,
        "sample_interval_s": float(b3["comparison_sample_interval_s"]),
    }
    q = b3["quiescent_9V"]
    q_state = _hardest_state(ROOT / str(q["state_source"]))
    if abs(q_state.time_s - float(q["accepted_time_s"])) > 1.0e-15:
        raise ValueError("frozen 9 V B3 state time drifted")
    _atomic_json(states_root / "quiescent_9V_initial_state.json", _state_payload(q_state))
    q_stop = float(q_state.time_s + float(q["relative_window_s"]))
    q_spec = {
        **common,
        "protocol_id": str(q["protocol_id"]),
        "time_divisor": int(q["time_divisor"]),
        "initial_state": _state_payload(q_state),
        "final_time_s": q_stop,
    }
    q_reference = run(
        {**q_spec, "case_id": "B3-9V-NLS-CORRECTNESS", "role": "correctness", "solver": "nls_v1"},
        "01_9V_nls_correctness",
    )
    q_candidate = run(
        {
            **q_spec,
            "case_id": "B3-9V-AA-CORRECTNESS",
            "role": "correctness",
            "solver": "anderson_v1",
        },
        "02_9V_aa_correctness",
    )
    comparisons = [_safe_compare_window_payloads(q_reference, q_candidate, b3)]
    comparisons[0]["regime"] = "quiescent_9V"
    if int(q_candidate.get("diagnostics", {}).get("growth_events", 0)) < int(
        b3["correctness"]["quiescent_growth_events_min"]
    ):
        comparisons[0]["passed"] = False
        comparisons[0]["growth_gate_pass"] = False
    else:
        comparisons[0]["growth_gate_pass"] = True

    t = b3["transition_12p5V"]
    locator = run(
        {
            **common,
            "case_id": "B3-12P5V-NLS-LOCATOR",
            "role": "locator",
            "solver": "nls_v1",
            "protocol_id": str(t["protocol_id"]),
            "time_divisor": int(t["time_divisor"]),
            "final_time_s": float(t["locator_maximum_horizon_s"]),
            "window_padding_s": float(t["window_padding_s"]),
        },
        "03_12p5V_locator",
    )
    coverage_pass = bool(locator.get("coverage_pass", False) and locator.get("local_pass", False))
    if coverage_pass:
        transition_state = dict(locator["window_initial_state"])
        _atomic_json(states_root / "transition_12p5V_window_initial_state.json", transition_state)
        transition_spec = {
            **common,
            "protocol_id": str(t["protocol_id"]),
            "time_divisor": int(t["time_divisor"]),
            "initial_state": transition_state,
            "final_time_s": float(locator["window_stop_s"]),
        }
        t_reference = run(
            {
                **transition_spec,
                "case_id": "B3-12P5V-NLS-CORRECTNESS",
                "role": "correctness",
                "solver": "nls_v1",
            },
            "04_12p5V_nls_correctness",
        )
        t_candidate = run(
            {
                **transition_spec,
                "case_id": "B3-12P5V-AA-CORRECTNESS",
                "role": "correctness",
                "solver": "anderson_v1",
            },
            "05_12p5V_aa_correctness",
        )
        transition_comparison = _safe_compare_window_payloads(
            t_reference, t_candidate, b3
        )
        transition_comparison["regime"] = "transition_12p5V"
        transition_comparison["growth_gate_pass"] = True
        comparisons.append(transition_comparison)
    correctness_pass = bool(
        coverage_pass
        and len(comparisons) == 2
        and all(item["passed"] for item in comparisons)
    )

    timing_rows: list[dict[str, Any]] = []
    if correctness_pass:
        regimes = [("9V", q_spec)]
        regimes.append(("12p5V", transition_spec))
        warmup = float(b3["timing"]["warmup_prefix_s"])
        for regime, base_spec in regimes:
            warm_spec = dict(base_spec)
            warm_spec["final_time_s"] = min(
                float(base_spec["final_time_s"]),
                float(base_spec["initial_state"]["time_s"]) + warmup,
            )
            for solver in ("nls_v1", "anderson_v1"):
                run(
                    {
                        **warm_spec,
                        "case_id": f"B3-{regime}-{solver}-WARMUP",
                        "role": "warmup",
                        "solver": solver,
                    },
                    f"warmup_{regime}_{solver}",
                )
        repetitions = int(b3["timing"]["alternating_timed_repetitions"])
        for repetition in range(1, repetitions + 1):
            order = ("nls_v1", "anderson_v1") if repetition % 2 else ("anderson_v1", "nls_v1")
            for regime, base_spec in regimes:
                for solver in order:
                    result = run(
                        {
                            **base_spec,
                            "case_id": f"B3-{regime}-{solver}-TIMING-{repetition}",
                            "role": "timing",
                            "solver": solver,
                        },
                        f"timing_{regime}_{repetition}_{solver}",
                    )
                    timing_rows.append(
                        {
                            "regime": regime,
                            "repetition": repetition,
                            "solver": solver,
                            "wall_time_s": float(
                                result.get("wall_time_s", FINITE_REJECTION_PENALTY)
                            ),
                            "cpu_time_s": float(
                                result.get("cpu_time_s", FINITE_REJECTION_PENALTY)
                            ),
                            "local_pass": bool(result.get("local_pass", False)),
                        }
                    )

    performance: dict[str, Any] = {"executed": bool(correctness_pass), "passed": False}
    if correctness_pass:
        medians: dict[str, dict[str, float]] = {}
        for regime in ("9V", "12p5V"):
            medians[regime] = {}
            for solver in ("nls_v1", "anderson_v1"):
                values = [
                    row["wall_time_s"]
                    for row in timing_rows
                    if row["regime"] == regime and row["solver"] == solver and row["local_pass"]
                ]
                medians[regime][solver] = (
                    statistics.median(values)
                    if len(values) == 3
                    else FINITE_REJECTION_PENALTY
                )
        speedup_9 = medians["9V"]["nls_v1"] / medians["9V"]["anderson_v1"]
        speedup_12 = medians["12p5V"]["nls_v1"] / medians["12p5V"]["anderson_v1"]
        projected = (
            float(b3["performance"]["projection_safety_factor"])
            * float(b3["performance"]["historical_F9_wall_s"])
            / speedup_9
        )
        performance = {
            "executed": True,
            "median_wall_time_s": medians,
            "speedup_9V": speedup_9,
            "speedup_12p5V": speedup_12,
            "projected_full_9V_wall_time_s": projected,
            "passed": bool(
                speedup_9 >= float(b3["performance"]["speedup_9V_min"])
                and speedup_12 >= float(b3["performance"]["speedup_12p5V_min"])
                and projected <= float(b3["performance"]["projected_9V_wall_s_max"])
                and all(row["local_pass"] for row in timing_rows)
            ),
        }

    if not coverage_pass:
        disposition = "B3_TRANSITION_COVERAGE_VALID_FAIL"
    elif not correctness_pass:
        disposition = "B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL"
    elif not performance["passed"]:
        disposition = "B3_MATCHED_WINDOW_PERFORMANCE_VALID_FAIL"
    else:
        disposition = "B3_MATCHED_WINDOW_PASS"
    passed = disposition == "B3_MATCHED_WINDOW_PASS"
    comparison_path = output_root / str(b3["outputs"]["comparison_csv"])
    timing_path = output_root / str(b3["outputs"]["timing_csv"])
    _write_csv(comparison_path, comparisons)
    _write_csv(timing_path, timing_rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["b3_run_id"],
        "git_sha": git_sha,
        "branch": branch,
        "solver_id": b3["solver_id"],
        "reference_solver_id": b3["reference_solver_id"],
        "validity": "valid",
        "disposition": disposition,
        "route": "B4" if passed else "STOP_FINAL_FORWARD_SOLVER_RESCUE",
        "lifecycle_state": "numerically_validated",
        "claim_status": "qualified_supported" if passed else "failed_but_informative",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "coverage_pass": coverage_pass,
        "correctness_pass": correctness_pass,
        "performance": performance,
        "comparisons": comparisons,
        "locator": {
            key: value
            for key, value in locator.items()
            if key not in ("scalar_records", "final_state", "window_initial_state")
        },
        "aggregate_cpu_time_s": aggregate_cpu,
        "aggregate_cpu_time_s_max": budget,
        "wall_time_s": perf_counter() - started,
        "worker_count": len(worker_results),
        "verified_frozen_inputs": verified,
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha256(config_path),
        "parent_r2_summary": parent_path.relative_to(ROOT).as_posix(),
        "parent_r2_summary_sha256": _sha256(parent_path),
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "thread_environment": _thread_environment(_worker_environment()),
            "command": sys.argv,
        },
        "artifacts": {
            "config_snapshot": snapshot.relative_to(ROOT).as_posix(),
            "config_snapshot_sha256": _sha256(snapshot),
            "comparison_csv": comparison_path.relative_to(ROOT).as_posix(),
            "comparison_csv_sha256": _sha256(comparison_path),
            "timing_csv": timing_path.relative_to(ROOT).as_posix(),
            "timing_csv_sha256": _sha256(timing_path),
        },
        "evidence_type": contract["evidence_type"],
    }
    summary_path = output_root / str(b3["outputs"]["summary_json"])
    _atomic_json(summary_path, summary)
    return summary


def recompute_b3_metrics(config_path: Path, output_root: Path) -> dict[str, Any]:
    """Repair reporting-only metrics from immutable B3 worker payloads.

    No solver, controller, locator, or timing process is invoked.  The original
    summary and comparison table are preserved before the repaired view is
    published.
    """

    config_path = Path(config_path).resolve()
    contract = load_contract(config_path)
    b3 = contract["b3"]
    expected_root = (
        ROOT
        / str(contract["outputs"]["namespace"])
        / str(contract["identity"]["b3_run_id"])
    ).resolve()
    output_root = Path(output_root).resolve()
    if output_root != expected_root:
        raise ValueError(f"B3 metric repair root must be {expected_root}")
    if _git_value("status", "--porcelain"):
        raise ValueError("B3 metric repair requires a clean anchored worktree")
    outputs = b3["outputs"]
    summary_path = output_root / str(outputs["summary_json"])
    comparison_path = output_root / str(outputs["comparison_csv"])
    if not summary_path.exists() or not comparison_path.exists():
        raise ValueError("B3 metric repair requires the completed raw summary and table")
    original = json.loads(summary_path.read_text(encoding="utf-8"))
    if original.get("disposition") != "B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL":
        raise ValueError("B3 metric repair is limited to the frozen correctness FAIL")
    original_summary_path = output_root / "b3_summary.pre_metric_repair.json"
    original_comparison_path = output_root / "b3_comparisons.pre_metric_repair.csv"
    if original_summary_path.exists() or original_comparison_path.exists():
        raise ValueError("B3 metric repair may run only once")
    _atomic_bytes(original_summary_path, summary_path.read_bytes())
    _atomic_bytes(original_comparison_path, comparison_path.read_bytes())

    workers = output_root / str(outputs["worker_directory"])
    q_reference = json.loads(
        (workers / "01_9V_nls_correctness.json").read_text(encoding="utf-8")
    )
    q_candidate = json.loads(
        (workers / "02_9V_aa_correctness.json").read_text(encoding="utf-8")
    )
    t_reference = json.loads(
        (workers / "04_12p5V_nls_correctness.json").read_text(encoding="utf-8")
    )
    t_candidate = json.loads(
        (workers / "05_12p5V_aa_correctness.json").read_text(encoding="utf-8")
    )
    q_comparison = _safe_compare_window_payloads(q_reference, q_candidate, b3)
    q_comparison.update(
        {
            "regime": "quiescent_9V",
            "growth_gate_pass": int(q_candidate["diagnostics"]["growth_events"])
            >= int(b3["correctness"]["quiescent_growth_events_min"]),
        }
    )
    q_comparison["passed"] = bool(
        q_comparison["passed"] and q_comparison["growth_gate_pass"]
    )
    t_comparison = _safe_compare_window_payloads(t_reference, t_candidate, b3)
    t_comparison.update(
        {"regime": "transition_12p5V", "growth_gate_pass": True}
    )
    comparisons = [q_comparison, t_comparison]
    _write_csv(comparison_path, comparisons)
    repaired = {
        **original,
        "comparisons": comparisons,
        "correctness_pass": False,
        "disposition": "B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL",
        "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
        "metric_repair": {
            "kind": "reporting_only_fixed_grid_roundoff_tolerance",
            "repair_git_sha": _git_value("rev-parse", "HEAD"),
            "solver_rerun": False,
            "worker_rerun": False,
            "scientific_disposition_changed": False,
            "preserved_original_summary": original_summary_path.relative_to(ROOT).as_posix(),
            "preserved_original_summary_sha256": _sha256(original_summary_path),
            "preserved_original_comparison": original_comparison_path.relative_to(ROOT).as_posix(),
            "preserved_original_comparison_sha256": _sha256(original_comparison_path),
        },
    }
    repaired["artifacts"] = {
        **dict(original["artifacts"]),
        "comparison_csv_sha256": _sha256(comparison_path),
        "pre_metric_repair_summary": original_summary_path.relative_to(ROOT).as_posix(),
        "pre_metric_repair_summary_sha256": _sha256(original_summary_path),
        "pre_metric_repair_comparison": original_comparison_path.relative_to(ROOT).as_posix(),
        "pre_metric_repair_comparison_sha256": _sha256(original_comparison_path),
    }
    _atomic_json(summary_path, repaired)
    return repaired


__all__ = [
    "SCHEMA_VERSION",
    "WORKER_SCHEMA_VERSION",
    "_event_comparison",
    "_trajectory_nrmse",
    "_window_sample_times",
    "compare_window_payloads",
    "recompute_b3_metrics",
    "run_b3_qualification",
    "run_b3_worker",
]
