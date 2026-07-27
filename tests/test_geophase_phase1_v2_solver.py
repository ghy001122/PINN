from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_ledgers import require_ledger_gate
from pinnpcm.physics.geophase_s2_ledgers import build_s2_ledgers
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    derive_nominal_s2_source_scale,
    effective_vo2_closure_from_v2_config,
    s2_uniform_mode_identities,
)
from pinnpcm.solvers.geophase_2p5d_fvm import SheetElectricalSolution
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    assemble_sheet_thermal_matrix,
    reconstruct_lateral_fluxes,
    solve_s2_thermal_backward_euler,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as implicit


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def grid(config: dict):
    # Preserve the locked 10 nm x-face alignment while shortening y for tests.
    return build_geophase_grid(config, nx_override=10, ny_override=2)


@pytest.fixture(scope="module")
def fields(grid, config: dict):
    return build_s2_thermal_fields(grid, config)


@pytest.fixture(scope="module")
def closure(config: dict):
    return effective_vo2_closure_from_v2_config(config)


def _state_at(
    template: implicit.S2State,
    *,
    time_s: float,
    branch_value: float | None = None,
) -> implicit.S2State:
    branch = (
        template.branch_memory.copy()
        if branch_value is None
        else np.full_like(template.branch_memory, branch_value)
    )
    return implicit.S2State(
        time_s=float(time_s),
        temperature_K=template.temperature_K.copy(),
        conductive_state=template.conductive_state.copy(),
        branch_memory=branch,
        device_voltage_V=float(template.device_voltage_V),
    )


def _mock_step(
    old_state: implicit.S2State,
    dt_s: float,
    *,
    branch_increment: float = 0.0,
    method: str = "damped_newton_krylov",
):
    state = implicit.S2State(
        time_s=old_state.time_s + dt_s,
        temperature_K=old_state.temperature_K.copy(),
        conductive_state=old_state.conductive_state.copy(),
        branch_memory=old_state.branch_memory + branch_increment,
        device_voltage_V=old_state.device_voltage_V,
    )
    return SimpleNamespace(state=state, nonlinear=SimpleNamespace(method=method))


def test_s2_source_scale_identities_and_masks(config: dict, grid, fields) -> None:
    scale = derive_nominal_s2_source_scale(config)
    identities = s2_uniform_mode_identities(grid, fields)
    preflights = config["analytic_source_scale_preflights"]

    assert scale["nominal_memory_coefficient_J_K"] > 0.0
    assert identities["memory_coefficient_positive"] is True
    assert identities["nominal_overlap"] is True
    assert identities["capacity_identity_voting"] is True
    assert identities["capacity_relative_error"] <= preflights[
        "area_integrated_explicit_plus_memory_coefficient_relative_error_max"
    ]
    assert identities["conductance_relative_error"] <= preflights[
        "area_integrated_dc_thermal_conductance_relative_error_max"
    ]

    expected_explicit = (
        fields.vo2_areal_capacity_J_m2K
        + grid.contact_mask.astype(float) * fields.electrode_areal_capacity_J_m2K
    )
    expected_sheet = (
        fields.vo2_sheet_conductance_W_K
        + grid.contact_mask.astype(float) * fields.electrode_sheet_conductance_W_K
    )
    np.testing.assert_allclose(
        fields.explicit_areal_capacity_J_m2K, expected_explicit, rtol=1.0e-12
    )
    np.testing.assert_allclose(
        fields.sheet_thermal_conductance_W_K, expected_sheet, rtol=1.0e-12
    )
    np.testing.assert_allclose(
        fields.effective_areal_capacity_J_m2K,
        expected_explicit + fields.memory_areal_coefficient_J_m2K,
        rtol=1.0e-12,
    )


