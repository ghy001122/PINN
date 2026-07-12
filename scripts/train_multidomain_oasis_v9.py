"""Small actual-training audit for multidomain OASIS-PINN v9.

Synthetic numerical digital-twin benchmark evidence only. The goal is a finite
training loop with non-degenerate interface losses, not performance superiority.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.multilayer_sandwich import simulate_phase_activated_multilayer_case
from pinnpcm.pinn.oasis_components import DifferentiablePortCircuit, InterfaceMortarLoss, LayerExperts, OrderedStackEncoder, generic_pcm_sigma
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/multidomain_oasis_training_summary.json")


class MonolithicField(nn.Module):
    def __init__(self, layers: int, hidden: int = 24) -> None:
        super().__init__()
        self.layers = layers
        self.net = nn.Sequential(nn.Linear(3, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 3 * layers))

    def forward(self, coords: torch.Tensor, V_left: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = self.net(coords).reshape(coords.shape[0], self.layers, 3)
        z = coords[:, :1].clamp(0.0, 1.0)
        phi_base = (1.0 - z) * V_left.reshape(-1, 1)
        phi = phi_base + z * (1.0 - z) * raw[..., 0]
        return {"phi": phi, "T": 295.0 + torch.nn.functional.softplus(raw[..., 1]), "m": torch.sigmoid(raw[..., 2])}


def _target_case() -> dict[str, Any]:
    cfg = {"ny": 10, "nt": 24, "V_peak": 10.0, "R_load_ohm": 8.0e3, "vo2_Tc_up_K": 308.0, "vo2_Tc_down_K": 304.0, "vo2_width_K": 1.2, "vo2_sigma_ins": 2.0, "vo2_sigma_met": 8.0e4}
    return simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "vo2", "activation_triangle", 2031, cfg)


def _sample(case: dict[str, Any], n: int = 64, seed: int = 2026) -> dict[str, torch.Tensor]:
    rng = np.random.default_rng(seed)
    T = case["temperature"]
    m = case["state_m"]
    sigma = case["sigma"]
    nt, layers, ny = T.shape
    ti = rng.integers(0, nt, size=n)
    yi = rng.integers(0, ny, size=n)
    coords = np.stack([np.full(n, 0.5), ti / max(nt - 1, 1), yi / max(ny - 1, 1)], axis=1)
    return {
        "coords": torch.tensor(coords, dtype=torch.float32),
        "T": torch.tensor(T[ti, :, yi], dtype=torch.float32),
        "m": torch.tensor(m[ti, yi], dtype=torch.float32),
        "sigma": torch.tensor(sigma[ti, :, yi], dtype=torch.float32),
        "V": torch.tensor(case["voltage_app"][ti], dtype=torch.float32),
        "G": torch.tensor(case["conductance"][ti], dtype=torch.float32),
        "I": torch.tensor(case["current"][ti], dtype=torch.float32),
    }


def _variant_model(name: str, layers: int):
    if name == "monolithic_pinn":
        return MonolithicField(layers), None, False
    features = torch.tensor([[[18e-9, 5e5, 20.0, 0.0], [30e-9, 25.0, 1.4, 1.0], [15e-9, 1e4, 0.35, 2.0], [18e-9, 6e5, 18.0, 3.0], [120e-9, 1e9, 2.1, 4.0]]], dtype=torch.float32)
    role_ids = torch.tensor([[0, 1, 2, 3, 4]], dtype=torch.long)
    encoder = OrderedStackEncoder(in_dim=4, embed_dim=12, max_layers=8, role_count=8)
    experts = LayerExperts(coord_dim=3, embed_dim=12, hidden_dim=20, layers=layers, pcm_mask=torch.tensor([False, True, False, False, False]))
    return nn.ModuleDict({"encoder": encoder, "experts": experts}), (features, role_ids), True


def _forward(model, aux, coords: torch.Tensor, V: torch.Tensor, hard_bc: bool) -> dict[str, torch.Tensor]:
    if aux is None:
        return model(coords, V)
    features, role_ids = aux
    emb = model["encoder"](features.to(coords.device), role_ids.to(coords.device))
    return model["experts"](coords, emb, V_left=V, V_right=0.0)


def _train_variant(name: str, target: dict[str, torch.Tensor], layer_count: int, epochs: int = 10) -> dict[str, Any]:
    torch.manual_seed(2026)
    model, aux, hard_bc = _variant_model(name, layer_count)
    opt = torch.optim.Adam(model.parameters(), lr=0.018)
    thickness = torch.tensor([18e-9, 30e-9, 15e-9, 18e-9, 120e-9], dtype=torch.float32)[:layer_count]
    k = torch.tensor([20.0, 1.4, 0.35, 18.0, 2.1], dtype=torch.float32)[:layer_count]
    port = DifferentiablePortCircuit(port_solver="series_stack", layer_thickness_m=thickness)
    mortar = InterfaceMortarLoss(thickness, k, Rc_ohm_m2=torch.tensor([1.2e-10, 2.4e-10, 0.9e-10, 0.2e-10])[:max(layer_count-1,0)], Rth_m2K_W=torch.tensor([0.8e-8, 3.4e-8, 2.2e-8, 4.0e-8])[:max(layer_count-1,0)])
    losses: list[float] = []
    start = time.perf_counter()
    for _ in range(epochs):
        opt.zero_grad(set_to_none=True)
        fields = _forward(model, aux, target["coords"], target["V"], hard_bc)
        m_all = fields["m"]
        sigma_pred = generic_pcm_sigma(fields["T"], m_all, sigma_ins0=2.0, sigma_met0=8.0e4)
        non_pcm_mask = torch.tensor([True, False, True, True, True], dtype=torch.bool)[:layer_count]
        sigma_pred = torch.where(non_pcm_mask.reshape(1, -1), target["sigma"].mean(dim=0, keepdim=True).expand_as(sigma_pred), sigma_pred)
        port_pred = port(sigma_pred, target["V"])
        field_loss = torch.mean(((fields["T"] - target["T"]) / 20.0).square()) + torch.mean((fields["m"][:, 1] - target["m"]).square())
        port_loss = torch.mean(((port_pred["G"] - target["G"]) / torch.clamp(torch.max(torch.abs(target["G"])), min=1e-12)).square()) + torch.mean(((port_pred["I"] - target["I"]) / torch.clamp(torch.max(torch.abs(target["I"])), min=1e-12)).square())
        mortar_losses = mortar(fields["phi"], fields["T"], sigma_pred)
        mortar_loss = sum(mortar_losses.values()) if name == "full_mortar" else 0.0 * field_loss
        smooth = torch.mean((fields["T"][1:] - fields["T"][:-1]).square()) / 100.0
        mortar_weight = 0.002 if name == "full_mortar" else 0.0
        loss = field_loss + 0.2 * port_loss + 0.05 * smooth + mortar_weight * mortar_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()
        losses.append(float(loss.detach()))
    elapsed = time.perf_counter() - start
    with torch.no_grad():
        fields = _forward(model, aux, target["coords"], target["V"], hard_bc)
        sigma_pred = generic_pcm_sigma(fields["T"], fields["m"], sigma_ins0=2.0, sigma_met0=8.0e4)
        mort = mortar(fields["phi"], fields["T"], sigma_pred)
        field_error = float(torch.sqrt(torch.mean(((fields["T"] - target["T"]) / 20.0).square()) + torch.mean((fields["m"][:, 1] - target["m"]).square())))
        interface_residual = float(sum(v for v in mort.values()))
        pde_residual = float(torch.mean((fields["T"][1:] - fields["T"][:-1]).square()) / 100.0)
    return {
        "variant": name,
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "loss_decreased": bool(losses[-1] <= losses[0]),
        "finite_loss": bool(np.isfinite(losses).all()),
        "field_error": field_error,
        "PDE_residual": pde_residual,
        "interface_residual": interface_residual,
        "wall_time_s": float(elapsed),
        "success": bool(np.isfinite(losses).all() and losses[-1] <= losses[0]),
    }


def run_multidomain_oasis_training(epochs: int = 10) -> dict[str, Any]:
    case = _target_case()
    target = _sample(case)
    variants = ["monolithic_pinn", "ordered_multidomain", "multidomain_hard_bc", "full_mortar"]
    rows = [_train_variant(v, target, layer_count=len(case["layers"]), epochs=epochs) for v in variants]
    summary = {
        "benchmark": "multidomain_oasis_training_v9",
        "note": "Synthetic numerical small-budget actual training; not performance superiority and not experimental validation.",
        "epochs": int(epochs),
        "uses_activated_case": bool(case["activated"]),
        "variants": rows,
        "best_variant_by_final_loss": min(rows, key=lambda r: r["final_loss"])["variant"],
        "full_mortar_success": bool(next(r for r in rows if r["variant"] == "full_mortar")["success"]),
        "P1_gate_passed": bool(case["activated"] and next(r for r in rows if r["variant"] == "full_mortar")["success"]),
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
        "forbidden_claims": ["performance superiority", "experimental validation", "full hidden-field recovery"],
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(run_multidomain_oasis_training(args.epochs), indent=2))


if __name__ == "__main__":
    main()
