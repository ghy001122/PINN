"""Fail-closed verification and copy utility for local replay assets."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from pinnpcm.audit.evidence_identity import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "configs/local_replay_asset_manifest_v1.json"


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "local_replay_asset_manifest_v1":
        raise ValueError("Unsupported local replay asset manifest schema")
    if int(payload.get("required_asset_count", -1)) != 50:
        raise ValueError("The local replay contract requires exactly 50 assets")
    if len(payload.get("records", [])) != 50:
        raise ValueError("The local replay manifest does not contain 50 records")
    return payload


def _validate_ceba(path: Path, record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    try:
        with np.load(path, allow_pickle=False) as payload:
            if set(payload.files) != {"cache_key", "t", "G", "I"}:
                failures.append("ceba_fields")
                return failures
            if str(payload["cache_key"].item()) != str(record["cache_key"]):
                failures.append("ceba_cache_key")
            t = np.asarray(payload["t"], dtype=float)
            g = np.asarray(payload["G"], dtype=float)
            current = np.asarray(payload["I"], dtype=float)
    except (OSError, ValueError) as error:
        return [f"ceba_unreadable:{type(error).__name__}"]
    if t.ndim != 1 or t.size < 2 or g.shape != t.shape or current.shape != t.shape:
        failures.append("ceba_shape")
    if not (np.isfinite(t).all() and np.isfinite(g).all() and np.isfinite(current).all()):
        failures.append("ceba_nonfinite")
    if t.size >= 2 and not np.all(np.diff(t) > 0.0):
        failures.append("ceba_time_order")
    return failures


def verify_assets(
    *,
    root: Path = ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    copy_to: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest = load_manifest(manifest_path)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    copied: list[str] = []
    for record in manifest["records"]:
        relative = str(record["path"])
        source = root / relative
        local_failures: list[str] = []
        if not source.is_file():
            local_failures.append("missing")
        else:
            if source.stat().st_size != int(record["byte_size"]):
                local_failures.append("size")
            if sha256_file(source) != str(record["sha256"]).upper():
                local_failures.append("sha256")
            if record["asset_class"] == "ceba_solver_generated_trajectory":
                local_failures.extend(_validate_ceba(source, record))
        if local_failures:
            failures.extend(f"{relative}:{item}" for item in local_failures)
        elif copy_to is not None:
            destination = copy_to.resolve() / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256_file(destination) != str(record["sha256"]).upper():
                failures.append(f"{relative}:copy_sha256")
            else:
                copied.append(relative)
        checks.append(
            {
                "path": relative,
                "asset_class": record["asset_class"],
                "passed": not local_failures,
                "failures": local_failures,
            }
        )

    sealed_checks: list[dict[str, Any]] = []
    for sealed in manifest["sealed_metadata_only_records"]:
        archive = root / sealed["archive_path"]
        expected_members = {item["member_name"]: item for item in sealed["members"]}
        observed: dict[str, zipfile.ZipInfo] = {}
        if archive.is_file():
            with zipfile.ZipFile(archive) as handle:
                for info in handle.infolist():
                    if info.filename in expected_members:
                        observed[info.filename] = info
        for name, expected in expected_members.items():
            info = observed.get(name)
            passed = bool(
                info
                and info.CRC == int(str(expected["crc32"]), 16)
                and info.file_size == int(expected["uncompressed_size"])
                and info.compress_size == int(expected["compressed_size"])
                and expected["content_read_prelock"] is False
            )
            extracted = root / "data/external/vo2_zhang_2024/raw/allowed_prelock" / name
            passed = passed and not extracted.exists()
            if not passed:
                failures.append(f"sealed_metadata:{name}")
            sealed_checks.append({"member_name": name, "passed": passed})

    return {
        "schema_version": "local_replay_asset_validation_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "required_asset_count": 50,
        "verified_asset_count": sum(bool(item["passed"]) for item in checks),
        "copied_asset_count": len(copied),
        "copy_target": None if copy_to is None else str(copy_to.resolve()),
        "sealed_member_payload_accessed": False,
        "sealed_metadata_checks": sealed_checks,
        "all_passed": not failures,
        "failures": failures,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--copy-to", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_assets(
        root=args.root,
        manifest_path=args.manifest,
        copy_to=args.copy_to,
    )
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else args.root.resolve() / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
