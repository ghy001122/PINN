"""Conservative branch-conditioned steady 2.5D electrothermal model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import sparse

from pinnpcm.branchconserve.contract import BranchConserveContract
from pinnpcm.physics.geophase_geometry import GeoPhaseGrid, build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    S2ThermalFields,
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_2p5d_fvm import (
    FrozenSheetElectricalFactorization,
    SheetElectricalTopology,
    build_sheet_electrical_topology,
    factor_sheet_electrical,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    assemble_sheet_thermal_matrix,
    reconstruct_lateral_fluxes,
)


class SteadyModelError(RuntimeError):
    """Structured model-evaluation failure used by the unique solver."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ElectricalFaceAudit:
    x_face_current_A: np.ndarray
    y_face_current_A: np.ndarray
    source_face_current_A: np.ndarray
    ground_face_current_A: np.ndarray
    cell_joule_power_W: np.ndarray
    source_current_A: float
    ground_current_A: float
    field_joule_power_W: float
    terminal_device_power_W: float
    integrated_residual_A: np.ndarray


@dataclass(frozen=True)
class LedgerAudit:
    current_balance_error: float
    terminal_field_power_error: float
    field_thermal_error: float
    source_load_current_error: float
    source_load_power_error: float
    pass_all: bool
    raw: dict[str, float]


@dataclass(frozen=True)
class SteadyEvaluation:
    temperature_K: np.ndarray
    potential_V: np.ndarray
    conductive_state: np.ndarray
    conductivity_S_m: np.ndarray
    vertical_conductance_W_m2K: np.ndarray
    cell_joule_power_W: np.ndarray
    thermal_residual_W: np.ndarray
    scaled_thermal_residual: np.ndarray
    electrical_residual_A: np.ndarray
    source_voltage_V: float
    device_voltage_V: float
    source_current_A: float
    ground_current_A: float
    source_load_current_A: float
    field_joule_power_W: float
    vertical_sink_power_W: float
    lateral_boundary_outflow_W: float
    scaled_electrical_residual_inf: float
    scaled_thermal_residual_inf: float
    load_line_residual: float
    active_area_mean_conductive_state: float
    electrical_faces: ElectricalFaceAudit
    thermal_x_face_flux_W: np.ndarray
    thermal_y_face_flux_W: np.ndarray
    thermal_net_cell_outflow_W: np.ndarray
    ledger: LedgerAudit
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
                    self.load_line_residual,
                ]
            ).all()
        )


def symmetric_relative_error(a: float, b: float, floor: float) -> float:
    denominator = max(0.5 * (abs(a) + abs(b)), floor)
    return abs(a - b) / denominator


