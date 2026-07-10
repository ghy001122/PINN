"""OASIS-PINN components for claim-gated synthetic benchmarks."""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


class LiteratureStackEncoder(nn.Module):
    """Encode layer features into a compact stack embedding."""

    def __init__(self, in_dim: int = 4, embed_dim: int = 12) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(in_dim, embed_dim), nn.SiLU(), nn.Linear(embed_dim, embed_dim))

    def forward(self, layer_features: torch.Tensor) -> torch.Tensor:
        if layer_features.ndim != 3:
            raise ValueError("layer_features must have shape (batch, layers, features)")
        encoded = self.net(layer_features)
        return encoded.mean(dim=1)


class LayerWiseNeuralField(nn.Module):
    """Predict layer-wise phi, T, and m fields from coordinates plus stack embedding."""

    def __init__(self, coord_dim: int = 3, stack_dim: int = 12, hidden_dim: int = 32, layers: int = 4) -> None:
        super().__init__()
        self.layers = int(layers)
        self.net = nn.Sequential(
            nn.Linear(coord_dim + stack_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, 3 * self.layers),
        )

    def forward(self, coords: torch.Tensor, stack_embedding: torch.Tensor) -> dict[str, torch.Tensor]:
        if stack_embedding.ndim == 2 and coords.ndim == 2 and stack_embedding.shape[0] == 1 and coords.shape[0] != 1:
            stack_embedding = stack_embedding.expand(coords.shape[0], -1)
        raw = self.net(torch.cat([coords, stack_embedding], dim=-1)).reshape(coords.shape[0], self.layers, 3)
        return {"phi": raw[..., 0], "T": 250.0 + torch.nn.functional.softplus(raw[..., 1]), "m": torch.sigmoid(raw[..., 2])}


def generic_pcm_sigma(T: torch.Tensor, m: torch.Tensor, sigma_ins0: float = 1.0e-2, sigma_met0: float = 1.0e3, T_ref: float = 300.0) -> torch.Tensor:
    sigma_ins = sigma_ins0 * torch.exp(torch.clamp(0.010 * (T - T_ref), -40.0, 40.0))
    sigma_met = sigma_met0 * torch.exp(torch.clamp(-0.001 * (T - T_ref), -40.0, 40.0))
    return torch.clamp((1.0 - m) * sigma_ins + m * sigma_met, min=1.0e-12)


def vo2_hysteretic_rt_kernel(T: torch.Tensor, branch: torch.Tensor | None = None, T_c: float = 340.0, width: float = 3.0, R0: float = 1.0e5, Rm: float = 1.0e2) -> torch.Tensor:
    shift = torch.zeros_like(T) if branch is None else 2.0 * torch.tanh(branch)
    frac = torch.sigmoid((T - T_c + shift) / max(width, 1.0e-6))
    R = (1.0 - frac) * R0 + frac * Rm
    return torch.clamp(R, min=1.0e-9)


def nb_o2_pf_ndr_current(E: torch.Tensor, T: torch.Tensor, A: float = 1.0e-9, beta: float = 2.0e-5, Ea_eV: float = 0.18) -> torch.Tensor:
    kB = 8.617333262145e-5
    thermal = torch.exp(torch.clamp(-Ea_eV / (kB * torch.clamp(T, min=1.0)), -80.0, 20.0))
    pf = torch.sinh(torch.clamp(beta * E / torch.sqrt(torch.clamp(T, min=1.0)), -30.0, 30.0))
    ndr = 1.0 / (1.0 + torch.square(E / 2.0e7))
    return A * thermal * pf * ndr


