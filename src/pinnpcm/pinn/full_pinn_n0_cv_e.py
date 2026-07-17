"""N0-CV-E v3: analytic series electrostatics plus solver-exact CV dynamics."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import numpy as np
import torch
from torch import nn

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.physics.params import initial_defect_profile, merge_params, spatial_param_profiles
from pinnpcm.pinn.network import StiffAwareMLP


def _scalar(value: float, like: torch.Tensor) -> torch.Tensor:
    return torch.as_tensor(value, dtype=like.dtype, device=like.device)


def _safe_logit(value: torch.Tensor) -> torch.Tensor:
    clipped = torch.clamp(value, 1.0e-7, 1.0 - 1.0e-7)
    return torch.log(clipped) - torch.log1p(-clipped)


def _arrhenius(
    prefactor: torch.Tensor,
    activation_e_ev: float,
    temperature: torch.Tensor,
    reference_temperature: float,
) -> torch.Tensor:
    safe_temperature = torch.clamp(temperature, 1.0, 5000.0)
    exponent = -float(activation_e_ev) / K_B_EV_PER_K * (
        1.0 / safe_temperature - 1.0 / float(reference_temperature)
    )
    return prefactor * torch.exp(torch.clamp(exponent, -80.0, 80.0))


class ControlVolumeFullPINN(nn.Module):
    """Temporal state network on the frozen 31-cell finite-volume grid.

    The network learns only bounded ``c_v``, ``T``, and ``m``. Potential,
    conductivity, field, current density, current, and conductance are analytic
    consequences of the frozen series-electrical relation.
    """

    def __init__(
        self,
        *,
        params: Mapping[str, Any] | None = None,
        nx: int = 31,
        t_max_s: float = 3.0e-3,
        hidden_dim: int = 32,
        hidden_layers: int = 3,
        fourier_scales: tuple[float, ...] | list[float] = (1.0, 2.0, 4.0, 8.0),
        temperature_min_k: float = 300.0,
        temperature_max_k: float = 350.0,
        registry: Mapping[str, Any] | None = None,
        seed: int = 20260715,
    ) -> None:
        super().__init__()
        if nx < 3:
            raise ValueError("nx must be at least 3.")
        if temperature_max_k <= temperature_min_k:
            raise ValueError("temperature_max_k must exceed temperature_min_k.")
        torch.manual_seed(int(seed))
        self.params = merge_params(dict(params) if params is not None else None)
        self.nx = int(nx)
        self.t_max_s = float(t_max_s)
        self.temperature_min_k = float(temperature_min_k)
        self.temperature_max_k = float(temperature_max_k)
        self.registry = deepcopy(dict(registry or {}))
        self.dx_m = float(self.params["L_eff"]) / self.nx

        x = (np.arange(self.nx, dtype=float) + 0.5) * self.dx_m
        profiles = spatial_param_profiles(x, self.params)
        c_initial = initial_defect_profile(x, self.params)
        argument = (
            float(self.params["T0"])
            - float(self.params["T_sw"])
            + float(self.params["alpha_c"]) * (c_initial - float(self.params["c_v0"]))
        ) / float(self.params["dT_sw"])
        m_initial = 1.0 / (1.0 + np.exp(-np.clip(argument, -60.0, 60.0)))
        self.register_buffer("x_m", torch.as_tensor(x, dtype=torch.float32).reshape(1, -1))
        self.register_buffer("c_initial", torch.as_tensor(c_initial, dtype=torch.float32).reshape(1, -1))
        self.register_buffer("m_initial", torch.as_tensor(m_initial, dtype=torch.float32).reshape(1, -1))
        for key, value in profiles.items():
            self.register_buffer(f"profile_{key}", torch.as_tensor(value, dtype=torch.float32).reshape(1, -1))

        self.backbone = StiffAwareMLP(
            in_dim=1,
            out_dim=3 * self.nx,
            hidden_dim=int(hidden_dim),
            hidden_layers=int(hidden_layers),
            scales=tuple(float(value) for value in fourier_scales),
            use_fourier=True,
        )

    def voltage(self, t_norm: torch.Tensor) -> torch.Tensor:
        phase = torch.clamp(t_norm.reshape(-1, 1), 0.0, 1.0)
        peak = _scalar(float(self.params["triangle_v_peak"]), phase)
        return torch.where(phase <= 0.5, -peak + 4.0 * peak * phase, 3.0 * peak - 4.0 * peak * phase)

    def material_profiles(self, like: torch.Tensor) -> dict[str, torch.Tensor]:
        return {
            key: getattr(self, f"profile_{key}").to(dtype=like.dtype, device=like.device).expand(like.shape[0], -1)
            for key in ("sigma_off0", "sigma_on0", "D_v0", "mu_v0", "k_th")
        }

    def equilibrium_phase(self, c_v: torch.Tensor, temperature: torch.Tensor) -> torch.Tensor:
        argument = (
            temperature
            - _scalar(float(self.params["T_sw"]), temperature)
            + _scalar(float(self.params["alpha_c"]), temperature)
            * (c_v - _scalar(float(self.params["c_v0"]), c_v))
        ) / _scalar(float(self.params["dT_sw"]), temperature)
        return torch.sigmoid(argument)

    def conductivity(self, c_v: torch.Tensor, temperature: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
        profiles = self.material_profiles(c_v)
        thermal = _arrhenius(
            torch.ones_like(temperature),
            float(self.params["E_off_eV"]),
            temperature,
            float(self.params["T0"]),
        )
        delta = c_v - _scalar(float(self.params["c_v0"]), c_v)
        sigma_off = profiles["sigma_off0"] * thermal * torch.exp(
            torch.clamp(_scalar(float(self.params["beta_off"]), c_v) * delta, -80.0, 80.0)
        )
        sigma_on = profiles["sigma_on0"] * torch.exp(
            torch.clamp(_scalar(float(self.params["beta_on"]), c_v) * delta, -80.0, 80.0)
        )
        epsilon = _scalar(float(self.params["eps_sigma"]), c_v)
        log_sigma = (1.0 - m) * torch.log(torch.clamp(sigma_off, min=epsilon)) + m * torch.log(
            torch.clamp(sigma_on, min=epsilon)
        )
        return torch.maximum(
            torch.exp(torch.clamp(log_sigma, -80.0, 80.0)), epsilon
        )

    def dynamic_states(self, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        t = t_norm.reshape(-1, 1)
        raw = self.backbone(t).reshape(-1, self.nx, 3)
        c0 = self.c_initial.to(dtype=t.dtype, device=t.device)
        m0 = self.m_initial.to(dtype=t.dtype, device=t.device)
        c_v = torch.sigmoid(_safe_logit(c0) + t * raw[..., 0])
        temperature_fraction = torch.sigmoid(raw[..., 1])
        temperature = _scalar(float(self.params["T0"]), t) + (
            _scalar(self.temperature_max_k - float(self.params["T0"]), t)
            * t
            * temperature_fraction
        )
        m = torch.sigmoid(_safe_logit(m0) + t * raw[..., 2])
        return {"c_v": c_v, "T": temperature, "m": m}

    def analytic_electrostatics(
        self,
        c_v: torch.Tensor,
        temperature: torch.Tensor,
        m: torch.Tensor,
        voltage: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        if voltage is None:
            raise ValueError("voltage must be supplied to the analytic electrostatic head.")
        sigma = self.conductivity(c_v, temperature, m)
        epsilon_sigma = _scalar(float(self.params["eps_sigma"]), sigma)
        sigma = torch.maximum(sigma, epsilon_sigma)
        resistance_area = torch.sum(_scalar(self.dx_m, sigma) / sigma, dim=1) + _scalar(
            float(self.params["eps_R"]), sigma
        )
        applied = voltage.reshape(-1)
        current_density = applied / resistance_area
        electric_field = current_density[:, None] / sigma
        cell_drop = electric_field * _scalar(self.dx_m, electric_field)
        phi = applied[:, None] - (torch.cumsum(cell_drop, dim=1) - 0.5 * cell_drop)
        active_area = float(self.params["eta_A"]) * float(self.params["A_contact"])
        current = _scalar(active_area, current_density) * current_density
        conductance = current / (applied + _scalar(float(self.params["eps_V"]), applied))
        return {
            "sigma": sigma,
            "R_area": resistance_area,
            "J": current_density,
            "E": electric_field,
            "phi": phi,
            "I": current,
            "G": conductance,
            "V": applied,
        }

    def forward(self, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        states = self.dynamic_states(t_norm)
        voltage = self.voltage(t_norm)
        electrical = self.analytic_electrostatics(
            states["c_v"], states["T"], states["m"], voltage
        )
        return {**states, **electrical}

    def si_to_dimensionless(self, states: Mapping[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        registry = self.registry
        return {
            "c_v": states["c_v"] / float(registry["concentration_scale"]),
            "T": (states["T"] - float(self.params["T0"])) / float(registry["temperature_scale_K"]),
            "m": states["m"] / float(registry["phase_scale"]),
            "phi": states["phi"] / float(registry["voltage_scale_V"]),
            "E": states["E"] / (float(registry["voltage_scale_V"]) / float(registry["length_scale_m"])),
            "sigma": states["sigma"] / float(registry["conductivity_scale_S_per_m"]),
            "J": states["J"] / float(registry["current_density_scale_A_per_m2"]),
        }

    def dimensionless_to_si(self, states: Mapping[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        registry = self.registry
        return {
            "c_v": states["c_v"] * float(registry["concentration_scale"]),
            "T": states["T"] * float(registry["temperature_scale_K"]) + float(self.params["T0"]),
            "m": states["m"] * float(registry["phase_scale"]),
            "phi": states["phi"] * float(registry["voltage_scale_V"]),
            "E": states["E"] * (float(registry["voltage_scale_V"]) / float(registry["length_scale_m"])),
            "sigma": states["sigma"] * float(registry["conductivity_scale_S_per_m"]),
            "J": states["J"] * float(registry["current_density_scale_A_per_m2"]),
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)

    def contract(self) -> dict[str, Any]:
        return {
            "contract_id": "full_pinn_n0_cv_e_v3",
            "learned_states": ["c_v_cell", "T_cell", "m_cell"],
            "returned_states": ["phi", "c_v", "T", "m", "sigma", "E", "J", "I", "G"],
            "independent_phi_network": False,
            "independent_sigma_network": False,
            "hard_initial_conditions": True,
            "hard_series_electrostatics": True,
            "face_average": "frozen_arithmetic_cell_face",
            "outer_defect_and_heat_flux": "zero",
            "training_labels": [],
            "frozen_fields": "post_training_score_only",
            "claim_scope": "frozen one-dimensional synthetic forward and conservation only",
            "parameter_count": self.parameter_count(),
        }


def torch_cv_rhs(
    model: ControlVolumeFullPINN,
    t_norm: torch.Tensor,
    c_v: torch.Tensor,
    temperature: torch.Tensor,
    m: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Torch translation of ``gt_solver._rhs_factory`` without altered faces."""

    c = torch.clamp(c_v, 1.0e-8, 1.0 - 1.0e-8)
    temp = torch.clamp(temperature, 1.0, 5000.0)
    phase = torch.clamp(m, 0.0, 1.0)
    voltage = model.voltage(t_norm)
    electrical = model.analytic_electrostatics(c, temp, phase, voltage)
    profiles = model.material_profiles(c)
    diffusion = _arrhenius(
        profiles["D_v0"], float(model.params["E_D_eV"]), temp, float(model.params["T0"])
    )
    mobility = _arrhenius(
        profiles["mu_v0"], float(model.params["E_mu_eV"]), temp, float(model.params["T0"])
    )
    reaction_rate = _arrhenius(
        torch.ones_like(c) * _scalar(float(model.params["k_r0"]), c),
        float(model.params["E_r_eV"]),
        temp,
        float(model.params["T0"]),
    )
    average = lambda value: 0.5 * (value[:, :-1] + value[:, 1:])
    concentration_gradient = (c[:, 1:] - c[:, :-1]) / _scalar(model.dx_m, c)
    interior_defect_flux = (
        -average(diffusion) * concentration_gradient
        + average(mobility)
        * average(c)
        * (1.0 - average(c))
        * average(electrical["E"])
    )
    zeros = torch.zeros((c.shape[0], 1), dtype=c.dtype, device=c.device)
    defect_flux = torch.cat([zeros, interior_defect_flux, zeros], dim=1)
    dc_dt = -(
        defect_flux[:, 1:] - defect_flux[:, :-1]
    ) / _scalar(model.dx_m, c) - reaction_rate * (c - _scalar(float(model.params["c_v0"]), c))

    temperature_gradient = (temp[:, 1:] - temp[:, :-1]) / _scalar(model.dx_m, temp)
    interior_heat_flux = -average(profiles["k_th"]) * temperature_gradient
    heat_flux = torch.cat([zeros, interior_heat_flux, zeros], dim=1)
    joule = electrical["J"][:, None] * electrical["E"]
    sink = _scalar(float(model.params["gamma_sub"]), temp) * (
        temp - _scalar(float(model.params["T0"]), temp)
    )
    dT_dt = (
        -(heat_flux[:, 1:] - heat_flux[:, :-1]) / _scalar(model.dx_m, temp)
        + joule
        - sink
    ) / _scalar(float(model.params["rho"]) * float(model.params["Cp"]), temp)
    equilibrium = model.equilibrium_phase(c, temp)
    dm_dt = (equilibrium - phase) / _scalar(float(model.params["tau_m"]), phase)
    return {
        "dc_dt": dc_dt,
        "dT_dt": dT_dt,
        "dm_dt": dm_dt,
        "defect_flux": defect_flux,
        "heat_flux": heat_flux,
        "reaction_rate": reaction_rate,
        "reaction": reaction_rate * (c - _scalar(float(model.params["c_v0"]), c)),
        "joule": joule,
        "sink": sink,
        **electrical,
    }


