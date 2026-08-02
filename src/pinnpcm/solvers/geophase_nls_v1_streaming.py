"""Fixed-output streaming adapter for the independently versioned NLS-v1."""

from __future__ import annotations

from typing import Any

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_nls_v1 import NLS_V1_ID, simulate_s2_protocol_nls_v1
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import S2EmbeddedStepResult
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2PerformanceTimings,
    S2SolverCache,
    S2State,
    build_s2_solver_cache,
    protocol_discontinuities,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import (
    S2StreamingResult,
    _ControllerV2AttemptAccumulator,
    fixed_scalar_sample_times,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming_v3 import (
    _ControllerV3StreamingRecorder,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import protocol_voltage_scale


def run_s2_streaming_protocol_nls_v1(
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

    result = simulate_s2_protocol_nls_v1(
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
        raise RuntimeError("NLS-v1 completed without all fixed output samples")
    for row in recorder.scalar_records:
        row["nonlinear_solver_identity"] = NLS_V1_ID
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


__all__ = ["run_s2_streaming_protocol_nls_v1"]
