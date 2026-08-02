"""Non-voting qualification for the versioned NLS-v1 S2 execution path."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

from pinnpcm.evaluation import geophase_controller_v3_qualification as prior
from pinnpcm.evaluation.geophase_s0_direct_physics import (
    ROOT,
    S0ExecutionError,
    atomic_json,
    resolved_s2_config,
)
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_nls_v1 import (
    NLS_V1_ID,
    NLS_V1_TIME_LANDING_RELATIVE_TOLERANCE,
    NLSV1SolveError,
    advance_s2_backward_euler_nls_v1,
)
from pinnpcm.solvers.geophase_nls_v1_streaming import (
    run_s2_streaming_protocol_nls_v1,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    initial_s2_state,
    protocol_discontinuities,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import fixed_scalar_sample_times


def _state_from_replay(payload: Mapping[str, Any]) -> S2State:
    return S2State(
        time_s=float(payload["time_s"]),
        temperature_K=np.asarray(payload["temperature_K"], dtype=float),
        conductive_state=np.asarray(payload["conductive_state"], dtype=float),
        branch_memory=np.asarray(payload["branch_memory"], dtype=float),
        device_voltage_V=float(payload["device_voltage_V"]),
    )


def _replay_failure_state(path: Path) -> dict[str, Any]:
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    replay = source["replay"]
    scientific = resolved_s2_config()
    grid = build_geophase_grid(scientific, spatial_level=1)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    started = perf_counter()
    try:
        result = advance_s2_backward_euler_nls_v1(
            _state_from_replay(replay["previous_state"]),
            input_voltage_V=float(replay["full_input_voltage_V"]),
            dt_s=float(replay["attempted_outer_interval_s"]),
            grid=grid,
            closure=closure,
            fields=fields,
            config=scientific,
            cache=build_s2_solver_cache(grid, fields),
            use_equivalent_optimizations=True,
            use_unit_voltage_scaling=True,
        )
    except NLSV1SolveError as error:
        return {
            "source_path": str(Path(path).relative_to(ROOT)).replace("\\", "/"),
            "source_error_message": str(source["error_message"]),
            "passed": False,
            "wall_time_s": float(perf_counter() - started),
            "error_message": str(error),
            "diagnostics": error.diagnostics,
        }
    nonlinear = result.nonlinear
    return {
        "source_path": str(Path(path).relative_to(ROOT)).replace("\\", "/"),
        "source_error_message": str(source["error_message"]),
        "passed": True,
        "wall_time_s": float(perf_counter() - started),
        "method": str(nonlinear.method),
        "iterations": int(nonlinear.iterations),
        "scaled_residual_inf": float(nonlinear.scaled_residual_inf),
        "fixed_point_defect_inf": float(nonlinear.fixed_point_defect_inf),
        "residual_blocks_inf": dict(nonlinear.residual_blocks_inf),
        "newton_failure": nonlinear.newton_failure,
        "fallback_iteration_history": [
            {
                name: getattr(item, name)
                for name in item.__dataclass_fields__
            }
            for item in nonlinear.fallback_iteration_history
        ],
    }


def _run_payload(
    *,
    case: Mapping[str, Any],
    divisor: int,
    final_time_s: float,
    failure_path: Path,
    maximum_wall_clock_s: float,
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
    result = run_s2_streaming_protocol_nls_v1(
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
        maximum_wall_clock_s=float(maximum_wall_clock_s),
        attempt_record_callback=record_attempt,
        failure_callback=publish_failure,
        cache=build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )
    wall_time_s = perf_counter() - started
    records = list(result.scalar_records)
    times = np.asarray([row["time_s"] for row in records], dtype=float)
    expected_output_points = len(fixed_scalar_sample_times(scientific, final_time_s))
    discontinuities = [
        float(value)
        for value in protocol_discontinuities(protocol)
        if initial.time_s < float(value) <= final_time_s
    ]
    required_landings = discontinuities + [float(final_time_s)]
    landing_tolerance = max(
        1.0e-18,
        abs(final_time_s) * NLS_V1_TIME_LANDING_RELATIVE_TOLERANCE,
    )
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
        np.isfinite([float(row[key]) for key in numeric_keys]).all()
        for row in records
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
    path_prefixes = ("full", "first_half", "second_half")
    max_residual = max(
        float(row.get(f"{prefix}_scaled_residual_inf", 0.0))
        for row in records[1:]
        for prefix in path_prefixes
    )
    max_defect = max(
        float(row.get(f"{prefix}_scaled_update_inf", 0.0))
        for row in records[1:]
        for prefix in path_prefixes
    )
    integrity = bool(
        result.protocol_result.completed
        and all(bool(row.get("aggregate_overall_pass", False)) for row in records[1:])
        and all(bool(row.get("temperature_in_declared_range", True)) for row in records)
        and all(
            bool(row.get("conductive_state_in_declared_range", True))
            for row in records
        )
        and all(bool(row.get("branch_memory_in_declared_range", True)) for row in records)
    )
    nonlinear = scientific["reference_solver"]["nonlinear_tolerances"]
    residual_limit = max(
        float(nonlinear["scaled_residual_absolute"]),
        float(nonlinear["scaled_residual_relative"]),
    )
    update_limit = float(nonlinear["scaled_update_relative"])
    local_pass = bool(
        len(records) == expected_output_points
        and times.size == expected_output_points
        and np.all(np.diff(times) > 0.0)
        and len(np.unique(times)) == expected_output_points
        and abs(times[-1] - final_time_s) <= landing_tolerance
        and exact_landings
        and finite
        and integrity
        and max_residual <= residual_limit
        and max_defect <= update_limit
        and max_current_imbalance
        <= float(gates["terminal_current_relative_imbalance_max"])
        and max_power_imbalance
        <= float(gates["device_power_identity_relative_residual_max"])
        and max_ledger["thermal"]
        <= float(gates["thermal_ledger_relative_residual_max"])
        and max_ledger["circuit"]
        <= float(gates["circuit_ledger_relative_residual_max"])
        and max_ledger["combined"]
        <= float(gates["combined_ledger_relative_residual_max"])
        and max_ledger["device_power"]
        <= float(gates["device_power_identity_relative_residual_max"])
    )
    return {
        "schema_version": "geophase_nls_v1_qualification_run_v1",
        "solver_identity": NLS_V1_ID,
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
        "expected_output_timestamp_count": expected_output_points,
        "ordered_unique_timestamps": bool(
            times.size == expected_output_points
            and np.all(np.diff(times) > 0.0)
            and len(np.unique(times)) == expected_output_points
        ),
        "finite": finite,
        "integrity_pass": integrity,
        "maximum_nonlinear_scaled_residual_inf": max_residual,
        "maximum_nonlinear_fixed_point_defect_inf": max_defect,
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


def run_nls_v1_qualification(
    *, config_path: Path, output_root: Path, anchor_commit: str
) -> dict[str, Any]:
    config = prior._load_yaml(config_path)
    authority = prior._validate_authority(config)
    if len(anchor_commit) != 40 or any(
        character not in "0123456789abcdef" for character in anchor_commit
    ):
        raise S0ExecutionError("NLS-v1 anchor must be a lowercase 40-character SHA")
    qualification = config["qualification"]
    standard_divisor = int(qualification["standard_time_divisor"])
    stricter_divisor = int(qualification["stricter_time_divisor"])
    final_time_s = float(qualification["final_time_s"])
    maximum_wall_clock_s = float(qualification["per_run_wall_time_s_max"])
    output_root = Path(output_root)
    if output_root.exists():
        raise S0ExecutionError("NLS-v1 qualification identity already exists")
    output_root.mkdir(parents=True)
    atomic_json(output_root / "config_snapshot.json", deepcopy(config))
    registry: dict[str, Any] = {
        "schema_version": "geophase_nls_v1_qualification_registry_v1",
        "qualification_id": config["identity"]["qualification_id"],
        "solver_identity": NLS_V1_ID,
        "anchor_commit": anchor_commit,
        "state": "RUNNING",
        "scientific_vote": False,
        "authority_sha256": authority,
        "run_hashes": {},
    }
    atomic_json(output_root / "registry.json", registry)
    replay_payloads = [
        _replay_failure_state(ROOT / item["path"])
        for item in qualification["failure_state_replays"]
    ]
    for index, payload in enumerate(replay_payloads, start=1):
        atomic_json(output_root / "replays" / f"replay_{index}.json", payload)
    if not all(payload["passed"] for payload in replay_payloads):
        registry["state"] = "NLS_V1_REPLAY_FAILED"
        atomic_json(output_root / "registry.json", registry)
        raise S0ExecutionError("NLS-v1 failed a frozen failure-state replay")

    run_payloads: list[dict[str, Any]] = []
    profile_payloads: list[dict[str, Any]] = []
    try:
        for case in qualification["cases"]:
            for divisor in (standard_divisor, stricter_divisor):
                run_id = f"{case['case_id']}-T{divisor}"
                payload = _run_payload(
                    case=case,
                    divisor=divisor,
                    final_time_s=final_time_s,
                    failure_path=output_root / "failures" / f"{run_id}.json",
                    maximum_wall_clock_s=maximum_wall_clock_s,
                )
                hashes = prior._atomic_gzip_json(
                    output_root / "runs" / f"{run_id}.json.gz", payload
                )
                registry["run_hashes"][run_id] = hashes
                atomic_json(output_root / "registry.json", registry)
                run_payloads.append(payload)
        for profile in qualification["runtime_profiles"]:
            run_id = str(profile["case_id"])
            payload = _run_payload(
                case=profile,
                divisor=int(profile["time_divisor"]),
                final_time_s=float(profile["final_time_s"]),
                failure_path=output_root / "failures" / f"{run_id}.json",
                maximum_wall_clock_s=maximum_wall_clock_s,
            )
            payload["run_role"] = "runtime_profile"
            hashes = prior._atomic_gzip_json(
                output_root / "profiles" / f"{run_id}.json.gz", payload
            )
            registry["run_hashes"][run_id] = hashes
            atomic_json(output_root / "registry.json", registry)
            profile_payloads.append(payload)
    except Exception as error:
        registry.update(
            {
                "state": "INVALID_NLS_V1_QUALIFICATION",
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
            if payload["case_id"] == case_id
            and payload["time_divisor"] == standard_divisor
        )
        stricter = next(
            payload
            for payload in run_payloads
            if payload["case_id"] == case_id
            and payload["time_divisor"] == stricter_divisor
        )
        comparisons.append(
            prior._comparison(standard, stricter, qualification["gates"])
        )
    projection = prior._runtime_projection(
        run_payloads,
        profile_payloads,
        worker_count_max=int(qualification["runtime_profile_worker_count_max"]),
    )
    passed = bool(
        all(item["passed"] for item in comparisons)
        and projection["projected_60_unit_wall_time_s"]
        <= float(qualification["gates"]["projected_60_unit_wall_clock_s_max"])
        and projection["projected_60_unit_cpu_time_s"]
        <= float(qualification["gates"]["projected_60_unit_cpu_time_s_max"])
    )
    summary = {
        "schema_version": "geophase_nls_v1_qualification_summary_v1",
        "qualification_id": config["identity"]["qualification_id"],
        "solver_identity": NLS_V1_ID,
        "anchor_commit": anchor_commit,
        "terminal_state": "NLS_V1_QUALIFIED" if passed else "NLS_V1_REJECTED",
        "scientific_vote": False,
        "failure_state_replays": replay_payloads,
        "run_count": len(run_payloads) + len(profile_payloads),
        "qualification_run_count": len(run_payloads),
        "runtime_profile_run_count": len(profile_payloads),
        "comparisons": comparisons,
        "runtime_projection": projection,
        "all_required_gates_pass": passed,
        "run_hashes": dict(sorted(registry["run_hashes"].items())),
        "authority_sha256": authority,
    }
    summary_sha = atomic_json(output_root / "qualification_summary.json", summary)
    registry.update(
        {"state": summary["terminal_state"], "summary_sha256": summary_sha}
    )
    atomic_json(output_root / "registry.json", registry)
    return summary


__all__ = ["run_nls_v1_qualification"]
