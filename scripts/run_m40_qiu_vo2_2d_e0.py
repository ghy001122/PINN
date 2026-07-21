"""Preregister and execute the formal M40 Qiu-VO2 conservative 2D E0 verifier."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml

from pinnpcm.physics.qiu_vo2_device import (
    QiuCircuit,
    QiuGeometry,
    QiuHysteresis,
    QiuMesh,
    advance_history_state,
    build_qiu_domain_masks,
    major_loop_targets,
    material_property_fields,
)
from pinnpcm.solvers.qiu_vo2_2d_fvm import (
    BoundaryFace,
    advance_thermal_implicit,
    cell_electric_field_V_m,
    implicit_rc_voltage,
    qiu_terminal_faces,
    rc_residual_A,
    solve_electrical,
    solve_steady_thermal,
)


ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _resolve(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    records = list(rows)
    fields: list[str] = []
    for row in records:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({key: _jsonable(row.get(key)) for key in fields})


def _load_config(path: str | Path) -> dict[str, Any]:
    return dict(yaml.safe_load(_resolve(path).read_text(encoding="utf-8")))


def _frozen_files() -> list[Path]:
    fixed = [
        ROOT / "configs/gt_v1_acceptance_triangle.yaml",
        ROOT / "configs/gt_v1_acceptance_ltp_ltd.yaml",
        ROOT / "docs/gt_v1_acceptance_report.md",
        ROOT / "data/processed/gt_v1_acceptance/manifest.json",
    ]
    arrays = sorted((ROOT / "data/processed/gt_v1_acceptance").glob("**/*"))
    return sorted({path for path in [*fixed, *arrays] if path.is_file()})


def _hash_records(paths: Sequence[Path]) -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): _sha256(path)
        for path in paths
        if path.exists() and path.is_file()
    }


def _generic_mesh(
    x_edges_m: np.ndarray,
    z_edges_m: np.ndarray,
    material: np.ndarray,
    *,
    depth_m: float,
    electrical_mask: np.ndarray | None = None,
    thermal_mask: np.ndarray | None = None,
) -> QiuMesh:
    values = np.asarray(material, dtype="U12")
    electrical = np.ones(values.shape, dtype=bool) if electrical_mask is None else np.asarray(electrical_mask, dtype=bool)
    thermal = np.ones(values.shape, dtype=bool) if thermal_mask is None else np.asarray(thermal_mask, dtype=bool)
    return QiuMesh(
        x_edges_m=np.asarray(x_edges_m, dtype=float),
        z_edges_m=np.asarray(z_edges_m, dtype=float),
        material=values,
        electrical_mask=electrical,
        thermal_mask=thermal,
        source_terminal_cells=(),
        ground_terminal_cells=(),
        depth_m=float(depth_m),
    )


def _side_terminals(mesh: QiuMesh, left_value: float, right_value: float) -> list[BoundaryFace]:
    return [
        *[
            BoundaryFace("source", iz, 0, "left", left_value)
            for iz in range(mesh.shape[0])
            if mesh.electrical_mask[iz, 0]
        ],
        *[
            BoundaryFace("ground", iz, mesh.shape[1] - 1, "right", right_value)
            for iz in range(mesh.shape[0])
            if mesh.electrical_mask[iz, mesh.shape[1] - 1]
        ],
    ]


def _manufactured_and_uniform(config: Mapping[str, Any]) -> dict[str, float]:
    nx = int(config["verification"]["manufactured_grid"]["nx"])
    nz = int(config["verification"]["manufactured_grid"]["nz"])
    length, height, depth = 2.0e-6, 8.0e-7, 5.0e-7
    sigma_value, voltage = 7.5e3, 0.8
    mesh = _generic_mesh(
        np.linspace(0.0, length, nx + 1),
        np.linspace(0.0, height, nz + 1),
        np.full((nz, nx), "uniform"),
        depth_m=depth,
    )
    sigma = np.full(mesh.shape, sigma_value)
    result = solve_electrical(mesh, sigma, _side_terminals(mesh, voltage, 0.0))
    expected_phi = voltage * (1.0 - mesh.x_centers_m / length)
    expected = np.repeat(expected_phi[None, :], nz, axis=0)
    l2 = float(
        np.linalg.norm(result["potential_V"] - expected)
        / max(np.linalg.norm(expected), 1.0e-30)
    )
    area = height * depth
    expected_current = sigma_value * area * voltage / length
    current = float(result["terminal_currents_A"]["source"])
    reduced_error = abs(current - expected_current) / abs(expected_current)
    return {
        "manufactured_electrical_relative_l2": l2,
        "uniform_2d_to_reduced_error": float(reduced_error),
        "manufactured_current_imbalance": float(result["relative_current_imbalance"]),
        "manufactured_power_imbalance": float(result["relative_electrical_power_imbalance"]),
    }


def _layered_electrical() -> dict[str, float]:
    length, depth = 1.2e-6, 6.0e-7
    z_edges = np.concatenate(
        [np.linspace(0.0, 0.4e-6, 5), np.linspace(0.4e-6, 1.0e-6, 7)[1:]]
    )
    nx, nz = 12, z_edges.size - 1
    z = 0.5 * (z_edges[:-1] + z_edges[1:])
    material = np.where(z[:, None] < 0.4e-6, "layer_a", "layer_b")
    material = np.repeat(material, nx, axis=1)
    mesh = _generic_mesh(
        np.linspace(0.0, length, nx + 1), z_edges, material, depth_m=depth
    )
    sigma = np.where(material == "layer_a", 2.0e3, 9.0e3)
    result = solve_electrical(mesh, sigma, _side_terminals(mesh, 1.0, 0.0))
    expected = depth / length * (2.0e3 * 0.4e-6 + 9.0e3 * 0.6e-6)
    current = float(result["terminal_currents_A"]["source"])
    return {
        "layered_electrical_relative_error": abs(current - expected) / abs(expected),
        "layered_current_imbalance": float(result["relative_current_imbalance"]),
    }


def _electrical_contact_jump() -> dict[str, float]:
    L1, L2, height, depth = 0.8e-6, 1.2e-6, 0.5e-6, 0.7e-6
    sigma1, sigma2, rc = 4.0e3, 8.0e3, 2.0e-10
    x_edges = np.concatenate(
        [np.linspace(0.0, L1, 5), np.linspace(L1, L1 + L2, 7)[1:]]
    )
    nx, nz = x_edges.size - 1, 4
    x = 0.5 * (x_edges[:-1] + x_edges[1:])
    material = np.where(x[None, :] < L1, "leftmat", "rightmat")
    material = np.repeat(material, nz, axis=0)
    mesh = _generic_mesh(
        x_edges, np.linspace(0.0, height, nz + 1), material, depth_m=depth
    )
    sigma = np.where(material == "leftmat", sigma1, sigma2)
    result = solve_electrical(
        mesh,
        sigma,
        _side_terminals(mesh, 1.0, 0.0),
        {("leftmat", "rightmat"): rc},
    )
    area = height * depth
    expected = 1.0 / (L1 / (sigma1 * area) + rc / area + L2 / (sigma2 * area))
    current = float(result["terminal_currents_A"]["source"])
    expected_jump = expected * rc / area
    jumps = [abs(float(row["contact_voltage_jump_V"])) for row in result["interface_records"]]
    observed_jump = float(np.mean(jumps))
    return {
        "electrical_contact_current_relative_error": abs(current - expected) / abs(expected),
        "electrical_contact_jump_relative_error": abs(observed_jump - expected_jump) / abs(expected_jump),
    }


def _layered_thermal() -> dict[str, float]:
    width, depth = 0.8e-6, 0.6e-6
    d1, d2, k1, k2, rth = 0.4e-6, 0.6e-6, 2.5, 11.0, 3.0e-8
    x_edges = np.linspace(0.0, width, 5)
    z_edges = np.concatenate(
        [np.linspace(0.0, d1, 5), np.linspace(d1, d1 + d2, 7)[1:]]
    )
    z = 0.5 * (z_edges[:-1] + z_edges[1:])
    material = np.where(z[:, None] < d1, "coldmat", "hotmat")
    material = np.repeat(material, x_edges.size - 1, axis=1)
    mesh = _generic_mesh(x_edges, z_edges, material, depth_m=depth)
    k = np.where(material == "coldmat", k1, k2)
    bottom = [BoundaryFace("hot", 0, ix, "bottom", 350.0) for ix in range(mesh.shape[1])]
    top = [BoundaryFace("cold", mesh.shape[0] - 1, ix, "top", 300.0) for ix in range(mesh.shape[1])]
    result = solve_steady_thermal(
        mesh, k, [*bottom, *top], {("coldmat", "hotmat"): rth}
    )
    area = width * depth
    expected = 50.0 * area / (d1 / k1 + rth + d2 / k2)
    observed = float(result["boundary_heat_in_W"]["hot"])
    q_density = observed / area
    lower_index = np.flatnonzero(z < d1)[-1]
    upper_index = np.flatnonzero(z > d1)[0]
    center_drop = float(
        np.mean(result["temperature_K"][lower_index])
        - np.mean(result["temperature_K"][upper_index])
    )
    bulk_half_drop = q_density * (
        0.5 * mesh.dz_m[lower_index] / k1
        + 0.5 * mesh.dz_m[upper_index] / k2
    )
    observed_jump = center_drop - bulk_half_drop
    expected_jump = q_density * rth
    return {
        "layered_thermal_relative_error": abs(observed - expected) / abs(expected),
        "thermal_interface_jump_relative_error": abs(observed_jump - expected_jump) / max(abs(expected_jump), 1.0e-30),
        "thermal_steady_balance": float(result["relative_heat_imbalance"]),
    }


def _model_objects(config: Mapping[str, Any]) -> tuple[QiuGeometry, QiuHysteresis, QiuCircuit]:
    return (
        QiuGeometry.from_mapping(config["geometry"]),
        QiuHysteresis.from_mapping(config["hysteresis"]),
        QiuCircuit.from_mapping(config["circuit"]),
    )


def _interface_maps(config: Mapping[str, Any]) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    electrical = {
        ("vo2", "ti"): float(
            config["interfaces"]["electrical_contact_resistance_m2_ohm"]["vo2_ti"]
        )
    }
    thermal_values = config["interfaces"]["thermal_boundary_resistance_m2K_W"]
    thermal = {
        ("vo2", "al2o3"): float(thermal_values["vo2_al2o3"]),
        ("vo2", "ti"): float(thermal_values["vo2_ti"]),
        ("ti", "au"): float(thermal_values["ti_au"]),
    }
    return electrical, thermal


def _initial_fields(
    mesh: QiuMesh, circuit: QiuCircuit, hysteresis: QiuHysteresis
) -> tuple[np.ndarray, np.ndarray]:
    temperature = np.full(mesh.shape, circuit.ambient_temperature_K, dtype=float)
    heating, _ = major_loop_targets(temperature, hysteresis)
    history = np.asarray(heating, dtype=float)
    return temperature, history


def _substrate_tamper(config: Mapping[str, Any]) -> dict[str, float]:
    geometry, hysteresis, circuit = _model_objects(config)
    mesh = build_qiu_domain_masks(geometry, 2)
    temperature, history = _initial_fields(mesh, circuit, hysteresis)
    sigma, _, _ = material_property_fields(
        mesh, temperature, history, geometry, hysteresis, config["materials"]
    )
    electrical_contacts, _ = _interface_maps(config)
    terminals = qiu_terminal_faces(mesh, 1.0)
    low = sigma.copy()
    high = sigma.copy()
    low[mesh.material == "al2o3"] = 1.0e-14
    high[mesh.material == "al2o3"] = 1.0e8
    official_low = solve_electrical(mesh, low, terminals, electrical_contacts)
    official_high = solve_electrical(mesh, high, terminals, electrical_contacts)
    tampered = solve_electrical(
        mesh,
        high,
        terminals,
        electrical_contacts,
        electrical_mask=mesh.thermal_mask,
    )
    reference = float(official_low["terminal_currents_A"]["source"])
    invariant = abs(
        float(official_high["terminal_currents_A"]["source"]) - reference
    ) / max(abs(reference), 1.0e-30)
    effect = abs(float(tampered["terminal_currents_A"]["source"]) - reference) / max(
        abs(reference), 1.0e-30
    )
    return {
        "substrate_invariance_relative_error": float(invariant),
        "substrate_tamper_effect_relative": float(effect),
    }


def _energy_ledgers(config: Mapping[str, Any]) -> dict[str, float | bool]:
    geometry, hysteresis, circuit = _model_objects(config)
    mesh = build_qiu_domain_masks(geometry, 1)
    temperature, history = _initial_fields(mesh, circuit, hysteresis)
    _, k, rho_cp = material_property_fields(
        mesh, temperature, history, geometry, hysteresis, config["materials"]
    )
    _, thermal_interfaces = _interface_maps(config)
    bottom = float(config["interfaces"]["bottom_conductance_W_K"])
    smooth_heat = np.zeros(mesh.shape)
    smooth_heat[mesh.material == "vo2"] = 1.0e-8 / np.sum(mesh.material == "vo2")
    smooth = advance_thermal_implicit(
        mesh,
        temperature,
        k,
        rho_cp,
        smooth_heat,
        1.0e-10,
        circuit.ambient_temperature_K,
        bottom,
        thermal_interfaces,
    )
    switch_cfg = config["verification"]["switching_fixture"]
    dt = float(switch_cfg["dt_s"])
    steps = int(switch_cfg["steps"])
    target_rise = float(switch_cfg["pulse_temperature_rise_target_K"])
    old_T = np.full(mesh.shape, hysteresis.critical_temperature_K - 8.0)
    h, _ = major_loop_targets(old_T, hysteresis)
    initial_h = np.asarray(h, dtype=float).copy()
    switching_errors: list[float] = []
    for _ in range(steps):
        cell_volume = mesh.dz_m[:, None] * mesh.dx_m[None, :] * mesh.depth_m
        heat = np.zeros(mesh.shape)
        vo2 = mesh.material == "vo2"
        heat[vo2] = rho_cp[vo2] * cell_volume[vo2] * (target_rise / steps) / dt
        step = advance_thermal_implicit(
            mesh,
            old_T,
            k,
            rho_cp,
            heat,
            dt,
            circuit.ambient_temperature_K,
            bottom,
            thermal_interfaces,
        )
        new_T = np.asarray(step["temperature_K"])
        h_new = h.copy()
        h_new[vo2] = advance_history_state(
            old_T[vo2], new_T[vo2], h[vo2], dt, hysteresis
        )
        h = h_new
        old_T = new_T
        switching_errors.append(float(step["relative_energy_imbalance"]))
    history_change = float(np.mean(np.abs(h[vo2] - initial_h[vo2])))
    return {
        "smooth_window_energy_imbalance": float(smooth["relative_energy_imbalance"]),
        "switching_window_energy_imbalance": float(max(switching_errors)),
        "switching_fixture_history_change": history_change,
        "switching_fixture_exercised": bool(history_change > 1.0e-3),
    }


def _mesh_refinement(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    geometry, hysteresis, circuit = _model_objects(config)
    electrical_contacts, _ = _interface_maps(config)
    peak = config["verification"]["peak_field_definition"]
    x_exclusion = float(peak["x_exclusion_from_contact_edge_m"])
    z_exclusion = float(peak["z_exclusion_from_vo2_boundary_m"])
    rows: list[dict[str, Any]] = []
    for level in config["verification"]["mesh_refinement_levels"]:
        mesh = build_qiu_domain_masks(geometry, int(level))
        temperature, history = _initial_fields(mesh, circuit, hysteresis)
        sigma, _, _ = material_property_fields(
            mesh, temperature, history, geometry, hysteresis, config["materials"]
        )
        result = solve_electrical(
            mesh, sigma, qiu_terminal_faces(mesh, 1.0), electrical_contacts
        )
        field = cell_electric_field_V_m(mesh, result["potential_V"], sigma)
        xx, zz = np.meshgrid(mesh.x_centers_m, mesh.z_centers_m)
        core = (
            (mesh.material == "vo2")
            & (xx >= geometry.electrode_overlap_m + x_exclusion)
            & (xx <= geometry.device_length_m - geometry.electrode_overlap_m - x_exclusion)
            & (zz >= z_exclusion)
            & (zz <= geometry.vo2_thickness_m - z_exclusion)
        )
        if not np.any(core):
            raise RuntimeError("predeclared peak-field physical window is empty")
        row = {
            "refinement": int(level),
            "nx": int(mesh.shape[1]),
            "nz": int(mesh.shape[0]),
            "source_current_A_at_1V": float(result["terminal_currents_A"]["source"]),
            "peak_field_p99_V_m": float(np.nanpercentile(field[core], 99.0)),
            "relative_current_imbalance": float(result["relative_current_imbalance"]),
        }
        if rows:
            row["main_qoi_change_from_previous"] = abs(
                row["source_current_A_at_1V"] - rows[-1]["source_current_A_at_1V"]
            ) / max(abs(row["source_current_A_at_1V"]), 1.0e-30)
            row["peak_field_change_from_previous"] = abs(
                row["peak_field_p99_V_m"] - rows[-1]["peak_field_p99_V_m"]
            ) / max(abs(row["peak_field_p99_V_m"]), 1.0e-30)
        else:
            row["main_qoi_change_from_previous"] = None
            row["peak_field_change_from_previous"] = None
        rows.append(row)
    return rows, {
        "main_qoi_mesh_change": float(rows[-1]["main_qoi_change_from_previous"]),
        "peak_field_mesh_change": float(rows[-1]["peak_field_change_from_previous"]),
        "maximum_mesh_current_imbalance": float(
            max(row["relative_current_imbalance"] for row in rows)
        ),
    }


def _nominal_smoke(config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray], QiuMesh]:
    geometry, hysteresis, circuit = _model_objects(config)
    smoke = config["nominal_smoke"]
    mesh = build_qiu_domain_masks(geometry, int(smoke["refinement"]))
    temperature, history = _initial_fields(mesh, circuit, hysteresis)
    voltage = float(smoke["initial_voltage_V"])
    dt = float(smoke["dt_s"])
    electrical_contacts, thermal_interfaces = _interface_maps(config)
    bottom = float(config["interfaces"]["bottom_conductance_W_K"])
    times, voltages, currents, tmax, hmean = [], [], [], [], []
    max_current_imbalance = 0.0
    max_energy_imbalance = 0.0
    max_rc_residual = 0.0
    last_electrical: dict[str, Any] | None = None
    for step_index in range(int(smoke["steps"])):
        sigma, k, rho_cp = material_property_fields(
            mesh, temperature, history, geometry, hysteresis, config["materials"]
        )
        unit = solve_electrical(
            mesh, sigma, qiu_terminal_faces(mesh, 1.0), electrical_contacts
        )
        conductance = float(unit["terminal_currents_A"]["source"])
        new_voltage = implicit_rc_voltage(
            voltage,
            circuit.input_voltage_V,
            circuit.load_resistance_ohm,
            circuit.parallel_capacitance_F,
            conductance,
            dt,
        )
        current = conductance * new_voltage
        heat = np.asarray(unit["cell_joule_power_W"]) * new_voltage**2
        thermal = advance_thermal_implicit(
            mesh,
            temperature,
            k,
            rho_cp,
            heat,
            dt,
            circuit.ambient_temperature_K,
            bottom,
            thermal_interfaces,
        )
        new_temperature = np.asarray(thermal["temperature_K"])
        vo2 = mesh.material == "vo2"
        new_history = history.copy()
        new_history[vo2] = advance_history_state(
            temperature[vo2], new_temperature[vo2], history[vo2], dt, hysteresis
        )
        residual = abs(
            rc_residual_A(
                voltage,
                new_voltage,
                circuit.input_voltage_V,
                circuit.load_resistance_ohm,
                circuit.parallel_capacitance_F,
                current,
                dt,
            )
        )
        max_current_imbalance = max(
            max_current_imbalance, float(unit["relative_current_imbalance"])
        )
        max_energy_imbalance = max(
            max_energy_imbalance, float(thermal["relative_energy_imbalance"])
        )
        max_rc_residual = max(max_rc_residual, residual)
        voltage = new_voltage
        temperature = new_temperature
        history = new_history
        times.append((step_index + 1) * dt)
        voltages.append(voltage)
        currents.append(current)
        tmax.append(float(np.nanmax(temperature)))
        hmean.append(float(np.mean(history[vo2])))
        last_electrical = {
            **unit,
            "potential_V": np.asarray(unit["potential_V"]) * voltage,
        }
    assert last_electrical is not None
    finite = bool(
        np.isfinite(temperature[mesh.thermal_mask]).all()
        and np.isfinite(history[mesh.material == "vo2"]).all()
        and np.isfinite(voltages).all()
        and np.isfinite(currents).all()
    )
    metrics = {
        "nominal_smoke_finite": finite,
        "nominal_final_voltage_V": float(voltage),
        "nominal_final_current_A": float(currents[-1]),
        "nominal_max_temperature_K": float(max(tmax)),
        "nominal_final_mean_history": float(hmean[-1]),
        "nominal_max_current_imbalance": float(max_current_imbalance),
        "nominal_max_energy_imbalance": float(max_energy_imbalance),
        "nominal_max_rc_residual_A": float(max_rc_residual),
        "nominal_steps": int(smoke["steps"]),
        "nominal_dt_s": dt,
        "nominal_is_smoke_not_curve_reproduction": True,
    }
    fields = {
        "temperature_K": temperature,
        "history": history,
        "potential_V": np.asarray(last_electrical["potential_V"]),
        "time_s": np.asarray(times),
        "voltage_V": np.asarray(voltages),
        "current_A": np.asarray(currents),
    }
    return metrics, fields, mesh


def _plot_geometry(config: Mapping[str, Any], mesh: QiuMesh) -> None:
    target = _resolve(config["outputs"]["geometry_figure"])
    target.parent.mkdir(parents=True, exist_ok=True)
    codes = {"void": 0, "al2o3": 1, "vo2": 2, "ti": 3, "au": 4}
    values = np.vectorize(codes.get)(mesh.material)
    fig, ax = plt.subplots(figsize=(7.0, 3.8), constrained_layout=True)
    image = ax.pcolormesh(
        mesh.x_edges_m * 1e9,
        mesh.z_edges_m * 1e9,
        values,
        shading="flat",
        cmap=plt.get_cmap("viridis", 5),
        vmin=-0.5,
        vmax=4.5,
    )
    colorbar = fig.colorbar(image, ax=ax, ticks=list(codes.values()))
    colorbar.ax.set_yticklabels(list(codes))
    ax.set_xlabel("x (nm)")
    ax.set_ylabel("z (nm)")
    ax.set_title("Qiu-source-constrained E0 geometry; overlap/substrate depth are priors")
    fig.savefig(target, dpi=180)
    plt.close(fig)


def _plot_fields(config: Mapping[str, Any], mesh: QiuMesh, fields: Mapping[str, np.ndarray]) -> None:
    target = _resolve(config["outputs"]["field_figure"])
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.5), constrained_layout=True)
    for ax, key, title in zip(
        axes,
        ("potential_V", "temperature_K", "history"),
        ("Potential (V)", "Temperature (K)", "History h"),
        strict=True,
    ):
        data = np.asarray(fields[key])
        image = ax.pcolormesh(
            mesh.x_edges_m * 1e9,
            mesh.z_edges_m * 1e9,
            data,
            shading="flat",
        )
        fig.colorbar(image, ax=ax)
        ax.set_title(title)
        ax.set_xlabel("x (nm)")
        ax.set_ylabel("z (nm)")
    fig.suptitle("M40 nominal Qiu protocol smoke fields (solver-generated, not measured)")
    fig.savefig(target, dpi=180)
    plt.close(fig)


def _preregistration(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    if _git("rev-parse", "HEAD") != str(config["base_snapshot"]):
        raise RuntimeError("M40 preregistration must start from the declared baseline")
    manifest = json.loads(_resolve(config["source_contract"]["manifest"]).read_text(encoding="utf-8"))
    for source in manifest["sources"][:2]:
        if _sha256(source["local_raw_path"]) != str(source["sha256"]):
            raise RuntimeError(f"Qiu source hash mismatch: {source['artifact_id']}")
    locked_relative = [
        config_path.relative_to(ROOT).as_posix(),
        "data/external/qiu_2024_thermal_neuristor/manifest.json",
        "src/pinnpcm/physics/qiu_vo2_device.py",
        "src/pinnpcm/solvers/__init__.py",
        "src/pinnpcm/solvers/qiu_vo2_2d_fvm.py",
        "scripts/run_m40_qiu_vo2_2d_e0.py",
        "tests/test_m40_qiu_geometry.py",
        "tests/test_m40_qiu_2d_fvm.py",
        "tests/test_m40_qiu_energy_ledger.py",
        "tests/test_m40_qiu_result_evidence.py",
        "docs/physics/m40_qiu_model_responsibility.md",
        "docs/physics/m40_qiu_2d_equations.md",
    ]
    missing = [name for name in locked_relative if not _resolve(name).exists()]
    if missing:
        raise RuntimeError(f"M40 preregistration files missing: {missing}")
    historical = [
        "outputs/tables/m37r_cross_regime_jacobian.json",
        "outputs/tables/m34_contract_audit_summary.json",
        "outputs/tables/m33_mixed_flux_final_summary.json",
        "outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json",
    ]
    payload = {
        "schema_version": "m40_qiu_e0_preregistration_v1",
        "task_id": config["task_id"],
        "created_at_utc": _utc_now(),
        "base_snapshot": config["base_snapshot"],
        "head_before_preregistration_commit": _git("rev-parse", "HEAD"),
        "formal_execution_limit": int(config["execution_contract"]["formal_execution_limit"]),
        "formal_solver_executed": False,
        "source_contract_complete_for_e0": True,
        "source_contract_complete_for_real_device_calibration": False,
        "parameter_setting_lock": config["source_contract"]["parameter_setting_lock"],
        "nominal_protocol_lock": config["source_contract"]["nominal_protocol"],
        "holdout_lock": config["source_contract"]["repository_withheld_future_curve"],
        "gate_thresholds": config["gates"],
        "peak_field_definition": config["verification"]["peak_field_definition"],
        "mesh_refinement_levels": config["verification"]["mesh_refinement_levels"],
        "locked_files": {name: _sha256(name) for name in locked_relative},
        "frozen_gt_hashes": _hash_records(_frozen_files()),
        "historical_read_only_hashes": {
            name: _sha256(name) for name in historical if _resolve(name).exists()
        },
        "raw_source_hashes": {
            source["artifact_id"]: source["sha256"] for source in manifest["sources"][:2]
        },
        "forbidden_actions": [
            "inverse",
            "PINN training",
            "parameter search",
            "M38",
            "Zhang sealed 13 V access",
            "frozen GT modification",
            "real-device calibrated wording",
            "experimental validation wording",
        ],
    }
    _write_json(config["outputs"]["preregistration"], payload)
    return payload


def _verify_formal_lock(config: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    path = _resolve(config["outputs"]["preregistration"])
    if not path.exists():
        raise RuntimeError("formal E0 requires the preregistration artifact")
    if _resolve(config["outputs"]["summary"]).exists():
        raise RuntimeError("formal E0 execution limit already consumed")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    if head == str(config["base_snapshot"]):
        raise RuntimeError("formal E0 requires a separate preregistration commit")
    if _git("status", "--short"):
        raise RuntimeError("formal E0 requires a clean preregistration commit")
    mismatches = {
        name: {"expected": expected, "actual": _sha256(name) if _resolve(name).exists() else None}
        for name, expected in prereg["locked_files"].items()
        if not _resolve(name).exists() or _sha256(name) != expected
    }
    if mismatches:
        raise RuntimeError(f"M40 locked-file mismatch: {mismatches}")
    historical_mismatches = {
        name: {"expected": expected, "actual": _sha256(name) if _resolve(name).exists() else None}
        for name, expected in prereg["historical_read_only_hashes"].items()
        if not _resolve(name).exists() or _sha256(name) != expected
    }
    if historical_mismatches:
        raise RuntimeError(f"historical read-only evidence changed: {historical_mismatches}")
    return prereg, head


def _gate_decisions(values: Mapping[str, Any], thresholds: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "manufactured_electrical": values["manufactured_electrical_relative_l2"] <= float(thresholds["manufactured_electrical_relative_l2_max"]),
        "layered_electrical": values["layered_electrical_relative_error"] <= float(thresholds["layered_electrical_relative_error_max"]),
        "layered_thermal": values["layered_thermal_relative_error"] <= float(thresholds["layered_thermal_relative_error_max"]),
        "electrical_contact_jump": values["electrical_contact_jump_relative_error"] <= float(thresholds["electrical_contact_jump_relative_error_max"]),
        "thermal_interface_jump": values["thermal_interface_jump_relative_error"] <= float(thresholds["thermal_interface_jump_relative_error_max"]),
        "substrate_electrical_invariance": values["substrate_invariance_relative_error"] <= float(thresholds["substrate_invariance_relative_error_max"]),
        "substrate_leak_tamper_detection": values["substrate_tamper_effect_relative"] >= float(thresholds["substrate_tamper_effect_relative_min"]),
        "current_conservation": values["relative_current_imbalance"] <= float(thresholds["relative_current_imbalance_max"]),
        "smooth_window_energy_conservation": values["smooth_window_energy_imbalance"] <= float(thresholds["smooth_window_energy_imbalance_max"]),
        "switching_window_energy_conservation": values["switching_window_energy_imbalance"] <= float(thresholds["switching_window_energy_imbalance_max"]) and bool(values["switching_fixture_exercised"]),
        "main_qoi_mesh_convergence": values["main_qoi_mesh_change"] <= float(thresholds["main_qoi_mesh_change_max"]),
        "peak_field_mesh_convergence": values["peak_field_mesh_change"] <= float(thresholds["peak_field_mesh_change_max"]),
        "uniform_2d_to_reduced": values["uniform_2d_to_reduced_error"] <= float(thresholds["uniform_2d_to_reduced_error_max"]),
        "nominal_qiu_forward_smoke": bool(values["nominal_smoke_finite"]) and values["nominal_max_rc_residual_A"] <= float(thresholds["nominal_rc_residual_A_max"]),
    }


def _write_report(config: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    lines = [
        "# M40 Qiu VO2 Conservative 2D E0 Results",
        "",
        f"- Task: `{summary['task_id']}`",
        f"- Base: `{summary['base_snapshot']}`",
        f"- Preregistration commit: `{summary['preregistration_commit']}`",
        f"- Evidence status: `{summary['status']}`",
        f"- E0 all gates pass: `{summary['e0_all_gates_pass']}`",
        f"- Frozen GT unchanged: `{summary['frozen_gt_unchanged']}`",
        "",
        "## Source boundary",
        "",
        "Qiu et al. report the VO2/Ti/Au/Al2O3 geometry, circuit topology,",
        "R-T loops, and lumped fitted compact parameters. Local 2D thermal",
        "properties, substrate thickness, contact resistivity, interface thermal",
        "resistance, and raw numeric curves are unresolved. No fit or digitization",
        "was performed in M40.",
        "",
        "## Formal gates",
        "",
        "| Gate | Value | Threshold | Pass |",
        "| --- | ---: | ---: | :---: |",
    ]
    for name, passed in summary["gate_results"].items():
        value_key = {
            "manufactured_electrical": "manufactured_electrical_relative_l2",
            "layered_electrical": "layered_electrical_relative_error",
            "layered_thermal": "layered_thermal_relative_error",
            "electrical_contact_jump": "electrical_contact_jump_relative_error",
            "thermal_interface_jump": "thermal_interface_jump_relative_error",
            "substrate_electrical_invariance": "substrate_invariance_relative_error",
            "substrate_leak_tamper_detection": "substrate_tamper_effect_relative",
            "current_conservation": "relative_current_imbalance",
            "smooth_window_energy_conservation": "smooth_window_energy_imbalance",
            "switching_window_energy_conservation": "switching_window_energy_imbalance",
            "main_qoi_mesh_convergence": "main_qoi_mesh_change",
            "peak_field_mesh_convergence": "peak_field_mesh_change",
            "uniform_2d_to_reduced": "uniform_2d_to_reduced_error",
            "nominal_qiu_forward_smoke": "nominal_max_rc_residual_A",
        }[name]
        lines.append(
            f"| {name} | {summary['gate_values'][value_key]:.6e} | locked config | {passed} |"
        )
    lines.extend(
        [
            "",
            "## Claim decision",
            "",
            summary["allowed_claim"],
            "",
            "Forbidden: " + "; ".join(summary["forbidden_claims"]),
            "",
            f"M41 conservative reduction authorized: `{summary['m41_conservative_reduction_authorized']}`.",
        ]
    )
    target = _resolve(config["outputs"]["report"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _formal(config: Mapping[str, Any]) -> dict[str, Any]:
    prereg, prereg_commit = _verify_formal_lock(config)
    started = time.perf_counter()
    manufactured = _manufactured_and_uniform(config)
    layered_electrical = _layered_electrical()
    contact = _electrical_contact_jump()
    thermal = _layered_thermal()
    tamper = _substrate_tamper(config)
    energy = _energy_ledgers(config)
    mesh_rows, mesh_metrics = _mesh_refinement(config)
    nominal, fields, nominal_mesh = _nominal_smoke(config)
    values: dict[str, Any] = {
        **manufactured,
        **layered_electrical,
        **contact,
        **thermal,
        **tamper,
        **energy,
        **mesh_metrics,
        **nominal,
    }
    values["relative_current_imbalance"] = max(
        float(values["manufactured_current_imbalance"]),
        float(values["layered_current_imbalance"]),
        float(values["maximum_mesh_current_imbalance"]),
        float(values["nominal_max_current_imbalance"]),
    )
    thresholds = dict(config["gates"])
    decisions = _gate_decisions(values, thresholds)
    frozen_now = _hash_records(_frozen_files())
    frozen_unchanged = frozen_now == prereg["frozen_gt_hashes"]
    all_pass = bool(all(decisions.values()) and frozen_unchanged)
    elapsed = time.perf_counter() - started
    budget_pass = elapsed <= float(config["execution_contract"]["maximum_wall_clock_s"])
    if not budget_pass:
        all_pass = False
        decisions["wall_clock_budget"] = False
    status = "qualified_supported" if all_pass else "failed_but_informative"
    summary = {
        "schema_version": "m40_qiu_e0_summary_v1",
        "task_id": config["task_id"],
        "base_snapshot": config["base_snapshot"],
        "preregistration_commit": prereg_commit,
        "formal_execution_attempt": 1,
        "formal_completed_at_utc": _utc_now(),
        "wall_clock_s": float(elapsed),
        "machine_summary": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "evidence_type": config["evidence_type"],
        "source_namespace": config["namespace"],
        "source_contract": {
            "main_and_supporting_information_hash_locked": True,
            "local_2d_parameters_complete": False,
            "raw_numeric_curves_available": False,
            "nominal_protocol": config["source_contract"]["nominal_protocol"],
            "withheld_curve": config["source_contract"]["repository_withheld_future_curve"],
        },
        "gate_thresholds": thresholds,
        "gate_values": values,
        "gate_results": decisions,
        "e0_all_gates_pass": all_pass,
        "m41_conservative_reduction_authorized": all_pass,
        "frozen_gt_unchanged": frozen_unchanged,
        "frozen_gt_modified": not frozen_unchanged,
        "inverse_executed": False,
        "pinn_training_performed": False,
        "parameter_search_performed": False,
        "m38_executed": False,
        "sealed_13v_access": False,
        "real_device_calibrated_claim_allowed": False,
        "experimental_validation_claim_allowed": False,
        "inverse_claim_allowed": False,
        "status": status,
        "allowed_claim": (
            "Qualified source-traceable Qiu-inspired conservative x-z solver E0 verification under reported and explicitly labeled prior quantities."
            if all_pass
            else "No positive M40 solver claim; the failed E0 boundary is retained."
        ),
        "forbidden_claims": [
            "Qiu real-device calibrated",
            "exact Qiu source-model reproduction",
            "experimental validation",
            "inverse identification",
            "PINN training or sensitivity fidelity",
            "gamma_eff relation",
            "full 2D hidden-field recovery",
        ],
        "forbidden_actions": prereg["forbidden_actions"],
        "outputs": config["outputs"],
    }
    _write_csv(config["outputs"]["mesh_convergence"], mesh_rows)
    _plot_geometry(config, nominal_mesh)
    _plot_fields(config, nominal_mesh, fields)
    _write_json(config["outputs"]["summary"], summary)
    _write_report(config, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mode", choices=("preregister", "formal"), required=True)
    args = parser.parse_args()
    config_path = _resolve(args.config)
    config = _load_config(config_path)
    result = (
        _preregistration(config_path, config)
        if args.mode == "preregister"
        else _formal(config)
    )
    print(json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
