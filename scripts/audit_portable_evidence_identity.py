"""Audit newline-portable historical evidence identities without reruns."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from pinnpcm.audit.evidence_identity import verify_evidence_lock


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(path)
    return payload


def _pairs_from_map(mapping: dict[str, Any]) -> Iterable[tuple[str, str, int | None]]:
    for path, expected in mapping.items():
        if isinstance(path, str) and isinstance(expected, str) and len(expected) == 64:
            yield path, expected, None


def collect_locks(root: Path = ROOT) -> list[dict[str, Any]]:
    locks: dict[tuple[str, str], dict[str, Any]] = {}

    def add(path: str, sha256: str, size: int | None, source: str) -> None:
        normalized = path.replace("\\", "/")
        key = (normalized, sha256.upper())
        item = locks.setdefault(
            key,
            {"path": normalized, "sha256": sha256.upper(), "size": size, "sources": []},
        )
        if item["size"] is None and size is not None:
            item["size"] = int(size)
        if source not in item["sources"]:
            item["sources"].append(source)

    protected = _json(root / "outputs/tables/submission_protected_evidence_manifest.json")
    for record in protected["records"]:
        if bool(record.get("tracked")):
            add(
                str(record["path"]),
                str(record["sha256"]),
                int(record["byte_size"]),
                "submission_protected_evidence_manifest",
            )

    prereg_paths = [
        "outputs/tables/e1f_qiu_author_anchor_preregistration.json",
        "outputs/tables/e1fr_qiu_source_equation_correction_preregistration.json",
        "outputs/tables/gamma_sub_scis_preregistration.json",
        "outputs/tables/m35_public_multivoltage_preregistration.json",
        "outputs/tables/m36_event_resolved_orbit_preregistration.json",
        "outputs/tables/m37_preregistration.json",
        "outputs/tables/m37r_preregistration.json",
        "outputs/tables/m40r_qiu_e0_preregistration.json",
    ]
    for relative in prereg_paths:
        payload = _json(root / relative)
        for field in (
            "locked_files",
            "historical_read_only_files",
            "old_m40_protected_hashes",
            "ceba_immutable_hashes",
        ):
            mapping = payload.get(field)
            if isinstance(mapping, dict):
                for path, sha, size in _pairs_from_map(mapping):
                    add(path, sha, size, f"{relative}:{field}")
        for field in (
            "raw_source_records",
            "m40_protected_records",
            "m40r_protected_records",
            "frozen_gt_records",
            "implementation_records",
            "open_curve_records",
        ):
            records = payload.get(field)
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict) and record.get("path") and record.get("sha256"):
                        add(
                            str(record["path"]),
                            str(record["sha256"]),
                            record.get("size_bytes"),
                            f"{relative}:{field}",
                        )

    cpcf = yaml.safe_load(
        (root / "configs/gamma_sub_calibration_protocol_cost_frontier.yaml").read_text(
            encoding="utf-8"
        )
    )
    for record in cpcf["inputs"]:
        add(str(record["path"]), str(record["sha256"]), None, "cpcf_input_lock")

    m37_config = yaml.safe_load(
        (root / "configs/m37_continuous_event_observability.yaml").read_text(encoding="utf-8")
    )
    m37_audit = _json(root / m37_config["outputs"]["semantic_audit"])
    add(
        str(m37_config["historical_inputs"]["m36_summary"]),
        str(m37_audit["source_summary_sha256"]),
        None,
        "m37_semantic_audit_source_summary",
    )
    add(
        str(m37_config["historical_inputs"]["m36_metrics"]),
        str(m37_audit["source_metrics_sha256"]),
        None,
        "m37_semantic_audit_source_metrics",
    )
    return sorted(locks.values(), key=lambda item: (item["path"], item["sha256"]))


def audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for lock in collect_locks(root):
        path = str(lock["path"])
        definition = path == ".gitignore" or path.startswith(
            ("configs/", "scripts/", "src/", "tests/", ".github/")
        )
        result = verify_evidence_lock(
            path,
            str(lock["sha256"]),
            expected_size=lock["size"],
            root=root,
            allow_historical_revision=definition,
        )
        result["sources"] = lock["sources"]
        result["evidence_role"] = "historical_definition" if definition else "preserved_artifact"
        records.append(result)
        if not result["passed"]:
            failures.append(f"{path}:{lock['sha256']}")
    modes: dict[str, int] = {}
    for record in records:
        mode = str(record["mode"])
        modes[mode] = modes.get(mode, 0) + 1
    return {
        "schema_version": "portable_evidence_identity_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "lock_count": len(records),
        "all_passed": not failures,
        "mode_counts": modes,
        "failures": failures,
        "contract": {
            "raw_sha256_changed": False,
            "newline_equivalence_only": True,
            "whitespace_or_semantic_normalization_allowed": False,
            "historical_definition_revisions_resolved_through_git_objects": True,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/tables/portable_evidence_identity_audit.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    result = audit(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"all_passed": result["all_passed"], "lock_count": result["lock_count"]}, indent=2))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
