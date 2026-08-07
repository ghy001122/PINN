from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.current_clamp.cc_b_campaign import _exclusive_formal_launch
from pinnpcm.current_clamp.cc_b_contract import (
    CCBContractError,
    EXPECTED_SEQUENCE,
    load_cc_b_contract,
)
from pinnpcm.current_clamp.cc_b_model import (
    build_cc_b_model,
    uniform_electrical_geometry_ratio,
)
from pinnpcm.current_clamp.cc_b_solver import prolong_temperature, restrict_area_average
from pinnpcm.current_clamp.cc_b_stability import uniform_mode_operator_regression
from pinnpcm.current_clamp.contract import CurrentClampContractError, load_current_clamp_contract
from pinnpcm.current_clamp.source_oracle import discover_roots, run_cc_a
from pinnpcm.evaluation.q2_qiu_source_oracle import OracleParameters


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_current_clamp_hysgeo_pinn_v1_cc_b.yaml"
CC_A_CONFIG = ROOT / "configs/q2_current_clamp_hysgeo_pinn_v1_cc_a.yaml"


@pytest.fixture(scope="module")
def contract():
    return load_cc_b_contract(CONFIG, repository_root=ROOT)


def test_contract_authenticates_topology_and_full_manifest(contract) -> None:
    assert contract.raw["clamp_topology"]["clamp_target"] == "conductive_sheet_current"
    assert contract.raw["clamp_topology"]["dynamic_state"] == "temperature_cells_only"
    assert contract.raw["clamp_topology"]["parallel_capacitance_role"] == "inactive_external_source_metadata"
    assert contract.sequence == EXPECTED_SEQUENCE
    assert len(contract.sequence) == len(set(contract.sequence)) == 36
    assert contract.raw["budget"]["formal_matrix_launches_max"] == 1


def test_cc_a_claim_bearing_threshold_drift_fails_closed(tmp_path: Path) -> None:
    payload = yaml.safe_load(CC_A_CONFIG.read_text(encoding="utf-8"))
    payload["branch_admission"]["common_current_state_separation_min"] = 0.09
    path = tmp_path / "drifted.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(CurrentClampContractError, match="admission gate drifted"):
        load_current_clamp_contract(path)


def test_cc_b_contract_rejects_terminal_total_clamp(tmp_path: Path) -> None:
    payload = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    payload["clamp_topology"]["clamp_target"] = "terminal_total_current"
    path = tmp_path / "invalid_cc_b.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(CCBContractError, match="topology drifted"):
        load_cc_b_contract(path, repository_root=ROOT)


def test_current_projection_is_algebraic_and_conservative(contract) -> None:
    params = OracleParameters.from_config(contract.cc_a_config)
    root = discover_roots(
        branch="heating", current_A=2.0e-4, params=params, config=contract.cc_a_config
    ).roots[0]
    model = build_cc_b_model(
        contract,
        spatial_level=1,
        current_set_A=2.0e-4,
        branch="heating",
        defect="NOM",
    )
    evaluation = model.evaluate_temperature(
        np.full(model.grid.shape, root.temperature_K, dtype=float)
    )
    assert evaluation.source_current_A == pytest.approx(2.0e-4, rel=1.0e-12)
    assert -evaluation.ground_current_A == pytest.approx(2.0e-4, rel=1.0e-12)
    assert evaluation.device_voltage_V == pytest.approx(
        evaluation.current_set_A / evaluation.unit_conductance_S
    )
    assert not hasattr(model, "external_capacitance_F")


def test_defects_are_local_and_not_renormalized(contract) -> None:
    nominal = build_cc_b_model(
        contract, spatial_level=1, current_set_A=4.0e-4, branch="heating", defect="NOM"
    )
    lu = build_cc_b_model(
        contract, spatial_level=1, current_set_A=4.0e-4, branch="heating", defect="LU"
    )
    changed = lu.vertical_conductance_W_m2K != nominal.vertical_conductance_W_m2K
    assert changed.any() and (~changed).any()
    assert np.all(lu.vertical_conductance_W_m2K[~changed] == nominal.vertical_conductance_W_m2K[~changed])
    assert np.all(lu.vertical_conductance_W_m2K[changed] == 0.5 * nominal.vertical_conductance_W_m2K[changed])
    assert float(np.sum(lu.vertical_conductance_W_m2K)) < float(
        np.sum(nominal.vertical_conductance_W_m2K)
    )


def test_uniform_electrical_mapping_uses_real_fvm(contract) -> None:
    geometry = float(contract.raw["source_mapping"]["geometry_factor_m"])
    ratios = [
        uniform_electrical_geometry_ratio(contract, spatial_level=level, conductivity_S_m=123.0)
        for level in (1, 2)
    ]
    errors = [abs(value - geometry) / geometry for value in ratios]
    assert max(errors) <= 5.0e-3
    assert errors[1] <= errors[0] or max(errors) <= 64.0 * np.finfo(float).eps


def test_uniform_topology_recovers_one_cc_a_rate(contract) -> None:
    params = OracleParameters.from_config(contract.cc_a_config)
    root = discover_roots(
        branch="cooling", current_A=4.0e-4, params=params, config=contract.cc_a_config
    ).roots[0]
    model = build_cc_b_model(
        contract,
        spatial_level=1,
        current_set_A=4.0e-4,
        branch="cooling",
        defect="NOM",
        uniform_coefficients=True,
    )
    result = uniform_mode_operator_regression(
        model,
        equilibrium_temperature_K=root.temperature_K,
        analytic_lambda_per_s=root.spectral_abscissa_per_s,
    )
    assert result["passed"]


def test_nested_grid_transfer_is_conservative() -> None:
    coarse = np.arange(6.0).reshape(2, 3)
    fine = prolong_temperature(coarse, (4, 6))
    assert fine.shape == (4, 6)
    assert np.array_equal(restrict_area_average(fine, coarse.shape), coarse)


def test_formal_launch_is_exclusive(tmp_path: Path) -> None:
    marker = tmp_path / "formal_launch.json"
    _exclusive_formal_launch(marker)
    with pytest.raises(FileExistsError):
        _exclusive_formal_launch(marker)


def test_cc_a_contract_load_failure_emits_unique_invalid_terminal(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [valid", encoding="utf-8")
    first = run_cc_a(
        config_path=bad, repository_root=ROOT, output_root=tmp_path / "outputs"
    )
    second = run_cc_a(
        config_path=bad, repository_root=ROOT, output_root=tmp_path / "outputs"
    )
    assert first["validity"] == second["validity"] == "invalid"
    assert first["execution_id"] != second["execution_id"]
    assert (tmp_path / "outputs" / first["execution_id"] / "terminal.json").is_file()


def test_cc_b_model_does_not_import_retired_control_paths() -> None:
    import pinnpcm.current_clamp.cc_b_model as module

    syntax = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = ("controller", "geophase_nls", "pinnpcm.pinn", "continuation")
    assert not any(any(token in name for token in forbidden) for name in imports)
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "series_resistance" not in source
    assert "parallel_capacitance" not in source
