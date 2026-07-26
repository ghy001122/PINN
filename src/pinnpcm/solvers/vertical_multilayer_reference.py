"""Independent 1D multilayer references for the two Phase 1 regions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Mapping

import numpy as np
from scipy import linalg
from scipy.optimize import least_squares

from pinnpcm.physics.vertical_thermal_memory import (
    PassiveThermalLadder,
    initial_passive_ladder,
)


@dataclass(frozen=True)
class VerticalThermalReference:
    """Linear passive driving-point thermal model per unit surface area."""

    region_id: str
    capacities_J_m2K: np.ndarray
    conductance_matrix_W_m2K: np.ndarray
    input_vector_W_m2K: np.ndarray
    output_vector_W_m2K: np.ndarray
    direct_conductance_W_m2K: float

    def __post_init__(self) -> None:
        capacities = np.asarray(self.capacities_J_m2K, dtype=float)
        matrix = np.asarray(self.conductance_matrix_W_m2K, dtype=float)
        input_vector = np.asarray(self.input_vector_W_m2K, dtype=float)
        output_vector = np.asarray(self.output_vector_W_m2K, dtype=float)
        size = capacities.size
        if capacities.ndim != 1 or matrix.shape != (size, size):
            raise ValueError("vertical reference dimensions are inconsistent")
        if input_vector.shape != (size,) or output_vector.shape != (size,):
            raise ValueError("vertical reference port vectors are inconsistent")
        arrays = (capacities, matrix, input_vector, output_vector)
        if any(not np.isfinite(array).all() for array in arrays):
            raise ValueError("vertical reference coefficients must be finite")
        if np.any(capacities <= 0.0) or self.direct_conductance_W_m2K <= 0.0:
            raise ValueError("vertical reference must have positive storage and input link")
        if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1.0e-12):
            raise ValueError("vertical reference conductance matrix must be symmetric")
        if np.min(np.linalg.eigvalsh(matrix)) <= 0.0:
            raise ValueError("vertical reference conductance matrix must be positive definite")
        object.__setattr__(self, "capacities_J_m2K", capacities)
        object.__setattr__(self, "conductance_matrix_W_m2K", matrix)
        object.__setattr__(self, "input_vector_W_m2K", input_vector)
        object.__setattr__(self, "output_vector_W_m2K", output_vector)

    @property
    def order(self) -> int:
        return int(self.capacities_J_m2K.size)

    @property
    def total_capacity_J_m2K(self) -> float:
        return float(np.sum(self.capacities_J_m2K))

    def state_matrix_per_s(self) -> np.ndarray:
        return -self.conductance_matrix_W_m2K / self.capacities_J_m2K[:, None]

    def input_rate_vector_per_s(self) -> np.ndarray:
        return self.input_vector_W_m2K / self.capacities_J_m2K

    def poles_per_s(self) -> np.ndarray:
        poles = np.linalg.eigvals(self.state_matrix_per_s())
        if np.max(np.abs(np.imag(poles))) > 1.0e-7 * max(
            np.max(np.abs(np.real(poles))), 1.0
        ):
            raise ValueError("vertical reference produced complex poles")
        return np.sort(np.real(poles))

    @property
    def dc_conductance_W_m2K(self) -> float:
        correction = self.output_vector_W_m2K @ np.linalg.solve(
            self.conductance_matrix_W_m2K, self.input_vector_W_m2K
        )
        return float(self.direct_conductance_W_m2K - correction)

    def driving_admittance_W_m2K(self, angular_frequency_rad_s: np.ndarray) -> np.ndarray:
        omega = np.atleast_1d(np.asarray(angular_frequency_rad_s, dtype=float))
        if np.any(omega < 0.0) or not np.isfinite(omega).all():
            raise ValueError("angular frequencies must be finite and nonnegative")
        response = np.empty(omega.size, dtype=complex)
        capacity = np.diag(self.capacities_J_m2K)
        for index, value in enumerate(omega):
            state = np.linalg.solve(
                1j * value * capacity + self.conductance_matrix_W_m2K,
                self.input_vector_W_m2K,
            )
            response[index] = (
                self.direct_conductance_W_m2K
                - self.output_vector_W_m2K @ state
            )
        return response

    def step_heat_flux_W_m2(
        self, time_s: np.ndarray, step_temperature_K: float = 1.0
    ) -> np.ndarray:
        time = np.atleast_1d(np.asarray(time_s, dtype=float))
        if np.any(time < 0.0) or not np.isfinite(time).all():
            raise ValueError("step-response times must be finite and nonnegative")
        matrix = self.state_matrix_per_s()
        rate_input = self.input_rate_vector_per_s()
        steady = -np.linalg.solve(matrix, rate_input) * float(step_temperature_K)
        flux = np.empty(time.size, dtype=float)
        for index, value in enumerate(time):
            state = steady - linalg.expm(matrix * value) @ steady
            flux[index] = (
                self.direct_conductance_W_m2K * float(step_temperature_K)
                - self.output_vector_W_m2K @ state
            )
        return flux

    def impulse_tail_W_m2K_s(
        self, time_s: np.ndarray, impulse_temperature_K_s: float = 1.0
    ) -> np.ndarray:
        time = np.atleast_1d(np.asarray(time_s, dtype=float))
        matrix = self.state_matrix_per_s()
        rate_input = self.input_rate_vector_per_s()
        return np.asarray(
            [
                -float(
                    self.output_vector_W_m2K
                    @ (linalg.expm(matrix * value) @ rate_input)
                )
                * float(impulse_temperature_K_s)
                for value in time
            ],
            dtype=float,
        )


@dataclass(frozen=True)
class NormalizedVerticalReferences:
    references: dict[str, VerticalThermalReference]
    region_areas_m2: dict[str, float]
    conductance_scale: float
    capacity_scale: float
    integrated_dc_conductance_W_K: float
    integrated_memory_capacity_J_K: float


@dataclass(frozen=True)
class VerticalNormalizationScales:
    """One pair-wide source-author G/C normalization."""

    conductance_scale: float
    capacity_scale: float
    raw_integrated_dc_conductance_W_K: float
    raw_integrated_memory_capacity_J_K: float

    def __post_init__(self) -> None:
        values = np.asarray(
            [
                self.conductance_scale,
                self.capacity_scale,
                self.raw_integrated_dc_conductance_W_K,
                self.raw_integrated_memory_capacity_J_K,
            ],
            dtype=float,
        )
        if not np.isfinite(values).all() or np.any(values <= 0.0):
            raise ValueError("vertical normalization scales must be finite and positive")


@dataclass(frozen=True)
class RawVerticalComponents:
    """Reusable substrate and overlay branches before global normalization."""

    substrate: VerticalThermalReference
    overlay: VerticalThermalReference
    region_areas_m2: dict[str, float]
    substrate_depth_m: float
    grid_level: str
    substrate_cell_widths_m: np.ndarray
    overlay_cell_widths_m: np.ndarray

    def __post_init__(self) -> None:
        substrate_widths = np.asarray(self.substrate_cell_widths_m, dtype=float)
        overlay_widths = np.asarray(self.overlay_cell_widths_m, dtype=float)
        if (
            substrate_widths.ndim != 1
            or overlay_widths.ndim != 1
            or np.any(substrate_widths <= 0.0)
            or np.any(overlay_widths <= 0.0)
        ):
            raise ValueError("vertical cell widths must be positive one-dimensional arrays")
        if not np.isclose(
            np.sum(substrate_widths), self.substrate_depth_m, rtol=1.0e-13, atol=0.0
        ):
            raise ValueError("substrate cells do not span the requested physical depth")
        object.__setattr__(self, "substrate_cell_widths_m", substrate_widths)
        object.__setattr__(self, "overlay_cell_widths_m", overlay_widths)

    def raw_region_references(self) -> dict[str, VerticalThermalReference]:
        return {
            "bare_vo2": _rename_reference(self.substrate, "bare_vo2"),
            "electrode_covered_vo2": _combine_reference_models(
                "electrode_covered_vo2", [self.substrate, self.overlay]
            ),
        }


class VerticalReferenceModalEvaluator:
    """Efficient symmetric modal evaluation of a passive vertical reference."""

    def __init__(self, reference: VerticalThermalReference) -> None:
        self.reference = reference
        inverse_sqrt_capacity = 1.0 / np.sqrt(reference.capacities_J_m2K)
        symmetric = (
            inverse_sqrt_capacity[:, None]
            * reference.conductance_matrix_W_m2K
            * inverse_sqrt_capacity[None, :]
        )
        rates, vectors = linalg.eigh(symmetric, check_finite=True)
        if np.any(rates <= 0.0) or not np.isfinite(rates).all():
            raise ValueError("vertical modal rates must be finite and positive")
        transformed_input = inverse_sqrt_capacity * reference.input_vector_W_m2K
        transformed_output = inverse_sqrt_capacity * reference.output_vector_W_m2K
        left = vectors.T @ transformed_output
        right = vectors.T @ transformed_input
        weights = left * right
        if not np.isfinite(weights).all():
            raise ValueError("vertical modal weights must be finite")
        self.rates_per_s = rates
        self.weights = weights

    def driving_admittance_W_m2K(
        self, angular_frequency_rad_s: np.ndarray
    ) -> np.ndarray:
        omega = np.atleast_1d(np.asarray(angular_frequency_rad_s, dtype=float))
        if np.any(omega < 0.0) or not np.isfinite(omega).all():
            raise ValueError("angular frequencies must be finite and nonnegative")
        correction = np.sum(
            self.weights[:, None]
            / (self.rates_per_s[:, None] + 1j * omega[None, :]),
            axis=0,
        )
        return self.reference.direct_conductance_W_m2K - correction

    def step_heat_flux_W_m2(self, time_s: np.ndarray) -> np.ndarray:
        time = np.atleast_1d(np.asarray(time_s, dtype=float))
        if np.any(time < 0.0) or not np.isfinite(time).all():
            raise ValueError("step-response times must be finite and nonnegative")
        dynamic = np.sum(
            (self.weights / self.rates_per_s)[:, None]
            * np.exp(-self.rates_per_s[:, None] * time[None, :]),
            axis=0,
        )
        return self.reference.dc_conductance_W_m2K + dynamic

    def impulse_tail_W_m2K_s(self, time_s: np.ndarray) -> np.ndarray:
        time = np.atleast_1d(np.asarray(time_s, dtype=float))
        if np.any(time < 0.0) or not np.isfinite(time).all():
            raise ValueError("impulse-response times must be finite and nonnegative")
        return -np.sum(
            self.weights[:, None]
            * np.exp(-self.rates_per_s[:, None] * time[None, :]),
            axis=0,
        )

    @property
    def impulse_tail_integral_W_m2K(self) -> float:
        return float(-np.sum(self.weights / self.rates_per_s))


@dataclass(frozen=True)
class VerticalRawBuildRecord:
    build_id: str
    spec_sha256: str
    builder_invocation_count: int
    request_count: int


class VerticalRawBuildRegistry:
    """Fail-closed exactly-once registry for preregistered raw builds."""

    def __init__(self) -> None:
        self._objects: dict[str, object] = {}
        self._spec_hashes: dict[str, str] = {}
        self._invocations: dict[str, int] = {}
        self._requests: dict[str, int] = {}

    @staticmethod
    def spec_sha256(spec: Mapping[str, object]) -> str:
        encoded = json.dumps(
            dict(spec),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def get_or_build(
        self,
        build_id: str,
        spec: Mapping[str, object],
        builder: Callable[[], object],
    ) -> object:
        identifier = str(build_id)
        if not identifier or identifier.startswith("P1-"):
            raise ValueError("raw readiness build ID is empty or uses a formal prefix")
        spec_hash = self.spec_sha256(spec)
        if identifier in self._objects:
            if self._spec_hashes[identifier] != spec_hash:
                raise ValueError(
                    f"raw build ID {identifier!r} was requested with a different spec"
                )
            self._requests[identifier] += 1
            return self._objects[identifier]
        value = builder()
        self._objects[identifier] = value
        self._spec_hashes[identifier] = spec_hash
        self._invocations[identifier] = 1
        self._requests[identifier] = 1
        return value

    @property
    def unique_build_ids(self) -> tuple[str, ...]:
        return tuple(self._objects)

    def records(self) -> list[VerticalRawBuildRecord]:
        return [
            VerticalRawBuildRecord(
                build_id=build_id,
                spec_sha256=self._spec_hashes[build_id],
                builder_invocation_count=self._invocations[build_id],
                request_count=self._requests[build_id],
            )
            for build_id in self._objects
        ]

    def assert_exactly_once(self, declared_build_ids: list[str] | tuple[str, ...]) -> None:
        declared = tuple(str(value) for value in declared_build_ids)
        if len(set(declared)) != len(declared):
            raise ValueError("declared raw build IDs are not unique")
        if set(declared) != set(self._objects):
            missing = sorted(set(declared) - set(self._objects))
            unexpected = sorted(set(self._objects) - set(declared))
            raise ValueError(
                f"raw build manifest mismatch: missing={missing}, unexpected={unexpected}"
            )
        if any(self._invocations[build_id] != 1 for build_id in declared):
            raise ValueError("each declared raw builder must be invoked exactly once")


def _branch_matrices(
    layers: list[tuple[float, float, float, int]],
    *,
    fixed_terminal: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Build one finite-volume branch attached to the active temperature."""

    cell_k: list[float] = []
    cell_cp: list[float] = []
    cell_dz: list[float] = []
    for thickness, conductivity, volumetric_capacity, cells in layers:
        if thickness <= 0.0 or conductivity <= 0.0 or volumetric_capacity <= 0.0:
            raise ValueError("layer properties must be positive")
        if cells <= 0:
            raise ValueError("each layer requires at least one cell")
        dz = thickness / cells
        cell_k.extend([conductivity] * cells)
        cell_cp.extend([volumetric_capacity] * cells)
        cell_dz.extend([dz] * cells)
    k = np.asarray(cell_k, dtype=float)
    cp = np.asarray(cell_cp, dtype=float)
    dz = np.asarray(cell_dz, dtype=float)
    capacities = cp * dz
    size = capacities.size
    matrix = np.zeros((size, size), dtype=float)

    input_link = k[0] / (0.5 * dz[0])
    matrix[0, 0] += input_link
    input_vector = np.zeros(size, dtype=float)
    output_vector = np.zeros(size, dtype=float)
    input_vector[0] = input_link
    output_vector[0] = input_link
    for index in range(size - 1):
        link = 1.0 / (
            0.5 * dz[index] / k[index]
            + 0.5 * dz[index + 1] / k[index + 1]
        )
        matrix[index, index] += link
        matrix[index + 1, index + 1] += link
        matrix[index, index + 1] -= link
        matrix[index + 1, index] -= link
    if fixed_terminal:
        matrix[-1, -1] += k[-1] / (0.5 * dz[-1])
    return capacities, matrix, input_vector, output_vector, float(input_link)


