"""Non-voting Stage A audit for exact S2 nonlinear block condensation.

The audit does not advance a trajectory or call a nonlinear solver.  It uses
the production residual definition to verify that, for a prescribed candidate
temperature and previous full state, the branch, conductive-state, and circuit
blocks can be reconstructed algebraically to roundoff.  The temperature block
remains the only nonlinear residual to solve in a future implementation.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
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
from pinnpcm.solvers import geophase_phase1_v2_implicit as production


SCHEMA_VERSION = "geophase_exact_block_condensation_stage_a_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Stage A config must contain a mapping")
    return payload


def _validate_frozen_inputs(config: Mapping[str, Any]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in config["frozen_inputs"]:
        relative = Path(str(item["path"]))
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"missing frozen Stage A input: {relative}")
        observed = _sha256(path)
        expected = str(item["sha256"])
        if observed != expected:
            raise ValueError(
                f"frozen Stage A input drifted: {relative}: {observed} != {expected}"
            )
        verified.append(
            {
                "path": relative.as_posix(),
                "sha256": observed,
            }
        )
    return verified


def _residual_block_norms(residual: np.ndarray, cells: int) -> dict[str, float]:
    values = np.asarray(residual, dtype=float)
    return {
        "temperature": float(np.max(np.abs(values[:cells]))),
        "conductive_state": float(np.max(np.abs(values[cells : 2 * cells]))),
        "branch": float(np.max(np.abs(values[2 * cells : 3 * cells]))),
        "circuit": float(abs(values[-1])),
    }


def evaluate_exact_condensation(
    *,
    candidate_temperature_K: np.ndarray,
    old_state: production.S2State,
    input_voltage_V: float,
    dt_s: float,
    grid,
    closure,
    fields,
    scientific_config: Mapping[str, Any],
    cache: production.S2SolverCache,
) -> dict[str, float]:
    """Reconstruct auxiliary blocks and evaluate the production full residual."""

    temperature = np.asarray(candidate_temperature_K, dtype=float)
    if temperature.shape != grid.shape:
        raise ValueError("candidate temperature must match the frozen grid")
    if not np.isfinite(temperature).all() or not np.isfinite(dt_s) or dt_s <= 0.0:
        raise ValueError("candidate temperature and positive dt must be finite")

    heating, cooling = closure.branch_activations(
        temperature, old_state.temperature_K, dt_s
    )
    ratio_b = dt_s / closure.branch_relaxation_s
    branch = (
        old_state.branch_memory + ratio_b * (heating - cooling)
    ) / (1.0 + ratio_b * (heating + cooling))

    equilibrium = closure.equilibrium_state(temperature, branch)
    ratio_s = dt_s / closure.state_relaxation_s
    conductive = (
        old_state.conductive_state + ratio_s * equilibrium
    ) / (1.0 + ratio_s)

    conductivity = closure.conductivity_S_m(temperature, conductive)
    unit_electrical, _ = production._electrical_unit_and_actual(
        grid=grid,
        conductivity_S_m=conductivity,
        actual_voltage_V=1.0,
        topology=cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=None,
    )
    load_resistance_ohm, capacitance_F = production._circuit_parameters(
        scientific_config
    )
    voltage = (
        capacitance_F / dt_s * old_state.device_voltage_V
        + input_voltage_V / load_resistance_ohm
    ) / (
        capacitance_F / dt_s
        + 1.0 / load_resistance_ohm
        + unit_electrical.source_current_A
    )

    vector = production._pack(temperature, conductive, branch, voltage)
    residual = production._scaled_residual(
        vector,
        old_state=old_state,
        input_voltage_V=float(input_voltage_V),
        dt_s=float(dt_s),
        grid=grid,
        closure=closure,
        fields=fields,
        lateral_matrix=cache.lateral_matrix,
        thermal_linear_solver=None,
        electrical_topology=cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=None,
        load_resistance_ohm=load_resistance_ohm,
        capacitance_F=capacitance_F,
    )
    blocks = _residual_block_norms(residual, grid.nx * grid.ny)
    auxiliary = max(
        blocks["conductive_state"], blocks["branch"], blocks["circuit"]
    )
    return {
        **blocks,
        "auxiliary": float(auxiliary),
        "full": float(max(blocks.values())),
        "device_voltage_V": float(voltage),
    }


def _trace_statistics(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    endpoints = np.asarray(payload["accepted_endpoint_times_s"], dtype=float)
    accepted_dt_s = np.diff(np.concatenate(([0.0], endpoints)))
    diagnostics = payload["diagnostics"]
    counts = Counter(round(float(value) * 1.0e12, 6) for value in accepted_dt_s)
    distribution = [
        {
            "dt_ps": float(dt_ps),
            "accepted_step_count": int(count),
            "accepted_step_fraction": float(count / accepted_dt_s.size),
        }
        for dt_ps, count in sorted(counts.items())
    ]
    at_minimum = int(counts[min(counts)])
    at_or_below_312p5_ps = sum(
        count for dt_ps, count in counts.items() if dt_ps <= 312.5 + 1.0e-6
    )
    accepted_steps = int(diagnostics["accepted_steps"])
    fallback_steps = int(diagnostics["fallback_steps"])
    statistics = {
        "source_sha256": _sha256(path),
        "accepted_steps": accepted_steps,
        "rejected_steps": int(diagnostics["rejected_steps"]),
        "fallback_steps": fallback_steps,
        "fallback_step_fraction": float(fallback_steps / accepted_steps),
        "fallback_free_steps": int(accepted_steps - fallback_steps),
        "growth_events": int(diagnostics["growth_events"]),
        "embedded_error_rejections": int(
            diagnostics["embedded_error_rejections"]
        ),
        "integrity_rejections": int(diagnostics["integrity_rejections"]),
        "minimum_accepted_step_s": float(accepted_dt_s.min()),
        "median_accepted_step_s": float(np.median(accepted_dt_s)),
        "maximum_accepted_step_s": float(accepted_dt_s.max()),
        "minimum_step_fraction": float(at_minimum / accepted_steps),
        "at_or_below_0p3125ns_fraction": float(
            at_or_below_312p5_ps / accepted_steps
        ),
        "total_coupled_solves": int(diagnostics["total_coupled_solves"]),
        "coupled_solves_per_accepted_step": float(
            diagnostics["total_coupled_solves"] / accepted_steps
        ),
        "fallback_picard_iterations": int(
            diagnostics["fallback_picard_iterations"]
        ),
        "fallback_picard_iterations_per_fallback_step": float(
            diagnostics["fallback_picard_iterations"] / fallback_steps
        ),
        "controller_growth_requires_no_fallback": True,
        "fallback_directly_halves_interval": False,
        "only_rejected_candidates_halve_interval": True,
    }
    return statistics, distribution


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty Stage A table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_stage_a(config_path: Path, output_root: Path) -> dict[str, Any]:
    config = _load_config(config_path)
    verified_inputs = _validate_frozen_inputs(config)
    scientific = resolved_s2_config()
    level = int(config["microbench"]["spatial_level"])
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    dt_grid_ns = [float(value) for value in config["microbench"]["dt_grid_ns"]]

    residual_rows: list[dict[str, Any]] = []
    for relative in config["microbench"]["failure_replay_paths"]:
        path = ROOT / str(relative)
        source = json.loads(path.read_text(encoding="utf-8"))
        replay = source["replay"]
        old_state = _state_from_replay(replay["previous_state"])
        for dt_ns in dt_grid_ns:
            started = perf_counter()
            blocks = evaluate_exact_condensation(
                candidate_temperature_K=old_state.temperature_K,
                old_state=old_state,
                input_voltage_V=float(replay["full_input_voltage_V"]),
                dt_s=dt_ns * 1.0e-9,
                grid=grid,
                closure=closure,
                fields=fields,
                scientific_config=scientific,
                cache=cache,
            )
            residual_rows.append(
                {
                    "source_path": Path(str(relative)).as_posix(),
                    "source_time_s": float(old_state.time_s),
                    "dt_ns": float(dt_ns),
                    "temperature_residual_inf": blocks["temperature"],
                    "conductive_state_residual_inf": blocks["conductive_state"],
                    "branch_residual_inf": blocks["branch"],
                    "circuit_residual_inf": blocks["circuit"],
                    "auxiliary_residual_inf": blocks["auxiliary"],
                    "full_residual_inf": blocks["full"],
                    "evaluation_wall_s": float(perf_counter() - started),
                }
            )

    trace_path = ROOT / str(config["microbench"]["nls_v1_trace_path"])
    trace_statistics, trace_distribution = _trace_statistics(trace_path)
    auxiliary_limit = float(
        config["gates"]["auxiliary_scaled_residual_inf_max"]
    )
    maximum_auxiliary = max(
        float(row["auxiliary_residual_inf"]) for row in residual_rows
    )
    condensation_identity_pass = bool(maximum_auxiliary <= auxiliary_limit)
    terminal_state = (
        "GO_EXACT_BLOCK_CONDENSATION_PROTOTYPE_ONLY"
        if condensation_identity_pass
        else "STOP_EXACT_BLOCK_CONDENSATION_IDENTITY_FAIL"
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "task_id": str(config["task_id"]),
        "analysis_id": str(config["analysis_id"]),
        "terminal_state": terminal_state,
        "validity": "valid_bounded_non_voting_stage_a",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "nonlinear_or_trajectory_execution_count": 0,
        "solver_source_modified": False,
        "verified_frozen_inputs": verified_inputs,
        "mathematical_disposition": {
            "global_temperature_only_markov_state": False,
            "within_step_temperature_primary_static_condensation": True,
            "history_retained_in_previous_s_b_Vd": True,
            "learned_or_tabulated_closure_required": False,
            "full_unknown_count": int(3 * grid.nx * grid.ny + 1),
            "reduced_nonlinear_unknown_count": int(grid.nx * grid.ny),
            "nonlinear_unknown_reduction_fraction": float(
                1.0 - (grid.nx * grid.ny) / (3 * grid.nx * grid.ny + 1)
            ),
            "maximum_auxiliary_scaled_residual_inf": maximum_auxiliary,
            "auxiliary_scaled_residual_inf_limit": auxiliary_limit,
            "identity_pass": condensation_identity_pass,
        },
        "formulae": {
            "branch": "b_np1=(b_n+r_b*(h-c))/(1+r_b*(h+c))",
            "conductive_state": "s_np1=(s_n+r_s*s_eq(T_np1,b_np1))/(1+r_s)",
            "circuit": "Vd_np1=((C/dt)*Vd_n+Vin/R)/((C/dt)+1/R+Gdev(T_np1,s_np1))",
            "remaining_equation": "thermal_backward_euler_residual_in_T_np1",
        },
        "microbench": {
            "source_state_count": len(
                config["microbench"]["failure_replay_paths"]
            ),
            "dt_count": len(dt_grid_ns),
            "row_count": len(residual_rows),
            "dt_grid_ns": dt_grid_ns,
        },
        "frozen_nls_v1_trace": trace_statistics,
        "coverage": {
            "quiescent_9V_frozen_trace": "available",
            "frozen_failure_replays": 2,
            "transition_12p5V_frozen_trace": "unavailable",
            "reduced_solver_convergence": "unassessed",
            "reduced_solver_fallback_fraction": "unassessed",
            "reduced_solver_timestep_growth": "unassessed",
            "reduced_solver_runtime": "unassessed",
        },
        "claim_boundary": {
            "supported": "exact algebraic condensability of auxiliary residual blocks under the frozen backward-Euler equations",
            "qualified_supported": "fallback suppresses controller growth on the frozen NLS-v1 path; rejection alone halves the interval",
            "failed_but_informative": "NLS-v1 frozen performance qualification remains rejected",
            "forbidden": [
                "reduced solver is faster or convergent",
                "12.5 V transition performance",
                "S0 or Phase 1 PASS or FAIL",
                "C01 or PINN conclusions",
                "experimental validation",
            ],
        },
        "next_step": "new identity exact-condensation prototype with unchanged 1e-8 full residual and defect gates",
    }

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "exact_condensation_residuals.csv", residual_rows)
    _write_csv(output_root / "nls_v1_trace_dt_distribution.csv", trace_distribution)
    (output_root / "stage_a_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


__all__ = ["evaluate_exact_condensation", "run_stage_a"]
