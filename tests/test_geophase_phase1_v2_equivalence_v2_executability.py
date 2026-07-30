from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest

from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_metric_validity_coverage_correction as correction,
)
from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator as v2
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as strict_v1


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "geophase_phase1_v2_equivalence_v2"
    / "sealed_contract_cases.json"
)
MANIFEST_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_metric_validity"
    / "coverage_correction"
    / "mechanical_field_contract.csv"
)
MANIFEST_SHA256 = "670dbb5acee9bc0bc4796e9c54d9de39c5a4016cc7344f1eff5f53291fb74f07"


@pytest.fixture(scope="module")
def contract() -> v2.LoadedContract:
    return v2.load_preregistered_contract_bundle()


@pytest.fixture(scope="module")
def streaming_schema() -> dict[str, Any]:
    return correction.derive_streaming_schema_from_source()


def _record(
    observation: Any,
    *,
    plan_index: int,
    sample_id: str,
    family: str,
    profile_id: str,
    grid_id: str = "L1",
    maximum_accepted_intervals: int | None = None,
    validation_errors: tuple[str, ...] = (),
) -> dict[str, Any]:
    return v2.observation_to_record(
        observation,
        plan_index=plan_index,
        sample_id=sample_id,
        family=family,
        profile_id=profile_id,
        grid_id=grid_id,
        protocol_voltage_scale_V=15.8,
        maximum_accepted_intervals=maximum_accepted_intervals,
        validation_errors=validation_errors,
    )


def _attempt_record(
    raw: Any,
    *,
    profile_id: str = "interval_full_accepted",
    plan_index: int = 11,
    sample_id: str = "EQ-INTERVAL-L1-legal_critical-base",
    include_only_integrity_passed_steps: bool = False,
    declared_failure: str | None = None,
    validation_errors: tuple[str, ...] = (),
) -> dict[str, Any]:
    observation, errors = correction._extract_attempt(
        raw,
        include_only_integrity_passed_steps=include_only_integrity_passed_steps,
        declared_failure=declared_failure,
    )
    assert not errors and observation is not None
    return _record(
        observation,
        plan_index=plan_index,
        sample_id=sample_id,
        family=("failure" if declared_failure else "interval"),
        profile_id=profile_id,
        validation_errors=validation_errors,
    )


