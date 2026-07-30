from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_metric_validity_coverage_correction as correction,
)
from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator as core
from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator_v3 as v3


SEALED_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "geophase_phase1_v2_equivalence_v2"
    / "sealed_comparator_closure_v3_cases.json"
)
SEALED_FIXTURE_SHA256 = hashlib.sha256(SEALED_FIXTURE_PATH.read_bytes()).hexdigest()
SEALED_FIXTURE_PAYLOAD = json.loads(SEALED_FIXTURE_PATH.read_text(encoding="utf-8"))
SEALED_CASES = tuple(SEALED_FIXTURE_PAYLOAD["cases"])


@pytest.fixture(scope="module")
def contract() -> core.LoadedContract:
    return v3.load_preregistered_contract_bundle()


@pytest.fixture(scope="module")
def streaming_schema() -> dict[str, Any]:
    return correction.derive_streaming_schema_from_source()


def _resize_step(step: Any, ny: int, nx: int) -> None:
    if step is None:
        return
    for name in ("temperature_K", "conductive_state", "branch_memory"):
        setattr(step.state, name, np.full((ny, nx), float(np.ravel(getattr(step.state, name))[0])))
    step.electrical.potential_V = np.full(
        (ny, nx), float(np.ravel(step.electrical.potential_V)[0])
    )
    step.electrical.cell_joule_power_W = np.full(
        (ny, nx), float(np.ravel(step.electrical.cell_joule_power_W)[0])
    )
    step.lateral_flux.net_cell_outflow_W = np.zeros((ny, nx), dtype=float)
    step.lateral_flux.x_face_flux_W = np.zeros((ny, nx - 1), dtype=float)
    step.lateral_flux.y_face_flux_W = np.zeros((ny - 1, nx), dtype=float)
    step.lateral_flux.boundary_face_flux_W = np.zeros(2 * ny + 2 * nx, dtype=float)


def _resize_attempt(raw: Any, ny: int, nx: int) -> None:
    for name in ("full_candidate", "first_half_candidate", "second_half_candidate"):
        _resize_step(getattr(raw, name), ny, nx)


def _resize_progression(raw: Any, attempts: Any, ny: int, nx: int) -> None:
    for step in raw.protocol_result.steps:
        _resize_step(step, ny, nx)
        _resize_step(step.accepted_first_half, ny, nx)
    for name in ("temperature_K", "conductive_state", "branch_memory"):
        setattr(raw.final_state, name, np.full((ny, nx), float(np.ravel(getattr(raw.final_state, name))[0])))
    for snapshot in raw.field_snapshots:
        for name in (
            "temperature_K",
            "conductive_state",
            "branch_memory",
            "potential_V",
            "cell_joule_power_W",
        ):
            setattr(snapshot, name, np.full((ny, nx), float(np.ravel(getattr(snapshot, name))[0])))
    for attempt in attempts:
        _resize_attempt(attempt, ny, nx)


def _input_sha(contract: core.LoadedContract, plan_index: int) -> str:
    return contract.plan_rows[plan_index]["plan_sha256"]


