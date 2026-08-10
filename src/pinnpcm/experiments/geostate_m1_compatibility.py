"""Discrete teacher--objective compatibility for the frozen M1 data.

This module reconstructs conservative face quantities directly from the
stored potential, temperature, conductivity, and the production FVM topology.
The legacy cell-centred ``np.gradient`` J/q fields are deliberately ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from pinnpcm.experiments.geostate_fasttrack import GeoStateReferenceContext
from pinnpcm.solvers.geophase_2p5d_fvm import factor_sheet_electrical


@dataclass(frozen=True)
class M1TeacherCase:
    case_id: str
    branch_label: str
    branch_value: float
    device_voltage_V: float
    state_coordinate: float
    sink_amplitude: float
    potential_V: np.ndarray
    temperature_K: np.ndarray
    conductivity_S_m: np.ndarray
    stored_sink_heat_W_m2: np.ndarray
    source_path: Path


@dataclass(frozen=True)
class ConservativeTeacherFields:
    electrical_x_face_current_A: np.ndarray
    electrical_y_face_current_A: np.ndarray
    thermal_x_face_power_W: np.ndarray
    thermal_y_face_power_W: np.ndarray
    source_face_current_A: np.ndarray
    ground_face_current_A: np.ndarray
    internal_joule_cell_W: np.ndarray
    contact_joule_cell_W: np.ndarray
    vertical_sink_cell_W: np.ndarray
    normalized_current_residual: np.ndarray
    normalized_energy_residual: np.ndarray


def load_teacher_case(path: Path) -> M1TeacherCase:
    """Load only conserved-state teacher fields and immutable metadata."""

    with np.load(path, allow_pickle=False) as payload:
        required = {
            "potential_V",
            "temperature_K",
            "conductivity_S_m",
            "sink_heat_W_m2",
            "case_id",
            "model_form",
            "branch_label",
            "branch_value",
            "state_coordinate",
            "device_voltage_V",
            "sink_amplitude",
        }
        missing = required.difference(payload.files)
        if missing:
            raise ValueError(f"{path} is missing {sorted(missing)}")
        if str(payload["model_form"].item()) != "M1":
            raise ValueError(f"{path} is not an M1 teacher case")
        arrays = {
            name: np.asarray(payload[name], dtype=float).copy()
            for name in (
                "potential_V",
                "temperature_K",
                "conductivity_S_m",
                "sink_heat_W_m2",
            )
        }
        if not all(np.isfinite(value).all() for value in arrays.values()):
            raise ValueError(f"{path} contains nonfinite teacher fields")
        return M1TeacherCase(
            case_id=str(payload["case_id"].item()),
            branch_label=str(payload["branch_label"].item()),
            branch_value=float(payload["branch_value"].reshape(-1)[0]),
            device_voltage_V=float(payload["device_voltage_V"].item()),
            state_coordinate=float(payload["state_coordinate"].reshape(-1)[0]),
            sink_amplitude=float(payload["sink_amplitude"].item()),
            potential_V=arrays["potential_V"],
            temperature_K=arrays["temperature_K"],
            conductivity_S_m=arrays["conductivity_S_m"],
            stored_sink_heat_W_m2=arrays["sink_heat_W_m2"],
            source_path=path,
        )


def load_teacher_cases(root: Path) -> list[M1TeacherCase]:
    cases = [load_teacher_case(path) for path in sorted(root.glob("*.npz"))]
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("teacher case identifiers are not unique")
    return cases


def _harmonic(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return 2.0 * left * right / (left + right)


def _thermal_face_conductances(
    context: GeoStateReferenceContext,
) -> tuple[np.ndarray, np.ndarray]:
    grid = context.grid
    sheet = np.asarray(
        context.thermal_fields.sheet_thermal_conductance_W_K, dtype=float
    )
    gx = _harmonic(sheet[:, :-1], sheet[:, 1:]) * grid.dy_m / grid.dx_m
    gy = _harmonic(sheet[:-1, :], sheet[1:, :]) * grid.dx_m / grid.dy_m
    return gx, gy


def m1_vertical_conductance(
    context: GeoStateReferenceContext,
    case: M1TeacherCase,
    base_config: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Return exact M1 g_eff and its contact-resistance field."""

    grid = context.grid
    rectangle = base_config["physical_model"]["localized_sink"]["rectangle_m"]
    xx, yy = np.meshgrid(grid.x_centers_m, grid.y_centers_m)
    patch = (
        (xx >= float(rectangle["x"][0]))
        & (xx <= float(rectangle["x"][1]))
        & (yy >= float(rectangle["y"][0]))
        & (yy <= float(rectangle["y"][1]))
    )
    nominal = float(context.thermal_fields.vertical_conductance_W_m2K)
    local = nominal * (1.0 + float(case.sink_amplitude) * patch.astype(float))
    values = base_config["physical_model"]["model_forms"]["M1"]
    resistance = np.zeros(grid.shape, dtype=float)
    resistance[grid.left_contact_mask] = float(
        values["thermal_contact_resistance_m2K_W"]["left"]
    )
    resistance[grid.right_contact_mask] = float(
        values["thermal_contact_resistance_m2K_W"]["right"]
    )
    return 1.0 / (1.0 / local + resistance), resistance


