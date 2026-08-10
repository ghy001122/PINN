from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from pinnpcm.experiments.geostate_fasttrack import load_yaml, material_parameters
from pinnpcm.experiments.m1_self_consistent_imt_contraction import load_qiu_parameters
from pinnpcm.physics.m1_self_consistent_imt import (
    PRESCRIBED_STATE_MODE,
    SELF_CONSISTENT_MAJOR_BRANCH_MODE,
    M1SelfConsistentIMTProjection,
    compare_fixed_points,
    equilibrium_conductive_state,
    estimate_local_damped_map_singular_value,
    true_lookahead_defects,
)
from pinnpcm.physics.m1_torch_projection import M1TorchProjection


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = load_yaml(ROOT / "configs/q2_mf_geostate_mc_pinn_fasttrack_v1.yaml")
TASK_CONFIG = load_yaml(
    ROOT / "configs/q2_m1_self_consistent_imt_contraction_gate_v1.yaml"
)
QIU = load_qiu_parameters(TASK_CONFIG, ROOT)


def _m1_kwargs() -> dict:
    x = np.array([1.0e-8, 3.0e-8, 5.0e-8], dtype=float)
    y = np.array([1.0e-7, 3.0e-7], dtype=float)
    sheet = np.full((2, 3), 6.0e-7, dtype=float)
    left = np.zeros_like(sheet, dtype=bool)
    right = np.zeros_like(sheet, dtype=bool)
    left[:, 0] = True
    right[:, -1] = True
    form = BASE_CONFIG["physical_model"]["model_forms"]["M1"]
    return {
        "x_centers_m": x,
        "y_centers_m": y,
        "thickness_m": 1.0e-7,
        "sheet_thermal_conductance_W_K": sheet,
        "left_contact_mask": left,
        "right_contact_mask": right,
        "ambient_temperature_K": 325.0,
        "vertical_conductance_W_m2K": 1.0e7,
        "electrical_contact_resistance_ohm": form[
            "electrical_contact_resistance_ohm"
        ],
        "thermal_contact_resistance_m2K_W": form[
            "thermal_contact_resistance_m2K_W"
        ],
        "localized_sink_rectangle_m": {
            "x": [2.0e-8, 4.0e-8],
            "y": [0.0, 4.0e-7],
        },
        "material_params": material_parameters(BASE_CONFIG),
    }


def _operator(
    *,
    mode: str = SELF_CONSISTENT_MAJOR_BRANCH_MODE,
    lambda_j: float = 1.0,
) -> M1SelfConsistentIMTProjection:
    return M1SelfConsistentIMTProjection(
        **_m1_kwargs(),
        qiu_major_branch_parameters=QIU,
        constitutive_mode=mode,
        phase_width_multiplier=1.0,
        joule_feedback_multiplier=lambda_j,
        relaxation_alpha=0.35,
    )


def test_prescribed_state_historical_raw_projection_is_numerically_unchanged() -> None:
    historical = M1TorchProjection(**_m1_kwargs())
    versioned = _operator(mode=PRESCRIBED_STATE_MODE)
    temperature = torch.linspace(325.0, 341.0, 6, dtype=torch.float64).reshape(2, 3)
    reference = historical.projection(temperature, 1.15, 0.48, 1.5)
    candidate = versioned.raw_projection(temperature, 1.15, 0.48, 1.5)
    for name in (
        "conductivity_S_m",
        "potential_V",
        "temperature_K",
        "source_current_A",
        "total_joule_cell_W",
        "vertical_sink_W",
    ):
        torch.testing.assert_close(candidate[name], reference[name], rtol=0.0, atol=0.0)


def test_self_consistent_major_branches_are_monotone_bounded_and_ordered() -> None:
    temperature = torch.linspace(290.0, 380.0, 401, dtype=torch.float64)
    heating = equilibrium_conductive_state(temperature, 1.0, QIU)
    cooling = equilibrium_conductive_state(temperature, -1.0, QIU)
    assert bool(torch.all((heating >= 0.0) & (heating <= 1.0)))
    assert bool(torch.all((cooling >= 0.0) & (cooling <= 1.0)))
    assert bool(torch.all(torch.diff(heating) >= 0.0))
    assert bool(torch.all(torch.diff(cooling) >= 0.0))
    assert bool(torch.all(cooling >= heating))


