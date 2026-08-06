from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.evaluation import q2_qiu_source_oracle as oracle
from pinnpcm.physics.qiu_author_compact_model import (
    default_parameters,
    major_branch_insulating_fraction,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs/q2_qiu_source_consistent_branchconserve_v2_stage_a.yaml"
)


@pytest.fixture(scope="module")
def config() -> dict:
    return oracle.load_stage_a_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def params(config: dict) -> oracle.OracleParameters:
    return oracle.OracleParameters.from_config(config)


def test_stage_a_contract_is_nonvoting_and_has_exact_terminal_vocabulary(
    config: dict,
) -> None:
    assert config["scientific_vote"] is False
    assert config["formal_execution_count"] == 0
    assert set(config["terminal_dispositions"]) == oracle.TERMINAL_DISPOSITIONS
    assert config["planned_stage_b_uniform_limit"]["status"] == (
        "planned_not_executed"
    )
    assert config["resistance_variants"]["S1_QS"]["production_eligibility"] == (
        "only_candidate_for_later_v2_uniform_limit"
    )
    assert config["resistance_variants"]["S7_DYNAMIC_COMPARATOR"][
        "production_eligibility"
    ] == "forbidden"


def test_major_branch_thresholds_and_steepness_are_source_consistent(
    config: dict, params: oracle.OracleParameters
) -> None:
    assert params.critical_temperature_K + params.loop_width_K / 2.0 == (
        pytest.approx(336.3965)
    )
    assert params.critical_temperature_K - params.loop_width_K / 2.0 == (
        pytest.approx(329.2035)
    )
    assert 1.0 / (2.0 * params.beta_per_K) == pytest.approx(
        config["branch_contract"]["equivalent_logistic_scale_K"]
    )
    assert not math.isclose(
        params.loop_width_K,
        config["branch_contract"]["equivalent_logistic_scale_K"],
    )
    assert config["branch_contract"]["direct_beta_plus_k_patch"] == "rejected"


@pytest.mark.parametrize("branch,delta", [("heating", 1), ("cooling", -1)])
def test_independent_major_branch_matches_existing_source_module(
    branch: str,
    delta: int,
    params: oracle.OracleParameters,
) -> None:
    temperatures = np.linspace(320.0, 360.0, 101)
    expected = major_branch_insulating_fraction(
        temperatures, delta, default_parameters()
    )
    observed = oracle.insulating_fraction(temperatures, delta, params)
    assert np.max(np.abs(np.asarray(observed) - np.asarray(expected))) <= 1.0e-15
    threshold = params.critical_temperature_K + delta * params.loop_width_K / 2.0
    assert oracle.insulating_fraction(threshold, delta, params) == pytest.approx(0.5)
    assert branch in ("heating", "cooling")


def test_s1_and_s7_have_distinct_source_roles(
    params: oracle.OracleParameters,
) -> None:
    temperature = 350.0
    s1, _ = oracle.resistance_and_derivative(temperature, 1, 1.0, params)
    s7, _ = oracle.resistance_and_derivative(
        temperature, 1, params.dynamic_metallic_factor, params
    )
    assert s7 - s1 == pytest.approx(
        (params.dynamic_metallic_factor - 1.0) * params.metallic_resistance_ohm
    )
    assert s7 > s1


@pytest.mark.parametrize("delta", [1, -1])
@pytest.mark.parametrize("multiplier", [1.0, 4.90])
def test_resistance_derivative_matches_central_difference(
    delta: int, multiplier: float, params: oracle.OracleParameters
) -> None:
    temperature = 334.0
    _, analytic = oracle.resistance_and_derivative(
        temperature, delta, multiplier, params
    )
    step = 1.0e-4
    plus, _ = oracle.resistance_and_derivative(
        temperature + step, delta, multiplier, params
    )
    minus, _ = oracle.resistance_and_derivative(
        temperature - step, delta, multiplier, params
    )
    finite_difference = (plus - minus) / (2.0 * step)
    assert analytic == pytest.approx(finite_difference, rel=2.0e-8)


