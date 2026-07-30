"""Task adapter for the source-corrected Phase 1-v2 readiness closure.

This module is deliberately non-formal.  It resolves only the preregistered
source-corrected controller-v2 contract, exposes the narrow hook surface used
by the locked readiness runner, and never creates a formal run identifier.
The final equivalence audit is implemented separately; asking this adapter to
run it before that wiring exists fails closed.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Any, Mapping

import numpy as np

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    attempt_s2_embedded_interval,
    controller_v2_limits,
)
from pinnpcm.solvers.geophase_phase1_v2_formal_runner import (
    InvalidContractError,
    begin_running,
    complete_pass,
    create_partial_case_work,
    create_prepared_registry,
    interrupt_resumable,
    load_registry,
    publish_synthetic_case,
    record_foundation_failure,
    resume_same_run,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    PERFORMANCE_TIMING_SEMANTICS,
    S2PerformanceTimings,
    S2State,
    build_s2_solver_cache,
)
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    build_campaign_cost_forecast,
    measure_launch_environment as _measure_runtime_environment,
    process_memory,
)
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    resolve_controller_v2,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import (
    publish_pre_streaming_case,
    published_case_bytes,
    run_s2_streaming_protocol_v2,
)


ROOT = Path(__file__).resolve().parents[3]
BASE_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
OVERLAY_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml"
)
EXECUTION_DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "runtime_readiness"
    / "execution_dag.json"
)
RUNTIME_IDENTITY_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "resolved_runtime_identity.json"
)
FORMAL_MANIFEST_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml"
)
EXECUTION_ADDENDUM_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml"
)
EXPANDED_MANIFEST_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "formal_evaluation_manifest.json"
)

_PROTOCOL_BY_STATE = {
    "equilibrium": "zero_drive",
    "legal_critical": "transition_probe_12p5V",
    "high_conductive": "high_bias_lock_15p8V",
}
_PROTOCOL_SCALE_V = {
    "zero_drive": 1.0,
    "transition_probe_12p5V": 12.5,
    "high_bias_lock_15p8V": 15.8,
}
_ALLOWED_LEVELS = {1, 2, 4}
_TIMING_FIELDS = tuple(S2PerformanceTimings.__dataclass_fields__)
_THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
_READINESS_CONTEXT: dict[str, Any] = {}
_LAUNCH_ENVIRONMENT: dict[str, Any] | None = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: Any, label: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return text


def _apply_single_thread_environment() -> None:
    for name, value in _THREAD_ENVIRONMENT.items():
        os.environ[name] = value


@lru_cache(maxsize=1)
def _resolved_config() -> dict[str, Any]:
    resolved = resolve_controller_v2(BASE_CONFIG_PATH, OVERLAY_PATH)
    config = resolved.resolved_config
    mapping = config["reference_solver"]["active_time_controller"]["voltage_scale"]
    observed = {
        key: float(mapping["protocol_V_scale_V"][key])
        for key in _PROTOCOL_SCALE_V
    }
    if observed != _PROTOCOL_SCALE_V:
        raise RuntimeError("source-corrected readiness voltage-scale mapping drifted")
    protocols = config["formal_protocols"]["protocols"]
    if "high_bias_15V" in protocols or "high_bias_lock_15p8V" not in protocols:
        raise RuntimeError("active source-corrected protocol namespace is invalid")
    if int(config["execution_contract"]["formal_execution_count"]) != 0:
        raise RuntimeError("source-corrected readiness cannot consume formal execution")
    return config


def _context(level: int) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    if level not in _ALLOWED_LEVELS:
        raise ValueError("source-corrected readiness level must be L1, L2, or L4")
    config = _resolved_config()
    grid = build_geophase_grid(config, spatial_level=level)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    cache = build_s2_solver_cache(grid, fields)
    return grid, fields, closure, cache, config


def _deterministic_state(
    state_id: str, *, grid: Any, fields: Any, closure: Any
) -> S2State:
    if state_id == "equilibrium":
        temperature = np.full(grid.shape, float(fields.ambient_temperature_K))
        branch = np.ones(grid.shape, dtype=float)
        conductive = closure.equilibrium_state(temperature, branch)
    elif state_id == "legal_critical":
        temperature = np.full(grid.shape, float(closure.T_c_up_K))
        branch = np.ones(grid.shape, dtype=float)
        conductive = np.full(grid.shape, 0.5, dtype=float)
    elif state_id == "high_conductive":
        temperature = np.full(grid.shape, 380.0, dtype=float)
        branch = np.ones(grid.shape, dtype=float)
        conductive = closure.equilibrium_state(temperature, branch)
    else:
        raise ValueError("undeclared source-corrected readiness state")
    return S2State(
        time_s=0.0,
        temperature_K=temperature,
        conductive_state=conductive,
        branch_memory=branch,
        device_voltage_V=0.0,
    )


def _protocol_identity(state_id: str, config: dict[str, Any]) -> tuple[str, dict, float]:
    if state_id not in _PROTOCOL_BY_STATE:
        raise ValueError("undeclared source-corrected readiness state")
    protocol_id = _PROTOCOL_BY_STATE[state_id]
    scale = _PROTOCOL_SCALE_V[protocol_id]
    configured_scale = float(
        config["reference_solver"]["active_time_controller"]["voltage_scale"]
        ["protocol_V_scale_V"][protocol_id]
    )
    if configured_scale != scale:
        raise RuntimeError("fixed readiness voltage scale changed")
    return protocol_id, config["formal_protocols"]["protocols"][protocol_id], scale


@lru_cache(maxsize=1)
def _legacy_parity_helpers() -> Any:
    """Load only pure parity helpers from the historical readiness runner."""

    path = ROOT / "scripts" / "run_geophase_phase1_v2_embedded_controller_readiness.py"
    specification = importlib.util.spec_from_file_location(
        "_pinnpcm_controller_v2_readiness_parity_helpers", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("controller-v2 parity helper module cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    for name in (
        "_history_streaming_parity",
        "_history_streaming_event_parity",
        "_history_streaming_reversal_parity",
    ):
        if not callable(getattr(module, name, None)):
            raise RuntimeError(f"controller-v2 parity helper {name} is unavailable")
    return module




def _streamed_integrity(
    scalar_rows: tuple[dict[str, Any], ...], config: dict[str, Any]
) -> dict[str, Any]:
    gates = config["gates"]
    limits = {
        "thermal": float(gates["thermal_ledger_relative_residual_max"]),
        "circuit": float(gates["circuit_ledger_relative_residual_max"]),
        "combined": float(gates["combined_ledger_relative_residual_max"]),
        "device_power": float(gates["device_power_identity_relative_residual_max"]),
    }
    maxima = {name: 0.0 for name in limits}
    lateral_relative = 0.0
    lateral_roundoff = 0.0
    passed = bool(scalar_rows)
    for row in scalar_rows:
        for prefix in ("full", "first_half", "second_half"):
            passed = passed and all(
                row.get(f"{prefix}_{name}") is True
                for name in (
                    "finite",
                    "nonlinear_pass",
                    "ledger_pass",
                    "lateral_pass",
                    "overall_pass",
                )
            )
            relative = float(row[f"{prefix}_lateral_relative_mismatch"])
            roundoff = float(row[f"{prefix}_lateral_roundoff_ratio"])
            lateral_relative = max(lateral_relative, relative)
            lateral_roundoff = max(lateral_roundoff, roundoff)
            passed = passed and (relative <= 1.0e-10 or roundoff <= 1.0)
            for ledger, limit in limits.items():
                residual = float(row[f"{prefix}_{ledger}_relative_residual"])
                maxima[ledger] = max(maxima[ledger], residual)
                passed = passed and residual <= limit
        passed = passed and all(
            row.get(f"aggregate_{name}") is True
            for name in ("finite", "ledger_pass", "overall_pass")
        )
        for ledger, limit in limits.items():
            residual = float(row[f"aggregate_{ledger}_relative_residual"])
            maxima[ledger] = max(maxima[ledger], residual)
            passed = passed and residual <= limit
        passed = passed and float(row["e_max"]) <= 0.02
    return {
        "pass": bool(passed),
        "ledger_maxima": maxima,
        "lateral_relative_max": lateral_relative,
        "lateral_roundoff_max": lateral_roundoff,
    }


def _path_integrity(observation: Any) -> dict[str, Any]:
    diagnostics = observation.diagnostics
    paths = (
        diagnostics.full_step,
        diagnostics.first_half_step,
        diagnostics.second_half_step,
    )
    complete = all(path is not None for path in paths) and diagnostics.aggregate is not None
    overall = bool(
        complete
        and all(path.overall_pass for path in paths)
        and diagnostics.aggregate.overall_pass
    )
    finite = bool(
        complete
        and all(path.finite for path in paths)
        and diagnostics.aggregate.finite
    )
    nonlinear = bool(
        complete
        and all(path.nonlinear_pass for path in paths)
    )
    ledger = bool(
        complete
        and all(path.ledger_pass for path in paths)
        and diagnostics.aggregate.ledger_pass
    )
    lateral = bool(complete and all(path.lateral_pass for path in paths))
    return {
        "complete": complete,
        "overall_pass": overall,
        "finite": finite,
        "nonlinear_pass": nonlinear,
        "ledger_pass": ledger,
        "lateral_pass": lateral,
    }


def _timing_payload(timings: S2PerformanceTimings) -> dict[str, Any]:
    values = timings.as_dict()
    if set(values) != set(_TIMING_FIELDS) or any(
        not math.isfinite(float(value)) or float(value) < 0.0
        for value in values.values()
    ):
        raise RuntimeError("performance timing telemetry is invalid")
    return {
        "timing_semantics": PERFORMANCE_TIMING_SEMANTICS,
        "performance_timings_s": values,
        "timing_fields_are_hierarchical_nonadditive": True,
    }


def _same_run_parity(
    initial: S2State, result: Any, *, grid: Any, closure: Any, config: dict[str, Any], protocol_id: str
) -> dict[str, Any]:
    helpers = _legacy_parity_helpers()
    state = helpers._history_streaming_parity(
        initial, result, grid, config, protocol_id
    )
    events = helpers._history_streaming_event_parity(initial, result, config, grid)
    reversals = helpers._history_streaming_reversal_parity(
        initial, result, closure, grid
    )
    return {
        "state_scalar_field": state,
        "event_topology": events,
        "reversal_topology": reversals,
        "pass": bool(state["pass"] and events["pass"] and reversals["pass"]),
        "same_numerical_run": True,
    }


def _result_hashes(payload: dict[str, Any], *, input_identity: Any) -> dict[str, Any]:
    result = dict(payload)
    result["input_sha256"] = _canonical_sha256(input_identity)
    result["output_sha256"] = _canonical_sha256(result)
    return result


def _run_c1(remaining_s: float) -> dict[str, Any]:
    if not math.isfinite(float(remaining_s)) or float(remaining_s) <= 0.0:
        raise ValueError("C1 remaining budget must be positive")
    grid, fields, closure, cache, config = _context(1)
    initial = _deterministic_state(
        "legal_critical", grid=grid, fields=fields, closure=closure
    )
    protocol_id, protocol, scale = _protocol_identity("legal_critical", config)
    timings = S2PerformanceTimings()
    started = perf_counter()
    try:
        result = run_s2_streaming_protocol_v2(
            "PRE-CTRL-LEGAL-CRITICAL",
            initial,
            protocol=protocol,
            protocol_id=protocol_id,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            final_time_s=2.0e-8,
            maximum_wall_clock_s=float(remaining_s),
            retain_full_history=True,
            cache=cache,
            use_equivalent_optimizations=True,
            use_unit_voltage_scaling=False,
            performance_timings=timings,
        )
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
        parity = _same_run_parity(
            initial,
            result,
            grid=grid,
            closure=closure,
            config=config,
            protocol_id=protocol_id,
        )
        passed = bool(
            result.protocol_result.completed
            and result.protocol_result.diagnostics.accepted_steps > 0
            and integrity
            and parity["pass"]
        )
        payload = {
            "status": "PASS" if passed else "FAIL",
            "failure_class": None if passed else "numerical_integrity",
            "sample_id": "PRE-CTRL-LEGAL-CRITICAL",
            "protocol_id": protocol_id,
            "protocol_V_scale_V": scale,
            "accepted_interval_count": int(
                result.protocol_result.diagnostics.accepted_steps
            ),
            "maximum_embedded_error": float(
                result.protocol_result.diagnostics.maximum_e_max
            ),
            "completed": bool(result.protocol_result.completed),
            "stop_reason": str(result.protocol_result.stop_reason),
            "full_history_streaming_parity": parity,
            "finite_nonlinear_ledger_lateral_pass": integrity,
            "wall_clock_s": perf_counter() - started,
            **_timing_payload(timings),
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    except Exception as error:
        payload = {
            "status": "FAIL",
            "failure_class": "numerical_integrity",
            "sample_id": "PRE-CTRL-LEGAL-CRITICAL",
            "error_class": type(error).__name__,
            "error_message": str(error),
            "wall_clock_s": perf_counter() - started,
            **_timing_payload(timings),
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    return _result_hashes(
        payload,
        input_identity={
            "sample_id": "PRE-CTRL-LEGAL-CRITICAL",
            "config_sha256": _sha256(BASE_CONFIG_PATH),
            "overlay_sha256": _sha256(OVERLAY_PATH),
        },
    )


def _trajectory_payload(
    *,
    sample_id: str,
    level: int,
    state_id: str,
    maximum_wall_clock_s: float,
    retain_full_history: bool,
    allow_budget_truncation: bool,
) -> tuple[dict[str, Any], Any]:
    grid, fields, closure, cache, config = _context(level)
    initial = _deterministic_state(state_id, grid=grid, fields=fields, closure=closure)
    protocol_id, protocol, scale = _protocol_identity(state_id, config)
    timings = S2PerformanceTimings()
    started = perf_counter()
    result = run_s2_streaming_protocol_v2(
        sample_id,
        initial,
        protocol=protocol,
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=1.0e-6,
        maximum_accepted_steps=128,
        maximum_wall_clock_s=float(maximum_wall_clock_s),
        retain_full_history=retain_full_history,
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
        performance_timings=timings,
    )
    wall = perf_counter() - started
    diagnostics = result.protocol_result.diagnostics
    scalar_rows = tuple(result.scalar_records[1:])
    path = _streamed_integrity(scalar_rows, config)
    final = result.final_state
    finite = bool(
        np.isfinite(final.temperature_K).all()
        and np.isfinite(final.conductive_state).all()
        and np.isfinite(final.branch_memory).all()
        and np.isfinite(final.device_voltage_V)
    )
    bounded = bool(
        np.all(final.conductive_state >= -1.0e-12)
        and np.all(final.conductive_state <= 1.0 + 1.0e-12)
        and np.all(final.branch_memory >= -1.0 - 1.0e-12)
        and np.all(final.branch_memory <= 1.0 + 1.0e-12)
        and np.all(final.temperature_K >= float(closure.temperature_min_K) - 1.0e-9)
        and np.all(final.temperature_K <= float(closure.temperature_max_K) + 1.0e-9)
        and -1.0e-12 <= float(final.device_voltage_V) <= scale + 1.0e-9
    )
    progression = bool(
        diagnostics.accepted_steps > 0
        and result.protocol_result.achieved_final_time_s > initial.time_s
    )
    acceptable_stop = str(result.protocol_result.stop_reason) in {
        "requested_final_time_reached",
        "maximum_accepted_steps_reached",
    }
    if allow_budget_truncation:
        acceptable_stop = acceptable_stop or (
            str(result.protocol_result.stop_reason) == "maximum_wall_clock_reached"
        )
    history_parity: dict[str, Any] | None = None
    if retain_full_history:
        history_parity = _same_run_parity(
            initial,
            result,
            grid=grid,
            closure=closure,
            config=config,
            protocol_id=protocol_id,
        )
    passed = bool(
        finite
        and bounded
        and progression
        and acceptable_stop
        and path["pass"]
        and (history_parity is None or history_parity["pass"])
    )
    payload = {
        "sample_id": sample_id,
        "sample_kind": "short_trajectory",
        "spatial_level": level,
        "nx": int(grid.nx),
        "ny": int(grid.ny),
        "state_id": state_id,
        "protocol_id": protocol_id,
        "protocol_V_scale_V": scale,
        "status": "pass" if passed else "fail",
        "failure_class": "" if passed else "numerical_integrity",
        "accepted_steps": int(diagnostics.accepted_steps),
        "rejected_steps": int(diagnostics.rejected_steps),
        "coupled_solve_count": int(diagnostics.total_coupled_solves),
        "newton_iterations": int(diagnostics.newton_iterations),
        "krylov_matvecs": int(diagnostics.krylov_matvecs),
        "armijo_backtracks": int(diagnostics.armijo_backtracks),
        "fallback_steps": int(diagnostics.fallback_steps),
        "fallback_picard_iterations": int(diagnostics.fallback_picard_iterations),
        "step_wall_time_p50_s": float(diagnostics.step_wall_time_p50_s),
        "step_wall_time_p90_s": float(diagnostics.step_wall_time_p90_s),
        "step_wall_time_max_s": float(diagnostics.step_wall_time_max_s),
        "achieved_simulated_time_s": float(result.protocol_result.achieved_final_time_s),
        "completed": bool(result.protocol_result.completed),
        "stop_reason": str(result.protocol_result.stop_reason),
        "finite": finite,
        "bounded": bounded,
        "ledgers_pass": bool(path["pass"]),
        "lateral_pass": bool(path["pass"]),
        "maximum_ledger_residuals": path["ledger_maxima"],
        "lateral_relative_mismatch_max": path["lateral_relative_max"],
        "lateral_roundoff_ratio_max": path["lateral_roundoff_max"],
        "embedded_error_max": float(diagnostics.maximum_e_max),
        "event_count": len(result.event_records),
        "event_topology": [
            (row["direction"], int(row["event_index"])) for row in result.event_records
        ],
        "reversal_count": len(result.reversal_records),
        "reversal_topology": [
            (row["direction"], int(row["reversal_index"]))
            for row in result.reversal_records
        ],
        "history_streaming_parity": history_parity,
        "observed_solver_wall_time_s": wall,
        "peak_rss_bytes": int(process_memory().peak_working_set_bytes),
        **_timing_payload(timings),
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    return payload, result


def _run_c2(remaining_s: float) -> dict[str, Any]:
    if not math.isfinite(float(remaining_s)) or float(remaining_s) <= 0.0:
        raise ValueError("C2 remaining budget must be positive")
    started = perf_counter()
    try:
        row, _ = _trajectory_payload(
            sample_id="PRE-CTRL-CRITICAL-TRAJECTORY",
            level=1,
            state_id="legal_critical",
            maximum_wall_clock_s=float(remaining_s),
            retain_full_history=True,
            allow_budget_truncation=True,
        )
        passed = row["status"] == "pass"
        truncated = row["stop_reason"] == "maximum_wall_clock_reached"
        payload = {
            "status": "PASS" if passed else "FAIL",
            "failure_class": None if passed else "numerical_integrity",
            **row,
            "status": "PASS" if passed else "FAIL",
            "stop_reason": (
                "C2_truncated_by_readiness_budget" if truncated else row["stop_reason"]
            ),
            "runtime_evidence_sufficient": bool(
                passed
                and row["accepted_steps"] > 0
                and row["step_wall_time_p90_s"] > 0.0
            ),
            "forecast_sample_row": row,
            "event_observation": (
                "NA_not_observed_within_bounded_C2_window"
                if row["event_count"] == 0 and row["reversal_count"] == 0
                else "observed_and_parity_checked"
            ),
            "wall_clock_s": perf_counter() - started,
            "formal_event_or_trend_vote": False,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    except Exception as error:
        payload = {
            "status": "FAIL",
            "failure_class": "numerical_integrity",
            "sample_id": "PRE-CTRL-CRITICAL-TRAJECTORY",
            "error_class": type(error).__name__,
            "error_message": str(error),
            "runtime_evidence_sufficient": False,
            "wall_clock_s": perf_counter() - started,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    return _result_hashes(
        payload,
        input_identity={
            "sample_id": "PRE-CTRL-CRITICAL-TRAJECTORY",
            "config_sha256": _sha256(BASE_CONFIG_PATH),
            "overlay_sha256": _sha256(OVERLAY_PATH),
            "maximum_accepted_intervals": 128,
            "maximum_time_s": 1.0e-6,
        },
    )


def _validate_plan(plan: Mapping[str, Any]) -> tuple[int, str, str, str]:
    sample_id = str(plan.get("sample_id", ""))
    if not sample_id.startswith("PRE-") or "P1V2-" in sample_id:
        raise ValueError("C3 adapter accepts only non-formal PRE sample IDs")
    level = int(plan.get("spatial_level", 0))
    if level not in _ALLOWED_LEVELS:
        raise ValueError("C3 sample has an undeclared spatial level")
    state_id = str(plan.get("state_id", ""))
    protocol_id = str(plan.get("protocol", ""))
    if _PROTOCOL_BY_STATE.get(state_id) != protocol_id:
        raise ValueError("C3 state/protocol mapping differs from preregistration")
    scale = float(plan.get("protocol_V_scale_V", math.nan))
    if scale != _PROTOCOL_SCALE_V[protocol_id]:
        raise ValueError("C3 protocol voltage scale differs from preregistration")
    _require_sha256(plan.get("input_sha256"), "C3 input_sha256")
    kind = str(plan.get("sample_kind", ""))
    if kind not in {"single_interval", "short_trajectory"}:
        raise ValueError("C3 sample kind is invalid")
    return level, state_id, protocol_id, kind


def _single_interval_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    level, state_id, protocol_id, _ = _validate_plan(plan)
    grid, fields, closure, cache, config = _context(level)
    initial = _deterministic_state(state_id, grid=grid, fields=fields, closure=closure)
    _, protocol, scale = _protocol_identity(state_id, config)
    maximum_H, floor_H = controller_v2_limits(config, 1)
    interval_class = str(plan.get("interval_class", ""))
    if interval_class == "base":
        interval = maximum_H
    elif interval_class == "floor":
        interval = floor_H
    else:
        raise ValueError("single-interval sample lacks base/floor identity")
    timings = S2PerformanceTimings()
    started = perf_counter()
    observation = attempt_s2_embedded_interval(
        initial,
        protocol=protocol,
        protocol_id=protocol_id,
        outer_interval_s=interval,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        at_outer_floor=interval_class == "floor",
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
        performance_timings=timings,
    )
    wall = perf_counter() - started
    integrity = _path_integrity(observation)
    embedded = observation.diagnostics.embedded_error
    accepted = bool(
        observation.step is not None
        and integrity["overall_pass"]
        and embedded is not None
        and float(embedded.e_max) <= 0.02
    )
    valid_rejection = bool(
        observation.step is None
        and interval_class == "base"
        and integrity["overall_pass"]
        and embedded is not None
        and float(embedded.e_max) > 0.02
        and observation.error_class is None
    )
    status = "pass" if accepted else "valid_rejection" if valid_rejection else "fail"
    candidates = tuple(
        item
        for item in (
            observation.full_candidate,
            observation.first_half_candidate,
            observation.second_half_candidate,
        )
        if item is not None
    )
    return {
        "sample_id": str(plan["sample_id"]),
        "sample_kind": "single_interval",
        "spatial_level": level,
        "nx": int(grid.nx),
        "ny": int(grid.ny),
        "state_id": state_id,
        "protocol_id": protocol_id,
        "protocol_V_scale_V": scale,
        "interval_class": interval_class,
        "outer_interval_s": interval,
        "status": status,
        "failure_class": "" if status != "fail" else "numerical_integrity",
        "accepted_steps": int(accepted),
        "rejected_steps": int(not accepted),
        "coupled_solve_count": int(observation.diagnostics.coupled_solve_count),
        "newton_iterations": sum(item.nonlinear.iterations for item in candidates),
        "krylov_matvecs": sum(item.nonlinear.krylov_matvecs for item in candidates),
        "armijo_backtracks": sum(item.nonlinear.armijo_backtracks for item in candidates),
        "fallback_steps": int(observation.diagnostics.any_fallback),
        "fallback_picard_iterations": sum(
            item.nonlinear.fallback_picard_iterations for item in candidates
        ),
        "step_wall_time_p50_s": wall,
        "step_wall_time_p90_s": wall,
        "step_wall_time_max_s": wall,
        "achieved_simulated_time_s": interval if accepted else 0.0,
        "completed": status != "fail",
        "stop_reason": (
            "single_embedded_interval_completed"
            if accepted
            else "valid_error_driven_rejection"
            if valid_rejection
            else "single_embedded_interval_failed"
        ),
        "finite": integrity["finite"],
        "nonlinear_pass": integrity["nonlinear_pass"],
        "ledgers_pass": integrity["ledger_pass"],
        "lateral_pass": integrity["lateral_pass"],
        "embedded_error_max": None if embedded is None else float(embedded.e_max),
        "peak_rss_bytes": int(process_memory().peak_working_set_bytes),
        "streaming_output_bytes": 0,
        "predicted_full_streaming_bytes": 0,
        "predicted_full_streaming_io_s": 0.0,
        "observed_solver_wall_time_s": wall,
        **_timing_payload(timings),
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def run_c3_sample(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Run one independent C3 sample without cached/uncached duplication."""

    _, state_id, _, kind = _validate_plan(plan)
    try:
        if kind == "single_interval":
            payload = _single_interval_payload(plan)
        else:
            payload, result = _trajectory_payload(
                sample_id=str(plan["sample_id"]),
                level=int(plan["spatial_level"]),
                state_id=state_id,
                maximum_wall_clock_s=860.0,
                retain_full_history=False,
                allow_budget_truncation=False,
            )
            with tempfile.TemporaryDirectory(prefix="pinn-phase1v2-c3-stream-") as root:
                publish_started = perf_counter()
                published = publish_pre_streaming_case(
                    Path(root),
                    result,
                    identity_hashes={
                        "resolved_runtime_identity": _resolved_runtime_identity_sha256()
                    },
                )
                output_bytes = published_case_bytes(published)
                publish_wall = perf_counter() - publish_started
            scale = max(1, math.ceil(4001 / max(len(result.scalar_records), 1)))
            payload.update(
                {
                    "streaming_output_bytes": output_bytes,
                    "streaming_publish_wall_s": publish_wall,
                    "predicted_full_streaming_bytes": int(output_bytes * scale),
                    "predicted_full_streaming_io_s": float(publish_wall * scale),
                    "streaming_io_measurement_status": "measured_atomic_temp_publish",
                }
            )
        if payload["status"] not in {"pass", "valid_rejection"}:
            return {
                "status": "FAIL",
                "failure_class": "numerical_integrity",
                "payload": payload,
            }
        return {"status": "PASS", "payload": payload}
    except (FloatingPointError, RuntimeError, ValueError) as error:
        return {
            "status": "FAIL",
            "failure_class": "numerical_integrity",
            "payload": {
                "sample_id": str(plan.get("sample_id", "")),
                "sample_kind": kind,
                "state_id": state_id,
                "error_class": type(error).__name__,
                "error_message": str(error),
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            },
        }


