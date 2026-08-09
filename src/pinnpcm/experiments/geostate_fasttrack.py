"""Fast-track quasi-static 2.5D reference models for GeoState-MC-PINN.

The implementation is a thin, versioned adapter around the existing Qiu
geometry, conservative sheet-current topology, and areal thermal operators.
It adds only the M0/M1/M2 closures authorized by the fast-track contract.  The
conductive state is prescribed case metadata; it is not inferred from fields
or represented as a measured phase fraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml
from scipy import sparse
from scipy.sparse.linalg import splu

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid, build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    S2ThermalFields,
    build_s2_thermal_fields,
)
from pinnpcm.physics.vo2_constitutive import vo2_sigma
from pinnpcm.solvers.geophase_2p5d_fvm import (
    SheetElectricalTopology,
    build_sheet_electrical_topology,
    factor_sheet_electrical,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    assemble_sheet_thermal_matrix,
)


EVIDENCE_TYPE = "literature-guided synthetic numerical digital-twin evidence"


@dataclass(frozen=True)
class GeoStateCase:
    case_id: str
    branch_label: str
    branch_value: float
    device_voltage_V: float
    state_coordinate: float
    thermal_condition: str
    sink_amplitude: float
    contact_override: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class GeoStateReferenceContext:
    fast_config: dict[str, Any]
    parent_config: dict[str, Any]
    grid: GeoPhaseGrid
    thermal_fields: S2ThermalFields
    electrical_topology: SheetElectricalTopology
    device_thermal_matrix: sparse.csr_matrix

    @property
    def ambient_temperature_K(self) -> float:
        return float(self.thermal_fields.ambient_temperature_K)

    @property
    def length_m(self) -> float:
        return float(self.grid.x_edges_m[-1] - self.grid.x_edges_m[0])

    @property
    def width_m(self) -> float:
        return float(self.grid.y_edges_m[-1] - self.grid.y_edges_m[0])


@dataclass(frozen=True)
class GeoStateReferenceResult:
    model_form: str
    case: GeoStateCase
    grid: GeoPhaseGrid
    fields: Mapping[str, np.ndarray]
    metrics: Mapping[str, float | int | bool | str]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected a mapping in {path}")
    return payload


def build_reference_context(
    fast_config: dict[str, Any],
    repository_root: Path,
    *,
    refinement: int = 1,
) -> GeoStateReferenceContext:
    parent_path = repository_root / fast_config["parent_physics"]["config"]
    parent = load_yaml(parent_path)
    base = fast_config["reference_solver"]["grid"]
    grid = build_geophase_grid(
        parent,
        nx_override=int(base["nx"]) * int(refinement),
        ny_override=int(base["ny"]) * int(refinement),
    )
    thermal = build_s2_thermal_fields(grid, parent)
    return GeoStateReferenceContext(
        fast_config=fast_config,
        parent_config=parent,
        grid=grid,
        thermal_fields=thermal,
        electrical_topology=build_sheet_electrical_topology(grid),
        device_thermal_matrix=assemble_sheet_thermal_matrix(
            grid, thermal.sheet_thermal_conductance_W_K
        ),
    )


def material_parameters(config: Mapping[str, Any]) -> dict[str, Any]:
    source = config["physical_model"]["material"]
    return {
        "T_c": float(source["T_ref_K"]),
        "transition_width": float(source["transition_width_K"]),
        "transition_width_min": float(source["transition_width_min_K"]),
        "T_ref": float(source["T_ref_K"]),
        "c_v_ref": float(source["c_v"]),
        "sigma_ins0": float(source["sigma_ins0_S_m"]),
        "sigma_met0": float(source["sigma_met0_S_m"]),
        "E_ins_eV": float(source["E_ins_eV"]),
        "beta_c": float(source["beta_c"]),
        "metal_temp_coeff": float(source["metal_temp_coeff_per_K"]),
        "mixing_mode": str(source["mixing_mode"]),
        "smooth_power": float(source["smooth_power"]),
    }


def conductivity_numpy(
    temperature_K: np.ndarray,
    state_coordinate: float,
    config: Mapping[str, Any],
) -> np.ndarray:
    temperature = np.asarray(temperature_K, dtype=float)
    like = torch.as_tensor(temperature, dtype=torch.float64)
    state = torch.full_like(like, float(state_coordinate))
    defect = torch.full_like(like, float(config["physical_model"]["material"]["c_v"]))
    with torch.no_grad():
        sigma = vo2_sigma(like, defect, m=state, params=material_parameters(config))
    return sigma.detach().cpu().numpy().astype(float, copy=False)


def _contact_values(
    config: Mapping[str, Any], model_form: str, case: GeoStateCase
) -> tuple[dict[str, float], dict[str, float]]:
    form = config["physical_model"]["model_forms"][model_form]
    electrical = {
        key: float(value)
        for key, value in form["electrical_contact_resistance_ohm"].items()
    }
    thermal = {
        key: float(value)
        for key, value in form["thermal_contact_resistance_m2K_W"].items()
    }
    if model_form != "M0" and case.contact_override:
        if "electrical_contact_resistance_ohm" in case.contact_override:
            electrical.update(
                {
                    key: float(value)
                    for key, value in case.contact_override[
                        "electrical_contact_resistance_ohm"
                    ].items()
                }
            )
        if "thermal_contact_resistance_m2K_W" in case.contact_override:
            thermal.update(
                {
                    key: float(value)
                    for key, value in case.contact_override[
                        "thermal_contact_resistance_m2K_W"
                    ].items()
                }
            )
    return electrical, thermal


def localized_sink_mask(context: GeoStateReferenceContext) -> np.ndarray:
    rectangle = context.fast_config["physical_model"]["localized_sink"][
        "rectangle_m"
    ]
    x, y = np.meshgrid(context.grid.x_centers_m, context.grid.y_centers_m)
    return (
        (x >= float(rectangle["x"][0]))
        & (x <= float(rectangle["x"][1]))
        & (y >= float(rectangle["y"][0]))
        & (y <= float(rectangle["y"][1]))
    )


def _solve_electrical_robin(
    context: GeoStateReferenceContext,
    conductivity_S_m: np.ndarray,
    voltage_V: float,
    contact_resistance_ohm: Mapping[str, float],
) -> dict[str, Any]:
    grid = context.grid
    factor = factor_sheet_electrical(
        grid, conductivity_S_m, topology=context.electrical_topology
    )
    source_base = np.asarray(factor.source_face_conductance_S, dtype=float)
    ground_base = np.asarray(factor.ground_face_conductance_S, dtype=float)
    source_face_R = float(contact_resistance_ohm["left"]) * grid.ny
    ground_face_R = float(contact_resistance_ohm["right"]) * grid.ny
    source_g = 1.0 / (1.0 / source_base + source_face_R)
    ground_g = 1.0 / (1.0 / ground_base + ground_face_R)

    matrix = factor.conductivity_matrix_csr.copy().tolil()
    for row, delta in zip(
        factor.topology.source_nodes, source_g - source_base, strict=True
    ):
        matrix[int(row), int(row)] += float(delta)
    for row, delta in zip(
        factor.topology.ground_nodes, ground_g - ground_base, strict=True
    ):
        matrix[int(row), int(row)] += float(delta)
    matrix = matrix.tocsr()
    rhs = np.zeros(grid.nx * grid.ny, dtype=float)
    rhs[factor.topology.source_nodes] = source_g * float(voltage_V)
    values = np.asarray(splu(matrix.tocsc()).solve(rhs), dtype=float)
    phi = values.reshape(grid.shape)

    source_face_current = source_g * (float(voltage_V) - phi[:, 0])
    ground_face_current = ground_g * (0.0 - phi[:, -1])
    source_current = float(np.sum(source_face_current))
    ground_current = float(np.sum(ground_face_current))

    cell_joule = np.zeros(grid.shape, dtype=float)
    x_power = factor.x_face_conductance_S * (phi[:, :-1] - phi[:, 1:]) ** 2
    y_power = factor.y_face_conductance_S * (phi[:-1, :] - phi[1:, :]) ** 2
    cell_joule[:, :-1] += 0.5 * x_power
    cell_joule[:, 1:] += 0.5 * x_power
    cell_joule[:-1, :] += 0.5 * y_power
    cell_joule[1:, :] += 0.5 * y_power
    cell_joule[:, 0] += source_g * (float(voltage_V) - phi[:, 0]) ** 2
    cell_joule[:, -1] += ground_g * phi[:, -1] ** 2

    terminal_power = float(voltage_V) * source_current
    field_joule = float(np.sum(cell_joule))
    current_scale = max(abs(source_current) + abs(ground_current), 1.0e-30)
    power_scale = max(abs(terminal_power), abs(field_joule), 1.0e-30)
    residual = np.asarray(matrix @ values - rhs, dtype=float)
    residual_scale = max(current_scale / residual.size, 1.0e-30)
    return {
        "potential_V": phi,
        "cell_joule_power_W": cell_joule,
        "source_current_A": source_current,
        "ground_current_A": ground_current,
        "terminal_power_W": terminal_power,
        "field_joule_power_W": field_joule,
        "current_imbalance": abs(source_current + ground_current) / current_scale,
        "terminal_field_error": abs(terminal_power - field_joule) / power_scale,
        "scaled_electrical_residual": float(np.max(np.abs(residual)) / residual_scale),
        "source_face_current_A": source_face_current,
        "ground_face_current_A": ground_face_current,
    }


def solve_constant_property_electrical(
    context: GeoStateReferenceContext,
    conductivity_S_m: float,
    voltage_V: float,
) -> dict[str, Any]:
    field = np.full(context.grid.shape, float(conductivity_S_m), dtype=float)
    return _solve_electrical_robin(
        context, field, voltage_V, {"left": 0.0, "right": 0.0}
    )


def _thermal_closure(
    context: GeoStateReferenceContext,
    model_form: str,
    case: GeoStateCase,
    thermal_contact_resistance_m2K_W: Mapping[str, float],
) -> dict[str, Any]:
    grid = context.grid
    area = grid.cell_area_m2
    g0 = float(context.thermal_fields.vertical_conductance_W_m2K)
    patch = localized_sink_mask(context).astype(float)
    local_g = g0 * (1.0 + float(case.sink_amplitude) * patch)
    if model_form in {"M1", "M2"}:
        resistance = np.zeros(grid.shape, dtype=float)
        resistance[grid.left_contact_mask] = float(
            thermal_contact_resistance_m2K_W["left"]
        )
        resistance[grid.right_contact_mask] = float(
            thermal_contact_resistance_m2K_W["right"]
        )
        local_g = 1.0 / (1.0 / local_g + resistance)

    if model_form != "M2":
        matrix = context.device_thermal_matrix + sparse.diags(
            (local_g * area).reshape(-1), format="csr"
        )
        return {
            "solver": splu(matrix.tocsc()),
            "local_g_W_m2K": local_g,
            "device_substrate_g_W_m2K": None,
            "substrate_ambient_g_W_m2K": None,
            "substrate_matrix": None,
        }

    form = context.fast_config["physical_model"]["model_forms"]["M2"]
    g_ds = float(form["device_substrate_conductance_multiplier"]) * g0
    g_ds_field = np.full(grid.shape, g_ds, dtype=float)
    resistance = np.zeros(grid.shape, dtype=float)
    resistance[grid.left_contact_mask] = float(
        thermal_contact_resistance_m2K_W["left"]
    )
    resistance[grid.right_contact_mask] = float(
        thermal_contact_resistance_m2K_W["right"]
    )
    g_ds_field = 1.0 / (1.0 / g_ds_field + resistance)
    g_sa = (
        float(form["substrate_ambient_conductance_multiplier"])
        * g0
        * (1.0 + float(case.sink_amplitude) * patch)
    )
    substrate_sheet = (
        float(form["substrate_thermal_conductivity_W_mK"])
        * float(form["substrate_effective_depth_m"])
        * float(form["lateral_spreading_scale"])
    )
    substrate_lateral = assemble_sheet_thermal_matrix(grid, substrate_sheet)
    gds_cell = (g_ds_field * area).reshape(-1)
    gsa_cell = (g_sa * area).reshape(-1)
    device = context.device_thermal_matrix + sparse.diags(gds_cell, format="csr")
    substrate = substrate_lateral + sparse.diags(
        gds_cell + gsa_cell, format="csr"
    )
    coupling = sparse.diags(-gds_cell, format="csr")
    block = sparse.bmat([[device, coupling], [coupling, substrate]], format="csc")
    return {
        "solver": splu(block),
        "local_g_W_m2K": None,
        "device_substrate_g_W_m2K": g_ds_field,
        "substrate_ambient_g_W_m2K": g_sa,
        "substrate_matrix": substrate_lateral,
    }


def _thermal_target(
    context: GeoStateReferenceContext,
    model_form: str,
    closure: Mapping[str, Any],
    joule_W: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    grid = context.grid
    ambient = context.ambient_temperature_K
    if model_form != "M2":
        local_g = np.asarray(closure["local_g_W_m2K"], dtype=float)
        rhs = joule_W.reshape(-1) + local_g.reshape(-1) * grid.cell_area_m2 * ambient
        return np.asarray(closure["solver"].solve(rhs), dtype=float).reshape(grid.shape), None

    gsa = np.asarray(closure["substrate_ambient_g_W_m2K"], dtype=float)
    count = grid.nx * grid.ny
    rhs = np.concatenate(
        [joule_W.reshape(-1), gsa.reshape(-1) * grid.cell_area_m2 * ambient]
    )
    values = np.asarray(closure["solver"].solve(rhs), dtype=float)
    return values[:count].reshape(grid.shape), values[count:].reshape(grid.shape)


def _thermal_residual_and_sink(
    context: GeoStateReferenceContext,
    model_form: str,
    closure: Mapping[str, Any],
    temperature_K: np.ndarray,
    substrate_temperature_K: np.ndarray | None,
    joule_W: np.ndarray,
) -> tuple[np.ndarray, float, np.ndarray]:
    grid = context.grid
    ambient = context.ambient_temperature_K
    lateral = np.asarray(
        context.device_thermal_matrix
        @ (temperature_K - ambient).reshape(-1),
        dtype=float,
    ).reshape(grid.shape)
    if model_form != "M2":
        g = np.asarray(closure["local_g_W_m2K"], dtype=float)
        sink_cell = g * grid.cell_area_m2 * (temperature_K - ambient)
        return lateral + sink_cell - joule_W, float(np.sum(sink_cell)), sink_cell

    if substrate_temperature_K is None:
        raise ValueError("M2 requires a substrate temperature field")
    gds = np.asarray(closure["device_substrate_g_W_m2K"], dtype=float)
    gsa = np.asarray(closure["substrate_ambient_g_W_m2K"], dtype=float)
    device_to_substrate = gds * grid.cell_area_m2 * (
        temperature_K - substrate_temperature_K
    )
    ambient_sink = gsa * grid.cell_area_m2 * (substrate_temperature_K - ambient)
    substrate_lateral = np.asarray(
        closure["substrate_matrix"]
        @ (substrate_temperature_K - ambient).reshape(-1),
        dtype=float,
    ).reshape(grid.shape)
    substrate_residual = substrate_lateral - device_to_substrate + ambient_sink
    residual = lateral + device_to_substrate - joule_W
    return (
        np.concatenate([residual.reshape(-1), substrate_residual.reshape(-1)]),
        float(np.sum(ambient_sink)),
        ambient_sink,
    )


def _cell_vector_fields(
    context: GeoStateReferenceContext,
    potential_V: np.ndarray,
    temperature_K: np.ndarray,
    conductivity_S_m: np.ndarray,
) -> dict[str, np.ndarray]:
    grid = context.grid
    dphi_dy, dphi_dx = np.gradient(
        potential_V, grid.dy_m, grid.dx_m, edge_order=2
    )
    dT_dy, dT_dx = np.gradient(
        temperature_K, grid.dy_m, grid.dx_m, edge_order=2
    )
    Jx = -grid.thickness_m * conductivity_S_m * dphi_dx
    Jy = -grid.thickness_m * conductivity_S_m * dphi_dy
    k_sheet = context.thermal_fields.sheet_thermal_conductance_W_K
    qx = -k_sheet * dT_dx
    qy = -k_sheet * dT_dy
    return {
        "Jx_A_m": Jx,
        "Jy_A_m": Jy,
        "J_magnitude_A_m": np.hypot(Jx, Jy),
        "qx_W_m": qx,
        "qy_W_m": qy,
        "q_magnitude_W_m": np.hypot(qx, qy),
    }


def solve_reference_case(
    context: GeoStateReferenceContext,
    model_form: str,
    case: GeoStateCase,
) -> GeoStateReferenceResult:
    if model_form not in {"M0", "M1", "M2"}:
        raise ValueError(f"unknown model form {model_form}")
    if not 0.0 <= case.state_coordinate <= 1.0:
        raise ValueError("state coordinate must lie in [0, 1]")
    config = context.fast_config
    solver_config = config["reference_solver"]["fixed_point"]
    electrical_contact, thermal_contact = _contact_values(config, model_form, case)
    thermal_closure = _thermal_closure(
        context, model_form, case, thermal_contact
    )
    grid = context.grid
    ambient = context.ambient_temperature_K
    temperature_scale = float(solver_config["temperature_scale_K"])
    sigma0 = conductivity_numpy(
        np.full(grid.shape, ambient), case.state_coordinate, config
    )
    uniform_rise = (
        grid.thickness_m
        * float(np.mean(sigma0))
        * (float(case.device_voltage_V) / context.length_m) ** 2
        / float(context.thermal_fields.vertical_conductance_W_m2K)
    )
    initial_rise = min(max(uniform_rise, 0.0), 0.75 * temperature_scale)
    temperature = np.full(grid.shape, ambient + initial_rise, dtype=float)
    substrate_temperature = (
        np.full(grid.shape, ambient + 0.5 * initial_rise, dtype=float)
        if model_form == "M2"
        else None
    )
    relaxation = float(solver_config["relaxation"])
    residual_gate = float(solver_config["scaled_residual_max"])
    update_gate = float(solver_config["scaled_update_max"])
    maximum_iterations = int(solver_config["maximum_iterations"])
    # The initial iterate has no preceding accepted update.  Treat its update
    # norm as zero so an exact analytic limit (notably V=0) can certify without
    # taking a roundoff-producing linear solve.
    scaled_update = 0.0
    converged = False

    for iteration in range(maximum_iterations + 1):
        sigma = conductivity_numpy(temperature, case.state_coordinate, config)
        electrical = _solve_electrical_robin(
            context, sigma, case.device_voltage_V, electrical_contact
        )
        residual, _, _ = _thermal_residual_and_sink(
            context,
            model_form,
            thermal_closure,
            temperature,
            substrate_temperature,
            electrical["cell_joule_power_W"],
        )
        cell_scale = max(
            abs(float(electrical["field_joule_power_W"])) / grid.nx / grid.ny,
            1.0e-15,
        )
        scaled_thermal = float(np.max(np.abs(residual)) / cell_scale)
        scaled_residual = max(
            scaled_thermal, float(electrical["scaled_electrical_residual"])
        )
        if scaled_residual <= residual_gate and scaled_update <= update_gate:
            converged = True
            break
        if iteration == maximum_iterations:
            break
        target_temperature, target_substrate = _thermal_target(
            context,
            model_form,
            thermal_closure,
            electrical["cell_joule_power_W"],
        )
        device_delta = target_temperature - temperature
        scaled_update = float(np.max(np.abs(device_delta)) / temperature_scale)
        temperature = temperature + relaxation * device_delta
        if model_form == "M2":
            if target_substrate is None or substrate_temperature is None:
                raise RuntimeError("M2 target lost its substrate field")
            substrate_delta = target_substrate - substrate_temperature
            scaled_update = max(
                scaled_update,
                float(np.max(np.abs(substrate_delta)) / temperature_scale),
            )
            substrate_temperature = substrate_temperature + relaxation * substrate_delta

    sigma = conductivity_numpy(temperature, case.state_coordinate, config)
    electrical = _solve_electrical_robin(
        context, sigma, case.device_voltage_V, electrical_contact
    )
    residual, sink_power, sink_cell = _thermal_residual_and_sink(
        context,
        model_form,
        thermal_closure,
        temperature,
        substrate_temperature,
        electrical["cell_joule_power_W"],
    )
    cell_scale = max(
        abs(float(electrical["field_joule_power_W"])) / grid.nx / grid.ny,
        1.0e-15,
    )
    scaled_thermal = float(np.max(np.abs(residual)) / cell_scale)
    scaled_residual = max(
        scaled_thermal, float(electrical["scaled_electrical_residual"])
    )
    joule_power = float(electrical["field_joule_power_W"])
    ledger_error = abs(joule_power - sink_power) / max(
        abs(joule_power), abs(sink_power), 1.0e-30
    )
    vectors = _cell_vector_fields(
        context, electrical["potential_V"], temperature, sigma
    )
    temperature_rise = temperature - ambient
    transverse = temperature_rise - np.mean(temperature_rise, axis=0, keepdims=True)
    chi_2d = float(
        np.linalg.norm(transverse.reshape(-1))
        / max(np.linalg.norm(temperature_rise.reshape(-1)), 1.0e-30)
    )
    hotspot_flat = int(np.argmax(temperature))
    hotspot_y_index, hotspot_x_index = np.unravel_index(hotspot_flat, grid.shape)
    hotspot_x = float(grid.x_centers_m[hotspot_x_index])
    hotspot_y = float(grid.y_centers_m[hotspot_y_index])
    hotspot_shift = abs(hotspot_y / context.width_m - 0.5)
    finite = bool(
        np.isfinite(temperature).all()
        and np.isfinite(electrical["potential_V"]).all()
        and all(np.isfinite(value).all() for value in vectors.values())
    )
    metrics: dict[str, float | int | bool | str] = {
        "evidence_type": EVIDENCE_TYPE,
        "iterations": int(iteration),
        "converged": bool(converged),
        "finite": finite,
        "scaled_nonlinear_residual": float(scaled_residual),
        "scaled_thermal_residual": scaled_thermal,
        "scaled_electrical_residual": float(
            electrical["scaled_electrical_residual"]
        ),
        "terminal_current_imbalance": float(electrical["current_imbalance"]),
        "terminal_field_joule_error": float(electrical["terminal_field_error"]),
        "joule_sink_ledger_error": float(ledger_error),
        "source_current_A": float(electrical["source_current_A"]),
        "ground_current_A": float(electrical["ground_current_A"]),
        "terminal_power_W": float(electrical["terminal_power_W"]),
        "field_joule_power_W": joule_power,
        "sink_power_W": float(sink_power),
        "Tmax_K": float(np.max(temperature)),
        "Tmean_K": float(np.mean(temperature)),
        "hotspot_x_m": hotspot_x,
        "hotspot_y_m": hotspot_y,
        "hotspot_lateral_shift_width_fraction": float(hotspot_shift),
        "chi_2d": chi_2d,
    }
    fields: dict[str, np.ndarray] = {
        "x_m": np.asarray(grid.x_centers_m),
        "y_m": np.asarray(grid.y_centers_m),
        "potential_V": np.asarray(electrical["potential_V"]),
        "temperature_K": temperature,
        "conductivity_S_m": sigma,
        "state_coordinate": np.full(grid.shape, case.state_coordinate),
        "branch_value": np.full(grid.shape, case.branch_value),
        "joule_heat_W_m2": np.asarray(electrical["cell_joule_power_W"])
        / grid.cell_area_m2,
        "sink_heat_W_m2": np.asarray(sink_cell) / grid.cell_area_m2,
        **vectors,
    }
    if substrate_temperature is not None:
        fields["substrate_temperature_K"] = substrate_temperature
    return GeoStateReferenceResult(
        model_form=model_form,
        case=case,
        grid=grid,
        fields=fields,
        metrics=metrics,
    )


def independent_ledger_reconstruction(
    result: GeoStateReferenceResult,
) -> dict[str, float]:
    metrics = result.metrics
    terminal = float(result.case.device_voltage_V) * float(metrics["source_current_A"])
    field = float(np.sum(result.fields["joule_heat_W_m2"]) * result.grid.cell_area_m2)
    sink = float(np.sum(result.fields["sink_heat_W_m2"]) * result.grid.cell_area_m2)
    return {
        "terminal_power_W": terminal,
        "field_joule_power_W": field,
        "sink_power_W": sink,
        "terminal_field_error": abs(terminal - field)
        / max(abs(terminal), abs(field), 1.0e-30),
        "field_sink_error": abs(field - sink)
        / max(abs(field), abs(sink), 1.0e-30),
    }


def model_form_case_from_config(
    config: Mapping[str, Any], case_id: str
) -> GeoStateCase:
    item = config["model_form_cases"][case_id]
    return GeoStateCase(
        case_id=case_id,
        branch_label=str(item["branch_label"]),
        branch_value=float(item["branch_value"]),
        device_voltage_V=float(item["device_voltage_V"]),
        state_coordinate=float(item["state_coordinate"]),
        thermal_condition=str(item["thermal_condition"]),
        sink_amplitude=float(item["sink_amplitude"]),
        contact_override=item.get("contact_override"),
    )


def pilot_cases_from_config(config: Mapping[str, Any]) -> list[GeoStateCase]:
    dataset = config["pilot_dataset"]
    cases: list[GeoStateCase] = []
    for branch_label, branch_value in dataset["branches"].items():
        short_branch = str(branch_label).replace("-conditioned", "")
        for level, voltage in dataset["voltage_levels_V"].items():
            state = dataset["state_coordinates"][branch_label][level]
            for thermal_condition, amplitude in dataset["thermal_conditions"].items():
                case_id = f"{short_branch}_{level}_{thermal_condition}"
                cases.append(
                    GeoStateCase(
                        case_id=case_id,
                        branch_label=str(branch_label),
                        branch_value=float(branch_value),
                        device_voltage_V=float(voltage),
                        state_coordinate=float(state),
                        thermal_condition=str(thermal_condition),
                        sink_amplitude=float(amplitude),
                    )
                )
    return cases


def reference_case_passes(
    result: GeoStateReferenceResult, config: Mapping[str, Any]
) -> bool:
    gates = config["reference_solver"]["sanity_gates"]
    metrics = result.metrics
    return bool(
        metrics["converged"]
        and metrics["finite"]
        and float(metrics["scaled_nonlinear_residual"])
        <= float(gates["scaled_nonlinear_residual_max"])
        and float(metrics["terminal_current_imbalance"])
        <= float(gates["terminal_current_imbalance_max"])
        and float(metrics["terminal_field_joule_error"])
        <= float(gates["terminal_field_joule_error_max"])
        and float(metrics["joule_sink_ledger_error"])
        <= float(gates["joule_sink_ledger_error_max"])
    )


def select_reference_model(
    results: Mapping[tuple[str, str], GeoStateReferenceResult],
    config: Mapping[str, Any],
) -> tuple[str | None, dict[str, dict[str, float | bool]]]:
    selection = config["reference_solver"]["model_selection"]
    chi_gate = float(config["reference_solver"]["sanity_gates"]["chi_2d_min"])
    richest = {case: results[("M2", case)] for case in ("C0", "C1")}
    audit: dict[str, dict[str, float | bool]] = {}
    for model in ("M0", "M1", "M2"):
        maximum_current = 0.0
        maximum_temperature = 0.0
        maximum_hotspot = 0.0
        ledgers_pass = True
        for case in ("C0", "C1"):
            candidate = results[(model, case)]
            target = richest[case]
            ledgers_pass = ledgers_pass and reference_case_passes(candidate, config)
            current_a = abs(float(candidate.metrics["source_current_A"]))
            current_b = abs(float(target.metrics["source_current_A"]))
            current_difference = abs(current_a - current_b) / max(
                0.5 * (current_a + current_b), 1.0e-30
            )
            temperature_difference = abs(
                float(candidate.metrics["Tmax_K"]) - float(target.metrics["Tmax_K"])
            )
            # A single-cell argmax is undefined for the uniform C0 limit.  A
            # hotspot coordinate votes only when either model has resolved 2D
            # contrast, and its distance is normalized by the specified width W.
            if (
                float(candidate.metrics["chi_2d"]) >= chi_gate
                or float(target.metrics["chi_2d"]) >= chi_gate
            ):
                dx = float(candidate.metrics["hotspot_x_m"]) - float(
                    target.metrics["hotspot_x_m"]
                )
                dy = float(candidate.metrics["hotspot_y_m"]) - float(
                    target.metrics["hotspot_y_m"]
                )
                width = float(
                    candidate.grid.y_edges_m[-1] - candidate.grid.y_edges_m[0]
                )
                hotspot_difference = float(np.hypot(dx, dy) / width)
            else:
                hotspot_difference = 0.0
            maximum_current = max(maximum_current, current_difference)
            maximum_temperature = max(maximum_temperature, temperature_difference)
            maximum_hotspot = max(maximum_hotspot, hotspot_difference)
        sufficient = bool(
            ledgers_pass
            and maximum_current
            <= float(selection["terminal_current_relative_difference_max"])
            and maximum_temperature
            <= float(selection["Tmax_absolute_difference_K_max"])
            and maximum_hotspot
            <= float(selection["hotspot_distance_width_fraction_max"])
        )
        audit[model] = {
            "ledger_gates_pass": bool(ledgers_pass),
            "max_current_relative_difference_vs_M2": maximum_current,
            "max_Tmax_difference_K_vs_M2": maximum_temperature,
            "max_hotspot_distance_width_fraction_vs_M2": maximum_hotspot,
            "sufficient": sufficient,
        }
        if sufficient:
            return model, audit
    return None, audit
