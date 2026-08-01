"""Thin real-path S0 execution utilities.

This module is a fresh direct-physics path.  It calls the production S2 FVM
solver and controller directly and deliberately does not import historical E0,
readiness, or equivalence runners.  It owns one recursive JSON boundary and
small atomic evidence writes; scientific gates remain in the frozen S2 config.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping
from uuid import uuid4

import numpy as np
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    derive_nominal_s2_source_scale,
    effective_vo2_closure_from_v2_config,
    s2_uniform_mode_identities,
)
from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    attempt_s2_embedded_interval,
    controller_v2_limits,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import solve_s2_thermal_backward_euler
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    initial_s2_state,
)
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    resolve_controller_v2,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import run_s2_streaming_protocol_v2


ROOT = Path(__file__).resolve().parents[3]
S2_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
CONTROLLER_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml"
)
FORMAL_MANIFEST_CSV = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "formal_evaluation_manifest.csv"
)
EXECUTION_DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "runtime_readiness"
    / "execution_dag.json"
)
EXECUTION_SOURCE_PATHS = (
    ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_s0_direct_physics.py",
    ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_s0_formal.py",
    ROOT / "scripts" / "run_geophase_s0_direct_physics.py",
)

_THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


class S0ExecutionError(RuntimeError):
    """Raised when the fresh S0 execution boundary is invalid."""


def apply_single_thread_environment() -> None:
    for name, value in _THREAD_ENVIRONMENT.items():
        os.environ[name] = value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise S0ExecutionError(f"{path} must contain a YAML mapping")
    return payload


def to_builtin(value: Any) -> Any:
    """Recursively convert an execution payload to strict JSON builtins.

    NaN and infinities fail closed.  Mapping keys must already be strings so
    canonical ordering cannot silently change an identity.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise S0ExecutionError("nonfinite floating value at JSON boundary")
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        converted = float(value)
        if not math.isfinite(converted):
            raise S0ExecutionError("nonfinite NumPy floating value at JSON boundary")
        return converted
    if isinstance(value, np.ndarray):
        if value.dtype.kind in {"f", "c"} and not np.isfinite(value).all():
            raise S0ExecutionError("nonfinite ndarray at JSON boundary")
        if value.dtype.kind == "c":
            raise S0ExecutionError("complex ndarray requires an explicit representation")
        return to_builtin(value.tolist())
    if isinstance(value, Path):
        return value.as_posix()
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_builtin(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise S0ExecutionError("JSON mapping key must be a string")
            converted[key] = to_builtin(item)
        return converted
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    raise S0ExecutionError(f"unsupported JSON boundary type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    builtin = to_builtin(value)
    return (
        json.dumps(
            builtin,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def atomic_json(path: Path, payload: Any) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_bytes(payload)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if hashlib.sha256(temporary.read_bytes()).digest() != hashlib.sha256(content).digest():
        temporary.unlink(missing_ok=True)
        raise S0ExecutionError("atomic JSON temporary hash mismatch")
    os.replace(temporary, destination)
    return hashlib.sha256(content).hexdigest()


def read_canonical_json(path: Path, expected_sha256: str | None = None) -> Any:
    content = Path(path).read_bytes()
    observed = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None and observed != expected_sha256:
        raise S0ExecutionError(f"published JSON hash mismatch: {path}")
    payload = json.loads(content)
    if canonical_bytes(payload) != content:
        raise S0ExecutionError(f"published JSON is not canonical: {path}")
    return payload


def validate_authority(root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for item in config["authority"]["files"]:
        relative = str(item["path"])
        path = Path(root) / relative
        if not path.is_file():
            raise S0ExecutionError(f"authority file is missing: {relative}")
        digest = sha256_file(path)
        if digest != str(item["sha256"]):
            raise S0ExecutionError(f"authority hash drifted: {relative}")
        observed[relative] = digest
    return observed


def execution_code_hashes() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): sha256_file(path)
        for path in EXECUTION_SOURCE_PATHS
    }


def resolved_s2_config() -> dict[str, Any]:
    resolved = resolve_controller_v2(S2_CONFIG_PATH, CONTROLLER_PATH)
    config = resolved.resolved_config
    if int(config["execution_contract"]["formal_execution_count"]) != 0:
        raise S0ExecutionError("frozen S2 config formal count drifted")
    return config


def _context(
    spatial_level: int, *, contact_overlap_m: float | None = None
) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    config = resolved_s2_config()
    grid = build_geophase_grid(
        config,
        spatial_level=spatial_level,
        contact_overlap_m=contact_overlap_m,
    )
    thermal = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    cache = build_s2_solver_cache(grid, thermal)
    return grid, thermal, closure, cache, config


def _critical_state(grid: Any, closure: Any) -> S2State:
    temperature = np.full(grid.shape, float(closure.T_c_up_K), dtype=float)
    return S2State(
        time_s=0.0,
        temperature_K=temperature,
        conductive_state=np.full(grid.shape, 0.5, dtype=float),
        branch_memory=np.ones(grid.shape, dtype=float),
        device_voltage_V=0.0,
    )


def _integrity_payload(observation: Any) -> dict[str, Any]:
    diagnostics = observation.diagnostics
    return {
        "accepted": diagnostics.accepted,
        "outer_interval_s": diagnostics.outer_interval_s,
        "embedded_error": diagnostics.embedded_error,
        "full_step": diagnostics.full_step,
        "first_half_step": diagnostics.first_half_step,
        "second_half_step": diagnostics.second_half_step,
        "aggregate": diagnostics.aggregate,
        "error_class": observation.error_class,
        "error_message": observation.error_message,
    }


def foundation_payload() -> dict[str, Any]:
    config = resolved_s2_config()
    grid, thermal, closure, cache, _ = _context(1)
    scale = derive_nominal_s2_source_scale(config)
    identities = s2_uniform_mode_identities(grid, thermal)
    gates = config["gates"]
    source_gates = config["analytic_source_scale_preflights"]

    sigma = np.full(grid.shape, 12.0, dtype=float)
    electrical = solve_sheet_electrical(grid, sigma, 1.0)
    expected_1d = 1.0 - grid.x_centers_m / grid.x_edges_m[-1]
    expected = np.broadcast_to(expected_1d[None, :], grid.shape)
    electrical_l2 = float(
        np.linalg.norm(electrical.potential_V - expected)
        / max(np.linalg.norm(expected), 1.0e-30)
    )
    exact_current = 12.0 * grid.thickness_m * grid.y_edges_m[-1] / grid.x_edges_m[-1]
    current_error = abs(electrical.source_current_A - exact_current) / exact_current

    dt_s = 1.0e-8
    delta_K = 1.0e-2
    old_temperature = np.full(grid.shape, thermal.ambient_temperature_K)
    target_temperature = old_temperature + delta_K
    source = (
        thermal.effective_areal_capacity_J_m2K * delta_K / dt_s
        + thermal.vertical_conductance_W_m2K * delta_K
    )
    solved_temperature = solve_s2_thermal_backward_euler(
        grid,
        thermal,
        old_temperature,
        np.zeros(grid.shape),
        dt_s,
        external_areal_source_W_m2=source,
    )
    thermal_l2 = float(
        np.linalg.norm(solved_temperature - target_temperature)
        / max(np.linalg.norm(target_temperature), 1.0e-30)
    )
    equilibrium = initial_s2_state(grid, closure, thermal, config)
    zero_protocol = config["formal_protocols"]["protocols"]["zero_drive"]
    _, floor = controller_v2_limits(config, 1)
    step = attempt_s2_embedded_interval(
        equilibrium,
        protocol=zero_protocol,
        protocol_id="zero_drive",
        outer_interval_s=floor,
        grid=grid,
        closure=closure,
        fields=thermal,
        config=config,
        at_outer_floor=True,
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
    )
    interval = _integrity_payload(step)
    checks = {
        "source_memory_coefficient_positive": scale["nominal_memory_coefficient_J_K"] > 0.0,
        "uniform_capacity_identity": identities["capacity_relative_error"]
        <= float(source_gates["area_integrated_explicit_plus_memory_coefficient_relative_error_max"]),
        "uniform_conductance_identity": identities["conductance_relative_error"]
        <= float(source_gates["area_integrated_dc_thermal_conductance_relative_error_max"]),
        "manufactured_electrical": electrical_l2
        <= float(gates["manufactured_electrical_relative_l2_max"]),
        "analytic_current": current_error
        <= float(source_gates["uniform_insulating_resistance_relative_error_max"]),
        "terminal_current_balance": electrical.relative_current_imbalance
        <= float(gates["terminal_current_relative_imbalance_max"]),
        "device_power_identity": electrical.relative_power_imbalance
        <= float(gates["device_power_identity_relative_residual_max"]),
        "manufactured_thermal": thermal_l2
        <= float(gates["manufactured_thermal_relative_l2_max"]),
        "zero_interval_accepted": bool(step.step is not None and step.diagnostics.accepted),
        "zero_interval_integrity": bool(
            step.diagnostics.full_step.overall_pass
            and step.diagnostics.first_half_step is not None
            and step.diagnostics.first_half_step.overall_pass
            and step.diagnostics.second_half_step is not None
            and step.diagnostics.second_half_step.overall_pass
            and step.diagnostics.aggregate is not None
            and step.diagnostics.aggregate.overall_pass
        ),
    }
    return {
        "case_id": "S0-SMOKE-FOUNDATION",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "metrics": {
            "manufactured_electrical_relative_l2": electrical_l2,
            "analytic_current_relative_error": current_error,
            "manufactured_thermal_relative_l2": thermal_l2,
            "terminal_current_relative_imbalance": electrical.relative_current_imbalance,
            "device_power_relative_imbalance": electrical.relative_power_imbalance,
        },
        "real_interval": interval,
        "scientific_vote": False,
    }


def interval_payload(*, state_id: str) -> dict[str, Any]:
    grid, thermal, closure, cache, config = _context(1)
    if state_id == "equilibrium":
        state = initial_s2_state(grid, closure, thermal, config)
        protocol_id = "zero_drive"
        maximum, _ = controller_v2_limits(config, 1)
        interval_s = maximum
    elif state_id == "legal_critical":
        state = _critical_state(grid, closure)
        protocol_id = "transition_probe_12p5V"
        _, interval_s = controller_v2_limits(config, 1)
    else:
        raise ValueError("undeclared S0 smoke state")
    protocol = config["formal_protocols"]["protocols"][protocol_id]
    observation = attempt_s2_embedded_interval(
        state,
        protocol=protocol,
        protocol_id=protocol_id,
        outer_interval_s=interval_s,
        grid=grid,
        closure=closure,
        fields=thermal,
        config=config,
        at_outer_floor=state_id == "legal_critical",
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
    )
    integrity = _integrity_payload(observation)
    passed = bool(
        observation.step is not None
        and observation.diagnostics.accepted
        and observation.diagnostics.full_step.overall_pass
        and observation.diagnostics.first_half_step is not None
        and observation.diagnostics.first_half_step.overall_pass
        and observation.diagnostics.second_half_step is not None
        and observation.diagnostics.second_half_step.overall_pass
        and observation.diagnostics.aggregate is not None
        and observation.diagnostics.aggregate.overall_pass
    )
    return {
        "case_id": f"S0-SMOKE-{state_id.upper().replace('_', '-')}-INTERVAL",
        "state_id": state_id,
        "protocol_id": protocol_id,
        "status": "PASS" if passed else "FAIL",
        "integrity": integrity,
        "scientific_vote": False,
    }


def short_trajectory_payload(final_time_s: float) -> dict[str, Any]:
    grid, thermal, closure, cache, config = _context(1)
    state = _critical_state(grid, closure)
    protocol_id = "transition_probe_12p5V"
    protocol = config["formal_protocols"]["protocols"][protocol_id]
    result = run_s2_streaming_protocol_v2(
        "S0-SMOKE-LEGAL-CRITICAL-TRAJECTORY",
        state,
        protocol=protocol,
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=thermal,
        config=config,
        final_time_s=float(final_time_s),
        maximum_wall_clock_s=1800.0,
        retain_full_history=True,
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
    )
    diagnostics = result.protocol_result.diagnostics
    history = tuple(result.protocol_result.steps)
    integrity = bool(
        history
        and all(
            step.controller.full_step.overall_pass
            and step.controller.first_half_step is not None
            and step.controller.first_half_step.overall_pass
            and step.controller.second_half_step is not None
            and step.controller.second_half_step.overall_pass
            and step.controller.aggregate is not None
            and step.controller.aggregate.overall_pass
            for step in history
        )
    )
    passed = bool(result.protocol_result.completed and diagnostics.accepted_steps > 0 and integrity)
    return {
        "case_id": result.case_id,
        "status": "PASS" if passed else "FAIL",
        "protocol_id": protocol_id,
        "protocol_result": {
            "completed": result.protocol_result.completed,
            "stop_reason": result.protocol_result.stop_reason,
            "achieved_final_time_s": result.protocol_result.achieved_final_time_s,
            "diagnostics": diagnostics,
        },
        "scalar_records": result.scalar_records,
        "event_records": result.event_records,
        "reversal_records": result.reversal_records,
        "field_snapshots": result.field_snapshots,
        "accepted_history_integrity": integrity,
        "scientific_vote": False,
    }


def formal_plan() -> dict[str, Any]:
    dag = json.loads(EXECUTION_DAG_PATH.read_text(encoding="utf-8"))
    units = dag.get("execution_units")
    if not isinstance(units, list) or len(units) != 60:
        raise S0ExecutionError("execution DAG must contain exactly 60 units")
    identifiers = [str(item["execution_unit_id"]) for item in units]
    if len(set(identifiers)) != 60:
        raise S0ExecutionError("execution DAG contains duplicate units")
    consumers = [str(value) for item in units for value in item["consumer_evaluation_ids"]]
    if len(consumers) != 63 or len(set(consumers)) != 63:
        raise S0ExecutionError("execution DAG must cover 63 unique evaluations")
    reused = sum(max(0, len(item["consumer_evaluation_ids"]) - 1) for item in units)
    if reused != 3:
        raise S0ExecutionError("execution DAG must contain exactly three legal reuses")
    return {
        "evaluation_items": len(consumers),
        "execution_units": len(units),
        "legal_reuses": reused,
        "unit_ids": identifiers,
        "dag_sha256": sha256_file(EXECUTION_DAG_PATH),
        "manifest_csv_sha256": sha256_file(FORMAL_MANIFEST_CSV),
    }


def recompute_smoke_status(case_payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    expected = {
        "S0-SMOKE-FOUNDATION",
        "S0-SMOKE-EQUILIBRIUM-INTERVAL",
        "S0-SMOKE-LEGAL-CRITICAL-INTERVAL",
        "S0-SMOKE-LEGAL-CRITICAL-TRAJECTORY",
    }
    if set(case_payloads) != expected:
        raise S0ExecutionError("smoke case coverage changed")
    statuses = {case_id: str(payload["status"]) for case_id, payload in case_payloads.items()}
    return {
        "terminal_state": "PASS" if all(value == "PASS" for value in statuses.values()) else "FAIL",
        "case_status": statuses,
        "completed_cases": len(statuses),
        "scientific_vote": False,
    }


def run_real_smoke(*, config_path: Path, output_root: Path) -> dict[str, Any]:
    apply_single_thread_environment()
    config = load_yaml(config_path)
    authority = validate_authority(ROOT, config)
    smoke = config["smoke"]
    started = perf_counter()
    cases = (
        foundation_payload(),
        interval_payload(state_id="equilibrium"),
        interval_payload(state_id="legal_critical"),
        short_trajectory_payload(float(smoke["short_trajectory_final_time_s"])),
    )
    if perf_counter() - started > float(config["budgets"]["smoke_wall_clock_s"]):
        raise S0ExecutionError("real payload smoke exceeded its wall-clock budget")
    case_hashes: dict[str, str] = {}
    loaded: dict[str, Mapping[str, Any]] = {}
    for payload in cases:
        case_id = str(payload["case_id"])
        path = output_root / "cases" / f"{case_id}.json"
        digest = atomic_json(path, payload)
        case_hashes[case_id] = digest
        loaded[case_id] = read_canonical_json(path, digest)
    recomputed = recompute_smoke_status(loaded)
    summary = {
        "schema_version": "geophase_s0_real_payload_smoke_v1",
        "task_id": config["task_id"],
        "run_id": config["identity"]["new_smoke_run_id"],
        "terminal_state": recomputed["terminal_state"],
        "validity": "valid" if recomputed["terminal_state"] == "PASS" else "invalid",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "case_hashes": case_hashes,
        "case_status": recomputed["case_status"],
        "completed_cases": recomputed["completed_cases"],
        "authority_sha256": authority,
        "execution_code_sha256": execution_code_hashes(),
        "formal_plan": formal_plan(),
        "wall_clock_s": perf_counter() - started,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    atomic_json(output_root / "smoke_summary.json", summary)
    return summary


__all__ = [
    "S0ExecutionError",
    "atomic_json",
    "canonical_bytes",
    "canonical_sha256",
    "execution_code_hashes",
    "formal_plan",
    "read_canonical_json",
    "recompute_smoke_status",
    "run_real_smoke",
    "to_builtin",
    "validate_authority",
]
