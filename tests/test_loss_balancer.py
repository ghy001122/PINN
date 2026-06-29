from __future__ import annotations

import torch

from pinnpcm.pinn.loss_balancer import DynamicResidualGate, gated_residual_loss


def test_dynamic_residual_gate_weights_normalized_and_positive() -> None:
    gate = DynamicResidualGate(3, tau=2.5, min_weight=0.09, entropy_weight=1.0e-3)
    residuals = [torch.ones(8, 1), 2.0 * torch.ones(8, 1), 3.0 * torch.ones(8, 1)]
    out = gate(residuals)
    weights = out["weights"]
    assert weights.shape == (3,)
    assert torch.all(weights > 0.0)
    assert torch.isclose(weights.sum(), torch.tensor(1.0), atol=1.0e-6)
    assert torch.all(torch.isfinite(out["total"]))


def test_dynamic_residual_gate_anti_collapse_under_extreme_scales() -> None:
    gate = DynamicResidualGate(3, tau=3.0, min_weight=0.12, entropy_weight=1.0e-3)
    residuals = [1.0e-9 * torch.ones(16), 1.0e9 * torch.ones(16), torch.ones(16)]
    out = gate(residuals)
    weights = out["weights"]
    assert torch.all(weights >= (0.12 / 3.0) - 1.0e-7)
    assert torch.max(weights) < 0.95
    assert torch.min(weights) > 0.0
    assert torch.isclose(weights.sum(), torch.tensor(1.0), atol=1.0e-6)


def test_gated_residual_loss_backward_is_finite() -> None:
    residuals = [torch.randn(12, requires_grad=True), torch.randn(12, requires_grad=True)]
    gate = DynamicResidualGate(2, tau=2.0, min_weight=0.05)
    out = gated_residual_loss(residuals, gate=gate)
    out["total"].backward()
    for residual in residuals:
        assert residual.grad is not None
        assert torch.all(torch.isfinite(residual.grad))
    assert gate.logits.grad is not None
    assert torch.all(torch.isfinite(gate.logits.grad))