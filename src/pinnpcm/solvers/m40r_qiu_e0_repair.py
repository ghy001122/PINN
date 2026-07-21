"""Independent M40R repairs for the Qiu-source-constrained E0 solver.

The original M40 implementation and failed formal artifacts remain immutable.
This namespace reconstructs electric-field quantities from the conservative
finite-volume face currents and later hosts the bounded active-transient
repair.  It does not introduce fitted device parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy import sparse
from scipy.signal import find_peaks
from scipy.sparse.linalg import splu

from pinnpcm.physics.qiu_vo2_device import (
    QiuCircuit,
    QiuGeometry,
    QiuHysteresis,
    QiuMesh,
    build_qiu_domain_masks,
    major_loop_targets,
    material_property_fields,
)
from pinnpcm.solvers.qiu_vo2_2d_fvm import (
    BoundaryFace,
    implicit_rc_voltage,
    qiu_terminal_faces,
    rc_residual_A,
    solve_electrical,
)


@dataclass(frozen=True)
class ConservativeElectricField:
    """Face-current and cell-field representation in SI units."""

    jx_face_A_m2: np.ndarray
    jz_face_A_m2: np.ndarray
    ex_cell_V_m: np.ndarray
    ez_cell_V_m: np.ndarray
    magnitude_cell_V_m: np.ndarray
    terminal_currents_A: dict[str, float]


@dataclass(frozen=True)
class ReferenceFieldSample:
    """Electric field sampled on one mesh-independent physical grid."""

    x_m: np.ndarray
    z_m: np.ndarray
    ex_V_m: np.ndarray
    ez_V_m: np.ndarray
    magnitude_V_m: np.ndarray


@dataclass(frozen=True)
class ThermalExcessStep:
    """One implicit excess-temperature step and its independent ledger."""

    temperature_K: np.ndarray
    storage_rate_W: float
    boundary_outflow_W: float
    source_power_W: float
    relative_energy_imbalance: float
    finite: bool


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((str(a), str(b))))


def _face_area(mesh: QiuMesh, iz: int, ix: int, side: str) -> float:
    if side in {"left", "right"}:
        return float(mesh.dz_m[iz] * mesh.depth_m)
    return float(mesh.dx_m[ix] * mesh.depth_m)


def _component_at_center(
    coordinates: list[float], values: list[float], center: float
) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    order = np.argsort(np.asarray(coordinates))
    x = np.asarray(coordinates, dtype=float)[order]
    y = np.asarray(values, dtype=float)[order]
    if abs(x[-1] - x[0]) <= 1.0e-30:
        return float(np.mean(y))
    return float(y[0] + (center - x[0]) * (y[-1] - y[0]) / (x[-1] - x[0]))


def reconstruct_conservative_electric_field(
    mesh: QiuMesh,
    potential_V: np.ndarray,
    conductivity_S_m: np.ndarray,
    terminals: Sequence[BoundaryFace],
    contact_resistance_m2_ohm: Mapping[tuple[str, str], float] | None = None,
) -> ConservativeElectricField:
    """Reconstruct ``J`` on FVM faces and local ``E=J/sigma`` in cells.

    Internal face currents use exactly the same two-point resistance as the
    M40 electrical solve, including area-specific contact resistance.  Cell
    components interpolate the two local bulk-side ``J/sigma`` values to the
    cell center.  Contact jumps are therefore not silently assigned to either
    bulk material.
    """

    phi = np.asarray(potential_V, dtype=float)
    sigma = np.asarray(conductivity_S_m, dtype=float)
    if phi.shape != mesh.shape or sigma.shape != mesh.shape:
        raise ValueError("electric fields must match the Qiu mesh")
    mask = np.asarray(mesh.electrical_mask, dtype=bool)
    if not np.isfinite(phi[mask]).all() or np.any(sigma[mask] <= 0.0):
        raise ValueError("active electric fields must be finite and positive")
    contacts = {
        _pair_key(*key): float(value)
        for key, value in (contact_resistance_m2_ohm or {}).items()
    }
    terminal_map = {(f.iz, f.ix, f.side): f for f in terminals}
    terminal_currents: dict[str, float] = {}
    nz, nx = mesh.shape
    jx = np.zeros((nz, nx + 1), dtype=float)
    jz = np.zeros((nz + 1, nx), dtype=float)

    for iz in range(nz):
        for face_ix in range(1, nx):
            left = (iz, face_ix - 1)
            right = (iz, face_ix)
            if not (mask[left] and mask[right]):
                continue
            resistance_area = (
                0.5 * mesh.dx_m[left[1]] / sigma[left]
                + contacts.get(_pair_key(mesh.material[left], mesh.material[right]), 0.0)
                + 0.5 * mesh.dx_m[right[1]] / sigma[right]
            )
            jx[iz, face_ix] = (phi[left] - phi[right]) / max(
                resistance_area, 1.0e-30
            )

    for face in terminals:
        iz, ix = int(face.iz), int(face.ix)
        if not mask[iz, ix]:
            raise ValueError("terminal must touch the electrical mask")
        if face.side in {"left", "right"}:
            resistance_area = (
                0.5 * mesh.dx_m[ix] / sigma[iz, ix] + float(face.resistance_area)
            )
            if face.side == "left":
                density = (face.value - phi[iz, ix]) / max(resistance_area, 1.0e-30)
                jx[iz, 0] = density
            else:
                density = (phi[iz, ix] - face.value) / max(resistance_area, 1.0e-30)
                jx[iz, nx] = density
        elif face.side in {"bottom", "top"}:
            resistance_area = (
                0.5 * mesh.dz_m[iz] / sigma[iz, ix] + float(face.resistance_area)
            )
            if face.side == "bottom":
                density = (face.value - phi[iz, ix]) / max(resistance_area, 1.0e-30)
                jz[0, ix] = density
            else:
                density = (phi[iz, ix] - face.value) / max(resistance_area, 1.0e-30)
                jz[nz, ix] = density
        else:
            raise ValueError(f"unsupported terminal side: {face.side}")
        area = _face_area(mesh, iz, ix, face.side)
        into_domain_current = (face.value - phi[iz, ix]) * area / max(
            resistance_area, 1.0e-30
        )
        terminal_currents[face.name] = terminal_currents.get(face.name, 0.0) + float(
            into_domain_current
        )

    for face_iz in range(1, nz):
        for ix in range(nx):
            lower = (face_iz - 1, ix)
            upper = (face_iz, ix)
            if not (mask[lower] and mask[upper]):
                continue
            resistance_area = (
                0.5 * mesh.dz_m[lower[0]] / sigma[lower]
                + contacts.get(_pair_key(mesh.material[lower], mesh.material[upper]), 0.0)
                + 0.5 * mesh.dz_m[upper[0]] / sigma[upper]
            )
            jz[face_iz, ix] = (phi[lower] - phi[upper]) / max(
                resistance_area, 1.0e-30
            )

    ex = np.full(mesh.shape, np.nan, dtype=float)
    ez = np.full(mesh.shape, np.nan, dtype=float)
    x_centers = mesh.x_centers_m
    z_centers = mesh.z_centers_m
    for iz in range(nz):
        for ix in range(nx):
            if not mask[iz, ix]:
                continue
            x_locations: list[float] = []
            x_values: list[float] = []
            if ix > 0 and mask[iz, ix - 1]:
                x_locations.append(0.5 * (x_centers[ix - 1] + x_centers[ix]))
                x_values.append(jx[iz, ix] / sigma[iz, ix])
            elif (iz, ix, "left") in terminal_map:
                x_locations.append(0.5 * (mesh.x_edges_m[ix] + x_centers[ix]))
                x_values.append(jx[iz, ix] / sigma[iz, ix])
            else:
                x_locations.append(float(mesh.x_edges_m[ix]))
                x_values.append(0.0)
            if ix + 1 < nx and mask[iz, ix + 1]:
                x_locations.append(0.5 * (x_centers[ix] + x_centers[ix + 1]))
                x_values.append(jx[iz, ix + 1] / sigma[iz, ix])
            elif (iz, ix, "right") in terminal_map:
                x_locations.append(0.5 * (x_centers[ix] + mesh.x_edges_m[ix + 1]))
                x_values.append(jx[iz, ix + 1] / sigma[iz, ix])
            else:
                x_locations.append(float(mesh.x_edges_m[ix + 1]))
                x_values.append(0.0)
            ex[iz, ix] = _component_at_center(
                x_locations, x_values, float(x_centers[ix])
            )

            z_locations: list[float] = []
            z_values: list[float] = []
            if iz > 0 and mask[iz - 1, ix]:
                z_locations.append(0.5 * (z_centers[iz - 1] + z_centers[iz]))
                z_values.append(jz[iz, ix] / sigma[iz, ix])
            elif (iz, ix, "bottom") in terminal_map:
                z_locations.append(0.5 * (mesh.z_edges_m[iz] + z_centers[iz]))
                z_values.append(jz[iz, ix] / sigma[iz, ix])
            else:
                z_locations.append(float(mesh.z_edges_m[iz]))
                z_values.append(0.0)
            if iz + 1 < nz and mask[iz + 1, ix]:
                z_locations.append(0.5 * (z_centers[iz] + z_centers[iz + 1]))
                z_values.append(jz[iz + 1, ix] / sigma[iz, ix])
            elif (iz, ix, "top") in terminal_map:
                z_locations.append(0.5 * (z_centers[iz] + mesh.z_edges_m[iz + 1]))
                z_values.append(jz[iz + 1, ix] / sigma[iz, ix])
            else:
                z_locations.append(float(mesh.z_edges_m[iz + 1]))
                z_values.append(0.0)
            ez[iz, ix] = _component_at_center(
                z_locations, z_values, float(z_centers[iz])
            )

    magnitude = np.hypot(ex, ez)
    return ConservativeElectricField(
        jx_face_A_m2=jx,
        jz_face_A_m2=jz,
        ex_cell_V_m=ex,
        ez_cell_V_m=ez,
        magnitude_cell_V_m=magnitude,
        terminal_currents_A=terminal_currents,
    )


def sample_vo2_field_on_fixed_grid(
    mesh: QiuMesh,
    field: ConservativeElectricField,
    geometry: QiuGeometry,
    *,
    x_exclusion_m: float,
    z_exclusion_m: float,
    reference_nx: int,
    reference_nz: int,
) -> ReferenceFieldSample:
    """Map VO2 bulk fields to one fixed physical grid before percentiles."""

    if reference_nx < 3 or reference_nz < 3:
        raise ValueError("reference field grid must have at least 3 points per axis")
    vo2_rows = np.flatnonzero(np.any(mesh.material == "vo2", axis=1))
    vo2_cols = np.flatnonzero(np.any(mesh.material == "vo2", axis=0))
    z_centers = mesh.z_centers_m[vo2_rows]
    x_centers = mesh.x_centers_m[vo2_cols]
    ex_values = field.ex_cell_V_m[np.ix_(vo2_rows, vo2_cols)]
    ez_values = field.ez_cell_V_m[np.ix_(vo2_rows, vo2_cols)]
    x_ref = np.linspace(
        geometry.electrode_overlap_m + x_exclusion_m,
        geometry.device_length_m - geometry.electrode_overlap_m - x_exclusion_m,
        reference_nx,
    )
    z_ref = np.linspace(
        z_exclusion_m,
        geometry.vo2_thickness_m - z_exclusion_m,
        reference_nz,
    )
    zz, xx = np.meshgrid(z_ref, x_ref, indexing="ij")
    points = np.column_stack((zz.ravel(), xx.ravel()))
    ex = RegularGridInterpolator(
        (z_centers, x_centers), ex_values, bounds_error=True
    )(points).reshape(zz.shape)
    ez = RegularGridInterpolator(
        (z_centers, x_centers), ez_values, bounds_error=True
    )(points).reshape(zz.shape)
    return ReferenceFieldSample(
        x_m=x_ref,
        z_m=z_ref,
        ex_V_m=ex,
        ez_V_m=ez,
        magnitude_V_m=np.hypot(ex, ez),
    )


def relative_field_norms(
    candidate: ReferenceFieldSample, reference: ReferenceFieldSample
) -> dict[str, float]:
    """Return component-vector L1/L2/Linf errors on a shared grid."""

    if candidate.ex_V_m.shape != reference.ex_V_m.shape:
        raise ValueError("reference samples must share one grid")
    difference = np.hypot(
        candidate.ex_V_m - reference.ex_V_m,
        candidate.ez_V_m - reference.ez_V_m,
    )
    magnitude = np.asarray(reference.magnitude_V_m)
    return {
        "relative_l1": float(np.mean(difference) / max(np.mean(magnitude), 1.0e-30)),
        "relative_l2": float(
            np.linalg.norm(difference.ravel())
            / max(np.linalg.norm(magnitude.ravel()), 1.0e-30)
        ),
        "relative_linf": float(
            np.max(difference) / max(np.max(magnitude), 1.0e-30)
        ),
    }


def advance_history_zero_drive_invariant(
    old_temperature_K: np.ndarray,
    new_temperature_K: np.ndarray,
    old_history: np.ndarray,
    dt_s: float,
    hysteresis: QiuHysteresis,
) -> np.ndarray:
    """Rate-smoothed history update with exact zero-drive memory retention.

    The M40 closure relaxed toward the average of both branches when
    ``dT/dt=0``.  M40R preserves history at zero drive by multiplying the
    relaxation rate by ``tanh(rate/v_s)^2``.  This remains an engineering-prior
    closure, not a reproduction of the source-paper reversal ledger.
    """

    if dt_s <= 0.0:
        raise ValueError("history time step must be positive")
    old_t = np.asarray(old_temperature_K, dtype=float)
    new_t = np.asarray(new_temperature_K, dtype=float)
    old_h = np.asarray(old_history, dtype=float)
    heating, cooling = major_loop_targets(new_t, hysteresis)
    signed_drive = np.tanh(
        ((new_t - old_t) / dt_s) / hysteresis.direction_smoothing_K_per_s
    )
    target = 0.5 * (1.0 + signed_drive) * heating + 0.5 * (
        1.0 - signed_drive
    ) * cooling
    activation = signed_drive * signed_drive
    alpha = 1.0 - np.exp(
        -activation * dt_s / hysteresis.history_relaxation_s
    )
    updated = old_h + alpha * (target - old_h)
    return np.clip(updated, 0.0, 1.0)


class ExcessTemperatureIntegrator:
    """Cached conservative implicit solver for ``u=T-T_ambient``.

    Solving the excess temperature avoids subtracting two large absolute-
    temperature storage terms when the startup Joule input is small.
    """

    def __init__(
        self,
        mesh: QiuMesh,
        thermal_conductivity_W_mK: np.ndarray,
        volumetric_heat_capacity_J_m3K: np.ndarray,
        ambient_temperature_K: float,
        bottom_conductance_W_K: float,
        interface_resistance_m2K_W: Mapping[tuple[str, str], float] | None = None,
    ) -> None:
        self.mesh = mesh
        self.ambient_temperature_K = float(ambient_temperature_K)
        self.bottom_conductance_W_K = float(bottom_conductance_W_K)
        self.mask = np.asarray(mesh.thermal_mask, dtype=bool)
        self.cells = np.argwhere(self.mask)
        self.node = np.full(mesh.shape, -1, dtype=int)
        for index, (iz, ix) in enumerate(self.cells):
            self.node[iz, ix] = index
        k = np.asarray(thermal_conductivity_W_mK, dtype=float)
        rho_cp = np.asarray(volumetric_heat_capacity_J_m3K, dtype=float)
        if k.shape != mesh.shape or rho_cp.shape != mesh.shape:
            raise ValueError("thermal property fields must match the mesh")
        contacts = {
            _pair_key(*key): float(value)
            for key, value in (interface_resistance_m2K_W or {}).items()
        }
        conductance = sparse.lil_matrix(
            (len(self.cells), len(self.cells)), dtype=float
        )
        self.capacity_J_K = np.zeros(len(self.cells), dtype=float)
        self.bottom_cell_conductance_W_K = np.zeros(len(self.cells), dtype=float)
        bottom_rows = [
            (index, int(iz), int(ix))
            for index, (iz, ix) in enumerate(self.cells)
            if int(iz) == 0
        ]
        bottom_area = math.fsum(
            mesh.dx_m[ix] * mesh.depth_m for _, _, ix in bottom_rows
        )
        nz, nx = mesh.shape
        for index, (iz_raw, ix_raw) in enumerate(self.cells):
            iz, ix = int(iz_raw), int(ix_raw)
            volume = mesh.dx_m[ix] * mesh.dz_m[iz] * mesh.depth_m
            self.capacity_J_K[index] = rho_cp[iz, ix] * volume
            for side, (diz, dix) in {
                "left": (0, -1),
                "right": (0, 1),
                "bottom": (-1, 0),
                "top": (1, 0),
            }.items():
                jz, jx = iz + diz, ix + dix
                if not (0 <= jz < nz and 0 <= jx < nx and self.mask[jz, jx]):
                    continue
                if side in {"left", "right"}:
                    area = mesh.dz_m[iz] * mesh.depth_m
                    half_i = 0.5 * mesh.dx_m[ix]
                    half_j = 0.5 * mesh.dx_m[jx]
                else:
                    area = mesh.dx_m[ix] * mesh.depth_m
                    half_i = 0.5 * mesh.dz_m[iz]
                    half_j = 0.5 * mesh.dz_m[jz]
                resistance = (
                    half_i / k[iz, ix]
                    + contacts.get(
                        _pair_key(mesh.material[iz, ix], mesh.material[jz, jx]),
                        0.0,
                    )
                    + half_j / k[jz, jx]
                )
                g = area / max(resistance, 1.0e-30)
                conductance[index, index] += g
                conductance[index, int(self.node[jz, jx])] -= g
            if iz == 0 and bottom_area > 0.0:
                area = mesh.dx_m[ix] * mesh.depth_m
                g_bottom = self.bottom_conductance_W_K * area / bottom_area
                conductance[index, index] += g_bottom
                self.bottom_cell_conductance_W_K[index] = g_bottom
        self.conductance = conductance.tocsc()
        self._factorizations: dict[float, object] = {}

    def step(
        self,
        old_temperature_K: np.ndarray,
        cell_heat_power_W: np.ndarray,
        dt_s: float,
    ) -> ThermalExcessStep:
        if dt_s <= 0.0:
            raise ValueError("thermal step must be positive")
        old = np.asarray(old_temperature_K, dtype=float)
        heat = np.asarray(cell_heat_power_W, dtype=float)
        if old.shape != self.mesh.shape or heat.shape != self.mesh.shape:
            raise ValueError("thermal state and source must match the mesh")
        old_u = np.asarray(
            [old[int(iz), int(ix)] - self.ambient_temperature_K for iz, ix in self.cells]
        )
        heat_nodes = np.asarray(
            [heat[int(iz), int(ix)] for iz, ix in self.cells], dtype=float
        )
        key = float(dt_s)
        factor = self._factorizations.get(key)
        if factor is None:
            matrix = self.conductance + sparse.diags(self.capacity_J_K / dt_s)
            factor = splu(matrix.tocsc())
            self._factorizations[key] = factor
        rhs = self.capacity_J_K * old_u / dt_s + heat_nodes
        new_u = np.asarray(factor.solve(rhs), dtype=float)
        new = np.full(self.mesh.shape, np.nan, dtype=float)
        for value, (iz, ix) in zip(new_u, self.cells, strict=True):
            new[int(iz), int(ix)] = self.ambient_temperature_K + value
        storage = math.fsum(
            float(capacity * (new_value - old_value) / dt_s)
            for capacity, new_value, old_value in zip(
                self.capacity_J_K, new_u, old_u, strict=True
            )
        )
        outflow = math.fsum(
            float(g * value)
            for g, value in zip(
                self.bottom_cell_conductance_W_K, new_u, strict=True
            )
        )
        source = math.fsum(float(value) for value in heat_nodes)
        residual = storage + outflow - source
        imbalance = abs(residual) / max(
            abs(storage) + abs(outflow) + abs(source), 1.0e-30
        )
        return ThermalExcessStep(
            temperature_K=new,
            storage_rate_W=float(storage),
            boundary_outflow_W=float(outflow),
            source_power_W=float(source),
            relative_energy_imbalance=float(imbalance),
            finite=bool(np.isfinite(new_u).all()),
        )


def _advance_history_substepped(
    old_temperature_K: np.ndarray,
    new_temperature_K: np.ndarray,
    old_history: np.ndarray,
    dt_s: float,
    substep_max_s: float,
    hysteresis: QiuHysteresis,
) -> np.ndarray:
    count = max(1, int(math.ceil(dt_s / substep_max_s)))
    history = np.asarray(old_history, dtype=float).copy()
    prior_temperature = np.asarray(old_temperature_K, dtype=float)
    for index in range(count):
        fraction = float(index + 1) / count
        next_temperature = old_temperature_K + fraction * (
            new_temperature_K - old_temperature_K
        )
        history = advance_history_zero_drive_invariant(
            prior_temperature,
            next_temperature,
            history,
            dt_s / count,
            hysteresis,
        )
        prior_temperature = next_temperature
    return history


def _coupled_trial_step(
    *,
    mesh: QiuMesh,
    geometry: QiuGeometry,
    hysteresis: QiuHysteresis,
    circuit: QiuCircuit,
    materials: Mapping[str, Mapping[str, float]],
    electrical_contacts: Mapping[tuple[str, str], float],
    thermal_integrator: ExcessTemperatureIntegrator,
    old_temperature_K: np.ndarray,
    old_history: np.ndarray,
    old_voltage_V: float,
    dt_s: float,
    history_substep_max_s: float,
    picard_max_iterations: int,
    voltage_relative_tolerance: float,
    temperature_absolute_tolerance_K: float,
    history_absolute_tolerance: float,
) -> dict[str, object]:
    guess_temperature = np.asarray(old_temperature_K, dtype=float).copy()
    guess_history = np.asarray(old_history, dtype=float).copy()
    guess_voltage = float(old_voltage_V)
    vo2 = mesh.material == "vo2"
    converged = False
    electrical: dict[str, object] | None = None
    thermal: ThermalExcessStep | None = None
    voltage = guess_voltage
    history = guess_history
    for iteration in range(1, picard_max_iterations + 1):
        sigma, _, _ = material_property_fields(
            mesh,
            guess_temperature,
            guess_history,
            geometry,
            hysteresis,
            materials,
        )
        electrical = solve_electrical(
            mesh,
            sigma,
            qiu_terminal_faces(mesh, 1.0),
            electrical_contacts,
        )
        conductance = float(electrical["terminal_currents_A"]["source"])
        voltage = implicit_rc_voltage(
            old_voltage_V,
            circuit.input_voltage_V,
            circuit.load_resistance_ohm,
            circuit.parallel_capacitance_F,
            conductance,
            dt_s,
        )
        heat = np.asarray(electrical["cell_joule_power_W"]) * voltage**2
        thermal = thermal_integrator.step(old_temperature_K, heat, dt_s)
        temperature = np.asarray(thermal.temperature_K)
        history = np.asarray(old_history, dtype=float).copy()
        history[vo2] = _advance_history_substepped(
            old_temperature_K[vo2],
            temperature[vo2],
            old_history[vo2],
            dt_s,
            history_substep_max_s,
            hysteresis,
        )
        voltage_error = abs(voltage - guess_voltage) / max(abs(voltage), 1.0)
        temperature_error = float(
            np.nanmax(abs(temperature[mesh.thermal_mask] - guess_temperature[mesh.thermal_mask]))
        )
        history_error = float(np.max(abs(history[vo2] - guess_history[vo2])))
        guess_voltage = voltage
        guess_temperature = temperature
        guess_history = history
        if (
            iteration > 1
            and voltage_error <= voltage_relative_tolerance
            and temperature_error <= temperature_absolute_tolerance_K
            and history_error <= history_absolute_tolerance
        ):
            converged = True
            break
    assert electrical is not None and thermal is not None
    current = float(electrical["terminal_currents_A"]["source"]) * voltage
    residual = abs(
        rc_residual_A(
            old_voltage_V,
            voltage,
            circuit.input_voltage_V,
            circuit.load_resistance_ohm,
            circuit.parallel_capacitance_F,
            current,
            dt_s,
        )
    )
    return {
        "temperature_K": guess_temperature,
        "history": guess_history,
        "voltage_V": voltage,
        "current_A": current,
        "thermal": thermal,
        "electrical": electrical,
        "picard_iterations": iteration,
        "picard_converged": converged,
        "rc_residual_A": residual,
    }


def run_active_transient(
    *,
    geometry: QiuGeometry,
    hysteresis: QiuHysteresis,
    circuit: QiuCircuit,
    materials: Mapping[str, Mapping[str, float]],
    electrical_contacts: Mapping[tuple[str, str], float],
    thermal_contacts: Mapping[tuple[str, str], float],
    bottom_conductance_W_K: float,
    profile: Mapping[str, float | int],
    controls: Mapping[str, float | int],
    maximum_steps: int,
    maximum_reject_fraction: float,
) -> dict[str, object]:
    """Run one deterministic, no-fit, multirate Qiu nominal trajectory."""

    mesh = build_qiu_domain_masks(geometry, int(profile["refinement"]))
    temperature = np.full(mesh.shape, circuit.ambient_temperature_K, dtype=float)
    history, _ = major_loop_targets(temperature, hysteresis)
    history = np.asarray(history, dtype=float)
    voltage = 0.0
    _, k, rho_cp = material_property_fields(
        mesh, temperature, history, geometry, hysteresis, materials
    )
    thermal_integrator = ExcessTemperatureIntegrator(
        mesh,
        k,
        rho_cp,
        circuit.ambient_temperature_K,
        bottom_conductance_W_K,
        thermal_contacts,
    )
    duration = 3.0 * circuit.load_resistance_ohm * circuit.parallel_capacitance_F
    smooth_dt = float(profile["smooth_dt_max_s"])
    switching_dt = float(profile["switching_dt_max_s"])
    history_substep = float(profile["history_substep_max_s"])
    minimum_dt = float(controls["minimum_dt_s"])
    accepted_before_growth = int(controls["accepted_steps_before_dt_growth"])
    dt_growth_factor = float(controls["dt_growth_factor"])
    if accepted_before_growth < 1 or dt_growth_factor <= 1.0:
        raise ValueError("adaptive time-step growth controls are invalid")
    temperature_half_width = float(controls["switching_temperature_half_width_K"])
    source_domain_max = float(controls["source_R_T_domain_max_K"])
    terminate_on_source_domain = bool(
        controls["terminate_on_source_R_T_domain_exceedance"]
    )
    max_temperature_change = float(controls["maximum_trial_temperature_change_K"])
    max_history_change = float(controls["maximum_trial_history_change"])
    vo2 = mesh.material == "vo2"
    cell_volume = mesh.dx_m[None, :] * mesh.dz_m[:, None] * mesh.depth_m
    vo2_weights = cell_volume[vo2]
    times = [0.0]
    voltages = [0.0]
    currents = [0.0]
    tmean_values = [float(np.average(temperature[vo2], weights=vo2_weights))]
    tmax_values = [float(np.max(temperature[vo2]))]
    hmean_values = [float(np.average(history[vo2], weights=vo2_weights))]
    joule_rates = [0.0]
    storage_rates = [0.0]
    outward_rates = [0.0]
    energy_imbalances = [0.0]
    history_step_changes = [0.0]
    rc_residuals = [0.0]
    current_imbalances = [0.0]
    picard_iterations = [0]
    switching_state_steps = [False]
    cumulative_joule = 0.0
    cumulative_storage = 0.0
    cumulative_outward = 0.0
    rejected = 0
    accepted = 0
    t = 0.0
    termination_reason: str | None = None
    previous_dt = minimum_dt
    consecutive_unrejected_steps = 0
    while t < duration - 1.0e-24:
        if accepted >= maximum_steps:
            raise RuntimeError("active transient accepted-step budget exhausted")
        near_transition = bool(
            np.any(
                abs(temperature[vo2] - hysteresis.critical_temperature_K)
                <= temperature_half_width
            )
        )
        base_dt = switching_dt if near_transition else smooth_dt
        growth_step = consecutive_unrejected_steps >= accepted_before_growth
        growth = (
            dt_growth_factor
            if growth_step
            else 1.0
        )
        dt = min(base_dt, max(minimum_dt, growth * previous_dt), duration - t)
        step_rejected = False
        while True:
            trial = _coupled_trial_step(
                mesh=mesh,
                geometry=geometry,
                hysteresis=hysteresis,
                circuit=circuit,
                materials=materials,
                electrical_contacts=electrical_contacts,
                thermal_integrator=thermal_integrator,
                old_temperature_K=temperature,
                old_history=history,
                old_voltage_V=voltage,
                dt_s=dt,
                history_substep_max_s=history_substep,
                picard_max_iterations=int(controls["picard_max_iterations"]),
                voltage_relative_tolerance=float(
                    controls["picard_voltage_relative_tolerance"]
                ),
                temperature_absolute_tolerance_K=float(
                    controls["picard_temperature_absolute_tolerance_K"]
                ),
                history_absolute_tolerance=float(
                    controls["picard_history_absolute_tolerance"]
                ),
            )
            new_temperature = np.asarray(trial["temperature_K"])
            new_history = np.asarray(trial["history"])
            switching_state_step = bool(
                np.any(
                    (
                        abs(temperature[vo2] - hysteresis.critical_temperature_K)
                        <= temperature_half_width
                    )
                    | (
                        abs(new_temperature[vo2] - hysteresis.critical_temperature_K)
                        <= temperature_half_width
                    )
                )
            )
            delta_temperature = float(
                np.max(abs(new_temperature[vo2] - temperature[vo2]))
            )
            delta_history = float(np.max(abs(new_history[vo2] - history[vo2])))
            acceptable = bool(
                trial["picard_converged"]
                and delta_temperature <= max_temperature_change
                and delta_history <= max_history_change
            )
            if acceptable:
                break
            if dt <= minimum_dt * (1.0 + 1.0e-12):
                raise RuntimeError(
                    "active transient could not satisfy the fixed numerical controls: "
                    f"t={t:.9e}s, dt={dt:.9e}s, "
                    f"picard_converged={trial['picard_converged']}, "
                    f"delta_T={delta_temperature:.9e}K, delta_h={delta_history:.9e}"
                )
            rejected += 1
            step_rejected = True
            dt = max(minimum_dt, 0.5 * dt)
            if (
                rejected + accepted >= 20
                and rejected / (rejected + accepted) > maximum_reject_fraction
            ):
                raise RuntimeError("active transient reject-fraction budget exhausted")
        thermal = trial["thermal"]
        assert isinstance(thermal, ThermalExcessStep)
        t += dt
        accepted += 1
        previous_dt = dt
        consecutive_unrejected_steps = (
            0
            if step_rejected or growth_step
            else consecutive_unrejected_steps + 1
        )
        voltage = float(trial["voltage_V"])
        temperature = new_temperature
        history = new_history
        joule = float(thermal.source_power_W)
        storage = float(thermal.storage_rate_W)
        outward = float(thermal.boundary_outflow_W)
        cumulative_joule = math.fsum((cumulative_joule, joule * dt))
        cumulative_storage = math.fsum((cumulative_storage, storage * dt))
        cumulative_outward = math.fsum((cumulative_outward, outward * dt))
        electrical = trial["electrical"]
        assert isinstance(electrical, Mapping)
        times.append(t)
        voltages.append(voltage)
        currents.append(float(trial["current_A"]))
        tmean_values.append(float(np.average(temperature[vo2], weights=vo2_weights)))
        tmax_values.append(float(np.max(temperature[vo2])))
        hmean_values.append(float(np.average(history[vo2], weights=vo2_weights)))
        joule_rates.append(joule)
        storage_rates.append(storage)
        outward_rates.append(outward)
        energy_imbalances.append(float(thermal.relative_energy_imbalance))
        history_step_changes.append(delta_history)
        rc_residuals.append(float(trial["rc_residual_A"]))
        current_imbalances.append(float(electrical["relative_current_imbalance"]))
        picard_iterations.append(int(trial["picard_iterations"]))
        switching_state_steps.append(switching_state_step)
        if terminate_on_source_domain and float(np.max(temperature[vo2])) > source_domain_max:
            termination_reason = "source_R_T_domain_exceeded"
            break

    time_array = np.asarray(times)
    current_array = np.asarray(currents)
    tmean_array = np.asarray(tmean_values)
    tmax_array = np.asarray(tmax_values)
    hmean_array = np.asarray(hmean_values)
    history_range = float(np.max(hmean_array) - np.min(hmean_array))
    max_temperature = float(np.max(tmax_array))
    active = bool(
        max_temperature >= hysteresis.critical_temperature_K
        and history_range >= 0.1
    )
    rc_time = circuit.load_resistance_ohm * circuit.parallel_capacitance_F
    post = time_array >= float(controls["event_statistics_discard_Rload_C"]) * rc_time
    current_post = current_array[post]
    time_post = time_array[post]
    if current_post.size >= 3 and np.ptp(current_post) > 0.0:
        prominence = float(controls["current_peak_prominence_fraction"]) * float(
            np.ptp(current_post)
        )
        peaks, _ = find_peaks(current_post, prominence=prominence)
    else:
        peaks = np.asarray([], dtype=int)
    peak_times = time_post[peaks]
    intervals = np.diff(peak_times)
    period = float(np.median(intervals)) if intervals.size else None
    isi_cv = (
        float(np.std(intervals) / np.mean(intervals))
        if intervals.size >= 2 and np.mean(intervals) > 0.0
        else None
    )
    if not active:
        activity_class = "inactive"
    elif len(peaks) >= int(controls["sustained_min_peaks"]) and isi_cv is not None and isi_cv <= float(controls["sustained_isi_cv_max"]):
        activity_class = "sustained_oscillation"
    elif len(peaks) >= 2:
        activity_class = "irregular_or_transient"
    else:
        activity_class = "active_nonoscillatory_or_latched"
    switching_mask = np.asarray(switching_state_steps, dtype=bool)
    smooth_mask = ~switching_mask
    switching_exercised = bool(np.any(switching_mask[1:]))
    smooth_max = float(np.max(np.asarray(energy_imbalances)[smooth_mask]))
    switching_max = (
        float(np.max(np.asarray(energy_imbalances)[switching_mask]))
        if switching_exercised
        else None
    )
    voltage_array = np.asarray(voltages)
    joule_array = np.asarray(joule_rates)
    storage_array = np.asarray(storage_rates)
    outward_array = np.asarray(outward_rates)
    energy_array = np.asarray(energy_imbalances)
    rc_array = np.asarray(rc_residuals)
    current_imbalance_array = np.asarray(current_imbalances)
    finite = bool(
        np.isfinite(time_array).all()
        and np.isfinite(voltage_array).all()
        and np.isfinite(current_array).all()
        and np.isfinite(tmean_array).all()
        and np.isfinite(tmax_array).all()
        and np.isfinite(hmean_array).all()
        and np.isfinite(joule_array).all()
        and np.isfinite(storage_array).all()
        and np.isfinite(outward_array).all()
        and np.isfinite(energy_array).all()
        and np.isfinite(rc_array).all()
        and np.isfinite(current_imbalance_array).all()
        and np.all((0.0 <= hmean_array) & (hmean_array <= 1.0))
    )
    cumulative_residual = cumulative_storage + cumulative_outward - cumulative_joule
    cumulative_imbalance = abs(cumulative_residual) / max(
        abs(cumulative_storage) + abs(cumulative_outward) + abs(cumulative_joule),
        1.0e-30,
    )
    return {
        "mesh": mesh,
        "time_s": time_array,
        "voltage_V": voltage_array,
        "current_A": current_array,
        "Tmean_K": tmean_array,
        "Tmax_K": tmax_array,
        "hmean": hmean_array,
        "joule_power_W": joule_array,
        "storage_rate_W": storage_array,
        "outward_heat_W": outward_array,
        "energy_imbalance": energy_array,
        "history_step_change": np.asarray(history_step_changes),
        "switching_state_window": switching_mask,
        "metrics": {
            "finite": finite,
            "duration_s": float(time_array[-1]),
            "duration_Rload_C_multiple": float(time_array[-1] / rc_time),
            "target_duration_s": float(duration),
            "target_duration_reached": bool(time_array[-1] >= duration * (1.0 - 1.0e-12)),
            "termination_reason": termination_reason,
            "accepted_steps": accepted,
            "rejected_steps": rejected,
            "reject_fraction": float(rejected / max(accepted + rejected, 1)),
            "Tmax_K": max_temperature,
            "Tmean_time_average_K": float(
                np.trapz(tmean_array, time_array) / time_array[-1]
            ),
            "h_range": history_range,
            "activity_class": activity_class,
            "event_count": int(len(peaks)),
            "median_period_s": period,
            "isi_cv": isi_cv,
            "switching_window_exercised": switching_exercised,
            "nominal_smooth_max_energy_imbalance": smooth_max,
            "nominal_switching_max_energy_imbalance": switching_max,
            "cumulative_joule_energy_J": float(cumulative_joule),
            "cumulative_storage_energy_J": float(cumulative_storage),
            "cumulative_outward_heat_J": float(cumulative_outward),
            "cumulative_energy_imbalance": float(cumulative_imbalance),
            "maximum_current_imbalance": float(max(current_imbalances)),
            "maximum_rc_residual_A": float(max(rc_residuals)),
            "maximum_picard_iterations": int(max(picard_iterations)),
            "source_R_T_domain_max_K": source_domain_max,
            "source_R_T_domain_exceeded": bool(max_temperature > source_domain_max),
            "local_2d_heat_capacity_J_K": float(
                np.sum(thermal_integrator.capacity_J_K)
            ),
            "local_2d_bottom_time_constant_s": float(
                np.sum(thermal_integrator.capacity_J_K)
                / max(bottom_conductance_W_K, 1.0e-30)
            ),
        },
    }


def compare_active_transients(
    coarse: Mapping[str, object],
    fine: Mapping[str, object],
    *,
    ambient_temperature_K: float,
    comparison_grid_points: int,
) -> dict[str, float]:
    """Compare two trajectories on raw absolute time without phase alignment."""

    coarse_time = np.asarray(coarse["time_s"], dtype=float)
    fine_time = np.asarray(fine["time_s"], dtype=float)
    end = min(float(coarse_time[-1]), float(fine_time[-1]))
    common = np.linspace(0.0, end, comparison_grid_points)
    coarse_current = np.interp(common, coarse_time, np.asarray(coarse["current_A"]))
    fine_current = np.interp(common, fine_time, np.asarray(fine["current_A"]))
    current_nrmse = float(
        np.sqrt(np.mean((coarse_current - fine_current) ** 2))
        / max(np.sqrt(np.mean(fine_current**2)), 1.0e-15)
    )
    coarse_metrics = coarse["metrics"]
    fine_metrics = fine["metrics"]
    if not isinstance(coarse_metrics, Mapping) or not isinstance(fine_metrics, Mapping):
        raise TypeError("transient metrics must be mappings")
    coarse_tmax_rise = float(coarse_metrics["Tmax_K"]) - ambient_temperature_K
    fine_tmax_rise = float(fine_metrics["Tmax_K"]) - ambient_temperature_K
    coarse_tmean_rise = float(coarse_metrics["Tmean_time_average_K"]) - ambient_temperature_K
    fine_tmean_rise = float(fine_metrics["Tmean_time_average_K"]) - ambient_temperature_K
    coarse_outward = float(coarse_metrics["cumulative_outward_heat_J"])
    fine_outward = float(fine_metrics["cumulative_outward_heat_J"])
    return {
        "current_raw_time_rms_nrmse": current_nrmse,
        "Tmax_rise_relative_change": abs(coarse_tmax_rise - fine_tmax_rise)
        / max(abs(fine_tmax_rise), 1.0e-6),
        "Tmean_rise_relative_change": abs(coarse_tmean_rise - fine_tmean_rise)
        / max(abs(fine_tmean_rise), 1.0e-6),
        "cumulative_outward_heat_relative_change": abs(coarse_outward - fine_outward)
        / max(abs(fine_outward), 1.0e-24),
    }
