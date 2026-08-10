"""Protocol-selected equilibria for the self-consistent conservative M1 model.

The module follows explicit monotone device-terminal voltage protocols.  It
never averages roots, assigns a hidden root identity, or uses pseudo-arclength
continuation.  Physical stability is assessed from the semi-discrete thermal
dynamics with one positive device-level heat-capacity scale from the frozen
Qiu source contract.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import load_yaml
from pinnpcm.experiments.m1_self_consistent_imt_contraction import (
    EVIDENCE_TYPE,
    FixedPointResult,
    build_operator,
    fixed_point_valid,
    load_qiu_parameters,
    solve_fixed_point,
)
from pinnpcm.physics.m1_self_consistent_imt import M1SelfConsistentIMTProjection


Tensor = torch.Tensor
SolveFunction = Callable[..., FixedPointResult]


@dataclass(frozen=True)
class ProtocolSpec:
    protocol_id: str
    context_id: str
    context_label: str
    contact_overlap_nm: float
    sink_amplitude: float
    branch_label: str
    branch_value: float
    direction: str
    start_voltage_V: float
    end_voltage_V: float
    voltage_step_V: float
    start_temperature_K: float
    endpoint_preparation: str
    endpoint_mean_state_bound: float
    fallback_preparation_voltage_V: float | None = None


@dataclass
class ProtocolPoint:
    point_id: str
    protocol_id: str
    context_id: str
    branch_label: str
    branch_value: float
    voltage_V: float
    point_kind: str
    sequence_index: int
    initial_state_provenance: str
    previous_point_id: str
    result: FixedPointResult
    valid: bool
    accepted: bool
    jump_from_previous: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolEvent:
    event_id: str
    protocol_id: str
    coarse_pre: ProtocolPoint
    coarse_post: ProtocolPoint
    refined_pre: ProtocolPoint
    refined_post: ProtocolPoint
    refinement_points: list[ProtocolPoint]
    refinement_solve_count: int
    resolved: bool

    @property
    def voltage_lower_V(self) -> float:
        return min(self.refined_pre.voltage_V, self.refined_post.voltage_V)

    @property
    def voltage_upper_V(self) -> float:
        return max(self.refined_pre.voltage_V, self.refined_post.voltage_V)

    @property
    def switching_voltage_estimate_V(self) -> float:
        return 0.5 * (self.voltage_lower_V + self.voltage_upper_V)


@dataclass
class ProtocolRun:
    spec: ProtocolSpec
    expected_coarse_points: int
    preparation_points: list[ProtocolPoint]
    coarse_points: list[ProtocolPoint]
    event: ProtocolEvent | None
    half_step_points: list[ProtocolPoint]
    half_step_event_pre: ProtocolPoint | None
    half_step_event_post: ProtocolPoint | None
    endpoint_pass: bool
    completed: bool
    failure_reason: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})


def _union_fieldnames(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Preserve every heterogeneous row field instead of trusting the first row."""

    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                names.append(str(name))
    return names


def _numpy(value: Tensor | np.ndarray | float | int | bool) -> np.ndarray:
    if isinstance(value, Tensor):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def _relative_scalar_jump(left: float, right: float) -> float:
    return abs(float(right) - float(left)) / max(abs(float(left)), abs(float(right)), 1.0e-30)


def _temperature_rise_relative_difference(
    left: Tensor, right: Tensor, ambient_temperature_K: float
) -> float:
    left_rise = left - float(ambient_temperature_K)
    right_rise = right - float(ambient_temperature_K)
    denominator = torch.clamp(
        torch.maximum(
            torch.linalg.vector_norm(left_rise),
            torch.linalg.vector_norm(right_rise),
        ),
        min=1.0e-30,
    )
    return float(torch.linalg.vector_norm(right_rise - left_rise) / denominator)


