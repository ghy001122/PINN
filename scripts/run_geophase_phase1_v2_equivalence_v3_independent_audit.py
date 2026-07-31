"""CLI for the independently authorised, non-retryable equivalence-v3 audit.

``--validate-only`` is authority-only and dispatches no numerical row.
``--execute-once`` becomes reachable only after the runner, adapter, config,
registry and remote anchor are all frozen and the single-thread environment
matches the versioned contract.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from pinnpcm.audit import geophase_phase1_v2_equivalence_v3_comparator as _v3
from pinnpcm.audit.geophase_phase1_v2_equivalence_v3_one_shot import (
    OutputPaths,
    RowObservationPair,
    load_registry,
    plan_rows_from_contract,
    run_independent_audit,
)
from pinnpcm.audit.geophase_phase1_v2_equivalence_v3_production_adapter import (
    execute_production_row,
    open_frozen_production_context,
)


DEFAULT_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_equivalence_v3_independent_audit.yaml"
)
EXPECTED_TASK_ID = (
    "Q2_PHASE1_V2_EQUIVALENCE_V3_INDEPENDENT_AUDIT"
)
EXPECTED_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v3_independent_audit_v1"
READY_STATUS = "ready_frozen_remote_anchor_not_executed"
REQUIRED_THREAD_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} path is absent")
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_config(path: Path) -> Mapping[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError("equivalence-v3 execution config is unreadable") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("equivalence-v3 execution config is not a mapping")
    if payload.get("task_id") != EXPECTED_TASK_ID:
        raise RuntimeError("equivalence-v3 task identity changed")
    if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise RuntimeError("equivalence-v3 schema identity changed")
    return payload


def _git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git authority query failed: {' '.join(arguments)}")
    return result.stdout.strip()


def _verify_file(record: Mapping[str, Any], *, label: str) -> Path:
    expected = record.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64 or expected == "0" * 64:
        raise RuntimeError(f"{label} SHA-256 is not frozen")
    path = _resolve_path(record.get("path"), label=label)
    if not path.is_file() or _sha256(path) != expected:
        raise RuntimeError(f"{label} identity drifted")
    return path


def _verify_frozen_inputs(config: Mapping[str, Any]) -> None:
    closure = config.get("frozen_schema_closure_v4")
    numerical = config.get("frozen_numerical_identity")
    if not isinstance(closure, Mapping) or not isinstance(numerical, Mapping):
        raise RuntimeError("frozen schema/numerical identities are absent")
    for key in (
        "config",
        "report",
        "preregistration",
        "comparator",
        "ledger_schema",
        "ledger_group_manifest",
        "field_manifest",
        "plan_manifest",
    ):
        record = closure.get(key)
        if not isinstance(record, Mapping):
            raise RuntimeError(f"frozen schema identity is absent: {key}")
        _verify_file(record, label=f"schema.{key}")
    candidate = numerical.get("candidate")
    oracle = numerical.get("oracle")
    builder = numerical.get("production_plan_builder")
    performance = numerical.get("performance_contract")
    dag = numerical.get("execution_DAG")
    if not all(isinstance(value, Mapping) for value in (candidate, oracle, builder, performance, dag)):
        raise RuntimeError("frozen numerical identities are incomplete")
    _verify_file(
        {"path": candidate.get("identity_path"), "sha256": candidate.get("identity_sha256")},
        label="candidate identity",
    )
    _verify_file(
        {"path": oracle.get("source_path"), "sha256": oracle.get("source_sha256")},
        label="oracle source",
    )
    _verify_file(builder, label="production plan builder")
    _verify_file(performance, label="performance contract")
    _verify_file(dag, label="execution DAG")


def _verify_execution_sources(config: Mapping[str, Any], *, execute: bool) -> None:
    identity = config.get("execution_identity")
    if not isinstance(identity, Mapping):
        raise RuntimeError("execution identity is absent")
    entries = (
        ("control_plane_source", "source_sha256"),
        ("production_wiring_source", "production_wiring_sha256"),
        ("cli", "cli_sha256"),
    )
    for path_key, hash_key in entries:
        expected = identity.get(hash_key)
        if not isinstance(expected, str) or len(expected) != 64 or expected == "0" * 64:
            if execute:
                raise RuntimeError(f"{hash_key} is not remotely frozen")
            continue
        if _sha256(_resolve_path(identity.get(path_key), label=path_key)) != expected:
            raise RuntimeError(f"{hash_key} drifted")
    anchor = identity.get("remote_anchor_commit")
    if not isinstance(anchor, str) or len(anchor) != 40:
        raise RuntimeError("remote anchor is invalid")
    if anchor == "0" * 40:
        if execute:
            raise RuntimeError("remote anchor is still pending")
        return
    branch = str(config["authority_lock"]["branch"])
    if _git_output("branch", "--show-current") != branch:
        raise RuntimeError("current branch differs from execution authority")
    head = _git_output("rev-parse", "HEAD")
    if _git_output("rev-parse", f"refs/remotes/origin/{branch}") != head:
        raise RuntimeError("local HEAD differs from current remote execution branch")
    _git_output("merge-base", "--is-ancestor", anchor, "HEAD")
    if execute and _git_output("status", "--porcelain=v1"):
        raise RuntimeError("tracked worktree is not clean before one-shot transition")


def _verify_environment(config: Mapping[str, Any], *, execute: bool) -> None:
    configured = config.get("environment_lock", {}).get("thread_environment")
    if configured != REQUIRED_THREAD_ENVIRONMENT:
        raise RuntimeError("single-thread environment definition changed")
    if execute:
        mismatches = [
            key
            for key, expected in REQUIRED_THREAD_ENVIRONMENT.items()
            if os.environ.get(key) != expected
        ]
        if mismatches:
            raise RuntimeError(
                "single-thread execution environment is not active: "
                + ", ".join(sorted(mismatches))
            )


def _verify_dependency_environment(contract: Any, *, execute: bool) -> None:
    environment = contract.predecessor.payload.get("environment_lock")
    if not isinstance(environment, Mapping):
        raise RuntimeError("frozen predecessor environment lock is absent")
    expected = {
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "scipy_version": importlib.metadata.version("scipy"),
        "pyyaml_version": importlib.metadata.version("PyYAML"),
    }
    for key, observed in expected.items():
        if environment.get(key) != observed:
            raise RuntimeError(f"frozen dependency environment differs: {key}")
    if environment.get("python_implementation") != platform.python_implementation():
        raise RuntimeError("frozen Python implementation differs")
    if execute:
        if environment.get("operating_system") != platform.platform():
            raise RuntimeError("frozen operating-system identity differs")
        if environment.get("architecture") != platform.machine():
            raise RuntimeError("frozen architecture differs")
        if int(environment.get("logical_processors", -1)) != int(os.cpu_count() or -1):
            raise RuntimeError("frozen logical processor count differs")


def _verify_execution_control(config: Mapping[str, Any], *, execute: bool) -> None:
    control = config.get("execution_control")
    counts = config.get("execution_counts")
    if not isinstance(control, Mapping) or not isinstance(counts, Mapping):
        raise RuntimeError("execution control/count locks are absent")
    required = {
        "execution_attempt_limit": 1,
        "initial_equivalence_v3_execution_count": 0,
        "automatic_retry": False,
        "manual_retry": False,
        "process_count": 1,
        "thread_count": 1,
        "preview_or_partial_trial_before_attempt": "forbidden",
        "stitch_or_resume_historical_rows": "forbidden",
    }
    for key, expected in required.items():
        if control.get(key) != expected:
            raise RuntimeError(f"execution control changed: {key}")
    required_counts = {
        "equivalence_v1_execution_count": 1,
        "equivalence_v2_execution_count": 1,
        "equivalence_v3_execution_count": 0,
        "equivalence_v3_completed_rows": 0,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    for key, expected in required_counts.items():
        if counts.get(key) != expected:
            raise RuntimeError(f"execution count changed: {key}")
    if execute and config.get("status") != READY_STATUS:
        raise RuntimeError("execution config is not remotely frozen and ready")


def _paths(config: Mapping[str, Any]) -> OutputPaths:
    records = config.get("machine_records")
    outputs = config.get("planned_outputs")
    if not isinstance(records, Mapping) or not isinstance(outputs, Mapping):
        raise RuntimeError("machine/output path map is absent")
    return OutputPaths(
        registry=_resolve_path(records.get("execution_registry"), label="registry"),
        journal=_resolve_path(outputs.get("journal"), label="journal"),
        normalized_records=_resolve_path(
            outputs.get("normalized_records"), label="normalized records"
        ),
        electrical_table=_resolve_path(outputs.get("electrical"), label="electrical"),
        interval_table=_resolve_path(outputs.get("interval"), label="interval"),
        progression_table=_resolve_path(outputs.get("progression"), label="progression"),
        failure_table=_resolve_path(outputs.get("failure"), label="failure"),
        summary=_resolve_path(outputs.get("summary"), label="summary"),
    )


def validate_execution_identity(
    config_path: Path = DEFAULT_CONFIG_PATH, *, execute: bool = False
) -> tuple[Mapping[str, Any], Any, OutputPaths, Mapping[str, Any]]:
    """Validate frozen authority without scheduling a numerical row."""

    config = _load_config(config_path)
    _verify_frozen_inputs(config)
    _verify_execution_sources(config, execute=execute)
    _verify_environment(config, execute=execute)
    _verify_execution_control(config, execute=execute)
    contract = _v3.load_preregistered_contract_bundle()
    _verify_dependency_environment(contract, execute=execute)
    rows = plan_rows_from_contract(contract)
    if tuple(row.plan_index for row in rows) != tuple(range(57)):
        raise RuntimeError("frozen plan order is not exactly 0..56")
    paths = _paths(config)
    registry = load_registry(paths.registry)
    identity = config["execution_identity"]
    expected = {
        "equivalence_v2_execution_count": 1,
        "plan_manifest_sha256": config["frozen_schema_closure_v4"]["plan_manifest"]["sha256"],
        "ledger_manifest_sha256": config["frozen_schema_closure_v4"]["ledger_group_manifest"]["sha256"],
        "contract_bundle_sha256": config["frozen_schema_closure_v4"]["preregistration"]["sha256"],
        "runner_source_sha256": identity.get("source_sha256"),
        "remote_anchor_commit": identity.get("remote_anchor_commit"),
        "formal_execution_count": 0,
    }
    for key, value in expected.items():
        if registry.get(key) != value:
            raise RuntimeError(f"execution registry differs: {key}")
    if execute and (
        registry.get("state") != "AUTHORIZED_NOT_STARTED"
        or registry.get("equivalence_v3_execution_count") != 0
    ):
        raise RuntimeError("the independent one-shot attempt is not available")
    return config, contract, paths, registry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    config, contract, paths, registry = validate_execution_identity(
        args.config, execute=args.execute_once
    )
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "frozen_v3_identity_valid_not_executed",
                    "plan_rows": 57,
                    "equivalence_v2_execution_count": 1,
                    "equivalence_v3_execution_count": registry[
                        "equivalence_v3_execution_count"
                    ],
                    "formal_execution_count": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    with open_frozen_production_context(contract=contract) as context:

        def row_executor(row: Any) -> RowObservationPair:
            pair = execute_production_row(context, row)
            if (
                pair.plan_index != row.plan_index
                or pair.sample_id != row.sample_id
                or pair.family != row.family
            ):
                raise RuntimeError("production adapter returned a different row identity")
            return RowObservationPair(
                candidate_observation=pair.candidate_observation,
                oracle_observation=pair.oracle_observation,
                runtime_input_sha256=pair.runtime_input_sha256,
                candidate_validation_errors=pair.candidate_validation_errors,
                oracle_validation_errors=pair.oracle_validation_errors,
            )

        outcome = run_independent_audit(
            contract=contract,
            row_executor=row_executor,
            paths=paths,
            expected_registry_sha256=str(registry["registry_sha256"]),
        )
    print(
        json.dumps(
            {
                "terminal_state": outcome.terminal_state,
                "completed_rows": outcome.completed_rows,
                "summary_path": outcome.summary_path.relative_to(ROOT).as_posix(),
                "equivalence_v3_execution_count": 1,
                "formal_execution_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
