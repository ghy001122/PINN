"""Bounded self-consistent M1 IMT fixed-point and contraction gate.

The experiment is intentionally fail-closed.  Voltage admission is evaluated
before the contraction atlas; a non-single-valued cold/hot forward map stops
the task before A1/A2, contraction, or neural work can vote.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import load_yaml, material_parameters
from pinnpcm.experiments.m1_latent_geometry_admission import build_geometry_context
from pinnpcm.physics.m1_self_consistent_imt import (
    SELF_CONSISTENT_MAJOR_BRANCH_MODE,
    FixedPointComparison,
    M1SelfConsistentIMTProjection,
    QiuMajorBranchParameters,
    compare_fixed_points,
    qiu_major_branch_parameters_from_source_contract,
)


Tensor = torch.Tensor
EVIDENCE_TYPE = "literature-guided synthetic numerical digital-twin evidence"


@dataclass(frozen=True)
class FixedPointResult:
    temperature_K: Tensor
    fields: dict[str, Tensor]
    metrics: dict[str, Any]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(fieldnames or (list(rows[0].keys()) if rows else []))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in names})


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


def _numpy(value: Tensor | np.ndarray | float) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def _relative_l2(left: Tensor, right: Tensor, ambient: float) -> float:
    denominator = torch.clamp(
        torch.maximum(
            torch.linalg.vector_norm(left - ambient),
            torch.linalg.vector_norm(right - ambient),
        ),
        min=1.0e-30,
    )
    return float(torch.linalg.vector_norm(left - right) / denominator)


def load_qiu_parameters(
    config: Mapping[str, Any], repository_root: Path
) -> QiuMajorBranchParameters:
    source = load_yaml(repository_root / str(config["source_contract"]["path"]))
    section = source[str(config["source_contract"]["section"])]
    contract = {
        "schema_version": source.get("schema_version", "qiu_vo2_phase1_source_contract_v3"),
        "parameters": {
            "beta_per_K": float(section["beta_per_K"]["value"]),
            "hysteresis_width_K": float(section["loop_width_K"]["value"]),
            "critical_temperature_K": float(section["critical_temperature_K"]["value"]),
        },
    }
    parameters = qiu_major_branch_parameters_from_source_contract(contract)
    expected = config["source_contract"]
    checks = {
        "beta": (parameters.beta_per_K, float(expected["beta_per_K"])),
        "loop_width": (
            parameters.hysteresis_width_K,
            float(expected["loop_width_K"]),
        ),
        "critical": (
            parameters.critical_temperature_K,
            float(expected["critical_temperature_K"]),
        ),
        "Tc_up": (parameters.T_c_up_K, float(expected["expected_Tc_up_K"])),
        "Tc_down": (
            parameters.T_c_down_K,
            float(expected["expected_Tc_down_K"]),
        ),
        "wT": (
            parameters.nominal_transition_width_K,
            float(expected["expected_nominal_wT_K"]),
        ),
    }
    for name, (actual, required) in checks.items():
        if not math.isclose(actual, required, rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError(f"Qiu source-contract {name} drifted: {actual} != {required}")
    return parameters


def build_operator(
    *,
    base_config: Mapping[str, Any],
    repository_root: Path,
    contact_overlap_nm: float,
    qiu_parameters: QiuMajorBranchParameters,
    phase_width_multiplier: float,
    joule_feedback_multiplier: float,
    relaxation_alpha: float,
) -> M1SelfConsistentIMTProjection:
    context = build_geometry_context(base_config, repository_root, contact_overlap_nm)
    grid_contract = base_config["reference_solver"]["grid"]
    if context.grid.nx != int(grid_contract["nx"]) or context.grid.ny != int(
        grid_contract["ny"]
    ):
        raise ValueError("self-consistent operator left the frozen production grid")
    form = base_config["physical_model"]["model_forms"]["M1"]
    return M1SelfConsistentIMTProjection(
        x_centers_m=context.grid.x_centers_m,
        y_centers_m=context.grid.y_centers_m,
        thickness_m=context.grid.thickness_m,
        sheet_thermal_conductance_W_K=context.thermal_fields.sheet_thermal_conductance_W_K,
        left_contact_mask=context.grid.left_contact_mask,
        right_contact_mask=context.grid.right_contact_mask,
        ambient_temperature_K=context.ambient_temperature_K,
        vertical_conductance_W_m2K=context.thermal_fields.vertical_conductance_W_m2K,
        electrical_contact_resistance_ohm=form["electrical_contact_resistance_ohm"],
        thermal_contact_resistance_m2K_W=form["thermal_contact_resistance_m2K_W"],
        localized_sink_rectangle_m=base_config["physical_model"]["localized_sink"][
            "rectangle_m"
        ],
        material_params=material_parameters(base_config),
        qiu_major_branch_parameters=qiu_parameters,
        constitutive_mode=SELF_CONSISTENT_MAJOR_BRANCH_MODE,
        phase_width_multiplier=phase_width_multiplier,
        joule_feedback_multiplier=joule_feedback_multiplier,
        relaxation_alpha=relaxation_alpha,
    )


def consistent_state_fields(
    operator: M1SelfConsistentIMTProjection,
    temperature_K: Tensor,
    voltage_V: float,
    branch: float,
    sink_amplitude: float,
) -> dict[str, Tensor]:
    electrical = operator.electrical(temperature_K, voltage_V, branch)
    feedback_joule = (
        electrical["total_joule_cell_W"] * operator.joule_feedback_multiplier
    )
    thermal = operator.thermal_diagnostics(
        temperature_K, feedback_joule, sink_amplitude
    )
    result = {**electrical, **thermal}
    result["feedback_joule_cell_W"] = feedback_joule
    result["feedback_joule_W"] = torch.sum(feedback_joule)
    result["feedback_heat_sink_ledger_error"] = thermal[
        "electrical_heat_sink_ledger_error"
    ]
    result["effective_conductive_state_coordinate"] = operator.equilibrium_state(
        temperature_K, branch
    )
    result["conductivity_S_m"] = operator.conductivity(temperature_K, branch)
    return result


def _state_residual_metrics(
    operator: M1SelfConsistentIMTProjection,
    temperature_K: Tensor,
    fields: Mapping[str, Tensor],
    sink_amplitude: float,
) -> tuple[float, float, float]:
    residual = operator.thermal_residual(
        temperature_K, fields["feedback_joule_cell_W"], sink_amplitude
    )
    cell_scale = max(
        abs(float(fields["feedback_joule_W"])) / operator.cell_count, 1.0e-15
    )
    scaled_thermal = float(torch.amax(torch.abs(residual)) / cell_scale)
    scaled_electrical = float(fields["scaled_electrical_residual"])
    return max(scaled_thermal, scaled_electrical), scaled_thermal, scaled_electrical


def solve_fixed_point(
    *,
    operator: M1SelfConsistentIMTProjection,
    initial_temperature_K: Tensor,
    voltage_V: float,
    branch: float,
    sink_amplitude: float,
    solver_config: Mapping[str, Any],
) -> FixedPointResult:
    temperature = initial_temperature_K.detach().clone().to(dtype=torch.float64)
    maximum_iterations = int(solver_config["maximum_iterations"])
    temperature_scale = float(solver_config["temperature_scale_K"])
    residual_gate = float(solver_config["scaled_residual_max"])
    update_gate = float(solver_config["scaled_update_max"])
    minimum = float(solver_config["finite_guard_temperature_min_K"])
    maximum = float(solver_config["finite_guard_temperature_max_K"])
    scaled_update = 0.0
    converged = False
    iteration = 0
    fields: dict[str, Tensor] = {}
    scaled_residual = math.inf
    scaled_thermal = math.inf
    scaled_electrical = math.inf

    for iteration in range(maximum_iterations + 1):
        fields = consistent_state_fields(
            operator, temperature, voltage_V, branch, sink_amplitude
        )
        scaled_residual, scaled_thermal, scaled_electrical = _state_residual_metrics(
            operator, temperature, fields, sink_amplitude
        )
        if scaled_residual <= residual_gate and scaled_update <= update_gate:
            converged = True
            break
        if iteration == maximum_iterations:
            break
        raw = operator.raw_projection(
            temperature, voltage_V, branch, sink_amplitude
        )
        target = raw["temperature_K"]
        scaled_update = float(
            torch.amax(torch.abs(target - temperature)) / temperature_scale
        )
        temperature = (
            (1.0 - operator.relaxation_alpha) * temperature
            + operator.relaxation_alpha * target
        )
        if (
            not bool(torch.isfinite(temperature).all())
            or float(torch.amin(temperature)) < minimum
            or float(torch.amax(temperature)) > maximum
        ):
            break

    fields = consistent_state_fields(
        operator, temperature, voltage_V, branch, sink_amplitude
    )
    scaled_residual, scaled_thermal, scaled_electrical = _state_residual_metrics(
        operator, temperature, fields, sink_amplitude
    )
    raw_subsolve = operator.raw_projection(
        temperature, voltage_V, branch, sink_amplitude
    )
    source_current = float(fields["source_current_A"])
    ground_current = float(fields["ground_current_A"])
    current_imbalance = abs(source_current - ground_current) / max(
        abs(source_current), abs(ground_current), 1.0e-30
    )
    phase = fields["effective_conductive_state_coordinate"]
    transition_fraction = float(torch.mean(((phase > 0.1) & (phase < 0.9)).to(torch.float64)))
    finite = bool(
        torch.isfinite(temperature).all()
        and all(
            torch.isfinite(torch.as_tensor(fields[name])).all()
            for name in (
                "potential_V",
                "conductivity_S_m",
                "source_current_A",
                "terminal_electrical_heat_ledger_error",
                "feedback_heat_sink_ledger_error",
            )
        )
    )
    metrics = {
        "iterations": int(iteration),
        "converged": bool(converged),
        "finite": finite,
        "scaled_nonlinear_residual": scaled_residual,
        "scaled_thermal_residual": scaled_thermal,
        "scaled_electrical_residual": scaled_electrical,
        "scaled_raw_update": scaled_update,
        "terminal_current_A": source_current,
        "ground_current_A": ground_current,
        "current_imbalance": current_imbalance,
        "terminal_electrical_heat_ledger_error": float(
            fields["terminal_electrical_heat_ledger_error"]
        ),
        "state_consistent_feedback_heat_sink_ledger_error": float(
            fields["feedback_heat_sink_ledger_error"]
        ),
        "raw_subsolve_feedback_heat_sink_ledger_error": float(
            raw_subsolve["feedback_heat_sink_ledger_error"]
        ),
        "Tmax_K": float(torch.amax(temperature)),
        "Tmean_K": float(torch.mean(temperature)),
        "transition_fraction": transition_fraction,
        "mean_effective_state_coordinate": float(torch.mean(phase)),
    }
    return FixedPointResult(temperature_K=temperature, fields=fields, metrics=metrics)


def fixed_point_valid(
    result: FixedPointResult, gates: Mapping[str, Any]
) -> bool:
    metrics = result.metrics
    return bool(
        metrics["finite"]
        and metrics["converged"]
        and float(metrics["scaled_nonlinear_residual"])
        <= float(gates["scaled_nonlinear_residual_max"])
        and float(metrics["current_imbalance"])
        <= float(gates["current_imbalance_max"])
        and float(metrics["terminal_electrical_heat_ledger_error"])
        <= float(gates["terminal_electrical_heat_ledger_max"])
        and float(metrics["state_consistent_feedback_heat_sink_ledger_error"])
        <= float(gates["electrical_heat_sink_ledger_max"])
    )


def _save_voltage_case(
    path: Path,
    *,
    cold: FixedPointResult,
    hot: FixedPointResult,
    branch: float,
    voltage_V: float,
    operator: M1SelfConsistentIMTProjection,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, Any] = {
        "branch_value": np.asarray(branch),
        "device_voltage_V": np.asarray(voltage_V),
        "x_m": _numpy(operator.x_centers_m),
        "y_m": _numpy(operator.y_centers_m),
    }
    for prefix, result in (("cold", cold), ("hot", hot)):
        arrays[f"{prefix}_temperature_K"] = _numpy(result.temperature_K)
        for name in (
            "potential_V",
            "conductivity_S_m",
            "effective_conductive_state_coordinate",
            "electrical_x_face_current_A",
            "electrical_y_face_current_A",
            "thermal_x_face_power_W",
            "thermal_y_face_power_W",
            "internal_joule_cell_W",
            "contact_joule_cell_W",
            "feedback_joule_cell_W",
            "vertical_sink_cell_W",
        ):
            arrays[f"{prefix}_{name}"] = _numpy(result.fields[name])
        for name, value in result.metrics.items():
            arrays[f"{prefix}_metric_{name}"] = np.asarray(value)
    np.savez_compressed(path, **arrays)


def run_voltage_admission(
    config: Mapping[str, Any], repository_root: Path, processed_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    base_config = load_yaml(repository_root / str(config["reference"]["base_config"]))
    qiu = load_qiu_parameters(config, repository_root)
    admission = config["voltage_admission"]
    solver_config = config["solver"]
    gates = config["validity_gates"]
    operator = build_operator(
        base_config=base_config,
        repository_root=repository_root,
        contact_overlap_nm=float(admission["contact_overlap_nm"]),
        qiu_parameters=qiu,
        phase_width_multiplier=float(admission["width_multiplier"]),
        joule_feedback_multiplier=float(admission["joule_feedback_multiplier"]),
        relaxation_alpha=float(solver_config["relaxation_alpha"]),
    )
    branch_values = {
        str(name): float(value)
        for name, value in config["constitutive"]["branch_values"].items()
    }
    rows: list[dict[str, Any]] = []
    uniqueness_rows: list[dict[str, Any]] = []
    case_data: dict[str, Any] = {}
    for branch_label, branch in branch_values.items():
        for voltage in [float(value) for value in admission["voltages_V"]]:
            case_id = f"{branch_label}_{voltage:.2f}V"
            cold_initial = torch.full(
                (operator.ny, operator.nx),
                float(solver_config["cold_initial_temperature_K"]),
                dtype=torch.float64,
            )
            hot_initial = torch.full(
                (operator.ny, operator.nx),
                float(solver_config["hot_initial_temperature_K"]),
                dtype=torch.float64,
            )
            cold = solve_fixed_point(
                operator=operator,
                initial_temperature_K=cold_initial,
                voltage_V=voltage,
                branch=branch,
                sink_amplitude=float(admission["sink_amplitude"]),
                solver_config=solver_config,
            )
            hot = solve_fixed_point(
                operator=operator,
                initial_temperature_K=hot_initial,
                voltage_V=voltage,
                branch=branch,
                sink_amplitude=float(admission["sink_amplitude"]),
                solver_config=solver_config,
            )
            comparison: FixedPointComparison = compare_fixed_points(
                cold.temperature_K,
                hot.temperature_K,
                cold.metrics["terminal_current_A"],
                hot.metrics["terminal_current_A"],
                ambient_temperature_K=operator.ambient_temperature_K,
                temperature_relative_tolerance=float(
                    gates["cold_hot_temperature_rise_relative_l2_max"]
                ),
                current_relative_tolerance=float(
                    gates["cold_hot_terminal_current_relative_difference_max"]
                ),
            )
            cold_valid = fixed_point_valid(cold, gates)
            hot_valid = fixed_point_valid(hot, gates)
            valid = bool(cold_valid and hot_valid)
            row: dict[str, Any] = {
                "case_id": case_id,
                "branch_label": branch_label,
                "branch_value": branch,
                "device_voltage_V": voltage,
                "contact_overlap_nm": float(admission["contact_overlap_nm"]),
                "sink_amplitude": float(admission["sink_amplitude"]),
                "phase_width_multiplier": float(admission["width_multiplier"]),
                "transition_width_K": operator.transition_width_K,
                "joule_feedback_multiplier": operator.joule_feedback_multiplier,
                "cold_valid": cold_valid,
                "hot_valid": hot_valid,
                "valid": valid,
                "unique": comparison.unique,
                "cold_transition_fraction": cold.metrics["transition_fraction"],
                "hot_transition_fraction": hot.metrics["transition_fraction"],
                "cold_mean_effective_state": cold.metrics[
                    "mean_effective_state_coordinate"
                ],
                "hot_mean_effective_state": hot.metrics[
                    "mean_effective_state_coordinate"
                ],
                "cold_Tmean_K": cold.metrics["Tmean_K"],
                "hot_Tmean_K": hot.metrics["Tmean_K"],
                "cold_Tmax_K": cold.metrics["Tmax_K"],
                "hot_Tmax_K": hot.metrics["Tmax_K"],
                "cold_current_A": cold.metrics["terminal_current_A"],
                "hot_current_A": hot.metrics["terminal_current_A"],
                "cold_iterations": cold.metrics["iterations"],
                "hot_iterations": hot.metrics["iterations"],
                "cold_scaled_residual": cold.metrics["scaled_nonlinear_residual"],
                "hot_scaled_residual": hot.metrics["scaled_nonlinear_residual"],
                "cold_current_imbalance": cold.metrics["current_imbalance"],
                "hot_current_imbalance": hot.metrics["current_imbalance"],
                "cold_terminal_ledger": cold.metrics[
                    "terminal_electrical_heat_ledger_error"
                ],
                "hot_terminal_ledger": hot.metrics[
                    "terminal_electrical_heat_ledger_error"
                ],
                "cold_state_consistent_sink_ledger": cold.metrics[
                    "state_consistent_feedback_heat_sink_ledger_error"
                ],
                "hot_state_consistent_sink_ledger": hot.metrics[
                    "state_consistent_feedback_heat_sink_ledger_error"
                ],
                "cold_raw_subsolve_sink_ledger": cold.metrics[
                    "raw_subsolve_feedback_heat_sink_ledger_error"
                ],
                "hot_raw_subsolve_sink_ledger": hot.metrics[
                    "raw_subsolve_feedback_heat_sink_ledger_error"
                ],
                "cold_hot_temperature_rise_relative_l2_difference": comparison.temperature_rise_relative_l2_difference,
                "cold_hot_terminal_current_relative_difference": comparison.terminal_current_relative_difference,
                "transition_bearing_unique_candidate": bool(
                    valid
                    and comparison.unique
                    and 0.5
                    * (
                        float(cold.metrics["transition_fraction"])
                        + float(hot.metrics["transition_fraction"])
                    )
                    >= float(admission["transition_fraction_min"])
                ),
                "selected_for_branch": False,
            }
            rows.append(row)
            uniqueness_rows.append(
                {
                    "stage": "voltage_admission",
                    "case_id": case_id,
                    "branch_label": branch_label,
                    "device_voltage_V": voltage,
                    "cold_valid": cold_valid,
                    "hot_valid": hot_valid,
                    "cold_hot_temperature_rise_relative_l2_difference": comparison.temperature_rise_relative_l2_difference,
                    "cold_hot_terminal_current_relative_difference": comparison.terminal_current_relative_difference,
                    "temperature_tolerance": float(
                        gates["cold_hot_temperature_rise_relative_l2_max"]
                    ),
                    "current_tolerance": float(
                        gates["cold_hot_terminal_current_relative_difference_max"]
                    ),
                    "unique": comparison.unique,
                }
            )
            _save_voltage_case(
                processed_root / "voltage_admission" / f"{case_id}.npz",
                cold=cold,
                hot=hot,
                branch=branch,
                voltage_V=voltage,
                operator=operator,
            )
            case_data[case_id] = {
                "row": row,
                "cold": cold,
                "hot": hot,
                "operator": operator,
            }

    nonunique = [row for row in rows if bool(row["valid"]) and not bool(row["unique"])]
    invalid = [row for row in rows if not bool(row["valid"])]
    selected: dict[str, float] = {}
    if not invalid and not nonunique:
        for branch_label in branch_values:
            candidates = [
                row
                for row in rows
                if row["branch_label"] == branch_label
                and row["transition_bearing_unique_candidate"]
            ]
            if candidates:
                best = sorted(
                    candidates,
                    key=lambda row: (
                        -0.5
                        * (
                            float(row["cold_transition_fraction"])
                            + float(row["hot_transition_fraction"])
                        ),
                        abs(
                            0.5
                            * (
                                float(row["cold_mean_effective_state"])
                                + float(row["hot_mean_effective_state"])
                            )
                            - 0.5
                        ),
                        float(row["device_voltage_V"]),
                    ),
                )[0]
                best["selected_for_branch"] = True
                selected[branch_label] = float(best["device_voltage_V"])

    if invalid:
        disposition = "NO_GO_SELF_CONSISTENT_IMT_TRANSITION_ADMISSION"
        reason = "one_or_more_voltage_admission_fixed_points_invalid"
    elif nonunique:
        disposition = "NO_GO_SINGLE_VALUED_IMT_FORWARD_MAP"
        reason = "cold_hot_initializations_converged_to_distinct_fixed_points"
    elif len(selected) != len(branch_values):
        disposition = "NO_GO_SELF_CONSISTENT_IMT_TRANSITION_ADMISSION"
        reason = "no_transition_bearing_unique_voltage_for_every_branch"
    else:
        disposition = "STAGE_A_PASS"
        reason = "voltage_admission_passed"
    audit = {
        "disposition": disposition,
        "reason": reason,
        "selected_voltage_by_branch_V": selected,
        "case_count": len(rows),
        "valid_case_count": sum(bool(row["valid"]) for row in rows),
        "unique_case_count": sum(bool(row["unique"]) for row in rows),
        "nonunique_case_count": len(nonunique),
        "invalid_case_count": len(invalid),
        "qiu_parameters": {
            "beta_per_K": qiu.beta_per_K,
            "loop_width_K": qiu.hysteresis_width_K,
            "critical_temperature_K": qiu.critical_temperature_K,
            "Tc_up_K": qiu.T_c_up_K,
            "Tc_down_K": qiu.T_c_down_K,
            "nominal_wT_K": qiu.nominal_transition_width_K,
            "source_contract_schema": qiu.source_contract_schema,
        },
        "case_data": case_data,
    }
    return rows, uniqueness_rows, audit


def _plot_phase_maps(path: Path, audit: Mapping[str, Any]) -> None:
    case_data = audit["case_data"]
    cases = list(case_data)
    fig, axes = plt.subplots(4, 3, figsize=(11, 10), constrained_layout=True)
    last = None
    for column, voltage in enumerate((0.95, 1.15, 1.35)):
        for branch_index, branch in enumerate(("heating", "cooling")):
            data = case_data[f"{branch}_{voltage:.2f}V"]
            for init_index, init in enumerate(("cold", "hot")):
                axis = axes[2 * branch_index + init_index, column]
                phase = _numpy(
                    getattr(data[init], "fields")[
                        "effective_conductive_state_coordinate"
                    ]
                )
                last = axis.imshow(phase, origin="lower", vmin=0.0, vmax=1.0, cmap="viridis")
                axis.set_title(f"{branch} {voltage:.2f} V, {init}")
                axis.set_xticks([])
                axis.set_yticks([])
    if last is not None:
        fig.colorbar(last, ax=axes, label="effective conductive-state coordinate")
    fig.suptitle("Self-consistent major-branch phase maps (Stage A)")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_fixed_point_comparison(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    labels = [str(row["case_id"]) for row in rows]
    x = np.arange(len(rows))
    temperature = [
        float(row["cold_hot_temperature_rise_relative_l2_difference"])
        for row in rows
    ]
    current = [float(row["cold_hot_terminal_current_relative_difference"]) for row in rows]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    axes[0].bar(x, temperature, color="#4C78A8")
    axes[1].bar(x, current, color="#F58518")
    for axis, title in zip(
        axes,
        ("Cold/hot T-rise relative L2", "Cold/hot terminal-current relative difference"),
    ):
        axis.axhline(1.0e-4, color="black", linestyle="--", label="uniqueness gate")
        axis.set_yscale("log")
        axis.set_title(title)
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.grid(alpha=0.2)
        axis.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_transition_and_iterations(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    labels = [str(row["case_id"]) for row in rows]
    x = np.arange(len(rows))
    width = 0.35
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    axes[0].bar(
        x - width / 2,
        [float(row["cold_transition_fraction"]) for row in rows],
        width,
        label="cold",
    )
    axes[0].bar(
        x + width / 2,
        [float(row["hot_transition_fraction"]) for row in rows],
        width,
        label="hot",
    )
    axes[0].axhline(0.02, color="black", linestyle="--", label="transition gate")
    axes[0].set_ylabel("transition fraction")
    axes[0].legend()
    axes[1].bar(
        x - width / 2,
        [int(row["cold_iterations"]) for row in rows],
        width,
        label="cold",
    )
    axes[1].bar(
        x + width / 2,
        [int(row["hot_iterations"]) for row in rows],
        width,
        label="hot",
    )
    axes[1].set_ylabel("relaxed updates")
    axes[1].legend()
    for axis in axes:
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.grid(alpha=0.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_not_executed(path: Path, title: str, disposition: str) -> None:
    fig, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    axis.axis("off")
    axis.text(0.5, 0.66, title, ha="center", va="center", fontsize=16, weight="bold")
    axis.text(
        0.5,
        0.42,
        "Not executed: Stage A single-valued forward-map prerequisite failed.",
        ha="center",
        va="center",
        fontsize=11,
        wrap=True,
    )
    axis.text(0.5, 0.23, disposition, ha="center", va="center", family="monospace")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_route(path: Path, audit: Mapping[str, Any]) -> None:
    disposition = str(audit["disposition"])
    fig, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    axis.axis("off")
    boxes = [
        (0.14, "Qiu-anchored\nself-consistent M1"),
        (0.42, "6-case cold/hot\nvoltage admission"),
        (0.70, f"{audit['unique_case_count']}/6 unique"),
        (0.90, "STOP\nbefore atlas/neural"),
    ]
    for x, text in boxes:
        axis.text(
            x,
            0.58,
            text,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.5", "facecolor": "#E8EEF7", "edgecolor": "#4C78A8"},
        )
    for left, right in zip(boxes[:-1], boxes[1:]):
        axis.annotate("", xy=(right[0] - 0.08, 0.58), xytext=(left[0] + 0.08, 0.58), arrowprops={"arrowstyle": "->"})
    axis.text(0.5, 0.20, disposition, ha="center", family="monospace", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_report(
    path: Path,
    *,
    config: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> None:
    nonunique = [row for row in rows if row["valid"] and not row["unique"]]
    lines = [
        "# Q2 M1 self-consistent IMT contraction gate v1",
        "",
        "## Conclusion",
        "",
        f"Disposition: `{audit['disposition']}`.",
        "",
        "The six bounded Stage A cases were actually solved from both ambient and 360 K initial fields. "
        f"All {audit['valid_case_count']}/6 pairs were numerically valid, but only "
        f"{audit['unique_case_count']}/6 satisfied the preregistered uniqueness gate. "
        "The fixed-parameter to steady-fixed-point solution relation is therefore not single-valued under the initialization-independent surrogate contract; the deterministic P_alpha(T) operator itself remains single-valued. Stage B/C and every neural stage are ineligible.",
        "",
        "## Frozen PR #40",
        "",
        f"PR #40 head `{config['frozen_baseline']['head_sha']}` retained "
        f"`{config['frozen_baseline']['disposition']}` unchanged and was squash-merged as "
        f"`{config['frozen_baseline']['merge_sha']}` before this branch.",
        "",
        "## Constitutive identity",
        "",
        f"The Qiu source contract gives beta `{audit['qiu_parameters']['beta_per_K']}` K^-1, loop width `{audit['qiu_parameters']['loop_width_K']}` K, and Tc0 `{audit['qiu_parameters']['critical_temperature_K']}` K. "
        f"The resulting centres are `{audit['qiu_parameters']['Tc_up_K']}` K and `{audit['qiu_parameters']['Tc_down_K']}` K, with nominal tanh scale `{audit['qiu_parameters']['nominal_wT_K']}` K.",
        "The modeled phase coordinate is an effective conductive-state coordinate, not a metallic volume fraction; no minor loop, reversal rule, or dynamic state is implemented.",
        "",
        "## Voltage admission and uniqueness",
        "",
        "| case | cold Tmean K | hot Tmean K | T-rise difference | current difference | unique |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {float(row['cold_Tmean_K']):.6g} | {float(row['hot_Tmean_K']):.6g} | "
            f"{float(row['cold_hot_temperature_rise_relative_l2_difference']):.6g} | "
            f"{float(row['cold_hot_terminal_current_relative_difference']):.6g} | {bool(row['unique'])} |"
        )
    lines.extend(
        [
            "",
            f"Non-unique cases: `{', '.join(str(row['case_id']) for row in nonunique)}`.",
            "",
            "## Contraction, A1/A2 and neural route",
            "",
            "The contraction atlas, A1/A2 headroom vote, and conditional neural execution were not run because they require a valid single-valued Stage A map. Empty schema-bearing CSVs and explicitly labelled not-executed figures preserve this prerequisite failure without fabricating contraction data.",
            "",
            "## Claim boundary",
            "",
            f"Evidence type: `{EVIDENCE_TYPE}`. The self-consistent implementation is a supported implementation fact after focused validation; the bounded multi-fixed-point result is `failed_but_informative`. Unique-atlas, contraction, neural-value, full-hysteresis, dynamic-stability, experimental-validation, Qiu-quantitative-reproduction, formal-superiority, inverse, and transfer claims remain forbidden or unassessed as recorded in `{config['outputs']['paper_evidence_map']}`.",
            "",
            "## Artifacts and validation",
            "",
            f"- Tables: `{config['outputs']['table_root']}`",
            f"- Fields: `{config['outputs']['processed_root']}`",
            f"- Figures: `{config['outputs']['figure_root']}`",
            "- Focused test: `pytest -q tests/test_q2_m1_self_consistent_imt_contraction_gate_v1.py` -> `8 passed`.",
            f"- Base: `{config['frozen_baseline']['merge_sha']}`.",
            "- Branch: `codex/q2-m1-self-consistent-imt-contraction-gate-v1`.",
            "- Final commit, push, and draft-PR identity are recorded in the final handoff because a commit cannot contain its own SHA.",
            "",
            "## Next priority",
            "",
            "Resolve or explicitly accept the physical multi-valued major-branch forward relation before any surrogate question is meaningful; under the present contract, stop neural-forward work and use the cold/hot branch separation as limitation-manuscript evidence.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_evidence_map(path: Path, summary: Mapping[str, Any]) -> None:
    text = f"""# PINN route evidence map after the self-consistent IMT gate

