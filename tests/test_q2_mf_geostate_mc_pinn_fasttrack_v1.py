from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import (
    GeoStateCase,
    build_reference_context,
    independent_ledger_reconstruction,
    load_yaml,
    solve_constant_property_electrical,
    solve_reference_case,
)
from pinnpcm.experiments.geostate_training import build_model


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/q2_mf_geostate_mc_pinn_fasttrack_v1.yaml"


def _context():
    config = load_yaml(CONFIG_PATH)
    return config, build_reference_context(config, ROOT)


def test_zero_bias_limit_is_exact() -> None:
    config, context = _context()
    case = GeoStateCase(
        case_id="zero_bias",
        branch_label="heating-conditioned",
        branch_value=1.0,
        device_voltage_V=0.0,
        state_coordinate=0.5,
        thermal_condition="nominal",
        sink_amplitude=0.0,
    )
    result = solve_reference_case(context, "M0", case)
    assert np.max(np.abs(result.fields["potential_V"])) < 1.0e-14
    assert np.max(np.abs(result.fields["temperature_K"] - context.ambient_temperature_K)) < 1.0e-10
    for name in ("Jx_A_m", "Jy_A_m", "qx_W_m", "qy_W_m"):
        assert np.max(np.abs(result.fields[name])) < 1.0e-8
    assert bool(result.metrics["converged"])


def test_constant_property_manufactured_linear_potential_and_current() -> None:
    _, context = _context()
    solution = solve_constant_property_electrical(context, 500.0, 1.2)
    expected = 1.2 * (1.0 - context.grid.x_centers_m / context.length_m)
    expected = np.broadcast_to(expected[None, :], context.grid.shape)
    relative_l2 = np.linalg.norm(solution["potential_V"] - expected) / np.linalg.norm(expected)
    assert relative_l2 < 1.0e-12
    assert solution["current_imbalance"] < 1.0e-12
    assert solution["terminal_field_error"] < 1.0e-12


def test_hard_electrode_bc_and_interface_normal_flux_check() -> None:
    config, context = _context()
    model = build_model("M0", context, config)
    for parameter in model.parameters():
        parameter.data.zero_()
    voltage_norm = 0.6
    boundary = torch.tensor(
        [
            [0.0, 0.3, voltage_norm, 1.0, 0.5, 0.0],
            [1.0, 0.7, voltage_norm, 1.0, 0.5, 0.0],
        ],
        dtype=torch.float32,
    )
    fields = model.field_outputs(boundary)
    assert torch.allclose(
        fields["phi_V"][0],
        torch.tensor([voltage_norm * model.scales.voltage_V]),
        rtol=0.0,
        atol=1.0e-7,
    )
    assert torch.allclose(
        fields["phi_V"][1], torch.tensor([0.0]), rtol=0.0, atol=0.0
    )

    overlap = model.contact_overlap_fraction
    minus = torch.tensor(
        [[overlap - 1.0e-4, 0.5, voltage_norm, 1.0, 0.5, 0.0]],
        dtype=torch.float32,
        requires_grad=True,
    )
    plus = torch.tensor(
        [[overlap + 1.0e-4, 0.5, voltage_norm, 1.0, 0.5, 0.0]],
        dtype=torch.float32,
        requires_grad=True,
    )
    _, parts = model.interface_loss(minus, plus)
    assert float(parts["normal_flux_continuity"].detach()) < 1.0e-12


def test_independent_port_and_energy_ledger_reconstruction() -> None:
    _, context = _context()
    case = GeoStateCase(
        case_id="ledger_check",
        branch_label="cooling-conditioned",
        branch_value=-1.0,
        device_voltage_V=0.75,
        state_coordinate=0.2,
        thermal_condition="localized-sink",
        sink_amplitude=0.5,
    )
    result = solve_reference_case(context, "M0", case)
    ledger = independent_ledger_reconstruction(result)
    assert ledger["terminal_field_error"] < 1.0e-10
    assert ledger["field_sink_error"] < 1.0e-7


def test_mixed_pinn_forward_backward_is_finite() -> None:
    config, context = _context()
    model = build_model("M0", context, config)
    inputs = torch.tensor(
        [
            [0.2, 0.3, 0.5, 1.0, 0.4, 0.0],
            [0.5, 0.6, 0.8, -1.0, 0.7, 1.5],
            [0.8, 0.2, 1.0, 1.0, 0.9, 0.0],
        ],
        dtype=torch.float32,
        requires_grad=True,
    )
    groups = model.residual_groups(inputs)
    loss = torch.stack([torch.mean(value.square()) for value in groups.values()]).sum()
    assert torch.isfinite(loss)
    loss.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    assert gradients
    assert all(torch.isfinite(gradient).all() for gradient in gradients)
