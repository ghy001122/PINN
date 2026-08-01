"""Nonzero-drive controller-v3 with output-grid-independent integration.

The inner backward-Euler solves, embedded full-step/two-half-step estimator,
integrity gates, and numerical thresholds are inherited unchanged from
controller-v2.  Controller-v3 changes only the outer scheduling contract:
protocol discontinuities and the requested final time are mandatory landings;
fixed reporting times are reconstructed by the streaming layer and never
constrain the adaptive integrator.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import traceback
from time import perf_counter
from typing import Any, Callable

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    S2EmbeddedAdaptiveDiagnostics,
    S2EmbeddedAttemptObservation,
    S2EmbeddedStepResult,
    attempt_s2_embedded_interval,
    controller_v2_limits,
    protocol_voltage_scale,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2PerformanceTimings,
    S2ProtocolResult,
    S2SolverCache,
    S2State,
    protocol_discontinuities,
    validate_s2_state,
)


CONTROLLER_V3_ID = "nonzero_drive_output_decoupled_controller_v3"
FAILURE_SCHEMA_VERSION = "geophase_controller_v3_failure_attempt_v1"


def _state_hash(state: S2State) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray([state.time_s, state.device_voltage_V], dtype="<f8").tobytes())
    for values in (
        state.temperature_K,
        state.conductive_state,
        state.branch_memory,
    ):
        array = np.ascontiguousarray(np.asarray(values, dtype="<f8"))
        digest.update(np.asarray(array.shape, dtype="<i8").tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _state_replay_payload(state: S2State) -> dict[str, Any]:
    return {
        "time_s": float(state.time_s),
        "device_voltage_V": float(state.device_voltage_V),
        "temperature_K": np.asarray(state.temperature_K, dtype=float).tolist(),
        "conductive_state": np.asarray(state.conductive_state, dtype=float).tolist(),
        "branch_memory": np.asarray(state.branch_memory, dtype=float).tolist(),
    }


def _nonlinear_payload(candidate: Any | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    nonlinear = candidate.nonlinear
    return {
        "method": str(nonlinear.method),
        "iterations": int(nonlinear.iterations),
        "scaled_residual_inf": float(nonlinear.scaled_residual_inf),
        "scaled_update_inf": float(nonlinear.scaled_update_inf),
        "converged": bool(nonlinear.converged),
        "krylov_matvecs": int(nonlinear.krylov_matvecs),
        "armijo_backtracks": int(nonlinear.armijo_backtracks),
        "predictor_picard_iterations": int(nonlinear.predictor_picard_iterations),
        "fallback_picard_iterations": int(nonlinear.fallback_picard_iterations),
    }


def _attempt_payload(
    observation: S2EmbeddedAttemptObservation,
    *,
    case_id: str,
    protocol_id: str,
    time_divisor: int,
    proposed_outer_interval_s: float,
    attempted_outer_interval_s: float,
    floor_outer_interval_s: float,
    target_time_s: float,
    next_discontinuity_s: float | None,
    remaining_to_target_s: float,
    terminal: bool,
    terminal_reason: str | None = None,
) -> dict[str, Any]:
    embedded = observation.diagnostics.embedded_error
    integrity_failure = bool(
        observation.error_class is not None
        or observation.diagnostics.aggregate is None
        or not observation.diagnostics.full_step.overall_pass
        or observation.diagnostics.first_half_step is None
        or not observation.diagnostics.first_half_step.overall_pass
        or observation.diagnostics.second_half_step is None
        or not observation.diagnostics.second_half_step.overall_pass
        or not observation.diagnostics.aggregate.overall_pass
    )
    return {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "controller_id": CONTROLLER_V3_ID,
        "case_id": str(case_id),
        "protocol_id": str(protocol_id),
        "time_divisor": int(time_divisor),
        "current_time_s": float(observation.previous_state.time_s),
        "target_time_s": float(target_time_s),
        "next_discontinuity_s": (
            None if next_discontinuity_s is None else float(next_discontinuity_s)
        ),
        "remaining_to_target_s": float(remaining_to_target_s),
        "proposed_outer_interval_s": float(proposed_outer_interval_s),
        "attempted_outer_interval_s": float(attempted_outer_interval_s),
        "floor_outer_interval_s": float(floor_outer_interval_s),
        "below_floor_mandatory_remainder": bool(
            observation.diagnostics.below_floor_remainder
        ),
        "at_outer_floor": bool(observation.diagnostics.at_outer_floor),
        "rejection_index": int(observation.diagnostics.rejection_index),
        "accepted": observation.step is not None,
        "terminal": bool(terminal),
        "terminal_reason": terminal_reason,
        "rejection_class": (
            None
            if observation.step is not None
            else "integrity_or_solver"
            if integrity_failure
            else "embedded_error"
        ),
        "error_class": observation.error_class,
        "error_message": observation.error_message,
        "candidate_presence": {
            "full_step": observation.full_candidate is not None,
            "first_half_step": observation.first_half_candidate is not None,
            "second_half_step": observation.second_half_candidate is not None,
        },
        "path_integrity": {
            "full_step": bool(observation.diagnostics.full_step.overall_pass),
            "first_half_step": (
                None
                if observation.diagnostics.first_half_step is None
                else bool(observation.diagnostics.first_half_step.overall_pass)
            ),
            "second_half_step": (
                None
                if observation.diagnostics.second_half_step is None
                else bool(observation.diagnostics.second_half_step.overall_pass)
            ),
            "aggregate": (
                None
                if observation.diagnostics.aggregate is None
                else bool(observation.diagnostics.aggregate.overall_pass)
            ),
        },
        "embedded_error": (
            None
            if embedded is None
            else {
                "e_T": float(embedded.e_T),
                "e_s": float(embedded.e_s),
                "e_b": float(embedded.e_b),
                "e_V": float(embedded.e_V),
                "e_max": float(embedded.e_max),
            }
        ),
        "nonlinear": {
            "full_step": _nonlinear_payload(observation.full_candidate),
            "first_half_step": _nonlinear_payload(observation.first_half_candidate),
            "second_half_step": _nonlinear_payload(observation.second_half_candidate),
        },
        "last_valid_state_sha256": _state_hash(observation.previous_state),
    }


class ControllerV3ExecutionError(RuntimeError):
    """Fail-closed controller-v3 terminal carrying a replayable record."""

    def __init__(self, message: str, record: dict[str, Any]):
        super().__init__(message)
        self.record = record


def _raise_terminal(
    message: str,
    observation: S2EmbeddedAttemptObservation,
    payload: dict[str, Any],
    *,
    failure_callback: Callable[[dict[str, Any]], None] | None,
) -> None:
    record = {
        **payload,
        "terminal": True,
        "terminal_reason": message,
        "exception_class": "ControllerV3ExecutionError",
        "exception_message": message,
        "traceback": "".join(traceback.format_stack()),
        "replay": {
            "previous_state": _state_replay_payload(observation.previous_state),
            "attempted_outer_interval_s": float(
                observation.diagnostics.outer_interval_s
            ),
            "full_input_voltage_V": float(
                observation.diagnostics.full_input_voltage_V
            ),
            "first_half_input_voltage_V": float(
                observation.diagnostics.first_half_input_voltage_V
            ),
            "second_half_input_voltage_V": float(
                observation.diagnostics.second_half_input_voltage_V
            ),
        },
    }
    if failure_callback is not None:
        failure_callback(record)
    raise ControllerV3ExecutionError(message, record)


def _empty_diagnostics(**values: Any) -> S2EmbeddedAdaptiveDiagnostics:
    defaults: dict[str, Any] = {
        "accepted_steps": 0,
        "rejected_steps": 0,
        "transition_rejections": 0,
        "nonlinear_rejections": 0,
        "endpoint_remainder_steps": 0,
        "minimum_accepted_step_s": 0.0,
        "maximum_accepted_step_s": 0.0,
        "maximum_transition_increment": 0.0,
        "fallback_steps": 0,
        "newton_iterations": 0,
        "krylov_matvecs": 0,
        "armijo_backtracks": 0,
        "fallback_picard_iterations": 0,
        "step_wall_time_p50_s": 0.0,
        "step_wall_time_p90_s": 0.0,
        "step_wall_time_max_s": 0.0,
        "accepted_dt_p10_s": 0.0,
        "accepted_dt_p50_s": 0.0,
        "accepted_dt_p90_s": 0.0,
        "embedded_error_rejections": 0,
        "integrity_rejections": 0,
        "locked_floor_failures": 0,
        "growth_events": 0,
        "full_step_solves": 0,
        "half_step_solves": 0,
        "total_coupled_solves": 0,
        "maximum_e_T": 0.0,
        "maximum_e_s": 0.0,
        "maximum_e_b": 0.0,
        "maximum_e_V": 0.0,
        "maximum_e_max": 0.0,
    }
    defaults.update(values)
    return S2EmbeddedAdaptiveDiagnostics(**defaults)


def simulate_s2_protocol_v3(
    initial_state: S2State,
    *,
    case_id: str,
    protocol: dict,
    protocol_id: str,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    time_divisor: int = 1,
    final_time_s: float | None = None,
    maximum_accepted_steps: int | None = None,
    maximum_wall_clock_s: float | None = None,
    retain_full_history: bool = True,
    retained_step_limit: int = 0,
    accepted_step_callback: Callable[
        [S2State, S2EmbeddedStepResult, float, float, float], None
    ]
    | None = None,
    attempted_candidate_callback: Callable[[S2EmbeddedAttemptObservation], None]
    | None = None,
    attempt_record_callback: Callable[[dict[str, Any]], None] | None = None,
    failure_callback: Callable[[dict[str, Any]], None] | None = None,
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
    performance_timings: S2PerformanceTimings | None = None,
) -> S2ProtocolResult:
    """Advance one protocol without using reporting times as solver landings."""

    if not case_id:
        raise ValueError("controller-v3 requires a nonempty case_id")
    if maximum_accepted_steps is not None and maximum_accepted_steps <= 0:
        raise ValueError("maximum_accepted_steps must be positive")
    if maximum_wall_clock_s is not None and (
        not np.isfinite(maximum_wall_clock_s) or maximum_wall_clock_s <= 0.0
    ):
        raise ValueError("maximum_wall_clock_s must be finite and positive")
    if retained_step_limit < 0:
        raise ValueError("retained_step_limit cannot be negative")

    maximum_H, floor_H = controller_v2_limits(config, time_divisor)
    stop = float(
        config["reference_solver"]["time_grid"]["final_time_s"]
        if final_time_s is None
        else final_time_s
    )
    if not np.isfinite(stop) or stop <= initial_state.time_s:
        raise ValueError("controller-v3 final time must follow its initial time")
    protocol_voltage_scale(config, protocol_id)
    discontinuities = tuple(
        float(value)
        for value in protocol_discontinuities(protocol)
        if initial_state.time_s < float(value) <= stop
    )
    fields.validate_grid(grid)
    validate_s2_state(initial_state, grid, closure)
    if cache is not None:
        cache.validate_context(grid, fields)

    # The embedded estimator and its thresholds remain the frozen v2 object;
    # only this module's outer scheduling policy is versioned as controller-v3.
    controller = config["reference_solver"]["active_time_controller"]
    rejection_cap = int(controller["outer_interval"]["outer_rejection_cap"])
    case_rejection_cap = int(
        config["reference_solver"]["time_grid"]["maximum_rejected_steps_per_case"]
    )
    easy_max = float(controller["growth"]["easy_error_max"])
    easy_required = int(controller["growth"]["required_consecutive_easy_intervals"])
    eps = max(1.0e-18, abs(stop) * 1.0e-14)

    state = initial_state
    current_H = maximum_H
    steps: list[S2EmbeddedStepResult] = []
    accepted_dts: list[float] = []
    interval_wall_times: list[float] = []
    accepted_steps = rejected = 0
    embedded_rejections = integrity_rejections = 0
    endpoint_remainders = growth_events = 0
    full_solves = half_solves = total_solves = 0
    newton_iterations = krylov = armijo = fallback_picard = fallback_steps = 0
    maximum_increment = 0.0
    maxima = {name: 0.0 for name in ("e_T", "e_s", "e_b", "e_V", "e_max")}
    easy_streak = 0
    minimum_H = float("inf")
    maximum_accepted_H = 0.0
    stop_reason = "requested_final_time_reached"
    started = perf_counter()

    while state.time_s < stop - eps:
        if maximum_wall_clock_s is not None and perf_counter() - started >= maximum_wall_clock_s:
            stop_reason = "maximum_wall_clock_reached"
            break
        if maximum_accepted_steps is not None and accepted_steps >= maximum_accepted_steps:
            stop_reason = "maximum_accepted_steps_reached"
            break

        future = [value for value in discontinuities if value > state.time_s + eps]
        next_discontinuity = min(future) if future else None
        target = stop if next_discontinuity is None else min(stop, next_discontinuity)
        proposal_H = current_H
        remaining = target - state.time_s
        H = min(proposal_H, remaining)
        below_floor_remainder = H < floor_H - eps
        previous_state = state
        rejection_index = 0
        had_rejection = False
        interval_started = perf_counter()

        while True:
            observation = attempt_s2_embedded_interval(
                state,
                protocol=protocol,
                protocol_id=protocol_id,
                outer_interval_s=H,
                grid=grid,
                closure=closure,
                fields=fields,
                config=config,
                rejection_index=rejection_index,
                below_floor_remainder=below_floor_remainder,
                at_outer_floor=bool(H <= floor_H * (1.0 + 1.0e-12)),
                cache=cache,
                use_equivalent_optimizations=use_equivalent_optimizations,
                use_unit_voltage_scaling=use_unit_voltage_scaling,
                performance_timings=performance_timings,
            )
            if attempted_candidate_callback is not None:
                attempted_candidate_callback(observation)
            attempt_record = _attempt_payload(
                observation,
                case_id=case_id,
                protocol_id=protocol_id,
                time_divisor=time_divisor,
                proposed_outer_interval_s=proposal_H,
                attempted_outer_interval_s=H,
                floor_outer_interval_s=floor_H,
                target_time_s=target,
                next_discontinuity_s=next_discontinuity,
                remaining_to_target_s=remaining,
                terminal=False,
            )
            if attempt_record_callback is not None:
                attempt_record_callback(attempt_record)

            solves = observation.diagnostics.coupled_solve_count
            total_solves += solves
            full_solves += int(solves >= 1)
            half_solves += int(solves >= 2) + int(solves >= 3)
            for candidate_path in (
                observation.full_candidate,
                observation.first_half_candidate,
                observation.second_half_candidate,
            ):
                if candidate_path is None:
                    continue
                nonlinear = candidate_path.nonlinear
                newton_iterations += nonlinear.iterations
                krylov += nonlinear.krylov_matvecs
                armijo += nonlinear.armijo_backtracks
                fallback_picard += nonlinear.fallback_picard_iterations
            embedded = observation.diagnostics.embedded_error
            if embedded is not None:
                for name in maxima:
                    maxima[name] = max(maxima[name], float(getattr(embedded, name)))
            if observation.step is not None:
                candidate = observation.step
                break

            integrity_failure = bool(attempt_record["rejection_class"] == "integrity_or_solver")
            integrity_rejections += int(integrity_failure)
            embedded_rejections += int(not integrity_failure)
            terminal_message: str | None = None
            if below_floor_remainder:
                terminal_message = "controller-v3 mandatory landing remainder failed closed"
            elif H <= floor_H * (1.0 + 1.0e-12):
                terminal_message = "controller-v3 failed at locked outer floor"
            elif rejected + 1 > case_rejection_cap:
                terminal_message = "controller-v3 per-case rejection cap exceeded"
            elif rejection_index + 1 > rejection_cap:
                terminal_message = "controller-v3 outer rejection cap exceeded"
            if terminal_message is not None:
                _raise_terminal(
                    terminal_message,
                    observation,
                    attempt_record,
                    failure_callback=failure_callback,
                )
            rejected += 1
            rejection_index += 1
            had_rejection = True
            H = max(0.5 * H, floor_H)

        interval_wall = perf_counter() - interval_started
        accepted_steps += 1
        accepted_dts.append(float(H))
        if retain_full_history:
            steps.append(candidate)
        elif retained_step_limit:
            steps.append(candidate)
            if len(steps) > retained_step_limit:
                del steps[0]
        accepted_voltage = candidate.controller.second_half_input_voltage_V
        if accepted_step_callback is not None:
            accepted_step_callback(
                previous_state,
                candidate,
                float(H),
                float(accepted_voltage),
                float(interval_wall),
            )
        interval_wall_times.append(float(perf_counter() - interval_started))
        state = candidate.state
        minimum_H = min(minimum_H, H)
        maximum_accepted_H = max(maximum_accepted_H, H)
        maximum_increment = max(
            maximum_increment,
            float(candidate.controller.legacy_conductive_increment or 0.0),
            float(candidate.controller.legacy_branch_increment or 0.0),
        )
        endpoint_remainders += int(below_floor_remainder)
        fallback_steps += int(candidate.controller.any_fallback)
        embedded = candidate.controller.embedded_error
        assert embedded is not None
        if (
            embedded.e_max <= easy_max
            and not had_rejection
            and not candidate.controller.any_fallback
            and not below_floor_remainder
        ):
            easy_streak += 1
        else:
            easy_streak = 0
        if below_floor_remainder:
            current_H = proposal_H
        else:
            current_H = H
            if easy_streak >= easy_required:
                expanded_H = min(2.0 * current_H, maximum_H)
                growth_events += int(expanded_H > current_H)
                current_H = expanded_H
                easy_streak = 0

    completed = bool(state.time_s >= stop - eps)
    dt_values = np.asarray(accepted_dts, dtype=float)
    wall_values = np.asarray(interval_wall_times, dtype=float)
    diagnostics = _empty_diagnostics(
        accepted_steps=accepted_steps,
        rejected_steps=rejected,
        nonlinear_rejections=integrity_rejections,
        endpoint_remainder_steps=endpoint_remainders,
        minimum_accepted_step_s=0.0 if not accepted_steps else minimum_H,
        maximum_accepted_step_s=maximum_accepted_H,
        maximum_transition_increment=maximum_increment,
        fallback_steps=fallback_steps,
        newton_iterations=int(newton_iterations),
        krylov_matvecs=int(krylov),
        armijo_backtracks=int(armijo),
        fallback_picard_iterations=int(fallback_picard),
        step_wall_time_p50_s=float(np.quantile(wall_values, 0.50)) if wall_values.size else 0.0,
        step_wall_time_p90_s=float(np.quantile(wall_values, 0.90)) if wall_values.size else 0.0,
        step_wall_time_max_s=float(np.max(wall_values)) if wall_values.size else 0.0,
        accepted_dt_p10_s=float(np.quantile(dt_values, 0.10)) if dt_values.size else 0.0,
        accepted_dt_p50_s=float(np.quantile(dt_values, 0.50)) if dt_values.size else 0.0,
        accepted_dt_p90_s=float(np.quantile(dt_values, 0.90)) if dt_values.size else 0.0,
        embedded_error_rejections=embedded_rejections,
        integrity_rejections=integrity_rejections,
        growth_events=growth_events,
        full_step_solves=full_solves,
        half_step_solves=half_solves,
        total_coupled_solves=total_solves,
        **{f"maximum_{key}": value for key, value in maxima.items()},
    )
    return S2ProtocolResult(
        steps=tuple(steps),
        diagnostics=diagnostics,
        requested_final_time_s=stop,
        achieved_final_time_s=float(state.time_s),
        completed=completed,
        stop_reason="requested_final_time_reached" if completed else stop_reason,
    )


__all__ = [
    "CONTROLLER_V3_ID",
    "ControllerV3ExecutionError",
    "FAILURE_SCHEMA_VERSION",
    "simulate_s2_protocol_v3",
]
