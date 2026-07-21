"""Source-constrained Qiu-2024 VO2 coplanar-device definitions.

The module deliberately keeps the Qiu device separate from the Zhang public-
data model.  The only dynamic material state is ``h``, the insulating phase
fraction/history state.  Conductivity is a deterministic constitutive closure
of temperature and history; it is never a freely predicted state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class QiuGeometry:
    device_length_m: float
    device_width_m: float
    vo2_thickness_m: float
    ti_thickness_m: float
    au_thickness_m: float
    substrate_depth_m: float
    electrode_overlap_m: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "QiuGeometry":
        return cls(**{name: float(values[name]) for name in cls.__annotations__})

    def validate(self) -> None:
        if min(
            self.device_length_m,
            self.device_width_m,
            self.vo2_thickness_m,
            self.ti_thickness_m,
            self.au_thickness_m,
            self.substrate_depth_m,
        ) <= 0.0:
            raise ValueError("Qiu geometry dimensions must be positive")
        if not 0.0 < self.electrode_overlap_m < 0.5 * self.device_length_m:
            raise ValueError("electrode overlap must lie inside half the device")


@dataclass(frozen=True)
class QiuHysteresis:
    resistance_prefactor_ohm: float
    metallic_resistance_ohm: float
    activation_temperature_K: float
    beta_per_K: float
    loop_width_K: float
    critical_temperature_K: float
    proximity_gamma: float
    dynamic_metallic_factor: float
    history_relaxation_s: float
    direction_smoothing_K_per_s: float
    explicit_contact_total_ohm: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "QiuHysteresis":
        return cls(**{name: float(values[name]) for name in cls.__annotations__})


@dataclass(frozen=True)
class QiuCircuit:
    load_resistance_ohm: float
    parallel_capacitance_F: float
    ambient_temperature_K: float
    input_voltage_V: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "QiuCircuit":
        return cls(**{name: float(values[name]) for name in cls.__annotations__})


@dataclass(frozen=True)
class QiuMesh:
    x_edges_m: np.ndarray
    z_edges_m: np.ndarray
    material: np.ndarray
    electrical_mask: np.ndarray
    thermal_mask: np.ndarray
    source_terminal_cells: tuple[tuple[int, int], ...]
    ground_terminal_cells: tuple[tuple[int, int], ...]
    depth_m: float

    @property
    def dx_m(self) -> np.ndarray:
        return np.diff(self.x_edges_m)

    @property
    def dz_m(self) -> np.ndarray:
        return np.diff(self.z_edges_m)

    @property
    def x_centers_m(self) -> np.ndarray:
        return 0.5 * (self.x_edges_m[:-1] + self.x_edges_m[1:])

    @property
    def z_centers_m(self) -> np.ndarray:
        return 0.5 * (self.z_edges_m[:-1] + self.z_edges_m[1:])

    @property
    def shape(self) -> tuple[int, int]:
        return self.material.shape


def _segmented_edges(points: list[float], counts: list[int]) -> np.ndarray:
    pieces: list[np.ndarray] = []
    for index, count in enumerate(counts):
        if count <= 0:
            raise ValueError("mesh segment counts must be positive")
        part = np.linspace(points[index], points[index + 1], count + 1)
        pieces.append(part if index == 0 else part[1:])
    return np.concatenate(pieces)


def build_qiu_domain_masks(geometry: QiuGeometry, refinement: int) -> QiuMesh:
    """Build an aligned x-z mesh for VO2/Ti/Au on thermal-only Al2O3.

    The reported 100 x 500 nm device footprint and layer thicknesses are
    retained.  The top-contact overlap and finite substrate truncation are
    explicitly configured engineering priors, not source-reported geometry.
    """
    geometry.validate()
    if refinement < 1:
        raise ValueError("refinement must be at least one")
    L = geometry.device_length_m
    overlap = geometry.electrode_overlap_m
    x_edges = _segmented_edges(
        [0.0, overlap, L - overlap, L],
        [2 * refinement, 6 * refinement, 2 * refinement],
    )
    z0 = -geometry.substrate_depth_m
    zv = geometry.vo2_thickness_m
    zt = zv + geometry.ti_thickness_m
    za = zt + geometry.au_thickness_m
    z_edges = _segmented_edges(
        [z0, 0.0, zv, zt, za],
        [8 * refinement, 4 * refinement, refinement, 2 * refinement],
    )
    x = 0.5 * (x_edges[:-1] + x_edges[1:])
    z = 0.5 * (z_edges[:-1] + z_edges[1:])
    zz, xx = np.meshgrid(z, x, indexing="ij")
    material = np.full(zz.shape, "void", dtype="U12")
    material[zz < 0.0] = "al2o3"
    material[(zz >= 0.0) & (zz < zv)] = "vo2"
    contact_x = (xx < overlap) | (xx > L - overlap)
    material[contact_x & (zz >= zv) & (zz < zt)] = "ti"
    material[contact_x & (zz >= zt) & (zz < za)] = "au"
    electrical = np.isin(material, ["vo2", "ti", "au"])
    thermal = material != "void"
    top_row = material.shape[0] - 1
    source = tuple(
        (top_row, ix)
        for ix, value in enumerate(x)
        if value < overlap and material[top_row, ix] == "au"
    )
    ground = tuple(
        (top_row, ix)
        for ix, value in enumerate(x)
        if value > L - overlap and material[top_row, ix] == "au"
    )
    if not source or not ground:
        raise RuntimeError("Qiu mesh did not create both Au terminals")
    return QiuMesh(
        x_edges_m=x_edges,
        z_edges_m=z_edges,
        material=material,
        electrical_mask=electrical,
        thermal_mask=thermal,
        source_terminal_cells=source,
        ground_terminal_cells=ground,
        depth_m=geometry.device_width_m,
    )


def major_loop_targets(
    temperature_K: np.ndarray | float, hysteresis: QiuHysteresis
) -> tuple[np.ndarray, np.ndarray]:
    """Return smooth insulating fractions on Qiu heating/cooling major loops."""
    T = np.asarray(temperature_K, dtype=float)
    heating = 0.5 + 0.5 * np.tanh(
        hysteresis.beta_per_K
        * (hysteresis.critical_temperature_K + 0.5 * hysteresis.loop_width_K - T)
    )
    cooling = 0.5 + 0.5 * np.tanh(
        hysteresis.beta_per_K
        * (hysteresis.critical_temperature_K - 0.5 * hysteresis.loop_width_K - T)
    )
    return heating, cooling


def advance_history_state(
    old_temperature_K: np.ndarray,
    new_temperature_K: np.ndarray,
    old_history: np.ndarray,
    dt_s: float,
    hysteresis: QiuHysteresis,
) -> np.ndarray:
    """Advance a differentiable rate-smoothed hysteretic history closure.

    ``h=1`` is insulating and ``h=0`` metallic.  Incomplete relaxation retains
    the prior state and creates minor-loop memory.  This is a source-informed
    E0 closure, not a claim of exact reproduction of Qiu equations S2-S4.
    """
    if dt_s <= 0.0 or hysteresis.history_relaxation_s <= 0.0:
        raise ValueError("history time scales must be positive")
    old_T = np.asarray(old_temperature_K, dtype=float)
    new_T = np.asarray(new_temperature_K, dtype=float)
    h = np.asarray(old_history, dtype=float)
    heating_target, cooling_target = major_loop_targets(new_T, hysteresis)
    rate = (new_T - old_T) / dt_s
    heating_weight = 0.5 * (
        1.0 + np.tanh(rate / hysteresis.direction_smoothing_K_per_s)
    )
    target = heating_weight * heating_target + (1.0 - heating_weight) * cooling_target
    alpha = 1.0 - np.exp(-dt_s / hysteresis.history_relaxation_s)
    return (1.0 - alpha) * h + alpha * target


def qiu_equivalent_device_resistance_ohm(
    temperature_K: np.ndarray, history: np.ndarray, hysteresis: QiuHysteresis
) -> np.ndarray:
    T = np.asarray(temperature_K, dtype=float)
    h = np.asarray(history, dtype=float)
    return (
        hysteresis.resistance_prefactor_ohm
        * np.exp(hysteresis.activation_temperature_K / T)
        * h
        + hysteresis.dynamic_metallic_factor * hysteresis.metallic_resistance_ohm
    )


def conductivity_from_temperature_history(
    temperature_K: np.ndarray,
    history: np.ndarray,
    geometry: QiuGeometry,
    hysteresis: QiuHysteresis,
) -> np.ndarray:
    """Map the source-fitted lumped R(T,h) to an E0 equivalent VO2 sigma.

    The explicitly represented contact contribution is subtracted once before
    mapping the remaining resistance to a uniform VO2 conductivity.  This is a
    declared model bridge; it is not a measured local conductivity field.
    """
    total = qiu_equivalent_device_resistance_ohm(
        temperature_K, history, hysteresis
    )
    bulk = np.maximum(total - hysteresis.explicit_contact_total_ohm, 1.0e-9)
    area = geometry.device_width_m * geometry.vo2_thickness_m
    return geometry.device_length_m / (area * bulk)


def material_property_fields(
    mesh: QiuMesh,
    temperature_K: np.ndarray,
    history: np.ndarray,
    geometry: QiuGeometry,
    hysteresis: QiuHysteresis,
    materials: Mapping[str, Mapping[str, float]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return sigma, thermal conductivity, and volumetric heat capacity."""
    shape = mesh.shape
    sigma = np.ones(shape, dtype=float)
    k = np.ones(shape, dtype=float)
    rho_cp = np.ones(shape, dtype=float)
    for name in ("al2o3", "vo2", "ti", "au"):
        mask = mesh.material == name
        values = materials[name]
        k[mask] = float(values["thermal_conductivity_W_mK"])
        rho_cp[mask] = float(values["volumetric_heat_capacity_J_m3K"])
        if name != "vo2":
            sigma[mask] = float(values.get("electrical_conductivity_S_m", 1.0))
    vo2 = mesh.material == "vo2"
    sigma[vo2] = conductivity_from_temperature_history(
        np.asarray(temperature_K)[vo2],
        np.asarray(history)[vo2],
        geometry,
        hysteresis,
    )
    sigma[~mesh.electrical_mask] = 1.0
    return sigma, k, rho_cp

