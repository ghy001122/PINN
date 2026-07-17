"""Matched-budget dual-domain conservative full PINN for bounded N0-R.

The model uses one state expert per material layer. Each expert receives a
layer-local spatial coordinate, while the residual operators convert every
derivative back to the common global SI coordinate. Frozen GT fields are never
inputs to this module.
"""

from __future__ import annotations

from typing import Any, Literal

import torch
from torch import nn

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.network import StiffAwareMLP


DomainName = Literal["left", "right"]


def _float(value: Any) -> float:
    return float(value)


def _tensor(value: float, like: torch.Tensor) -> torch.Tensor:
    return torch.as_tensor(value, dtype=like.dtype, device=like.device)


def _safe_logit(value: torch.Tensor) -> torch.Tensor:
    clipped = torch.clamp(value, 1.0e-7, 1.0 - 1.0e-7)
    return torch.log(clipped) - torch.log1p(-clipped)


def _arrhenius_factor(temperature: torch.Tensor, energy_eV: float, reference_K: float) -> torch.Tensor:
    safe_temperature = torch.clamp(temperature, 1.0, 5000.0)
    exponent = -float(energy_eV) / K_B_EV_PER_K * (1.0 / safe_temperature - 1.0 / float(reference_K))
    return torch.exp(torch.clamp(exponent, -80.0, 80.0))


