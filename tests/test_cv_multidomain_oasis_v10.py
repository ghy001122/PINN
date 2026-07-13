from __future__ import annotations

from pathlib import Path

import torch

from pinnpcm.pinn.oasis_components import control_volume_residuals, one_sided_interface_mortar
import scripts.train_cv_multidomain_oasis_v10 as train


def test_control_volume_residuals_are_differentiable() -> None:
    phi = torch.linspace(1.0, 0.0, 3).reshape(1, 3, 1).repeat(4, 1, 2).requires_grad_()
    T = (torch.ones(4, 3, 2) * 305.0).requires_grad_()
    m = (torch.ones(4, 3, 2) * 0.2).requires_grad_()
    sigma = torch.tensor([1e5, 20.0, 1e5]).reshape(1, 3, 1).repeat(4, 1, 2)
    losses = control_volume_residuals(
        phi, T, m, sigma, torch.ones(4), torch.zeros(4), dt_s=1e-7, dy_m=1e-7,
        dz_m=torch.tensor([10e-9, 20e-9, 10e-9]), k_w_mk=torch.tensor([20.0, 1.4, 20.0]),
        rho_c_j_m3k=torch.tensor([2e6, 2e6, 2e6]), Rc_ohm_m2=torch.tensor([1e-10, 1e-10]),
        Rth_m2K_W=torch.tensor([1e-8, 1e-8]), electrical_layers=3, area_m2=1e-12,
        T0_K=300.0, h_top_w_m2k=1e4, h_sub_w_m2k=1e5, tau_m_s=1e-6,
        Tc_up_K=310.0, Tc_down_K=305.0, transition_width_K=2.0,
    )
    total = sum(value for key, value in losses.items() if key.endswith("loss"))
    total.backward()
    assert phi.grad is not None and torch.isfinite(phi.grad).all()
    assert T.grad is not None and torch.isfinite(T.grad).all()


def test_one_sided_mortar_is_not_identity_zero() -> None:
    x = torch.tensor([1.0], requires_grad=True)
    losses = one_sided_interface_mortar(x, x * 0.8, 305 * x, 300 * x, x * 2, -x, x * 3, -x * 2, x * 10, x * 20, x, x, x * 1e-10, x * 1e-8)
    assert float(sum(losses.values())) > 0.0


def test_cv_training_smoke_writes_strict_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(train, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(train, "CASES_CSV", tmp_path / "cases.csv")
    summary = train.run_cv_multidomain_oasis(epochs=2, seeds=(2026,))
    assert summary["uses_actual_cv_residuals"] is True
    assert summary["uses_target_non_pcm_sigma"] is False
    assert "loss decrease alone" in summary["success_definition"]
    assert (tmp_path / "summary.json").exists()
