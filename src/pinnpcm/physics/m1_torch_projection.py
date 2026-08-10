"""Differentiable conservative M1 electrothermal fixed-point projection.

The operator mirrors the finite-volume semantics used by the frozen M1 teacher:
cell-centred conductivity, harmonic interior faces, half-cell electrical
conductance in series with an external Robin contact, contact-aware vertical
thermal closure, and an exact boundary-cell Joule partition.  It intentionally
implements the *undamped* thermal target map.  The frozen nonlinear solver's
0.35 relaxation is an outer iteration policy, not part of this projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import torch
from torch import nn

from pinnpcm.physics.vo2_constitutive import vo2_sigma


Tensor = torch.Tensor


def _harmonic(left: Tensor, right: Tensor) -> Tensor:
    return 2.0 * left * right / (left + right)


def _as_batch_field(value: Tensor, ny: int, nx: int) -> tuple[Tensor, bool]:
    if value.ndim == 2:
        if tuple(value.shape) != (ny, nx):
            raise ValueError(f"expected {(ny, nx)} field, received {tuple(value.shape)}")
        return value.unsqueeze(0), True
    if value.ndim != 3 or tuple(value.shape[1:]) != (ny, nx):
        raise ValueError(f"expected [batch,{ny},{nx}] field, received {tuple(value.shape)}")
    return value, False


def _as_batch_scalar(value: Tensor | float, batch: int, like: Tensor) -> Tensor:
    result = torch.as_tensor(value, dtype=like.dtype, device=like.device)
    if result.ndim == 0:
        return result.expand(batch)
    result = result.reshape(-1)
    if result.numel() == 1:
        return result.expand(batch)
    if result.numel() != batch:
        raise ValueError(f"expected {batch} scalar values, received {result.numel()}")
    return result


def _relative_error(numerator: Tensor, left: Tensor, right: Tensor) -> Tensor:
    eps = torch.as_tensor(1.0e-30, dtype=numerator.dtype, device=numerator.device)
    return torch.abs(numerator) / torch.maximum(torch.maximum(torch.abs(left), torch.abs(right)), eps)


class M1TorchProjection(nn.Module):
    """Dense float64 M1 projection with batched autograd-preserving solves."""

    def __init__(
        self,
        *,
        x_centers_m: np.ndarray,
        y_centers_m: np.ndarray,
        thickness_m: float,
        sheet_thermal_conductance_W_K: np.ndarray,
        left_contact_mask: np.ndarray,
        right_contact_mask: np.ndarray,
        ambient_temperature_K: float,
        vertical_conductance_W_m2K: float,
        electrical_contact_resistance_ohm: Mapping[str, float],
        thermal_contact_resistance_m2K_W: Mapping[str, float],
        localized_sink_rectangle_m: Mapping[str, Any],
        material_params: Mapping[str, Any],
    ) -> None:
        super().__init__()
        x = np.asarray(x_centers_m, dtype=float)
        y = np.asarray(y_centers_m, dtype=float)
        sheet = np.array(sheet_thermal_conductance_W_K, dtype=float, copy=True)
        left_mask = np.asarray(left_contact_mask, dtype=bool)
        right_mask = np.asarray(right_contact_mask, dtype=bool)
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("M1 projection requires one-dimensional grid centres")
        self.nx = int(x.size)
        self.ny = int(y.size)
        self.cell_count = self.nx * self.ny
        if sheet.shape != (self.ny, self.nx):
            raise ValueError("sheet thermal conductance does not match the grid")
        if left_mask.shape != sheet.shape or right_mask.shape != sheet.shape:
            raise ValueError("contact masks do not match the grid")
        self.dx_m = float(np.mean(np.diff(x)))
        self.dy_m = float(np.mean(np.diff(y)))
        self.length_m = float(self.dx_m * self.nx)
        self.width_m = float(self.dy_m * self.ny)
        self.thickness_m = float(thickness_m)
        self.cell_area_m2 = self.dx_m * self.dy_m
        self.ambient_temperature_K = float(ambient_temperature_K)
        self.vertical_conductance_W_m2K = float(vertical_conductance_W_m2K)
        self.rc_left_ohm = float(electrical_contact_resistance_ohm["left"])
        self.rc_right_ohm = float(electrical_contact_resistance_ohm["right"])
        self.rth_left_m2K_W = float(thermal_contact_resistance_m2K_W["left"])
        self.rth_right_m2K_W = float(thermal_contact_resistance_m2K_W["right"])
        self.material_params = dict(material_params)

        ids = np.arange(self.cell_count, dtype=np.int64).reshape(self.ny, self.nx)
        x_left = ids[:, :-1].reshape(-1)
        x_right = ids[:, 1:].reshape(-1)
        y_bottom = ids[:-1, :].reshape(-1)
        y_top = ids[1:, :].reshape(-1)
        source_nodes = ids[:, 0].copy()
        ground_nodes = ids[:, -1].copy()
        self.register_buffer("x_left_nodes", torch.as_tensor(x_left, dtype=torch.long))
        self.register_buffer("x_right_nodes", torch.as_tensor(x_right, dtype=torch.long))
        self.register_buffer("y_bottom_nodes", torch.as_tensor(y_bottom, dtype=torch.long))
        self.register_buffer("y_top_nodes", torch.as_tensor(y_top, dtype=torch.long))
        self.register_buffer("source_nodes", torch.as_tensor(source_nodes, dtype=torch.long))
        self.register_buffer("ground_nodes", torch.as_tensor(ground_nodes, dtype=torch.long))
        self.register_buffer("x_centers_m", torch.as_tensor(x, dtype=torch.float64))
        self.register_buffer("y_centers_m", torch.as_tensor(y, dtype=torch.float64))
        self.register_buffer("left_contact_mask", torch.as_tensor(left_mask.reshape(-1)))
        self.register_buffer("right_contact_mask", torch.as_tensor(right_mask.reshape(-1)))
        resistance = np.zeros(sheet.shape, dtype=float)
        resistance[left_mask] = self.rth_left_m2K_W
        resistance[right_mask] = self.rth_right_m2K_W
        self.register_buffer(
            "thermal_contact_resistance_field_m2K_W",
            torch.as_tensor(resistance.reshape(-1), dtype=torch.float64),
        )

        xx, yy = np.meshgrid(x, y)
        rectangle_x = localized_sink_rectangle_m["x"]
        rectangle_y = localized_sink_rectangle_m["y"]
        patch = (
            (xx >= float(rectangle_x[0]))
            & (xx <= float(rectangle_x[1]))
            & (yy >= float(rectangle_y[0]))
            & (yy <= float(rectangle_y[1]))
        )
        self.register_buffer("localized_sink_mask", torch.as_tensor(patch.reshape(-1)))

        sheet_t = torch.as_tensor(sheet, dtype=torch.float64)
        gx = _harmonic(sheet_t[:, :-1], sheet_t[:, 1:]) * self.dy_m / self.dx_m
        gy = _harmonic(sheet_t[:-1, :], sheet_t[1:, :]) * self.dx_m / self.dy_m
        self.register_buffer("thermal_x_face_conductance_W_K", gx.reshape(-1))
        self.register_buffer("thermal_y_face_conductance_W_K", gy.reshape(-1))
        lateral = self._edge_matrix(gx.reshape(1, -1), gy.reshape(1, -1))[0]
        self.register_buffer("thermal_lateral_matrix_W_K", lateral)
        self.to(dtype=torch.float64)

    def _edge_matrix(self, gx: Tensor, gy: Tensor) -> Tensor:
        batch = gx.shape[0]
        diagonal = torch.zeros(
            (batch, self.cell_count), dtype=gx.dtype, device=gx.device
        )
        diagonal.index_add_(1, self.x_left_nodes, gx)
        diagonal.index_add_(1, self.x_right_nodes, gx)
        diagonal.index_add_(1, self.y_bottom_nodes, gy)
        diagonal.index_add_(1, self.y_top_nodes, gy)
        matrix = torch.diag_embed(diagonal)
        matrix[:, self.x_left_nodes, self.x_right_nodes] = -gx
        matrix[:, self.x_right_nodes, self.x_left_nodes] = -gx
        matrix[:, self.y_bottom_nodes, self.y_top_nodes] = -gy
        matrix[:, self.y_top_nodes, self.y_bottom_nodes] = -gy
        return matrix

    def conductivity(self, temperature_K: Tensor, state_coordinate: Tensor | float) -> Tensor:
        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        state = _as_batch_scalar(state_coordinate, temperature.shape[0], temperature)
        state_field = state[:, None, None].expand_as(temperature)
        defect = torch.full_like(
            temperature, float(self.material_params["c_v_ref"])
        )
        sigma = vo2_sigma(
            temperature, defect, m=state_field, params=self.material_params
        )
        return sigma[0] if squeezed else sigma

    def electrical(
        self,
        temperature_K: Tensor,
        voltage_V: Tensor | float,
        state_coordinate: Tensor | float,
    ) -> dict[str, Tensor]:
        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        batch = temperature.shape[0]
        voltage = _as_batch_scalar(voltage_V, batch, temperature)
        sigma = self.conductivity(temperature, state_coordinate)
        if sigma.ndim == 2:
            sigma = sigma.unsqueeze(0)
        flat = sigma.reshape(batch, -1)
        sigma_x_left = flat[:, self.x_left_nodes]
        sigma_x_right = flat[:, self.x_right_nodes]
        sigma_y_bottom = flat[:, self.y_bottom_nodes]
        sigma_y_top = flat[:, self.y_top_nodes]
        gx = (
            _harmonic(sigma_x_left, sigma_x_right)
            * self.thickness_m
            * self.dy_m
            / self.dx_m
        )
        gy = (
            _harmonic(sigma_y_bottom, sigma_y_top)
            * self.thickness_m
            * self.dx_m
            / self.dy_m
        )
        source_base = (
            flat[:, self.source_nodes]
            * self.thickness_m
            * self.dy_m
            / (0.5 * self.dx_m)
        )
        ground_base = (
            flat[:, self.ground_nodes]
            * self.thickness_m
            * self.dy_m
            / (0.5 * self.dx_m)
        )
        source_face_resistance = self.rc_left_ohm * self.ny
        ground_face_resistance = self.rc_right_ohm * self.ny
        source_g = 1.0 / (1.0 / source_base + source_face_resistance)
        ground_g = 1.0 / (1.0 / ground_base + ground_face_resistance)

        matrix = self._edge_matrix(gx, gy)
        boundary_diagonal = torch.zeros_like(flat)
        boundary_diagonal.index_add_(1, self.source_nodes, source_g)
        boundary_diagonal.index_add_(1, self.ground_nodes, ground_g)
        matrix = matrix + torch.diag_embed(boundary_diagonal)
        rhs = torch.zeros_like(flat)
        rhs[:, self.source_nodes] = source_g * voltage[:, None]
        phi_flat = torch.linalg.solve(matrix, rhs.unsqueeze(-1)).squeeze(-1)
        phi = phi_flat.reshape(batch, self.ny, self.nx)

        source_face_current = source_g * (voltage[:, None] - phi[:, :, 0])
        ground_face_current = ground_g * phi[:, :, -1]
        x_internal_current = gx * (
            phi_flat[:, self.x_left_nodes] - phi_flat[:, self.x_right_nodes]
        )
        y_internal_current = gy * (
            phi_flat[:, self.y_bottom_nodes] - phi_flat[:, self.y_top_nodes]
        )
        x_face_current = torch.zeros(
            (batch, self.ny, self.nx + 1), dtype=temperature.dtype, device=temperature.device
        )
        y_face_current = torch.zeros(
            (batch, self.ny + 1, self.nx), dtype=temperature.dtype, device=temperature.device
        )
        x_face_current[:, :, 0] = source_face_current
        x_face_current[:, :, 1:-1] = x_internal_current.reshape(batch, self.ny, self.nx - 1)
        x_face_current[:, :, -1] = ground_face_current
        y_face_current[:, 1:-1, :] = y_internal_current.reshape(batch, self.ny - 1, self.nx)

        internal_joule = torch.zeros_like(flat)
        x_power = gx * (
            phi_flat[:, self.x_left_nodes] - phi_flat[:, self.x_right_nodes]
        ).square()
        y_power = gy * (
            phi_flat[:, self.y_bottom_nodes] - phi_flat[:, self.y_top_nodes]
        ).square()
        internal_joule.index_add_(1, self.x_left_nodes, 0.5 * x_power)
        internal_joule.index_add_(1, self.x_right_nodes, 0.5 * x_power)
        internal_joule.index_add_(1, self.y_bottom_nodes, 0.5 * y_power)
        internal_joule.index_add_(1, self.y_top_nodes, 0.5 * y_power)
        internal_joule[:, self.source_nodes] += source_face_current.square() / source_base
        internal_joule[:, self.ground_nodes] += ground_face_current.square() / ground_base
        contact_joule = torch.zeros_like(flat)
        contact_joule[:, self.source_nodes] = (
            source_face_current.square() * source_face_resistance
        )
        contact_joule[:, self.ground_nodes] = (
            ground_face_current.square() * ground_face_resistance
        )
        total_joule = internal_joule + contact_joule
        source_current = torch.sum(source_face_current, dim=1)
        ground_current = torch.sum(ground_face_current, dim=1)
        terminal_power = voltage * source_current
        internal_power = torch.sum(internal_joule, dim=1)
        contact_power = torch.sum(contact_joule, dim=1)
        total_heat = internal_power + contact_power
        terminal_ledger = _relative_error(
            terminal_power - total_heat, terminal_power, total_heat
        )
        residual = torch.bmm(matrix, phi_flat.unsqueeze(-1)).squeeze(-1) - rhs
        current_scale = torch.clamp(
            (torch.abs(source_current) + torch.abs(ground_current)) / self.cell_count,
            min=1.0e-30,
        )
        scaled_residual = torch.amax(torch.abs(residual), dim=1) / current_scale

        result = {
            "temperature_input_K": temperature,
            "conductivity_S_m": sigma,
            "potential_V": phi,
            "electrical_x_face_current_A": x_face_current,
            "electrical_y_face_current_A": y_face_current,
            "source_face_current_A": source_face_current,
            "ground_face_current_A": ground_face_current,
            "source_current_A": source_current,
            "ground_current_A": ground_current,
            "internal_joule_cell_W": internal_joule.reshape(batch, self.ny, self.nx),
            "contact_joule_cell_W": contact_joule.reshape(batch, self.ny, self.nx),
            "total_joule_cell_W": total_joule.reshape(batch, self.ny, self.nx),
            "internal_joule_W": internal_power,
            "contact_joule_W": contact_power,
            "total_electrical_heat_W": total_heat,
            "terminal_power_W": terminal_power,
            "terminal_electrical_heat_ledger_error": terminal_ledger,
            "scaled_electrical_residual": scaled_residual,
            "electrical_matrix": matrix,
            "electrical_rhs": rhs,
        }
        if squeezed:
            return {name: value[0] for name, value in result.items()}
        return result

    def vertical_conductance(
        self, sink_amplitude: Tensor | float, *, like: Tensor, batch: int
    ) -> Tensor:
        amplitude = _as_batch_scalar(sink_amplitude, batch, like)
        local = self.vertical_conductance_W_m2K * (
            1.0 + amplitude[:, None] * self.localized_sink_mask.to(like.dtype)[None, :]
        )
        resistance = self.thermal_contact_resistance_field_m2K_W.to(like.dtype)[None, :]
        return 1.0 / (1.0 / local + resistance)

    def thermal(
        self,
        total_joule_cell_W: Tensor,
        sink_amplitude: Tensor | float,
    ) -> dict[str, Tensor]:
        joule, squeezed = _as_batch_field(total_joule_cell_W, self.ny, self.nx)
        batch = joule.shape[0]
        flat_joule = joule.reshape(batch, -1)
        vertical_g = self.vertical_conductance(sink_amplitude, like=joule, batch=batch)
        vertical_cell = vertical_g * self.cell_area_m2
        matrix = self.thermal_lateral_matrix_W_K.to(joule.dtype)[None, :, :] + torch.diag_embed(
            vertical_cell
        )
        rhs = flat_joule + vertical_cell * self.ambient_temperature_K
        temperature_flat = torch.linalg.solve(matrix, rhs.unsqueeze(-1)).squeeze(-1)
        temperature = temperature_flat.reshape(batch, self.ny, self.nx)
        x_internal = self.thermal_x_face_conductance_W_K.to(joule.dtype)[None, :] * (
            temperature_flat[:, self.x_left_nodes] - temperature_flat[:, self.x_right_nodes]
        )
        y_internal = self.thermal_y_face_conductance_W_K.to(joule.dtype)[None, :] * (
            temperature_flat[:, self.y_bottom_nodes] - temperature_flat[:, self.y_top_nodes]
        )
        x_face_power = torch.zeros(
            (batch, self.ny, self.nx + 1), dtype=joule.dtype, device=joule.device
        )
        y_face_power = torch.zeros(
            (batch, self.ny + 1, self.nx), dtype=joule.dtype, device=joule.device
        )
        x_face_power[:, :, 1:-1] = x_internal.reshape(batch, self.ny, self.nx - 1)
        y_face_power[:, 1:-1, :] = y_internal.reshape(batch, self.ny - 1, self.nx)
        sink_cell = vertical_cell * (temperature_flat - self.ambient_temperature_K)
        total_heat = torch.sum(flat_joule, dim=1)
        total_sink = torch.sum(sink_cell, dim=1)
        sink_ledger = _relative_error(total_heat - total_sink, total_heat, total_sink)
        result = {
            "temperature_K": temperature,
            "thermal_x_face_power_W": x_face_power,
            "thermal_y_face_power_W": y_face_power,
            "vertical_conductance_W_m2K": vertical_g.reshape(batch, self.ny, self.nx),
            "vertical_sink_cell_W": sink_cell.reshape(batch, self.ny, self.nx),
            "vertical_sink_W": total_sink,
            "electrical_heat_sink_ledger_error": sink_ledger,
            "thermal_matrix": matrix,
            "thermal_rhs": rhs,
        }
        if squeezed:
            return {name: value[0] for name, value in result.items()}
        return result

    def thermal_residual(
        self,
        temperature_K: Tensor,
        total_joule_cell_W: Tensor,
        sink_amplitude: Tensor | float,
    ) -> Tensor:
        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        joule, _ = _as_batch_field(total_joule_cell_W, self.ny, self.nx)
        batch = temperature.shape[0]
        vertical_g = self.vertical_conductance(sink_amplitude, like=temperature, batch=batch)
        rise = temperature.reshape(batch, -1) - self.ambient_temperature_K
        residual = torch.matmul(
            self.thermal_lateral_matrix_W_K.to(temperature.dtype), rise.T
        ).T
        residual = residual + vertical_g * self.cell_area_m2 * rise - joule.reshape(batch, -1)
        residual = residual.reshape(batch, self.ny, self.nx)
        return residual[0] if squeezed else residual

    def thermal_diagnostics(
        self,
        temperature_K: Tensor,
        total_joule_cell_W: Tensor,
        sink_amplitude: Tensor | float,
    ) -> dict[str, Tensor]:
        """Evaluate conservative heat faces and sink without taking a projection."""

        temperature, squeezed = _as_batch_field(temperature_K, self.ny, self.nx)
        joule, _ = _as_batch_field(total_joule_cell_W, self.ny, self.nx)
        batch = temperature.shape[0]
        flat = temperature.reshape(batch, -1)
        vertical_g = self.vertical_conductance(sink_amplitude, like=temperature, batch=batch)
        x_internal = self.thermal_x_face_conductance_W_K.to(temperature.dtype)[None, :] * (
            flat[:, self.x_left_nodes] - flat[:, self.x_right_nodes]
        )
        y_internal = self.thermal_y_face_conductance_W_K.to(temperature.dtype)[None, :] * (
            flat[:, self.y_bottom_nodes] - flat[:, self.y_top_nodes]
        )
        x_face = torch.zeros(
            (batch, self.ny, self.nx + 1), dtype=temperature.dtype, device=temperature.device
        )
        y_face = torch.zeros(
            (batch, self.ny + 1, self.nx), dtype=temperature.dtype, device=temperature.device
        )
        x_face[:, :, 1:-1] = x_internal.reshape(batch, self.ny, self.nx - 1)
        y_face[:, 1:-1, :] = y_internal.reshape(batch, self.ny - 1, self.nx)
        sink_cell = vertical_g * self.cell_area_m2 * (
            flat - self.ambient_temperature_K
        )
        total_heat = torch.sum(joule.reshape(batch, -1), dim=1)
        total_sink = torch.sum(sink_cell, dim=1)
        result = {
            "temperature_K": temperature,
            "thermal_x_face_power_W": x_face,
            "thermal_y_face_power_W": y_face,
            "vertical_conductance_W_m2K": vertical_g.reshape(batch, self.ny, self.nx),
            "vertical_sink_cell_W": sink_cell.reshape(batch, self.ny, self.nx),
            "vertical_sink_W": total_sink,
            "electrical_heat_sink_ledger_error": _relative_error(
                total_heat - total_sink, total_heat, total_sink
            ),
        }
        if squeezed:
            return {name: value[0] for name, value in result.items()}
        return result

    def projection(
        self,
        temperature_K: Tensor,
        voltage_V: Tensor | float,
        state_coordinate: Tensor | float,
        sink_amplitude: Tensor | float,
    ) -> dict[str, Tensor]:
        electrical = self.electrical(temperature_K, voltage_V, state_coordinate)
        thermal = self.thermal(electrical["total_joule_cell_W"], sink_amplitude)
        result = {**electrical, **thermal}
        result["linear_solve_count"] = torch.as_tensor(
            2, dtype=thermal["temperature_K"].dtype, device=thermal["temperature_K"].device
        )
        return result

    def forward(
        self,
        temperature_K: Tensor,
        voltage_V: Tensor | float,
        state_coordinate: Tensor | float,
        sink_amplitude: Tensor | float,
    ) -> dict[str, Tensor]:
        return self.projection(
            temperature_K, voltage_V, state_coordinate, sink_amplitude
        )

    def cold_initial_temperature(
        self, voltage_V: Tensor | float, state_coordinate: Tensor | float, *, batch: int = 1
    ) -> Tensor:
        like = self.x_centers_m
        voltage = _as_batch_scalar(voltage_V, batch, like)
        state = _as_batch_scalar(state_coordinate, batch, like)
        ambient = torch.full(
            (batch, self.ny, self.nx),
            self.ambient_temperature_K,
            dtype=like.dtype,
            device=like.device,
        )
        sigma0 = self.conductivity(ambient, state)
        uniform_rise = (
            self.thickness_m
            * torch.mean(sigma0, dim=(1, 2))
            * (voltage / self.length_m).square()
            / self.vertical_conductance_W_m2K
        )
        initial_rise = torch.clamp(uniform_rise, min=0.0, max=37.5)
        return ambient + initial_rise[:, None, None]