def _progression_record(
    raw: Any,
    attempts: Any,
    schema: dict[str, Any],
    *,
    profile_id: str = "progression_full",
    validation_errors: tuple[str, ...] = (),
    fallback_observation: Any | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    observation, errors = correction._extract_progression(raw, attempts, schema)
    if observation is None:
        assert fallback_observation is not None
        observation = fallback_observation
    combined_errors = tuple(errors) + tuple(validation_errors)
    return (
        _record(
            observation,
            plan_index=28,
            sample_id="EQ-PROGRESSION-L1-legal_critical",
            family="progression",
            profile_id=profile_id,
            maximum_accepted_intervals=4,
            validation_errors=combined_errors,
        ),
        tuple(errors),
    )


def _failure_raw(
    *,
    path: str = "full_step",
    error_class: str | None = "RuntimeError",
    message_path: str | None = None,
) -> Any:
    message = None
    if error_class is not None:
        message = f"{message_path or path} synthetic failure"
    return correction._raw_attempt(
        accepted=False,
        failing_path=path,
        error_class=error_class,
        error_message=message,
    )


def _failure_record(
    raw: Any,
    *,
    path: str = "full_step",
    plan_index: int = 36,
    sample_id: str = "EQ-FAILURE-full_step-nonfinite",
) -> dict[str, Any]:
    return _attempt_record(
        raw,
        profile_id=f"failure_at_{path}",
        plan_index=plan_index,
        sample_id=sample_id,
        include_only_integrity_passed_steps=True,
        declared_failure=f"{path}:nonfinite",
    )


def _set_nonzero_lateral(raw: Any) -> None:
    for name in ("full_candidate", "first_half_candidate", "second_half_candidate"):
        step = getattr(raw, name)
        step.state.temperature_K = np.asarray([[336.0]], dtype=float)
        step.lateral_flux.x_face_flux_W = np.asarray([2.0e-6, -1.0e-6])
        step.lateral_flux.y_face_flux_W = np.asarray([5.0e-7, -5.0e-7])
        step.lateral_flux.net_cell_outflow_W = np.asarray([2.5e-6, -1.5e-6])
        step.lateral_flux.internal_pair_cancellation_W = 0.0
        step.lateral_flux.face_to_cell_global_residual_W = 0.0
        step.lateral_flux.matrix_face_relative_mismatch = 1.0e-12
        step.lateral_flux.matrix_face_roundoff_ratio = 0.25


def _comparison_terminal(comparison: dict[str, Any]) -> v2.TerminalState:
    event = comparison.get("failure_event")
    if event is None:
        return v2.finalise_plan_terminal(
            completed_rows=57,
            expected_rows=57,
            all_rows_pass=bool(comparison["row_pass"]),
        )
    return v2.classify_terminal(v2.TerminalEvent(event))


def _manifest_rows() -> list[dict[str, str]]:
    with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> str:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(v2.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_contract_loads_all_638_templates_and_exact_plan(
    contract: v2.LoadedContract,
) -> None:
    assert len(contract.templates) == 638
    assert len(contract.plan_rows) == 57
    assignments = v2.manifest_handler_assignments(contract)
    assert len(assignments) == 638
    assert set(assignments) == {
        template.template_id for template in contract.templates.values()
    }
    assert {
        handler: list(assignments.values()).count(handler)
        for handler in set(assignments.values())
    } == {
        "strict_primary_physical_vote": 544,
        "exact_topology_vote": 21,
        "analytic_mixed_flux_vote": 21,
        "lateral_hard_gate_disposition_vote": 22,
        "analytic_cancellation_vote": 15,
        "nonvoting_structural_validation": 15,
    }


def test_partition_is_an_exact_disjoint_12_plus_45_cover(
    contract: v2.LoadedContract,
) -> None:
    partition = contract.payload["ordered_plan_partition"]
    development = set(
        range(
            partition["metric_development"]["inclusive_start"],
            partition["metric_development"]["inclusive_end"] + 1,
        )
    )
    held_out = set(
        range(
            partition["held_out"]["inclusive_start"],
            partition["held_out"]["inclusive_end"] + 1,
        )
    )
    assert len(development) == 12
    assert len(held_out) == 45
    assert not development & held_out
    assert development | held_out == set(range(57))


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        *[(event, v2.TerminalState.INVALID_INFRA) for event in v2.INFRA_EVENTS],
        *[(event, v2.TerminalState.VALID_FAIL) for event in v2.VALID_FAIL_EVENTS],
        (v2.TerminalEvent.COMPLETE_PASS, v2.TerminalState.PASS),
    ],
)
def test_terminal_truth_table_is_exhaustive_and_disjoint(
    event: v2.TerminalEvent, expected: v2.TerminalState
) -> None:
    assert v2.classify_terminal(event) is expected
    assert v2.INFRA_EVENTS.isdisjoint(v2.VALID_FAIL_EVENTS)
    assert set(v2.INFRA_EVENTS | v2.VALID_FAIL_EVENTS) | {
        v2.TerminalEvent.COMPLETE_PASS
    } == set(v2.TerminalEvent)


def test_fail_fast_valid_failure_precedes_incomplete_plan() -> None:
    assert v2.finalise_plan_terminal(
        completed_rows=12,
        expected_rows=57,
        all_rows_pass=False,
        valid_failure_event=v2.TerminalEvent.FIELD_VOTE_FAILURE,
    ) is v2.TerminalState.VALID_FAIL
    assert v2.finalise_plan_terminal(
        completed_rows=12,
        expected_rows=57,
        all_rows_pass=True,
    ) is v2.TerminalState.INVALID_INFRA
    assert v2.finalise_plan_terminal(
        completed_rows=1,
        expected_rows=1,
        all_rows_pass=True,
    ) is v2.TerminalState.INVALID_INFRA


def test_all_required_when_profiles_are_executable(
    contract: v2.LoadedContract, streaming_schema: dict[str, Any]
) -> None:
    electrical = strict_v1.electrical_observation(correction._step().electrical)
    cases: list[dict[str, Any]] = [
        _record(
            electrical,
            plan_index=1,
            sample_id="EQ-ELECTRICAL-L1-legal_critical",
            family="electrical",
            profile_id="electrical_full",
        ),
        _attempt_record(correction._raw_attempt(accepted=True)),
        _attempt_record(
            correction._raw_attempt(
                accepted=False,
                present_paths=("full_step",),
                include_optional=False,
            ),
            profile_id="interval_minimal_rejected",
        ),
        _failure_record(_failure_raw()),
        _failure_record(
            _failure_raw(path="first_half_step"),
            path="first_half_step",
            plan_index=43,
            sample_id="EQ-FAILURE-first_half_step-nonfinite",
        ),
        _failure_record(
            _failure_raw(path="second_half_step"),
            path="second_half_step",
            plan_index=50,
            sample_id="EQ-FAILURE-second_half_step-nonfinite",
        ),
    ]
    for directions, profile in (
        (("upward", "downward"), "progression_full"),
        ((), "progression_NA_no_event_or_reversal"),
    ):
        raw, attempts = correction._raw_progression(
            streaming_schema,
            event_directions=directions,
            reversal_directions=(
                ("heating_to_cooling", "cooling_to_heating")
                if directions
                else ()
            ),
        )
        record, errors = _progression_record(
            raw, attempts, streaming_schema, profile_id=profile
        )
        assert not errors
        cases.append(record)
    for record in cases:
        comparison = v2.compare_record_pair(record, copy.deepcopy(record), contract)
        assert comparison["record_status"] == "auditable"
        assert comparison["row_pass"] is True
        assert comparison["template_consumption"][
            "all_active_templates_consumed_once"
        ] is True


