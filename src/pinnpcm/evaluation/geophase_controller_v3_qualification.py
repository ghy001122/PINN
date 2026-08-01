"""Bounded, non-voting qualification for the nonzero-drive controller-v3."""

from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_s0_direct_physics import (
    ROOT,
    S0ExecutionError,
    atomic_json,
    canonical_bytes,
    resolved_s2_config,
    sha256_file,
)
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    build_s2_solver_cache,
    initial_s2_state,
    protocol_discontinuities,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming_v3 import (
    run_s2_streaming_protocol_v3,
)


_DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "runtime_readiness"
    / "execution_dag.json"
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise S0ExecutionError("controller-v3 qualification config must be a mapping")
    return payload


def _validate_authority(config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for item in config["frozen_authority"]:
        relative = str(item["path"])
        digest = sha256_file(ROOT / relative)
        if digest != str(item["sha256"]):
            raise S0ExecutionError(f"controller-v3 frozen authority drifted: {relative}")
        observed[relative] = digest
    for item in config["implementation"]["source_files"]:
        relative = str(item["path"])
        digest = sha256_file(ROOT / relative)
        if digest != str(item["sha256"]):
            raise S0ExecutionError(f"controller-v3 source identity drifted: {relative}")
        observed[relative] = digest
    return observed


def _atomic_gzip_json(path: Path, payload: Any) -> dict[str, str]:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canonical = canonical_bytes(payload)
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise S0ExecutionError(f"stale qualification output exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(compressed)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return {
        "artifact_sha256": sha256_file(destination),
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _read_gzip_json(path: Path, hashes: Mapping[str, str]) -> dict[str, Any]:
    compressed = Path(path).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != str(hashes["artifact_sha256"]):
        raise S0ExecutionError("qualification run artifact hash drifted")
    canonical = gzip.decompress(compressed)
    if hashlib.sha256(canonical).hexdigest() != str(hashes["canonical_sha256"]):
        raise S0ExecutionError("qualification run canonical hash drifted")
    payload = json.loads(canonical)
    if canonical_bytes(payload) != canonical:
        raise S0ExecutionError("qualification run is not canonical JSON")
    return payload


def _nrmse(observed: np.ndarray, reference: np.ndarray) -> float:
    observed = np.asarray(observed, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if observed.shape != reference.shape or not np.isfinite(observed).all() or not np.isfinite(reference).all():
        return float("inf")
    scale = max(float(np.sqrt(np.mean(reference**2))), 1.0e-30)
    return float(np.sqrt(np.mean((observed - reference) ** 2)) / scale)


def _event_relative_error(observed: list[dict[str, Any]], reference: list[dict[str, Any]]) -> float:
    observed_directions = [str(item["direction"]) for item in observed]
    reference_directions = [str(item["direction"]) for item in reference]
    if observed_directions != reference_directions:
        return float("inf")
    if not reference:
        return 0.0
    differences = []
    for left, right in zip(observed, reference, strict=True):
        reference_time = abs(float(right["crossing_time_s"]))
        differences.append(
            abs(float(left["crossing_time_s"]) - float(right["crossing_time_s"]))
            / max(reference_time, 5.0e-9)
        )
    return float(max(differences, default=0.0))


def _run_payload(
    *,
    case: Mapping[str, Any],
    divisor: int,
    final_time_s: float,
    failure_path: Path,
) -> dict[str, Any]:
    scientific = resolved_s2_config()
    level = int(case["spatial_level"])
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    initial = initial_s2_state(grid, closure, fields, scientific)
    protocol_id = str(case["protocol_id"])
    protocol = scientific["formal_protocols"]["protocols"][protocol_id]
    accepted_endpoints: list[float] = []

    def record_attempt(payload: dict[str, Any]) -> None:
        if bool(payload["accepted"]):
            accepted_endpoints.append(
                float(payload["current_time_s"])
                + float(payload["attempted_outer_interval_s"])
            )

    def publish_failure(payload: dict[str, Any]) -> None:
        atomic_json(failure_path, payload)

    started = perf_counter()
    result = run_s2_streaming_protocol_v3(
        f"{case['case_id']}-T{divisor}",
        initial,
        protocol=protocol,
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        time_divisor=int(divisor),
        final_time_s=float(final_time_s),
        maximum_wall_clock_s=172800.0,
        attempt_record_callback=record_attempt,
        failure_callback=publish_failure,
        cache=build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )
    wall_time_s = perf_counter() - started
    records = list(result.scalar_records)
    times = np.asarray([row["time_s"] for row in records], dtype=float)
    discontinuities = [
        float(value)
        for value in protocol_discontinuities(protocol)
        if initial.time_s < float(value) <= final_time_s
    ]
    required_landings = discontinuities + [float(final_time_s)]
    landing_tolerance = max(1.0e-18, abs(final_time_s) * 1.0e-12)
    exact_landings = all(
        any(abs(endpoint - target) <= landing_tolerance for endpoint in accepted_endpoints)
        for target in required_landings
    )
    numeric_keys = (
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
    finite = all(
        np.isfinite([float(row[key]) for key in numeric_keys]).all() for row in records
    )
    gates = scientific["gates"]
    max_ledger = {
        name: max(float(row[f"{name}_relative_residual"]) for row in records)
        for name in ("thermal", "circuit", "combined", "device_power")
    }
    max_current_imbalance = max(
        float(row.get("terminal_current_relative_imbalance", 0.0)) for row in records
    )
    max_power_imbalance = max(
        float(row.get("device_power_relative_imbalance", 0.0)) for row in records
    )
    integrity = bool(
        result.protocol_result.completed
        and all(bool(row.get("aggregate_overall_pass", False)) for row in records[1:])
        and all(bool(row.get("temperature_in_declared_range", True)) for row in records)
        and all(bool(row.get("conductive_state_in_declared_range", True)) for row in records)
        and all(bool(row.get("branch_memory_in_declared_range", True)) for row in records)
    )
    local_pass = bool(
        len(records) == 4001
        and times.size == 4001
        and np.all(np.diff(times) > 0.0)
        and len(np.unique(times)) == 4001
        and abs(times[-1] - final_time_s) <= landing_tolerance
        and exact_landings
        and finite
        and integrity
        and max_current_imbalance <= float(gates["terminal_current_relative_imbalance_max"])
        and max_power_imbalance <= float(gates["device_power_identity_relative_residual_max"])
        and max_ledger["thermal"] <= float(gates["thermal_ledger_relative_residual_max"])
        and max_ledger["circuit"] <= float(gates["circuit_ledger_relative_residual_max"])
        and max_ledger["combined"] <= float(gates["combined_ledger_relative_residual_max"])
        and max_ledger["device_power"] <= float(gates["device_power_identity_relative_residual_max"])
    )
    return {
        "schema_version": "geophase_controller_v3_qualification_run_v1",
        "case_id": str(case["case_id"]),
        "protocol_id": protocol_id,
        "spatial_level": level,
        "time_divisor": int(divisor),
        "scientific_vote": False,
        "wall_time_s": float(wall_time_s),
        "completed": bool(result.protocol_result.completed),
        "stop_reason": str(result.protocol_result.stop_reason),
        "diagnostics": result.protocol_result.diagnostics,
        "accepted_endpoint_times_s": accepted_endpoints,
        "required_landing_times_s": required_landings,
        "exact_mandatory_landings": exact_landings,
        "output_timestamp_count": len(records),
        "ordered_unique_timestamps": bool(
            times.size == 4001 and np.all(np.diff(times) > 0.0) and len(np.unique(times)) == 4001
        ),
        "finite": finite,
        "integrity_pass": integrity,
        "maximum_ledger_relative_residual": max_ledger,
        "maximum_terminal_current_relative_imbalance": max_current_imbalance,
        "maximum_device_power_relative_imbalance": max_power_imbalance,
        "event_records": result.event_records,
        "reversal_records": result.reversal_records,
        "scalar_records": result.scalar_records,
        "field_snapshots": result.field_snapshots,
        "final_state": result.final_state,
        "local_pass": local_pass,
    }


def _comparison(
    standard: Mapping[str, Any],
    stricter: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    standard_records = list(standard["scalar_records"])
    stricter_records = list(stricter["scalar_records"])
    current_nrmse = _nrmse(
        np.asarray([row["terminal_current_A"] for row in standard_records]),
        np.asarray([row["terminal_current_A"] for row in stricter_records]),
    )
    voltage_nrmse = _nrmse(
        np.asarray([row["device_voltage_V"] for row in standard_records]),
        np.asarray([row["device_voltage_V"] for row in stricter_records]),
    )
    event_error = _event_relative_error(
        list(standard["event_records"]), list(stricter["event_records"])
    )
    event_sequence_equal = [item["direction"] for item in standard["event_records"]] == [
        item["direction"] for item in stricter["event_records"]
    ]
    reversal_sequence_equal = [item["direction"] for item in standard["reversal_records"]] == [
        item["direction"] for item in stricter["reversal_records"]
    ]
    port_nrmse = max(current_nrmse, voltage_nrmse)
    passed = bool(
        standard["local_pass"]
        and stricter["local_pass"]
        and current_nrmse <= float(gates["standard_vs_stricter_terminal_current_nrmse_max"])
        and port_nrmse <= float(gates["dense_output_vs_stricter_port_nrmse_max"])
        and event_error <= float(gates["standard_vs_stricter_event_time_relative_error_max"])
        and event_sequence_equal
        and reversal_sequence_equal
    )
    return {
        "case_id": standard["case_id"],
        "terminal_current_nrmse": current_nrmse,
        "device_voltage_nrmse": voltage_nrmse,
        "port_nrmse": port_nrmse,
        "event_time_max_relative_error": event_error,
        "event_sequence_equal": event_sequence_equal,
        "reversal_sequence_equal": reversal_sequence_equal,
        "passed": passed,
    }


def _runtime_projection(run_payloads: list[Mapping[str, Any]]) -> dict[str, Any]:
    strict_runs = [payload for payload in run_payloads if int(payload["time_divisor"]) == 4]
    if not strict_runs:
        raise S0ExecutionError("runtime projection requires divisor-4 qualification runs")
    per_unit = max(float(payload["wall_time_s"]) for payload in strict_runs)
    projected = 60.0 * per_unit
    return {
        "formula": "60_times_max_observed_L1_divisor4_full_protocol_wall_time",
        "max_observed_unit_wall_time_s": per_unit,
        "projected_60_unit_wall_time_s": projected,
    }


def run_controller_v3_qualification(
    *, config_path: Path, output_root: Path
) -> dict[str, Any]:
    config = _load_yaml(config_path)
    authority = _validate_authority(config)
    qualification = config["qualification"]
    standard_divisor = int(qualification["standard_time_divisor"])
    stricter_divisor = int(qualification["stricter_time_divisor"])
    final_time_s = float(qualification["final_time_s"])
    output_root = Path(output_root)
    if output_root.exists():
        raise S0ExecutionError("controller-v3 qualification identity already exists")
    output_root.mkdir(parents=True)
    atomic_json(output_root / "config_snapshot.json", deepcopy(config))
    registry: dict[str, Any] = {
        "schema_version": "geophase_controller_v3_qualification_registry_v1",
        "qualification_id": config["identity"]["qualification_id"],
        "state": "RUNNING",
        "scientific_vote": False,
        "authority_sha256": authority,
        "run_hashes": {},
    }
    atomic_json(output_root / "registry.json", registry)
    run_payloads: list[dict[str, Any]] = []
    try:
        for case in qualification["cases"]:
            for divisor in (standard_divisor, stricter_divisor):
                run_id = f"{case['case_id']}-T{divisor}"
                failure_path = output_root / "failures" / f"{run_id}.json"
                payload = _run_payload(
                    case=case,
                    divisor=divisor,
                    final_time_s=final_time_s,
                    failure_path=failure_path,
                )
                hashes = _atomic_gzip_json(output_root / "runs" / f"{run_id}.json.gz", payload)
                registry["run_hashes"][run_id] = hashes
                atomic_json(output_root / "registry.json", registry)
                run_payloads.append(payload)
    except Exception as error:
        registry.update(
            {
                "state": "INVALID_CONTROLLER_V3_QUALIFICATION",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
        atomic_json(output_root / "registry.json", registry)
        raise

    comparisons = []
    for case in qualification["cases"]:
        case_id = str(case["case_id"])
        standard = next(
            payload
            for payload in run_payloads
            if payload["case_id"] == case_id and payload["time_divisor"] == standard_divisor
        )
        stricter = next(
            payload
            for payload in run_payloads
            if payload["case_id"] == case_id and payload["time_divisor"] == stricter_divisor
        )
        comparisons.append(_comparison(standard, stricter, qualification["gates"]))
    projection = _runtime_projection(run_payloads)
    passed = bool(
        all(item["passed"] for item in comparisons)
        and projection["projected_60_unit_wall_time_s"]
        <= float(qualification["gates"]["projected_60_unit_wall_clock_s_max"])
    )
    summary = {
        "schema_version": "geophase_controller_v3_qualification_summary_v1",
        "qualification_id": config["identity"]["qualification_id"],
        "terminal_state": (
            "CONTROLLER_V3_QUALIFIED" if passed else "CONTROLLER_V3_CANDIDATE_REJECTED"
        ),
        "scientific_vote": False,
        "controller_candidate_index": int(config["identity"]["controller_candidate_index"]),
        "run_count": len(run_payloads),
        "comparisons": comparisons,
        "runtime_projection": projection,
        "all_required_gates_pass": passed,
        "run_hashes": dict(sorted(registry["run_hashes"].items())),
        "authority_sha256": authority,
    }
    summary_sha = atomic_json(output_root / "qualification_summary.json", summary)
    registry.update(
        {
            "state": summary["terminal_state"],
            "summary_sha256": summary_sha,
        }
    )
    atomic_json(output_root / "registry.json", registry)
    return summary


def validate_controller_v3_config(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    authority = _validate_authority(config)
    return {
        "task_id": config["task_id"],
        "controller_id": config["identity"]["controller_id"],
        "qualification_id": config["identity"]["qualification_id"],
        "formal_execution_count": int(config["formal_s0"]["formal_execution_count"]),
        "qualification_cases": len(config["qualification"]["cases"]),
        "authority_file_count": len(authority),
    }


__all__ = ["run_controller_v3_qualification", "validate_controller_v3_config"]
