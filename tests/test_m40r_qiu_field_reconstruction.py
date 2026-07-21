"""Behavioral tests for M40R conservative electric-field reconstruction."""
from __future__ import annotations

import numpy as np
import pytest

from pinnpcm.physics.qiu_vo2_device import QiuMesh
from pinnpcm.solvers.m40r_qiu_e0_repair import (
    reconstruct_conservative_electric_field,
)
from pinnpcm.solvers.qiu_vo2_2d_fvm import BoundaryFace, solve_electrical


def _mesh(x_edges: np.ndarray, z_edges: np.ndarray) -> QiuMesh:
    material = np.full((len(z_edges) - 1, len(x_edges) - 1), "vo2", dtype="U12")
    mask = np.ones_like(material, dtype=bool)
    return QiuMesh(
        x_edges_m=np.asarray(x_edges),
        z_edges_m=np.asarray(z_edges),
        material=material,
        electrical_mask=mask,
        thermal_mask=mask,
        source_terminal_cells=(),
        ground_terminal_cells=(),
        depth_m=7.0e-7,
    )


def _side_terminals(mesh: QiuMesh, voltage: float) -> list[BoundaryFace]:
    return [
        *[BoundaryFace("source", iz, 0, "left", voltage) for iz in range(mesh.shape[0])],
        *[
            BoundaryFace("ground", iz, mesh.shape[1] - 1, "right", 0.0)
            for iz in range(mesh.shape[0])
        ],
    ]


def test_linear_field_and_terminal_flux_are_exact() -> None:
    mesh = _mesh(np.linspace(0.0, 2.0e-6, 17), np.linspace(0.0, 0.8e-6, 7))
    sigma = np.full(mesh.shape, 3.5e5)
    terminals = _side_terminals(mesh, 0.9)
    solved = solve_electrical(mesh, sigma, terminals)
    field = reconstruct_conservative_electric_field(
        mesh, solved["potential_V"], sigma, terminals
    )
    expected = 0.9 / 2.0e-6

    assert np.max(abs(field.ex_cell_V_m - expected)) <= 2.0e-8 * expected
    assert np.max(abs(field.ez_cell_V_m)) <= 1.0e-7
    assert field.terminal_currents_A["source"] == pytest.approx(
        solved["terminal_currents_A"]["source"], rel=2.0e-12
    )
    assert field.terminal_currents_A["ground"] == pytest.approx(
        solved["terminal_currents_A"]["ground"], rel=2.0e-12
    )


def test_quadratic_field_reconstruction_is_exact_on_nonuniform_interior() -> None:
    x_edges = np.array([0.0, 0.11, 0.29, 0.52, 0.78, 1.0]) * 1.0e-6
    z_edges = np.array([0.0, 0.13, 0.37, 0.66, 1.0]) * 0.7e-6
    mesh = _mesh(x_edges, z_edges)
    zz, xx = np.meshgrid(mesh.z_centers_m, mesh.x_centers_m, indexing="ij")
    ax, az = 1.7e11, -2.3e11
    potential = ax * xx**2 + az * zz**2
    sigma = np.full(mesh.shape, 4.0e4)
    field = reconstruct_conservative_electric_field(mesh, potential, sigma, [])
    interior = np.s_[1:-1, 1:-1]

    assert field.ex_cell_V_m[interior] == pytest.approx(
        -2.0 * ax * xx[interior], rel=2.0e-12, abs=1.0e-8
    )
    assert field.ez_cell_V_m[interior] == pytest.approx(
        -2.0 * az * zz[interior], rel=2.0e-12, abs=1.0e-8
    )


def test_insulating_zero_flux_faces_participate_in_boundary_reconstruction() -> None:
    mesh = _mesh(np.array([0.0, 1.0]), np.array([0.0, 0.5, 1.0]))
    sigma = np.full(mesh.shape, 2.0)
    potential = np.array([[1.0], [0.0]])
    field = reconstruct_conservative_electric_field(mesh, potential, sigma, [])

    assert field.jz_face_A_m2[:, 0] == pytest.approx([0.0, 4.0, 0.0])
    assert field.ez_cell_V_m[:, 0] == pytest.approx([1.0, 1.0])
    assert field.ex_cell_V_m[:, 0] == pytest.approx([0.0, 0.0])


def test_contact_face_current_is_continuous_but_bulk_fields_use_local_sigma() -> None:
    mesh = _mesh(np.linspace(0.0, 1.0e-6, 9), np.linspace(0.0, 0.4e-6, 3))
    mesh.material[:, 4:] = "ti"
    sigma = np.where(mesh.material == "vo2", 2.0e4, 8.0e4)
    terminals = _side_terminals(mesh, 1.0)
    contact = {("vo2", "ti"): 3.0e-10}
    solved = solve_electrical(mesh, sigma, terminals, contact)
    field = reconstruct_conservative_electric_field(
        mesh, solved["potential_V"], sigma, terminals, contact
    )
    interface_face = 4
    density = field.jx_face_A_m2[:, interface_face]

    assert np.all(np.isfinite(density))
    assert np.all(abs(density) > 0.0)
    left_bulk = field.ex_cell_V_m[:, interface_face - 1]
    right_bulk = field.ex_cell_V_m[:, interface_face]
    assert np.mean(abs(left_bulk)) > np.mean(abs(right_bulk))
    assert np.mean(abs(left_bulk)) / np.mean(abs(right_bulk)) == pytest.approx(
        4.0, rel=0.15
    )
