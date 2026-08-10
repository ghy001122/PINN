from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from pinnpcm.experiments.geostate_fasttrack import load_yaml, material_parameters
from pinnpcm.experiments.m1_protocol_selected_equilibrium_manifold import (
    ProtocolEvent,
    ProtocolPoint,
    ProtocolRun,
    ProtocolSpec,
    _union_fieldnames,
    build_protocol_specs,
    classify_stability_margin,
    event_step_sensitivity,
    evaluate_physical_stability,
    jump_diagnostics,
    protocol_voltage_grid,
    refine_protocol_event,
    run_coarse_protocol,
    thermal_dynamic_rhs,
    validate_future_input_contract,
)
from pinnpcm.experiments.m1_self_consistent_imt_contraction import (
    FixedPointResult,
    solve_fixed_point,
)
from pinnpcm.physics.m1_self_consistent_imt import (
    M1SelfConsistentIMTProjection,
    QiuMajorBranchParameters,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_yaml(
    ROOT / "configs/q2_m1_protocol_selected_equilibrium_manifold_mve_v1.yaml"
)
BASE = load_yaml(ROOT / "configs/q2_mf_geostate_mc_pinn_fasttrack_v1.yaml")
SOLVER = CONFIG["solver"]
GATES = CONFIG["validity_gates"]
JUMP = CONFIG["jump_detection"]


def _metrics(
    temperature: torch.Tensor,
    *,
    state: float,
    current: float,
    iterations: int = 2,
) -> dict[str, object]:
    return {
        "iterations": iterations,
        "converged": True,
        "finite": True,
        "scaled_nonlinear_residual": 1.0e-9,
        "scaled_thermal_residual": 1.0e-9,
        "scaled_electrical_residual": 1.0e-9,
        "scaled_raw_update": 1.0e-10,
        "terminal_current_A": current,
        "ground_current_A": current,
        "current_imbalance": 0.0,
        "terminal_electrical_heat_ledger_error": 0.0,
        "state_consistent_feedback_heat_sink_ledger_error": 0.0,
        "raw_subsolve_feedback_heat_sink_ledger_error": 0.0,
        "Tmax_K": float(torch.max(temperature)),
        "Tmean_K": float(torch.mean(temperature)),
        "transition_fraction": 0.0,
        "mean_effective_state_coordinate": state,
    }


def _result(
    temperature_K: float,
    *,
    state: float,
    current: float,
    shape: tuple[int, int] = (2, 3),
) -> FixedPointResult:
    temperature = torch.full(shape, temperature_K, dtype=torch.float64)
    return FixedPointResult(
        temperature_K=temperature,
        fields={},
        metrics=_metrics(temperature, state=state, current=current),
    )


def _point(
    point_id: str,
    voltage: float,
    result: FixedPointResult,
    *,
    index: int,
    kind: str = "coarse",
) -> ProtocolPoint:
    return ProtocolPoint(
        point_id=point_id,
        protocol_id="G0_heating",
        context_id="G0",
        branch_label="heating",
        branch_value=1.0,
        voltage_V=voltage,
        point_kind=kind,
        sequence_index=index,
        initial_state_provenance="immediately_preceding_accepted_protocol_equilibrium",
        previous_point_id="",
        result=result,
        valid=True,
        accepted=True,
    )


def _small_operator() -> M1SelfConsistentIMTProjection:
    x = np.array([1.0e-8, 3.0e-8, 5.0e-8])
    y = np.array([1.0e-7, 3.0e-7])
    sheet = np.full((2, 3), 6.0e-7)
    left = np.zeros((2, 3), dtype=bool)
    right = np.zeros((2, 3), dtype=bool)
    left[:, 0] = True
    right[:, -1] = True
    form = BASE["physical_model"]["model_forms"]["M1"]
    qiu = QiuMajorBranchParameters(
        beta_per_K=0.253,
        hysteresis_width_K=7.193,
        critical_temperature_K=332.8,
        T_c_up_K=336.3965,
        T_c_down_K=329.2035,
        nominal_transition_width_K=1.0 / 0.253,
        source_contract_schema="qiu_vo2_phase1_source_contract_v3",
    )
    return M1SelfConsistentIMTProjection(
        x_centers_m=x,
        y_centers_m=y,
        thickness_m=1.0e-7,
        sheet_thermal_conductance_W_K=sheet,
        left_contact_mask=left,
        right_contact_mask=right,
        ambient_temperature_K=325.0,
        vertical_conductance_W_m2K=1.0e7,
        electrical_contact_resistance_ohm=form["electrical_contact_resistance_ohm"],
        thermal_contact_resistance_m2K_W=form["thermal_contact_resistance_m2K_W"],
        localized_sink_rectangle_m={"x": [2.0e-8, 4.0e-8], "y": [0.0, 4.0e-7]},
        material_params=material_parameters(BASE),
        qiu_major_branch_parameters=qiu,
        phase_width_multiplier=1.0,
        joule_feedback_multiplier=1.0,
        relaxation_alpha=0.35,
    )


def test_protocol_directions_endpoints_and_integer_voltage_grids() -> None:
    specs = build_protocol_specs(CONFIG)
    assert len(specs) == 4
    for spec in specs:
        grid = protocol_voltage_grid(spec)
        assert grid.size == 33
        assert grid[0] == pytest.approx(spec.start_voltage_V)
        assert grid[-1] == pytest.approx(spec.end_voltage_V)
        if spec.branch_label == "heating":
            assert spec.direction == "increasing" and np.all(np.diff(grid) > 0.0)
            assert spec.start_temperature_K == 325.0
        else:
            assert spec.direction == "decreasing" and np.all(np.diff(grid) < 0.0)
            assert spec.start_temperature_K == 360.0
            assert spec.fallback_preparation_voltage_V == 1.75


def test_previous_accepted_equilibrium_is_next_protocol_initial_state() -> None:
    spec = next(spec for spec in build_protocol_specs(CONFIG) if spec.protocol_id == "G0_heating")
    calls: list[torch.Tensor] = []
    outputs: list[torch.Tensor] = []

    def fake_solve(**kwargs: object) -> FixedPointResult:
        initial = torch.as_tensor(kwargs["initial_temperature_K"], dtype=torch.float64).clone()
        calls.append(initial)
        output = initial + 1.0e-3
        outputs.append(output)
        voltage = float(kwargs["voltage_V"])
        return FixedPointResult(
            temperature_K=output,
            fields={},
            metrics=_metrics(output, state=0.02, current=1.0e-5 * voltage),
        )

    run = run_coarse_protocol(
        spec=spec,
        operator=_small_operator(),
        solver_config=SOLVER,
        validity_gates=GATES,
        jump_config=JUMP,
        solve_function=fake_solve,
    )
    assert run.completed and len(calls) == 33
    for index in range(1, len(calls)):
        torch.testing.assert_close(calls[index], outputs[index - 1], rtol=0.0, atol=0.0)
        assert run.coarse_points[index].previous_point_id == run.coarse_points[index - 1].point_id


def test_jump_detector_uses_inclusive_frozen_thresholds() -> None:
    previous = _result(326.0, state=0.0, current=1.0)
    exact = _result(326.0, state=0.4, current=2.0)
    below = _result(326.01, state=0.399, current=1.99)
    exact_metrics = jump_diagnostics(
        previous, exact, ambient_temperature_K=325.0, jump_config=JUMP
    )
    below_metrics = jump_diagnostics(
        previous, below, ambient_temperature_K=325.0, jump_config=JUMP
    )
    assert exact_metrics["mean_state_jump"]
    assert exact_metrics["current_jump"]
    assert exact_metrics["jump_candidate"]
    assert not below_metrics["jump_candidate"]


def test_event_bisection_follows_protocol_pre_state_and_resolves() -> None:
    spec = next(spec for spec in build_protocol_specs(CONFIG) if spec.protocol_id == "G0_heating")
    pre = _point("pre", 1.0, _result(326.0, state=0.01, current=1.0e-5), index=10)
    post = _point("post", 1.025, _result(350.0, state=0.99, current=4.0e-3), index=11)
    post.jump_from_previous = jump_diagnostics(
        pre.result, post.result, ambient_temperature_K=325.0, jump_config=JUMP
    )
    run = ProtocolRun(
        spec=spec,
        expected_coarse_points=33,
        preparation_points=[],
        coarse_points=[pre, post],
        event=ProtocolEvent("event", spec.protocol_id, pre, post, pre, post, [], 0, False),
        half_step_points=[],
        half_step_event_pre=None,
        half_step_event_post=None,
        endpoint_pass=True,
        completed=True,
        failure_reason="",
    )

    def fake_solve(**kwargs: object) -> FixedPointResult:
        voltage = float(kwargs["voltage_V"])
        return (
            _result(326.0, state=0.01, current=1.0e-5)
            if voltage < 1.013
            else _result(350.0, state=0.99, current=4.0e-3)
        )

    event = refine_protocol_event(
        run=run,
        operator=_small_operator(),
        solver_config=SOLVER,
        validity_gates=GATES,
        jump_config=JUMP,
        solve_function=fake_solve,
    )
    assert event is not None and event.resolved
    assert event.voltage_upper_V - event.voltage_lower_V <= 0.005
    assert event.refinement_solve_count <= 6
    assert event.refined_post.initial_state_provenance == "final_refined_pre_switch_equilibrium"


def test_thermal_dynamic_jacobian_is_finite_and_matches_residual_sign() -> None:
    operator = _small_operator()
    initial = torch.full((2, 3), 325.0, dtype=torch.float64)
    solved = solve_fixed_point(
        operator=operator,
        initial_temperature_K=initial,
        voltage_V=0.4,
        branch=1.0,
        sink_amplitude=0.0,
        solver_config=SOLVER,
    )
    point = _point("stable_probe", 0.4, solved, index=0)
    capacity = 4.96e-11 / 6.0
    flat = solved.temperature_K.reshape(-1)
    rhs = thermal_dynamic_rhs(
        operator,
        flat,
        voltage_V=0.4,
        branch_value=1.0,
        sink_amplitude=0.0,
        cell_thermal_capacity_J_K=capacity,
    )
    electrical = operator.electrical(solved.temperature_K, 0.4, 1.0)
    residual = operator.thermal_residual(
        solved.temperature_K, electrical["total_joule_cell_W"], 0.0
    ).reshape(-1)
    torch.testing.assert_close(capacity * rhs, -residual, rtol=1.0e-13, atol=1.0e-18)
    metrics = evaluate_physical_stability(
        operator=operator,
        point=point,
        sink_amplitude=0.0,
        cell_thermal_capacity_J_K=capacity,
        stability_config=CONFIG["stability"],
    )
    assert metrics["finite"] and metrics["eigenvalue_count"] == 6
    assert np.isfinite(metrics["relative_stability_margin"])


def test_stability_classifier_includes_frozen_boundaries() -> None:
    assert classify_stability_margin(-1.0e-6) == "stable"
    assert classify_stability_margin(1.0e-6) == "unstable"
    assert classify_stability_margin(0.0) == "indeterminate"


def test_half_step_event_comparison_checks_threshold_fields_and_classification() -> None:
    spec = next(spec for spec in build_protocol_specs(CONFIG) if spec.protocol_id == "G0_heating")
    coarse = [
        _point(f"coarse_{index}", voltage, _result(326.0 if voltage < 1.0 else 350.0, state=0.01 if voltage < 1.0 else 0.99, current=1.0e-5 if voltage < 1.0 else 4.0e-3), index=index)
        for index, voltage in enumerate((0.95, 0.975, 1.0, 1.025, 1.05, 1.075))
    ]
    primary_pre = _point("primary_pre", 0.9984375, _result(326.0, state=0.01, current=1.0e-5), index=0, kind="event_refinement")
    primary_post = _point("primary_post", 1.0015625, _result(350.0, state=0.99, current=4.0e-3), index=1, kind="event_refinement")
    half_pre = _point("half_pre", 0.9984375, _result(326.0, state=0.01, current=1.0e-5), index=0, kind="half_step_event_refinement")
    half_post = _point("half_post", 1.0015625, _result(350.0, state=0.99, current=4.0e-3), index=1, kind="half_step_event_refinement")
    event = ProtocolEvent("event", spec.protocol_id, coarse[2], coarse[3], primary_pre, primary_post, [], 4, True)
    half_points = [
        _point(f"half_{index}", point.voltage_V, point.result, index=index, kind="half_step_continuation")
        for index, point in enumerate(coarse)
    ]
    run = ProtocolRun(spec, 33, [], coarse, event, half_points, half_pre, half_post, True, True, "")
    stability = {
        point_id: {"stability_class": "stable"}
        for point_id in ("primary_pre", "primary_post", "half_pre", "half_post")
    }
    row = event_step_sensitivity(
        run=run,
        stability_by_point=stability,
        sensitivity_config={
            **CONFIG["step_sensitivity"],
            "refinement_voltage_resolution_V": 0.005,
        },
    )
    assert row["pass"]
    assert row["switching_voltage_difference_V"] == pytest.approx(0.0)
    assert row["stability_classification_reversal_count"] == 0
    no_event_run = ProtocolRun(
        spec, 33, [], coarse, None, [], None, None, True, True, ""
    )
    not_applicable = event_step_sensitivity(
        run=no_event_run,
        stability_by_point={},
        sensitivity_config=CONFIG["step_sensitivity"],
    )
    assert not_applicable["executed"] is False
    assert not_applicable["pass"] is None


def test_root_averaging_and_root_identifiers_are_forbidden_future_inputs() -> None:
    validate_future_input_contract(
        CONFIG["surrogate_eligibility"]["future_allowed_inputs"],
        CONFIG["surrogate_eligibility"]["future_forbidden_inputs"],
    )
    with pytest.raises(ValueError):
        validate_future_input_contract(
            [*CONFIG["surrogate_eligibility"]["future_allowed_inputs"], "root_id"],
            CONFIG["surrogate_eligibility"]["future_forbidden_inputs"],
        )
    assert _union_fieldnames(
        [{"event_id": "", "detected": False}, {"event_id": "e", "interval": 1.0}]
    ) == ["event_id", "detected", "interval"]
    with pytest.raises(ValueError):
        validate_future_input_contract(
            [*CONFIG["surrogate_eligibility"]["future_allowed_inputs"], "root_averaging"],
            CONFIG["surrogate_eligibility"]["future_forbidden_inputs"],
        )
