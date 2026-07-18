"""M33 mixed state--flux PINN on the frozen one-dimensional CV operator.

This module changes the mathematical residual contract, not the frozen
physics.  Cell states and face fluxes are learned jointly; constitutive and
conservation equations are evaluated as separate first-order constraints.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import torch
from torch import nn

from pinnpcm.pinn.full_pinn_n0_cv_e import (
    ControlVolumeFullPINN,
    _safe_logit,
    _scalar,
    model_state_time_derivatives,
    torch_cv_rhs,
)
from pinnpcm.pinn.network import FourierPyramidEmbedding


class MixedStateFluxPINN(ControlVolumeFullPINN):
    """Matched-budget temporal PINN with explicit heat and defect face heads."""

    def __init__(
        self,
        *,
        params: Mapping[str, Any] | None = None,
        nx: int = 31,
        t_max_s: float = 3.0e-3,
        hidden_dim: int = 25,
        hidden_layers: int = 3,
        fourier_scales: tuple[float, ...] | list[float] = (1.0, 2.0, 4.0, 8.0),
        temperature_min_k: float = 300.0,
        temperature_max_k: float = 350.0,
        registry: Mapping[str, Any] | None = None,
        seed: int = 20260715,
    ) -> None:
        super().__init__(
            params=params,
            nx=nx,
            t_max_s=t_max_s,
            hidden_dim=hidden_dim,
            hidden_layers=hidden_layers,
            fourier_scales=fourier_scales,
            temperature_min_k=temperature_min_k,
            temperature_max_k=temperature_max_k,
            registry=registry,
            seed=seed,
        )
        # Replace the v3 monolithic state network with one matched shared trunk
        # and three explicit heads. Resetting the seed makes this contract
        # independent of the discarded v3 backbone initialization.
        del self.backbone
        torch.manual_seed(int(seed))
        self.embedding = FourierPyramidEmbedding(
            in_dim=1, scales=tuple(float(value) for value in fourier_scales), include_input=True
        )
        layers: list[nn.Module] = []
        last = self.embedding.out_dim
        for _ in range(int(hidden_layers)):
            layers.extend([nn.Linear(last, int(hidden_dim)), nn.SiLU()])
            last = int(hidden_dim)
        self.shared_trunk = nn.Sequential(*layers)
        self.state_head = nn.Linear(last, 3 * self.nx)
        self.heat_flux_head = nn.Linear(last, self.nx + 1)
        self.defect_flux_head = nn.Linear(last, self.nx + 1)

        k_profile = self.profile_k_th.detach().cpu().numpy().reshape(-1)
        changes = np.flatnonzero(k_profile[:-1] != k_profile[1:])
        self.interface_left = int(changes[0]) if changes.size else self.nx // 2 - 1
        self.interface_face = self.interface_left + 1

        # SI scales are derived from the frozen parameter registry.  q_T has
        # W m^-2 and q_c has m s^-1 because c_v is dimensionless.
        length = float(self.params["L_eff"])
        temperature_scale = float(self.registry["temperature_scale_K"])
        voltage_scale = float(self.registry["voltage_scale_V"])
        temperature_max = float(temperature_max_k)
        profiles = self.material_profiles(torch.ones((1, self.nx)))
        d_max = torch_cv_rhs(
            self,
            torch.ones((1, 1)),
            torch.full((1, self.nx), float(self.params["c_v0"])),
            torch.full((1, self.nx), temperature_max),
            torch.zeros((1, self.nx)),
        )["defect_flux"]
        # The frozen flux itself can cancel, so use its declared diffusion and
        # drift coefficient bounds rather than an observed trajectory maximum.
        from pinnpcm.pinn.full_pinn_n0_cv_e import _arrhenius

        like = profiles["D_v0"]
        d_bound = _arrhenius(
            profiles["D_v0"], float(self.params["E_D_eV"]),
            torch.full_like(like, temperature_max), float(self.params["T0"])
        ).max()
        mu_bound = _arrhenius(
            profiles["mu_v0"], float(self.params["E_mu_eV"]),
            torch.full_like(like, temperature_max), float(self.params["T0"])
        ).max()
        defect_scale = float(d_bound) / length + 0.25 * float(mu_bound) * voltage_scale / length
        heat_scale = float(np.max(k_profile)) * temperature_scale / length
        if not (np.isfinite(defect_scale) and defect_scale > 0.0 and np.isfinite(heat_scale) and heat_scale > 0.0):
            raise ValueError("Derived mixed-flux scales must be finite and positive.")
        self.register_buffer("defect_flux_scale", torch.tensor(defect_scale, dtype=torch.float32))
        self.register_buffer("heat_flux_scale", torch.tensor(heat_scale, dtype=torch.float32))
        del d_max

    def _features(self, t_norm: torch.Tensor) -> torch.Tensor:
        return self.shared_trunk(self.embedding(t_norm.reshape(-1, 1)))

    def _states_from_features(self, features: torch.Tensor, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        t = t_norm.reshape(-1, 1)
        raw = self.state_head(features).reshape(-1, self.nx, 3)
        c0 = self.c_initial.to(dtype=t.dtype, device=t.device)
        m0 = self.m_initial.to(dtype=t.dtype, device=t.device)
        c_v = torch.sigmoid(_safe_logit(c0) + t * raw[..., 0])
        temperature = _scalar(float(self.params["T0"]), t) + (
            _scalar(self.temperature_max_k - float(self.params["T0"]), t)
            * t
            * torch.sigmoid(raw[..., 1])
        )
        m = torch.sigmoid(_safe_logit(m0) + t * raw[..., 2])
        return {"c_v": c_v, "T": temperature, "m": m}

    def _initial_fluxes(self, like: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        batch = like.shape[0]
        c0 = self.c_initial.to(dtype=like.dtype, device=like.device).expand(batch, -1)
        t0 = torch.full_like(c0, float(self.params["T0"]))
        m0 = self.m_initial.to(dtype=like.dtype, device=like.device).expand(batch, -1)
        zero_time = torch.zeros((batch, 1), dtype=like.dtype, device=like.device)
        rhs = torch_cv_rhs(self, zero_time, c0, t0, m0)
        return rhs["heat_flux"], rhs["defect_flux"]

    @staticmethod
    def _hard_zero_boundaries(interior_source: torch.Tensor) -> torch.Tensor:
        zero = torch.zeros((interior_source.shape[0], 1), dtype=interior_source.dtype, device=interior_source.device)
        return torch.cat([zero, interior_source[:, 1:-1], zero], dim=1)

    def _fluxes_from_features(self, features: torch.Tensor, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        time = t_norm.reshape(-1, 1)
        raw_heat = self._hard_zero_boundaries(self.heat_flux_head(features))
        raw_defect = self._hard_zero_boundaries(self.defect_flux_head(features))
        initial_heat, initial_defect = self._initial_fluxes(time)
        q_T = initial_heat + time * self.heat_flux_scale.to(time) * raw_heat
        q_c = initial_defect + time * self.defect_flux_scale.to(time) * raw_defect
        return {"q_T": q_T, "q_c": q_c}

    def mixed_outputs(self, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self._features(t_norm)
        states = self._states_from_features(features, t_norm)
        fluxes = self._fluxes_from_features(features, t_norm)
        return {**states, **fluxes}

    def dynamic_states(self, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self._features(t_norm)
        return self._states_from_features(features, t_norm)

    def flux_heads(self, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self._features(t_norm)
        return self._fluxes_from_features(features, t_norm)

    def forward(self, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        mixed = self.mixed_outputs(t_norm)
        electrical = self.analytic_electrostatics(
            mixed["c_v"], mixed["T"], mixed["m"], self.voltage(t_norm)
        )
        return {**mixed, **electrical}

    def contract(self) -> dict[str, Any]:
        baseline = 5501
        count = self.parameter_count()
        return {
            "contract_id": "m33_mixed_state_flux_v1",
            "learned_cell_states": ["c_v", "T", "m"],
            "explicit_face_flux_heads": ["q_c", "q_T"],
            "returned_states": ["phi", "c_v", "T", "m", "sigma", "E", "J", "I", "G", "q_c", "q_T"],
            "hard_initial_states": True,
            "hard_outer_flux_boundaries": True,
            "hard_series_electrostatics": True,
            "interface_face_index": self.interface_face,
            "parameter_count": count,
            "v3r_parameter_count": baseline,
            "relative_parameter_difference": (count - baseline) / baseline,
            "flux_units": {"q_c": "m s^-1", "q_T": "W m^-2"},
            "training_labels": [],
            "claim_scope": "frozen one-dimensional synthetic forward-fidelity MVE only",
        }


def mixed_operator_residuals(
    model: MixedStateFluxPINN,
    t_norm: torch.Tensor,
    c_v: torch.Tensor,
    temperature: torch.Tensor,
    m: torch.Tensor,
    dc_dt: torch.Tensor,
    dT_dt: torch.Tensor,
    dm_dt: torch.Tensor,
    q_c: torch.Tensor,
    q_T: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Evaluate the first-order frozen operator for explicit state/flux values."""

    frozen = torch_cv_rhs(model, t_norm, c_v, temperature, m)
    dx = _scalar(model.dx_m, c_v)
    scales = model.registry["residual_scales"]
    rho_cp = float(model.params["rho"]) * float(model.params["Cp"])
    dc_rhs = -(q_c[:, 1:] - q_c[:, :-1]) / dx - frozen["reaction"]
    dT_rhs = (
        -(q_T[:, 1:] - q_T[:, :-1]) / dx + frozen["joule"] - frozen["sink"]
    ) / _scalar(rho_cp, temperature)
    current_scale = _scalar(float(model.registry["current_density_scale_A_per_m2"]), frozen["E"])
    return {
        "q_c_constitutive": (q_c - frozen["defect_flux"]) / model.defect_flux_scale.to(q_c),
        "q_T_constitutive": (q_T - frozen["heat_flux"]) / model.heat_flux_scale.to(q_T),
        "r_c": (dc_dt - dc_rhs) / float(scales["r_c_per_s"]),
        "r_T": (dT_dt - dT_rhs) / float(scales["r_T_K_per_s"]),
        "r_m": (dm_dt - frozen["dm_dt"]) / float(scales["r_m_per_s"]),
        "discrete_electrical": (frozen["sigma"] * frozen["E"] - frozen["J"][:, None]) / current_scale,
        "frozen": frozen,
    }


