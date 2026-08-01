"""Fixed-output streaming for controller-v3 without forced sample landings."""

from __future__ import annotations

from typing import Any

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    S2EmbeddedStepResult,
    protocol_voltage_scale,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_v3 import (
    CONTROLLER_V3_ID,
    simulate_s2_protocol_v3,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import reconstruct_lateral_fluxes
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2PerformanceTimings,
    S2SolverCache,
    S2State,
    S2StepResult,
    build_s2_solver_cache,
    protocol_discontinuities,
    protocol_voltage,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import (
    S2StreamingResult,
    _ControllerV2AttemptAccumulator,
    _ControllerV2StreamingRecorder,
    _StreamingRecorder,
    fixed_scalar_sample_times,
)


DENSE_OUTPUT_ID = "accepted_two_half_path_piecewise_linear_state_v1"
LEDGER_OUTPUT_SEMANTICS = "accepted_fine_interval_not_interpolated"


def _interpolate_state(start: S2State, stop: S2State, target_s: float) -> S2State:
    width = float(stop.time_s - start.time_s)
    if not np.isfinite(width) or width <= 0.0:
        raise ValueError("dense-output state interval must have positive width")
    fraction = float((target_s - start.time_s) / width)
    tolerance = 1.0e-12
    if fraction < -tolerance or fraction > 1.0 + tolerance:
        raise ValueError("dense-output target lies outside accepted state interval")
    fraction = min(max(fraction, 0.0), 1.0)
    blend = lambda left, right: np.asarray(left, dtype=float) + fraction * (
        np.asarray(right, dtype=float) - np.asarray(left, dtype=float)
    )
    return S2State(
        time_s=float(target_s),
        temperature_K=blend(start.temperature_K, stop.temperature_K),
        conductive_state=blend(start.conductive_state, stop.conductive_state),
        branch_memory=blend(start.branch_memory, stop.branch_memory),
        device_voltage_V=float(
            start.device_voltage_V
            + fraction * (stop.device_voltage_V - start.device_voltage_V)
        ),
    )


def _reconstructed_step(
    *,
    target_s: float,
    interval_start: S2State,
    accepted_endpoint: S2StepResult,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
) -> S2StepResult:
    tolerance = max(1.0e-18, abs(target_s) * 1.0e-12)
    if abs(target_s - accepted_endpoint.state.time_s) <= tolerance:
        return accepted_endpoint
    state = _interpolate_state(interval_start, accepted_endpoint.state, target_s)
    conductivity = closure.conductivity_S_m(
        state.temperature_K, state.conductive_state
    )
    electrical = solve_sheet_electrical(
        grid, conductivity, state.device_voltage_V
    )
    lateral = reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        state.temperature_K,
    )
    # The state and electrical QoIs use accepted-path dense reconstruction.
    # Ledger and nonlinear values remain those of the actual accepted fine
    # interval; powers and residuals are never interpolated between intervals.
    return S2StepResult(
        state=state,
        electrical=electrical,
        ledgers=accepted_endpoint.ledgers,
        lateral_flux=lateral,
        nonlinear=accepted_endpoint.nonlinear,
    )


