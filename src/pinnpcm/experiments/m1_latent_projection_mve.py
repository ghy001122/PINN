"""Single-seed M1 latent solver-projected PINN scientific MVE."""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import (
    GeoStateReferenceContext,
    build_reference_context,
    load_yaml,
    material_parameters,
)
from pinnpcm.experiments.geostate_m1_compatibility import (
    M1TeacherCase,
    load_teacher_cases,
    reconstruct_conservative_teacher,
)
from pinnpcm.physics.m1_torch_projection import M1TorchProjection
from pinnpcm.pinn.m1_latent_projection_pinn import M1LatentProjectionPINN


EVIDENCE_TYPE = "literature-guided synthetic numerical digital-twin evidence"


@dataclass(frozen=True)
class ThermalPOD:
    mean_y: np.ndarray
    basis: np.ndarray
    coefficients: np.ndarray
    coefficient_center: np.ndarray
    coefficient_scale: np.ndarray
    singular_values: np.ndarray
    cumulative_energy: np.ndarray
    rank: int
    rank_cap_relaxed: bool
    train_case_ids: tuple[str, ...]
    reconstruction_errors: np.ndarray


@dataclass(frozen=True)
class FrozenIterationResult:
    fields: dict[str, torch.Tensor]
    converged: bool
    additional_iterations: int
    scaled_residual: float
    scaled_update: float
    electrical_solve_count: int
    thermal_solve_count: int


def build_projection_operator(
    context: GeoStateReferenceContext, base_config: Mapping[str, Any]
) -> M1TorchProjection:
    form = base_config["physical_model"]["model_forms"]["M1"]
    return M1TorchProjection(
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
    )


def split_case_ids(
    cases: Sequence[M1TeacherCase], config: Mapping[str, Any]
) -> dict[str, tuple[str, ...]]:
    all_ids = {case.case_id for case in cases}
    validation = tuple(str(value) for value in config["dataset"]["validation_cases"])
    test = tuple(str(value) for value in config["dataset"]["test_cases"])
    if set(validation) & set(test):
        raise ValueError("validation and test case identifiers overlap")
    if not set(validation + test) <= all_ids:
        raise ValueError("configured validation/test cases are absent from the frozen data")
    train = tuple(sorted(all_ids - set(validation) - set(test)))
    if len(train) != 8 or len(validation) != 2 or len(test) != 2:
        raise ValueError("the frozen complete-case split must contain 8/2/2 cases")
    return {"train": train, "validation": validation, "test": test}


def case_mapping(cases: Sequence[M1TeacherCase]) -> dict[str, M1TeacherCase]:
    result = {case.case_id: case for case in cases}
    if len(result) != len(cases):
        raise ValueError("case identifiers are not unique")
    return result


def normalized_mu(cases: Sequence[M1TeacherCase], config: Mapping[str, Any]) -> torch.Tensor:
    voltage_scale = float(config["model"]["voltage_scale_V"])
    sink_scale = float(config["model"]["sink_amplitude_scale"])
    values = [
        [
            case.device_voltage_V / voltage_scale,
            case.branch_value,
            case.state_coordinate,
            case.sink_amplitude / sink_scale,
        ]
        for case in cases
    ]
    return torch.as_tensor(values, dtype=torch.float64)


def physical_parameters(cases: Sequence[M1TeacherCase]) -> tuple[torch.Tensor, ...]:
    voltage = torch.as_tensor([case.device_voltage_V for case in cases], dtype=torch.float64)
    state = torch.as_tensor([case.state_coordinate for case in cases], dtype=torch.float64)
    sink = torch.as_tensor([case.sink_amplitude for case in cases], dtype=torch.float64)
    return voltage, state, sink


def _relative_l2(predicted: torch.Tensor, reference: torch.Tensor, eps: float = 1.0e-30) -> torch.Tensor:
    if predicted.ndim == reference.ndim and predicted.ndim >= 2:
        dims = tuple(range(1, predicted.ndim))
        return torch.linalg.vector_norm(predicted - reference, dim=dims) / torch.clamp(
            torch.linalg.vector_norm(reference, dim=dims), min=eps
        )
    return torch.linalg.vector_norm(predicted - reference) / torch.clamp(
        torch.linalg.vector_norm(reference), min=eps
    )


def _scalar_relative(predicted: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    return torch.abs(predicted - reference) / torch.clamp(torch.abs(reference), min=1.0e-30)


def _numpy_relative_l2(predicted: np.ndarray, reference: np.ndarray, eps: float = 1.0e-30) -> float:
    return float(np.linalg.norm(np.asarray(predicted) - np.asarray(reference)) / max(np.linalg.norm(reference), eps))


def operator_parity_rows(
    operator: M1TorchProjection,
    context: GeoStateReferenceContext,
    cases: Sequence[M1TeacherCase],
    base_config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]]]:
    rows: list[dict[str, Any]] = []
    plotting: dict[str, dict[str, np.ndarray]] = {}
    operator.eval()
    with torch.no_grad():
        for case in cases:
            temperature = torch.as_tensor(case.temperature_K, dtype=torch.float64)
            result = operator.projection(
                temperature,
                case.device_voltage_V,
                case.state_coordinate,
                case.sink_amplitude,
            )
            teacher_row, teacher_fields = reconstruct_conservative_teacher(
                context, case, base_config
            )
            predicted_phi = result["potential_V"].cpu().numpy()
            mapped_temperature = result["temperature_K"].cpu().numpy()
            internal = result["internal_joule_cell_W"].cpu().numpy()
            contact = result["contact_joule_cell_W"].cpu().numpy()
            temperature_rise = case.temperature_K - context.ambient_temperature_K
            map_defect = float(
                np.linalg.norm(mapped_temperature - case.temperature_K)
                / max(np.linalg.norm(temperature_rise), 1.0e-30)
            )
            row = {
                "case_id": case.case_id,
                "finite": bool(
                    all(
                        np.isfinite(value).all()
                        for value in (predicted_phi, mapped_temperature, internal, contact)
                    )
                ),
                "phi_relative_l2": _numpy_relative_l2(predicted_phi, case.potential_V),
                "mapped_temperature_relative_l2": _numpy_relative_l2(
                    mapped_temperature, case.temperature_K
                ),
                "terminal_current_relative_error": abs(
                    float(result["source_current_A"]) - float(teacher_row["source_current_A"])
                )
                / max(abs(float(teacher_row["source_current_A"])), 1.0e-30),
                "internal_joule_relative_error": _numpy_relative_l2(
                    internal, teacher_fields.internal_joule_cell_W
                ),
                "contact_joule_relative_error": _numpy_relative_l2(
                    contact, teacher_fields.contact_joule_cell_W
                ),
                "terminal_electrical_heat_ledger_error": float(
                    result["terminal_electrical_heat_ledger_error"]
                ),
                "electrical_heat_sink_ledger_error": float(
                    result["electrical_heat_sink_ledger_error"]
                ),
                "fixed_point_map_defect": map_defect,
            }
            rows.append(row)
            plotting[case.case_id] = {
                "reference_temperature_K": case.temperature_K,
                "mapped_temperature_K": mapped_temperature,
                "reference_potential_V": case.potential_V,
                "mapped_potential_V": predicted_phi,
            }
    return rows, plotting


