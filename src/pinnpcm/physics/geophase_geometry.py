"""Geometry and region masks for the active Phase 1 single-device model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


BARE_REGION = 0
CONTACT_REGION = 1


@dataclass(frozen=True)
class GeoPhaseGrid:
    """Uniform cell-centred mesh on the resolved VO2 x-y footprint."""

    x_edges_m: np.ndarray
    y_edges_m: np.ndarray
    thickness_m: float
    contact_overlap_m: float
    left_contact_mask: np.ndarray
    right_contact_mask: np.ndarray
    region_index: np.ndarray

    @property
    def nx(self) -> int:
        return int(self.x_edges_m.size - 1)

    @property
    def ny(self) -> int:
        return int(self.y_edges_m.size - 1)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.ny, self.nx)

    @property
    def dx_m(self) -> float:
        return float(self.x_edges_m[1] - self.x_edges_m[0])

    @property
    def dy_m(self) -> float:
        return float(self.y_edges_m[1] - self.y_edges_m[0])

    @property
    def x_centers_m(self) -> np.ndarray:
        return 0.5 * (self.x_edges_m[:-1] + self.x_edges_m[1:])

    @property
    def y_centers_m(self) -> np.ndarray:
        return 0.5 * (self.y_edges_m[:-1] + self.y_edges_m[1:])

    @property
    def cell_area_m2(self) -> float:
        return self.dx_m * self.dy_m

    @property
    def device_area_m2(self) -> float:
        return float(
            (self.x_edges_m[-1] - self.x_edges_m[0])
            * (self.y_edges_m[-1] - self.y_edges_m[0])
        )

    @property
    def contact_mask(self) -> np.ndarray:
        return self.left_contact_mask | self.right_contact_mask

    @property
    def bare_mask(self) -> np.ndarray:
        return self.region_index == BARE_REGION


def build_geophase_grid(
    config: dict,
    *,
    spatial_level: int = 1,
    contact_overlap_m: float | None = None,
    nx_override: int | None = None,
    ny_override: int | None = None,
) -> GeoPhaseGrid:
    """Build the locked physical x-y grid and fail closed on coordinate drift."""

    if spatial_level <= 0:
        raise ValueError("spatial_level must be positive")
    geometry = config["geometry"]["primary_single_device"]
    base = config["reference_solver"]["base_grid"]
    length = float(geometry["vo2_length_m"])
    width = float(geometry["vo2_width_m"])
    thickness = float(geometry["vo2_thickness_m"])
    nx = int(nx_override or int(base["nx"]) * spatial_level)
    ny = int(ny_override or int(base["ny"]) * spatial_level)
    if nx <= 1 or ny <= 1:
        raise ValueError("the x-y grid requires at least two cells per direction")
    if not np.isclose(length, float(base["domain_x_m"][1])):
        raise ValueError("x extent no longer matches the current-path contract")
    if not np.isclose(width, float(base["domain_y_m"][1])):
        raise ValueError("y extent no longer matches the width contract")

    overlap = float(
        geometry["contact_overlap_nominal_m"]
        if contact_overlap_m is None
        else contact_overlap_m
    )
    if not 0.0 < overlap < 0.5 * length:
        raise ValueError("contact overlap must leave a non-empty bare channel")
    x_edges = np.linspace(0.0, length, nx + 1)
    y_edges = np.linspace(0.0, width, ny + 1)
    dx = float(x_edges[1] - x_edges[0])
    edge_ratio = overlap / dx
    if config["geometry"]["region_masks"]["mask_edges_must_align_with_fvm_faces"]:
        if not np.isclose(edge_ratio, round(edge_ratio), rtol=0.0, atol=1.0e-10):
            raise ValueError("contact-mask edge does not align with an FVM face")

    x_centers = 0.5 * (x_edges[:-1] + x_edges[1:])
    left_1d = x_centers < overlap
    right_1d = x_centers > length - overlap
    left = np.broadcast_to(left_1d[None, :], (ny, nx)).copy()
    right = np.broadcast_to(right_1d[None, :], (ny, nx)).copy()
    if np.any(left & right):
        raise ValueError("left and right contact masks overlap")
    region = np.where(left | right, CONTACT_REGION, BARE_REGION).astype(np.int8)
    return GeoPhaseGrid(
        x_edges_m=x_edges,
        y_edges_m=y_edges,
        thickness_m=thickness,
        contact_overlap_m=overlap,
        left_contact_mask=left,
        right_contact_mask=right,
        region_index=region,
    )


def assert_not_coordinate_swapped(grid: GeoPhaseGrid, config: dict) -> None:
    """Fail when the 100 nm current path and 500 nm width are exchanged."""

    geometry = config["geometry"]["primary_single_device"]
    x_extent = float(grid.x_edges_m[-1] - grid.x_edges_m[0])
    y_extent = float(grid.y_edges_m[-1] - grid.y_edges_m[0])
    if not np.isclose(x_extent, float(geometry["vo2_length_m"])):
        raise ValueError("coordinate swap or x-extent corruption detected")
    if not np.isclose(y_extent, float(geometry["vo2_width_m"])):
        raise ValueError("coordinate swap or y-extent corruption detected")
