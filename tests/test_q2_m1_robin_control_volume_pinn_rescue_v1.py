from __future__ import annotations

from pathlib import Path
from types import MethodType

import numpy as np
import torch

from pinnpcm.experiments.geostate_fasttrack import (
    _solve_electrical_robin,
    build_reference_context,
    load_yaml,
)
from pinnpcm.experiments.geostate_m1_compatibility import (
    M1TeacherCase,
    load_teacher_case,
    m1_vertical_conductance,
    reconstruct_conservative_teacher,
)
from pinnpcm.experiments.geostate_m1_rcv_training import build_model, case_inputs


ROOT = Path(__file__).resolve().parents[1]
RESCUE_CONFIG = load_yaml(ROOT / "configs/q2_m1_robin_control_volume_pinn_rescue_v1.yaml")
BASE_CONFIG = load_yaml(ROOT / RESCUE_CONFIG["reference"]["config"])
CONTEXT = build_reference_context(BASE_CONFIG, ROOT)


def _one_case() -> M1TeacherCase:
    path = sorted((ROOT / RESCUE_CONFIG["reference"]["data_root"]).glob("*.npz"))[0]
    return load_teacher_case(path)


def test_zero_bias_phi_current_and_contact_joule_are_exact() -> None:
    model = build_model("P0-RCV", CONTEXT, RESCUE_CONFIG, BASE_CONFIG)
    case = _one_case()
    zero = M1TeacherCase(
        **{
            **case.__dict__,
            "device_voltage_V": 0.0,
        }
    )
    y = np.linspace(0.05, 0.95, 8)
    inputs = case_inputs(zero, np.linspace(0.1, 0.9, 8), y, model, requires_grad=True)
    fields = model.field_outputs(inputs)
    assert torch.count_nonzero(fields["phi_V"]).item() == 0
    assert torch.count_nonzero(fields["Jx_A_m"]).item() == 0
    assert torch.count_nonzero(fields["Jy_A_m"]).item() == 0
    left = case_inputs(zero, np.zeros(8), y, model, requires_grad=True)
    right = case_inputs(zero, np.ones(8), y, model, requires_grad=True)
    _, _, ledger = model.port_and_ledger(
        left, right, inputs, torch.as_tensor(0.0, dtype=torch.float64)
    )
    assert float(ledger["contact_joule_W"].detach()) == 0.0


def test_m1_robin_constant_sigma_matches_series_resistance() -> None:
    sigma = 500.0
    voltage = 1.2
    rc = {"left": 5.0, "right": 5.0}
    result = _solve_electrical_robin(
        CONTEXT, np.full(CONTEXT.grid.shape, sigma), voltage, rc
    )
    device_resistance = CONTEXT.length_m / (
        sigma * CONTEXT.grid.thickness_m * CONTEXT.width_m
    )
    expected_current = voltage / (device_resistance + rc["left"] + rc["right"])
    assert np.isclose(result["source_current_A"], expected_current, rtol=1.0e-12)
    source_surface = voltage - result["source_current_A"] * rc["left"]
    assert np.isclose(
        voltage - source_surface,
        result["source_current_A"] * rc["left"],
        rtol=0.0,
        atol=1.0e-15,
    )


def test_m1_thermal_contact_closure_modifies_only_contact_mask() -> None:
    case = load_teacher_case(
        ROOT
        / RESCUE_CONFIG["reference"]["data_root"]
        / "cooling_high_nominal.npz"
    )
    conductance, _ = m1_vertical_conductance(CONTEXT, case, BASE_CONFIG)
    nominal = float(CONTEXT.thermal_fields.vertical_conductance_W_m2K)
    rth = float(
        BASE_CONFIG["physical_model"]["model_forms"]["M1"]
        ["thermal_contact_resistance_m2K_W"]["left"]
    )
    expected_contact = 1.0 / (1.0 / nominal + rth)
    assert np.allclose(conductance[CONTEXT.grid.contact_mask], expected_contact)
    assert np.allclose(conductance[CONTEXT.grid.bare_mask], nominal)


def test_control_volume_manufactured_constant_current_is_conservative() -> None:
    model = build_model("P0-RCV", CONTEXT, RESCUE_CONFIG, BASE_CONFIG)
    case = _one_case()

    def analytic_fields(self, inputs, *, region_override=None):
        x = inputs[:, 0:1]
        phi = inputs[:, 2:3] * self.voltage_scale_V * (1.0 - x)
        zeros = torch.zeros_like(x)
        return {
            "phi_V": phi,
            "T_K": torch.full_like(x, self.ambient_temperature_K),
            "Jx_A_m": torch.full_like(x, 123.0),
            "Jy_A_m": zeros,
            "qx_W_m": zeros,
            "qy_W_m": zeros,
            "sigma_S_m": torch.full_like(x, 500.0),
            "dphi_dx": torch.full_like(x, -self.voltage_scale_V / self.length_m),
            "dphi_dy": zeros,
            "dT_dx": zeros,
            "dT_dy": zeros,
        }

    model.field_outputs = MethodType(analytic_fields, model)
    bounds = torch.tensor(
        [[0.30, 0.40, 0.20, 0.30], [0.50, 0.60, 0.60, 0.70]],
        dtype=torch.float64,
    )
    centers = 0.5 * (bounds[:, [0, 2]] + bounds[:, [1, 3]])
    base = case_inputs(case, centers[:, 0].numpy(), centers[:, 1].numpy(), model)
    current, _ = model.control_volume_residuals(
        base, bounds, torch.ones(2, dtype=torch.long)
    )
    assert float(torch.max(torch.abs(current))) < 1.0e-14


def test_interface_metric_uses_the_same_two_trace_definition() -> None:
    model = build_model("P0-RCV", CONTEXT, RESCUE_CONFIG, BASE_CONFIG)
    model.region_heads[1].load_state_dict(model.region_heads[0].state_dict())
    model.region_heads[2].load_state_dict(model.region_heads[0].state_dict())
    case = _one_case()
    y = np.linspace(0.05, 0.95, 10)
    ids = np.arange(10) % 2
    x = np.where(ids == 0, model.contact_fraction, 1.0 - model.contact_fraction)
    inputs = case_inputs(case, x, y, model, requires_grad=True)
    state, flux, metrics = model.interface_terms(
        inputs, torch.as_tensor(ids, dtype=torch.long)
    )
    assert float(state.detach()) < 1.0e-24
    assert float(flux.detach()) < 1.0e-24
    assert float(metrics["metric"].detach()) < 1.0e-12


def test_teacher_parser_reconstructs_finite_conservative_faces() -> None:
    case = _one_case()
    row, fields = reconstruct_conservative_teacher(CONTEXT, case, BASE_CONFIG)
    assert bool(row["finite"])
    assert fields.electrical_x_face_current_A.shape == (
        CONTEXT.grid.ny,
        CONTEXT.grid.nx + 1,
    )
    assert fields.thermal_y_face_power_W.shape == (
        CONTEXT.grid.ny + 1,
        CONTEXT.grid.nx,
    )
    assert np.isfinite(fields.normalized_energy_residual).all()
