from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from pinnpcm.experiments.geostate_fasttrack import load_yaml
from pinnpcm.experiments.m1_latent_projection_mve import fit_train_only_pod
from pinnpcm.experiments.m1_protocol_selected_equilibrium_manifold import rehydrate_protocol_runs
from pinnpcm.experiments.protocol_manifold_branch_aware_surrogate import (
    _build_all_operators,
    _headline_state_ids,
    _sample_split,
)
from pinnpcm.pinn.protocol_manifold_surrogate import (
    HistoryBlindLatentNet,
    ProtocolGatedLatentNet,
    ProtocolSingleHeadLatentNet,
    fit_degree2_ridge,
    fit_input_normalization,
    parameter_difference_fraction,
    predict_degree2_ridge,
    unknown_protocol_decision,
    validate_surrogate_schema,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_yaml(ROOT / "configs/q2_protocol_manifold_branch_aware_surrogate_mve_v1.yaml")


def _codec_kwargs(rank: int = 2) -> dict[str, object]:
    cells = 250
    basis = torch.zeros((rank, cells), dtype=torch.float64)
    basis[:, :rank] = torch.eye(rank, dtype=torch.float64)
    return {
        "pod_mean_y": torch.zeros(cells, dtype=torch.float64),
        "pod_basis": basis,
        "coefficient_center": torch.zeros(rank, dtype=torch.float64),
        "coefficient_scale": torch.ones(rank, dtype=torch.float64),
        "ambient_temperature_K": 325.0,
        "smooth_nonnegative_beta_K": 0.05,
    }


@pytest.fixture(scope="module")
def operators():
    return _build_all_operators(CONFIG, ROOT)


def test_factorial_context_masks_and_thermal_fields_are_physical(operators) -> None:
    assert set(operators) == {"G0", "G1", "G2", "G3"}
    covered = {
        key: int(operator.left_contact_mask.sum() + operator.right_contact_mask.sum())
        for key, operator in operators.items()
    }
    assert covered == {"G0": 100, "G1": 150, "G2": 100, "G3": 150}
    torch.testing.assert_close(
        operators["G0"].thermal_x_face_conductance_W_K,
        operators["G2"].thermal_x_face_conductance_W_K,
    )
    assert not torch.equal(
        operators["G0"].thermal_x_face_conductance_W_K,
        operators["G3"].thermal_x_face_conductance_W_K,
    )
    probe = torch.full((25, 10), 330.0, dtype=torch.float64)
    nominal = operators["G0"].vertical_conductance(0.0, like=probe, batch=1)
    localized = operators["G2"].vertical_conductance(1.5, like=probe, batch=1)
    assert torch.any(localized > nominal)


def test_frozen_g0_g1_protocol_artifacts_read_without_reexecution() -> None:
    old_config = load_yaml(ROOT / CONFIG["reference"]["historical_protocol_config"])
    runs = rehydrate_protocol_runs(
        config=old_config,
        processed_root=ROOT / CONFIG["reference"]["historical_processed_root"],
    )
    assert {run.spec.context_id for run in runs} == {"G0", "G1"}
    assert len(runs) == 4
    assert sum(len(run.coarse_points) for run in runs) == 132
    assert all(run.completed and all(point.valid for point in run.coarse_points) for run in runs)


def test_split_excludes_g1_from_every_fit_role() -> None:
    old_config = load_yaml(ROOT / CONFIG["reference"]["historical_protocol_config"])
    runs = rehydrate_protocol_runs(
        config=old_config,
        processed_root=ROOT / CONFIG["reference"]["historical_processed_root"],
    )
    headline = _headline_state_ids(CONFIG, ROOT)
    g1_point = next(point for run in runs if run.spec.context_id == "G1" for point in run.coarse_points)
    split, fit, full, _ = _sample_split(
        g1_point, context_id="G1", validation_indices={6, 14, 22, 30}, headline_ids=headline
    )
    assert split.startswith("test_") and not fit and full
    g0_point = next(point for run in runs if run.spec.context_id == "G0" for point in run.coarse_points)
    validation_point = replace(g0_point, sequence_index=6)
    assert _sample_split(
        validation_point,
        context_id="G0",
        validation_indices={6, 14, 22, 30},
        headline_ids=headline,
    )[0] == "validation"


def test_train_only_pod_and_normalization_reject_holdout_leakage() -> None:
    train_fields = {
        f"train_{index}": np.full((25, 10), 325.0 + index, dtype=np.float64)
        for index in range(1, 5)
    }
    pod = fit_train_only_pod(
        train_fields,
        tuple(train_fields),
        ambient_temperature_K=325.0,
        cumulative_energy_target=0.999,
        rank_cap=8,
        training_sample_rank_cap=8,
    )
    assert set(pod.train_case_ids) == set(train_fields)
    with pytest.raises(ValueError, match="exactly the frozen train cases"):
        fit_train_only_pod(
            {**train_fields, "G1_holdout": np.full((25, 10), 330.0)},
            tuple(train_fields),
            ambient_temperature_K=325.0,
            cumulative_energy_target=0.999,
            rank_cap=8,
            training_sample_rank_cap=8,
        )
    with pytest.raises(ValueError, match="holdout"):
        fit_input_normalization(
            np.ones((2, 3)),
            ["train", "G1_holdout"],
            feature_names=CONFIG["network"]["history_blind_input_order"],
            forbidden_sample_ids=["G1_holdout"],
        )


def test_fixed_degree2_ridge_predictor_is_finite() -> None:
    rng = np.random.default_rng(20260809)
    inputs = rng.normal(size=(32, 5))
    targets = rng.normal(size=(32, 3))
    ridge = fit_degree2_ridge(inputs, targets, regularization_lambda=1.0e-8)
    prediction = predict_degree2_ridge(ridge, inputs[:4])
    assert prediction.shape == (4, 3)
    assert np.isfinite(prediction).all()
    assert ridge.weights.shape[0] == 21


def test_explicit_direction_hard_gate_selects_branch_head() -> None:
    model = ProtocolGatedLatentNet(**_codec_kwargs())
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.heating_head.bias.fill_(2.0)
        model.cooling_head.bias.fill_(-3.0)
    inputs = torch.zeros((2, 5), dtype=torch.float64)
    output = model(inputs, torch.tensor([1.0, -1.0], dtype=torch.float64))
    torch.testing.assert_close(output[0], torch.full((2,), 2.0, dtype=torch.float64))
    torch.testing.assert_close(output[1], torch.full((2,), -3.0, dtype=torch.float64))
    single = ProtocolSingleHeadLatentNet(**_codec_kwargs())
    assert parameter_difference_fraction(single, model) <= 0.05


def test_root_labels_and_solution_labels_are_forbidden() -> None:
    validate_surrogate_schema(CONFIG["network"]["protocol_input_order"], mode="G")
    validate_surrogate_schema(CONFIG["network"]["history_blind_input_order"], mode="H")
    for forbidden in ("root_id", "cold_label", "hot_solution_label"):
        with pytest.raises(ValueError, match="forbidden"):
            validate_surrogate_schema(
                ["device_voltage_V", "ramp_direction", "start_voltage_V", "contact_overlap_nm", forbidden],
                mode="G",
            )


def test_unknown_protocol_output_returns_set_without_averaging() -> None:
    decision = unknown_protocol_decision(
        heating_candidate={"field": "heating"},
        cooling_candidate={"field": "cooling"},
        predicted_current_separation=0.2,
        predicted_temperature_separation=0.05,
        ambiguity_threshold=0.1,
    )
    assert decision.status == "AMBIGUOUS_PROTOCOL"
    assert decision.unique_candidate is None
    assert decision.heating_candidate != decision.cooling_candidate
    assert not decision.candidate_averaging_used


def test_one_two_projection_and_neural_autograd_are_finite(operators) -> None:
    operator = operators["G0"]
    model = HistoryBlindLatentNet(**_codec_kwargs())
    inputs = torch.zeros((1, 3), dtype=torch.float64, requires_grad=True)
    temperature0 = model.decode_temperature(model(inputs), ny=25, nx=10)[0]
    one = operator.projection(temperature0, 1.0, 1.0, 0.0)
    two = operator.projection(one["temperature_K"], 1.0, 1.0, 0.0)
    loss = two["temperature_K"].mean() + two["potential_V"].mean()
    loss.backward()
    assert torch.isfinite(one["temperature_K"]).all()
    assert torch.isfinite(two["temperature_K"]).all()
    assert all(parameter.grad is not None for parameter in model.parameters())


def test_projection_ledgers_close_at_machine_precision(operators) -> None:
    operator = operators["G1"]
    result = operator.projection(
        torch.full((25, 10), 335.0, dtype=torch.float64), 1.2, -1.0, 1.5
    )
    assert "source_current_A" in result and "terminal_current_A" not in result
    assert float(result["terminal_electrical_heat_ledger_error"]) <= 1.0e-8
    assert float(result["raw_subsolve_feedback_heat_sink_ledger_error"]) <= 1.0e-8