def _combine_branches(
    region_id: str,
    branches: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]],
) -> VerticalThermalReference:
    capacities = np.concatenate([branch[0] for branch in branches])
    matrix = linalg.block_diag(*[branch[1] for branch in branches])
    input_vector = np.concatenate([branch[2] for branch in branches])
    output_vector = np.concatenate([branch[3] for branch in branches])
    direct = float(sum(branch[4] for branch in branches))
    return VerticalThermalReference(
        region_id,
        capacities,
        matrix,
        input_vector,
        output_vector,
        direct,
    )


def _rename_reference(
    reference: VerticalThermalReference, region_id: str
) -> VerticalThermalReference:
    return VerticalThermalReference(
        region_id=region_id,
        capacities_J_m2K=reference.capacities_J_m2K.copy(),
        conductance_matrix_W_m2K=reference.conductance_matrix_W_m2K.copy(),
        input_vector_W_m2K=reference.input_vector_W_m2K.copy(),
        output_vector_W_m2K=reference.output_vector_W_m2K.copy(),
        direct_conductance_W_m2K=reference.direct_conductance_W_m2K,
    )


def _combine_reference_models(
    region_id: str, references: list[VerticalThermalReference]
) -> VerticalThermalReference:
    branches = [
        (
            reference.capacities_J_m2K,
            reference.conductance_matrix_W_m2K,
            reference.input_vector_W_m2K,
            reference.output_vector_W_m2K,
            reference.direct_conductance_W_m2K,
        )
        for reference in references
    ]
    return _combine_branches(region_id, branches)


