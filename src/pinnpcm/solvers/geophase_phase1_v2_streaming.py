"""Bounded-memory streaming evidence for Phase 1-v2 S2 trajectories."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2ProtocolResult,
    S2SolverCache,
    S2State,
    S2StepResult,
    build_s2_solver_cache,
    protocol_discontinuities,
    protocol_voltage,
    simulate_s2_protocol,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    S2EmbeddedAttemptObservation,
    S2EmbeddedStepResult,
    protocol_voltage_scale,
    simulate_s2_protocol_v2,
)


@dataclass(frozen=True)
class S2FullFieldSnapshot:
    time_s: float
    snapshot_kind: str
    event_index: int | None
    event_direction: str | None
    temperature_K: np.ndarray
    conductive_state: np.ndarray
    branch_memory: np.ndarray
    potential_V: np.ndarray
    cell_joule_power_W: np.ndarray


@dataclass(frozen=True)
class S2StreamingResult:
    case_id: str
    protocol_result: S2ProtocolResult
    final_state: S2State
    scalar_records: tuple[dict[str, Any], ...]
    event_records: tuple[dict[str, Any], ...]
    field_snapshots: tuple[S2FullFieldSnapshot, ...]
    retained_event_snapshot_count: int
    maximum_in_memory_event_snapshots: int


def fixed_scalar_sample_times(config: dict, final_time_s: float) -> np.ndarray:
    """Return the locked physical comparison grid truncated to a run window."""

    definition = config["reference_solver"]["fixed_physical_comparison_time_grid"]
    start = float(definition["start_s"])
    stop = float(definition["stop_s"])
    points = int(definition["points"])
    interval = float(definition["interval_s"])
    if points != 4001 or not np.isclose(stop - start, interval * (points - 1)):
        raise ValueError("Phase 1-v2 fixed scalar grid no longer matches its lock")
    requested_stop = float(final_time_s)
    if not np.isfinite(requested_stop) or requested_stop <= start or requested_stop > stop:
        raise ValueError("streaming final time is outside the locked comparison window")
    full = start + interval * np.arange(points, dtype=float)
    tolerance = max(1.0e-18, abs(stop) * 1.0e-13)
    return full[full <= requested_stop + tolerance]


def _state_mean(values: np.ndarray, grid: GeoPhaseGrid) -> float:
    weights = np.full(grid.shape, grid.cell_area_m2, dtype=float)
    return float(np.sum(np.asarray(values, dtype=float) * weights) / np.sum(weights))


def _snapshot(
    state: S2State,
    *,
    potential_V: np.ndarray,
    cell_joule_power_W: np.ndarray,
    kind: str,
    event_index: int | None = None,
    event_direction: str | None = None,
) -> S2FullFieldSnapshot:
    return S2FullFieldSnapshot(
        time_s=float(state.time_s),
        snapshot_kind=kind,
        event_index=event_index,
        event_direction=event_direction,
        temperature_K=np.asarray(state.temperature_K, dtype=float).copy(),
        conductive_state=np.asarray(state.conductive_state, dtype=float).copy(),
        branch_memory=np.asarray(state.branch_memory, dtype=float).copy(),
        potential_V=np.asarray(potential_V, dtype=float).copy(),
        cell_joule_power_W=np.asarray(cell_joule_power_W, dtype=float).copy(),
    )


def _ledger_columns(prefix: str, balance) -> dict[str, float]:
    return {
        f"{prefix}_input_power_W": float(balance.input_power_W),
        f"{prefix}_accounted_power_W": float(balance.accounted_power_W),
        f"{prefix}_signed_residual_W": float(balance.signed_residual_W),
        f"{prefix}_relative_residual": float(balance.relative_residual),
    }


class _StreamingRecorder:
    def __init__(
        self,
        *,
        case_id: str,
        grid: GeoPhaseGrid,
        fields: S2ThermalFields,
        protocol: dict,
        config: dict,
        sample_times_s: np.ndarray,
        fixed_snapshot_times_s: tuple[float, ...],
        initial_state: S2State,
    ) -> None:
        self.case_id = case_id
        self.grid = grid
        self.fields = fields
        self.protocol = protocol
        self.sample_times_s = np.asarray(sample_times_s, dtype=float)
        self.fixed_snapshot_times_s = fixed_snapshot_times_s
        event = config["metric_contract"]["event_definition"]
        self.threshold = float(event["threshold"])
        self.minimum_event_separation_s = float(event["minimum_separation_s"])
        self.scalar_records: list[dict[str, Any]] = []
        self.event_records: list[dict[str, Any]] = []
        self.fixed_snapshots: list[S2FullFieldSnapshot] = []
        self._event_snapshot_pairs: list[
            tuple[S2FullFieldSnapshot, S2FullFieldSnapshot]
        ] = []
        self.maximum_in_memory_event_snapshots = 0
        self._sample_index = 1
        self._previous_scalar_signal = _state_mean(
            initial_state.conductive_state, grid
        )
        self._previous_scalar_snapshot = _snapshot(
            initial_state,
            potential_V=np.zeros(grid.shape, dtype=float),
            cell_joule_power_W=np.zeros(grid.shape, dtype=float),
            kind="initial_scalar",
        )
        self.final_state = initial_state
        self.scalar_records.append(
            {
                "case_id": case_id,
                "sample_index": 0,
                "time_s": float(initial_state.time_s),
                "sample_kind": "initial_no_interval",
                "input_voltage_V": float(protocol_voltage(protocol, initial_state.time_s)),
                "device_voltage_V": float(initial_state.device_voltage_V),
                "terminal_current_A": 0.0,
                "terminal_device_power_W": 0.0,
                "maximum_temperature_K": float(np.max(initial_state.temperature_K)),
                "minimum_temperature_K": float(np.min(initial_state.temperature_K)),
                "mean_temperature_K": _state_mean(initial_state.temperature_K, grid),
                "mean_conductive_state": self._previous_scalar_signal,
                "mean_branch_memory": _state_mean(initial_state.branch_memory, grid),
                "event_count_to_date": 0,
                "last_event_direction": "",
                "last_event_time_s": "",
                "nonlinear_method": "initial_no_interval",
                "newton_iterations": 0,
                "krylov_matvecs": 0,
                "armijo_backtracks": 0,
                "fallback_picard_iterations": 0,
                "lateral_matrix_face_relative_mismatch": 0.0,
                "lateral_matrix_face_roundoff_ratio": 0.0,
                "lateral_face_to_cell_global_residual_W": 0.0,
                **{
                    f"{prefix}_{field}": 0.0
                    for prefix in ("thermal", "circuit", "combined", "device_power")
                    for field in (
                        "input_power_W",
                        "accounted_power_W",
                        "signed_residual_W",
                        "relative_residual",
                    )
                },
            }
        )
        if self._matches_any(initial_state.time_s, fixed_snapshot_times_s):
            self.fixed_snapshots.append(
                _snapshot(
                    initial_state,
                    potential_V=np.zeros(grid.shape, dtype=float),
                    cell_joule_power_W=np.zeros(grid.shape, dtype=float),
                    kind="fixed",
                )
            )

    @staticmethod
    def _matches_any(value: float, candidates: tuple[float, ...]) -> bool:
        return any(
            abs(float(value) - candidate)
            <= max(1.0e-18, abs(candidate) * 1.0e-12)
            for candidate in candidates
        )

    def _record_event(
        self,
        *,
        previous_signal: float,
        current_signal: float,
        current_snapshot: S2FullFieldSnapshot,
    ) -> None:
        direction: str | None = None
        if previous_signal < self.threshold <= current_signal:
            direction = "upward"
        elif previous_signal > self.threshold >= current_signal:
            direction = "downward"
        if direction is None:
            return
        denominator = current_signal - previous_signal
        if denominator == 0.0:
            return
        fraction = (self.threshold - previous_signal) / denominator
        crossing_time = self._previous_scalar_snapshot.time_s + fraction * (
            current_snapshot.time_s - self._previous_scalar_snapshot.time_s
        )
        if self.event_records and (
            crossing_time - float(self.event_records[-1]["crossing_time_s"])
            < self.minimum_event_separation_s - 1.0e-18
        ):
            return
        index = len(self.event_records) + 1
        before = S2FullFieldSnapshot(
            **{
                **self._previous_scalar_snapshot.__dict__,
                "snapshot_kind": "event_before",
                "event_index": index,
                "event_direction": direction,
            }
        )
        after = S2FullFieldSnapshot(
            **{
                **current_snapshot.__dict__,
                "snapshot_kind": "event_after",
                "event_index": index,
                "event_direction": direction,
            }
        )
        pair = (before, after)
        if len(self._event_snapshot_pairs) < 8:
            self._event_snapshot_pairs.append(pair)
        else:
            self._event_snapshot_pairs = (
                self._event_snapshot_pairs[:4]
                + self._event_snapshot_pairs[-3:]
                + [pair]
            )
        self.maximum_in_memory_event_snapshots = max(
            self.maximum_in_memory_event_snapshots,
            2 * len(self._event_snapshot_pairs),
        )
        self.event_records.append(
            {
                "case_id": self.case_id,
                "event_index": index,
                "direction": direction,
                "crossing_time_s": float(crossing_time),
                "before_sample_time_s": float(self._previous_scalar_snapshot.time_s),
                "after_sample_time_s": float(current_snapshot.time_s),
                "before_signal": float(previous_signal),
                "after_signal": float(current_signal),
            }
        )

    def __call__(
        self,
        _previous_state: S2State,
        step: S2StepResult,
        _dt_s: float,
        input_voltage_V: float,
        _wall_time_s: float,
    ) -> None:
        self.final_state = step.state
        if self._matches_any(step.state.time_s, self.fixed_snapshot_times_s):
            self.fixed_snapshots.append(
                _snapshot(
                    step.state,
                    potential_V=step.electrical.potential_V,
                    cell_joule_power_W=step.electrical.cell_joule_power_W,
                    kind="fixed",
                )
            )
        if self._sample_index >= len(self.sample_times_s):
            return
        target = float(self.sample_times_s[self._sample_index])
        tolerance = max(1.0e-18, abs(target) * 1.0e-12)
        if abs(step.state.time_s - target) > tolerance:
            return
        current_signal = _state_mean(step.state.conductive_state, self.grid)
        current_snapshot = _snapshot(
            step.state,
            potential_V=step.electrical.potential_V,
            cell_joule_power_W=step.electrical.cell_joule_power_W,
            kind="scalar",
        )
        self._record_event(
            previous_signal=self._previous_scalar_signal,
            current_signal=current_signal,
            current_snapshot=current_snapshot,
        )
        last_event = self.event_records[-1] if self.event_records else None
        row: dict[str, Any] = {
            "case_id": self.case_id,
            "sample_index": self._sample_index,
            "time_s": float(step.state.time_s),
            "sample_kind": "fixed_grid",
            "input_voltage_V": float(input_voltage_V),
            "device_voltage_V": float(step.state.device_voltage_V),
            "terminal_current_A": float(step.electrical.source_current_A),
            "terminal_device_power_W": float(step.electrical.terminal_device_power_W),
            "maximum_temperature_K": float(np.max(step.state.temperature_K)),
            "minimum_temperature_K": float(np.min(step.state.temperature_K)),
            "mean_temperature_K": _state_mean(step.state.temperature_K, self.grid),
            "mean_conductive_state": current_signal,
            "mean_branch_memory": _state_mean(step.state.branch_memory, self.grid),
            "event_count_to_date": len(self.event_records),
            "last_event_direction": "" if last_event is None else last_event["direction"],
            "last_event_time_s": "" if last_event is None else last_event["crossing_time_s"],
            "nonlinear_method": step.nonlinear.method,
            "newton_iterations": int(step.nonlinear.iterations),
            "krylov_matvecs": int(step.nonlinear.krylov_matvecs),
            "armijo_backtracks": int(step.nonlinear.armijo_backtracks),
            "fallback_picard_iterations": int(step.nonlinear.fallback_picard_iterations),
            "lateral_matrix_face_relative_mismatch": float(
                step.lateral_flux.matrix_face_relative_mismatch
            ),
            "lateral_matrix_face_roundoff_ratio": float(
                step.lateral_flux.matrix_face_roundoff_ratio
            ),
            "lateral_face_to_cell_global_residual_W": float(
                step.lateral_flux.face_to_cell_global_residual_W
            ),
        }
        for name in ("thermal", "circuit", "combined", "device_power"):
            row.update(_ledger_columns(name, getattr(step.ledgers, name)))
        self.scalar_records.append(row)
        self._previous_scalar_signal = current_signal
        self._previous_scalar_snapshot = current_snapshot
        self._sample_index += 1

    def selected_event_snapshots(self) -> tuple[S2FullFieldSnapshot, ...]:
        return tuple(
            snapshot for pair in self._event_snapshot_pairs for snapshot in pair
        )


class _ControllerV2AttemptAccumulator:
    """Count every coupled solve without exposing rejected-path state to output."""

    def __init__(self) -> None:
        self._coupled_solve_count = 0

    def __call__(self, observation: S2EmbeddedAttemptObservation) -> None:
        self._coupled_solve_count += int(observation.diagnostics.coupled_solve_count)

    def consume(self, accepted_step: S2EmbeddedStepResult) -> int:
        observed = self._coupled_solve_count
        self._coupled_solve_count = 0
        return max(observed, int(accepted_step.controller.coupled_solve_count))


class _ControllerV2StreamingRecorder(_StreamingRecorder):
    """Record only the accepted two-half path plus controller-v2 telemetry."""

    _INITIAL_TELEMETRY: dict[str, Any] = {
        "time_controller": "embedded_time_consistency_v2_only",
        "outer_interval_s": 0.0,
        "outer_rejections": 0,
        "coupled_solve_count": 0,
        "accepted_bundle_coupled_solve_count": 0,
        "e_T": 0.0,
        "e_s": 0.0,
        "e_b": 0.0,
        "e_V": 0.0,
        "e_max": 0.0,
        "legacy_max_absolute_delta_s": 0.0,
        "legacy_max_absolute_delta_b": 0.0,
    }

    def __init__(self, *, voltage_scale_V: float, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.scalar_records[0].update(
            {
                **self._INITIAL_TELEMETRY,
                "voltage_scale_V": float(voltage_scale_V),
                **self._empty_path_telemetry(),
            }
        )
        self._fine_previous_signal = self._previous_scalar_signal
        self._fine_previous_snapshot = self._previous_scalar_snapshot

    @staticmethod
    def _empty_path_telemetry() -> dict[str, Any]:
        values: dict[str, Any] = {}
        for prefix in ("full", "first_half", "second_half"):
            for suffix in (
                "finite",
                "nonlinear_pass",
                "ledger_pass",
                "lateral_pass",
                "overall_pass",
                "lateral_relative_mismatch",
                "lateral_roundoff_ratio",
                "nonlinear_method",
                "nonlinear_iterations",
                "krylov_matvecs",
                "armijo_backtracks",
                "fallback_picard_iterations",
            ):
                values[f"{prefix}_{suffix}"] = None
            for ledger in ("thermal", "circuit", "combined", "device_power"):
                values[f"{prefix}_{ledger}_relative_residual"] = None
        for suffix in ("finite", "ledger_pass", "overall_pass"):
            values[f"aggregate_{suffix}"] = None
        for ledger in ("thermal", "circuit", "combined", "device_power"):
            values[f"aggregate_{ledger}_relative_residual"] = None
        return values

    @staticmethod
    def _path_telemetry(prefix: str, path: Any, nonlinear: Any) -> dict[str, Any]:
        values = {
            f"{prefix}_finite": bool(path.finite),
            f"{prefix}_nonlinear_pass": bool(path.nonlinear_pass),
            f"{prefix}_ledger_pass": bool(path.ledger_pass),
            f"{prefix}_lateral_pass": bool(path.lateral_pass),
            f"{prefix}_overall_pass": bool(path.overall_pass),
            f"{prefix}_lateral_relative_mismatch": float(
                path.lateral_relative_mismatch
            ),
            f"{prefix}_lateral_roundoff_ratio": float(path.lateral_roundoff_ratio),
            f"{prefix}_nonlinear_method": str(nonlinear.method),
            f"{prefix}_nonlinear_iterations": int(nonlinear.iterations),
            f"{prefix}_krylov_matvecs": int(nonlinear.krylov_matvecs),
            f"{prefix}_armijo_backtracks": int(nonlinear.armijo_backtracks),
            f"{prefix}_fallback_picard_iterations": int(
                nonlinear.fallback_picard_iterations
            ),
        }
        values.update(
            {
                f"{prefix}_{ledger}_relative_residual": float(residual)
                for ledger, residual in path.ledger_relative_residuals.items()
            }
        )
        return values

    @staticmethod
    def _aggregate_telemetry(aggregate: Any) -> dict[str, Any]:
        values = {
            "aggregate_finite": bool(aggregate.finite),
            "aggregate_ledger_pass": bool(aggregate.ledger_pass),
            "aggregate_overall_pass": bool(aggregate.overall_pass),
        }
        values.update(
            {
                f"aggregate_{ledger}_relative_residual": float(residual)
                for ledger, residual in aggregate.ledger_relative_residuals.items()
            }
        )
        return values

    def _record_event(self, **_kwargs: Any) -> None:
        """Base fixed-grid event hook is replaced by accepted fine-path events."""

    def _record_accepted_fine_event_state(
        self, candidate: Any, *, nonlinear: Any | None = None
    ) -> None:
        nonlinear = candidate.nonlinear if nonlinear is None else nonlinear
        current_signal = _state_mean(candidate.state.conductive_state, self.grid)
        current_snapshot = _snapshot(
            candidate.state,
            potential_V=candidate.electrical.potential_V,
            cell_joule_power_W=candidate.electrical.cell_joule_power_W,
            kind="accepted_fine_path",
        )
        direction: str | None = None
        if self._fine_previous_signal < self.threshold <= current_signal:
            direction = "upward"
        elif self._fine_previous_signal > self.threshold >= current_signal:
            direction = "downward"
        denominator = current_signal - self._fine_previous_signal
        if direction is not None and denominator != 0.0:
            fraction = (self.threshold - self._fine_previous_signal) / denominator
            crossing_time = self._fine_previous_snapshot.time_s + fraction * (
                current_snapshot.time_s - self._fine_previous_snapshot.time_s
            )
            separated = not self.event_records or (
                crossing_time - float(self.event_records[-1]["crossing_time_s"])
                >= self.minimum_event_separation_s - 1.0e-18
            )
            if separated:
                index = len(self.event_records) + 1
                before = S2FullFieldSnapshot(
                    **{
                        **self._fine_previous_snapshot.__dict__,
                        "snapshot_kind": "event_before",
                        "event_index": index,
                        "event_direction": direction,
                    }
                )
                after = S2FullFieldSnapshot(
                    **{
                        **current_snapshot.__dict__,
                        "snapshot_kind": "event_after",
                        "event_index": index,
                        "event_direction": direction,
                    }
                )
                pair = (before, after)
                if len(self._event_snapshot_pairs) < 8:
                    self._event_snapshot_pairs.append(pair)
                else:
                    self._event_snapshot_pairs = (
                        self._event_snapshot_pairs[:4]
                        + self._event_snapshot_pairs[-3:]
                        + [pair]
                    )
                self.maximum_in_memory_event_snapshots = max(
                    self.maximum_in_memory_event_snapshots,
                    2 * len(self._event_snapshot_pairs),
                )
                self.event_records.append(
                    {
                        "case_id": self.case_id,
                        "event_index": index,
                        "direction": direction,
                        "crossing_time_s": float(crossing_time),
                        "before_sample_time_s": float(
                            self._fine_previous_snapshot.time_s
                        ),
                        "after_sample_time_s": float(current_snapshot.time_s),
                        "before_signal": float(self._fine_previous_signal),
                        "after_signal": float(current_signal),
                        "nonlinear_method": str(nonlinear.method),
                        "nonlinear_iterations": int(nonlinear.iterations),
                        "krylov_matvecs": int(nonlinear.krylov_matvecs),
                        "armijo_backtracks": int(
                            nonlinear.armijo_backtracks
                        ),
                        "fallback_picard_iterations": int(
                            nonlinear.fallback_picard_iterations
                        ),
                    }
                )
        self._fine_previous_signal = current_signal
        self._fine_previous_snapshot = current_snapshot

    def record_accepted_interval(
        self,
        previous_state: S2State,
        step: S2EmbeddedStepResult,
        outer_interval_s: float,
        input_voltage_V: float,
        wall_time_s: float,
        *,
        coupled_solve_count: int,
    ) -> None:
        self._record_accepted_fine_event_state(step.accepted_first_half)
        self._record_accepted_fine_event_state(
            step, nonlinear=step.controller.second_half_nonlinear
        )
        previous_record_count = len(self.scalar_records)
        super().__call__(
            previous_state,
            step,
            outer_interval_s,
            input_voltage_V,
            wall_time_s,
        )
        if len(self.scalar_records) == previous_record_count:
            return
        embedded = step.controller.embedded_error
        if embedded is None:
            raise RuntimeError("accepted controller-v2 step lacks embedded error")
        self.scalar_records[-1].update(
            {
                "time_controller": "embedded_time_consistency_v2_only",
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
                    "full",
                    step.controller.full_step,
                    step.controller.full_nonlinear,
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


def run_s2_streaming_protocol(
    case_id: str,
    initial_state: S2State,
    *,
    protocol: dict,
    grid: GeoPhaseGrid,
    closure: EffectiveVO2Closure,
    fields: S2ThermalFields,
    config: dict,
    time_divisor: int = 1,
    final_time_s: float | None = None,
    maximum_accepted_steps: int | None = None,
    maximum_wall_clock_s: float | None = None,
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
) -> S2StreamingResult:
    """Run S2 with fixed-grid scalar evidence and bounded full-field memory."""

    stop = float(
        config["reference_solver"]["time_grid"]["final_time_s"]
        if final_time_s is None
        else final_time_s
    )
    samples = fixed_scalar_sample_times(config, stop)
    fixed = set(
        float(value)
        for value in (
            0.0,
            5.0e-6,
            1.0e-5,
            1.5e-5,
            2.0e-5,
            *protocol_discontinuities(protocol),
        )
        if initial_state.time_s <= float(value) <= stop
    )
    recorder = _StreamingRecorder(
        case_id=case_id,
        grid=grid,
        fields=fields,
        protocol=protocol,
        config=config,
        sample_times_s=samples,
        fixed_snapshot_times_s=tuple(sorted(fixed)),
        initial_state=initial_state,
    )
    result = simulate_s2_protocol(
        initial_state,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        time_divisor=time_divisor,
        final_time_s=stop,
        maximum_accepted_steps=maximum_accepted_steps,
        maximum_wall_clock_s=maximum_wall_clock_s,
        forced_times_s=tuple(samples),
        retain_full_history=False,
        retained_step_limit=0,
        accepted_step_callback=recorder,
        cache=cache if cache is not None else build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=use_equivalent_optimizations,
        use_unit_voltage_scaling=use_unit_voltage_scaling,
    )
    event_snapshots = recorder.selected_event_snapshots()
    snapshots = tuple(recorder.fixed_snapshots) + event_snapshots
    return S2StreamingResult(
        case_id=case_id,
        protocol_result=result,
        final_state=recorder.final_state,
        scalar_records=tuple(recorder.scalar_records),
        event_records=tuple(recorder.event_records),
        field_snapshots=snapshots,
        retained_event_snapshot_count=len(event_snapshots),
        maximum_in_memory_event_snapshots=recorder.maximum_in_memory_event_snapshots,
    )


def run_s2_streaming_protocol_v2(
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
    cache: S2SolverCache | None = None,
    use_equivalent_optimizations: bool = True,
    use_unit_voltage_scaling: bool = False,
) -> S2StreamingResult:
    """Run active controller-v2 with one accepted-path streaming recorder.

    ``retain_full_history=True`` is reserved for bounded parity/readiness cases
    such as C1.  The returned ``protocol_result.steps`` and streaming records
    then come from the same call to :func:`simulate_s2_protocol_v2`; no second
    numerical trajectory is needed.  Rejected and full-step estimator paths
    contribute only solve-count telemetry and can never enter events, fields,
    or scalar QoIs.
    """

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
    forced_landings = tuple(
        sorted(set(float(value) for value in samples) | set(discontinuities))
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
    voltage_scale = protocol_voltage_scale(config, protocol_id)
    recorder = _ControllerV2StreamingRecorder(
        case_id=case_id,
        grid=grid,
        fields=fields,
        protocol=protocol,
        config=config,
        sample_times_s=samples,
        fixed_snapshot_times_s=tuple(sorted(fixed)),
        initial_state=initial_state,
        voltage_scale_V=voltage_scale,
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

    result = simulate_s2_protocol_v2(
        initial_state,
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
        forced_times_s=forced_landings,
        retain_full_history=retain_full_history,
        retained_step_limit=retained_step_limit,
        accepted_step_callback=record_accepted,
        attempted_candidate_callback=attempts,
        cache=cache if cache is not None else build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=use_equivalent_optimizations,
        use_unit_voltage_scaling=use_unit_voltage_scaling,
    )
    event_snapshots = recorder.selected_event_snapshots()
    snapshots = tuple(recorder.fixed_snapshots) + event_snapshots
    return S2StreamingResult(
        case_id=case_id,
        protocol_result=result,
        final_state=recorder.final_state,
        scalar_records=tuple(recorder.scalar_records),
        event_records=tuple(recorder.event_records),
        field_snapshots=snapshots,
        retained_event_snapshot_count=len(event_snapshots),
        maximum_in_memory_event_snapshots=recorder.maximum_in_memory_event_snapshots,
    )


def _csv_text(rows: tuple[dict[str, Any], ...], fieldnames: list[str]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_pre_streaming_case(
    parent: Path,
    result: S2StreamingResult,
    *,
    identity_hashes: dict[str, str],
) -> Path:
    """Validate and atomically publish one immutable PRE streaming case."""

    if not result.case_id.startswith("PRE-"):
        raise ValueError("readiness streaming publication accepts PRE IDs only")
    root = Path(parent)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / result.case_id
    if destination.exists():
        raise FileExistsError("PRE case publication is immutable")
    temporary = root / f".{result.case_id}.tmp-{uuid4().hex}"
    temporary.mkdir()
    try:
        scalar_fields = list(result.scalar_records[0])
        (temporary / "scalars.csv").write_text(
            _csv_text(result.scalar_records, scalar_fields),
            encoding="utf-8",
            newline="\n",
        )
        event_fields = (
            list(result.event_records[0])
            if result.event_records
            else [
                "case_id",
                "event_index",
                "direction",
                "crossing_time_s",
                "before_sample_time_s",
                "after_sample_time_s",
                "before_signal",
                "after_signal",
            ]
        )
        (temporary / "events.csv").write_text(
            _csv_text(result.event_records, event_fields),
            encoding="utf-8",
            newline="\n",
        )
        arrays: dict[str, np.ndarray] = {}
        snapshot_index: list[dict[str, Any]] = []
        for index, snapshot in enumerate(result.field_snapshots):
            prefix = f"snapshot_{index:03d}"
            arrays[f"{prefix}_temperature_K"] = snapshot.temperature_K
            arrays[f"{prefix}_conductive_state"] = snapshot.conductive_state
            arrays[f"{prefix}_branch_memory"] = snapshot.branch_memory
            arrays[f"{prefix}_potential_V"] = snapshot.potential_V
            arrays[f"{prefix}_cell_joule_power_W"] = snapshot.cell_joule_power_W
            snapshot_index.append(
                {
                    "prefix": prefix,
                    "time_s": snapshot.time_s,
                    "snapshot_kind": snapshot.snapshot_kind,
                    "event_index": snapshot.event_index,
                    "event_direction": snapshot.event_direction,
                }
            )
        np.savez_compressed(temporary / "fields.npz", **arrays)
        metadata = {
            "schema_version": "geophase_phase1_v2_streaming_case_v1",
            "case_id": result.case_id,
            "formal": False,
            "formal_execution_count": 0,
            "completed": result.protocol_result.completed,
            "stop_reason": result.protocol_result.stop_reason,
            "accepted_steps": result.protocol_result.diagnostics.accepted_steps,
            "scalar_record_count": len(result.scalar_records),
            "event_record_count": len(result.event_records),
            "field_snapshot_count": len(result.field_snapshots),
            "retained_full_accepted_step_history": len(result.protocol_result.steps),
            "snapshot_index": snapshot_index,
            "identity_hashes": dict(sorted(identity_hashes.items())),
        }
        (temporary / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        payload_names = ("scalars.csv", "events.csv", "fields.npz", "metadata.json")
        payload_hashes = {name: _sha256(temporary / name) for name in payload_names}
        completion = {
            "schema_version": "geophase_phase1_v2_streaming_case_completion_v1",
            "case_id": result.case_id,
            "status": "validated_complete",
            "payload_hashes_sha256": payload_hashes,
        }
        (temporary / "completion.json").write_text(
            json.dumps(completion, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        observed_metadata = json.loads(
            (temporary / "metadata.json").read_text(encoding="utf-8")
        )
        observed_completion = json.loads(
            (temporary / "completion.json").read_text(encoding="utf-8")
        )
        if observed_metadata["case_id"] != result.case_id:
            raise RuntimeError("PRE streaming metadata validation failed")
        if observed_metadata["retained_full_accepted_step_history"] != 0:
            raise RuntimeError("PRE streaming case retained forbidden full history")
        for name, expected in observed_completion["payload_hashes_sha256"].items():
            if _sha256(temporary / name) != expected:
                raise RuntimeError("PRE streaming payload hash validation failed")
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def published_case_bytes(path: Path) -> int:
    return int(sum(item.stat().st_size for item in Path(path).iterdir() if item.is_file()))


__all__ = [
    "S2FullFieldSnapshot",
    "S2StreamingResult",
    "fixed_scalar_sample_times",
    "publish_pre_streaming_case",
    "published_case_bytes",
    "run_s2_streaming_protocol",
    "run_s2_streaming_protocol_v2",
]