def _attempt_records(
    contract: core.LoadedContract,
    *,
    plan_index: int,
    declared_failure: str | None = None,
    failing_path: str | None = None,
    accepted: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = contract.payload["operator_contexts"][
        contract.plan_rows[plan_index]["grid"] or "L1"
    ]
    ny, nx = context["shape"]
    oracle_raw = correction._raw_attempt(
        accepted=accepted,
        failing_path=failing_path,
        error_class=("RuntimeError" if failing_path else None),
        error_message=(f"{failing_path} synthetic failure" if failing_path else None),
    )
    candidate_raw = copy.deepcopy(oracle_raw)
    for raw in (candidate_raw, oracle_raw):
        _resize_attempt(raw, ny, nx)
    candidate_observation, candidate_errors = correction._extract_attempt(
        candidate_raw,
        include_only_integrity_passed_steps=declared_failure is not None,
        declared_failure=declared_failure,
    )
    oracle_observation, oracle_errors = correction._extract_attempt(
        oracle_raw,
        include_only_integrity_passed_steps=declared_failure is not None,
        declared_failure=declared_failure,
    )
    assert candidate_observation is not None and not candidate_errors
    assert oracle_observation is not None and not oracle_errors
    input_sha = _input_sha(contract, plan_index)
    return (
        v3.observation_to_record(
            candidate_observation,
            plan_index=plan_index,
            input_sha256=input_sha,
            contract=contract,
        ),
        v3.observation_to_record(
            oracle_observation,
            plan_index=plan_index,
            input_sha256=input_sha,
            contract=contract,
        ),
    )


def _progression_records(
    contract: core.LoadedContract, schema: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_index = 28
    ny, nx = contract.payload["operator_contexts"]["L1"]["shape"]
    oracle_raw, oracle_attempts = correction._raw_progression(schema)
    candidate_raw = copy.deepcopy(oracle_raw)
    candidate_attempts = copy.deepcopy(oracle_attempts)
    _resize_progression(candidate_raw, candidate_attempts, ny, nx)
    _resize_progression(oracle_raw, oracle_attempts, ny, nx)
    candidate_observation, candidate_errors = correction._extract_progression(
        candidate_raw, candidate_attempts, schema
    )
    oracle_observation, oracle_errors = correction._extract_progression(
        oracle_raw, oracle_attempts, schema
    )
    assert candidate_observation is not None and not candidate_errors
    assert oracle_observation is not None and not oracle_errors
    input_sha = _input_sha(contract, plan_index)
    return (
        v3.observation_to_record(
            candidate_observation,
            plan_index=plan_index,
            input_sha256=input_sha,
            contract=contract,
        ),
        v3.observation_to_record(
            oracle_observation,
            plan_index=plan_index,
            input_sha256=input_sha,
            contract=contract,
        ),
    )


def _duplicate_dynamic_index(
    record: dict[str, Any], *, namespace: str, source: int = 0, target: int = 1
) -> None:
    """Create a second synthetic dynamic index without invoking a solver."""

    observation = record["observation"]
    source_prefix = f"streaming.{namespace}.{source}."
    target_prefix = f"streaming.{namespace}.{target}."
    copied = 0
    for bucket in ("numeric", "exact_votes", "telemetry"):
        values = observation[bucket]
        additions = {
            target_prefix + name[len(source_prefix) :]: copy.deepcopy(value)
            for name, value in tuple(values.items())
            if name.startswith(source_prefix)
        }
        values.update(additions)
        copied += len(additions)
    assert copied > 0


def _mutate_terminal_outcomes(
    outcomes: list[dict[str, Any]], mutation: str
) -> None:
    if mutation == "none":
        return
    if mutation == "missing":
        outcomes.pop(12)
    elif mutation == "duplicate":
        outcomes[12] = copy.deepcopy(outcomes[11])
    elif mutation == "reordered":
        outcomes[11], outcomes[12] = outcomes[12], outcomes[11]
    elif mutation == "replaced":
        outcomes[12]["plan_identity"]["sample_id"] = outcomes[13]["plan_identity"][
            "sample_id"
        ]
        _rehash(outcomes[12])
    elif mutation == "out_of_range":
        outcomes[56]["plan_identity"]["plan_index"] = 57
        _rehash(outcomes[56])
    else:  # pragma: no cover - the fixture catalog is itself contract evidence.
        raise AssertionError(f"unknown terminal mutation: {mutation}")


@pytest.mark.parametrize("plan_index", [11, 17, 23])
def test_valid_l1_l2_l4_records_reach_unchanged_core_votes(
    contract: core.LoadedContract, plan_index: int
) -> None:
    candidate, oracle = _attempt_records(contract, plan_index=plan_index)
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is True
    assert result["core_comparison"]["row_pass"] is True
    assert result["votes"] == result["core_comparison"]["votes"]


@pytest.mark.parametrize(
    ("plan_index", "field_name"),
    [
        (11, "full_step.state.temperature_K"),
        (11, "full_step.lateral.x_face_flux_W"),
        (11, "full_step.lateral.y_face_flux_W"),
        (17, "full_step.state.temperature_K"),
        (17, "full_step.lateral.x_face_flux_W"),
        (17, "full_step.lateral.y_face_flux_W"),
        (23, "full_step.state.temperature_K"),
        (23, "full_step.lateral.x_face_flux_W"),
        (23, "full_step.lateral.y_face_flux_W"),
    ],
)
def test_common_mode_wrong_grid_shapes_are_rejected(
    contract: core.LoadedContract, plan_index: int, field_name: str
) -> None:
    candidate, oracle = _attempt_records(contract, plan_index=plan_index)
    for record in (candidate, oracle):
        record["observation"]["numeric"][field_name]["value"] = [[0.0]]
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any("numeric topology differs" in issue for issue in result["issues"])


def test_common_mode_wrong_boundary_face_cardinality_is_rejected(
    contract: core.LoadedContract,
) -> None:
    candidate, oracle = _attempt_records(contract, plan_index=11)
    name = "full_step.lateral.boundary_face_flux_W"
    for record in (candidate, oracle):
        record["observation"]["numeric"][name]["value"] = [0.0]
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any("numeric topology differs" in issue for issue in result["issues"])


@pytest.mark.parametrize(
    "field_name",
    [
        "history.0.accepted.state.time_s",
        "streaming.scalar.0.time_s",
        "streaming.snapshot.0.time_s",
    ],
)
def test_common_mode_dynamic_index_field_deletion_is_rejected(
    contract: core.LoadedContract,
    streaming_schema: dict[str, Any],
    field_name: str,
) -> None:
    candidate, oracle = _progression_records(contract, streaming_schema)
    baseline = v3.compare_record_pair(candidate, oracle, contract)
    assert baseline["row_pass"] is True
    for record in (candidate, oracle):
        del record["observation"]["numeric"][field_name]
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any(
        "dynamic template index cover differs" in issue
        or "anchor domain is absent" in issue
        for issue in result["issues"]
    )


def test_common_mode_wrong_input_hash_is_rejected(contract: core.LoadedContract) -> None:
    candidate, oracle = _attempt_records(contract, plan_index=11)
    for record in (candidate, oracle):
        record["plan_identity"]["input_sha256"] = "0" * 64
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any("input identity differs" in issue for issue in result["issues"])


@pytest.mark.parametrize("key", ["sample_id", "family"])
def test_common_mode_row_relabel_is_rejected(
    contract: core.LoadedContract, key: str
) -> None:
    candidate, oracle = _attempt_records(contract, plan_index=11)
    for record in (candidate, oracle):
        record["plan_identity"][key] = "forged"
        record["observation"][key] = "forged"
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any("identity differs" in issue for issue in result["issues"])


@pytest.mark.parametrize(
    "declared_failure",
    ["full_step:lateral_audit", "first_half_step:nonfinite"],
)
def test_common_mode_wrong_failure_type_or_location_is_rejected(
    contract: core.LoadedContract, declared_failure: str
) -> None:
    candidate, oracle = _attempt_records(
        contract,
        plan_index=36,
        declared_failure=declared_failure,
        failing_path=declared_failure.split(":", 1)[0],
        accepted=False,
    )
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any("failure" in issue for issue in result["issues"])


def test_success_failure_inversion_is_rejected(contract: core.LoadedContract) -> None:
    candidate, oracle = _attempt_records(contract, plan_index=11)
    for record in (candidate, oracle):
        record["failure_contract"]["extracted_failure_classification"] = (
            "RuntimeError:forged failure"
        )
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any("relabelled as a failure" in issue for issue in result["issues"])


def test_progression_failure_relabelling_cannot_override_production_exact_vote(
    contract: core.LoadedContract, streaming_schema: dict[str, Any]
) -> None:
    candidate, oracle = _progression_records(contract, streaming_schema)
    for record in (candidate, oracle):
        record["failure_contract"]["extracted_failure_classification"] = (
            "RuntimeError:forged progression failure"
        )
    result = v3.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert any(
        "differs from nested production exact vote" in issue
        for issue in result["issues"]
    )


def _terminal_outcome(contract: core.LoadedContract, index: int) -> dict[str, Any]:
    row = contract.plan_rows[index]
    payload = {
        "schema_version": v3.COMPARISON_SCHEMA_VERSION,
        "record_status": "auditable",
        "row_pass": True,
        "failure_event": None,
        "issues": [],
        "votes": [],
        "plan_identity": {
            "plan_index": index,
            "sample_id": row["sample_id"],
            "family": row["family"],
            "grid_id": row["grid"] or "L1",
            "input_sha256": row["plan_sha256"],
        },
        "candidate_record_sha256": str(index).zfill(64),
        "oracle_record_sha256": str(index + 1).zfill(64),
        "core_comparison": {"synthetic": True},
    }
    payload["comparison_sha256"] = core.canonical_sha256(payload)
    return payload


def _rehash(outcome: dict[str, Any]) -> None:
    outcome.pop("comparison_sha256", None)
    outcome["comparison_sha256"] = core.canonical_sha256(outcome)


def test_sealed_fixture_catalog_is_content_addressed_and_unique(
    contract: v3.V3LoadedContract,
) -> None:
    fixture_lock = contract.closure_payload["sealed_synthetic_fixtures"]
    assert SEALED_FIXTURE_PAYLOAD["schema_version"].endswith("_v3")
    assert SEALED_FIXTURE_PAYLOAD["evidence_type"] == (
        "synthetic_contract_evidence_nonvoting"
    )
    assert SEALED_FIXTURE_PAYLOAD["audit_row_count"] == 0
    assert fixture_lock["definitions_sha256"] == SEALED_FIXTURE_SHA256
    assert Path(fixture_lock["definitions_path"]).as_posix() == (
        "tests/fixtures/geophase_phase1_v2_equivalence_v2/"
        "sealed_comparator_closure_v3_cases.json"
    )
    fixture_ids = [case["fixture_id"] for case in SEALED_CASES]
    assert len(fixture_ids) == len(set(fixture_ids))


@pytest.mark.parametrize(
    "case", SEALED_CASES, ids=[case["fixture_id"] for case in SEALED_CASES]
)
def test_each_declared_sealed_fixture_reaches_the_v3_contract_gate(
    contract: v3.V3LoadedContract,
    streaming_schema: dict[str, Any],
    case: dict[str, Any],
) -> None:
    """Consume every declared fixture; none is merely listed as future coverage."""

    group = case["group"]
    if group == "terminal":
        outcomes = [_terminal_outcome(contract, index) for index in range(57)]
        mutation = case["mutation"]
        _mutate_terminal_outcomes(outcomes, mutation)
        expected = (
            core.TerminalState.PASS
            if mutation == "none"
            else core.TerminalState.INVALID_INFRA
        )
        assert v3.finalise_plan_terminal(outcomes, contract) is expected
        return

    if group.startswith("dynamic"):
        candidate, oracle = _progression_records(contract, streaming_schema)
        if group == "dynamic_scalar_nonanchor":
            for record in (candidate, oracle):
                _duplicate_dynamic_index(record, namespace="scalar")
        elif group == "dynamic_snapshot_nonanchor":
            for record in (candidate, oracle):
                _duplicate_dynamic_index(record, namespace="snapshot")
        elif group != "dynamic":  # pragma: no cover - catalog schema guard.
            raise AssertionError(f"unknown dynamic fixture group: {group}")
        for record in (candidate, oracle):
            del record["observation"]["numeric"][case["field"]]
        result = v3.compare_record_pair(candidate, oracle, contract)
        assert result["row_pass"] is False
        assert any(
            "dynamic template index cover differs" in issue
            or "anchor domain is absent" in issue
            for issue in result["issues"]
        )
        return

    if group == "shape":
        candidate, oracle = _attempt_records(
            contract, plan_index=int(case["plan_index"])
        )
        for record in (candidate, oracle):
            record["observation"]["numeric"][case["field"]]["value"] = [[0.0]]
        result = v3.compare_record_pair(candidate, oracle, contract)
        assert result["row_pass"] is False
        assert any("numeric topology differs" in issue for issue in result["issues"])
        return

    if group == "identity":
        candidate, oracle = _attempt_records(contract, plan_index=11)
        mutation = case["mutation"]
        if mutation == "input_sha256":
            for record in (candidate, oracle):
                record["plan_identity"]["input_sha256"] = "0" * 64
        elif mutation in {"sample_id", "family"}:
            for record in (candidate, oracle):
                record["plan_identity"][mutation] = "forged"
                record["observation"][mutation] = "forged"
        elif mutation == "success_failure_inversion":
            for record in (candidate, oracle):
                record["failure_contract"]["extracted_failure_classification"] = (
                    "RuntimeError:forged failure"
                )
        else:  # pragma: no cover - catalog schema guard.
            raise AssertionError(f"unknown identity mutation: {mutation}")
        assert v3.compare_record_pair(candidate, oracle, contract)["row_pass"] is False
        return

    if group == "failure":
        declared_failure = (
            "full_step:lateral_audit"
            if case["mutation"] == "failure_type"
            else "first_half_step:nonfinite"
        )
        candidate, oracle = _attempt_records(
            contract,
            plan_index=36,
            declared_failure=declared_failure,
            failing_path=declared_failure.split(":", 1)[0],
            accepted=False,
        )
        result = v3.compare_record_pair(candidate, oracle, contract)
        assert result["row_pass"] is False
        assert any("failure" in issue for issue in result["issues"])
        return

    raise AssertionError(f"unknown sealed fixture group: {group}")


def test_pass_requires_exact_content_addressed_zero_through_56(
    contract: core.LoadedContract,
) -> None:
    outcomes = [_terminal_outcome(contract, index) for index in range(57)]
    assert v3.finalise_plan_terminal(outcomes, contract) is core.TerminalState.PASS


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered", "replaced", "out_of_range"])
def test_plan_terminal_rejects_nonexact_cover(
    contract: core.LoadedContract, mutation: str
) -> None:
    outcomes = [_terminal_outcome(contract, index) for index in range(57)]
    if mutation == "missing":
        outcomes.pop(12)
    elif mutation == "duplicate":
        outcomes[12] = copy.deepcopy(outcomes[11])
    elif mutation == "reordered":
        outcomes[11], outcomes[12] = outcomes[12], outcomes[11]
    elif mutation == "replaced":
        outcomes[12]["plan_identity"]["sample_id"] = outcomes[13]["plan_identity"][
            "sample_id"
        ]
        _rehash(outcomes[12])
    elif mutation == "out_of_range":
        outcomes[56]["plan_identity"]["plan_index"] = 57
        _rehash(outcomes[56])
    assert (
        v3.finalise_plan_terminal(outcomes, contract)
        is core.TerminalState.INVALID_INFRA
    )


def test_terminal_rejects_tampered_comparison_hash(contract: core.LoadedContract) -> None:
    outcomes = [_terminal_outcome(contract, index) for index in range(57)]
    outcomes[42]["row_pass"] = False
    assert (
        v3.finalise_plan_terminal(outcomes, contract)
        is core.TerminalState.INVALID_INFRA
    )


@pytest.mark.parametrize("hash_key", ["candidate_record_sha256", "oracle_record_sha256"])
def test_terminal_rejects_non_sha_record_identity(
    contract: core.LoadedContract, hash_key: str
) -> None:
    outcomes = [_terminal_outcome(contract, index) for index in range(57)]
    outcomes[23][hash_key] = "not-a-sha256"
    _rehash(outcomes[23])
    assert (
        v3.finalise_plan_terminal(outcomes, contract)
        is core.TerminalState.INVALID_INFRA
    )


def test_terminal_accepts_exact_fail_fast_prefix_and_rejects_post_failure_outcome(
    contract: core.LoadedContract,
) -> None:
    prefix = [_terminal_outcome(contract, index) for index in range(12)]
    prefix[-1]["row_pass"] = False
    prefix[-1]["failure_event"] = core.TerminalEvent.FIELD_VOTE_FAILURE.value
    _rehash(prefix[-1])
    assert v3.finalise_plan_terminal(prefix, contract) is core.TerminalState.VALID_FAIL

    prefix.append(_terminal_outcome(contract, 12))
    assert (
        v3.finalise_plan_terminal(prefix, contract)
        is core.TerminalState.INVALID_INFRA
    )