def _interface_flux_mismatch(
    context: GeoStateReferenceContext,
    case: M1TeacherCase,
) -> float:
    """Evaluate two one-sided traces around both aligned coefficient jumps."""

    grid = context.grid
    phi = case.potential_V
    temperature = case.temperature_K
    sigma = case.conductivity_S_m
    sheet = np.asarray(context.thermal_fields.sheet_thermal_conductance_W_K)
    interface_faces = np.flatnonzero(
        np.any(grid.region_index[:, :-1] != grid.region_index[:, 1:], axis=0)
    )
    mismatches: list[float] = []
    for face in interface_faces:
        r_e_left = 0.5 * grid.dx_m / (
            sigma[:, face] * grid.thickness_m * grid.dy_m
        )
        r_e_right = 0.5 * grid.dx_m / (
            sigma[:, face + 1] * grid.thickness_m * grid.dy_m
        )
        current = (phi[:, face] - phi[:, face + 1]) / (r_e_left + r_e_right)
        phi_face = phi[:, face] - current * r_e_left
        left_trace = (phi[:, face] - phi_face) / r_e_left
        right_trace = (phi_face - phi[:, face + 1]) / r_e_right
        current_floor = max(float(np.max(np.abs(current))) * 1.0e-12, 1.0e-30)
        e_current = np.linalg.norm(left_trace - right_trace) / np.sqrt(
            0.5
            * (np.linalg.norm(left_trace) ** 2 + np.linalg.norm(right_trace) ** 2)
            + current_floor**2
        )

        r_q_left = 0.5 * grid.dx_m / (sheet[:, face] * grid.dy_m)
        r_q_right = 0.5 * grid.dx_m / (sheet[:, face + 1] * grid.dy_m)
        heat = (temperature[:, face] - temperature[:, face + 1]) / (
            r_q_left + r_q_right
        )
        temperature_face = temperature[:, face] - heat * r_q_left
        q_left = (temperature[:, face] - temperature_face) / r_q_left
        q_right = (temperature_face - temperature[:, face + 1]) / r_q_right
        heat_floor = max(float(np.max(np.abs(heat))) * 1.0e-12, 1.0e-30)
        e_heat = np.linalg.norm(q_left - q_right) / np.sqrt(
            0.5 * (np.linalg.norm(q_left) ** 2 + np.linalg.norm(q_right) ** 2)
            + heat_floor**2
        )
        mismatches.append(float(max(e_current, e_heat)))
    return max(mismatches, default=0.0)


