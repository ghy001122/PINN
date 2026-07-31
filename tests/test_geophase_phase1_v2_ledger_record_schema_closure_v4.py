from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pytest

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator as core
from pinnpcm.audit import geophase_phase1_v2_equivalence_v3_comparator as comparator
from pinnpcm.audit import geophase_phase1_v2_ledger_record_schema_v4 as schema


REQUIRED_MANIFEST_COLUMNS = {
    "family",
    "profile",
    "field_pattern",
    "producer_balance_name",
    "normalized_scale_group_id",
    "required_when",
    "source_constructor",
    "source_extractor",
}
LEDGER_PREFIX_BY_PROFILE = {
    "full": "full_step.ledgers.",
    "first_half": "first_half_step.ledgers.",
    "second_half": "second_half_step.ledgers.",
    "aggregate": "aggregate_ledgers.",
}


@pytest.fixture(scope="module")
def contract() -> comparator.LoadedContract:
    return comparator.load_preregistered_contract_bundle()


@pytest.fixture(scope="module")
def manifest_rows(
    contract: comparator.LoadedContract,
) -> tuple[schema.LedgerManifestEntry, ...]:
    return tuple(schema.build_ledger_group_manifest(contract.predecessor))


def _plan_index_for_scenario(
    contract: comparator.LoadedContract, scenario: Any, grid_id: str
) -> int:
    for index, row in contract.predecessor.plan_rows.items():
        if row["family"] != scenario.family:
            continue
        if scenario.family in {"interval", "progression"} and row["grid"] != grid_id:
            continue
        if scenario.family == "failure":
            path = scenario.profile.removeprefix("failure_at_")
            if row["candidate_paths"] != path or row["failure_class"] != "nonfinite":
                continue
        return index
    raise AssertionError(
        f"no frozen row for {scenario.family}:{scenario.profile}:{grid_id}"
    )


def _record_for_scenario(
    contract: comparator.LoadedContract, scenario: Any, grid_id: str
) -> dict[str, Any]:
    plan_index = _plan_index_for_scenario(contract, scenario, grid_id)
    input_sha = contract.predecessor.plan_rows[plan_index]["plan_sha256"]
    return comparator.observation_to_record(
        scenario.observation,
        plan_index=plan_index,
        input_sha256=input_sha,
        contract=contract,
    )


def _interval_pair(
    contract: comparator.LoadedContract, grid_id: str = "L1"
) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario = next(
        value
        for value in schema.build_production_real_scenarios(grid_id)
        if value.family == "interval"
    )
    record = _record_for_scenario(contract, scenario, grid_id)
    return copy.deepcopy(record), copy.deepcopy(record)