@pytest.mark.parametrize("overlap_m", [1.0e-8, 3.0e-8])
def test_contact_overlap_audits_freeze_nominal_memory_scale(
    config: dict, fields, overlap_m: float
) -> None:
    audit_grid = build_geophase_grid(
        config, contact_overlap_m=overlap_m, nx_override=10, ny_override=2
    )
    audit_fields = build_s2_thermal_fields(audit_grid, config)
    identities = s2_uniform_mode_identities(audit_grid, audit_fields)

    assert audit_fields.memory_areal_coefficient_J_m2K == pytest.approx(
        fields.memory_areal_coefficient_J_m2K, rel=0.0, abs=0.0
    )
    assert audit_fields.vertical_conductance_W_m2K == pytest.approx(
        fields.vertical_conductance_W_m2K, rel=0.0, abs=0.0
    )
    assert identities["nominal_overlap"] is False
    assert identities["capacity_identity_voting"] is False
    assert np.count_nonzero(audit_grid.contact_mask) != np.count_nonzero(
        build_geophase_grid(config, nx_override=10, ny_override=2).contact_mask
    )


def test_single_thermal_step_closes_all_ledgers_and_tamper_fails(
    config: dict, grid, fields
) -> None:
    ambient = fields.ambient_temperature_K
    old_temperature = np.full(grid.shape, ambient, dtype=float)
    dt_s = 1.0e-6
    old_voltage = 0.0
    new_voltage = 0.1
    device_current = 1.0e-6
    device_power = new_voltage * device_current
    joule_cells = np.full(grid.shape, device_power / (grid.nx * grid.ny))
    matrix = assemble_sheet_thermal_matrix(
        grid, fields.sheet_thermal_conductance_W_K
    )
    new_temperature = solve_s2_thermal_backward_euler(
        grid,
        fields,
        old_temperature,
        joule_cells,
        dt_s,
        lateral_matrix=matrix,
    )
    flux = reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        new_temperature,
        matrix=matrix,
    )

    circuit = config["physics_contract"]["circuit"]
    load = float(circuit["load_resistance_ohm"])
    capacitance = float(circuit["parallel_capacitance_F"])
    source_current = capacitance * (new_voltage - old_voltage) / dt_s + device_current
    input_voltage = new_voltage + load * source_current
    electrical = SheetElectricalSolution(
        potential_V=np.zeros(grid.shape, dtype=float),
        source_current_A=device_current,
        ground_current_A=-device_current,
        cell_joule_power_W=joule_cells,
        joule_power_W=device_power,
        terminal_device_power_W=device_power,
        relative_current_imbalance=0.0,
        relative_power_imbalance=0.0,
    )
    ledgers = build_s2_ledgers(
        grid=grid,
        fields=fields,
        old_temperature_K=old_temperature,
        new_temperature_K=new_temperature,
        old_device_voltage_V=old_voltage,
        new_device_voltage_V=new_voltage,
        input_voltage_V=input_voltage,
        load_resistance_ohm=load,
        capacitance_F=capacitance,
        dt_s=dt_s,
        electrical=electrical,
        lateral_boundary_outflow_W=flux.boundary_outflow_W,
    )
    thresholds = config["gates"]
    require_ledger_gate(
        ledgers.thermal, thresholds["thermal_ledger_relative_residual_max"]
    )
    require_ledger_gate(
        ledgers.circuit, thresholds["circuit_ledger_relative_residual_max"]
    )
    require_ledger_gate(
        ledgers.combined, thresholds["combined_ledger_relative_residual_max"]
    )
    require_ledger_gate(
        ledgers.device_power,
        thresholds["device_power_identity_relative_residual_max"],
    )
    assert ledgers.storage.effective_storage_rate_W == pytest.approx(
        ledgers.storage.explicit_plane_storage_rate_W
        + ledgers.storage.closure_storage_rate_W,
        rel=1.0e-12,
    )

    tampered = replace(electrical, joule_power_W=1.1 * device_power)
    tampered_ledgers = build_s2_ledgers(
        grid=grid,
        fields=fields,
        old_temperature_K=old_temperature,
        new_temperature_K=new_temperature,
        old_device_voltage_V=old_voltage,
        new_device_voltage_V=new_voltage,
        input_voltage_V=input_voltage,
        load_resistance_ohm=load,
        capacitance_F=capacitance,
        dt_s=dt_s,
        electrical=tampered,
        lateral_boundary_outflow_W=flux.boundary_outflow_W,
    )
    with pytest.raises(ValueError, match="ledger failed"):
        require_ledger_gate(
            tampered_ledgers.thermal,
            thresholds["thermal_ledger_relative_residual_max"],
        )
    with pytest.raises(ValueError, match="ledger failed"):
        require_ledger_gate(
            tampered_ledgers.device_power,
            thresholds["device_power_identity_relative_residual_max"],
        )


