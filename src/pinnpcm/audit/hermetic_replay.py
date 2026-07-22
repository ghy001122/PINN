"""Fail-closed facts for a detached, asset-injected repository replay."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _read_status(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


@dataclass(frozen=True)
class HermeticReplayInputs:
    root: Path
    expected_commit: str
    status_before_path: Path
    status_after_path: Path
    output_path: Path
    asset_source_root: Path
    required_checkout_paths: tuple[str, ...]


def evaluate_facts(facts: dict[str, bool]) -> dict[str, Any]:
    failures = sorted(key for key, passed in facts.items() if not passed)
    return {
        "status": "pass" if not failures else "fail",
        "all_passed": not failures,
        "failures": failures,
        "facts": facts,
    }


def inspect_hermetic_replay(inputs: HermeticReplayInputs) -> dict[str, Any]:
    root = inputs.root.resolve()
    actual_root_result = _git(root, "rev-parse", "--show-toplevel")
    head_result = _git(root, "rev-parse", "HEAD")
    symbolic_result = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    actual_root = (
        Path(actual_root_result.stdout.strip()).resolve()
        if actual_root_result.returncode == 0
        else None
    )
    actual_head = head_result.stdout.strip() if head_result.returncode == 0 else ""
    status_before = _read_status(inputs.status_before_path)
    status_after = _read_status(inputs.status_after_path)

    import_probe = (
        "import importlib.util,json;"
        "s=importlib.util.find_spec('pinnpcm');"
        "print(json.dumps({'origin':None if s is None else s.origin}))"
    )
    environment = os.environ.copy()
    source_root = root / "src"
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(source_root) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    import_result = subprocess.run(
        [sys.executable, "-c", import_probe],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    try:
        import_origin_text = json.loads(import_result.stdout)["origin"]
        import_origin = None if import_origin_text is None else Path(import_origin_text).resolve()
    except (json.JSONDecodeError, KeyError, TypeError):
        import_origin = None

    required = [root / relative for relative in inputs.required_checkout_paths]
    asset_source = inputs.asset_source_root.resolve()
    facts = {
        "actual_git_root_is_requested_root": actual_root == root,
        "actual_head_matches_expected": actual_head == inputs.expected_commit,
        "head_is_detached": symbolic_result.returncode != 0,
        "status_before_is_clean": status_before == "",
        "status_after_is_clean": status_after == "",
        "status_before_equals_status_after": status_before == status_after,
        "pinnpcm_import_is_inside_checkout_src": bool(
            import_origin is not None and _within(import_origin, source_root)
        ),
        "asset_source_is_external_to_checkout": asset_source != root
        and not _within(asset_source, root),
        "runtime_output_is_external_to_checkout": not _within(inputs.output_path, root),
        "required_config_and_evidence_are_inside_checkout": all(
            path.exists() and _within(path, root) for path in required
        ),
    }
    result = evaluate_facts(facts)
    result.update(
        {
            "schema_version": "m42_hermetic_replay_v1",
            "requested_root": str(root),
            "actual_git_root": None if actual_root is None else str(actual_root),
            "expected_commit": inputs.expected_commit,
            "actual_head": actual_head,
            "symbolic_head": symbolic_result.stdout.strip() or None,
            "pinnpcm_origin": None if import_origin is None else str(import_origin),
            "asset_source_root": str(asset_source),
            "status_before": status_before,
            "status_after": status_after,
            "required_checkout_paths": list(inputs.required_checkout_paths),
        }
    )
    return result


def normalize_required_paths(values: Iterable[object]) -> tuple[str, ...]:
    paths = tuple(str(value).replace("\\", "/") for value in values)
    if not paths or any(Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
        raise ValueError("required checkout paths must be non-empty repository-relative paths")
    return paths
