"""CLI for the single frozen equivalence-v2 execution attempt.

Solver-free validation and numerical execution are separate explicit modes.
Numerical row dispatch is only reachable through ``--execute-once`` after the
remote anchor, source hashes, registry, contract bundle, and single-thread
environment agree.
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

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator_v3 as _v3
from pinnpcm.audit.geophase_phase1_v2_equivalence_v2_one_shot import (
    OutputPaths,
    RowObservationPair,
    load_registry,
    plan_rows_from_contract,
    run_one_shot_audit,
)
from pinnpcm.audit.geophase_phase1_v2_equivalence_v2_production_adapter import (
    execute_production_row,
    open_frozen_production_context,
)

DEFAULT_CONFIG_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_equivalence_v2_one_shot_execution.yaml"
)
EXPECTED_TASK_ID = "Q2_PHASE1_V2_EQUIVALENCE_V2_ONE_SHOT_AUDIT"
EXPECTED_SCHEMA_VERSION = "geophase_phase1_v2_equivalence_v2_one_shot_execution_v1"
READY_AUTHORIZATION_STATUS = "READY_FROZEN_REMOTE_ANCHOR_NOT_EXECUTED"
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
        raise RuntimeError("one-shot execution config is unreadable") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("one-shot execution config is not a mapping")
    if payload.get("task_id") != EXPECTED_TASK_ID:
        raise RuntimeError("one-shot task identity changed")
    if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise RuntimeError("one-shot schema identity changed")
    return payload


def _git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git authority query failed: {' '.join(arguments)}")
    return result.stdout.strip()


def _verify_source_identity(config: Mapping[str, Any], *, execute: bool) -> None:
    identity = config.get("execution_identity")
    if not isinstance(identity, Mapping):
        raise RuntimeError("execution identity is absent")
    locked_paths = {
        "source_sha256": identity.get("control_plane_source"),
        "production_wiring_sha256": identity.get("production_wiring_source"),
        "cli_sha256": identity.get("cli"),
    }
    for hash_key, path_value in locked_paths.items():
        expected = identity.get(hash_key)
        if not isinstance(expected, str) or len(expected) != 64:
            if execute:
                raise RuntimeError(f"{hash_key} is not remotely frozen")
            continue
        if _sha256(_resolve_path(path_value, label=hash_key)) != expected:
            raise RuntimeError(f"{hash_key} drifted")
    remote_anchor = identity.get("remote_anchor_commit")
    if not isinstance(remote_anchor, str) or len(remote_anchor) != 40:
        if execute:
            raise RuntimeError("remote anchor commit is not frozen")
        return
    branch = config.get("authority_lock", {}).get("branch")
    if not isinstance(branch, str) or not branch:
        raise RuntimeError("execution branch identity is absent")
    if _git_output("branch", "--show-current") != branch:
        raise RuntimeError("current branch differs from the frozen execution branch")
    if remote_anchor == "0" * 40:
        if execute:
            raise RuntimeError("remote anchor commit is still pending")
        return
    _git_output("merge-base", "--is-ancestor", remote_anchor, "HEAD")
    remote_ref = f"refs/remotes/origin/{branch}"
    head = _git_output("rev-parse", "HEAD")
    if _git_output("rev-parse", remote_ref) != head:
        raise RuntimeError("local HEAD differs from the current origin execution branch")
    if execute and _git_output("status", "--porcelain=v1"):
        raise RuntimeError("tracked worktree is not clean before the one-shot transition")


def _verify_environment(config: Mapping[str, Any], *, execute: bool) -> None:
    configured = config.get("environment_lock", {}).get("thread_environment")
    if configured != REQUIRED_THREAD_ENVIRONMENT:
        raise RuntimeError("frozen single-thread environment definition changed")
    if execute:
        mismatches = {
            key: os.environ.get(key)
            for key, expected in REQUIRED_THREAD_ENVIRONMENT.items()
            if os.environ.get(key) != expected
        }
        if mismatches:
            raise RuntimeError(
                "single-thread execution environment is not active: "
                + ", ".join(sorted(mismatches))
            )


def _verify_frozen_dependency_environment(contract: Any, *, execute: bool) -> None:
    environment = contract.payload.get("environment_lock")
    if not isinstance(environment, Mapping):
        raise RuntimeError("frozen closure environment lock is absent")
    expected_versions = {
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "scipy_version": importlib.metadata.version("scipy"),
        "pyyaml_version": importlib.metadata.version("PyYAML"),
    }
    for key, observed in expected_versions.items():
        if environment.get(key) != observed:
            raise RuntimeError(f"frozen dependency environment differs: {key}")
    if environment.get("python_implementation") != platform.python_implementation():
        raise RuntimeError("frozen Python implementation differs")
    if execute:
        if environment.get("operating_system") != platform.platform():
            raise RuntimeError("frozen operating system identity differs")
        if environment.get("architecture") != platform.machine():
            raise RuntimeError("frozen machine architecture differs")
        if int(environment.get("logical_processors", -1)) != int(os.cpu_count() or -1):
            raise RuntimeError("frozen logical processor count differs")
    dependency_locks = environment.get("dependency_locks")
    if not isinstance(dependency_locks, Mapping):
        raise RuntimeError("frozen dependency file locks are absent")
    for key, relative_path in (
        ("requirements_sha256", "requirements.txt"),
        ("pyproject_sha256", "pyproject.toml"),
    ):
        if dependency_locks.get(key) != _sha256(ROOT / relative_path):
            raise RuntimeError(f"frozen dependency lock differs: {relative_path}")


def _verify_execution_control(config: Mapping[str, Any], *, execute: bool) -> None:
    control = config.get("execution_control")
    counts = config.get("execution_counts")
    if not isinstance(control, Mapping) or not isinstance(counts, Mapping):
        raise RuntimeError("execution control/count locks are absent")
    required = {
        "execution_attempt_limit": 1,
        "initial_equivalence_v2_execution_count": 0,
        "automatic_retry": False,
        "manual_retry": False,
        "process_count": 1,
        "thread_count": 1,
        "fail_fast": "first_valid_A_B_or_C_failure",
        "preview_or_partial_trial_before_attempt": "forbidden",
    }
    for key, expected in required.items():
        if control.get(key) != expected:
            raise RuntimeError(f"execution control changed: {key}")
    for key in (
        "equivalence_v2_execution_count",
        "equivalence_v2_completed_rows",
        "equivalence_v2_result_artifact_count",
        "formal_execution_count",
        "formal_artifact_count",
    ):
        if counts.get(key) != 0:
            raise RuntimeError(f"prospective execution count changed: {key}")
    expected_status = (
        "ready_frozen_remote_anchor_not_executed"
        if execute
        else config.get("status")
    )
    if execute and config.get("status") != expected_status:
        raise RuntimeError("execution config is not in the frozen ready state")


def _verify_frozen_input_paths(config: Mapping[str, Any]) -> None:
    closure = config.get("frozen_closure_v3")
    numerical = config.get("frozen_numerical_identity")
    if not isinstance(closure, Mapping) or not isinstance(numerical, Mapping):
        raise RuntimeError("frozen closure/numerical identities are absent")
    records: list[tuple[str, Any, Any]] = []
    for key in ("config", "report", "preregistration", "comparator", "field_manifest", "plan_manifest"):
        record = closure.get(key)
        if not isinstance(record, Mapping):
            raise RuntimeError(f"frozen closure identity is absent: {key}")
        records.append((f"closure.{key}", record.get("path"), record.get("sha256")))
    candidate = numerical.get("candidate")
    oracle = numerical.get("oracle")
    builder = numerical.get("production_plan_builder")
    performance = numerical.get("performance_contract")
    dag = numerical.get("execution_DAG")
    if not all(isinstance(value, Mapping) for value in (candidate, oracle, builder, performance, dag)):
        raise RuntimeError("frozen numerical path identities are incomplete")
    records.extend(
        (
            ("candidate.identity", candidate.get("identity_path"), candidate.get("identity_sha256")),
            ("oracle.source", "tests/oracles/pr8_geophase_2p5d_fvm.py", oracle.get("source_sha256")),
            ("production_plan_builder", builder.get("path"), builder.get("sha256")),
            ("performance_contract", performance.get("path"), performance.get("sha256")),
            ("execution_DAG", dag.get("path"), dag.get("sha256")),
        )
    )
    for label, path_value, expected in records:
        if not isinstance(expected, str) or len(expected) != 64:
            raise RuntimeError(f"frozen input SHA-256 is invalid: {label}")
        if _sha256(_resolve_path(path_value, label=label)) != expected:
            raise RuntimeError(f"frozen input identity drifted: {label}")


def _verify_execution_authorization(
    config_path: Path, config: Mapping[str, Any], *, execute: bool
) -> Mapping[str, Any]:
    records = config.get("machine_records")
    if not isinstance(records, Mapping):
        raise RuntimeError("machine record paths are absent")
    path = _resolve_path(records.get("execution_authorization"), label="authorization")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("execution authorization is unreadable") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("execution authorization is not a mapping")
    if payload.get("task_id") != EXPECTED_TASK_ID:
        raise RuntimeError("execution authorization task identity differs")
    if payload.get("execution_config_sha256") != _sha256(config_path):
        raise RuntimeError("execution authorization/config identity differs")
    identity = config["execution_identity"]
    required_matches = {
        "runner_source_sha256": identity.get("source_sha256"),
        "production_wiring_sha256": identity.get("production_wiring_sha256"),
        "runner_cli_sha256": identity.get("cli_sha256"),
        "remote_anchor_commit": identity.get("remote_anchor_commit"),
    }
    for key, expected in required_matches.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"execution authorization differs: {key}")
    if payload.get("execution_attempt_limit") != 1:
        raise RuntimeError("execution authorization attempt limit changed")
    if payload.get("automatic_retry") is not False:
        raise RuntimeError("execution authorization enabled automatic retry")
    if payload.get("manual_retry") is not False:
        raise RuntimeError("execution authorization enabled manual retry")
    for key in ("equivalence_v2_execution_count", "formal_execution_count"):
        if payload.get(key) != 0:
            raise RuntimeError(f"execution authorization count changed: {key}")
    if payload.get("formal_artifact_count") != 0:
        raise RuntimeError("execution authorization formal artifact count changed")
    if payload.get("expected_plan_count") != 57:
        raise RuntimeError("execution authorization plan count changed")
    if execute:
        if payload.get("status") != READY_AUTHORIZATION_STATUS:
            raise RuntimeError("execution authorization is not ready for one-shot execution")
        if payload.get("clean_checkout_CI") != (
            "required_before_execution_and_verified_externally"
        ):
            raise RuntimeError("execution authorization clean-checkout CI gate changed")
    elif payload.get("status") not in {
        "PREPARED_PENDING_REMOTE_ANCHOR_NOT_EXECUTED",
        READY_AUTHORIZATION_STATUS,
    }:
        raise RuntimeError("execution authorization has an unknown prospective status")
    return payload


def _paths(config: Mapping[str, Any]) -> OutputPaths:
    records = config.get("machine_records")
    outputs = config.get("planned_outputs")
    if not isinstance(records, Mapping) or not isinstance(outputs, Mapping):
        raise RuntimeError("one-shot machine/output path map is absent")
    return OutputPaths(
        registry=_resolve_path(records.get("execution_registry"), label="registry"),
        journal=_resolve_path(outputs.get("journal"), label="journal"),
        electrical_table=_resolve_path(outputs.get("electrical"), label="electrical"),
        interval_table=_resolve_path(outputs.get("interval"), label="interval"),
        progression_table=_resolve_path(
            outputs.get("progression"), label="progression"
        ),
        failure_table=_resolve_path(outputs.get("failure"), label="failure"),
        summary=_resolve_path(outputs.get("summary"), label="summary"),
    )


def validate_execution_identity(
    config_path: Path = DEFAULT_CONFIG_PATH, *, execute: bool = False
) -> tuple[Mapping[str, Any], Any, OutputPaths, Mapping[str, Any]]:
    """Validate the frozen runner identity without dispatching a row."""

    config = _load_config(config_path)
    _verify_source_identity(config, execute=execute)
    _verify_environment(config, execute=execute)
    _verify_execution_control(config, execute=execute)
    _verify_frozen_input_paths(config)
    contract = _v3.load_preregistered_contract_bundle()
    _verify_frozen_dependency_environment(contract, execute=execute)
    _verify_execution_authorization(config_path, config, execute=execute)
    rows = plan_rows_from_contract(contract)
    if tuple(row.plan_index for row in rows) != tuple(range(57)):
        raise RuntimeError("frozen plan order is not exactly 0..56")
    paths = _paths(config)
    registry = load_registry(paths.registry)
    execution_identity = config["execution_identity"]
    for key, expected in (
        ("plan_manifest_sha256", config["frozen_closure_v3"]["plan_manifest"]["sha256"]),
        (
            "contract_bundle_sha256",
            config["frozen_closure_v3"]["preregistration"]["sha256"],
        ),
        ("runner_source_sha256", execution_identity.get("source_sha256")),
        ("remote_anchor_commit", execution_identity.get("remote_anchor_commit")),
    ):
        if registry.get(key) != expected:
            raise RuntimeError(f"execution registry differs: {key}")
    if registry.get("formal_execution_count") != 0:
        raise RuntimeError("formal execution count changed")
    if execute and (
        registry.get("state") != "AUTHORIZED_NOT_STARTED"
        or registry.get("equivalence_v2_execution_count") != 0
    ):
        raise RuntimeError("the one-shot execution attempt is not available")
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
        with open_frozen_production_context() as context:
            if context.contract.plan_rows_sha256 != contract.plan_rows_sha256:
                raise RuntimeError("production/v3 plan identity differs")
        print(
            json.dumps(
                {
                    "status": "frozen_one_shot_identity_valid_not_executed",
                    "plan_rows": 57,
                    "equivalence_v2_execution_count": registry[
                        "equivalence_v2_execution_count"
                    ],
                    "formal_execution_count": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    with open_frozen_production_context() as context:
        if context.contract.plan_rows_sha256 != contract.plan_rows_sha256:
            raise RuntimeError("production/v3 plan identity differs")

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
                candidate_validation_errors=pair.candidate_validation_errors,
                oracle_validation_errors=pair.oracle_validation_errors,
            )

        outcome = run_one_shot_audit(
            contract=contract,
            row_executor=row_executor,
            paths=paths,
            expected_registry_sha256=str(registry["registry_sha256"]),
        )
    print(
        json.dumps(
            {
                "terminal_state": outcome.terminal_state,
                "terminal_event": outcome.terminal_event,
                "completed_rows": outcome.completed_rows,
                "summary_path": outcome.summary_path.relative_to(ROOT).as_posix(),
                "formal_execution_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
