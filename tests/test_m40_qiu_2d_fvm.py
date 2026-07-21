"""Conservative electrical FVM verification for the M40 Qiu namespace."""

from __future__ import annotations

import numpy as np
import pytest

from pinnpcm.physics.qiu_vo2_device import QiuGeometry, QiuMesh, build_qiu_domain_masks
from pinnpcm.solvers.qiu_vo2_2d_fvm import (
    BoundaryFace,
    qiu_terminal_faces,
    solve_electrical,
)


def _rect_mesh(
    *,
    nx: int = 12,
    nz: int = 4,
    length_m: float = 3.0e-6,
    height_m: float = 0.8e-6,
    depth_m: float = 2.0e-6,
    layered: bool = False,
) -> QiuMesh:
    x_edges = np.linspace(0.0, length_m, nx + 1)
    z_edges = np.linspace(0.0, height_m, nz + 1)
    material = np.full((nz, nx), "vo2", dtype="U12")
    if layered:
        material[:, nx // 2 :] = "ti"
    mask = np.ones_like(material, dtype=bool)
    return QiuMesh(
        x_edges_m=x_edges,
        z_edges_m=z_edges,
        material=material,
        electrical_mask=mask.copy(),
        thermal_mask=mask.copy(),
        source_terminal_cells=tuple((iz, 0) for iz in range(nz)),
        ground_terminal_cells=tuple((iz, nx - 1) for iz in range(nz)),
        depth_m=depth_m,
    )


def _side_terminals(mesh: QiuMesh, voltage_V: float = 1.0) -> list[BoundaryFace]:
    return [
        *[
            BoundaryFace("source", iz, 0, "left", voltage_V)
            for iz in range(mesh.shape[0])
        ],
        *[
            BoundaryFace("ground", iz, mesh.shape[1] - 1, "right", 0.0)
            for iz in range(mesh.shape[0])
        ],
    ]


def test_constant_coefficient_manufactured_solution_is_linear_and_conservative() -> None:
    mesh = _rect_mesh(nx=16, nz=5)
    sigma_value = 2.5e5
    voltage = 0.8
    result = solve_electrical(
        mesh,
        np.full(mesh.shape, sigma_value),
        _side_terminals(mesh, voltage),
    )

    exact = voltage * (1.0 - mesh.x_centers_m / mesh.x_edges_m[-1])
    assert np.max(np.abs(result["potential_V"] - exact[None, :])) <= 2.0e-12
    area = (mesh.z_edges_m[-1] - mesh.z_edges_m[0]) * mesh.depth_m
    expected_current = sigma_value * area * voltage / mesh.x_edges_m[-1]
    assert result["terminal_currents_A"]["source"] == pytest.approx(
        expected_current, rel=2.0e-12
    )
    assert result["terminal_currents_A"]["ground"] == pytest.approx(
        -expected_current, rel=2.0e-12
    )
    assert result["relative_current_imbalance"] <= 1.0e-12
    assert result["relative_electrical_power_imbalance"] <= 1.0e-12


def test_layered_electrical_limit_matches_series_resistance() -> None:
    mesh = _rect_mesh(nx=20, nz=3, layered=True)
    sigma_left = 1.7e5
    sigma_right = 4.2e6
    sigma = np.where(mesh.material == "vo2", sigma_left, sigma_right)
    voltage = 1.2
    result = solve_electrical(mesh, sigma, _side_terminals(mesh, voltage))

    area = (mesh.z_edges_m[-1] - mesh.z_edges_m[0]) * mesh.depth_m
    half_length = 0.5 * mesh.x_edges_m[-1]
    resistance = half_length / (sigma_left * area) + half_length / (sigma_right * area)
    expected_current = voltage / resistance
    assert result["terminal_currents_A"]["source"] == pytest.approx(
        expected_current, rel=2.0e-12
    )
    assert result["relative_current_imbalance"] <= 1.0e-12


def test_electrical_contact_jump_uses_area_specific_resistance_once() -> None:
    mesh = _rect_mesh(nx=20, nz=2, layered=True)
    sigma_left = 3.0e5
    sigma_right = 9.0e5
    sigma = np.where(mesh.material == "vo2", sigma_left, sigma_right)
    contact_resistance = 2.0e-12
    voltage = 0.6
    result = solve_electrical(
        mesh,
        sigma,
        _side_terminals(mesh, voltage),
        {("vo2", "ti"): contact_resistance},
    )

    area = (mesh.z_edges_m[-1] - mesh.z_edges_m[0]) * mesh.depth_m
    half_length = 0.5 * mesh.x_edges_m[-1]
    expected_current = voltage / (
        half_length / (sigma_left * area)
        + contact_resistance / area
        + half_length / (sigma_right * area)
    )
    records = result["interface_records"]
    assert len(records) == mesh.shape[0]
    assert result["terminal_currents_A"]["source"] == pytest.approx(
        expected_current, rel=2.0e-12
    )
    expected_density = expected_current / area
    for record in records:
        local_area = mesh.dz_m[record["cell_a"][0]] * mesh.depth_m
        local_current = abs(record["signed_current_A"])
        assert record["contact_voltage_jump_V"] == pytest.approx(
            local_current * contact_resistance / local_area,
            rel=2.0e-12,
        )
        assert local_current / local_area == pytest.approx(expected_density, rel=2.0e-12)


def test_substrate_conductivity_cannot_leak_without_explicit_mask_tamper() -> None:
    geometry = QiuGeometry(
        device_length_m=500.0e-9,
        device_width_m=100.0e-9,
        vo2_thickness_m=100.0e-9,
        ti_thickness_m=5.0e-9,
        au_thickness_m=100.0e-9,
        substrate_depth_m=1.0e-6,
        electrode_overlap_m=75.0e-9,
    )
    mesh = build_qiu_domain_masks(geometry, refinement=1)
    sigma_reference = np.full(mesh.shape, 1.0e5)
    sigma_tamper = sigma_reference.copy()
    sigma_tamper[mesh.material == "al2o3"] = 1.0e12
    terminals = qiu_terminal_faces(mesh, 1.0)

    reference = solve_electrical(mesh, sigma_reference, terminals)
    protected = solve_electrical(mesh, sigma_tamper, terminals)
    assert protected["terminal_currents_A"]["source"] == pytest.approx(
        reference["terminal_currents_A"]["source"], rel=0.0, abs=1.0e-18
    )
    assert np.allclose(
        protected["potential_V"][mesh.electrical_mask],
        reference["potential_V"][mesh.electrical_mask],
        rtol=0.0,
        atol=1.0e-14,
    )
    assert np.isnan(protected["potential_V"][mesh.material == "al2o3"]).all()

    leaked = solve_electrical(
        mesh,
        sigma_tamper,
        terminals,
        electrical_mask=mesh.thermal_mask,
    )
    # The finite contact/VO2 access resistance limits the tampered short, but
    # admitting Al2O3 still produces a large, readily detected current change.
    assert leaked["terminal_currents_A"]["source"] > 1.5 * protected["terminal_currents_A"]["source"]
    assert leaked["relative_current_imbalance"] <= 1.0e-6


def test_current_ledger_gate_is_individual_and_not_hidden_by_power_balance() -> None:
    mesh = _rect_mesh(nx=13, nz=4, layered=True)
    sigma = np.where(mesh.material == "vo2", 8.0e4, 2.0e6)
    result = solve_electrical(mesh, sigma, _side_terminals(mesh, 0.9))
    currents = result["terminal_currents_A"]

    assert set(currents) == {"source", "ground"}
    assert currents["source"] > 0.0 > currents["ground"]
    assert result["relative_current_imbalance"] <= 1.0e-6
    assert result["relative_electrical_power_imbalance"] <= 1.0e-12