def _branch_reference_from_cells(
    region_id: str,
    *,
    cell_widths_m: np.ndarray,
    thermal_conductivities_W_mK: np.ndarray,
    volumetric_capacities_J_m3K: np.ndarray,
    fixed_terminal: bool,
) -> VerticalThermalReference:
    dz = np.asarray(cell_widths_m, dtype=float)
    k = np.asarray(thermal_conductivities_W_mK, dtype=float)
    cp = np.asarray(volumetric_capacities_J_m3K, dtype=float)
    if dz.ndim != 1 or k.shape != dz.shape or cp.shape != dz.shape:
        raise ValueError("cellwise vertical material arrays are inconsistent")
    if (
        not np.isfinite(dz).all()
        or not np.isfinite(k).all()
        or not np.isfinite(cp).all()
        or np.any(dz <= 0.0)
        or np.any(k <= 0.0)
        or np.any(cp <= 0.0)
    ):
        raise ValueError("cellwise vertical properties must be finite and positive")
    capacities = cp * dz
    size = dz.size
    matrix = np.zeros((size, size), dtype=float)
    input_link = k[0] / (0.5 * dz[0])
    matrix[0, 0] += input_link
    input_vector = np.zeros(size, dtype=float)
    output_vector = np.zeros(size, dtype=float)
    input_vector[0] = input_link
    output_vector[0] = input_link
    for index in range(size - 1):
        link = 1.0 / (
            0.5 * dz[index] / k[index]
            + 0.5 * dz[index + 1] / k[index + 1]
        )
        matrix[index, index] += link
        matrix[index + 1, index + 1] += link
        matrix[index, index + 1] -= link
        matrix[index + 1, index] -= link
    if fixed_terminal:
        matrix[-1, -1] += k[-1] / (0.5 * dz[-1])
    return VerticalThermalReference(
        region_id=region_id,
        capacities_J_m2K=capacities,
        conductance_matrix_W_m2K=matrix,
        input_vector_W_m2K=input_vector,
        output_vector_W_m2K=output_vector,
        direct_conductance_W_m2K=float(input_link),
    )