def model_state_time_derivatives(
    model: ControlVolumeFullPINN, t_norm: torch.Tensor
) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    """Differentiate all learned cell states with one differentiable JVP."""

    time = t_norm.reshape(-1, 1)

    def packed(input_time: torch.Tensor) -> torch.Tensor:
        states = model.dynamic_states(input_time)
        return torch.cat([states["c_v"], states["T"], states["m"]], dim=1)

    packed_states, derivative_norm = torch.autograd.functional.jvp(
        packed,
        time,
        torch.ones_like(time),
        create_graph=True,
        strict=True,
    )
    nx = model.nx
    states = {
        "c_v": packed_states[:, :nx],
        "T": packed_states[:, nx : 2 * nx],
        "m": packed_states[:, 2 * nx :],
    }
    derivatives = {
        "dc_dt": derivative_norm[:, :nx] / model.t_max_s,
        "dT_dt": derivative_norm[:, nx : 2 * nx] / model.t_max_s,
        "dm_dt": derivative_norm[:, 2 * nx :] / model.t_max_s,
    }
    return states, derivatives


def control_volume_residuals(
    model: ControlVolumeFullPINN, t_norm: torch.Tensor
) -> dict[str, torch.Tensor]:
    states, derivatives = model_state_time_derivatives(model, t_norm)
    rhs = torch_cv_rhs(model, t_norm, states["c_v"], states["T"], states["m"])
    scales = model.registry["residual_scales"]
    current_scale = _scalar(float(model.registry["current_density_scale_A_per_m2"]), rhs["E"])
    current_matrix = rhs["sigma"] * rhs["E"]
    return {
        "r_c": (derivatives["dc_dt"] - rhs["dc_dt"]) / float(scales["r_c_per_s"]),
        "r_T": (derivatives["dT_dt"] - rhs["dT_dt"]) / float(scales["r_T_K_per_s"]),
        "r_m": (derivatives["dm_dt"] - rhs["dm_dt"]) / float(scales["r_m_per_s"]),
        "discrete_electrical": (current_matrix - rhs["J"][:, None]) / current_scale,
        "states": states,
        "rhs": rhs,
        "derivatives": derivatives,
    }


