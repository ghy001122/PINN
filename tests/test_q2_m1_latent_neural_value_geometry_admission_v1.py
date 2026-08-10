from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from pinnpcm.experiments.geostate_fasttrack import build_reference_context, load_yaml
from pinnpcm.experiments.m1_latent_geometry_admission import (
    build_geometry_cases,
    build_geometry_context,
    build_geometry_model,
    build_projection_operator,
    fit_input_normalization,
    fit_ridge_latent,
    normalize_mu,
    ridge_coefficients,
    true_lookahead_defects,
)
from pinnpcm.experiments.m1_latent_projection_mve import fit_train_only_pod


ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_yaml(
    ROOT / "configs/q2_m1_latent_neural_value_geometry_admission_v1.yaml"
)
BASE_CONFIG = load_yaml(ROOT / CONFIG["reference"]["config"])
CASES = build_geometry_cases(CONFIG)
TRAIN_CASES = sorted(
    (case for case in CASES if case.split == "train"), key=lambda case: case.case_id
)


def _synthetic_pod():
    ny = int(CONFIG["reference"]["production_grid"]["ny"])
    nx = int(CONFIG["reference"]["production_grid"]["nx"])
    yy, xx = np.meshgrid(
        np.linspace(-1.0, 1.0, ny), np.linspace(-1.0, 1.0, nx), indexing="ij"
    )
    fields = {}
    for index, case in enumerate(TRAIN_CASES):
        rise = (
            2.0
            + 0.04 * index
            + (0.2 + 0.01 * index) * xx
            + (0.1 - 0.002 * index) * yy
            + 0.03 * case.branch_value * xx * yy
        )
        fields[case.case_id] = 325.0 + rise
    return fit_train_only_pod(
        fields,
        [case.case_id for case in TRAIN_CASES],
        ambient_temperature_K=325.0,
        cumulative_energy_target=0.999,
        rank_cap=8,
        training_sample_rank_cap=8,
    ), fields


def test_contact_masks_and_thermal_sheet_fields_change_for_all_geometries() -> None:
    contexts = {
        overlap: build_geometry_context(BASE_CONFIG, ROOT, overlap)
        for overlap in (10.0, 20.0, 30.0)
    }
    assert [int(np.sum(contexts[value].grid.contact_mask)) for value in contexts] == [
        50,
        100,
        150,
    ]
    assert not np.array_equal(
        contexts[10.0].thermal_fields.sheet_thermal_conductance_W_K,
        contexts[20.0].thermal_fields.sheet_thermal_conductance_W_K,
    )
    assert not np.array_equal(
        contexts[20.0].thermal_fields.sheet_thermal_conductance_W_K,
        contexts[30.0].thermal_fields.sheet_thermal_conductance_W_K,
    )


def test_twenty_nm_operator_preserves_pr39_projection_parity() -> None:
    old_context = build_reference_context(BASE_CONFIG, ROOT)
    new_context = build_geometry_context(BASE_CONFIG, ROOT, 20.0)
    old_operator = build_projection_operator(old_context, BASE_CONFIG)
    new_operator = build_projection_operator(new_context, BASE_CONFIG)
    np.testing.assert_array_equal(old_context.grid.contact_mask, new_context.grid.contact_mask)
    np.testing.assert_allclose(
        old_context.thermal_fields.sheet_thermal_conductance_W_K,
        new_context.thermal_fields.sheet_thermal_conductance_W_K,
        rtol=0.0,
        atol=0.0,
    )
    temperature = torch.linspace(
        325.0, 340.0, old_operator.cell_count, dtype=torch.float64
    ).reshape(
        old_operator.ny, old_operator.nx
    )
    old = old_operator.projection(temperature, 1.15, 0.48, 1.5)
    new = new_operator.projection(temperature, 1.15, 0.48, 1.5)
    for name in ("temperature_K", "potential_V", "source_current_A"):
        torch.testing.assert_close(old[name], new[name], rtol=0.0, atol=0.0)


