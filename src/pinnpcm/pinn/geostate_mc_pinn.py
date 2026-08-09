"""State-conditioned 2.5D forward PINNs for the R1-Lite fast track.

Three matched-input models are supported: B0 is anchor-only, B1 uses a
second-order strong form, and M0 learns states and sheet fluxes jointly through
first-order mixed constitutive and conservative residuals.  All physical loss
groups are nondimensionalized before fixed weighting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import torch
from torch import nn

from pinnpcm.physics.vo2_constitutive import vo2_sigma


@dataclass(frozen=True)
class GeoStatePINNScales:
    voltage_V: float
    temperature_rise_K: float
    sheet_current_A_m: float
    sheet_heat_flux_W_m: float
    power_W: float


def _gradient(output: torch.Tensor, inputs: torch.Tensor) -> torch.Tensor:
    return torch.autograd.grad(
        output,
        inputs,
        grad_outputs=torch.ones_like(output),
        create_graph=True,
        retain_graph=True,
    )[0]


class GeoStateMCPINN(nn.Module):
    """Hard-BC coordinate network with data-only, strong, or mixed physics."""

    model_kinds = {"B0", "B1", "M0", "M1"}

    def __init__(
        self,
        *,
        model_kind: str,
        config: Mapping[str, Any],
        geometry: Mapping[str, float],
        thermal: Mapping[str, float],
        seed: int,
    ) -> None:
        super().__init__()
        if model_kind not in self.model_kinds:
            raise ValueError(f"unsupported GeoState model kind {model_kind}")
        self.model_kind = model_kind
        self.length_m = float(geometry["length_m"])
        self.width_m = float(geometry["width_m"])
        self.thickness_m = float(geometry["thickness_m"])
        self.contact_overlap_fraction = float(geometry["contact_overlap_m"]) / self.length_m
        self.ambient_temperature_K = float(thermal["ambient_temperature_K"])
        self.vertical_conductance_W_m2K = float(
            thermal["vertical_conductance_W_m2K"]
        )
        self.vo2_sheet_thermal_W_K = float(thermal["vo2_sheet_thermal_W_K"])
        self.electrode_sheet_thermal_W_K = float(
            thermal["electrode_sheet_thermal_W_K"]
        )
        self.sink_rectangle = tuple(float(value) for value in geometry["sink_rectangle_norm"])
        self.sink_amplitude_max = float(geometry["sink_amplitude_max"])
        self.material_params = dict(config["material_params"])
        self.defect_coordinate = float(config["defect_coordinate"])
        self.phase_width_multiplier = 1.0
        scale_values = config["scales"]
        self.scales = GeoStatePINNScales(
            voltage_V=float(scale_values["voltage_V"]),
            temperature_rise_K=float(scale_values["temperature_rise_K"]),
            sheet_current_A_m=float(scale_values["sheet_current_A_m"]),
            sheet_heat_flux_W_m=float(scale_values["sheet_heat_flux_W_m"]),
            power_W=float(scale_values["power_W"]),
        )
        torch.manual_seed(int(seed))
        width = int(config["hidden_width"])
        layers = int(config["hidden_layers"])
        modules: list[nn.Module] = []
        previous = 10
        for _ in range(layers):
            modules.extend([nn.Linear(previous, width), nn.Tanh()])
            previous = width
        output_size = 2 if model_kind == "B1" else 6
        modules.append(nn.Linear(previous, output_size))
        self.network = nn.Sequential(*modules)

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def _sink_signed_distance(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        x0, x1, y0, y1 = self.sink_rectangle
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * (y0 + y1)
        hx = 0.5 * (x1 - x0)
        hy = 0.5 * (y1 - y0)
        qx = torch.abs(x - cx) - hx
        qy = torch.abs(y - cy) - hy
        outside = torch.sqrt(torch.clamp(qx, min=0.0).square() + torch.clamp(qy, min=0.0).square() + 1.0e-12)
        inside = torch.clamp(torch.maximum(qx, qy), max=0.0)
        return outside + inside

    def _region_feature(self, x: torch.Tensor) -> torch.Tensor:
        contact = (x < self.contact_overlap_fraction) | (
            x > 1.0 - self.contact_overlap_fraction
        )
        return contact.to(dtype=x.dtype)

    def feature_map(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim != 2 or inputs.shape[1] != 6:
            raise ValueError("GeoState inputs must be [x,y,V,b,s,sink]")
        x = inputs[:, 0:1]
        y = inputs[:, 1:2]
        voltage = inputs[:, 2:3]
        branch = inputs[:, 3:4]
        state = inputs[:, 4:5]
        sink = inputs[:, 5:6] / max(self.sink_amplitude_max, 1.0e-12)
        left_distance = x - self.contact_overlap_fraction
        right_distance = (1.0 - self.contact_overlap_fraction) - x
        sink_distance = self._sink_signed_distance(x, y)
        region = self._region_feature(x)
        return torch.cat(
            [
                x,
                y,
                voltage,
                branch,
                state,
                left_distance,
                right_distance,
                sink_distance,
                sink,
                region,
            ],
            dim=1,
        )

    def conductivity(self, temperature_K: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        defect = torch.full_like(temperature_K, self.defect_coordinate)
        state_clamped = torch.clamp(state, 1.0e-6, 1.0 - 1.0e-6)
        if self.model_kind == "M1":
            state_logit = torch.log(state_clamped) - torch.log1p(-state_clamped)
            state_clamped = torch.sigmoid(
                state_logit / float(self.phase_width_multiplier)
            )
        return vo2_sigma(
            temperature_K,
            defect,
            m=state_clamped,
            params=self.material_params,
        )

    def set_phase_width_multiplier(self, multiplier: float) -> None:
        value = float(multiplier)
        if value < 1.0:
            raise ValueError("phase-width homotopy multiplier must be at least one")
        self.phase_width_multiplier = value

    def _base_outputs(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = self.network(self.feature_map(inputs))
        x = inputs[:, 0:1]
        voltage_norm = inputs[:, 2:3]
        state = inputs[:, 4:5]
        voltage = self.scales.voltage_V * voltage_norm
        ambient = torch.full_like(x, self.ambient_temperature_K)
        sigma_ambient = self.conductivity(ambient, state)
        uniform_rise = (
            self.thickness_m
            * sigma_ambient
            * (voltage / self.length_m).square()
            / self.vertical_conductance_W_m2K
        )
        phi = voltage * (1.0 - x) + 0.25 * voltage * x * (1.0 - x) * torch.tanh(raw[:, 0:1])
        temperature = ambient + uniform_rise * torch.exp(
            0.75 * torch.tanh(raw[:, 1:2])
        )
        outputs: dict[str, torch.Tensor] = {
            "phi_V": phi,
            "T_K": temperature,
        }
        if self.model_kind != "B1":
            current_base = self.thickness_m * sigma_ambient * voltage / self.length_m
            outputs.update(
                {
                    "Jx_A_m": current_base * (1.0 + 0.5 * torch.tanh(raw[:, 2:3])),
                    "Jy_A_m": self.scales.sheet_current_A_m
                    * voltage_norm
                    * 0.2
                    * torch.tanh(raw[:, 3:4]),
                    "qx_W_m": self.scales.sheet_heat_flux_W_m
                    * voltage_norm.square()
                    * torch.tanh(raw[:, 4:5]),
                    "qy_W_m": self.scales.sheet_heat_flux_W_m
                    * voltage_norm.square()
                    * torch.tanh(raw[:, 5:6]),
                }
            )
        return outputs

    def _physical_gradients(
        self, outputs: Mapping[str, torch.Tensor], inputs: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        grad_phi = _gradient(outputs["phi_V"], inputs)
        grad_T = _gradient(outputs["T_K"], inputs)
        return {
            "dphi_dx": grad_phi[:, 0:1] / self.length_m,
            "dphi_dy": grad_phi[:, 1:2] / self.width_m,
            "dT_dx": grad_T[:, 0:1] / self.length_m,
            "dT_dy": grad_T[:, 1:2] / self.width_m,
        }

    def _sheet_thermal(self, x: torch.Tensor) -> torch.Tensor:
        return self.vo2_sheet_thermal_W_K + self._region_feature(x) * self.electrode_sheet_thermal_W_K

    def field_outputs(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        if not inputs.requires_grad and self.model_kind == "B1":
            inputs.requires_grad_(True)
        outputs = self._base_outputs(inputs)
        if self.model_kind == "B1":
            gradients = self._physical_gradients(outputs, inputs)
            sigma = self.conductivity(outputs["T_K"], inputs[:, 4:5])
            k_sheet = self._sheet_thermal(inputs[:, 0:1])
            outputs.update(
                {
                    "Jx_A_m": -self.thickness_m * sigma * gradients["dphi_dx"],
                    "Jy_A_m": -self.thickness_m * sigma * gradients["dphi_dy"],
                    "qx_W_m": -k_sheet * gradients["dT_dx"],
                    "qy_W_m": -k_sheet * gradients["dT_dy"],
                }
            )
        return outputs

    def sink_conductance(self, inputs: torch.Tensor) -> torch.Tensor:
        x0, x1, y0, y1 = self.sink_rectangle
        x = inputs[:, 0:1]
        y = inputs[:, 1:2]
        mask = ((x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)).to(x.dtype)
        return self.vertical_conductance_W_m2K * (
            1.0 + inputs[:, 5:6] * mask
        )

    def residual_groups(
        self,
        inputs: torch.Tensor,
        *,
        joule_feedback: float = 1.0,
    ) -> dict[str, torch.Tensor]:
        if self.model_kind == "B0":
            raise ValueError("B0 has no physics residual")
        if not inputs.requires_grad:
            inputs.requires_grad_(True)
        outputs = self.field_outputs(inputs)
        gradients = self._physical_gradients(outputs, inputs)
        sigma = self.conductivity(outputs["T_K"], inputs[:, 4:5])
        k_sheet = self._sheet_thermal(inputs[:, 0:1])
        Jx = outputs["Jx_A_m"]
        Jy = outputs["Jy_A_m"]
        qx = outputs["qx_W_m"]
        qy = outputs["qy_W_m"]
        grad_Jx = _gradient(Jx, inputs)
        grad_Jy = _gradient(Jy, inputs)
        grad_qx = _gradient(qx, inputs)
        grad_qy = _gradient(qy, inputs)
        div_J = grad_Jx[:, 0:1] / self.length_m + grad_Jy[:, 1:2] / self.width_m
        div_q = grad_qx[:, 0:1] / self.length_m + grad_qy[:, 1:2] / self.width_m
        joule = self.thickness_m * sigma * (
            gradients["dphi_dx"].square() + gradients["dphi_dy"].square()
        )
        sink = self.sink_conductance(inputs) * (
            outputs["T_K"] - self.ambient_temperature_K
        )
        current_div_scale = self.scales.sheet_current_A_m / self.length_m
        heat_div_scale = self.scales.sheet_heat_flux_W_m / self.length_m
        groups: dict[str, torch.Tensor] = {
            "current_conservation": div_J / current_div_scale,
            "energy_conservation": (div_q - float(joule_feedback) * joule + sink)
            / heat_div_scale,
        }
        if self.model_kind in {"M0", "M1"}:
            groups.update(
                {
                    "current_constitutive_x": (
                        Jx + self.thickness_m * sigma * gradients["dphi_dx"]
                    )
                    / self.scales.sheet_current_A_m,
                    "current_constitutive_y": (
                        Jy + self.thickness_m * sigma * gradients["dphi_dy"]
                    )
                    / self.scales.sheet_current_A_m,
                    "heat_constitutive_x": (qx + k_sheet * gradients["dT_dx"])
                    / self.scales.sheet_heat_flux_W_m,
                    "heat_constitutive_y": (qy + k_sheet * gradients["dT_dy"])
                    / self.scales.sheet_heat_flux_W_m,
                }
            )
        return groups

    def normalized_outputs(
        self, outputs: Mapping[str, torch.Tensor]
    ) -> dict[str, torch.Tensor]:
        return {
            "phi_V": outputs["phi_V"] / self.scales.voltage_V,
            "T_K": (outputs["T_K"] - self.ambient_temperature_K)
            / self.scales.temperature_rise_K,
            "Jx_A_m": outputs["Jx_A_m"] / self.scales.sheet_current_A_m,
            "Jy_A_m": outputs["Jy_A_m"] / self.scales.sheet_current_A_m,
            "qx_W_m": outputs["qx_W_m"] / self.scales.sheet_heat_flux_W_m,
            "qy_W_m": outputs["qy_W_m"] / self.scales.sheet_heat_flux_W_m,
        }

    def anchor_loss(
        self, inputs: torch.Tensor, targets: Mapping[str, torch.Tensor]
    ) -> torch.Tensor:
        outputs = self.normalized_outputs(self.field_outputs(inputs))
        return torch.stack(
            [torch.mean((outputs[name] - targets[name]) ** 2) for name in outputs]
        ).mean()

    def interface_loss(
        self, minus_inputs: torch.Tensor, plus_inputs: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        if not minus_inputs.requires_grad:
            minus_inputs.requires_grad_(True)
        if not plus_inputs.requires_grad:
            plus_inputs.requires_grad_(True)
        minus = self.field_outputs(minus_inputs)
        plus = self.field_outputs(plus_inputs)
        state_continuity = 0.5 * (
            torch.mean(((minus["phi_V"] - plus["phi_V"]) / self.scales.voltage_V) ** 2)
            + torch.mean(((minus["T_K"] - plus["T_K"]) / self.scales.temperature_rise_K) ** 2)
        )
        flux_continuity = 0.5 * (
            torch.mean(((minus["Jx_A_m"] - plus["Jx_A_m"]) / self.scales.sheet_current_A_m) ** 2)
            + torch.mean(((minus["qx_W_m"] - plus["qx_W_m"]) / self.scales.sheet_heat_flux_W_m) ** 2)
        )
        return state_continuity + flux_continuity, {
            "state_continuity": state_continuity,
            "normal_flux_continuity": flux_continuity,
        }