def test_progression_scalar_hard_gate_templates_all_vote(
    contract: v2.LoadedContract, streaming_schema: dict[str, Any]
) -> None:
    raw, attempts = correction._raw_progression(streaming_schema)
    record, errors = _progression_record(raw, attempts, streaming_schema)
    assert not errors
    comparison = v2.compare_record_pair(record, copy.deepcopy(record), contract)
    hard_votes = [
        vote
        for vote in comparison["votes"]
        if vote["category"] == "C_lateral_hard_gate"
    ]
    active_hard_templates = {
        template.template_id
        for template in contract.templates.values()
        if template.family == "progression"
        and template.category == "C_lateral_hard_gate"
    }
    consumed = {
        template_id
        for vote in hard_votes
        for template_id in vote["template_ids"]
    }
    assert consumed == active_hard_templates
    assert all(len(vote["template_ids"]) == 2 for vote in hard_votes)


def _interval_fixture_records(mutation: str) -> tuple[dict[str, Any], dict[str, Any]]:
    oracle_raw = correction._raw_attempt(accepted=True)
    candidate_raw = copy.deepcopy(oracle_raw)
    if mutation == "temperature":
        candidate_raw.full_candidate.state.temperature_K += 1.0e-6
    elif mutation == "terminal_current":
        candidate_raw.full_candidate.electrical.source_current_A += 1.0e-6
    elif mutation == "joule_power":
        candidate_raw.full_candidate.electrical.cell_joule_power_W += 1.0e-6
        candidate_raw.full_candidate.electrical.joule_power_W += 1.0e-6
        candidate_raw.full_candidate.electrical.terminal_device_power_W += 1.0e-6
    elif mutation == "ledger":
        candidate_raw.full_candidate.ledgers.thermal.accounted_power_W += 1.0e-6
    elif mutation == "accepted_rejected":
        candidate_raw = correction._raw_attempt(
            accepted=False,
            present_paths=("full_step",),
            include_optional=False,
        )
    elif mutation == "nonlinear_method":
        candidate_raw.full_candidate.nonlinear.method = "alternate_newton"
    elif mutation == "converged":
        candidate_raw.full_candidate.nonlinear.converged = False
    elif mutation == "fallback":
        candidate_raw.second_half_candidate.nonlinear.method = (
            "fail_closed_fixed_point_fallback"
        )
    elif mutation == "success_to_failure":
        candidate_raw.error_class = "RuntimeError"
        candidate_raw.error_message = "unexpected synthetic failure"
    elif mutation == "nonfinite":
        candidate_raw.full_candidate.state.temperature_K[:] = np.nan
    elif mutation == "ledger_scale_group":
        pass
    elif mutation != "none":
        raise AssertionError(f"unknown interval mutation: {mutation}")
    candidate_profile = (
        "interval_minimal_rejected"
        if mutation == "accepted_rejected"
        else "interval_full_accepted"
    )
    candidate_record = _attempt_record(candidate_raw, profile_id=candidate_profile)
    oracle_record = _attempt_record(oracle_raw)
    if mutation == "ledger_scale_group":
        target = next(
            name
            for name, field in candidate_record["numeric"].items()
            if field["denominator_key"] == "ledger_power_terms"
        )
        candidate_record["numeric"][target]["scale_group"] = "forged:ledger"
        oracle_record["numeric"][target]["scale_group"] = "forged:ledger"
    return candidate_record, oracle_record