def _resolved_runtime_identity_sha256() -> str:
    payload = json.loads(RUNTIME_IDENTITY_PATH.read_text(encoding="utf-8"))
    return _require_sha256(
        payload["resolved_runtime_identity_sha256"],
        "resolved_runtime_identity_sha256",
    )


def _measure_launch_environment() -> dict[str, Any]:
    global _LAUNCH_ENVIRONMENT
    environment = dict(_measure_runtime_environment(ROOT))
    environment["launch_available_RAM_bytes"] = int(
        environment["available_ram_bytes_at_launch"]
    )
    environment["formal_execution_count"] = 0
    environment["formal_artifact_count"] = 0
    _LAUNCH_ENVIRONMENT = environment
    return dict(environment)


def _rss_probe_worker(connection: Any, candidate_identity_sha256: str) -> None:
    try:
        plan = {
            "plan_index": 0,
            "sample_id": "PRE-RSS-L4-high_conductive-base",
            "sample_kind": "single_interval",
            "spatial_level": 4,
            "state_id": "high_conductive",
            "interval_class": "base",
            "protocol": "high_bias_lock_15p8V",
            "protocol_V_scale_V": 15.8,
        }
        plan["input_sha256"] = _canonical_sha256(plan)
        result = run_c3_sample(plan)
        if result.get("status") != "PASS":
            raise RuntimeError("L4 RSS probe sample did not pass")
        connection.send(
            {
                "status": "PASS",
                "schema_version": "geophase_phase1_v2_worker_RSS_microbenchmark_v1",
                "sample_id": plan["sample_id"],
                "candidate_identity_sha256": candidate_identity_sha256,
                "measured_peak_worker_RSS_bytes": int(
                    process_memory().peak_working_set_bytes
                ),
                "sample_payload": result["payload"],
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }
        )
    except Exception as error:
        connection.send(
            {
                "status": "INVALID",
                "error_class": type(error).__name__,
                "error_message": str(error),
                "candidate_identity_sha256": candidate_identity_sha256,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }
        )
    finally:
        connection.close()