def operator_parity_summary(
    rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    gates = config["operator_parity"]
    maxima = {
        "max_phi_relative_l2": max(float(row["phi_relative_l2"]) for row in rows),
        "max_mapped_temperature_relative_l2": max(
            float(row["mapped_temperature_relative_l2"]) for row in rows
        ),
        "max_terminal_current_relative_error": max(
            float(row["terminal_current_relative_error"]) for row in rows
        ),
        "max_internal_joule_relative_error": max(
            float(row["internal_joule_relative_error"]) for row in rows
        ),
        "max_contact_joule_relative_error": max(
            float(row["contact_joule_relative_error"]) for row in rows
        ),
        "max_terminal_electrical_heat_ledger_error": max(
            float(row["terminal_electrical_heat_ledger_error"]) for row in rows
        ),
        "max_electrical_heat_sink_ledger_error": max(
            float(row["electrical_heat_sink_ledger_error"]) for row in rows
        ),
        "max_fixed_point_map_defect": max(
            float(row["fixed_point_map_defect"]) for row in rows
        ),
    }
    finite_count = sum(bool(row["finite"]) for row in rows)
    passed = bool(
        len(rows) == int(config["reference"]["expected_cases"])
        and finite_count == int(gates["finite_case_count_required"])
        and maxima["max_phi_relative_l2"] <= float(gates["phi_relative_l2_max"])
        and maxima["max_mapped_temperature_relative_l2"]
        <= float(gates["mapped_temperature_relative_l2_max"])
        and maxima["max_terminal_current_relative_error"]
        <= float(gates["terminal_current_relative_error_max"])
        and maxima["max_internal_joule_relative_error"]
        <= float(gates["internal_joule_relative_error_max"])
        and maxima["max_contact_joule_relative_error"]
        <= float(gates["contact_joule_relative_error_max"])
        and maxima["max_terminal_electrical_heat_ledger_error"]
        <= float(gates["terminal_electrical_heat_ledger_max"])
        and maxima["max_electrical_heat_sink_ledger_error"]
        <= float(gates["electrical_heat_sink_ledger_max"])
        and maxima["max_fixed_point_map_defect"]
        <= float(gates["fixed_point_map_defect_max"])
    )
    return {
        "case_count": len(rows),
        "finite_case_count": finite_count,
        **maxima,
        "passed": passed,
        "implementation_repairs_used": 0,
        "reference_nonlinear_solves_rerun": 0,
        "disposition_if_stopped": None if passed else "NO_GO_DIFFERENTIABLE_M1_OPERATOR_PARITY",
    }


def fit_train_only_pod(
    fields_by_case: Mapping[str, np.ndarray],
    train_case_ids: Sequence[str],
    *,
    ambient_temperature_K: float,
    cumulative_energy_target: float,
    rank_cap: int,
    training_sample_rank_cap: int,
) -> ThermalPOD:
    expected = tuple(sorted(str(value) for value in train_case_ids))
    if tuple(sorted(fields_by_case)) != expected:
        raise ValueError("POD fit data must contain exactly the frozen train cases")
    transformed = []
    for case_id in expected:
        rise = np.asarray(fields_by_case[case_id], dtype=float) - ambient_temperature_K
        if np.any(rise < -1.0e-9):
            raise ValueError(f"{case_id} contains a negative temperature rise")
        transformed.append(np.log1p(np.maximum(rise, 0.0) / 1.0).reshape(-1))
    y = np.stack(transformed)
    mean_y = np.mean(y, axis=0)
    centered = y - mean_y
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    energy = np.square(singular_values)
    cumulative = np.cumsum(energy) / max(float(np.sum(energy)), 1.0e-30)
    required_rank = int(np.searchsorted(cumulative, cumulative_energy_target) + 1)
    if required_rank > training_sample_rank_cap:
        raise RuntimeError("NO_GO_LOW_RANK_THERMAL_MANIFOLD")
    rank_cap_relaxed = required_rank > rank_cap
    rank = required_rank
    basis = vt[:rank].copy()
    coefficients = centered @ basis.T
    reconstruction = mean_y + coefficients @ basis
    reconstruction_errors = np.linalg.norm(reconstruction - y, axis=1) / np.maximum(
        np.linalg.norm(y, axis=1), 1.0e-30
    )
    coefficient_center = np.mean(coefficients, axis=0)
    coefficient_scale = np.std(coefficients, axis=0)
    coefficient_scale = np.maximum(coefficient_scale, 1.0e-12)
    return ThermalPOD(
        mean_y=mean_y,
        basis=basis,
        coefficients=coefficients,
        coefficient_center=coefficient_center,
        coefficient_scale=coefficient_scale,
        singular_values=singular_values,
        cumulative_energy=cumulative,
        rank=rank,
        rank_cap_relaxed=rank_cap_relaxed,
        train_case_ids=expected,
        reconstruction_errors=reconstruction_errors,
    )


def build_latent_model(pod: ThermalPOD, config: Mapping[str, Any]) -> M1LatentProjectionPINN:
    return M1LatentProjectionPINN(
        pod_mean_y=torch.as_tensor(pod.mean_y, dtype=torch.float64),
        pod_basis=torch.as_tensor(pod.basis, dtype=torch.float64),
        coefficient_center=torch.as_tensor(pod.coefficient_center, dtype=torch.float64),
        coefficient_scale=torch.as_tensor(pod.coefficient_scale, dtype=torch.float64),
        ambient_temperature_K=float(config["reference"]["ambient_temperature_K"]),
        smooth_nonnegative_beta_K=float(config["pod"]["smooth_nonnegative_beta_K"]),
        hidden_width=int(config["model"]["hidden_width"]),
    )


def unroll_two_projections(
    model: M1LatentProjectionPINN,
    operator: M1TorchProjection,
    mu: torch.Tensor,
    voltage: torch.Tensor,
    state: torch.Tensor,
    sink: torch.Tensor,
) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    temperature0 = model.initial_temperature(mu, operator.ny, operator.nx)
    first = operator.projection(temperature0, voltage, state, sink)
    second = operator.projection(first["temperature_K"], voltage, state, sink)
    return temperature0, first, second


def train_latent_model(
    model: M1LatentProjectionPINN,
    operator: M1TorchProjection,
    train_cases: Sequence[M1TeacherCase],
    pod: ThermalPOD,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    training = config["training"]
    mu = normalized_mu(train_cases, config)
    voltage, state, sink = physical_parameters(train_cases)
    target_coefficients = torch.as_tensor(pod.coefficients, dtype=torch.float64)
    target_temperature = torch.as_tensor(
        np.stack([case.temperature_K for case in train_cases]), dtype=torch.float64
    )
    target_phi = torch.as_tensor(
        np.stack([case.potential_V for case in train_cases]), dtype=torch.float64
    )
    reference_electrical = operator.electrical(target_temperature, voltage, state)
    target_current = reference_electrical["source_current_A"].detach()
    ambient = operator.ambient_temperature_K
    weights = {name: float(value) for name, value in training["fixed_loss_weights"].items()}
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    global_step = 0

    optimizer = torch.optim.Adam(model.parameters(), lr=float(training["stage1_learning_rate"]))
    for stage_step in range(1, int(training["stage1_steps"]) + 1):
        optimizer.zero_grad(set_to_none=True)
        coefficients = model(mu)
        coefficient = torch.mean(
            ((coefficients - target_coefficients) / model.coefficient_scale).square()
        )
        coefficient.backward()
        optimizer.step()
        global_step += 1
        elapsed = time.perf_counter() - started
        history.append(
            {
                "stage": 1,
                "stage_step": stage_step,
                "global_step": global_step,
                "learning_rate": float(training["stage1_learning_rate"]),
                "coefficient_loss": float(coefficient.detach()),
                "projected_temperature_loss": 0.0,
                "projected_potential_loss": 0.0,
                "terminal_current_loss": 0.0,
                "fixed_point_defect_loss": 0.0,
                "total_loss": float(coefficient.detach()),
                "finite": bool(torch.isfinite(coefficient)),
                "elapsed_wall_s": elapsed,
            }
        )
        if elapsed > float(training["maximum_wall_time_s"]):
            raise TimeoutError("latent training exceeded the frozen 30 minute wall-clock budget")

    optimizer = torch.optim.Adam(model.parameters(), lr=float(training["stage2_learning_rate"]))
    for stage_step in range(1, int(training["stage2_steps"]) + 1):
        optimizer.zero_grad(set_to_none=True)
        coefficients = model(mu)
        temperature0, first, second = unroll_two_projections(
            model, operator, mu, voltage, state, sink
        )
        del temperature0
        coefficient = torch.mean(
            ((coefficients - target_coefficients) / model.coefficient_scale).square()
        )
        target_rise_norm = torch.clamp(
            torch.linalg.vector_norm(target_temperature - ambient, dim=(1, 2)), min=1.0e-30
        )
        temperature_loss = torch.mean(
            (
                torch.linalg.vector_norm(second["temperature_K"] - target_temperature, dim=(1, 2))
                / target_rise_norm
            ).square()
        )
        phi_loss = torch.mean(_relative_l2(second["potential_V"], target_phi).square())
        current_loss = torch.mean(
            _scalar_relative(second["source_current_A"], target_current).square()
        )
        defect = torch.linalg.vector_norm(
            second["temperature_K"] - first["temperature_K"], dim=(1, 2)
        ) / torch.clamp(
            torch.linalg.vector_norm(second["temperature_K"] - ambient, dim=(1, 2)),
            min=1.0e-30,
        )
        defect_loss = torch.mean(defect.square())
        groups = {
            "coefficient": coefficient,
            "projected_temperature": temperature_loss,
            "projected_potential": phi_loss,
            "terminal_current": current_loss,
            "fixed_point_defect": defect_loss,
        }
        total = sum(weights[name] * value for name, value in groups.items())
        if not bool(torch.isfinite(total)):
            raise FloatingPointError("nonfinite loss in formal latent training")
        total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=100.0)
        optimizer.step()
        global_step += 1
        elapsed = time.perf_counter() - started
        history.append(
            {
                "stage": 2,
                "stage_step": stage_step,
                "global_step": global_step,
                "learning_rate": float(training["stage2_learning_rate"]),
                "coefficient_loss": float(coefficient.detach()),
                "projected_temperature_loss": float(temperature_loss.detach()),
                "projected_potential_loss": float(phi_loss.detach()),
                "terminal_current_loss": float(current_loss.detach()),
                "fixed_point_defect_loss": float(defect_loss.detach()),
                "total_loss": float(total.detach()),
                "finite": True,
                "elapsed_wall_s": elapsed,
            }
        )
        if elapsed > float(training["maximum_wall_time_s"]):
            raise TimeoutError("latent training exceeded the frozen 30 minute wall-clock budget")

    return history, {
        "completed_steps": global_step,
        "stage1_steps": int(training["stage1_steps"]),
        "stage2_steps": int(training["stage2_steps"]),
        "wall_time_s": time.perf_counter() - started,
        "finite": all(bool(row["finite"]) for row in history),
        "parameter_count": model.parameter_count,
        "seed": int(config["model"]["seed"]),
        "dtype": "float64",
    }


def frozen_m1_iteration(
    operator: M1TorchProjection,
    *,
    initial_temperature_K: torch.Tensor,
    voltage_V: float,
    state_coordinate: float,
    sink_amplitude: float,
    maximum_updates: int,
    relaxation: float,
    temperature_scale_K: float,
    residual_gate: float,
    update_gate: float,
) -> FrozenIterationResult:
    """Run the frozen relaxed M1 iteration from an explicit initial field."""

    temperature = initial_temperature_K.detach().clone().to(dtype=torch.float64)
    if temperature.shape != (operator.ny, operator.nx) or not bool(torch.isfinite(temperature).all()):
        raise ValueError("frozen M1 iteration requires one finite grid-shaped warm start")
    scaled_update = 0.0
    converged = False
    electrical_solve_count = 0
    thermal_solve_count = 0
    scaled_residual = math.inf
    electrical: dict[str, torch.Tensor] | None = None
    accepted_updates = 0
    with torch.no_grad():
        for iteration in range(maximum_updates + 1):
            electrical = operator.electrical(temperature, voltage_V, state_coordinate)
            electrical_solve_count += 1
            residual = operator.thermal_residual(
                temperature, electrical["total_joule_cell_W"], sink_amplitude
            )
            cell_scale = max(
                abs(float(electrical["total_electrical_heat_W"])) / operator.cell_count,
                1.0e-15,
            )
            scaled_thermal = float(torch.max(torch.abs(residual))) / cell_scale
            scaled_residual = max(
                scaled_thermal, float(electrical["scaled_electrical_residual"])
            )
            if scaled_residual <= residual_gate and scaled_update <= update_gate:
                converged = True
                accepted_updates = iteration
                break
            if iteration == maximum_updates:
                accepted_updates = iteration
                break
            thermal = operator.thermal(electrical["total_joule_cell_W"], sink_amplitude)
            thermal_solve_count += 1
            delta = thermal["temperature_K"] - temperature
            scaled_update = float(torch.max(torch.abs(delta))) / temperature_scale_K
            temperature = temperature + relaxation * delta
        if electrical is None:
            raise RuntimeError("frozen M1 iteration did not perform an electrical check")
        diagnostics = operator.thermal_diagnostics(
            temperature, electrical["total_joule_cell_W"], sink_amplitude
        )
        fields = {**electrical, **diagnostics}
    return FrozenIterationResult(
        fields=fields,
        converged=converged,
        additional_iterations=accepted_updates,
        scaled_residual=scaled_residual,
        scaled_update=scaled_update,
        electrical_solve_count=electrical_solve_count,
        thermal_solve_count=thermal_solve_count,
    )


def _projection_defects(
    operator: M1TorchProjection,
    previous_temperature: torch.Tensor,
    next_temperature: torch.Tensor,
    state_coordinate: float,
) -> tuple[float, float]:
    ambient = operator.ambient_temperature_K
    fixed = float(
        torch.linalg.vector_norm(next_temperature - previous_temperature)
        / torch.clamp(
            torch.linalg.vector_norm(next_temperature - ambient), min=1.0e-30
        )
    )
    sigma_previous = operator.conductivity(previous_temperature, state_coordinate)
    sigma_next = operator.conductivity(next_temperature, state_coordinate)
    sigma = float(
        torch.linalg.vector_norm(sigma_next - sigma_previous)
        / torch.clamp(torch.linalg.vector_norm(sigma_next), min=1.0e-30)
    )
    return fixed, sigma


def _consistent_fields(
    operator: M1TorchProjection,
    temperature_K: torch.Tensor,
    voltage_V: float,
    state_coordinate: float,
    sink_amplitude: float,
) -> dict[str, torch.Tensor]:
    electrical = operator.electrical(temperature_K, voltage_V, state_coordinate)
    diagnostics = operator.thermal_diagnostics(
        temperature_K, electrical["total_joule_cell_W"], sink_amplitude
    )
    return {**electrical, **diagnostics}


def _metric_row(
    *,
    operator: M1TorchProjection,
    case: M1TeacherCase,
    split: str,
    mode: str,
    fields: Mapping[str, torch.Tensor],
    reference_current_A: float,
    fixed_point_defect: float,
    sigma_defect: float,
    projection_count: int,
    additional_iterations: int,
    total_nonlinear_iterations: int,
    electrical_solve_count: int,
    thermal_solve_count: int,
    converged: bool,
    scaled_residual: float,
) -> dict[str, Any]:
    predicted_t = fields["temperature_K"].detach().cpu().numpy()
    predicted_phi = fields["potential_V"].detach().cpu().numpy()
    reference_rise = case.temperature_K - operator.ambient_temperature_K
    predicted_rise = predicted_t - operator.ambient_temperature_K
    t_error = _numpy_relative_l2(predicted_rise, reference_rise)
    phi_error = _numpy_relative_l2(predicted_phi, case.potential_V)
    current = float(fields["source_current_A"])
    current_error = abs(current - reference_current_A) / max(abs(reference_current_A), 1.0e-30)
    predicted_hotspot = np.unravel_index(int(np.argmax(predicted_t)), predicted_t.shape)
    reference_hotspot = np.unravel_index(int(np.argmax(case.temperature_K)), case.temperature_K.shape)
    dx = float(operator.x_centers_m[predicted_hotspot[1]] - operator.x_centers_m[reference_hotspot[1]])
    dy = float(operator.y_centers_m[predicted_hotspot[0]] - operator.y_centers_m[reference_hotspot[0]])
    hotspot_error = math.hypot(dx, dy) / operator.width_m
    terminal_ledger = float(fields["terminal_electrical_heat_ledger_error"])
    sink_ledger = float(fields["electrical_heat_sink_ledger_error"])
    finite = bool(
        np.isfinite(predicted_t).all()
        and np.isfinite(predicted_phi).all()
        and np.isfinite(
            [
                current,
                t_error,
                phi_error,
                fixed_point_defect,
                sigma_defect,
                terminal_ledger,
                sink_ledger,
            ]
        ).all()
    )
    total_solves = electrical_solve_count + thermal_solve_count
    return {
        "split": split,
        "case_id": case.case_id,
        "mode": mode,
        "temperature_rise_relative_l2": t_error,
        "potential_relative_l2": phi_error,
        "joint_field_score": 0.5 * (t_error + phi_error),
        "terminal_current_relative_error": current_error,
        "predicted_terminal_current_A": current,
        "reference_terminal_current_A": reference_current_A,
        "hotspot_coordinate_error_width_fraction": hotspot_error,
        "fixed_point_defect": fixed_point_defect,
        "sigma_defect": sigma_defect,
        "terminal_electrical_heat_ledger_error": terminal_ledger,
        "electrical_heat_sink_ledger_error": sink_ledger,
        "energy_ledger_error": max(terminal_ledger, sink_ledger),
        "projection_count": projection_count,
        "additional_iterations": additional_iterations,
        "total_nonlinear_iterations": total_nonlinear_iterations,
        "electrical_linear_solve_count": electrical_solve_count,
        "thermal_linear_solve_count": thermal_solve_count,
        "linear_solve_count": total_solves,
        "factorization_count": total_solves,
        "converged": converged,
        "scaled_nonlinear_residual": scaled_residual,
        "finite": finite,
        "fast_case_pass": False,
        "certified_case_pass": False,
    }


def _time_callable(
    function: Callable[[], Any], repeats: int, warmups: int
) -> list[float]:
    with torch.no_grad():
        for _ in range(warmups):
            function()
        values = []
        for _ in range(repeats):
            started = time.perf_counter()
            function()
            values.append(time.perf_counter() - started)
    return values


def evaluate_case_modes(
    *,
    model: M1LatentProjectionPINN,
    operator: M1TorchProjection,
    case: M1TeacherCase,
    split: str,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, torch.Tensor]]]:
    evaluation = config["evaluation"]
    mu = normalized_mu([case], config)
    voltage, state, sink = physical_parameters([case])
    reference_t = torch.as_tensor(case.temperature_K, dtype=torch.float64)
    reference_electrical = operator.electrical(
        reference_t, case.device_voltage_V, case.state_coordinate
    )
    reference_current = float(reference_electrical["source_current_A"])
    cold_initial = operator.cold_initial_temperature(
        case.device_voltage_V, case.state_coordinate
    )[0]

    with torch.no_grad():
        temperature0, first, second = unroll_two_projections(
            model, operator, mu, voltage, state, sink
        )
        temperature0 = temperature0[0]
        first = {name: value[0] if value.ndim > 0 and value.shape[0] == 1 else value for name, value in first.items()}
        second = {name: value[0] if value.ndim > 0 and value.shape[0] == 1 else value for name, value in second.items()}
        n0_fields = _consistent_fields(
            operator,
            temperature0,
            case.device_voltage_V,
            case.state_coordinate,
            case.sink_amplitude,
        )
        a_first = operator.projection(
            cold_initial,
            case.device_voltage_V,
            case.state_coordinate,
            case.sink_amplitude,
        )
        a_second = operator.projection(
            a_first["temperature_K"],
            case.device_voltage_V,
            case.state_coordinate,
            case.sink_amplitude,
        )
        cold = frozen_m1_iteration(
            operator,
            initial_temperature_K=cold_initial,
            voltage_V=case.device_voltage_V,
            state_coordinate=case.state_coordinate,
            sink_amplitude=case.sink_amplitude,
            maximum_updates=int(evaluation["cold_maximum_iterations"]),
            relaxation=float(evaluation["relaxation"]),
            temperature_scale_K=float(evaluation["temperature_scale_K"]),
            residual_gate=float(evaluation["scaled_residual_max"]),
            update_gate=float(evaluation["scaled_update_max"]),
        )
        nc = frozen_m1_iteration(
            operator,
            initial_temperature_K=second["temperature_K"],
            voltage_V=case.device_voltage_V,
            state_coordinate=case.state_coordinate,
            sink_amplitude=case.sink_amplitude,
            maximum_updates=int(evaluation["nc_maximum_additional_iterations"]),
            relaxation=float(evaluation["relaxation"]),
            temperature_scale_K=float(evaluation["temperature_scale_K"]),
            residual_gate=float(evaluation["scaled_residual_max"]),
            update_gate=float(evaluation["scaled_update_max"]),
        )

        n0_fixed, n0_sigma = _projection_defects(
            operator, temperature0, first["temperature_K"], case.state_coordinate
        )
        chain_fixed, chain_sigma = _projection_defects(
            operator, first["temperature_K"], second["temperature_K"], case.state_coordinate
        )
        a_fixed, a_sigma = _projection_defects(
            operator, a_first["temperature_K"], a_second["temperature_K"], case.state_coordinate
        )
        cold_lookahead = operator.projection(
            cold.fields["temperature_K"],
            case.device_voltage_V,
            case.state_coordinate,
            case.sink_amplitude,
        )
        cold_fixed, cold_sigma = _projection_defects(
            operator,
            cold.fields["temperature_K"],
            cold_lookahead["temperature_K"],
            case.state_coordinate,
        )
        nc_lookahead = operator.projection(
            nc.fields["temperature_K"],
            case.device_voltage_V,
            case.state_coordinate,
            case.sink_amplitude,
        )
        nc_fixed, nc_sigma = _projection_defects(
            operator,
            nc.fields["temperature_K"],
            nc_lookahead["temperature_K"],
            case.state_coordinate,
        )

    definitions = [
        ("COLD", cold.fields, cold_fixed, cold_sigma, 0, cold.additional_iterations, cold.additional_iterations, cold.electrical_solve_count, cold.thermal_solve_count, cold.converged, cold.scaled_residual),
        ("A2", a_second, a_fixed, a_sigma, 2, 0, 2, 2, 2, False, a_fixed),
        ("N0", n0_fields, n0_fixed, n0_sigma, 0, 0, 0, 1, 0, False, n0_fixed),
        ("N1", first, chain_fixed, chain_sigma, 1, 0, 1, 1, 1, False, chain_fixed),
        ("N2", second, chain_fixed, chain_sigma, 2, 0, 2, 2, 2, False, chain_fixed),
        ("NC", nc.fields, nc_fixed, nc_sigma, 2, nc.additional_iterations, 2 + nc.additional_iterations, 2 + nc.electrical_solve_count, 2 + nc.thermal_solve_count, nc.converged, nc.scaled_residual),
    ]
    rows = [
        _metric_row(
            operator=operator,
            case=case,
            split=split,
            mode=mode,
            fields=fields,
            reference_current_A=reference_current,
            fixed_point_defect=fixed,
            sigma_defect=sigma_value,
            projection_count=projection_count,
            additional_iterations=additional_iterations,
            total_nonlinear_iterations=total_iterations,
            electrical_solve_count=electrical_count,
            thermal_solve_count=thermal_count,
            converged=converged,
            scaled_residual=scaled_residual,
        )
        for (
            mode,
            fields,
            fixed,
            sigma_value,
            projection_count,
            additional_iterations,
            total_iterations,
            electrical_count,
            thermal_count,
            converged,
            scaled_residual,
        ) in definitions
    ]

    fast_repeats = int(evaluation["fast_timing_repeats"])
    certified_repeats = int(evaluation["certified_timing_repeats"])
    warmups = int(evaluation["timing_warmup_repeats"])

    def neural_chain(count: int) -> Any:
        t0 = model.initial_temperature(mu, operator.ny, operator.nx)[0]
        if count == 0:
            return operator.electrical(t0, case.device_voltage_V, case.state_coordinate)
        value = operator.projection(
            t0, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
        )
        if count == 2:
            value = operator.projection(
                value["temperature_K"],
                case.device_voltage_V,
                case.state_coordinate,
                case.sink_amplitude,
            )
        return value

    closures: dict[str, tuple[Callable[[], Any], int]] = {
        "COLD": (
            lambda: frozen_m1_iteration(
                operator,
                initial_temperature_K=operator.cold_initial_temperature(
                    case.device_voltage_V, case.state_coordinate
                )[0],
                voltage_V=case.device_voltage_V,
                state_coordinate=case.state_coordinate,
                sink_amplitude=case.sink_amplitude,
                maximum_updates=int(evaluation["cold_maximum_iterations"]),
                relaxation=float(evaluation["relaxation"]),
                temperature_scale_K=float(evaluation["temperature_scale_K"]),
                residual_gate=float(evaluation["scaled_residual_max"]),
                update_gate=float(evaluation["scaled_update_max"]),
            ),
            certified_repeats,
        ),
        "A2": (
            lambda: operator.projection(
                operator.projection(
                    operator.cold_initial_temperature(
                        case.device_voltage_V, case.state_coordinate
                    )[0],
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )["temperature_K"],
                case.device_voltage_V,
                case.state_coordinate,
                case.sink_amplitude,
            ),
            fast_repeats,
        ),
        "N0": (lambda: neural_chain(0), fast_repeats),
        "N1": (lambda: neural_chain(1), fast_repeats),
        "N2": (lambda: neural_chain(2), fast_repeats),
        "NC": (
            lambda: frozen_m1_iteration(
                operator,
                initial_temperature_K=neural_chain(2)["temperature_K"],
                voltage_V=case.device_voltage_V,
                state_coordinate=case.state_coordinate,
                sink_amplitude=case.sink_amplitude,
                maximum_updates=int(evaluation["nc_maximum_additional_iterations"]),
                relaxation=float(evaluation["relaxation"]),
                temperature_scale_K=float(evaluation["temperature_scale_K"]),
                residual_gate=float(evaluation["scaled_residual_max"]),
                update_gate=float(evaluation["scaled_update_max"]),
            ),
            certified_repeats,
        ),
    }
    speed_rows: list[dict[str, Any]] = []
    medians: dict[str, float] = {}
    for mode, (function, repeats) in closures.items():
        timings = _time_callable(function, repeats, warmups)
        medians[mode] = float(np.median(timings))
        metric = next(row for row in rows if row["mode"] == mode)
        for repeat_index, wall_s in enumerate(timings):
            speed_rows.append(
                {
                    "split": split,
                    "case_id": case.case_id,
                    "mode": mode,
                    "repeat_index": repeat_index,
                    "wall_time_s": wall_s,
                    "linear_solve_count": metric["linear_solve_count"],
                    "factorization_count": metric["factorization_count"],
                    "timing_repeats": repeats,
                }
            )
    for row in rows:
        row["median_wall_time_s"] = medians[row["mode"]]
        row["timing_repeats"] = int(
            evaluation["certified_timing_repeats"]
            if row["mode"] in {"COLD", "NC"}
            else evaluation["fast_timing_repeats"]
        )
        row["speedup_vs_cold"] = medians["COLD"] / medians[row["mode"]]
    predictions = {
        "N0": n0_fields,
        "N1": first,
        "N2": second,
        "NC": nc.fields,
    }
    return rows, speed_rows, predictions