def _flux_fixture_records(mutation: str) -> tuple[dict[str, Any], dict[str, Any]]:
    oracle_raw = correction._raw_attempt(accepted=True)
    _set_nonzero_lateral(oracle_raw)
    candidate_raw = copy.deepcopy(oracle_raw)
    lateral = candidate_raw.full_candidate.lateral_flux
    if mutation == "none":
        pass
    elif mutation == "x_flux_sign":
        lateral.x_face_flux_W[0] *= -1.0
    elif mutation == "y_flux_sign":
        lateral.y_face_flux_W[0] *= -1.0
    elif mutation == "global_leak":
        lateral.net_cell_outflow_W[0] += 1.0e-5
    elif mutation == "hard_gate":
        lateral.matrix_face_relative_mismatch = 1.0
        lateral.matrix_face_roundoff_ratio = 2.0
    elif mutation == "cancellation":
        context = v2.load_preregistered_contract_bundle().payload[
            "operator_contexts"
        ]["L1"]
        qx = float(np.max(np.abs(lateral.x_face_flux_W)))
        qy = float(np.max(np.abs(lateral.y_face_flux_W)))
        bound = (
            64.0
            * np.finfo(float).eps
            * 2.0
            * (context["n_x_faces"] * qx + context["n_y_faces"] * qy)
        )
        lateral.internal_pair_cancellation_W = 1.01 * bound
    elif mutation == "global_cancellation":
        context = v2.load_preregistered_contract_bundle().payload[
            "operator_contexts"
        ]["L1"]
        qx = float(np.max(np.abs(lateral.x_face_flux_W)))
        qy = float(np.max(np.abs(lateral.y_face_flux_W)))
        bound = (
            64.0
            * np.finfo(float).eps
            * 2.0
            * (context["n_x_faces"] * qx + context["n_y_faces"] * qy)
        )
        lateral.face_to_cell_global_residual_W = 1.01 * bound
    else:
        raise AssertionError(f"unknown flux mutation: {mutation}")
    return _attempt_record(candidate_raw), _attempt_record(oracle_raw)


def _progression_fixture_records(
    mutation: str,
    schema: dict[str, Any],
    contract: v2.LoadedContract,
) -> tuple[dict[str, Any], dict[str, Any]]:
    oracle_raw, oracle_attempts = correction._raw_progression(schema)
    if mutation == "progression_cancellation":
        for attempt in oracle_attempts:
            _set_nonzero_lateral(attempt)
    oracle_observation, oracle_errors = correction._extract_progression(
        oracle_raw, oracle_attempts, schema
    )
    assert not oracle_errors and oracle_observation is not None
    candidate_raw = copy.deepcopy(oracle_raw)
    candidate_attempts = copy.deepcopy(oracle_attempts)
    validation_errors: tuple[str, ...] = ()
    if mutation == "event_count":
        candidate_raw.event_records = candidate_raw.event_records[:1]
    elif mutation == "event_direction":
        candidate_raw.event_records[0]["direction"] = "downward"
    elif mutation == "event_order":
        candidate_raw.event_records = tuple(reversed(candidate_raw.event_records))
    elif mutation == "reversal_count":
        candidate_raw.reversal_records = candidate_raw.reversal_records[:1]
    elif mutation == "reversal_direction":
        candidate_raw.reversal_records[0]["direction"] = "cooling_to_heating"
    elif mutation == "reversal_order":
        candidate_raw.reversal_records = tuple(
            reversed(candidate_raw.reversal_records)
        )
    elif mutation == "missing":
        del candidate_raw.scalar_records[0]["time_s"]
    elif mutation == "extra":
        candidate_raw.scalar_records[0]["unregistered_power_W"] = 1.0
    elif mutation == "invalid_na":
        candidate_raw.event_records[0]["direction"] = "NA"
        oracle_raw.event_records[0]["direction"] = "NA"
        oracle_observation, oracle_errors = correction._extract_progression(
            oracle_raw, oracle_attempts, schema
        )
        assert not oracle_errors and oracle_observation is not None
    elif mutation == "validation_error":
        candidate_raw.protocol_result.diagnostics.accepted_steps = 3
        validation_errors = strict_v1._progression_validation_errors(
            candidate_raw, candidate_attempts, 4
        )
    elif mutation == "topology_missing":
        del candidate_raw.event_records[0]["direction"]
    elif mutation == "topology_extra":
        candidate_raw.event_records[0]["unregistered_topology"] = "unexpected"
    elif mutation == "progression_cancellation":
        context = contract.payload["operator_contexts"]["L1"]
        qx = 2.0e-6
        qy = 5.0e-7
        bound = (
            64.0
            * np.finfo(float).eps
            * 2.0
            * (context["n_x_faces"] * qx + context["n_y_faces"] * qy)
        )
        candidate_raw.scalar_records[0][
            "lateral_face_to_cell_global_residual_W"
        ] = 1.01 * bound
    elif mutation != "none":
        raise AssertionError(f"unknown progression mutation: {mutation}")
    candidate_record, extraction_errors = _progression_record(
        candidate_raw,
        candidate_attempts,
        schema,
        validation_errors=validation_errors,
        fallback_observation=oracle_observation,
    )
    if extraction_errors:
        assert mutation in {"topology_missing", "topology_extra"}
    oracle_record = _record(
        oracle_observation,
        plan_index=28,
        sample_id="EQ-PROGRESSION-L1-legal_critical",
        family="progression",
        profile_id="progression_full",
        maximum_accepted_intervals=4,
    )
    return candidate_record, oracle_record


