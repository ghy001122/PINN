from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_equivalence_v2_one_shot_execution.yaml"
OUTPUT_ROOT = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_v2_audit"
)
AUTHORIZATION_PATH = OUTPUT_ROOT / "execution_authorization.json"
REGISTRY_PATH = OUTPUT_ROOT / "execution_registry.json"
PREREGISTRATION_PATH = OUTPUT_ROOT / "preregistration.json"
FIELD_MANIFEST_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "equivalence_metric_validity"
    / "coverage_correction"
    / "mechanical_field_contract.csv"
)
PLAN_MANIFEST_PATH = FIELD_MANIFEST_PATH.with_name("mechanical_plan_contract.csv")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _yaml() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_execution_contract_freezes_closure_and_historical_v1() -> None:
    config = _yaml()
    authority = config["authority_lock"]
    closure = config["frozen_closure_v3"]

    assert authority["base_main"] == "85d5c7ba5b0da8c3919e2ccc5a844ded4dcbec68"
    assert authority["closure_v3_merge_commit"] == authority["base_main"]
    assert authority["strict_equivalence_v1"] == {
        "disposition": "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR",
        "completed_rows": 12,
        "expected_rows": 57,
        "immutable": True,
    }
    expected = {
        "config": "931d69d23cd446c451288dc0f3c9f639e214721da7c6e50bc2b5aca01e852a1b",
        "report": "352a7a9fbf48c884d48e14ee5f401f3cfec39e6e2980b07748fa4ed44d37bf97",
        "preregistration": "cc6de62b4eebae48cbaebbf55ef4bbd8b022d60cc75276afba9ce44470d7d42a",
        "comparator": "e902e6f06b9213e1ce4278b003de588358fe03fe193391fafebc26aeda095851",
        "field_manifest": "670dbb5acee9bc0bc4796e9c54d9de39c5a4016cc7344f1eff5f53291fb74f07",
        "plan_manifest": "cc65de070be1efd9951d609a96e4e1311bbcbf178f9ff478d0a0a2cd3d149c0e",
    }
    for key, expected_sha in expected.items():
        entry = closure[key]
        assert _sha256(ROOT / entry["path"]) == entry["sha256"] == expected_sha

    assert _sha256(PREREGISTRATION_PATH) == (
        "3a7f8e506a21eeb088cef9896bcb1dd015bd125e5b01c37ded1c672262e22a08"
    )


def test_execution_authorization_binds_config_manifests_and_attempt_limit() -> None:
    config = _yaml()
    authorization = _json(AUTHORIZATION_PATH)

    assert authorization["execution_config_sha256"] == _sha256(CONFIG_PATH)
    assert authorization["contract_bundle_sha256"] == (
        "cc6de62b4eebae48cbaebbf55ef4bbd8b022d60cc75276afba9ce44470d7d42a"
    )
    assert authorization["field_manifest_sha256"] == _sha256(FIELD_MANIFEST_PATH)
    assert authorization["plan_manifest_sha256"] == _sha256(PLAN_MANIFEST_PATH)
    assert authorization["expected_plan_indices_sha256"] == (
        "b8407db67660b6b982b3f3458c694bc62f2bdeade733d25279acdcf476a7e1b4"
    )
    assert authorization["execution_attempt_limit"] == 1
    assert authorization["automatic_retry"] is False
    assert authorization["manual_retry"] is False
    assert authorization["formal_execution_count"] == 0
    assert config["execution_control"]["counter_transition"] == (
        "atomic_0_to_1_immediately_before_plan_index_0_schedule"
    )


def test_frozen_plan_is_exactly_ordered_and_partitioned() -> None:
    with PLAN_MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indices = [int(row["plan_index"]) for row in rows]
    assert indices == list(range(57))
    assert len({row["sample_id"] for row in rows}) == 57

    config = _yaml()
    execution = config["execution_control"]
    assert execution["exact_plan_order"] == {
        "inclusive_start": 0,
        "inclusive_end": 56,
        "sequence": "ascending_without_skip_reorder_or_retry",
    }
    assert execution["metric_development_partition"] == {
        "inclusive_start": 0,
        "inclusive_end": 11,
        "count": 12,
    }
    assert execution["held_out_partition"] == {
        "inclusive_start": 12,
        "inclusive_end": 56,
        "count": 45,
    }
    development = set(range(0, 12))
    held_out = set(range(12, 57))
    assert development.isdisjoint(held_out)
    assert development | held_out == set(indices)