def geometric_surface_refined_cell_widths(
    depth_m: float,
    *,
    top_cell_m: float,
    growth_ratio: float,
) -> np.ndarray:
    """Return the preregistered deterministic surface-refined grid.

    The first cell is exactly ``top_cell_m``.  The cell count is the smallest
    integer whose geometric sum at ``growth_ratio`` reaches the requested
    depth, and the effective ratio is the unique binary64 bisection root that
    makes that same cell count span the depth.  No residual terminal cell is
    appended.
    """

    depth = float(depth_m)
    top = float(top_cell_m)
    ratio = float(growth_ratio)
    if not np.isfinite([depth, top, ratio]).all() or depth <= 0.0 or top <= 0.0:
        raise ValueError("geometric-grid depth and top cell must be positive")
    if ratio < 1.0:
        raise ValueError("geometric-grid growth ratio must be at least one")
    if depth < top:
        raise ValueError("geometric-grid depth cannot be smaller than its first cell")
    if depth == top:
        return np.asarray([top], dtype=float)
    if ratio == 1.0:
        cells_exact = depth / top
        cells = int(round(cells_exact))
        if not np.isclose(cells_exact, cells, rtol=0.0, atol=8.0 * np.spacing(cells_exact)):
            raise ValueError("unit-growth grid cannot span depth without a residual cell")
        return np.full(cells, top, dtype=float)

    def geometric_sum(cell_count: int, effective_ratio: float) -> float:
        return float(
            top
            * np.sum(effective_ratio ** np.arange(cell_count, dtype=np.float64))
        )

    cells = 1
    while geometric_sum(cells, ratio) < depth:
        cells += 1
    if cells == 1:
        return np.asarray([top], dtype=float)
    if geometric_sum(cells, 1.0) > depth:
        raise RuntimeError("locked geometric cell count has no admissible ratio root")

    lower = 1.0
    upper = ratio
    for _ in range(80):
        midpoint = np.float64(0.5) * (np.float64(lower) + np.float64(upper))
        if geometric_sum(cells, float(midpoint)) < depth:
            lower = float(midpoint)
        else:
            upper = float(midpoint)
    effective_ratio = float(np.float64(0.5) * (np.float64(lower) + np.float64(upper)))
    widths = top * effective_ratio ** np.arange(cells, dtype=np.float64)
    relative_span_error = abs(float(np.sum(widths)) - depth) / depth
    if widths[0] != top:
        raise RuntimeError("deterministic geometric grid changed the locked first cell")
    if relative_span_error > 2.0e-14:
        raise RuntimeError("deterministic geometric grid did not span the requested depth")
    if widths.size > 1 and np.max(widths[1:] / widths[:-1]) > ratio * (
        1.0 + 1.0e-13
    ):
        raise RuntimeError("deterministic geometric grid exceeded its growth bound")
    return widths


def bisect_cell_widths(cell_widths_m: np.ndarray) -> np.ndarray:
    widths = np.asarray(cell_widths_m, dtype=float)
    if widths.ndim != 1 or np.any(widths <= 0.0):
        raise ValueError("only positive one-dimensional cells can be bisected")
    return np.repeat(0.5 * widths, 2)


def _region_areas(config: dict) -> dict[str, float]:
    geometry = config["geometry"]["primary_single_device"]
    overlap = float(geometry["contact_overlap_nominal_m"])
    length = float(geometry["vo2_length_m"])
    width = float(geometry["vo2_width_m"])
    if not 0.0 < 2.0 * overlap < length:
        raise ValueError("contact overlap leaves no bare region")
    return {
        "bare_vo2": (length - 2.0 * overlap) * width,
        "electrode_covered_vo2": 2.0 * overlap * width,
    }