def _measure_worker_rss(candidate_identity_sha256: str) -> dict[str, Any]:
    candidate = _require_sha256(
        candidate_identity_sha256, "candidate_identity_sha256"
    )
    _apply_single_thread_environment()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_rss_probe_worker, args=(child, candidate))
    process.start()
    child.close()
    if not parent.poll(600.0):
        process.terminate()
        process.join(timeout=10.0)
        raise RuntimeError("spawn L4 worker RSS probe exceeded its bounded wait")
    payload = parent.recv()
    process.join(timeout=10.0)
    if process.is_alive():
        process.terminate()
        process.join(timeout=10.0)
        raise RuntimeError("spawn L4 worker RSS probe did not exit")
    if process.exitcode != 0 or payload.get("status") != "PASS":
        raise RuntimeError("spawn L4 worker RSS probe failed closed")
    return dict(payload)


def _identity_hashes(environment: Mapping[str, Any]) -> dict[str, str]:
    candidate = _require_sha256(
        _READINESS_CONTEXT.get("candidate_identity_sha256"),
        "readiness candidate_identity_sha256",
    )
    return {
        "code_tree": candidate,
        "S2_config": _sha256(BASE_CONFIG_PATH),
        "controller_v2_overlay": _sha256(OVERLAY_PATH),
        "resolved_runtime_identity": _resolved_runtime_identity_sha256(),
        "formal_manifest_contract": _sha256(FORMAL_MANIFEST_PATH),
        "expanded_manifest": _sha256(EXPANDED_MANIFEST_PATH),
        "execution_addendum": _sha256(EXECUTION_ADDENDUM_PATH),
        "execution_DAG": _sha256(EXECUTION_DAG_PATH),
        "environment": _canonical_sha256(dict(environment)),
    }


