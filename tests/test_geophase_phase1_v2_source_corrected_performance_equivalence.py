from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.solvers.geophase_phase1_v2_performance_equivalence import (
    EXPECTED_EXACT_VOTES,
    EXPECTED_TELEMETRY,
    EquivalenceObservation,
    NumericField,
    PairExecution,
    atomic_write_json,
    atomic_write_text,
    build_equivalence_csv,
    build_deterministic_audit_cases,
    build_equivalence_plan,
    build_equivalence_summary,
    canonical_sha256,
    compare_observations,
    hash_equivalence_input,
    load_equivalence_contract,
    make_evidence_row,
    run_equivalence_audit,
    run_electrical_pair,
)
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    resolve_controller_v2,
)
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as equivalence


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_source_corrected_performance_repair.yaml"
)
S2_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
ORACLE_PATH = ROOT / "tests" / "oracles" / "pr8_geophase_2p5d_fvm.py"
OVERLAY_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml"
)
MODULE_PATH = (
    ROOT
    / "src"
    / "pinnpcm"
    / "solvers"
    / "geophase_phase1_v2_performance_equivalence.py"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _load_test_only_oracle() -> ModuleType:
    module_name = "_phase1_v2_performance_equivalence_injected_pr8_oracle"
    spec = importlib.util.spec_from_file_location(module_name, ORACLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


@pytest.fixture(scope="module")
def contract():
    return load_equivalence_contract(CONTRACT_PATH)


@pytest.fixture(scope="module")
def resolved_source():
    source = yaml.safe_load(S2_CONFIG_PATH.read_text(encoding="utf-8"))
    resolved = resolve_controller_v2(S2_CONFIG_PATH, OVERLAY_PATH)
    return source, resolved


def _exact_votes() -> dict[str, object]:
    return {
        "nonlinear_method": "damped_newton_krylov",
        "converged_disposition": "converged",
        "fallback_disposition": "not_used",
        "accepted_rejected_sequence": ["rejected", "accepted"],
        "failure_classification": "none",
        "event_count_direction_and_order": ["heating_up"],
        "reversal_count_direction_and_order": ["heating_to_cooling"],
    }


def _telemetry(offset: int = 0) -> dict[str, int]:
    return {
        "Newton_iterations": 3 + offset,
        "Krylov_matvecs": 7 + offset,
        "Armijo_backtracks": 1 + offset,
        "Picard_iterations": 2 + offset,
        "fallback_iterations": offset,
    }


def _observation(
    *,
    conductive_offset: float = 0.0,
    exact_overrides: dict[str, object] | None = None,
    telemetry_offset: int = 0,
) -> EquivalenceObservation:
    exact = _exact_votes()
    exact.update(exact_overrides or {})
    return EquivalenceObservation(
        numeric={
            "phi": NumericField(np.array([0.0, 12.5]), "potential_V"),
            "T": NumericField(np.array([336.4, 336.5]), "temperature_K"),
            "s": NumericField(
                np.array([0.5 + conductive_offset, 0.6]), "conductive_state"
            ),
            "b": NumericField(np.array([1.0, 0.99]), "branch_memory"),
            "Vd": NumericField(12.5, "device_voltage_V"),
            "terminal_current": NumericField(2.0e-6, "terminal_current_A"),
            "cell_Joule_power": NumericField(
                np.array([1.0e-6, 2.0e-6]), "power_W"
            ),
            "thermal_storage": NumericField(
                2.0e-6, "ledger_power_terms", scale_group="thermal"
            ),
            "thermal_sink": NumericField(
                -1.0e-6, "ledger_power_terms", scale_group="thermal"
            ),
            "thermal_relative_residual": NumericField(
                2.0e-14, "relative_residual"
            ),
            "sample_time": NumericField(1.0e-8, "time_s"),
        },
        exact_votes=exact,
        telemetry=_telemetry(telemetry_offset),
    )


def test_contract_and_plan_lock_9_18_9_21_without_running_cases(contract) -> None:
    assert contract.normalized_relative_difference_max == 1.0e-12
    assert contract.exact_votes == EXPECTED_EXACT_VOTES
    assert contract.telemetry_only == EXPECTED_TELEMETRY

    plan = build_equivalence_plan(contract)
    counts = {
        family: sum(row.family == family for row in plan)
        for family in ("electrical", "interval", "progression", "failure")
    }

    assert counts == {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }
    assert len(plan) == 57
    assert [row.plan_index for row in plan] == list(range(57))
    assert len({row.sample_id for row in plan}) == 57
    assert len({row.input_sha256 for row in plan}) == 57
    assert all(len(row.input_sha256) == 64 for row in plan)
    assert all(
        row.candidate_paths
        == ("full_step", "first_half_step", "second_half_step")
        for row in plan
        if row.family == "interval"
    )
    failure_pairs = {
        (row.candidate_paths[0], row.failure_class)
        for row in plan
        if row.family == "failure"
    }
    assert len(failure_pairs) == 3 * 7


def test_concrete_input_hash_binds_plan_contract_and_runtime_input(contract) -> None:
    row = build_equivalence_plan(contract)[0]
    first = hash_equivalence_input(
        row,
        {"protocol": "zero_drive", "conductivity": [1.0, 2.0]},
        contract,
    )
    repeated = hash_equivalence_input(
        row,
        {"conductivity": [1.0, 2.0], "protocol": "zero_drive"},
        contract,
    )
    changed = hash_equivalence_input(
        row,
        {"protocol": "zero_drive", "conductivity": [1.0, 2.1]},
        contract,
    )

    assert first == repeated
    assert first != changed
    assert len(first) == 64


def test_dynamic_test_only_oracle_is_injected_at_low_level(contract) -> None:
    config = yaml.safe_load(S2_CONFIG_PATH.read_text(encoding="utf-8"))
    grid = build_geophase_grid(config, spatial_level=1)
    conductivity = np.full(grid.shape, 2.5e4, dtype=float)
    production_module_name = "pinnpcm.solvers.geophase_2p5d_fvm"
    production_before = sys.modules.get(production_module_name)
    oracle = _load_test_only_oracle()

    def candidate_solver(grid, conductivity, source_voltage, ground_voltage):
        return oracle.solve_sheet_electrical(
            grid, conductivity, source_voltage, ground_voltage
        )

    result = run_electrical_pair(
        candidate_solver=candidate_solver,
        comparison_solver=oracle.solve_sheet_electrical,
        grid=grid,
        conductivity_S_m=conductivity,
        source_voltage_V=15.8,
        ground_voltage_V=0.0,
        protocol_voltage_scale_V=15.8,
        contract=contract,
    )

    assert result.comparison.passed is True
    assert result.comparison.maximum_normalized_difference == 0.0
    assert result.candidate is not result.oracle
    assert "tests.oracles" not in MODULE_PATH.read_text(encoding="utf-8")
    assert "pr8_geophase_2p5d_fvm" not in MODULE_PATH.read_text(encoding="utf-8")
    assert sys.modules.get(production_module_name) is production_before


def test_numeric_comparison_uses_locked_floors_and_shared_ledger_scale(contract) -> None:
    oracle = _observation()
    candidate = _observation(conductive_offset=5.0e-13, telemetry_offset=100)

    comparison = compare_observations(
        candidate,
        oracle,
        contract,
        protocol_voltage_scale_V=12.5,
    )

    assert comparison.passed is True
    assert comparison.maximum_normalized_difference == pytest.approx(5.0e-13)
    assert not comparison.exact_mismatches
    assert all(item["voting"] is False for item in comparison.telemetry.values())
    assert any(item["equal"] is False for item in comparison.telemetry.values())
    thermal = {
        result.field: result
        for result in comparison.numeric
        if result.field.startswith("thermal_")
    }
    assert thermal["thermal_storage"].denominator == pytest.approx(2.0e-6)
    assert thermal["thermal_sink"].denominator == pytest.approx(2.0e-6)


@pytest.mark.parametrize(
    ("vote", "changed"),
    [
        ("nonlinear_method", "fail_closed_fixed_point_fallback"),
        ("converged_disposition", "not_converged"),
        ("fallback_disposition", "used"),
        ("accepted_rejected_sequence", ["accepted"]),
        ("failure_classification", "thermal_ledger"),
        ("event_count_direction_and_order", ["cooling_down"]),
        ("reversal_count_direction_and_order", []),
    ],
)
def test_each_preregistered_topology_vote_is_exact(
    contract, vote: str, changed: object
) -> None:
    comparison = compare_observations(
        _observation(exact_overrides={vote: changed}),
        _observation(),
        contract,
        protocol_voltage_scale_V=12.5,
    )

    assert comparison.passed is False
    assert set(comparison.exact_mismatches) == {vote}


@pytest.mark.parametrize(
    "candidate_field",
    [
        NumericField(np.array([0.5, np.nan]), "conductive_state"),
        NumericField(np.array([0.5, 0.6, 0.7]), "conductive_state"),
        NumericField(np.array([0.5 + 2.0e-12, 0.6]), "conductive_state"),
    ],
)
def test_nonfinite_shape_or_tolerance_failure_fails_closed(
    contract, candidate_field: NumericField
) -> None:
    oracle = _observation()
    numeric = dict(_observation().numeric)
    numeric["s"] = candidate_field
    candidate = EquivalenceObservation(
        numeric=numeric,
        exact_votes=_exact_votes(),
        telemetry=_telemetry(),
    )

    comparison = compare_observations(
        candidate,
        oracle,
        contract,
        protocol_voltage_scale_V=12.5,
    )

    assert comparison.passed is False
    assert comparison.maximum_normalized_difference > 1.0e-12
    assert comparison.worst_field == "s"


def test_atomic_builders_are_deterministic_and_incomplete_is_nonvoting(
    contract, tmp_path: Path
) -> None:
    plan = build_equivalence_plan(contract)
    passing_comparison = compare_observations(
        _observation(),
        _observation(),
        contract,
        protocol_voltage_scale_V=12.5,
    )
    rows = [make_evidence_row(row, passing_comparison) for row in plan]
    csv_text = build_equivalence_csv(rows)
    summary = build_equivalence_summary(rows, contract)
    incomplete = build_equivalence_summary(rows[:-1], contract)
    csv_path = tmp_path / "equivalence.csv"
    json_path = tmp_path / "equivalence.json"

    atomic_write_text(csv_path, csv_text)
    atomic_write_json(json_path, summary)

    parsed_rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
    parsed_summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(parsed_rows) == 57
    assert [int(row["plan_index"]) for row in parsed_rows] == list(range(57))
    assert all(len(row["input_sha256"]) == 64 for row in parsed_rows)
    assert all(len(row["plan_sha256"]) == 64 for row in parsed_rows)
    assert all(len(row["output_sha256"]) == 64 for row in parsed_rows)
    assert parsed_summary["status"] == (
        "strict_equivalence_pass_pending_runtime_readiness"
    )
    assert parsed_summary["complete"] is True
    assert parsed_summary["all_equivalence_votes_pass"] is True
    assert parsed_summary["plan_identities_valid"] is True
    assert parsed_summary["hash_fields_valid"] is True
    assert parsed_summary["formal_execution_count"] == 0
    assert parsed_summary["formal_artifact_count"] == 0
    assert incomplete["status"] == "incomplete_nonvoting_equivalence_evidence"
    assert incomplete["disposition"] == "INCOMPLETE_NONVOTING"
    assert incomplete["all_equivalence_votes_pass"] is False
    assert not list(tmp_path.glob("*.tmp"))
    assert canonical_sha256(summary) == canonical_sha256(parsed_summary)
    with pytest.raises(FileExistsError, match="immutable artifact"):
        atomic_write_text(csv_path, csv_text)


def test_deterministic_real_cases_lock_three_states_and_corrected_protocol(
    resolved_source,
) -> None:
    source, resolved = resolved_source
    cases = build_deterministic_audit_cases(source, resolved)

    assert len(cases) == 9
    equilibrium = cases[("L1", "equilibrium")]
    critical = cases[("L1", "legal_critical")]
    high = cases[("L1", "high_conductive")]
    assert equilibrium.protocol_id == "zero_drive"
    assert equilibrium.protocol_voltage_scale_V == 1.0
    assert np.all(critical.initial_state.temperature_K == pytest.approx(336.4))
    assert np.all(critical.initial_state.conductive_state == 0.5)
    assert critical.protocol_id == "transition_probe_12p5V"
    assert critical.protocol_voltage_scale_V == 12.5
    assert np.all(high.initial_state.temperature_K == 380.0)
    assert high.protocol_id == "high_bias_lock_15p8V"
    assert high.protocol_voltage_scale_V == 15.8


def test_real_L1_equilibrium_interval_uses_all_three_paths_and_PR8_oracle(
    contract, resolved_source
) -> None:
    from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical

    source, resolved = resolved_source
    config = resolved.resolved_config
    cases = build_deterministic_audit_cases(source, resolved)
    row = next(
        item
        for item in build_equivalence_plan(contract)
        if item.family == "interval"
        and item.grid == "L1"
        and item.state == "equilibrium"
        and item.interval_class == "base"
    )
    pair = equivalence._execute_interval_row(
        row, cases[("L1", "equilibrium")], config, _load_test_only_oracle().solve_sheet_electrical
    )
    comparison = compare_observations(
        pair.candidate_observation,
        pair.oracle_observation,
        contract,
        protocol_voltage_scale_V=pair.protocol_voltage_scale_V,
    )

    assert solve_sheet_electrical is not _load_test_only_oracle().solve_sheet_electrical
    assert pair.validation_errors == ()
    assert pair.candidate_raw.full_candidate is not None
    assert pair.candidate_raw.first_half_candidate is not None
    assert pair.candidate_raw.second_half_candidate is not None
    assert pair.oracle_raw.full_candidate is not None
    assert pair.oracle_raw.first_half_candidate is not None
    assert pair.oracle_raw.second_half_candidate is not None
    assert comparison.passed is True


def test_real_failure_hook_hits_named_path_and_compares_classification(
    contract, resolved_source
) -> None:
    source, resolved = resolved_source
    config = resolved.resolved_config
    cases = build_deterministic_audit_cases(source, resolved)
    row = next(
        item
        for item in build_equivalence_plan(contract)
        if item.family == "failure"
        and item.candidate_paths == ("full_step",)
        and item.failure_class == "nonfinite"
    )
    pair = equivalence._execute_failure_row(
        row,
        cases[("L1", "legal_critical")],
        config,
        _load_test_only_oracle().solve_sheet_electrical,
    )
    comparison = compare_observations(
        pair.candidate_observation,
        pair.oracle_observation,
        contract,
        protocol_voltage_scale_V=pair.protocol_voltage_scale_V,
    )

    assert pair.validation_errors == ()
    assert pair.candidate_raw.diagnostics.full_step.finite is False
    assert pair.oracle_raw.diagnostics.full_step.finite is False
    assert pair.candidate_raw.first_half_candidate is None
    assert pair.oracle_raw.first_half_candidate is None
    assert comparison.passed is True
    assert "injected:full_step:nonfinite" in str(
        pair.candidate_observation.exact_votes["failure_classification"]
    )


def test_real_four_interval_zero_drive_progression_captures_streaming_and_order(
    contract, resolved_source
) -> None:
    source, resolved = resolved_source
    config = resolved.resolved_config
    cases = build_deterministic_audit_cases(source, resolved)
    row = next(
        item
        for item in build_equivalence_plan(contract)
        if item.family == "progression"
        and item.grid == "L1"
        and item.state == "equilibrium"
    )
    pair = equivalence._execute_progression_row(
        row,
        cases[("L1", "equilibrium")],
        config,
        _load_test_only_oracle().solve_sheet_electrical,
    )
    comparison = compare_observations(
        pair.candidate_observation,
        pair.oracle_observation,
        contract,
        protocol_voltage_scale_V=pair.protocol_voltage_scale_V,
    )

    assert pair.validation_errors == ()
    assert pair.candidate_raw.protocol_result.diagnostics.accepted_steps == 4
    assert pair.oracle_raw.protocol_result.diagnostics.accepted_steps == 4
    assert len(pair.candidate_raw.protocol_result.steps) == 4
    assert len(pair.oracle_raw.protocol_result.steps) == 4
    assert pair.candidate_raw.scalar_records
    assert pair.oracle_raw.scalar_records
    assert comparison.passed is True
    assert pair.candidate_observation.exact_votes[
        "accepted_rejected_sequence"
    ] == ("accepted", "accepted", "accepted", "accepted")


def test_run_equivalence_audit_orchestrates_four_in_memory_tables_without_publish(
    contract, resolved_source, tmp_path: Path
) -> None:
    source, resolved = resolved_source

    def oracle_stub(*args, **kwargs):
        raise AssertionError("focused orchestration stub must not run numerics")

    def candidate_stub(*args, **kwargs):
        raise AssertionError("focused orchestration stub must not run numerics")

    def row_executor(row, cases, config, locked, oracle_solver, candidate_solver):
        del cases, config, locked, oracle_solver, candidate_solver
        if row.family == "electrical":
            observation = EquivalenceObservation(
                numeric={"phi": NumericField(np.zeros(2), "potential_V")},
                exact_votes={},
                telemetry={},
            )
        else:
            observation = _observation()
        return PairExecution(
            candidate_observation=observation,
            oracle_observation=observation,
            candidate_raw={"stub": "candidate"},
            oracle_raw={"stub": "oracle"},
            protocol_voltage_scale_V=12.5,
        )

    result = run_equivalence_audit(
        oracle_solver=oracle_stub,
        candidate_solver=candidate_stub,
        source_config=source,
        resolved_controller=resolved,
        contract=contract,
        publish=False,
        _test_row_executor=row_executor,
    )

    assert len(result.rows) == 57
    assert set(result.tables) == {
        "electrical",
        "interval",
        "progression",
        "failure",
    }
    assert result.summary["all_equivalence_votes_pass"] is True
    assert result.summary["completed_counts"] == {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }
    assert result.published_paths == {}
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="can never publish"):
        run_equivalence_audit(
            oracle_solver=oracle_stub,
            candidate_solver=candidate_stub,
            source_config=source,
            resolved_controller=resolved,
            contract=contract,
            publish=True,
            output_dir=tmp_path,
            _test_row_executor=row_executor,
        )