def _progression_na_fixture_records(
    schema: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, attempts = correction._raw_progression(
        schema, event_directions=(), reversal_directions=()
    )
    record, errors = _progression_record(
        raw,
        attempts,
        schema,
        profile_id="progression_NA_no_event_or_reversal",
    )
    assert not errors
    return record, copy.deepcopy(record)


def _failure_fixture_records(mutation: str) -> tuple[dict[str, Any], dict[str, Any]]:
    oracle_raw = _failure_raw()
    if mutation == "failure_type":
        candidate_raw = _failure_raw(error_class="ValueError")
    elif mutation == "failure_location":
        candidate_raw = _failure_raw(message_path="first_half_step")
    elif mutation == "failure_to_success":
        candidate_raw = _failure_raw(error_class=None)
    else:
        raise AssertionError(f"unknown failure mutation: {mutation}")
    return _failure_record(candidate_raw), _failure_record(oracle_raw)


def _seal_comparison(
    fixture_id: str,
    candidate: dict[str, Any],
    oracle: dict[str, Any],
    contract: v2.LoadedContract,
) -> dict[str, Any]:
    comparison = v2.compare_record_pair(candidate, oracle, contract)
    outcomes = [
        {"plan_index": index, "row_pass": True}
        for index in range(57)
    ]
    return v2.seal_synthetic_fixture(
        fixture_id=fixture_id,
        comparison=comparison,
        synthetic_plan_outcomes=(
            outcomes if comparison.get("failure_event") is None else None
        ),
    )


def _infra_comparison(event: v2.TerminalEvent) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "record_status": "invalid_infrastructure",
        "row_pass": False,
        "failure_event": event.value,
        "issues": [],
        "votes": [],
        "candidate_record_sha256": None,
        "oracle_record_sha256": None,
    }
    payload["comparison_sha256"] = v2.canonical_sha256(payload)
    return payload


def _run_infra_fixture(
    mutation: str, tmp_path: Path, contract: v2.LoadedContract
) -> dict[str, Any]:
    try:
        if mutation == "contract_hash":
            preregistration = json.loads(
                v2.DEFAULT_PREREGISTRATION_PATH.read_text(encoding="utf-8")
            )
            preregistration["config_sha256"] = "0" * 64
            path = tmp_path / "preregistration.json"
            path.write_text(
                json.dumps(preregistration, sort_keys=True), encoding="utf-8"
            )
            v2.load_preregistered_contract_bundle(path)
        elif mutation == "manifest_missing":
            v2.load_field_manifest(
                tmp_path / "absent.csv",
                expected_sha256=MANIFEST_SHA256,
                expected_rows=638,
            )
        elif mutation == "manifest_hash":
            v2.load_field_manifest(
                MANIFEST_PATH,
                expected_sha256="0" * 64,
                expected_rows=638,
            )
        elif mutation == "manifest_parse":
            path = tmp_path / "parse.csv"
            path.write_text("wrong,header\n1,2\n", encoding="utf-8")
            v2.load_field_manifest(
                path,
                expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                expected_rows=638,
            )
        elif mutation in {
            "manifest_duplicate",
            "manifest_row_count",
            "manifest_unknown_category",
            "manifest_unknown_cardinality",
            "manifest_invalid_required_when",
        }:
            rows = copy.deepcopy(_manifest_rows())
            if mutation == "manifest_duplicate":
                rows[-1] = copy.deepcopy(rows[0])
            elif mutation == "manifest_row_count":
                rows.pop()
            elif mutation == "manifest_unknown_category":
                rows[0]["category"] = "unknown_category"
            elif mutation == "manifest_unknown_cardinality":
                rows[0]["static_cardinality_rule"] = "unknown_rule"
            else:
                rows[0]["required_when"] = "scenario_in:not_a_profile"
            path = tmp_path / f"{mutation}.csv"
            observed_sha = _write_manifest(path, rows)
            v2.load_field_manifest(
                path,
                expected_sha256=observed_sha,
                expected_rows=638,
            )
        elif mutation == "environment_mismatch":
            observed = copy.deepcopy(contract.payload["environment_lock"])
            observed["logical_processors"] = 999
            v2.validate_environment(contract, observed)
        elif mutation == "canonical_serialization":
            v2.canonical_sha256(object())
        else:
            raise AssertionError(f"unknown infra mutation: {mutation}")
    except v2.ContractInfrastructureError as exc:
        return v2.seal_synthetic_fixture(
            fixture_id=f"SF-INFRA-{mutation}",
            comparison=_infra_comparison(exc.event),
        )
    raise AssertionError(f"infra fixture did not fail closed: {mutation}")