def jump_diagnostics(
    previous: FixedPointResult,
    candidate: FixedPointResult,
    *,
    ambient_temperature_K: float,
    jump_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen disjunctive protocol-jump definition."""

    mean_state_change = abs(
        float(candidate.metrics["mean_effective_state_coordinate"])
        - float(previous.metrics["mean_effective_state_coordinate"])
    )
    current_jump = _relative_scalar_jump(
        float(previous.metrics["terminal_current_A"]),
        float(candidate.metrics["terminal_current_A"]),
    )
    temperature_jump = _temperature_rise_relative_difference(
        previous.temperature_K,
        candidate.temperature_K,
        ambient_temperature_K,
    )
    flags = {
        "mean_state_jump": mean_state_change
        >= float(jump_config["mean_state_change_min"]),
        "current_jump": current_jump
        >= float(jump_config["terminal_current_relative_jump_min"]),
        "temperature_jump": temperature_jump
        >= float(jump_config["temperature_rise_field_relative_jump_min"]),
    }
    return {
        "mean_state_change": mean_state_change,
        "terminal_current_relative_jump": current_jump,
        "temperature_rise_field_relative_jump": temperature_jump,
        **flags,
        "jump_candidate": bool(any(flags.values())),
    }


def validate_protocol_schema(config: Mapping[str, Any]) -> None:
    """Reject hidden-root semantics and non-monotone protocol metadata."""

    protocols = config["protocols"]
    forbidden = {str(item) for item in protocols["forbidden_future_inputs"]}
    required_forbidden = {"root_id", "cold_solution_label", "hot_solution_label"}
    if not required_forbidden.issubset(forbidden):
        raise ValueError("protocol schema must explicitly forbid hidden root labels")
    operations = {str(item) for item in protocols["forbidden_selection_operations"]}
    if "root_averaging" not in operations or "pseudo_arclength" not in operations:
        raise ValueError("protocol schema must forbid root averaging and pseudo-arclength")
    heating = protocols["heating"]
    cooling = protocols["cooling"]
    if not (
        str(heating["direction"]) == "increasing"
        and float(heating["voltage_step_V"]) > 0.0
        and float(heating["start_voltage_V"]) < float(heating["end_voltage_V"])
    ):
        raise ValueError("heating protocol is not a monotone increasing ramp")
    if not (
        str(cooling["direction"]) == "decreasing"
        and float(cooling["voltage_step_V"]) < 0.0
        and float(cooling["start_voltage_V"]) > float(cooling["end_voltage_V"])
    ):
        raise ValueError("cooling protocol is not a monotone decreasing ramp")


def validate_future_input_contract(
    allowed_inputs: Sequence[str], forbidden_inputs: Sequence[str]
) -> None:
    """Fail closed if a future schema smuggles a numerical-root identity."""

    forbidden = {str(item) for item in forbidden_inputs}
    required = {"root_id", "cold_solution_label", "hot_solution_label"}
    if not required.issubset(forbidden):
        raise ValueError("future protocol schema must forbid every root label")
    normalized = {str(item).lower().replace("-", "_") for item in allowed_inputs}
    disallowed_tokens = {
        "root_id",
        "cold_solution_label",
        "hot_solution_label",
        "root_average",
        "root_averaging",
        "averaged_root",
    }
    if normalized.intersection(disallowed_tokens):
        raise ValueError("future input schema contains hidden root selection semantics")


def build_protocol_specs(config: Mapping[str, Any]) -> list[ProtocolSpec]:
    validate_protocol_schema(config)
    validate_future_input_contract(
        config["surrogate_eligibility"]["future_allowed_inputs"],
        config["surrogate_eligibility"]["future_forbidden_inputs"],
    )
    specs: list[ProtocolSpec] = []
    for context_id, context in config["contexts"].items():
        for branch_label in ("heating", "cooling"):
            protocol = config["protocols"][branch_label]
            bound = (
                float(protocol["endpoint_mean_state_max"])
                if branch_label == "heating"
                else float(protocol["endpoint_mean_state_min"])
            )
            specs.append(
                ProtocolSpec(
                    protocol_id=f"{context_id}_{branch_label}",
                    context_id=str(context_id),
                    context_label=str(context["label"]),
                    contact_overlap_nm=float(context["contact_overlap_nm"]),
                    sink_amplitude=float(context["sink_amplitude"]),
                    branch_label=branch_label,
                    branch_value=float(protocol["branch_value"]),
                    direction=str(protocol["direction"]),
                    start_voltage_V=float(protocol["start_voltage_V"]),
                    end_voltage_V=float(protocol["end_voltage_V"]),
                    voltage_step_V=float(protocol["voltage_step_V"]),
                    start_temperature_K=float(protocol["start_temperature_K"]),
                    endpoint_preparation=str(protocol["endpoint_preparation"]),
                    endpoint_mean_state_bound=bound,
                    fallback_preparation_voltage_V=(
                        float(protocol["fallback_preparation_voltage_V"])
                        if "fallback_preparation_voltage_V" in protocol
                        else None
                    ),
                )
            )
    if len(specs) != int(config["budgets"]["main_protocol_ramps"]):
        raise ValueError("protocol specification left the four-ramp budget")
    return specs


def protocol_voltage_grid(spec: ProtocolSpec) -> np.ndarray:
    span = spec.end_voltage_V - spec.start_voltage_V
    steps = int(round(span / spec.voltage_step_V))
    grid = spec.start_voltage_V + spec.voltage_step_V * np.arange(steps + 1)
    grid[-1] = spec.end_voltage_V
    if grid.size != 33 or not np.all(np.diff(grid) * spec.voltage_step_V > 0.0):
        raise ValueError("protocol ramp must contain 33 monotone coarse voltages")
    return grid.astype(float)


def _endpoint_pass(spec: ProtocolSpec, point: ProtocolPoint) -> bool:
    mean_state = float(point.result.metrics["mean_effective_state_coordinate"])
    if spec.branch_label == "heating":
        return bool(point.valid and mean_state <= spec.endpoint_mean_state_bound)
    return bool(point.valid and mean_state >= spec.endpoint_mean_state_bound)


def _solve_point(
    *,
    point_id: str,
    spec: ProtocolSpec,
    voltage_V: float,
    point_kind: str,
    sequence_index: int,
    initial_temperature_K: Tensor,
    initial_state_provenance: str,
    previous_point_id: str,
    operator: M1SelfConsistentIMTProjection,
    solver_config: Mapping[str, Any],
    validity_gates: Mapping[str, Any],
    solve_function: SolveFunction,
) -> ProtocolPoint:
    result = solve_function(
        operator=operator,
        initial_temperature_K=initial_temperature_K,
        voltage_V=float(voltage_V),
        branch=spec.branch_value,
        sink_amplitude=spec.sink_amplitude,
        solver_config=solver_config,
    )
    valid = fixed_point_valid(result, validity_gates)
    return ProtocolPoint(
        point_id=point_id,
        protocol_id=spec.protocol_id,
        context_id=spec.context_id,
        branch_label=spec.branch_label,
        branch_value=spec.branch_value,
        voltage_V=float(voltage_V),
        point_kind=point_kind,
        sequence_index=int(sequence_index),
        initial_state_provenance=initial_state_provenance,
        previous_point_id=previous_point_id,
        result=result,
        valid=valid,
        accepted=valid,
    )


def run_coarse_protocol(
    *,
    spec: ProtocolSpec,
    operator: M1SelfConsistentIMTProjection,
    solver_config: Mapping[str, Any],
    validity_gates: Mapping[str, Any],
    jump_config: Mapping[str, Any],
    solve_function: SolveFunction = solve_fixed_point,
) -> ProtocolRun:
    """Run one explicit ramp using exactly the previous accepted equilibrium."""

    voltages = protocol_voltage_grid(spec)
    uniform = torch.full(
        (operator.ny, operator.nx), spec.start_temperature_K, dtype=torch.float64
    )
    preparations: list[ProtocolPoint] = []
    first = _solve_point(
        point_id=f"{spec.protocol_id}_coarse_000",
        spec=spec,
        voltage_V=float(voltages[0]),
        point_kind="coarse",
        sequence_index=0,
        initial_temperature_K=uniform,
        initial_state_provenance=f"uniform_{spec.start_temperature_K:g}K",
        previous_point_id="",
        operator=operator,
        solver_config=solver_config,
        validity_gates=validity_gates,
        solve_function=solve_function,
    )

    if not _endpoint_pass(spec, first) and spec.branch_label == "cooling":
        fallback_voltage = spec.fallback_preparation_voltage_V
        if fallback_voltage is None:
            return ProtocolRun(
                spec, len(voltages), [], [first], None, [], None, None, False, False,
                "cooling_endpoint_failed_without_fallback",
            )
        preparations.append(first)
        preparation = _solve_point(
            point_id=f"{spec.protocol_id}_endpoint_preparation_175V",
            spec=spec,
            voltage_V=fallback_voltage,
            point_kind="endpoint_preparation",
            sequence_index=-1,
            initial_temperature_K=uniform,
            initial_state_provenance=f"uniform_{spec.start_temperature_K:g}K",
            previous_point_id="",
            operator=operator,
            solver_config=solver_config,
            validity_gates=validity_gates,
            solve_function=solve_function,
        )
        preparations.append(preparation)
        if preparation.valid and float(
            preparation.result.metrics["mean_effective_state_coordinate"]
        ) >= spec.endpoint_mean_state_bound:
            first = _solve_point(
                point_id=f"{spec.protocol_id}_coarse_000",
                spec=spec,
                voltage_V=float(voltages[0]),
                point_kind="coarse",
                sequence_index=0,
                initial_temperature_K=preparation.result.temperature_K,
                initial_state_provenance="accepted_1.75V_endpoint_preparation",
                previous_point_id=preparation.point_id,
                operator=operator,
                solver_config=solver_config,
                validity_gates=validity_gates,
                solve_function=solve_function,
            )

    endpoint_pass = _endpoint_pass(spec, first)
    coarse = [first]
    if not endpoint_pass:
        return ProtocolRun(
            spec, len(voltages), preparations, coarse, None, [], None, None, False, False,
            f"{spec.branch_label}_endpoint_gate_failed",
        )
    if not first.valid:
        return ProtocolRun(
            spec, len(voltages), preparations, coarse, None, [], None, None, True, False,
            "invalid_start_endpoint",
        )

    first_event_pair: tuple[ProtocolPoint, ProtocolPoint] | None = None
    previous = first
    for index, voltage in enumerate(voltages[1:], start=1):
        point = _solve_point(
            point_id=f"{spec.protocol_id}_coarse_{index:03d}",
            spec=spec,
            voltage_V=float(voltage),
            point_kind="coarse",
            sequence_index=index,
            initial_temperature_K=previous.result.temperature_K,
            initial_state_provenance="immediately_preceding_accepted_protocol_equilibrium",
            previous_point_id=previous.point_id,
            operator=operator,
            solver_config=solver_config,
            validity_gates=validity_gates,
            solve_function=solve_function,
        )
        if point.valid:
            point.jump_from_previous = jump_diagnostics(
                previous.result,
                point.result,
                ambient_temperature_K=operator.ambient_temperature_K,
                jump_config=jump_config,
            )
        coarse.append(point)
        if not point.valid:
            return ProtocolRun(
                spec, len(voltages), preparations, coarse, None, [], None, None,
                True, False, f"invalid_coarse_point_{index}",
            )
        if first_event_pair is None and bool(point.jump_from_previous["jump_candidate"]):
            first_event_pair = (previous, point)
        previous = point

    run = ProtocolRun(
        spec=spec,
        expected_coarse_points=len(voltages),
        preparation_points=preparations,
        coarse_points=coarse,
        event=None,
        half_step_points=[],
        half_step_event_pre=None,
        half_step_event_post=None,
        endpoint_pass=True,
        completed=len(coarse) == len(voltages),
        failure_reason="",
    )
    if first_event_pair is not None:
        run.event = ProtocolEvent(
            event_id=f"{spec.protocol_id}_event_01",
            protocol_id=spec.protocol_id,
            coarse_pre=first_event_pair[0],
            coarse_post=first_event_pair[1],
            refined_pre=first_event_pair[0],
            refined_post=first_event_pair[1],
            refinement_points=[],
            refinement_solve_count=0,
            resolved=False,
        )
    return run


def refine_protocol_event(
    *,
    run: ProtocolRun,
    operator: M1SelfConsistentIMTProjection,
    solver_config: Mapping[str, Any],
    validity_gates: Mapping[str, Any],
    jump_config: Mapping[str, Any],
    solve_function: SolveFunction = solve_fixed_point,
) -> ProtocolEvent | None:
    """Bisect only the first detected bracket in protocol order."""

    if run.event is None:
        return None
    event = run.event
    pre = event.coarse_pre
    post = event.coarse_post
    refinements: list[ProtocolPoint] = []
    resolution = float(jump_config["refinement_voltage_resolution_V"])
    maximum = int(jump_config["maximum_refinement_solves_per_event"])
    for index in range(maximum):
        if abs(post.voltage_V - pre.voltage_V) <= resolution:
            break
        midpoint = 0.5 * (pre.voltage_V + post.voltage_V)
        point = _solve_point(
            point_id=f"{run.spec.protocol_id}_event_refine_{index + 1:02d}",
            spec=run.spec,
            voltage_V=midpoint,
            point_kind="event_refinement",
            sequence_index=index,
            initial_temperature_K=pre.result.temperature_K,
            initial_state_provenance="last_accepted_pre_switch_equilibrium",
            previous_point_id=pre.point_id,
            operator=operator,
            solver_config=solver_config,
            validity_gates=validity_gates,
            solve_function=solve_function,
        )
        if not point.valid:
            refinements.append(point)
            break
        point.jump_from_previous = jump_diagnostics(
            pre.result,
            point.result,
            ambient_temperature_K=operator.ambient_temperature_K,
            jump_config=jump_config,
        )
        refinements.append(point)
        if bool(point.jump_from_previous["jump_candidate"]):
            post = point
        else:
            pre = point
    resolved_width = bool(
        pre.valid and post.valid and abs(post.voltage_V - pre.voltage_V) <= resolution
    )
    confirmed_post = post
    if resolved_width and len(refinements) < maximum:
        confirmation = _solve_point(
            point_id=f"{run.spec.protocol_id}_event_reachability_confirmation",
            spec=run.spec,
            voltage_V=post.voltage_V,
            point_kind="event_reachability_confirmation",
            sequence_index=len(refinements),
            initial_temperature_K=pre.result.temperature_K,
            initial_state_provenance="final_refined_pre_switch_equilibrium",
            previous_point_id=pre.point_id,
            operator=operator,
            solver_config=solver_config,
            validity_gates=validity_gates,
            solve_function=solve_function,
        )
        if confirmation.valid:
            confirmation.jump_from_previous = jump_diagnostics(
                pre.result,
                confirmation.result,
                ambient_temperature_K=operator.ambient_temperature_K,
                jump_config=jump_config,
            )
        refinements.append(confirmation)
        if confirmation.valid and bool(confirmation.jump_from_previous["jump_candidate"]):
            confirmed_post = confirmation
        else:
            resolved_width = False
    resolved = bool(resolved_width)
    run.event = ProtocolEvent(
        event_id=event.event_id,
        protocol_id=event.protocol_id,
        coarse_pre=event.coarse_pre,
        coarse_post=event.coarse_post,
        refined_pre=pre,
        refined_post=confirmed_post,
        refinement_points=refinements,
        refinement_solve_count=len(refinements),
        resolved=resolved,
    )
    return run.event


def run_half_step_event_window(
    *,
    run: ProtocolRun,
    operator: M1SelfConsistentIMTProjection,
    solver_config: Mapping[str, Any],
    validity_gates: Mapping[str, Any],
    jump_config: Mapping[str, Any],
    sensitivity_config: Mapping[str, Any],
    solve_function: SolveFunction = solve_fixed_point,
) -> tuple[ProtocolPoint | None, ProtocolPoint | None]:
    """Repeat the local protocol window at half step without restarting roots."""

    if run.event is None or not run.event.resolved:
        return None, None
    pre_index = run.event.coarse_pre.sequence_index
    post_index = run.event.coarse_post.sequence_index
    before = int(sensitivity_config["coarse_points_before_event"])
    after = int(sensitivity_config["coarse_points_after_event"])
    start_index = max(0, pre_index - before)
    end_index = min(len(run.coarse_points) - 1, post_index + after)
    anchor = run.coarse_points[start_index]
    end_voltage = run.coarse_points[end_index].voltage_V
    signed_step = math.copysign(
        float(sensitivity_config["half_voltage_step_abs_V"]),
        run.spec.voltage_step_V,
    )
    count = int(round((end_voltage - anchor.voltage_V) / signed_step))
    voltages = anchor.voltage_V + signed_step * np.arange(count + 1)
    voltages[-1] = end_voltage

    anchor_copy = ProtocolPoint(
        point_id=f"{run.spec.protocol_id}_half_anchor",
        protocol_id=run.spec.protocol_id,
        context_id=run.spec.context_id,
        branch_label=run.spec.branch_label,
        branch_value=run.spec.branch_value,
        voltage_V=anchor.voltage_V,
        point_kind="half_step_anchor_reused",
        sequence_index=0,
        initial_state_provenance="accepted_coarse_window_anchor_reused_without_solve",
        previous_point_id=anchor.point_id,
        result=anchor.result,
        valid=anchor.valid,
        accepted=anchor.accepted,
    )
    points = [anchor_copy]
    previous = anchor_copy
    first_pair: tuple[ProtocolPoint, ProtocolPoint] | None = None
    for index, voltage in enumerate(voltages[1:], start=1):
        point = _solve_point(
            point_id=f"{run.spec.protocol_id}_half_{index:03d}",
            spec=run.spec,
            voltage_V=float(voltage),
            point_kind="half_step_continuation",
            sequence_index=index,
            initial_temperature_K=previous.result.temperature_K,
            initial_state_provenance="immediately_preceding_accepted_half_step_equilibrium",
            previous_point_id=previous.point_id,
            operator=operator,
            solver_config=solver_config,
            validity_gates=validity_gates,
            solve_function=solve_function,
        )
        if point.valid:
            point.jump_from_previous = jump_diagnostics(
                previous.result,
                point.result,
                ambient_temperature_K=operator.ambient_temperature_K,
                jump_config=jump_config,
            )
        points.append(point)
        if not point.valid:
            break
        if first_pair is None and bool(point.jump_from_previous["jump_candidate"]):
            first_pair = (previous, point)
        previous = point
    run.half_step_points = points
    if first_pair is None:
        return None, None
    run.half_step_event_pre, run.half_step_event_post = first_pair
    return first_pair


def refine_half_step_event(
    *,
    run: ProtocolRun,
    operator: M1SelfConsistentIMTProjection,
    solver_config: Mapping[str, Any],
    validity_gates: Mapping[str, Any],
    jump_config: Mapping[str, Any],
    maximum_solves: int = 2,
    solve_function: SolveFunction = solve_fixed_point,
) -> tuple[ProtocolPoint | None, ProtocolPoint | None, list[ProtocolPoint]]:
    """Refine the reproduced half-step event with its preallocated two solves."""

    pre = run.half_step_event_pre
    post = run.half_step_event_post
    if pre is None or post is None:
        return None, None, []
    refinements: list[ProtocolPoint] = []
    resolution = float(jump_config["refinement_voltage_resolution_V"])
    for index in range(int(maximum_solves)):
        if abs(post.voltage_V - pre.voltage_V) <= resolution:
            break
        midpoint = 0.5 * (pre.voltage_V + post.voltage_V)
        point = _solve_point(
            point_id=f"{run.spec.protocol_id}_half_refine_{index + 1:02d}",
            spec=run.spec,
            voltage_V=midpoint,
            point_kind="half_step_event_refinement",
            sequence_index=index,
            initial_temperature_K=pre.result.temperature_K,
            initial_state_provenance="half_step_last_pre_switch_equilibrium",
            previous_point_id=pre.point_id,
            operator=operator,
            solver_config=solver_config,
            validity_gates=validity_gates,
            solve_function=solve_function,
        )
        if point.valid:
            point.jump_from_previous = jump_diagnostics(
                pre.result,
                point.result,
                ambient_temperature_K=operator.ambient_temperature_K,
                jump_config=jump_config,
            )
        refinements.append(point)
        if not point.valid:
            break
        if bool(point.jump_from_previous["jump_candidate"]):
            post = point
        else:
            pre = point
    run.half_step_points.extend(refinements)
    run.half_step_event_pre, run.half_step_event_post = pre, post
    return pre, post, refinements


def thermal_dynamic_rhs(
    operator: M1SelfConsistentIMTProjection,
    temperature_flat_K: Tensor,
    *,
    voltage_V: float,
    branch_value: float,
    sink_amplitude: float,
    cell_thermal_capacity_J_K: float,
) -> Tensor:
    """Return the semi-discrete thermal dynamics after quasi-static phi elimination."""

    if not math.isclose(operator.joule_feedback_multiplier, 1.0, rel_tol=0.0, abs_tol=0.0):
        raise ValueError("physical stability requires full Joule feedback lambda_J=1")
    capacity = float(cell_thermal_capacity_J_K)
    if not math.isfinite(capacity) or capacity <= 0.0:
        raise ValueError("cell thermal capacity must be finite and positive")
    temperature = temperature_flat_K.reshape(operator.ny, operator.nx)
    electrical = operator.electrical(temperature, voltage_V, branch_value)
    residual = operator.thermal_residual(
        temperature,
        electrical["total_joule_cell_W"],
        sink_amplitude,
    )
    return -residual.reshape(-1) / capacity


def classify_stability_margin(
    margin: float,
    *,
    stable_margin_max: float = -1.0e-6,
    unstable_margin_min: float = 1.0e-6,
) -> str:
    if not math.isfinite(float(margin)):
        return "indeterminate"
    if float(margin) <= float(stable_margin_max):
        return "stable"
    if float(margin) >= float(unstable_margin_min):
        return "unstable"
    return "indeterminate"


def evaluate_physical_stability(
    *,
    operator: M1SelfConsistentIMTProjection,
    point: ProtocolPoint,
    sink_amplitude: float,
    cell_thermal_capacity_J_K: float,
    stability_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Form and diagonalize the full non-symmetric thermal-dynamics Jacobian."""

    flat = point.result.temperature_K.detach().clone().reshape(-1).to(dtype=torch.float64)

    def rhs_with_sink(value: Tensor) -> Tensor:
        return thermal_dynamic_rhs(
            operator,
            value,
            voltage_V=point.voltage_V,
            branch_value=point.branch_value,
            sink_amplitude=sink_amplitude,
            cell_thermal_capacity_J_K=cell_thermal_capacity_J_K,
        )

    with torch.enable_grad():
        flat.requires_grad_(True)
        try:
            jacobian = torch.autograd.functional.jacobian(
                rhs_with_sink,
                flat,
                create_graph=False,
                strict=False,
                vectorize=True,
            )
        except RuntimeError:
            jacobian = torch.autograd.functional.jacobian(
                rhs_with_sink,
                flat,
                create_graph=False,
                strict=False,
                vectorize=False,
            )
    finite_jacobian = bool(torch.isfinite(jacobian).all())
    if finite_jacobian:
        eigenvalues = torch.linalg.eigvals(jacobian).detach().cpu().numpy()
        maximum_real = float(np.max(np.real(eigenvalues)))
        spectral_radius = float(np.max(np.abs(eigenvalues)))
        margin = maximum_real / max(spectral_radius, 1.0e-30)
        finite = bool(np.isfinite(eigenvalues).all() and math.isfinite(margin))
    else:
        eigenvalues = np.full(operator.cell_count, np.nan + 0.0j)
        maximum_real = math.nan
        spectral_radius = math.nan
        margin = math.nan
        finite = False
    classification = classify_stability_margin(
        margin,
        stable_margin_max=float(stability_config["stable_margin_max"]),
        unstable_margin_min=float(stability_config["unstable_margin_min"]),
    )
    return {
        "eigenvalue_count": int(eigenvalues.size),
        "maximum_real_eigenvalue_per_s": maximum_real,
        "spectral_radius_per_s": spectral_radius,
        "relative_stability_margin": margin,
        "stability_class": classification,
        "finite": finite,
        "jacobian_frobenius_norm_per_s": float(torch.linalg.matrix_norm(jacobian))
        if finite_jacobian
        else math.nan,
        "positive_real_eigenvalue_count": int(np.sum(np.real(eigenvalues) > 0.0))
        if finite
        else 0,
    }


def _temperature_sha256(temperature_K: Tensor) -> str:
    array = np.ascontiguousarray(_numpy(temperature_K), dtype=np.float64)
    return hashlib.sha256(array.tobytes()).hexdigest()


def _hotspot_coordinates(
    temperature_K: Tensor, operator: M1SelfConsistentIMTProjection
) -> tuple[float, float]:
    flat_index = int(torch.argmax(temperature_K).detach())
    iy, ix = np.unravel_index(flat_index, (operator.ny, operator.nx))
    return float(operator.x_centers_m[ix]), float(operator.y_centers_m[iy])


def point_to_row(
    point: ProtocolPoint,
    *,
    operator: M1SelfConsistentIMTProjection,
    point_index_in_npz: int,
    stability: Mapping[str, Any] | None,
    role: str,
) -> dict[str, Any]:
    hotspot_x, hotspot_y = _hotspot_coordinates(point.result.temperature_K, operator)
    metrics = point.result.metrics
    stability_class = str(stability["stability_class"]) if stability else "not_evaluated"
    return {
        "point_id": point.point_id,
        "protocol_id": point.protocol_id,
        "context_id": point.context_id,
        "branch_label": point.branch_label,
        "branch_value": point.branch_value,
        "device_voltage_V": point.voltage_V,
        "point_kind": point.point_kind,
        "role": role,
        "sequence_index": point.sequence_index,
        "count_in_main_ramp": point.point_kind == "coarse",
        "initial_state_provenance": point.initial_state_provenance,
        "previous_point_id": point.previous_point_id,
        "temperature_sha256": _temperature_sha256(point.result.temperature_K),
        "valid": point.valid,
        "accepted": point.accepted,
        "converged": bool(metrics["converged"]),
        "finite": bool(metrics["finite"]),
        "iterations": int(metrics["iterations"]),
        "scaled_nonlinear_residual": float(metrics["scaled_nonlinear_residual"]),
        "current_imbalance": float(metrics["current_imbalance"]),
        "terminal_electrical_heat_ledger_error": float(
            metrics["terminal_electrical_heat_ledger_error"]
        ),
        "electrical_heat_sink_ledger_error": float(
            metrics["state_consistent_feedback_heat_sink_ledger_error"]
        ),
        "terminal_current_A": float(metrics["terminal_current_A"]),
        "ground_current_A": float(metrics["ground_current_A"]),
        "Tmean_K": float(metrics["Tmean_K"]),
        "Tmax_K": float(metrics["Tmax_K"]),
        "mean_effective_state": float(metrics["mean_effective_state_coordinate"]),
        "transition_fraction": float(metrics["transition_fraction"]),
        "hotspot_x_m": hotspot_x,
        "hotspot_y_m": hotspot_y,
        "jump_mean_state_change": point.jump_from_previous.get("mean_state_change"),
        "jump_terminal_current_relative": point.jump_from_previous.get(
            "terminal_current_relative_jump"
        ),
        "jump_temperature_rise_relative": point.jump_from_previous.get(
            "temperature_rise_field_relative_jump"
        ),
        "jump_candidate": point.jump_from_previous.get("jump_candidate", False),
        "stability_class": stability_class,
        "stability_evaluated": stability is not None,
        "manuscript_eligible": bool(stability_class == "stable" and point.valid),
        "npz_record_index": point_index_in_npz,
    }


def _unique_points(points: Sequence[ProtocolPoint]) -> list[ProtocolPoint]:
    result: list[ProtocolPoint] = []
    seen: set[str] = set()
    for point in points:
        if point.point_id not in seen:
            seen.add(point.point_id)
            result.append(point)
    return result


def all_run_points(run: ProtocolRun) -> list[ProtocolPoint]:
    points = list(run.preparation_points) + list(run.coarse_points)
    if run.event is not None:
        points.extend(run.event.refinement_points)
        points.extend([run.event.refined_pre, run.event.refined_post])
    points.extend(run.half_step_points)
    if run.half_step_event_pre is not None:
        points.append(run.half_step_event_pre)
    if run.half_step_event_post is not None:
        points.append(run.half_step_event_post)
    return _unique_points(points)


def stability_candidates(
    runs: Sequence[ProtocolRun],
    *,
    interior_coarse_indices: Sequence[int] = (8, 24),
    state_equivalence_temperature_rise_relative_max: float = 1.0e-8,
) -> tuple[
    list[ProtocolPoint],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    candidates: list[ProtocolPoint] = []
    roles: dict[str, list[str]] = {}
    aliases: dict[str, list[str]] = {}
    representatives_by_location: dict[
        tuple[str, str, float], list[ProtocolPoint]
    ] = {}

    def add(point: ProtocolPoint | None, role: str) -> None:
        if point is None:
            return
        location_key = (
            point.context_id,
            point.branch_label,
            round(point.voltage_V, 12),
        )
        representative = next(
            (
                existing
                for existing in representatives_by_location.get(location_key, [])
                if _temperature_rise_relative_difference(
                    existing.result.temperature_K,
                    point.result.temperature_K,
                    325.0,
                )
                <= state_equivalence_temperature_rise_relative_max
            ),
            None,
        )
        if representative is None:
            representatives_by_location.setdefault(location_key, []).append(point)
            candidates.append(point)
            representative = point
        roles.setdefault(representative.point_id, [])
        if role not in roles[representative.point_id]:
            roles[representative.point_id].append(role)
        aliases.setdefault(representative.point_id, [])
        if point.point_id not in aliases[representative.point_id]:
            aliases[representative.point_id].append(point.point_id)

    for run in runs:
        if run.coarse_points:
            add(run.coarse_points[0], "start_endpoint")
            add(run.coarse_points[-1], "end_endpoint")
            # Two fixed interior indices close the stable same-voltage-pair
            # evidence without adapting the selection to observed errors.
            if len(interior_coarse_indices) != 2:
                raise ValueError("stability selection requires exactly two fixed interior indices")
            for index, role in zip(
                interior_coarse_indices,
                ("protocol_quartile_1_interior", "protocol_quartile_3_interior"),
            ):
                if not 0 < int(index) < len(run.coarse_points) - 1:
                    raise ValueError("fixed stability index is not an interior coarse point")
                add(run.coarse_points[int(index)], role)
        if run.event is not None:
            add(run.event.refined_pre, "last_pre_switch")
            add(run.event.refined_post, "first_post_switch")
        add(run.half_step_event_pre, "half_step_pre_switch")
        add(run.half_step_event_post, "half_step_post_switch")
    return candidates, roles, aliases


def load_device_thermal_capacitance(
    config: Mapping[str, Any], repository_root: Path, *, cell_count: int
) -> tuple[float, float]:
    source = load_yaml(repository_root / str(config["reference"]["source_contract"]))
    section = source["source_author_fitted_lumped_quantities"]
    device = float(section["lumped_thermal_capacitance_J_K"]["value"])
    expected = float(config["source_role"]["expected_device_thermal_capacitance_J_K"])
    if not math.isclose(device, expected, rel_tol=0.0, abs_tol=0.0):
        raise ValueError("Qiu device thermal capacitance drifted")
    if cell_count != int(config["reference"]["production_grid"]["nx"]) * int(
        config["reference"]["production_grid"]["ny"]
    ):
        raise ValueError("thermal mass left the production grid")
    return device, device / cell_count


def evaluate_stability_budget(
    *,
    runs: Sequence[ProtocolRun],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    config: Mapping[str, Any],
    repository_root: Path,
    existing_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, list[str]],
    dict[str, int],
]:
    candidates, roles, aliases = stability_candidates(
        runs,
        interior_coarse_indices=config["stability"]["fixed_interior_coarse_indices"],
        state_equivalence_temperature_rise_relative_max=float(
            config["stability"]["state_equivalence_temperature_rise_relative_max"]
        ),
    )
    maximum = int(config["stability"]["maximum_states"])
    if len(candidates) > maximum:
        raise RuntimeError("required physical-stability states exceed the frozen 24-state budget")
    device_capacity, cell_capacity = load_device_thermal_capacitance(
        config, repository_root, cell_count=next(iter(operators.values())).cell_count
    )
    run_by_id = {run.spec.protocol_id: run for run in runs}
    rows: list[dict[str, Any]] = []
    metrics_by_point: dict[str, dict[str, Any]] = {}
    existing_by_state: dict[tuple[str, str, float, str], Mapping[str, Any]] = {}
    for row in existing_rows:
        key = (
            str(row["context_id"]),
            str(row["branch_label"]),
            round(float(row["device_voltage_V"]), 12),
            str(row["temperature_sha256"]),
        )
        existing_by_state.setdefault(key, row)
    reused_count = 0
    new_count = 0
    for point in candidates:
        run = run_by_id[point.protocol_id]
        temperature_hash = _temperature_sha256(point.result.temperature_K)
        key = (
            point.context_id,
            point.branch_label,
            round(point.voltage_V, 12),
            temperature_hash,
        )
        prior = existing_by_state.get(key)
        if prior is not None:
            metrics = {
                "eigenvalue_count": int(prior["eigenvalue_count"]),
                "maximum_real_eigenvalue_per_s": float(
                    prior["maximum_real_eigenvalue_per_s"]
                ),
                "spectral_radius_per_s": float(prior["spectral_radius_per_s"]),
                "relative_stability_margin": float(
                    prior["relative_stability_margin"]
                ),
                "stability_class": str(prior["stability_class"]),
                "positive_real_eigenvalue_count": int(
                    prior["positive_real_eigenvalue_count"]
                ),
                "finite": str(prior["finite"]).lower() == "true",
            }
            spectrum_origin = (
                "aggregation_repair_fixed_interior_probe"
                if any("interior" in role for role in roles[point.point_id])
                else "reused_from_initial_formal_execution"
            )
            reused_count += 1
        else:
            metrics = evaluate_physical_stability(
                operator=operators[point.context_id],
                point=point,
                sink_amplitude=run.spec.sink_amplitude,
                cell_thermal_capacity_J_K=cell_capacity,
                stability_config=config["stability"],
            )
            spectrum_origin = "aggregation_repair_fixed_interior_probe"
            new_count += 1
        for alias_id in aliases[point.point_id]:
            metrics_by_point[alias_id] = metrics
        rows.append(
            {
                "state_id": point.point_id,
                "alias_point_ids": "|".join(aliases[point.point_id]),
                "protocol_id": point.protocol_id,
                "context_id": point.context_id,
                "branch_label": point.branch_label,
                "device_voltage_V": point.voltage_V,
                "roles": "|".join(roles.get(point.point_id, [])),
                "temperature_sha256": temperature_hash,
                "device_thermal_capacitance_J_K": device_capacity,
                "cell_thermal_capacitance_J_K": cell_capacity,
                "eigenvalue_count": metrics["eigenvalue_count"],
                "maximum_real_eigenvalue_per_s": metrics[
                    "maximum_real_eigenvalue_per_s"
                ],
                "spectral_radius_per_s": metrics["spectral_radius_per_s"],
                "relative_stability_margin": metrics["relative_stability_margin"],
                "stability_class": metrics["stability_class"],
                "positive_real_eigenvalue_count": metrics[
                    "positive_real_eigenvalue_count"
                ],
                "finite": metrics["finite"],
                "manuscript_eligible": bool(
                    metrics["stability_class"] == "stable" and point.valid
                ),
                "thermal_mass_interpretation": config["source_role"]["interpretation"],
                "spectrum_origin": spectrum_origin,
            }
        )
    return rows, metrics_by_point, roles, {
        "unique_state_count": len(candidates),
        "existing_spectrum_row_count": len(existing_rows),
        "reused_unique_state_count": reused_count,
        "new_spectrum_evaluation_count": new_count,
        "cumulative_spectrum_evaluation_count": len(existing_rows) + new_count,
    }


def event_step_sensitivity(
    *,
    run: ProtocolRun,
    stability_by_point: Mapping[str, Mapping[str, Any]],
    sensitivity_config: Mapping[str, Any],
) -> dict[str, Any]:
    if run.event is None:
        return {
            "event_id": "",
            "protocol_id": run.spec.protocol_id,
            "executed": False,
            "pass": None,
            "reason": "not_applicable_no_detected_event",
        }
    if not run.event.resolved:
        return {
            "event_id": run.event.event_id,
            "protocol_id": run.spec.protocol_id,
            "executed": True,
            "pass": False,
            "reason": "detected_primary_event_not_resolved",
        }
    primary = run.event
    half_pre = run.half_step_event_pre
    half_post = run.half_step_event_post
    if half_pre is None or half_post is None:
        return {
            "event_id": primary.event_id,
            "protocol_id": run.spec.protocol_id,
            "executed": True,
            "pass": False,
            "reason": "half_step_event_not_reproduced",
        }
    half_lower = min(half_pre.voltage_V, half_post.voltage_V)
    half_upper = max(half_pre.voltage_V, half_post.voltage_V)
    half_mid = 0.5 * (half_lower + half_upper)
    primary_mid = primary.switching_voltage_estimate_V
    switch_difference = abs(primary_mid - half_mid)
    coarse_by_voltage = {round(p.voltage_V, 10): p for p in run.coarse_points}
    aligned: list[dict[str, Any]] = []
    for point in run.half_step_points:
        coarse = coarse_by_voltage.get(round(point.voltage_V, 10))
        if coarse is None:
            continue
        distance = min(abs(point.voltage_V - primary_mid), abs(point.voltage_V - half_mid))
        if distance + 1.0e-12 < float(sensitivity_config["off_event_distance_min_V"]):
            continue
        aligned.append(
            {
                "voltage_V": point.voltage_V,
                "side": "pre"
                if (point.voltage_V - primary_mid) * run.spec.voltage_step_V < 0.0
                else "post",
                "temperature_difference": _temperature_rise_relative_difference(
                    coarse.result.temperature_K,
                    point.result.temperature_K,
                    325.0,
                ),
                "current_difference": _relative_scalar_jump(
                    coarse.result.metrics["terminal_current_A"],
                    point.result.metrics["terminal_current_A"],
                ),
            }
        )
    worst_temperature = max(
        (float(item["temperature_difference"]) for item in aligned), default=math.inf
    )
    worst_current = max(
        (float(item["current_difference"]) for item in aligned), default=math.inf
    )
    sides = {str(item["side"]) for item in aligned}
    primary_classes = [
        str(stability_by_point.get(primary.refined_pre.point_id, {}).get("stability_class", "not_evaluated")),
        str(stability_by_point.get(primary.refined_post.point_id, {}).get("stability_class", "not_evaluated")),
    ]
    half_classes = [
        str(stability_by_point.get(half_pre.point_id, {}).get("stability_class", "not_evaluated")),
        str(stability_by_point.get(half_post.point_id, {}).get("stability_class", "not_evaluated")),
    ]
    reversals = sum(
        1
        for left, right in zip(primary_classes, half_classes)
        if {left, right} == {"stable", "unstable"}
    )
    indeterminate = sum(
        value in {"indeterminate", "not_evaluated"}
        for value in primary_classes + half_classes
    )
    passed = bool(
        abs(half_post.voltage_V - half_pre.voltage_V)
        <= float(sensitivity_config.get("refinement_voltage_resolution_V", 0.005))
        and switch_difference
        <= float(sensitivity_config["switching_voltage_difference_max_V"])
        and {"pre", "post"}.issubset(sides)
        and worst_temperature
        <= float(sensitivity_config["temperature_rise_relative_difference_max"])
        and worst_current
        <= float(sensitivity_config["terminal_current_relative_difference_max"])
        and reversals == 0
        and indeterminate == 0
    )
    return {
        "event_id": primary.event_id,
        "protocol_id": run.spec.protocol_id,
        "executed": True,
        "primary_interval_lower_V": primary.voltage_lower_V,
        "primary_interval_upper_V": primary.voltage_upper_V,
        "primary_switching_voltage_estimate_V": primary_mid,
        "half_step_interval_lower_V": half_lower,
        "half_step_interval_upper_V": half_upper,
        "half_step_switching_voltage_estimate_V": half_mid,
        "switching_voltage_difference_V": switch_difference,
        "aligned_off_event_comparison_count": len(aligned),
        "aligned_pre_side_count": sum(item["side"] == "pre" for item in aligned),
        "aligned_post_side_count": sum(item["side"] == "post" for item in aligned),
        "worst_off_event_temperature_rise_relative_difference": worst_temperature,
        "worst_off_event_terminal_current_relative_difference": worst_current,
        "primary_pre_stability": primary_classes[0],
        "primary_post_stability": primary_classes[1],
        "half_step_pre_stability": half_classes[0],
        "half_step_post_stability": half_classes[1],
        "stability_classification_reversal_count": reversals,
        "stability_indeterminate_count": indeterminate,
        "half_step_continuation_solve_count": sum(
            point.point_kind == "half_step_continuation"
            for point in run.half_step_points
        ),
        "pass": passed,
        "reason": "passed" if passed else "one_or_more_frozen_step_gates_failed",
    }


def _event_row(run: ProtocolRun) -> dict[str, Any]:
    if run.event is None:
        return {
            "event_id": "",
            "protocol_id": run.spec.protocol_id,
            "context_id": run.spec.context_id,
            "branch_label": run.spec.branch_label,
            "detected": False,
            "resolved": False,
            "reason": "no_coarse_jump_candidate",
        }
    event = run.event
    final_jump = jump_diagnostics(
        event.refined_pre.result,
        event.refined_post.result,
        ambient_temperature_K=325.0,
        jump_config={
            "mean_state_change_min": 0.4,
            "terminal_current_relative_jump_min": 0.5,
            "temperature_rise_field_relative_jump_min": 0.25,
        },
    )
    trigger = event.coarse_post.jump_from_previous
    return {
        "event_id": event.event_id,
        "protocol_id": run.spec.protocol_id,
        "context_id": run.spec.context_id,
        "branch_label": run.spec.branch_label,
        "detected": True,
        "resolved": event.resolved,
        "coarse_pre_point_id": event.coarse_pre.point_id,
        "coarse_post_point_id": event.coarse_post.point_id,
        "coarse_pre_voltage_V": event.coarse_pre.voltage_V,
        "coarse_post_voltage_V": event.coarse_post.voltage_V,
        "coarse_mean_state_change": trigger.get("mean_state_change"),
        "coarse_terminal_current_relative_jump": trigger.get(
            "terminal_current_relative_jump"
        ),
        "coarse_temperature_rise_field_relative_jump": trigger.get(
            "temperature_rise_field_relative_jump"
        ),
        "coarse_mean_state_trigger": trigger.get("mean_state_jump"),
        "coarse_current_trigger": trigger.get("current_jump"),
        "coarse_temperature_trigger": trigger.get("temperature_jump"),
        "refinement_solve_count": event.refinement_solve_count,
        "refined_pre_point_id": event.refined_pre.point_id,
        "refined_post_point_id": event.refined_post.point_id,
        "refined_pre_voltage_V": event.refined_pre.voltage_V,
        "refined_post_voltage_V": event.refined_post.voltage_V,
        "interval_lower_V": event.voltage_lower_V,
        "interval_upper_V": event.voltage_upper_V,
        "switching_voltage_estimate_V": event.switching_voltage_estimate_V,
        "interval_width_V": event.voltage_upper_V - event.voltage_lower_V,
        "refined_mean_state_jump": final_jump["mean_state_change"],
        "refined_terminal_current_relative_jump": final_jump[
            "terminal_current_relative_jump"
        ],
        "refined_temperature_rise_field_relative_jump": final_jump[
            "temperature_rise_field_relative_jump"
        ],
        "reason": "resolved" if event.resolved else "refinement_failed",
    }


def _manifest_row(run: ProtocolRun, npz_path: Path) -> dict[str, Any]:
    valid_main = sum(point.valid for point in run.coarse_points)
    attempted = len(run.coarse_points)
    preparation = next(
        (point for point in run.preparation_points if point.point_kind == "endpoint_preparation"),
        None,
    )
    return {
        "protocol_id": run.spec.protocol_id,
        "context_id": run.spec.context_id,
        "context_label": run.spec.context_label,
        "branch_label": run.spec.branch_label,
        "branch_value": run.spec.branch_value,
        "contact_overlap_nm": run.spec.contact_overlap_nm,
        "sink_amplitude": run.spec.sink_amplitude,
        "start_voltage_V": run.spec.start_voltage_V,
        "end_voltage_V": run.spec.end_voltage_V,
        "voltage_step_V": run.spec.voltage_step_V,
        "direction": run.spec.direction,
        "start_temperature_K": run.spec.start_temperature_K,
        "endpoint_preparation_contract": run.spec.endpoint_preparation,
        "fallback_used": preparation is not None,
        "fallback_voltage_V": preparation.voltage_V if preparation else None,
        "fallback_valid": preparation.valid if preparation else None,
        "previous_state_provenance_contract": "immediately_preceding_accepted_protocol_equilibrium",
        "expected_main_point_count": run.expected_coarse_points,
        "attempted_main_point_count": attempted,
        "valid_main_point_count": valid_main,
        "valid_main_fraction": valid_main / run.expected_coarse_points,
        "endpoint_pass": run.endpoint_pass,
        "completed": run.completed,
        "event_detected": run.event is not None,
        "event_resolved": bool(run.event and run.event.resolved),
        "failure_reason": run.failure_reason,
        "field_npz_path": npz_path.as_posix(),
        "root_identifier_present": False,
    }


def save_protocol_npz(
    path: Path,
    *,
    run: ProtocolRun,
    operator: M1SelfConsistentIMTProjection,
    stability_by_point: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    points = all_run_points(run)
    arrays: dict[str, Any] = {
        "protocol_id": np.asarray(run.spec.protocol_id),
        "context_id": np.asarray(run.spec.context_id),
        "branch_label": np.asarray(run.spec.branch_label),
        "branch_value": np.asarray(run.spec.branch_value),
        "direction": np.asarray(run.spec.direction),
        "start_voltage_V": np.asarray(run.spec.start_voltage_V),
        "end_voltage_V": np.asarray(run.spec.end_voltage_V),
        "voltage_step_V": np.asarray(run.spec.voltage_step_V),
        "contact_overlap_nm": np.asarray(run.spec.contact_overlap_nm),
        "sink_amplitude": np.asarray(run.spec.sink_amplitude),
        "previous_state_provenance_contract": np.asarray(
            "immediately_preceding_accepted_protocol_equilibrium"
        ),
        "x_m": _numpy(operator.x_centers_m),
        "y_m": _numpy(operator.y_centers_m),
        "point_id": np.asarray([point.point_id for point in points]),
        "point_kind": np.asarray([point.point_kind for point in points]),
        "point_voltage_V": np.asarray([point.voltage_V for point in points]),
        "point_sequence_index": np.asarray([point.sequence_index for point in points]),
        "point_valid": np.asarray([point.valid for point in points]),
        "point_accepted": np.asarray([point.accepted for point in points]),
        "point_previous_id": np.asarray([point.previous_point_id for point in points]),
        "point_initial_state_provenance": np.asarray(
            [point.initial_state_provenance for point in points]
        ),
        "point_temperature_sha256": np.asarray(
            [_temperature_sha256(point.result.temperature_K) for point in points]
        ),
        "point_stability_class": np.asarray(
            [
                str(stability_by_point.get(point.point_id, {}).get("stability_class", "not_evaluated"))
                for point in points
            ]
        ),
        "point_manuscript_eligible": np.asarray(
            [
                stability_by_point.get(point.point_id, {}).get("stability_class") == "stable"
                and point.valid
                for point in points
            ]
        ),
    }
    field_names = (
        "potential_V",
        "conductivity_S_m",
        "effective_conductive_state_coordinate",
        "electrical_x_face_current_A",
        "electrical_y_face_current_A",
        "source_face_current_A",
        "ground_face_current_A",
        "thermal_x_face_power_W",
        "thermal_y_face_power_W",
        "internal_joule_cell_W",
        "contact_joule_cell_W",
        "total_joule_cell_W",
        "feedback_joule_cell_W",
        "vertical_sink_cell_W",
    )
    arrays["temperature_K"] = np.stack([_numpy(point.result.temperature_K) for point in points])
    for name in field_names:
        arrays[name] = np.stack([_numpy(point.result.fields[name]) for point in points])
    scalar_metrics = (
        "iterations",
        "scaled_nonlinear_residual",
        "current_imbalance",
        "terminal_electrical_heat_ledger_error",
        "state_consistent_feedback_heat_sink_ledger_error",
        "terminal_current_A",
        "ground_current_A",
        "Tmean_K",
        "Tmax_K",
        "mean_effective_state_coordinate",
        "transition_fraction",
    )
    for name in scalar_metrics:
        arrays[f"metric_{name}"] = np.asarray(
            [point.result.metrics[name] for point in points]
        )
    global_fields = (
        "internal_joule_W",
        "contact_joule_W",
        "total_electrical_heat_W",
        "terminal_power_W",
        "vertical_sink_W",
        "feedback_joule_W",
    )
    for name in global_fields:
        arrays[name] = np.asarray([float(point.result.fields[name]) for point in points])
    np.savez_compressed(path, **arrays)
    return {point.point_id: index for index, point in enumerate(points)}


def _common_voltage_pairs(
    heating: ProtocolRun, cooling: ProtocolRun
) -> list[tuple[ProtocolPoint, ProtocolPoint]]:
    cooling_by_voltage = {round(point.voltage_V, 10): point for point in cooling.coarse_points}
    pairs: list[tuple[ProtocolPoint, ProtocolPoint]] = []
    for point in heating.coarse_points:
        other = cooling_by_voltage.get(round(point.voltage_V, 10))
        if other is not None and point.valid and other.valid:
            pairs.append((point, other))
    return pairs


def _context_gate_summary(
    *,
    context_id: str,
    heating: ProtocolRun,
    cooling: ProtocolRun,
    stability_by_point: Mapping[str, Mapping[str, Any]],
    sensitivity_by_protocol: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    valid_min = float(config["validity_gates"]["minimum_valid_fraction_per_ramp"])
    ramps_complete = all(
        run.completed
        and sum(point.valid for point in run.coarse_points) / run.expected_coarse_points
        >= valid_min
        for run in (heating, cooling)
    )
    detected_events = [run.event for run in (heating, cooling) if run.event is not None]
    events_resolved = bool(
        detected_events and all(event.resolved for event in detected_events)
    )
    required_points: list[ProtocolPoint] = []
    for run in (heating, cooling):
        required_points.extend([run.coarse_points[0], run.coarse_points[-1]])
        if run.event is not None:
            required_points.extend([run.event.refined_pre, run.event.refined_post])
    required_classes = [
        str(stability_by_point.get(point.point_id, {}).get("stability_class", "not_evaluated"))
        for point in required_points
    ]
    required_stable = bool(required_classes and all(value == "stable" for value in required_classes))
    required_unstable = any(value == "unstable" for value in required_classes)
    required_indeterminate = any(
        value in {"indeterminate", "not_evaluated"} for value in required_classes
    )
    executed_sensitivity = [
        sensitivity_by_protocol.get(run.spec.protocol_id, {})
        for run in (heating, cooling)
        if bool(sensitivity_by_protocol.get(run.spec.protocol_id, {}).get("executed", False))
    ]
    step_pass = bool(
        executed_sensitivity
        and all(bool(row.get("pass", False)) for row in executed_sensitivity)
    )
    if heating.event is not None and cooling.event is not None:
        heating_lower = heating.event.voltage_lower_V  # type: ignore[union-attr]
        cooling_upper = cooling.event.voltage_upper_V  # type: ignore[union-attr]
        conservative_separation = heating_lower - cooling_upper
    else:
        conservative_separation = math.nan
    pairs = _common_voltage_pairs(heating, cooling)
    pair_metrics: list[dict[str, float]] = []
    for up, down in pairs:
        up_stable = (
            stability_by_point.get(up.point_id, {}).get("stability_class") == "stable"
        )
        down_stable = (
            stability_by_point.get(down.point_id, {}).get("stability_class") == "stable"
        )
        pair_metrics.append(
            {
                "voltage_V": up.voltage_V,
                "current_difference": _relative_scalar_jump(
                    up.result.metrics["terminal_current_A"],
                    down.result.metrics["terminal_current_A"],
                ),
                "temperature_difference": _temperature_rise_relative_difference(
                    up.result.temperature_K, down.result.temperature_K, 325.0
                ),
                "both_locally_stable": float(up_stable and down_stable),
            }
        )
    decision = config["decision_gates"]
    stable_distinct_pairs = [
        item
        for item in pair_metrics
        if bool(item["both_locally_stable"])
        and (
            item["current_difference"]
            >= float(decision["bistable_current_relative_difference_min"])
            or item["temperature_difference"]
            >= float(decision["bistable_temperature_rise_relative_difference_min"])
        )
    ]
    if len(stable_distinct_pairs) >= 2:
        stable_voltages = [item["voltage_V"] for item in stable_distinct_pairs]
        bistable_width = max(stable_voltages) - min(stable_voltages)
    else:
        bistable_width = 0.0
    max_current_difference = max(
        (item["current_difference"] for item in stable_distinct_pairs), default=0.0
    )
    max_temperature_difference = max(
        (item["temperature_difference"] for item in stable_distinct_pairs), default=0.0
    )
    phase_separation = bool(
        (
            math.isfinite(conservative_separation)
            and conservative_separation
            >= float(decision["switching_voltage_separation_min_V"])
        )
        or bistable_width >= float(decision["bistable_reachable_width_min_V"])
    )
    branch_difference = bool(
        max_current_difference
        >= float(decision["bistable_current_relative_difference_min"])
        or max_temperature_difference
        >= float(decision["bistable_temperature_rise_relative_difference_min"])
    )
    event_jumps = []
    for run in (heating, cooling):
        if run.event is not None:
            event_jumps.append(
                jump_diagnostics(
                    run.event.refined_pre.result,
                    run.event.refined_post.result,
                    ambient_temperature_K=325.0,
                    jump_config=config["jump_detection"],
                )["mean_state_change"]
            )
    stable_transition = any(
        stability_by_point.get(point.point_id, {}).get("stability_class") == "stable"
        and float(point.result.metrics["transition_fraction"])
        >= float(decision["stable_transition_fraction_min"])
        for point in required_points
    )
    transition_evidence = bool(
        max(event_jumps, default=0.0) >= float(decision["event_mean_state_jump_min"])
        or stable_transition
    )
    qualified = bool(
        ramps_complete
        and events_resolved
        and required_stable
        and step_pass
        and phase_separation
        and branch_difference
        and transition_evidence
    )
    return {
        "context_id": context_id,
        "ramps_complete": ramps_complete,
        "events_resolved": events_resolved,
        "required_state_classes": required_classes,
        "required_states_stable": required_stable,
        "required_state_unstable_present": required_unstable,
        "required_state_indeterminate_present": required_indeterminate,
        "step_sensitivity_pass": step_pass,
        "heating_switch_interval_V": [
            heating.event.voltage_lower_V if heating.event else None,
            heating.event.voltage_upper_V if heating.event else None,
        ],
        "cooling_switch_interval_V": [
            cooling.event.voltage_lower_V if cooling.event else None,
            cooling.event.voltage_upper_V if cooling.event else None,
        ],
        "conservative_switching_voltage_separation_V": conservative_separation,
        "protocol_bistable_reachable_width_V": bistable_width,
        "common_voltage_pair_count": len(pairs),
        "stable_distinct_common_voltage_pair_count": len(stable_distinct_pairs),
        "maximum_bistable_current_relative_difference": max_current_difference,
        "maximum_bistable_temperature_rise_relative_difference": max_temperature_difference,
        "phase_separation_gate": phase_separation,
        "branch_difference_gate": branch_difference,
        "maximum_event_mean_state_jump": max(event_jumps, default=0.0),
        "stable_transition_fraction_gate": stable_transition,
        "transition_evidence_gate": transition_evidence,
        "qualified": qualified,
    }


def aggregate_decision(
    *,
    runs: Sequence[ProtocolRun],
    stability_rows: Sequence[Mapping[str, Any]],
    stability_by_point: Mapping[str, Mapping[str, Any]],
    sensitivity_rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    refinement_solve_count: int,
) -> dict[str, Any]:
    run_by_id = {run.spec.protocol_id: run for run in runs}
    sensitivity_by_protocol = {
        str(row["protocol_id"]): row for row in sensitivity_rows
    }
    contexts: dict[str, Any] = {}
    for context_id in config["contexts"]:
        contexts[str(context_id)] = _context_gate_summary(
            context_id=str(context_id),
            heating=run_by_id[f"{context_id}_heating"],
            cooling=run_by_id[f"{context_id}_cooling"],
            stability_by_point=stability_by_point,
            sensitivity_by_protocol=sensitivity_by_protocol,
            config=config,
        )

    dispositions = config["decision_gates"]["dispositions"]
    cooling_endpoint_failure = any(
        run.spec.branch_label == "cooling" and not run.endpoint_pass for run in runs
    )
    heating_endpoint_failure = any(
        run.spec.branch_label == "heating" and not run.endpoint_pass for run in runs
    )
    ramp_or_event_unresolved = any(
        not run.completed or (run.event is not None and not run.event.resolved)
        for run in runs
    )
    indeterminate = any(
        bool(context["required_state_indeterminate_present"])
        for context in contexts.values()
    )
    unstable = any(
        bool(context["required_state_unstable_present"])
        for context in contexts.values()
    )
    executed_sensitivity = [
        row for row in sensitivity_rows if bool(row.get("executed", False))
    ]
    step_failure = any(not bool(row.get("pass", False)) for row in executed_sensitivity)
    refinement_budget_pass = refinement_solve_count <= int(
        config["budgets"]["maximum_event_refinement_solves"]
    )
    stability_budget_pass = len(stability_rows) <= int(
        config["budgets"]["maximum_stability_states"]
    )

    if cooling_endpoint_failure:
        disposition = str(dispositions["cooling_endpoint"])
        reason = "cooling_high_conductive_endpoint_not_prepared"
    elif heating_endpoint_failure or ramp_or_event_unresolved or not refinement_budget_pass:
        disposition = str(dispositions["unresolved"])
        reason = "endpoint_ramp_or_event_selection_unresolved"
    elif indeterminate or not stability_budget_pass:
        disposition = str(dispositions["unresolved"])
        reason = "required_physical_stability_unclassified_or_budget_exceeded"
    elif unstable:
        disposition = str(dispositions["dynamic"])
        reason = "required_endpoint_or_event_adjacent_equilibrium_is_unstable"
    elif step_failure:
        disposition = str(dispositions["step_dependent"])
        reason = "half_step_protocol_reproducibility_gate_failed"
    elif all(bool(context["qualified"]) for context in contexts.values()):
        disposition = str(dispositions["go"])
        reason = "both_contexts_pass_all_protocol_manifold_gates"
    elif bool(contexts["G0"]["qualified"]) and not bool(contexts["G1"]["qualified"]):
        disposition = str(dispositions["partial"])
        reason = "nominal_context_qualified_but_geometry_sink_context_did_not"
    else:
        disposition = str(dispositions["unresolved"])
        reason = "protocol_selection_did_not_satisfy_the_complete_frozen_gate"

    validity = "valid"
    claim_status = (
        "qualified_supported"
        if disposition in {str(dispositions["go"]), str(dispositions["partial"])}
        else "failed_but_informative"
    )
    return {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "evidence_type": EVIDENCE_TYPE,
        "disposition": disposition,
        "reason": reason,
        "validity": validity,
        "claim_status": claim_status,
        "main_protocol_ramp_count": len(runs),
        "completed_protocol_ramp_count": sum(run.completed for run in runs),
        "main_protocol_point_count": sum(len(run.coarse_points) for run in runs),
        "valid_main_protocol_point_count": sum(
            point.valid for run in runs for point in run.coarse_points
        ),
        "event_count": sum(run.event is not None for run in runs),
        "resolved_event_count": sum(
            bool(run.event and run.event.resolved) for run in runs
        ),
        "event_refinement_solve_count": refinement_solve_count,
        "event_refinement_budget_pass": refinement_budget_pass,
        "physical_stability_state_count": len(stability_rows),
        "physical_stability_budget_pass": stability_budget_pass,
        "stable_state_count": sum(
            str(row["stability_class"]) == "stable" for row in stability_rows
        ),
        "unstable_state_count": sum(
            str(row["stability_class"]) == "unstable" for row in stability_rows
        ),
        "indeterminate_state_count": sum(
            str(row["stability_class"]) == "indeterminate" for row in stability_rows
        ),
        "step_sensitivity_all_pass": not step_failure,
        "step_sensitivity_event_count": len(executed_sensitivity),
        "contexts": contexts,
        "routing_precedence": [
            "cooling_endpoint",
            "ramp_or_event_unresolved",
            "stability_indeterminate_or_budget",
            "dynamic_instability",
            "step_sensitivity",
            "GO",
            "PARTIAL_GO",
            "NO_GO_unresolved",
        ],
        "neural_training_executed": False,
        "root_identifier_used": False,
        "root_averaging_used": False,
        "claim_boundary": config["claim_boundary"],
    }


def build_surrogate_eligibility(
    *,
    runs: Sequence[ProtocolRun],
    decision: Mapping[str, Any],
    stability_by_point: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    eligible_dispositions = {
        str(value) for value in config["surrogate_eligibility"]["execute_only_after"]
    }
    executed = str(decision["disposition"]) in eligible_dispositions
    all_points = [point for run in runs for point in all_run_points(run)]
    stable_points: list[ProtocolPoint] = []
    for point in all_points:
        if not (
            stability_by_point.get(point.point_id, {}).get("stability_class") == "stable"
            and point.valid
        ):
            continue
        equivalent = any(
            existing.context_id == point.context_id
            and existing.branch_label == point.branch_label
            and math.isclose(existing.voltage_V, point.voltage_V, rel_tol=0.0, abs_tol=1.0e-12)
            and _temperature_rise_relative_difference(
                existing.result.temperature_K, point.result.temperature_K, 325.0
            )
            <= float(
                config["stability"][
                    "state_equivalence_temperature_rise_relative_max"
                ]
            )
            for existing in stable_points
        )
        if not equivalent:
            stable_points.append(point)
    pairs = []
    for context_id in config["contexts"]:
        up = next(run for run in runs if run.spec.protocol_id == f"{context_id}_heating")
        down = next(run for run in runs if run.spec.protocol_id == f"{context_id}_cooling")
        pairs.extend(_common_voltage_pairs(up, down))
    numeric_ambiguity = 0
    practical_ambiguity = 0
    for up, down in pairs:
        current = _relative_scalar_jump(
            up.result.metrics["terminal_current_A"], down.result.metrics["terminal_current_A"]
        )
        temperature = _temperature_rise_relative_difference(
            up.result.temperature_K, down.result.temperature_K, 325.0
        )
        numeric_ambiguity += max(current, temperature) > 1.0e-4
        practical_ambiguity += max(current, temperature) >= 0.2

    pod: dict[str, Any] = {
        "executed": False,
        "population": "actual_spectrum_stable_manuscript_eligible_points",
        "transform": config["surrogate_eligibility"]["pod_transform"],
        "energy_target": float(config["surrogate_eligibility"]["pod_energy_target"]),
        "rank_cap": int(config["surrogate_eligibility"]["pod_rank_cap"]),
        "split_status": config["surrogate_eligibility"]["split_status"],
        "no_holdout_diagnostic": True,
    }
    pod_cap_pass = False
    if executed and len(stable_points) >= 2:
        matrix = np.stack(
            [
                np.log1p(
                    np.maximum(_numpy(point.result.temperature_K) - 325.0, 0.0)
                ).reshape(-1)
                for point in stable_points
            ]
        )
        centered = matrix - np.mean(matrix, axis=0, keepdims=True)
        singular = np.linalg.svd(centered, full_matrices=False, compute_uv=False)
        energy = singular**2
        cumulative = np.cumsum(energy) / max(float(np.sum(energy)), 1.0e-30)
        rank = int(np.searchsorted(cumulative, pod["energy_target"], side="left") + 1)
        pod_cap_pass = rank <= int(pod["rank_cap"])
        pod.update(
            {
                "executed": True,
                "fit_point_count": len(stable_points),
                "fit_point_ids": [point.point_id for point in stable_points],
                "rank": rank,
                "rank_cap_pass": pod_cap_pass,
                "cumulative_energy_at_rank": float(cumulative[rank - 1]),
                "singular_values": singular.tolist(),
            }
        )
    iterations = [
        int(point.result.metrics["iterations"])
        for run in runs
        for point in run.coarse_points[1:]
        if point.valid
    ]
    coarse_keys = [
        (point.protocol_id, round(point.voltage_V, 10))
        for run in runs
        for point in run.coarse_points
    ]
    protocol_metadata_sufficient = bool(
        executed
        and all(run.completed for run in runs)
        and len(set(coarse_keys)) == len(coarse_keys)
        and all(
            point.initial_state_provenance
            == "immediately_preceding_accepted_protocol_equilibrium"
            for run in runs
            for point in run.coarse_points[1:]
        )
    )
    eligible = bool(
        executed and protocol_metadata_sufficient and pod.get("executed") and pod_cap_pass
    )
    return {
        "executed": executed,
        "eligible": eligible,
        "reason": (
            "protocol_selected_manifold_and_rank_cap_pass"
            if eligible
            else "manifold_disposition_or_rank_prerequisite_not_satisfied"
        ),
        "protocol_metadata_sufficient_for_executed_paths": protocol_metadata_sufficient,
        "allowed_input_contract": config["surrogate_eligibility"]["future_allowed_inputs"],
        "forbidden_input_keys": config["surrogate_eligibility"]["future_forbidden_inputs"],
        "stable_manifold_point_count": len(stable_points),
        "event_count": int(decision["resolved_event_count"]),
        "common_voltage_branch_pair_count": len(pairs),
        "unknown_protocol_numeric_ambiguity_count": int(numeric_ambiguity),
        "unknown_protocol_practical_ambiguity_count": int(practical_ambiguity),
        "thermal_pod": pod,
        "continuation": {
            "median_previous_state_warmstart_iterations": float(np.median(iterations))
            if iterations
            else None,
            "median_previous_state_warmstart_linear_solve_count": float(
                np.median([2 * value + 1 for value in iterations])
            )
            if iterations
            else None,
            "total_electrical_solve_count": int(sum(value + 1 for value in iterations)),
            "total_thermal_solve_count": int(sum(iterations)),
            "total_linear_solve_count": int(sum(2 * value + 1 for value in iterations)),
            "point_count": len(iterations),
            "previous_state_summary_contract": "deployable_previous_equilibrium_summary_only",
        },
        "neural_training_executed": False,
        "future_split_required": True,
    }


def _plot_protocol_iv(
    path: Path,
    runs: Sequence[ProtocolRun],
    stability_by_point: Mapping[str, Mapping[str, Any]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=False)
    for axis, context_id in zip(axes, ("G0", "G1")):
        for run in [item for item in runs if item.spec.context_id == context_id]:
            voltage = [point.voltage_V for point in run.coarse_points]
            current = [point.result.metrics["terminal_current_A"] * 1.0e3 for point in run.coarse_points]
            axis.plot(voltage, current, "-", lw=1.4, label=run.spec.branch_label)
            for point in all_run_points(run):
                classification = stability_by_point.get(point.point_id, {}).get("stability_class")
                if classification not in {"stable", "unstable", "indeterminate"}:
                    continue
                marker = {"stable": "o", "unstable": "x", "indeterminate": "o"}[str(classification)]
                face = "none" if classification == "indeterminate" else None
                axis.scatter(
                    point.voltage_V,
                    point.result.metrics["terminal_current_A"] * 1.0e3,
                    marker=marker,
                    s=24,
                    facecolors=face,
                    color="black",
                    zorder=4,
                )
        axis.set_title(context_id)
        axis.set_xlabel("Device-terminal voltage (V)")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Terminal current (mA)")
    axes[0].legend(frameon=False)
    figure.suptitle("Protocol I-V paths; stability markers only where spectra were evaluated")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_temperature_state(path: Path, runs: Sequence[ProtocolRun]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex="col")
    for column, context_id in enumerate(("G0", "G1")):
        for run in [item for item in runs if item.spec.context_id == context_id]:
            voltage = [point.voltage_V for point in run.coarse_points]
            rise = [point.result.metrics["Tmean_K"] - 325.0 for point in run.coarse_points]
            state = [point.result.metrics["mean_effective_state_coordinate"] for point in run.coarse_points]
            axes[0, column].plot(voltage, rise, label=run.spec.branch_label)
            axes[1, column].plot(voltage, state, label=run.spec.branch_label)
            if run.event is not None and run.event.resolved:
                for axis in axes[:, column]:
                    axis.axvspan(
                        run.event.voltage_lower_V,
                        run.event.voltage_upper_V,
                        alpha=0.12,
                    )
        axes[0, column].set_title(context_id)
        axes[0, column].set_ylabel("Mean temperature rise (K)")
        axes[1, column].set_ylabel("Mean effective state")
        axes[1, column].set_xlabel("Device-terminal voltage (V)")
        axes[0, column].grid(alpha=0.25)
        axes[1, column].grid(alpha=0.25)
    axes[0, 0].legend(frameon=False)
    figure.suptitle("Branch-resolved monotone protocol loops")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_stable_manifold(
    path: Path,
    runs: Sequence[ProtocolRun],
    stability_by_point: Mapping[str, Mapping[str, Any]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for axis, context_id in zip(axes, ("G0", "G1")):
        for run in [item for item in runs if item.spec.context_id == context_id]:
            axis.plot(
                [p.voltage_V for p in run.coarse_points],
                [p.result.metrics["mean_effective_state_coordinate"] for p in run.coarse_points],
                color="0.75",
                lw=1.0,
                label=f"{run.spec.branch_label}: reached, spectrum not exhaustive",
            )
            stable = [
                p
                for p in all_run_points(run)
                if stability_by_point.get(p.point_id, {}).get("stability_class") == "stable"
            ]
            unstable = [
                p
                for p in all_run_points(run)
                if stability_by_point.get(p.point_id, {}).get("stability_class") == "unstable"
            ]
            axis.scatter(
                [p.voltage_V for p in stable],
                [p.result.metrics["mean_effective_state_coordinate"] for p in stable],
                s=32,
                label=f"{run.spec.branch_label}: locally stable",
            )
            axis.scatter(
                [p.voltage_V for p in unstable],
                [p.result.metrics["mean_effective_state_coordinate"] for p in unstable],
                marker="x",
                color="red",
                s=34,
                label=f"{run.spec.branch_label}: unstable boundary",
            )
        axis.set_title(context_id)
        axis.set_xlabel("Device-terminal voltage (V)")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Mean effective conductive-state coordinate")
    axes[0].legend(frameon=False, fontsize=7)
    figure.suptitle("Locally assessed stable reachable equilibria (not an all-point stability claim)")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_event_maps(path: Path, runs: Sequence[ProtocolRun]) -> None:
    resolved = [run for run in runs if run.event is not None and run.event.resolved]
    if not resolved:
        figure, axis = plt.subplots(figsize=(8, 3.5))
        axis.axis("off")
        axis.text(0.5, 0.5, "No resolved protocol switching event", ha="center", va="center")
    else:
        figure, axes = plt.subplots(len(resolved), 4, figsize=(11, 2.5 * len(resolved)))
        axes = np.atleast_2d(axes)
        for row, run in enumerate(resolved):
            event = run.event
            assert event is not None
            fields = [
                _numpy(event.refined_pre.result.temperature_K) - 325.0,
                _numpy(event.refined_post.result.temperature_K) - 325.0,
                _numpy(event.refined_pre.result.fields["effective_conductive_state_coordinate"]),
                _numpy(event.refined_post.result.fields["effective_conductive_state_coordinate"]),
            ]
            titles = ("pre ΔT", "post ΔT", "pre m_eq", "post m_eq")
            temperature_limits = (
                float(min(np.min(fields[0]), np.min(fields[1]))),
                float(max(np.max(fields[0]), np.max(fields[1]))),
            )
            for column, (field_value, title) in enumerate(zip(fields, titles)):
                limits = temperature_limits if column < 2 else (0.0, 1.0)
                image = axes[row, column].imshow(
                    field_value,
                    origin="lower",
                    aspect="auto",
                    vmin=limits[0],
                    vmax=limits[1],
                )
                axes[row, column].set_title(f"{run.spec.protocol_id} {title}", fontsize=8)
                figure.colorbar(image, ax=axes[row, column], fraction=0.046)
    figure.suptitle("Refined protocol switch-event fields")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_stability(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.8))
    colors = {"stable": "tab:green", "unstable": "tab:red", "indeterminate": "tab:orange"}
    for protocol_id in sorted({str(row["protocol_id"]) for row in rows}):
        selected = [row for row in rows if str(row["protocol_id"]) == protocol_id]
        axis.plot(
            [float(row["device_voltage_V"]) for row in selected],
            [float(row["relative_stability_margin"]) for row in selected],
            "--",
            color="0.65",
            lw=0.8,
        )
        for row in selected:
            axis.scatter(
                float(row["device_voltage_V"]),
                float(row["relative_stability_margin"]),
                color=colors[str(row["stability_class"])],
                s=32,
                label=f"{protocol_id} {row['stability_class']}",
            )
    axis.axhline(-1.0e-6, color="tab:green", ls=":", lw=1.0)
    axis.axhline(1.0e-6, color="tab:red", ls=":", lw=1.0)
    axis.set_xlabel("Device-terminal voltage (V)")
    axis.set_ylabel("Relative stability margin")
    axis.set_title("Physical thermal-dynamics spectrum at preregistered states")
    axis.grid(alpha=0.25)
    handles, labels = axis.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    axis.legend(unique.values(), unique.keys(), fontsize=6, ncol=2, frameon=False)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_sensitivity(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    rows = [row for row in rows if bool(row.get("executed", False))]
    figure, (left, right) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    labels = [str(row["protocol_id"]) for row in rows]
    x = np.arange(len(rows))
    left.bar(x - 0.18, [float(row.get("primary_switching_voltage_estimate_V", 0.0) or 0.0) for row in rows], width=0.36, label="0.025 V + refine")
    left.bar(x + 0.18, [float(row.get("half_step_switching_voltage_estimate_V", 0.0) or 0.0) for row in rows], width=0.36, label="0.0125 V + refine")
    left.set_xticks(x, labels, rotation=25, ha="right")
    left.set_ylabel("Switching voltage estimate (V)")
    left.legend(frameon=False)
    right.bar(x - 0.18, [float(row.get("worst_off_event_temperature_rise_relative_difference", 0.0) or 0.0) for row in rows], width=0.36, label="T-rise")
    right.bar(x + 0.18, [float(row.get("worst_off_event_terminal_current_relative_difference", 0.0) or 0.0) for row in rows], width=0.36, label="current")
    right.axhline(0.01, color="black", ls=":")
    right.set_xticks(x, labels, rotation=25, ha="right")
    right.set_ylabel("Off-event relative difference")
    right.legend(frameon=False)
    figure.suptitle("Protocol event half-step reproducibility")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_single_vs_protocol(
    path: Path, runs: Sequence[ProtocolRun], repository_root: Path
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    prior = repository_root / (
        "outputs/tables/q2_m1_self_consistent_imt_contraction_gate_v1/"
        "Q2-M1-SELF-CONSISTENT-IMT-CONTRACTION-GATE-20260810-V1/voltage_admission.csv"
    )
    if prior.exists():
        with prior.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for branch in ("heating", "cooling"):
            selected = [row for row in rows if row["branch_label"] == branch]
            axes[0].plot(
                [float(row["device_voltage_V"]) for row in selected],
                [float(row["cold_mean_effective_state"]) for row in selected],
                "o--",
                label=f"{branch}: cold init",
            )
            axes[0].plot(
                [float(row["device_voltage_V"]) for row in selected],
                [float(row["hot_mean_effective_state"]) for row in selected],
                "s--",
                label=f"{branch}: hot init",
            )
    g0 = [run for run in runs if run.spec.context_id == "G0"]
    for run in g0:
        axes[1].plot(
            [point.voltage_V for point in run.coarse_points],
            [point.result.metrics["mean_effective_state_coordinate"] for point in run.coarse_points],
            label=f"explicit {run.spec.direction} protocol",
        )
    axes[0].set_title("Fixed parameter + unspecified initialization")
    axes[1].set_title("Explicit direction/start/previous-state protocol")
    for axis in axes:
        axis.set_xlabel("Device-terminal voltage (V)")
        axis.grid(alpha=0.25)
        axis.legend(frameon=False, fontsize=7)
    axes[0].set_ylabel("Mean effective conductive-state coordinate")
    figure.suptitle("Actual numerical multi-valued relation versus selected execution paths")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_decision(path: Path, decision: Mapping[str, Any]) -> None:
    figure, axis = plt.subplots(figsize=(10, 4.8))
    axis.axis("off")
    contexts = decision["contexts"]
    text = (
        f"Disposition: {decision['disposition']}\n\n"
        f"Ramps completed: {decision['completed_protocol_ramp_count']}/4\n"
        f"Events resolved: {decision['resolved_event_count']}/{decision['event_count']}\n"
        f"Stability: {decision['stable_state_count']} stable, "
        f"{decision['unstable_state_count']} unstable, "
        f"{decision['indeterminate_state_count']} indeterminate\n"
        f"Half-step reproducibility: {decision['step_sensitivity_all_pass']}\n\n"
        f"G0 qualified: {contexts['G0']['qualified']}\n"
        f"G1 qualified: {contexts['G1']['qualified']}\n\n"
        "No neural training; no root ID; no root averaging."
    )
    axis.text(0.04, 0.94, text, va="top", ha="left", fontsize=12, family="monospace")
    axis.set_title("Protocol-manifold paper route decision")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_report(
    path: Path,
    *,
    config: Mapping[str, Any],
    decision: Mapping[str, Any],
    manifest_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    stability_rows: Sequence[Mapping[str, Any]],
    sensitivity_rows: Sequence[Mapping[str, Any]],
    eligibility: Mapping[str, Any],
) -> None:
    event_lines = []
    for row in event_rows:
        estimate = row.get("switching_voltage_estimate_V")
        event_lines.append(
            "| {protocol} | {lower} | {upper} | {estimate} | {jump} | {resolved} |".format(
                protocol=row["protocol_id"],
                lower=f"{float(row['interval_lower_V']):.6f}" if estimate is not None else "--",
                upper=f"{float(row['interval_upper_V']):.6f}" if estimate is not None else "--",
                estimate=f"{float(estimate):.6f}" if estimate is not None else "--",
                jump=f"{float(row.get('refined_mean_state_jump', 0.0) or 0.0):.6f}",
                resolved=row.get("resolved", False),
            )
        )
    context_lines = []
    for context_id, values in decision["contexts"].items():
        separation = float(values["conservative_switching_voltage_separation_V"])
        context_lines.append(
            f"| {context_id} | "
            f"{f'{separation:.6g}' if math.isfinite(separation) else '--'} | "
            f"{values['protocol_bistable_reachable_width_V']:.6g} | "
            f"{values['stable_distinct_common_voltage_pair_count']} | "
            f"{values['maximum_bistable_current_relative_difference']:.6g} | "
            f"{values['maximum_bistable_temperature_rise_relative_difference']:.6g} | "
            f"{values['qualified']} |"
        )
    validation_command = (
        "pytest -q tests/test_q2_m1_protocol_selected_equilibrium_manifold_mve_v1.py"
    )
    allowed_sentence = (
        "Although the fixed-parameter steady relation was multi-valued, explicit monotone "
        "voltage protocols selected reproducible, locally stable and continuously reachable "
        "heating/cooling equilibrium components within the frozen synthetic M1 model."
        if decision["disposition"] == config["decision_gates"]["dispositions"]["go"]
        else "No positive protocol-manifold sentence is admitted by this bounded result."
    )
    text = f"""# Q2 M1 protocol-selected equilibrium-manifold MVE v1

## Conclusion

Disposition: `{decision['disposition']}`.

All outputs are `{EVIDENCE_TYPE}`. Four explicit device-terminal voltage protocols were executed; no neural model, hidden root identifier, root averaging, pseudo-arclength continuation, source-RC model, or time-domain attractor simulation was used.

## Frozen PR #41

PR #41 head `{config['frozen_baseline']['head_sha']}` retained `{config['frozen_baseline']['disposition']}` unchanged and was squash-merged as `{config['frozen_baseline']['merge_sha']}` before this branch.

## Protocol execution

| protocol | expected points | valid points | valid fraction | endpoint | completed |
|---|---:|---:|---:|---:|---:|
"""
    for row in manifest_rows:
        text += (
            f"| {row['protocol_id']} | {row['expected_main_point_count']} | "
            f"{row['valid_main_point_count']} | {float(row['valid_main_fraction']):.6f} | "
            f"{row['endpoint_pass']} | {row['completed']} |\n"
        )
    text += """

Every non-initial coarse point records the immediately preceding accepted equilibrium as its actual initialization provenance. Continuation reachability is quasi-static numerical protocol evidence, not a time-domain dynamics claim.

## Switching events

| protocol | lower V | upper V | estimate V | mean-state jump | resolved |
|---|---:|---:|---:|---:|---:|
""" + "\n".join(event_lines)
    text += f"""

Total event-refinement solves, including primary confirmation and half-step bisection: `{decision['event_refinement_solve_count']}` / `{config['budgets']['maximum_event_refinement_solves']}`.

## Local physical stability

The full 250 x 250 Jacobian is the derivative of the semi-discrete thermal dynamics after quasi-static electrical elimination, not the derivative of `P_alpha`. The Qiu source-contract device capacity `{config['source_role']['expected_device_thermal_capacitance_J_K']}` J/K is divided uniformly over 250 cells only as a positive device-level time scale.

- evaluated states: `{len(stability_rows)}` / `{config['budgets']['maximum_stability_states']}`
- stable: `{decision['stable_state_count']}`
- unstable: `{decision['unstable_state_count']}`
- indeterminate: `{decision['indeterminate_state_count']}`
- cumulative spectrum evaluations: `{decision['stability_execution']['cumulative_spectrum_evaluation_count']}` / `{config['budgets']['maximum_stability_states']}` (`16` initial plus `8` fixed interior probes)

Only actually evaluated states classified `stable` enter the manuscript-stable dataset; unassessed protocol points remain numerical reachable equilibria only.

## Half-step reproducibility

| protocol | switch difference V | worst off-event T | worst off-event I | class reversal | pass |
|---|---:|---:|---:|---:|---:|
"""
    for row in sensitivity_rows:
        if not bool(row.get("executed", False)):
            text += f"| {row['protocol_id']} | -- | -- | -- | -- | N/A |\n"
        else:
            text += (
                f"| {row['protocol_id']} | {float(row['switching_voltage_difference_V']):.6g} | "
                f"{float(row['worst_off_event_temperature_rise_relative_difference']):.6g} | "
                f"{float(row['worst_off_event_terminal_current_relative_difference']):.6g} | "
                f"{row.get('stability_classification_reversal_count')} | {row.get('pass')} |\n"
            )
    text += """

## Context gates

| context | conservative switch separation V | stable sampled bistable span V | stable same-V pairs | max current separation | max T-rise separation | qualified |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(context_lines)
    text += f"""

## Surrogate eligibility without training

- eligibility executed: `{eligibility['executed']}`
- eligible for a separately preregistered next task: `{eligibility['eligible']}`
- stable manuscript point count: `{eligibility['stable_manifold_point_count']}`
- unknown-protocol practical ambiguity count: `{eligibility['unknown_protocol_practical_ambiguity_count']}`
- POD diagnostic: `{json.dumps(_json_safe(eligibility['thermal_pod']), sort_keys=True)}`
- neural training executed: `False`

This task freezes no future train/validation/test split; the POD number is an eligibility-only stable-point diagnostic and cannot vote on generalization.

## Claim boundary

Allowed sentence: {allowed_sentence}

The most favorable result is limited to the frozen ideal device-terminal voltage-clamp protocol. Full hysteresis, minor loops, Qiu source/12-kOhm/RC reproduction, dynamic-attractor behavior, experimental validation, formal PINN superiority, inverse recovery, and material transfer remain forbidden.

## Artifacts and validation

- Tables: `{config['outputs']['table_root']}`
- Fields: `{config['outputs']['processed_root']}`
- Figures: `{config['outputs']['figure_root']}`
- Focused validation command: `{validation_command}`
- Base: `{config['frozen_baseline']['merge_sha']}`
- Final commit, push, and draft PR are recorded in the final handoff because a commit cannot contain its own SHA.

## Next priority

Under fresh authorization, execute only `Q2_PROTOCOL_MANIFOLD_BRANCH_AWARE_SURROGATE_MVE_V1`: freeze a future split; compare analytic, ridge, single-head, and physically gated branch-aware latent baselines; preserve conservative projection; and require unknown-protocol set output or refusal. Do not infer a dynamic attractor or train a surrogate in this task.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_evidence_map(
    path: Path,
    *,
    decision: Mapping[str, Any],
    eligibility: Mapping[str, Any],
) -> None:
    positive = decision["disposition"] in {
        "GO_PROTOCOL_SELECTED_EQUILIBRIUM_MANIFOLD",
        "PARTIAL_GO_PROTOCOL_SELECTED_MANIFOLD",
    }
    text = f"""# Q2 protocol-manifold evidence map

| Proposition | Lifecycle | Claim status | Evidence | Boundary |
|---|---|---|---|---|
| Conservative self-consistent M1 operator remains implemented | numerically_validated | supported | Frozen operator and focused parity/ledger checks | Synthetic M1 only |
| Explicit protocols select reproducible equilibrium components | {'claim_supported' if positive else 'numerically_validated'} | {'qualified_supported' if positive else 'failed_but_informative'} | Four ramps, refined events, half-step comparison | Ideal terminal-voltage protocol only |
| Local physical stability of sampled states | numerically_validated | qualified_supported | Full thermal-dynamics spectra at at most 24 states | Uniform positive device-level heat capacity; not all ramp points |
| Detected cooling-event thresholds are step-reproducible | numerically_validated | qualified_supported | Primary and half-step refined intervals with local field/current comparison | Frozen voltage steps and refinement only |
| Protocol-aware surrogate is eligible | {'implemented' if eligibility['eligible'] else 'planned'} | {'qualified_supported' if eligibility['eligible'] else 'forbidden'} | Read-only eligibility JSON; no training | A future task must freeze a split and matched budgets |
| Full hysteresis, minor loops, source-RC reproduction, dynamic attractor, experiment, inverse, transfer, formal PINN superiority | planned | forbidden | Not executed | Explicitly outside this task |

Final disposition: `{decision['disposition']}`.

Evidence type: `{EVIDENCE_TYPE}`.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_protocol_operators(
    config: Mapping[str, Any], repository_root: Path
) -> dict[str, M1SelfConsistentIMTProjection]:
    base_config = load_yaml(repository_root / str(config["reference"]["base_config"]))
    qiu = load_qiu_parameters(
        {
            "source_contract": {
                "path": config["reference"]["source_contract"],
                "section": "source_author_fitted_lumped_quantities",
                "beta_per_K": 0.253,
                "loop_width_K": 7.193,
                "critical_temperature_K": 332.8,
                "expected_Tc_up_K": config["reference"]["Tc_up_K"],
                "expected_Tc_down_K": config["reference"]["Tc_down_K"],
                "expected_nominal_wT_K": config["reference"][
                    "nominal_transition_width_K"
                ],
            }
        },
        repository_root,
    )
    operators: dict[str, M1SelfConsistentIMTProjection] = {}
    for context_id, context in config["contexts"].items():
        operators[str(context_id)] = build_operator(
            base_config=base_config,
            repository_root=repository_root,
            contact_overlap_nm=float(context["contact_overlap_nm"]),
            qiu_parameters=qiu,
            phase_width_multiplier=float(config["reference"]["phase_width_multiplier"]),
            joule_feedback_multiplier=float(
                config["reference"]["joule_feedback_multiplier"]
            ),
            relaxation_alpha=float(config["reference"]["relaxation_alpha"]),
        )
    return operators


def _fixed_point_from_npz(data: Mapping[str, Any], index: int) -> FixedPointResult:
    field_names = (
        "potential_V",
        "conductivity_S_m",
        "effective_conductive_state_coordinate",
        "electrical_x_face_current_A",
        "electrical_y_face_current_A",
        "source_face_current_A",
        "ground_face_current_A",
        "thermal_x_face_power_W",
        "thermal_y_face_power_W",
        "internal_joule_cell_W",
        "contact_joule_cell_W",
        "total_joule_cell_W",
        "feedback_joule_cell_W",
        "vertical_sink_cell_W",
    )
    global_fields = (
        "internal_joule_W",
        "contact_joule_W",
        "total_electrical_heat_W",
        "terminal_power_W",
        "vertical_sink_W",
        "feedback_joule_W",
    )
    fields = {
        name: torch.as_tensor(np.asarray(data[name][index]), dtype=torch.float64)
        for name in field_names
    }
    fields.update(
        {
            name: torch.as_tensor(float(data[name][index]), dtype=torch.float64)
            for name in global_fields
        }
    )
    valid = bool(data["point_valid"][index])
    metrics = {
        "converged": valid,
        "finite": bool(
            np.isfinite(np.asarray(data["temperature_K"][index])).all()
            and all(bool(torch.isfinite(value).all()) for value in fields.values())
        ),
    }
    metric_names = (
        "iterations",
        "scaled_nonlinear_residual",
        "current_imbalance",
        "terminal_electrical_heat_ledger_error",
        "state_consistent_feedback_heat_sink_ledger_error",
        "terminal_current_A",
        "ground_current_A",
        "Tmean_K",
        "Tmax_K",
        "mean_effective_state_coordinate",
        "transition_fraction",
    )
    for name in metric_names:
        value = np.asarray(data[f"metric_{name}"][index]).item()
        metrics[name] = int(value) if name == "iterations" else float(value)
    return FixedPointResult(
        temperature_K=torch.as_tensor(
            np.asarray(data["temperature_K"][index]), dtype=torch.float64
        ),
        fields=fields,
        metrics=metrics,
    )


def rehydrate_protocol_runs(
    *,
    config: Mapping[str, Any],
    processed_root: Path,
) -> list[ProtocolRun]:
    """Rebuild execution objects from the four immutable formal-ramp NPZ files."""

    specs = {spec.protocol_id: spec for spec in build_protocol_specs(config)}
    runs: list[ProtocolRun] = []
    for protocol_id, spec in specs.items():
        path = processed_root / f"{protocol_id}.npz"
        if not path.exists():
            raise FileNotFoundError(f"missing formal protocol artifact: {path}")
        with np.load(path, allow_pickle=False) as loaded:
            data = {name: loaded[name] for name in loaded.files}
        points: list[ProtocolPoint] = []
        for index in range(len(data["point_id"])):
            points.append(
                ProtocolPoint(
                    point_id=str(data["point_id"][index]),
                    protocol_id=protocol_id,
                    context_id=spec.context_id,
                    branch_label=spec.branch_label,
                    branch_value=spec.branch_value,
                    voltage_V=float(data["point_voltage_V"][index]),
                    point_kind=str(data["point_kind"][index]),
                    sequence_index=int(data["point_sequence_index"][index]),
                    initial_state_provenance=str(
                        data["point_initial_state_provenance"][index]
                    ),
                    previous_point_id=str(data["point_previous_id"][index]),
                    result=_fixed_point_from_npz(data, index),
                    valid=bool(data["point_valid"][index]),
                    accepted=bool(data["point_accepted"][index]),
                )
            )
        by_id = {point.point_id: point for point in points}
        coarse = sorted(
            [point for point in points if point.point_kind == "coarse"],
            key=lambda point: point.sequence_index,
        )
        for previous, point in zip(coarse, coarse[1:]):
            point.jump_from_previous = jump_diagnostics(
                previous.result,
                point.result,
                ambient_temperature_K=325.0,
                jump_config=config["jump_detection"],
            )
        candidate_index = next(
            (
                index
                for index, point in enumerate(coarse[1:], start=1)
                if bool(point.jump_from_previous.get("jump_candidate", False))
            ),
            None,
        )
        primary_points = [
            point
            for point in points
            if point.point_kind
            in {"event_refinement", "event_reachability_confirmation"}
        ]
        event: ProtocolEvent | None = None
        if candidate_index is not None:
            confirmation = next(
                (
                    point
                    for point in primary_points
                    if point.point_kind == "event_reachability_confirmation"
                ),
                None,
            )
            if confirmation is None:
                raise ValueError(f"saved detected event lacks confirmation: {protocol_id}")
            refined_pre = by_id[confirmation.previous_point_id]
            confirmation.jump_from_previous = jump_diagnostics(
                refined_pre.result,
                confirmation.result,
                ambient_temperature_K=325.0,
                jump_config=config["jump_detection"],
            )
            event = ProtocolEvent(
                event_id=f"{protocol_id}_event_01",
                protocol_id=protocol_id,
                coarse_pre=coarse[candidate_index - 1],
                coarse_post=coarse[candidate_index],
                refined_pre=refined_pre,
                refined_post=confirmation,
                refinement_points=primary_points,
                refinement_solve_count=len(primary_points),
                resolved=bool(
                    confirmation.valid
                    and confirmation.jump_from_previous["jump_candidate"]
                    and abs(confirmation.voltage_V - refined_pre.voltage_V)
                    <= float(config["jump_detection"]["refinement_voltage_resolution_V"])
                ),
            )
        half_points = [
            point
            for point in points
            if point.point_kind
            in {
                "half_step_anchor_reused",
                "half_step_continuation",
                "half_step_event_refinement",
            }
        ]
        half_pre: ProtocolPoint | None = None
        half_post: ProtocolPoint | None = None
        half_core = [
            point
            for point in half_points
            if point.point_kind
            in {"half_step_anchor_reused", "half_step_continuation"}
        ]
        for previous, point in zip(half_core, half_core[1:]):
            point.jump_from_previous = jump_diagnostics(
                previous.result,
                point.result,
                ambient_temperature_K=325.0,
                jump_config=config["jump_detection"],
            )
            if half_pre is None and point.jump_from_previous["jump_candidate"]:
                half_pre, half_post = previous, point
        for point in [
            item for item in half_points if item.point_kind == "half_step_event_refinement"
        ]:
            if half_pre is None or half_post is None:
                break
            point.jump_from_previous = jump_diagnostics(
                half_pre.result,
                point.result,
                ambient_temperature_K=325.0,
                jump_config=config["jump_detection"],
            )
            if point.jump_from_previous["jump_candidate"]:
                half_post = point
            else:
                half_pre = point
        endpoint_metric = float(coarse[0].result.metrics["mean_effective_state_coordinate"])
        endpoint_pass = bool(
            coarse[0].valid
            and (
                endpoint_metric <= spec.endpoint_mean_state_bound
                if spec.branch_label == "heating"
                else endpoint_metric >= spec.endpoint_mean_state_bound
            )
        )
        runs.append(
            ProtocolRun(
                spec=spec,
                expected_coarse_points=33,
                preparation_points=[
                    point for point in points if point.point_kind == "endpoint_preparation"
                ],
                coarse_points=coarse,
                event=event,
                half_step_points=half_points,
                half_step_event_pre=half_pre,
                half_step_event_post=half_post,
                endpoint_pass=endpoint_pass,
                completed=bool(len(coarse) == 33 and all(point.valid for point in coarse)),
                failure_reason="",
            )
        )
    return runs


def _finalize_protocol_outputs(
    *,
    config: Mapping[str, Any],
    repository_root: Path,
    runs: Sequence[ProtocolRun],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    stability_rows: Sequence[Mapping[str, Any]],
    stability_by_point: Mapping[str, Mapping[str, Any]],
    roles: Mapping[str, Sequence[str]],
    sensitivity_rows: Sequence[Mapping[str, Any]],
    decision: dict[str, Any],
    eligibility: Mapping[str, Any],
    stability_execution: Mapping[str, int],
    postprocess_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    processed_root = repository_root / str(config["outputs"]["processed_root"])
    table_root = repository_root / str(config["outputs"]["table_root"])
    figure_root = repository_root / str(config["outputs"]["figure_root"])
    manifest_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    npz_paths: dict[str, str] = {}
    for run in runs:
        npz_path = processed_root / f"{run.spec.protocol_id}.npz"
        index_by_point = save_protocol_npz(
            npz_path,
            run=run,
            operator=operators[run.spec.context_id],
            stability_by_point=stability_by_point,
        )
        npz_paths[run.spec.protocol_id] = npz_path.relative_to(repository_root).as_posix()
        manifest_rows.append(_manifest_row(run, npz_path.relative_to(repository_root)))
        for point in all_run_points(run):
            point_rows.append(
                point_to_row(
                    point,
                    operator=operators[run.spec.context_id],
                    point_index_in_npz=index_by_point[point.point_id],
                    stability=stability_by_point.get(point.point_id),
                    role="|".join(roles.get(point.point_id, [point.point_kind])),
                )
            )
    event_rows = [_event_row(run) for run in runs]

    _write_csv(table_root / "protocol_manifest.csv", manifest_rows, _union_fieldnames(manifest_rows))
    _write_csv(
        table_root / "protocol_equilibrium_points.csv",
        point_rows,
        _union_fieldnames(point_rows),
    )
    _write_csv(
        table_root / "protocol_switching_events.csv",
        event_rows,
        _union_fieldnames(event_rows),
    )
    _write_csv(
        table_root / "physical_stability_metrics.csv",
        stability_rows,
        _union_fieldnames(stability_rows)
        if stability_rows
        else ["state_id", "execution_status"],
    )
    _write_csv(
        table_root / "event_step_sensitivity.csv",
        sensitivity_rows,
        _union_fieldnames(sensitivity_rows),
    )
    decision.update(
        {
            "base_sha": config["frozen_baseline"]["merge_sha"],
            "branch": "codex/q2-m1-protocol-selected-equilibrium-manifold-mve-v1",
            "protocol_npz_paths": npz_paths,
            "table_root": config["outputs"]["table_root"],
            "figure_root": config["outputs"]["figure_root"],
            "report_path": config["outputs"]["report"],
            "paper_evidence_map_path": config["outputs"]["paper_evidence_map"],
            "endpoint_auxiliary_solve_count": sum(
                len(run.preparation_points) for run in runs
            ),
            "half_step_continuation_solve_count": sum(
                max(
                    0,
                    len(
                        [
                            point
                            for point in run.half_step_points
                            if point.point_kind != "half_step_event_refinement"
                        ]
                    )
                    - 1,
                )
                for run in runs
            ),
            "focused_test_file": "tests/test_q2_m1_protocol_selected_equilibrium_manifold_mve_v1.py",
            "stability_execution": dict(stability_execution),
        }
    )
    if postprocess_metadata is not None:
        decision["aggregation_repair"] = dict(postprocess_metadata)
    _write_json(table_root / "surrogate_eligibility.json", eligibility)
    _write_json(table_root / "decision_summary.json", decision)

    _plot_protocol_iv(figure_root / "protocol_iv_hysteresis.png", runs, stability_by_point)
    _plot_temperature_state(
        figure_root / "protocol_temperature_and_state_loops.png", runs
    )
    _plot_stable_manifold(
        figure_root / "stable_reachable_equilibrium_manifold.png", runs, stability_by_point
    )
    _plot_event_maps(figure_root / "switch_event_field_maps.png", runs)
    _plot_stability(figure_root / "physical_stability_margin.png", stability_rows)
    _plot_sensitivity(figure_root / "event_step_sensitivity.png", sensitivity_rows)
    _plot_single_vs_protocol(
        figure_root / "single_valued_vs_protocol_selected_map.png", runs, repository_root
    )
    _plot_decision(figure_root / "paper_route_decision.png", decision)

    _write_report(
        repository_root / str(config["outputs"]["report"]),
        config=config,
        decision=decision,
        manifest_rows=manifest_rows,
        event_rows=event_rows,
        stability_rows=stability_rows,
        sensitivity_rows=sensitivity_rows,
        eligibility=eligibility,
    )
    _write_evidence_map(
        repository_root / str(config["outputs"]["paper_evidence_map"]),
        decision=decision,
        eligibility=eligibility,
    )
    return _json_safe(decision)


def run_experiment(config_path: Path, repository_root: Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    validate_protocol_schema(config)
    processed_root = repository_root / str(config["outputs"]["processed_root"])
    table_root = repository_root / str(config["outputs"]["table_root"])
    figure_root = repository_root / str(config["outputs"]["figure_root"])
    processed_root.mkdir(parents=True, exist_ok=True)
    table_root.mkdir(parents=True, exist_ok=True)
    figure_root.mkdir(parents=True, exist_ok=True)

    operators = _build_protocol_operators(config, repository_root)

    specs = build_protocol_specs(config)
    runs: list[ProtocolRun] = []
    with torch.no_grad():
        for spec in specs:
            run = run_coarse_protocol(
                spec=spec,
                operator=operators[spec.context_id],
                solver_config=config["solver"],
                validity_gates=config["validity_gates"],
                jump_config=config["jump_detection"],
            )
            runs.append(run)

        for run in runs:
            if run.completed and run.event is not None:
                refine_protocol_event(
                    run=run,
                    operator=operators[run.spec.context_id],
                    solver_config=config["solver"],
                    validity_gates=config["validity_gates"],
                    jump_config=config["jump_detection"],
                )
                if run.event is not None and run.event.resolved:
                    run_half_step_event_window(
                        run=run,
                        operator=operators[run.spec.context_id],
                        solver_config=config["solver"],
                        validity_gates=config["validity_gates"],
                        jump_config=config["jump_detection"],
                        sensitivity_config=config["step_sensitivity"],
                    )
                    refine_half_step_event(
                        run=run,
                        operator=operators[run.spec.context_id],
                        solver_config=config["solver"],
                        validity_gates=config["validity_gates"],
                        jump_config=config["jump_detection"],
                        maximum_solves=2,
                    )

    primary_refinements = sum(
        run.event.refinement_solve_count if run.event is not None else 0 for run in runs
    )
    half_refinements = sum(
        point.point_kind == "half_step_event_refinement"
        for run in runs
        for point in run.half_step_points
    )
    refinement_solve_count = primary_refinements + half_refinements

    stability_rows, stability_by_point, roles, stability_execution = evaluate_stability_budget(
        runs=runs,
        operators=operators,
        config=config,
        repository_root=repository_root,
    )
    sensitivity_rows = [
        event_step_sensitivity(
            run=run,
            stability_by_point=stability_by_point,
            sensitivity_config={
                **config["step_sensitivity"],
                "refinement_voltage_resolution_V": config["jump_detection"][
                    "refinement_voltage_resolution_V"
                ],
            },
        )
        for run in runs
    ]
    decision = aggregate_decision(
        runs=runs,
        stability_rows=stability_rows,
        stability_by_point=stability_by_point,
        sensitivity_rows=sensitivity_rows,
        config=config,
        refinement_solve_count=refinement_solve_count,
    )
    eligibility = build_surrogate_eligibility(
        runs=runs,
        decision=decision,
        stability_by_point=stability_by_point,
        config=config,
    )

    return _finalize_protocol_outputs(
        config=config,
        repository_root=repository_root,
        runs=runs,
        operators=operators,
        stability_rows=stability_rows,
        stability_by_point=stability_by_point,
        roles=roles,
        sensitivity_rows=sensitivity_rows,
        decision=decision,
        eligibility=eligibility,
        stability_execution=stability_execution,
    )


def postprocess_existing_experiment(
    config_path: Path, repository_root: Path
) -> dict[str, Any]:
    """Repair aggregation from saved formal ramps without another ramp solve."""

    config = load_yaml(config_path)
    validate_protocol_schema(config)
    processed_root = repository_root / str(config["outputs"]["processed_root"])
    table_root = repository_root / str(config["outputs"]["table_root"])
    existing_stability_path = table_root / "physical_stability_metrics.csv"
    existing_summary_path = table_root / "decision_summary.json"
    if not existing_stability_path.exists() or not existing_summary_path.exists():
        raise FileNotFoundError("postprocess requires the completed formal-ramp artifacts")
    with existing_stability_path.open("r", newline="", encoding="utf-8") as handle:
        existing_stability_rows = list(csv.DictReader(handle))
    original_summary = json.loads(existing_summary_path.read_text(encoding="utf-8"))
    if int(original_summary.get("main_protocol_point_count", -1)) != 132:
        raise ValueError("saved formal execution is not the frozen four-ramp result")

    operators = _build_protocol_operators(config, repository_root)
    runs = rehydrate_protocol_runs(config=config, processed_root=processed_root)
    stability_rows, stability_by_point, roles, stability_execution = (
        evaluate_stability_budget(
            runs=runs,
            operators=operators,
            config=config,
            repository_root=repository_root,
            existing_rows=existing_stability_rows,
        )
    )
    prior_repair = original_summary.get("aggregation_repair", {})
    initial_spectrum_row_count = int(
        prior_repair.get("initial_spectrum_row_count", len(existing_stability_rows))
    )
    fixed_interior_spectrum_count = int(
        prior_repair.get("fixed_interior_spectrum_evaluation_count", 0)
    ) + int(stability_execution["new_spectrum_evaluation_count"])
    cumulative_spectrum_count = int(
        prior_repair.get(
            "cumulative_spectrum_evaluation_count", len(existing_stability_rows)
        )
    ) + int(stability_execution["new_spectrum_evaluation_count"])
    stability_execution = {
        "final_unique_stability_state_count": int(
            stability_execution["unique_state_count"]
        ),
        "reused_final_unique_state_count": int(
            stability_execution["reused_unique_state_count"]
        ),
        "initial_formal_spectrum_evaluation_count": initial_spectrum_row_count,
        "aggregation_repair_fixed_interior_spectrum_evaluation_count": (
            fixed_interior_spectrum_count
        ),
        "current_postprocess_new_spectrum_evaluation_count": int(
            stability_execution["new_spectrum_evaluation_count"]
        ),
        "cumulative_spectrum_evaluation_count": cumulative_spectrum_count,
    }
    sensitivity_rows = [
        event_step_sensitivity(
            run=run,
            stability_by_point=stability_by_point,
            sensitivity_config={
                **config["step_sensitivity"],
                "refinement_voltage_resolution_V": config["jump_detection"][
                    "refinement_voltage_resolution_V"
                ],
            },
        )
        for run in runs
    ]
    primary_refinements = sum(
        run.event.refinement_solve_count if run.event is not None else 0 for run in runs
    )
    half_refinements = sum(
        point.point_kind == "half_step_event_refinement"
        for run in runs
        for point in run.half_step_points
    )
    refinement_solve_count = primary_refinements + half_refinements
    decision = aggregate_decision(
        runs=runs,
        stability_rows=stability_rows,
        stability_by_point=stability_by_point,
        sensitivity_rows=sensitivity_rows,
        config=config,
        refinement_solve_count=refinement_solve_count,
    )
    eligibility = build_surrogate_eligibility(
        runs=runs,
        decision=decision,
        stability_by_point=stability_by_point,
        config=config,
    )
    return _finalize_protocol_outputs(
        config=config,
        repository_root=repository_root,
        runs=runs,
        operators=operators,
        stability_rows=stability_rows,
        stability_by_point=stability_by_point,
        roles=roles,
        sensitivity_rows=sensitivity_rows,
        decision=decision,
        eligibility=eligibility,
        stability_execution=stability_execution,
        postprocess_metadata={
            "classification": "aggregation_and_evidence_schema_defect",
            "main_protocol_ramps_reexecuted": 0,
            "main_protocol_points_reexecuted": 0,
            "thresholds_changed": False,
            "physics_changed": False,
            "saved_protocol_npz_rehydrated": 4,
            "initial_spectrum_row_count": initial_spectrum_row_count,
            "fixed_interior_spectrum_evaluation_count": fixed_interior_spectrum_count,
            "cumulative_spectrum_evaluation_count": cumulative_spectrum_count,
        },
    )