def mixed_state_flux_residuals(
    model: MixedStateFluxPINN, t_norm: torch.Tensor
) -> dict[str, torch.Tensor]:
    states, derivatives = model_state_time_derivatives(model, t_norm)
    fluxes = model.flux_heads(t_norm)
    result = mixed_operator_residuals(
        model,
        t_norm,
        states["c_v"], states["T"], states["m"],
        derivatives["dc_dt"], derivatives["dT_dt"], derivatives["dm_dt"],
        fluxes["q_c"], fluxes["q_T"],
    )
    return {**result, "states": states, "derivatives": derivatives, **fluxes}


def mixed_ledger_residuals(
    model: MixedStateFluxPINN, t_norm: torch.Tensor
) -> dict[str, torch.Tensor]:
    """Global mass, energy, and current ledgers using the explicit heads."""

    time = t_norm.reshape(-1, 1)
    order = torch.argsort(time[:, 0])
    time = time[order]
    outputs = model(time)
    frozen = torch_cv_rhs(model, time, outputs["c_v"], outputs["T"], outputs["m"])
    dt = (time[1:, 0] - time[:-1, 0]) * model.t_max_s
    dx = _scalar(model.dx_m, outputs["c_v"])

    mass = torch.sum(outputs["c_v"], dim=1) * dx
    reaction = torch.sum(frozen["reaction"], dim=1) * dx
    mass_boundary = outputs["q_c"][:, -1] - outputs["q_c"][:, 0]
    mass_rate = reaction + mass_boundary
    mass_balance = mass[1:] - mass[:-1] + 0.5 * (mass_rate[1:] + mass_rate[:-1]) * dt
    mass_scale = _scalar(float(model.params["L_eff"]), mass_balance)

    rho_cp = float(model.params["rho"]) * float(model.params["Cp"])
    energy = torch.sum(_scalar(rho_cp, outputs["T"]) * outputs["T"], dim=1) * dx
    joule = torch.sum(frozen["joule"], dim=1) * dx
    sink = torch.sum(frozen["sink"], dim=1) * dx
    heat_boundary = outputs["q_T"][:, -1] - outputs["q_T"][:, 0]
    energy_rate = heat_boundary - joule + sink
    energy_balance = energy[1:] - energy[:-1] + 0.5 * (energy_rate[1:] + energy_rate[:-1]) * dt
    energy_scale = _scalar(
        rho_cp * float(model.registry["temperature_scale_K"]) * float(model.params["L_eff"]),
        energy_balance,
    )
    current_scale = _scalar(float(model.registry["current_density_scale_A_per_m2"]), outputs["E"])
    current_balance = (outputs["sigma"] * outputs["E"] - outputs["J"][:, None]) / current_scale
    return {
        "defect_mass_ledger": mass_balance / mass_scale,
        "energy_ledger": energy_balance / energy_scale,
        "current_ledger": current_balance,
    }