@pytest.mark.parametrize(
    "source_voltage,branch,variant",
    [
        (9.0, "heating", "S1_QS"),
        (15.8, "cooling", "S1_QS"),
        (17.0, "cooling", "S7_DYNAMIC_COMPARATOR"),
    ],
)
def test_nested_root_discovery_certifies_every_reported_fixed_point(
    source_voltage: float,
    branch: str,
    variant: str,
    config: dict,
    params: oracle.OracleParameters,
) -> None:
    result = oracle.discover_fixed_points(
        source_voltage_V=source_voltage,
        load_resistance_ohm=12000.0,
        branch=branch,
        resistance_variant=variant,
        params=params,
        config=config,
    )
    assert len(result.fixed_points) >= 1
    assert result.root_set_hausdorff_K <= 1.0e-8
    for point in result.fixed_points:
        assert point.current_residual <= 1.0e-12
        assert point.thermal_residual <= 1.0e-12
        assert point.stability.analytic_fd_relative_frobenius <= 1.0e-6
        assert point.stability.eigenpair_relative_residual_max <= 1.0e-10


def test_analytic_stability_jacobian_matches_central_difference(
    config: dict, params: oracle.OracleParameters
) -> None:
    result = oracle.discover_fixed_points(
        source_voltage_V=9.0,
        load_resistance_ohm=12000.0,
        branch="heating",
        resistance_variant="S1_QS",
        params=params,
        config=config,
    )
    point = result.fixed_points[0]
    state = np.asarray([point.device_voltage_V, point.temperature_K])
    analytic = oracle.analytic_jacobian(
        state,
        source_voltage_V=9.0,
        load_resistance_ohm=12000.0,
        delta=1,
        metallic_multiplier=1.0,
        params=params,
    )
    finite = oracle.finite_difference_jacobian(
        state,
        source_voltage_V=9.0,
        load_resistance_ohm=12000.0,
        delta=1,
        metallic_multiplier=1.0,
        params=params,
    )
    assert np.linalg.norm(analytic - finite, ord="fro") / np.linalg.norm(
        analytic, ord="fro"
    ) <= 1.0e-6


def _fake_reachability_row(
    *, branch: str, voltage: float, conductive_state: float
) -> dict:
    return {
        "branch": branch,
        "source_voltage_V": voltage,
        "conductive_state": conductive_state,
        "robust_stability_margin": 0.1,
        "voting_eligible": True,
    }


def test_domain_gate_requires_nondegenerate_forward_and_dual_branch_separation(
    config: dict,
) -> None:
    voltages = [9.0, 10.0, 11.0, 13.0, 14.0]
    heating_states = [0.05, 0.2, 0.5, 0.8, 0.9]
    cooling_states = [0.8, 0.75, 0.7, 0.65, 0.6]
    rows = [
        _fake_reachability_row(
            branch="heating", voltage=voltage, conductive_state=state
        )
        for voltage, state in zip(voltages, heating_states, strict=True)
    ] + [
        _fake_reachability_row(
            branch="cooling", voltage=voltage, conductive_state=state
        )
        for voltage, state in zip(voltages, cooling_states, strict=True)
    ]
    result = oracle.evaluate_domain_gates(rows, config)
    assert result["forward"]["heating"]["pass"] is True
    assert result["dual_branch"]["pass"] is True


def test_12p5v_is_diagnostic_only_and_cannot_vote(config: dict) -> None:
    assert config["base_matrix"]["diagnostic_only_source_voltages_V"] == [12.5]
    assert config["reachability"]["diagnostic_only_source_voltages_V"] == [12.5]


def test_source_discrepancy_matrix_rejects_direct_beta_k_patch() -> None:
    rows = oracle.build_source_to_code_discrepancy_rows()
    direct = next(row for row in rows if row["source_equation"] == "direct beta+k patch")
    assert direct["proposed_v2_mapping"] == "REJECT_DIRECT_BETA_K_PATCH"
    s7 = next(row for row in rows if row["source_equation"] == "S7")
    assert "diagnostic comparator only" in s7["proposed_v2_mapping"]


def test_source_audit_checks_primary_artifacts_and_formula_parity(
    config: dict, params: oracle.OracleParameters
) -> None:
    result = oracle.audit_source_contract(
        repo_root=ROOT, config=config, params=params
    )
    assert result["status"] == "PASS"
    assert result["major_loop_Tpr_semantics"] == "Tpr_inactive_before_reversal"
    assert result["direct_beta_plus_k_patch_verdict"] == (
        "REJECT_DIRECT_BETA_K_PATCH"
    )
    assert result["independent_repository_formula_parity_max"] <= 1.0e-13


def test_oracle_has_no_branchconserve_or_pinn_import() -> None:
    syntax = ast.parse(Path(oracle.__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any("branchconserve" in name for name in imports)
    assert not any("pinnpcm.pinn" in name for name in imports)
