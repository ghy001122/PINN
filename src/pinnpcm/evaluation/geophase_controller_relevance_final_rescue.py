"""Bounded R0 controller-relevance audit after the immutable D0 stop.

The audit calls the production exact-condensed controller entrypoint.  It does
not mirror controller logic, alter the v1 root solver, or cast a scientific
vote.  Large-root failures are recorded as ordinary controller rejections;
only the terminal locked-floor outcome determines the R0 route.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import traceback
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_controller_v2 as controller_v2
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_exact_condensed import ExactCondensedRootTelemetry
from pinnpcm.solvers.geophase_exact_condensed_controller_v2 import (
    ExactCondensedEmbeddedAttemptObservation,
    simulate_exact_condensed_protocol_v2,
)


SCHEMA_VERSION = "geophase_controller_relevance_r0_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_builtin(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return _to_builtin(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        if not np.isfinite(result):
            raise ValueError("nonfinite floating value cannot be published")
        return result
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError("nonfinite floating value cannot be published")
    return value


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        _to_builtin(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _payload_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_bytes(
        path,
        (
            json.dumps(
                _to_builtin(payload),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8"),
    )


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML contract must contain a mapping: {path}")
    return payload


def _state_payload(state: production.S2State) -> dict[str, Any]:
    return {
        "time_s": float(state.time_s),
        "temperature_K": np.asarray(state.temperature_K, dtype=float),
        "conductive_state": np.asarray(state.conductive_state, dtype=float),
        "branch_memory": np.asarray(state.branch_memory, dtype=float),
        "device_voltage_V": float(state.device_voltage_V),
    }


def _state_sha256(state: production.S2State) -> str:
    return _payload_sha256(_state_payload(state))


def _git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def load_contract(path: Path) -> dict[str, Any]:
    contract = _load_yaml(path)
    expected_schema = "geophase_controller_relevance_final_rescue_v1"
    if contract.get("schema_version") != expected_schema:
        raise ValueError("unexpected controller-relevance rescue schema")
    return contract


def verify_frozen_inputs(contract: Mapping[str, Any]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in contract["frozen_inputs"]:
        relative = Path(str(item["path"]))
        observed = _sha256(ROOT / relative)
        expected = str(item["sha256"])
        if observed != expected:
            raise ValueError(
                f"frozen controller-relevance input drifted: {relative}: "
                f"{observed} != {expected}"
            )
        verified.append({"path": relative.as_posix(), "sha256": observed})
    return verified


def resolve_and_validate_limits(
    scientific: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, dict[str, float | int]]:
    observed: dict[str, dict[str, float | int]] = {}
    for name, expected in contract["controller_contract"]["expected_limits"].items():
        divisor = int(expected["time_divisor"])
        maximum, floor = controller_v2.controller_v2_limits(dict(scientific), divisor)
        if not np.isclose(maximum, float(expected["Hmax_s"]), rtol=0.0, atol=0.0):
            raise ValueError(f"{name} Hmax differs from the frozen rescue contract")
        if not np.isclose(floor, float(expected["Hmin_s"]), rtol=0.0, atol=0.0):
            raise ValueError(f"{name} Hmin differs from the frozen rescue contract")
        observed[name] = {
            "time_divisor": divisor,
            "Hmax_s": float(maximum),
            "Hmin_s": float(floor),
        }
    return observed


def validate_thread_environment(contract: Mapping[str, Any]) -> dict[str, str]:
    required = {
        str(name): str(value)
        for name, value in contract["runtime"]["required_thread_environment"].items()
    }
    observed = {name: os.environ.get(name, "") for name in required}
    mismatches = {
        name: {"expected": required[name], "observed": observed[name]}
        for name in required
        if observed[name] != required[name]
    }
    if mismatches:
        raise ValueError(f"single-thread runtime contract not satisfied: {mismatches}")
    return observed


def _case_state(case: Mapping[str, Any], grid: Any) -> production.S2State:
    source = ROOT / str(case["state_source"])
    if case["state_kind"] == "accepted_on_trajectory_previous_state":
        replay = json.loads(source.read_text(encoding="utf-8"))["replay"]
        return _state_from_replay(replay["previous_state"])
    if case["state_kind"] == "critical_transition_fixture":
        fixture = _load_yaml(source)["single_locked_replay"]["initial_state"]
        return production.S2State(
            time_s=0.0,
            temperature_K=np.full(
                grid.shape, float(fixture["temperature_K"]), dtype=float
            ),
            conductive_state=np.full(
                grid.shape, float(fixture["conductive_state_s"]), dtype=float
            ),
            branch_memory=np.full(
                grid.shape, float(fixture["branch_memory_b"]), dtype=float
            ),
            device_voltage_V=float(fixture["device_voltage_V"]),
        )
    raise ValueError(f"unknown R0 state kind: {case['state_kind']}")


def _candidate_payload(
    candidate: production.S2StepResult | None,
    integrity: Any,
) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "endpoint_time_s": float(candidate.state.time_s),
        "endpoint_state_sha256": _state_sha256(candidate.state),
        "nonlinear": asdict(candidate.nonlinear),
        "relative_current_imbalance": float(
            candidate.electrical.relative_current_imbalance
        ),
        "relative_power_imbalance": float(
            candidate.electrical.relative_power_imbalance
        ),
        "integrity": None if integrity is None else asdict(integrity),
    }


def _root_for_path(
    observation: ExactCondensedEmbeddedAttemptObservation, index: int
) -> ExactCondensedRootTelemetry | None:
    if index >= len(observation.root_telemetry):
        return None
    return observation.root_telemetry[index]


def _attempt_payload(
    case_id: str,
    observation: ExactCondensedEmbeddedAttemptObservation,
) -> dict[str, Any]:
    diagnostics = observation.diagnostics
    path_specs = (
        ("full_step", observation.full_candidate, diagnostics.full_step),
        (
            "first_half_step",
            observation.first_half_candidate,
            diagnostics.first_half_step,
        ),
        (
            "second_half_step",
            observation.second_half_candidate,
            diagnostics.second_half_step,
        ),
    )
    paths: list[dict[str, Any]] = []
    for index, (name, candidate, integrity) in enumerate(path_specs):
        root = _root_for_path(observation, index)
        paths.append(
            {
                "path": name,
                "root": None if root is None else asdict(root),
                "candidate": _candidate_payload(candidate, integrity),
            }
        )
    committed_hash = None
    first_endpoint_hash = None
    accepted_first_hash = None
    second_endpoint_hash = None
    if observation.first_half_candidate is not None:
        first_endpoint_hash = _state_sha256(observation.first_half_candidate.state)
    if observation.second_half_candidate is not None:
        second_endpoint_hash = _state_sha256(observation.second_half_candidate.state)
    if observation.step is not None:
        committed_hash = _state_sha256(observation.step.state)
        accepted_first_hash = _state_sha256(observation.step.accepted_first_half.state)
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "previous_state_sha256": _state_sha256(observation.previous_state),
        "attempted_outer_interval_s": float(diagnostics.outer_interval_s),
        "half_interval_s": float(diagnostics.half_interval_s),
        "rejection_index": int(diagnostics.rejection_index),
        "at_outer_floor": bool(diagnostics.at_outer_floor),
        "below_floor_remainder": bool(diagnostics.below_floor_remainder),
        "accepted": bool(diagnostics.accepted),
        "error_class": observation.error_class,
        "error_message": observation.error_message,
        "paths": paths,
        "aggregate_integrity": (
            None if diagnostics.aggregate is None else asdict(diagnostics.aggregate)
        ),
        "embedded_error": (
            None
            if diagnostics.embedded_error is None
            else asdict(diagnostics.embedded_error)
        ),
        "first_half_endpoint_sha256": first_endpoint_hash,
        "accepted_first_half_endpoint_sha256": accepted_first_hash,
        "second_half_endpoint_sha256": second_endpoint_hash,
        "committed_endpoint_sha256": committed_hash,
        "first_half_endpoint_preserved": bool(
            first_endpoint_hash is not None
            and first_endpoint_hash == accepted_first_hash
        ),
        "committed_endpoint_is_second_half": bool(
            second_endpoint_hash is not None and second_endpoint_hash == committed_hash
        ),
        "wall_time_s": float(diagnostics.wall_time_s),
    }


def _terminal_root_context(
    case: Mapping[str, Any],
    observation: ExactCondensedEmbeddedAttemptObservation,
) -> dict[str, Any] | None:
    failed_index = None
    for index, telemetry in enumerate(observation.root_telemetry):
        if telemetry.status == "FAIL":
            failed_index = index
            break
    if failed_index is None:
        return None
    path_names = ("full_step", "first_half_step", "second_half_step")
    if failed_index >= len(path_names):
        raise ValueError("root telemetry count exceeds the three controller paths")
    diagnostics = observation.diagnostics
    if failed_index == 0:
        old_state = observation.previous_state
        dt_s = diagnostics.outer_interval_s
        voltage = diagnostics.full_input_voltage_V
    elif failed_index == 1:
        old_state = observation.previous_state
        dt_s = diagnostics.half_interval_s
        voltage = diagnostics.first_half_input_voltage_V
    else:
        if observation.first_half_candidate is None:
            raise ValueError("second-half root failure lacks its first-half endpoint")
        old_state = observation.first_half_candidate.state
        dt_s = diagnostics.half_interval_s
        voltage = diagnostics.second_half_input_voltage_V
    context = {
        "case_id": str(case["case_id"]),
        "path": path_names[failed_index],
        "spatial_level": int(case["spatial_level"]),
        "protocol_id": str(case["protocol_id"]),
        "time_divisor": int(case["time_divisor"]),
        "dt_s": float(dt_s),
        "input_voltage_V": float(voltage),
        "old_state": _state_payload(old_state),
        "root_telemetry": asdict(observation.root_telemetry[failed_index]),
    }
    context["complete_input_sha256"] = _payload_sha256(
        {key: value for key, value in context.items() if key != "root_telemetry"}
    )
    return context


def _accepted_gate(
    observation: ExactCondensedEmbeddedAttemptObservation,
    *,
    floor_s: float,
    acceptance_max: float,
    source_hash_verified: bool,
) -> dict[str, bool]:
    diagnostics = observation.diagnostics
    root_pass = bool(
        len(observation.root_telemetry) == 3
        and all(item.status == "PASS" for item in observation.root_telemetry)
    )
    path_pass = bool(
        diagnostics.full_step.overall_pass
        and diagnostics.first_half_step is not None
        and diagnostics.first_half_step.overall_pass
        and diagnostics.second_half_step is not None
        and diagnostics.second_half_step.overall_pass
    )
    aggregate_pass = bool(
        diagnostics.aggregate is not None and diagnostics.aggregate.overall_pass
    )
    embedded_pass = bool(
        diagnostics.embedded_error is not None
        and diagnostics.embedded_error.e_max <= acceptance_max
    )
    attempt = _attempt_payload("gate", observation)
    gates = {
        "accepted": bool(observation.step is not None and diagnostics.accepted),
        "outer_interval_at_or_above_floor": bool(
            diagnostics.outer_interval_s >= floor_s * (1.0 - 1.0e-12)
        ),
        "three_roots_pass": root_pass,
        "three_path_integrity_pass": path_pass,
        "aggregate_ledger_pass": aggregate_pass,
        "embedded_error_pass": embedded_pass,
        "second_half_source_semantics_frozen": bool(source_hash_verified),
        "first_half_endpoint_preserved": bool(
            attempt["first_half_endpoint_preserved"]
        ),
        "committed_endpoint_is_second_half": bool(
            attempt["committed_endpoint_is_second_half"]
        ),
    }
    gates["all_required"] = bool(all(gates.values()))
    return gates


def _classify_terminal_failure(
    observation: ExactCondensedEmbeddedAttemptObservation | None,
) -> tuple[str, bool]:
    if observation is None:
        return "R0_INVALID_NO_ATTEMPT_OBSERVATION", False
    if not observation.diagnostics.at_outer_floor:
        return "R0_INVALID_TERMINAL_NOT_AT_OUTER_FLOOR", False
    if any(item.status == "FAIL" for item in observation.root_telemetry):
        return "R0_TERMINAL_NONLINEAR_ROOT_FAILURE", True
    diagnostics = observation.diagnostics
    if (
        diagnostics.aggregate is not None
        and not diagnostics.aggregate.overall_pass
    ) or any(
        item is not None and not item.overall_pass
        for item in (
            diagnostics.full_step,
            diagnostics.first_half_step,
            diagnostics.second_half_step,
        )
    ):
        return "R0_VALID_NONSOLVER_INTEGRITY_FAILURE", False
    if diagnostics.embedded_error is not None and not diagnostics.accepted:
        return "R0_VALID_NONSOLVER_EMBEDDED_FAILURE", False
    return "R0_INVALID_UNCLASSIFIED_CONTROLLER_FAILURE", False


def run_r0_case(
    case: Mapping[str, Any],
    *,
    scientific: dict[str, Any],
    remaining_wall_s: float,
    exact_controller_hash_verified: bool,
) -> dict[str, Any]:
    grid = build_geophase_grid(scientific, spatial_level=int(case["spatial_level"]))
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    state = _case_state(case, grid)
    production.validate_s2_state(state, grid, closure)
    divisor = int(case["time_divisor"])
    maximum_H, floor_H = controller_v2.controller_v2_limits(scientific, divisor)
    acceptance_max = float(
        controller_v2._controller(scientific)["embedded_error"]["acceptance_max"]
    )
    protocol_id = str(case["protocol_id"])
    protocol = scientific["formal_protocols"]["protocols"][protocol_id]
    attempts: list[ExactCondensedEmbeddedAttemptObservation] = []
    started = perf_counter()
    result = None
    error_class = None
    error_message = None
    try:
        result = simulate_exact_condensed_protocol_v2(
            state,
            protocol=protocol,
            protocol_id=protocol_id,
            grid=grid,
            closure=closure,
            fields=fields,
            config=scientific,
            time_divisor=divisor,
            final_time_s=float(state.time_s + maximum_H),
            maximum_accepted_steps=1,
            maximum_wall_clock_s=float(remaining_wall_s),
            forced_times_s=(),
            retain_full_history=True,
            attempted_candidate_callback=attempts.append,
            cache=cache,
        )
    except (
        RuntimeError,
        ValueError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as error:
        error_class = type(error).__name__
        error_message = str(error)
    attempt_payloads = [
        _attempt_payload(str(case["case_id"]), observation) for observation in attempts
    ]
    accepted_observation = next(
        (
            observation
            for observation in reversed(attempts)
            if observation.step is not None
        ),
        None,
    )
    gates = (
        None
        if accepted_observation is None
        else _accepted_gate(
            accepted_observation,
            floor_s=floor_H,
            acceptance_max=acceptance_max,
            source_hash_verified=exact_controller_hash_verified,
        )
    )
    if gates is not None and gates["all_required"]:
        status = "PASS"
        route = "B3"
        validity = "valid"
        claim_status = "qualified_supported"
        r1_eligible = False
    elif error_message == "controller-v2 failed at locked outer floor":
        status, r1_eligible = _classify_terminal_failure(
            None if not attempts else attempts[-1]
        )
        route = "R1" if r1_eligible else "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        validity = (
            "valid" if status.startswith("R0_VALID") or r1_eligible else "invalid"
        )
        claim_status = "failed_but_informative" if validity == "valid" else "forbidden"
    elif result is not None and result.stop_reason == "maximum_wall_clock_reached":
        status = "R0_BUDGET_EXHAUSTED"
        route = "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        validity = "invalid"
        claim_status = "forbidden"
        r1_eligible = False
    else:
        status = "R0_INVALID_EXECUTION"
        route = "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        validity = "invalid"
        claim_status = "forbidden"
        r1_eligible = False
    terminal_context = None
    if r1_eligible and attempts:
        terminal_context = _terminal_root_context(case, attempts[-1])
    return {
        "schema_version": SCHEMA_VERSION,
        "case": dict(case),
        "state_role": str(case["state_kind"]),
        "initial_state_sha256": _state_sha256(state),
        "resolved_Hmax_s": float(maximum_H),
        "resolved_Hmin_s": float(floor_H),
        "initial_proposal_s": float(maximum_H),
        "embedded_acceptance_max": acceptance_max,
        "final_time_s": float(state.time_s + maximum_H),
        "maximum_accepted_steps": 1,
        "forced_times_s": [],
        "validity": validity,
        "status": status,
        "claim_status": claim_status,
        "route": route,
        "r1_eligible": bool(r1_eligible),
        "error_class": error_class,
        "error_message": error_message,
        "attempt_count": len(attempt_payloads),
        "attempted_outer_intervals_s": [
            item["attempted_outer_interval_s"] for item in attempt_payloads
        ],
        "accepted_outer_interval_s": (
            None
            if accepted_observation is None
            else float(accepted_observation.diagnostics.outer_interval_s)
        ),
        "stop_reason": None if result is None else result.stop_reason,
        "completed": None if result is None else bool(result.completed),
        "gates": gates,
        "attempts": attempt_payloads,
        "r1_terminal_context": terminal_context,
        "wall_time_s": float(perf_counter() - started),
    }


def _write_attempts_csv(path: Path, cases: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fields = [
        "case_id",
        "rejection_index",
        "attempted_outer_interval_s",
        "at_outer_floor",
        "accepted_bundle",
        "path",
        "root_status",
        "root_failure_code",
        "reduced_residual_inf",
        "full_scaled_residual_inf",
        "full_fixed_point_defect_inf",
        "auxiliary_scaled_residual_inf",
        "root_iterations",
        "map_or_residual_evaluations",
        "krylov_matvecs",
        "backtracks",
        "path_integrity_pass",
        "current_relative_imbalance",
        "power_relative_imbalance",
        "embedded_e_max",
        "attempt_wall_time_s",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for case in cases:
            for attempt in case["attempts"]:
                for path_payload in attempt["paths"]:
                    root = path_payload["root"] or {}
                    candidate = path_payload["candidate"] or {}
                    integrity = candidate.get("integrity") or {}
                    embedded = attempt["embedded_error"] or {}
                    writer.writerow(
                        {
                            "case_id": case["case"]["case_id"],
                            "rejection_index": attempt["rejection_index"],
                            "attempted_outer_interval_s": attempt[
                                "attempted_outer_interval_s"
                            ],
                            "at_outer_floor": attempt["at_outer_floor"],
                            "accepted_bundle": attempt["accepted"],
                            "path": path_payload["path"],
                            "root_status": root.get("status"),
                            "root_failure_code": root.get("failure_code"),
                            "reduced_residual_inf": root.get("reduced_residual_inf"),
                            "full_scaled_residual_inf": root.get(
                                "full_scaled_residual_inf"
                            ),
                            "full_fixed_point_defect_inf": root.get(
                                "full_fixed_point_defect_inf"
                            ),
                            "auxiliary_scaled_residual_inf": root.get(
                                "auxiliary_scaled_residual_inf"
                            ),
                            "root_iterations": root.get("newton_iterations"),
                            "map_or_residual_evaluations": root.get(
                                "reduced_residual_evaluations"
                            ),
                            "krylov_matvecs": root.get("krylov_matvecs"),
                            "backtracks": root.get("line_search_backtracks"),
                            "path_integrity_pass": integrity.get("overall_pass"),
                            "current_relative_imbalance": candidate.get(
                                "relative_current_imbalance"
                            ),
                            "power_relative_imbalance": candidate.get(
                                "relative_power_imbalance"
                            ),
                            "embedded_e_max": embedded.get("e_max"),
                            "attempt_wall_time_s": attempt["wall_time_s"],
                        }
                    )
    temporary.replace(path)


def run_r0_audit(config_path: Path, output_root: Path) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    contract = load_contract(config_path)
    verified = verify_frozen_inputs(contract)
    scientific = resolved_s2_config()
    limits = resolve_and_validate_limits(scientific, contract)
    thread_environment = validate_thread_environment(contract)
    configured_branch = str(contract["identity"]["branch"])
    branch = _git_value("branch", "--show-current")
    if branch != configured_branch:
        raise ValueError(f"R0 must run on {configured_branch}, observed {branch}")
    if _git_value("status", "--porcelain"):
        raise ValueError("R0 requires a clean anchored worktree")
    git_sha = _git_value("rev-parse", "HEAD")
    config_sha = _sha256(config_path)
    output_root = Path(output_root).resolve()
    expected_output_root = (
        ROOT
        / str(contract["outputs"]["namespace"])
        / str(contract["identity"]["r0_run_id"])
    ).resolve()
    if output_root != expected_output_root:
        raise ValueError(
            f"R0 output root must be {expected_output_root}, observed {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot = output_root / str(contract["outputs"]["config_snapshot"])
    _atomic_bytes(snapshot, Path(config_path).read_bytes())
    exact_controller_expected = next(
        item["sha256"]
        for item in verified
        if item["path"]
        == "src/pinnpcm/solvers/geophase_exact_condensed_controller_v2.py"
    )
    started = perf_counter()
    timebox_start = datetime.fromisoformat(
        str(contract["timebox"]["started_utc"]).replace("Z", "+00:00")
    )
    if timebox_start.tzinfo is None:
        raise ValueError("R0-R2 cumulative timebox start must include a timezone")
    cumulative_before_s = max(
        0.0,
        (
            datetime.now(timezone.utc) - timebox_start.astimezone(timezone.utc)
        ).total_seconds(),
    )
    cumulative_limit_s = float(
        contract["timebox"]["r0_r1_r2_cumulative_wall_s_max"]
    )
    cumulative_remaining_s = cumulative_limit_s - cumulative_before_s
    if cumulative_remaining_s <= 0.0:
        raise RuntimeError("R0-R2 cumulative one-day timebox exhausted before R0")
    budget = min(
        float(contract["r0"]["wall_time_s_max"]), cumulative_remaining_s
    )
    results: list[dict[str, Any]] = []
    for case in contract["r0"]["cases"]:
        remaining = budget - (perf_counter() - started)
        if remaining <= 0.0:
            results.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "case": dict(case),
                    "validity": "invalid",
                    "status": "R0_BUDGET_EXHAUSTED_BEFORE_CASE",
                    "claim_status": "forbidden",
                    "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
                    "r1_eligible": False,
                    "attempts": [],
                    "wall_time_s": 0.0,
                }
            )
            break
        try:
            result = run_r0_case(
                case,
                scientific=scientific,
                remaining_wall_s=remaining,
                exact_controller_hash_verified=(
                    exact_controller_expected
                    == (
                        "9a8122949bcd4f7403fd93d627c00469e1fc8d622dc914750093b4989acd66fa"
                    )
                ),
            )
        except Exception as error:  # publish runner defects as invalid evidence
            result = {
                "schema_version": SCHEMA_VERSION,
                "case": dict(case),
                "validity": "invalid",
                "status": "R0_INVALID_RUNNER_OR_SCHEMA_DEFECT",
                "claim_status": "forbidden",
                "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
                "r1_eligible": False,
                "error_class": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                "attempts": [],
                "wall_time_s": 0.0,
            }
        results.append(result)
        case_path = output_root / str(contract["outputs"]["case_directory"])
        _atomic_json(case_path / f"{case['case_id']}.json", result)
        if result["route"] == "STOP_FINAL_FORWARD_SOLVER_RESCUE":
            break
    statuses = [result["status"] for result in results]
    if len(results) == 2 and all(status == "PASS" for status in statuses):
        disposition = "R0_CONTROLLER_RELEVANCE_PASS"
        route = "B3"
        validity = "valid"
        claim_status = "qualified_supported"
    elif results and all(
        result.get("status") == "PASS" or result.get("r1_eligible", False)
        for result in results
    ) and any(result.get("r1_eligible", False) for result in results):
        disposition = "R0_NONLINEAR_FLOOR_FAILURE_R1_AUTHORIZED"
        route = "R1"
        validity = "valid"
        claim_status = "failed_but_informative"
    elif any(
        result.get("route") == "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        and result.get("validity") == "valid"
        for result in results
    ):
        disposition = "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        route = "STOP"
        validity = "valid"
        claim_status = "failed_but_informative"
    else:
        disposition = "INVALID_R0_EXECUTION"
        route = "STOP"
        validity = "invalid"
        claim_status = "forbidden"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["r0_run_id"],
        "invocation_count": int(contract["identity"]["r0_invocation_count"]),
        "invalid_invocation_count": int(
            contract["identity"]["r0_invalid_invocation_count"]
        ),
        "runner_repair_count": int(contract["identity"]["runner_repair_count"]),
        "previous_invalid_invocation": contract["identity"][
            "previous_invalid_invocation"
        ],
        "git_sha": git_sha,
        "branch": branch,
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": config_sha,
        "verified_frozen_inputs": verified,
        "resolved_controller_limits": limits,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "thread_environment": thread_environment,
            "command": sys.argv,
        },
        "validity": validity,
        "disposition": disposition,
        "route": route,
        "lifecycle_state": "executed",
        "claim_status": claim_status,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "case_count": len(results),
        "case_statuses": {
            result["case"]["case_id"]: result["status"] for result in results
        },
        "cases": results,
        "wall_time_s": float(perf_counter() - started),
        "budget_wall_time_s": budget,
        "cumulative_timebox": {
            "started_utc": contract["timebox"]["started_utc"],
            "elapsed_before_r0_s": cumulative_before_s,
            "limit_s": cumulative_limit_s,
            "remaining_before_r0_s": cumulative_remaining_s,
            "external_ci_queue_excluded": bool(
                contract["timebox"]["external_ci_queue_excluded"]
            ),
        },
        "evidence_type": contract["evidence_type"],
    }
    attempts_path = output_root / str(contract["outputs"]["attempts_csv"])
    _write_attempts_csv(attempts_path, results)
    summary["artifacts"] = {
        "attempts_csv": attempts_path.relative_to(ROOT).as_posix(),
        "attempts_csv_sha256": _sha256(attempts_path),
        "config_snapshot": snapshot.relative_to(ROOT).as_posix(),
        "config_snapshot_sha256": _sha256(snapshot),
    }
    summary_path = output_root / str(contract["outputs"]["summary_json"])
    _atomic_json(summary_path, summary)
    return summary


__all__ = [
    "SCHEMA_VERSION",
    "load_contract",
    "resolve_and_validate_limits",
    "run_r0_audit",
    "run_r0_case",
    "validate_thread_environment",
    "verify_frozen_inputs",
]
