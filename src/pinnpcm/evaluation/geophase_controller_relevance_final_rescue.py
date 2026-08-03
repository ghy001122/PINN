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
from typing import Any, Callable, Mapping

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
from pinnpcm.solvers import geophase_exact_condensed as exact_v1
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_exact_condensed import ExactCondensedRootTelemetry
from pinnpcm.solvers.geophase_exact_condensed_anderson import (
    SafeguardedAndersonSettings,
)
from pinnpcm.solvers.geophase_exact_condensed_anderson_controller_v2 import (
    simulate_exact_condensed_anderson_protocol_v2,
)
from pinnpcm.solvers.geophase_exact_condensed_controller_v2 import (
    ExactCondensedEmbeddedAttemptObservation,
    simulate_exact_condensed_protocol_v2,
)


SCHEMA_VERSION = "geophase_controller_relevance_r0_v1"
R1_SCHEMA_VERSION = "geophase_controller_relevance_r1_v1"


class R1BudgetExceeded(RuntimeError):
    """The preregistered R1 wall-time budget expired."""


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
    simulate_protocol: Callable[..., Any] = simulate_exact_condensed_protocol_v2,
    simulation_kwargs: Mapping[str, Any] | None = None,
    stage_label: str = "R0",
    nonlinear_failure_route: str = "R1",
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
        result = simulate_protocol(
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
            **dict(simulation_kwargs or {}),
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
        status, terminal_is_nonlinear = _classify_terminal_failure(
            None if not attempts else attempts[-1]
        )
        status = status.replace("R0_", f"{stage_label}_", 1)
        r1_eligible = bool(
            terminal_is_nonlinear and nonlinear_failure_route == "R1"
        )
        route = (
            "R1" if r1_eligible else "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        )
        validity = (
            "valid"
            if status.startswith(f"{stage_label}_VALID")
            or terminal_is_nonlinear
            else "invalid"
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
        "stage": stage_label,
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
                            "root_iterations": root.get(
                                "iterations", root.get("newton_iterations")
                            ),
                            "map_or_residual_evaluations": root.get(
                                "map_evaluations",
                                root.get("reduced_residual_evaluations"),
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
                        "9a8122949bcd4f7403fd93d627c00469e1fc8d622dc914750093b"
                        "4989acd66fa"
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


def audit_unscaled_fixed_point_contraction(
    phi_temperature: Callable[[np.ndarray], np.ndarray],
    initial_temperature_K: np.ndarray,
    *,
    relaxation: float,
    iteration_count: int,
    gates: Mapping[str, Any],
    validate_temperature: Callable[[np.ndarray], None],
    deadline: float,
) -> dict[str, Any]:
    """Audit the frozen relaxed temperature map without scaled residuals."""

    if iteration_count != 8:
        raise ValueError("the R1 contraction audit requires exactly eight steps")
    if relaxation != 0.5:
        raise ValueError("the R1 contraction audit requires relaxation 0.5")
    temperature = np.asarray(initial_temperature_K, dtype=float).copy()
    if not np.isfinite(temperature).all():
        raise ValueError("R1 initial temperature is nonfinite")
    validate_temperature(temperature)
    shape = temperature.shape
    cells = temperature.size
    map_evaluations = 0

    def checked_phi(candidate: np.ndarray) -> np.ndarray:
        nonlocal map_evaluations
        if perf_counter() >= deadline:
            raise R1BudgetExceeded("R1 contraction audit exceeded its wall budget")
        values = np.asarray(candidate, dtype=float).reshape(shape)
        if not np.isfinite(values).all():
            raise ValueError("R1 temperature iterate is nonfinite")
        validate_temperature(values)
        mapped = np.asarray(phi_temperature(values), dtype=float).reshape(shape)
        map_evaluations += 1
        if not np.isfinite(mapped).all():
            raise FloatingPointError("R1 temperature map returned nonfinite values")
        validate_temperature(mapped)
        return mapped

    def psi(candidate: np.ndarray) -> np.ndarray:
        values = np.asarray(candidate, dtype=float).reshape(shape)
        mapped = checked_phi(values)
        relaxed = values + relaxation * (mapped - values)
        if not np.isfinite(relaxed).all():
            raise FloatingPointError("R1 relaxed Picard iterate is nonfinite")
        validate_temperature(relaxed)
        return relaxed

    defect_history: list[float] = []
    iterate_temperature_inf: list[float] = []
    for step_index in range(iteration_count + 1):
        mapped = checked_phi(temperature)
        defect = temperature - mapped
        defect_history.append(float(np.max(np.abs(defect))))
        iterate_temperature_inf.append(float(np.max(np.abs(temperature))))
        if step_index < iteration_count:
            temperature = temperature - relaxation * defect
            if not np.isfinite(temperature).all():
                raise FloatingPointError("R1 relaxed Picard iterate is nonfinite")
            validate_temperature(temperature)

    ratios: list[float] = []
    for previous, current in zip(defect_history[:-1], defect_history[1:]):
        if previous == 0.0:
            ratios.append(0.0 if current == 0.0 else float("inf"))
        else:
            ratios.append(float(current / previous))
    last_four = ratios[-4:]
    if len(last_four) != 4:
        raise ValueError("R1 did not produce four terminal contraction ratios")
    if any(not np.isfinite(value) for value in last_four):
        geometric_mean = float("inf")
    elif any(value == 0.0 for value in last_four):
        geometric_mean = 0.0
    else:
        geometric_mean = float(
            np.exp(np.mean(np.log(np.asarray(last_four, dtype=float))))
        )

    epsilon = np.finfo(float).eps
    finite_difference_h = float(
        epsilon ** (1.0 / 3.0)
        * max(1.0, float(np.max(np.abs(temperature))))
    )
    jacobian = np.empty((cells, cells), dtype=float)
    flat = temperature.reshape(-1)
    for column in range(cells):
        perturbation = np.zeros(cells, dtype=float)
        perturbation[column] = finite_difference_h
        plus = psi((flat + perturbation).reshape(shape)).reshape(-1)
        minus = psi((flat - perturbation).reshape(shape)).reshape(-1)
        jacobian[:, column] = (plus - minus) / (2.0 * finite_difference_h)
    if not np.isfinite(jacobian).all():
        raise FloatingPointError("R1 central-difference Jacobian is nonfinite")

    eigenvalues, eigenvectors = np.linalg.eig(jacobian)
    spectral_radius = float(np.max(np.abs(eigenvalues)))
    operator_norm_2 = float(np.linalg.norm(jacobian, ord=2))
    eigenvector_condition = float(np.linalg.cond(eigenvectors))
    transpose_commutator = jacobian.T @ jacobian - jacobian @ jacobian.T
    frobenius = float(np.linalg.norm(jacobian, ord="fro"))
    nonnormality = float(
        np.linalg.norm(transpose_commutator, ord="fro")
        / max(frobenius * frobenius, epsilon)
    )
    power = np.eye(cells, dtype=float)
    power_norms: list[float] = []
    for _ in range(8):
        power = power @ jacobian
        power_norms.append(float(np.linalg.norm(power, ord=2)))
    maximum_power_norm = float(max(power_norms))
    jacobian_sha256 = hashlib.sha256(
        np.asarray(jacobian, dtype="<f8", order="C").tobytes(order="C")
    ).hexdigest()

    gate_results = {
        "all_iterates_finite_and_range_legal": True,
        "last_four_ratios_strictly_below_one": bool(
            all(value < 1.0 for value in last_four)
        ),
        "last_four_geometric_mean": bool(
            geometric_mean
            <= float(gates["last_four_geometric_mean_max"])
        ),
        "step_8_defect_relative_to_initial": bool(
            defect_history[-1]
            <= float(gates["step_8_defect_relative_to_initial_max"])
            * defect_history[0]
        ),
        "spectral_radius": bool(
            spectral_radius < float(gates["spectral_radius_max_exclusive"])
        ),
        "maximum_power_norm_k_1_to_8": bool(
            maximum_power_norm
            <= float(gates["maximum_power_norm_k_1_to_8"])
        ),
    }
    gate_results["all_required"] = bool(all(gate_results.values()))
    return {
        "relaxation": float(relaxation),
        "iteration_count": int(iteration_count),
        "defect_history_inf_K": defect_history,
        "contraction_ratios": ratios,
        "last_four_ratios": last_four,
        "last_four_geometric_mean_ratio": geometric_mean,
        "step_8_relative_defect": (
            0.0
            if defect_history[0] == 0.0 and defect_history[-1] == 0.0
            else float(defect_history[-1] / defect_history[0])
        ),
        "iterate_temperature_inf_K": iterate_temperature_inf,
        "central_difference_h_K": finite_difference_h,
        "central_difference_rule": "eps^(1/3)*max(1,||T8||inf)",
        "jacobian_shape": [cells, cells],
        "jacobian_sha256_little_endian_float64": jacobian_sha256,
        "spectral_radius": spectral_radius,
        "operator_norm_2": operator_norm_2,
        "eigenvector_condition": (
            None if not np.isfinite(eigenvector_condition) else eigenvector_condition
        ),
        "eigenvector_condition_finite": bool(np.isfinite(eigenvector_condition)),
        "nonnormality_frobenius_commutator_ratio": nonnormality,
        "power_norms_2_k_1_to_8": power_norms,
        "maximum_power_norm_k_1_to_8": maximum_power_norm,
        "map_evaluations": int(map_evaluations),
        "gates": gate_results,
    }


def _r1_temperature_map(
    candidate_temperature_K: np.ndarray,
    *,
    old_state: production.S2State,
    input_voltage_V: float,
    dt_s: float,
    grid: Any,
    closure: Any,
    fields: Any,
    scientific: dict[str, Any],
    cache: production.S2SolverCache,
) -> np.ndarray:
    auxiliary = exact_v1.reconstruct_exact_auxiliary_state(
        candidate_temperature_K,
        old_state,
        dt_s,
        input_voltage_V,
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        cache=cache,
    )
    load_resistance, capacitance = production._circuit_parameters(scientific)
    mapped = production._fixed_point_map(
        auxiliary.full_vector,
        old_state=old_state,
        input_voltage_V=float(input_voltage_V),
        dt_s=float(dt_s),
        grid=grid,
        closure=closure,
        fields=fields,
        lateral_matrix=cache.lateral_matrix,
        thermal_linear_solver=cache.thermal_solver(dt_s),
        electrical_topology=cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=None,
        load_resistance_ohm=load_resistance,
        capacitance_F=capacitance,
    )
    mapped_temperature, _, _, _ = production._unpack(mapped, grid)
    return np.asarray(mapped_temperature, dtype=float)


def run_r1_context(
    context: Mapping[str, Any],
    *,
    scientific: dict[str, Any],
    contract: Mapping[str, Any],
    deadline: float,
) -> dict[str, Any]:
    started = perf_counter()
    level = int(context["spatial_level"])
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    old_state = _state_from_replay(context["old_state"])
    production.validate_s2_state(old_state, grid, closure)
    dt_s = float(context["dt_s"])
    input_voltage = float(context["input_voltage_V"])
    try:
        predictor = exact_v1._predict_temperature(
            old_state=old_state,
            input_voltage_V=input_voltage,
            dt_s=dt_s,
            grid=grid,
            closure=closure,
            fields=fields,
            config=scientific,
            cache=cache,
            performance_timings=None,
        )
        metrics = audit_unscaled_fixed_point_contraction(
            lambda candidate: _r1_temperature_map(
                candidate,
                old_state=old_state,
                input_voltage_V=input_voltage,
                dt_s=dt_s,
                grid=grid,
                closure=closure,
                fields=fields,
                scientific=scientific,
                cache=cache,
            ),
            predictor,
            relaxation=float(contract["r1"]["relaxation"]),
            iteration_count=int(contract["r1"]["relaxed_picard_steps"]),
            gates=contract["r1"]["gates"],
            validate_temperature=closure.validate_temperature,
            deadline=deadline,
        )
    except R1BudgetExceeded as error:
        return {
            "schema_version": R1_SCHEMA_VERSION,
            "context_sha256": context["complete_input_sha256"],
            "context": dict(context),
            "validity": "invalid",
            "status": "R1_BUDGET_EXHAUSTED",
            "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "error_class": type(error).__name__,
            "error_message": str(error),
            "wall_time_s": float(perf_counter() - started),
        }
    except (
        RuntimeError,
        ValueError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as error:
        return {
            "schema_version": R1_SCHEMA_VERSION,
            "context_sha256": context["complete_input_sha256"],
            "context": dict(context),
            "validity": "valid",
            "status": "R1_VALID_MAP_OR_RANGE_FAILURE",
            "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
            "lifecycle_state": "executed",
            "claim_status": "failed_but_informative",
            "error_class": type(error).__name__,
            "error_message": str(error),
            "wall_time_s": float(perf_counter() - started),
        }
    passed = bool(metrics["gates"]["all_required"])
    return {
        "schema_version": R1_SCHEMA_VERSION,
        "context_sha256": context["complete_input_sha256"],
        "context": dict(context),
        "validity": "valid",
        "status": "R1_CONTRACTION_PASS" if passed else "R1_CONTRACTION_VALID_FAIL",
        "route": "R2" if passed else "STOP_FINAL_FORWARD_SOLVER_RESCUE",
        "lifecycle_state": "numerically_validated",
        "claim_status": "qualified_supported" if passed else "failed_but_informative",
        "metrics": metrics,
        "wall_time_s": float(perf_counter() - started),
    }


def run_r1_audit(config_path: Path, output_root: Path) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    contract = load_contract(config_path)
    verified = verify_frozen_inputs(contract)
    scientific = resolved_s2_config()
    limits = resolve_and_validate_limits(scientific, contract)
    thread_environment = validate_thread_environment(contract)
    configured_branch = str(contract["identity"]["branch"])
    branch = _git_value("branch", "--show-current")
    if branch != configured_branch:
        raise ValueError(f"R1 must run on {configured_branch}, observed {branch}")
    if _git_value("status", "--porcelain"):
        raise ValueError("R1 requires a clean anchored worktree")
    git_sha = _git_value("rev-parse", "HEAD")
    parent_path = (ROOT / str(contract["r1"]["parent_r0_summary"])).resolve()
    if _sha256(parent_path) != str(contract["r1"]["parent_r0_summary_sha256"]):
        raise ValueError("R1 parent R0 summary hash differs from its contract")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if parent.get("disposition") != "R0_NONLINEAR_FLOOR_FAILURE_R1_AUTHORIZED":
        raise ValueError("R1 parent did not authorize the contraction audit")
    contexts_by_hash: dict[str, dict[str, Any]] = {}
    for case in parent["cases"]:
        context = case.get("r1_terminal_context")
        if not case.get("r1_eligible", False):
            continue
        if not isinstance(context, dict):
            raise ValueError("R1-eligible case lacks its terminal root context")
        contexts_by_hash[str(context["complete_input_sha256"])] = context
    if not contexts_by_hash:
        raise ValueError("R1 found no actual floor-terminal root context")

    output_root = Path(output_root).resolve()
    expected_output_root = (
        ROOT
        / str(contract["outputs"]["namespace"])
        / str(contract["identity"]["r1_run_id"])
    ).resolve()
    if output_root != expected_output_root:
        raise ValueError(
            f"R1 output root must be {expected_output_root}, observed {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot = output_root / str(contract["outputs"]["config_snapshot"])
    _atomic_bytes(snapshot, config_path.read_bytes())

    timebox_start = datetime.fromisoformat(
        str(contract["timebox"]["started_utc"]).replace("Z", "+00:00")
    )
    cumulative_before_s = max(
        0.0,
        (
            datetime.now(timezone.utc) - timebox_start.astimezone(timezone.utc)
        ).total_seconds(),
    )
    cumulative_limit_s = float(
        contract["timebox"]["r0_r1_r2_cumulative_wall_s_max"]
    )
    remaining = cumulative_limit_s - cumulative_before_s
    if remaining <= 0.0:
        raise RuntimeError("R0-R2 cumulative one-day timebox exhausted before R1")
    budget = min(float(contract["r1"]["wall_time_s_max"]), remaining)
    started = perf_counter()
    deadline = started + budget
    results: list[dict[str, Any]] = []
    context_root = output_root / str(contract["outputs"]["r1_case_directory"])
    for context_hash, context in contexts_by_hash.items():
        try:
            result = run_r1_context(
                context,
                scientific=scientific,
                contract=contract,
                deadline=deadline,
            )
        except Exception as error:
            # The repair budget is exhausted; preserve an invalid terminal result.
            result = {
                "schema_version": R1_SCHEMA_VERSION,
                "context_sha256": context_hash,
                "context": context,
                "validity": "invalid",
                "status": "R1_INVALID_RUNNER_DEFECT",
                "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
                "lifecycle_state": "executed",
                "claim_status": "forbidden",
                "error_class": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                "wall_time_s": 0.0,
            }
        results.append(result)
        _atomic_json(context_root / f"{context_hash}.json", result)
        if result["status"] != "R1_CONTRACTION_PASS":
            break

    if len(results) == len(contexts_by_hash) and all(
        result["status"] == "R1_CONTRACTION_PASS" for result in results
    ):
        disposition = "R1_CONTRACTION_PASS_R2_AUTHORIZED"
        route = "R2"
        validity = "valid"
        claim_status = "qualified_supported"
        lifecycle_state = "numerically_validated"
    elif any(result["validity"] == "valid" for result in results):
        disposition = "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        route = "STOP"
        validity = "valid"
        claim_status = "failed_but_informative"
        lifecycle_state = "numerically_validated"
    else:
        disposition = "INVALID_R1_EXECUTION_STOP_FINAL_FORWARD_SOLVER_RESCUE"
        route = "STOP"
        validity = "invalid"
        claim_status = "forbidden"
        lifecycle_state = "executed"
    summary = {
        "schema_version": R1_SCHEMA_VERSION,
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["r1_run_id"],
        "git_sha": git_sha,
        "branch": branch,
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha256(config_path),
        "parent_r0_summary": parent_path.relative_to(ROOT).as_posix(),
        "parent_r0_summary_sha256": _sha256(parent_path),
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
        "lifecycle_state": lifecycle_state,
        "claim_status": claim_status,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "context_count": len(results),
        "deduplicated_context_count": len(contexts_by_hash),
        "contexts": results,
        "wall_time_s": float(perf_counter() - started),
        "budget_wall_time_s": budget,
        "cumulative_timebox": {
            "started_utc": contract["timebox"]["started_utc"],
            "elapsed_before_r1_s": cumulative_before_s,
            "limit_s": cumulative_limit_s,
            "remaining_before_r1_s": remaining,
            "external_ci_queue_excluded": bool(
                contract["timebox"]["external_ci_queue_excluded"]
            ),
        },
        "evidence_type": contract["evidence_type"],
        "artifacts": {
            "config_snapshot": snapshot.relative_to(ROOT).as_posix(),
            "config_snapshot_sha256": _sha256(snapshot),
        },
    }
    summary_path = output_root / str(contract["outputs"]["r1_summary_json"])
    _atomic_json(summary_path, summary)
    return summary


def _r2_settings(contract: Mapping[str, Any]) -> SafeguardedAndersonSettings:
    frozen = contract["r2"]["map"]
    settings = SafeguardedAndersonSettings(
        depth=int(frozen["anderson_depth"]),
        relaxation=float(frozen["relaxation"]),
        maximum_map_evaluations=int(frozen["maximum_map_evaluations_per_root"]),
        coefficient_regularization=float(frozen["coefficient_regularization"]),
        svd_rcond=float(frozen["svd_rcond"]),
        residual_scale_floor_K=float(frozen["residual_scale_floor_K"]),
        sufficient_decrease_c1=float(frozen["sufficient_decrease_c1"]),
    )
    settings.validate()
    return settings


def run_r2_qualification(config_path: Path, output_root: Path) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    contract = load_contract(config_path)
    verified = verify_frozen_inputs(contract)
    scientific = resolved_s2_config()
    limits = resolve_and_validate_limits(scientific, contract)
    thread_environment = validate_thread_environment(contract)
    settings = _r2_settings(contract)
    configured_branch = str(contract["identity"]["branch"])
    branch = _git_value("branch", "--show-current")
    if branch != configured_branch:
        raise ValueError(f"R2 must run on {configured_branch}, observed {branch}")
    if _git_value("status", "--porcelain"):
        raise ValueError("R2 requires a clean anchored worktree")
    git_sha = _git_value("rev-parse", "HEAD")
    parent_path = (ROOT / str(contract["r2"]["parent_r1_summary"])).resolve()
    if _sha256(parent_path) != str(contract["r2"]["parent_r1_summary_sha256"]):
        raise ValueError("R2 parent R1 summary hash differs from its contract")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if parent.get("disposition") != "R1_CONTRACTION_PASS_R2_AUTHORIZED":
        raise ValueError("R2 parent did not authorize safeguarded Anderson")

    output_root = Path(output_root).resolve()
    expected_output_root = (
        ROOT
        / str(contract["outputs"]["namespace"])
        / str(contract["identity"]["r2_run_id"])
    ).resolve()
    if output_root != expected_output_root:
        raise ValueError(
            f"R2 output root must be {expected_output_root}, observed {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot = output_root / str(contract["outputs"]["config_snapshot"])
    _atomic_bytes(snapshot, config_path.read_bytes())

    timebox_start = datetime.fromisoformat(
        str(contract["timebox"]["started_utc"]).replace("Z", "+00:00")
    )
    cumulative_before_s = max(
        0.0,
        (
            datetime.now(timezone.utc) - timebox_start.astimezone(timezone.utc)
        ).total_seconds(),
    )
    cumulative_limit_s = float(
        contract["timebox"]["r0_r1_r2_cumulative_wall_s_max"]
    )
    remaining = cumulative_limit_s - cumulative_before_s
    if remaining <= 0.0:
        raise RuntimeError("R0-R2 cumulative one-day timebox exhausted before R2")
    budget = min(float(contract["r2"]["qualification_wall_time_s_max"]), remaining)
    started = perf_counter()
    results: list[dict[str, Any]] = []
    exact_controller_expected = next(
        item["sha256"]
        for item in verified
        if item["path"]
        == "src/pinnpcm/solvers/geophase_exact_condensed_controller_v2.py"
    )
    for case in contract["r0"]["cases"]:
        case_remaining = budget - (perf_counter() - started)
        if case_remaining <= 0.0:
            results.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "stage": "R2",
                    "case": dict(case),
                    "validity": "invalid",
                    "status": "R2_BUDGET_EXHAUSTED_BEFORE_CASE",
                    "claim_status": "forbidden",
                    "route": "STOP_FINAL_FORWARD_SOLVER_RESCUE",
                    "r1_eligible": False,
                    "attempts": [],
                    "wall_time_s": 0.0,
                }
            )
            break
        result = run_r0_case(
            case,
            scientific=scientific,
            remaining_wall_s=case_remaining,
            exact_controller_hash_verified=(
                exact_controller_expected
                == (
                    "9a8122949bcd4f7403fd93d627c00469e1fc8d622dc914750093b"
                    "4989acd66fa"
                )
            ),
            simulate_protocol=simulate_exact_condensed_anderson_protocol_v2,
            simulation_kwargs={"anderson_settings": settings},
            stage_label="R2",
            nonlinear_failure_route="STOP_FINAL_FORWARD_SOLVER_RESCUE",
        )
        results.append(result)
        case_root = output_root / str(contract["outputs"]["r2_case_directory"])
        _atomic_json(case_root / f"{case['case_id']}.json", result)
        if result["status"] != "PASS":
            break

    statuses = [result["status"] for result in results]
    if len(results) == 2 and all(status == "PASS" for status in statuses):
        disposition = "R2_CONTROLLER_ADMISSIBLE_QUALIFICATION_PASS"
        route = "B3"
        validity = "valid"
        claim_status = "qualified_supported"
        lifecycle_state = "numerically_validated"
    elif any(result.get("validity") == "valid" for result in results):
        disposition = "STOP_FINAL_FORWARD_SOLVER_RESCUE"
        route = "STOP"
        validity = "valid"
        claim_status = "failed_but_informative"
        lifecycle_state = "numerically_validated"
    else:
        disposition = "INVALID_R2_EXECUTION_STOP_FINAL_FORWARD_SOLVER_RESCUE"
        route = "STOP"
        validity = "invalid"
        claim_status = "forbidden"
        lifecycle_state = "executed"

    attempts_path = output_root / str(contract["outputs"]["r2_attempts_csv"])
    _write_attempts_csv(attempts_path, results)
    summary = {
        "schema_version": "geophase_controller_relevance_r2_v1",
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["r2_run_id"],
        "solver_id": contract["r2"]["solver_id"],
        "git_sha": git_sha,
        "branch": branch,
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha256(config_path),
        "parent_r1_summary": parent_path.relative_to(ROOT).as_posix(),
        "parent_r1_summary_sha256": _sha256(parent_path),
        "verified_frozen_inputs": verified,
        "resolved_controller_limits": limits,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "thread_environment": thread_environment,
            "command": sys.argv,
        },
        "settings": asdict(settings),
        "validity": validity,
        "disposition": disposition,
        "route": route,
        "lifecycle_state": lifecycle_state,
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
            "elapsed_before_r2_s": cumulative_before_s,
            "limit_s": cumulative_limit_s,
            "remaining_before_r2_s": remaining,
            "external_ci_queue_excluded": bool(
                contract["timebox"]["external_ci_queue_excluded"]
            ),
        },
        "evidence_type": contract["evidence_type"],
        "artifacts": {
            "attempts_csv": attempts_path.relative_to(ROOT).as_posix(),
            "attempts_csv_sha256": _sha256(attempts_path),
            "config_snapshot": snapshot.relative_to(ROOT).as_posix(),
            "config_snapshot_sha256": _sha256(snapshot),
        },
    }
    summary_path = output_root / str(contract["outputs"]["r2_summary_json"])
    _atomic_json(summary_path, summary)
    return summary


__all__ = [
    "R1_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "audit_unscaled_fixed_point_contraction",
    "load_contract",
    "resolve_and_validate_limits",
    "run_r0_audit",
    "run_r0_case",
    "run_r1_audit",
    "run_r1_context",
    "run_r2_qualification",
    "validate_thread_environment",
    "verify_frozen_inputs",
]
