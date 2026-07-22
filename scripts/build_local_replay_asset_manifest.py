"""Build the exact local-only asset contract required for detached replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pinnpcm.audit.evidence_identity import sha256_file


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _record(
    root: Path,
    *,
    path: str,
    expected_sha256: str,
    asset_class: str,
    source: str,
    redistribute_raw: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    local = root / path
    if not local.is_file():
        raise FileNotFoundError(local)
    observed = sha256_file(local)
    expected = expected_sha256.upper()
    if observed != expected:
        raise RuntimeError(f"Asset hash mismatch while building manifest: {path}")
    result: dict[str, Any] = {
        "path": path.replace("\\", "/"),
        "asset_class": asset_class,
        "required_for_local_replay": True,
        "sha256": expected,
        "byte_size": local.stat().st_size,
        "identity": "exact_raw_bytes",
        "source": source,
        "redistribute_raw": bool(redistribute_raw),
    }
    if extra:
        result.update(extra)
    return result


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    qiu = _json(root / "data/external/qiu_2024_thermal_neuristor/manifest.json")
    e1f = _json(root / "outputs/tables/e1f_qiu_author_anchor_preregistration.json")
    m35 = _json(root / "outputs/tables/m35_public_multivoltage_preregistration.json")
    zhang = _json(root / "data/external/vo2_zhang_2024/multivoltage_prereg_manifest_v1.json")
    scis = _json(root / "outputs/tables/gamma_sub_scis_cache_preflight.json")

    records: list[dict[str, Any]] = []
    for source in qiu["sources"]:
        path = source.get("local_raw_path")
        if not path:
            continue
        records.append(
            _record(
                root,
                path=str(path),
                expected_sha256=str(source["sha256"]),
                asset_class="qiu_third_party_pdf",
                source="qiu_2024_drive_and_publisher_contract",
                redistribute_raw=bool(source.get("redistribute_raw", False)),
                extra={
                    "drive_file_id": source.get("drive_file_id"),
                    "drive_url": source.get("drive_url"),
                    "license_or_terms": source.get("license_or_terms"),
                },
            )
        )

    frozen = [
        item
        for item in e1f["frozen_gt_records"]
        if str(item["path"]).startswith("data/processed/gt_v1_acceptance/")
    ]
    if len(frozen) != 6:
        raise RuntimeError(f"Expected six frozen-GT payloads, found {len(frozen)}")
    for item in frozen:
        records.append(
            _record(
                root,
                path=str(item["path"]),
                expected_sha256=str(item["sha256"]),
                asset_class="frozen_gt_v1_1",
                source="e1f_frozen_gt_protection_lock",
                redistribute_raw=False,
            )
        )

    zhang_paths = [
        "data/external/vo2_zhang_2024/raw/nature_source_data.zip",
        "data/external/vo2_zhang_2024/raw/allowed_prelock/Source Data/Fig. 1/Fig. 1b.csv",
        "data/external/vo2_zhang_2024/raw/allowed_prelock/Source Data/Fig. 1/Fig. 1c/Experiment_9V.csv",
        "data/external/vo2_zhang_2024/raw/allowed_prelock/Source Data/Fig. 1/Fig. 1c/Experiment_11V.csv",
        "data/external/vo2_zhang_2024/raw/allowed_prelock/Source Data/Fig. 1/Fig. 1c/Experiment_15V.csv",
        "data/external/vo2_zhang_2024/raw/allowed_prelock/Source Data/Fig. 1/Fig. 1c/Experiment_17V.csv",
    ]
    for path in zhang_paths:
        expected = m35["locked_files"][path]
        records.append(
            _record(
                root,
                path=path,
                expected_sha256=str(expected),
                asset_class="zhang_open_public_input",
                source="m35_public_multivoltage_preregistration",
                redistribute_raw=True,
                extra={"license_id": "CC-BY-4.0"},
            )
        )

    entries = scis.get("entries", [])
    if len(entries) != 36 or int(scis.get("unique_trajectory_count", -1)) != 36:
        raise RuntimeError("SCIS preflight must contain exactly 36 unique cached trajectories")
    seen_paths: set[str] = set()
    for item in entries:
        path = str(item["path"]).replace("\\", "/")
        if path in seen_paths:
            continue
        seen_paths.add(path)
        records.append(
            _record(
                root,
                path=path,
                expected_sha256=str(item["sha256"]),
                asset_class="ceba_solver_generated_trajectory",
                source="gamma_sub_scis_cache_preflight",
                redistribute_raw=False,
                extra={
                    "cache_key": item["cache_key"],
                    "role": item["role"],
                    "protocol": item["protocol"],
                    "coordinate": item["coordinate"],
                },
            )
        )
    if len(seen_paths) != 36:
        raise RuntimeError(f"Expected 36 CEBA trajectory paths, found {len(seen_paths)}")

    sealed = zhang["sealed_members_metadata_only"]
    if len(sealed) != 2 or any(bool(item["content_read_prelock"]) for item in sealed):
        raise RuntimeError("The Zhang 13 V metadata-only seal is not intact")
    sealed_record = {
        "record_id": "zhang_13v_sealed_metadata_only",
        "asset_class": "forbidden_sealed_input",
        "required_for_local_replay": False,
        "archive_path": "data/external/vo2_zhang_2024/raw/nature_source_data.zip",
        "access_policy": "central_directory_metadata_only_no_member_payload_read",
        "members": sealed,
        "scientific_access_authorized": False,
    }

    class_counts: dict[str, int] = {}
    for record in records:
        key = str(record["asset_class"])
        class_counts[key] = class_counts.get(key, 0) + 1
    if len(records) != 50:
        raise RuntimeError(f"Expected 50 required assets, found {len(records)}")
    return {
        "schema_version": "local_replay_asset_manifest_v1",
        "required_asset_count": 50,
        "sealed_metadata_record_count": 1,
        "class_counts": class_counts,
        "records": sorted(records, key=lambda item: str(item["path"])),
        "sealed_metadata_only_records": [sealed_record],
        "boundary": {
            "all_required_assets_are_local_only": True,
            "public_checkout_is_not_standalone_reproducible": True,
            "sealed_13v_member_payload_accessed": False,
            "solver_regeneration_cannot_substitute_for_frozen_bytes": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("configs/local_replay_asset_manifest_v1.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    payload = build_manifest(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "required_asset_count": 50}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