class DifferentiablePortCircuit(nn.Module):
    """Map layer conductivities to port current with a load-line circuit.

    `series_stack` is the default physical port layer. `mean_sigma_ablation`
    preserves the old shortcut only for explicit ablation use.
    """

    def __init__(
        self,
        area_m2: float = 1.0e-12,
        thickness_m: float = 100e-9,
        R_load_ohm: float = 1.0e5,
        port_solver: str = "series_stack",
        layer_thickness_m: torch.Tensor | None = None,
    ) -> None:
        super().__init__()
        self.area_m2 = float(area_m2)
        self.thickness_m = float(thickness_m)
        self.R_load_ohm = float(R_load_ohm)
        self.port_solver = str(port_solver)
        if layer_thickness_m is None:
            self.register_buffer("layer_thickness_m", torch.empty(0))
        else:
            self.register_buffer("layer_thickness_m", torch.as_tensor(layer_thickness_m, dtype=torch.float32))

    def _thickness(self, sigma: torch.Tensor) -> torch.Tensor:
        layers = sigma.shape[-1]
        if self.layer_thickness_m.numel() == layers:
            return self.layer_thickness_m.to(dtype=sigma.dtype, device=sigma.device)
        return torch.full((layers,), self.thickness_m / max(layers, 1), dtype=sigma.dtype, device=sigma.device)

    def _mean_sigma_ablation(self, sigma: torch.Tensor, V_app: torch.Tensor) -> dict[str, torch.Tensor]:
        sigma_eff = torch.mean(torch.clamp(sigma, min=1.0e-12), dim=-1)
        G = sigma_eff * self.area_m2 / self.thickness_m
        V_dev = V_app / (1.0 + self.R_load_ohm * G)
        I = G * V_dev
        J = I / self.area_m2
        E = J.unsqueeze(-1) / torch.clamp(sigma, min=1.0e-12)
        Q_J = torch.clamp(sigma, min=1.0e-12) * E.square()
        return {"G": G, "I": I, "V_dev": V_dev, "J": J, "Q_J": Q_J, "port_solver": "mean_sigma_ablation"}

    def _series_stack(self, sigma: torch.Tensor, V_app: torch.Tensor) -> dict[str, torch.Tensor]:
        safe_sigma = torch.clamp(sigma, min=1.0e-12)
        thickness = self._thickness(safe_sigma)
        R_area = torch.sum(thickness / safe_sigma, dim=-1)
        G = self.area_m2 / torch.clamp(R_area, min=1.0e-30)
        V_dev = V_app / (1.0 + self.R_load_ohm * G)
        J = V_dev / torch.clamp(R_area, min=1.0e-30)
        I = J * self.area_m2
        E = J.unsqueeze(-1) / safe_sigma
        Q_J = safe_sigma * E.square()
        return {"G": G, "I": I, "V_dev": V_dev, "J": J, "Q_J": Q_J, "port_solver": "series_stack"}

    def _resistor_network(self, sigma: torch.Tensor, V_app: torch.Tensor) -> dict[str, torch.Tensor]:
        # Optional reduced network: lateral cells are parallel columns, each
        # column is a series stack. Expected shape can be (batch, cells, layers).
        if sigma.ndim < 3:
            return self._series_stack(sigma, V_app)
        safe_sigma = torch.clamp(sigma, min=1.0e-12)
        thickness = self._thickness(safe_sigma)
        R_area = torch.sum(thickness / safe_sigma, dim=-1)
        G_cols = (self.area_m2 / safe_sigma.shape[-2]) / torch.clamp(R_area, min=1.0e-30)
        G = torch.sum(G_cols, dim=-1)
        V_dev = V_app / (1.0 + self.R_load_ohm * G)
        J_cols = V_dev.unsqueeze(-1) / torch.clamp(R_area, min=1.0e-30)
        I = G * V_dev
        E = J_cols.unsqueeze(-1) / safe_sigma
        Q_J = safe_sigma * E.square()
        return {"G": G, "I": I, "V_dev": V_dev, "J": J_cols, "Q_J": Q_J, "port_solver": "resistor_network"}

    def forward(self, sigma: torch.Tensor, V_app: torch.Tensor) -> dict[str, torch.Tensor]:
        if self.port_solver == "mean_sigma_ablation":
            return self._mean_sigma_ablation(sigma, V_app)
        if self.port_solver == "series_stack":
            return self._series_stack(sigma, V_app)
        if self.port_solver == "resistor_network":
            return self._resistor_network(sigma, V_app)
        raise ValueError(f"Unknown port_solver: {self.port_solver}")


class ObservationOperator(nn.Module):
    """Observation operator H_p for terminal and optional anchor features."""

    def forward(self, port: dict[str, torch.Tensor], anchors: torch.Tensor | None = None) -> torch.Tensor:
        parts = [port["I"].reshape(-1, 1), port["G"].reshape(-1, 1), port["V_dev"].reshape(-1, 1)]
        if anchors is not None:
            parts.append(anchors.reshape(anchors.shape[0], -1))
        return torch.cat(parts, dim=-1)


def stiffness_indicator(transition_width: float | torch.Tensor) -> torch.Tensor:
    w = torch.as_tensor(transition_width, dtype=torch.float32)
    return 0.25 / torch.clamp(torch.abs(w), min=1.0e-8)


@dataclass(frozen=True)
class StiffnessDecision:
    chi: float
    branch: str
    use_fourier: bool
    use_front_focus: bool
    use_asinh: bool


class StiffnessGatedTrainingController:
    """Select low-frequency or stiffness-mitigation branches by chi."""

    def __init__(self, chi_c: float = 2.0) -> None:
        self.chi_c = float(chi_c)

    def decide(self, transition_width: float) -> StiffnessDecision:
        chi = float(stiffness_indicator(transition_width))
        stiff = chi > self.chi_c
        return StiffnessDecision(
            chi=chi,
            branch="fourier_front_asinh" if stiff else "vanilla_low_frequency",
            use_fourier=stiff,
            use_front_focus=stiff,
            use_asinh=stiff,
        )


class ClaimGatedInverseHead:
    """Small utility that maps metrics into claim-gate labels."""

    def __init__(self, success_threshold: float, partial_threshold: float | None = None) -> None:
        self.success_threshold = float(success_threshold)
        self.partial_threshold = float(partial_threshold if partial_threshold is not None else success_threshold * 1.5)

    def status(self, value: float) -> str:
        v = float(value)
        if v <= self.success_threshold:
            return "qualified_supported"
        if v <= self.partial_threshold:
            return "failed_but_informative"
        return "forbidden"