def reconstruct_conservative_teacher(
    context: GeoStateReferenceContext,
    case: M1TeacherCase,
    base_config: Mapping[str, Any],
) -> tuple[dict[str, float | bool | str], ConservativeTeacherFields]:
    """Reconstruct the exact discrete teacher objective without a solve."""

    grid = context.grid
    if case.potential_V.shape != grid.shape:
        raise ValueError(f"{case.case_id} does not match the locked grid")
    factor = factor_sheet_electrical(
        grid, case.conductivity_S_m, topology=context.electrical_topology
    )
    contact = base_config["physical_model"]["model_forms"]["M1"]
    rc_left = float(contact["electrical_contact_resistance_ohm"]["left"])
    rc_right = float(contact["electrical_contact_resistance_ohm"]["right"])
    left_face_r = rc_left * grid.ny
    right_face_r = rc_right * grid.ny
    source_base = np.asarray(factor.source_face_conductance_S)
    ground_base = np.asarray(factor.ground_face_conductance_S)
    source_g = 1.0 / (1.0 / source_base + left_face_r)
    ground_g = 1.0 / (1.0 / ground_base + right_face_r)
    phi = case.potential_V

    x_current = np.empty((grid.ny, grid.nx + 1), dtype=float)
    y_current = np.zeros((grid.ny + 1, grid.nx), dtype=float)
    x_current[:, 0] = source_g * (case.device_voltage_V - phi[:, 0])
    x_current[:, 1:-1] = np.asarray(factor.x_face_conductance_S) * (
        phi[:, :-1] - phi[:, 1:]
    )
    x_current[:, -1] = ground_g * phi[:, -1]
    y_current[1:-1, :] = np.asarray(factor.y_face_conductance_S) * (
        phi[:-1, :] - phi[1:, :]
    )
    current_residual = (
        x_current[:, 1:]
        - x_current[:, :-1]
        + y_current[1:, :]
        - y_current[:-1, :]
    )
    source_current = float(np.sum(x_current[:, 0]))
    ground_current = float(np.sum(x_current[:, -1]))
    current_scale = max(
        float(np.percentile(np.abs(x_current), 95)),
        float(np.percentile(np.abs(y_current), 95)),
        abs(source_current) / grid.ny,
        1.0e-30,
    )
    normalized_current = np.abs(current_residual) / current_scale

    source_surface = phi[:, 0] + x_current[:, 0] / source_base
    ground_surface = phi[:, -1] - x_current[:, -1] / ground_base
    source_contact_current = (case.device_voltage_V - source_surface) / left_face_r
    ground_contact_current = ground_surface / right_face_r
    robin_residual = np.concatenate(
        [x_current[:, 0] - source_contact_current, x_current[:, -1] - ground_contact_current]
    )
    robin_scale = max(
        float(np.percentile(np.abs(np.concatenate([x_current[:, 0], x_current[:, -1]])), 95)),
        1.0e-30,
    )

    internal_joule = np.zeros(grid.shape, dtype=float)
    x_power = np.asarray(factor.x_face_conductance_S) * (
        phi[:, :-1] - phi[:, 1:]
    ) ** 2
    y_power = np.asarray(factor.y_face_conductance_S) * (
        phi[:-1, :] - phi[1:, :]
    ) ** 2
    internal_joule[:, :-1] += 0.5 * x_power
    internal_joule[:, 1:] += 0.5 * x_power
    internal_joule[:-1, :] += 0.5 * y_power
    internal_joule[1:, :] += 0.5 * y_power
    internal_joule[:, 0] += x_current[:, 0] ** 2 / source_base
    internal_joule[:, -1] += x_current[:, -1] ** 2 / ground_base
    contact_joule = np.zeros(grid.shape, dtype=float)
    contact_joule[:, 0] = x_current[:, 0] ** 2 * left_face_r
    contact_joule[:, -1] = x_current[:, -1] ** 2 * right_face_r

    gx, gy = _thermal_face_conductances(context)
    temperature = case.temperature_K
    x_heat = np.zeros((grid.ny, grid.nx + 1), dtype=float)
    y_heat = np.zeros((grid.ny + 1, grid.nx), dtype=float)
    x_heat[:, 1:-1] = gx * (temperature[:, :-1] - temperature[:, 1:])
    y_heat[1:-1, :] = gy * (temperature[:-1, :] - temperature[1:, :])
    lateral_outflow = (
        x_heat[:, 1:] - x_heat[:, :-1] + y_heat[1:, :] - y_heat[:-1, :]
    )
    vertical_g, resistance = m1_vertical_conductance(context, case, base_config)
    sink = (
        vertical_g
        * grid.cell_area_m2
        * (temperature - context.ambient_temperature_K)
    )
    energy_residual = lateral_outflow - internal_joule - contact_joule + sink
    energy_scale = max(
        float(np.percentile(np.abs(internal_joule + contact_joule), 95)),
        float(np.percentile(np.abs(sink), 95)),
        abs(case.device_voltage_V * source_current) / (grid.nx * grid.ny),
        1.0e-30,
    )
    normalized_energy = np.abs(energy_residual) / energy_scale

    stored_sink = case.stored_sink_heat_W_m2
    expected_sink = vertical_g * (temperature - context.ambient_temperature_K)
    sink_scale = max(float(np.percentile(np.abs(expected_sink), 95)), 1.0e-30)
    thermal_closure = np.abs(stored_sink - expected_sink) / sink_scale
    del resistance

    terminal_power = case.device_voltage_V * source_current
    total_internal = float(np.sum(internal_joule))
    total_contact = float(np.sum(contact_joule))
    total_electrical_heat = total_internal + total_contact
    total_sink = float(np.sum(sink))
    electrical_ledger = abs(terminal_power - total_electrical_heat) / max(
        abs(terminal_power), abs(total_electrical_heat), 1.0e-30
    )
    sink_ledger = abs(total_electrical_heat - total_sink) / max(
        abs(total_electrical_heat), abs(total_sink), 1.0e-30
    )
    interface = _interface_flux_mismatch(context, case)
    finite = bool(
        all(
            np.isfinite(values).all()
            for values in (
                normalized_current,
                normalized_energy,
                robin_residual,
                thermal_closure,
            )
        )
        and np.isfinite([electrical_ledger, sink_ledger, interface]).all()
    )
    row: dict[str, float | bool | str] = {
        "case_id": case.case_id,
        "finite": finite,
        "local_current_balance_p95": float(np.percentile(normalized_current, 95)),
        "local_energy_balance_p95": float(np.percentile(normalized_energy, 95)),
        "external_robin_residual_p95": float(
            np.percentile(np.abs(robin_residual) / robin_scale, 95)
        ),
        "thermal_contact_closure_p95": float(np.percentile(thermal_closure, 95)),
        "interface_flux_mismatch": float(interface),
        "terminal_electrical_heat_ledger_error": float(electrical_ledger),
        "electrical_heat_sink_ledger_error": float(sink_ledger),
        "source_current_A": source_current,
        "ground_current_A": ground_current,
        "terminal_power_W": terminal_power,
        "internal_joule_W": total_internal,
        "contact_joule_W": total_contact,
        "vertical_sink_W": total_sink,
    }
    fields = ConservativeTeacherFields(
        electrical_x_face_current_A=x_current,
        electrical_y_face_current_A=y_current,
        thermal_x_face_power_W=x_heat,
        thermal_y_face_power_W=y_heat,
        source_face_current_A=x_current[:, 0].copy(),
        ground_face_current_A=x_current[:, -1].copy(),
        internal_joule_cell_W=internal_joule,
        contact_joule_cell_W=contact_joule,
        vertical_sink_cell_W=sink,
        normalized_current_residual=normalized_current,
        normalized_energy_residual=normalized_energy,
    )
    return row, fields