def _numeric(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return record["observation"]["numeric"]


def _ledger_fields(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: value
        for name, value in _numeric(record).items()
        if value.get("denominator_key") == "ledger_power_terms"
    }


def _fields_by_group(record: Mapping[str, Any]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = defaultdict(list)
    for name, value in _ledger_fields(record).items():
        output[str(value["scale_group_id"])].append(name)
    return dict(output)


def _state(result: Mapping[str, Any]) -> str:
    value = result["terminal_state"]
    return value.value if hasattr(value, "value") else str(value)


def _assert_rejected(
    contract: comparator.LoadedContract,
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    *,
    expected_state: str | None = None,
) -> Mapping[str, Any]:
    result = comparator.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is False
    assert result["issues"] or any(
        vote.get("passed") is False
        for vote in result.get("votes", ())
        if isinstance(vote, Mapping)
    )
    if expected_state is not None:
        assert _state(result) == expected_state
    return result


def test_manifest_is_mechanical_complete_unique_and_content_addressed(
    contract: comparator.LoadedContract,
    manifest_rows: tuple[schema.LedgerManifestEntry, ...],
) -> None:
    actual = [entry.as_row() for entry in manifest_rows]
    assert actual
    assert all(REQUIRED_MANIFEST_COLUMNS == set(row) for row in actual)

    source_templates = {
        (template.family, template.field_pattern)
        for template in contract.predecessor.templates.values()
        if template.value_kind == "numeric"
        and template.denominator_key == "ledger_power_terms"
    }
    identities = [(entry.family, entry.field_pattern) for entry in manifest_rows]
    assert Counter(identities) == Counter({identity: 1 for identity in source_templates})
    assert len(manifest_rows) == 252
    assert all(entry.producer_balance_name for entry in manifest_rows)
    assert all(entry.normalized_scale_group_id for entry in manifest_rows)
    assert all(
        entry.source_constructor.startswith("pinnpcm.physics.")
        for entry in manifest_rows
    )
    assert all(
        entry.source_extractor.startswith("pinnpcm.solvers.")
        and "observation" in entry.source_extractor
        for entry in manifest_rows
    )

    manifest_path = Path(contract.ledger_group_manifest_path)
    assert manifest_path.is_file()
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == (
        contract.ledger_group_manifest_sha256
    )
    loaded = schema.load_ledger_group_manifest(
        manifest_path, expected_sha256=contract.ledger_group_manifest_sha256
    )
    assert set(loaded.entries) == set(source_templates)


def test_production_scenarios_mechanically_consume_each_template(
    contract: comparator.LoadedContract,
    manifest_rows: tuple[schema.LedgerManifestEntry, ...],
) -> None:
    observed: set[tuple[str, str]] = set()
    for scenario in schema.build_production_real_scenarios("L1"):
        for name, field in scenario.observation.numeric.items():
            if field.denominator_key == "ledger_power_terms":
                observed.add((scenario.family, core._normalise_field(name)))
    expected = {(entry.family, entry.field_pattern) for entry in manifest_rows}
    assert observed == expected


@pytest.mark.parametrize("grid_id", ["L1", "L2", "L4"])
@pytest.mark.parametrize("step_profile", tuple(LEDGER_PREFIX_BY_PROFILE))
def test_real_production_names_are_accepted_across_grid_and_step_profiles(
    contract: comparator.LoadedContract, grid_id: str, step_profile: str
) -> None:
    candidate, oracle = _interval_pair(contract, grid_id)
    result = comparator.compare_record_pair(candidate, oracle, contract)
    assert result["row_pass"] is True
    selected = {
        name: value
        for name, value in _ledger_fields(candidate).items()
        if name.startswith(LEDGER_PREFIX_BY_PROFILE[step_profile])
    }
    assert selected
    groups: dict[str, set[str]] = defaultdict(set)
    for value in selected.values():
        assert value["ledger_balance_name"]
        assert value["scale_group_id"]
        groups[str(value["scale_group_id"])].add(
            str(value["ledger_balance_name"])
        )
    assert all(len(names) == 1 for names in groups.values())


@pytest.mark.parametrize("mutation", ["old_simplified", "forged"])
def test_common_mode_wrong_producer_names_are_rejected(
    contract: comparator.LoadedContract, mutation: str
) -> None:
    candidate, oracle = _interval_pair(contract)
    for record in (candidate, oracle):
        for field in _ledger_fields(record).values():
            field["ledger_balance_name"] = (
                str(field["scale_group_id"]).rsplit(":", 1)[-1]
                if mutation == "old_simplified"
                else "forged_common_mode_balance"
            )
    _assert_rejected(
        contract, candidate, oracle, expected_state="INVALID_INFRA"
    )


def test_ledger_slot_exchange_is_rejected(
    contract: comparator.LoadedContract,
) -> None:
    candidate, oracle = _interval_pair(contract)
    for record in (candidate, oracle):
        groups = _fields_by_group(record)
        first, second = sorted(groups)[:2]
        fields = _ledger_fields(record)
        first_name = fields[groups[first][0]]["ledger_balance_name"]
        second_name = fields[groups[second][0]]["ledger_balance_name"]
        for field_name in groups[first]:
            fields[field_name]["ledger_balance_name"] = second_name
        for field_name in groups[second]:
            fields[field_name]["ledger_balance_name"] = first_name
    _assert_rejected(
        contract, candidate, oracle, expected_state="INVALID_INFRA"
    )


@pytest.mark.parametrize(
    "mutation", ["single_wrong", "split", "merge", "missing", "extra", "collision"]
)
def test_group_structure_controls_reject_common_mode_corruption(
    contract: comparator.LoadedContract, mutation: str
) -> None:
    candidate, oracle = _interval_pair(contract)
    for record in (candidate, oracle):
        groups = _fields_by_group(record)
        group_ids = sorted(groups)
        fields = _ledger_fields(record)
        if mutation == "single_wrong":
            fields[groups[group_ids[0]][0]]["scale_group_id"] = group_ids[1]
        elif mutation == "split":
            fields[groups[group_ids[0]][0]]["scale_group_id"] = (
                group_ids[0] + ":illegal_split"
            )
        elif mutation == "merge":
            for name in groups[group_ids[1]]:
                fields[name]["scale_group_id"] = group_ids[0]
        elif mutation == "missing":
            for name in groups[group_ids[0]]:
                del record["observation"]["numeric"][name]
        elif mutation == "extra":
            source_name = groups[group_ids[0]][0]
            record["observation"]["numeric"][
                source_name + ".unregistered_extra"
            ] = copy.deepcopy(fields[source_name])
        elif mutation == "collision":
            forged_name = fields[groups[group_ids[0]][0]]["ledger_balance_name"]
            for name in groups[group_ids[1]]:
                fields[name]["ledger_balance_name"] = forged_name
        else:  # pragma: no cover - parameter catalog is contract evidence.
            raise AssertionError(mutation)
    _assert_rejected(contract, candidate, oracle)


def test_field_membership_denominators_and_abc_rules_are_unchanged(
    contract: comparator.LoadedContract,
) -> None:
    scenario = next(
        value
        for value in schema.build_production_real_scenarios("L1")
        if value.family == "interval"
    )
    candidate = _record_for_scenario(contract, scenario, "L1")
    predecessor = schema.project_to_predecessor_record(candidate)
    current_numeric = candidate["observation"]["numeric"]
    old_numeric = predecessor["observation"]["numeric"]
    assert set(current_numeric) == set(old_numeric)
    assert {
        name: field["denominator_key"] for name, field in current_numeric.items()
    } == {name: field["denominator_key"] for name, field in old_numeric.items()}

    producer_members: dict[str, set[str]] = defaultdict(set)
    producer_denominators: dict[str, float] = {}
    for name, field in scenario.observation.numeric.items():
        if field.denominator_key != "ledger_power_terms":
            continue
        group = str(field.scale_group)
        producer_members[group].add(name)
        values = np.ravel(np.abs(np.asarray(field.value, dtype=float)))
        producer_denominators[group] = max(
            producer_denominators.get(group, 1.0e-30),
            float(np.max(values)) if values.size else 1.0e-30,
        )

    structural_members: dict[str, set[str]] = defaultdict(set)
    for name, field in _ledger_fields(candidate).items():
        structural_members[str(field["scale_group_id"])].add(name)
    assert sorted(map(sorted, producer_members.values())) == sorted(
        map(sorted, structural_members.values())
    )

    structural_denominators = schema.group_denominators(candidate)
    producer_by_members = {
        tuple(sorted(producer_members[group])): denominator
        for group, denominator in producer_denominators.items()
    }
    structural_by_members = {
        tuple(sorted(members)): structural_denominators[group]
        for group, members in structural_members.items()
    }
    assert structural_by_members.keys() == producer_by_members.keys()
    for members, denominator in producer_by_members.items():
        assert structural_by_members[members] == pytest.approx(
            denominator, rel=0.0, abs=0.0
        )
    assert contract.payload["unchanged_comparison_rules"]["A_primary_physical"][
        "threshold"
    ] == pytest.approx(1.0e-12)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_true_record_content_missing_or_extra_is_valid_fail(
    contract: comparator.LoadedContract, mutation: str
) -> None:
    candidate, oracle = _interval_pair(contract)
    for record in (candidate, oracle):
        fields = _ledger_fields(record)
        name = sorted(fields)[0]
        if mutation == "missing":
            del record["observation"]["numeric"][name]
        else:
            record["observation"]["numeric"][name + ".unregistered_extra"] = (
                copy.deepcopy(fields[name])
            )
    result = _assert_rejected(
        contract, candidate, oracle, expected_state="VALID_FAIL"
    )
    assert comparator.classify_terminal(
        stage=str(result["failure_stage"]),
        category=str(result["failure_category"]),
    ).value == result["terminal_state"]


def test_vote_failure_round_trips_through_structured_terminal_classifier(
    contract: comparator.LoadedContract,
) -> None:
    candidate, oracle = _interval_pair(contract)
    temperature = next(
        name
        for name in candidate["observation"]["numeric"]
        if name.endswith("state.temperature_K")
    )
    value = np.asarray(
        candidate["observation"]["numeric"][temperature]["value"], dtype=float
    )
    candidate["observation"]["numeric"][temperature]["value"] = (
        value + 1.0
    ).tolist()
    result = _assert_rejected(
        contract, candidate, oracle, expected_state="VALID_FAIL"
    )
    assert result["failure_category"] == "A_vote_failure"
    assert comparator.classify_terminal(
        stage=str(result["failure_stage"]),
        category=str(result["failure_category"]),
    ).value == result["terminal_state"]


@pytest.mark.parametrize(
    ("stage", "category", "expected"),
    [
        ("producer", "constructor_failure", "INVALID_INFRA"),
        ("schema_loading", "manifest_hash_failure", "INVALID_INFRA"),
        ("normalization", "ledger_group_failure", "INVALID_INFRA"),
        ("canonical_record_formation", "serialization_failure", "INVALID_INFRA"),
        ("record_comparison", "missing", "VALID_FAIL"),
        ("record_comparison", "extra", "VALID_FAIL"),
        ("record_comparison", "nonfinite", "VALID_FAIL"),
        ("record_comparison", "invalid_NA", "VALID_FAIL"),
        ("record_comparison", "A_vote_failure", "VALID_FAIL"),
        ("record_comparison", "B_vote_failure", "VALID_FAIL"),
        ("record_comparison", "C_vote_failure", "VALID_FAIL"),
        ("plan_complete", "all_rows_and_votes_pass", "PASS"),
    ],
)
def test_terminal_routing_uses_explicit_stage_not_message_text(
    stage: str, category: str, expected: str
) -> None:
    state = comparator.classify_terminal(stage=stage, category=category)
    assert state.value == expected


def test_atomic_content_addressed_record_publication(
    contract: comparator.LoadedContract, tmp_path: Path
) -> None:
    record, _oracle = _interval_pair(contract)
    path, digest = schema.publish_normalized_record(
        record, tmp_path, side="candidate"
    )
    assert path.is_file()
    assert path.stem == digest
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert schema.load_normalized_record(path, expected_sha256=digest) == record
    assert not list(tmp_path.rglob("*.tmp"))

    repeated = schema.publish_normalized_record(
        copy.deepcopy(record), tmp_path, side="candidate"
    )
    assert repeated == (path, digest)
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["runtime_input_sha256"] = "0" * 64
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(schema.LedgerSchemaError) as caught:
        schema.publish_normalized_record(record, tmp_path, side="candidate")
    assert caught.value.stage == "IO"


def test_stage_a_execution_counters_remain_frozen(
    contract: comparator.LoadedContract,
) -> None:
    assert contract.execution_counts["equivalence_v2_execution_count"] == 1
    assert contract.execution_counts["equivalence_v3_execution_count"] == 0
    assert contract.execution_counts["formal_execution_count"] == 0
    assert contract.execution_counts["formal_artifact_count"] == 0
