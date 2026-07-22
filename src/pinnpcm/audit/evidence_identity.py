"""Portable verification for immutable historical evidence locks.

Historical preregistrations in this repository include SHA-256 values that
were calculated from Windows worktree bytes.  Git stores the same tracked text
with LF line endings, so a clean checkout can be semantically identical while
having a different raw SHA-256.  This module accepts only these identities:

1. the exact preregistered raw bytes; or
2. a clean current or historical Git object whose bytes differ from that raw
   lock only by LF/CRLF encoding; or
3. an exact declared raw/canonical pair for a tracked text artifact whose
   original Windows bytes used mixed line endings; or
4. an exact, declared legacy exception for a non-scientific routing file whose
   lost worktree byte sequence was never stored as a Git object.

It never normalizes whitespace, JSON, CSV fields, ordering, or numeric text.
Untracked local assets remain exact-byte-only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
LEGACY_EXCEPTION_PATH = ROOT / "configs/legacy_nonportable_lock_exceptions_v1.json"
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_lf_bytes(payload: bytes) -> bytes:
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_crlf_bytes(payload: bytes) -> bytes:
    return canonical_lf_bytes(payload).replace(b"\n", b"\r\n")


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=True,
        text=not binary,
    )
    if binary:
        return result.stdout
    return str(result.stdout).strip()


@lru_cache(maxsize=None)
def _tracked_at_head(root_text: str, relative: str) -> bool:
    root = Path(root_text)
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


@lru_cache(maxsize=None)
def _blob_at(root_text: str, commit: str, relative: str) -> tuple[str, bytes]:
    root = Path(root_text)
    oid = str(_git(root, "rev-parse", f"{commit}:{relative}"))
    payload = bytes(_git(root, "show", f"{commit}:{relative}", binary=True))
    return oid, payload


def _expected_matches_blob(expected_sha256: str, payload: bytes, *, text: bool) -> bool:
    candidates = {sha256_bytes(payload)}
    if text:
        candidates.add(sha256_bytes(canonical_lf_bytes(payload)))
        candidates.add(sha256_bytes(canonical_crlf_bytes(payload)))
    return expected_sha256.upper() in candidates


@lru_cache(maxsize=None)
def _declared_legacy_exception(
    root_text: str, relative: str, expected_sha256: str
) -> dict[str, Any] | None:
    path = Path(root_text) / "configs/legacy_nonportable_lock_exceptions_v1.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "legacy_nonportable_lock_exceptions_v1":
        raise ValueError("Unsupported legacy lock exception schema")
    for record in payload.get("exceptions", []):
        if (
            record.get("path") == relative
            and str(record.get("expected_sha256", "")).upper() == expected_sha256.upper()
            and record.get("scientific_vote_changed") is False
            and record.get("raw_hash_rewritten") is False
        ):
            return dict(record)
    return None


@lru_cache(maxsize=None)
def _declared_portable_text_identity(
    root_text: str, relative: str, expected_sha256: str
) -> dict[str, Any] | None:
    path = Path(root_text) / "configs/portable_text_lock_identities_v1.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "portable_text_lock_identities_v1":
        raise ValueError("Unsupported portable text identity schema")
    for record in payload.get("records", []):
        if (
            record.get("path") == relative
            and str(record.get("raw_sha256", "")).upper() == expected_sha256.upper()
            and record.get("raw_bytes_observed_during_contract_creation") is True
            and record.get("raw_hash_rewritten") is False
            and record.get("allowed_transformation") == "line_endings_only"
        ):
            return dict(record)
    return None


@lru_cache(maxsize=None)
def _find_historical_blob(
    root_text: str,
    relative: str,
    expected_sha256: str,
    text: bool,
) -> tuple[str, str, str] | None:
    root = Path(root_text)
    result = subprocess.run(
        ["git", "log", "--all", "--format=%H", "--", relative],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    seen_oids: set[str] = set()
    for commit in (line.strip() for line in result.stdout.splitlines() if line.strip()):
        try:
            oid, payload = _blob_at(root_text, commit, relative)
        except subprocess.CalledProcessError:
            continue
        if oid in seen_oids:
            continue
        seen_oids.add(oid)
        if _expected_matches_blob(expected_sha256, payload, text=text):
            return commit, oid, sha256_bytes(canonical_lf_bytes(payload) if text else payload)
    return None


def verify_evidence_lock(
    path: Path | str,
    expected_sha256: str,
    *,
    expected_size: int | None = None,
    root: Path = ROOT,
    allow_historical_revision: bool = False,
) -> dict[str, Any]:
    """Verify one preregistered lock without weakening its byte identity."""

    root = root.resolve()
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else root / candidate
    expected = str(expected_sha256).upper()
    relative = _relative(candidate, root)
    text = candidate.suffix.lower() in TEXT_SUFFIXES or candidate.name == ".gitignore"
    result: dict[str, Any] = {
        "path": relative,
        "expected_sha256": expected,
        "expected_size": None if expected_size is None else int(expected_size),
        "text_newline_portability": text,
        "allow_historical_revision": bool(allow_historical_revision),
        "passed": False,
        "mode": "missing",
    }
    if not candidate.is_file():
        return result

    current = candidate.read_bytes()
    current_sha = sha256_bytes(current)
    result.update({"current_sha256": current_sha, "current_size": len(current)})
    size_exact = expected_size is None or len(current) == int(expected_size)
    if current_sha == expected and size_exact:
        result.update({"passed": True, "mode": "current_raw_exact"})
        return result

    root_text = str(root)
    current_matches_head = False
    if _tracked_at_head(root_text, relative):
        try:
            # Resolve HEAD before entering the blob cache.  Caching the literal
            # string "HEAD" would return a stale object after a new commit in
            # the same Python process.
            head_commit = str(_git(root, "rev-parse", "HEAD"))
            head_oid, head_payload = _blob_at(root_text, head_commit, relative)
        except subprocess.CalledProcessError:
            head_commit, head_oid, head_payload = "", "", b""
        current_matches_head = (
            canonical_lf_bytes(current) == canonical_lf_bytes(head_payload)
            if text
            else current == head_payload
        )
        result["current_matches_head"] = current_matches_head
        expected_matches_head = _expected_matches_blob(expected, head_payload, text=text)
        if current_matches_head and expected_matches_head:
            result.update(
                {
                    "passed": True,
                    "mode": "current_git_blob_newline_equivalent",
                    "matched_commit": head_commit,
                    "git_blob_oid": head_oid,
                    "canonical_sha256": sha256_bytes(
                        canonical_lf_bytes(head_payload) if text else head_payload
                    ),
                }
            )
            return result
        declared_text = _declared_portable_text_identity(root_text, relative, expected)
        if current_matches_head and declared_text is not None:
            canonical_sha = sha256_bytes(canonical_lf_bytes(head_payload))
            declared_raw_size = int(declared_text["raw_byte_size"])
            declared_canonical_size = int(declared_text["canonical_lf_byte_size"])
            raw_size_matches = expected_size is None or declared_raw_size == int(expected_size)
            if (
                canonical_sha == str(declared_text["canonical_lf_sha256"]).upper()
                and len(canonical_lf_bytes(head_payload)) == declared_canonical_size
                and raw_size_matches
            ):
                result.update(
                    {
                        "passed": True,
                        "mode": "declared_mixed_newline_equivalent",
                        "matched_commit": head_commit,
                        "git_blob_oid": head_oid,
                        "canonical_sha256": canonical_sha,
                        "raw_bytes_observed_during_contract_creation": True,
                    }
                )
                return result

    # A historical definition can explain a preregistered lock only from a
    # clean checkout.  Otherwise an arbitrary dirty replacement could inherit
    # the identity of an unrelated historical Git object.
    if allow_historical_revision and current_matches_head:
        historical = _find_historical_blob(root_text, relative, expected, text)
        if historical is not None:
            commit, oid, canonical_sha = historical
            result.update(
                {
                    "passed": True,
                    "mode": "historical_git_object",
                    "matched_commit": commit,
                    "git_blob_oid": oid,
                    "canonical_sha256": canonical_sha,
                }
            )
            return result
        exception = _declared_legacy_exception(root_text, relative, expected)
        if exception is not None:
            result.update(
                {
                    "passed": True,
                    "mode": "declared_nonportable_legacy_exception",
                    "exception_status": exception["status"],
                    "exception_reason": exception["reason"],
                    "scientific_vote_changed": False,
                }
            )
            return result

    result["mode"] = "identity_mismatch"
    return result


def assert_evidence_lock(
    path: Path | str,
    expected_sha256: str,
    *,
    expected_size: int | None = None,
    root: Path = ROOT,
    allow_historical_revision: bool = False,
) -> dict[str, Any]:
    result = verify_evidence_lock(
        path,
        expected_sha256,
        expected_size=expected_size,
        root=root,
        allow_historical_revision=allow_historical_revision,
    )
    if not result["passed"]:
        raise AssertionError(
            f"Evidence identity mismatch for {result['path']}: "
            f"expected={result['expected_sha256']} observed={result.get('current_sha256', 'MISSING')}"
        )
    return result
