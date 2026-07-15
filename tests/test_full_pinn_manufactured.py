"""Manufactured and residual sanity tests for N0."""

from __future__ import annotations

import torch

from pinnpcm.physics.params import default_gt_params
from pinnpcm.pinn.full_residuals_1d import compute_full_residuals, residual_rms


class ConstantEquilibrium(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.params = {**default_gt_params(), "layer_profile": "uniform", "initial_defect_mode": "uniform"}
        self.t_max_s = 3.0e-3
        self.voltage_scale_v = 0.2
        self.temperature_scale_k = 20.0

    def equilibrium_phase(self, c_v: torch.Tensor, temperature: torch.Tensor) -> torch.Tensor:
        p = self.params
        return torch.sigmoid((temperature - p["T_sw"] + p["alpha_c"] * (c_v - p["c_v0"])) / p["dT_sw"])

    def forward(self, coords: torch.Tensor) -> dict[str, object]:
        zero = coords[:, :1] * 0.0 + coords[:, 1:] * 0.0
        c_v = zero + self.params["c_v0"]
        temperature = zero + self.params["T0"]
        m = self.equilibrium_phase(c_v, temperature)
        sigma = torch.exp((1.0 - m) * torch.log(zero + self.params["sigma_off0"]) + m * torch.log(zero + self.params["sigma_on0"]))
        profiles = {key: zero + self.params[key] for key in ("sigma_off0", "sigma_on0", "D_v0", "mu_v0", "k_th")}
        return {"phi": zero, "c_v": c_v, "T": temperature, "m": m, "sigma": sigma, "V": zero, "profiles": profiles}


def test_constant_equilibrium_manufactured_solution_has_zero_residual() -> None:
    model = ConstantEquilibrium().to(dtype=torch.float64)
    coords = torch.rand((64, 2), generator=torch.Generator().manual_seed(11), dtype=torch.float64)
    rms = residual_rms(compute_full_residuals(model, coords))
    assert max(rms.values()) < 1.0e-12