def test_nominal_phase_width_and_centres_are_derived_from_qiu_source_contract() -> None:
    assert QIU.beta_per_K == pytest.approx(0.253, rel=0.0, abs=0.0)
    assert QIU.hysteresis_width_K == pytest.approx(7.193, rel=0.0, abs=0.0)
    assert QIU.critical_temperature_K == pytest.approx(332.8, rel=0.0, abs=0.0)
    assert QIU.T_c_up_K == pytest.approx(332.8 + 7.193 / 2.0)
    assert QIU.T_c_down_K == pytest.approx(332.8 - 7.193 / 2.0)
    assert QIU.nominal_transition_width_K == pytest.approx(1.0 / 0.253)
    assert QIU.source_contract_schema == "qiu_vo2_phase1_source_contract_v3"


def test_zero_voltage_self_consistent_projection_has_zero_electrical_heating() -> None:
    operator = _operator()
    ambient = torch.full((2, 3), 325.0, dtype=torch.float64)
    result = operator.projection(ambient, 0.0, 1.0, 1.5)
    torch.testing.assert_close(result["potential_V"], torch.zeros_like(ambient))
    torch.testing.assert_close(result["source_current_A"], torch.zeros((), dtype=torch.float64))
    torch.testing.assert_close(result["contact_joule_cell_W"], torch.zeros_like(ambient))
    # Dense thermal solves preserve the ambient state to float64 roundoff.
    torch.testing.assert_close(result["temperature_K"], ambient, rtol=0.0, atol=5.0e-12)


def test_cold_hot_fixed_point_uniqueness_comparator_applies_both_gates() -> None:
    cold = torch.full((2, 3), 335.0, dtype=torch.float64)
    near = cold + 1.0e-5
    accepted = compare_fixed_points(
        cold,
        near,
        1.0e-3,
        1.0e-3 * (1.0 + 5.0e-5),
        ambient_temperature_K=325.0,
    )
    rejected = compare_fixed_points(
        cold,
        cold + 1.0,
        1.0e-3,
        1.2e-3,
        ambient_temperature_K=325.0,
    )
    assert accepted.finite and accepted.unique
    assert not rejected.unique


def test_true_lookahead_defect_matches_task_definition() -> None:
    operator = _operator()
    temperature = torch.full((2, 3), 330.0, dtype=torch.float64)
    diagnostics = true_lookahead_defects(operator, temperature, 1.15, 1.0, 0.0)
    explicit = operator.projection(temperature, 1.15, 1.0, 0.0)["temperature_K"]
    expected = torch.linalg.vector_norm(explicit - temperature) / torch.linalg.vector_norm(
        explicit - operator.ambient_temperature_K
    )
    assert diagnostics.fixed_point_defect == pytest.approx(float(expected), rel=1.0e-14)
    assert np.isfinite(diagnostics.sigma_defect)


def test_eight_step_jvp_vjp_local_contraction_estimate_is_finite() -> None:
    operator = _operator()
    temperature = torch.full((2, 3), 330.0, dtype=torch.float64)
    estimate = estimate_local_damped_map_singular_value(
        operator,
        temperature,
        1.15,
        1.0,
        0.0,
        power_iterations=8,
    )
    assert estimate.method == "torch_autograd_jvp_vjp_power_iteration"
    assert estimate.power_iterations == 8
    assert estimate.finite
    assert np.isfinite(estimate.singular_value_estimate)


def test_lambda_j_one_uses_complete_internal_and_contact_joule_heating() -> None:
    operator = _operator(lambda_j=1.0)
    temperature = torch.full((2, 3), 332.0, dtype=torch.float64)
    result = operator.raw_projection(temperature, 1.15, -1.0, 1.5)
    torch.testing.assert_close(
        result["feedback_joule_cell_W"], result["total_joule_cell_W"], rtol=0.0, atol=0.0
    )
    torch.testing.assert_close(
        result["feedback_joule_cell_W"],
        result["internal_joule_cell_W"] + result["contact_joule_cell_W"],
        rtol=0.0,
        atol=0.0,
    )
    assert float(result["joule_feedback_multiplier"]) == 1.0
    torch.testing.assert_close(
        result["electrical_heat_sink_ledger_error"],
        result["feedback_heat_sink_ledger_error"],
    )
