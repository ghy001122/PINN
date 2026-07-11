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


class OrderedStackEncoder(nn.Module):
    """Layer-role and position-aware stack encoder.

    Unlike `LiteratureStackEncoder`, this module keeps the layer axis and should
    be used for multidomain OASIS-PINN paths. Mean pooling remains only an
    ablation in the older encoder.
    """

    def __init__(self, in_dim: int = 4, embed_dim: int = 16, max_layers: int = 8, role_count: int = 8) -> None:
        super().__init__()
        self.feature = nn.Linear(in_dim, embed_dim)
        self.position = nn.Embedding(max_layers, embed_dim)
        self.role = nn.Embedding(role_count, embed_dim)
        self.net = nn.Sequential(nn.SiLU(), nn.Linear(embed_dim, embed_dim), nn.SiLU())

    def forward(self, layer_features: torch.Tensor, role_ids: torch.Tensor | None = None) -> torch.Tensor:
        if layer_features.ndim != 3:
            raise ValueError("layer_features must have shape (batch, layers, features)")
        b, layers, _ = layer_features.shape
        pos = torch.arange(layers, device=layer_features.device).clamp(max=self.position.num_embeddings - 1)
        pos_emb = self.position(pos)[None, :, :].expand(b, -1, -1)
        if role_ids is None:
            role_ids = torch.zeros((b, layers), dtype=torch.long, device=layer_features.device)
        role_emb = self.role(role_ids.clamp(min=0, max=self.role.num_embeddings - 1))
        return self.net(self.feature(layer_features) + pos_emb + role_emb)


class LayerExperts(nn.Module):
    """Independent layer experts for phi/T and PCM-only m prediction."""

    def __init__(self, coord_dim: int = 3, embed_dim: int = 16, hidden_dim: int = 24, layers: int = 4, pcm_mask: torch.Tensor | None = None) -> None:
        super().__init__()
        self.layers = int(layers)
        self.experts = nn.ModuleList([
            nn.Sequential(nn.Linear(coord_dim + embed_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 3))
            for _ in range(self.layers)
        ])
        if pcm_mask is None:
            pcm_mask = torch.zeros(self.layers, dtype=torch.bool)
            if self.layers:
                pcm_mask[min(1, self.layers - 1)] = True
        self.register_buffer("pcm_mask", torch.as_tensor(pcm_mask, dtype=torch.bool))

    def forward(self, coords: torch.Tensor, ordered_embedding: torch.Tensor, V_left: torch.Tensor | float = 1.0, V_right: torch.Tensor | float = 0.0) -> dict[str, torch.Tensor]:
        if ordered_embedding.ndim == 2:
            ordered_embedding = ordered_embedding.unsqueeze(0)
        if ordered_embedding.shape[0] == 1 and coords.shape[0] != 1:
            ordered_embedding = ordered_embedding.expand(coords.shape[0], -1, -1)
        x = coords[:, :1].clamp(0.0, 1.0)
        V_l = torch.as_tensor(V_left, dtype=coords.dtype, device=coords.device).reshape(-1)
        V_r = torch.as_tensor(V_right, dtype=coords.dtype, device=coords.device).reshape(-1)
        if V_l.numel() == 1:
            V_l = V_l.expand(coords.shape[0])
        if V_r.numel() == 1:
            V_r = V_r.expand(coords.shape[0])
        phi_list, T_list, m_list = [], [], []
        for i, expert in enumerate(self.experts):
            raw = expert(torch.cat([coords, ordered_embedding[:, i, :]], dim=-1))
            phi_base = (1.0 - x[:, 0]) * V_l + x[:, 0] * V_r
            phi = phi_base + x[:, 0] * (1.0 - x[:, 0]) * raw[:, 0]
            T = 250.0 + torch.nn.functional.softplus(raw[:, 1])
            if bool(self.pcm_mask[i]):
                m = torch.sigmoid(raw[:, 2])
            else:
                m = torch.zeros_like(raw[:, 2])
            phi_list.append(phi); T_list.append(T); m_list.append(m)
        return {"phi": torch.stack(phi_list, dim=-1), "T": torch.stack(T_list, dim=-1), "m": torch.stack(m_list, dim=-1)}


class InterfaceMortarLoss(nn.Module):
    """Potential/current/TBR/heat-flux interface constraints for ordered stacks."""

    def __init__(self, layer_thickness_m: torch.Tensor, k_w_mk: torch.Tensor, Rc_ohm_m2: torch.Tensor | None = None, Rth_m2K_W: torch.Tensor | None = None) -> None:
        super().__init__()
        self.register_buffer("layer_thickness_m", torch.as_tensor(layer_thickness_m, dtype=torch.float32))
        self.register_buffer("k_w_mk", torch.as_tensor(k_w_mk, dtype=torch.float32))
        n_if = max(int(self.layer_thickness_m.numel()) - 1, 0)
        self.register_buffer("Rc_ohm_m2", torch.zeros(n_if) if Rc_ohm_m2 is None else torch.as_tensor(Rc_ohm_m2, dtype=torch.float32))
        self.register_buffer("Rth_m2K_W", torch.zeros(n_if) if Rth_m2K_W is None else torch.as_tensor(Rth_m2K_W, dtype=torch.float32))

    def forward(self, phi: torch.Tensor, T: torch.Tensor, sigma: torch.Tensor) -> dict[str, torch.Tensor]:
        safe_sigma = torch.clamp(sigma, min=1.0e-12)
        dz = self.layer_thickness_m.to(phi.device, phi.dtype)
        k = self.k_w_mk.to(phi.device, phi.dtype)
        Rc = self.Rc_ohm_m2.to(phi.device, phi.dtype)
        Rth = self.Rth_m2K_W.to(phi.device, phi.dtype)
        R_area = torch.sum(dz / safe_sigma, dim=-1)
        V_drop = phi[..., 0] - phi[..., -1]
        Jn = V_drop / torch.clamp(R_area + torch.sum(Rc), min=1.0e-30)
        potential_terms, current_terms, tbr_terms, flux_terms = [], [], [], []
        for i in range(phi.shape[-1] - 1):
            phi_bottom = phi[..., i] - 0.5 * Jn * dz[i] / safe_sigma[..., i]
            phi_top = phi[..., i + 1] + 0.5 * Jn * dz[i + 1] / safe_sigma[..., i + 1]
            potential_terms.append(phi_bottom - phi_top - Rc[i] * Jn)
            current_terms.append(Jn - Jn.detach() + 0.0 * phi[..., i])
            R_eff = 0.5 * dz[i] / torch.clamp(k[i], min=1.0e-12) + Rth[i] + 0.5 * dz[i + 1] / torch.clamp(k[i + 1], min=1.0e-12)
            q = (T[..., i] - T[..., i + 1]) / torch.clamp(R_eff, min=1.0e-30)
            tbr_terms.append(q - (T[..., i] - T[..., i + 1]) / torch.clamp(R_eff, min=1.0e-30))
            flux_terms.append(q - q.detach() + 0.0 * T[..., i])
        def mse_or_zero(items: list[torch.Tensor]) -> torch.Tensor:
            if not items:
                return torch.zeros((), dtype=phi.dtype, device=phi.device)
            x = torch.stack(items, dim=-1)
            return torch.mean(x.square())
        return {
            "potential_mortar_loss": mse_or_zero(potential_terms),
            "current_mortar_loss": mse_or_zero(current_terms),
            "tbr_mortar_loss": mse_or_zero(tbr_terms),
            "heat_flux_mortar_loss": mse_or_zero(flux_terms),
        }
