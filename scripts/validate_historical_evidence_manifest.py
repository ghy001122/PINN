"""Validate immutable historical evidence locks without recomputing experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "configs" / "historical_evidence_manifest_v1.json"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def _git_text(*args: str) -> str:
    return _git_bytes(*args).decode("utf-8").strip()


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "historical_evidence_manifest_v1":
        raise ValueError("Unsupported historical evidence manifest schema")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Historical evidence manifest requires entries")
    required = {"historic_commit", "artifact_path", "git_blob_oid", "sha256", "claim_scope", "current_file_required"}
    for index, entry in enumerate(entries):
        missing = required - set(entry)
        if missing:
            raise ValueError(f"Manifest entry {index} is missing {sorted(missing)}")
        if len(str(entry["historic_commit"])) != 40 or len(str(entry["git_blob_oid"])) != 40:
            raise ValueError(f"Manifest entry {index} has a non-full Git identifier")
        if len(str(entry["sha256"])) != 64:
            raise ValueError(f"Manifest entry {index} has an invalid SHA-256")
    return payload


def validate_manifest(path: Path = DEFAULT_MANIFEST, *, verify_history: bool = False) -> dict[str, Any]:
    manifest = load_manifest(path)
    current_checks: list[dict[str, Any]] = []
    history_checks: list[dict[str, Any]] = []
    failures: list[str] = []
    for entry in manifest["entries"]:
        artifact = str(entry["artifact_path"])
        expected_sha = str(entry["sha256"]).lower()
        if bool(entry["current_file_required"]):
            current_path = ROOT / artifact
            if current_path.is_file():
                observed_blob = _git_text("hash-object", f"--path={artifact}", artifact)
                observed_worktree_sha = _sha256_file(current_path)
            else:
                observed_blob = None
                observed_worktree_sha = None
            passed = observed_blob == str(entry["git_blob_oid"])
            current_checks.append(
                {
                    "artifact_path": artifact,
                    "expected_blob_oid": entry["git_blob_oid"],
                    "observed_worktree_blob_oid": observed_blob,
                    "expected_canonical_sha256": expected_sha,
                    "observed_worktree_sha256": observed_worktree_sha,
                    "line_ending_note": "Git filtered blob identity is authoritative for text files; raw worktree SHA may differ under core.autocrlf.",
                    "passed": passed,
                }
            )
            if not passed:
                failures.append(f"current:{artifact}")
        if verify_history:
            commit = str(entry["historic_commit"])
            spec = f"{commit}:{artifact}"
            try:
                observed_oid = _git_text("rev-parse", spec)
                payload = _git_bytes("show", spec)
                observed_sha = _sha256_bytes(payload)
            except subprocess.CalledProcessError:
                observed_oid = None
                observed_sha = None
            passed = observed_oid == str(entry["git_blob_oid"]) and observed_sha == expected_sha
            history_checks.append(
                {
                    "historic_commit": commit,
                    "artifact_path": artifact,
                    "expected_blob_oid": entry["git_blob_oid"],
                    "observed_blob_oid": observed_oid,
                    "expected_sha256": expected_sha,
                    "observed_sha256": observed_sha,
                    "passed": passed,
                }
            )
            if not passed:
                failures.append(f"history:{spec}")
    result = {
        "schema_version": "historical_evidence_manifest_validation_v1",
        "manifest_path": str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
        "entry_count": len(manifest["entries"]),
        "current_check_count": len(current_checks),
        "history_check_count": len(history_checks),
        "verify_history": bool(verify_history),
        "all_passed": not failures,
        "failures": failures,
        "current_checks": current_checks,
        "history_checks": history_checks,
    }
    if failures:
        raise RuntimeError("Historical evidence manifest validation failed: " + ", ".join(failures))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--verify-history", action="store_true")
    args = parser.parse_args()
    result = validate_manifest(args.manifest, verify_history=args.verify_history)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
