"""Runtime measurement and deterministic campaign forecasting for Phase 1-v2."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any

import numpy as np
import scipy


@dataclass(frozen=True)
class ProcessMemory:
    working_set_bytes: int
    peak_working_set_bytes: int


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


class _ProcessorCoreRelationship(ctypes.Structure):
    _fields_ = [("Flags", ctypes.c_ubyte)]


class _NumaNodeRelationship(ctypes.Structure):
    _fields_ = [("NodeNumber", ctypes.c_ulong)]


class _CacheDescriptor(ctypes.Structure):
    _fields_ = [
        ("Level", ctypes.c_ubyte),
        ("Associativity", ctypes.c_ubyte),
        ("LineSize", ctypes.c_ushort),
        ("Size", ctypes.c_ulong),
        ("Type", ctypes.c_int),
    ]


class _ProcessorRelationshipUnion(ctypes.Union):
    _fields_ = [
        ("ProcessorCore", _ProcessorCoreRelationship),
        ("NumaNode", _NumaNodeRelationship),
        ("Cache", _CacheDescriptor),
        ("Reserved", ctypes.c_ulonglong * 2),
    ]


class _SystemLogicalProcessorInformation(ctypes.Structure):
    _anonymous_ = ("relationship_data",)
    _fields_ = [
        ("ProcessorMask", ctypes.c_size_t),
        ("Relationship", ctypes.c_int),
        ("relationship_data", _ProcessorRelationshipUnion),
    ]


def process_memory() -> ProcessMemory:
    if os.name == "nt":
        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        handle = kernel32.GetCurrentProcess()
        query = getattr(kernel32, "K32GetProcessMemoryInfo", None)
        if query is None:
            query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        query.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ProcessMemoryCountersEx),
            ctypes.c_ulong,
        ]
        query.restype = ctypes.c_int
        if not query(handle, ctypes.byref(counters), counters.cb):
            error = ctypes.get_last_error()
            raise OSError(error, "GetProcessMemoryInfo failed")
        return ProcessMemory(
            working_set_bytes=int(counters.WorkingSetSize),
            peak_working_set_bytes=int(counters.PeakWorkingSetSize),
        )
    import resource

    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform != "darwin":
        maximum *= 1024
    return ProcessMemory(working_set_bytes=maximum, peak_working_set_bytes=maximum)


def _physical_cores_windows() -> tuple[int | None, str]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel32.GetLogicalProcessorInformation
    query.argtypes = [
        ctypes.POINTER(_SystemLogicalProcessorInformation),
        ctypes.POINTER(ctypes.c_ulong),
    ]
    query.restype = ctypes.c_int
    byte_count = ctypes.c_ulong(0)
    query(None, ctypes.byref(byte_count))
    if byte_count.value:
        buffer = ctypes.create_string_buffer(byte_count.value)
        pointer = ctypes.cast(
            buffer, ctypes.POINTER(_SystemLogicalProcessorInformation)
        )
        if query(pointer, ctypes.byref(byte_count)):
            item_size = ctypes.sizeof(_SystemLogicalProcessorInformation)
            count = byte_count.value // item_size
            physical = sum(
                1 for index in range(count) if pointer[index].Relationship == 0
            )
            if physical > 0:
                return physical, "GetLogicalProcessorInformation.RelationProcessorCore"
    command = (
        "[int](Get-CimInstance Win32_Processor | "
        "Measure-Object -Property NumberOfCores -Sum).Sum"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        value = int(completed.stdout.strip())
        if value > 0:
            return value, "Win32_Processor.NumberOfCores"
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None, "unavailable"


def measure_launch_environment(workspace: Path) -> dict[str, Any]:
    if os.name == "nt":
        memory = _MemoryStatusEx()
        memory.dwLength = ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("GlobalMemoryStatusEx failed")
        total_ram = int(memory.ullTotalPhys)
        available_ram = int(memory.ullAvailPhys)
        physical_cores, physical_source = _physical_cores_windows()
    else:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total_ram = page_size * int(os.sysconf("SC_PHYS_PAGES"))
        available_ram = page_size * int(os.sysconf("SC_AVPHYS_PAGES"))
        physical_cores = None
        physical_source = "unavailable_without_optional_dependency"
    logical_cores = int(os.cpu_count() or 0)
    disk = shutil.disk_usage(Path(workspace))
    memory_now = process_memory()
    thread_variables = {
        name: os.environ.get(name)
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        )
    }
    return {
        "schema_version": "geophase_phase1_v2_runtime_environment_v1",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "logical_core_count": logical_cores,
        "physical_core_count": physical_cores,
        "physical_core_measurement_source": physical_source,
        "total_ram_bytes": total_ram,
        "available_ram_bytes_at_launch": available_ram,
        "process_working_set_bytes_at_launch": memory_now.working_set_bytes,
        "process_peak_working_set_bytes_at_launch": memory_now.peak_working_set_bytes,
        "disk_total_bytes": int(disk.total),
        "disk_free_bytes_at_launch": int(disk.free),
        "thread_environment": thread_variables,
        "all_worker_math_thread_limits_equal_one": all(
            value == "1" for value in thread_variables.values()
        ),
        "physical_core_measurement_available": physical_cores is not None,
    }


def deterministic_lpt_schedule(
    unit_rows: list[dict[str, Any]], workers: int, cost_key: str
) -> tuple[list[dict[str, Any]], float]:
    if workers <= 0:
        raise ValueError("LPT worker count must be positive")
    ordered = sorted(
        unit_rows,
        key=lambda item: (-float(item[cost_key]), str(item["execution_unit_id"])),
    )
    loads = [0.0] * workers
    scheduled: list[dict[str, Any]] = []
    for item in ordered:
        worker = min(range(workers), key=lambda index: (loads[index], index))
        start = loads[worker]
        duration = float(item[cost_key])
        loads[worker] += duration
        scheduled.append(
            {
                **item,
                f"{cost_key}_worker": worker,
                f"{cost_key}_start_s": start,
                f"{cost_key}_finish_s": loads[worker],
            }
        )
    return scheduled, float(max(loads, default=0.0))


def build_campaign_cost_forecast(
    *,
    execution_dag: dict[str, Any],
    sample_rows: list[dict[str, Any]],
    environment: dict[str, Any],
    floor_dt_s: float,
    disk_free_fraction_min: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grids = (1, 2, 4)
    by_grid: dict[int, dict[str, float]] = {}
    for level in grids:
        applicable = [
            row
            for row in sample_rows
            if int(row.get("spatial_level", 0)) == level
            and row.get("status") == "pass"
        ]
        trajectories = [
            row
            for row in applicable
            if row.get("sample_kind") in {"short_trajectory", "optional_long_prefix"}
            and float(row.get("achieved_simulated_time_s", 0.0)) > 0.0
        ]
        if not trajectories:
            raise ValueError(f"missing passing trajectory telemetry for L{level}")
        accepted_rate = max(
            float(row["accepted_steps"]) / float(row["achieved_simulated_time_s"])
            for row in trajectories
        )
        step_p90 = max(float(row["step_wall_time_p90_s"]) for row in trajectories)
        step_max = max(
            float(row["step_wall_time_max_s"])
            for row in applicable
            if float(row.get("step_wall_time_max_s", 0.0)) >= 0.0
        )
        full_streaming_bytes = max(
            int(row.get("predicted_full_streaming_bytes", 0)) for row in trajectories
        )
        full_io_s = max(
            float(row.get("predicted_full_streaming_io_s", 0.0))
            for row in trajectories
        )
        by_grid[level] = {
            "accepted_rate_per_simulated_s": accepted_rate,
            "step_wall_time_p90_s": step_p90,
            "step_wall_time_max_s": step_max,
            "predicted_full_streaming_bytes": float(full_streaming_bytes),
            "predicted_full_streaming_io_s": full_io_s,
        }

    rows: list[dict[str, Any]] = []
    duration = 2.0e-5
    for unit in execution_dag["execution_units"]:
        group = str(unit["execution_group"])
        level = int(unit.get("spatial_level") or 1)
        divisor = int(unit.get("time_divisor") or 1)
        fixture = unit.get("fixture_id")
        full_trajectory = group in {"REF", "TOP", "DUAL0"} or (
            group == "LIM" and fixture == "zero_drive_equilibrium"
        )
        observed = by_grid[level]
        if full_trajectory:
            unreserved_steps = int(
                math.ceil(
                    duration
                    * observed["accepted_rate_per_simulated_s"]
                    * divisor
                )
            )
            safety_steps = int(math.ceil(1.25 * unreserved_steps))
            absolute_floor_steps = int(math.ceil(duration / (floor_dt_s / divisor)))
            io_s = observed["predicted_full_streaming_io_s"]
            disk_bytes = int(observed["predicted_full_streaming_bytes"])
        else:
            unreserved_steps = safety_steps = absolute_floor_steps = 1
            io_s = min(observed["predicted_full_streaming_io_s"], 0.05)
            disk_bytes = max(4096, int(observed["predicted_full_streaming_bytes"] / 4001))
        multiplier = 2.0 if group == "DUAL0" else 1.10 if group == "TOP" else 1.0
        unreserved_wall = multiplier * (
            observed["step_wall_time_max_s"]
            + max(unreserved_steps - 1, 0) * observed["step_wall_time_p90_s"]
            + io_s
        )
        safety_wall = multiplier * (
            observed["step_wall_time_max_s"]
            + max(safety_steps - 1, 0)
            * 1.25
            * observed["step_wall_time_p90_s"]
            + 1.25 * io_s
        )
        rows.append(
            {
                "execution_unit_id": unit["execution_unit_id"],
                "execution_group": group,
                "spatial_level": level,
                "time_divisor": divisor,
                "full_trajectory": full_trajectory,
                "unreserved_accepted_steps": unreserved_steps,
                "safety_accepted_steps": safety_steps,
                "absolute_floor_accepted_steps": absolute_floor_steps,
                "observed_step_wall_time_p90_s": observed["step_wall_time_p90_s"],
                "observed_step_wall_time_max_s": observed["step_wall_time_max_s"],
                "unreserved_wall_clock_s": unreserved_wall,
                "safety_wall_clock_s": safety_wall,
                "predicted_output_bytes": disk_bytes,
            }
        )

    peak_rss = max(int(row.get("peak_rss_bytes", 0)) for row in sample_rows)
    physical = environment.get("physical_core_count")
    available = int(environment["available_ram_bytes_at_launch"])
    memory_workers = max(1, int(math.floor(0.70 * available / max(peak_rss, 1))))
    selected_workers = max(1, min(int(physical or 0), memory_workers))
    scheduled_unreserved, unreserved_makespan = deterministic_lpt_schedule(
        rows, selected_workers, "unreserved_wall_clock_s"
    )
    scheduled_safety, safety_makespan = deterministic_lpt_schedule(
        rows, selected_workers, "safety_wall_clock_s"
    )
    unreserved_assignment = {
        row["execution_unit_id"]: row for row in scheduled_unreserved
    }
    safety_assignment = {row["execution_unit_id"]: row for row in scheduled_safety}
    merged: list[dict[str, Any]] = []
    for row in rows:
        unit_id = row["execution_unit_id"]
        merged.append(
            {
                **row,
                "unreserved_worker": unreserved_assignment[unit_id][
                    "unreserved_wall_clock_s_worker"
                ],
                "unreserved_start_s": unreserved_assignment[unit_id][
                    "unreserved_wall_clock_s_start_s"
                ],
                "unreserved_finish_s": unreserved_assignment[unit_id][
                    "unreserved_wall_clock_s_finish_s"
                ],
                "safety_worker": safety_assignment[unit_id][
                    "safety_wall_clock_s_worker"
                ],
                "safety_start_s": safety_assignment[unit_id][
                    "safety_wall_clock_s_start_s"
                ],
                "safety_finish_s": safety_assignment[unit_id][
                    "safety_wall_clock_s_finish_s"
                ],
            }
        )
    predicted_disk = int(sum(row["predicted_output_bytes"] for row in rows))
    disk_total = int(environment["disk_total_bytes"])
    disk_free = int(environment["disk_free_bytes_at_launch"])
    disk_fraction_after = (disk_free - predicted_disk) / max(disk_total, 1)
    worker_rss = selected_workers * peak_rss
    summary = {
        "unit_count": len(rows),
        "scheduler": "deterministic_longest_processing_time_first",
        "selected_worker_count": selected_workers,
        "physical_core_limit": physical,
        "memory_worker_limit": memory_workers,
        "peak_worker_rss_bytes": peak_rss,
        "aggregate_worker_rss_bytes": worker_rss,
        "aggregate_worker_rss_fraction_of_launch_available_ram": worker_rss
        / max(available, 1),
        "unreserved_lpt_makespan_s": unreserved_makespan,
        "safety_lpt_makespan_s": safety_makespan,
        "predicted_campaign_output_bytes": predicted_disk,
        "disk_free_fraction_after_forecast": disk_fraction_after,
        "disk_free_fraction_min": disk_free_fraction_min,
        "grid_telemetry": by_grid,
    }
    return merged, summary


__all__ = [
    "ProcessMemory",
    "build_campaign_cost_forecast",
    "deterministic_lpt_schedule",
    "measure_launch_environment",
    "process_memory",
]