def test_one_shot_contract_cannot_call_old_v1_audit_comparator() -> None:
    config = _yaml()
    identity = config["execution_identity"]
    assert _sha256(ROOT / identity["control_plane_source"]) == identity["source_sha256"]
    assert _sha256(ROOT / identity["production_wiring_source"]) == identity[
        "production_wiring_sha256"
    ]
    cli_path = ROOT / identity["cli"]
    if cli_path.exists():
        assert _sha256(cli_path) == identity["cli_sha256"]
    else:
        assert identity["cli_sha256"] == "0" * 64
    assert identity["frozen_comparison_entrypoints"] == [
        "load_preregistered_contract_bundle",
        "observation_to_record",
        "compare_record_pair",
        "finalise_plan_terminal",
    ]
    assert identity["forbidden_entrypoints"] == [
        "run_equivalence_audit",
        "compare_observations",
        "strict_equivalence_v1_comparator",
    ]
    assert config["comparison_rules"]["field_manifest_bypass"] == "forbidden"
    assert config["comparison_rules"]["comparator_bypass"] == "forbidden"


def test_production_adapter_and_cli_have_no_forbidden_v1_call_expression() -> None:
    forbidden = {
        "run_equivalence_audit",
        "compare_observations",
        "run_electrical_pair",
    }
    paths = (
        ROOT
        / "src"
        / "pinnpcm"
        / "audit"
        / "geophase_phase1_v2_equivalence_v2_production_adapter.py",
        ROOT / "scripts" / "run_geophase_phase1_v2_equivalence_v2_one_shot.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        called: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if isinstance(function, ast.Name):
                called.add(function.id)
            elif isinstance(function, ast.Attribute):
                called.add(function.attr)
        assert forbidden.isdisjoint(called), f"forbidden v1 call in {path.name}"


def test_initial_or_activated_registry_remains_single_attempt_and_formal_zero() -> None:
    registry = _json(REGISTRY_PATH)
    required = {
        "schema_version",
        "task_id",
        "attempt_id",
        "state",
        "execution_attempt_limit",
        "equivalence_v2_execution_count",
        "formal_execution_count",
        "automatic_retry",
        "manual_retry",
        "expected_plan_count",
        "expected_plan_indices_sha256",
        "plan_manifest_sha256",
        "contract_bundle_sha256",
        "runner_source_sha256",
        "remote_anchor_commit",
        "started_at_utc",
        "owner_pid",
        "completed_rows",
        "terminal_state",
        "terminal_event",
        "final_journal_sha256",
        "registry_sha256",
    }
    assert set(registry) == required
    assert registry["execution_attempt_limit"] == 1
    assert registry["automatic_retry"] is False
    assert registry["manual_retry"] is False
    assert registry["expected_plan_count"] == 57
    assert registry["expected_plan_indices_sha256"] == (
        "b8407db67660b6b982b3f3458c694bc62f2bdeade733d25279acdcf476a7e1b4"
    )
    assert registry["formal_execution_count"] == 0
    assert registry["equivalence_v2_execution_count"] in {0, 1}
    if registry["equivalence_v2_execution_count"] == 0:
        assert registry["state"] == "AUTHORIZED_NOT_STARTED"
        assert registry["completed_rows"] == 0
        assert registry["terminal_state"] is None
    else:
        assert registry["state"] in {"RUNNING", "TERMINAL"}
        assert 0 <= registry["completed_rows"] <= 57


def test_claim_and_result_boundaries_remain_fail_closed() -> None:
    config = _yaml()
    counts = config["execution_counts"]
    claims = config["claim_boundary"]
    assert counts == {
        "equivalence_v2_execution_count": 0,
        "equivalence_v2_completed_rows": 0,
        "equivalence_v2_result_artifact_count": 0,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    assert claims["strict_equivalence_v1"] == "NO_GO_12_of_57_unchanged"
    assert claims["equivalence_v2"] == "authorized_but_not_started"
    assert claims["Phase1_S2_science"] == "forbidden"
    assert claims["PINN_claims"] == "forbidden"
