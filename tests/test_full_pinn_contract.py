"""Behavioral tests for the versioned N0 full-PINN contract."""

from __future__ import annotations

import numpy as np
import torch

from pinnpcm.physics.params import default_gt_params, initial_defect_profile
from pinnpcm.pinn.full_pinn_1d import EventLedgerState, FullPINN1D, update_event_ledger


def _model() -> FullPINN1D:
    return FullPINN1D(params=default_gt_params(), hidden_dim=16, hidden_layers=1, fourier_scales=(1.0,), seed=7)


def test_full_pinn_has_state_network_and_physical_conductivity_closure() -> None:
    model = _model()
    contract = model.contract()
    assert contract["states"] == ["phi", "c_v", "T", "m"]
    assert contract["independent_log_sigma_output"] is False
    assert "sigma" not in model.state_names
    fields = model(torch.tensor([[0.25, 0.4], [0.75, 0.4]], dtype=torch.float32))
    assert fields["sigma"].shape == (2, 1)
    assert torch.all(fields["sigma"] > 0)


def test_hard_electrical_boundaries_and_frozen_initial_conditions() -> None:
    model = _model()
    t = torch.linspace(0.0, 1.0, 21).reshape(-1, 1)
    left = model(torch.cat([torch.zeros_like(t), t], dim=-1))
    right = model(torch.cat([torch.ones_like(t), t], dim=-1))
    assert torch.max(torch.abs(left["phi"])).item() < 1.0e-7
    assert torch.max(torch.abs(right["phi"] - model.voltage(t))).item() < 1.0e-7

    x = torch.linspace(0.0, 1.0, 41).reshape(-1, 1)
    initial = model(torch.cat([x, torch.zeros_like(x)], dim=-1))
    expected = initial_defect_profile(x.numpy().reshape(-1) * model.params["L_eff"], model.params)
    np.testing.assert_allclose(initial["c_v"].detach().numpy().reshape(-1), expected, rtol=0.0, atol=2.0e-7)
    assert torch.max(torch.abs(initial["T"] - model.params["T0"])).item() < 1.0e-7


def test_terminal_operator_is_series_resistance_integral() -> None:
    model = _model()
    sigma = torch.full((3, 11), 2.0, dtype=torch.float64)
    voltage = torch.tensor([-0.2, 0.0, 0.2], dtype=torch.float64)
    port = model.port_observation(sigma, voltage)
    expected_r_area = model.params["L_eff"] / 2.0
    expected_area = model.params["eta_A"] * model.params["A_contact"]
    torch.testing.assert_close(port["R_area"], torch.full((3,), expected_r_area, dtype=torch.float64))
    torch.testing.assert_close(port["I"], expected_area * voltage / expected_r_area)


def test_event_ledger_is_explicit_and_records_reversal() -> None:
    state = EventLedgerState(
        branch="heating",
        reversal_temperature_K=325.0,
        reversal_phase=0.0,
        previous_temperature_K=330.0,
    )
    unchanged = update_event_ledger(state, temperature_K=330.005, phase=0.1)
    assert unchanged.branch == "heating"
    changed = update_event_ledger(unchanged, temperature_K=329.98, phase=0.2)
    assert changed.branch == "cooling"
    assert changed.reversal_temperature_K == 329.98
    assert changed.reversal_phase == 0.2
