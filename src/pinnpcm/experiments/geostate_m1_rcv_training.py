"""Fixed-sample training and isomorphic evaluation for the M1 RCV rescue."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import (
    GeoStateReferenceContext,
    material_parameters,
)
from pinnpcm.experiments.geostate_m1_compatibility import M1TeacherCase
from pinnpcm.pinn.geostate_m1_rcv_pinn import GeoStateM1RCVPINN


@dataclass(frozen=True)
class FixedCaseSamples:
    collocation_xy: np.ndarray
    control_volume_bounds: np.ndarray
    control_volume_regions: np.ndarray
    interface_y: np.ndarray
    interface_ids: np.ndarray
    boundary_y: np.ndarray
    volume_xy: np.ndarray


@dataclass(frozen=True)
class TrainingOutcome:
    model_name: str
    model: GeoStateM1RCVPINN
    history: list[dict[str, Any]]
    finite: bool
    completed_steps: int
    wall_time_s: float
    parameter_count: int
    gradient_norms: dict[str, float]
    gradient_ratio: float


class GradientScaleDefect(RuntimeError):
    def __init__(self, model_name: str, ratio: float, norms: Mapping[str, float]):
        super().__init__(f"{model_name} gradient-scale ratio {ratio:.6g} exceeds gate")
        self.model_name = model_name
        self.ratio = float(ratio)
        self.norms = dict(norms)


def build_model(
    model_name: str,
    context: GeoStateReferenceContext,
    rescue_config: Mapping[str, Any],
    base_config: Mapping[str, Any],
) -> GeoStateM1RCVPINN:
    model_config = dict(rescue_config["model"])
    contact = base_config["physical_model"]["model_forms"]["M1"]
    model_config.update(
        {
            "rc_left_ohm": float(contact["electrical_contact_resistance_ohm"]["left"]),
            "rc_right_ohm": float(contact["electrical_contact_resistance_ohm"]["right"]),
            "rth_left_m2K_W": float(
                contact["thermal_contact_resistance_m2K_W"]["left"]
            ),
            "rth_right_m2K_W": float(
                contact["thermal_contact_resistance_m2K_W"]["right"]
            ),
            "defect_coordinate": float(base_config["physical_model"]["material"]["c_v"]),
        }
    )
    rectangle = base_config["physical_model"]["localized_sink"]["rectangle_m"]
    geometry = {
        "length_m": context.length_m,
        "width_m": context.width_m,
        "thickness_m": context.grid.thickness_m,
        "contact_overlap_m": context.grid.contact_overlap_m,
        "sink_rectangle_norm": (
            float(rectangle["x"][0]) / context.length_m,
            float(rectangle["x"][1]) / context.length_m,
            float(rectangle["y"][0]) / context.width_m,
            float(rectangle["y"][1]) / context.width_m,
        ),
        "sink_amplitude_max": float(
            base_config["physical_model"]["localized_sink"]["amplitude"]
        ),
    }
    thermal = {
        "ambient_temperature_K": context.ambient_temperature_K,
        "vertical_conductance_W_m2K": float(
            context.thermal_fields.vertical_conductance_W_m2K
        ),
        "vo2_sheet_thermal_W_K": float(
            context.thermal_fields.vo2_sheet_conductance_W_K
        ),
        "electrode_sheet_thermal_W_K": float(
            context.thermal_fields.electrode_sheet_conductance_W_K
        ),
    }
    return GeoStateM1RCVPINN(
        model_kind=model_name,
        config=model_config,
        geometry=geometry,
        thermal=thermal,
        material_params=material_parameters(base_config),
        seed=int(model_config["seed"]),
    ).to(dtype=torch.float64)


def case_inputs(
    case: M1TeacherCase,
    x: np.ndarray,
    y: np.ndarray,
    model: GeoStateM1RCVPINN,
    *,
    requires_grad: bool = False,
) -> torch.Tensor:
    x_values = np.asarray(x, dtype=float).reshape(-1)
    y_values = np.asarray(y, dtype=float).reshape(-1)
    values = np.column_stack(
        [
            x_values,
            y_values,
            np.full(x_values.size, case.device_voltage_V / model.voltage_scale_V),
            np.full(x_values.size, case.branch_value),
            np.full(x_values.size, case.state_coordinate),
            np.full(x_values.size, case.sink_amplitude),
        ]
    )
    return torch.as_tensor(values, dtype=torch.float64).requires_grad_(requires_grad)


def _choose_without_overlap(
    rng: np.random.Generator,
    candidates: np.ndarray,
    count: int,
    used: set[int],
) -> list[int]:
    available = np.asarray([value for value in candidates if int(value) not in used])
    if available.size < count:
        raise ValueError("insufficient geometry-only anchor candidates")
    selected = rng.choice(available, size=count, replace=False).astype(int).tolist()
    used.update(selected)
    return selected


def build_anchor_indices(
    cases: Sequence[M1TeacherCase],
    context: GeoStateReferenceContext,
    rescue_config: Mapping[str, Any],
) -> dict[str, list[int]]:
    grid = context.grid
    xx, yy = np.meshgrid(
        grid.x_centers_m / context.length_m,
        grid.y_centers_m / context.width_m,
    )
    total = xx.size
    dataset = rescue_config["dataset"]
    count = max(
        int(dataset["minimum_anchor_points_per_train_case"]),
        int(round(float(dataset["anchor_fraction"]) * total)),
    )
    counts = (int(round(0.40 * count)), int(round(0.30 * count)))
    counts = (counts[0], counts[1], count - counts[0] - counts[1])
    contact_fraction = grid.contact_overlap_m / context.length_m
    dx = grid.dx_m / context.length_m
    dy = grid.dy_m / context.width_m
    interface_mask = (
        (xx < contact_fraction + 1.5 * dx)
        | (xx > 1.0 - contact_fraction - 1.5 * dx)
    )
    rectangle = rescue_config.get("_sink_rectangle_norm")
    if rectangle is None:
        rectangle = (0.30, 0.70, 0.60, 1.00)
    x0, x1, y0, y1 = [float(value) for value in rectangle]
    sink_mask = (
        (xx >= x0 - 1.5 * dx)
        & (xx <= x1 + 1.5 * dx)
        & (yy >= y0 - 1.5 * dy)
        & (yy <= y1 + 1.5 * dy)
    )
    all_indices = np.arange(total)
    interface_indices = np.flatnonzero(interface_mask.reshape(-1))
    sink_indices = np.flatnonzero(sink_mask.reshape(-1))
    rng = np.random.default_rng(int(rescue_config["model"]["seed"]))
    output: dict[str, list[int]] = {}
    for case in cases:
        used: set[int] = set()
        chosen = _choose_without_overlap(rng, all_indices, counts[0], used)
        chosen += _choose_without_overlap(rng, interface_indices, counts[1], used)
        chosen += _choose_without_overlap(rng, sink_indices, counts[2], used)
        output[case.case_id] = sorted(chosen)
    return output


def anchor_tensors(
    cases: Sequence[M1TeacherCase],
    model: GeoStateM1RCVPINN,
    context: GeoStateReferenceContext,
    indices_by_case: Mapping[str, Sequence[int]],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    grid = context.grid
    xx, yy = np.meshgrid(
        grid.x_centers_m / context.length_m,
        grid.y_centers_m / context.width_m,
    )
    inputs, phi_targets, temperature_targets = [], [], []
    for case in cases:
        indices = np.asarray(indices_by_case[case.case_id], dtype=int)
        inputs.append(case_inputs(case, xx.reshape(-1)[indices], yy.reshape(-1)[indices], model))
        phi_targets.append(
            torch.as_tensor(
                case.potential_V.reshape(-1)[indices, None] / model.voltage_scale_V,
                dtype=torch.float64,
            )
        )
        temperature_targets.append(
            torch.as_tensor(
                (
                    case.temperature_K.reshape(-1)[indices, None]
                    - model.ambient_temperature_K
                )
                / model.temperature_scale_K,
                dtype=torch.float64,
            )
        )
    return torch.cat(inputs), torch.cat(phi_targets), torch.cat(temperature_targets)


def build_fixed_samples(
    cases: Sequence[M1TeacherCase],
    context: GeoStateReferenceContext,
    rescue_config: Mapping[str, Any],
) -> dict[str, FixedCaseSamples]:
    grid = context.grid
    sampling = rescue_config["sampling"]
    rng = np.random.default_rng(int(rescue_config["model"]["seed"]) + 17)
    contact = grid.contact_overlap_m / context.length_m
    domains = ((0.0, contact), (contact, 1.0 - contact), (1.0 - contact, 1.0))
    all_bounds = []
    all_regions = []
    for iy in range(grid.ny):
        for ix in range(grid.nx):
            all_bounds.append(
                [
                    grid.x_edges_m[ix] / context.length_m,
                    grid.x_edges_m[ix + 1] / context.length_m,
                    grid.y_edges_m[iy] / context.width_m,
                    grid.y_edges_m[iy + 1] / context.width_m,
                ]
            )
            all_regions.append(
                0
                if grid.left_contact_mask[iy, ix]
                else 2
                if grid.right_contact_mask[iy, ix]
                else 1
            )
    all_bounds_array = np.asarray(all_bounds, dtype=float)
    all_regions_array = np.asarray(all_regions, dtype=int)
    boundary_candidates = np.flatnonzero(
        np.isclose(all_bounds_array[:, 0], 0.0) | np.isclose(all_bounds_array[:, 1], 1.0)
    )
    interface_candidates = np.flatnonzero(
        np.isclose(all_bounds_array[:, 0], contact)
        | np.isclose(all_bounds_array[:, 1], contact)
        | np.isclose(all_bounds_array[:, 0], 1.0 - contact)
        | np.isclose(all_bounds_array[:, 1], 1.0 - contact)
    )
    output: dict[str, FixedCaseSamples] = {}
    for case in cases:
        collocation_count = int(sampling["collocation_points_per_case"])
        per_domain = [collocation_count // 3] * 3
        per_domain[-1] += collocation_count - sum(per_domain)
        points = []
        for (lower, upper), count in zip(domains, per_domain, strict=True):
            margin = min(1.0e-3, 0.05 * (upper - lower))
            points.append(
                np.column_stack(
                    [
                        rng.uniform(lower + margin, upper - margin, count),
                        rng.uniform(1.0e-3, 1.0 - 1.0e-3, count),
                    ]
                )
            )
        collocation = np.vstack(points)

        cv_count = int(sampling["control_volumes_per_case"])
        mandatory = np.unique(
            np.concatenate(
                [
                    rng.choice(boundary_candidates, size=min(8, boundary_candidates.size), replace=False),
                    rng.choice(interface_candidates, size=min(8, interface_candidates.size), replace=False),
                ]
            )
        )
        remaining = np.setdiff1d(np.arange(all_bounds_array.shape[0]), mandatory)
        extra = rng.choice(remaining, size=cv_count - mandatory.size, replace=False)
        chosen = np.sort(np.concatenate([mandatory, extra]))
        interface_count = int(sampling["interface_points_per_case"])
        interface_ids = np.arange(interface_count) % 2
        interface_y = (np.arange(interface_count) + 0.5) / interface_count
        boundary_count = int(sampling["boundary_points_per_case"])
        boundary_y = (np.arange(boundary_count) + 0.5) / boundary_count
        volume_count = max(64, collocation_count)
        volume_xy = np.column_stack(
            [rng.random(volume_count), rng.random(volume_count)]
        )
        output[case.case_id] = FixedCaseSamples(
            collocation_xy=collocation,
            control_volume_bounds=all_bounds_array[chosen],
            control_volume_regions=all_regions_array[chosen],
            interface_y=interface_y,
            interface_ids=interface_ids,
            boundary_y=boundary_y,
            volume_xy=volume_xy,
        )
    return output


def _sample_tensors(
    case: M1TeacherCase,
    sample: FixedCaseSamples,
    model: GeoStateM1RCVPINN,
) -> dict[str, torch.Tensor]:
    collocation = case_inputs(
        case, sample.collocation_xy[:, 0], sample.collocation_xy[:, 1], model, requires_grad=True
    )
    interface_x = np.where(
        sample.interface_ids == 0, model.contact_fraction, 1.0 - model.contact_fraction
    )
    interface = case_inputs(case, interface_x, sample.interface_y, model, requires_grad=True)
    left = case_inputs(
        case, np.zeros(sample.boundary_y.size), sample.boundary_y, model, requires_grad=True
    )
    right = case_inputs(
        case, np.ones(sample.boundary_y.size), sample.boundary_y, model, requires_grad=True
    )
    volume = case_inputs(
        case, sample.volume_xy[:, 0], sample.volume_xy[:, 1], model, requires_grad=True
    )
    centers = 0.5 * (
        sample.control_volume_bounds[:, [0, 2]]
        + sample.control_volume_bounds[:, [1, 3]]
    )
    cv_base = case_inputs(case, centers[:, 0], centers[:, 1], model)
    return {
        "collocation": collocation,
        "interface": interface,
        "interface_ids": torch.as_tensor(sample.interface_ids, dtype=torch.long),
        "left": left,
        "right": right,
        "volume": volume,
        "cv_base": cv_base,
        "cv_bounds": torch.as_tensor(sample.control_volume_bounds, dtype=torch.float64),
        "cv_regions": torch.as_tensor(sample.control_volume_regions, dtype=torch.long),
    }


def _gradient_norms(
    losses: Mapping[str, torch.Tensor], model: GeoStateM1RCVPINN
) -> tuple[dict[str, float], float]:
    norms: dict[str, float] = {}
    parameters = tuple(model.parameters())
    for name, loss in losses.items():
        if not loss.requires_grad or float(torch.abs(loss).detach()) == 0.0:
            continue
        gradients = torch.autograd.grad(
            loss, parameters, retain_graph=True, allow_unused=True
        )
        norm = torch.sqrt(
            sum(
                torch.sum(gradient.square())
                for gradient in gradients
                if gradient is not None
            )
        )
        value = float(norm.detach())
        if np.isfinite(value) and value > 0.0:
            norms[name] = value
    values = np.asarray(list(norms.values()), dtype=float)
    ratio = float(np.max(values) / np.median(values)) if values.size else 1.0
    return norms, ratio


def train_model(
    model_name: str,
    context: GeoStateReferenceContext,
    rescue_config: Mapping[str, Any],
    base_config: Mapping[str, Any],
    train_cases: Sequence[M1TeacherCase],
    anchor_indices: Mapping[str, Sequence[int]],
    samples: Mapping[str, FixedCaseSamples],
    target_currents_A: Mapping[str, float],
) -> TrainingOutcome:
    model = build_model(model_name, context, rescue_config, base_config)
    anchor_input, target_phi, target_t = anchor_tensors(
        train_cases, model, context, anchor_indices
    )
    contract = rescue_config["training"]
    stage1_steps = int(contract["stage1_steps"])
    stage2_steps = int(contract["stage2_steps"])
    requested_steps = stage1_steps + stage2_steps
    weights = contract["fixed_loss_weights"]
    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(contract["stage1_learning_rate"])
    )
    history: list[dict[str, Any]] = []
    gradient_norms: dict[str, float] = {}
    gradient_ratio = 1.0
    started = perf_counter()
    finite = True
    completed = 0
    for step_index in range(requested_steps):
        step = step_index + 1
        if perf_counter() - started > float(contract["maximum_wall_time_s_per_model"]):
            finite = False
            break
        if step == stage1_steps + 1:
            for group in optimizer.param_groups:
                group["lr"] = float(contract["stage2_learning_rate"])
        optimizer.zero_grad(set_to_none=True)
        losses = {
            name: torch.zeros((), dtype=torch.float64)
            for name in (
                "anchor",
                "constitutive",
                "local_current_cv",
                "local_energy_cv",
                "external_robin",
                "interface_state",
                "interface_flux",
                "port",
                "ledger",
            )
        }
        losses["anchor"] = model.anchor_loss(anchor_input, target_phi, target_t)
        if model_name != "B0-R":
            case = train_cases[step_index % len(train_cases)]
            tensors = _sample_tensors(case, samples[case.case_id], model)
            losses["external_robin"], _ = model.external_robin(
                tensors["left"], tensors["right"]
            )
            losses["interface_state"], interface_flux, _ = model.interface_terms(
                tensors["interface"], tensors["interface_ids"]
            )
            if step > stage1_steps:
                losses["interface_flux"] = interface_flux
                if model_name == "P0-RCV":
                    losses["constitutive"] = model.constitutive_loss(tensors["collocation"])
                    current_residual, energy_residual = model.control_volume_residuals(
                        tensors["cv_base"], tensors["cv_bounds"], tensors["cv_regions"]
                    )
                    losses["local_current_cv"] = torch.mean(current_residual.square())
                    losses["local_energy_cv"] = torch.mean(energy_residual.square())
                else:
                    losses["local_current_cv"], losses["local_energy_cv"] = (
                        model.strong_form_losses(tensors["collocation"])
                    )
                target_current = torch.as_tensor(
                    target_currents_A[case.case_id], dtype=torch.float64
                )
                losses["port"], losses["ledger"], _ = model.port_and_ledger(
                    tensors["left"], tensors["right"], tensors["volume"], target_current
                )
        if step == stage1_steps + 1 and model_name != "B0-R":
            gradient_norms, gradient_ratio = _gradient_norms(losses, model)
            if gradient_ratio > float(contract["gradient_scale_ratio_max"]):
                raise GradientScaleDefect(model_name, gradient_ratio, gradient_norms)
        total = sum(float(weights[name]) * value for name, value in losses.items())
        if not torch.isfinite(total):
            finite = False
            break
        total.backward()
        if not all(
            parameter.grad is None or torch.isfinite(parameter.grad).all()
            for parameter in model.parameters()
        ):
            finite = False
            break
        torch.nn.utils.clip_grad_norm_(
            model.parameters(), max_norm=float(contract["clip_grad_norm"])
        )
        optimizer.step()
        completed = step
        stride = int(contract["history_stride"])
        if step == 1 or step % stride == 0 or step in {stage1_steps, stage1_steps + 1, requested_steps}:
            history.append(
                {
                    "model": model_name,
                    "step": step,
                    "stage": 1 if step <= stage1_steps else 2,
                    **{f"{name}_loss": float(value.detach()) for name, value in losses.items()},
                    "total_loss": float(total.detach()),
                    "finite": True,
                }
            )
    return TrainingOutcome(
        model_name=model_name,
        model=model,
        history=history,
        finite=finite,
        completed_steps=completed,
        wall_time_s=float(perf_counter() - started),
        parameter_count=model.parameter_count(),
        gradient_norms=gradient_norms,
        gradient_ratio=gradient_ratio,
    )


def full_grid_samples(
    case: M1TeacherCase,
    context: GeoStateReferenceContext,
    model: GeoStateM1RCVPINN,
) -> dict[str, torch.Tensor]:
    grid = context.grid
    xx, yy = np.meshgrid(
        grid.x_centers_m / context.length_m,
        grid.y_centers_m / context.width_m,
    )
    y_boundary = grid.y_centers_m / context.width_m
    left = case_inputs(case, np.zeros(grid.ny), y_boundary, model, requires_grad=True)
    right = case_inputs(case, np.ones(grid.ny), y_boundary, model, requires_grad=True)
    volume = case_inputs(case, xx.reshape(-1), yy.reshape(-1), model, requires_grad=True)
    interface_y = np.tile(y_boundary, 2)
    interface_ids = np.repeat([0, 1], grid.ny)
    interface_x = np.where(
        interface_ids == 0, model.contact_fraction, 1.0 - model.contact_fraction
    )
    interface = case_inputs(case, interface_x, interface_y, model, requires_grad=True)
    bounds, regions = [], []
    for iy in range(grid.ny):
        for ix in range(grid.nx):
            bounds.append(
                [
                    grid.x_edges_m[ix] / context.length_m,
                    grid.x_edges_m[ix + 1] / context.length_m,
                    grid.y_edges_m[iy] / context.width_m,
                    grid.y_edges_m[iy + 1] / context.width_m,
                ]
            )
            regions.append(
                0 if grid.left_contact_mask[iy, ix] else 2 if grid.right_contact_mask[iy, ix] else 1
            )
    bounds_array = np.asarray(bounds)
    centers = 0.5 * (bounds_array[:, [0, 2]] + bounds_array[:, [1, 3]])
    cv_base = case_inputs(case, centers[:, 0], centers[:, 1], model)
    return {
        "volume": volume,
        "left": left,
        "right": right,
        "interface": interface,
        "interface_ids": torch.as_tensor(interface_ids, dtype=torch.long),
        "cv_base": cv_base,
        "cv_bounds": torch.as_tensor(bounds_array, dtype=torch.float64),
        "cv_regions": torch.as_tensor(regions, dtype=torch.long),
    }


def evaluate_case(
    outcome: TrainingOutcome,
    case: M1TeacherCase,
    context: GeoStateReferenceContext,
    rescue_config: Mapping[str, Any],
    target_current_A: float,
    *,
    split: str,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    model = outcome.model
    tensors = full_grid_samples(case, context, model)
    fields = model.field_outputs(tensors["volume"])
    shape = context.grid.shape
    prediction = {
        name: value.detach().cpu().numpy().reshape(shape)
        for name, value in fields.items()
        if name in {"phi_V", "T_K", "Jx_A_m", "Jy_A_m", "qx_W_m", "qy_W_m", "sigma_S_m"}
    }
    ambient = model.ambient_temperature_K
    t_reference = case.temperature_K - ambient
    t_prediction = prediction["T_K"] - ambient
    temperature_error = float(
        np.linalg.norm(t_prediction - t_reference) / max(np.linalg.norm(t_reference), 1.0e-30)
    )
    potential_error = float(
        np.linalg.norm(prediction["phi_V"] - case.potential_V)
        / max(np.linalg.norm(case.potential_V), 1.0e-30)
    )
    target = torch.as_tensor(target_current_A, dtype=torch.float64)
    _, _, ledger = model.port_and_ledger(
        tensors["left"], tensors["right"], tensors["volume"], target
    )
    predicted_current = 0.5 * (
        float(ledger["source_current_A"].detach())
        + float(ledger["ground_current_A"].detach())
    )
    current_error = abs(predicted_current - target_current_A) / max(
        abs(target_current_A), 1.0e-30
    )
    _, _, interface = model.interface_terms(
        tensors["interface"], tensors["interface_ids"]
    )
    current_cv, energy_cv = model.control_volume_residuals(
        tensors["cv_base"], tensors["cv_bounds"], tensors["cv_regions"]
    )
    current_cv_values = np.abs(current_cv.detach().cpu().numpy().reshape(shape))
    energy_cv_values = np.abs(energy_cv.detach().cpu().numpy().reshape(shape))
    reference_peak = np.unravel_index(int(np.argmax(case.temperature_K)), shape)
    predicted_peak = np.unravel_index(int(np.argmax(prediction["T_K"])), shape)
    dx = (predicted_peak[1] - reference_peak[1]) * context.grid.dx_m
    dy = (predicted_peak[0] - reference_peak[0]) * context.grid.dy_m
    hotspot_error = float(np.hypot(dx, dy) / context.width_m)
    energy_error = float(ledger["energy_ledger_error"].detach())
    interface_error = float(interface["metric"].detach())
    current_p95 = float(np.percentile(current_cv_values, 95))
    energy_p95 = float(np.percentile(energy_cv_values, 95))
    finite = bool(
        outcome.finite
        and all(np.isfinite(value).all() for value in prediction.values())
        and np.isfinite(
            [
                temperature_error,
                potential_error,
                current_error,
                energy_error,
                interface_error,
                current_p95,
                energy_p95,
                hotspot_error,
            ]
        ).all()
    )
    gates = rescue_config["engineering_screen"]
    passed = bool(
        finite
        and temperature_error <= float(gates["temperature_rise_relative_l2_max"])
        and potential_error <= float(gates["potential_relative_l2_max"])
        and current_error <= float(gates["terminal_current_relative_error_max"])
        and energy_error <= float(gates["energy_ledger_relative_error_max"])
        and interface_error <= float(gates["interface_flux_mismatch_max"])
        and current_p95 <= float(gates["local_current_cv_p95_max"])
        and energy_p95 <= float(gates["local_energy_cv_p95_max"])
    )
    metrics = {
        "model": outcome.model_name,
        "case_id": case.case_id,
        "split": split,
        "temperature_rise_relative_l2": temperature_error,
        "potential_relative_l2": potential_error,
        "joint_field_score": 0.5 * (temperature_error + potential_error),
        "terminal_current_relative_error": current_error,
        "predicted_terminal_current_A": predicted_current,
        "target_terminal_current_A": target_current_A,
        "energy_ledger_relative_error": energy_error,
        "interface_flux_mismatch": interface_error,
        "local_current_cv_residual_p95": current_p95,
        "local_energy_cv_residual_p95": energy_p95,
        "hotspot_coordinate_error_width_fraction": hotspot_error,
        "finite": finite,
        "passes_complete_case_gate": passed,
    }
    prediction["local_current_cv_residual"] = current_cv_values
    prediction["local_energy_cv_residual"] = energy_cv_values
    return metrics, prediction


def aggregate_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    numeric = (
        "temperature_rise_relative_l2",
        "potential_relative_l2",
        "joint_field_score",
        "terminal_current_relative_error",
        "energy_ledger_relative_error",
        "interface_flux_mismatch",
        "local_current_cv_residual_p95",
        "local_energy_cv_residual_p95",
        "hotspot_coordinate_error_width_fraction",
    )
    aggregate: dict[str, Any] = {
        f"mean_{name}": float(np.mean([float(row[name]) for row in rows]))
        for name in numeric
    }
    aggregate.update(
        {
            "case_count": len(rows),
            "complete_case_pass_count": sum(
                bool(row["passes_complete_case_gate"]) for row in rows
            ),
            "all_finite": all(bool(row["finite"]) for row in rows),
        }
    )
    return aggregate


def decide_disposition(
    test_aggregates: Mapping[str, Mapping[str, Any]],
    rescue_config: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    gates = rescue_config["engineering_screen"]
    b0, b1, p0 = (
        test_aggregates["B0-R"],
        test_aggregates["B1-R"],
        test_aggregates["P0-RCV"],
    )
    field_improvement = (
        float(b0["mean_joint_field_score"]) - float(p0["mean_joint_field_score"])
    ) / max(float(b0["mean_joint_field_score"]), 1.0e-30)
    b1_conservation = max(
        float(b1["mean_energy_ledger_relative_error"]),
        float(b1["mean_interface_flux_mismatch"]),
    )
    p0_conservation = max(
        float(p0["mean_energy_ledger_relative_error"]),
        float(p0["mean_interface_flux_mismatch"]),
    )
    conservation_factor = b1_conservation / max(p0_conservation, 1.0e-30)
    catastrophic = any(
        float(p0[name])
        > float(gates["catastrophic_regression_factor"]) * max(float(b1[name]), 1.0e-30)
        for name in (
            "mean_temperature_rise_relative_l2",
            "mean_potential_relative_l2",
            "mean_terminal_current_relative_error",
        )
    )
    p0_more_passes = int(p0["complete_case_pass_count"]) > int(
        b1["complete_case_pass_count"]
    )
    go = bool(
        int(p0["complete_case_pass_count"]) >= int(gates["required_p0_test_passes"])
        and field_improvement >= float(gates["field_improvement_over_b0_min"])
        and (
            conservation_factor
            >= float(gates["conservation_improvement_over_b1_min"])
            or p0_more_passes
        )
        and not catastrophic
    )
    if go:
        disposition = "GO_M1_RCV_PINN_IDEA_SCREEN"
    elif int(b1["complete_case_pass_count"]) >= 1:
        disposition = "PARTIAL_GO_M1_STRONG_FORM_ONLY"
    else:
        disposition = "NO_GO_M1_RCV_PINN_RESCUE"
    return disposition, {
        "p0_test_pass_count": int(p0["complete_case_pass_count"]),
        "b1_test_pass_count": int(b1["complete_case_pass_count"]),
        "p0_field_improvement_over_b0": float(field_improvement),
        "p0_conservation_improvement_factor_over_b1": float(conservation_factor),
        "p0_more_complete_passes_than_b1": bool(p0_more_passes),
        "catastrophic_regression_vs_b1": bool(catastrophic),
        "all_minimum_go_conditions_met": bool(go),
    }