def test_pulse_drive_is_selected_over_each_clipped_interval(
    monkeypatch: pytest.MonkeyPatch, config: dict, grid, closure, fields
) -> None:
    pulse = config["formal_protocols"]["protocols"]["pulse_12p5V"]
    base_dt = float(config["reference_solver"]["time_grid"]["base_max_step_s"])
    template = implicit.initial_s2_state(grid, closure, fields, config)
    recorded: list[float] = []

    def fake_advance(old_state, *, input_voltage_V, dt_s, **_kwargs):
        recorded.append(float(input_voltage_V))
        return _mock_step(old_state, dt_s)

    monkeypatch.setattr(implicit, "advance_s2_backward_euler", fake_advance)
    cases = (
        (float(pulse["pulse_start_s"]), float(pulse["baseline_voltage_V"])),
        (float(pulse["pulse_stop_s"]), float(pulse["pulse_voltage_V"])),
    )
    for boundary, expected_voltage in cases:
        initial = _state_at(template, time_s=boundary - base_dt)
        result = implicit.simulate_s2_protocol(
            initial,
            protocol=pulse,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            final_time_s=boundary,
            maximum_accepted_steps=1,
        )
        assert result.completed is True
        assert recorded[-1] == pytest.approx(expected_voltage)


def test_branch_memory_increment_controls_adaptive_rejection(
    monkeypatch: pytest.MonkeyPatch, config: dict, grid, closure, fields
) -> None:
    template = implicit.initial_s2_state(grid, closure, fields, config)
    initial = _state_at(template, time_s=0.0, branch_value=0.0)
    # Keep the conductive state valid for the altered branch fixture.
    initial = replace(
        initial,
        conductive_state=closure.equilibrium_state(
            initial.temperature_K, initial.branch_memory
        ),
    )
    attempted_dt: list[float] = []
    branch_rate_per_s = 3.0e6

    def fake_advance(old_state, *, dt_s, **_kwargs):
        attempted_dt.append(float(dt_s))
        return _mock_step(
            old_state, dt_s, branch_increment=branch_rate_per_s * dt_s
        )

    monkeypatch.setattr(implicit, "advance_s2_backward_euler", fake_advance)
    protocol = {"kind": "constant_voltage_step_at_t0", "input_voltage_V": 0.0}
    base_dt = float(config["reference_solver"]["time_grid"]["base_max_step_s"])
    result = implicit.simulate_s2_protocol(
        initial,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=base_dt,
        maximum_accepted_steps=1,
    )

    assert attempted_dt[:2] == pytest.approx([base_dt, 0.5 * base_dt])
    assert result.diagnostics.transition_rejections == 1
    assert result.diagnostics.accepted_steps == 1
    assert result.diagnostics.maximum_transition_increment == pytest.approx(0.015)
    assert result.diagnostics.maximum_transition_increment <= config[
        "reference_solver"
    ]["time_grid"]["transition_increment_threshold"]


def test_decoupled_copy_api_preserves_independent_states_and_protocols(
    monkeypatch: pytest.MonkeyPatch, config: dict, grid, closure, fields
) -> None:
    initial_A = implicit.initial_s2_state(grid, closure, fields, config)
    initial_B = _state_at(initial_A, time_s=0.0, branch_value=-0.25)
    protocol_A = {"kind": "constant_voltage_step_at_t0", "input_voltage_V": 9.0}
    protocol_B = {"kind": "constant_voltage_step_at_t0", "input_voltage_V": 0.0}
    calls: list[tuple[implicit.S2State, dict]] = []

    def fake_simulate(initial_state, *, protocol, **_kwargs):
        calls.append((initial_state, protocol))
        return (id(initial_state), float(protocol["input_voltage_V"]))

    monkeypatch.setattr(implicit, "simulate_s2_protocol", fake_simulate)
    results = implicit.simulate_s2_decoupled_copies(
        initial_state_A=initial_A,
        protocol_A=protocol_A,
        initial_state_B=initial_B,
        protocol_B=protocol_B,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )

    assert len(calls) == 2
    assert calls[0][0] is initial_A
    assert calls[0][1] is protocol_A
    assert calls[1][0] is initial_B
    assert calls[1][1] is protocol_B
    assert results == ((id(initial_A), 9.0), (id(initial_B), 0.0))