def _run_case(
    case: dict[str, str],
    *,
    contract: v2.LoadedContract,
    schema: dict[str, Any],
    tmp_path: Path,
) -> dict[str, Any]:
    builder = case["builder"]
    mutation = case["mutation"]
    if builder == "infra":
        fixture = _run_infra_fixture(mutation, tmp_path, contract)
        fixture["fixture_id"] = case["fixture_id"]
        fixture.pop("fixture_sha256")
        fixture["fixture_sha256"] = v2.canonical_sha256(fixture)
        return fixture
    if builder == "interval":
        candidate, oracle = _interval_fixture_records(mutation)
    elif builder == "interval_flux":
        candidate, oracle = _flux_fixture_records(mutation)
    elif builder == "progression":
        candidate, oracle = _progression_fixture_records(
            mutation, schema, contract
        )
    elif builder == "progression_na":
        candidate, oracle = _progression_na_fixture_records(schema)
    elif builder == "failure":
        candidate, oracle = _failure_fixture_records(mutation)
    elif builder == "terminal":
        candidate, oracle = _interval_fixture_records("none")
    else:
        raise AssertionError(f"unknown fixture builder: {builder}")
    return _seal_comparison(case["fixture_id"], candidate, oracle, contract)


SEALED_CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", SEALED_CASES, ids=lambda case: case["fixture_id"])
def test_sealed_contract_fixture_detects_expected_outcome(
    case: dict[str, str],
    contract: v2.LoadedContract,
    streaming_schema: dict[str, Any],
    tmp_path: Path,
) -> None:
    first = _run_case(
        case, contract=contract, schema=streaming_schema, tmp_path=tmp_path
    )
    second = _run_case(
        case, contract=contract, schema=streaming_schema, tmp_path=tmp_path
    )
    assert first == second
    assert first["terminal_state"] == case["expected_terminal"]
    assert first["failure_event"] == case.get("expected_event")
    if "expected_category" in case:
        assert case["expected_category"] in first["failed_categories"]
    if "expected_field_contains" in case:
        assert any(
            case["expected_field_contains"] in field
            for field in first["failed_fields"]
        )
    if "expected_issue_contains" in case:
        assert any(
            case["expected_issue_contains"] in issue
            for issue in first["issues"]
        )
    assert first["evidence_type"] == "synthetic_contract_evidence_nonvoting"
    assert first["audit_row_count"] == 0
    assert first["fixture_sha256"] == v2.canonical_sha256(
        {key: value for key, value in first.items() if key != "fixture_sha256"}
    )
    json.dumps(first, sort_keys=True, allow_nan=False)


