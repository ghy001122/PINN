"""Build the solver-free Phase 1-v2 ledger schema closure artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator_v3 as predecessor
from pinnpcm.audit import geophase_phase1_v2_ledger_record_schema_v4 as schema


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "ledger_record_schema_closure_v4"
)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_manifest(path: Path) -> dict[str, object]:
    contract = predecessor.load_preregistered_contract_bundle()
    entries = schema.build_ledger_group_manifest(contract)
    payload = schema.ledger_manifest_csv_bytes(entries)
    _atomic_write(path, payload)
    families: dict[str, int] = {}
    for entry in entries:
        families[entry.family] = families.get(entry.family, 0) + 1
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "mechanically_derived_template_count": len(entries),
        "family_counts": dict(sorted(families.items())),
        "template_identity_sha256": schema.canonical_sha256(
            [entry.as_row() for entry in entries]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    arguments = parser.parse_args()
    record = build_manifest(OUTPUT_DIR / "ledger_group_manifest.csv")
    print(json.dumps(record, sort_keys=True))
    if not arguments.manifest_only:
        raise SystemExit(
            "Only --manifest-only is valid before the config, comparator, and report hashes are frozen."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