def apply_decision_gates(
    rows: list[dict[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    fast = config["evaluation"]["fast_go"]
    certified = config["evaluation"]["certified_go"]
    test_n2 = [row for row in rows if row["split"] == "test" and row["mode"] == "N2"]
    test_n0 = [row for row in rows if row["split"] == "test" and row["mode"] == "N0"]
    test_a2 = [row for row in rows if row["split"] == "test" and row["mode"] == "A2"]
    test_nc = [row for row in rows if row["split"] == "test" and row["mode"] == "NC"]
    if len(test_n2) != 2 or len(test_n0) != 2 or len(test_a2) != 2 or len(test_nc) != 2:
        raise ValueError("decision gates require exactly two frozen test cases")
    for row in test_n2:
        row["fast_case_pass"] = bool(
            row["finite"]
            and row["temperature_rise_relative_l2"] <= float(fast["temperature_rise_relative_l2_max"])
            and row["potential_relative_l2"] <= float(fast["potential_relative_l2_max"])
            and row["terminal_current_relative_error"] <= float(fast["terminal_current_relative_error_max"])
            and row["fixed_point_defect"] <= float(fast["fixed_point_defect_max"])
            and row["sigma_defect"] <= float(fast["sigma_defect_max"])
            and row["terminal_electrical_heat_ledger_error"] <= float(fast["terminal_electrical_heat_ledger_max"])
            and row["electrical_heat_sink_ledger_error"] <= float(fast["electrical_heat_sink_ledger_max"])
        )
    for row in test_nc:
        row["certified_case_pass"] = bool(
            row["finite"]
            and row["converged"]
            and row["additional_iterations"] <= int(certified["maximum_additional_iterations"])
            and row["temperature_rise_relative_l2"] <= float(certified["field_and_current_relative_error_max"])
            and row["potential_relative_l2"] <= float(certified["field_and_current_relative_error_max"])
            and row["terminal_current_relative_error"] <= float(certified["field_and_current_relative_error_max"])
            and row["terminal_electrical_heat_ledger_error"] <= float(certified["ledger_error_max"])
            and row["electrical_heat_sink_ledger_error"] <= float(certified["ledger_error_max"])
        )
    n2_speedup = float(np.median([row["speedup_vs_cold"] for row in test_n2]))
    a2_speedup = float(np.median([row["speedup_vs_cold"] for row in test_a2]))
    nc_speedup = float(np.median([row["speedup_vs_cold"] for row in test_nc]))
    mean_n0_joint = float(np.mean([row["joint_field_score"] for row in test_n0]))
    mean_n2_joint = float(np.mean([row["joint_field_score"] for row in test_n2]))
    mean_a2_joint = float(np.mean([row["joint_field_score"] for row in test_a2]))
    joint_improvement = (mean_n0_joint - mean_n2_joint) / max(mean_n0_joint, 1.0e-30)
    n2_improvement_over_a2 = (mean_a2_joint - mean_n2_joint) / max(mean_a2_joint, 1.0e-30)
    a2_fast_like_pass_count = sum(
        bool(
            row["finite"]
            and row["temperature_rise_relative_l2"] <= float(fast["temperature_rise_relative_l2_max"])
            and row["potential_relative_l2"] <= float(fast["potential_relative_l2_max"])
            and row["terminal_current_relative_error"] <= float(fast["terminal_current_relative_error_max"])
            and row["fixed_point_defect"] <= float(fast["fixed_point_defect_max"])
            and row["sigma_defect"] <= float(fast["sigma_defect_max"])
            and row["terminal_electrical_heat_ledger_error"] <= float(fast["terminal_electrical_heat_ledger_max"])
            and row["electrical_heat_sink_ledger_error"] <= float(fast["electrical_heat_sink_ledger_max"])
        )
        for row in test_a2
    )
    catastrophic = any(
        (not row["finite"])
        or max(
            row["temperature_rise_relative_l2"],
            row["potential_relative_l2"],
            row["terminal_current_relative_error"],
        )
        > float(fast["catastrophic_relative_error_max"])
        for row in test_n2
    )
    fast_pass_count = sum(bool(row["fast_case_pass"]) for row in test_n2)
    fast_go = bool(
        fast_pass_count >= int(fast["required_test_case_passes"])
        and n2_speedup >= float(fast["speedup_min"])
        and joint_improvement >= float(fast["joint_field_improvement_over_n0_min"])
        and not catastrophic
    )
    certified_pass_count = sum(bool(row["certified_case_pass"]) for row in test_nc)
    median_total_iterations = float(
        np.median([row["total_nonlinear_iterations"] for row in test_nc])
    )
    certified_go = bool(
        certified_pass_count >= int(certified["required_test_case_passes"])
        and median_total_iterations <= float(certified["median_total_projection_updates_max"])
        and nc_speedup >= float(certified["speedup_min"])
    )
    if fast_go:
        disposition = "GO_M1_LATENT_PROJECTION_PINN_MVE"
    elif certified_go:
        disposition = "PARTIAL_GO_M1_NEURAL_WARMSTART_SOLVER"
    else:
        disposition = "NO_GO_M1_SOLVER_PROJECTED_ROUTE"
    return {
        "disposition": disposition,
        "fast_go": fast_go,
        "fast_test_pass_count": fast_pass_count,
        "n2_median_speedup_vs_cold": n2_speedup,
        "n2_mean_joint_field_score": mean_n2_joint,
        "n0_mean_joint_field_score": mean_n0_joint,
        "n2_joint_field_improvement_over_n0": joint_improvement,
        "n2_catastrophic_error": catastrophic,
        "a2_fast_like_test_pass_count_diagnostic": a2_fast_like_pass_count,
        "a2_mean_joint_field_score": mean_a2_joint,
        "a2_median_speedup_vs_cold": a2_speedup,
        "n2_joint_field_improvement_over_a2_diagnostic": n2_improvement_over_a2,
        "neural_specific_advantage_over_a2_supported": bool(n2_improvement_over_a2 > 0.0),
        "certified_go": certified_go,
        "certified_test_pass_count": certified_pass_count,
        "nc_median_speedup_vs_cold": nc_speedup,
        "nc_median_total_projection_updates": median_total_iterations,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    fieldnames: list[str] = []
    for row in rows:
        for name in row:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"cannot JSON encode {type(value).__name__}")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _plot_parity(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    plotting: Mapping[str, Mapping[str, np.ndarray]],
) -> None:
    worst = max(rows, key=lambda row: float(row["fixed_point_map_defect"]))
    values = plotting[str(worst["case_id"])]
    reference_t = values["reference_temperature_K"]
    mapped_t = values["mapped_temperature_K"]
    reference_phi = values["reference_potential_V"]
    mapped_phi = values["mapped_potential_V"]
    figure, axes = plt.subplots(2, 3, figsize=(11, 6), constrained_layout=True)
    images = [
        (reference_t, "reference T [K]"),
        (mapped_t, "projection(T) [K]"),
        (mapped_t - reference_t, "T map difference [K]"),
        (reference_phi, "reference phi [V]"),
        (mapped_phi, "Torch phi [V]"),
        (mapped_phi - reference_phi, "phi difference [V]"),
    ]
    for axis, (image, title) in zip(axes.flat, images, strict=True):
        plotted = axis.imshow(image, origin="lower", aspect="auto")
        axis.set_title(title)
        figure.colorbar(plotted, ax=axis, shrink=0.75)
    figure.suptitle(f"Worst stored-fixed-point parity: {worst['case_id']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_pod(path: Path, pod: ThermalPOD, ny: int, nx: int) -> None:
    figure = plt.figure(figsize=(11, 6), constrained_layout=True)
    grid = figure.add_gridspec(2, 3)
    axis = figure.add_subplot(grid[0, :])
    indices = np.arange(1, len(pod.singular_values) + 1)
    axis.semilogy(indices, np.maximum(pod.singular_values, 1.0e-16), "o-", label="singular value")
    second = axis.twinx()
    second.plot(indices, pod.cumulative_energy, "s--", color="tab:orange", label="cumulative energy")
    second.axhline(0.999, color="black", linestyle=":", linewidth=1)
    axis.axvline(pod.rank, color="tab:green", linestyle="--", linewidth=1)
    axis.set_xlabel("mode")
    axis.set_ylabel("singular value")
    second.set_ylabel("cumulative energy")
    axis.set_title(f"Train-only thermal POD: selected rank {pod.rank}")
    fields = [
        (np.expm1(pod.mean_y).reshape(ny, nx), "train mean rise [K]"),
        (pod.basis[0].reshape(ny, nx), "POD mode 1"),
        (pod.basis[1].reshape(ny, nx) if pod.rank > 1 else np.zeros((ny, nx)), "POD mode 2"),
    ]
    for column, (field, title) in enumerate(fields):
        sub = figure.add_subplot(grid[1, column])
        image = sub.imshow(field, origin="lower", aspect="auto", cmap="coolwarm")
        sub.set_title(title)
        figure.colorbar(image, ax=sub, shrink=0.75)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_field_comparison(
    path: Path,
    cases: Sequence[M1TeacherCase],
    predictions: Mapping[str, Mapping[str, Mapping[str, torch.Tensor]]],
    ambient: float,
) -> None:
    modes = ["reference", "N0", "N1", "N2"]
    figure, axes = plt.subplots(4, 4, figsize=(13, 10), constrained_layout=True)
    for case_index, case in enumerate(cases):
        for mode_index, mode in enumerate(modes):
            if mode == "reference":
                temperature = case.temperature_K
                potential = case.potential_V
            else:
                temperature = predictions[case.case_id][mode]["temperature_K"].detach().cpu().numpy()
                potential = predictions[case.case_id][mode]["potential_V"].detach().cpu().numpy()
            t_axis = axes[2 * case_index, mode_index]
            p_axis = axes[2 * case_index + 1, mode_index]
            t_image = t_axis.imshow(temperature - ambient, origin="lower", aspect="auto")
            p_image = p_axis.imshow(potential, origin="lower", aspect="auto")
            t_axis.set_title(f"{case.case_id}\n{mode} T-rise")
            p_axis.set_title(f"{mode} phi")
            figure.colorbar(t_image, ax=t_axis, shrink=0.65)
            figure.colorbar(p_image, ax=p_axis, shrink=0.65)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_defects(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    selected = [row for row in rows if row["mode"] in {"N0", "N1", "N2"}]
    case_ids = sorted({str(row["case_id"]) for row in selected})
    figure, axis = plt.subplots(figsize=(11, 5), constrained_layout=True)
    x = np.arange(len(case_ids))
    width = 0.24
    for offset, mode in enumerate(("N0", "N1", "N2")):
        values = [
            next(float(row["fixed_point_defect"]) for row in selected if row["case_id"] == case_id and row["mode"] == mode)
            for case_id in case_ids
        ]
        axis.bar(x + (offset - 1) * width, values, width, label=mode)
    axis.set_yscale("log")
    axis.set_xticks(x, case_ids, rotation=25, ha="right")
    axis.set_ylabel("fixed-point defect")
    axis.legend()
    axis.set_title("Fixed-point defect across latent projections")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_ledgers(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    modes = ["N0", "N1", "N2", "NC"]
    selected = [row for row in rows if row["mode"] in modes]
    labels = [f"{row['case_id']}:{row['mode']}" for row in selected]
    terminal = [max(float(row["terminal_electrical_heat_ledger_error"]), 1.0e-18) for row in selected]
    sink = [max(float(row["electrical_heat_sink_ledger_error"]), 1.0e-18) for row in selected]
    x = np.arange(len(labels))
    figure, axis = plt.subplots(figsize=(13, 5), constrained_layout=True)
    axis.semilogy(x, terminal, "o", label="terminal to electrical heat")
    axis.semilogy(x, sink, "s", label="electrical heat to sink")
    axis.set_xticks(x, labels, rotation=65, ha="right", fontsize=7)
    axis.set_ylabel("relative ledger error")
    axis.legend()
    axis.set_title("Port and energy ledgers by projection mode")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_pareto(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    test = [row for row in rows if row["split"] == "test"]
    figure, axis = plt.subplots(figsize=(7, 5), constrained_layout=True)
    for mode in ("COLD", "A2", "N0", "N1", "N2", "NC"):
        subset = [row for row in test if row["mode"] == mode]
        axis.scatter(
            np.mean([row["median_wall_time_s"] for row in subset]),
            np.mean([row["joint_field_score"] for row in subset]),
            s=60,
            label=mode,
        )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("median wall time per case [s]")
    axis.set_ylabel("mean joint field score")
    axis.legend()
    axis.set_title("Speed-accuracy Pareto on the two frozen test cases")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_historical_comparison(
    path: Path, rows: Sequence[Mapping[str, Any]], repository_root: Path
) -> None:
    fast_path = repository_root / "outputs/tables/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/summary.json"
    rescue_path = repository_root / "outputs/tables/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/summary.json"
    fast = json.loads(fast_path.read_text(encoding="utf-8"))
    rescue = json.loads(rescue_path.read_text(encoding="utf-8"))
    m0 = fast["training"]["aggregate_test_metrics"]["M0"]
    p0 = rescue["test_aggregates"]["P0-RCV"]
    n2_rows = [row for row in rows if row["split"] == "test" and row["mode"] == "N2"]
    values = {
        "historical M0": [m0["mean_temperature_relative_l2"], m0["mean_potential_relative_l2"], m0["mean_terminal_current_error"]],
        "historical P0-RCV": [p0["mean_temperature_rise_relative_l2"], p0["mean_potential_relative_l2"], p0["mean_terminal_current_relative_error"]],
        "M1-LatentProj N2": [
            np.mean([row["temperature_rise_relative_l2"] for row in n2_rows]),
            np.mean([row["potential_relative_l2"] for row in n2_rows]),
            np.mean([row["terminal_current_relative_error"] for row in n2_rows]),
        ],
    }
    x = np.arange(3)
    width = 0.25
    figure, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for index, (label, metrics) in enumerate(values.items()):
        axis.bar(x + (index - 1) * width, metrics, width, label=label)
    axis.set_yscale("log")
    axis.set_xticks(x, ["T-rise L2", "phi L2", "current error"])
    axis.legend()
    axis.set_title("Historical direct PINNs vs projected MVE (diagnostic, unmatched objectives)")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _save_prediction(
    path: Path,
    *,
    case: M1TeacherCase,
    mode: str,
    fields: Mapping[str, torch.Tensor],
    operator: M1TorchProjection,
) -> None:
    names = (
        "temperature_input_K",
        "temperature_K",
        "potential_V",
        "conductivity_S_m",
        "electrical_x_face_current_A",
        "electrical_y_face_current_A",
        "thermal_x_face_power_W",
        "thermal_y_face_power_W",
        "internal_joule_cell_W",
        "contact_joule_cell_W",
        "total_joule_cell_W",
        "vertical_sink_cell_W",
        "source_current_A",
        "ground_current_A",
        "terminal_power_W",
        "internal_joule_W",
        "contact_joule_W",
        "total_electrical_heat_W",
        "vertical_sink_W",
        "terminal_electrical_heat_ledger_error",
        "electrical_heat_sink_ledger_error",
    )
    payload: dict[str, Any] = {
        "case_id": np.asarray(case.case_id),
        "mode": np.asarray(mode),
        "evidence_type": np.asarray(EVIDENCE_TYPE),
        "x_m": operator.x_centers_m.detach().cpu().numpy(),
        "y_m": operator.y_centers_m.detach().cpu().numpy(),
        "reference_temperature_K": case.temperature_K,
        "reference_potential_V": case.potential_V,
        "device_voltage_V": np.asarray(case.device_voltage_V),
        "state_coordinate": np.asarray(case.state_coordinate),
        "branch_value": np.asarray(case.branch_value),
        "sink_amplitude": np.asarray(case.sink_amplitude),
    }
    for name in names:
        if name in fields:
            value = fields[name]
            payload[name] = value.detach().cpu().numpy() if isinstance(value, torch.Tensor) else np.asarray(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)


def _test_mode_aggregates(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    aggregates: dict[str, Any] = {}
    for mode in ("COLD", "A2", "N0", "N1", "N2", "NC"):
        subset = [row for row in rows if row["split"] == "test" and row["mode"] == mode]
        aggregates[mode] = {
            "case_count": len(subset),
            "mean_temperature_rise_relative_l2": float(np.mean([row["temperature_rise_relative_l2"] for row in subset])),
            "mean_potential_relative_l2": float(np.mean([row["potential_relative_l2"] for row in subset])),
            "mean_terminal_current_relative_error": float(np.mean([row["terminal_current_relative_error"] for row in subset])),
            "mean_fixed_point_defect": float(np.mean([row["fixed_point_defect"] for row in subset])),
            "mean_sigma_defect": float(np.mean([row["sigma_defect"] for row in subset])),
            "max_energy_ledger_error": float(max(row["energy_ledger_error"] for row in subset)),
            "median_wall_time_s": float(np.median([row["median_wall_time_s"] for row in subset])),
            "median_speedup_vs_cold": float(np.median([row["speedup_vs_cold"] for row in subset])),
            "converged_case_count": sum(bool(row["converged"]) for row in subset),
            "fast_case_pass_count": sum(bool(row["fast_case_pass"]) for row in subset),
            "certified_case_pass_count": sum(bool(row["certified_case_pass"]) for row in subset),
        }
    return aggregates


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    aggregates = summary["test_mode_aggregates"]
    decision = summary["decision"]
    lines = [
        "# Q2 M1 latent solver-projected PINN MVE v1",
        "",
        "## Conclusion",
        "",
        f"Disposition: `{decision['disposition']}`. This is a single-seed diagnostic MVE on literature-guided synthetic numerical digital-twin evidence; it is not formal superiority or experimental validation.",
        "",
        "## Frozen baseline and operator parity",
        "",
        "Base is the unchanged PR #38 squash merge `425d485838ac90cb2b7dba36bad409a9ef931b28`; the result branch is `codex/q2-m1-latent-solver-projected-pinn-mve-v1`. The final commit is recorded in the Git handoff because this report is part of that commit.",
        "",
        "PR #38 remains unchanged as the bounded negative result `NO_GO_M1_RCV_PINN_RESCUE` and was squash-merged before this branch. The dense float64 Torch M1 operator preserves the same Robin contacts, conservative face conductances, boundary-cell Joule partition, contact-corrected thermal closure, localized sink, ports, and ledgers.",
        "",
        f"Parity passed `{summary['operator_parity']['finite_case_count']}/12` cases; worst phi/T map errors were `{summary['operator_parity']['max_phi_relative_l2']:.3e}` and `{summary['operator_parity']['max_mapped_temperature_relative_l2']:.3e}`.",
        "",
        "## Train-only POD and actual training",
        "",
        f"The POD used complete temperature fields from the eight training cases only and selected rank `{summary['pod']['rank']}` at cumulative energy `{summary['pod']['selected_cumulative_energy']:.9f}`. This method is not data-free, mesh-free, or sparse-anchor-only; it is a projection-embedded physics-informed neural reduced-order model.",
        "",
        f"The sole latent network completed `{summary['training']['completed_steps']}` Adam steps in float64 at seed `{summary['training']['seed']}` with wall time `{summary['training']['wall_time_s']:.1f}` s.",
        "",
        "## Frozen test metrics",
        "",
        "| mode | T-rise L2 | phi L2 | current | fixed defect | sigma defect | max ledger | speedup |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in ("N0", "N1", "N2", "NC"):
        row = aggregates[mode]
        lines.append(
            f"| {mode} | {row['mean_temperature_rise_relative_l2']:.5g} | {row['mean_potential_relative_l2']:.5g} | {row['mean_terminal_current_relative_error']:.5g} | {row['mean_fixed_point_defect']:.5g} | {row['mean_sigma_defect']:.5g} | {row['max_energy_ledger_error']:.3e} | {row['median_speedup_vs_cold']:.3g}x |"
        )
    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            f"N2 passed `{decision['fast_test_pass_count']}/2` complete fast test cases, achieved median speedup `{decision['n2_median_speedup_vs_cold']:.3g}x`, and improved mean joint field score over N0 by `{100.0 * decision['n2_joint_field_improvement_over_n0']:.2f}%`. NC passed `{decision['certified_test_pass_count']}/2` certified cases with median total projection updates `{decision['nc_median_total_projection_updates']:.3g}` and speedup `{decision['nc_median_speedup_vs_cold']:.3g}x`.",
            "",
            f"Diagnostic caveat: A2 passed the same fast per-case thresholds on `{decision['a2_fast_like_test_pass_count_diagnostic']}/2` test cases, with mean joint field score `{decision['a2_mean_joint_field_score']:.6g}` versus N2 `{decision['n2_mean_joint_field_score']:.6g}`. Therefore this MVE supports the frozen Fast-GO route but does not support a neural-specific advantage over the analytic two-projection baseline.",
            "",
            "Allowed identity: `M1-LatentProj-PINN`, a learned low-rank initialization embedded in a frozen conservative M1 electrothermal projection. Operator parity is `supported`; M1 reference sufficiency remains `qualified_supported`; this single-seed MVE remains `diagnostic_non_voting`.",
            "",
            "Forbidden sentences: data-free PINN, mesh-free PINN, sparse-anchor-only PINN, formal OOD superiority, experimental validation, full hysteresis, inverse recovery, or zero-shot material transfer.",
            "",
            "## Figures",
            "",
        ]
    )
    for figure in summary["paths"]["figures"]:
        lines.append(f"- `{figure}`")
    lines.extend(
        [
            "",
            "## Single next priority",
            "",
            summary["next_single_priority"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_experiment(config_path: Path, repository_root: Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    base_config = load_yaml(repository_root / config["reference"]["config"])
    context = build_reference_context(base_config, repository_root)
    cases = load_teacher_cases(repository_root / config["reference"]["data_root"])
    if len(cases) != int(config["reference"]["expected_cases"]):
        raise ValueError("frozen M1 case count does not match the preregistration")
    split = split_case_ids(cases, config)
    by_id = case_mapping(cases)
    operator = build_projection_operator(context, base_config)
    processed_root = repository_root / config["outputs"]["processed_root"]
    table_root = repository_root / config["outputs"]["table_root"]
    figure_root = repository_root / config["outputs"]["figure_root"]
    checkpoint_root = repository_root / config["outputs"]["checkpoint_root"]
    for path in (processed_root, table_root, figure_root, checkpoint_root):
        path.mkdir(parents=True, exist_ok=True)

    parity_rows, parity_plotting = operator_parity_rows(
        operator, context, cases, base_config
    )
    parity_summary = operator_parity_summary(parity_rows, config)
    _write_csv(table_root / "m1_projection_parity.csv", parity_rows)
    _write_json(table_root / "m1_projection_parity_summary.json", parity_summary)
    _plot_parity(
        figure_root / "projection_operator_parity.png", parity_rows, parity_plotting
    )
    if not parity_summary["passed"]:
        stopped = {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "evidence_type": EVIDENCE_TYPE,
            "operator_parity": parity_summary,
            "disposition": "NO_GO_DIFFERENTIABLE_M1_OPERATOR_PARITY",
        }
        _write_json(table_root / "summary.json", stopped)
        return stopped

    train_cases = [by_id[case_id] for case_id in split["train"]]
    pod = fit_train_only_pod(
        {case.case_id: case.temperature_K for case in train_cases},
        split["train"],
        ambient_temperature_K=context.ambient_temperature_K,
        cumulative_energy_target=float(config["pod"]["cumulative_energy_target"]),
        rank_cap=int(config["pod"]["rank_cap"]),
        training_sample_rank_cap=int(config["pod"]["training_sample_rank_cap"]),
    )
    np.save(processed_root / "thermal_pod_mean.npy", pod.mean_y)
    np.save(processed_root / "thermal_pod_basis.npy", pod.basis)
    spectrum_rows = [
        {
            "mode_index": index + 1,
            "singular_value": float(value),
            "modal_energy_fraction": float(value**2 / max(np.sum(pod.singular_values**2), 1.0e-30)),
            "cumulative_energy": float(pod.cumulative_energy[index]),
            "selected": bool(index < pod.rank),
        }
        for index, value in enumerate(pod.singular_values)
    ]
    coefficient_rows = [
        {
            "case_id": case_id,
            **{f"a_{index + 1}": float(pod.coefficients[row_index, index]) for index in range(pod.rank)},
            "reconstruction_relative_l2": float(pod.reconstruction_errors[row_index]),
        }
        for row_index, case_id in enumerate(pod.train_case_ids)
    ]
    _write_csv(table_root / "thermal_pod_spectrum.csv", spectrum_rows)
    _write_csv(table_root / "thermal_pod_coefficients.csv", coefficient_rows)
    _plot_pod(
        figure_root / "thermal_pod_spectrum_and_modes.png", pod, operator.ny, operator.nx
    )
    _plot_pod(figure_root / "thermal_pod_spectrum.png", pod, operator.ny, operator.nx)

    seed = int(config["model"]["seed"])
    np.random.seed(seed)
    torch.manual_seed(seed)
    model = build_latent_model(pod, config)
    history, training_summary = train_latent_model(
        model, operator, train_cases, pod, config
    )
    _write_csv(table_root / "training_history.csv", history)
    checkpoint_path = checkpoint_root / "m1_latent_projection_pinn.pt"
    torch.save(
        {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "model_state_dict": model.state_dict(),
            "pod_mean_y": pod.mean_y,
            "pod_basis": pod.basis,
            "coefficient_center": pod.coefficient_center,
            "coefficient_scale": pod.coefficient_scale,
            "rank": pod.rank,
            "seed": seed,
            "train_case_ids": pod.train_case_ids,
            "excluded_validation_case_ids": split["validation"],
            "excluded_test_case_ids": split["test"],
            "completed_steps": training_summary["completed_steps"],
        },
        checkpoint_path,
    )

    model.eval()
    operator.eval()
    prior_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    mode_rows: list[dict[str, Any]] = []
    speed_rows: list[dict[str, Any]] = []
    predictions: dict[str, dict[str, dict[str, torch.Tensor]]] = {}
    try:
        for split_name in ("validation", "test"):
            for case_id in split[split_name]:
                case_rows, case_speed, case_predictions = evaluate_case_modes(
                    model=model,
                    operator=operator,
                    case=by_id[case_id],
                    split=split_name,
                    config=config,
                )
                mode_rows.extend(case_rows)
                speed_rows.extend(case_speed)
                predictions[case_id] = case_predictions
    finally:
        torch.set_num_threads(prior_threads)
    decision = apply_decision_gates(mode_rows, config)
    _write_csv(table_root / "mode_metrics.csv", mode_rows)
    _write_csv(table_root / "speed_benchmark.csv", speed_rows)
    for split_name in ("validation", "test"):
        for case_id in split[split_name]:
            for mode in ("N0", "N1", "N2", "NC"):
                _save_prediction(
                    processed_root / "predictions" / mode.lower() / f"{case_id}.npz",
                    case=by_id[case_id],
                    mode=mode,
                    fields=predictions[case_id][mode],
                    operator=operator,
                )

    test_cases = [by_id[case_id] for case_id in split["test"]]
    _plot_field_comparison(
        figure_root / "field_comparison_n0_n1_n2_reference.png",
        test_cases,
        predictions,
        context.ambient_temperature_K,
    )
    _plot_defects(figure_root / "fixed_point_defect_by_projection.png", mode_rows)
    _plot_ledgers(figure_root / "port_and_ledger_by_projection.png", mode_rows)
    _plot_pareto(figure_root / "speed_accuracy_pareto.png", mode_rows)
    _plot_historical_comparison(
        figure_root / "direct_pinn_vs_projected_method.png", mode_rows, repository_root
    )
    figure_paths = [
        (figure_root / name).relative_to(repository_root).as_posix()
        for name in (
            "thermal_pod_spectrum_and_modes.png",
            "projection_operator_parity.png",
            "field_comparison_n0_n1_n2_reference.png",
            "fixed_point_defect_by_projection.png",
            "port_and_ledger_by_projection.png",
            "speed_accuracy_pareto.png",
            "direct_pinn_vs_projected_method.png",
        )
    ]
    if decision["disposition"] == "GO_M1_LATENT_PROJECTION_PINN_MVE":
        next_priority = "Preregister Q2_M1_LATENT_PROJECTION_PINN_FORMAL_OOD_V1 with analytic A2 as the first neural-specific value comparator; do not execute it in this round."
    elif decision["disposition"] == "PARTIAL_GO_M1_NEURAL_WARMSTART_SOLVER":
        next_priority = "Preregister only a bounded 36-case solver-acceleration benchmark; formal PINN superiority remains forbidden."
    else:
        next_priority = "Stop neural forward architecture work and route the result to the limitation/negative manuscript."
    summary = {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "phase_id": config["phase_id"],
        "evidence_type": EVIDENCE_TYPE,
        "validity": "valid",
        "lifecycle_state": "executed",
        "claim_status": "qualified_supported" if decision["disposition"] != "NO_GO_M1_SOLVER_PROJECTED_ROUTE" else "failed_but_informative",
        "frozen_baseline": config["frozen_baseline"],
        "operator_parity": parity_summary,
        "pod": {
            "rank": pod.rank,
            "selected_cumulative_energy": float(pod.cumulative_energy[pod.rank - 1]),
            "rank_cap_relaxed_by_training_sample_dimension": pod.rank_cap_relaxed,
            "train_case_ids": pod.train_case_ids,
            "validation_and_test_used_for_fit": False,
            "uses_complete_train_fields": True,
            "method_identity": "projection-embedded physics-informed neural reduced-order model",
        },
        "training": training_summary,
        "decision": decision,
        "disposition": decision["disposition"],
        "test_mode_aggregates": _test_mode_aggregates(mode_rows),
        "timing_contract": {
            "fast_repeats": int(config["evaluation"]["fast_timing_repeats"]),
            "cold_and_nc_repeats": int(config["evaluation"]["certified_timing_repeats"]),
            "timed_region_excludes_loading_plotting_and_file_io": True,
            "torch_threads_during_timing": 1,
            "lookahead_defect_diagnostics_excluded_from_timing_and_solve_counts": True,
            "final_convergence_check_electrical_reused_in_cold_and_nc": True,
        },
        "reference_nonlinear_dataset_solves_rerun": 0,
        "evaluation_cold_solves_are_timing_baselines_not_new_reference_data": True,
        "claim_boundary": {**config["claim_boundary"], "operator_parity": "supported"},
        "paths": {
            "processed_root": config["outputs"]["processed_root"],
            "table_root": config["outputs"]["table_root"],
            "figure_root": config["outputs"]["figure_root"],
            "checkpoint": checkpoint_path.relative_to(repository_root).as_posix(),
            "report": config["outputs"]["report"],
            "figures": figure_paths,
        },
        "next_single_priority": next_priority,
    }
    _write_json(table_root / "summary.json", summary)
    _write_report(repository_root / config["outputs"]["report"], summary)
    return summary
