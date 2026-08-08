"""Conservative current-clamped 2.5D steady electrothermal model for CC-B."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Callable
from typing import Any

import numpy as np
from scipy import sparse

from pinnpcm.branchconserve.steady_model import (
    ElectricalFaceAudit,
    _independent_electrical_faces,
    symmetric_relative_error,
)
from pinnpcm.current_clamp.cc_b_contract import CCBContract
from pinnpcm.current_clamp.source_mapping import device_effective_conductivity_S_m
from pinnpcm.evaluation.q2_qiu_source_oracle import (
    OracleParameters,
    insulating_fraction,
    resistance_and_derivative,
)
from pinnpcm.physics.geophase_geometry import GeoPhaseGrid, build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import S2ThermalFields, build_s2_thermal_fields
from pinnpcm.solvers.geophase_2p5d_fvm import (
    SheetElectricalTopology,
    build_sheet_electrical_topology,
    factor_sheet_electrical,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    assemble_sheet_thermal_matrix,
    reconstruct_lateral_fluxes,
)


class CCBModelError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CCBLedger:
    current_error: float
    terminal_field_power_error: float
    field_thermal_error: float
    pass_all: bool
    raw: dict[str, float]


@dataclass(frozen=True)
class CCBEvaluation:
    temperature_K: np.ndarray
    unit_potential: np.ndarray
    potential_V: np.ndarray
    conductive_state: np.ndarray
    conductivity_S_m: np.ndarray
    vertical_conductance_W_m2K: np.ndarray
    cell_joule_power_W: np.ndarray
    thermal_residual_W: np.ndarray
    scaled_thermal_residual: np.ndarray
    electrical_residual_A: np.ndarray
    current_set_A: float
    unit_conductance_S: float
    device_voltage_V: float
    source_current_A: float
    ground_current_A: float
    field_joule_power_W: float
    vertical_sink_power_W: float
    lateral_boundary_outflow_W: float
    scaled_electrical_residual_inf: float
    scaled_thermal_residual_inf: float
    active_area_mean_conductive_state: float
    effective_total_vertical_conductance_W_K: float
    electrical_faces: ElectricalFaceAudit
    thermal_x_face_flux_W: np.ndarray
    thermal_y_face_flux_W: np.ndarray
    thermal_net_cell_outflow_W: np.ndarray
    ledger: CCBLedger
    finite_and_range_legal: bool

    @property
    def postcertified(self) -> bool:
        return bool(
            self.finite_and_range_legal
            and self.ledger.pass_all
            and np.isfinite(
                [
                    self.scaled_electrical_residual_inf,
                    self.scaled_thermal_residual_inf,
                    self.device_voltage_V,
                ]
            ).all()
        )


def branch_delta(branch: str) -> int:
    if branch == "heating":
        return 1
    if branch == "cooling":
        return -1
    raise CCBModelError("CCB_NONFINITE_OR_RANGE", f"unknown branch: {branch}")


def _patch_mask(grid: GeoPhaseGrid, rectangles: list[dict[str, Any]]) -> np.ndarray:
    x, y = np.meshgrid(grid.x_centers_m, grid.y_centers_m)
    mask = np.zeros(grid.shape, dtype=bool)
    for rectangle in rectangles:
        x0, x1 = map(float, rectangle["x"])
        y0, y1 = map(float, rectangle["y"])
        mask |= (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    return mask


@dataclass
class CurrentClamp2DModel:
    contract: CCBContract
    grid: GeoPhaseGrid
    thermal_fields: S2ThermalFields
    source_parameters: OracleParameters
    electrical_topology: SheetElectricalTopology
    thermal_matrix: sparse.csr_matrix
    sheet_thermal_conductance_W_K: np.ndarray
    areal_capacity_J_m2K: np.ndarray
    vertical_conductance_W_m2K: np.ndarray
    current_set_A: float
    branch: str
    defect: str
    spatial_level: int
    uniform_coefficients: bool = False

    @property
    def ambient_temperature_K(self) -> float:
        return float(self.source_parameters.ambient_temperature_K)

    @property
    def temperature_reference_K(self) -> float:
        return self.contract.scales.temperature_K

    @property
    def cell_capacity_J_K(self) -> np.ndarray:
        return (self.areal_capacity_J_m2K * self.grid.cell_area_m2).reshape(-1)

    @property
    def sink_cell_W_K(self) -> np.ndarray:
        return (self.vertical_conductance_W_m2K * self.grid.cell_area_m2).reshape(-1)

    @property
    def tau0_s(self) -> float:
        return float(
            self.source_parameters.thermal_capacitance_J_K
            / self.source_parameters.thermal_conductance_W_K
        )

    def temperature_from_scaled(self, values: np.ndarray) -> np.ndarray:
        z = np.asarray(values, dtype=float)
        if z.size != self.grid.nx * self.grid.ny:
            raise CCBModelError("CCB_NONFINITE_OR_RANGE", "temperature vector has wrong size")
        return (
            self.ambient_temperature_K + self.temperature_reference_K * z
        ).reshape(self.grid.shape)

    def scaled_from_temperature(self, temperature_K: np.ndarray) -> np.ndarray:
        temperature = np.asarray(temperature_K, dtype=float)
        if temperature.shape != self.grid.shape:
            raise CCBModelError("CCB_NONFINITE_OR_RANGE", "temperature field has wrong shape")
        return ((temperature - self.ambient_temperature_K) / self.temperature_reference_K).reshape(-1)

    def validate_temperature(self, temperature_K: np.ndarray) -> None:
        temperature = np.asarray(temperature_K, dtype=float)
        lower, upper = map(float, self.contract.raw["equilibrium_gates"]["temperature_K"])
        if (
            temperature.shape != self.grid.shape
            or not np.isfinite(temperature).all()
            or np.any(temperature < lower)
            or np.any(temperature > upper)
        ):
            raise CCBModelError("CCB_NONFINITE_OR_RANGE", "temperature left the frozen source domain")

    def source_fields(
        self, temperature_K: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        delta = branch_delta(self.branch)
        resistance, _ = resistance_and_derivative(
            temperature_K, delta, 1.0, self.source_parameters
        )
        resistance = np.asarray(resistance, dtype=float)
        state = 1.0 - np.asarray(
            insulating_fraction(temperature_K, delta, self.source_parameters),
            dtype=float,
        )
        geometry_factor = float(self.contract.raw["source_mapping"]["geometry_factor_m"])
        conductivity = 1.0 / (geometry_factor * resistance)
        if (
            not np.isfinite(resistance).all()
            or np.any(resistance <= 0.0)
            or not np.isfinite(conductivity).all()
            or np.any(conductivity <= 0.0)
            or np.any(state < 0.0)
            or np.any(state > 1.0)
        ):
            raise CCBModelError("CCB_SOURCE_MAPPING_INVALID", "S1 source mapping became illegal")
        return state, resistance, conductivity

    def evaluate_scaled_temperature(self, scaled_temperature: np.ndarray) -> CCBEvaluation:
        return self.evaluate_temperature(self.temperature_from_scaled(scaled_temperature))

    def evaluate_temperature(
        self,
        temperature_K: np.ndarray,
        *,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> CCBEvaluation:
        temperature = np.asarray(temperature_K, dtype=float)
        self.validate_temperature(temperature)
        state, _resistance, conductivity = self.source_fields(temperature)
        electrical_wall_started = perf_counter() if telemetry_callback is not None else 0.0
        electrical_cpu_started = process_time() if telemetry_callback is not None else 0.0
        try:
            factor = factor_sheet_electrical(
                self.grid, conductivity, topology=self.electrical_topology
            )
            unit_solution = factor.solve(1.0)
            unit_audit = _independent_electrical_faces(
                factor, unit_solution.potential_V, 1.0
            )
        except Exception as exc:
            if telemetry_callback is not None:
                telemetry_callback(
                    {
                        "success": False,
                        "solver_type": "sparse_direct",
                        "iterations": "not_applicable",
                        "wall_time_s": perf_counter() - electrical_wall_started,
                        "cpu_time_s": process_time() - electrical_cpu_started,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    }
                )
            raise CCBModelError("CCB_ELECTRICAL_SUBSOLVE_FAIL", str(exc)) from exc
        conductance = float(unit_audit.source_current_A)
        if not math_is_positive_finite(conductance):
            raise CCBModelError("CCB_ELECTRICAL_SUBSOLVE_FAIL", "unit conductance is invalid")
        device_voltage = self.current_set_A / conductance
        if (
            not math_is_positive_finite(device_voltage)
            or device_voltage
            > float(self.contract.raw["equilibrium_gates"]["voltage_operating_envelope_max_V"])
        ):
            raise CCBModelError("CCB_NONFINITE_OR_RANGE", "projected device voltage is outside the envelope")
        potential = np.asarray(unit_solution.potential_V, dtype=float) * device_voltage
        electrical = _independent_electrical_faces(factor, potential, device_voltage)
        lateral = reconstruct_lateral_fluxes(
            self.grid,
            self.sheet_thermal_conductance_W_K,
            temperature,
            matrix=self.thermal_matrix,
        )
        sink = self.vertical_conductance_W_m2K * self.grid.cell_area_m2 * (
            temperature - self.ambient_temperature_K
        )
        thermal_residual = lateral.net_cell_outflow_W + sink - electrical.cell_joule_power_W
        n = temperature.size
        scaled_thermal = thermal_residual.reshape(-1) / (self.contract.scales.power_W / n)
        scaled_electrical = float(
            np.max(np.abs(electrical.integrated_residual_A)) / self.contract.scales.current_A
        )
        current_error = max(
            symmetric_relative_error(
                electrical.source_current_A,
                -electrical.ground_current_A,
                self.contract.scales.current_floor_A,
            ),
            symmetric_relative_error(
                electrical.source_current_A,
                self.current_set_A,
                self.contract.scales.current_floor_A,
            ),
        )
        terminal_power = device_voltage * self.current_set_A
        terminal_field_error = symmetric_relative_error(
            terminal_power,
            electrical.field_joule_power_W,
            self.contract.scales.power_floor_W,
        )
        vertical_sink = float(np.sum(sink))
        lateral_boundary = float(lateral.boundary_outflow_W)
        field_thermal_error = symmetric_relative_error(
            electrical.field_joule_power_W,
            vertical_sink + lateral_boundary,
            self.contract.scales.power_floor_W,
        )
        ledger_max = float(self.contract.raw["equilibrium_gates"]["ledger_symmetric_relative_max"])
        ledger_values = (current_error, terminal_field_error, field_thermal_error)
        ledger = CCBLedger(
            current_error=current_error,
            terminal_field_power_error=terminal_field_error,
            field_thermal_error=field_thermal_error,
            pass_all=bool(np.isfinite(ledger_values).all() and max(ledger_values) <= ledger_max),
            raw={
                "current_set_A": self.current_set_A,
                "source_current_A": electrical.source_current_A,
                "ground_current_A": electrical.ground_current_A,
                "terminal_power_W": terminal_power,
                "field_joule_power_W": electrical.field_joule_power_W,
                "vertical_sink_power_W": vertical_sink,
                "lateral_boundary_outflow_W": lateral_boundary,
            },
        )
        finite = bool(
            np.isfinite(temperature).all()
            and np.isfinite(potential).all()
            and np.isfinite(state).all()
            and np.isfinite(conductivity).all()
            and np.isfinite(thermal_residual).all()
        )
        evaluation = CCBEvaluation(
            temperature_K=temperature,
            unit_potential=np.asarray(unit_solution.potential_V, dtype=float),
            potential_V=potential,
            conductive_state=state,
            conductivity_S_m=conductivity,
            vertical_conductance_W_m2K=self.vertical_conductance_W_m2K.copy(),
            cell_joule_power_W=electrical.cell_joule_power_W,
            thermal_residual_W=thermal_residual,
            scaled_thermal_residual=scaled_thermal,
            electrical_residual_A=electrical.integrated_residual_A,
            current_set_A=self.current_set_A,
            unit_conductance_S=conductance,
            device_voltage_V=device_voltage,
            source_current_A=electrical.source_current_A,
            ground_current_A=electrical.ground_current_A,
            field_joule_power_W=electrical.field_joule_power_W,
            vertical_sink_power_W=vertical_sink,
            lateral_boundary_outflow_W=lateral_boundary,
            scaled_electrical_residual_inf=scaled_electrical,
            scaled_thermal_residual_inf=float(np.max(np.abs(scaled_thermal))),
            active_area_mean_conductive_state=float(np.mean(state)),
            effective_total_vertical_conductance_W_K=float(
                np.sum(self.vertical_conductance_W_m2K) * self.grid.cell_area_m2
            ),
            electrical_faces=electrical,
            thermal_x_face_flux_W=lateral.x_face_flux_W,
            thermal_y_face_flux_W=lateral.y_face_flux_W,
            thermal_net_cell_outflow_W=lateral.net_cell_outflow_W,
            ledger=ledger,
            finite_and_range_legal=finite,
        )

        if telemetry_callback is not None:
            telemetry_callback(
                {
                    "success": True,
                    "solver_type": "sparse_direct",
                    "iterations": "not_applicable",
                    "wall_time_s": perf_counter() - electrical_wall_started,
                    "cpu_time_s": process_time() - electrical_cpu_started,
                    "unit_conductance_S": conductance,
                    "device_voltage_V": device_voltage,
                    "source_current_A": evaluation.source_current_A,
                    "ground_current_A": evaluation.ground_current_A,
                    "normalized_current_error": abs(
                        evaluation.source_current_A - self.current_set_A
                    )
                    / self.contract.scales.current_A,
                    "scaled_electrical_residual_inf": evaluation.scaled_electrical_residual_inf,
                    "temperature_min_K": float(np.min(temperature)),
                    "temperature_max_K": float(np.max(temperature)),
                }
            )
        return evaluation

    def conservative_thermal_jv_from_pair(
        self,
        direction_scaled_temperature: np.ndarray,
        step: float,
        plus: CCBEvaluation,
        minus: CCBEvaluation,
    ) -> np.ndarray:
        direction = np.asarray(direction_scaled_temperature, dtype=float)
        delta_temperature = 2.0 * step * self.temperature_reference_K * direction
        physical = (
            self.thermal_matrix @ delta_temperature
            + self.sink_cell_W_K * delta_temperature
            - (plus.cell_joule_power_W.reshape(-1) - minus.cell_joule_power_W.reshape(-1))
        )
        scale = self.contract.scales.power_W / direction.size
        return np.asarray(physical, dtype=float) / (2.0 * step * scale)

    def dynamic_rhs(
        self,
        temperature_K: np.ndarray,
        *,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> np.ndarray:
        evaluation = self.evaluate_temperature(
            temperature_K, telemetry_callback=telemetry_callback
        )
        return -evaluation.thermal_residual_W.reshape(-1) / self.cell_capacity_J_K


def math_is_positive_finite(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def build_cc_b_model(
    contract: CCBContract,
    *,
    spatial_level: int,
    current_set_A: float,
    branch: str,
    defect: str = "NOM",
    uniform_coefficients: bool = False,
) -> CurrentClamp2DModel:
    if current_set_A not in tuple(float(value) for value in contract.raw["matrix"]["official_currents_A"]):
        # Uniform operator regression also uses the seven immutable CC-A roots.
        cc_a_currents = tuple(float(value) for value in contract.cc_a_config["current_clamp"]["official_currents_A"])
        if current_set_A not in cc_a_currents:
            raise ValueError("current is not registered by CC-A or CC-B")
    if branch not in ("heating", "cooling") or defect not in ("NOM", "LU", "RD"):
        raise ValueError("branch or defect identity is not registered")
    grid = build_geophase_grid(contract.parent_config, spatial_level=spatial_level)
    fields = build_s2_thermal_fields(grid, contract.parent_config)
    source_parameters = OracleParameters.from_config(contract.cc_a_config)
    if uniform_coefficients:
        area = grid.device_area_m2
        capacity = np.full(
            grid.shape, source_parameters.thermal_capacitance_J_K / area, dtype=float
        )
        vertical = np.full(
            grid.shape, source_parameters.thermal_conductance_W_K / area, dtype=float
        )
        sheet = np.full(
            grid.shape, float(np.mean(fields.sheet_thermal_conductance_W_K)), dtype=float
        )
    else:
        capacity = np.asarray(fields.effective_areal_capacity_J_m2K, dtype=float).copy()
        sheet = np.asarray(fields.sheet_thermal_conductance_W_K, dtype=float).copy()
        vertical = np.full(grid.shape, float(fields.vertical_conductance_W_m2K), dtype=float)
        if defect != "NOM":
            rectangles = contract.raw["geometry_and_thermal"][defect]["rectangles_m"]
            mask = _patch_mask(grid, rectangles)
            vertical *= 1.0 - float(contract.raw["geometry_and_thermal"]["defect_multiplier"]) * mask.astype(float)
    if (
        not np.isfinite(vertical).all()
        or np.any(vertical <= 0.0)
        or not np.isfinite(capacity).all()
        or np.any(capacity <= 0.0)
    ):
        raise ValueError("CC-B thermal coefficients are illegal")
    return CurrentClamp2DModel(
        contract=contract,
        grid=grid,
        thermal_fields=fields,
        source_parameters=source_parameters,
        electrical_topology=build_sheet_electrical_topology(grid),
        thermal_matrix=assemble_sheet_thermal_matrix(grid, sheet),
        sheet_thermal_conductance_W_K=sheet,
        areal_capacity_J_m2K=capacity,
        vertical_conductance_W_m2K=vertical,
        current_set_A=float(current_set_A),
        branch=branch,
        defect=defect,
        spatial_level=int(spatial_level),
        uniform_coefficients=bool(uniform_coefficients),
    )


def uniform_electrical_geometry_ratio(
    contract: CCBContract, *, spatial_level: int, conductivity_S_m: float
) -> float:
    """Return G_port/sigma for a constant conductivity sentinel."""

    grid = build_geophase_grid(contract.parent_config, spatial_level=spatial_level)
    conductivity = np.full(grid.shape, float(conductivity_S_m), dtype=float)
    factor = factor_sheet_electrical(
        grid, conductivity, topology=build_sheet_electrical_topology(grid)
    )
    solution = factor.solve(1.0)
    audit = _independent_electrical_faces(factor, solution.potential_V, 1.0)
    return float(audit.source_current_A / conductivity_S_m)
