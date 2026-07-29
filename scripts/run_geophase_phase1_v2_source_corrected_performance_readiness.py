"""Source-corrected v3 equivalence and runtime-readiness orchestrator.

The runner is fail closed by default.  Numerical entry points are explicit,
task-scoped adapters; importing this module or invoking it without a mode can
never dispatch C1, C2, C3, a formal evaluation ID, or a formal artifact.
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
from time import perf_counter
from types import ModuleType
from typing import Any, Callable, Iterator, Mapping, Sequence

import yaml

from pinnpcm.solvers.geophase_phase1_v2_readiness_journal import (
    ReadinessProvenanceJournal,
    SampleArtifactError,
    build_completed_sample_document,
    publish_completed_sample,
    write_completed_sample_temp,
)
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    C3WorkerMemoryLimitError,
    select_c3_worker_count,
)
from pinnpcm.solvers.geophase_phase1_v2_performance_equivalence import (
    atomic_write_json as atomic_write_equivalence_json,
    atomic_write_text as atomic_write_equivalence_text,
    run_equivalence_audit,
)
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    resolve_controller_v2,
)


ROOT = Path(__file__).resolve().parents[1]
STAGE_PATH = ROOT / "configs" / "geo2p5d_stage_source_corrected_v3.yaml"
PREREGISTRATION_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "source_correction_preregistration.json"
)
IDENTITY_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "resolved_runtime_identity.json"
)
PERFORMANCE_PREREGISTRATION_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_source_corrected_performance_repair.yaml"
)
PERFORMANCE_PREREGISTRATION_SHA256 = (
    "84e1ecb298cfa6264646cc5e74df602b3e9e790e3eecfdc1abea62c087e87db4"
)
SOURCE_PREREGISTRATION_COMMIT = "0ebe037ef707a56750c5db0c52f7a312ee251b6c"
SOURCE_PREREGISTRATION_SHA256 = (
    "5b132f85c4d94ac504a6558ad889f69f094e30797c694015bb96904268d0e966"
)
PERFORMANCE_OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "performance_repair"
)
CANDIDATE_IDENTITY_PATH = PERFORMANCE_OUTPUT_DIR / "optimized_candidate_identity.json"
AUDIT_HARNESS_IDENTITY_PATH = (
    PERFORMANCE_OUTPUT_DIR / "audit_harness_erratum_identity.json"
)
EQUIVALENCE_ATTEMPT_PROVENANCE_PATH = (
    PERFORMANCE_OUTPUT_DIR / "equivalence_valid_attempt_provenance.jsonl"
)
AUDIT_HARNESS_ADDENDUM_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_equivalence_audit_harness_erratum_v1.yaml"
)
SOURCE_CORRECTED_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
SOURCE_CORRECTED_CONTROLLER_OVERLAY_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml"
)
PR8_ORACLE_PATH = ROOT / "tests" / "oracles" / "pr8_geophase_2p5d_fvm.py"
PR8_ORACLE_SHA256 = (
    "e1a349ca0275021508cd07da02576adafbbcdae81e122659274769f329016a37"
)
READINESS_OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "controller_v2_readiness"
)
EQUIVALENCE_SUMMARY_PATH = PERFORMANCE_OUTPUT_DIR / "equivalence_summary.json"
WORKER_RSS_PATH = PERFORMANCE_OUTPUT_DIR / "worker_RSS_microbenchmark.json"
READINESS_JOURNAL_PATH = READINESS_OUTPUT_DIR / "provenance_journal.jsonl"
READINESS_SUMMARY_PATH = READINESS_OUTPUT_DIR / "readiness_summary.json"

# Retained for the already-merged routing-contract test.  Execution readiness
# is no longer inferred from this Boolean: every numerical mode instead needs
# an explicit task adapter and the relevant frozen identity/hash inputs.
IMPLEMENTATION_READY = False

PREFLIGHT_LIMIT_S = 900.0
WORKER_BACKSTOP_S = 880.0
PARENT_FINALIZATION_RESERVE_S = 20.0
INDEPENDENT_C3_SAMPLE_COUNT = 26
EQUIVALENCE_GATE = 1.0e-12
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
}
_VALID_DISPOSITIONS = frozenset(
    {
        "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "NO_GO_RUNTIME",
        "INVALID_PREFLIGHT_INFRASTRUCTURE",
    }
)
_VALID_RUNTIME_FAILURE_CLASSES = frozenset(
    {"numerical_integrity", "performance_budget", "memory", "disk", "dormant_runner"}
)
_WORKER_EVENT_QUEUE: Any = None
_WORKER_START_ACKS: Any = None
PERFORMANCE_TIMING_SEMANTICS = (
    "hierarchical_nonadditive_use_observed_sample_wall_time_for_forecast"
)
TASK_ADAPTER_ENTRYPOINT = (
    "pinnpcm.solvers.geophase_phase1_v2_source_corrected_performance:task_adapter"
)
CANDIDATE_BRANCH = "codex/phase1-v2-source-corrected-performance-repair"
CANDIDATE_REMOTE_REF = f"refs/remotes/origin/{CANDIDATE_BRANCH}"
FROZEN_CANDIDATE_COMMIT = "1ae2704f6d84a3733d9de58aa23d992aa0c471a5"
FROZEN_CANDIDATE_TREE = "d3833a4a5dd067dab72c84f15fe2f8e726bd9512"
FROZEN_CANDIDATE_IDENTITY_SHA256 = (
    "39044f37c983060df48e9915c594f69fbfbeacc60eef9a32bc352bdb5ec25b10"
)
INVALID_LAUNCH_EVIDENCE_COMMIT = "8e4f787e3b349c1858f53847c9f7f2bc4e712627"
INVALID_LAUNCH_EVIDENCE_TREE = "2a2a3b74692a64482c212214146cf8add263f111"
INVALID_LAUNCH_PROVENANCE_PATH = (
    PERFORMANCE_OUTPUT_DIR / "invalid_equivalence_launch_provenance.json"
)
INVALID_LAUNCH_PROVENANCE_SHA256 = (
    "58443b4a6961926c43c60b205e0abe407cb4217360912aef28489d3d7697ea2b"
)
AUDIT_HARNESS_IDENTITY_SCHEMA = (
    "geophase_phase1_v2_equivalence_audit_harness_identity_v1"
)
AUDIT_HARNESS_ORACLE_MODULE_NAME = (
    "_phase1_v2_pr8_test_only_electrical_oracle"
)
AUDIT_HARNESS_ALLOWED_PATHS = (
    ".gitignore",
    "configs/geophase_phase1_v2_equivalence_audit_harness_erratum_v1.yaml",
    "scripts/run_geophase_phase1_v2_source_corrected_performance_readiness.py",
    "scripts/run_geophase_phase1_v2_equivalence_audit_harness.py",
    "tests/test_geophase_phase1_v2_source_corrected_performance_closure_runner.py",
    "tests/test_geophase_phase1_v2_source_corrected_performance_oracle.py",
    "tests/test_geophase_phase1_v2_source_corrected_performance_repair_preregistration.py",
)
CANDIDATE_IMPLEMENTATION_PATHS = (
    "scripts/run_geophase_phase1_v2_source_corrected_performance_readiness.py",
    "src/pinnpcm/solvers/geophase_2p5d_fvm.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_fvm.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_controller_v2.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_implicit.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_runtime.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_streaming.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_performance_equivalence.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_readiness_journal.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_source_corrected_performance.py",
    "tests/oracles/pr8_geophase_2p5d_fvm.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _mapping_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(dict(value))).hexdigest()


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(
                handle,
                parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid strict JSON: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a mapping")
    return value


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise RuntimeError(f"{label} must be a lowercase SHA-256")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() or path.exists():
        raise RuntimeError(f"one-shot readiness output already exists: {path}")
    data = json.dumps(
        dict(payload), indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _git_output(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"git {' '.join(arguments)} failed with {completed.returncode}: {detail}"
        )
    return completed.stdout.strip()


def _git_candidate_path_is_clean(candidate_commit: str, relative_path: str) -> bool:
    completed = subprocess.run(
        ["git", "diff", "--quiet", candidate_commit, "--", relative_path],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"cannot compare candidate path with Git: {relative_path}")
    return completed.returncode == 0


def _candidate_git_identity() -> dict[str, str]:
    branch = _git_output(("branch", "--show-current"))
    if branch != CANDIDATE_BRANCH:
        raise RuntimeError(
            f"candidate identity may only be frozen on {CANDIDATE_BRANCH}"
        )
    candidate_commit = _git_output(("rev-parse", "HEAD"))
    candidate_tree = _git_output(("rev-parse", "HEAD^{tree}"))
    remote_commit = _git_output(("rev-parse", CANDIDATE_REMOTE_REF))
    if candidate_commit != remote_commit:
        raise RuntimeError("candidate commit is not the pushed remote branch head")
    return {
        "candidate_branch": branch,
        "candidate_commit": candidate_commit,
        "candidate_tree": candidate_tree,
        "remote_tracking_ref": CANDIDATE_REMOTE_REF,
        "remote_tracking_commit": remote_commit,
    }


def _candidate_implementation_records(candidate_commit: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative_path in CANDIDATE_IMPLEMENTATION_PATHS:
        path = ROOT / relative_path
        if not path.is_file():
            raise RuntimeError(f"candidate implementation path is absent: {relative_path}")
        tracked = _git_output(("ls-files", "--error-unmatch", "--", relative_path))
        if tracked.replace("\\", "/") != relative_path:
            raise RuntimeError(f"candidate implementation path is not uniquely tracked: {relative_path}")
        if not _git_candidate_path_is_clean(candidate_commit, relative_path):
            raise RuntimeError(f"candidate implementation path differs from commit: {relative_path}")
        records.append(
            {
                "path": relative_path,
                "git_blob": _git_output(
                    ("rev-parse", f"{candidate_commit}:{relative_path}")
                ),
                "sha256": _sha256(path),
            }
        )
    return records


def build_optimized_candidate_identity(
    *, route: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the one-shot, non-numerical identity for a pushed candidate."""

    if _git_output(("status", "--porcelain", "--untracked-files=no")):
        raise RuntimeError("tracked worktree changes remain before candidate freeze")
    git_identity = _candidate_git_identity()
    if _sha256(PERFORMANCE_PREREGISTRATION_PATH) != PERFORMANCE_PREREGISTRATION_SHA256:
        raise RuntimeError("performance preregistration bytes changed")
    return {
        "task_id": "PHASE1_V2_SOURCE_CORRECTED_PERFORMANCE_CLOSURE",
        "schema_version": (
            "geophase_phase1_v2_source_corrected_optimized_candidate_identity_v1"
        ),
        "status": "optimized_candidate_frozen_before_final_equivalence_audit",
        **git_identity,
        "performance_repair_preregistration": {
            "path": PERFORMANCE_PREREGISTRATION_PATH.relative_to(ROOT).as_posix(),
            "sha256": PERFORMANCE_PREREGISTRATION_SHA256,
        },
        "resolved_runtime_identity_sha256": route[
            "resolved_runtime_identity_sha256"
        ],
        "implementation_paths": _candidate_implementation_records(
            git_identity["candidate_commit"]
        ),
        "code_change_after_freeze": "forbidden",
        "final_equivalence_audit_attempt_limit": 1,
        "numerical_execution_performed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def validate_optimized_candidate_identity(
    *, expected_file_sha256: str
) -> dict[str, Any]:
    """Verify the fixed candidate identity against Git and current bytes."""

    expected_hash = _require_sha256(
        expected_file_sha256, "candidate identity file SHA-256"
    )
    if _sha256(CANDIDATE_IDENTITY_PATH) != expected_hash:
        raise RuntimeError("candidate identity file hash mismatch")
    payload = _strict_json(CANDIDATE_IDENTITY_PATH)
    if payload.get("schema_version") != (
        "geophase_phase1_v2_source_corrected_optimized_candidate_identity_v1"
    ):
        raise RuntimeError("candidate identity schema mismatch")
    if payload.get("status") != (
        "optimized_candidate_frozen_before_final_equivalence_audit"
    ):
        raise RuntimeError("candidate identity status mismatch")
    if payload.get("formal_execution_count") != 0:
        raise RuntimeError("candidate identity consumed formal execution")
    if payload.get("formal_artifact_count") != 0:
        raise RuntimeError("candidate identity contains a formal artifact")
    if payload.get("numerical_execution_performed") is not False:
        raise RuntimeError("candidate identity incorrectly records numerical work")

    current = _candidate_git_identity()
    for key, value in current.items():
        if payload.get(key) != value:
            raise RuntimeError(f"candidate Git identity mismatch: {key}")
    preregistration = payload.get("performance_repair_preregistration")
    if preregistration != {
        "path": PERFORMANCE_PREREGISTRATION_PATH.relative_to(ROOT).as_posix(),
        "sha256": PERFORMANCE_PREREGISTRATION_SHA256,
    }:
        raise RuntimeError("candidate preregistration identity mismatch")
    if _sha256(PERFORMANCE_PREREGISTRATION_PATH) != PERFORMANCE_PREREGISTRATION_SHA256:
        raise RuntimeError("performance preregistration bytes changed")

    records = payload.get("implementation_paths")
    if not isinstance(records, list):
        raise RuntimeError("candidate implementation path records are absent")
    by_path = {
        str(record.get("path")): record
        for record in records
        if isinstance(record, Mapping)
    }
    if tuple(by_path) != CANDIDATE_IMPLEMENTATION_PATHS or len(by_path) != len(records):
        raise RuntimeError("candidate implementation path allowlist mismatch")
    candidate_commit = current["candidate_commit"]
    for relative_path in CANDIDATE_IMPLEMENTATION_PATHS:
        record = by_path[relative_path]
        if not _git_candidate_path_is_clean(candidate_commit, relative_path):
            raise RuntimeError(f"candidate implementation path changed: {relative_path}")
        if record.get("git_blob") != _git_output(
            ("rev-parse", f"{candidate_commit}:{relative_path}")
        ):
            raise RuntimeError(f"candidate Git blob mismatch: {relative_path}")
        if record.get("sha256") != _sha256(ROOT / relative_path):
            raise RuntimeError(f"candidate byte hash mismatch: {relative_path}")
    result = dict(payload)
    result["file_sha256"] = expected_hash
    return result