def repair_surface_cell_bound_m(formal_config: dict, repair_config: dict) -> float:
    geometry = formal_config["geometry"]["primary_single_device"]
    al2o3 = formal_config["parameter_contract"]["passive_region_materials"][
        "al2o3"
    ]
    grid = repair_config["nonuniform_grid"]
    diffusivity = float(al2o3["thermal_conductivity_W_mK"]) / float(
        al2o3["volumetric_heat_capacity_J_m3K"]
    )
    penetration = np.sqrt(
        diffusivity / (np.pi * float(grid["high_frequency_Hz"]))
    )
    return float(
        min(
            penetration / 10.0,
            float(geometry["ti_thickness_m"]) / int(grid["ti_cells_min"]),
            float(geometry["au_thickness_m"]) / int(grid["au_cells_min"]),
            float(grid["coarse_top_cell_m_max"]),
        )
    )


def build_repair_overlay_branch(
    formal_config: dict, repair_config: dict, *, grid_level: str
) -> tuple[VerticalThermalReference, np.ndarray]:
    if grid_level not in {"coarse", "fine"}:
        raise ValueError("repair grid level must be coarse or fine")
    geometry = formal_config["geometry"]["primary_single_device"]
    materials = formal_config["parameter_contract"]["passive_region_materials"]
    grid = repair_config["nonuniform_grid"]
    multiplier = 1 if grid_level == "coarse" else 2
    ti_cells = int(grid["ti_cells_min"]) * multiplier
    au_cells = int(grid["au_cells_min"]) * multiplier
    ti_widths = np.full(ti_cells, float(geometry["ti_thickness_m"]) / ti_cells)
    au_widths = np.full(au_cells, float(geometry["au_thickness_m"]) / au_cells)
    widths = np.concatenate([ti_widths, au_widths])
    conductivity = np.concatenate(
        [
            np.full(ti_cells, float(materials["ti"]["thermal_conductivity_W_mK"])),
            np.full(au_cells, float(materials["au"]["thermal_conductivity_W_mK"])),
        ]
    )
    capacity = np.concatenate(
        [
            np.full(
                ti_cells,
                float(materials["ti"]["volumetric_heat_capacity_J_m3K"]),
            ),
            np.full(
                au_cells,
                float(materials["au"]["volumetric_heat_capacity_J_m3K"]),
            ),
        ]
    )
    return (
        _branch_reference_from_cells(
            "ti_au_overlay_branch",
            cell_widths_m=widths,
            thermal_conductivities_W_mK=conductivity,
            volumetric_capacities_J_m3K=capacity,
            fixed_terminal=False,
        ),
        widths,
    )


def build_repair_substrate_branch(
    formal_config: dict,
    repair_config: dict,
    *,
    substrate_depth_m: float,
    grid_level: str,
) -> tuple[VerticalThermalReference, np.ndarray]:
    if grid_level not in {"coarse", "fine"}:
        raise ValueError("repair grid level must be coarse or fine")
    material = formal_config["parameter_contract"]["passive_region_materials"][
        "al2o3"
    ]
    grid = repair_config["nonuniform_grid"]
    coarse = geometric_surface_refined_cell_widths(
        substrate_depth_m,
        top_cell_m=repair_surface_cell_bound_m(formal_config, repair_config),
        growth_ratio=float(grid["adjacent_cell_growth_ratio_max"]),
    )
    widths = coarse if grid_level == "coarse" else bisect_cell_widths(coarse)
    conductivity = np.full(
        widths.size, float(material["thermal_conductivity_W_mK"])
    )
    capacity = np.full(
        widths.size, float(material["volumetric_heat_capacity_J_m3K"])
    )
    return (
        _branch_reference_from_cells(
            "al2o3_substrate_branch",
            cell_widths_m=widths,
            thermal_conductivities_W_mK=conductivity,
            volumetric_capacities_J_m3K=capacity,
            fixed_terminal=True,
        ),
        widths,
    )


def build_repair_raw_components(
    formal_config: dict,
    repair_config: dict,
    *,
    substrate_depth_m: float,
    grid_level: str,
    overlay_branch: VerticalThermalReference,
    overlay_cell_widths_m: np.ndarray,
) -> RawVerticalComponents:
    substrate, substrate_widths = build_repair_substrate_branch(
        formal_config,
        repair_config,
        substrate_depth_m=substrate_depth_m,
        grid_level=grid_level,
    )
    overlay_widths = np.asarray(overlay_cell_widths_m, dtype=float)
    return RawVerticalComponents(
        substrate=substrate,
        overlay=overlay_branch,
        region_areas_m2=_region_areas(formal_config),
        substrate_depth_m=float(substrate_depth_m),
        grid_level=grid_level,
        substrate_cell_widths_m=substrate_widths,
        overlay_cell_widths_m=overlay_widths,
    )


def _scaled_reference(
    reference: VerticalThermalReference,
    conductance_scale: float,
    capacity_scale: float,
) -> VerticalThermalReference:
    if conductance_scale <= 0.0 or capacity_scale <= 0.0:
        raise ValueError("reference normalization scales must be positive")
    return VerticalThermalReference(
        reference.region_id,
        reference.capacities_J_m2K * capacity_scale,
        reference.conductance_matrix_W_m2K * conductance_scale,
        reference.input_vector_W_m2K * conductance_scale,
        reference.output_vector_W_m2K * conductance_scale,
        reference.direct_conductance_W_m2K * conductance_scale,
    )


