"""Multidomain OASIS-PINN actual-autograd smoke audit."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.pinn.oasis_components import DifferentiablePortCircuit, InterfaceMortarLoss, LayerExperts, OrderedStackEncoder, generic_pcm_sigma
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/multidomain_oasis_pinn_summary.json")


def run_multidomain_oasis_pinn(seed: int = 2026) -> dict[str, object]:
    torch.manual_seed(seed)
    n = 12
    layers = 4
    coords = torch.rand(n, 3, requires_grad=True)
    features = torch.tensor([[[18e-9, 5e5, 20.0, 0.0], [30e-9, 2.5e2, 1.4, 1.0], [15e-9, 5e-2, 0.45, 2.0], [120e-9, 1e-9, 2.1, 3.0]]], dtype=torch.float32)
    role_ids = torch.tensor([[0, 1, 2, 3]], dtype=torch.long)
    encoder = OrderedStackEncoder(in_dim=4, embed_dim=10, max_layers=8, role_count=8)
    experts = LayerExperts(coord_dim=3, embed_dim=10, hidden_dim=14, layers=layers, pcm_mask=torch.tensor([False, True, False, False]))
    emb = encoder(features, role_ids)
    fields = experts(coords, emb, V_left=0.1, V_right=0.0)
    sigma = generic_pcm_sigma(fields["T"], torch.clamp(fields["m"], 0.0, 1.0), sigma_ins0=1.0e-2, sigma_met0=1.0e2)
    sigma = torch.where(torch.tensor([False, True, False, False], device=sigma.device)[None, :], sigma, torch.full_like(sigma, 10.0))
    mortar = InterfaceMortarLoss(torch.tensor([18e-9, 30e-9, 15e-9, 120e-9]), torch.tensor([20.0, 1.4, 0.45, 2.1]), Rc_ohm_m2=torch.tensor([0.0, 2.5e-10, 0.0]), Rth_m2K_W=torch.tensor([0.0, 2.0e-8, 0.0]))
    losses = mortar(fields["phi"], fields["T"], sigma)
    port = DifferentiablePortCircuit(port_solver="series_stack", layer_thickness_m=torch.tensor([18e-9, 30e-9, 15e-9, 120e-9]))(sigma, torch.ones(n) * 0.1)
    total = port["I"].square().mean() + sum(losses.values()) + 1.0e-8 * port["Q_J"].mean()
    total.backward()
    finite = bool(torch.isfinite(total).item() and torch.isfinite(coords.grad).all().item())
    summary = {
        "benchmark": "multidomain_oasis_pinn_smoke",
        "note": "Synthetic numerical actual-autograd smoke for ordered multidomain OASIS-PINN components; not performance evidence.",
        "finite_loss": finite,
        "used_ordered_stack_encoder": True,
        "used_mean_pooling_main_path": False,
        "used_layer_experts": True,
        "used_hard_dirichlet_transform": True,
        "used_interface_mortar_loss": True,
        "used_series_stack_port": port["port_solver"] == "series_stack",
        "loss_value": float(total.detach().cpu()),
        "mortar_losses": {k: float(v.detach().cpu()) for k, v in losses.items()},
        "sigma_min": float(torch.min(sigma).detach().cpu()),
        "sigma_max": float(torch.max(sigma).detach().cpu()),
        "status": "qualified_supported" if finite else "failed_but_informative",
        "forbidden_claims": ["performance superiority", "experimental validation", "full hidden-field recovery"],
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(run_multidomain_oasis_pinn())


if __name__ == "__main__":
    main()