def test_true_lookahead_defect_definition_is_identical_for_a1_a2_n1_n2() -> None:
    operator = build_projection_operator(
        build_geometry_context(BASE_CONFIG, ROOT, 20.0), BASE_CONFIG
    )
    case = next(case for case in CASES if case.case_id == "g020nm_heating_near-transition_localized-sink")
    cold = operator.cold_initial_temperature(case.device_voltage_V, case.state_coordinate)[0]
    a1 = operator.projection(cold, case.device_voltage_V, case.state_coordinate, case.sink_amplitude)
    a2 = operator.projection(a1["temperature_K"], case.device_voltage_V, case.state_coordinate, case.sink_amplitude)
    pod, _ = _synthetic_pod()
    normalization = fit_input_normalization(TRAIN_CASES, pod.train_case_ids)
    model = build_geometry_model(pod, CONFIG)
    n0 = model.initial_temperature(normalize_mu([case], normalization), operator.ny, operator.nx)[0]
    n1 = operator.projection(n0, case.device_voltage_V, case.state_coordinate, case.sink_amplitude)
    n2 = operator.projection(n1["temperature_K"], case.device_voltage_V, case.state_coordinate, case.sink_amplitude)
    for temperature in (
        a1["temperature_K"],
        a2["temperature_K"],
        n1["temperature_K"],
        n2["temperature_K"],
    ):
        fixed, sigma, look = true_lookahead_defects(operator, temperature, case)
        expected_fixed = float(
            torch.linalg.vector_norm(look["temperature_K"] - temperature)
            / torch.linalg.vector_norm(look["temperature_K"] - operator.ambient_temperature_K)
        )
        sigma_now = operator.conductivity(temperature, case.state_coordinate)
        sigma_look = operator.conductivity(look["temperature_K"], case.state_coordinate)
        expected_sigma = float(
            torch.linalg.vector_norm(sigma_look - sigma_now)
            / torch.linalg.vector_norm(sigma_look)
        )
        assert fixed == pytest.approx(expected_fixed, rel=1.0e-14)
        assert sigma == pytest.approx(expected_sigma, rel=1.0e-14)


def test_geometry_pod_fit_rejects_validation_or_test_leakage() -> None:
    _, fields = _synthetic_pod()
    leaked = dict(fields)
    validation = next(case for case in CASES if case.split == "validation")
    leaked[validation.case_id] = np.full((25, 10), 330.0)
    with pytest.raises(ValueError, match="exactly the frozen train cases"):
        fit_train_only_pod(
            leaked,
            [case.case_id for case in TRAIN_CASES],
            ambient_temperature_K=325.0,
            cumulative_energy_target=0.999,
            rank_cap=8,
            training_sample_rank_cap=8,
        )


def test_closed_form_ridge_predictor_is_finite() -> None:
    pod, _ = _synthetic_pod()
    normalization = fit_input_normalization(TRAIN_CASES, pod.train_case_ids)
    ridge = fit_ridge_latent(
        cases=TRAIN_CASES,
        pod=pod,
        normalization=normalization,
        regularization_lambda=1.0e-8,
    )
    prediction = ridge_coefficients(CASES, ridge, normalization)
    assert prediction.shape == (36, pod.rank)
    assert torch.isfinite(prediction).all()


def test_neural_n1_n2_forward_and_autograd_are_finite() -> None:
    pod, _ = _synthetic_pod()
    normalization = fit_input_normalization(TRAIN_CASES, pod.train_case_ids)
    model = build_geometry_model(pod, CONFIG)
    case = TRAIN_CASES[0]
    operator = build_projection_operator(
        build_geometry_context(BASE_CONFIG, ROOT, case.contact_overlap_nm), BASE_CONFIG
    )
    temperature0 = model.initial_temperature(
        normalize_mu([case], normalization), operator.ny, operator.nx
    )
    n1 = operator.projection(
        temperature0, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
    )
    n2 = operator.projection(
        n1["temperature_K"], case.device_voltage_V, case.state_coordinate, case.sink_amplitude
    )
    objective = n1["potential_V"].mean() + n2["temperature_K"].mean()
    objective.backward()
    gradients = [parameter.grad for parameter in model.parameters()]
    assert all(gradient is not None for gradient in gradients)
    assert all(torch.isfinite(gradient).all() for gradient in gradients if gradient is not None)
    assert torch.isfinite(n1["temperature_K"]).all()
    assert torch.isfinite(n2["potential_V"]).all()


def test_one_geometry_projection_hard_closes_m1_ledgers() -> None:
    case = next(case for case in CASES if case.case_id == "g010nm_heating_high_localized-sink")
    operator = build_projection_operator(
        build_geometry_context(BASE_CONFIG, ROOT, 10.0), BASE_CONFIG
    )
    initial = operator.cold_initial_temperature(case.device_voltage_V, case.state_coordinate)[0]
    projected = operator.projection(
        initial, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
    )
    assert float(projected["terminal_electrical_heat_ledger_error"]) <= 1.0e-12
    assert float(projected["electrical_heat_sink_ledger_error"]) <= 1.0e-10
