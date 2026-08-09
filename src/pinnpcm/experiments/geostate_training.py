"""Training and scoring utilities for the GeoState fast-track screen."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import (
    GeoStateCase,
    GeoStateReferenceContext,
    GeoStateReferenceResult,
    material_parameters,
)
from pinnpcm.pinn.geostate_mc_pinn import GeoStateMCPINN


FIELD_NAMES = ("phi_V", "T_K", "Jx_A_m", "Jy_A_m", "qx_W_m", "qy_W_m")
REFERENCE_NAMES = {
    "phi_V": "potential_V",
    "T_K": "temperature_K",
    "Jx_A_m": "Jx_A_m",
    "Jy_A_m": "Jy_A_m",
    "qx_W_m": "qx_W_m",
    "qy_W_m": "qy_W_m",
}


@dataclass(frozen=True)
class TrainingOutcome:
    model_name: str
    model: GeoStateMCPINN
    history: list[dict[str, float | int | str | bool]]
    finite: bool
    completed_steps: int
    wall_time_s: float
    parameter_count: int


def model_config(
    context: GeoStateReferenceContext, config: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
    pinn = config["pinn"]
    rectangle = config["physical_model"]["localized_sink"]["rectangle_m"]
    length = context.length_m
    width = context.width_m
    network = {
        "hidden_width": int(pinn["hidden_width"]),
        "hidden_layers": int(pinn["hidden_layers"]),
        "scales": dict(pinn["scales"]),
        "material_params": material_parameters(config),
        "defect_coordinate": float(config["physical_model"]["material"]["c_v"]),
    }
    geometry = {
        "length_m": length,
        "width_m": width,
        "thickness_m": float(context.grid.thickness_m),
        "contact_overlap_m": float(context.grid.contact_overlap_m),
        "sink_rectangle_norm": (
            float(rectangle["x"][0]) / length,
            float(rectangle["x"][1]) / length,
            float(rectangle["y"][0]) / width,
            float(rectangle["y"][1]) / width,
        ),
        "sink_amplitude_max": float(
            config["physical_model"]["localized_sink"]["amplitude"]
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
    return network, geometry, thermal


def build_model(
    model_name: str,
    context: GeoStateReferenceContext,
    config: Mapping[str, Any],
) -> GeoStateMCPINN:
    network, geometry, thermal = model_config(context, config)
    return GeoStateMCPINN(
        model_kind=model_name,
        config=network,
        geometry=geometry,
        thermal=thermal,
        seed=int(config["pinn"]["seed"]),
    )


def _case_inputs(
    case: GeoStateCase,
    x_norm: np.ndarray,
    y_norm: np.ndarray,
    voltage_scale_V: float,
    *,
    dtype: torch.dtype,
) -> torch.Tensor:
    x = np.asarray(x_norm, dtype=np.float32).reshape(-1)
    y = np.asarray(y_norm, dtype=np.float32).reshape(-1)
    count = x.size
    values = np.column_stack(
        [
            x,
            y,
            np.full(count, case.device_voltage_V / voltage_scale_V),
            np.full(count, case.branch_value),
            np.full(count, case.state_coordinate),
            np.full(count, case.sink_amplitude),
        ]
    )
    return torch.as_tensor(values, dtype=dtype)


def _normalized_target_arrays(
    result: GeoStateReferenceResult, model: GeoStateMCPINN, indices: np.ndarray
) -> dict[str, torch.Tensor]:
    targets: dict[str, torch.Tensor] = {}
    for name, reference_name in REFERENCE_NAMES.items():
        values = np.asarray(result.fields[reference_name], dtype=np.float32).reshape(-1)[indices]
        tensor = torch.as_tensor(values.reshape(-1, 1), dtype=next(model.parameters()).dtype)
        if name == "phi_V":
            tensor = tensor / model.scales.voltage_V
        elif name == "T_K":
            tensor = (tensor - model.ambient_temperature_K) / model.scales.temperature_rise_K
        elif name.startswith("J"):
            tensor = tensor / model.scales.sheet_current_A_m
        else:
            tensor = tensor / model.scales.sheet_heat_flux_W_m
        targets[name] = tensor
    return targets


def build_anchor_tensors(
    train_results: Sequence[GeoStateReferenceResult],
    model: GeoStateMCPINN,
    config: Mapping[str, Any],
) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, list[int]]]:
    dataset = config["pilot_dataset"]
    rng = np.random.default_rng(int(config["pinn"]["seed"]))
    all_inputs: list[torch.Tensor] = []
    all_targets: dict[str, list[torch.Tensor]] = {name: [] for name in FIELD_NAMES}
    indices_by_case: dict[str, list[int]] = {}
    dtype = next(model.parameters()).dtype
    for result in train_results:
        grid = result.grid
        xx, yy = np.meshgrid(
            grid.x_centers_m / grid.x_edges_m[-1],
            grid.y_centers_m / grid.y_edges_m[-1],
        )
        total = xx.size
        count = max(
            int(dataset["minimum_anchor_points_per_train_case"]),
            int(round(float(dataset["anchor_fraction"]) * total)),
        )
        indices = np.sort(rng.choice(total, size=count, replace=False))
        indices_by_case[result.case.case_id] = indices.tolist()
        all_inputs.append(
            _case_inputs(
                result.case,
                xx.reshape(-1)[indices],
                yy.reshape(-1)[indices],
                model.scales.voltage_V,
                dtype=dtype,
            )
        )
        targets = _normalized_target_arrays(result, model, indices)
        for name in FIELD_NAMES:
            all_targets[name].append(targets[name])
    return (
        torch.cat(all_inputs, dim=0),
        {name: torch.cat(values, dim=0) for name, values in all_targets.items()},
        indices_by_case,
    )


def _sample_case_inputs(
    rng: np.random.Generator,
    cases: Sequence[GeoStateCase],
    count: int,
    model: GeoStateMCPINN,
) -> torch.Tensor:
    selected = rng.integers(0, len(cases), size=count)
    x = rng.random(count)
    y = rng.random(count)
    dtype = next(model.parameters()).dtype
    values = np.column_stack(
        [
            x,
            y,
            np.asarray(
                [cases[int(index)].device_voltage_V for index in selected]
            )
            / model.scales.voltage_V,
            np.asarray([cases[int(index)].branch_value for index in selected]),
            np.asarray([cases[int(index)].state_coordinate for index in selected]),
            np.asarray([cases[int(index)].sink_amplitude for index in selected]),
        ]
    )
    return torch.as_tensor(values, dtype=dtype).requires_grad_(True)


def _interface_pairs(
    rng: np.random.Generator,
    cases: Sequence[GeoStateCase],
    count: int,
    model: GeoStateMCPINN,
) -> tuple[torch.Tensor, torch.Tensor]:
    selected = rng.integers(0, len(cases), size=count)
    y = rng.random(count)
    left_interface = np.arange(count) % 2 == 0
    center = np.where(
        left_interface,
        model.contact_overlap_fraction,
        1.0 - model.contact_overlap_fraction,
    )
    epsilon = 1.0e-4
    x_minus = center - epsilon
    x_plus = center + epsilon
    dtype = next(model.parameters()).dtype
    voltage = np.asarray(
        [cases[int(index)].device_voltage_V for index in selected]
    ) / model.scales.voltage_V
    branch = np.asarray([cases[int(index)].branch_value for index in selected])
    state = np.asarray([cases[int(index)].state_coordinate for index in selected])
    sink = np.asarray([cases[int(index)].sink_amplitude for index in selected])
    minus_values = np.column_stack([x_minus, y, voltage, branch, state, sink])
    plus_values = np.column_stack([x_plus, y, voltage, branch, state, sink])
    return (
        torch.as_tensor(minus_values, dtype=dtype).requires_grad_(True),
        torch.as_tensor(plus_values, dtype=dtype).requires_grad_(True),
    )


def _port_and_ledger_losses(
    model: GeoStateMCPINN,
    result: GeoStateReferenceResult,
    rng: np.random.Generator,
    count: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    dtype = next(model.parameters()).dtype
    y = np.linspace(0.0, 1.0, count, dtype=np.float32)
    left = _case_inputs(
        result.case,
        np.zeros(count),
        y,
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(True)
    right = _case_inputs(
        result.case,
        np.ones(count),
        y,
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(True)
    left_fields = model.field_outputs(left)
    right_fields = model.field_outputs(right)
    current_left = torch.mean(left_fields["Jx_A_m"]) * model.width_m
    current_right = torch.mean(right_fields["Jx_A_m"]) * model.width_m
    target = torch.as_tensor(
        abs(float(result.metrics["source_current_A"])), dtype=dtype
    )
    current_scale = model.scales.sheet_current_A_m * model.width_m
    port_loss = 0.5 * (
        ((current_left - target) / current_scale).square()
        + ((current_right - target) / current_scale).square()
    )

    interior = _case_inputs(
        result.case,
        rng.random(count),
        rng.random(count),
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(True)
    interior_fields = model.field_outputs(interior)
    gradients = model._physical_gradients(interior_fields, interior)
    sigma = model.conductivity(interior_fields["T_K"], interior[:, 4:5])
    joule = model.thickness_m * sigma * (
        gradients["dphi_dx"].square() + gradients["dphi_dy"].square()
    )
    sink = model.sink_conductance(interior) * (
        interior_fields["T_K"] - model.ambient_temperature_K
    )
    area = model.length_m * model.width_m
    field_power = torch.mean(joule) * area
    sink_power = torch.mean(sink) * area
    port_power = result.case.device_voltage_V * current_left
    power_scale = model.scales.power_W
    ledger_loss = 0.5 * (
        ((port_power - field_power) / power_scale).square()
        + ((field_power - sink_power) / power_scale).square()
    )
    return port_loss.reshape(()), ledger_loss.reshape(())


def train_model(
    model_name: str,
    context: GeoStateReferenceContext,
    config: Mapping[str, Any],
    train_results: Sequence[GeoStateReferenceResult],
    *,
    adam_steps: int | None = None,
    joule_schedule: Sequence[float] | None = None,
    phase_width_schedule: Sequence[float] | None = None,
) -> tuple[TrainingOutcome, dict[str, list[int]]]:
    model = build_model(model_name, context, config)
    dtype_name = str(config["pinn"]["dtype"])
    model = model.to(dtype=torch.float64 if dtype_name == "float64" else torch.float32)
    anchor_inputs, anchor_targets, anchor_indices = build_anchor_tensors(
        train_results, model, config
    )
    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(config["pinn"]["learning_rate"])
    )
    fixed_weights = config["pinn"]["fixed_loss_weights"]
    requested_steps = int(adam_steps or config["pinn"]["adam_steps"])
    rng = np.random.default_rng(int(config["pinn"]["seed"]))
    cases = [result.case for result in train_results]
    history: list[dict[str, float | int | str | bool]] = []
    started = perf_counter()
    finite = True
    completed = 0
    for step in range(requested_steps):
        if perf_counter() - started > float(
            config["pinn"]["maximum_wall_time_s_per_model"]
        ):
            finite = False
            break
        optimizer.zero_grad(set_to_none=True)
        if phase_width_schedule:
            model.set_phase_width_multiplier(
                float(phase_width_schedule[min(step, len(phase_width_schedule) - 1)])
            )
        anchor_leaf = anchor_inputs.detach().clone().requires_grad_(model_name == "B1")
        anchor = model.anchor_loss(anchor_leaf, anchor_targets)
        constitutive = torch.zeros((), dtype=anchor.dtype)
        conservation = torch.zeros((), dtype=anchor.dtype)
        interface = torch.zeros((), dtype=anchor.dtype)
        port = torch.zeros((), dtype=anchor.dtype)
        ledger = torch.zeros((), dtype=anchor.dtype)
        if model_name != "B0":
            collocation = _sample_case_inputs(
                rng,
                cases,
                int(config["pinn"]["collocation_points_per_step"]),
                model,
            )
            joule_feedback = (
                float(joule_schedule[min(step, len(joule_schedule) - 1)])
                if joule_schedule
                else 1.0
            )
            residuals = model.residual_groups(
                collocation, joule_feedback=joule_feedback
            )
            conservation = 0.5 * (
                torch.mean(residuals["current_conservation"].square())
                + torch.mean(residuals["energy_conservation"].square())
            )
            constitutive_terms = [
                value
                for name, value in residuals.items()
                if "constitutive" in name
            ]
            if constitutive_terms:
                constitutive = torch.stack(
                    [torch.mean(value.square()) for value in constitutive_terms]
                ).mean()
            minus, plus = _interface_pairs(
                rng,
                cases,
                int(config["pinn"]["interface_points_per_step"]),
                model,
            )
            interface, _ = model.interface_loss(minus, plus)
            port_result = train_results[step % len(train_results)]
            port, ledger = _port_and_ledger_losses(
                model,
                port_result,
                rng,
                int(config["pinn"]["port_points_per_step"]),
            )
        total = (
            float(fixed_weights["anchor"]) * anchor
            + float(fixed_weights["constitutive"]) * constitutive
            + float(fixed_weights["conservation"]) * conservation
            + float(fixed_weights["interface"]) * interface
            + float(fixed_weights["port"]) * port
            + float(fixed_weights["ledger"]) * ledger
        )
        if not torch.isfinite(total):
            finite = False
            break
        total.backward()
        gradients_finite = all(
            parameter.grad is None or torch.isfinite(parameter.grad).all()
            for parameter in model.parameters()
        )
        if not gradients_finite:
            finite = False
            break
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=100.0)
        optimizer.step()
        completed = step + 1
        stride = int(config["pinn"]["history_stride"])
        if step % stride == 0 or step + 1 == requested_steps:
            history.append(
                {
                    "model": model_name,
                    "step": step + 1,
                    "anchor_loss": float(anchor.detach()),
                    "constitutive_loss": float(constitutive.detach()),
                    "conservation_loss": float(conservation.detach()),
                    "interface_loss": float(interface.detach()),
                    "port_loss": float(port.detach()),
                    "ledger_loss": float(ledger.detach()),
                    "total_loss": float(total.detach()),
                    "finite": True,
                }
            )
    wall = perf_counter() - started
    model.set_phase_width_multiplier(1.0)
    return (
        TrainingOutcome(
            model_name=model_name,
            model=model,
            history=history,
            finite=finite,
            completed_steps=completed,
            wall_time_s=float(wall),
            parameter_count=model.parameter_count(),
        ),
        anchor_indices,
    )


def predict_case(
    model: GeoStateMCPINN, result: GeoStateReferenceResult
) -> dict[str, np.ndarray]:
    grid = result.grid
    xx, yy = np.meshgrid(
        grid.x_centers_m / grid.x_edges_m[-1],
        grid.y_centers_m / grid.y_edges_m[-1],
    )
    dtype = next(model.parameters()).dtype
    inputs = _case_inputs(
        result.case,
        xx.reshape(-1),
        yy.reshape(-1),
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(model.model_kind == "B1")
    outputs = model.field_outputs(inputs)
    return {
        name: values.detach().cpu().numpy().reshape(grid.shape)
        for name, values in outputs.items()
    }


def _relative_l2(candidate: np.ndarray, reference: np.ndarray) -> float:
    return float(
        np.linalg.norm((candidate - reference).reshape(-1))
        / max(np.linalg.norm(reference.reshape(-1)), 1.0e-12)
    )


def evaluate_case(
    model: GeoStateMCPINN,
    result: GeoStateReferenceResult,
    config: Mapping[str, Any],
) -> tuple[dict[str, float | bool | str], dict[str, np.ndarray]]:
    prediction = predict_case(model, result)
    ambient = model.ambient_temperature_K
    temperature_error = _relative_l2(
        prediction["T_K"] - ambient,
        np.asarray(result.fields["temperature_K"]) - ambient,
    )
    potential_error = _relative_l2(
        prediction["phi_V"], np.asarray(result.fields["potential_V"])
    )
    dtype = next(model.parameters()).dtype
    port_count = 96
    y = np.linspace(0.0, 1.0, port_count)
    left = _case_inputs(
        result.case,
        np.zeros(port_count),
        y,
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(model.model_kind == "B1")
    right = _case_inputs(
        result.case,
        np.ones(port_count),
        y,
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(model.model_kind == "B1")
    left_fields = model.field_outputs(left)
    right_fields = model.field_outputs(right)
    current_left = float(torch.mean(left_fields["Jx_A_m"]).detach()) * model.width_m
    current_right = float(torch.mean(right_fields["Jx_A_m"]).detach()) * model.width_m
    target_current = abs(float(result.metrics["source_current_A"]))
    terminal_error = abs(0.5 * (current_left + current_right) - target_current) / max(
        target_current, 1.0e-30
    )

    grid = result.grid
    xx, yy = np.meshgrid(
        grid.x_centers_m / grid.x_edges_m[-1],
        grid.y_centers_m / grid.y_edges_m[-1],
    )
    interior = _case_inputs(
        result.case,
        xx.reshape(-1),
        yy.reshape(-1),
        model.scales.voltage_V,
        dtype=dtype,
    ).requires_grad_(True)
    fields = model.field_outputs(interior)
    gradients = model._physical_gradients(fields, interior)
    sigma = model.conductivity(fields["T_K"], interior[:, 4:5])
    joule = model.thickness_m * sigma * (
        gradients["dphi_dx"].square() + gradients["dphi_dy"].square()
    )
    sink = model.sink_conductance(interior) * (
        fields["T_K"] - model.ambient_temperature_K
    )
    area = model.length_m * model.width_m
    field_power = float(torch.mean(joule).detach()) * area
    sink_power = float(torch.mean(sink).detach()) * area
    port_power = result.case.device_voltage_V * current_left
    port_field_error = abs(port_power - field_power) / max(
        abs(port_power), abs(field_power), 1.0e-30
    )
    field_sink_error = abs(field_power - sink_power) / max(
        abs(field_power), abs(sink_power), 1.0e-30
    )
    ledger_error = max(port_field_error, field_sink_error)

    interface_count = 96
    rng = np.random.default_rng(20260809)
    minus, plus = _interface_pairs(
        rng, [result.case], interface_count, model
    )
    minus_fields = model.field_outputs(minus)
    plus_fields = model.field_outputs(plus)
    j_difference = torch.sqrt(
        torch.mean((minus_fields["Jx_A_m"] - plus_fields["Jx_A_m"]) ** 2)
    )
    j_scale = torch.sqrt(
        0.5
        * torch.mean(
            minus_fields["Jx_A_m"].square() + plus_fields["Jx_A_m"].square()
        )
    )
    q_difference = torch.sqrt(
        torch.mean((minus_fields["qx_W_m"] - plus_fields["qx_W_m"]) ** 2)
    )
    q_scale = torch.sqrt(
        0.5
        * torch.mean(minus_fields["qx_W_m"].square() + plus_fields["qx_W_m"].square())
    )
    interface_mismatch = max(
        float(
            (
                j_difference
                / torch.clamp(
                    j_scale, min=1.0e-3 * model.scales.sheet_current_A_m
                )
            ).detach()
        ),
        float(
            (
                q_difference
                / torch.clamp(
                    q_scale, min=1.0e-3 * model.scales.sheet_heat_flux_W_m
                )
            ).detach()
        ),
    )
    finite = bool(
        all(np.isfinite(value).all() for value in prediction.values())
        and np.isfinite(
            [
                temperature_error,
                potential_error,
                terminal_error,
                ledger_error,
                interface_mismatch,
            ]
        ).all()
    )
    gates = config["engineering_screen"]
    passes = bool(
        finite
        and temperature_error <= float(gates["temperature_field_relative_l2_max"])
        and potential_error <= float(gates["potential_field_relative_l2_max"])
        and terminal_error <= float(gates["terminal_current_relative_error_max"])
        and ledger_error <= float(gates["energy_ledger_relative_error_max"])
        and interface_mismatch <= float(gates["interface_flux_mismatch_max"])
    )
    metrics: dict[str, float | bool | str] = {
        "model": model.model_kind,
        "case_id": result.case.case_id,
        "temperature_relative_l2": temperature_error,
        "potential_relative_l2": potential_error,
        "field_score": 0.5 * (temperature_error + potential_error),
        "terminal_current_error": terminal_error,
        "predicted_terminal_current_A": 0.5 * (current_left + current_right),
        "target_terminal_current_A": target_current,
        "port_field_error": port_field_error,
        "field_sink_error": field_sink_error,
        "energy_ledger_error": ledger_error,
        "interface_flux_mismatch": interface_mismatch,
        "finite": finite,
        "engineering_gate_pass": passes,
    }
    return metrics, prediction


def aggregate_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | int | bool]:
    numeric = (
        "temperature_relative_l2",
        "potential_relative_l2",
        "field_score",
        "terminal_current_error",
        "energy_ledger_error",
        "interface_flux_mismatch",
    )
    aggregate: dict[str, float | int | bool] = {
        f"mean_{name}": float(np.mean([float(row[name]) for row in rows]))
        for name in numeric
    }
    aggregate.update(
        {
            f"max_{name}": float(np.max([float(row[name]) for row in rows]))
            for name in numeric
        }
    )
    aggregate["passing_complete_cases"] = int(
        sum(bool(row["engineering_gate_pass"]) for row in rows)
    )
    aggregate["all_finite"] = bool(all(bool(row["finite"]) for row in rows))
    return aggregate
