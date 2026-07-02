"""Quasi-2D PINN residual and boundary preflight."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.vo2_constitutive import vo2_sigma
from pinnpcm.pinn.network import StiffAwareMLP
from scripts.gamma_sub_validation_common import load_yaml, write_json

DEFAULT_CONFIG = Path("configs/pinn_quasi_2d_residual_preflight.yaml")


def _grad(y: torch.Tensor, coords: torch.Tensor) -> torch.Tensor:
    return torch.autograd.grad(y.sum(), coords, create_graph=True, retain_graph=True)[0]


def _second(partial: torch.Tensor, coords: torch.Tensor, dim: int) -> torch.Tensor:
    return _grad(partial, coords)[:, dim:dim + 1]


def _run_model(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    torch.manual_seed(int(cfg.get("seed", 2026)))
    n = int(cfg.get("num_points", 96))
    coords = torch.rand(n, 3, dtype=torch.float32, requires_grad=True)
    use_fourier = name != "vanilla_mlp"
    model = StiffAwareMLP(in_dim=3, out_dim=4, hidden_dim=24, hidden_layers=2, scales=(1.0, 2.0, 4.0), use_fourier=use_fourier)
    raw = model(coords)
    phi = 0.2 * torch.tanh(raw[:, 0:1])
    T = float(cfg["physics"]["T0"]) + 25.0 * torch.sigmoid(raw[:, 1:2])
    c_v = 0.08 + 0.025 * torch.tanh(raw[:, 2:3])
    m = torch.sigmoid(raw[:, 3:4])
    sigma = vo2_sigma(T, c_v, m, params={"T_c": float(cfg["physics"]["T_c"]), "transition_width": float(cfg["physics"]["transition_width"]), "sigma_ins0": 2.0e-3, "sigma_met0": 2.0, "sigma_max": 1.0e4})
    grad_phi = _grad(phi, coords)
    grad_T = _grad(T, coords)
    grad_c = _grad(c_v, coords)
    grad_m = _grad(m, coords)
    dphidx, dphidy = grad_phi[:, 0:1], grad_phi[:, 1:2]
    dTdt = grad_T[:, 2:3]
    dcdt = grad_c[:, 2:3]
    dmdt = grad_m[:, 2:3]
    dTxx = _second(grad_T[:, 0:1], coords, 0)
    dTyy = _second(grad_T[:, 1:2], coords, 1)
    dcxx = _second(grad_c[:, 0:1], coords, 0)
    dcyy = _second(grad_c[:, 1:2], coords, 1)
    div_sigma_grad_phi = _grad(sigma * dphidx, coords)[:, 0:1] + _grad(sigma * dphidy, coords)[:, 1:2]
    joule = sigma * (dphidx.square() + dphidy.square())
    phase_eq = torch.sigmoid((T - float(cfg["physics"]["T_c"])) / float(cfg["physics"]["transition_width"]))
    heat_res = dTdt - float(cfg["physics"]["kappa_norm"]) * (dTxx + dTyy) + 0.01 * (T - float(cfg["physics"]["T0"])) - 1.0e-4 * joule
    state_res = dmdt - (phase_eq - m) / float(cfg["physics"]["tau_m_norm"])
    defect_res = dcdt - float(cfg["physics"]["defect_D_norm"]) * (dcxx + dcyy)
    potential_res = div_sigma_grad_phi
    left = torch.cat([torch.zeros(16, 1), torch.rand(16, 1), torch.rand(16, 1)], dim=1)
    right = torch.cat([torch.ones(16, 1), torch.rand(16, 1), torch.rand(16, 1)], dim=1)
    left_phi = 0.2 * torch.tanh(model(left)[:, 0:1])
    right_phi = 0.2 * torch.tanh(model(right)[:, 0:1])
    boundary_loss = (left_phi - float(cfg["physics"]["voltage_left"])).square().mean() + right_phi.square().mean()
    terminal_current = torch.mean(sigma * (-dphidx))
    return {
        "model": name,
        "all_residuals_finite": bool(torch.isfinite(torch.stack([heat_res.mean(), state_res.mean(), defect_res.mean(), potential_res.mean()])).all().item()),
        "boundary_losses_finite": bool(torch.isfinite(boundary_loss).item()),
        "terminal_current_integral_finite": bool(torch.isfinite(terminal_current).item()),
        "heat_residual_mse": float(torch.mean(heat_res.square()).detach().cpu()),
        "state_residual_mse": float(torch.mean(state_res.square()).detach().cpu()),
        "defect_residual_mse": float(torch.mean(defect_res.square()).detach().cpu()),
        "potential_residual_mse": float(torch.mean(potential_res.square()).detach().cpu()),
        "boundary_loss": float(boundary_loss.detach().cpu()),
        "terminal_current_integral": float(terminal_current.detach().cpu()),
        "uses_fourier_features": bool(use_fourier),
    }


def run_residual_preflight(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    rows = [_run_model(str(name), cfg) for name in cfg["models"]]
    all_ok = all(row["all_residuals_finite"] and row["boundary_losses_finite"] and row["terminal_current_integral_finite"] for row in rows)
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic quasi-2D autograd residual preflight; no full 2D inverse claim.",
        "model_results": rows,
        "all_residuals_finite": bool(all(row["all_residuals_finite"] for row in rows)),
        "boundary_losses_finite": bool(all(row["boundary_losses_finite"] for row in rows)),
        "terminal_current_integral_finite": bool(all(row["terminal_current_integral_finite"] for row in rows)),
        "fourier_feature_stability_note": "Both vanilla and Fourier-feature residual evaluations are finite in this smoke preflight." if all_ok else "At least one residual path is non-finite and requires debugging before future 2D training.",
        "whether_ready_for_future_2d_training": bool(all_ok),
        "whether_2d_inverse_claim_allowed": False,
        "forbidden_claims": ["2D inverse diagnosis solved", "experimental validation", "full hidden-field recovery from sparse port current"],
        "outputs": {"summary_json": cfg["summary_json"]},
    }
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_residual_preflight(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
