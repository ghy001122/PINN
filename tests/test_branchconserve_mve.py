from __future__ import annotations

from pathlib import Path

import numpy as np

from pinnpcm.branchconserve.artifacts import (
    atomic_write_json,
    atomic_write_npz,
    file_sha256,
    to_builtin,
)
from pinnpcm.branchconserve.contract import load_branchconserve_contract
from pinnpcm.branchconserve.observations import (
    area_weighted_rms,
    hotspot_centroid_m,
    minimum_passing_tier,
    select_sensor_blocks,
    two_dimensional_response_ratio,
)
from pinnpcm.branchconserve.steady_model import build_branchconserve_model


ROOT = Path(__file__).resolve().parents[1]


def _model():
    contract = load_branchconserve_contract(
        ROOT / "configs/q2_branchconserve_2d_steady_mve_v1.yaml",
        repository_root=ROOT,
    )
    return build_branchconserve_model(contract, spatial_level=1)


def test_hotspot_and_2d_response_use_frozen_area_weighting() -> None:
    model = _model()
    x, y = np.meshgrid(model.grid.x_centers_m, model.grid.y_centers_m)
    response = 2.0 + 0.5 * y / y.max()
    assert area_weighted_rms(response, model.grid.cell_area_m2) > 2.0
    assert two_dimensional_response_ratio(response, model.grid.cell_area_m2) > 0.0
    temperature = model.ambient_temperature_K + response
    x_c, y_c = hotspot_centroid_m(
        model.grid, temperature, model.ambient_temperature_K
    )
    assert model.grid.x_centers_m[0] <= x_c <= model.grid.x_centers_m[-1]
    assert y_c > float(np.mean(model.grid.y_centers_m))


def test_sensor_selection_appends_complete_ten_row_blocks() -> None:
    o1 = np.zeros((10, 2))
    candidates = {
        (25.0e-9, 50.0e-9): np.tile([1.0, 0.0], (10, 1)),
        (50.0e-9, 150.0e-9): np.tile([0.0, 2.0], (10, 1)),
        (75.0e-9, 250.0e-9): np.tile([1.0, 1.0], (10, 1)),
    }
    selected = select_sensor_blocks(o1, candidates, count=2)
    assert len(selected.coordinates_m) == 2
    assert selected.augmented_jacobian.shape == (30, 2)


def test_o1_rank_zero_still_allows_o2_or_o3_to_pass() -> None:
    tiers = {
        "O1": np.zeros((10, 2)),
        "O2": np.vstack((np.zeros((10, 2)), np.eye(2) * 2.0)),
        "O3": np.eye(2) * 3.0,
        "O4": np.eye(2) * 10.0,
    }
    assert minimum_passing_tier(tiers) == "O2"
    failing = {"O1": np.zeros((1, 2)), "O2": np.zeros((2, 2)), "O3": np.zeros((3, 2)), "O4": np.eye(2) * 10}
    assert minimum_passing_tier(failing) is None


def test_atomic_artifacts_handle_numpy_scalars_and_reject_nonfinite(tmp_path: Path) -> None:
    payload = {"flag": np.bool_(True), "count": np.int64(3), "value": np.float64(1.5)}
    assert to_builtin(payload) == {"flag": True, "count": 3, "value": 1.5}
    json_path = tmp_path / "record.json"
    npz_path = tmp_path / "field.npz"
    atomic_write_json(json_path, payload)
    atomic_write_npz(npz_path, field=np.arange(4.0))
    assert json_path.exists() and npz_path.exists()
    assert len(file_sha256(json_path)) == 64
    with np.testing.assert_raises(ValueError):
        atomic_write_json(tmp_path / "bad.json", {"bad": float("nan")})


def test_batch2_target_counts_and_dynamic_pinn_import_ban() -> None:
    contract = load_branchconserve_contract(
        ROOT / "configs/q2_branchconserve_2d_steady_mve_v1.yaml",
        repository_root=ROOT,
    )
    assert contract.raw["batch2"]["perturbation_targets_max"] == 384
    assert contract.raw["batch2"]["anchor_equilibria_max"] == 68
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/pinnpcm/branchconserve").glob("*.py")
    )
    assert "pinnpcm.pinn" not in source
    assert "geophase_phase1_v2_controller" not in source
