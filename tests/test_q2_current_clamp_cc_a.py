from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.current_clamp import source_oracle
from pinnpcm.current_clamp.artifacts import atomic_write_json
from pinnpcm.current_clamp.contract import (
    OFFICIAL_CURRENTS_A,
    TERMINAL_DISPOSITIONS,
    load_current_clamp_contract,
)
from pinnpcm.current_clamp.source_mapping import (
    analytic_geometry_factor_m,
    device_effective_conductivity_S_m,
    uniform_port_resistance_ohm,
)
from pinnpcm.evaluation.q2_qiu_source_oracle import OracleParameters


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_current_clamp_hysgeo_pinn_v1_cc_a.yaml"


@pytest.fixture(scope="module")
def config() -> dict:
    return load_current_clamp_contract(CONFIG)


@pytest.fixture(scope="module")
def params(config: dict) -> OracleParameters:
    return OracleParameters.from_config(config)


def test_contract_freezes_nonvoting_batch1_scope(config: dict) -> None:
    assert config["scientific_vote"] is False
    assert config["formal_execution_count"] == 0
    assert tuple(config["current_clamp"]["official_currents_A"]) == pytest.approx(
        OFFICIAL_CURRENTS_A
    )
    assert set(config["terminal_dispositions"]) == TERMINAL_DISPOSITIONS
    assert config["source_mapping"]["two_dimensional_execution_in_batch1"] is False
    assert config["production_source"]["resistance_variant"] == "S1_QS"


def test_uniform_port_mapping_roundtrips_exactly() -> None:
    geometry_factor = analytic_geometry_factor_m(
        length_m=100e-9, width_m=500e-9, thickness_m=100e-9
    )
    assert geometry_factor == pytest.approx(5.0e-7)
    resistance = 1234.5
    conductivity = device_effective_conductivity_S_m(
        device_resistance_ohm=resistance,
        geometry_factor_m=geometry_factor,
    )
    assert uniform_port_resistance_ohm(
        conductivity_S_m=conductivity,
        geometry_factor_m=geometry_factor,
    ) == pytest.approx(resistance, rel=1.0e-15)


@pytest.mark.parametrize("branch", ["heating", "cooling"])
@pytest.mark.parametrize("current_A", [1.0e-4, 4.0e-4, 7.0e-4])
def test_nested_current_clamp_roots_are_unique_and_certified(
    branch: str,
    current_A: float,
    params: OracleParameters,
    config: dict,
) -> None:
    result = source_oracle.discover_roots(
        branch=branch,
        current_A=current_A,
        params=params,
        config=config,
    )
    assert len(result.roots) == 1
    assert result.root_hausdorff_K <= 1.0e-8
    root = result.roots[0]
    assert root.certified
    assert root.scaled_equilibrium_residual <= 1.0e-12
    assert root.resistance_derivative_relative_error <= 1.0e-6
    assert root.alpha_tau_dimensionless <= -1.0e-3


def test_current_clamp_admission_evaluator_obeys_frozen_gate(config: dict) -> None:
    gate, roots, _stationary, continuation = source_oracle.evaluate_admission(config)
    assert gate["disposition"] in TERMINAL_DISPOSITIONS
    assert len(roots) == 14
    assert {row["branch"] for row in roots} == {"heating", "cooling"}
    assert all(row["continuation_connected"] for row in continuation)
    assert gate["semantic_boundary"].startswith("branch-conditioned")


def test_current_clamp_module_does_not_import_retired_solver_or_pinn() -> None:
    syntax = ast.parse(Path(source_oracle.__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = ("branchconserve", "geophase", "pinnpcm.pinn")
    assert not any(any(token in name for token in forbidden) for name in imports)


def test_atomic_json_rejects_nonfinite_payload(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="NaN and infinity"):
        atomic_write_json(tmp_path / "invalid.json", {"bad": np.float64(np.nan)})
    assert not (tmp_path / "invalid.json").exists()