def compatibility_passes(
    rows: Sequence[Mapping[str, Any]], rescue_config: Mapping[str, Any]
) -> tuple[bool, dict[str, Any]]:
    gates = rescue_config["compatibility"]
    summary = {
        "case_count": len(rows),
        "finite_case_count": sum(bool(row["finite"]) for row in rows),
        "max_local_current_balance_p95": max(
            float(row["local_current_balance_p95"]) for row in rows
        ),
        "max_local_energy_balance_p95": max(
            float(row["local_energy_balance_p95"]) for row in rows
        ),
        "max_external_robin_residual_p95": max(
            float(row["external_robin_residual_p95"]) for row in rows
        ),
        "max_thermal_contact_closure_p95": max(
            float(row["thermal_contact_closure_p95"]) for row in rows
        ),
        "max_interface_flux_mismatch": max(
            float(row["interface_flux_mismatch"]) for row in rows
        ),
        "max_terminal_electrical_heat_ledger_error": max(
            float(row["terminal_electrical_heat_ledger_error"]) for row in rows
        ),
        "max_electrical_heat_sink_ledger_error": max(
            float(row["electrical_heat_sink_ledger_error"]) for row in rows
        ),
    }
    passed = bool(
        summary["case_count"] == int(rescue_config["reference"]["expected_cases"])
        and summary["finite_case_count"] == summary["case_count"]
        and summary["max_local_current_balance_p95"]
        <= float(gates["local_current_p95_max"])
        and summary["max_local_energy_balance_p95"]
        <= float(gates["local_energy_p95_max"])
        and summary["max_external_robin_residual_p95"]
        <= float(gates["external_robin_p95_max"])
        and summary["max_thermal_contact_closure_p95"]
        <= float(gates["thermal_contact_closure_p95_max"])
        and summary["max_interface_flux_mismatch"]
        <= float(gates["interface_flux_mismatch_max"])
        and summary["max_terminal_electrical_heat_ledger_error"]
        <= float(gates["terminal_electrical_heat_ledger_max"])
        and summary["max_electrical_heat_sink_ledger_error"]
        <= float(gates["electrical_heat_sink_ledger_max"])
    )
    summary["passed"] = passed
    summary["disposition_if_stopped"] = (
        None if passed else "NO_GO_TEACHER_OBJECTIVE_INCOMPATIBLE"
    )
    return passed, summary