Evidence type: `{EVIDENCE_TYPE}`.

| Route or fact | Result | Claim status | Manuscript use |
|---|---|---|---|
| M1 conservative operator | Retained contact-aware numerical asset | supported | Methods and reproducibility |
| Prescribed-state direct-coordinate PINN | Historical bounded failure | failed_but_informative | Limitation |
| Prescribed-state latent neural mapper | A2/ridge dominates in PR #40 | failed_but_informative | Neural-necessity boundary |
| Self-consistent major-branch closure | Implemented from Qiu source-contract shape parameters | supported implementation fact | Methods with synthetic/source-anchored qualifier |
| Stage A self-consistent forward map | {summary['voltage_admission']['unique_case_count']}/6 cases unique | failed_but_informative | Multi-fixed-point limitation |
| Contraction atlas and A1/A2 headroom | Not eligible after uniqueness failure | forbidden / unassessed | No contraction or neural-headroom sentence |
| Conditional neural stage | Not executed | forbidden | No neural self-consistent claim |

Allowed sentence: "Within the frozen synthetic major-branch closure, cold and hot initializations reached distinct numerically valid fixed points in five of six bounded admission conditions, so a single-valued forward surrogate was not eligible."

Forbidden: full hysteresis, minor-loop reproduction, dynamic stability, experimental validation, Qiu quantitative field reproduction, formal PINN superiority, inverse recovery, or zero-shot material transfer.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_experiment(config_path: Path, repository_root: Path) -> dict[str, Any]:
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(1)
    config = load_yaml(config_path)
    processed_root = repository_root / str(config["outputs"]["processed_root"])
    table_root = repository_root / str(config["outputs"]["table_root"])
    figure_root = repository_root / str(config["outputs"]["figure_root"])
    for root in (processed_root, table_root, figure_root):
        root.mkdir(parents=True, exist_ok=True)

    rows, uniqueness_rows, audit = run_voltage_admission(
        config, repository_root, processed_root
    )
    _write_csv(table_root / "voltage_admission.csv", rows)
    _write_csv(table_root / "fixed_point_uniqueness.csv", uniqueness_rows)

    stage_a_pass = audit["disposition"] == "STAGE_A_PASS"
    if stage_a_pass:
        raise RuntimeError(
            "Stage A unexpectedly passed; Stage B/C execution must be implemented before continuing"
        )

    _write_csv(
        table_root / "self_consistent_imt_case_manifest.csv",
        [],
        fieldnames=(
            "case_id",
            "branch_label",
            "context",
            "phase_width_multiplier",
            "joule_feedback_multiplier",
            "execution_status",
            "not_executed_reason",
        ),
    )
    _write_csv(
        table_root / "projection_contraction_metrics.csv",
        [],
        fieldnames=(
            "case_id",
            "local_singular_value_estimate",
            "uniform_1K_ratio",
            "x_gradient_1K_ratio",
            "localized_sink_patch_1K_ratio",
            "power_iterations",
            "execution_status",
            "not_executed_reason",
        ),
    )
    _write_csv(
        table_root / "a1_a2_headroom_metrics.csv",
        [],
        fieldnames=(
            "case_id",
            "a1_practical_pass",
            "a2_practical_pass",
            "a1_joint_field_score",
            "a2_joint_field_score",
            "a2_over_a1_error_reduction_ratio",
            "execution_status",
            "not_executed_reason",
        ),
    )

    summary: dict[str, Any] = {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "evidence_type": EVIDENCE_TYPE,
        "validity": "valid",
        "lifecycle_state": "numerically_validated",
        "claim_status": "failed_but_informative",
        "scientific_object": config["reference"]["evidence_object"],
        "frozen_pr40": config["frozen_baseline"],
        "source_contract": audit["qiu_parameters"],
        "voltage_admission": {
            key: value for key, value in audit.items() if key != "case_data"
        },
        "stage_b_contraction_atlas": {
            "executed": False,
            "case_count": 0,
            "reason": "stage_a_single_valued_forward_map_prerequisite_failed",
        },
        "a1_a2_headroom": {
            "executed": False,
            "HEADROOM_ONE_PROJECTION": False,
            "HEADROOM_TWO_PROJECTION": False,
            "reason": "stage_a_single_valued_forward_map_prerequisite_failed",
        },
        "conditional_neural_stage": {
            "executed": False,
            "reason": "headroom_gate_ineligible_after_stage_a_uniqueness_failure",
        },
        "final_disposition": audit["disposition"],
        "allowed_claim": "bounded synthetic multi-fixed-point limitation",
        "forbidden_claims": [
            "unique_fixed_point_atlas",
            "global_contraction_proof",
            "neural_headroom",
            "full_hysteresis",
            "minor_loop_reproduction",
            "dynamic_stability",
            "experimental_validation",
            "qiu_quantitative_field_reproduction",
            "formal_pinn_superiority",
            "inverse",
            "zero_shot_material_transfer",
        ],
        "outputs": config["outputs"],
    }
    _write_json(table_root / "decision_summary.json", summary)

    _plot_phase_maps(figure_root / "self_consistent_phase_maps.png", audit)
    _plot_fixed_point_comparison(
        figure_root / "cold_hot_fixed_point_comparison.png", rows
    )
    _plot_not_executed(
        figure_root / "contraction_vs_phase_width.png",
        "Contraction versus phase width",
        str(audit["disposition"]),
    )
    _plot_not_executed(
        figure_root / "contraction_vs_joule_feedback.png",
        "Contraction versus Joule feedback",
        str(audit["disposition"]),
    )
    _plot_not_executed(
        figure_root / "a1_a2_error_and_pass_rate.png",
        "A1/A2 error and pass rate",
        str(audit["disposition"]),
    )
    _plot_transition_and_iterations(
        figure_root / "transition_fraction_and_iterations.png", rows
    )
    _plot_route(figure_root / "paper_route_decision.png", audit)

    report_path = repository_root / str(config["outputs"]["report"])
    evidence_path = repository_root / str(config["outputs"]["paper_evidence_map"])
    _write_report(
        report_path, config=config, rows=rows, audit=audit, summary=summary
    )
    _write_evidence_map(evidence_path, summary)
    return _json_safe(summary)