def test_fixture_catalog_is_unique_frozen_and_outside_result_namespace(
    contract: v2.LoadedContract,
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture_ids = [case["fixture_id"] for case in payload["cases"]]
    assert len(fixture_ids) == len(set(fixture_ids))
    assert payload["audit_row_count"] == 0
    fixture_lock = contract.payload["sealed_synthetic_fixtures"]
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == fixture_lock[
        "definitions_sha256"
    ]
    assert "equivalence_v2_audit" not in fixture_lock["definitions_path"]


def test_synthetic_pass_requires_57_explicit_passing_row_outcomes(
    contract: v2.LoadedContract,
) -> None:
    candidate, oracle = _interval_fixture_records("none")
    comparison = v2.compare_record_pair(candidate, oracle, contract)
    incomplete = v2.seal_synthetic_fixture(
        fixture_id="SF-TERMINAL-INCOMPLETE",
        comparison=comparison,
        synthetic_plan_outcomes=[{"plan_index": 0, "row_pass": True}],
    )
    one_failure = v2.seal_synthetic_fixture(
        fixture_id="SF-TERMINAL-ONE-FAILURE",
        comparison=comparison,
        synthetic_plan_outcomes=[
            {"plan_index": index, "row_pass": index != 42}
            for index in range(57)
        ],
    )
    complete = v2.seal_synthetic_fixture(
        fixture_id="SF-TERMINAL-COMPLETE",
        comparison=comparison,
        synthetic_plan_outcomes=[
            {"plan_index": index, "row_pass": True}
            for index in range(57)
        ],
    )
    assert incomplete["terminal_state"] == "INVALID_INFRA"
    assert one_failure["terminal_state"] == "VALID_FAIL"
    assert complete["terminal_state"] == "PASS"
    assert complete["synthetic_terminal_truth_table_count"] == 57
    assert complete["synthetic_terminal_truth_table_complete_index_cover"] is True
    assert complete["synthetic_terminal_truth_table_all_rows_pass"] is True
    assert one_failure["synthetic_terminal_truth_table_complete_index_cover"] is True
    assert one_failure["synthetic_terminal_truth_table_all_rows_pass"] is False


@pytest.mark.parametrize(
    ("plan_index", "sample_id", "grid_id"),
    [
        (11, "EQ-INTERVAL-L1-legal_critical-base", "L1"),
        (17, "EQ-INTERVAL-L2-legal_critical-base", "L2"),
        (23, "EQ-INTERVAL-L4-legal_critical-base", "L4"),
    ],
)
def test_identical_analytic_flux_rules_apply_on_every_frozen_grid(
    contract: v2.LoadedContract,
    plan_index: int,
    sample_id: str,
    grid_id: str,
) -> None:
    context = contract.payload["operator_contexts"][grid_id]
    temperature_name = "full_step.state.temperature_K"
    for direction, conductance_key in (
        ("x", "g_x_max_W_K"),
        ("y", "g_y_max_W_K"),
    ):
        candidate, oracle = _flux_fixture_records("none")
        for record in (candidate, oracle):
            record["plan_index"] = plan_index
            record["sample_id"] = sample_id
            record["grid_id"] = grid_id
        temperature = np.asarray(
            candidate["numeric"][temperature_name]["value"], dtype=float
        )
        temperature.flat[0] += 1.0e-6
        candidate["numeric"][temperature_name]["value"] = temperature.tolist()
        flux_name = f"full_step.lateral.{direction}_face_flux_W"
        flux = np.asarray(candidate["numeric"][flux_name]["value"], dtype=float)
        flux.flat[0] += 1.0e-5
        candidate["numeric"][flux_name]["value"] = flux.tolist()
        delta_temperature = 1.0e-6
        temperature_scale = max(
            float(np.max(np.abs(candidate["numeric"][temperature_name]["value"]))),
            float(np.max(np.abs(oracle["numeric"][temperature_name]["value"]))),
        )
        q_scale = max(
            float(np.max(np.abs(candidate["numeric"][flux_name]["value"]))),
            float(np.max(np.abs(oracle["numeric"][flux_name]["value"]))),
        )
        conductance = context[conductance_key]
        expected_bound = 2.0 * conductance * delta_temperature + (
            64.0
            * np.finfo(float).eps
            * max(conductance * temperature_scale, q_scale)
        )
        comparison = v2.compare_record_pair(candidate, oracle, contract)
        vote = next(
            item for item in comparison["votes"] if item["field"] == flux_name
        )
        assert vote["bound"] == pytest.approx(expected_bound, rel=1.0e-15)
        assert vote["category"] == "C_physical_lateral_flux"
        assert vote["passed"] is False

    candidate, oracle = _flux_fixture_records("none")
    for record in (candidate, oracle):
        record["plan_index"] = plan_index
        record["sample_id"] = sample_id
        record["grid_id"] = grid_id

    net_name = "full_step.lateral.net_cell_outflow_W"
    candidate["numeric"][net_name]["value"][0] += 1.0e-5
    temperature_scale = max(
        float(np.max(np.abs(candidate["numeric"][temperature_name]["value"]))),
        float(np.max(np.abs(oracle["numeric"][temperature_name]["value"]))),
    )
    q_scale = max(
        float(np.max(np.abs(candidate["numeric"][net_name]["value"]))),
        float(np.max(np.abs(oracle["numeric"][net_name]["value"]))),
    )
    expected_net_bound = 64.0 * np.finfo(float).eps * max(
        context["L_infinity_norm_W_K"] * temperature_scale,
        q_scale,
    )
    comparison = v2.compare_record_pair(candidate, oracle, contract)
    net_vote = next(vote for vote in comparison["votes"] if vote["field"] == net_name)
    assert net_vote["bound"] == pytest.approx(expected_net_bound, rel=1.0e-15)
    assert net_vote["category"] == "C_physical_lateral_flux"
    assert net_vote["passed"] is False

    candidate, oracle = _flux_fixture_records("none")
    for record in (candidate, oracle):
        record["plan_index"] = plan_index
        record["sample_id"] = sample_id
        record["grid_id"] = grid_id
    cancellation_name = "full_step.lateral.face_to_cell_global_residual_W"
    qx = 2.0e-6
    qy = 5.0e-7
    expected_cancellation_bound = (
        64.0
        * np.finfo(float).eps
        * 2.0
        * (context["n_x_faces"] * qx + context["n_y_faces"] * qy)
    )
    candidate["numeric"][cancellation_name]["value"] = (
        1.01 * expected_cancellation_bound
    )
    comparison = v2.compare_record_pair(candidate, oracle, contract)
    cancellation_vote = next(
        vote for vote in comparison["votes"] if vote["field"] == cancellation_name
    )
    assert cancellation_vote["bound"] == pytest.approx(
        expected_cancellation_bound, rel=1.0e-15
    )
    assert cancellation_vote["category"] == "C_cancellation_roundoff"
    assert cancellation_vote["passed"] is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("family", []),
        ("profile_id", {}),
        ("grid_id", []),
        ("plan_index", True),
        ("protocol_voltage_scale_V", False),
    ],
)
def test_malformed_record_metadata_routes_to_valid_fail(
    contract: v2.LoadedContract, key: str, value: Any
) -> None:
    candidate, oracle = _interval_fixture_records("none")
    candidate[key] = value
    oracle[key] = copy.deepcopy(value)
    comparison = v2.compare_record_pair(candidate, oracle, contract)
    assert comparison["failure_event"] == "RECORD_VALIDATION_FAILURE"
    assert _comparison_terminal(comparison) is v2.TerminalState.VALID_FAIL


