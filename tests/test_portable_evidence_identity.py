from __future__ import annotations

import json
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


def test_declared_mixed_newline_identity_preserves_raw_lock(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "core.autocrlf", "false")
    definition = tmp_path / "mixed.json"
    canonical = b'{\n  "a": 1,\n  "b": 2\n}\n'
    definition.write_bytes(canonical)
    _git(tmp_path, "add", "mixed.json")
    _commit(tmp_path, "mixed text")
    mixed = b'{\r\n  "a": 1,\n  "b": 2\r\n}\r\n'
    config = tmp_path / "configs" / "portable_text_lock_identities_v1.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "schema_version": "portable_text_lock_identities_v1",
                "records": [
                    {
                        "path": "mixed.json",
                        "raw_sha256": sha256_bytes(mixed),
                        "raw_byte_size": len(mixed),
                        "canonical_lf_sha256": sha256_bytes(canonical),
                        "canonical_lf_byte_size": len(canonical),
                        "allowed_transformation": "line_endings_only",
                        "raw_bytes_observed_during_contract_creation": True,
                        "raw_hash_rewritten": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = verify_evidence_lock(
        definition,
        sha256_bytes(mixed),
        expected_size=len(mixed),
        root=tmp_path,
    )
    assert result["passed"] is True
    assert result["mode"] == "declared_mixed_newline_equivalent"