def _patch_mask(grid: GeoPhaseGrid, rectangles: list[dict[str, Any]]) -> np.ndarray:
    x, y = np.meshgrid(grid.x_centers_m, grid.y_centers_m)
    mask = np.zeros(grid.shape, dtype=bool)
    for rectangle in rectangles:
        x0, x1 = map(float, rectangle["x"])
        y0, y1 = map(float, rectangle["y"])
        mask |= (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    return mask


def _independent_electrical_faces(
    factor: FrozenSheetElectricalFactorization,
    potential_V: np.ndarray,
    source_voltage_V: float,
) -> ElectricalFaceAudit:
    """Rebuild every face current and Joule term outside the solver result."""

    phi = np.asarray(potential_V, dtype=float)
    x_current = factor.x_face_conductance_S * (phi[:, :-1] - phi[:, 1:])
    y_current = factor.y_face_conductance_S * (phi[:-1, :] - phi[1:, :])
    source_face = factor.source_face_conductance_S * (source_voltage_V - phi[:, 0])
    ground_face = factor.ground_face_conductance_S * (0.0 - phi[:, -1])

    cell_power = np.zeros_like(phi)
    cell_power[:, 0] += factor.source_face_conductance_S * (
        source_voltage_V - phi[:, 0]
    ) ** 2
    cell_power[:, -1] += factor.ground_face_conductance_S * phi[:, -1] ** 2
    x_power = factor.x_face_conductance_S * (phi[:, :-1] - phi[:, 1:]) ** 2
    y_power = factor.y_face_conductance_S * (phi[:-1, :] - phi[1:, :]) ** 2
    cell_power[:, :-1] += 0.5 * x_power
    cell_power[:, 1:] += 0.5 * x_power
    cell_power[:-1, :] += 0.5 * y_power
    cell_power[1:, :] += 0.5 * y_power

    rhs = np.zeros(phi.size, dtype=float)
    rhs[factor.topology.source_nodes] = (
        factor.source_face_conductance_S * source_voltage_V
    )
    residual = (
        factor.conductivity_matrix_csr @ phi.reshape(-1) - rhs
    ).reshape(phi.shape)
    source_current = float(np.sum(source_face))
    ground_current = float(np.sum(ground_face))
    field_power = float(np.sum(cell_power))
    return ElectricalFaceAudit(
        x_face_current_A=x_current,
        y_face_current_A=y_current,
        source_face_current_A=source_face,
        ground_face_current_A=ground_face,
        cell_joule_power_W=cell_power,
        source_current_A=source_current,
        ground_current_A=ground_current,
        field_joule_power_W=field_power,
        terminal_device_power_W=float(source_voltage_V * source_current),
        integrated_residual_A=residual,
    )


@dataclass
class BranchConserveModel:
    """One fixed-grid, fixed-defect steady model instance."""

    contract: BranchConserveContract
    grid: GeoPhaseGrid
    thermal_fields: S2ThermalFields
    closure: EffectiveVO2Closure
    electrical_topology: SheetElectricalTopology
    thermal_matrix: sparse.csr_matrix
    vertical_conductance_W_m2K: np.ndarray
    alpha_lu: float
    alpha_rd: float

    @property
    def ambient_temperature_K(self) -> float:
        return float(self.thermal_fields.ambient_temperature_K)

    @property
    def temperature_reference_K(self) -> float:
        return self.contract.scales.temperature_K

    @property
    def branch_shape(self) -> tuple[int, int]:
        return self.grid.shape

    @property
    def cell_capacity_J_K(self) -> np.ndarray:
        return (
            self.thermal_fields.effective_areal_capacity_J_m2K
            * self.grid.cell_area_m2
        ).reshape(-1)

    @property
    def sink_cell_W_K(self) -> np.ndarray:
        return (
            self.vertical_conductance_W_m2K * self.grid.cell_area_m2
        ).reshape(-1)

    def temperature_from_scaled(self, scaled_temperature: np.ndarray) -> np.ndarray:
        z = np.asarray(scaled_temperature, dtype=float)
        if z.size != self.grid.nx * self.grid.ny:
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "temperature unknown has wrong size"
            )
        temperature = self.ambient_temperature_K + self.temperature_reference_K * z
        return temperature.reshape(self.grid.shape)

    def scaled_from_temperature(self, temperature_K: np.ndarray) -> np.ndarray:
        temperature = np.asarray(temperature_K, dtype=float)
        if temperature.shape != self.grid.shape:
            raise ValueError("temperature shape does not match model grid")
        return (
            (temperature - self.ambient_temperature_K)
            / self.temperature_reference_K
        ).reshape(-1)

    def _validate_temperature(self, temperature_K: np.ndarray) -> None:
        if not np.isfinite(temperature_K).all():
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "temperature is nonfinite"
            )
        if np.any(temperature_K < self.closure.temperature_min_K) or np.any(
            temperature_K > self.closure.temperature_max_K
        ):
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE",
                "temperature left the frozen constitutive validity range",
            )

    def evaluate_scaled_temperature(
        self,
        scaled_temperature: np.ndarray,
        device_voltage_V: float,
        branch_memory: float,
        *,
        source_voltage_V: float | None = None,
    ) -> SteadyEvaluation:
        temperature = self.temperature_from_scaled(scaled_temperature)
        return self.evaluate_temperature(
            temperature,
            device_voltage_V,
            branch_memory,
            source_voltage_V=source_voltage_V,
        )

    def evaluate_temperature(
        self,
        temperature_K: np.ndarray,
        device_voltage_V: float,
        branch_memory: float,
        *,
        source_voltage_V: float | None = None,
    ) -> SteadyEvaluation:
        temperature = np.asarray(temperature_K, dtype=float)
        self._validate_temperature(temperature)
        if temperature.shape != self.grid.shape:
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "temperature shape is invalid"
            )
        if branch_memory not in (-1.0, 1.0):
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "branch metadata must be +1 or -1"
            )
        # The fixed-source load-line bracket enforces 0 <= Vd <= Vs.  The
        # dynamic local-stability derivative at the zero-voltage endpoint must
        # nevertheless admit an infinitesimal signed Vd perturbation.
        if not np.isfinite(device_voltage_V):
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "device voltage is invalid"
            )
        branch = np.full(self.grid.shape, branch_memory, dtype=float)
        try:
            conductive_state = self.closure.equilibrium_state(temperature, branch)
            conductivity = self.closure.conductivity_S_m(
                temperature, conductive_state
            )
            factor = factor_sheet_electrical(
                self.grid, conductivity, topology=self.electrical_topology
            )
            electrical_solution = factor.solve(device_voltage_V)
        except SteadyModelError:
            raise
        except Exception as exc:
            raise SteadyModelError(
                "STEADY_ELECTRICAL_SUBSOLVE_FAIL", str(exc)
            ) from exc

        electrical = _independent_electrical_faces(
            factor, electrical_solution.potential_V, device_voltage_V
        )
        lateral = reconstruct_lateral_fluxes(
            self.grid,
            self.thermal_fields.sheet_thermal_conductance_W_K,
            temperature,
            matrix=self.thermal_matrix,
        )
        sink_cell = (
            self.vertical_conductance_W_m2K
            * self.grid.cell_area_m2
            * (temperature - self.ambient_temperature_K)
        )
        thermal_residual = (
            lateral.net_cell_outflow_W + sink_cell - electrical.cell_joule_power_W
        )
        n_cells = temperature.size
        scaled_thermal = thermal_residual.reshape(-1) / (
            self.contract.scales.power_W / n_cells
        )

        source_current = electrical.source_current_A
        derived_source = (
            device_voltage_V
            + self.contract.series_resistance_ohm * source_current
        )
        source_voltage = (
            derived_source if source_voltage_V is None else float(source_voltage_V)
        )
        if not np.isfinite(source_voltage):
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "source voltage is nonfinite"
            )
        source_load_current = (
            source_voltage - device_voltage_V
        ) / self.contract.series_resistance_ohm
        load_line_residual = abs(source_load_current - source_current) / (
            self.contract.scales.current_A
        )
        vertical_sink = float(np.sum(sink_cell))
        lateral_boundary = float(lateral.boundary_outflow_W)
        scales = self.contract.scales
        current_error = symmetric_relative_error(
            source_current, -electrical.ground_current_A, scales.current_floor_A
        )
        terminal_power = device_voltage_V * source_current
        terminal_field_error = symmetric_relative_error(
            terminal_power, electrical.field_joule_power_W, scales.power_floor_W
        )
        field_thermal_error = symmetric_relative_error(
            electrical.field_joule_power_W,
            vertical_sink + lateral_boundary,
            scales.power_floor_W,
        )
        source_load_current_error = symmetric_relative_error(
            source_load_current, source_current, scales.current_floor_A
        )
        source_power = source_voltage * source_load_current
        partitioned_power = (
            self.contract.series_resistance_ohm * source_load_current**2
            + device_voltage_V * source_current
        )
        source_load_power_error = symmetric_relative_error(
            source_power, partitioned_power, scales.power_floor_W
        )
        ledger_values = (
            current_error,
            terminal_field_error,
            field_thermal_error,
            source_load_current_error,
            source_load_power_error,
        )
        ledger = LedgerAudit(
            current_balance_error=current_error,
            terminal_field_power_error=terminal_field_error,
            field_thermal_error=field_thermal_error,
            source_load_current_error=source_load_current_error,
            source_load_power_error=source_load_power_error,
            pass_all=bool(
                np.isfinite(ledger_values).all()
                and max(ledger_values) <= scales.ledger_relative_max
            ),
            raw={
                "source_current_A": source_current,
                "ground_current_A": electrical.ground_current_A,
                "terminal_device_power_W": terminal_power,
                "field_joule_power_W": electrical.field_joule_power_W,
                "vertical_sink_power_W": vertical_sink,
                "lateral_boundary_outflow_W": lateral_boundary,
                "source_power_W": source_power,
                "load_resistor_power_W": self.contract.series_resistance_ohm
                * source_load_current**2,
                "partitioned_power_W": partitioned_power,
            },
        )
        electrical_residual_inf = float(
            np.max(np.abs(electrical.integrated_residual_A)) / scales.current_A
        )
        thermal_residual_inf = float(np.max(np.abs(scaled_thermal)))
        finite = bool(
            np.isfinite(temperature).all()
            and np.isfinite(electrical_solution.potential_V).all()
            and np.isfinite(conductive_state).all()
            and np.isfinite(conductivity).all()
            and np.isfinite(thermal_residual).all()
        )
        return SteadyEvaluation(
            temperature_K=temperature,
            potential_V=np.asarray(electrical_solution.potential_V, dtype=float),
            conductive_state=conductive_state,
            conductivity_S_m=conductivity,
            vertical_conductance_W_m2K=self.vertical_conductance_W_m2K.copy(),
            cell_joule_power_W=electrical.cell_joule_power_W,
            thermal_residual_W=thermal_residual,
            scaled_thermal_residual=scaled_thermal,
            electrical_residual_A=electrical.integrated_residual_A,
            source_voltage_V=source_voltage,
            device_voltage_V=float(device_voltage_V),
            source_current_A=source_current,
            ground_current_A=electrical.ground_current_A,
            source_load_current_A=source_load_current,
            field_joule_power_W=electrical.field_joule_power_W,
            vertical_sink_power_W=vertical_sink,
            lateral_boundary_outflow_W=lateral_boundary,
            scaled_electrical_residual_inf=electrical_residual_inf,
            scaled_thermal_residual_inf=thermal_residual_inf,
            load_line_residual=load_line_residual,
            active_area_mean_conductive_state=float(np.mean(conductive_state)),
            electrical_faces=electrical,
            thermal_x_face_flux_W=lateral.x_face_flux_W,
            thermal_y_face_flux_W=lateral.y_face_flux_W,
            thermal_net_cell_outflow_W=lateral.net_cell_outflow_W,
            ledger=ledger,
            finite_and_range_legal=finite,
        )

    def frozen_joule_linear_correction(
        self,
        temperature_guess_K: np.ndarray,
        device_voltage_V: float,
        branch_memory: float,
        thermal_factorization: Any,
    ) -> np.ndarray:
        evaluation = self.evaluate_temperature(
            temperature_guess_K, device_voltage_V, branch_memory
        )
        rhs = evaluation.cell_joule_power_W.reshape(-1) + (
            self.sink_cell_W_K * self.ambient_temperature_K
        )
        corrected = np.asarray(thermal_factorization.solve(rhs), dtype=float)
        if not np.isfinite(corrected).all():
            raise SteadyModelError(
                "STEADY_PRECONDITIONER_FAIL",
                "frozen-Joule thermal correction produced nonfinite values",
            )
        corrected = corrected.reshape(self.grid.shape)
        self._validate_temperature(corrected)
        return corrected

    def dynamic_rhs(
        self,
        temperature_K: np.ndarray,
        device_voltage_V: float,
        source_voltage_V: float,
        branch_memory: float,
    ) -> np.ndarray:
        evaluation = self.evaluate_temperature(
            temperature_K,
            device_voltage_V,
            branch_memory,
            source_voltage_V=source_voltage_V,
        )
        thermal_rhs = -evaluation.thermal_residual_W.reshape(-1)
        circuit_rhs = np.asarray(
            [evaluation.source_load_current_A - evaluation.source_current_A],
            dtype=float,
        )
        return np.concatenate((thermal_rhs, circuit_rhs))

    def conservative_thermal_jv_from_pair(
        self,
        direction_scaled_temperature: np.ndarray,
        step: float,
        plus: SteadyEvaluation,
        minus: SteadyEvaluation,
    ) -> np.ndarray:
        """Subtract the central pair termwise to avoid CV cancellation noise.

        Both endpoint evaluations are complete conservative residual calls.  The
        lateral and sink blocks are exactly linear, so differencing those terms
        before assembling the large equilibrium cancellation is algebraically
        identical to ``(R+ - R-) / (2h)`` and substantially more accurate.
        """

        direction = np.asarray(direction_scaled_temperature, dtype=float)
        if direction.size != self.grid.nx * self.grid.ny or step <= 0.0:
            raise ValueError("thermal Jv direction or central step is invalid")
        delta_temperature = (
            2.0 * step * self.temperature_reference_K * direction
        )
        physical = (
            self.thermal_matrix @ delta_temperature
            + self.sink_cell_W_K * delta_temperature
            - (
                plus.cell_joule_power_W.reshape(-1)
                - minus.cell_joule_power_W.reshape(-1)
            )
        )
        scale = self.contract.scales.power_W / direction.size
        return np.asarray(physical, dtype=float) / (2.0 * step * scale)


