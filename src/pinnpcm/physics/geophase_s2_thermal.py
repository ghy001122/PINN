"""Phase 1-v2 source-scale-preserving S2 thermal closure.

The closure is deliberately separate from the retired fixed-bottom material-
stack and passive-ladder implementation.  It represents the Qiu source-author
thermal quantities only as uniform-mode device-level coefficients.  It does
not recover a substrate field or identify intrinsic local material properties.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pinnpcm.physics.geophase_geometry import GeoPhaseGrid
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure


@dataclass(frozen=True)
class S2ThermalFields:
    """Spatial areal coefficients for the nominal local S2 closure."""

    explicit_areal_capacity_J_m2K: np.ndarray
    effective_areal_capacity_J_m2K: np.ndarray
    sheet_thermal_conductance_W_K: np.ndarray
    memory_areal_coefficient_J_m2K: float
    vertical_conductance_W_m2K: float
    ambient_temperature_K: float
    device_area_m2: float
    nominal_contact_overlap_m: float
    nominal_explicit_capacity_J_K: float
    nominal_memory_coefficient_J_K: float
    target_uniform_capacity_J_K: float
    target_uniform_conductance_W_K: float
    vo2_areal_capacity_J_m2K: float
    electrode_areal_capacity_J_m2K: float
    vo2_sheet_conductance_W_K: float
    electrode_sheet_conductance_W_K: float

    def __post_init__(self) -> None:
        names = (
            "explicit_areal_capacity_J_m2K",
            "effective_areal_capacity_J_m2K",
            "sheet_thermal_conductance_W_K",
        )
        arrays = []
        for name in names:
            array = np.array(getattr(self, name), dtype=float, copy=True)
            array.setflags(write=False)
            object.__setattr__(self, name, array)
            arrays.append(array)
        if any(array.ndim != 2 for array in arrays):
            raise ValueError("S2 coefficient fields must be two-dimensional")
        if len({array.shape for array in arrays}) != 1:
            raise ValueError("S2 coefficient fields must share one grid shape")
        if any(not np.isfinite(array).all() for array in arrays):
            raise ValueError("S2 coefficient fields must be finite")
        if any(np.any(array <= 0.0) for array in arrays):
            raise ValueError("S2 capacity and sheet-conductance fields must be positive")
        scalars = np.asarray(
            [
                self.memory_areal_coefficient_J_m2K,
                self.vertical_conductance_W_m2K,
                self.ambient_temperature_K,
                self.device_area_m2,
                self.nominal_contact_overlap_m,
                self.nominal_explicit_capacity_J_K,
                self.nominal_memory_coefficient_J_K,
                self.target_uniform_capacity_J_K,
                self.target_uniform_conductance_W_K,
                self.vo2_areal_capacity_J_m2K,
                self.electrode_areal_capacity_J_m2K,
                self.vo2_sheet_conductance_W_K,
                self.electrode_sheet_conductance_W_K,
            ],
            dtype=float,
        )
        if not np.isfinite(scalars).all() or np.any(scalars <= 0.0):
            raise ValueError("S2 source-scale and material coefficients must be positive")

    def integrated_explicit_capacity_J_K(self, grid: GeoPhaseGrid) -> float:
        self.validate_grid(grid)
        return float(np.sum(self.explicit_areal_capacity_J_m2K) * grid.cell_area_m2)

    def integrated_effective_capacity_J_K(self, grid: GeoPhaseGrid) -> float:
        self.validate_grid(grid)
        return float(np.sum(self.effective_areal_capacity_J_m2K) * grid.cell_area_m2)

    def integrated_vertical_conductance_W_K(self, grid: GeoPhaseGrid) -> float:
        self.validate_grid(grid)
        return float(self.vertical_conductance_W_m2K * grid.device_area_m2)

    def validate_grid(self, grid: GeoPhaseGrid) -> None:
        if self.explicit_areal_capacity_J_m2K.shape != grid.shape:
            raise ValueError("S2 coefficient fields do not match the supplied grid")
        if not np.isclose(
            grid.device_area_m2,
            self.device_area_m2,
            rtol=1.0e-12,
            atol=0.0,
        ):
            raise ValueError("S2 coefficient fields belong to a different device area")
        expected_explicit = (
            self.vo2_areal_capacity_J_m2K
            + grid.contact_mask.astype(float) * self.electrode_areal_capacity_J_m2K
        )
        expected_sheet = (
            self.vo2_sheet_conductance_W_K
            + grid.contact_mask.astype(float) * self.electrode_sheet_conductance_W_K
        )
        expected_effective = expected_explicit + self.memory_areal_coefficient_J_m2K
        if not np.allclose(
            self.explicit_areal_capacity_J_m2K, expected_explicit, rtol=1.0e-12, atol=0.0
        ):
            raise ValueError("S2 explicit capacity is not confined to the locked masks")
        if not np.allclose(
            self.sheet_thermal_conductance_W_K, expected_sheet, rtol=1.0e-12, atol=0.0
        ):
            raise ValueError("S2 sheet conductance is not confined to the locked masks")
        if not np.allclose(
            self.effective_areal_capacity_J_m2K, expected_effective, rtol=1.0e-12, atol=0.0
        ):
            raise ValueError("S2 effective capacity does not equal explicit plus closure capacity")


def _positive_float(value: object, *, name: str) -> float:
    number = float(value)
    if not np.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def _nominal_geometry(config: dict) -> tuple[float, float, float]:
    geometry = config["geometry"]["primary_single_device"]
    length = _positive_float(geometry["vo2_length_m"], name="VO2 length")
    width = _positive_float(geometry["vo2_width_m"], name="VO2 width")
    overlap = _positive_float(
        geometry["contact_overlap_nominal_m"], name="nominal contact overlap"
    )
    if 2.0 * overlap >= length:
        raise ValueError("nominal contact overlap leaves no bare active channel")
    return length, width, overlap


def derive_nominal_s2_source_scale(config: dict) -> dict[str, float]:
    """Derive the locked S2 areal scale at the nominal 20 nm geometry.

    The computation is analytic and deterministic.  It is not a fit to a
    source curve.  The returned ``cm_A`` is subsequently frozen for all
    contact-overlap audits.
    """

    length, width, overlap = _nominal_geometry(config)
    geometry = config["geometry"]["primary_single_device"]
    materials = config["parameter_contract"]["areal_plane_materials"]
    moments = config["source_contract"]["thermal_moments"]

    vo2_t = _positive_float(geometry["vo2_thickness_m"], name="VO2 thickness")
    ti_t = _positive_float(geometry["ti_thickness_m"], name="Ti thickness")
    au_t = _positive_float(geometry["au_thickness_m"], name="Au thickness")
    vo2 = materials["vo2"]
    ti = materials["ti"]
    au = materials["au"]

    vo2_capacity_A = _positive_float(
        vo2["volumetric_heat_capacity_J_m3K"], name="VO2 volumetric capacity"
    ) * vo2_t
    electrode_capacity_A = (
        _positive_float(
            ti["volumetric_heat_capacity_J_m3K"], name="Ti volumetric capacity"
        )
        * ti_t
        + _positive_float(
            au["volumetric_heat_capacity_J_m3K"], name="Au volumetric capacity"
        )
        * au_t
    )
    vo2_sheet = _positive_float(
        vo2["thermal_conductivity_W_mK"], name="VO2 conductivity"
    ) * vo2_t
    electrode_sheet = (
        _positive_float(ti["thermal_conductivity_W_mK"], name="Ti conductivity")
        * ti_t
        + _positive_float(au["thermal_conductivity_W_mK"], name="Au conductivity")
        * au_t
    )

    area = length * width
    electrode_area = 2.0 * overlap * width
    explicit_capacity = vo2_capacity_A * area + electrode_capacity_A * electrode_area
    target_capacity = _positive_float(
        moments["total_device_low_frequency_admittance_coefficient_J_K"],
        name="Qiu uniform-mode capacity coefficient",
    )
    target_conductance = _positive_float(
        moments["total_device_conductance_W_K"],
        name="Qiu uniform-mode conductance",
    )
    memory_coefficient = target_capacity - explicit_capacity
    if not np.isfinite(memory_coefficient) or memory_coefficient <= 0.0:
        raise ValueError(
            "S2 requires C_m=C_theta-C_explicit to be finite and positive"
        )

    return {
        "device_area_m2": area,
        "nominal_contact_overlap_m": overlap,
        "nominal_electrode_area_m2": electrode_area,
        "vo2_areal_capacity_J_m2K": vo2_capacity_A,
        "electrode_areal_capacity_J_m2K": electrode_capacity_A,
        "vo2_sheet_conductance_W_K": vo2_sheet,
        "electrode_sheet_conductance_W_K": electrode_sheet,
        "nominal_explicit_capacity_J_K": explicit_capacity,
        "nominal_memory_coefficient_J_K": memory_coefficient,
        "memory_areal_coefficient_J_m2K": memory_coefficient / area,
        "vertical_conductance_W_m2K": target_conductance / area,
        "target_uniform_capacity_J_K": target_capacity,
        "target_uniform_conductance_W_K": target_conductance,
    }


def build_s2_thermal_fields(grid: GeoPhaseGrid, config: dict) -> S2ThermalFields:
    """Build local S2 fields while freezing the nominal areal memory scale."""

    scale = derive_nominal_s2_source_scale(config)
    nominal_length, nominal_width, _ = _nominal_geometry(config)
    if not np.isclose(
        grid.device_area_m2,
        nominal_length * nominal_width,
        rtol=1.0e-12,
        atol=0.0,
    ):
        raise ValueError("S2 grid area does not match the locked active-plane area")

    contact = grid.contact_mask.astype(float)
    explicit = (
        scale["vo2_areal_capacity_J_m2K"]
        + contact * scale["electrode_areal_capacity_J_m2K"]
    )
    effective = explicit + scale["memory_areal_coefficient_J_m2K"]
    sheet = (
        scale["vo2_sheet_conductance_W_K"]
        + contact * scale["electrode_sheet_conductance_W_K"]
    )
    ambient = float(config["parameter_contract"]["ambient_temperature_K"])
    if not np.isfinite(ambient):
        raise ValueError("ambient temperature must be finite")
    return S2ThermalFields(
        explicit_areal_capacity_J_m2K=explicit,
        effective_areal_capacity_J_m2K=effective,
        sheet_thermal_conductance_W_K=sheet,
        memory_areal_coefficient_J_m2K=scale[
            "memory_areal_coefficient_J_m2K"
        ],
        vertical_conductance_W_m2K=scale["vertical_conductance_W_m2K"],
        ambient_temperature_K=ambient,
        device_area_m2=scale["device_area_m2"],
        nominal_contact_overlap_m=scale["nominal_contact_overlap_m"],
        nominal_explicit_capacity_J_K=scale["nominal_explicit_capacity_J_K"],
        nominal_memory_coefficient_J_K=scale[
            "nominal_memory_coefficient_J_K"
        ],
        target_uniform_capacity_J_K=scale["target_uniform_capacity_J_K"],
        target_uniform_conductance_W_K=scale[
            "target_uniform_conductance_W_K"
        ],
        vo2_areal_capacity_J_m2K=scale["vo2_areal_capacity_J_m2K"],
        electrode_areal_capacity_J_m2K=scale[
            "electrode_areal_capacity_J_m2K"
        ],
        vo2_sheet_conductance_W_K=scale["vo2_sheet_conductance_W_K"],
        electrode_sheet_conductance_W_K=scale[
            "electrode_sheet_conductance_W_K"
        ],
    )


def effective_vo2_closure_from_v2_config(config: dict) -> EffectiveVO2Closure:
    """Build the shared white-box closure without mutating the locked v2 YAML."""

    geometry = config["geometry"]["primary_single_device"]
    parameter_contract = dict(config["parameter_contract"])
    conductivity = dict(parameter_contract["vo2_conductivity"])
    conductivity.update(
        {
            "effective_current_path_m": geometry["vo2_length_m"],
            "effective_width_m": geometry["vo2_width_m"],
            "active_thickness_m": geometry["vo2_thickness_m"],
        }
    )
    parameter_contract["vo2_conductivity"] = conductivity
    adapted = dict(config)
    adapted["parameter_contract"] = parameter_contract
    return EffectiveVO2Closure.from_config(adapted)


def s2_uniform_mode_identities(
    grid: GeoPhaseGrid, fields: S2ThermalFields
) -> dict[str, float | bool]:
    """Return nominal S2 coefficient identities without upgrading a claim."""

    fields.validate_grid(grid)
    nominal_overlap = np.isclose(
        grid.contact_overlap_m,
        fields.nominal_contact_overlap_m,
        rtol=1.0e-12,
        atol=0.0,
    )
    integrated_capacity = fields.integrated_effective_capacity_J_K(grid)
    integrated_conductance = fields.integrated_vertical_conductance_W_K(grid)
    capacity_scale = max(abs(fields.target_uniform_capacity_J_K), 1.0e-30)
    conductance_scale = max(abs(fields.target_uniform_conductance_W_K), 1.0e-30)
    capacity_error = abs(
        integrated_capacity - fields.target_uniform_capacity_J_K
    ) / capacity_scale
    conductance_error = abs(
        integrated_conductance - fields.target_uniform_conductance_W_K
    ) / conductance_scale
    return {
        "integrated_effective_capacity_J_K": integrated_capacity,
        "target_uniform_capacity_J_K": fields.target_uniform_capacity_J_K,
        "capacity_relative_error": capacity_error,
        "integrated_vertical_conductance_W_K": integrated_conductance,
        "target_uniform_conductance_W_K": fields.target_uniform_conductance_W_K,
        "conductance_relative_error": conductance_error,
        "memory_coefficient_positive": fields.nominal_memory_coefficient_J_K > 0.0,
        "nominal_overlap": bool(nominal_overlap),
        "capacity_identity_voting": bool(nominal_overlap),
    }
