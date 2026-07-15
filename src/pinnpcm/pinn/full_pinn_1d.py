"""Versioned complete 1D phase-transition PINN architecture.

This module is intentionally separate from the historical lightweight PINN
path.  The network predicts physical state variables only.  Conductivity and
terminal current are derived from those states and the declared physics.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

import torch
from torch import nn

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.network import StiffAwareMLP


def _tensor(value: float, like: torch.Tensor) -> torch.Tensor:
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
    exponent = -activation_e_ev / K_B_EV_PER_K * (
        1.0 / safe_temperature - 1.0 / reference_temperature
    )
    return prefactor * torch.exp(torch.clamp(exponent, -80.0, 80.0))


@dataclass(frozen=True)
class EventLedgerState:
    """Piecewise-constant hysteresis history outside the neural state.

    The ledger is inactive for frozen GT v1.1, whose continuous phase fraction
    is sufficient. Explicit hysteretic VO2 protocols may enable this map; it is
    never replaced by an unconstrained learned event head.
    """

    branch: str
    reversal_temperature_K: float
    reversal_phase: float
    previous_temperature_K: float


def update_event_ledger(
    state: EventLedgerState,
    *,
    temperature_K: float,
    phase: float,
    reversal_delta_T_threshold_K: float = 0.01,
) -> EventLedgerState:
    """Apply a deterministic reversal map after one accepted time step."""

    delta = float(temperature_K) - float(state.previous_temperature_K)
    threshold = float(reversal_delta_T_threshold_K)
    new_branch = state.branch
    if delta > threshold:
        new_branch = "heating"
    elif delta < -threshold:
        new_branch = "cooling"
    changed = new_branch != state.branch
    return replace(
        state,
        branch=new_branch,
        reversal_temperature_K=float(temperature_K) if changed else state.reversal_temperature_K,
        reversal_phase=float(phase) if changed else state.reversal_phase,
        previous_temperature_K=float(temperature_K),
    )


class FullPINN1D(nn.Module):
    """State PINN with hard electrical and initial constraints.

    Coordinates are normalized as ``(x/L, t/t_max)``.  The four neural outputs
    map to ``phi, c_v, T, m``.  There is deliberately no independent
    conductivity output.
    """

    def __init__(
        self,
        *,
        params: dict[str, Any] | None = None,
        t_max_s: float = 3.0e-3,
        hidden_dim: int = 48,
        hidden_layers: int = 3,
        fourier_scales: list[float] | tuple[float, ...] = (1.0, 2.0, 4.0, 8.0),
        voltage_scale_v: float = 0.20,
        temperature_scale_k: float = 20.0,
        seed: int = 20260715,
    ) -> None:
        super().__init__()
        torch.manual_seed(int(seed))
        self.params = merge_params(params)
        self.t_max_s = float(t_max_s)
        self.voltage_scale_v = float(voltage_scale_v)
        self.temperature_scale_k = float(temperature_scale_k)
        self.backbone = StiffAwareMLP(
            in_dim=2,
            out_dim=4,
            hidden_dim=int(hidden_dim),
            hidden_layers=int(hidden_layers),
            scales=tuple(float(value) for value in fourier_scales),
            use_fourier=True,
        )

    @property
    def state_names(self) -> tuple[str, ...]:
        return ("phi", "c_v", "T", "m")

    def voltage(self, t_norm: torch.Tensor) -> torch.Tensor:
        """Frozen triangle protocol in differentiable form."""

        phase = torch.clamp(t_norm, 0.0, 1.0)
        peak = _tensor(float(self.params["triangle_v_peak"]), phase)
        return torch.where(
            phase <= 0.5,
            -peak + 4.0 * peak * phase,
            3.0 * peak - 4.0 * peak * phase,
        )

    def material_profiles(self, x_norm: torch.Tensor) -> dict[str, torch.Tensor]:
        """Return declared uniform or bilayer coefficient profiles."""

        mode = str(self.params.get("layer_profile", "uniform"))
        profiles: dict[str, torch.Tensor] = {}
        keys = ("sigma_off0", "sigma_on0", "D_v0", "mu_v0", "k_th")
        if mode == "uniform":
            for key in keys:
                profiles[key] = torch.ones_like(x_norm) * _tensor(float(self.params[key]), x_norm)
            return profiles
        if mode != "bilayer":
            raise ValueError(f"Unsupported layer_profile: {mode}")

        interface = float(self.params["L_int"]) / float(self.params["L_eff"])
        left = x_norm <= interface
        mapping = {
            "sigma_off0": ("nb_oxide_sigma_off0", "v2o5_sigma_off0"),
            "sigma_on0": ("nb_oxide_sigma_on0", "v2o5_sigma_on0"),
            "D_v0": ("nb_oxide_D_v0", "v2o5_D_v0"),
            "mu_v0": ("nb_oxide_mu_v0", "v2o5_mu_v0"),
            "k_th": ("nb_oxide_k_th", "v2o5_k_th"),
        }
        for key, (left_key, right_key) in mapping.items():
            profiles[key] = torch.where(
                left,
                torch.ones_like(x_norm) * _tensor(float(self.params[left_key]), x_norm),
                torch.ones_like(x_norm) * _tensor(float(self.params[right_key]), x_norm),
            )
        return profiles

    def initial_defect(self, x_norm: torch.Tensor) -> torch.Tensor:
        """Frozen GT v1.1 initial defect field, including its Gaussian seed."""

        base = torch.ones_like(x_norm) * _tensor(float(self.params["c_v0"]), x_norm)
        mode = str(self.params.get("initial_defect_mode", "uniform"))
        if mode == "uniform":
            return base
        if mode not in {"gaussian_seed", "seeded_defect"}:
            raise ValueError(f"Unsupported initial_defect_mode: {mode}")
        x_m = x_norm * _tensor(float(self.params["L_eff"]), x_norm)
        seeded = base + _tensor(float(self.params["gaussian_delta_c"]), x_norm) * torch.exp(
            -0.5
            * ((x_m - _tensor(float(self.params["gaussian_x_d"]), x_norm))
               / _tensor(float(self.params["gaussian_w_d"]), x_norm))
            ** 2
        )
        return torch.clamp(seeded, 1.0e-7, 1.0 - 1.0e-7)

    def equilibrium_phase(self, c_v: torch.Tensor, temperature: torch.Tensor) -> torch.Tensor:
        argument = (
            temperature
            - _tensor(float(self.params["T_sw"]), temperature)
            + _tensor(float(self.params["alpha_c"]), temperature)
            * (c_v - _tensor(float(self.params["c_v0"]), temperature))
        ) / _tensor(float(self.params["dT_sw"]), temperature)
        return torch.sigmoid(argument)

    def conductivity(
        self,
        c_v: torch.Tensor,
        temperature: torch.Tensor,
        m: torch.Tensor,
        profiles: dict[str, torch.Tensor],
    ) -> torch.Tensor:
        """Physical conductivity closure; never an independent network output."""

        thermal_factor = _arrhenius(
            torch.ones_like(temperature),
            float(self.params["E_off_eV"]),
            temperature,
            float(self.params["T0"]),
        )
        c_delta = c_v - _tensor(float(self.params["c_v0"]), c_v)
        sigma_off = profiles["sigma_off0"] * thermal_factor * torch.exp(
            torch.clamp(_tensor(float(self.params["beta_off"]), c_v) * c_delta, -80.0, 80.0)
        )
        sigma_on = profiles["sigma_on0"] * torch.exp(
            torch.clamp(_tensor(float(self.params["beta_on"]), c_v) * c_delta, -80.0, 80.0)
        )
        eps = _tensor(float(self.params["eps_sigma"]), c_v)
        log_sigma = (1.0 - m) * torch.log(torch.clamp(sigma_off, min=eps)) + m * torch.log(
            torch.clamp(sigma_on, min=eps)
        )
        return torch.exp(torch.clamp(log_sigma, -80.0, 80.0))

    def forward(self, coords: torch.Tensor) -> dict[str, torch.Tensor]:
        if coords.shape[-1] != 2:
            raise ValueError("coords must contain normalized (x, t).")
        x_norm = coords[..., 0:1]
        t_norm = coords[..., 1:2]
        raw = self.backbone(coords)
        voltage = self.voltage(t_norm)

        phi = voltage * x_norm + _tensor(self.voltage_scale_v, x_norm) * x_norm * (1.0 - x_norm) * raw[..., 0:1]
        c_initial = self.initial_defect(x_norm)
        c_v = torch.sigmoid(_safe_logit(c_initial) + t_norm * raw[..., 1:2])
        temperature = _tensor(float(self.params["T0"]), x_norm) + t_norm * _tensor(
            self.temperature_scale_k, x_norm
        ) * torch.nn.functional.softplus(raw[..., 2:3])
        m_initial = self.equilibrium_phase(
            c_initial,
            torch.ones_like(c_initial) * _tensor(float(self.params["T0"]), c_initial),
        )
        m = torch.sigmoid(_safe_logit(m_initial) + t_norm * raw[..., 3:4])
        profiles = self.material_profiles(x_norm)
        sigma = self.conductivity(c_v, temperature, m, profiles)
        return {
            "phi": phi,
            "c_v": c_v,
            "T": temperature,
            "m": m,
            "sigma": sigma,
            "V": voltage,
            "profiles": profiles,
        }

    def port_observation(self, sigma_tx: torch.Tensor, voltage_t: torch.Tensor) -> dict[str, torch.Tensor]:
        """Series-resistance terminal operator on a uniform cell-center grid."""

        if sigma_tx.ndim != 2:
            raise ValueError("sigma_tx must have shape (n_t, n_x).")
        resistance_area = _tensor(float(self.params["L_eff"]), sigma_tx) * torch.mean(
            1.0 / torch.clamp(sigma_tx, min=_tensor(float(self.params["eps_sigma"]), sigma_tx)), dim=-1
        )
        active_area = float(self.params["eta_A"]) * float(self.params["A_contact"])
        current = _tensor(active_area, sigma_tx) * voltage_t.reshape(-1) / resistance_area
        conductance = current / (
            voltage_t.reshape(-1) + _tensor(float(self.params["eps_V"]), sigma_tx)
        )
        return {"I": current, "G": conductance, "R_area": resistance_area}

    def contract(self) -> dict[str, Any]:
        """Serializable scientific architecture contract."""

        return {
            "contract_id": "full_pinn_architecture_v1",
            "coordinate_system": {"x": "x/L_eff", "t": "t/t_max"},
            "states": list(self.state_names),
            "state_network": True,
            "conductivity": "derived_from_c_v_T_m_and_material_parameters",
            "independent_log_sigma_output": False,
            "residuals": ["r_phi", "r_c", "r_T", "r_m"],
            "initial_conditions": ["c_v_gaussian_seed", "T_0", "m_equilibrium"],
            "boundary_conditions": ["phi_dirichlet", "zero_defect_flux", "zero_heat_flux"],
            "interface_conditions": ["current_flux", "defect_flux", "heat_flux"],
            "history_state": {
                "continuous": "m",
                "event_ledger": ["branch", "reversal_temperature_K", "reversal_phase"],
                "frozen_gt_event_ledger_active": False,
                "learned_event_head": False,
                "implementation": "EventLedgerState + update_event_ledger explicit map",
            },
            "observation_operator": "I=A_eff*V/integral(dx/sigma)",
            "inverse_outputs": ["identifiable_quotient", "equivalence_class"],
            "training_evidence": "PDE_IC_BC_only; frozen full fields score-only",
            "claim_scope": "conditional 1D synthetic forward evidence only",
        }


def clone_parameter_dict(params: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive copy for audit utilities."""

    return deepcopy(params)