def _run_dormant_runner() -> dict[str, Any]:
    environment = (
        dict(_LAUNCH_ENVIRONMENT)
        if _LAUNCH_ENVIRONMENT is not None
        else _measure_launch_environment()
    )
    dag = json.loads(EXECUTION_DAG_PATH.read_text(encoding="utf-8"))
    identity = _identity_hashes(environment)
    with tempfile.TemporaryDirectory(prefix="pinn-phase1v2-v3-dormant-") as directory:
        root = Path(directory)
        prepared = create_prepared_registry(
            root,
            run_id="PRE-SOURCE-CORRECTED-RUNNER-PASS",
            identity_hashes=identity,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(prepared.path)
        partial = create_partial_case_work(
            prepared.path, "PRE-SOURCE-CORRECTED-UNIT-A", {"synthetic_step": 1}
        )
        interrupt_resumable(
            prepared.path,
            reason="injected interruption",
            partial_case_id="PRE-SOURCE-CORRECTED-UNIT-A",
        )
        unpublished = not (
            prepared.path / "cases" / "PRE-SOURCE-CORRECTED-UNIT-A.json"
        ).exists()
        resume_same_run(
            prepared.path,
            run_id="PRE-SOURCE-CORRECTED-RUNNER-PASS",
            expected_identity_hashes=identity,
        )
        publish_synthetic_case(
            prepared.path,
            case_id="PRE-SOURCE-CORRECTED-UNIT-A",
            outcome="pass",
            classification="synthetic_pass",
            payload={"synthetic_step": 2},
        )
        passed = complete_pass(prepared.path)

        mismatch = create_prepared_registry(
            root,
            run_id="PRE-SOURCE-CORRECTED-RUNNER-HASH",
            identity_hashes=identity,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(mismatch.path)
        interrupt_resumable(mismatch.path, reason="injected interruption")
        changed = dict(identity)
        changed["resolved_runtime_identity"] = "0" * 64
        mismatch_rejected = False
        try:
            resume_same_run(
                mismatch.path,
                run_id="PRE-SOURCE-CORRECTED-RUNNER-HASH",
                expected_identity_hashes=changed,
            )
        except InvalidContractError:
            mismatch_rejected = True

        foundation = create_prepared_registry(
            root,
            run_id="PRE-SOURCE-CORRECTED-RUNNER-FOUNDATION",
            identity_hashes=identity,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(foundation.path)
        foundation_view = record_foundation_failure(
            foundation.path,
            failing_case_id="PRE-SOURCE-CORRECTED-FOUNDATION-FAIL",
            remaining_case_ids=["PRE-SOURCE-CORRECTED-BLOCKED-A"],
            reason="injected foundation failure",
        )
        checks = {
            "coverage_63_60_3": passed.identity["coverage"]
            == {"evaluation_items": 63, "execution_units": 60, "legal_reuses": 3},
            "same_run_ID_resume": passed.state == "COMPLETED_PASS",
            "partial_case_not_published": unpublished,
            "per_case_atomic_completion": (
                prepared.path / "cases" / "PRE-SOURCE-CORRECTED-UNIT-A.json"
            ).exists()
            and not partial.exists(),
            "hash_mismatch_rejected": mismatch_rejected
            and load_registry(mismatch.path).state == "INVALID_CONTRACT",
            "foundation_fail_fast": foundation_view.state
            == "COMPLETED_SCIENTIFIC_FAIL",
            "formal_count_zero": passed.identity["formal_execution_count"] == 0,
            "formal_dispatch_disabled": passed.identity[
                "formal_unit_dispatch_enabled"
            ]
            is False,
        }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "failure_class": None if all(checks.values()) else "dormant_runner",
        "checks": checks,
        "registry_location": "temporary_directory_only",
        "run_ID_prefix": "PRE-",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def _build_forecast(
    completed_samples: tuple[Mapping[str, Any], ...],
    C2: Mapping[str, Any],
    worker_count: int,
) -> dict[str, Any]:
    if _LAUNCH_ENVIRONMENT is None:
        raise RuntimeError("launch environment was not measured before forecast")
    rows: list[dict[str, Any]] = []
    for completed in completed_samples:
        if not isinstance(completed.get("payload"), Mapping):
            raise RuntimeError("completed C3 sample lost its validated payload")
        envelope = {
            key: value for key, value in completed.items() if key != "payload"
        }
        row = {**envelope, **dict(completed["payload"])}
        if row.get("timing_semantics") != PERFORMANCE_TIMING_SEMANTICS:
            raise RuntimeError("C3 timing semantics changed")
        rows.append(row)
    c2_row = C2.get("forecast_sample_row")
    if not isinstance(c2_row, Mapping):
        raise RuntimeError("C2 did not provide a forecast sample row")
    rows.append(dict(c2_row))
    dag = json.loads(EXECUTION_DAG_PATH.read_text(encoding="utf-8"))
    environment = dict(_LAUNCH_ENVIRONMENT)
    environment["physical_core_count"] = int(worker_count)
    schedule, forecast = build_campaign_cost_forecast(
        execution_dag=dag,
        sample_rows=rows,
        environment=environment,
        disk_free_fraction_min=0.20,
        outer_interval_floor_s=9.765625e-12,
        coupled_solves_per_clean_outer_interval=3,
        measured_interval_wall_time_includes_all_coupled_solves=True,
    )
    registered_rss = int(
        _READINESS_CONTEXT.get("worker_rss", {}).get(
            "measured_peak_worker_RSS_bytes", 0
        )
    )
    if registered_rss <= 0:
        raise RuntimeError("registered spawn-worker RSS measurement is absent")
    aggregate_rss = int(worker_count) * registered_rss
    rss_fraction = aggregate_rss / max(
        int(_LAUNCH_ENVIRONMENT["launch_available_RAM_bytes"]), 1
    )
    return {
        **forecast,
        "predicted_hard_makespan_s": float(forecast["hard_makespan_s"]),
        "RSS_gate_pass": rss_fraction <= 0.70,
        "disk_gate_pass": float(forecast["disk_free_fraction_after_forecast"])
        >= 0.20,
        "frozen_pool_worker_count": int(worker_count),
        "registered_peak_worker_RSS_bytes": registered_rss,
        "aggregate_worker_RSS_bytes": aggregate_rss,
        "aggregate_worker_RSS_fraction_of_launch_available_RAM": rss_fraction,
        "schedule": schedule,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def task_adapter(*, mode: str, payload: Mapping[str, Any]) -> Any:
    """Expose the exact adapter modes used by the locked task runner."""

    if mode == "equivalence":
        raise RuntimeError(
            "frozen equivalence audit is not wired in the readiness adapter"
        )
    if mode == "measure_worker_rss":
        _apply_single_thread_environment()
        return _measure_worker_rss(
            _require_sha256(
                payload.get("candidate_identity_sha256"),
                "candidate_identity_sha256",
            )
        )
    if mode == "readiness_hooks":
        _apply_single_thread_environment()
        candidate = payload.get("equivalence", {}).get(
            "candidate_identity_sha256"
        )
        _READINESS_CONTEXT.clear()
        _READINESS_CONTEXT.update(
            {
                "candidate_identity_sha256": _require_sha256(
                    candidate, "equivalence candidate_identity_sha256"
                ),
                "worker_rss": dict(payload.get("worker_rss", {})),
            }
        )
        return {
            "run_c1": _run_c1,
            "run_c2": _run_c2,
            "measure_launch_environment": _measure_launch_environment,
            "c3_worker_entrypoint": (
                "pinnpcm.solvers.geophase_phase1_v2_source_corrected_performance:"
                "run_c3_sample"
            ),
            "run_dormant_runner": _run_dormant_runner,
            "build_forecast": _build_forecast,
        }
    raise ValueError(f"unsupported source-corrected task adapter mode: {mode}")


__all__ = ["run_c3_sample", "task_adapter"]
