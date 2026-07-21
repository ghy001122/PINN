from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from pinnpcm.audit.qiu_llp_source_contract import build_source_contract_summary


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "76970488118612f6ccf9c3cbf6cb17946ca0d999"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _git_blob(path: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", f"{BASE_COMMIT}:{path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _protected_records() -> list[dict[str, Any]]:
    original = json.loads((ROOT / "outputs/tables/e1f_qiu_author_anchor_preregistration.json").read_text(encoding="utf-8"))
    correction = json.loads((ROOT / "outputs/tables/e1fr_qiu_source_equation_correction_preregistration.json").read_text(encoding="utf-8"))
    authoritative: dict[str, dict[str, Any]] = {}
    for key in ["frozen_gt_records", "raw_source_records", "m40_protected_records", "m40r_protected_records", "preregistration_implementation_records"]:
        for record in original.get(key, []):
            authoritative[record["path"]] = record
    for record in correction.get("implementation_records", []):
        authoritative.setdefault(record["path"], record)
    additional = {
        "src/pinnpcm/physics/vo2_thermal_neuristor.py": "protected_production_physics",
        "outputs/tables/e1fr_qiu_source_equation_correction.json": "historical_e1fr_result",
        "outputs/tables/e1fr_qiu_source_equation_correction.csv": "historical_e1fr_result",
        "outputs/tables/e1fr_effective_coordinate_preflight.json": "historical_e1fr_result",
        "docs/codex_reports/e1fr_qiu_source_equation_correction_results.md": "historical_e1fr_report",
        "docs/manuscript/main_submission_v1.md": "superseded_manuscript_snapshot",
        "outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json": "locked_gamma_sub_evidence",
        "outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json": "locked_gamma_sub_evidence",
        "outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json": "locked_gamma_sub_evidence",
    }
    for path, evidence_class in additional.items():
        authoritative.setdefault(path, {"path": path, "evidence_class": evidence_class})
    records: list[dict[str, Any]] = []
    for rel, source in sorted(authoritative.items()):
        path = ROOT / rel
        if not path.exists() or path.is_symlink():
            raise RuntimeError(f"protected evidence missing or symbolic link: {rel}")
        stat_before = path.stat()
        expected = source.get("sha256")
        actual = _sha256(path)
        if expected is not None and actual != str(expected).upper():
            raise RuntimeError(f"protected evidence hash mismatch: {rel}")
        blob = _git_blob(rel)
        stat_after = path.stat()
        records.append({
            "path": rel,
            "evidence_class": source.get("evidence_class", "historically_preregistered_protected_evidence"),
            "tracked": blob is not None,
            "git_blob_oid": blob,
            "byte_size": stat_after.st_size,
            "sha256": actual,
            "expected_sha256_source": "historical_preregistration" if expected is not None else "newly_observed_not_previously_anchored",
            "copy_required": blob is None,
            "mtime_ns_before": stat_before.st_mtime_ns,
            "mtime_ns_after": stat_after.st_mtime_ns,
            "status": "pass" if expected is not None else "newly_observed_not_previously_anchored",
        })
    return records


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    summary, rows = build_source_contract_summary(config)
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    outputs = config["outputs"]
    summary_path = ROOT / outputs["summary"]
    cases_path = ROOT / outputs["cases"]
    amendment_path = ROOT / outputs["amendment"]
    manifest_path = ROOT / outputs["protected_manifest"]
    for path in [summary_path, cases_path, amendment_path, manifest_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with cases_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    amendment = {
        "schema_version": "e1f_source_contract_amendment_v2",
        "generated_at_utc": summary["generated_at_utc"],
        "main_submission_v1_byte_modified": False,
        "e1f": {
            "preregistered_literal_contract_compliance": False,
            "scientific_vote": False,
            "atanh_transform_reference_supported": bool(summary["blocking_gates_pass"]),
            "full_qiu_author_algorithm_equivalence": "unverified",
            "fig2b_extraction_valid": False,
        },
        "e1fr": {
            "role": "qiu_2024_printed_s3_sensitivity",
            "solver_parity": "passed",
            "clean_s1_source_curve_match": "failed",
            "status": "failed_but_informative",
            "external_quantitative_validation": "unsupported",
            "canonical_or_general_llp_refuted": False,
        },
        "root_cause_boundary": "The mismatch is non-identifying among the printed formula, reversal-event rules, undisclosed author implementation details, initial conditions, parameter applicability, and digitization error.",
        "qiu_author_intent_inferred": False,
        "qiu_author_code_verified": False,
    }
    amendment_path.write_text(json.dumps(amendment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protected = _protected_records()
    manifest = {
        "schema_version": "submission_protected_evidence_manifest_v1",
        "base_commit": BASE_COMMIT,
        "generated_at_utc": summary["generated_at_utc"],
        "record_count": len(protected),
        "all_previously_anchored_records_match": all(item["status"] != "pass" or item["mtime_ns_before"] == item["mtime_ns_after"] for item in protected),
        "records": protected,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/qiu_llp_source_contract.yaml")
    args = parser.parse_args()
    summary = run(args.config.resolve())
    print(json.dumps({"blocking_gates_pass": summary["blocking_gates_pass"], "formula_contract_evaluations": summary["formula_contract_evaluations"]}, sort_keys=True))


if __name__ == "__main__":
    main()
