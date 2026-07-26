from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation.geophase_phase1_gates import (
    build_formal_case_inventory,
    contact_overlap_qoi_audit,
    source_scale_preflight,
    source_envelope_noise_audit,
    substrate_depth_truncation_metrics,
)
from pinnpcm.physics.geophase_geometry import (
    CONTACT_REGION,
    assert_not_coordinate_swapped,
    build_geophase_grid,
)
from pinnpcm.physics.geophase_ledgers import (
    circuit_ledger,
    combined_electrothermal_ledger,
    device_power_identity,
    require_ledger_gate,
    thermal_ledger,
)
from pinnpcm.physics.vertical_thermal_memory import (
    PassiveThermalLadder,
    initial_passive_ladder,
)
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_2p5d_fvm import (
    assemble_lateral_thermal_matrix,
    solve_sheet_electrical,
    solve_steady_thermal_dirichlet,
)
from pinnpcm.solvers.geophase_2p5d_implicit import (
    advance_backward_euler,
    initial_state,
    simulate_adaptive_protocol,
    simulate_decoupled_copies,
)
from pinnpcm.solvers.vertical_multilayer_reference import (
    build_normalized_vertical_references,
    reduction_validation_metrics,
    select_smallest_passing_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml"


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def references(config: dict):
    return build_normalized_vertical_references(config)


@pytest.fixture(scope="module")
def smoke_components(config: dict, references):
    grid = build_geophase_grid(config, nx_override=10, ny_override=5)
    ladders = {
        region: initial_passive_ladder(
            region_id=region,
            order=3,
            total_capacity_J_m2K=reference.total_capacity_J_m2K,
            dc_conductance_W_m2K=reference.dc_conductance_W_m2K,
        )
        for region, reference in references.references.items()
    }
    closure = EffectiveVO2Closure.from_config(config)
    state = initial_state(grid, closure, ladders, config)
    return grid, ladders, closure, state


@pytest.mark.current
@pytest.mark.phase1
def test_locked_inventory_has_exactly_96_unexecuted_cases(config: dict) -> None:
    rows = build_formal_case_inventory(config)
    assert len(rows) == 96
    assert len({row["case_id"] for row in rows}) == 96
    assert {row["formal_status"] for row in rows} == {"planned_not_executed"}
    group_counts = {
        group: sum(row["case_group"] == group for row in rows)
        for group in {row["case_group"] for row in rows}
    }
    assert group_counts == {
        "vertical_reference_and_reduction": 24,
        "manufactured_solutions": 9,
        "single_device_refinement": 30,
        "topology_and_prior_audits": 18,
        "decoupled_dual_copy_limits": 4,
        "fail_closed_negative_controls": 5,
        "analytic_limits": 6,
    }


@pytest.mark.current
@pytest.mark.phase1
def test_source_scale_preflight_and_locked_rm_endmember(config: dict, references) -> None:
    checks = source_scale_preflight(config, normalized_references=references)
    assert checks["passed"] is True
    conductivity = config["parameter_contract"]["vo2_conductivity"]
    assert conductivity["source_metallic_resistance_ohm"] == pytest.approx(262.5)
    expected_sigma = conductivity["effective_current_path_m"] / (
        conductivity["effective_width_m"]
        * conductivity["active_thickness_m"]
        * 262.5
    )
    assert conductivity["sigma_met_ref_S_m"] == pytest.approx(expected_sigma)
    assert config["formal_case_inventory"]["total_expected_count"] == 96


@pytest.mark.current
@pytest.mark.phase1
def test_geometry_masks_and_coordinate_swap_fail_closed(config: dict) -> None:
    grid = build_geophase_grid(config)
    assert grid.shape == (25, 10)
    assert np.any(grid.region_index == CONTACT_REGION)
    assert np.any(grid.bare_mask)
    assert np.array_equal(grid.contact_mask, grid.left_contact_mask | grid.right_contact_mask)
    assert_not_coordinate_swapped(grid, config)
    swapped = replace(
        grid,
        x_edges_m=grid.y_edges_m.copy(),
        y_edges_m=grid.x_edges_m.copy(),
    )
    with pytest.raises(ValueError, match="coordinate swap"):
        assert_not_coordinate_swapped(swapped, config)


@pytest.mark.current
@pytest.mark.phase1
def test_uniform_sheet_manufactured_solution(config: dict) -> None:
    grid = build_geophase_grid(config)
    sigma = np.full(grid.shape, 12.0)
    result = solve_sheet_electrical(grid, sigma, 1.0)
    expected_1d = 1.0 - grid.x_centers_m / grid.x_edges_m[-1]
    expected = np.broadcast_to(expected_1d[None, :], grid.shape)
    relative_l2 = np.linalg.norm(result.potential_V - expected) / np.linalg.norm(expected)
    exact_current = 12.0 * grid.thickness_m * grid.y_edges_m[-1] / grid.x_edges_m[-1]
    assert relative_l2 < 1.0e-12
    assert result.source_current_A == pytest.approx(exact_current, rel=1.0e-12)
    assert result.ground_current_A == pytest.approx(-exact_current, rel=1.0e-12)
    assert result.relative_current_imbalance < 1.0e-12
    assert result.relative_power_imbalance < 1.0e-12


@pytest.mark.current
@pytest.mark.phase1
def test_thermal_manufactured_solution_and_no_flux_conservation(config: dict) -> None:
    grid = build_geophase_grid(config)
    result = solve_steady_thermal_dirichlet(grid, 4.0, 320.0, 330.0)
    expected_1d = 320.0 + 10.0 * grid.x_centers_m / grid.x_edges_m[-1]
    expected = np.broadcast_to(expected_1d[None, :], grid.shape)
    relative_l2 = np.linalg.norm(result - expected) / np.linalg.norm(expected)
    assert relative_l2 < 1.0e-12
    lateral = assemble_lateral_thermal_matrix(grid, 4.0)
    assert np.linalg.norm(lateral @ np.ones(grid.nx * grid.ny)) < 1.0e-18
    assert abs(float(np.sum(lateral @ result.reshape(-1)))) < 1.0e-16


@pytest.mark.current
@pytest.mark.phase1
def test_vertical_references_and_all_locked_orders_are_passive(config: dict, references) -> None:
    assert references.integrated_dc_conductance_W_K == pytest.approx(2.06e-4)
    assert references.integrated_memory_capacity_J_K == pytest.approx(4.958465e-11)
    bare = references.references["bare_vo2"]
    contact = references.references["electrode_covered_vo2"]
    assert contact.total_capacity_J_m2K > bare.total_capacity_J_m2K
    times = np.asarray([0.0, 1.0e-10, 1.0e-8])
    omega = 2.0 * np.pi * np.asarray([1.0e3, 1.0e6, 1.0e10])
    for order in (1, 2, 3, 8):
        for region, reference in references.references.items():
            ladder = initial_passive_ladder(
                region_id=region,
                order=order,
                total_capacity_J_m2K=reference.total_capacity_J_m2K,
                dc_conductance_W_m2K=reference.dc_conductance_W_m2K,
            )
            assert np.all(ladder.poles_per_s() < 0.0)
            assert np.isfinite(ladder.step_heat_flux_W_m2(times)).all()
            assert np.isfinite(ladder.impulse_tail_W_m2K_s(times)).all()
            assert np.isfinite(ladder.driving_admittance_W_m2K(omega)).all()
    with pytest.raises(ValueError, match="positive"):
        PassiveThermalLadder("bad", np.asarray([-1.0]), np.asarray([1.0, 1.0]))
    with pytest.raises(ValueError, match="positive"):
        PassiveThermalLadder("bad", np.asarray([1.0]), np.asarray([1.0, -1.0]))


@pytest.mark.current
@pytest.mark.phase1
def test_reduction_validation_is_held_out_and_selection_is_candidate_only(
    config: dict, references
) -> None:
    reference = references.references["bare_vo2"]
    fitted: dict[int, tuple[PassiveThermalLadder, dict[str, float]]] = {}
    for order in (1, 2, 3, 8):
        ladder = initial_passive_ladder(
            region_id="bare_vo2",
            order=order,
            total_capacity_J_m2K=reference.total_capacity_J_m2K,
            dc_conductance_W_m2K=reference.dc_conductance_W_m2K,
        )
        metrics = reduction_validation_metrics(
            reference,
            ladder,
            config["vertical_reference"]["reduction_fit_contract"],
        )
        assert np.isfinite(np.asarray(list(metrics.values()))).all()
        fitted[order] = (ladder, metrics)
    passing = dict(fitted)
    passing[2] = (
        passing[2][0],
        {
            **passing[2][1],
            "step_response_nrmse": 0.0,
            "impulse_response_nrmse": 0.0,
            "frequency_log_magnitude_rmse": 0.0,
        },
    )
    assert select_smallest_passing_candidate(passing, config).order == 2


@pytest.mark.current
@pytest.mark.phase1
def test_engineering_prior_audit_builders_preserve_locked_global_scales(config: dict) -> None:
    for depth in config["vertical_reference"]["substrate_depth_audit_m"]:
        audit = build_normalized_vertical_references(config, substrate_depth_m=depth)
        assert audit.integrated_dc_conductance_W_K == pytest.approx(2.06e-4)
        assert audit.integrated_memory_capacity_J_K == pytest.approx(4.958465e-11)
    for overlap in config["geometry"]["primary_single_device"]["contact_overlap_audit_m"]:
        audit = build_normalized_vertical_references(config, contact_overlap_m=overlap)
        assert audit.integrated_dc_conductance_W_K == pytest.approx(2.06e-4)
        assert audit.integrated_memory_capacity_J_K == pytest.approx(4.958465e-11)
        grid = build_geophase_grid(config, contact_overlap_m=overlap)
        assert np.any(grid.contact_mask)
        assert np.any(grid.bare_mask)


@pytest.mark.current
@pytest.mark.phase1
def test_locked_prior_vote_evaluators_are_quantitative(config: dict) -> None:
    depth = substrate_depth_truncation_metrics(config)
    values = [
        metric
        for region in depth["regions"].values()
        for metric in region.values()
    ]
    assert np.isfinite(np.asarray(values, dtype=float)).all()
    expected_depth_pass = all(
        region["step_response_nrmse"]
        <= config["gates"]["substrate_depth_step_response_nrmse_max"]
        and region["frequency_log_magnitude_rmse"]
        <= config["gates"]["substrate_depth_frequency_log_magnitude_rmse_max"]
        for region in depth["regions"].values()
    )
    assert depth["would_pass_locked_gate"] is expected_depth_pass

    overlaps = config["geometry"]["primary_single_device"]["contact_overlap_audit_m"]
    qois = {
        float(overlaps[0]): {"terminal_current": 0.99},
        float(overlaps[1]): {"terminal_current": 1.00},
        float(overlaps[2]): {"terminal_current": 1.01},
    }
    permissive = contact_overlap_qoi_audit(
        config, qois, {"terminal_current": 0.02}
    )
    strict = contact_overlap_qoi_audit(
        config, qois, {"terminal_current": 0.005}
    )
    assert permissive["geometry_robust_wording_eligible"] is True
    assert strict["geometry_robust_wording_eligible"] is False
    assert permissive["reporting_required"] is True

    eligible = source_envelope_noise_audit(config, np.asarray([1.0, 1.1]), 0.05)
    ineligible = source_envelope_noise_audit(config, np.asarray([1.0, 1.1]), 0.2)
    assert eligible["eligible_to_vote"] is True
    assert ineligible["eligible_to_vote"] is False


@pytest.mark.current
@pytest.mark.phase1
def test_three_ledgers_and_tamper_control() -> None:
    thermal = thermal_ledger(
        joule_power_W=10.0,
        active_storage_rate_W=3.0,
        memory_storage_rate_W=2.0,
        vertical_sink_power_W=4.0,
        lateral_outflow_power_W=1.0,
    )
    circuit = circuit_ledger(
        input_voltage_V=0.5,
        old_device_voltage_V=0.2,
        new_device_voltage_V=0.3,
        load_resistance_ohm=100.0,
        capacitance_F=1.0e-3,
        device_current_A=1.0e-3,
        dt_s=0.1,
    )
    combined = combined_electrothermal_ledger(
        input_voltage_V=0.5,
        old_device_voltage_V=0.2,
        new_device_voltage_V=0.3,
        load_resistance_ohm=100.0,
        capacitance_F=1.0e-3,
        dt_s=0.1,
        active_storage_rate_W=1.0e-4,
        memory_storage_rate_W=5.0e-5,
        vertical_sink_power_W=1.0e-4,
        lateral_outflow_power_W=5.0e-5,
    )
    power = device_power_identity(
        terminal_device_power_W=3.0e-4,
        field_joule_power_W=3.0e-4,
    )
    assert thermal.relative_residual == pytest.approx(0.0)
    assert circuit.relative_residual == pytest.approx(0.0, abs=1.0e-15)
    assert combined.relative_residual == pytest.approx(0.0, abs=1.0e-15)
    assert power.relative_residual == pytest.approx(0.0)
    tampered = thermal_ledger(
        joule_power_W=10.0,
        active_storage_rate_W=3.0,
        memory_storage_rate_W=2.0,
        vertical_sink_power_W=3.0,
        lateral_outflow_power_W=1.0,
    )
    with pytest.raises(ValueError, match="ledger failed"):
        require_ledger_gate(tampered, 1.0e-2)


@pytest.mark.current
@pytest.mark.phase1
def test_implicit_zero_and_low_drive_smoke(config: dict, smoke_components) -> None:
    grid, ladders, closure, state = smoke_components
    zero = advance_backward_euler(
        state,
        input_voltage_V=0.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert np.max(np.abs(zero.state.temperature_K - state.temperature_K)) < 1.0e-8
    assert np.array_equal(zero.state.branch_memory, state.branch_memory)
    assert zero.nonlinear.converged
    low = advance_backward_euler(
        state,
        input_voltage_V=1.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert low.state.device_voltage_V > 0.0
    assert low.electrical.source_current_A > 0.0
    assert low.nonlinear.method in {
        "damped_newton_krylov",
        "fail_closed_fixed_point_fallback",
    }
    assert low.nonlinear.converged
    assert low.thermal_balance.relative_residual < config["gates"]["thermal_ledger_relative_residual_max"]
    assert low.circuit_balance.relative_residual < config["gates"]["circuit_ledger_relative_residual_max"]
    assert low.combined_balance.relative_residual < config["gates"]["combined_ledger_relative_residual_max"]
    assert low.device_power_balance.relative_residual < config["gates"]["device_power_identity_relative_residual_max"]


@pytest.mark.current
@pytest.mark.phase1
def test_adaptive_protocol_accepts_low_drive_and_reports_diagnostics(
    config: dict, smoke_components
) -> None:
    grid, ladders, closure, state = smoke_components
    protocol = simulate_adaptive_protocol(
        state,
        input_voltage=lambda _time: 1.0,
        final_time_s=2.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert protocol.diagnostics.accepted_steps >= 1
    assert protocol.diagnostics.rejected_steps == 0
    assert protocol.steps[-1].state.time_s == pytest.approx(2.0e-9)
    assert (
        protocol.diagnostics.maximum_transition_increment
        <= config["reference_solver"]["time_grid"]["transition_increment_threshold"]
    )


@pytest.mark.current
@pytest.mark.phase1
def test_adaptive_protocol_rejects_large_transition_and_enforces_cap(
    monkeypatch: pytest.MonkeyPatch, config: dict, smoke_components
) -> None:
    import copy
    import pinnpcm.solvers.geophase_2p5d_implicit as implicit

    grid, ladders, closure, state = smoke_components
    original = implicit.advance_backward_euler

    def controlled(old_state, *, dt_s, **kwargs):
        baseline = original(old_state, dt_s=min(float(dt_s), 1.0e-9), **kwargs)
        increment = 0.03 if float(dt_s) > 2.0e-9 else 0.01
        trial_state = replace(
            baseline.state,
            time_s=old_state.time_s + float(dt_s),
            conductive_state=np.clip(old_state.conductive_state + increment, 0.0, 1.0),
            branch_memory=old_state.branch_memory.copy(),
        )
        return replace(baseline, state=trial_state)

    monkeypatch.setattr(implicit, "advance_backward_euler", controlled)
    protocol = implicit.simulate_adaptive_protocol(
        state,
        input_voltage=lambda _time: 0.0,
        final_time_s=3.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert protocol.diagnostics.transition_rejections == 1
    assert protocol.diagnostics.minimum_accepted_step_s == pytest.approx(1.5e-9)

    always_reject = copy.deepcopy(config)
    always_reject["reference_solver"]["time_grid"][
        "maximum_rejected_steps_per_accepted_step"
    ] = 0
    with pytest.raises(RuntimeError, match="rejection cap"):
        implicit.simulate_adaptive_protocol(
            state,
            input_voltage=lambda _time: 0.0,
            final_time_s=3.0e-9,
            grid=grid,
            closure=closure,
            ladders=ladders,
            config=always_reject,
        )


@pytest.mark.current
@pytest.mark.phase1
def test_fixed_point_fallback_is_real_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch, config: dict, smoke_components
) -> None:
    import pinnpcm.solvers.geophase_2p5d_implicit as implicit

    grid, ladders, closure, state = smoke_components

    def fail_newton(*_args, **_kwargs):
        raise ValueError("forced Newton failure")

    monkeypatch.setattr(implicit, "_damped_newton_krylov", fail_newton)
    result = implicit.advance_backward_euler(
        state,
        input_voltage_V=0.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert result.nonlinear.method == "fail_closed_fixed_point_fallback"
    assert result.nonlinear.converged


@pytest.mark.current
@pytest.mark.phase1
def test_decoupled_copy_symmetry_and_label_exchange(config: dict, smoke_components) -> None:
    grid, ladders, closure, state = smoke_components
    first, second = simulate_decoupled_copies(
        state,
        state,
        input_voltage_a_V=1.0,
        input_voltage_b_V=1.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert np.array_equal(first.state.temperature_K, second.state.temperature_K)
    assert first.state.device_voltage_V == second.state.device_voltage_V
    swapped_second, swapped_first = simulate_decoupled_copies(
        state,
        state,
        input_voltage_a_V=1.0,
        input_voltage_b_V=1.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    assert np.array_equal(first.state.temperature_K, swapped_first.state.temperature_K)
    assert np.array_equal(second.state.temperature_K, swapped_second.state.temperature_K)


@pytest.mark.current
@pytest.mark.phase1
def test_nonfinite_and_temperature_domain_fail_closed(config: dict, smoke_components) -> None:
    grid, ladders, closure, state = smoke_components
    bad_temperature = state.temperature_K.copy()
    bad_temperature[0, 0] = 381.0
    bad = replace(state, temperature_K=bad_temperature)
    with pytest.raises(ValueError, match="validity range"):
        advance_backward_euler(
            bad,
            input_voltage_V=0.0,
            dt_s=1.0e-9,
            grid=grid,
            closure=closure,
            ladders=ladders,
            config=config,
        )
    nonfinite = state.temperature_K.copy()
    nonfinite[0, 0] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        advance_backward_euler(
            replace(state, temperature_K=nonfinite),
            input_voltage_V=0.0,
            dt_s=1.0e-9,
            grid=grid,
            closure=closure,
            ladders=ladders,
            config=config,
        )


@pytest.mark.current
@pytest.mark.phase1
def test_reference_solver_does_not_import_pinn_residuals() -> None:
    files = [
        ROOT / "src" / "pinnpcm" / "solvers" / "geophase_2p5d_fvm.py",
        ROOT / "src" / "pinnpcm" / "solvers" / "geophase_2p5d_implicit.py",
        ROOT / "src" / "pinnpcm" / "solvers" / "vertical_multilayer_reference.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "pinnpcm.pinn" not in text
        assert "geophase_residual" not in text
