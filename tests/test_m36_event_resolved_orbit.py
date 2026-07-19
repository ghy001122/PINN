"""Behavioral tests for the preregistered M36 numerical protocol."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.external_data.vo2_orbit_convergence import convergence_loglog_slope
from pinnpcm.external_data.vo2_orbit_fit import regime_feature_vector
from pinnpcm.physics.vo2_event_resolved import (
    event_sequence_signature,
    simulate_event_resolved_si,
    simulate_source_compatible_family_member,
)
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


CONFIG_PATH = Path("configs/m36_event_resolved_orbit_convergence.yaml")


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _params() -> VO2ThermalNeuristorParameters:
    source = yaml.safe_load(
        Path("configs/vo2_d0a_exact_source_v2.yaml").read_text(encoding="utf-8")
    )
    return VO2ThermalNeuristorParameters.from_config(source)


def test_m36_voltage_roles_steps_and_sealed_boundary_are_exact() -> None:
    config = _config()
    curves = config["data"]["open_voltage_curves"]
    assert [float(item["voltage_V"]) for item in curves] == [9.0, 11.0, 15.0, 17.0]
    assert [item["regime"] for item in curves] == [
        "static",
        "oscillatory",
        "oscillatory",
        "static",
    ]
    assert config["fixed_step_family"]["dt_values_s"] == [
        2.5e-9,
        1.25e-9,
        6.25e-10,
        3.125e-10,
    ]
    assert config["independent_reference"]["methods"] == ["DOP853", "Radau"]
    assert config["data"]["withheld_13v"]["numeric_access"] == "forbidden"
    assert config["data"]["withheld_13v"]["extracted_path"] is None
    assert all(
        "13v" not in Path(item["path"]).name.casefold().replace("_", "")
        for item in curves
    )


def test_continuous_and_sampled_event_semantics_are_not_mislabeled_as_identical() -> None:
    source = _config()["source_model"]
    assert source["semantics_are_identical"] is False
    assert source["discrete_semantics_name"] != source["continuous_semantics_name"]
    assert source["shared_physical_rhs"] is True
    assert len(source["source_event_order"]) == 4
    assert len(source["continuous_event_order"]) == 6


def test_dop853_and_radau_short_branch_reference_is_finite_and_consistent() -> None:
    config = _config()
    times = np.linspace(0.0, 2.0e-6, 401)
    dop = simulate_event_resolved_si(
        _params(),
        input_voltage_V=9.0,
        evaluation_times_s=times,
        method="DOP853",
        reference_config=config["independent_reference"],
    )
    radau = simulate_event_resolved_si(
        _params(),
        input_voltage_V=9.0,
        evaluation_times_s=times,
        method="Radau",
        reference_config=config["independent_reference"],
    )
    assert np.isfinite(dop.trace.current_A).all()
    assert np.isfinite(radau.trace.current_A).all()
    assert np.max(np.abs(dop.trace.voltage_V - radau.trace.voltage_V)) < 1.0e-6
    assert np.max(np.abs(dop.trace.temperature_K - radau.trace.temperature_K)) < 1.0e-4
    assert event_sequence_signature(dop.event_records) == event_sequence_signature(
        radau.event_records
    )
    assert dop.event_semantics == radau.event_semantics


def test_source_family_member_remains_explicitly_separate() -> None:
    result = simulate_source_compatible_family_member(
        _params(), input_voltage_V=9.0, t_max_s=2.0e-7, dt_s=2.5e-9
    )
    assert result.method == "explicit_Euler"
    assert result.event_semantics == "source_compatible_threshold_sampled_explicit_euler"
    assert result.trace.source_kind == "repository_si_solver"
    assert result.solver_statistics["steps"] == result.trace.time_s.size


def test_regime_feature_vectors_are_fixed_dimensional_and_finite() -> None:
    config = _config()
    time_s = np.linspace(0.0, 1.0e-5, 1000)
    static = {
        "time_s": time_s,
        "current_A": np.full_like(time_s, 2.0e-5),
        "device_voltage_V": np.full_like(time_s, 1.0),
    }
    vector = regime_feature_vector(
        static,
        regime="static",
        event_config=config["event_metrics"],
        current_noise_A=1.0e-6,
        voltage_noise_V=1.0e-3,
    )
    assert vector.shape == (68,)
    assert np.isfinite(vector).all()


def test_convergence_slope_has_expected_sign() -> None:
    dt = [2.5e-9, 1.25e-9, 6.25e-10, 3.125e-10]
    first_order_errors = [8.0, 4.0, 2.0, 1.0]
    assert convergence_loglog_slope(dt, first_order_errors) == pytest.approx(1.0)


def test_schema_and_claim_boundary_forbid_rank_and_validation_overclaims() -> None:
    config = _config()
    schema = json.loads(
        Path("docs/schemas/m36_event_resolved_orbit_evidence_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["sealed_13v_access"]["const"] is False
    assert config["conditional_jacobian"][
        "reversible_coordinate_transform_rank_increase_claim"
    ] == "forbidden"
    forbidden = set(config["claim_boundary"]["forbidden"])
    assert "independent_external_validation" in forbidden
    assert "trained_PINN_claim" in forbidden
    assert "world_first" in forbidden