class DualDomainFullPINN1D(nn.Module):
    """Two small state networks with exact one-sided interface traces."""

    def __init__(
        self,
        *,
        params: dict[str, Any] | None = None,
        t_max_s: float = 3.0e-3,
        hidden_dim_per_domain: int = 32,
        hidden_layers: int = 3,
        fourier_scales: list[float] | tuple[float, ...] = (1.0, 2.0, 4.0, 8.0),
        voltage_scale_v: float = 0.20,
        temperature_scale_k: float = 20.0,
        seed: int = 20260715,
    ) -> None:
        super().__init__()
        self.params = merge_params(params)
        self.t_max_s = float(t_max_s)
        self.voltage_scale_v = float(voltage_scale_v)
        self.temperature_scale_k = float(temperature_scale_k)
        torch.manual_seed(int(seed))
        self.left_backbone = StiffAwareMLP(
            in_dim=2,
            out_dim=4,
            hidden_dim=int(hidden_dim_per_domain),
            hidden_layers=int(hidden_layers),
            scales=tuple(float(value) for value in fourier_scales),
            use_fourier=True,
        )
        torch.manual_seed(int(seed) + 1)
        self.right_backbone = StiffAwareMLP(
            in_dim=2,
            out_dim=4,
            hidden_dim=int(hidden_dim_per_domain),
            hidden_layers=int(hidden_layers),
            scales=tuple(float(value) for value in fourier_scales),
            use_fourier=True,
        )

    @property
    def interface_norm(self) -> float:
        return _float(self.params["L_int"]) / _float(self.params["L_eff"])

    @property
    def state_names(self) -> tuple[str, ...]:
        return ("phi", "c_v", "T", "m")

    def domain_length_m(self, domain: DomainName) -> float:
        if domain == "left":
            return _float(self.params["L_int"])
        if domain == "right":
            return _float(self.params["L_eff"]) - _float(self.params["L_int"])
        raise ValueError(f"Unsupported domain: {domain}")

    def global_x_norm(self, local_x_norm: torch.Tensor, domain: DomainName) -> torch.Tensor:
        if domain == "left":
            return local_x_norm * self.interface_norm
        if domain == "right":
            return self.interface_norm + local_x_norm * (1.0 - self.interface_norm)
        raise ValueError(f"Unsupported domain: {domain}")

    def local_x_norm(self, global_x_norm: torch.Tensor, domain: DomainName) -> torch.Tensor:
        if domain == "left":
            return global_x_norm / self.interface_norm
        if domain == "right":
            return (global_x_norm - self.interface_norm) / (1.0 - self.interface_norm)
        raise ValueError(f"Unsupported domain: {domain}")

    def voltage(self, t_norm: torch.Tensor) -> torch.Tensor:
        phase = torch.clamp(t_norm, 0.0, 1.0)
        peak = _tensor(_float(self.params["triangle_v_peak"]), phase)
        return torch.where(phase <= 0.5, -peak + 4.0 * peak * phase, 3.0 * peak - 4.0 * peak * phase)

    def initial_defect_global(self, x_norm: torch.Tensor) -> torch.Tensor:
        base = torch.ones_like(x_norm) * _tensor(_float(self.params["c_v0"]), x_norm)
        mode = str(self.params.get("initial_defect_mode", "uniform"))
        if mode == "uniform":
            return base
        if mode not in {"gaussian_seed", "seeded_defect"}:
            raise ValueError(f"Unsupported initial_defect_mode: {mode}")
        x_m = x_norm * _tensor(_float(self.params["L_eff"]), x_norm)
        seeded = base + _tensor(_float(self.params["gaussian_delta_c"]), x_norm) * torch.exp(
            -0.5
            * ((x_m - _tensor(_float(self.params["gaussian_x_d"]), x_norm))
               / _tensor(_float(self.params["gaussian_w_d"]), x_norm))
            ** 2
        )
        return torch.clamp(seeded, 1.0e-7, 1.0 - 1.0e-7)

    def equilibrium_phase(self, c_v: torch.Tensor, temperature: torch.Tensor) -> torch.Tensor:
        argument = (
            temperature
            - _tensor(_float(self.params["T_sw"]), temperature)
            + _tensor(_float(self.params["alpha_c"]), temperature)
            * (c_v - _tensor(_float(self.params["c_v0"]), c_v))
        ) / _tensor(_float(self.params["dT_sw"]), temperature)
        return torch.sigmoid(argument)

    def material_profiles(self, like: torch.Tensor, domain: DomainName) -> dict[str, torch.Tensor]:
        if domain == "left":
            mapping = {
                "sigma_off0": "nb_oxide_sigma_off0",
                "sigma_on0": "nb_oxide_sigma_on0",
                "D_v0": "nb_oxide_D_v0",
                "mu_v0": "nb_oxide_mu_v0",
                "k_th": "nb_oxide_k_th",
            }
        elif domain == "right":
            mapping = {
                "sigma_off0": "v2o5_sigma_off0",
                "sigma_on0": "v2o5_sigma_on0",
                "D_v0": "v2o5_D_v0",
                "mu_v0": "v2o5_mu_v0",
                "k_th": "v2o5_k_th",
            }
        else:
            raise ValueError(f"Unsupported domain: {domain}")
        return {
            key: torch.ones_like(like) * _tensor(_float(self.params[source]), like)
            for key, source in mapping.items()
        }

    def conductivity(
        self,
        c_v: torch.Tensor,
        temperature: torch.Tensor,
        m: torch.Tensor,
        profiles: dict[str, torch.Tensor],
    ) -> torch.Tensor:
        thermal_factor = _arrhenius_factor(
            temperature, _float(self.params["E_off_eV"]), _float(self.params["T0"])
        )
        c_delta = c_v - _tensor(_float(self.params["c_v0"]), c_v)
        sigma_off = profiles["sigma_off0"] * thermal_factor * torch.exp(
            torch.clamp(_tensor(_float(self.params["beta_off"]), c_v) * c_delta, -80.0, 80.0)
        )
        sigma_on = profiles["sigma_on0"] * torch.exp(
            torch.clamp(_tensor(_float(self.params["beta_on"]), c_v) * c_delta, -80.0, 80.0)
        )
        epsilon = _tensor(_float(self.params["eps_sigma"]), c_v)
        log_sigma = (1.0 - m) * torch.log(torch.clamp(sigma_off, min=epsilon)) + m * torch.log(
            torch.clamp(sigma_on, min=epsilon)
        )
        return torch.exp(torch.clamp(log_sigma, -80.0, 80.0))

    def forward_domain(self, local_coords: torch.Tensor, domain: DomainName) -> dict[str, torch.Tensor]:
        if local_coords.shape[-1] != 2:
            raise ValueError("local_coords must contain layer-local (xi, t/t_max).")
        xi = local_coords[..., 0:1]
        t_norm = local_coords[..., 1:2]
        global_x = self.global_x_norm(xi, domain)
        backbone = self.left_backbone if domain == "left" else self.right_backbone
        raw = backbone(local_coords)
        voltage = self.voltage(t_norm)

        phi_base = voltage * (1.0 - global_x)
        envelope = xi if domain == "left" else (1.0 - xi)
        phi = phi_base + _tensor(self.voltage_scale_v, xi) * envelope * raw[..., 0:1]
        c_initial = self.initial_defect_global(global_x)
        c_v = torch.sigmoid(_safe_logit(c_initial) + t_norm * raw[..., 1:2])
        temperature = _tensor(_float(self.params["T0"]), xi) + t_norm * _tensor(
            self.temperature_scale_k, xi
        ) * torch.nn.functional.softplus(raw[..., 2:3])
        m_initial = self.equilibrium_phase(
            c_initial, torch.ones_like(c_initial) * _tensor(_float(self.params["T0"]), c_initial)
        )
        m = torch.sigmoid(_safe_logit(m_initial) + t_norm * raw[..., 3:4])
        profiles = self.material_profiles(xi, domain)
        sigma = self.conductivity(c_v, temperature, m, profiles)
        return {
            "phi": phi,
            "c_v": c_v,
            "T": temperature,
            "m": m,
            "sigma": sigma,
            "V": voltage,
            "profiles": profiles,
            "global_x_norm": global_x,
            "local_x_norm": xi,
        }

    def forward(self, global_coords: torch.Tensor) -> dict[str, torch.Tensor]:
        if global_coords.shape[-1] != 2:
            raise ValueError("global_coords must contain global normalized (x/L, t/t_max).")
        x_norm = global_coords[..., 0:1]
        t_norm = global_coords[..., 1:2]
        left_coords = torch.cat([self.local_x_norm(x_norm, "left"), t_norm], dim=-1)
        right_coords = torch.cat([self.local_x_norm(x_norm, "right"), t_norm], dim=-1)
        left = self.forward_domain(left_coords, "left")
        right = self.forward_domain(right_coords, "right")
        mask = x_norm <= self.interface_norm
        result: dict[str, torch.Tensor] = {}
        for key in ("phi", "c_v", "T", "m", "sigma", "V", "global_x_norm"):
            result[key] = torch.where(mask, left[key], right[key])
        result["profiles"] = {
            key: torch.where(mask, left["profiles"][key], right["profiles"][key])
            for key in left["profiles"]
        }
        return result

    def port_observation(self, sigma_tx: torch.Tensor, voltage_t: torch.Tensor) -> dict[str, torch.Tensor]:
        if sigma_tx.ndim != 2:
            raise ValueError("sigma_tx must have shape (n_t, n_x).")
        resistance_area = _tensor(_float(self.params["L_eff"]), sigma_tx) * torch.mean(
            1.0 / torch.clamp(sigma_tx, min=_tensor(_float(self.params["eps_sigma"]), sigma_tx)), dim=-1
        )
        active_area = _float(self.params["eta_A"]) * _float(self.params["A_contact"])
        current = _tensor(active_area, sigma_tx) * voltage_t.reshape(-1) / resistance_area
        conductance = current / (voltage_t.reshape(-1) + _tensor(_float(self.params["eps_V"]), sigma_tx))
        return {"I": current, "G": conductance, "R_area": resistance_area}

    def parameter_counts(self) -> dict[str, int]:
        left = sum(parameter.numel() for parameter in self.left_backbone.parameters() if parameter.requires_grad)
        right = sum(parameter.numel() for parameter in self.right_backbone.parameters() if parameter.requires_grad)
        return {"left": left, "right": right, "total": left + right}

    def contract(self) -> dict[str, Any]:
        return {
            "contract_id": "full_pinn_n0_repair_v2",
            "states": list(self.state_names),
            "domains": ["left_nb_oxide", "right_v2o5"],
            "local_coordinates": True,
            "global_SI_derivatives": True,
            "hard_electrical_boundaries": ["phi(0,t)=V(t)", "phi(L,t)=0"],
            "hard_initial_conditions": ["c_v_gaussian_seed", "T_0", "m_equilibrium"],
            "conductivity": "derived_from_c_v_T_m_and_layer_parameters",
            "independent_log_sigma_output": False,
            "exact_interface_traces": True,
            "interface_state_continuity": ["phi", "c_v", "T", "m"],
            "interface_flux_continuity": ["current", "heat", "defect"],
            "training_evidence": "PDE_IC_BC_interface_only; frozen full fields score-only",
            "claim_scope": "bounded synthetic 1D forward repair; not interface novelty",
            "parameter_counts": self.parameter_counts(),
        }
