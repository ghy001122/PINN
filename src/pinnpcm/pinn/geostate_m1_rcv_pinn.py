"""M1-consistent three-region neural fields for the bounded RCV rescue."""

from __future__ import annotations

from typing import Any, Mapping

import torch
from torch import nn
from torch.nn import functional as F

from pinnpcm.physics.vo2_constitutive import vo2_sigma


def _gradient(output: torch.Tensor, inputs: torch.Tensor) -> torch.Tensor:
    return torch.autograd.grad(
        output,
        inputs,
        grad_outputs=torch.ones_like(output),
        create_graph=True,
        retain_graph=True,
    )[0]


class GeoStateM1RCVPINN(nn.Module):
    """Shared trunk with explicit left-contact, bare, and right-contact heads."""

    model_kinds = {"B0-R", "B1-R", "P0-RCV"}

    def __init__(
        self,
        *,
        model_kind: str,
        config: Mapping[str, Any],
        geometry: Mapping[str, float],
        thermal: Mapping[str, float],
        material_params: Mapping[str, Any],
        seed: int,
    ) -> None:
        super().__init__()
        if model_kind not in self.model_kinds:
            raise ValueError(f"unsupported model kind {model_kind}")
        self.model_kind = model_kind
        self.length_m = float(geometry["length_m"])
        self.width_m = float(geometry["width_m"])
        self.thickness_m = float(geometry["thickness_m"])
        self.contact_fraction = float(geometry["contact_overlap_m"]) / self.length_m
        self.sink_rectangle = tuple(float(v) for v in geometry["sink_rectangle_norm"])
        self.sink_amplitude_max = float(geometry["sink_amplitude_max"])
        self.ambient_temperature_K = float(thermal["ambient_temperature_K"])
        self.vertical_conductance_W_m2K = float(
            thermal["vertical_conductance_W_m2K"]
        )
        self.vo2_sheet_thermal_W_K = float(thermal["vo2_sheet_thermal_W_K"])
        self.electrode_sheet_thermal_W_K = float(
            thermal["electrode_sheet_thermal_W_K"]
        )
        self.rc_left_ohm = float(config["rc_left_ohm"])
        self.rc_right_ohm = float(config["rc_right_ohm"])
        self.rth_left_m2K_W = float(config["rth_left_m2K_W"])
        self.rth_right_m2K_W = float(config["rth_right_m2K_W"])
        self.voltage_scale_V = float(config["voltage_scale_V"])
        self.temperature_scale_K = float(config["temperature_rise_scale_K"])
        self.current_scale_A_m = float(config["sheet_current_scale_A_m"])
        self.heat_flux_scale_W_m = float(config["sheet_heat_flux_scale_W_m"])
        self.current_floor_A_m = (
            float(config["current_floor_fraction"]) * self.current_scale_A_m
        )
        self.heat_flux_floor_W_m = (
            float(config["heat_flux_floor_fraction"]) * self.heat_flux_scale_W_m
        )
        self.material_params = dict(material_params)
        self.defect_coordinate = float(config["defect_coordinate"])

        torch.manual_seed(int(seed))
        width = int(config["trunk_width"])
        layers = int(config["trunk_layers"])
        modules: list[nn.Module] = []
        previous = 9
        for _ in range(layers):
            modules.extend([nn.Linear(previous, width), nn.Tanh()])
            previous = width
        self.trunk = nn.Sequential(*modules)
        head_width = int(config["head_width"])
        output_size = 6 if model_kind == "P0-RCV" else 2
        self.region_heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(width, head_width),
                    nn.Tanh(),
                    nn.Linear(head_width, output_size),
                )
                for _ in range(3)
            ]
        )

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def _sink_signed_distance(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        x0, x1, y0, y1 = self.sink_rectangle
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        hx, hy = 0.5 * (x1 - x0), 0.5 * (y1 - y0)
        qx, qy = torch.abs(x - cx) - hx, torch.abs(y - cy) - hy
        outside = torch.sqrt(
            torch.clamp(qx, min=0.0).square()
            + torch.clamp(qy, min=0.0).square()
            + 1.0e-18
        )
        return outside + torch.clamp(torch.maximum(qx, qy), max=0.0)

    def feature_map(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim != 2 or inputs.shape[1] != 6:
            raise ValueError("inputs must be [x,y,Vd,branch,state,sink]")
        x, y = inputs[:, 0:1], inputs[:, 1:2]
        sink = inputs[:, 5:6] / max(self.sink_amplitude_max, 1.0e-30)
        return torch.cat(
            [
                x,
                y,
                inputs[:, 2:3],
                inputs[:, 3:4],
                inputs[:, 4:5],
                sink,
                x - self.contact_fraction,
                (1.0 - self.contact_fraction) - x,
                self._sink_signed_distance(x, y),
            ],
            dim=1,
        )

    def region_ids(self, x: torch.Tensor) -> torch.Tensor:
        return torch.where(
            x < self.contact_fraction,
            torch.zeros_like(x, dtype=torch.long),
            torch.where(
                x > 1.0 - self.contact_fraction,
                torch.full_like(x, 2, dtype=torch.long),
                torch.ones_like(x, dtype=torch.long),
            ),
        )

    def raw_outputs(
        self, inputs: torch.Tensor, *, region_override: int | torch.Tensor | None = None
    ) -> torch.Tensor:
        shared = self.trunk(self.feature_map(inputs))
        candidates = torch.stack([head(shared) for head in self.region_heads], dim=1)
        if region_override is None:
            region = self.region_ids(inputs[:, 0]).reshape(-1)
        elif isinstance(region_override, int):
            region = torch.full(
                (inputs.shape[0],), region_override, dtype=torch.long, device=inputs.device
            )
        else:
            region = region_override.to(dtype=torch.long, device=inputs.device).reshape(-1)
        index = region[:, None, None].expand(-1, 1, candidates.shape[-1])
        return torch.gather(candidates, 1, index).squeeze(1)

    def conductivity(self, temperature_K: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        defect = torch.full_like(temperature_K, self.defect_coordinate)
        return vo2_sigma(
            temperature_K,
            defect,
            m=torch.clamp(state, 1.0e-6, 1.0 - 1.0e-6),
            params=self.material_params,
        )

    def state_fields(
        self, inputs: torch.Tensor, *, region_override: int | torch.Tensor | None = None
    ) -> dict[str, torch.Tensor]:
        raw = self.raw_outputs(inputs, region_override=region_override)
        voltage_norm = inputs[:, 2:3]
        voltage = voltage_norm * self.voltage_scale_V
        phi = voltage * torch.sigmoid(raw[:, 0:1])
        temperature = self.ambient_temperature_K + (
            voltage_norm.square()
            * self.temperature_scale_K
            * F.softplus(raw[:, 1:2])
        )
        return {"phi_V": phi, "T_K": temperature, "raw": raw}

    def physical_gradients(
        self, states: Mapping[str, torch.Tensor], inputs: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        grad_phi = _gradient(states["phi_V"], inputs)
        grad_t = _gradient(states["T_K"], inputs)
        return {
            "dphi_dx": grad_phi[:, 0:1] / self.length_m,
            "dphi_dy": grad_phi[:, 1:2] / self.width_m,
            "dT_dx": grad_t[:, 0:1] / self.length_m,
            "dT_dy": grad_t[:, 1:2] / self.width_m,
        }

    def sheet_thermal_conductance(
        self, inputs: torch.Tensor, region_override: int | torch.Tensor | None = None
    ) -> torch.Tensor:
        if region_override is None:
            region = self.region_ids(inputs[:, 0]).reshape(-1, 1)
        elif isinstance(region_override, int):
            region = torch.full_like(inputs[:, 0:1], region_override, dtype=torch.long)
        else:
            region = region_override.to(dtype=torch.long, device=inputs.device).reshape(-1, 1)
        contact = (region != 1).to(dtype=inputs.dtype)
        return self.vo2_sheet_thermal_W_K + contact * self.electrode_sheet_thermal_W_K

    def sink_conductance(
        self, inputs: torch.Tensor, region_override: int | torch.Tensor | None = None
    ) -> torch.Tensor:
        x, y = inputs[:, 0:1], inputs[:, 1:2]
        x0, x1, y0, y1 = self.sink_rectangle
        patch = ((x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)).to(inputs.dtype)
        local = self.vertical_conductance_W_m2K * (1.0 + inputs[:, 5:6] * patch)
        if region_override is None:
            region = self.region_ids(inputs[:, 0]).reshape(-1, 1)
        elif isinstance(region_override, int):
            region = torch.full_like(inputs[:, 0:1], region_override, dtype=torch.long)
        else:
            region = region_override.to(dtype=torch.long, device=inputs.device).reshape(-1, 1)
        resistance = torch.where(
            region == 0,
            torch.full_like(local, self.rth_left_m2K_W),
            torch.where(
                region == 2,
                torch.full_like(local, self.rth_right_m2K_W),
                torch.zeros_like(local),
            ),
        )
        return 1.0 / (1.0 / local + resistance)

    def field_outputs(
        self, inputs: torch.Tensor, *, region_override: int | torch.Tensor | None = None
    ) -> dict[str, torch.Tensor]:
        if not inputs.requires_grad:
            inputs.requires_grad_(True)
        states = self.state_fields(inputs, region_override=region_override)
        gradients = self.physical_gradients(states, inputs)
        sigma = self.conductivity(states["T_K"], inputs[:, 4:5])
        sheet = self.sheet_thermal_conductance(inputs, region_override)
        if self.model_kind == "P0-RCV":
            raw = states["raw"]
            voltage_norm = inputs[:, 2:3]
            Jx = voltage_norm * self.current_scale_A_m * 1.25 * torch.tanh(raw[:, 2:3])
            Jy = voltage_norm * self.current_scale_A_m * 0.25 * torch.tanh(raw[:, 3:4])
            qx = voltage_norm.square() * self.heat_flux_scale_W_m * torch.tanh(raw[:, 4:5])
            qy = voltage_norm.square() * self.heat_flux_scale_W_m * torch.tanh(raw[:, 5:6])
        else:
            Jx = -self.thickness_m * sigma * gradients["dphi_dx"]
            Jy = -self.thickness_m * sigma * gradients["dphi_dy"]
            qx = -sheet * gradients["dT_dx"]
            qy = -sheet * gradients["dT_dy"]
        return {
            "phi_V": states["phi_V"],
            "T_K": states["T_K"],
            "Jx_A_m": Jx,
            "Jy_A_m": Jy,
            "qx_W_m": qx,
            "qy_W_m": qy,
            "sigma_S_m": sigma,
            **gradients,
        }

    def anchor_loss(
        self, inputs: torch.Tensor, target_phi: torch.Tensor, target_t: torch.Tensor
    ) -> torch.Tensor:
        states = self.state_fields(inputs)
        phi = states["phi_V"] / self.voltage_scale_V
        temperature = (states["T_K"] - self.ambient_temperature_K) / self.temperature_scale_K
        return 0.5 * (torch.mean((phi - target_phi) ** 2) + torch.mean((temperature - target_t) ** 2))

    def constitutive_loss(self, inputs: torch.Tensor) -> torch.Tensor:
        if self.model_kind != "P0-RCV":
            return torch.zeros((), dtype=inputs.dtype, device=inputs.device)
        fields = self.field_outputs(inputs)
        sheet = self.sheet_thermal_conductance(inputs)
        residuals = (
            (fields["Jx_A_m"] + self.thickness_m * fields["sigma_S_m"] * fields["dphi_dx"])
            / self.current_scale_A_m,
            (fields["Jy_A_m"] + self.thickness_m * fields["sigma_S_m"] * fields["dphi_dy"])
            / self.current_scale_A_m,
            (fields["qx_W_m"] + sheet * fields["dT_dx"]) / self.heat_flux_scale_W_m,
            (fields["qy_W_m"] + sheet * fields["dT_dy"]) / self.heat_flux_scale_W_m,
        )
        return torch.stack([torch.mean(value.square()) for value in residuals]).mean()

    def strong_form_losses(self, inputs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        fields = self.field_outputs(inputs)
        grad_jx, grad_jy = _gradient(fields["Jx_A_m"], inputs), _gradient(fields["Jy_A_m"], inputs)
        grad_qx, grad_qy = _gradient(fields["qx_W_m"], inputs), _gradient(fields["qy_W_m"], inputs)
        div_j = grad_jx[:, 0:1] / self.length_m + grad_jy[:, 1:2] / self.width_m
        div_q = grad_qx[:, 0:1] / self.length_m + grad_qy[:, 1:2] / self.width_m
        joule = self.thickness_m * fields["sigma_S_m"] * (
            fields["dphi_dx"].square() + fields["dphi_dy"].square()
        )
        sink = self.sink_conductance(inputs) * (
            fields["T_K"] - self.ambient_temperature_K
        )
        current = div_j / (self.current_scale_A_m / self.length_m)
        energy = (div_q - joule + sink) / (self.heat_flux_scale_W_m / self.length_m)
        return torch.mean(current.square()), torch.mean(energy.square())

    def external_robin(
        self, left_inputs: torch.Tensor, right_inputs: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        left = self.field_outputs(left_inputs, region_override=0)
        right = self.field_outputs(right_inputs, region_override=2)
        left_contact_j = (
            left_inputs[:, 2:3] * self.voltage_scale_V - left["phi_V"]
        ) / (self.rc_left_ohm * self.width_m)
        right_contact_j = right["phi_V"] / (self.rc_right_ohm * self.width_m)
        residual_left = (left["Jx_A_m"] - left_contact_j) / self.current_scale_A_m
        residual_right = (right["Jx_A_m"] - right_contact_j) / self.current_scale_A_m
        loss = 0.5 * (torch.mean(residual_left.square()) + torch.mean(residual_right.square()))
        return loss, {
            "left_contact_J_A_m": left_contact_j,
            "right_contact_J_A_m": right_contact_j,
            "left_flux_J_A_m": left["Jx_A_m"],
            "right_flux_J_A_m": right["Jx_A_m"],
        }

    def interface_terms(
        self, inputs: torch.Tensor, interface_ids: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        ids = interface_ids.to(dtype=torch.long, device=inputs.device).reshape(-1)
        minus_regions = torch.where(ids == 0, torch.zeros_like(ids), torch.ones_like(ids))
        plus_regions = torch.where(ids == 0, torch.ones_like(ids), torch.full_like(ids, 2))
        minus = self.field_outputs(inputs, region_override=minus_regions)
        plus = self.field_outputs(inputs, region_override=plus_regions)
        state_loss = 0.5 * (
            torch.mean(((minus["phi_V"] - plus["phi_V"]) / self.voltage_scale_V).square())
            + torch.mean(((minus["T_K"] - plus["T_K"]) / self.temperature_scale_K).square())
        )
        j_difference = torch.sqrt(torch.mean((minus["Jx_A_m"] - plus["Jx_A_m"]).square()))
        j_denominator = torch.sqrt(
            0.5 * torch.mean(minus["Jx_A_m"].square() + plus["Jx_A_m"].square())
            + self.current_floor_A_m**2
        )
        q_difference = torch.sqrt(torch.mean((minus["qx_W_m"] - plus["qx_W_m"]).square()))
        q_denominator = torch.sqrt(
            0.5 * torch.mean(minus["qx_W_m"].square() + plus["qx_W_m"].square())
            + self.heat_flux_floor_W_m**2
        )
        e_j, e_q = j_difference / j_denominator, q_difference / q_denominator
        flux_metric = torch.maximum(e_j, e_q)
        return state_loss, flux_metric.square(), {"e_J": e_j, "e_q": e_q, "metric": flux_metric}

    def control_volume_residuals(
        self,
        base_inputs: torch.Tensor,
        bounds: torch.Tensor,
        region_ids: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        x0, x1, y0, y1 = [bounds[:, i : i + 1] for i in range(4)]
        xc, yc = 0.5 * (x0 + x1), 0.5 * (y0 + y1)

        def at(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
            values = base_inputs.clone()
            values[:, 0:1], values[:, 1:2] = x, y
            return values.requires_grad_(True)

        left_i, right_i = at(x0, yc), at(x1, yc)
        bottom_i, top_i = at(xc, y0), at(xc, y1)
        center_i = at(xc, yc)
        left = self.field_outputs(left_i, region_override=region_ids)
        right = self.field_outputs(right_i, region_override=region_ids)
        bottom = self.field_outputs(bottom_i, region_override=region_ids)
        top = self.field_outputs(top_i, region_override=region_ids)
        center = self.field_outputs(center_i, region_override=region_ids)
        width = (x1 - x0) * self.length_m
        height = (y1 - y0) * self.width_m
        current = (
            (right["Jx_A_m"] - left["Jx_A_m"]) * height
            + (top["Jy_A_m"] - bottom["Jy_A_m"]) * width
        )
        heat_out = (
            (right["qx_W_m"] - left["qx_W_m"]) * height
            + (top["qy_W_m"] - bottom["qy_W_m"]) * width
        )
        area = width * height
        internal_joule = self.thickness_m * center["sigma_S_m"] * (
            center["dphi_dx"].square() + center["dphi_dy"].square()
        ) * area
        sink = self.sink_conductance(center_i, region_ids) * (
            center["T_K"] - self.ambient_temperature_K
        ) * area
        left_boundary = torch.isclose(x0, torch.zeros_like(x0), atol=1.0e-12)
        right_boundary = torch.isclose(x1, torch.ones_like(x1), atol=1.0e-12)
        left_contact_j = (
            left_i[:, 2:3] * self.voltage_scale_V - left["phi_V"]
        ) / (self.rc_left_ohm * self.width_m)
        right_contact_j = right["phi_V"] / (self.rc_right_ohm * self.width_m)
        contact_joule = (
            left_boundary.to(base_inputs.dtype)
            * left_contact_j.square()
            * self.rc_left_ohm
            * self.width_m
            * height
            + right_boundary.to(base_inputs.dtype)
            * right_contact_j.square()
            * self.rc_right_ohm
            * self.width_m
            * height
        )
        energy = heat_out - internal_joule - contact_joule + sink
        current_scale = self.current_scale_A_m * torch.maximum(width, height)
        energy_scale = self.heat_flux_scale_W_m * torch.maximum(width, height)
        return current / current_scale, energy / energy_scale

    def port_and_ledger(
        self,
        left_inputs: torch.Tensor,
        right_inputs: torch.Tensor,
        volume_inputs: torch.Tensor,
        target_current_A: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        left = self.field_outputs(left_inputs, region_override=0)
        right = self.field_outputs(right_inputs, region_override=2)
        left_j = (
            left_inputs[:, 2:3] * self.voltage_scale_V - left["phi_V"]
        ) / (self.rc_left_ohm * self.width_m)
        right_j = right["phi_V"] / (self.rc_right_ohm * self.width_m)
        source_current = torch.mean(left_j) * self.width_m
        ground_current = torch.mean(right_j) * self.width_m
        target = target_current_A.reshape(())
        current_denom = torch.clamp(torch.abs(target), min=1.0e-12)
        port_loss = 0.5 * (
            ((source_current - target) / current_denom).square()
            + ((ground_current - target) / current_denom).square()
        ) + ((source_current - ground_current) / current_denom).square()

        volume = self.field_outputs(volume_inputs)
        area = self.length_m * self.width_m
        internal = torch.mean(
            self.thickness_m
            * volume["sigma_S_m"]
            * (volume["dphi_dx"].square() + volume["dphi_dy"].square())
        ) * area
        sink = torch.mean(
            self.sink_conductance(volume_inputs)
            * (volume["T_K"] - self.ambient_temperature_K)
        ) * area
        contact = (
            self.rc_left_ohm * self.width_m**2 * torch.mean(left_j.square())
            + self.rc_right_ohm * self.width_m**2 * torch.mean(right_j.square())
        )
        total_heat = internal + contact
        terminal = left_inputs[0, 2] * self.voltage_scale_V * source_current
        eps = torch.as_tensor(1.0e-12, dtype=terminal.dtype, device=terminal.device)
        e_port = torch.abs(terminal - total_heat) / torch.maximum(
            torch.maximum(torch.abs(terminal), torch.abs(total_heat)), eps
        )
        e_sink = torch.abs(total_heat - sink) / torch.maximum(
            torch.maximum(torch.abs(total_heat), torch.abs(sink)), eps
        )
        ledger_loss = 0.5 * (e_port.square() + e_sink.square())
        return port_loss, ledger_loss, {
            "source_current_A": source_current,
            "ground_current_A": ground_current,
            "terminal_power_W": terminal,
            "internal_joule_W": internal,
            "contact_joule_W": contact,
            "total_electrical_heat_W": total_heat,
            "vertical_sink_W": sink,
            "e_port": e_port,
            "e_sink": e_sink,
            "energy_ledger_error": torch.maximum(e_port, e_sink),
        }
