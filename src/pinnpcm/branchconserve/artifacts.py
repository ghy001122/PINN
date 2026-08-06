"""Atomic, recoverable artifacts for BranchConserve pilots."""

from __future__ import annotations

import csv
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping

import numpy as np

from pinnpcm.branchconserve.continuation import BranchPoint
from pinnpcm.branchconserve.solver import SteadySolveOutcome
from pinnpcm.branchconserve.stability import StabilityOutcome


def to_builtin(value: Any) -> Any:
    """Recursively canonicalize supported scientific payloads and fail closed."""

    if is_dataclass(value):
        return to_builtin(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {
                "real": to_builtin(value.real),
                "imag": to_builtin(value.imag),
            }
        return to_builtin(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("NaN and infinity are forbidden in canonical artifacts")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported artifact value type: {type(value).__name__}")


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        to_builtin(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    """Hash the exact worktree bytes used by an execution identity."""

    return sha256(Path(path).read_bytes()).hexdigest()


def atomic_write_json(path: Path, payload: Any, *, pretty: bool = True) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    built = to_builtin(payload)
    text = json.dumps(
        built,
        indent=2 if pretty else None,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return sha256(path.read_bytes()).hexdigest()


def atomic_write_csv(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    fieldnames: list[str],
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: to_builtin(row.get(key)) for key in fieldnames})
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return sha256(path.read_bytes()).hexdigest()


def atomic_write_npz(path: Path, **arrays: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        # NumPy appends .npz when the supplied path has no suffix.
        appended = Path(str(temporary) + ".npz")
        source = appended if appended.exists() else temporary
        os.replace(source, path)
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + ".npz").unlink(missing_ok=True)
    return sha256(path.read_bytes()).hexdigest()


def current_process_rss_bytes() -> int | None:
    """Return current working-set bytes without adding a runtime dependency."""

    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
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
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        handle = get_process()
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            ctypes.c_ulong,
        ]
        get_memory.restype = ctypes.c_int
        ok = get_memory(
            handle, ctypes.byref(counters), counters.cb
        )
        return int(counters.WorkingSetSize) if ok else None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(usage * (1024 if sys.platform != "darwin" else 1))
    except Exception:
        return None


def system_memory_bytes() -> dict[str, int | None]:
    """Return total and currently available physical memory on Windows."""

    if os.name != "nt":
        return {"total": None, "available": None}

    class MEMORYSTATUSEX(ctypes.Structure):
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

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return {
        "total": int(status.ullTotalPhys) if ok else None,
        "available": int(status.ullAvailPhys) if ok else None,
    }


def git_head(repository_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def environment_record(repository_root: Path, *, run_id: str) -> dict[str, Any]:
    memory = system_memory_bytes()
    disk = shutil.disk_usage(repository_root)
    return {
        "run_id": run_id,
        "git_sha": git_head(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "rss_bytes_at_record": current_process_rss_bytes(),
        "system_memory_total_bytes": memory["total"],
        "system_memory_available_bytes": memory["available"],
        "workspace_disk_total_bytes": disk.total,
        "workspace_disk_free_bytes": disk.free,
        "blas_thread_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "command": [sys.executable, *sys.argv],
    }


def _stability_arrays(stability: StabilityOutcome | None) -> dict[str, np.ndarray]:
    if stability is None:
        return {}
    return {
        "stability_eigenvalues_real_per_s": stability.eigenvalues_per_s.real,
        "stability_eigenvalues_imag_per_s": stability.eigenvalues_per_s.imag,
        "stability_eigenvectors_real": stability.eigenvectors_scaled.real,
        "stability_eigenvectors_imag": stability.eigenvectors_scaled.imag,
        "stability_relative_residuals": stability.relative_residuals,
        "stability_backward_errors_per_s": stability.backward_errors_per_s,
    }


def save_equilibrium_artifact(
    root: Path,
    *,
    identity: str,
    solve: SteadySolveOutcome,
    stability: StabilityOutcome | None,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist every voting-source field and its compact manifest atomically."""

    if not solve.success or solve.evaluation is None or solve.temperature_K is None:
        raise ValueError("only successful equilibria can be persisted as source fields")
    if stability is not None and not stability.success:
        raise ValueError("an unsuccessful stability record cannot be persisted as certified")
    evaluation = solve.evaluation
    npz_path = root / "equilibria" / f"{identity}.npz"
    npz_hash = atomic_write_npz(
        npz_path,
        temperature_K=evaluation.temperature_K,
        potential_V=evaluation.potential_V,
        conductive_state=evaluation.conductive_state,
        conductivity_S_m=evaluation.conductivity_S_m,
        vertical_conductance_W_m2K=evaluation.vertical_conductance_W_m2K,
        cell_joule_power_W=evaluation.cell_joule_power_W,
        electrical_x_face_current_A=evaluation.electrical_faces.x_face_current_A,
        electrical_y_face_current_A=evaluation.electrical_faces.y_face_current_A,
        electrical_source_face_current_A=evaluation.electrical_faces.source_face_current_A,
        electrical_ground_face_current_A=evaluation.electrical_faces.ground_face_current_A,
        thermal_x_face_flux_W=evaluation.thermal_x_face_flux_W,
        thermal_y_face_flux_W=evaluation.thermal_y_face_flux_W,
        thermal_net_cell_outflow_W=evaluation.thermal_net_cell_outflow_W,
        thermal_residual_W=evaluation.thermal_residual_W,
        **_stability_arrays(stability),
    )
    manifest = {
        "schema_version": "q2_branchconserve_equilibrium_v1",
        "identity": identity,
        "metadata": dict(metadata),
        "npz_path": npz_path.as_posix(),
        "npz_sha256": npz_hash,
        "source_voltage_V": evaluation.source_voltage_V,
        "device_voltage_V": evaluation.device_voltage_V,
        "source_current_A": evaluation.source_current_A,
        "active_area_mean_conductive_state": evaluation.active_area_mean_conductive_state,
        "scaled_electrical_residual_inf": evaluation.scaled_electrical_residual_inf,
        "scaled_thermal_residual_inf": evaluation.scaled_thermal_residual_inf,
        "load_line_residual": evaluation.load_line_residual,
        "ledger": evaluation.ledger,
        "solver": solve.telemetry,
        "stability": None
        if stability is None
        else {
            "code": stability.code,
            "stable": stability.stable,
            "rightmost_spectral_abscissa_per_s": stability.rightmost_spectral_abscissa_per_s,
            "tau_lambda_per_s": stability.tau_lambda_per_s,
            "spectral_abscissa_repeats_per_s": stability.spectral_abscissa_repeats_per_s,
            "matched_repeat_spread_per_s": stability.matched_repeat_spread_per_s,
            "telemetry": stability.telemetry,
        },
    }
    manifest_path = root / "equilibria" / f"{identity}.json"
    manifest_hash = atomic_write_json(manifest_path, manifest)
    return {
        "identity": identity,
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": manifest_hash,
        "npz_path": npz_path.as_posix(),
        "npz_sha256": npz_hash,
    }


def branch_point_row(point: BranchPoint) -> dict[str, Any]:
    return {
        "index": point.index,
        "branch": point.branch_name,
        "branch_memory": point.branch_memory,
        "device_voltage_V": point.device_voltage_V,
        "source_voltage_V": point.source_voltage_V,
        "source_current_A": point.source_current_A,
        "active_area_mean_conductive_state": point.active_area_mean_conductive_state,
        "stable": point.stable,
        "reachable": point.reachable,
        "atlas_only_reason": point.atlas_only_reason,
        "nonlinear_iterations": point.solve.telemetry.nonlinear_iterations,
        "jv_evaluations": point.solve.telemetry.jv_evaluations,
        "residual_evaluations": point.solve.telemetry.full_residual_evaluations,
        "solver_wall_time_s": point.solve.telemetry.wall_time_s,
        "stability_wall_time_s": point.stability.telemetry.wall_time_s,
        "rightmost_spectral_abscissa_per_s": point.stability.rightmost_spectral_abscissa_per_s,
        "tau_lambda_per_s": point.stability.tau_lambda_per_s,
    }
