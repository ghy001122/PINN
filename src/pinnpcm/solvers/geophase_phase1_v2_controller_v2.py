"""Preregistered embedded full-step/two-half-step controller for Phase 1-v2.

The historical controller remains in :mod:`geophase_phase1_v2_implicit` and is
not modified here.  This module reuses its unchanged backward-Euler step and
changes only the outer temporal-consistency controller.
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
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2AdaptiveDiagnostics,
    S2NonlinearDiagnostics,
    S2ProtocolResult,
    S2SolverCache,
    S2State,
    S2StepResult,
    advance_s2_backward_euler,
    protocol_discontinuities,
    protocol_interval_voltage,
    validate_s2_state,
)


@dataclass(frozen=True)
class S2PathIntegrity:
    finite: bool
    nonlinear_pass: bool
    ledger_pass: bool
    lateral_pass: bool
    overall_pass: bool
    ledger_relative_residuals: dict[str, float]
    lateral_relative_mismatch: float | None
    lateral_roundoff_ratio: float | None
    error_class: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class S2AggregateIntegrity:
    finite: bool
    ledger_pass: bool
    overall_pass: bool
    ledger_relative_residuals: dict[str, float]
    error_class: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class S2EmbeddedError:
    e_T: float
    e_s: float
    e_b: float
    e_V: float
    e_max: float
    voltage_scale_V: float


@dataclass(frozen=True)
class S2EmbeddedIntervalDiagnostics:
    outer_interval_s: float
    half_interval_s: float
    voltage_scale_V: float
    full_input_voltage_V: float
    first_half_input_voltage_V: float
    second_half_input_voltage_V: float
    full_step: S2PathIntegrity
    first_half_step: S2PathIntegrity | None
    second_half_step: S2PathIntegrity | None
    aggregate: S2AggregateIntegrity | None
    embedded_error: S2EmbeddedError | None
    legacy_conductive_increment: float | None
    legacy_branch_increment: float | None
    rejection_index: int
    below_floor_remainder: bool
    at_outer_floor: bool
    accepted: bool
    coupled_solve_count: int
    any_fallback: bool
    wall_time_s: float


@dataclass(frozen=True)
class S2EmbeddedStepResult(S2StepResult):
    controller: S2EmbeddedIntervalDiagnostics
    aggregate_energy: S2IntervalEnergyTerms


@dataclass(frozen=True)
class S2EmbeddedAttemptObservation:
    previous_state: S2State
    step: S2EmbeddedStepResult | None
    full_candidate: S2StepResult | None
    first_half_candidate: S2StepResult | None
    second_half_candidate: S2StepResult | None
    diagnostics: S2EmbeddedIntervalDiagnostics
    error_class: str | None
    error_message: str | None


@dataclass(frozen=True)
class S2EmbeddedAdaptiveDiagnostics(S2AdaptiveDiagnostics):
    embedded_error_rejections: int
    integrity_rejections: int
    locked_floor_failures: int
    growth_events: int
    full_step_solves: int
    half_step_solves: int
    total_coupled_solves: int
    maximum_e_T: float
    maximum_e_s: float
    maximum_e_b: float
    maximum_e_V: float
    maximum_e_max: float


def _controller(config: dict) -> dict:
    controller = config["reference_solver"].get("active_time_controller")
    if not isinstance(controller, dict) or controller.get("controller_id") != (
        "embedded_time_consistency_v2_only"
    ):
        raise ValueError("resolved config does not select controller-v2")
    return controller


def controller_v2_limits(config: dict, time_divisor: int) -> tuple[float, float]:
    if time_divisor not in set(config["reference_solver"]["formal_time_step_divisors"]):
        raise ValueError("undeclared Phase 1-v2 time divisor")
    outer = _controller(config)["outer_interval"]
    maximum = float(outer["base_maximum_s"]) / time_divisor
    floor = float(outer["emergency_floor_base_s"]) / time_divisor
    if not np.isfinite([maximum, floor]).all() or not 0.0 < floor < maximum:
        raise ValueError("invalid controller-v2 outer interval bounds")
    return maximum, floor


def protocol_voltage_scale(config: dict, protocol_id: str) -> float:
    mapped = _controller(config)["voltage_scale"]["protocol_V_scale_V"]
    if protocol_id not in mapped:
        raise ValueError("controller-v2 protocol has no preregistered V_scale")
    value = float(mapped[protocol_id])
    if not np.isfinite(value) or value < 1.0:
        raise ValueError("controller-v2 protocol V_scale is invalid")
    return value


def _validate_protocol_identity(
    config: dict, protocol_id: str, protocol: dict
) -> None:
    declared = config["formal_protocols"]["protocols"]
    if protocol_id not in declared:
        raise ValueError("controller-v2 protocol is not declared by the base contract")
    if protocol != declared[protocol_id]:
        raise ValueError("controller-v2 protocol payload differs from its declared ID")


def compute_embedded_error(
    full_state: S2State,
    two_half_state: S2State,
    *,
    voltage_scale_V: float,
    temperature_scale_K: float = 7.19,
) -> S2EmbeddedError:
    if not np.isfinite([voltage_scale_V, temperature_scale_K]).all() or (
        voltage_scale_V <= 0.0 or temperature_scale_K <= 0.0
    ):
        raise ValueError("embedded error scales must be finite and positive")
    e_T = float(
        np.max(np.abs(two_half_state.temperature_K - full_state.temperature_K))
        / temperature_scale_K
    )
    e_s = float(
        np.max(
            np.abs(
                two_half_state.conductive_state - full_state.conductive_state
            )
        )
    )
    e_b = float(
        np.max(np.abs(two_half_state.branch_memory - full_state.branch_memory))
    )
    e_V = float(
        abs(two_half_state.device_voltage_V - full_state.device_voltage_V)
        / voltage_scale_V
    )
    values = np.asarray([e_T, e_s, e_b, e_V], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("embedded temporal error is nonfinite")
    return S2EmbeddedError(
        e_T=e_T,
        e_s=e_s,
        e_b=e_b,
        e_V=e_V,
        e_max=float(np.max(values)),
        voltage_scale_V=float(voltage_scale_V),
    )


def _ledger_residuals(ledgers: S2LedgerBundle) -> dict[str, float]:
    return {
        name: float(getattr(ledgers, name).relative_residual)
        for name in ("thermal", "circuit", "combined", "device_power")
    }


def _ledger_pass(residuals: dict[str, float], config: dict) -> bool:
    gates = config["gates"]
    return bool(
        residuals["thermal"]
        <= float(gates["thermal_ledger_relative_residual_max"])
        and residuals["circuit"]
        <= float(gates["circuit_ledger_relative_residual_max"])
        and residuals["combined"]
        <= float(gates["combined_ledger_relative_residual_max"])
        and residuals["device_power"]
        <= float(gates["device_power_identity_relative_residual_max"])
    )


def evaluate_s2_step_integrity(step: S2StepResult, config: dict) -> S2PathIntegrity:
    arrays = (
        step.state.temperature_K,
        step.state.conductive_state,
        step.state.branch_memory,
        step.electrical.potential_V,
        step.electrical.cell_joule_power_W,
    )
    scalars = np.asarray(
        [
            step.state.time_s,
            step.state.device_voltage_V,
            step.electrical.source_current_A,
            step.electrical.joule_power_W,
            step.electrical.terminal_device_power_W,
        ],
        dtype=float,
    )
    residuals = _ledger_residuals(step.ledgers)
    finite = bool(
        all(np.isfinite(np.asarray(value, dtype=float)).all() for value in arrays)
        and np.isfinite(scalars).all()
        and np.isfinite(np.asarray(list(residuals.values()), dtype=float)).all()
    )
    nonlinear = config["reference_solver"]["nonlinear_tolerances"]
    residual_limit = max(
        float(nonlinear["scaled_residual_absolute"]),
        float(nonlinear["scaled_residual_relative"]),
    )
    nonlinear_pass = bool(
        step.nonlinear.converged
        and np.isfinite(
            [
                step.nonlinear.scaled_residual_inf,
                step.nonlinear.scaled_update_inf,
            ]
        ).all()
        and step.nonlinear.scaled_residual_inf <= residual_limit
        and step.nonlinear.scaled_update_inf
        <= float(nonlinear["scaled_update_relative"])
    )
    ledgers_pass = finite and _ledger_pass(residuals, config)
    relative = float(step.lateral_flux.matrix_face_relative_mismatch)
    roundoff = float(step.lateral_flux.matrix_face_roundoff_ratio)
    lateral_pass = bool(
        np.isfinite([relative, roundoff]).all()
        and (relative <= 1.0e-10 or roundoff <= 1.0)
    )
    return S2PathIntegrity(
        finite=finite,
        nonlinear_pass=nonlinear_pass,
        ledger_pass=ledgers_pass,
        lateral_pass=lateral_pass,
        overall_pass=bool(finite and nonlinear_pass and ledgers_pass and lateral_pass),
        ledger_relative_residuals=residuals,
        lateral_relative_mismatch=relative,
        lateral_roundoff_ratio=roundoff,
    )


def _failed_integrity(error: BaseException) -> S2PathIntegrity:
    return S2PathIntegrity(
        finite=False,
        nonlinear_pass=False,
        ledger_pass=False,
        lateral_pass=False,
        overall_pass=False,
        ledger_relative_residuals={},
        lateral_relative_mismatch=None,
        lateral_roundoff_ratio=None,
        error_class=type(error).__name__,
        error_message=str(error),
    )


def _aggregate_integrity(
    ledgers: S2LedgerBundle, config: dict
) -> S2AggregateIntegrity:
    residuals = _ledger_residuals(ledgers)
    finite = bool(np.isfinite(np.asarray(list(residuals.values()), dtype=float)).all())
    passed = bool(finite and _ledger_pass(residuals, config))
    return S2AggregateIntegrity(
        finite=finite,
        ledger_pass=passed,
        overall_pass=passed,
        ledger_relative_residuals=residuals,
    )


def _combined_nonlinear(steps: tuple[S2StepResult, ...]) -> S2NonlinearDiagnostics:
    methods = tuple(step.nonlinear.method for step in steps)
    return S2NonlinearDiagnostics(
        method="embedded[" + ",".join(methods) + "]",
        iterations=sum(step.nonlinear.iterations for step in steps),
        scaled_residual_inf=max(step.nonlinear.scaled_residual_inf for step in steps),
        scaled_update_inf=max(step.nonlinear.scaled_update_inf for step in steps),
        converged=all(step.nonlinear.converged for step in steps),
        krylov_matvecs=sum(step.nonlinear.krylov_matvecs for step in steps),
        armijo_backtracks=sum(step.nonlinear.armijo_backtracks for step in steps),
        predictor_picard_iterations=sum(
            step.nonlinear.predictor_picard_iterations for step in steps
        ),
        fallback_picard_iterations=sum(
            step.nonlinear.fallback_picard_iterations for step in steps
        ),
    )


def attempt_s2_embedded_interval(
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
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
) -> S2EmbeddedAttemptObservation:
    H = float(outer_interval_s)
    if not np.isfinite(H) or H <= 0.0:
        raise ValueError("outer interval must be finite and positive")
    _validate_protocol_identity(config, protocol_id, protocol)
    half = 0.5 * H
    start = float(state.time_s)
    midpoint = start + half
    stop = start + H
    full_voltage = protocol_interval_voltage(protocol, start, stop)
    first_voltage = protocol_interval_voltage(protocol, start, midpoint)
    second_voltage = protocol_interval_voltage(protocol, midpoint, stop)
    voltage_scale = protocol_voltage_scale(config, protocol_id)
    started = perf_counter()
    full: S2StepResult | None = None
    first: S2StepResult | None = None
    second: S2StepResult | None = None
    full_integrity: S2PathIntegrity
    first_integrity: S2PathIntegrity | None = None
    second_integrity: S2PathIntegrity | None = None
    aggregate_integrity: S2AggregateIntegrity | None = None
    embedded: S2EmbeddedError | None = None
    energy: S2IntervalEnergyTerms | None = None
    aggregate_ledgers: S2LedgerBundle | None = None
    error_class: str | None = None
    error_message: str | None = None
    coupled_solves = 0

    common = dict(
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=cache,
        use_equivalent_optimizations=use_equivalent_optimizations,
        use_unit_voltage_scaling=use_unit_voltage_scaling,
    )
    try:
        coupled_solves += 1
        full = advance_s2_backward_euler(
            state, input_voltage_V=full_voltage, dt_s=H, **common
        )
        full_integrity = evaluate_s2_step_integrity(full, config)
        if not full_integrity.overall_pass:
            raise RuntimeError("controller-v2 full-step integrity failed")

        coupled_solves += 1
        first = advance_s2_backward_euler(
            state, input_voltage_V=first_voltage, dt_s=half, **common
        )
        first_integrity = evaluate_s2_step_integrity(first, config)
        if not first_integrity.overall_pass:
            raise RuntimeError("controller-v2 first-half integrity failed")

        coupled_solves += 1
        second = advance_s2_backward_euler(
            first.state, input_voltage_V=second_voltage, dt_s=half, **common
        )
        second_integrity = evaluate_s2_step_integrity(second, config)
        if not second_integrity.overall_pass:
            raise RuntimeError("controller-v2 second-half integrity failed")

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
        aggregate_integrity = _aggregate_integrity(aggregate_ledgers, config)
        if not aggregate_integrity.overall_pass:
            raise RuntimeError("controller-v2 aggregate ledger integrity failed")
        embedded = compute_embedded_error(
            full.state,
            second.state,
            voltage_scale_V=voltage_scale,
            temperature_scale_K=float(
                _controller(config)["embedded_error"]["temperature_scale_K"]
            ),
        )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        error_class = type(error).__name__
        error_message = str(error)
        if full is None:
            full_integrity = _failed_integrity(error)
        elif first is None:
            first_integrity = _failed_integrity(error)
        elif second is None:
            second_integrity = _failed_integrity(error)
        elif aggregate_integrity is None:
            aggregate_integrity = S2AggregateIntegrity(
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
        <= float(_controller(config)["embedded_error"]["acceptance_max"])
    )
    path_steps = tuple(item for item in (full, first, second) if item is not None)
    any_fallback = any(
        step.nonlinear.method == "fail_closed_fixed_point_fallback"
        for step in path_steps
    )
    diagnostics = S2EmbeddedIntervalDiagnostics(
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
        embedded_error=embedded,
        legacy_conductive_increment=legacy_s,
        legacy_branch_increment=legacy_b,
        rejection_index=int(rejection_index),
        below_floor_remainder=bool(below_floor_remainder),
        at_outer_floor=bool(at_outer_floor),
        accepted=accepted,
        coupled_solve_count=coupled_solves,
        any_fallback=any_fallback,
        wall_time_s=float(perf_counter() - started),
    )
    step: S2EmbeddedStepResult | None = None
    if accepted:
        assert second is not None
        assert aggregate_ledgers is not None
        assert energy is not None
        assert len(path_steps) == 3
        step = S2EmbeddedStepResult(
            state=second.state,
            electrical=second.electrical,
            ledgers=aggregate_ledgers,
            lateral_flux=second.lateral_flux,
            nonlinear=_combined_nonlinear(path_steps),
            controller=diagnostics,
            aggregate_energy=energy,
        )
    return S2EmbeddedAttemptObservation(
        previous_state=state,
        step=step,
        full_candidate=full,
        first_half_candidate=first,
        second_half_candidate=second,
        diagnostics=diagnostics,
        error_class=error_class,
        error_message=error_message,
    )


def _empty_adaptive_diagnostics(**extra: int | float) -> S2EmbeddedAdaptiveDiagnostics:
    return S2EmbeddedAdaptiveDiagnostics(
        accepted_steps=0,
        rejected_steps=0,
        transition_rejections=0,
        nonlinear_rejections=0,
        endpoint_remainder_steps=0,
        minimum_accepted_step_s=0.0,
        maximum_accepted_step_s=0.0,
        maximum_transition_increment=0.0,
        fallback_steps=0,
        newton_iterations=0,
        krylov_matvecs=0,
        armijo_backtracks=0,
        fallback_picard_iterations=0,
        step_wall_time_p50_s=0.0,
        step_wall_time_p90_s=0.0,
        step_wall_time_max_s=0.0,
        accepted_dt_p10_s=0.0,
        accepted_dt_p50_s=0.0,
        accepted_dt_p90_s=0.0,
        embedded_error_rejections=int(extra.get("embedded_error_rejections", 0)),
        integrity_rejections=int(extra.get("integrity_rejections", 0)),
        locked_floor_failures=int(extra.get("locked_floor_failures", 0)),
        growth_events=int(extra.get("growth_events", 0)),
        full_step_solves=int(extra.get("full_step_solves", 0)),
        half_step_solves=int(extra.get("half_step_solves", 0)),
        total_coupled_solves=int(extra.get("total_coupled_solves", 0)),
        maximum_e_T=float(extra.get("maximum_e_T", 0.0)),
        maximum_e_s=float(extra.get("maximum_e_s", 0.0)),
        maximum_e_b=float(extra.get("maximum_e_b", 0.0)),
        maximum_e_V=float(extra.get("maximum_e_V", 0.0)),
        maximum_e_max=float(extra.get("maximum_e_max", 0.0)),
    )


def simulate_s2_protocol_v2(
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
        [S2State, S2EmbeddedStepResult, float, float, float], None
    ]
    | None = None,
    attempted_candidate_callback: Callable[[S2EmbeddedAttemptObservation], None]
    | None = None,
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
) -> S2ProtocolResult:
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
        raise ValueError("controller-v2 final time must follow its initial time")
    protocol_voltage_scale(config, protocol_id)
    protocol_discontinuities(protocol)
    fields.validate_grid(grid)
    validate_s2_state(initial_state, grid, closure)
    if cache is not None:
        cache.validate_context(grid, fields)

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
    controller = _controller(config)
    rejection_cap = int(controller["outer_interval"]["outer_rejection_cap"])
    easy_max = float(controller["growth"]["easy_error_max"])
    easy_required = int(controller["growth"]["required_consecutive_easy_intervals"])
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
            )
            if attempted_candidate_callback is not None:
                attempted_candidate_callback(observation)
            solves = observation.diagnostics.coupled_solve_count
            total_solves += solves
            full_solves += int(solves >= 1)
            half_solves += int(solves >= 2) + int(solves >= 3)
            for candidate in (
                observation.full_candidate,
                observation.first_half_candidate,
                observation.second_half_candidate,
            ):
                if candidate is None:
                    continue
                newton_iterations += candidate.nonlinear.iterations
                krylov += candidate.nonlinear.krylov_matvecs
                armijo += candidate.nonlinear.armijo_backtracks
                fallback_picard += candidate.nonlinear.fallback_picard_iterations
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
            rejection_index += 1
            had_rejection = True
            if rejection_index > rejection_cap:
                raise RuntimeError("controller-v2 outer rejection cap exceeded")
            H = max(0.5 * H, floor_H)
        interval_wall = perf_counter() - interval_started
        accepted_steps += 1
        accepted_dts.append(float(H))
        interval_wall_times.append(float(interval_wall))
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
    diagnostics = _empty_adaptive_diagnostics(
        embedded_error_rejections=embedded_rejections,
        integrity_rejections=integrity_rejections,
        growth_events=growth_events,
        full_step_solves=full_solves,
        half_step_solves=half_solves,
        total_coupled_solves=total_solves,
        **{f"maximum_{key}": value for key, value in maxima.items()},
    )
    diagnostics = S2EmbeddedAdaptiveDiagnostics(
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
            "step_wall_time_p50_s": float(np.quantile(wall_values, 0.50)) if wall_values.size else 0.0,
            "step_wall_time_p90_s": float(np.quantile(wall_values, 0.90)) if wall_values.size else 0.0,
            "step_wall_time_max_s": float(np.max(wall_values)) if wall_values.size else 0.0,
            "accepted_dt_p10_s": float(np.quantile(dt_values, 0.10)) if dt_values.size else 0.0,
            "accepted_dt_p50_s": float(np.quantile(dt_values, 0.50)) if dt_values.size else 0.0,
            "accepted_dt_p90_s": float(np.quantile(dt_values, 0.90)) if dt_values.size else 0.0,
        }
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
    "S2AggregateIntegrity",
    "S2EmbeddedAdaptiveDiagnostics",
    "S2EmbeddedAttemptObservation",
    "S2EmbeddedError",
    "S2EmbeddedIntervalDiagnostics",
    "S2EmbeddedStepResult",
    "S2PathIntegrity",
    "attempt_s2_embedded_interval",
    "compute_embedded_error",
    "controller_v2_limits",
    "evaluate_s2_step_integrity",
    "protocol_voltage_scale",
    "simulate_s2_protocol_v2",
]