def grouped_constraint_tensors(
    model: MixedStateFluxPINN,
    train_t: torch.Tensor,
    ledger_t: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Return the six preregistered augmented-Lagrangian constraint groups."""

    residuals = mixed_state_flux_residuals(model, train_t)
    ledgers = mixed_ledger_residuals(model, ledger_t)
    output = model(train_t)
    i = model.interface_left
    j = i + 1
    state_scales = {
        "c_v": float(model.registry["concentration_scale"]),
        "T": float(model.registry["temperature_scale_K"]),
        "m": float(model.registry["phase_scale"]),
        "phi": float(model.registry["voltage_scale_V"]),
    }
    interface_state = []
    for name in ("c_v", "T", "m", "phi"):
        value = output[name]
        left_trace = 1.5 * value[:, i] - 0.5 * value[:, i - 1]
        right_trace = 1.5 * value[:, j] - 0.5 * value[:, j + 1]
        interface_state.append((right_trace - left_trace) / state_scales[name])
    interface_flux = torch.cat(
        [
            residuals["q_c_constitutive"][:, model.interface_face],
            residuals["q_T_constitutive"][:, model.interface_face],
        ]
    )

    zero = torch.zeros((1, 1), dtype=train_t.dtype, device=train_t.device)
    initial = model(zero)
    dx = _scalar(model.dx_m, output["E"])
    left_phi = output["phi"][:, 0] + 0.5 * output["E"][:, 0] * dx
    right_phi = output["phi"][:, -1] - 0.5 * output["E"][:, -1] * dx
    ic_bc = torch.cat(
        [
            (initial["c_v"] - model.c_initial.to(initial["c_v"])) .reshape(-1),
            ((initial["T"] - float(model.params["T0"])) / state_scales["T"]).reshape(-1),
            (initial["m"] - model.m_initial.to(initial["m"])) .reshape(-1),
            ((left_phi - output["V"]) / state_scales["phi"]).reshape(-1),
            (right_phi / state_scales["phi"]).reshape(-1),
            (output["q_c"][:, [0, -1]] / model.defect_flux_scale.to(output["q_c"])).reshape(-1),
            (output["q_T"][:, [0, -1]] / model.heat_flux_scale.to(output["q_T"])).reshape(-1),
        ]
    )
    return {
        "constitutive": torch.cat([residuals["q_c_constitutive"].reshape(-1), residuals["q_T_constitutive"].reshape(-1)]),
        "conservation": torch.cat([residuals["r_c"].reshape(-1), residuals["r_T"].reshape(-1)]),
        "phase_current": torch.cat([residuals["r_m"].reshape(-1), residuals["discrete_electrical"].reshape(-1)]),
        "ic_bc": ic_bc,
        "interface": torch.cat([*(value.reshape(-1) for value in interface_state), interface_flux.reshape(-1)]),
        "ledgers": torch.cat([value.reshape(-1) for value in ledgers.values()]),
    }


def rms(value: torch.Tensor) -> torch.Tensor:
    return torch.linalg.vector_norm(value.reshape(-1)) / float(max(value.numel(), 1)) ** 0.5

