"""Thermal, interface, energy-ledger, and RC tests for M40 E0."""

from __future__ import annotations

import numpy as np
import pytest

from pinnpcm.physics.qiu_vo2_device import QiuMesh
from pinnpcm.solvers.qiu_vo2_2d_fvm import (
    BoundaryFace,
    advance_thermal_implicit,
    implicit_rc_voltage,
    rc_residual_A,
    solve_steady_thermal,
)


def _thermal_mesh(*, nx: int = 20, nz: int = 3, layered: bool = True) -> QiuMesh:
    x_edges = np.linspace(0.0, 4.0e-6, nx + 1)
    z_edges = np.linspace(0.0, 0.9e-6, nz + 1)
    material = np.full((nz, nx), "al2o3", dtype="U12")
    if layered:
        material[:, nx // 2 :] = "vo2"
    mask = np.ones_like(material, dtype=bool)
    return QiuMesh(
        x_edges_m=x_edges,
        z_edges_m=z_edges,
        material=material,
        electrical_mask=np.zeros_like(mask),
        thermal_mask=mask,
        source_terminal_cells=(),
        ground_terminal_cells=(),
        depth_m=1.5e-6,
    )


def _thermal_boundaries(mesh: QiuMesh, hot_K: float, cold_K: float) -> list[BoundaryFace]:
    return [
        *[
            BoundaryFace("hot", iz, 0, "left", hot_K)
            for iz in range(mesh.shape[0])
        ],
        *[
            BoundaryFace("cold", iz, mesh.shape[1] - 1, "right", cold_K)
            for iz in range(mesh.shape[0])
        ],
    ]


def test_layered_thermal_analytic_limit_and_interface_jump() -> None:
    mesh = _thermal_mesh()
    k_left = 12.0
    k_right = 4.0
    k = np.where(mesh.material == "al2o3", k_left, k_right)
    interface_rth = 4.0e-8
    hot, cold = 370.0, 310.0
    result = solve_steady_thermal(
        mesh,
        k,
        _thermal_boundaries(mesh, hot, cold),
        {("al2o3", "vo2"): interface_rth},
    )

    area = (mesh.z_edges_m[-1] - mesh.z_edges_m[0]) * mesh.depth_m
    half_length = 0.5 * mesh.x_edges_m[-1]
    expected_heat = (hot - cold) / (
        half_length / (k_left * area)
        + interface_rth / area
        + half_length / (k_right * area)
    )
    assert result["boundary_heat_in_W"]["hot"] == pytest.approx(
        expected_heat, rel=2.0e-12
    )
    assert result["boundary_heat_in_W"]["cold"] == pytest.approx(
        -expected_heat, rel=2.0e-12
    )
    assert result["relative_heat_imbalance"] <= 1.0e-12

    left_ix = mesh.shape[1] // 2 - 1
    right_ix = left_ix + 1
    temperature = result["temperature_K"]
    bulk_half_drop = expected_heat * (
        0.5 * mesh.dx_m[left_ix] / (k_left * area)
        + 0.5 * mesh.dx_m[right_ix] / (k_right * area)
    )
    inferred_jump = float(
        np.mean(temperature[:, left_ix] - temperature[:, right_ix]) - bulk_half_drop
    )
    assert inferred_jump == pytest.approx(expected_heat * interface_rth / area, rel=2.0e-12)


@pytest.mark.parametrize(
    ("case_name", "heat_scale_W", "gate"),
    [
        ("smooth_window", 2.0e-4, 1.0e-4),
        ("switching_window", 2.0e-2, 1.0e-3),
    ],
)
def test_global_energy_ledger_closes_for_smooth_and_switching_windows(
    case_name: str, heat_scale_W: float, gate: float
) -> None:
    mesh = _thermal_mesh(nx=12, nz=4, layered=True)
    old = np.full(mesh.shape, 325.0)
    k = np.where(mesh.material == "al2o3", 24.0, 5.0)
    rho_cp = np.where(mesh.material == "al2o3", 3.0e6, 3.5e6)
    heat = np.zeros(mesh.shape)
    heat[mesh.material == "vo2"] = heat_scale_W / np.count_nonzero(
        mesh.material == "vo2"
    )

    result = advance_thermal_implicit(
        mesh,
        old,
        k,
        rho_cp,
        heat,
        dt_s=2.0e-10,
        ambient_temperature_K=325.0,
        bottom_conductance_W_K=1.0e-4,
        interface_resistance_m2K_W={("al2o3", "vo2"): 2.0e-8},
    )

    assert result["finite"] is True, case_name
    assert result["source_power_W"] == pytest.approx(heat_scale_W)
    reconstructed = result["storage_rate_W"] + result["boundary_outflow_W"]
    assert reconstructed == pytest.approx(result["source_power_W"], rel=gate)
    assert result["relative_energy_imbalance"] <= gate


def test_zero_source_uniform_temperature_is_an_exact_thermal_fixed_point() -> None:
    mesh = _thermal_mesh(nx=8, nz=2)
    ambient = 327.0
    result = advance_thermal_implicit(
        mesh,
        np.full(mesh.shape, ambient),
        np.full(mesh.shape, 7.0),
        np.full(mesh.shape, 2.4e6),
        np.zeros(mesh.shape),
        dt_s=1.0e-9,
        ambient_temperature_K=ambient,
        bottom_conductance_W_K=2.0e-5,
    )
    assert np.max(np.abs(result["temperature_K"] - ambient)) <= 1.0e-10
    assert abs(result["storage_rate_W"]) <= 1.0e-12
    assert abs(result["boundary_outflow_W"]) <= 1.0e-16


def test_implicit_rc_update_satisfies_the_declared_kcl_residual() -> None:
    old_voltage = 0.7
    input_voltage = 1.4
    load_resistance = 2.0e3
    capacitance = 3.0e-10
    conductance = 1.0 / 850.0
    dt_s = 2.0e-8
    new_voltage = implicit_rc_voltage(
        old_voltage,
        input_voltage,
        load_resistance,
        capacitance,
        conductance,
        dt_s,
    )
    residual = rc_residual_A(
        old_voltage,
        new_voltage,
        input_voltage,
        load_resistance,
        capacitance,
        conductance * new_voltage,
        dt_s,
    )
    scale = max(
        abs((input_voltage - new_voltage) / load_resistance),
        abs(conductance * new_voltage),
        1.0e-30,
    )
    assert abs(residual) / scale <= 1.0e-12
