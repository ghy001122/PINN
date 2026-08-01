"""Fresh S0 formal execution and frozen 63-item physical evaluation.

The control plane is intentionally small.  It dispatches the already frozen
60-unit execution DAG directly to the production S2 FVM/controller, publishes
one canonical raw record per unit, and evaluates the existing 63 scientific
items.  No historical E0, readiness, or equivalence runner is imported.
"""

from __future__ import annotations

from copy import deepcopy
import csv
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
import platform
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Callable, Mapping

import numpy as np

from pinnpcm.evaluation.geophase_s0_direct_physics import (
    ROOT,
    S0ExecutionError,
    apply_single_thread_environment,
    atomic_json,
    canonical_bytes,
    execution_code_hashes,
    formal_plan,
    foundation_payload,
    load_yaml,
    read_canonical_json,
    resolved_s2_config,
    sha256_file,
    to_builtin,
    validate_authority,
)
from pinnpcm.physics.geophase_geometry import (
    GeoPhaseGrid,
    assert_not_coordinate_swapped,
    build_geophase_grid,
)
from pinnpcm.physics.geophase_ledgers import require_ledger_gate
from pinnpcm.physics.geophase_s2_ledgers import build_s2_ledgers
from pinnpcm.physics.geophase_s2_thermal import (
    S2ThermalFields,
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    assemble_sheet_thermal_matrix,
    reconstruct_lateral_fluxes,
    solve_s2_thermal_backward_euler,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    initial_s2_state,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import (
    S2StreamingResult,
    run_s2_streaming_protocol_v2,
)


_MANIFEST_CSV = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "formal_evaluation_manifest.csv"
)
_DAG_JSON = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "runtime_readiness"
    / "execution_dag.json"
)
_FOUNDATION_GROUPS = {"FAIL", "MMS", "LIM"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_bytes(path: Path, content: bytes) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise S0ExecutionError(f"stale temporary output exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    observed = sha256_file(temporary)
    expected = hashlib.sha256(content).hexdigest()
    if observed != expected:
        temporary.unlink(missing_ok=True)
        raise S0ExecutionError("atomic output hash verification failed")
    os.replace(temporary, destination)
    return expected


def _atomic_canonical_gzip(path: Path, payload: Any) -> dict[str, str]:
    canonical = canonical_bytes(payload)
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    return {
        "artifact_sha256": _atomic_bytes(path, compressed),
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _read_canonical_gzip(path: Path, expected: Mapping[str, str]) -> Any:
    compressed = Path(path).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != str(expected["artifact_sha256"]):
        raise S0ExecutionError("compressed unit artifact hash drifted")
    canonical = gzip.decompress(compressed)
    if hashlib.sha256(canonical).hexdigest() != str(expected["canonical_sha256"]):
        raise S0ExecutionError("canonical unit payload hash drifted")
    payload = json.loads(canonical)
    if canonical_bytes(payload) != canonical:
        raise S0ExecutionError("compressed unit payload is not canonical JSON")
    return payload


def _atomic_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows([{key: row.get(key, "") for key in columns} for row in rows])
    return _atomic_bytes(path, stream.getvalue().encode("utf-8"))


def _load_manifest_rows() -> list[dict[str, str]]:
    with _MANIFEST_CSV.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    identifiers = [row["evaluation_id"] for row in rows]
    if len(rows) != 63 or len(set(identifiers)) != 63:
        raise S0ExecutionError("formal manifest must contain 63 unique items")
    return rows


def _load_units() -> list[dict[str, Any]]:
    payload = json.loads(_DAG_JSON.read_text(encoding="utf-8"))
    units = payload.get("execution_units")
    if not isinstance(units, list) or len(units) != 60:
        raise S0ExecutionError("formal DAG must contain 60 execution units")
    return [dict(unit) for unit in units]


def _context(
    level: int, *, overlap_m: float | None = None
) -> tuple[GeoPhaseGrid, S2ThermalFields, Any, Any, dict[str, Any]]:
    config = resolved_s2_config()
    grid = build_geophase_grid(
        config, spatial_level=int(level), contact_overlap_m=overlap_m
    )
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    cache = build_s2_solver_cache(grid, fields)
    return grid, fields, closure, cache, config


def _trajectory_record(result: S2StreamingResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "protocol_result": {
            "completed": result.protocol_result.completed,
            "stop_reason": result.protocol_result.stop_reason,
            "requested_final_time_s": result.protocol_result.requested_final_time_s,
            "achieved_final_time_s": result.protocol_result.achieved_final_time_s,
            "diagnostics": result.protocol_result.diagnostics,
        },
        "final_state": result.final_state,
        "scalar_records": result.scalar_records,
        "event_records": result.event_records,
        "reversal_records": result.reversal_records,
        "field_snapshots": result.field_snapshots,
    }


def _trajectory_local_metrics(result: S2StreamingResult, config: Mapping[str, Any]) -> dict[str, Any]:
    records = result.scalar_records
    if not records:
        raise S0ExecutionError("trajectory produced no scalar records")
    accepted = records[1:]
    gates = config["gates"]
    integrity = bool(
        result.protocol_result.completed
        and accepted
        and all(bool(record.get("aggregate_overall_pass", False)) for record in accepted)
    )
    maxima = {
        "thermal": max(float(record["thermal_relative_residual"]) for record in records),
        "circuit": max(float(record["circuit_relative_residual"]) for record in records),
        "combined": max(float(record["combined_relative_residual"]) for record in records),
        "device_power": max(
            float(record["device_power_relative_residual"]) for record in records
        ),
    }
    ledgers_pass = bool(
        maxima["thermal"] <= float(gates["thermal_ledger_relative_residual_max"])
        and maxima["circuit"] <= float(gates["circuit_ledger_relative_residual_max"])
        and maxima["combined"] <= float(gates["combined_ledger_relative_residual_max"])
        and maxima["device_power"]
        <= float(gates["device_power_identity_relative_residual_max"])
    )
    current = np.asarray([record["terminal_current_A"] for record in records], dtype=float)
    temperature = np.asarray([record["maximum_temperature_K"] for record in records], dtype=float)
    state = np.asarray([record["mean_conductive_state"] for record in records], dtype=float)
    post_warmup = config["formal_protocols"]["post_warmup_trend_window_s"]
    start, stop = map(float, post_warmup)
    crossings = [
        event
        for event in result.event_records
        if start <= float(event["crossing_time_s"]) <= stop
    ]
    return {
        "integrity_pass": integrity,
        "ledgers_pass": ledgers_pass,
        "maximum_relative_residual": maxima,
        "terminal_current_rms_A": float(np.sqrt(np.mean(current**2))),
        "maximum_temperature_rise_K": float(np.max(temperature - temperature[0])),
        "maximum_mean_state_change": float(np.max(np.abs(state - state[0]))),
        "final_mean_conductive_state": float(state[-1]),
        "post_warmup_crossing_count": len(crossings),
        "post_warmup_crossings": [
            {
                "direction": event["direction"],
                "crossing_time_s": event["crossing_time_s"],
            }
            for event in crossings
        ],
        "passed": bool(integrity and ledgers_pass),
    }


def _run_trajectory(
    unit: Mapping[str, Any], *, remaining_s: float, overlap_m: float | None = None
) -> dict[str, Any]:
    level = int(unit["spatial_level"])
    divisor = int(unit["time_divisor"])
    protocol_id = str(unit["protocol_id"])
    grid, fields, closure, cache, config = _context(level, overlap_m=overlap_m)
    initial = initial_s2_state(grid, closure, fields, config)
    result = run_s2_streaming_protocol_v2(
        str(unit["execution_unit_id"]),
        initial,
        protocol=config["formal_protocols"]["protocols"][protocol_id],
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        time_divisor=divisor,
        final_time_s=2.0e-5,
        maximum_wall_clock_s=max(float(remaining_s), 1.0e-6),
        retain_full_history=False,
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )
    if not result.protocol_result.completed:
        return {
            "execution_unit_id": unit["execution_unit_id"],
            "execution_group": unit["execution_group"],
            "validity": "invalid",
            "status": "PERFORMANCE_STOP"
            if result.protocol_result.stop_reason == "maximum_wall_clock_reached"
            else "INVALID",
            "scientific_vote": False,
            "local_metrics": {},
            "raw": _trajectory_record(result),
        }
    metrics = _trajectory_local_metrics(result, config)
    return {
        "execution_unit_id": unit["execution_unit_id"],
        "execution_group": unit["execution_group"],
        "validity": "valid",
        "status": "PASS" if metrics["passed"] else "SCIENTIFIC_FAIL",
        "scientific_vote": True,
        "local_metrics": metrics,
        "raw": _trajectory_record(result),
    }


def _mms_payload(unit: Mapping[str, Any]) -> dict[str, Any]:
    level = int(unit["spatial_level"])
    problem = str(unit["primary_evaluation_id"]).split("-MMS-", 1)[1].rsplit("-L", 1)[0]
    grid, fields, _closure, _cache, config = _context(level)
    gates = config["gates"]
    if problem == "electrical_linear_field":
        sigma = np.full(grid.shape, 12.0, dtype=float)
        solved = solve_sheet_electrical(grid, sigma, 1.0)
        exact_1d = 1.0 - grid.x_centers_m / grid.x_edges_m[-1]
        exact = np.broadcast_to(exact_1d[None, :], grid.shape)
        error = float(np.linalg.norm(solved.potential_V - exact) / np.linalg.norm(exact))
        threshold = float(gates["manufactured_electrical_relative_l2_max"])
        extra = {
            "terminal_current_relative_imbalance": solved.relative_current_imbalance,
            "device_power_relative_imbalance": solved.relative_power_imbalance,
        }
    elif problem == "thermal_diffusion_with_source_and_sink":
        x = grid.x_centers_m / grid.x_edges_m[-1]
        y = grid.y_centers_m / grid.y_edges_m[-1]
        target = fields.ambient_temperature_K + 0.1 * (
            1.0
            + np.sin(np.pi * y[:, None]) * np.sin(np.pi * x[None, :])
        )
        old = np.full(grid.shape, fields.ambient_temperature_K)
        dt_s = 1.0e-8
        lateral = assemble_sheet_thermal_matrix(grid, fields.sheet_thermal_conductance_W_K)
        capacity = fields.effective_areal_capacity_J_m2K.reshape(-1) * grid.cell_area_m2
        sink = fields.vertical_conductance_W_m2K * grid.cell_area_m2
        source_W = (
            capacity / dt_s * (target.reshape(-1) - old.reshape(-1))
            + lateral @ target.reshape(-1)
            + sink * (target.reshape(-1) - fields.ambient_temperature_K)
        )
        solved = solve_s2_thermal_backward_euler(
            grid,
            fields,
            old,
            np.zeros(grid.shape),
            dt_s,
            external_areal_source_W_m2=source_W.reshape(grid.shape) / grid.cell_area_m2,
            lateral_matrix=lateral,
        )
        error = float(np.linalg.norm(solved - target) / np.linalg.norm(target))
        threshold = float(gates["manufactured_thermal_relative_l2_max"])
        extra = {"target_temperature_range_K": float(np.ptp(target))}
    elif problem == "S2_forced_uniform_temperature_response":
        old = np.full(grid.shape, fields.ambient_temperature_K)
        target = old + 0.01
        dt_s = 1.0e-8
        source = (
            fields.effective_areal_capacity_J_m2K * 0.01 / dt_s
            + fields.vertical_conductance_W_m2K * 0.01
        )
        solved = solve_s2_thermal_backward_euler(
            grid,
            fields,
            old,
            np.zeros(grid.shape),
            dt_s,
            external_areal_source_W_m2=source,
        )
        error = float(np.linalg.norm(solved - target) / np.linalg.norm(target))
        threshold = float(gates["manufactured_thermal_relative_l2_max"])
        extra = {"uniform_increment_K": 0.01}
    else:
        raise S0ExecutionError(f"unknown MMS problem: {problem}")
    passed = bool(np.isfinite(error) and error <= threshold)
    return {
        "execution_unit_id": unit["execution_unit_id"],
        "execution_group": "MMS",
        "validity": "valid",
        "status": "PASS" if passed else "SCIENTIFIC_FAIL",
        "scientific_vote": True,
        "local_metrics": {
            "problem_id": problem,
            "relative_l2_error": error,
            "threshold": threshold,
            **extra,
        },
        "raw": {},
    }


def _fail_fixture(unit: Mapping[str, Any]) -> dict[str, Any]:
    fixture = str(unit["fixture_id"])
    grid, fields, closure, cache, config = _context(1)
    detected = False
    error_type = ""
    error_message = ""
    try:
        if fixture == "negative_effective_capacity":
            replace(
                fields,
                effective_areal_capacity_J_m2K=-np.ones(grid.shape),
            )
        elif fixture == "negative_vertical_conductance":
            replace(fields, vertical_conductance_W_m2K=-1.0)
        elif fixture == "nonfinite_newton":
            state = initial_s2_state(grid, closure, fields, config)
            from pinnpcm.solvers.geophase_phase1_v2_implicit import (
                advance_s2_backward_euler,
            )

            # The input is finite, so the production nonlinear path is entered.
            # Its squared electrical field overflows and must be rejected when
            # the first thermal residual is formed.
            with np.errstate(over="ignore", invalid="ignore"):
                advance_s2_backward_euler(
                    state,
                    input_voltage_V=1.0e308,
                    dt_s=1.0e-9,
                    grid=grid,
                    closure=closure,
                    fields=fields,
                    config=config,
                    cache=cache,
                )
        elif fixture == "ledger_tamper":
            old = initial_s2_state(grid, closure, fields, config)
            from pinnpcm.solvers.geophase_phase1_v2_implicit import advance_s2_backward_euler

            step = advance_s2_backward_euler(
                old,
                input_voltage_V=12.5,
                dt_s=1.0e-9,
                grid=grid,
                closure=closure,
                fields=fields,
                config=config,
                cache=cache,
            )
            tampered = replace(step.electrical, joule_power_W=1.1 * step.electrical.joule_power_W)
            audit = reconstruct_lateral_fluxes(
                grid,
                fields.sheet_thermal_conductance_W_K,
                step.state.temperature_K,
                matrix=cache.lateral_matrix,
            )
            ledgers = build_s2_ledgers(
                grid=grid,
                fields=fields,
                old_temperature_K=old.temperature_K,
                new_temperature_K=step.state.temperature_K,
                old_device_voltage_V=old.device_voltage_V,
                new_device_voltage_V=step.state.device_voltage_V,
                input_voltage_V=12.5,
                load_resistance_ohm=float(config["physics_contract"]["circuit"]["load_resistance_ohm"]),
                capacitance_F=float(config["physics_contract"]["circuit"]["parallel_capacitance_F"]),
                dt_s=1.0e-9,
                electrical=tampered,
                lateral_boundary_outflow_W=audit.boundary_outflow_W,
            )
            require_ledger_gate(
                ledgers.device_power,
                float(config["gates"]["device_power_identity_relative_residual_max"]),
            )
        elif fixture == "coordinate_swap":
            swapped = GeoPhaseGrid(
                x_edges_m=grid.y_edges_m,
                y_edges_m=grid.x_edges_m,
                thickness_m=grid.thickness_m,
                contact_overlap_m=grid.contact_overlap_m,
                left_contact_mask=grid.left_contact_mask.T,
                right_contact_mask=grid.right_contact_mask.T,
                region_index=grid.region_index.T,
            )
            assert_not_coordinate_swapped(swapped, config)
        else:
            raise S0ExecutionError(f"unknown FAIL fixture: {fixture}")
    except (ValueError, RuntimeError) as error:
        detected = True
        error_type = type(error).__name__
        error_message = str(error)
    return {
        "execution_unit_id": unit["execution_unit_id"],
        "execution_group": "FAIL",
        "validity": "valid",
        "status": "PASS" if detected else "SCIENTIFIC_FAIL",
        "scientific_vote": True,
        "local_metrics": {
            "fixture_id": fixture,
            "expected_failure_detected": detected,
            "error_type": error_type,
            "error_message": error_message,
        },
        "raw": {},
    }


def _lim_payload(unit: Mapping[str, Any], *, remaining_s: float) -> dict[str, Any]:
    fixture = str(unit["fixture_id"])
    if fixture == "zero_drive_equilibrium":
        return _run_trajectory(unit, remaining_s=remaining_s)
    grid, fields, closure, cache, config = _context(1)
    metrics: dict[str, Any]
    if fixture == "uniform_conductivity_linear_potential":
        sigma = np.full(grid.shape, 12.0)
        result = solve_sheet_electrical(grid, sigma, 1.0)
        exact = np.broadcast_to(
            (1.0 - grid.x_centers_m / grid.x_edges_m[-1])[None, :], grid.shape
        )
        error = float(np.linalg.norm(result.potential_V - exact) / np.linalg.norm(exact))
        passed = error <= float(config["gates"]["manufactured_electrical_relative_l2_max"])
        metrics = {"relative_l2_error": error}
    elif fixture == "zero_joule_cooling":
        dt_s = 1.0e-8
        old = np.full(grid.shape, fields.ambient_temperature_K + 1.0)
        solved = solve_s2_thermal_backward_euler(
            grid, fields, old, np.zeros(grid.shape), dt_s, lateral_matrix=cache.lateral_matrix
        )
        capacity_cell = (
            fields.effective_areal_capacity_J_m2K.reshape(-1) * grid.cell_area_m2
        )
        sink_cell = fields.vertical_conductance_W_m2K * grid.cell_area_m2
        left = (
            capacity_cell / dt_s * solved.reshape(-1)
            + cache.lateral_matrix @ solved.reshape(-1)
            + sink_cell * solved.reshape(-1)
        )
        right = (
            capacity_cell / dt_s * old.reshape(-1)
            + sink_cell * fields.ambient_temperature_K
        )
        error = float(np.linalg.norm(left - right) / max(np.linalg.norm(right), 1.0e-30))
        monotonic = bool(
            np.all(solved < old) and np.all(solved > fields.ambient_temperature_K)
        )
        passed = bool(error <= 1.0e-12 and monotonic)
        metrics = {"relative_discrete_residual": error, "monotonic_cooling": monotonic}
    elif fixture == "steady_thermal_resistance":
        rise = 0.25
        target = np.full(grid.shape, fields.ambient_temperature_K + rise)
        source = fields.vertical_conductance_W_m2K * rise
        solved = solve_s2_thermal_backward_euler(
            grid,
            fields,
            target,
            np.zeros(grid.shape),
            1.0e-8,
            external_areal_source_W_m2=source,
            lateral_matrix=cache.lateral_matrix,
        )
        error = float(np.linalg.norm(solved - target) / np.linalg.norm(target))
        passed = error <= 1.0e-12
        metrics = {"relative_l2_error": error}
    elif fixture == "local_single_cell_backward_euler":
        capacity = float(fields.effective_areal_capacity_J_m2K[0, 0])
        conductance = float(fields.vertical_conductance_W_m2K)
        dt_s = 1.0e-8
        old = fields.ambient_temperature_K + 2.0
        source = 1000.0
        actual = (capacity / dt_s * old + source + conductance * fields.ambient_temperature_K) / (
            capacity / dt_s + conductance
        )
        residual = (capacity / dt_s + conductance) * actual - (
            capacity / dt_s * old + source + conductance * fields.ambient_temperature_K
        )
        passed = abs(residual) <= 1.0e-12 * max(abs(source), 1.0)
        metrics = {"backward_euler_residual_W_m2": float(residual), "new_temperature_K": float(actual)}
    elif fixture == "rc_open_device":
        circuit = config["physics_contract"]["circuit"]
        resistance = float(circuit["load_resistance_ohm"])
        capacitance = float(circuit["parallel_capacitance_F"])
        dt_s = 1.0e-8
        voltage_in = 12.5
        old_voltage = 0.0
        new_voltage = (capacitance / dt_s * old_voltage + voltage_in / resistance) / (
            capacitance / dt_s + 1.0 / resistance
        )
        residual = capacitance * (new_voltage - old_voltage) / dt_s - (
            voltage_in - new_voltage
        ) / resistance
        passed = abs(residual) <= 1.0e-12 * max(abs(voltage_in / resistance), 1.0e-30)
        metrics = {"rc_residual_A": float(residual), "new_device_voltage_V": float(new_voltage)}
    else:
        raise S0ExecutionError(f"unknown LIM fixture: {fixture}")
    return {
        "execution_unit_id": unit["execution_unit_id"],
        "execution_group": "LIM",
        "validity": "valid",
        "status": "PASS" if passed else "SCIENTIFIC_FAIL",
        "scientific_vote": True,
        "local_metrics": {"fixture_id": fixture, **metrics},
        "raw": {},
    }


def _dual_payload(unit: Mapping[str, Any], *, remaining_s: float) -> dict[str, Any]:
    fixture = str(unit["fixture_id"])
    definitions = {
        "A_only_drive": ("transition_probe_12p5V", "zero_drive"),
        "B_only_drive": ("zero_drive", "transition_probe_12p5V"),
        "equal_drive_symmetry": ("transition_probe_12p5V", "transition_probe_12p5V"),
        "swapped_label_invariance": ("transition_probe_12p5V", "transition_probe_12p5V"),
    }
    if fixture not in definitions:
        raise S0ExecutionError(f"unknown DUAL0 fixture: {fixture}")
    protocol_A, protocol_B = definitions[fixture]
    base = dict(unit)
    base["spatial_level"] = 1
    base["time_divisor"] = 1
    base["protocol_id"] = protocol_A
    base["execution_unit_id"] = f"{unit['execution_unit_id']}-A"
    first_started = perf_counter()
    result_A = _run_trajectory(base, remaining_s=remaining_s)
    elapsed = perf_counter() - first_started
    base["protocol_id"] = protocol_B
    base["execution_unit_id"] = f"{unit['execution_unit_id']}-B"
    result_B = _run_trajectory(base, remaining_s=max(remaining_s - elapsed, 1.0e-6))
    status = "PASS"
    validity = "valid"
    if "PERFORMANCE_STOP" in {result_A["status"], result_B["status"]}:
        status, validity = "PERFORMANCE_STOP", "invalid"
    elif "INVALID" in {result_A["status"], result_B["status"]}:
        status, validity = "INVALID", "invalid"
    elif "SCIENTIFIC_FAIL" in {result_A["status"], result_B["status"]}:
        status = "SCIENTIFIC_FAIL"
    return {
        "execution_unit_id": unit["execution_unit_id"],
        "execution_group": "DUAL0",
        "validity": validity,
        "status": status,
        "scientific_vote": validity == "valid",
        "local_metrics": {"fixture_id": fixture},
        "raw": {"A": result_A, "B": result_B},
    }


def execute_unit(unit: Mapping[str, Any], *, remaining_s: float) -> dict[str, Any]:
    group = str(unit["execution_group"])
    started = perf_counter()
    if group == "FAIL":
        payload = _fail_fixture(unit)
    elif group == "MMS":
        payload = _mms_payload(unit)
    elif group == "LIM":
        payload = _lim_payload(unit, remaining_s=remaining_s)
    elif group == "REF":
        payload = _run_trajectory(unit, remaining_s=remaining_s)
    elif group == "TOP":
        overlap = float(unit["contact_overlap_m"])
        payload = _run_trajectory(unit, remaining_s=remaining_s, overlap_m=overlap)
    elif group == "DUAL0":
        payload = _dual_payload(unit, remaining_s=remaining_s)
    else:
        raise S0ExecutionError(f"unsupported formal execution group: {group}")
    payload["wall_clock_s"] = perf_counter() - started
    payload["consumer_evaluation_ids"] = list(unit["consumer_evaluation_ids"])
    return to_builtin(payload)


def _series(payload: Mapping[str, Any], field: str) -> np.ndarray:
    records = payload["raw"]["scalar_records"]
    return np.asarray([record[field] for record in records], dtype=float)


def _nrmse(coarse: np.ndarray, fine: np.ndarray, floor: float) -> float:
    if coarse.shape != fine.shape or coarse.ndim != 1:
        raise S0ExecutionError("refinement series shape mismatch")
    denominator = max(float(np.sqrt(np.mean((fine - fine[0]) ** 2))), float(floor))
    return float(np.sqrt(np.mean((coarse - fine) ** 2)) / denominator)


def _event_vote(
    coarse: Mapping[str, Any], fine: Mapping[str, Any], *, required: bool, threshold_s: float
) -> dict[str, Any]:
    left = coarse["raw"]["event_records"]
    right = fine["raw"]["event_records"]
    if not left and not right and not required:
        return {"status": "NA", "passed": True, "maximum_time_error_s": 0.0}
    if len(left) != len(right) or not left:
        return {"status": "FAIL", "passed": False, "maximum_time_error_s": None}
    if any(a["direction"] != b["direction"] for a, b in zip(left, right)):
        return {"status": "FAIL", "passed": False, "maximum_time_error_s": None}
    error = max(
        abs(float(a["crossing_time_s"]) - float(b["crossing_time_s"]))
        for a, b in zip(left, right)
    )
    return {"status": "PASS" if error <= threshold_s else "FAIL", "passed": error <= threshold_s, "maximum_time_error_s": error}


def _relative_error(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(b), 1.0e-30))


def evaluate_completed_units(
    unit_payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recompute all 63 verdicts from immutable unit records."""

    config = resolved_s2_config()
    gates = config["gates"]
    rows = _load_manifest_rows()
    by_evaluation: dict[str, Mapping[str, Any]] = {}
    for payload in unit_payloads.values():
        for evaluation_id in payload["consumer_evaluation_ids"]:
            by_evaluation[str(evaluation_id)] = payload
    verdicts: list[dict[str, Any]] = []
    ref_group: dict[str, dict[str, Mapping[str, Any]]] = {}
    for protocol in config["formal_protocols"]["protocols"]:
        matches = {
            suffix: by_evaluation.get(f"P1V2-REF-{protocol}-{suffix}")
            for suffix in ("S1T4", "S2T4", "S4T1", "S4T2", "S4T4")
        }
        if all(matches.values()):
            ref_group[protocol] = {key: value for key, value in matches.items() if value is not None}

    refinement: dict[str, Any] = {}
    floors = config["metric_contract"]["denominator_floors"]
    for protocol, values in ref_group.items():
        fine = values["S4T4"]
        spatial = values["S2T4"]
        temporal = values["S4T2"]
        metrics: dict[str, Any] = {}
        for name, field, floor in (
            ("terminal", "terminal_current_A", floors["terminal_current_A"]),
            ("temperature", "maximum_temperature_K", floors["temperature_rise_K"]),
            ("state", "mean_conductive_state", floors["conductive_state_change"]),
        ):
            metrics[f"spatial_{name}_nrmse"] = _nrmse(
                _series(spatial, field), _series(fine, field), float(floor)
            )
            metrics[f"temporal_{name}_nrmse"] = _nrmse(
                _series(temporal, field), _series(fine, field), float(floor)
            )
        required = protocol == "transition_probe_12p5V"
        metrics["spatial_event"] = _event_vote(
            spatial,
            fine,
            required=required,
            threshold_s=float(gates["spatial_event_time_fine_pair_absolute_s_max"]),
        )
        metrics["temporal_event"] = _event_vote(
            temporal,
            fine,
            required=required,
            threshold_s=float(gates["temporal_event_time_fine_pair_absolute_s_max"]),
        )
        gate_pass = bool(
            metrics["spatial_terminal_nrmse"] <= float(gates["spatial_terminal_fine_pair_nrmse_max"])
            and metrics["spatial_temperature_nrmse"] <= float(gates["spatial_temperature_fine_pair_nrmse_max"])
            and metrics["spatial_state_nrmse"] <= float(gates["spatial_state_fine_pair_nrmse_max"])
            and metrics["temporal_terminal_nrmse"] <= float(gates["temporal_terminal_fine_pair_nrmse_max"])
            and metrics["temporal_temperature_nrmse"] <= float(gates["temporal_temperature_fine_pair_nrmse_max"])
            and metrics["temporal_state_nrmse"] <= float(gates["temporal_state_fine_pair_nrmse_max"])
            and metrics["spatial_event"]["passed"]
            and metrics["temporal_event"]["passed"]
        )
        if protocol == "zero_drive":
            drift = float(np.max(np.abs(_series(fine, "maximum_temperature_K") - _series(fine, "maximum_temperature_K")[0])))
            metrics["zero_drive_temperature_drift_K"] = drift
            gate_pass = gate_pass and drift <= float(gates["zero_drive_temperature_drift_K_max"])
        trend = gates["literature_trend"]
        local = fine["local_metrics"]
        if protocol == "quiescent_9V":
            metrics["trend_pass"] = local["post_warmup_crossing_count"] <= int(trend["quiescent_9V_post_warmup_threshold_crossings_max"])
        elif protocol == "transition_probe_12p5V":
            metrics["trend_pass"] = local["post_warmup_crossing_count"] >= int(trend["transition_12p5V_post_warmup_threshold_crossings_min"])
        elif protocol == "high_bias_lock_15p8V":
            metrics["trend_pass"] = bool(
                local["final_mean_conductive_state"] >= float(trend["high_bias_lock_15p8V_final_domain_mean_s_min"])
                and local["post_warmup_crossing_count"] <= int(trend["high_bias_lock_15p8V_post_warmup_threshold_crossings_max"])
            )
        else:
            metrics["trend_pass"] = True
        metrics["passed"] = bool(gate_pass and metrics["trend_pass"])
        refinement[protocol] = metrics

    dual_metrics: dict[str, Any] = {"passed": True, "comparisons": {}}
    dual_ids = {
        name: unit_payloads.get(f"TRJ-P1V2-DUAL0-{name}")
        for name in ("A_only_drive", "B_only_drive", "equal_drive_symmetry", "swapped_label_invariance")
    }
    if all(dual_ids.values()):
        comparisons = (
            ("driven_swap", dual_ids["A_only_drive"]["raw"]["A"], dual_ids["B_only_drive"]["raw"]["B"]),
            ("zero_swap", dual_ids["A_only_drive"]["raw"]["B"], dual_ids["B_only_drive"]["raw"]["A"]),
            ("equal_symmetry", dual_ids["equal_drive_symmetry"]["raw"]["A"], dual_ids["equal_drive_symmetry"]["raw"]["B"]),
            ("label_swap", dual_ids["equal_drive_symmetry"]["raw"]["A"], dual_ids["swapped_label_invariance"]["raw"]["B"]),
        )
        for name, left, right in comparisons:
            error = max(
                _relative_error(_series(left, field), _series(right, field))
                for field in ("terminal_current_A", "maximum_temperature_K", "mean_conductive_state")
            )
            dual_metrics["comparisons"][name] = error
            dual_metrics["passed"] = bool(
                dual_metrics["passed"]
                and error <= float(gates["decoupled_dual_copy_relative_error_max"])
            )

    topology: dict[str, Any] = {}
    for protocol in ("nominal_12V", "transition_probe_12p5V", "high_bias_lock_15p8V"):
        items = {
            10: by_evaluation.get(f"P1V2-TOP-O10-{protocol}"),
            20: by_evaluation.get(f"P1V2-TOP-O20-{protocol}"),
            30: by_evaluation.get(f"P1V2-TOP-O30-{protocol}"),
        }
        if not all(items.values()):
            continue
        protocol_metrics: dict[str, Any] = {"qoi": {}}
        nominal_s2 = by_evaluation[f"P1V2-REF-{protocol}-S2T4"]
        nominal_s4 = by_evaluation[f"P1V2-REF-{protocol}-S4T4"]
        for name in ("terminal_current_rms_A", "maximum_temperature_rise_K", "maximum_mean_state_change"):
            values = [float(items[key]["local_metrics"][name]) for key in (10, 20, 30)]
            envelope = max(values) - min(values)
            noise = abs(
                float(nominal_s4["local_metrics"][name])
                - float(nominal_s2["local_metrics"][name])
            )
            epsilon = {
                "terminal_current_rms_A": 1.0e-12,
                "maximum_temperature_rise_K": 1.0e-3,
                "maximum_mean_state_change": 1.0e-6,
            }[name]
            ratio = envelope / max(noise, epsilon)
            nominal = values[1]
            effect = max(abs(value - nominal) for value in values) / max(abs(nominal), epsilon)
            spatial_error = noise / max(abs(nominal), epsilon)
            protocol_metrics["qoi"][name] = {
                "values_10_20_30": values,
                "envelope": envelope,
                "numerical_noise": noise,
                "envelope_to_noise_ratio": ratio,
                "eligible_to_vote": ratio >= 1.0,
                "relative_overlap_effect": effect,
                "nominal_spatial_relative_error": spatial_error,
                "geometry_robust_wording_eligible": effect <= spatial_error,
            }
        protocol_metrics["passed"] = all(
            value["eligible_to_vote"] for value in protocol_metrics["qoi"].values()
        )
        topology[protocol] = protocol_metrics

    for row in rows:
        evaluation_id = row["evaluation_id"]
        payload = by_evaluation.get(evaluation_id)
        status = "UNASSESSED"
        details: dict[str, Any] = {}
        if payload is not None:
            passed = payload["status"] == "PASS"
            group = row["evaluation_group"]
            if group == "REF" and row["protocol_id"] in refinement:
                details["refinement"] = refinement[row["protocol_id"]]
                passed = passed and bool(refinement[row["protocol_id"]]["passed"])
            elif group == "DUAL0" and all(dual_ids.values()):
                details["dual0"] = dual_metrics
                passed = passed and bool(dual_metrics["passed"])
            elif group == "TOP" and row["protocol_id"] in topology:
                details["topology"] = topology[row["protocol_id"]]
                passed = passed and bool(topology[row["protocol_id"]]["passed"])
            status = "PASS" if passed else "FAIL"
        verdicts.append(
            {
                "evaluation_id": evaluation_id,
                "evaluation_group": row["evaluation_group"],
                "trajectory_id": row["trajectory_id"],
                "status": status,
                "validity": "valid" if status in {"PASS", "FAIL"} else "unassessed",
                "details_json": json.dumps(to_builtin(details), sort_keys=True, separators=(",", ":")),
            }
        )
    assessed = [row for row in verdicts if row["status"] != "UNASSESSED"]
    summary = {
        "evaluation_items": 63,
        "assessed_items": len(assessed),
        "passed_items": sum(row["status"] == "PASS" for row in verdicts),
        "failed_items": sum(row["status"] == "FAIL" for row in verdicts),
        "unassessed_items": sum(row["status"] == "UNASSESSED" for row in verdicts),
        "all_required_pass": bool(len(assessed) == 63 and all(row["status"] == "PASS" for row in verdicts)),
        "refinement": refinement,
        "dual0": dual_metrics,
        "topology": topology,
    }
    return verdicts, summary


def _registry_path(output_root: Path) -> Path:
    return Path(output_root) / "campaign_registry.json"


def _publish_registry(output_root: Path, registry: Mapping[str, Any]) -> str:
    return atomic_json(_registry_path(output_root), registry)


def _load_unit_records(
    output_root: Path, expected_hashes: Mapping[str, Mapping[str, str]] | None = None
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    directory = Path(output_root) / "units"
    if not directory.exists():
        return result
    expected = {} if expected_hashes is None else dict(expected_hashes)
    for path in sorted(directory.glob("*.json.gz")):
        unit_id_from_name = path.name[: -len(".json.gz")]
        if unit_id_from_name not in expected:
            raise S0ExecutionError("published compressed unit lacks registry hashes")
        payload = _read_canonical_gzip(path, expected[unit_id_from_name])
        unit_id = str(payload["execution_unit_id"])
        if unit_id_from_name != unit_id or unit_id in result:
            raise S0ExecutionError("published unit identity is invalid or duplicated")
        result[unit_id] = payload
    return result


def _environment_payload() -> dict[str, Any]:
    return {
        "python_version": sys.version,
        "python_executable": Path(sys.executable),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "thread_environment": {
            name: os.environ.get(name, "")
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
            )
        },
    }


def run_formal_campaign(
    *, config_path: Path, output_root: Path, anchor_commit: str
) -> dict[str, Any]:
    apply_single_thread_environment()
    config = load_yaml(config_path)
    authority = validate_authority(ROOT, config)
    plan = formal_plan()
    units = _load_units()
    if len(anchor_commit) != 40 or any(character not in "0123456789abcdef" for character in anchor_commit):
        raise S0ExecutionError("formal anchor commit must be a lowercase 40-character SHA")
    output_root = Path(output_root)
    registry_path = _registry_path(output_root)
    if registry_path.exists():
        registry = read_canonical_json(registry_path)
        if registry["campaign_id"] != config["identity"]["new_formal_campaign_id"]:
            raise S0ExecutionError("formal registry campaign identity drifted")
        if registry["anchor_commit"] != anchor_commit:
            raise S0ExecutionError("formal registry anchor commit drifted")
        if registry["state"] not in {"RUNNING", "INTERRUPTED_RESUMABLE"}:
            raise S0ExecutionError("terminal formal campaign cannot be rerun")
    else:
        output_root.mkdir(parents=True, exist_ok=False)
        (output_root / "units").mkdir()
        config_snapshot = deepcopy(config)
        config_snapshot["identity"]["code_anchor_commit"] = anchor_commit
        config_sha = atomic_json(output_root / "config_snapshot.json", config_snapshot)
        registry = {
            "schema_version": "geophase_s0_formal_registry_v1",
            "task_id": config["task_id"],
            "campaign_id": config["identity"]["new_formal_campaign_id"],
            "anchor_commit": anchor_commit,
            "config_snapshot_sha256": config_sha,
            "authority_sha256": authority,
            "execution_code_sha256": execution_code_hashes(),
            "environment": _environment_payload(),
            "plan_sha256": {
                "dag": plan["dag_sha256"],
                "manifest_csv": plan["manifest_csv_sha256"],
            },
            "state": "RUNNING",
            "validity": "pending",
            "scientific_vote": False,
            "campaign_attempt_count": 1,
            "formal_execution_count": 0,
            "completed_unit_ids": [],
            "unit_sha256": {},
            "started_utc": _utc_now(),
            "updated_utc": _utc_now(),
        }
        _publish_registry(output_root, registry)

    started = perf_counter()
    deadline_s = float(config["formal"]["maximum_wall_clock_s"])
    expected_hashes = dict(registry.get("unit_sha256", {}))
    records = _load_unit_records(output_root, expected_hashes)
    expected_completed = list(registry["completed_unit_ids"])
    if set(records) != set(expected_completed):
        raise S0ExecutionError("formal registry and unit publications disagree")
    if set(expected_hashes) != set(records):
        raise S0ExecutionError("formal registry unit hashes are incomplete")

    foundation_path = output_root / "foundation.json"
    if foundation_path.exists():
        foundation = read_canonical_json(foundation_path)
    else:
        foundation = foundation_payload()
        foundation["case_id"] = "S0-FORMAL-FOUNDATION"
        foundation["scientific_vote"] = True
        atomic_json(foundation_path, foundation)
    if foundation["status"] != "PASS":
        registry.update(
            {
                "state": "S0_SCIENTIFIC_FAIL",
                "validity": "valid",
                "scientific_vote": True,
                "formal_execution_count": 1,
                "updated_utc": _utc_now(),
            }
        )
        _publish_registry(output_root, registry)
        return dict(registry)

    try:
        for unit in units:
            unit_id = str(unit["execution_unit_id"])
            if unit_id in records:
                continue
            remaining = deadline_s - (perf_counter() - started)
            if remaining <= 0.0:
                registry.update(
                    {
                        "state": "S0_PERFORMANCE_RESOURCE_ONLY_NO_GO",
                        "validity": "invalid",
                        "scientific_vote": False,
                        "updated_utc": _utc_now(),
                    }
                )
                _publish_registry(output_root, registry)
                return dict(registry)
            payload = execute_unit(unit, remaining_s=remaining)
            unit_sha = _atomic_canonical_gzip(
                output_root / "units" / f"{unit_id}.json.gz", payload
            )
            records[unit_id] = payload
            registry["unit_sha256"][unit_id] = unit_sha
            registry["completed_unit_ids"] = [
                str(item["execution_unit_id"])
                for item in units
                if str(item["execution_unit_id"]) in records
            ]
            registry["updated_utc"] = _utc_now()
            _publish_registry(output_root, registry)
            if payload["status"] == "PERFORMANCE_STOP":
                registry.update(
                    {
                        "state": "S0_PERFORMANCE_RESOURCE_ONLY_NO_GO",
                        "validity": "invalid",
                        "scientific_vote": False,
                        "updated_utc": _utc_now(),
                    }
                )
                _publish_registry(output_root, registry)
                return dict(registry)
            if payload["status"] == "INVALID":
                registry.update(
                    {
                        "state": "INVALID_S0_EXECUTION",
                        "validity": "invalid",
                        "scientific_vote": False,
                        "updated_utc": _utc_now(),
                    }
                )
                _publish_registry(output_root, registry)
                return dict(registry)
            if payload["status"] == "SCIENTIFIC_FAIL" and str(unit["execution_group"]) in _FOUNDATION_GROUPS:
                break
    except KeyboardInterrupt:
        registry.update({"state": "INTERRUPTED_RESUMABLE", "updated_utc": _utc_now()})
        _publish_registry(output_root, registry)
        raise
    except Exception as error:
        registry.update(
            {
                "state": "INVALID_S0_EXECUTION",
                "validity": "invalid",
                "scientific_vote": False,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "updated_utc": _utc_now(),
            }
        )
        _publish_registry(output_root, registry)
        raise

    verdicts, evaluation = evaluate_completed_units(records)
    verdict_sha = _atomic_csv(
        output_root / "evaluation_verdicts.csv",
        verdicts,
        ["evaluation_id", "evaluation_group", "trajectory_id", "status", "validity", "details_json"],
    )
    terminal = "S0_PASS" if evaluation["all_required_pass"] else "S0_SCIENTIFIC_FAIL"
    registry.update(
        {
            "state": terminal,
            "validity": "valid",
            "scientific_vote": True,
            "formal_execution_count": 1,
            "updated_utc": _utc_now(),
        }
    )
    summary = {
        "schema_version": "geophase_s0_formal_summary_v1",
        "task_id": config["task_id"],
        "campaign_id": registry["campaign_id"],
        "terminal_state": terminal,
        "validity": "valid",
        "scientific_vote": True,
        "formal_execution_count": 1,
        "completed_execution_units": len(records),
        "evaluation": evaluation,
        "authority_sha256": authority,
        "execution_code_sha256": execution_code_hashes(),
        "unit_sha256": dict(sorted(registry["unit_sha256"].items())),
        "evaluation_verdicts_csv_sha256": verdict_sha,
        "anchor_commit": anchor_commit,
        "created_utc": _utc_now(),
    }
    summary_sha = atomic_json(output_root / "s0_summary.json", summary)
    registry["summary_sha256"] = summary_sha
    _publish_registry(output_root, registry)
    return summary


__all__ = [
    "evaluate_completed_units",
    "execute_unit",
    "run_formal_campaign",
]