class _ControllerV3StreamingRecorder(_ControllerV2StreamingRecorder):
    """Project accepted two-half paths onto the locked 4001-point grid."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.scalar_records[0]["time_controller"] = CONTROLLER_V3_ID
        self.scalar_records[0]["dense_output"] = DENSE_OUTPUT_ID
        self.scalar_records[0]["ledger_output_semantics"] = LEDGER_OUTPUT_SEMANTICS

    def _update_controller_telemetry(
        self,
        *,
        step: S2EmbeddedStepResult,
        outer_interval_s: float,
        coupled_solve_count: int,
    ) -> None:
        embedded = step.controller.embedded_error
        if embedded is None:
            raise RuntimeError("accepted controller-v3 step lacks embedded error")
        self.scalar_records[-1].update(
            {
                "time_controller": CONTROLLER_V3_ID,
                "dense_output": DENSE_OUTPUT_ID,
                "ledger_output_semantics": LEDGER_OUTPUT_SEMANTICS,
                "voltage_scale_V": float(step.controller.voltage_scale_V),
                "outer_interval_s": float(outer_interval_s),
                "outer_rejections": int(step.controller.rejection_index),
                "coupled_solve_count": int(coupled_solve_count),
                "accepted_bundle_coupled_solve_count": int(
                    step.controller.coupled_solve_count
                ),
                "e_T": float(embedded.e_T),
                "e_s": float(embedded.e_s),
                "e_b": float(embedded.e_b),
                "e_V": float(embedded.e_V),
                "e_max": float(embedded.e_max),
                "legacy_max_absolute_delta_s": float(
                    step.controller.legacy_conductive_increment or 0.0
                ),
                "legacy_max_absolute_delta_b": float(
                    step.controller.legacy_branch_increment or 0.0
                ),
                **self._path_telemetry(
                    "full", step.controller.full_step, step.controller.full_nonlinear
                ),
                **self._path_telemetry(
                    "first_half",
                    step.controller.first_half_step,
                    step.controller.first_half_nonlinear,
                ),
                **self._path_telemetry(
                    "second_half",
                    step.controller.second_half_step,
                    step.controller.second_half_nonlinear,
                ),
                **self._aggregate_telemetry(step.controller.aggregate),
            }
        )

    def record_accepted_interval(
        self,
        previous_state: S2State,
        step: S2EmbeddedStepResult,
        outer_interval_s: float,
        _input_voltage_V: float,
        wall_time_s: float,
        *,
        coupled_solve_count: int,
    ) -> None:
        first = step.accepted_first_half
        self._record_accepted_fine_diagnostics(first)
        self._record_accepted_fine_diagnostics(
            step, nonlinear=step.controller.second_half_nonlinear
        )
        self.final_state = step.state
        tolerance = max(1.0e-18, abs(step.state.time_s) * 1.0e-12)
        while self._sample_index < len(self.sample_times_s):
            target = float(self.sample_times_s[self._sample_index])
            if target > step.state.time_s + tolerance:
                break
            if target <= first.state.time_s + tolerance:
                segment_start = previous_state
                accepted_endpoint: S2StepResult = first
            else:
                segment_start = first.state
                accepted_endpoint = step
            sampled = _reconstructed_step(
                target_s=target,
                interval_start=segment_start,
                accepted_endpoint=accepted_endpoint,
                grid=self.grid,
                closure=self.closure,
                fields=self.fields,
            )
            previous_count = len(self.scalar_records)
            self._fixed_event_nonlinear = sampled.nonlinear
            try:
                _StreamingRecorder.__call__(
                    self,
                    segment_start,
                    sampled,
                    float(sampled.state.time_s - segment_start.time_s),
                    float(protocol_voltage(self.protocol, target)),
                    wall_time_s,
                )
            finally:
                self._fixed_event_nonlinear = None
            if len(self.scalar_records) != previous_count + 1:
                raise RuntimeError("controller-v3 failed to publish a due fixed sample")
            self.scalar_records[-1].update(
                {
                    "terminal_current_relative_imbalance": float(
                        sampled.electrical.relative_current_imbalance
                    ),
                    "device_power_relative_imbalance": float(
                        sampled.electrical.relative_power_imbalance
                    ),
                    "temperature_in_declared_range": bool(
                        np.all(np.isfinite(sampled.state.temperature_K))
                        and np.all(
                            sampled.state.temperature_K
                            >= self.closure.temperature_min_K
                        )
                        and np.all(
                            sampled.state.temperature_K
                            <= self.closure.temperature_max_K
                        )
                    ),
                    "conductive_state_in_declared_range": bool(
                        np.all(
                            (sampled.state.conductive_state >= 0.0)
                            & (sampled.state.conductive_state <= 1.0)
                        )
                    ),
                    "branch_memory_in_declared_range": bool(
                        np.all(
                            (sampled.state.branch_memory >= -1.0)
                            & (sampled.state.branch_memory <= 1.0)
                        )
                    ),
                }
            )
            self._update_controller_telemetry(
                step=step,
                outer_interval_s=outer_interval_s,
                coupled_solve_count=coupled_solve_count,
            )


def run_s2_streaming_protocol_v3(
    case_id: str,
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
    retain_full_history: bool = False,
    retained_step_limit: int = 0,
    attempt_record_callback: Any | None = None,
    failure_callback: Any | None = None,
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
    performance_timings: S2PerformanceTimings | None = None,
) -> S2StreamingResult:
    stop = float(
        config["reference_solver"]["time_grid"]["final_time_s"]
        if final_time_s is None
        else final_time_s
    )
    samples = fixed_scalar_sample_times(config, stop)
    discontinuities = tuple(
        float(value)
        for value in protocol_discontinuities(protocol)
        if initial_state.time_s <= float(value) <= stop
    )
    fixed = set(
        float(value)
        for value in (
            0.0,
            5.0e-6,
            1.0e-5,
            1.5e-5,
            2.0e-5,
            *discontinuities,
        )
        if initial_state.time_s <= float(value) <= stop
    )
    recorder = _ControllerV3StreamingRecorder(
        case_id=case_id,
        grid=grid,
        fields=fields,
        protocol=protocol,
        config=config,
        sample_times_s=samples,
        fixed_snapshot_times_s=tuple(sorted(fixed)),
        initial_state=initial_state,
        voltage_scale_V=protocol_voltage_scale(config, protocol_id),
        closure=closure,
    )
    attempts = _ControllerV2AttemptAccumulator()

    def record_accepted(
        previous_state: S2State,
        step: S2EmbeddedStepResult,
        outer_interval_s: float,
        input_voltage_V: float,
        wall_time_s: float,
    ) -> None:
        recorder.record_accepted_interval(
            previous_state,
            step,
            outer_interval_s,
            input_voltage_V,
            wall_time_s,
            coupled_solve_count=attempts.consume(step),
        )

    result = simulate_s2_protocol_v3(
        initial_state,
        case_id=case_id,
        protocol=protocol,
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        time_divisor=time_divisor,
        final_time_s=stop,
        maximum_accepted_steps=maximum_accepted_steps,
        maximum_wall_clock_s=maximum_wall_clock_s,
        retain_full_history=retain_full_history,
        retained_step_limit=retained_step_limit,
        accepted_step_callback=record_accepted,
        attempted_candidate_callback=attempts,
        attempt_record_callback=attempt_record_callback,
        failure_callback=failure_callback,
        cache=cache if cache is not None else build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=use_equivalent_optimizations,
        use_unit_voltage_scaling=use_unit_voltage_scaling,
        performance_timings=performance_timings,
    )
    if result.completed and recorder._sample_index != len(samples):
        raise RuntimeError("controller-v3 completed without all fixed output samples")
    event_snapshots = recorder.selected_event_snapshots()
    return S2StreamingResult(
        case_id=case_id,
        protocol_result=result,
        final_state=recorder.final_state,
        scalar_records=tuple(recorder.scalar_records),
        event_records=tuple(recorder.event_records),
        reversal_records=tuple(recorder.reversal_records),
        field_snapshots=tuple(recorder.fixed_snapshots) + event_snapshots,
        retained_event_snapshot_count=len(event_snapshots),
        maximum_in_memory_event_snapshots=recorder.maximum_in_memory_event_snapshots,
    )


__all__ = [
    "DENSE_OUTPUT_ID",
    "LEDGER_OUTPUT_SEMANTICS",
    "run_s2_streaming_protocol_v3",
]