def repair_normalization_scales(
    raw_anchor: RawVerticalComponents,
    formal_config: dict,
) -> VerticalNormalizationScales:
    """Compute the single G/C scale pair from a production-D fine anchor."""

    if raw_anchor.grid_level != "fine":
        raise ValueError("repair normalization must be computed from a fine-grid anchor")
    regions = raw_anchor.raw_region_references()
    raw_conductance = sum(
        raw_anchor.region_areas_m2[region] * reference.dc_conductance_W_m2K
        for region, reference in regions.items()
    )
    raw_capacity = sum(
        raw_anchor.region_areas_m2[region] * reference.total_capacity_J_m2K
        for region, reference in regions.items()
    )
    normalization = formal_config["vertical_reference"][
        "device_effective_normalization"
    ]
    target_conductance = float(
        normalization["nominal_total_thermal_conductance_W_K"]
    )
    target_capacity = float(normalization["nominal_memory_capacity_target_J_K"])
    return VerticalNormalizationScales(
        conductance_scale=target_conductance / raw_conductance,
        capacity_scale=target_capacity / raw_capacity,
        raw_integrated_dc_conductance_W_K=float(raw_conductance),
        raw_integrated_memory_capacity_J_K=float(raw_capacity),
    )


def apply_repair_normalization(
    raw: RawVerticalComponents,
    scales: VerticalNormalizationScales,
) -> NormalizedVerticalReferences:
    """Apply an already-computed pair-wide scale without reanchoring."""

    raw_regions = raw.raw_region_references()
    regions = {
        region: _scaled_reference(
            reference,
            scales.conductance_scale,
            scales.capacity_scale,
        )
        for region, reference in raw_regions.items()
    }
    # Evaluate the two source-author anchors from the unscaled quantities and
    # their locked positive factors.  Re-solving a very stiff scaled matrix
    # here loses digits through direct-minus-dynamic cancellation even though
    # the normalized state-space model itself is unchanged.
    integrated_conductance = sum(
        raw.region_areas_m2[region] * reference.dc_conductance_W_m2K
        for region, reference in raw_regions.items()
    ) * scales.conductance_scale
    integrated_capacity = sum(
        raw.region_areas_m2[region] * reference.total_capacity_J_m2K
        for region, reference in raw_regions.items()
    ) * scales.capacity_scale
    return NormalizedVerticalReferences(
        references=regions,
        region_areas_m2=dict(raw.region_areas_m2),
        conductance_scale=float(scales.conductance_scale),
        capacity_scale=float(scales.capacity_scale),
        integrated_dc_conductance_W_K=float(integrated_conductance),
        integrated_memory_capacity_J_K=float(integrated_capacity),
    )


def analytic_homogeneous_substrate_admittance_W_m2K(
    formal_config: dict,
    angular_frequency_rad_s: np.ndarray,
    *,
    substrate_depth_m: float | None,
) -> np.ndarray:
    """Return the analytic Al2O3 finite-depth or semi-infinite admittance.

    ``substrate_depth_m=None`` selects the semi-infinite ``k*q`` comparator.
    A finite depth selects the fixed-bottom ``k*q*coth(q*D)`` comparator.  The
    analytic branch is diagnostic only and never substitutes for a production
    finite-volume reference.
    """

    omega = np.atleast_1d(np.asarray(angular_frequency_rad_s, dtype=float))
    if np.any(omega < 0.0) or not np.isfinite(omega).all():
        raise ValueError("angular frequencies must be finite and nonnegative")
    material = formal_config["parameter_contract"]["passive_region_materials"][
        "al2o3"
    ]
    conductivity = float(material["thermal_conductivity_W_mK"])
    volumetric_capacity = float(material["volumetric_heat_capacity_J_m3K"])
    q = np.sqrt(1j * omega * volumetric_capacity / conductivity)
    if substrate_depth_m is None:
        return conductivity * q
    depth = float(substrate_depth_m)
    if not np.isfinite(depth) or depth <= 0.0:
        raise ValueError("finite analytic substrate depth must be positive")
    response = np.empty(omega.size, dtype=complex)
    zero = omega == 0.0
    response[zero] = conductivity / depth
    nonzero_q = q[~zero]
    with np.errstate(over="ignore", invalid="ignore"):
        response[~zero] = conductivity * nonzero_q / np.tanh(nonzero_q * depth)
    return response


