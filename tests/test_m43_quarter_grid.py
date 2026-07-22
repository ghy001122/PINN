from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.solvers.m43_finite_width_thermal import build_quarter_grid


CONFIG = Path(__file__).resolve().parents[1] / "configs" / "m43_finite_width_thermal_spreading.yaml"


def _small_config() -> dict:
    config = deepcopy(yaml.safe_load(CONFIG.read_text(encoding="utf-8")))
    config["time"]["maximum_diffusion_length_m"] = 2.0e-7
    config["grid"]["domain_multipliers_of_maximum_diffusion_length"] = [1.0, 2.0, 3.0]
    return config


def test_quarter_grid_is_source_aligned_and_domain_prefix_nested() -> None:
    config = _small_config()
    d1 = build_quarter_grid(config, "rho5", "M1", "D1", mode="3d")
    d2 = build_quarter_grid(config, "rho5", "M1", "D2", mode="3d")
    d3 = build_quarter_grid(config, "rho5", "M1", "D3", mode="3d")

    assert np.array_equal(d1.x_edges_m, d2.x_edges_m[: d1.x_edges_m.size])
    assert np.array_equal(d2.x_edges_m, d3.x_edges_m[: d2.x_edges_m.size])
    assert np.array_equal(d1.y_edges_m, d2.y_edges_m[: d1.y_edges_m.size])
    assert np.array_equal(d2.y_edges_m, d3.y_edges_m[: d2.y_edges_m.size])
    assert np.array_equal(d1.z_edges_m, d2.z_edges_m[: d1.z_edges_m.size])
    assert np.array_equal(d2.z_edges_m, d3.z_edges_m[: d2.z_edges_m.size])
    assert np.any(np.isclose(d3.x_edges_m, 5.0e-8, rtol=0.0, atol=1.0e-22))
    assert np.any(np.isclose(d3.y_edges_m, 2.5e-7, rtol=0.0, atol=1.0e-22))
    assert np.all(np.diff(d3.x_edges_m) > 0.0)
    assert np.all(np.diff(d3.y_edges_m) > 0.0)
    assert np.all(np.diff(d3.z_edges_m) > 0.0)


def test_square_and_xz_grid_contracts_are_distinct() -> None:
    config = _small_config()
    square = build_quarter_grid(config, "rho1", "M1", "D1", mode="3d")
    xz = build_quarter_grid(config, "rho5", "M1", "D1", mode="xz")

    expected_square_half_side = 0.5 * np.sqrt(config["geometry"]["source_area_m2"])
    assert square.source_half_x_m == pytest.approx(expected_square_half_side)
    assert square.source_half_y_m == pytest.approx(expected_square_half_side)
    assert square.far_y_dirichlet is True
    assert xz.shape[1] == 1
    assert xz.y_edges_m.tolist() == pytest.approx(
        [0.0, config["geometry"]["source_full_y_m"]]
    )
    assert xz.far_y_dirichlet is False


def test_matched_three_d_and_xz_grids_share_short_axis_and_depth() -> None:
    config = _small_config()
    three_d = build_quarter_grid(config, "rho5", "M2", "D2", mode="3d")
    xz = build_quarter_grid(config, "rho5", "M2", "D2", mode="xz")
    assert np.array_equal(three_d.x_edges_m, xz.x_edges_m)
    assert np.array_equal(three_d.z_edges_m, xz.z_edges_m)
@pytest.mark.parametrize("geometry", ["rho1", "rho5"])
@pytest.mark.parametrize("mesh", ["M1", "M2", "M3"])
def test_m43_near_source_cells_are_isotropic_in_all_three_directions(
    geometry: str, mesh: str
) -> None:
    config = _small_config()
    grid = build_quarter_grid(config, geometry, mesh, "D1", mode="3d")
    profile = config["grid"]["mesh_profiles"][mesh]
    key = "square_quarter_source_cells_xy" if geometry == "rho1" else "rho5_quarter_source_cells_xy"
    depth_key = "square_source_depth_cells" if geometry == "rho1" else "rho5_source_depth_cells"
    nx, ny = (int(value) for value in profile[key])
    nz = int(profile[depth_key])

    dx = np.diff(grid.x_edges_m)[:nx]
    dy = np.diff(grid.y_edges_m)[:ny]
    dz = np.diff(grid.z_edges_m)[:nz]
    spacing = float(dx[0])
    assert np.allclose(dx, spacing, rtol=1.0e-14, atol=0.0)
    assert np.allclose(dy, spacing, rtol=1.0e-14, atol=0.0)
    assert np.allclose(dz, spacing, rtol=1.0e-14, atol=0.0)
    assert grid.x_edges_m[nx] == pytest.approx(grid.source_half_x_m, rel=1.0e-14)
    assert grid.y_edges_m[ny] == pytest.approx(grid.source_half_y_m, rel=1.0e-14)