"""Controller-v2 semantics driven by the independent exact-condensed step.

The frozen controller-v2 source is not modified.  This module reuses its
public data contracts and integrity helpers while reproducing the same
full/half/half, rejection, growth, landing, dense-output, and second-half
commit control flow with :func:`solve_exact_condensed_step` as the sole step
solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_ledgers import (
    S2IntervalEnergyTerms,
    S2LedgerBundle,
    build_s2_two_half_interval_ledgers,
)
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers import geophase_phase1_v2_controller_v2 as frozen_controller
from pinnpcm.solvers.geophase_exact_condensed import (
    DEFAULT_EXACT_CONDENSED_SETTINGS,
    ExactCondensedRootFailure,
    ExactCondensedRootTelemetry,
    ExactCondensedSettings,
    solve_exact_condensed_step,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2PerformanceTimings,
    S2ProtocolResult,
    S2SolverCache,
    S2State,
    S2StepResult,
    build_s2_solver_cache,
    protocol_discontinuities,
    protocol_interval_voltage,
    validate_s2_state,
)


@dataclass(frozen=True)
class ExactCondensedEmbeddedAttemptObservation(
    frozen_controller.S2EmbeddedAttemptObservation
):
    root_telemetry: tuple[ExactCondensedRootTelemetry, ...] = ()


@dataclass(frozen=True)
class ExactCondensedProtocolResult(S2ProtocolResult):
    root_telemetry: tuple[ExactCondensedRootTelemetry, ...] = ()


def attempt_exact_condensed_embedded_interval(
    state: S2State,
    *,
    protocol: dict,
    protocol_id: str,
    outer_interval_s: float,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    rejection_index: int = 0,
    below_floor_remainder: bool = False,
    at_outer_floor: bool = False,
    cache: S2SolverCache | None = None,
    settings: ExactCondensedSettings = DEFAULT_EXACT_CONDENSED_SETTINGS,
    performance_timings: S2PerformanceTimings | None = None,
) -> ExactCondensedEmbeddedAttemptObservation:
    H = float(outer_interval_s)
    if not np.isfinite(H) or H <= 0.0:
        raise ValueError("outer interval must be finite and positive")
    frozen_controller._validate_protocol_identity(config, protocol_id, protocol)
    half = 0.5 * H
    start = float(state.time_s)
    midpoint = start + half
    stop = start + H
    full_voltage = protocol_interval_voltage(protocol, start, stop)
    first_voltage = protocol_interval_voltage(protocol, start, midpoint)
    second_voltage = protocol_interval_voltage(protocol, midpoint, stop)
    voltage_scale = frozen_controller.protocol_voltage_scale(config, protocol_id)
    active_cache = cache or build_s2_solver_cache(grid, fields)
    active_cache.validate_context(grid, fields)
    started = perf_counter()
    full: S2StepResult | None = None
    first: S2StepResult | None = None
    second: S2StepResult | None = None
    full_integrity: frozen_controller.S2PathIntegrity | None = None
    first_integrity: frozen_controller.S2PathIntegrity | None = None
    second_integrity: frozen_controller.S2PathIntegrity | None = None
    aggregate_integrity: frozen_controller.S2AggregateIntegrity | None = None
    embedded: frozen_controller.S2EmbeddedError | None = None
    energy: S2IntervalEnergyTerms | None = None
    aggregate_ledgers: S2LedgerBundle | None = None
    error_class: str | None = None
    error_message: str | None = None
    coupled_solves = 0
    active_path = "full_step"
    root_telemetry: list[ExactCondensedRootTelemetry] = []

    def solve(previous: S2State, voltage: float, dt: float) -> S2StepResult:
        try:
            outcome = solve_exact_condensed_step(
                previous,
                input_voltage_V=voltage,
                dt_s=dt,
                grid=grid,
                closure=closure,
                fields=fields,
                config=config,
                cache=active_cache,
                settings=settings,
                performance_timings=performance_timings,
            )
        except ExactCondensedRootFailure as error:
            root_telemetry.append(error.telemetry)
            raise
        root_telemetry.append(outcome.telemetry)
        return outcome.step

    try:
        active_path = "full_step"
        coupled_solves += 1
        full = solve(state, full_voltage, H)
        full_integrity = frozen_controller.evaluate_s2_step_integrity(full, config)
        if not full_integrity.overall_pass:
            raise RuntimeError("controller-v2 full-step integrity failed")

        active_path = "first_half_step"
        coupled_solves += 1
        first = solve(state, first_voltage, half)
        first_integrity = frozen_controller.evaluate_s2_step_integrity(first, config)
        if not first_integrity.overall_pass:
            raise RuntimeError("controller-v2 first-half integrity failed")

        active_path = "second_half_step"
        coupled_solves += 1
        second = solve(first.state, second_voltage, half)
        second_integrity = frozen_controller.evaluate_s2_step_integrity(second, config)
        if not second_integrity.overall_pass:
            raise RuntimeError("controller-v2 second-half integrity failed")

        active_path = "aggregate_ledgers"
        capacitance = float(
            config["physics_contract"]["circuit"]["parallel_capacitance_F"]
        )
        aggregate_ledgers, energy = build_s2_two_half_interval_ledgers(
            grid=grid,
            fields=fields,
            outer_initial_temperature_K=state.temperature_K,
            outer_initial_device_voltage_V=state.device_voltage_V,
            first_half=first,
            second_half=second,
            half_dt_s=half,
            capacitance_F=capacitance,
        )
        aggregate_integrity = frozen_controller._aggregate_integrity(
            aggregate_ledgers, config
        )
        if not aggregate_integrity.overall_pass:
            raise RuntimeError("controller-v2 aggregate ledger integrity failed")
        active_path = "embedded_error"
        embedded = frozen_controller.compute_embedded_error(
            full.state,
            second.state,
            voltage_scale_V=voltage_scale,
            temperature_scale_K=float(
                frozen_controller._controller(config)["embedded_error"][
                    "temperature_scale_K"
                ]
            ),
        )
    except (
        ExactCondensedRootFailure,
        RuntimeError,
        ValueError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as error:
        error_class = type(error).__name__
        error_message = str(error)
        if active_path == "full_step" and full_integrity is None:
            full_integrity = frozen_controller._failed_integrity(error)
        elif active_path == "first_half_step" and first is None:
            first_integrity = frozen_controller._failed_integrity(error)
        elif active_path == "second_half_step" and second is None:
            second_integrity = frozen_controller._failed_integrity(error)
        elif active_path == "aggregate_ledgers" and aggregate_integrity is None:
            aggregate_integrity = frozen_controller.S2AggregateIntegrity(
                finite=False,
                ledger_pass=False,
                overall_pass=False,
                ledger_relative_residuals={},
                error_class=error_class,
                error_message=error_message,
            )

    legacy_s = (
        None
        if second is None
        else float(
            np.max(np.abs(second.state.conductive_state - state.conductive_state))
        )
    )
    legacy_b = (
        None
        if second is None
        else float(np.max(np.abs(second.state.branch_memory - state.branch_memory)))
    )
    assert full_integrity is not None
    integrity_pass = bool(
        full_integrity.overall_pass
        and first_integrity is not None
        and first_integrity.overall_pass
        and second_integrity is not None
        and second_integrity.overall_pass
        and aggregate_integrity is not None
        and aggregate_integrity.overall_pass
    )
    accepted = bool(
        integrity_pass
        and embedded is not None
        and embedded.e_max
        <= float(
            frozen_controller._controller(config)["embedded_error"]["acceptance_max"]
        )
    )
    path_steps = tuple(item for item in (full, first, second) if item is not None)
    diagnostics = frozen_controller.S2EmbeddedIntervalDiagnostics(
        outer_interval_s=H,
        half_interval_s=half,
        voltage_scale_V=voltage_scale,
        full_input_voltage_V=float(full_voltage),
        first_half_input_voltage_V=float(first_voltage),
        second_half_input_voltage_V=float(second_voltage),
        full_step=full_integrity,
        first_half_step=first_integrity,
        second_half_step=second_integrity,
        aggregate=aggregate_integrity,
        full_nonlinear=None if full is None else full.nonlinear,
        first_half_nonlinear=None if first is None else first.nonlinear,
        second_half_nonlinear=None if second is None else second.nonlinear,
        embedded_error=embedded,
        legacy_conductive_increment=legacy_s,
        legacy_branch_increment=legacy_b,
        rejection_index=int(rejection_index),
        below_floor_remainder=bool(below_floor_remainder),
        at_outer_floor=bool(at_outer_floor),
        accepted=accepted,
        coupled_solve_count=coupled_solves,
        any_fallback=False,
        wall_time_s=float(perf_counter() - started),
    )
    step: frozen_controller.S2EmbeddedStepResult | None = None
    if accepted:
        assert second is not None
        assert aggregate_ledgers is not None
        assert energy is not None
        assert len(path_steps) == 3
        assert first is not None
        step = frozen_controller.S2EmbeddedStepResult(
            state=second.state,
            electrical=second.electrical,
            ledgers=aggregate_ledgers,
            lateral_flux=second.lateral_flux,
            nonlinear=frozen_controller._combined_nonlinear((first, second)),
            controller=diagnostics,
            aggregate_energy=energy,
            accepted_first_half=first,
        )
    return ExactCondensedEmbeddedAttemptObservation(
        previous_state=state,
        step=step,
        full_candidate=full,
        first_half_candidate=first,
        second_half_candidate=second,
        diagnostics=diagnostics,
        error_class=error_class,
        error_message=error_message,
        aggregate_ledgers=aggregate_ledgers,
        aggregate_energy=energy,
        root_telemetry=tuple(root_telemetry),
    )


def simulate_exact_condensed_protocol_v2(
    initial_state: S2State,
    *,
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
    forced_times_s: tuple[float, ...] | list[float] | np.ndarray = (),
    retain_full_history: bool = True,
    retained_step_limit: int = 0,
    accepted_step_callback: Callable[
        [S2State, frozen_controller.S2EmbeddedStepResult, float, float, float], None
    ]
    | None = None,
    attempted_candidate_callback: Callable[
        [ExactCondensedEmbeddedAttemptObservation], None
    ]
    | None = None,
    cache: S2SolverCache | None = None,
    settings: ExactCondensedSettings = DEFAULT_EXACT_CONDENSED_SETTINGS,
    performance_timings: S2PerformanceTimings | None = None,
) -> ExactCondensedProtocolResult:
    """Run the frozen controller-v2 state machine with exact-condensed roots."""

    if maximum_accepted_steps is not None and maximum_accepted_steps <= 0:
        raise ValueError("maximum_accepted_steps must be positive")
    if maximum_wall_clock_s is not None and (
        not np.isfinite(maximum_wall_clock_s) or maximum_wall_clock_s <= 0.0
    ):
        raise ValueError("maximum_wall_clock_s must be finite and positive")
    if retained_step_limit < 0:
        raise ValueError("retained_step_limit cannot be negative")
    maximum_H, floor_H = frozen_controller.controller_v2_limits(config, time_divisor)
    stop = float(
        config["reference_solver"]["time_grid"]["final_time_s"]
        if final_time_s is None
        else final_time_s
    )
    if not np.isfinite(stop) or stop <= initial_state.time_s:
        raise ValueError("controller-v2 final time must follow its initial time")
    frozen_controller.protocol_voltage_scale(config, protocol_id)
    protocol_discontinuities(protocol)
    fields.validate_grid(grid)
    validate_s2_state(initial_state, grid, closure)
    active_cache = cache or build_s2_solver_cache(grid, fields)
    active_cache.validate_context(grid, fields)

    forced = np.asarray(forced_times_s, dtype=float)
    if forced.ndim != 1 or not np.isfinite(forced).all():
        raise ValueError("forced controller-v2 landing times must be finite and 1D")
    if forced.size and np.any(np.diff(forced) <= 0.0):
        raise ValueError("forced controller-v2 landing times must increase")
    eps = max(1.0e-18, abs(stop) * 1.0e-14)
    if forced.size and (
        forced[0] < initial_state.time_s - eps or forced[-1] > stop + eps
    ):
        raise ValueError("forced controller-v2 times fall outside the run")
    landing_times = tuple(
        sorted(
            {
                float(value)
                for value in (*protocol_discontinuities(protocol), *forced.tolist())
                if initial_state.time_s < float(value) <= stop + eps
            }
        )
    )
    controller = frozen_controller._controller(config)
    rejection_cap = int(controller["outer_interval"]["outer_rejection_cap"])
    case_rejection_cap = int(
        config["reference_solver"]["time_grid"][
            "maximum_rejected_steps_per_case"
        ]
    )
    easy_max = float(controller["growth"]["easy_error_max"])
    easy_required = int(controller["growth"]["required_consecutive_easy_intervals"])
    state = initial_state
    current_H = maximum_H
    steps: list[frozen_controller.S2EmbeddedStepResult] = []
    all_root_telemetry: list[ExactCondensedRootTelemetry] = []
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
        if (
            maximum_wall_clock_s is not None
            and perf_counter() - started >= maximum_wall_clock_s
        ):
            stop_reason = "maximum_wall_clock_reached"
            break
        if maximum_accepted_steps is not None and accepted_steps >= maximum_accepted_steps:
            stop_reason = "maximum_accepted_steps_reached"
            break
        proposal_H = current_H
        remaining = stop - state.time_s
        H = min(proposal_H, remaining)
        future = [value for value in landing_times if value > state.time_s + eps]
        if future:
            H = min(H, min(future) - state.time_s)
        below_floor_remainder = H < floor_H - eps
        previous_state = state
        rejection_index = 0
        had_rejection = False
        interval_started = perf_counter()
        while True:
            observation = attempt_exact_condensed_embedded_interval(
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
                cache=active_cache,
                settings=settings,
                performance_timings=performance_timings,
            )
            all_root_telemetry.extend(observation.root_telemetry)
            if attempted_candidate_callback is not None:
                attempted_candidate_callback(observation)
            solves = observation.diagnostics.coupled_solve_count
            total_solves += solves
            full_solves += int(solves >= 1)
            half_solves += int(solves >= 2) + int(solves >= 3)
            for candidate_item in (
                observation.full_candidate,
                observation.first_half_candidate,
                observation.second_half_candidate,
            ):
                if candidate_item is None:
                    continue
                newton_iterations += candidate_item.nonlinear.iterations
                krylov += candidate_item.nonlinear.krylov_matvecs
                armijo += candidate_item.nonlinear.armijo_backtracks
                fallback_picard += candidate_item.nonlinear.fallback_picard_iterations
            embedded = observation.diagnostics.embedded_error
            if embedded is not None:
                for name in maxima:
                    maxima[name] = max(maxima[name], float(getattr(embedded, name)))
            if observation.step is not None:
                candidate = observation.step
                break
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
            integrity_rejections += int(integrity_failure)
            embedded_rejections += int(not integrity_failure)
            if below_floor_remainder:
                raise RuntimeError("controller-v2 forced remainder failed closed")
            if H <= floor_H * (1.0 + 1.0e-12):
                raise RuntimeError("controller-v2 failed at locked outer floor")
            rejected += 1
            if rejected > case_rejection_cap:
                raise RuntimeError("controller-v2 per-case rejection cap exceeded")
            rejection_index += 1
            had_rejection = True
            if rejection_index > rejection_cap:
                raise RuntimeError("controller-v2 outer rejection cap exceeded")
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
    diagnostics = frozen_controller._empty_adaptive_diagnostics(
        embedded_error_rejections=embedded_rejections,
        integrity_rejections=integrity_rejections,
        growth_events=growth_events,
        full_step_solves=full_solves,
        half_step_solves=half_solves,
        total_coupled_solves=total_solves,
        **{f"maximum_{key}": value for key, value in maxima.items()},
    )
    diagnostics = frozen_controller.S2EmbeddedAdaptiveDiagnostics(
        **{
            **diagnostics.__dict__,
            "accepted_steps": accepted_steps,
            "rejected_steps": rejected,
            "transition_rejections": 0,
            "nonlinear_rejections": integrity_rejections,
            "endpoint_remainder_steps": endpoint_remainders,
            "minimum_accepted_step_s": 0.0 if not accepted_steps else minimum_H,
            "maximum_accepted_step_s": maximum_accepted_H,
            "maximum_transition_increment": maximum_increment,
            "fallback_steps": fallback_steps,
            "newton_iterations": int(newton_iterations),
            "krylov_matvecs": int(krylov),
            "armijo_backtracks": int(armijo),
            "fallback_picard_iterations": int(fallback_picard),
            "step_wall_time_p50_s": (
                float(np.quantile(wall_values, 0.50)) if wall_values.size else 0.0
            ),
            "step_wall_time_p90_s": (
                float(np.quantile(wall_values, 0.90)) if wall_values.size else 0.0
            ),
            "step_wall_time_max_s": (
                float(np.max(wall_values)) if wall_values.size else 0.0
            ),
            "accepted_dt_p10_s": (
                float(np.quantile(dt_values, 0.10)) if dt_values.size else 0.0
            ),
            "accepted_dt_p50_s": (
                float(np.quantile(dt_values, 0.50)) if dt_values.size else 0.0
            ),
            "accepted_dt_p90_s": (
                float(np.quantile(dt_values, 0.90)) if dt_values.size else 0.0
            ),
        }
    )
    return ExactCondensedProtocolResult(
        steps=tuple(steps),
        diagnostics=diagnostics,
        requested_final_time_s=stop,
        achieved_final_time_s=float(state.time_s),
        completed=completed,
        stop_reason="requested_final_time_reached" if completed else stop_reason,
        root_telemetry=tuple(all_root_telemetry),
    )


__all__ = [
    "ExactCondensedEmbeddedAttemptObservation",
    "ExactCondensedProtocolResult",
    "attempt_exact_condensed_embedded_interval",
    "simulate_exact_condensed_protocol_v2",
]