def differentiable_ledger_residuals(
    model: ControlVolumeFullPINN, t_norm: torch.Tensor
) -> dict[str, torch.Tensor]:
    """Adjacent-state global ledgers used as explicit training blocks."""

    time = t_norm.reshape(-1, 1)
    order = torch.argsort(time[:, 0])
    time = time[order]
    states = model.dynamic_states(time)
    rhs = torch_cv_rhs(model, time, states["c_v"], states["T"], states["m"])
    dt = (time[1:, 0] - time[:-1, 0]) * model.t_max_s
    dx = _scalar(model.dx_m, states["c_v"])
    mass = torch.sum(states["c_v"], dim=1) * dx
    reaction_integrand = torch.sum(rhs["reaction"], dim=1) * dx
    mass_balance = mass[1:] - mass[:-1] + 0.5 * (
        reaction_integrand[1:] + reaction_integrand[:-1]
    ) * dt
    mass_scale = _scalar(float(model.params["L_eff"]), mass_balance)

    rho_cp = float(model.params["rho"]) * float(model.params["Cp"])
    energy = torch.sum(_scalar(rho_cp, states["T"]) * states["T"], dim=1) * dx
    joule_integrand = torch.sum(rhs["joule"], dim=1) * dx
    sink_integrand = torch.sum(rhs["sink"], dim=1) * dx
    energy_balance = energy[1:] - energy[:-1] - 0.5 * (
        joule_integrand[1:] + joule_integrand[:-1]
    ) * dt + 0.5 * (sink_integrand[1:] + sink_integrand[:-1]) * dt
    energy_scale = _scalar(
        rho_cp * float(model.registry["temperature_scale_K"]) * float(model.params["L_eff"]),
        energy_balance,
    )
    return {
        "defect_mass_ledger": mass_balance / mass_scale,
        "energy_ledger": energy_balance / energy_scale,
    }


