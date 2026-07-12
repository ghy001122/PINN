from __future__ import annotations

from pathlib import Path

import torch

from pinnpcm.pinn.oasis_components import InterfaceMortarLoss
import scripts.train_multidomain_oasis_v9 as train


def test_interface_mortar_loss_not_identity_zero() -> None:
    phi = torch.tensor([[0.2, 0.13, 0.04]], dtype=torch.float32, requires_grad=True)
    T = torch.tensor([[306.0, 302.0, 300.5]], dtype=torch.float32, requires_grad=True)
    sigma = torch.tensor([[2.0, 40.0, 1.0e4]], dtype=torch.float32)
    mortar = InterfaceMortarLoss(torch.tensor([18e-9, 30e-9, 15e-9]), torch.tensor([20.0, 1.4, 0.35]), Rc_ohm_m2=torch.tensor([1e-10, 2e-10]), Rth_m2K_W=torch.tensor([1e-8, 2e-8]))
    losses = mortar(phi, T, sigma)
    assert float(losses["current_mortar_loss"]) > 0.0
    assert float(losses["heat_flux_mortar_loss"]) > 0.0
    total = sum(losses.values())
    total.backward()
    assert phi.grad is not None


def test_multidomain_training_v9_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(train, "SUMMARY_JSON", tmp_path / "summary.json")
    summary = train.run_multidomain_oasis_training(epochs=2)
    assert summary["uses_activated_case"] is True
    assert len(summary["variants"]) == 4
    assert any(row["variant"] == "full_mortar" for row in summary["variants"])
    assert all(row["finite_loss"] for row in summary["variants"])
    assert (tmp_path / "summary.json").exists()