def build_normalized_vertical_references(
    config: dict,
    *,
    contact_overlap_m: float | None = None,
    substrate_depth_m: float | None = None,
    cells_per_layer: int | None = None,
) -> NormalizedVerticalReferences:
    """Build raw region references, then apply the two locked positive scales."""

    geometry = config["geometry"]["primary_single_device"]
    materials = config["parameter_contract"]["passive_region_materials"]
    reference_config = config["vertical_reference"]
    overlap = float(
        geometry["contact_overlap_nominal_m"]
        if contact_overlap_m is None
        else contact_overlap_m
    )
    length = float(geometry["vo2_length_m"])
    width = float(geometry["vo2_width_m"])
    if not 0.0 < 2.0 * overlap < length:
        raise ValueError("contact overlap leaves no bare region")
    areas = {
        "bare_vo2": (length - 2.0 * overlap) * width,
        "electrode_covered_vo2": 2.0 * overlap * width,
    }
    cells = int(cells_per_layer or reference_config["spatial_cells_per_layer_min"])
    substrate_depth = float(
        substrate_depth_m
        if substrate_depth_m is not None
        else reference_config["substrate_depth_nominal_m"]
    )
    al2o3 = materials["al2o3"]
    ti = materials["ti"]
    au = materials["au"]
    substrate = _branch_matrices(
        [
            (
                substrate_depth,
                float(al2o3["thermal_conductivity_W_mK"]),
                float(al2o3["volumetric_heat_capacity_J_m3K"]),
                cells,
            )
        ],
        fixed_terminal=True,
    )
    overlay = _branch_matrices(
        [
            (
                float(geometry["ti_thickness_m"]),
                float(ti["thermal_conductivity_W_mK"]),
                float(ti["volumetric_heat_capacity_J_m3K"]),
                cells,
            ),
            (
                float(geometry["au_thickness_m"]),
                float(au["thermal_conductivity_W_mK"]),
                float(au["volumetric_heat_capacity_J_m3K"]),
                cells,
            ),
        ],
        fixed_terminal=False,
    )
    raw = {
        "bare_vo2": _combine_branches("bare_vo2", [substrate]),
        "electrode_covered_vo2": _combine_branches(
            "electrode_covered_vo2", [substrate, overlay]
        ),
    }
    raw_integrated_conductance = sum(
        areas[region] * model.dc_conductance_W_m2K for region, model in raw.items()
    )
    raw_integrated_capacity = sum(
        areas[region] * model.total_capacity_J_m2K for region, model in raw.items()
    )
    normalization = reference_config["device_effective_normalization"]
    target_conductance = float(normalization["nominal_total_thermal_conductance_W_K"])
    target_capacity = float(normalization["nominal_memory_capacity_target_J_K"])
    conductance_scale = target_conductance / raw_integrated_conductance
    capacity_scale = target_capacity / raw_integrated_capacity
    scaled = {
        region: _scaled_reference(model, conductance_scale, capacity_scale)
        for region, model in raw.items()
    }
    integrated_conductance = sum(
        areas[region] * model.dc_conductance_W_m2K
        for region, model in scaled.items()
    )
    integrated_capacity = sum(
        areas[region] * model.total_capacity_J_m2K
        for region, model in scaled.items()
    )
    return NormalizedVerticalReferences(
        references=scaled,
        region_areas_m2=areas,
        conductance_scale=float(conductance_scale),
        capacity_scale=float(capacity_scale),
        integrated_dc_conductance_W_K=float(integrated_conductance),
        integrated_memory_capacity_J_K=float(integrated_capacity),
    )


def fit_passive_ladder(
    reference: VerticalThermalReference,
    order: int,
    fit_contract: dict,
    *,
    maximum_function_evaluations: int | None = None,
) -> tuple[PassiveThermalLadder, dict[str, float]]:
    """Fit a positive Cauer ladder to an independent reference response."""

    time_grid = fit_contract["time_fit_grid"]
    frequency_grid = fit_contract["frequency_fit_grid_Hz"]
    times = np.geomspace(
        float(time_grid["start_s"]),
        float(time_grid["stop_s"]),
        int(time_grid["points"]),
    )
    frequencies = np.geomspace(
        float(frequency_grid["start"]),
        float(frequency_grid["stop"]),
        int(frequency_grid["points"]),
    )
    omega = 2.0 * np.pi * frequencies
    reference_evaluator = VerticalReferenceModalEvaluator(reference)
    reference_step = reference_evaluator.step_heat_flux_W_m2(times)
    reference_impulse = reference_evaluator.impulse_tail_W_m2K_s(times)
    reference_frequency = reference_evaluator.driving_admittance_W_m2K(omega)
    weights = fit_contract["response_weights"]
    initial = initial_passive_ladder(
        region_id=reference.region_id,
        order=order,
        total_capacity_J_m2K=reference.total_capacity_J_m2K,
        dc_conductance_W_m2K=reference.dc_conductance_W_m2K,
    )
    initial_log = np.log(
        np.concatenate(
            [initial.capacities_J_m2K, initial.conductances_W_m2K]
        )
    )

    step_scale = max(float(np.sqrt(np.mean(reference_step**2))), 1.0e-30)
    impulse_scale = max(float(np.sqrt(np.mean(reference_impulse**2))), 1.0e-30)

    def residual(log_parameters: np.ndarray) -> np.ndarray:
        parameters = np.exp(log_parameters)
        ladder = PassiveThermalLadder(
            reference.region_id,
            parameters[:order],
            parameters[order:],
        )
        step = (ladder.step_heat_flux_W_m2(times) - reference_step) / step_scale
        impulse = (
            ladder.impulse_tail_W_m2K_s(times) - reference_impulse
        ) / impulse_scale
        candidate_frequency = ladder.driving_admittance_W_m2K(omega)
        frequency = np.log(np.maximum(np.abs(candidate_frequency), 1.0e-300)) - np.log(
            np.maximum(np.abs(reference_frequency), 1.0e-300)
        )
        return np.concatenate(
            [
                np.sqrt(float(weights["step"]) / step.size) * step,
                np.sqrt(float(weights["impulse"]) / impulse.size) * impulse,
                np.sqrt(float(weights["frequency_log_magnitude"]) / frequency.size)
                * frequency,
            ]
        )

    result = least_squares(
        residual,
        initial_log,
        xtol=float(fit_contract["optimizer_relative_objective_tolerance"]),
        ftol=float(fit_contract["optimizer_relative_objective_tolerance"]),
        gtol=float(fit_contract["optimizer_relative_objective_tolerance"]),
        max_nfev=int(
            maximum_function_evaluations
            or fit_contract["optimizer_max_iterations"]
        ),
    )
    fitted = np.exp(result.x)
    ladder = PassiveThermalLadder(
        reference.region_id, fitted[:order], fitted[order:]
    )
    return ladder, {
        "success": float(bool(result.success)),
        "cost": float(result.cost),
        "optimality": float(result.optimality),
        "function_evaluations": float(result.nfev),
    }