def test_zero_drive_analytic_path_is_not_counted_as_fallback(
    config: dict, grid, closure, fields
) -> None:
    initial = implicit.initial_s2_state(grid, closure, fields, config)
    dt_s = float(config["reference_solver"]["time_grid"]["base_max_step_s"])
    step = implicit.advance_s2_backward_euler(
        initial,
        input_voltage_V=0.0,
        dt_s=dt_s,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )
    assert step.nonlinear.method == "analytic_zero_drive_equilibrium"
    assert step.nonlinear.iterations == 0
    assert np.array_equal(step.state.temperature_K, initial.temperature_K)
    assert np.array_equal(step.state.conductive_state, initial.conductive_state)
    assert np.array_equal(step.state.branch_memory, initial.branch_memory)
    for name, threshold in (
        ("thermal", config["gates"]["thermal_ledger_relative_residual_max"]),
        ("circuit", config["gates"]["circuit_ledger_relative_residual_max"]),
        ("combined", config["gates"]["combined_ledger_relative_residual_max"]),
        (
            "device_power",
            config["gates"]["device_power_identity_relative_residual_max"],
        ),
    ):
        require_ledger_gate(getattr(step.ledgers, name), threshold)

    protocol = config["formal_protocols"]["protocols"]["zero_drive"]
    result = implicit.simulate_s2_protocol(
        initial,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=dt_s,
    )
    assert result.completed is True
    assert result.diagnostics.accepted_steps == 1
    assert result.diagnostics.fallback_steps == 0


def test_independent_face_reconstruction_detects_matrix_tamper(
    grid, fields
) -> None:
    x = np.broadcast_to(grid.x_centers_m[None, :], grid.shape)
    y = np.broadcast_to(grid.y_centers_m[:, None], grid.shape)
    temperature = 325.0 + 1.0e7 * x + 2.0e6 * y
    matrix = assemble_sheet_thermal_matrix(
        grid, fields.sheet_thermal_conductance_W_K
    )
    clean = reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        temperature,
        matrix=matrix,
    )
    assert clean.matrix_face_relative_mismatch <= 1.0e-12
    assert clean.matrix_face_roundoff_ratio <= 1.0
    assert abs(clean.internal_pair_cancellation_W) <= 1.0e-18
    assert clean.boundary_outflow_W == 0.0

    tampered = matrix.tolil(copy=True)
    tampered[0, 0] += max(abs(float(matrix[0, 0])), 1.0e-12)
    tampered_audit = reconstruct_lateral_fluxes(
        grid,
        fields.sheet_thermal_conductance_W_K,
        temperature,
        matrix=tampered.tocsr(),
    )
    assert tampered_audit.matrix_face_relative_mismatch > 1.0e-6
    assert tampered_audit.matrix_face_roundoff_ratio > 1.0


def test_phase1v2_solver_has_no_retired_or_pinn_residual_imports() -> None:
    targets = (
        ROOT / "src" / "pinnpcm" / "physics" / "geophase_s2_thermal.py",
        ROOT / "src" / "pinnpcm" / "physics" / "geophase_s2_ledgers.py",
        ROOT / "src" / "pinnpcm" / "solvers" / "geophase_phase1_v2_fvm.py",
        ROOT / "src" / "pinnpcm" / "solvers" / "geophase_phase1_v2_implicit.py",
    )
    forbidden_fragments = (
        "pinnpcm.pinn",
        "vertical_multilayer_reference",
        "vertical_thermal_memory",
        "geophase_2p5d_implicit",
    )
    imported: list[str] = []
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
    assert not any(
        fragment in module
        for module in imported
        for fragment in forbidden_fragments
    ), imported