def build_branchconserve_model(
    contract: BranchConserveContract,
    *,
    spatial_level: int,
    alpha_lu: float = 0.0,
    alpha_rd: float = 0.0,
) -> BranchConserveModel:
    """Build one SI-valued, fixed-grid model without touching dynamic solvers."""

    alpha_min, alpha_max = map(float, contract.raw["patches"]["alpha_range"])
    if not alpha_min <= alpha_lu <= alpha_max or not alpha_min <= alpha_rd <= alpha_max:
        raise ValueError("defect amplitudes are outside the frozen range")
    grid = build_geophase_grid(contract.parent_config, spatial_level=spatial_level)
    fields = build_s2_thermal_fields(grid, contract.parent_config)
    closure = effective_vo2_closure_from_v2_config(contract.parent_config)
    g0 = float(fields.vertical_conductance_W_m2K)
    vertical = np.full(grid.shape, g0, dtype=float)
    patches = contract.raw["patches"]
    lu = _patch_mask(grid, patches["lu"]["rectangles_m"])
    rd = _patch_mask(grid, patches["rd"]["rectangles_m"])
    vertical *= 1.0 + float(alpha_lu) * lu.astype(float)
    vertical *= 1.0 + float(alpha_rd) * rd.astype(float)
    floor = float(patches["vertical_conductance_floor_fraction"]) * g0
    if not np.isfinite(vertical).all() or np.any(vertical < floor):
        raise ValueError("defect patch violates the vertical-conductance floor")
    return BranchConserveModel(
        contract=contract,
        grid=grid,
        thermal_fields=fields,
        closure=closure,
        electrical_topology=build_sheet_electrical_topology(grid),
        thermal_matrix=assemble_sheet_thermal_matrix(
            grid, fields.sheet_thermal_conductance_W_K
        ),
        vertical_conductance_W_m2K=vertical,
        alpha_lu=float(alpha_lu),
        alpha_rd=float(alpha_rd),
    )