def hard_constraint_metrics(model: ControlVolumeFullPINN, t_norm: torch.Tensor) -> dict[str, float]:
    zero = torch.zeros((1, 1), dtype=t_norm.dtype, device=t_norm.device)
    initial = model(zero)
    expected_c = model.c_initial.to(dtype=t_norm.dtype, device=t_norm.device)
    expected_m = model.m_initial.to(dtype=t_norm.dtype, device=t_norm.device)
    output = model(t_norm)
    dx = _scalar(model.dx_m, output["E"])
    left_boundary = output["phi"][:, 0] + 0.5 * output["E"][:, 0] * dx
    right_boundary = output["phi"][:, -1] - 0.5 * output["E"][:, -1] * dx
    voltage_scale = max(float(model.registry["voltage_scale_V"]), 1.0e-30)
    temperature_scale = max(float(model.registry["temperature_scale_K"]), 1.0e-30)
    return {
        "ic_c_v": float(torch.max(torch.abs(initial["c_v"] - expected_c)).detach().cpu()),
        "ic_T": float(
            (torch.max(torch.abs(initial["T"] - float(model.params["T0"]))) / temperature_scale)
            .detach()
            .cpu()
        ),
        "ic_m": float(torch.max(torch.abs(initial["m"] - expected_m)).detach().cpu()),
        "bc_phi_left": float(
            (torch.max(torch.abs(left_boundary - output["V"])) / voltage_scale).detach().cpu()
        ),
        "bc_phi_right": float((torch.max(torch.abs(right_boundary)) / voltage_scale).detach().cpu()),
        "bc_defect_left": 0.0,
        "bc_defect_right": 0.0,
        "bc_heat_left": 0.0,
        "bc_heat_right": 0.0,
    }
