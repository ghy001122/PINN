from __future__ import annotations

from pathlib import Path

import numpy as np

from pinnpcm.branchconserve.contract import load_branchconserve_contract
from pinnpcm.branchconserve.steady_model import build_branchconserve_model


ROOT = Path(__file__).resolve().parents[1]


def _model(**kwargs):
    contract = load_branchconserve_contract(
        ROOT / "configs/q2_branchconserve_2d_steady_mve_v1.yaml",
        repository_root=ROOT,
    )
    return build_branchconserve_model(contract, spatial_level=1, **kwargs)


def test_boundary_faces_are_not_contact_mask_dirichlet_cells() -> None:
    model = _model()
    source_nodes = model.electrical_topology.source_nodes
    assert source_nodes.size == model.grid.ny
    assert int(np.count_nonzero(model.grid.left_contact_mask)) == 2 * model.grid.ny
    assert source_nodes.size < int(np.count_nonzero(model.grid.left_contact_mask))


def test_sheet_thermal_operator_does_not_multiply_thickness_again() -> None:
    model = _model()
    coefficient = model.thermal_fields.sheet_thermal_conductance_W_K
    k0 = coefficient[model.grid.ny // 2, 4]
    k1 = coefficient[model.grid.ny // 2, 5]
    harmonic = 2.0 * k0 * k1 / (k0 + k1)
    expected = harmonic * model.grid.dy_m / model.grid.dx_m
    row = (model.grid.ny // 2) * model.grid.nx + 4
    assert np.isclose(model.thermal_matrix[row, row + 1], -expected)
    assert not np.isclose(
        model.thermal_matrix[row, row + 1],
        -expected * model.grid.thickness_m,
    )


def test_zero_drive_control_volume_residual_and_ledgers_close() -> None:
    model = _model()
    temperature = np.full(model.grid.shape, model.ambient_temperature_K)
    evaluation = model.evaluate_temperature(
        temperature, 0.0, 1.0, source_voltage_V=0.0
    )
    assert evaluation.scaled_electrical_residual_inf <= 1.0e-14
    assert evaluation.scaled_thermal_residual_inf <= 1.0e-14
    assert evaluation.load_line_residual <= 1.0e-14
    assert evaluation.ledger.pass_all
    assert np.count_nonzero(evaluation.electrical_faces.x_face_current_A) == 0
    assert np.count_nonzero(evaluation.thermal_x_face_flux_W) == 0


def test_zero_voltage_stability_context_accepts_infinitesimal_signed_vd() -> None:
    model = _model()
    temperature = np.full(model.grid.shape, model.ambient_temperature_K)
    rhs = model.dynamic_rhs(
        temperature,
        device_voltage_V=-1.0e-6,
        source_voltage_V=0.0,
        branch_memory=1.0,
    )
    assert np.isfinite(rhs).all()


def test_lu_rd_patches_modify_only_registered_vertical_sink_cells() -> None:
    nominal = _model()
    modified = _model(alpha_lu=-0.25, alpha_rd=-0.25)
    ratio = modified.vertical_conductance_W_m2K / nominal.vertical_conductance_W_m2K
    assert set(np.unique(ratio)).issubset({0.75, 1.0})
    assert np.any(ratio == 0.75)
    assert np.all(modified.vertical_conductance_W_m2K >= 0.5 * nominal.vertical_conductance_W_m2K)
