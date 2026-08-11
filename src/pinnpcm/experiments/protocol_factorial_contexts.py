"""Bounded G2/G3 protocol-manifold reference execution.

This module is deliberately limited to the two missing factorial contexts for
``Q2_PROTOCOL_MANIFOLD_BRANCH_AWARE_SURROGATE_MVE_V1``.  It reuses the frozen
PR #42 protocol primitives without invoking that task's top-level runner, so
the historical G0/G1 ramps and artifacts are never rerun or rewritten.

The caller supplies the new task config.  The config must retain the PR #42
``reference``, ``protocols``, ``solver``, ``validity_gates``,
``jump_detection``, ``step_sensitivity``, ``stability``, and ``source_role``
contracts and define all four contexts, including G2 and G3.  Only G2/G3 are
read here.  Generated NPZ files are written beneath the caller-provided
``processed_root``; tabular rows and the stage decision are returned to the
integration owner for task-level aggregation.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from pinnpcm.experiments.m1_protocol_selected_equilibrium_manifold import (
    ProtocolPoint,
    ProtocolRun,
    ProtocolSpec,
    _build_protocol_operators,
    _manifest_row,
    _temperature_rise_relative_difference,
    _temperature_sha256,
    all_run_points,
    event_step_sensitivity,
    evaluate_physical_stability,
    load_device_thermal_capacitance,
    point_to_row,
    protocol_voltage_grid,
    refine_half_step_event,
    refine_protocol_event,
    run_coarse_protocol,
    run_half_step_event_window,
    save_protocol_npz,
    validate_protocol_schema,
)
from pinnpcm.physics.m1_self_consistent_imt import M1SelfConsistentIMTProjection


NEW_CONTEXT_IDS = ("G2", "G3")
REPRESENTATIVE_COARSE_INDEX = 16
MAXIMUM_NEW_STABILITY_STATES = 20
STATE_EQUIVALENCE_TOLERANCE = 1.0e-8


def _require_close(name: str, actual: float, expected: float) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(f"{name} drifted: {actual} != {expected}")


def _validate_new_context_contract(config: Mapping[str, Any]) -> None:
    """Fail before execution if the frozen factorial physics contract drifted."""

    validate_protocol_schema(config)
    contexts = config["contexts"]
    missing = [context_id for context_id in NEW_CONTEXT_IDS if context_id not in contexts]
    if missing:
        raise ValueError(f"missing factorial contexts: {missing}")
    expected_contexts = {
        "G2": (20.0, 1.5),
        "G3": (30.0, 0.0),
    }
    for context_id, (overlap_nm, sink_amplitude) in expected_contexts.items():
        context = contexts[context_id]
        _require_close(
            f"{context_id}.contact_overlap_nm",
            float(context["contact_overlap_nm"]),
            overlap_nm,
        )
        _require_close(
            f"{context_id}.sink_amplitude",
            float(context["sink_amplitude"]),
            sink_amplitude,
        )

    reference = config["reference"]
    grid = reference["production_grid"]
    if int(grid["nx"]) != 10 or int(grid["ny"]) != 25:
        raise ValueError("factorial protocol execution requires the frozen 10x25 grid")
    _require_close(
        "phase_width_multiplier", float(reference["phase_width_multiplier"]), 1.0
    )
    _require_close(
        "joule_feedback_multiplier",
        float(reference["joule_feedback_multiplier"]),
        1.0,
    )
    _require_close(
        "relaxation_alpha", float(reference["relaxation_alpha"]), 0.35
    )

    protocol_expectations = {
        "heating": {
            "branch_value": 1.0,
            "start_voltage_V": 0.75,
            "end_voltage_V": 1.55,
            "voltage_step_V": 0.025,
            "start_temperature_K": 325.0,
        },
        "cooling": {
            "branch_value": -1.0,
            "start_voltage_V": 1.55,
            "end_voltage_V": 0.75,
            "voltage_step_V": -0.025,
            "start_temperature_K": 360.0,
            "fallback_preparation_voltage_V": 1.75,
        },
    }
    for branch_label, expected in protocol_expectations.items():
        protocol = config["protocols"][branch_label]
        for name, required in expected.items():
            _require_close(
                f"{branch_label}.{name}", float(protocol[name]), required
            )

    stability = config["stability"]
    configured_maximum = int(
        stability.get(
            "maximum_new_context_states",
            stability.get("maximum_states", MAXIMUM_NEW_STABILITY_STATES),
        )
    )
    if configured_maximum <= 0 or configured_maximum > MAXIMUM_NEW_STABILITY_STATES:
        raise ValueError("new-context physical stability budget must be inside [1, 20]")
    tolerance = float(
        stability.get(
            "state_equivalence_temperature_rise_relative_max",
            STATE_EQUIVALENCE_TOLERANCE,
        )
    )
    _require_close(
        "state_equivalence_temperature_rise_relative_max",
        tolerance,
        STATE_EQUIVALENCE_TOLERANCE,
    )


def _new_context_specs(config: Mapping[str, Any]) -> list[ProtocolSpec]:
    specs: list[ProtocolSpec] = []
    for context_id in NEW_CONTEXT_IDS:
        context = config["contexts"][context_id]
        for branch_label in ("heating", "cooling"):
            protocol = config["protocols"][branch_label]
            bound_key = (
                "endpoint_mean_state_max"
                if branch_label == "heating"
                else "endpoint_mean_state_min"
            )
            spec = ProtocolSpec(
                protocol_id=f"{context_id}_{branch_label}",
                context_id=context_id,
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
                endpoint_mean_state_bound=float(protocol[bound_key]),
                fallback_preparation_voltage_V=(
                    float(protocol["fallback_preparation_voltage_V"])
                    if "fallback_preparation_voltage_V" in protocol
                    else None
                ),
            )
            # This also enforces the frozen 33-point monotone voltage grid.
            protocol_voltage_grid(spec)
            specs.append(spec)
    if len(specs) != 4:
        raise ValueError("G2/G3 execution must contain exactly four ramps")
    return specs


def _filtered_operator_config(config: Mapping[str, Any]) -> dict[str, Any]:
    filtered = copy.deepcopy(dict(config))
    filtered["contexts"] = {
        context_id: copy.deepcopy(dict(config["contexts"][context_id]))
        for context_id in NEW_CONTEXT_IDS
    }
    return filtered


def _disambiguate_endpoint_preparation_ids(run: ProtocolRun) -> None:
    """Prevent a failed cooling endpoint attempt shadowing its accepted retry."""

    coarse_ids = {point.point_id for point in run.coarse_points}
    occupied = set(coarse_ids)
    for index, point in enumerate(run.preparation_points):
        if point.point_id not in occupied:
            occupied.add(point.point_id)
            continue
        stem = f"{point.point_id}_preparation_attempt_{index + 1:02d}"
        candidate = stem
        suffix = 1
        while candidate in occupied:
            suffix += 1
            candidate = f"{stem}_{suffix:02d}"
        point.point_id = candidate
        occupied.add(candidate)


def _execute_protocol_ramps(
    *,
    specs: Sequence[ProtocolSpec],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    config: Mapping[str, Any],
) -> list[ProtocolRun]:
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
            _disambiguate_endpoint_preparation_ids(run)
            runs.append(run)

        for run in runs:
            if not run.completed or run.event is None:
                continue
            refine_protocol_event(
                run=run,
                operator=operators[run.spec.context_id],
                solver_config=config["solver"],
                validity_gates=config["validity_gates"],
                jump_config=config["jump_detection"],
            )
            if run.event is None or not run.event.resolved:
                continue
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
    return runs


def _pre_stability_failures(
    runs: Sequence[ProtocolRun], config: Mapping[str, Any]
) -> list[str]:
    failures: list[str] = []
    minimum_fraction = float(
        config["validity_gates"]["minimum_valid_fraction_per_ramp"]
    )
    for run in runs:
        valid_count = sum(point.valid for point in run.coarse_points)
        valid_fraction = valid_count / max(run.expected_coarse_points, 1)
        endpoints_valid = bool(
            run.coarse_points
            and run.coarse_points[0].valid
            and len(run.coarse_points) == run.expected_coarse_points
            and run.coarse_points[-1].valid
        )
        if not run.completed or valid_fraction < minimum_fraction:
            failures.append(f"{run.spec.protocol_id}:incomplete_or_below_valid_fraction")
        if not run.endpoint_pass or not endpoints_valid:
            failures.append(f"{run.spec.protocol_id}:endpoint_invalid")
        if run.event is not None:
            if not run.event.resolved:
                failures.append(f"{run.spec.protocol_id}:event_not_resolved")
            elif run.half_step_event_pre is None or run.half_step_event_post is None:
                failures.append(f"{run.spec.protocol_id}:half_step_event_not_reproduced")

    refinement_count = sum(
        run.event.refinement_solve_count if run.event is not None else 0
        for run in runs
    ) + sum(
        point.point_kind == "half_step_event_refinement"
        for run in runs
        for point in run.half_step_points
    )
    maximum_refinements = int(
        config["jump_detection"].get("maximum_total_refinement_solves", 24)
    )
    if refinement_count > maximum_refinements:
        failures.append("event_refinement_budget_exceeded")
    return failures


def _stability_candidates(
    runs: Sequence[ProtocolRun],
    *,
    ambient_temperature_K: float,
) -> tuple[
    list[ProtocolPoint],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    """Select the frozen <=20 new-context stability states and map aliases."""

    candidates: list[ProtocolPoint] = []
    roles: dict[str, list[str]] = {}
    aliases: dict[str, list[str]] = {}
    representatives: dict[tuple[str, str, float], list[ProtocolPoint]] = {}

    def add(point: ProtocolPoint | None, role: str) -> None:
        if point is None:
            return
        key = (point.context_id, point.branch_label, round(point.voltage_V, 12))
        representative = next(
            (
                existing
                for existing in representatives.get(key, [])
                if _temperature_rise_relative_difference(
                    existing.result.temperature_K,
                    point.result.temperature_K,
                    ambient_temperature_K,
                )
                <= STATE_EQUIVALENCE_TOLERANCE
            ),
            None,
        )
        if representative is None:
            representatives.setdefault(key, []).append(point)
            candidates.append(point)
            representative = point
        roles.setdefault(representative.point_id, [])
        if role not in roles[representative.point_id]:
            roles[representative.point_id].append(role)
        aliases.setdefault(representative.point_id, [])
        if point.point_id not in aliases[representative.point_id]:
            aliases[representative.point_id].append(point.point_id)

    for run in runs:
        if len(run.coarse_points) != run.expected_coarse_points:
            continue
        add(run.coarse_points[0], "start_endpoint")
        add(run.coarse_points[-1], "end_endpoint")
        add(
            run.coarse_points[REPRESENTATIVE_COARSE_INDEX],
            "representative_mid_protocol_state",
        )
        if run.event is not None:
            add(run.event.refined_pre, "last_pre_switch")
            add(run.event.refined_post, "first_post_switch")
            add(run.half_step_event_pre, "half_step_pre_switch")
            add(run.half_step_event_post, "half_step_post_switch")
    return candidates, roles, aliases


def _evaluate_new_context_stability(
    *,
    runs: Sequence[ProtocolRun],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    config: Mapping[str, Any],
    repository_root: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, list[str]],
    int,
    str,
]:
    candidates, roles, aliases = _stability_candidates(
        runs,
        ambient_temperature_K=float(config["reference"]["ambient_temperature_K"]),
    )
    configured_maximum = int(
        config["stability"].get(
            "maximum_new_context_states",
            config["stability"].get(
                "maximum_states", MAXIMUM_NEW_STABILITY_STATES
            ),
        )
    )
    if len(candidates) > configured_maximum:
        return (
            [],
            {},
            roles,
            len(candidates),
            "required_stability_candidates_exceed_configured_20_state_cap",
        )

    device_capacity, cell_capacity = load_device_thermal_capacitance(
        config,
        repository_root,
        cell_count=next(iter(operators.values())).cell_count,
    )
    runs_by_protocol = {run.spec.protocol_id: run for run in runs}
    rows: list[dict[str, Any]] = []
    by_point: dict[str, dict[str, Any]] = {}
    for point in candidates:
        run = runs_by_protocol[point.protocol_id]
        metrics = evaluate_physical_stability(
            operator=operators[point.context_id],
            point=point,
            sink_amplitude=run.spec.sink_amplitude,
            cell_thermal_capacity_J_K=cell_capacity,
            stability_config=config["stability"],
        )
        for alias_id in aliases[point.point_id]:
            by_point[alias_id] = metrics
        rows.append(
            {
                "state_id": point.point_id,
                "alias_point_ids": "|".join(aliases[point.point_id]),
                "protocol_id": point.protocol_id,
                "context_id": point.context_id,
                "branch_label": point.branch_label,
                "device_voltage_V": point.voltage_V,
                "roles": "|".join(roles[point.point_id]),
                "temperature_sha256": _temperature_sha256(
                    point.result.temperature_K
                ),
                "device_thermal_capacitance_J_K": device_capacity,
                "cell_thermal_capacitance_J_K": cell_capacity,
                "eigenvalue_count": metrics["eigenvalue_count"],
                "maximum_real_eigenvalue_per_s": metrics[
                    "maximum_real_eigenvalue_per_s"
                ],
                "spectral_radius_per_s": metrics["spectral_radius_per_s"],
                "relative_stability_margin": metrics[
                    "relative_stability_margin"
                ],
                "stability_class": metrics["stability_class"],
                "positive_real_eigenvalue_count": metrics[
                    "positive_real_eigenvalue_count"
                ],
                "finite": metrics["finite"],
                "manuscript_eligible": bool(
                    metrics["stability_class"] == "stable" and point.valid
                ),
                "thermal_mass_interpretation": config["source_role"][
                    "interpretation"
                ],
                "spectrum_origin": "new_context_formal_execution",
            }
        )
    return rows, by_point, roles, len(candidates), ""


def _sensitivity_rows(
    *,
    runs: Sequence[ProtocolRun],
    stability_by_point: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    sensitivity_config = {
        **config["step_sensitivity"],
        "refinement_voltage_resolution_V": config["jump_detection"][
            "refinement_voltage_resolution_V"
        ],
    }
    return [
        event_step_sensitivity(
            run=run,
            stability_by_point=stability_by_point,
            sensitivity_config=sensitivity_config,
        )
        for run in runs
    ]


def _context_summaries(
    *,
    runs: Sequence[ProtocolRun],
    stability_rows: Sequence[Mapping[str, Any]],
    sensitivity_rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    minimum_fraction = float(
        config["validity_gates"]["minimum_valid_fraction_per_ramp"]
    )
    sensitivity_by_protocol = {
        str(row["protocol_id"]): row for row in sensitivity_rows
    }
    result: dict[str, dict[str, Any]] = {}
    for context_id in NEW_CONTEXT_IDS:
        context_runs = [run for run in runs if run.spec.context_id == context_id]
        valid_fractions = {
            run.spec.branch_label: (
                sum(point.valid for point in run.coarse_points)
                / max(run.expected_coarse_points, 1)
            )
            for run in context_runs
        }
        endpoint_pass = bool(
            len(context_runs) == 2
            and all(
                run.endpoint_pass
                and len(run.coarse_points) == run.expected_coarse_points
                and run.coarse_points[-1].valid
                for run in context_runs
            )
        )
        ramp_pass = bool(
            len(context_runs) == 2
            and all(
                run.completed
                and valid_fractions[run.spec.branch_label] >= minimum_fraction
                for run in context_runs
            )
        )
        event_pass = all(
            run.event is None or run.event.resolved for run in context_runs
        )
        context_sensitivity = [
            sensitivity_by_protocol[run.spec.protocol_id] for run in context_runs
        ]
        # No detected event is explicitly N/A and therefore neutral.
        sensitivity_pass = all(
            not bool(row.get("executed", False)) or bool(row.get("pass", False))
            for row in context_sensitivity
        )
        context_stability = [
            row for row in stability_rows if row["context_id"] == context_id
        ]
        stability_pass = bool(
            context_stability
            and all(
                bool(row["finite"]) and row["stability_class"] == "stable"
                for row in context_stability
            )
        )
        result[context_id] = {
            "context_id": context_id,
            "ramp_count": len(context_runs),
            "valid_fraction_by_branch": valid_fractions,
            "ramps_pass": ramp_pass,
            "endpoints_pass": endpoint_pass,
            "event_count": sum(run.event is not None for run in context_runs),
            "resolved_event_count": sum(
                run.event is not None and run.event.resolved for run in context_runs
            ),
            "events_pass": event_pass,
            "step_sensitivity_pass": sensitivity_pass,
            "stability_state_count": len(context_stability),
            "stable_state_count": sum(
                row["stability_class"] == "stable" for row in context_stability
            ),
            "unstable_state_count": sum(
                row["stability_class"] == "unstable" for row in context_stability
            ),
            "indeterminate_state_count": sum(
                row["stability_class"] == "indeterminate"
                for row in context_stability
            ),
            "stability_pass": stability_pass,
            "qualified": bool(
                ramp_pass
                and endpoint_pass
                and event_pass
                and sensitivity_pass
                and stability_pass
            ),
        }
    return result


def _save_runs_and_rows(
    *,
    runs: Sequence[ProtocolRun],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    stability_by_point: Mapping[str, Mapping[str, Any]],
    roles: Mapping[str, Sequence[str]],
    repository_root: Path,
    processed_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    resolved_repository = repository_root.resolve()
    resolved_processed = (
        processed_root.resolve()
        if processed_root.is_absolute()
        else (repository_root / processed_root).resolve()
    )
    try:
        resolved_processed.relative_to(resolved_repository)
    except ValueError as error:
        raise ValueError("processed_root must remain inside the repository") from error

    physics_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    npz_paths: dict[str, str] = {}
    for run in runs:
        path = resolved_processed / f"{run.spec.protocol_id}.npz"
        relative_path = path.relative_to(resolved_repository)
        index_by_point = save_protocol_npz(
            path,
            run=run,
            operator=operators[run.spec.context_id],
            stability_by_point=stability_by_point,
        )
        npz_paths[run.spec.protocol_id] = relative_path.as_posix()
        manifest = _manifest_row(run, relative_path)
        manifest.update(
            {
                "source_role": "new_factorial_context_execution",
                "historical_protocol_reused": False,
            }
        )
        manifest_rows.append(manifest)
        for point in all_run_points(run):
            row = point_to_row(
                point,
                operator=operators[run.spec.context_id],
                point_index_in_npz=index_by_point[point.point_id],
                stability=stability_by_point.get(point.point_id),
                role="|".join(roles.get(point.point_id, [point.point_kind])),
            )
            row.update(
                {
                    "source_role": "new_factorial_context_execution",
                    "historical_protocol_reused": False,
                }
            )
            physics_rows.append(row)
    return physics_rows, manifest_rows, npz_paths


def execute_new_context_protocols(
    config: Mapping[str, Any],
    repository_root: Path,
    processed_root: Path,
) -> dict[str, Any]:
    """Execute and gate only G2/G3, saving their complete protocol NPZ files.

    A failed physical, event, sensitivity, or stability gate is returned as
    ``NO_GO_PROTOCOL_FACTORIAL_CONTEXT_REFERENCE``.  Contract drift raises a
    ``ValueError`` before any solve.  G0/G1 are never loaded or executed here.
    """

    _validate_new_context_contract(config)
    specs = _new_context_specs(config)
    operator_config = _filtered_operator_config(config)
    operators = _build_protocol_operators(operator_config, repository_root)
    if set(operators) != set(NEW_CONTEXT_IDS):
        raise ValueError("operator construction escaped the G2/G3 context filter")
    runs = _execute_protocol_ramps(specs=specs, operators=operators, config=config)

    failures = _pre_stability_failures(runs, config)
    stability_rows: list[dict[str, Any]] = []
    stability_by_point: dict[str, dict[str, Any]] = {}
    roles: dict[str, list[str]] = {}
    required_stability_state_count = 0
    if not failures:
        (
            stability_rows,
            stability_by_point,
            roles,
            required_stability_state_count,
            stability_failure,
        ) = _evaluate_new_context_stability(
            runs=runs,
            operators=operators,
            config=config,
            repository_root=repository_root,
        )
        if stability_failure:
            failures.append(stability_failure)

    sensitivity_rows = _sensitivity_rows(
        runs=runs,
        stability_by_point=stability_by_point,
        config=config,
    )
    context_summaries = _context_summaries(
        runs=runs,
        stability_rows=stability_rows,
        sensitivity_rows=sensitivity_rows,
        config=config,
    )
    if not all(item["qualified"] for item in context_summaries.values()):
        failures.append("one_or_more_new_context_gates_failed")

    physics_rows, manifest_rows, npz_paths = _save_runs_and_rows(
        runs=runs,
        operators=operators,
        stability_by_point=stability_by_point,
        roles=roles,
        repository_root=repository_root,
        processed_root=processed_root,
    )

    primary_refinements = sum(
        run.event.refinement_solve_count if run.event is not None else 0
        for run in runs
    )
    half_refinements = sum(
        point.point_kind == "half_step_event_refinement"
        for run in runs
        for point in run.half_step_points
    )
    unique_failures = list(dict.fromkeys(failures))
    gate_pass = not unique_failures
    summary = {
        "stage": "factorial_context_reference",
        "context_ids": list(NEW_CONTEXT_IDS),
        "main_protocol_ramp_count": len(runs),
        "completed_protocol_ramp_count": sum(run.completed for run in runs),
        "main_protocol_point_count": sum(
            len(run.coarse_points) for run in runs
        ),
        "valid_main_protocol_point_count": sum(
            point.valid for run in runs for point in run.coarse_points
        ),
        "event_count": sum(run.event is not None for run in runs),
        "resolved_event_count": sum(
            run.event is not None and run.event.resolved for run in runs
        ),
        "event_refinement_solve_count": primary_refinements + half_refinements,
        "half_step_continuation_solve_count": sum(
            point.point_kind == "half_step_continuation"
            for run in runs
            for point in run.half_step_points
        ),
        "required_stability_state_count": required_stability_state_count,
        "new_stability_spectrum_evaluation_count": len(stability_rows),
        "new_stability_budget_maximum": MAXIMUM_NEW_STABILITY_STATES,
        "stable_state_count": sum(
            row["stability_class"] == "stable" for row in stability_rows
        ),
        "unstable_state_count": sum(
            row["stability_class"] == "unstable" for row in stability_rows
        ),
        "indeterminate_state_count": sum(
            row["stability_class"] == "indeterminate" for row in stability_rows
        ),
        "step_sensitivity_event_count": sum(
            bool(row.get("executed", False)) for row in sensitivity_rows
        ),
        "step_sensitivity_all_executed_events_pass": all(
            not bool(row.get("executed", False)) or bool(row.get("pass", False))
            for row in sensitivity_rows
        ),
        "contexts": context_summaries,
        "new_context_reference_gate_pass": gate_pass,
        "surrogate_training_eligible": gate_pass,
        "stage_disposition": (
            "PASS_PROTOCOL_FACTORIAL_CONTEXT_REFERENCE"
            if gate_pass
            else "NO_GO_PROTOCOL_FACTORIAL_CONTEXT_REFERENCE"
        ),
        "failure_reasons": unique_failures,
        "root_identifier_used": False,
        "root_averaging_used": False,
        "historical_G0_G1_ramps_reexecuted": 0,
        "protocol_npz_paths": npz_paths,
    }
    return {
        "runs": runs,
        "operators": operators,
        "stability_rows": stability_rows,
        "stability_by_point": stability_by_point,
        "sensitivity_rows": sensitivity_rows,
        "physics_rows": physics_rows,
        "manifest_rows": manifest_rows,
        "summary": summary,
    }
