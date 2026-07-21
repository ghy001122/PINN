"""Behavioral tests for the source-constrained M40 Qiu device domain."""

from __future__ import annotations

from dataclasses import fields

import numpy as np
import pytest

from pinnpcm.physics.qiu_vo2_device import (
    QiuGeometry,
    QiuHysteresis,
    advance_history_state,
    build_qiu_domain_masks,
    conductivity_from_temperature_history,
    major_loop_targets,
)


def _geometry() -> QiuGeometry:
    return QiuGeometry(
        device_length_m=500.0e-9,
        device_width_m=100.0e-9,
        vo2_thickness_m=100.0e-9,
        ti_thickness_m=5.0e-9,
        au_thickness_m=100.0e-9,
        substrate_depth_m=1.0e-6,
        electrode_overlap_m=75.0e-9,
    )


def _hysteresis() -> QiuHysteresis:
    return QiuHysteresis(
        resistance_prefactor_ohm=2.5e-3,
        metallic_resistance_ohm=80.0,
        activation_temperature_K=3000.0,
        beta_per_K=0.35,
        loop_width_K=8.0,
        critical_temperature_K=340.0,
        proximity_gamma=0.2,
        dynamic_metallic_factor=1.0,
        history_relaxation_s=2.0e-7,
        direction_smoothing_K_per_s=1.0e5,
        explicit_contact_total_ohm=10.0,
    )


def test_material_masks_encode_thermal_only_substrate_and_coplanar_terminals() -> None:
    mesh = build_qiu_domain_masks(_geometry(), refinement=1)

    assert mesh.shape == (15, 10)
    assert set(np.unique(mesh.material)) == {"al2o3", "vo2", "ti", "au", "void"}
    assert np.all(mesh.thermal_mask[mesh.material == "al2o3"])
    assert not np.any(mesh.electrical_mask[mesh.material == "al2o3"])
    assert np.all(mesh.electrical_mask[np.isin(mesh.material, ["vo2", "ti", "au"])])
    assert not np.any(mesh.thermal_mask[mesh.material == "void"])
    assert not np.any(mesh.electrical_mask[mesh.material == "void"])

    assert len(mesh.source_terminal_cells) == 2
    assert len(mesh.ground_terminal_cells) == 2
    assert all(mesh.material[cell] == "au" for cell in mesh.source_terminal_cells)
    assert all(mesh.material[cell] == "au" for cell in mesh.ground_terminal_cells)
    assert {cell[0] for cell in mesh.source_terminal_cells + mesh.ground_terminal_cells} == {
        mesh.shape[0] - 1
    }
    assert not set(mesh.source_terminal_cells) & set(mesh.ground_terminal_cells)


def test_geometry_refinement_preserves_interfaces_and_physical_extent() -> None:
    geometry = _geometry()
    coarse = build_qiu_domain_masks(geometry, refinement=1)
    fine = build_qiu_domain_masks(geometry, refinement=3)

    assert fine.shape == tuple(3 * value for value in coarse.shape)
    assert coarse.x_edges_m[0] == fine.x_edges_m[0] == 0.0
    assert coarse.x_edges_m[-1] == pytest.approx(geometry.device_length_m)
    assert fine.x_edges_m[-1] == pytest.approx(geometry.device_length_m)
    expected_top = (
        geometry.vo2_thickness_m
        + geometry.ti_thickness_m
        + geometry.au_thickness_m
    )
    assert coarse.z_edges_m[0] == pytest.approx(-geometry.substrate_depth_m)
    assert coarse.z_edges_m[-1] == pytest.approx(expected_top)
    assert fine.z_edges_m[-1] == pytest.approx(expected_top)
    for interface in (0.0, geometry.vo2_thickness_m, geometry.vo2_thickness_m + geometry.ti_thickness_m):
        assert np.any(np.isclose(coarse.z_edges_m, interface, rtol=0.0, atol=1.0e-20))
        assert np.any(np.isclose(fine.z_edges_m, interface, rtol=0.0, atol=1.0e-20))


def test_geometry_rejects_nonphysical_or_unresolved_dimensions() -> None:
    values = {field.name: getattr(_geometry(), field.name) for field in fields(QiuGeometry)}
    values["substrate_depth_m"] = 0.0
    with pytest.raises(ValueError, match="positive"):
        QiuGeometry(**values).validate()

    values = {field.name: getattr(_geometry(), field.name) for field in fields(QiuGeometry)}
    values["electrode_overlap_m"] = 0.5 * values["device_length_m"]
    with pytest.raises(ValueError, match="overlap"):
        QiuGeometry(**values).validate()


def test_continuous_history_closure_is_bounded_directional_and_differentiable() -> None:
    hysteresis = _hysteresis()
    old_temperature = np.array([338.0, 342.0])
    old_history = np.array([0.8, 0.2])
    dt_s = 2.0e-8

    heating = advance_history_state(
        old_temperature,
        old_temperature + 1.0,
        old_history,
        dt_s,
        hysteresis,
    )
    cooling = advance_history_state(
        old_temperature,
        old_temperature - 1.0,
        old_history,
        dt_s,
        hysteresis,
    )
    assert np.all((0.0 <= heating) & (heating <= 1.0))
    assert np.all((0.0 <= cooling) & (cooling <= 1.0))

    major_heating, major_cooling = major_loop_targets(old_temperature, hysteresis)
    assert np.all(major_heating >= major_cooling)

    # A central derivative probes continuity through the smoothed direction switch.
    epsilon = 1.0e-7
    plus = advance_history_state(
        old_temperature,
        old_temperature + epsilon,
        old_history,
        dt_s,
        hysteresis,
    )
    minus = advance_history_state(
        old_temperature,
        old_temperature - epsilon,
        old_history,
        dt_s,
        hysteresis,
    )
    derivative = (plus - minus) / (2.0 * epsilon)
    assert np.isfinite(derivative).all()
    assert np.max(np.abs(plus - minus)) < 1.0e-5


def test_conductivity_is_a_constitutive_closure_not_an_independent_state() -> None:
    geometry = _geometry()
    hysteresis = _hysteresis()
    temperature = np.array([330.0, 350.0])
    insulating = conductivity_from_temperature_history(
        temperature, np.ones(2), geometry, hysteresis
    )
    metallic = conductivity_from_temperature_history(
        temperature, np.zeros(2), geometry, hysteresis
    )
    assert np.all(np.isfinite(insulating))
    assert np.all(insulating > 0.0)
    assert np.all(metallic > insulating)
