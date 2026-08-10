from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from pinnpcm.experiments.geostate_fasttrack import (
    GeoStateCase,
    _solve_electrical_robin,
    _thermal_closure,
    _thermal_target,
    build_reference_context,
    load_yaml,
)
from pinnpcm.experiments.geostate_m1_compatibility import load_teacher_cases
from pinnpcm.experiments.m1_latent_projection_mve import (
    build_latent_model,
    build_projection_operator,
    fit_train_only_pod,
    normalized_mu,
    physical_parameters,
    split_case_ids,
    unroll_two_projections,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_yaml(ROOT / "configs/q2_m1_latent_solver_projected_pinn_mve_v1.yaml")
BASE_CONFIG = load_yaml(ROOT / CONFIG["reference"]["config"])
CONTEXT = build_reference_context(BASE_CONFIG, ROOT)
CASES = load_teacher_cases(ROOT / CONFIG["reference"]["data_root"])
CASE_BY_ID = {case.case_id: case for case in CASES}
SPLIT = split_case_ids(CASES, CONFIG)


def _operator():
    return build_projection_operator(CONTEXT, BASE_CONFIG)


def _pod():
    return fit_train_only_pod(
        {case_id: CASE_BY_ID[case_id].temperature_K for case_id in SPLIT["train"]},
        SPLIT["train"],
        ambient_temperature_K=CONTEXT.ambient_temperature_K,
        cumulative_energy_target=float(CONFIG["pod"]["cumulative_energy_target"]),
        rank_cap=int(CONFIG["pod"]["rank_cap"]),
        training_sample_rank_cap=int(CONFIG["pod"]["training_sample_rank_cap"]),
    )


def test_torch_m1_electrical_constant_conductivity_matches_existing_operator() -> None:
    operator = _operator()
    temperature = torch.full(
        (operator.ny, operator.nx), CONTEXT.ambient_temperature_K, dtype=torch.float64
    )
    state = 0.48
    voltage = 1.15
    sigma = operator.conductivity(temperature, state).detach().cpu().numpy()
    expected = _solve_electrical_robin(
        CONTEXT,
        sigma,
        voltage,
        BASE_CONFIG["physical_model"]["model_forms"]["M1"][
            "electrical_contact_resistance_ohm"
        ],
    )
    actual = operator.electrical(temperature, voltage, state)
    np.testing.assert_allclose(actual["potential_V"].detach(), expected["potential_V"], rtol=1e-12, atol=1e-14)
    assert np.isclose(float(actual["source_current_A"]), expected["source_current_A"], rtol=1e-12)


def test_torch_m1_thermal_contact_and_sink_matrix_matches_existing_operator() -> None:
    operator = _operator()
    case = GeoStateCase(
        case_id="manufactured",
        branch_label="heating-conditioned",
        branch_value=1.0,
        device_voltage_V=1.15,
        state_coordinate=0.48,
        thermal_condition="localized-sink",
        sink_amplitude=1.5,
    )
    form = BASE_CONFIG["physical_model"]["model_forms"]["M1"]
    closure = _thermal_closure(
        CONTEXT, "M1", case, form["thermal_contact_resistance_m2K_W"]
    )
    joule = np.linspace(1.0e-6, 2.0e-6, operator.cell_count).reshape(operator.ny, operator.nx)
    expected, _ = _thermal_target(CONTEXT, "M1", closure, joule)
    actual = operator.thermal(torch.as_tensor(joule, dtype=torch.float64), case.sink_amplitude)
    np.testing.assert_allclose(actual["temperature_K"].detach(), expected, rtol=1e-12, atol=1e-11)


def test_zero_voltage_projection_is_exact() -> None:
    operator = _operator()
    temperature = torch.full(
        (operator.ny, operator.nx), CONTEXT.ambient_temperature_K, dtype=torch.float64
    )
    result = operator.projection(temperature, 0.0, 0.5, 1.5)
    assert torch.count_nonzero(result["potential_V"]).item() == 0
    assert torch.count_nonzero(result["electrical_x_face_current_A"]).item() == 0
    assert torch.count_nonzero(result["contact_joule_cell_W"]).item() == 0
    assert torch.max(torch.abs(result["temperature_K"] - CONTEXT.ambient_temperature_K)) < 1.0e-11


def test_reference_temperature_is_a_fixed_point_of_projection() -> None:
    operator = _operator()
    case = CASE_BY_ID["heating_near-transition_localized-sink"]
    temperature = torch.as_tensor(case.temperature_K, dtype=torch.float64)
    result = operator.projection(
        temperature, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
    )
    rise_norm = torch.linalg.vector_norm(temperature - CONTEXT.ambient_temperature_K)
    defect = torch.linalg.vector_norm(result["temperature_K"] - temperature) / rise_norm
    assert float(defect) <= float(CONFIG["operator_parity"]["fixed_point_map_defect_max"])
    np.testing.assert_allclose(result["potential_V"].detach(), case.potential_V, rtol=1e-11, atol=1e-13)


def test_autograd_crosses_electrical_and_thermal_dense_solves() -> None:
    operator = _operator()
    case = CASE_BY_ID["heating_low_nominal"]
    temperature = torch.as_tensor(case.temperature_K, dtype=torch.float64).clone().requires_grad_(True)
    result = operator.projection(
        temperature, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
    )
    objective = result["temperature_K"].mean() + result["potential_V"].mean()
    objective.backward()
    assert temperature.grad is not None
    assert torch.isfinite(temperature.grad).all()
    assert float(torch.linalg.vector_norm(temperature.grad)) > 0.0


def test_pod_fit_is_strictly_train_only() -> None:
    pod = _pod()
    assert pod.train_case_ids == tuple(sorted(SPLIT["train"]))
    assert pod.rank == 2
    leaked = {case_id: CASE_BY_ID[case_id].temperature_K for case_id in SPLIT["train"]}
    leaked[SPLIT["validation"][0]] = CASE_BY_ID[SPLIT["validation"][0]].temperature_K
    with pytest.raises(ValueError, match="exactly the frozen train cases"):
        fit_train_only_pod(
            leaked,
            SPLIT["train"],
            ambient_temperature_K=CONTEXT.ambient_temperature_K,
            cumulative_energy_target=0.999,
            rank_cap=6,
            training_sample_rank_cap=8,
        )


def test_latent_k0_k1_k2_outputs_are_finite() -> None:
    torch.manual_seed(int(CONFIG["model"]["seed"]))
    operator = _operator()
    pod = _pod()
    model = build_latent_model(pod, CONFIG)
    cases = [CASE_BY_ID[SPLIT["train"][0]], CASE_BY_ID[SPLIT["train"][1]]]
    mu = normalized_mu(cases, CONFIG)
    voltage, state, sink = physical_parameters(cases)
    temperature0, first, second = unroll_two_projections(
        model, operator, mu, voltage, state, sink
    )
    assert torch.isfinite(temperature0).all()
    assert torch.isfinite(first["temperature_K"]).all()
    assert torch.isfinite(second["temperature_K"]).all()
    assert torch.isfinite(second["potential_V"]).all()
