"""Behavioral tests for the matched-budget N0-R split-domain PINN."""

from __future__ import annotations

import torch
import pytest

from pinnpcm.physics.params import default_gt_params
from pinnpcm.pinn.full_pinn_1d_split import DualDomainFullPINN1D
from pinnpcm.pinn.full_residuals_1d_split import (
    compute_boundary_terms,
    compute_domain_residuals,
    compute_exact_interface_terms,
    layer_residual_scales,
)


def _model() -> DualDomainFullPINN1D:
    return DualDomainFullPINN1D(
        params=default_gt_params(), hidden_dim_per_domain=32, hidden_layers=3, seed=20260715
    )


def test_split_parameter_budget_is_within_ten_percent_of_v1_baseline() -> None:
    model = _model()
    count = model.parameter_counts()["total"]
    assert count == 5704
    assert abs(count - 5812) / 5812 <= 0.10


def test_split_model_uses_teacher_electrode_orientation_and_hard_initial_states() -> None:
    model = _model()
    t = torch.linspace(0.0, 1.0, 17).reshape(-1, 1)
    boundary = compute_boundary_terms(model, t)
    assert torch.max(torch.abs(boundary["phi_left"])).item() < 1.0e-7
    assert torch.max(torch.abs(boundary["phi_right"])).item() < 1.0e-7

    for domain, x in (("left", torch.linspace(0.0, 1.0, 23)), ("right", torch.linspace(0.0, 1.0, 23))):
        coords = torch.stack([x, torch.zeros_like(x)], dim=-1)
        fields = model.forward_domain(coords, domain)
        expected_c = model.initial_defect_global(fields["global_x_norm"])
        expected_m = model.equilibrium_phase(expected_c, torch.ones_like(expected_c) * model.params["T0"])
        torch.testing.assert_close(fields["c_v"], expected_c, rtol=0.0, atol=2.0e-7)
        torch.testing.assert_close(fields["T"], torch.ones_like(fields["T"]) * model.params["T0"])
        torch.testing.assert_close(fields["m"], expected_m, rtol=0.0, atol=2.0e-7)


def test_exact_interface_uses_independent_one_sided_traces() -> None:
    model = _model()
    t = torch.linspace(0.0, 1.0, 11).reshape(-1, 1)
    terms = compute_exact_interface_terms(model, t)
    assert terms["left"]["fields"]["local_x_norm"].min().item() == 1.0
    assert terms["right"]["fields"]["local_x_norm"].max().item() == 0.0
    assert terms["left"]["fields"]["profiles"]["k_th"][0].item() == pytest.approx(
        model.params["nb_oxide_k_th"], abs=1.0e-7
    )
    assert terms["right"]["fields"]["profiles"]["k_th"][0].item() == pytest.approx(
        model.params["v2o5_k_th"], abs=1.0e-7
    )


def test_layer_scales_include_all_preregistered_physical_terms() -> None:
    model = _model()
    for domain in ("left", "right"):
        scales = layer_residual_scales(model, domain)
        assert set(scales["defect_terms"]) == {"storage", "diffusion", "drift", "reaction"}
        assert set(scales["thermal_terms"]) == {"storage", "conduction", "joule", "sink"}
        assert set(scales["phase_terms"]) == {"storage", "relaxation"}
        assert all(scales[key] > 0.0 for key in ("r_phi", "r_c", "r_T", "r_m"))


def test_split_residuals_are_finite_on_both_domains() -> None:
    model = _model()
    generator = torch.Generator().manual_seed(9)
    for domain in ("left", "right"):
        residuals = compute_domain_residuals(model, torch.rand((24, 2), generator=generator), domain)
        for key in ("r_phi", "r_c", "r_T", "r_m"):
            assert torch.isfinite(residuals[key]).all()