def _frozen_candidate_records(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = payload.get("implementation_paths")
    if not isinstance(records, list):
        raise RuntimeError("frozen candidate implementation records are absent")
    by_path = {
        str(record.get("path")): record
        for record in records
        if isinstance(record, Mapping)
    }
    if tuple(by_path) != CANDIDATE_IMPLEMENTATION_PATHS or len(by_path) != len(records):
        raise RuntimeError("frozen candidate implementation allowlist mismatch")
    return by_path


def validate_frozen_candidate_identity_for_harness(
    *, expected_file_sha256: str
) -> dict[str, Any]:
    """Validate candidate Git objects while permitting one runner-only override."""

    expected_hash = _require_sha256(
        expected_file_sha256, "frozen candidate identity file SHA-256"
    )
    if expected_hash != FROZEN_CANDIDATE_IDENTITY_SHA256:
        raise RuntimeError("unexpected frozen candidate identity hash")
    if _sha256(CANDIDATE_IDENTITY_PATH) != expected_hash:
        raise RuntimeError("frozen candidate identity bytes changed")
    payload = _strict_json(CANDIDATE_IDENTITY_PATH)
    if payload.get("candidate_commit") != FROZEN_CANDIDATE_COMMIT:
        raise RuntimeError("frozen candidate commit changed")
    if payload.get("candidate_tree") != FROZEN_CANDIDATE_TREE:
        raise RuntimeError("frozen candidate tree changed")
    if _git_output(("rev-parse", f"{FROZEN_CANDIDATE_COMMIT}^{{tree}}")) != (
        FROZEN_CANDIDATE_TREE
    ):
        raise RuntimeError("frozen candidate Git tree cannot be recovered")
    if payload.get("formal_execution_count") != 0:
        raise RuntimeError("frozen candidate consumed formal execution")
    if payload.get("formal_artifact_count") != 0:
        raise RuntimeError("frozen candidate contains a formal artifact")
    if payload.get("numerical_execution_performed") is not False:
        raise RuntimeError("frozen candidate identity records numerical execution")
    preregistration = payload.get("performance_repair_preregistration")
    if preregistration != {
        "path": PERFORMANCE_PREREGISTRATION_PATH.relative_to(ROOT).as_posix(),
        "sha256": PERFORMANCE_PREREGISTRATION_SHA256,
    }:
        raise RuntimeError("frozen performance preregistration identity changed")
    if _sha256(PERFORMANCE_PREREGISTRATION_PATH) != PERFORMANCE_PREREGISTRATION_SHA256:
        raise RuntimeError("performance preregistration bytes changed")

    runner_path = CANDIDATE_IMPLEMENTATION_PATHS[0]
    by_path = _frozen_candidate_records(payload)
    for relative_path in CANDIDATE_IMPLEMENTATION_PATHS:
        record = by_path[relative_path]
        frozen_blob = _git_output(
            ("rev-parse", f"{FROZEN_CANDIDATE_COMMIT}:{relative_path}")
        )
        if record.get("git_blob") != frozen_blob:
            raise RuntimeError(f"frozen candidate Git blob mismatch: {relative_path}")
        frozen_bytes = subprocess.run(
            ["git", "show", f"{FROZEN_CANDIDATE_COMMIT}:{relative_path}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        if frozen_bytes.returncode != 0:
            raise RuntimeError(f"cannot recover frozen candidate path: {relative_path}")
        frozen_sha256 = hashlib.sha256(frozen_bytes.stdout).hexdigest()
        if record.get("sha256") != frozen_sha256:
            raise RuntimeError(f"frozen candidate byte hash mismatch: {relative_path}")
        if relative_path == runner_path:
            continue
        if _sha256(ROOT / relative_path) != frozen_sha256:
            raise RuntimeError(f"candidate numerical path changed: {relative_path}")

    result = dict(payload)
    result["file_sha256"] = expected_hash
    result["harness_only_override_path"] = runner_path
    return result


def _validate_loaded_candidate_module_origins() -> None:
    """Reject editable-install leakage from any checkout other than this worktree."""

    source_root = (ROOT / "src").resolve()
    foreign: list[str] = []
    for name, module in tuple(sys.modules.items()):
        if name != "pinnpcm" and not name.startswith("pinnpcm."):
            continue
        location = getattr(module, "__file__", None)
        if location is None:
            continue
        try:
            Path(location).resolve().relative_to(source_root)
        except ValueError:
            foreign.append(f"{name}={location}")
    if foreign:
        raise RuntimeError(
            "candidate modules were imported from a foreign checkout: "
            + ", ".join(sorted(foreign))
        )


def _harness_path_records(commit: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative_path in AUDIT_HARNESS_ALLOWED_PATHS:
        path = ROOT / relative_path
        if not path.is_file():
            raise RuntimeError(f"audit harness path is absent: {relative_path}")
        tracked = _git_output(("ls-files", "--error-unmatch", "--", relative_path))
        if tracked.replace("\\", "/") != relative_path:
            raise RuntimeError(f"audit harness path is not uniquely tracked: {relative_path}")
        if not _git_candidate_path_is_clean(commit, relative_path):
            raise RuntimeError(f"audit harness path differs from erratum commit: {relative_path}")
        records.append(
            {
                "path": relative_path,
                "git_blob": _git_output(("rev-parse", f"{commit}:{relative_path}")),
                "sha256": _sha256(path),
            }
        )
    return records


def _combined_audit_identity_sha256(payload: Mapping[str, Any]) -> str:
    harness = {
        key: value
        for key, value in payload.items()
        if key != "audit_identity_sha256"
    }
    return _mapping_sha256(harness)


def build_audit_harness_erratum_identity() -> dict[str, Any]:
    """Build the post-push identity that composes candidate and harness commits."""

    candidate = validate_frozen_candidate_identity_for_harness(
        expected_file_sha256=FROZEN_CANDIDATE_IDENTITY_SHA256
    )
    if _git_output(("status", "--porcelain", "--untracked-files=no")):
        raise RuntimeError("tracked changes remain before harness identity freeze")
    if _git_output(("branch", "--show-current")) != CANDIDATE_BRANCH:
        raise RuntimeError("audit harness identity is on the wrong branch")
    erratum_commit = _git_output(("rev-parse", "HEAD"))
    erratum_tree = _git_output(("rev-parse", "HEAD^{tree}"))
    remote_commit = _git_output(("rev-parse", CANDIDATE_REMOTE_REF))
    if erratum_commit != remote_commit:
        raise RuntimeError("audit harness erratum is not the pushed branch head")
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            INVALID_LAUNCH_EVIDENCE_COMMIT,
            erratum_commit,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("audit harness erratum does not descend from evidence commit")
    changed_paths = tuple(
        line.replace("\\", "/")
        for line in _git_output(
            ("diff", "--name-only", f"{INVALID_LAUNCH_EVIDENCE_COMMIT}..HEAD")
        ).splitlines()
        if line
    )
    if set(changed_paths) != set(AUDIT_HARNESS_ALLOWED_PATHS):
        raise RuntimeError("erratum commit changed paths outside the harness allowlist")
    if _sha256(INVALID_LAUNCH_PROVENANCE_PATH) != INVALID_LAUNCH_PROVENANCE_SHA256:
        raise RuntimeError("invalid-launch provenance bytes changed")

    payload: dict[str, Any] = {
        "task_id": "PHASE1_V2_EQUIVALENCE_AUDIT_HARNESS_ERRATUM_AND_VALID_AUDIT",
        "identity_schema_version": AUDIT_HARNESS_IDENTITY_SCHEMA,
        "status": "versioned_harness_fixed_one_valid_audit_authorized",
        "frozen_candidate": {
            "commit": candidate["candidate_commit"],
            "tree": candidate["candidate_tree"],
            "identity_path": CANDIDATE_IDENTITY_PATH.relative_to(ROOT).as_posix(),
            "identity_sha256": candidate["file_sha256"],
            "runner_harness_only_override": candidate["harness_only_override_path"],
        },
        "erratum_commit": erratum_commit,
        "erratum_tree": erratum_tree,
        "erratum_base_evidence_commit": INVALID_LAUNCH_EVIDENCE_COMMIT,
        "erratum_base_evidence_tree": INVALID_LAUNCH_EVIDENCE_TREE,
        "remote_tracking_ref": CANDIDATE_REMOTE_REF,
        "remote_tracking_commit": remote_commit,
        "harness_paths": _harness_path_records(erratum_commit),
        "oracle": {
            "path": PR8_ORACLE_PATH.relative_to(ROOT).as_posix(),
            "sha256": PR8_ORACLE_SHA256,
        },
        "invalid_launch_provenance": {
            "path": INVALID_LAUNCH_PROVENANCE_PATH.relative_to(ROOT).as_posix(),
            "sha256": INVALID_LAUNCH_PROVENANCE_SHA256,
            "equivalence_rows_completed": 0,
            "equivalence_votes_cast": 0,
        },
        "valid_audit_attempt_limit": 1,
        "automatic_retry": "forbidden",
        "readiness_execution": "forbidden_without_fresh_user_authorization",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    payload["audit_identity_sha256"] = _combined_audit_identity_sha256(payload)
    return payload


def validate_audit_harness_erratum_identity(
    *, expected_file_sha256: str
) -> dict[str, Any]:
    expected_hash = _require_sha256(
        expected_file_sha256, "audit harness identity file SHA-256"
    )
    if _sha256(AUDIT_HARNESS_IDENTITY_PATH) != expected_hash:
        raise RuntimeError("audit harness identity file hash mismatch")
    payload = _strict_json(AUDIT_HARNESS_IDENTITY_PATH)
    if payload.get("identity_schema_version") != AUDIT_HARNESS_IDENTITY_SCHEMA:
        raise RuntimeError("audit harness identity schema mismatch")
    if payload.get("status") != "versioned_harness_fixed_one_valid_audit_authorized":
        raise RuntimeError("audit harness identity status mismatch")
    if payload.get("formal_execution_count") != 0:
        raise RuntimeError("audit harness identity consumed formal execution")
    if payload.get("formal_artifact_count") != 0:
        raise RuntimeError("audit harness identity contains a formal artifact")
    if payload.get("automatic_retry") != "forbidden":
        raise RuntimeError("audit harness identity permits retry")
    if payload.get("valid_audit_attempt_limit") != 1:
        raise RuntimeError("audit harness attempt limit changed")
    if payload.get("readiness_execution") != (
        "forbidden_without_fresh_user_authorization"
    ):
        raise RuntimeError("audit harness identity permits readiness execution")
    candidate = validate_frozen_candidate_identity_for_harness(
        expected_file_sha256=FROZEN_CANDIDATE_IDENTITY_SHA256
    )
    frozen = payload.get("frozen_candidate")
    if not isinstance(frozen, Mapping) or frozen.get("commit") != candidate["candidate_commit"]:
        raise RuntimeError("audit harness candidate commit mismatch")
    if frozen.get("tree") != candidate["candidate_tree"]:
        raise RuntimeError("audit harness candidate tree mismatch")
    if frozen.get("identity_sha256") != candidate["file_sha256"]:
        raise RuntimeError("audit harness candidate identity mismatch")
    erratum_commit = str(payload.get("erratum_commit", ""))
    erratum_tree = str(payload.get("erratum_tree", ""))
    if payload.get("erratum_base_evidence_commit") != INVALID_LAUNCH_EVIDENCE_COMMIT:
        raise RuntimeError("audit harness base evidence commit mismatch")
    if payload.get("erratum_base_evidence_tree") != INVALID_LAUNCH_EVIDENCE_TREE:
        raise RuntimeError("audit harness base evidence tree mismatch")
    if _git_output(("rev-parse", f"{INVALID_LAUNCH_EVIDENCE_COMMIT}^{{tree}}")) != (
        INVALID_LAUNCH_EVIDENCE_TREE
    ):
        raise RuntimeError("audit harness base evidence tree cannot be recovered")
    if payload.get("remote_tracking_ref") != CANDIDATE_REMOTE_REF:
        raise RuntimeError("audit harness remote tracking ref mismatch")
    if payload.get("remote_tracking_commit") != erratum_commit:
        raise RuntimeError("audit harness remote tracking commit mismatch")
    if _git_output(("rev-parse", "HEAD")) != erratum_commit:
        raise RuntimeError("current HEAD is not the versioned harness erratum")
    if _git_output(("rev-parse", "HEAD^{tree}")) != erratum_tree:
        raise RuntimeError("current tree is not the versioned harness erratum")
    if _git_output(("rev-parse", CANDIDATE_REMOTE_REF)) != erratum_commit:
        raise RuntimeError("versioned harness erratum is not the remote branch head")
    if _git_output(("status", "--porcelain", "--untracked-files=no")):
        raise RuntimeError("tracked worktree changes exist before valid audit")
    records = payload.get("harness_paths")
    if not isinstance(records, list):
        raise RuntimeError("audit harness path records are absent")
    expected_records = _harness_path_records(erratum_commit)
    if records != expected_records:
        raise RuntimeError("audit harness path identity mismatch")
    if payload.get("oracle") != {
        "path": PR8_ORACLE_PATH.relative_to(ROOT).as_posix(),
        "sha256": PR8_ORACLE_SHA256,
    }:
        raise RuntimeError("audit harness oracle identity mismatch")
    if _sha256(PR8_ORACLE_PATH) != PR8_ORACLE_SHA256:
        raise RuntimeError("PR #8 oracle bytes changed")
    provenance = payload.get("invalid_launch_provenance")
    if not isinstance(provenance, Mapping):
        raise RuntimeError("invalid-launch provenance identity is absent")
    if provenance.get("sha256") != INVALID_LAUNCH_PROVENANCE_SHA256:
        raise RuntimeError("invalid-launch provenance identity mismatch")
    if _sha256(INVALID_LAUNCH_PROVENANCE_PATH) != INVALID_LAUNCH_PROVENANCE_SHA256:
        raise RuntimeError("invalid-launch provenance bytes changed")
    if payload.get("audit_identity_sha256") != _combined_audit_identity_sha256(payload):
        raise RuntimeError("combined audit identity hash mismatch")
    result = dict(payload)
    result["file_sha256"] = expected_hash
    return result


def write_audit_harness_erratum_identity() -> dict[str, Any]:
    payload = build_audit_harness_erratum_identity()
    _atomic_json(AUDIT_HARNESS_IDENTITY_PATH, payload)
    file_hash = _sha256(AUDIT_HARNESS_IDENTITY_PATH)
    validated = validate_audit_harness_erratum_identity(
        expected_file_sha256=file_hash
    )
    return {
        "status": "audit_harness_erratum_identity_written_and_verified",
        "path": AUDIT_HARNESS_IDENTITY_PATH.relative_to(ROOT).as_posix(),
        "file_sha256": file_hash,
        "audit_identity_sha256": validated["audit_identity_sha256"],
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def write_optimized_candidate_identity(*, route: Mapping[str, Any]) -> dict[str, Any]:
    payload = build_optimized_candidate_identity(route=route)
    _atomic_json(CANDIDATE_IDENTITY_PATH, payload)
    file_hash = _sha256(CANDIDATE_IDENTITY_PATH)
    validated = validate_optimized_candidate_identity(
        expected_file_sha256=file_hash
    )
    return {
        "status": "optimized_candidate_identity_written_and_verified",
        "path": CANDIDATE_IDENTITY_PATH.relative_to(ROOT).as_posix(),
        "candidate_commit": validated["candidate_commit"],
        "candidate_tree": validated["candidate_tree"],
        "file_sha256": file_hash,
        "numerical_execution_performed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


@contextmanager
def _loaded_pr8_test_only_oracle_solver() -> Iterator[Callable[..., Any]]:
    """Load the byte-locked oracle with scoped ``sys.modules`` registration."""

    if _sha256(PR8_ORACLE_PATH) != PR8_ORACLE_SHA256:
        raise RuntimeError("PR #8 test-only oracle bytes changed")
    specification = importlib.util.spec_from_file_location(
        AUDIT_HARNESS_ORACLE_MODULE_NAME, PR8_ORACLE_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("PR #8 test-only oracle cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    missing = object()
    previous: ModuleType | object = sys.modules.get(
        AUDIT_HARNESS_ORACLE_MODULE_NAME, missing
    )
    sys.modules[AUDIT_HARNESS_ORACLE_MODULE_NAME] = module
    try:
        specification.loader.exec_module(module)
        solver = getattr(module, "solve_sheet_electrical", None)
        if not callable(solver):
            raise RuntimeError("PR #8 test-only oracle solver is unavailable")
        yield solver
    finally:
        if previous is missing:
            sys.modules.pop(AUDIT_HARNESS_ORACLE_MODULE_NAME, None)
        else:
            sys.modules[AUDIT_HARNESS_ORACLE_MODULE_NAME] = previous


def check_audit_harness_loader() -> dict[str, Any]:
    """Exercise the actual runner loader without performing numerical work."""

    previous = sys.modules.get(AUDIT_HARNESS_ORACLE_MODULE_NAME)
    with _loaded_pr8_test_only_oracle_solver() as solver:
        registered = sys.modules.get(AUDIT_HARNESS_ORACLE_MODULE_NAME)
        if registered is None or solver.__module__ != AUDIT_HARNESS_ORACLE_MODULE_NAME:
            raise RuntimeError("oracle was not registered for its complete load scope")
    if sys.modules.get(AUDIT_HARNESS_ORACLE_MODULE_NAME) is not previous:
        raise RuntimeError("oracle module registration was not restored")
    return {
        "status": "audit_harness_loader_pass",
        "oracle_sha256": PR8_ORACLE_SHA256,
        "module_registration_scoped": True,
        "numerical_execution_performed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def _equivalence_output_paths() -> dict[str, Path]:
    return {
        "electrical": PERFORMANCE_OUTPUT_DIR / "electrical_equivalence.csv",
        "interval": PERFORMANCE_OUTPUT_DIR / "interval_equivalence.csv",
        "progression": PERFORMANCE_OUTPUT_DIR / "progression_equivalence.csv",
        "failure": PERFORMANCE_OUTPUT_DIR / "failure_equivalence.csv",
        "summary": EQUIVALENCE_SUMMARY_PATH,
    }


def _require_equivalence_outputs_absent() -> None:
    existing = [path for path in _equivalence_output_paths().values() if path.exists()]
    if EQUIVALENCE_ATTEMPT_PROVENANCE_PATH.exists():
        existing.append(EQUIVALENCE_ATTEMPT_PROVENANCE_PATH)
    if existing:
        raise RuntimeError(
            "refusing to overwrite standard equivalence evidence: "
            + ", ".join(str(path) for path in existing)
        )


def _append_equivalence_attempt_event(event: Mapping[str, Any]) -> None:
    data = json.dumps(dict(event), sort_keys=True, allow_nan=False) + "\n"
    with EQUIVALENCE_ATTEMPT_PROVENANCE_PATH.open(
        "a", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _begin_equivalence_attempt(
    *, candidate_identity: Mapping[str, Any], harness_identity: Mapping[str, Any]
) -> None:
    EQUIVALENCE_ATTEMPT_PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    scheduled = {
        "attempt": 1,
        "event": "SCHEDULED",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_commit": candidate_identity["candidate_commit"],
        "candidate_identity_sha256": candidate_identity["file_sha256"],
        "audit_harness_erratum_commit": harness_identity["erratum_commit"],
        "audit_harness_identity_file_sha256": harness_identity["file_sha256"],
        "audit_identity_sha256": harness_identity["audit_identity_sha256"],
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    data = json.dumps(scheduled, sort_keys=True, allow_nan=False) + "\n"
    with EQUIVALENCE_ATTEMPT_PROVENANCE_PATH.open(
        "x", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _append_equivalence_attempt_event(
        {
            **scheduled,
            "event": "STARTED",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    )


def _validate_equivalence_result(result: Any) -> tuple[str, dict[str, int]]:
    expected_counts = {
        "electrical": 9,
        "interval": 18,
        "progression": 9,
        "failure": 21,
    }
    rows = tuple(result.rows)
    indexes = [int(row.plan_index) for row in rows]
    if indexes != list(range(len(indexes))):
        raise RuntimeError("equivalence rows are missing, duplicated, or out of plan order")
    counts = {
        family: sum(row.family == family for row in rows)
        for family in expected_counts
    }
    summary = result.summary
    if summary.get("plan_identities_valid") is not True:
        raise RuntimeError("equivalence row plan identities are invalid")
    if summary.get("hash_fields_valid") is not True:
        raise RuntimeError("equivalence row hash fields are invalid")
    if summary.get("completed_counts") != counts:
        raise RuntimeError("equivalence completed-count summary mismatch")
    failed = [row for row in rows if not bool(row.passed)]
    if failed:
        if len(failed) != 1 or failed[0] is not rows[-1]:
            raise RuntimeError("valid mismatch did not stop the matrix immediately")
        if summary.get("disposition") != "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR":
            raise RuntimeError("valid mismatch has the wrong disposition")
        if summary.get("failing_plan_index") != failed[0].plan_index:
            raise RuntimeError("valid mismatch plan index is inconsistent")
        if summary.get("failing_sample_id") != failed[0].sample_id:
            raise RuntimeError("valid mismatch sample identity is inconsistent")
        return "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR", counts
    if any(
        not math.isfinite(float(row.maximum_normalized_difference))
        for row in rows
    ):
        raise RuntimeError("passing equivalence evidence contains a non-finite comparison")
    if counts != expected_counts or len(rows) != 57:
        raise RuntimeError("equivalence audit ended incomplete without a valid mismatch")
    if result.summary.get("all_equivalence_votes_pass") is not True:
        raise RuntimeError("complete equivalence audit did not pass all row votes")
    return "GO_FOR_SOURCE_CORRECTED_RUNTIME_READINESS_AUTHORIZATION", counts


def _run_frozen_equivalence(
    candidate_identity_sha256: str,
    audit_harness_identity_sha256: str,
) -> dict[str, Any]:
    """Execute and publish the only authorized valid strict-equivalence audit."""

    _require_equivalence_outputs_absent()
    candidate_identity = validate_frozen_candidate_identity_for_harness(
        expected_file_sha256=candidate_identity_sha256
    )
    harness_identity = validate_audit_harness_erratum_identity(
        expected_file_sha256=audit_harness_identity_sha256
    )
    _validate_loaded_candidate_module_origins()
    resolved = resolve_controller_v2(
        SOURCE_CORRECTED_CONFIG_PATH,
        SOURCE_CORRECTED_CONTROLLER_OVERLAY_PATH,
    )
    _begin_equivalence_attempt(
        candidate_identity=candidate_identity,
        harness_identity=harness_identity,
    )
    audit_started_utc = datetime.now(timezone.utc).isoformat()
    numeric_disposition: str | None = None
    completed_rows: int | None = None
    try:
        with _loaded_pr8_test_only_oracle_solver() as oracle_solver:
            result = run_equivalence_audit(
                oracle_solver=oracle_solver,
                source_config=resolved.base_config,
                resolved_controller=resolved,
                publish=False,
            )
            disposition, completed_counts = _validate_equivalence_result(result)
            numeric_disposition = disposition
            completed_rows = len(result.rows)
            _append_equivalence_attempt_event(
                {
                    "attempt": 1,
                    "event": "NUMERIC_DISPOSITION",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "disposition": disposition,
                    "completed_rows": completed_rows,
                    "completed_counts": completed_counts,
                    "formal_execution_count": 0,
                    "formal_artifact_count": 0,
                }
            )
            worst_row = max(
                result.rows,
                key=lambda row: row.maximum_normalized_difference,
                default=None,
            )
            summary = dict(result.summary)
            summary.update(
                {
                    "status": (
                        "strict_equivalence_pass_pending_runtime_readiness"
                        if disposition
                        == "GO_FOR_SOURCE_CORRECTED_RUNTIME_READINESS_AUTHORIZATION"
                        else "strict_equivalence_failed_fail_fast"
                    ),
                    "disposition": disposition,
                    "execution_validity": "valid",
                    "candidate_identity_sha256": candidate_identity["file_sha256"],
                    "candidate_commit": candidate_identity["candidate_commit"],
                    "candidate_tree": candidate_identity["candidate_tree"],
                    "audit_harness_identity_file_sha256": harness_identity["file_sha256"],
                    "audit_identity_sha256": harness_identity["audit_identity_sha256"],
                    "audit_harness_erratum_commit": harness_identity["erratum_commit"],
                    "audit_harness_erratum_tree": harness_identity["erratum_tree"],
                    "performance_repair_preregistration_sha256": (
                        PERFORMANCE_PREREGISTRATION_SHA256
                    ),
                    "audit_harness_addendum_sha256": _sha256(
                        AUDIT_HARNESS_ADDENDUM_PATH
                    ),
                    "base_source_corrected_config_sha256": _sha256(
                        SOURCE_CORRECTED_CONFIG_PATH
                    ),
                    "controller_overlay_sha256": _sha256(
                        SOURCE_CORRECTED_CONTROLLER_OVERLAY_PATH
                    ),
                    "PR8_test_only_oracle_sha256": PR8_ORACLE_SHA256,
                    "completed_counts": completed_counts,
                    "maximum_normalized_relative_difference": (
                        0.0 if worst_row is None else worst_row.maximum_normalized_difference
                    ),
                    "maximum_difference_plan_index": (
                        None if worst_row is None else worst_row.plan_index
                    ),
                    "maximum_difference_sample_id": (
                        None if worst_row is None else worst_row.sample_id
                    ),
                    "maximum_difference_field": (
                        None if worst_row is None else worst_row.worst_field
                    ),
                    "failure_topology_exact_match": all(
                        row.exact_mismatch_count == 0
                        for row in result.rows
                        if row.family == "failure"
                    ),
                    "evidence_table_sha256": {
                        f"{family}_equivalence.csv": hashlib.sha256(
                            table.encode("utf-8")
                        ).hexdigest()
                        for family, table in result.tables.items()
                    },
                    "audit_events": ["SCHEDULED", "STARTED", "COMPLETED"],
                    "audit_started_utc": audit_started_utc,
                    "audit_finished_utc": datetime.now(timezone.utc).isoformat(),
                    "valid_frozen_equivalence_audit_attempt": 1,
                    "automatic_retry": "forbidden",
                    "runtime_readiness_executed": False,
                    "runtime_readiness_authorization_status": (
                        "pending_fresh_user_authorization"
                    ),
                    "formal_execution_count": 0,
                    "formal_artifact_count": 0,
                }
            )
            if set(result.tables) != {
                "electrical",
                "interval",
                "progression",
                "failure",
            }:
                raise RuntimeError("equivalence table family set is invalid")
            if not math.isfinite(
                float(summary["maximum_normalized_relative_difference"])
            ):
                raise RuntimeError("equivalence summary maximum is non-finite")
            for family, table in result.tables.items():
                if not isinstance(table, str) or not table.startswith("plan_index,"):
                    raise RuntimeError(f"invalid equivalence CSV serialization: {family}")

            PERFORMANCE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            for family, table in result.tables.items():
                atomic_write_equivalence_text(
                    PERFORMANCE_OUTPUT_DIR / f"{family}_equivalence.csv", table
                )
            atomic_write_equivalence_json(EQUIVALENCE_SUMMARY_PATH, summary)
            _append_equivalence_attempt_event(
                {
                    "attempt": 1,
                    "event": "COMPLETED",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "disposition": disposition,
                    "completed_rows": completed_rows,
                    "output_sha256": {
                        path.name: _sha256(path)
                        for path in _equivalence_output_paths().values()
                    },
                    "formal_execution_count": 0,
                    "formal_artifact_count": 0,
                }
            )
        return summary
    except Exception as error:
        disposition = (
            "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
            if numeric_disposition == "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
            else "INVALID_PREFLIGHT_INFRASTRUCTURE"
        )
        invalid_summary = {
            "task_id": "PHASE1_V2_EQUIVALENCE_AUDIT_HARNESS_ERRATUM_AND_VALID_AUDIT",
            "schema_version": "geophase_phase1_v2_strict_equivalence_result_v1",
            "status": (
                "valid_numeric_mismatch_with_later_publication_error"
                if disposition == "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
                else "invalid_preflight_infrastructure"
            ),
            "disposition": disposition,
            "execution_validity": (
                "valid_numeric_mismatch"
                if disposition == "NO_GO_EQUIVALENT_PERFORMANCE_REPAIR"
                else "invalid"
            ),
            "audit_events": ["SCHEDULED", "STARTED", "INTERRUPTED"],
            "audit_started_utc": audit_started_utc,
            "audit_finished_utc": datetime.now(timezone.utc).isoformat(),
            "equivalence_rows_completed": completed_rows,
            "equivalence_votes_cast": completed_rows,
            "error_class": type(error).__name__,
            "error_message": str(error),
            "candidate_identity_sha256": candidate_identity["file_sha256"],
            "candidate_commit": candidate_identity["candidate_commit"],
            "candidate_tree": candidate_identity["candidate_tree"],
            "audit_harness_identity_file_sha256": harness_identity["file_sha256"],
            "audit_identity_sha256": harness_identity["audit_identity_sha256"],
            "valid_frozen_equivalence_audit_attempt": 1,
            "automatic_retry": "forbidden",
            "runtime_readiness_executed": False,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
        try:
            _append_equivalence_attempt_event(
                {
                    "attempt": 1,
                    "event": "FAILED",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "primary_disposition": disposition,
                    "completed_rows": completed_rows,
                    "error_class": type(error).__name__,
                    "error_message": str(error),
                    "formal_execution_count": 0,
                    "formal_artifact_count": 0,
                }
            )
        except Exception as provenance_error:
            invalid_summary["provenance_append_error"] = {
                "error_class": type(provenance_error).__name__,
                "error_message": str(provenance_error),
            }
        if not EQUIVALENCE_SUMMARY_PATH.exists():
            atomic_write_equivalence_json(EQUIVALENCE_SUMMARY_PATH, invalid_summary)
        return invalid_summary


def validate_active_route() -> dict[str, Any]:
    stage = _yaml(STAGE_PATH)
    active = stage["active_bundle"]
    if stage["formal_execution_count"] != 0 or stage["formal_artifact_count"] != 0:
        raise RuntimeError("source-corrected route cannot consume formal execution")
    if active["source_correction_preregistration_commit"] != SOURCE_PREREGISTRATION_COMMIT:
        raise RuntimeError("source-correction preregistration commit changed")
    if _sha256(PREREGISTRATION_PATH) != SOURCE_PREREGISTRATION_SHA256:
        raise RuntimeError("source-correction preregistration bytes changed")
    if active["high_bias_15V_compatibility_alias"] != "forbidden":
        raise RuntimeError("historical 15 V alias became selectable")
    if not PERFORMANCE_PREREGISTRATION_PATH.is_file():
        raise RuntimeError("performance-repair preregistration is absent")
    if _sha256(PERFORMANCE_PREREGISTRATION_PATH) != PERFORMANCE_PREREGISTRATION_SHA256:
        raise RuntimeError("performance-repair preregistration bytes changed")
    identity = _strict_json(IDENTITY_PATH)
    if identity["formal_execution_count"] != 0 or identity["formal_artifact_count"] != 0:
        raise RuntimeError("resolved v3 identity contains formal evidence")
    if active["runner"] != (
        "scripts/run_geophase_phase1_v2_source_corrected_performance_readiness.py"
    ):
        raise RuntimeError("active route no longer selects this runner")
    return {
        "active_checkpoint": stage["current_checkpoint"],
        "active_high_bias_protocol": active["active_high_bias_protocol"],
        "resolved_runtime_identity_sha256": identity[
            "resolved_runtime_identity_sha256"
        ],
        "source_correction_preregistration_commit": SOURCE_PREREGISTRATION_COMMIT,
        "performance_repair_preregistration_sha256": (
            PERFORMANCE_PREREGISTRATION_SHA256
        ),
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def validate_performance_contract() -> dict[str, Any]:
    contract = _yaml(PERFORMANCE_PREREGISTRATION_PATH)
    readiness = contract["readiness_execution"]
    c3 = readiness["C3"]
    if contract["execution_boundary"]["formal_execution_count"] != 0:
        raise RuntimeError("performance contract consumed formal execution")
    if contract["execution_boundary"]["formal_artifact_count"] != 0:
        raise RuntimeError("performance contract contains formal artifacts")
    if readiness["global_wall_clock_s_from_C1_start"] != 900:
        raise RuntimeError("runtime-preflight budget changed")
    if readiness["worker_backstop_from_C1_start_s"] != 880:
        raise RuntimeError("worker backstop changed")
    if c3["single_interval_samples"] != 18:
        raise RuntimeError("C3 interval count changed")
    if c3["short_trajectory_plans"] != 9:
        raise RuntimeError("C3 trajectory count changed")
    if c3["C2_reused_trajectory_plans"] != 1:
        raise RuntimeError("C2 reuse count changed")
    if c3["independently_submitted_pool_samples"] != 26:
        raise RuntimeError("C3 independent submission count changed")
    if c3["high_conductive_protocol"] != "high_bias_lock_15p8V":
        raise RuntimeError("source-corrected high-bias protocol changed")
    return contract


def build_source_corrected_c3_plan() -> tuple[dict[str, Any], ...]:
    """Return 27 countable plans, exactly one of which reuses C2."""

    protocols = {
        "equilibrium": ("zero_drive", 1.0),
        "legal_critical": ("transition_probe_12p5V", 12.5),
        "high_conductive": ("high_bias_lock_15p8V", 15.8),
    }
    plans: list[dict[str, Any]] = []
    for level in (1, 2, 4):
        for state in ("equilibrium", "legal_critical", "high_conductive"):
            protocol, voltage_scale = protocols[state]
            for interval_class in ("base", "floor"):
                plans.append(
                    {
                        "plan_index": len(plans),
                        "sample_id": (
                            f"PRE-C3-INTERVAL-L{level}-{state}-{interval_class}"
                        ),
                        "sample_kind": "single_interval",
                        "spatial_level": level,
                        "state_id": state,
                        "interval_class": interval_class,
                        "protocol": protocol,
                        "protocol_V_scale_V": voltage_scale,
                        "reuse_C2": False,
                        "pool_submit": True,
                    }
                )
    for level in (1, 2, 4):
        for state in ("equilibrium", "legal_critical", "high_conductive"):
            protocol, voltage_scale = protocols[state]
            reuse = level == 1 and state == "legal_critical"
            plans.append(
                {
                    "plan_index": len(plans),
                    "sample_id": (
                        "PRE-CTRL-CRITICAL-TRAJECTORY"
                        if reuse
                        else f"PRE-C3-TRAJECTORY-L{level}-{state}"
                    ),
                    "sample_kind": "short_trajectory",
                    "spatial_level": level,
                    "state_id": state,
                    "interval_class": None,
                    "protocol": protocol,
                    "protocol_V_scale_V": voltage_scale,
                    "reuse_C2": reuse,
                    "pool_submit": not reuse,
                }
            )
    if len(plans) != 27:
        raise AssertionError("C3 plan must contain 18 intervals plus 9 trajectories")
    if sum(item["pool_submit"] for item in plans) != INDEPENDENT_C3_SAMPLE_COUNT:
        raise AssertionError("C3 plan must submit exactly 26 independent samples")
    if sum(item["reuse_C2"] for item in plans) != 1:
        raise AssertionError("C3 plan must contain exactly one C2 reuse")
    return tuple(plans)


def bind_c3_plan_inputs(
    plans: Sequence[Mapping[str, Any]],
    *,
    route: Mapping[str, Any],
    candidate_identity_sha256: str,
) -> tuple[dict[str, Any], ...]:
    candidate_hash = _require_sha256(
        candidate_identity_sha256, "candidate_identity_sha256"
    )
    bound: list[dict[str, Any]] = []
    for item in plans:
        row = dict(item)
        if not str(row.get("sample_id", "")).startswith("PRE-"):
            raise RuntimeError("readiness plans must use PRE-* IDs")
        input_identity = {
            "plan": row,
            "resolved_runtime_identity_sha256": route[
                "resolved_runtime_identity_sha256"
            ],
            "performance_repair_preregistration_sha256": (
                PERFORMANCE_PREREGISTRATION_SHA256
            ),
            "candidate_identity_sha256": candidate_hash,
        }
        row["input_sha256"] = _mapping_sha256(input_identity)
        bound.append(row)
    return tuple(bound)


def validate_frozen_equivalence_summary(
    path: Path,
    *,
    expected_file_sha256: str,
    expected_candidate_identity_sha256: str,
) -> dict[str, Any]:
    """Validate the narrow PASS interface required before readiness."""

    expected_file = _require_sha256(
        expected_file_sha256, "expected equivalence summary SHA-256"
    )
    expected_candidate = _require_sha256(
        expected_candidate_identity_sha256, "expected candidate identity SHA-256"
    )
    if _sha256(path) != expected_file:
        raise RuntimeError("equivalence summary file hash mismatch")
    summary = _strict_json(path)
    if summary.get("status") != (
        "strict_equivalence_pass_pending_runtime_readiness"
    ):
        raise RuntimeError("frozen equivalence summary did not pass")
    if summary.get("all_equivalence_votes_pass") is not True:
        raise RuntimeError("equivalence gates are not all PASS")
    if summary.get("candidate_identity_sha256") != expected_candidate:
        raise RuntimeError("equivalence candidate identity mismatch")
    if summary.get("performance_repair_preregistration_sha256") != (
        PERFORMANCE_PREREGISTRATION_SHA256
    ):
        raise RuntimeError("equivalence preregistration identity mismatch")
    maximum = summary.get("maximum_normalized_relative_difference")
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
        raise RuntimeError("equivalence maximum relative difference is absent")
    if not math.isfinite(float(maximum)) or float(maximum) > EQUIVALENCE_GATE:
        raise RuntimeError("equivalence parity gate failed")
    if summary.get("formal_execution_count") != 0:
        raise RuntimeError("equivalence summary consumed formal execution")
    if summary.get("formal_artifact_count") != 0:
        raise RuntimeError("equivalence summary created a formal artifact")
    if "audit_harness_identity_file_sha256" in summary:
        if summary.get("disposition") != (
            "GO_FOR_SOURCE_CORRECTED_RUNTIME_READINESS_AUTHORIZATION"
        ):
            raise RuntimeError("versioned audit has the wrong GO disposition")
        expected_counts = {
            "electrical": 9,
            "interval": 18,
            "progression": 9,
            "failure": 21,
        }
        if summary.get("complete") is not True:
            raise RuntimeError("versioned audit is incomplete")
        if summary.get("completed_total") != 57:
            raise RuntimeError("versioned audit did not complete 57 rows")
        if summary.get("completed_counts") != expected_counts:
            raise RuntimeError("versioned audit family counts are invalid")
        if summary.get("failure_topology_exact_match") is not True:
            raise RuntimeError("versioned audit failure topology differs")
        if summary.get("valid_frozen_equivalence_audit_attempt") != 1:
            raise RuntimeError("versioned audit attempt identity is invalid")
        if summary.get("automatic_retry") != "forbidden":
            raise RuntimeError("versioned audit permits retry")
        if summary.get("runtime_readiness_authorization_status") != (
            "pending_fresh_user_authorization"
        ):
            raise RuntimeError("versioned audit bypasses readiness authorization")
    result = dict(summary)
    result["file_sha256"] = expected_file
    return result


def validate_worker_rss_measurement(
    path: Path,
    *,
    candidate_identity_sha256: str,
) -> dict[str, Any]:
    expected_candidate = _require_sha256(
        candidate_identity_sha256, "candidate_identity_sha256"
    )
    payload = _strict_json(path)
    if payload.get("status") != "PASS":
        raise RuntimeError("worker RSS microbenchmark did not pass")
    if payload.get("candidate_identity_sha256") != expected_candidate:
        raise RuntimeError("worker RSS candidate identity mismatch")
    peak = payload.get("measured_peak_worker_RSS_bytes")
    if isinstance(peak, bool) or not isinstance(peak, int) or peak <= 0:
        raise RuntimeError("worker RSS measurement is invalid")
    if payload.get("formal_execution_count") != 0:
        raise RuntimeError("worker RSS measurement consumed formal execution")
    if payload.get("formal_artifact_count") != 0:
        raise RuntimeError("worker RSS measurement created a formal artifact")
    result = dict(payload)
    result["file_sha256"] = _sha256(path)
    return result


def _apply_single_thread_environment() -> None:
    for name, value in _THREAD_ENVIRONMENT.items():
        os.environ[name] = value


def _worker_initializer(event_queue: Any, start_acks: Any) -> None:
    global _WORKER_EVENT_QUEUE, _WORKER_START_ACKS
    _apply_single_thread_environment()
    _WORKER_EVENT_QUEUE = event_queue
    _WORKER_START_ACKS = start_acks


def _resolve_entrypoint(specification: str) -> Callable[..., Any]:
    if not isinstance(specification, str) or specification.count(":") != 1:
        raise RuntimeError("task entrypoint must use module:function syntax")
    module_name, function_name = specification.split(":", 1)
    if not module_name or not function_name:
        raise RuntimeError("task entrypoint must use module:function syntax")
    function = getattr(importlib.import_module(module_name), function_name, None)
    if not callable(function):
        raise RuntimeError("task entrypoint is not callable")
    return function


def _synthetic_worker(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS",
        "payload": {
            "sample_kind": plan["sample_kind"],
            "spatial_level": plan["spatial_level"],
            "state_id": plan["state_id"],
            "synthetic_orchestration_only": True,
        },
    }


def _c3_worker_envelope(
    plan: Mapping[str, Any], worker_entrypoint: str
) -> dict[str, Any]:
    event = {
        "state": "STARTED",
        "plan_index": int(plan["plan_index"]),
        "sample_id": str(plan["sample_id"]),
        "PID": os.getpid(),
        "input_sha256": str(plan["input_sha256"]),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    if _WORKER_EVENT_QUEUE is None or _WORKER_START_ACKS is None:
        raise RuntimeError("worker provenance queue was not initialized")
    _WORKER_EVENT_QUEUE.put(event)
    while not bool(_WORKER_START_ACKS.get(int(plan["plan_index"]), False)):
        # STARTED must be durable in the parent journal before numerics begin.
        # The parent backstop owns termination if it cannot acknowledge.
        import time

        time.sleep(0.001)
    function = (
        _synthetic_worker
        if worker_entrypoint == "synthetic"
        else _resolve_entrypoint(worker_entrypoint)
    )
    task_started_s = perf_counter()
    result = function(dict(plan))
    observed_sample_wall_time_s = perf_counter() - task_started_s
    if not isinstance(result, Mapping):
        raise RuntimeError("C3 worker result must be a mapping")
    result = dict(result)
    if isinstance(result.get("payload"), Mapping):
        result["payload"] = {
            **dict(result["payload"]),
            "observed_sample_wall_time_s": observed_sample_wall_time_s,
            "timing_semantics": PERFORMANCE_TIMING_SEMANTICS,
        }
    return result


def _terminate_executor_process_tree(executor: Any) -> None:
    processes = list(getattr(executor, "_processes", {}).values())
    for process in processes:
        pid = getattr(process, "pid", None)
        if not isinstance(pid, int) or pid <= 0:
            continue
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif getattr(process, "is_alive", lambda: False)():
            process.terminate()
    executor.shutdown(wait=False, cancel_futures=True)


def _drain_started_events(
    event_queue: Any,
    *,
    journal: ReadinessProvenanceJournal,
    started_pids: dict[int, int],
    expected: Mapping[int, Mapping[str, Any]],
    start_acks: Any,
    block_timeout_s: float = 0.0,
) -> None:
    first = True
    while True:
        try:
            if first and block_timeout_s > 0.0:
                event = event_queue.get(timeout=block_timeout_s)
            else:
                event = event_queue.get_nowait()
        except queue.Empty:
            return
        first = False
        if not isinstance(event, Mapping) or event.get("state") != "STARTED":
            raise RuntimeError("worker provenance event schema mismatch")
        plan_index = int(event["plan_index"])
        item = expected.get(plan_index)
        if item is None:
            raise RuntimeError("worker started an unregistered plan")
        if event.get("sample_id") != item["sample_id"]:
            raise RuntimeError("worker sample identity mismatch")
        if event.get("input_sha256") != item["input_sha256"]:
            raise RuntimeError("worker input hash mismatch")
        pid = int(event["PID"])
        if plan_index in started_pids:
            raise RuntimeError("worker emitted a duplicate STARTED event")
        journal.append(
            "STARTED",
            plan_index=plan_index,
            sample_id=str(item["sample_id"]),
            PID=pid,
            input_sha256=str(item["input_sha256"]),
            timestamp_utc=str(event["timestamp_utc"]),
        )
        started_pids[plan_index] = pid
        start_acks[plan_index] = True


def _mark_unfinished_failed(
    *,
    journal: ReadinessProvenanceJournal,
    plans: Sequence[Mapping[str, Any]],
    terminal_indices: set[int],
    started_pids: Mapping[int, int],
    classification: str,
) -> None:
    parent_pid = os.getpid()
    for item in plans:
        plan_index = int(item["plan_index"])
        if plan_index in terminal_indices:
            continue
        journal.append(
            "FAILED",
            plan_index=plan_index,
            sample_id=str(item["sample_id"]),
            PID=int(started_pids.get(plan_index, parent_pid)),
            input_sha256=str(item["input_sha256"]),
            error_classification=classification,
        )
        terminal_indices.add(plan_index)


def run_c3_persistent_spawn_pool(
    plans: Sequence[Mapping[str, Any]],
    *,
    worker_count: int,
    worker_entrypoint: str,
    output_dir: Path,
    preflight_started_s: float,
    clock: Callable[[], float] = perf_counter,
    backstop_s: float = WORKER_BACKSTOP_S,
) -> dict[str, Any]:
    """Run one bounded spawn pool with parent-only journal publication."""

    submitted = tuple(dict(item) for item in plans if item.get("pool_submit"))
    if len(submitted) != INDEPENDENT_C3_SAMPLE_COUNT:
        raise RuntimeError("C3 pool must receive exactly 26 independent samples")
    if tuple(item["plan_index"] for item in submitted) != tuple(
        sorted(item["plan_index"] for item in submitted)
    ):
        raise RuntimeError("C3 samples must be submitted in plan_index order")
    output_dir = Path(output_dir)
    sample_dir = output_dir / "samples"
    journal_path = output_dir / "provenance_journal.jsonl"
    if journal_path.exists() or sample_dir.exists():
        raise RuntimeError("one-shot C3 readiness evidence already exists")
    sample_dir.mkdir(parents=True, exist_ok=False)
    journal = ReadinessProvenanceJournal(journal_path)
    parent_pid = os.getpid()
    expected = {int(item["plan_index"]): item for item in submitted}
    terminal_indices: set[int] = set()
    started_pids: dict[int, int] = {}
    completed: list[dict[str, Any]] = []
    active: dict[Any, dict[str, Any]] = {}
    next_index = 0
    _apply_single_thread_environment()
    context = multiprocessing.get_context("spawn")
    manager = context.Manager()
    event_queue = manager.Queue()
    start_acks = manager.dict()
    executor = ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=context,
        initializer=_worker_initializer,
        initargs=(event_queue, start_acks),
    )

    # The complete plan is journaled before the first pool submission.  This
    # makes a never-started plan distinguishable from an interrupted worker,
    # while actual submissions still occur strictly in plan_index order.
    for item in submitted:
        journal.append(
            "SCHEDULED",
            plan_index=int(item["plan_index"]),
            sample_id=str(item["sample_id"]),
            PID=parent_pid,
            input_sha256=str(item["input_sha256"]),
        )

    def schedule_one() -> None:
        nonlocal next_index
        item = submitted[next_index]
        future = executor.submit(_c3_worker_envelope, item, worker_entrypoint)
        active[future] = item
        next_index += 1

    try:
        while next_index < len(submitted) and len(active) < worker_count:
            schedule_one()
        while active:
            if clock() - preflight_started_s >= backstop_s:
                _drain_started_events(
                    event_queue,
                    journal=journal,
                    started_pids=started_pids,
                    expected=expected,
                    start_acks=start_acks,
                )
                _mark_unfinished_failed(
                    journal=journal,
                    plans=submitted,
                    terminal_indices=terminal_indices,
                    started_pids=started_pids,
                    classification="performance_budget_backstop",
                )
                _terminate_executor_process_tree(executor)
                return {
                    "status": "FAIL",
                    "disposition": "NO_GO_RUNTIME",
                    "failure_class": "performance_budget",
                    "completed_samples": tuple(sorted(completed, key=lambda row: row["plan_index"])),
                }
            _drain_started_events(
                event_queue,
                journal=journal,
                started_pids=started_pids,
                expected=expected,
                start_acks=start_acks,
            )
            done, _ = wait(tuple(active), timeout=0.05, return_when=FIRST_COMPLETED)
            if not done:
                continue
            for future in sorted(done, key=lambda item: active[item]["plan_index"]):
                item = active.pop(future)
                plan_index = int(item["plan_index"])
                _drain_started_events(
                    event_queue,
                    journal=journal,
                    started_pids=started_pids,
                    expected=expected,
                    start_acks=start_acks,
                    block_timeout_s=0.25 if plan_index not in started_pids else 0.0,
                )
                if plan_index not in started_pids:
                    raise RuntimeError("worker completed without a STARTED event")
                try:
                    result = future.result()
                except Exception as error:
                    journal.append(
                        "FAILED",
                        plan_index=plan_index,
                        sample_id=str(item["sample_id"]),
                        PID=started_pids[plan_index],
                        input_sha256=str(item["input_sha256"]),
                        error_classification="unexpected_worker_crash",
                    )
                    terminal_indices.add(plan_index)
                    _mark_unfinished_failed(
                        journal=journal,
                        plans=submitted,
                        terminal_indices=terminal_indices,
                        started_pids=started_pids,
                        classification="cancelled_after_infrastructure_failure",
                    )
                    _terminate_executor_process_tree(executor)
                    return {
                        "status": "INVALID",
                        "disposition": "INVALID_PREFLIGHT_INFRASTRUCTURE",
                        "failure_class": "unexpected_worker_crash",
                        "error": f"{type(error).__name__}: {error}",
                        "completed_samples": tuple(sorted(completed, key=lambda row: row["plan_index"])),
                    }
                if result.get("status") == "FAIL":
                    failure_class = str(result.get("failure_class", "numerical_integrity"))
                    if failure_class not in _VALID_RUNTIME_FAILURE_CLASSES:
                        failure_class = "numerical_integrity"
                    journal.append(
                        "FAILED",
                        plan_index=plan_index,
                        sample_id=str(item["sample_id"]),
                        PID=started_pids[plan_index],
                        input_sha256=str(item["input_sha256"]),
                        error_classification=failure_class,
                    )
                    terminal_indices.add(plan_index)
                    _mark_unfinished_failed(
                        journal=journal,
                        plans=submitted,
                        terminal_indices=terminal_indices,
                        started_pids=started_pids,
                        classification="cancelled_after_valid_sample_failure",
                    )
                    _terminate_executor_process_tree(executor)
                    return {
                        "status": "FAIL",
                        "disposition": "NO_GO_RUNTIME",
                        "failure_class": failure_class,
                        "failed_sample_id": item["sample_id"],
                        "completed_samples": tuple(sorted(completed, key=lambda row: row["plan_index"])),
                    }
                if result.get("status") != "PASS" or not isinstance(
                    result.get("payload"), Mapping
                ):
                    raise RuntimeError("worker returned an invalid result schema")
                document = build_completed_sample_document(
                    plan_index=plan_index,
                    sample_id=str(item["sample_id"]),
                    input_sha256=str(item["input_sha256"]),
                    payload=dict(result["payload"]),
                )
                safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(item["sample_id"]))
                temporary = sample_dir / f"{plan_index:03d}_{safe_name}.json.tmp"
                destination = sample_dir / f"{plan_index:03d}_{safe_name}.json"
                write_completed_sample_temp(temporary, document)
                published = publish_completed_sample(
                    temporary,
                    destination,
                    expected_plan_index=plan_index,
                    expected_sample_id=str(item["sample_id"]),
                    expected_input_sha256=str(item["input_sha256"]),
                )
                journal.append(
                    "COMPLETED",
                    plan_index=plan_index,
                    sample_id=str(item["sample_id"]),
                    PID=started_pids[plan_index],
                    input_sha256=str(item["input_sha256"]),
                    output_sha256=published.output_sha256,
                )
                terminal_indices.add(plan_index)
                completed.append(
                    {
                        **item,
                        "output_sha256": published.output_sha256,
                        "artifact": published.path.as_posix(),
                        "payload": dict(document["payload"]),
                        "observed_sample_wall_time_s": document["payload"][
                            "observed_sample_wall_time_s"
                        ],
                        "timing_semantics": document["payload"][
                            "timing_semantics"
                        ],
                    }
                )
            while next_index < len(submitted) and len(active) < worker_count:
                schedule_one()
        executor.shutdown(wait=True, cancel_futures=False)
        return {
            "status": "PASS",
            "disposition": None,
            "failure_class": None,
            "completed_samples": tuple(sorted(completed, key=lambda row: row["plan_index"])),
            "submitted_sample_count": len(submitted),
            "worker_count": worker_count,
            "start_method": "spawn",
            "worker_threads": 1,
        }
    except (SampleArtifactError, OSError, RuntimeError, ValueError) as error:
        _drain_started_events(
            event_queue,
            journal=journal,
            started_pids=started_pids,
            expected=expected,
            start_acks=start_acks,
        )
        _mark_unfinished_failed(
            journal=journal,
            plans=submitted,
            terminal_indices=terminal_indices,
            started_pids=started_pids,
            classification="schema_hash_or_IO_infrastructure_failure",
        )
        _terminate_executor_process_tree(executor)
        return {
            "status": "INVALID",
            "disposition": "INVALID_PREFLIGHT_INFRASTRUCTURE",
            "failure_class": "schema_hash_or_IO_infrastructure_failure",
            "error": f"{type(error).__name__}: {error}",
            "completed_samples": tuple(sorted(completed, key=lambda row: row["plan_index"])),
        }
    finally:
        manager.shutdown()


def _not_reached(reason: str) -> dict[str, Any]:
    return {"status": "NOT_REACHED", "reason": reason}


def _validate_gate_result(result: Any, label: str) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise RuntimeError(f"{label} result must be a mapping")
    row = dict(result)
    if row.get("status") not in {"PASS", "FAIL", "INVALID"}:
        raise RuntimeError(f"{label} result has an invalid status")
    if row.get("formal_execution_count", 0) != 0:
        raise RuntimeError(f"{label} consumed formal execution")
    if row.get("formal_artifact_count", 0) != 0:
        raise RuntimeError(f"{label} created a formal artifact")
    return row


def _failure_summary(
    *,
    started_s: float,
    clock: Callable[[], float],
    C1: Mapping[str, Any],
    C2: Mapping[str, Any],
    C3: Mapping[str, Any],
    disposition: str,
    failure_class: str,
    equivalence: Mapping[str, Any],
) -> dict[str, Any]:
    if disposition not in _VALID_DISPOSITIONS:
        raise RuntimeError("runner produced an unregistered disposition")
    return {
        "task_id": "PHASE1_V2_SOURCE_CORRECTED_PERFORMANCE_CLOSURE",
        "schema_version": "phase1_v2_source_corrected_readiness_summary_v1",
        "status": "FAIL" if disposition != "INVALID_PREFLIGHT_INFRASTRUCTURE" else "INVALID",
        "disposition": disposition,
        "failure_class": failure_class,
        "C1": dict(C1),
        "C2": dict(C2),
        "C3": dict(C3),
        "equivalence_summary_sha256": equivalence["file_sha256"],
        "candidate_identity_sha256": equivalence["candidate_identity_sha256"],
        "performance_timing_semantics": PERFORMANCE_TIMING_SEMANTICS,
        "preflight_wall_clock_s": clock() - started_s,
        "preflight_wall_clock_limit_s": PREFLIGHT_LIMIT_S,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "formal_campaign_authorized": False,
    }


def execute_readiness_orchestration(
    hooks: Mapping[str, Any],
    *,
    route: Mapping[str, Any],
    equivalence: Mapping[str, Any],
    worker_rss: Mapping[str, Any],
    output_dir: Path,
    clock: Callable[[], float] = perf_counter,
    c3_pool_runner: Callable[..., Mapping[str, Any]] = run_c3_persistent_spawn_pool,
) -> dict[str, Any]:
    """Execute C1/C2 barriers, one C3 pool, dormant runner, and forecast."""

    required = {
        "run_c1",
        "run_c2",
        "measure_launch_environment",
        "c3_worker_entrypoint",
        "run_dormant_runner",
        "build_forecast",
    }
    if set(hooks) != required:
        raise RuntimeError("readiness hook interface mismatch")
    if not all(callable(hooks[name]) for name in required - {"c3_worker_entrypoint"}):
        raise RuntimeError("readiness hook is not callable")
    if not isinstance(hooks["c3_worker_entrypoint"], str):
        raise RuntimeError("C3 worker entrypoint must be module:function")
    plans = bind_c3_plan_inputs(
        build_source_corrected_c3_plan(),
        route=route,
        candidate_identity_sha256=equivalence["candidate_identity_sha256"],
    )
    started_s = clock()

    def finish(summary: dict[str, Any]) -> dict[str, Any]:
        elapsed_before_publication = clock() - started_s
        conservative_wall_clock = (
            elapsed_before_publication + PARENT_FINALIZATION_RESERVE_S
        )
        summary["preflight_wall_clock_before_atomic_publication_s"] = (
            elapsed_before_publication
        )
        summary["preflight_wall_clock_s"] = conservative_wall_clock
        summary["preflight_wall_clock_measurement"] = (
            "conservative_upper_bound_including_parent_atomic_finalization_reserve"
        )
        summary["parent_atomic_finalization_reserve_s"] = (
            PARENT_FINALIZATION_RESERVE_S
        )
        if (
            conservative_wall_clock > PREFLIGHT_LIMIT_S
            and summary.get("disposition")
            == "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION"
        ):
            summary["status"] = "FAIL"
            summary["disposition"] = "NO_GO_RUNTIME"
            summary["failure_class"] = "performance_budget"
        normalized = json.loads(
            json.dumps(summary, sort_keys=True, allow_nan=False)
        )
        _atomic_json(Path(output_dir) / "readiness_summary.json", normalized)
        return normalized

    try:
        C1 = _validate_gate_result(
            hooks["run_c1"](PREFLIGHT_LIMIT_S), "C1"
        )
    except Exception as error:
        C1 = {
            "status": "INVALID",
            "failure_class": "C1_infrastructure_failure",
            "error": f"{type(error).__name__}: {error}",
        }
    if C1["status"] != "PASS":
        disposition = (
            "INVALID_PREFLIGHT_INFRASTRUCTURE"
            if C1["status"] == "INVALID"
            else "NO_GO_RUNTIME"
        )
        failure_class = (
            str(C1.get("failure_class", "infrastructure"))
            if C1["status"] == "INVALID"
            else "numerical_integrity"
        )
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=_not_reached("C1_not_passed"),
            C3=_not_reached("C1_not_passed"),
            disposition=disposition,
            failure_class=failure_class,
            equivalence=equivalence,
        ))
    try:
        C2 = _validate_gate_result(
            hooks["run_c2"](
                max(0.0, PREFLIGHT_LIMIT_S - (clock() - started_s))
            ),
            "C2",
        )
    except Exception as error:
        C2 = {
            "status": "INVALID",
            "failure_class": "C2_infrastructure_failure",
            "error": f"{type(error).__name__}: {error}",
        }
    if C2["status"] != "PASS":
        disposition = (
            "INVALID_PREFLIGHT_INFRASTRUCTURE"
            if C2["status"] == "INVALID"
            else "NO_GO_RUNTIME"
        )
        failure_class = (
            str(C2.get("failure_class", "infrastructure"))
            if C2["status"] == "INVALID"
            else "numerical_integrity"
        )
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=_not_reached("C2_not_passed"),
            disposition=disposition,
            failure_class=failure_class,
            equivalence=equivalence,
        ))
    if C2.get("sample_id") != "PRE-CTRL-CRITICAL-TRAJECTORY":
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=_not_reached("C2_reuse_identity_invalid"),
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="schema_or_hash_corruption",
            equivalence=equivalence,
        ))
    try:
        _require_sha256(C2.get("input_sha256"), "C2 input_sha256")
        _require_sha256(C2.get("output_sha256"), "C2 output_sha256")
        c2_wall = float(C2["observed_sample_wall_time_s"])
        if not math.isfinite(c2_wall) or c2_wall <= 0.0:
            raise RuntimeError("C2 observed wall time is invalid")
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=_not_reached("C2_reuse_evidence_invalid"),
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="schema_or_hash_corruption",
            equivalence=equivalence,
        ))
    if clock() - started_s >= WORKER_BACKSTOP_S:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=_not_reached("worker_backstop_reached_before_pool"),
            disposition="NO_GO_RUNTIME",
            failure_class="performance_budget",
            equivalence=equivalence,
        ))
    try:
        environment = hooks["measure_launch_environment"]()
    except Exception as error:
        environment = {
            "invalid": True,
            "error": f"{type(error).__name__}: {error}",
        }
    if not isinstance(environment, Mapping):
        environment = {"invalid": True, "error": "launch environment is not a mapping"}
    if environment.get("invalid") is True:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=_not_reached("launch_environment_invalid"),
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="environment_measurement_failure",
            equivalence=equivalence,
        ))
    try:
        worker_count = select_c3_worker_count(
            environment["physical_core_count"],
            environment["launch_available_RAM_bytes"],
            worker_rss["measured_peak_worker_RSS_bytes"],
            independent_sample_count=INDEPENDENT_C3_SAMPLE_COUNT,
        )
    except C3WorkerMemoryLimitError:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3={"status": "FAIL", "reason": "zero_memory_worker_limit"},
            disposition="NO_GO_RUNTIME",
            failure_class="memory",
            equivalence=equivalence,
        ))
    except (KeyError, TypeError, ValueError) as error:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=_not_reached("worker_count_input_invalid"),
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="environment_measurement_failure",
            equivalence=equivalence,
        ))
    try:
        C3 = dict(
            c3_pool_runner(
                plans,
                worker_count=worker_count,
                worker_entrypoint=hooks["c3_worker_entrypoint"],
                output_dir=Path(output_dir),
                preflight_started_s=started_s,
                clock=clock,
                backstop_s=WORKER_BACKSTOP_S,
            )
        )
    except Exception as error:
        C3 = {
            "status": "INVALID",
            "disposition": "INVALID_PREFLIGHT_INFRASTRUCTURE",
            "failure_class": "broken_process_pool",
            "error": f"{type(error).__name__}: {error}",
        }
    if C3.get("status") != "PASS":
        disposition = str(C3.get("disposition", "INVALID_PREFLIGHT_INFRASTRUCTURE"))
        failure_class = str(C3.get("failure_class", "infrastructure"))
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=C3,
            disposition=disposition,
            failure_class=failure_class,
            equivalence=equivalence,
        ))
    completed = list(C3.get("completed_samples", ()))
    interval_count = sum(row.get("sample_kind") == "single_interval" for row in completed)
    trajectory_count = sum(row.get("sample_kind") == "short_trajectory" for row in completed)
    if interval_count != 18 or trajectory_count != 8:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=C3,
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="schema_or_hash_corruption",
            equivalence=equivalence,
        ))
    if any(
        row.get("timing_semantics") != PERFORMANCE_TIMING_SEMANTICS
        or not isinstance(row.get("observed_sample_wall_time_s"), (int, float))
        or isinstance(row.get("observed_sample_wall_time_s"), bool)
        or not math.isfinite(float(row["observed_sample_wall_time_s"]))
        or float(row["observed_sample_wall_time_s"]) <= 0.0
        for row in completed
    ):
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=C3,
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="schema_or_hash_corruption",
            equivalence=equivalence,
        ))
    required_payload_fields = {
        "accepted_steps",
        "achieved_time_s",
        "peak_RSS_bytes",
        "streaming_output_bytes",
        "timing_telemetry",
    }
    if any(
        not isinstance(row.get("payload"), Mapping)
        or not required_payload_fields.issubset(row["payload"])
        or isinstance(row["payload"]["accepted_steps"], bool)
        or not isinstance(row["payload"]["accepted_steps"], int)
        or row["payload"]["accepted_steps"] <= 0
        or not isinstance(row["payload"]["timing_telemetry"], Mapping)
        for row in completed
    ):
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=C3,
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="sample_payload_schema_invalid",
            equivalence=equivalence,
        ))
    if clock() - started_s >= WORKER_BACKSTOP_S:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=C3,
            disposition="NO_GO_RUNTIME",
            failure_class="performance_budget",
            equivalence=equivalence,
        ))
    try:
        dormant = _validate_gate_result(
            hooks["run_dormant_runner"](), "dormant runner"
        )
    except Exception as error:
        dormant = {
            "status": "INVALID",
            "failure_class": "dormant_runner_infrastructure_failure",
            "error": f"{type(error).__name__}: {error}",
        }
    if dormant["status"] != "PASS":
        disposition = (
            "INVALID_PREFLIGHT_INFRASTRUCTURE"
            if dormant["status"] == "INVALID"
            else "NO_GO_RUNTIME"
        )
        failure_class = (
            str(dormant.get("failure_class", "infrastructure"))
            if dormant["status"] == "INVALID"
            else "dormant_runner"
        )
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3={**C3, "dormant_runner": dormant},
            disposition=disposition,
            failure_class=failure_class,
            equivalence=equivalence,
        ))
    try:
        forecast = hooks["build_forecast"](
            tuple(completed), dict(C2), worker_count
        )
    except Exception as error:
        forecast = {
            "invalid": True,
            "error": f"{type(error).__name__}: {error}",
        }
    if not isinstance(forecast, Mapping):
        forecast = {"invalid": True, "error": "forecast is not a mapping"}
    forecast = dict(forecast)
    if forecast.get("invalid") is True:
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3={**C3, "forecast": forecast},
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="forecast_infrastructure_failure",
            equivalence=equivalence,
        ))
    if (
        forecast.get("timing_semantics") != PERFORMANCE_TIMING_SEMANTICS
        or forecast.get("uses_observed_sample_wall_time_only") is not True
        or forecast.get("stage_timings_summed_for_forecast") is not False
    ):
        return finish(_failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3={**C3, "forecast": forecast},
            disposition="INVALID_PREFLIGHT_INFRASTRUCTURE",
            failure_class="forecast_timing_semantics_invalid",
            equivalence=equivalence,
        ))
    performance_failure: str | None = None
    if float(forecast.get("predicted_p95_makespan_s", math.inf)) > 11520.0:
        performance_failure = "performance_budget"
    if float(forecast.get("predicted_hard_makespan_s", math.inf)) > 14400.0:
        performance_failure = "performance_budget"
    if forecast.get("RSS_gate_pass") is not True:
        performance_failure = "memory"
    if forecast.get("disk_gate_pass") is not True:
        performance_failure = "disk"
    elapsed = clock() - started_s
    if elapsed > PREFLIGHT_LIMIT_S:
        performance_failure = "performance_budget"
    C3.update(
        {
            "single_intervals_completed": interval_count,
            "short_trajectories_completed_in_pool": trajectory_count,
            "short_trajectories_completed_with_C2_reuse": trajectory_count + 1,
            "C2_reuse_count": 1,
            "worker_count": worker_count,
            "launch_environment": dict(environment),
            "dormant_runner": dormant,
            "forecast": forecast,
        }
    )
    if performance_failure is not None:
        summary = _failure_summary(
            started_s=started_s,
            clock=clock,
            C1=C1,
            C2=C2,
            C3=C3,
            disposition="NO_GO_RUNTIME",
            failure_class=performance_failure,
            equivalence=equivalence,
        )
    else:
        summary = {
            "task_id": "PHASE1_V2_SOURCE_CORRECTED_PERFORMANCE_CLOSURE",
            "schema_version": "phase1_v2_source_corrected_readiness_summary_v1",
            "status": "PASS",
            "disposition": "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
            "failure_class": None,
            "C1": C1,
            "C2": C2,
            "C3": C3,
            "equivalence_summary_sha256": equivalence["file_sha256"],
            "candidate_identity_sha256": equivalence["candidate_identity_sha256"],
            "performance_timing_semantics": PERFORMANCE_TIMING_SEMANTICS,
            "preflight_wall_clock_s": elapsed,
            "preflight_wall_clock_limit_s": PREFLIGHT_LIMIT_S,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
            "formal_campaign_authorized": False,
        }
    if summary["disposition"] not in _VALID_DISPOSITIONS:
        raise RuntimeError("readiness disposition is not registered")
    return finish(summary)