def reduction_validation_metrics(
    reference: VerticalThermalReference,
    ladder: PassiveThermalLadder,
    fit_contract: dict,
) -> dict[str, float]:
    """Evaluate a fitted ladder only on held-out geometric-midpoint grids."""

    if reference.region_id != ladder.region_id:
        raise ValueError("reference and ladder region identifiers do not match")
    time_grid = fit_contract["time_fit_grid"]
    frequency_grid = fit_contract["frequency_fit_grid_Hz"]
    fit_times = np.geomspace(
        float(time_grid["start_s"]),
        float(time_grid["stop_s"]),
        int(time_grid["points"]),
    )
    validation_times = np.sqrt(fit_times[:-1] * fit_times[1:])
    fit_frequencies = np.geomspace(
        float(frequency_grid["start"]),
        float(frequency_grid["stop"]),
        int(frequency_grid["points"]),
    )
    validation_omega = 2.0 * np.pi * np.sqrt(
        fit_frequencies[:-1] * fit_frequencies[1:]
    )
    reference_evaluator = VerticalReferenceModalEvaluator(reference)
    reference_step = reference_evaluator.step_heat_flux_W_m2(validation_times)
    candidate_step = ladder.step_heat_flux_W_m2(validation_times)
    reference_step_zero = float(
        reference_evaluator.step_heat_flux_W_m2(np.asarray([0.0]))[0]
    )
    step_scale = max(
        float(np.sqrt(np.mean((reference_step - reference_step_zero) ** 2))),
        1.0e-30,
    )
    step_nrmse = float(
        np.sqrt(np.mean((candidate_step - reference_step) ** 2)) / step_scale
    )
    reference_impulse = reference_evaluator.impulse_tail_W_m2K_s(validation_times)
    candidate_impulse = ladder.impulse_tail_W_m2K_s(validation_times)
    impulse_scale = max(float(np.sqrt(np.mean(reference_impulse**2))), 1.0e-30)
    impulse_nrmse = float(
        np.sqrt(np.mean((candidate_impulse - reference_impulse) ** 2))
        / impulse_scale
    )
    reference_frequency = reference_evaluator.driving_admittance_W_m2K(
        validation_omega
    )
    candidate_frequency = ladder.driving_admittance_W_m2K(validation_omega)
    frequency_rmse = float(
        np.sqrt(
            np.mean(
                (
                    np.log(np.maximum(np.abs(candidate_frequency), 1.0e-300))
                    - np.log(np.maximum(np.abs(reference_frequency), 1.0e-300))
                )
                ** 2
            )
        )
    )
    metrics = {
        "step_response_nrmse": step_nrmse,
        "impulse_response_nrmse": impulse_nrmse,
        "frequency_log_magnitude_rmse": frequency_rmse,
        "maximum_pole_real_per_s": float(np.max(ladder.poles_per_s())),
        "minimum_capacity_J_m2K": float(np.min(ladder.capacities_J_m2K)),
        "minimum_conductance_W_m2K": float(np.min(ladder.conductances_W_m2K)),
    }
    if not np.isfinite(np.asarray(list(metrics.values()), dtype=float)).all():
        raise ValueError("reduction validation produced a nonfinite metric")
    return metrics


def fit_locked_order_family(
    reference: VerticalThermalReference,
    config: dict,
    *,
    maximum_function_evaluations: int | None = None,
) -> dict[int, tuple[PassiveThermalLadder, dict[str, float]]]:
    """Fit K=1,2,3,8 exactly as locked; selection is restricted to K=2,3."""

    reduction = config["vertical_reduction"]
    orders = [
        int(reduction["ablation_order"]),
        *(int(value) for value in reduction["candidate_orders"]),
        int(reduction["reference_order"]),
    ]
    if orders != [1, 2, 3, 8]:
        raise ValueError("the locked K-state order family drifted from [1,2,3,8]")
    fit_contract = config["vertical_reference"]["reduction_fit_contract"]
    fitted: dict[int, tuple[PassiveThermalLadder, dict[str, float]]] = {}
    for order in orders:
        ladder, optimizer = fit_passive_ladder(
            reference,
            order,
            fit_contract,
            maximum_function_evaluations=maximum_function_evaluations,
        )
        metrics = reduction_validation_metrics(reference, ladder, fit_contract)
        fitted[order] = (ladder, {**optimizer, **metrics})
    return fitted


def select_smallest_passing_candidate(
    fitted: dict[int, tuple[PassiveThermalLadder, dict[str, float]]],
    config: dict,
) -> PassiveThermalLadder:
    """Select only the smallest K in {2,3} passing every response gate."""

    gates = config["gates"]
    for order in (2, 3):
        if order not in fitted:
            raise ValueError(f"candidate K={order} was not fitted")
        ladder, metrics = fitted[order]
        passed = (
            metrics["step_response_nrmse"]
            <= float(gates["k_state_step_response_nrmse_max"])
            and metrics["impulse_response_nrmse"]
            <= float(gates["k_state_impulse_response_nrmse_max"])
            and metrics["frequency_log_magnitude_rmse"]
            <= float(gates["k_state_frequency_log_magnitude_rmse_max"])
            and metrics["maximum_pole_real_per_s"] < 0.0
            and metrics["minimum_capacity_J_m2K"] > 0.0
            and metrics["minimum_conductance_W_m2K"] > 0.0
        )
        if passed:
            return ladder
    raise RuntimeError("neither locked candidate K=2 nor K=3 passed every reduction gate")