def test_identical_invalid_NA_is_semantically_rejected(
    contract: v2.LoadedContract, streaming_schema: dict[str, Any]
) -> None:
    candidate, oracle = _progression_fixture_records(
        "invalid_na", streaming_schema, contract
    )
    assert candidate["exact_votes"] == oracle["exact_votes"]
    comparison = v2.compare_record_pair(candidate, oracle, contract)
    assert comparison["record_status"] == "invalid_content"
    assert _comparison_terminal(comparison) is v2.TerminalState.VALID_FAIL
    assert any("invalid NA" in issue for issue in comparison["issues"])


def test_plan_binding_rejects_grid_or_voltage_scale_bypass(
    contract: v2.LoadedContract,
) -> None:
    candidate, oracle = _interval_fixture_records("none")
    for key, value in (("grid_id", "L4"), ("protocol_voltage_scale_V", 1.0e9)):
        altered_candidate = copy.deepcopy(candidate)
        altered_oracle = copy.deepcopy(oracle)
        altered_candidate[key] = value
        altered_oracle[key] = value
        comparison = v2.compare_record_pair(
            altered_candidate, altered_oracle, contract
        )
        assert comparison["record_status"] == "invalid_content"
        assert _comparison_terminal(comparison) is v2.TerminalState.VALID_FAIL


def test_comparator_has_no_forbidden_solver_or_runner_import() -> None:
    source = (ROOT / "src" / "pinnpcm" / "audit" / (
        "geophase_phase1_v2_equivalence_v2_comparator.py"
    )).read_text(encoding="utf-8")
    forbidden = (
        "pinnpcm.solvers",
        "controller_v2",
        "performance_equivalence",
        "runtime_readiness",
        "formal_runner",
    )
    assert not any(token in source for token in forbidden)
    assert not hasattr(v2, "load_contract_bundle")


def test_execution_counts_and_frozen_predecessors_remain_unchanged(
    contract: v2.LoadedContract,
) -> None:
    counts = contract.payload["execution_counts"]
    assert counts == {
        "equivalence_v2_execution_count": 0,
        "equivalence_v2_completed_rows": 0,
        "equivalence_v2_result_artifact_count": 0,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    assert contract.payload["authority_lock"]["strict_equivalence_v1"] == {
        "disposition": "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR",
        "completed_rows": 12,
        "expected_rows": 57,
        "immutable": True,
    }


def test_machine_preregistration_binds_superseding_contract_and_engine() -> None:
    path = (
        ROOT
        / "outputs"
        / "tables"
        / "geophase_phase1_v2_source_corrected_v3"
        / "equivalence_v2_contract_executability"
        / "preregistration.json"
    )
    preregistration = json.loads(path.read_text(encoding="utf-8"))
    for prefix in (
        "config",
        "contract_document",
        "comparison_engine",
        "field_manifest",
        "plan_manifest",
        "sealed_fixture_definitions",
        "original_v2_config",
        "original_v2_preregistration",
    ):
        target = ROOT / preregistration[f"{prefix}_path"]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == preregistration[
            f"{prefix}_sha256"
        ]
    assert preregistration["equivalence_v2_execution_count"] == 0
    assert preregistration["equivalence_v2_completed_rows"] == 0
    assert preregistration["formal_execution_count"] == 0
    assert preregistration["numerical_audit_execution_performed"] is False
    assert preregistration["held_out_execution_performed"] is False
    loaded = v2.load_preregistered_contract_bundle(path)
    assert len(loaded.templates) == 638
    assert len(loaded.plan_rows) == 57