def _invoke_task_adapter(
    entrypoint: str, *, mode: str, payload: Mapping[str, Any]
) -> Any:
    return _resolve_entrypoint(entrypoint)(mode=mode, payload=dict(payload))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-route", action="store_true")
    modes.add_argument("--write-candidate-identity", action="store_true")
    modes.add_argument("--check-audit-harness", action="store_true")
    modes.add_argument("--write-audit-harness-identity", action="store_true")
    modes.add_argument("--run-equivalence", action="store_true")
    modes.add_argument("--measure-worker-rss", action="store_true")
    modes.add_argument("--run-readiness", action="store_true")
    parser.add_argument("--candidate-identity-sha256")
    parser.add_argument("--audit-harness-identity-sha256")
    parser.add_argument("--equivalence-summary", type=Path, default=EQUIVALENCE_SUMMARY_PATH)
    parser.add_argument("--equivalence-summary-sha256")
    parser.add_argument("--worker-rss-summary", type=Path, default=WORKER_RSS_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if not any(
        (
            args.check_route,
            args.write_candidate_identity,
            args.check_audit_harness,
            args.write_audit_harness_identity,
            args.run_equivalence,
            args.measure_worker_rss,
            args.run_readiness,
        )
    ):
        raise SystemExit(
            "no execution mode selected; choose --check-route, "
            "--write-candidate-identity, --check-audit-harness, "
            "--write-audit-harness-identity, --run-equivalence, "
            "--measure-worker-rss, or --run-readiness"
        )
    route = validate_active_route()
    contract = validate_performance_contract()
    if args.check_route:
        payload = {
            **route,
            "C3_countable_plan_count": len(build_source_corrected_c3_plan()),
            "C3_independent_pool_samples": INDEPENDENT_C3_SAMPLE_COUNT,
            "numerical_execution_performed": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.write_candidate_identity:
        result = write_optimized_candidate_identity(route=route)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return
    if args.check_audit_harness:
        result = check_audit_harness_loader()
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return
    if args.write_audit_harness_identity:
        result = write_audit_harness_erratum_identity()
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return
    if args.run_equivalence:
        if not args.candidate_identity_sha256:
            raise SystemExit(
                "--run-equivalence requires --candidate-identity-sha256"
            )
        if not args.audit_harness_identity_sha256:
            raise SystemExit(
                "--run-equivalence requires --audit-harness-identity-sha256"
            )
        candidate_identity = _require_sha256(
            args.candidate_identity_sha256, "candidate_identity_sha256"
        )
        audit_harness_identity = _require_sha256(
            args.audit_harness_identity_sha256,
            "audit_harness_identity_sha256",
        )
        result = _run_frozen_equivalence(
            candidate_identity,
            audit_harness_identity,
        )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return
    if args.measure_worker_rss:
        if not args.candidate_identity_sha256:
            raise SystemExit(
                "--measure-worker-rss requires --candidate-identity-sha256"
            )
        candidate_identity = _require_sha256(
            args.candidate_identity_sha256, "candidate_identity_sha256"
        )
        result = _invoke_task_adapter(
            TASK_ADAPTER_ENTRYPOINT,
            mode="measure_worker_rss",
            payload={
                "route": route,
                "performance_contract": contract,
                "candidate_identity_sha256": candidate_identity,
            },
        )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return
    if not args.candidate_identity_sha256 or not args.equivalence_summary_sha256:
        raise SystemExit(
            "--run-readiness requires frozen candidate and equivalence summary SHA-256 values"
        )
    equivalence = validate_frozen_equivalence_summary(
        args.equivalence_summary,
        expected_file_sha256=args.equivalence_summary_sha256,
        expected_candidate_identity_sha256=args.candidate_identity_sha256,
    )
    worker_rss = validate_worker_rss_measurement(
        args.worker_rss_summary,
        candidate_identity_sha256=args.candidate_identity_sha256,
    )
    hooks = _invoke_task_adapter(
        TASK_ADAPTER_ENTRYPOINT,
        mode="readiness_hooks",
        payload={
            "route": route,
            "performance_contract": contract,
            "equivalence": equivalence,
            "worker_rss": worker_rss,
        },
    )
    if not isinstance(hooks, Mapping):
        raise SystemExit("readiness task adapter did not return the locked hook interface")
    summary = execute_readiness_orchestration(
        hooks,
        route=route,
        equivalence=equivalence,
        worker_rss=worker_rss,
        output_dir=READINESS_OUTPUT_DIR,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
