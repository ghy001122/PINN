from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.physics.geophase_s2_ledgers import (
    build_s2_two_half_interval_ledgers,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_overlay import (
    resolve_controller_v2,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    S2EmbeddedAttemptObservation,
    attempt_s2_embedded_interval,
    compute_embedded_error,
    controller_v2_limits,
    simulate_s2_protocol_v2,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    initial_s2_state,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
OVERLAY_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_embedded_time_controller_v2.yaml"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def context():
    resolved = resolve_controller_v2(BASE_PATH, OVERLAY_PATH)
    config = resolved.resolved_config
    grid = build_geophase_grid(config)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    cache = build_s2_solver_cache(grid, fields)
    state = initial_s2_state(grid, closure, fields, config)
    zero = config["formal_protocols"]["protocols"]["zero_drive"]
    template = attempt_s2_embedded_interval(
        state,
        protocol=zero,
        protocol_id="zero_drive",
        outer_interval_s=1.0e-8,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=cache,
    )
    assert template.step is not None
    return config, grid, fields, closure, cache, state, template


def _scalar_state(*, temperature: float, conductive: float, branch: float, voltage: float):
    return S2State(
        time_s=0.0,
        temperature_K=np.asarray([[temperature]], dtype=float),
        conductive_state=np.asarray([[conductive]], dtype=float),
        branch_memory=np.asarray([[branch]], dtype=float),
        device_voltage_V=voltage,
    )


def test_smooth_linear_relaxation_full_two_half_error_is_analytic() -> None:
    y0 = 0.1
    equilibrium = 0.9
    tau = 2.0
    H = 0.4
    ratio = H / tau
    full_y = (y0 + ratio * equilibrium) / (1.0 + ratio)
    half_ratio = 0.5 * ratio
    first_half = (y0 + half_ratio * equilibrium) / (1.0 + half_ratio)
    two_half_y = (first_half + half_ratio * equilibrium) / (1.0 + half_ratio)
    full = _scalar_state(
        temperature=330.0, conductive=full_y, branch=0.0, voltage=2.0
    )
    fine = _scalar_state(
        temperature=330.0, conductive=two_half_y, branch=0.0, voltage=2.0
    )
    error = compute_embedded_error(full, fine, voltage_scale_V=12.5)
    assert error.e_s == pytest.approx(abs(two_half_y - full_y))
    assert error.e_T == error.e_b == error.e_V == 0.0
    assert error.e_max == error.e_s


def test_saturated_cooling_branch_full_two_half_error_is_analytic() -> None:
    b0 = 1.0
    cooling = 1.0
    tau = 1.0
    H = 0.25

    def update(value: float, dt: float) -> float:
        ratio = dt / tau
        return (value - ratio * cooling) / (1.0 + ratio * cooling)

    full_b = update(b0, H)
    two_half_b = update(update(b0, H / 2.0), H / 2.0)
    full = _scalar_state(
        temperature=329.0, conductive=0.2, branch=full_b, voltage=0.0
    )
    fine = _scalar_state(
        temperature=329.0, conductive=0.2, branch=two_half_b, voltage=0.0
    )
    error = compute_embedded_error(full, fine, voltage_scale_V=1.0)
    assert error.e_b == pytest.approx(abs(two_half_b - full_b))
    assert error.e_max == error.e_b


def test_divisor_bounds_apply_to_outer_interval_not_half_step(context) -> None:
    config = context[0]
    for divisor in (1, 2, 4):
        maximum, floor = controller_v2_limits(config, divisor)
        assert maximum == pytest.approx(1.0e-8 / divisor)
        assert floor == pytest.approx(9.765625e-12 / divisor)
        assert floor / 2.0 < floor


def test_zero_drive_embedded_attempt_passes_all_paths_and_aggregate(context) -> None:
    template = context[-1]
    step = template.step
    assert step is not None
    diagnostic = step.controller
    assert diagnostic.accepted is True
    assert diagnostic.coupled_solve_count == 3
    assert diagnostic.full_step.overall_pass is True
    assert diagnostic.first_half_step is not None
    assert diagnostic.first_half_step.overall_pass is True
    assert diagnostic.second_half_step is not None
    assert diagnostic.second_half_step.overall_pass is True
    assert diagnostic.aggregate is not None
    assert diagnostic.aggregate.overall_pass is True
    assert diagnostic.embedded_error is not None
    assert diagnostic.embedded_error.e_max == 0.0
    assert step.aggregate_energy.duration_s == pytest.approx(1.0e-8)


def test_cached_and_uncached_embedded_zero_drive_are_identical(context) -> None:
    config, grid, fields, closure, cache, state, cached = context
    direct = attempt_s2_embedded_interval(
        state,
        protocol=config["formal_protocols"]["protocols"]["zero_drive"],
        protocol_id="zero_drive",
        outer_interval_s=1.0e-8,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=None,
        use_equivalent_optimizations=False,
    )
    assert cached.step is not None and direct.step is not None
    assert np.array_equal(
        cached.step.state.temperature_K, direct.step.state.temperature_K
    )
    assert np.array_equal(
        cached.step.state.conductive_state, direct.step.state.conductive_state
    )
    assert cached.step.ledgers == direct.step.ledgers


def test_aggregate_ledger_cancels_midpoint_storage_and_rebuilds_signed_terms(
    context,
) -> None:
    config, grid, fields, _closure, _cache, state, template = context
    first = template.first_half_candidate
    second = template.second_half_candidate
    assert first is not None and second is not None
    final_temperature = state.temperature_K + 2.0
    first_a = replace(
        first,
        state=replace(first.state, temperature_K=state.temperature_K + 5.0),
    )
    first_b = replace(
        first,
        state=replace(first.state, temperature_K=state.temperature_K + 9.0),
    )
    final = replace(
        second,
        state=replace(second.state, temperature_K=final_temperature),
    )
    kwargs = dict(
        grid=grid,
        fields=fields,
        outer_initial_temperature_K=state.temperature_K,
        outer_initial_device_voltage_V=state.device_voltage_V,
        second_half=final,
        half_dt_s=5.0e-9,
        capacitance_F=float(
            config["physics_contract"]["circuit"]["parallel_capacitance_F"]
        ),
    )
    ledger_a, energy_a = build_s2_two_half_interval_ledgers(
        first_half=first_a, **kwargs
    )
    ledger_b, energy_b = build_s2_two_half_interval_ledgers(
        first_half=first_b, **kwargs
    )
    assert energy_a.explicit_plane_storage_J == pytest.approx(
        energy_b.explicit_plane_storage_J
    )
    assert energy_a.closure_storage_J == pytest.approx(energy_b.closure_storage_J)
    assert ledger_a == ledger_b


def test_aggregate_device_power_tamper_is_detected(context) -> None:
    config, grid, fields, _closure, _cache, state, template = context
    first = template.first_half_candidate
    second = template.second_half_candidate
    assert first is not None and second is not None
    tampered = replace(
        second,
        electrical=replace(second.electrical, terminal_device_power_W=1.0),
    )
    ledgers, _energy = build_s2_two_half_interval_ledgers(
        grid=grid,
        fields=fields,
        outer_initial_temperature_K=state.temperature_K,
        outer_initial_device_voltage_V=state.device_voltage_V,
        first_half=first,
        second_half=tampered,
        half_dt_s=5.0e-9,
        capacitance_F=float(
            config["physics_contract"]["circuit"]["parallel_capacitance_F"]
        ),
    )
    assert ledgers.device_power.relative_residual > float(
        config["gates"]["device_power_identity_relative_residual_max"]
    )


def test_legacy_state_increment_is_telemetry_and_does_not_veto(
    context, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, grid, fields, closure, _cache, state, template = context
    base_step = template.step
    assert base_step is not None
    old = replace(
        state,
        conductive_state=np.full(grid.shape, 0.5),
        branch_memory=np.zeros(grid.shape),
    )
    sequence = []
    for fraction, branch in ((1.0, 0.03), (0.5, 0.015), (1.0, 0.03)):
        sequence.append(
            replace(
                base_step,
                state=replace(
                    old,
                    time_s=old.time_s + fraction * 1.0e-8,
                    branch_memory=np.full(grid.shape, branch),
                ),
            )
        )

    def fake_advance(*_args, **_kwargs):
        return sequence.pop(0)

    monkeypatch.setattr(
        "pinnpcm.solvers.geophase_phase1_v2_controller_v2.advance_s2_backward_euler",
        fake_advance,
    )
    result = attempt_s2_embedded_interval(
        old,
        protocol=config["formal_protocols"]["protocols"]["zero_drive"],
        protocol_id="zero_drive",
        outer_interval_s=1.0e-8,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )
    assert result.step is not None
    assert result.step.controller.legacy_branch_increment == pytest.approx(0.03)
    assert result.step.controller.legacy_branch_increment > 0.02
    assert result.step.controller.embedded_error is not None
    assert result.step.controller.embedded_error.e_b == 0.0


@pytest.mark.parametrize("failing_call", (1, 2, 3))
def test_each_candidate_path_failure_is_fail_closed(
    context, monkeypatch: pytest.MonkeyPatch, failing_call: int
) -> None:
    config, grid, fields, closure, _cache, state, template = context
    base_step = template.step
    assert base_step is not None
    calls = 0

    def fake_advance(old, *, dt_s, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == failing_call:
            raise RuntimeError(f"injected path {failing_call} failure")
        return replace(base_step, state=replace(old, time_s=old.time_s + dt_s))

    monkeypatch.setattr(
        "pinnpcm.solvers.geophase_phase1_v2_controller_v2.advance_s2_backward_euler",
        fake_advance,
    )
    result = attempt_s2_embedded_interval(
        state,
        protocol=config["formal_protocols"]["protocols"]["zero_drive"],
        protocol_id="zero_drive",
        outer_interval_s=1.0e-8,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )
    assert result.step is None
    assert result.error_class == "RuntimeError"
    assert result.diagnostics.accepted is False
    assert result.diagnostics.coupled_solve_count == failing_call


def _observation_from_template(
    template: S2EmbeddedAttemptObservation,
    state: S2State,
    H: float,
    *,
    accepted: bool,
    e_max: float,
    rejection_index: int,
) -> S2EmbeddedAttemptObservation:
    assert template.step is not None
    embedded = replace(
        template.step.controller.embedded_error,
        e_T=e_max,
        e_s=0.0,
        e_b=0.0,
        e_V=0.0,
        e_max=e_max,
    )
    controller = replace(
        template.step.controller,
        outer_interval_s=H,
        half_interval_s=H / 2.0,
        embedded_error=embedded,
        rejection_index=rejection_index,
        accepted=accepted,
        wall_time_s=0.0,
    )
    step = None
    if accepted:
        step = replace(
            template.step,
            state=replace(state, time_s=state.time_s + H),
            controller=controller,
        )
    return S2EmbeddedAttemptObservation(
        previous_state=state,
        step=step,
        full_candidate=template.full_candidate,
        first_half_candidate=template.first_half_candidate,
        second_half_candidate=template.second_half_candidate,
        diagnostics=controller,
        error_class=None,
        error_message=None,
    )


def test_two_easy_intervals_grow_H_without_pid(
    context, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, grid, fields, closure, _cache, state, template = context
    attempted: list[float] = []

    def fake_attempt(current, *, outer_interval_s, rejection_index, **_kwargs):
        attempted.append(outer_interval_s)
        return _observation_from_template(
            template,
            current,
            outer_interval_s,
            accepted=True,
            e_max=0.0,
            rejection_index=rejection_index,
        )

    monkeypatch.setattr(
        "pinnpcm.solvers.geophase_phase1_v2_controller_v2.attempt_s2_embedded_interval",
        fake_attempt,
    )
    result = simulate_s2_protocol_v2(
        state,
        protocol=config["formal_protocols"]["protocols"]["zero_drive"],
        protocol_id="zero_drive",
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=1.5e-8,
        forced_times_s=(0.0, 2.5e-9, 5.0e-9, 1.0e-8, 1.5e-8),
    )
    assert result.completed is True
    assert attempted[:3] == pytest.approx([2.5e-9, 2.5e-9, 5.0e-9])
    assert result.diagnostics.growth_events >= 1


def test_floor_candidate_is_evaluated_after_ten_halvings_then_fails_closed(
    context, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, grid, fields, closure, _cache, state, template = context
    attempted: list[float] = []

    def fake_attempt(current, *, outer_interval_s, rejection_index, **_kwargs):
        attempted.append(outer_interval_s)
        return _observation_from_template(
            template,
            current,
            outer_interval_s,
            accepted=False,
            e_max=0.03,
            rejection_index=rejection_index,
        )

    monkeypatch.setattr(
        "pinnpcm.solvers.geophase_phase1_v2_controller_v2.attempt_s2_embedded_interval",
        fake_attempt,
    )
    with pytest.raises(RuntimeError, match="locked outer floor"):
        simulate_s2_protocol_v2(
            state,
            protocol=config["formal_protocols"]["protocols"]["zero_drive"],
            protocol_id="zero_drive",
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            final_time_s=1.0e-8,
        )
    assert len(attempted) == 11
    assert attempted[0] == pytest.approx(1.0e-8)
    assert attempted[-1] == pytest.approx(9.765625e-12)
    assert all(value >= attempted[-1] for value in attempted)


def test_below_floor_forced_remainder_is_attempted_once(
    context, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, grid, fields, closure, _cache, state, template = context
    attempted: list[float] = []

    def fake_attempt(current, *, outer_interval_s, rejection_index, **_kwargs):
        attempted.append(outer_interval_s)
        return _observation_from_template(
            template,
            current,
            outer_interval_s,
            accepted=False,
            e_max=0.03,
            rejection_index=rejection_index,
        )

    monkeypatch.setattr(
        "pinnpcm.solvers.geophase_phase1_v2_controller_v2.attempt_s2_embedded_interval",
        fake_attempt,
    )
    with pytest.raises(RuntimeError, match="forced remainder failed closed"):
        simulate_s2_protocol_v2(
            state,
            protocol=config["formal_protocols"]["protocols"]["zero_drive"],
            protocol_id="zero_drive",
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            final_time_s=0.5 * 9.765625e-12,
        )
    assert len(attempted) == 1


def test_formal_count_and_historical_controller_are_unchanged(context) -> None:
    config = context[0]
    base = resolve_controller_v2(BASE_PATH, OVERLAY_PATH).base_config
    assert base["reference_solver"]["time_grid"][
        "maximum_rejected_steps_per_accepted_step"
    ] == 6
    assert config["reference_solver"]["active_time_controller"][
        "outer_interval"
    ]["outer_rejection_cap"] == 10
    assert config["execution_contract"]["formal_execution_count"] == 0
