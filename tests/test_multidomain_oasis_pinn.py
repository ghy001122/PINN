from __future__ import annotations

from pathlib import Path

import torch

from pinnpcm.pinn.oasis_components import InterfaceMortarLoss, LayerExperts, OrderedStackEncoder
import scripts.audit_multidomain_oasis_pinn as audit


def test_ordered_stack_encoder_and_layer_experts_backward() -> None:
    coords = torch.rand(5, 3, requires_grad=True)
    features = torch.rand(1, 4, 4)
    role_ids = torch.tensor([[0, 1, 2, 3]], dtype=torch.long)
    encoder = OrderedStackEncoder(in_dim=4, embed_dim=8, max_layers=6, role_count=8)
    experts = LayerExperts(coord_dim=3, embed_dim=8, hidden_dim=10, layers=4, pcm_mask=torch.tensor([False, True, False, False]))
    emb = encoder(features, role_ids)
    fields = experts(coords, emb, V_left=0.2, V_right=0.0)
    assert emb.shape == (1, 4, 8)
    assert fields["phi"].shape == (5, 4)
    assert fields["T"].shape == (5, 4)
    boundary_coords = coords.detach().clone()
    boundary_coords[:, 0] = 0.0
    left = experts(boundary_coords, emb, V_left=0.2, V_right=0.0)["phi"]
    boundary_coords[:, 0] = 1.0
    right = experts(boundary_coords, emb, V_left=0.2, V_right=0.0)["phi"]
    assert torch.allclose(left[:, 0], torch.full((5,), 0.2), atol=1.0e-6)
    assert torch.allclose(right[:, -1], torch.zeros(5), atol=1.0e-6)
    assert torch.all(fields["m"][:, 0] == 0.0)
    loss = fields["T"].mean() + fields["m"].mean() + fields["phi"].mean()
    loss.backward()
    assert coords.grad is not None
    assert torch.isfinite(coords.grad).all()


def test_interface_mortar_loss_finite() -> None:
    phi = torch.linspace(0.1, 0.0, 4).repeat(6, 1).requires_grad_(True)
    T = torch.full((6, 4), 302.0, requires_grad=True)
    sigma = torch.full((6, 4), 0.05)
    mortar = InterfaceMortarLoss(torch.ones(4) * 1.0e-8, torch.ones(4), Rc_ohm_m2=torch.ones(3) * 1.0e-10, Rth_m2K_W=torch.ones(3) * 1.0e-8)
    losses = mortar(phi, T, sigma)
    total = sum(losses.values())
    assert torch.isfinite(total)
    total.backward()
    assert phi.grad is not None


def test_multidomain_oasis_pinn_script_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    summary = audit.run_multidomain_oasis_pinn(seed=2026)
    assert summary["finite_loss"] is True
    assert summary["used_ordered_stack_encoder"] is True
    assert summary["used_mean_pooling_main_path"] is False
    assert summary["used_layer_experts"] is True
    assert summary["used_interface_mortar_loss"] is True
    assert summary["status"] == "qualified_supported"
    assert (tmp_path / "summary.json").exists()
