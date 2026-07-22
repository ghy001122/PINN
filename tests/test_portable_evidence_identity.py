from __future__ import annotations

import subprocess
from pathlib import Path

from pinnpcm.audit.evidence_identity import (
    canonical_crlf_bytes,
    sha256_bytes,
    verify_evidence_lock,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _commit(root: Path, message: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Evidence Test",
            "-c",
            "user.email=evidence-test@example.invalid",
            "commit",
            "-m",
            message,
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_exact_untracked_asset_is_fail_closed(tmp_path: Path) -> None:
    asset = tmp_path / "asset.bin"
    asset.write_bytes(b"locked evidence\x00")
    expected = sha256_bytes(asset.read_bytes())

    exact = verify_evidence_lock(asset, expected, root=tmp_path)
    assert exact["passed"] is True
    assert exact["mode"] == "current_raw_exact"

    asset.write_bytes(b"tampered evidence\x00")
    mismatch = verify_evidence_lock(asset, expected, root=tmp_path)
    assert mismatch["passed"] is False
    assert mismatch["mode"] == "identity_mismatch"


def test_newline_portability_and_historical_lock_require_clean_checkout(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "core.autocrlf", "false")
    definition = tmp_path / "definition.yaml"
    version_one = b"gate: strict\nstatus: locked\n"
    definition.write_bytes(version_one)
    _git(tmp_path, "add", "definition.yaml")
    _commit(tmp_path, "v1")

    crlf_lock = sha256_bytes(canonical_crlf_bytes(version_one))
    portable = verify_evidence_lock(
        definition,
        crlf_lock,
        root=tmp_path,
    )
    assert portable["passed"] is True
    assert portable["mode"] == "current_git_blob_newline_equivalent"

    definition.write_bytes(b"gate: stricter\nstatus: current\n")
    _git(tmp_path, "add", "definition.yaml")
    _commit(tmp_path, "v2")
    historical = verify_evidence_lock(
        definition,
        sha256_bytes(version_one),
        root=tmp_path,
        allow_historical_revision=True,
    )
    assert historical["passed"] is True
    assert historical["mode"] == "historical_git_object"

    definition.write_bytes(b"gate: silently weakened\n")
    dirty = verify_evidence_lock(
        definition,
        sha256_bytes(version_one),
        root=tmp_path,
        allow_historical_revision=True,
    )
    assert dirty["passed"] is False
    assert dirty["mode"] == "identity_mismatch"
