from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.solvers.m44_heterogeneous_3d_thermal import (
    AL2O3,
    INACTIVE,
    TI,
    VO2,
    HeterogeneousThermalGrid,
    assemble_heterogeneous_system,
    build_heterogeneous_grid,
    build_homogeneous_anchor_grid,
    build_layered_1d_grid,
    build_layered_top_source,
    build_source_vector,
    build_surface_anchor_source,
    independent_boundary_outflow_W,
    solve_steady,
    solve_transient,
    surface_source_face_mean_rise_K,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def config() -> dict[str, object]:
    return yaml.safe_load(
        (ROOT / "configs" / "m44_qiu_heterogeneous_3d_thermal.yaml").read_text(
            encoding="utf-8"
        )
    )


def _manual_grid(material: np.ndarray) -> HeterogeneousThermalGrid:
    nz, ny, nx = material.shape
    return HeterogeneousThermalGrid(
        x_edges_m=np.arange(nx + 1, dtype=float),
        y_edges_m=np.arange(ny + 1, dtype=float),
        z_edges_m=np.arange(nz + 1, dtype=float),
        material_id=material,
        mode="xz",
        mesh="test",
        domain="test",
        device_half_x_m=1.0,
        device_half_y_m=1.0,
        contact_start_x_m=0.5,
        symmetry_fraction=0.5,
    )


def test_interface_conductance_is_series_resistance(config: dict[str, object]) -> None:
    material = np.asarray([[[VO2]], [[TI]]], dtype=np.int8)
    grid = _manual_grid(material)
    resistance = 2.5e-8
    system = assemble_heterogeneous_system(
        config, grid, interface_resistance_m2K_W={(VO2, TI): resistance}
    )
    conductivity = {
        VO2: float(config["materials"]["vo2"]["thermal_conductivity_W_mK"]),
        TI: float(config["materials"]["ti"]["thermal_conductivity_W_mK"]),
    }
    expected = 1.0 / (
        0.5 / conductivity[VO2] + resistance + 0.5 / conductivity[TI]
    )
    matrix = system.conductance_W_K.toarray()
    assert -matrix[0, 1] == pytest.approx(expected, rel=2e-15)
    assert -matrix[1, 0] == pytest.approx(expected, rel=2e-15)


def test_active_void_face_is_adiabatic(config: dict[str, object]) -> None:
    material = np.asarray([[[VO2, INACTIVE]]], dtype=np.int8)
    grid = _manual_grid(material)
    system = assemble_heterogeneous_system(config, grid)
    assert system.active_flat_indices.size == 1
    assert system.conductance_W_K.shape == (1, 1)
    assert system.conductance_W_K[0, 0] == pytest.approx(0.0)
    assert system.boundary_conductance_W_K[0] == pytest.approx(0.0)


def test_material_faces_and_homogeneous_anchor_are_explicit(
    config: dict[str, object],
) -> None:
    heterogeneous = build_heterogeneous_grid(config, mesh="M1", domain="D2")
    assert heterogeneous.z_edges_m[0] < 0.0
    assert {AL2O3, VO2, TI}.issubset(set(np.unique(heterogeneous.material_id)))
    assert INACTIVE in np.unique(heterogeneous.material_id)
    assert np.any(
        np.isclose(
            heterogeneous.x_edges_m,
            heterogeneous.contact_start_x_m,
            rtol=0.0,
            atol=1.0e-20,
        )
    )
    anchor = build_homogeneous_anchor_grid(config, mesh="M1", domain="D2")
    assert anchor.z_edges_m[0] == pytest.approx(0.0)
    assert np.array_equal(np.unique(anchor.material_id), np.asarray([AL2O3]))


def test_equal_power_source_families_and_symmetry_normalisation(
    config: dict[str, object],
) -> None:
    full_power = float(config["geometry"]["full_power_W"])
    for mode, fraction in (("3d", 0.25), ("xz", 0.5)):
        grid = build_heterogeneous_grid(config, mesh="M1", domain="D2", mode=mode)
        system = assemble_heterogeneous_system(config, grid)
        supports = []
        for source_id in ("S_bulk", "S_contact", "S_mixed"):
            source, audit = build_source_vector(config, system, source_id)
            assert np.sum(source) == pytest.approx(full_power * fraction, rel=2e-15)
            assert audit["source_power_integration_relative_error"] <= 2e-15
            assert audit["source_geometry_integration_relative_error"] <= 2e-15
            assert audit["contact_support_face_aligned"]
            supports.append(int(audit["source_cell_count"]))
        assert supports[1] < supports[0]
        assert supports[2] == supports[0]


def test_surface_anchor_integrates_quarter_power(config: dict[str, object]) -> None:
    grid = build_homogeneous_anchor_grid(config, mesh="M1", domain="D2")
    system = assemble_heterogeneous_system(config, grid)
    source, audit = build_surface_anchor_source(config, system)
    assert np.sum(source) == pytest.approx(
        float(config["geometry"]["quarter_power_W"]), rel=2e-15
    )
    expected_area = 0.25 * (
        float(config["geometry"]["vo2_full_x_m"])
        * float(config["geometry"]["vo2_full_y_m"])
    )
    assert audit["surface_source_area_m2"] == pytest.approx(expected_area, rel=2e-15)


def test_surface_anchor_reports_face_not_cell_centre_mean(
    config: dict[str, object],
) -> None:
    grid = build_homogeneous_anchor_grid(config, mesh="M1", domain="D2")
    system = assemble_heterogeneous_system(config, grid)
    source, _ = build_surface_anchor_source(config, system)
    result = solve_steady(
        system, source, full_power_W=float(config["geometry"]["full_power_W"])
    )
    face = surface_source_face_mean_rise_K(
        system, result["theta_active_K"], source
    )
    assert face == pytest.approx(
        result["metrics"]["source_surface_face_mean_rise_K"], rel=2e-15
    )
    assert face > result["metrics"]["source_mean_rise_K"]


def test_layered_1d_limit_has_adiabatic_sides_and_full_power(
    config: dict[str, object],
) -> None:
    grid = build_layered_1d_grid(config, resolution="base")
    system = assemble_heterogeneous_system(config, grid)
    source, audit = build_layered_top_source(config, system)
    result = solve_steady(
        system, source, full_power_W=float(config["geometry"]["full_power_W"])
    )
    assert grid.mode == "layered1d" and grid.shape[1:] == (1, 1)
    assert np.sum(source) == pytest.approx(float(config["geometry"]["full_power_W"]))
    assert audit["source_geometry_integration_relative_error"] == 0.0
    assert result["ledger"]["normalized_power_imbalance"] <= 1e-10
    assert result["metrics"]["source_surface_face_Zth_K_W"] > 0.0


def test_steady_solution_is_linear_positive_and_conservative(
    config: dict[str, object],
) -> None:
    grid = build_heterogeneous_grid(config, mesh="M1", domain="D2")
    system = assemble_heterogeneous_system(config, grid)
    source, _ = build_source_vector(config, system, "S_bulk")
    full_power = float(config["geometry"]["full_power_W"])
    result = solve_steady(system, source, full_power_W=full_power)
    doubled = solve_steady(system, 2.0 * source, full_power_W=2.0 * full_power)
    assert result["finite"] and result["positive"]
    assert np.allclose(doubled["theta_active_K"], 2.0 * result["theta_active_K"], rtol=2e-12, atol=1e-14)
    assert result["ledger"]["normalized_power_imbalance"] <= 1e-10
    assert result["ledger"]["boundary_flux_relative_disagreement"] <= 1e-13
    assert result["metrics"]["vo2_mean_Zth_K_W"] > 0.0


def test_independent_boundary_ledger_detects_tampered_assembly_audit(
    config: dict[str, object],
) -> None:
    grid = build_heterogeneous_grid(config, mesh="M1", domain="D2")
    system = assemble_heterogeneous_system(config, grid)
    source, _ = build_source_vector(config, system, "S_contact")
    theta = solve_steady(
        system, source, full_power_W=float(config["geometry"]["full_power_W"])
    )["theta_active_K"]
    independent = independent_boundary_outflow_W(system, theta)
    assert independent == pytest.approx(
        float(np.dot(system.boundary_conductance_W_K, theta)), rel=1e-13
    )
    tampered = replace(
        system,
        boundary_conductance_W_K=0.5 * system.boundary_conductance_W_K,
    )
    assembled_tampered = float(np.dot(tampered.boundary_conductance_W_K, theta))
    independent_tampered = independent_boundary_outflow_W(tampered, theta)
    assert abs(independent_tampered - assembled_tampered) / independent_tampered > 0.49


def test_transient_is_finite_monotone_and_closes_discrete_energy(
    config: dict[str, object],
) -> None:
    grid = build_heterogeneous_grid(config, mesh="M1", domain="D2")
    system = assemble_heterogeneous_system(config, grid)
    source, _ = build_source_vector(config, system, "S_mixed")
    result = solve_transient(
        system,
        source,
        full_power_W=float(config["geometry"]["full_power_W"]),
        times_s=[1.0e-10, 3.0e-10, 1.0e-9],
        steps_per_interval=2,
    )
    zth = np.asarray(result["metrics"]["vo2_mean_Zth_K_W"])
    assert result["finite"] and result["positive"] and result["monotone_vo2_mean"]
    assert np.all(np.isfinite(zth)) and np.all(zth > 0.0) and np.all(np.diff(zth) >= 0.0)
    assert result["ledger"]["maximum_normalized_sensible_energy_imbalance"] <= 1e-10
    assert result["ledger"]["maximum_boundary_flux_relative_disagreement"] <= 1e-13
