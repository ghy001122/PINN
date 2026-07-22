from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from pinnpcm.audit.evidence_identity import verify_evidence_lock


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
CLAIM_STATUSES = {
    "supported",
    "qualified_supported",
    "failed_but_informative",
    "forbidden",
}


def json_ready(value: Any) -> Any:
    """Convert YAML/Python scalar types to strict deterministic JSON values."""

    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported readiness JSON type: {type(value).__name__}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def normalized_text(text: str) -> str:
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text, flags=re.DOTALL)
    text = text.replace("\\gamma_{\\mathrm{sub}}", "gamma_sub")
    text = text.replace("T_{\\mathrm{sw}}", "T_sw")
    text = text.replace("\\(T_{\\mathrm{sw}}\\)", "T_sw")
    text = text.replace("\\(\\gamma_{\\mathrm{sub}}\\)", "gamma_sub")
    return " ".join(text.split())


def parse_bibtex_keys(text: str) -> set[str]:
    return set(re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)", text))


def parse_citation_keys(text: str) -> set[str]:
    return set(re.findall(r"@([A-Za-z0-9_:.-]+)", text))


def parse_exit_code(text: str) -> int | None:
    matches = re.findall(r"(?im)^exit_code\s*=\s*(-?\d+)\s*$", text)
    return int(matches[-1]) if matches else None


def parse_pytest_counts(text: str) -> dict[str, int]:
    passed = re.findall(r"(\d+)\s+passed", text)
    failed = re.findall(r"(\d+)\s+failed", text)
    smoke_nodes = {
        line.strip().split()[0]
        for line in text.splitlines()
        if "smoke" in line.lower() and re.search(r"\bPASSED\b", line)
    }
    return {
        "passed": int(passed[-1]) if passed else 0,
        "failed": int(failed[-1]) if failed else 0,
        "test_only_smoke_runs": len(smoke_nodes),
    }


def read_portable_log(path: Path) -> str:
    """Read UTF-8 or native Windows PowerShell UTF-16 evidence logs."""

    payload = path.read_bytes()
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        return payload.decode("utf-16")
    if payload.startswith(b"\xef\xbb\xbf"):
        return payload.decode("utf-8-sig")
    return payload.decode("utf-8", errors="replace")


def git_is_tracked(root: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative_path],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def audit_claim_rows(root: Path, manuscript_text: str, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_manuscript = normalized_text(manuscript_text)
    rows: list[dict[str, Any]] = []
    for claim in claims:
        evidence_paths: list[str] = []
        evidence_hashes: list[str] = []
        evidence_modes: list[str] = []
        evidence_verified = True
        for record in claim["evidence"]:
            relative = record["path"]
            expected = record["sha256"].upper()
            path = root / relative
            actual = sha256_file(path) if path.is_file() else "MISSING"
            identity = verify_evidence_lock(
                path,
                expected,
                root=root,
                allow_historical_revision=False,
            )
            evidence_paths.append(relative)
            evidence_hashes.append(actual)
            evidence_modes.append(str(identity["mode"]))
            evidence_verified &= bool(identity["passed"])
        sentence_found = normalized_text(claim["sentence"]) in normalized_manuscript
        rows.append(
            {
                "claim_id": claim["claim_id"],
                "status": claim["status"],
                "sentence": claim["sentence"],
                "sentence_found": sentence_found,
                "evidence_paths": ";".join(evidence_paths),
                "evidence_sha256": ";".join(evidence_hashes),
                "evidence_identity_modes": ";".join(evidence_modes),
                "evidence_verified": evidence_verified,
                "gate_pass": sentence_found and evidence_verified and claim["status"] in CLAIM_STATUSES,
            }
        )
    return rows


def audit_figure_manifest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    identity_modes: dict[str, int] = {}

    def verify_record(record: dict[str, Any]) -> None:
        relative = str(record["path"])
        path = root / relative
        if not path.is_file():
            failures.append(f"missing:{relative}")
            return
        identity = verify_evidence_lock(
            path,
            str(record["sha256"]),
            expected_size=record.get("bytes"),
            root=root,
            allow_historical_revision=False,
        )
        mode = str(identity["mode"])
        identity_modes[mode] = identity_modes.get(mode, 0) + 1
        if not identity["passed"]:
            failures.append(f"identity:{relative}")

    for figure in manifest.get("figures", []):
        verify_record(figure)
        if not git_is_tracked(root, figure["path"]):
            failures.append(f"untracked:{figure['path']}")
        for source in figure.get("source_data", []):
            verify_record(source)
    return {
        "status": "pass" if not failures and len(manifest.get("figures", [])) == 6 else "fail",
        "figure_count": len(manifest.get("figures", [])),
        "original_bytes_preserved": manifest.get("regenerated_during_submission_lock") is False,
        "identity_modes": identity_modes,
        "failures": sorted(failures),
    }


def audit_protected_manifest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    copy_required: list[str] = []
    identity_modes: dict[str, int] = {}
    for record in manifest.get("records", []):
        relative = record["path"]
        path = root / relative
        if record.get("copy_required"):
            copy_required.append(relative)
        if not path.is_file():
            failures.append(f"missing:{relative}")
            continue
        definition = relative == ".gitignore" or relative.startswith(
            ("configs/", "scripts/", "src/", "tests/", ".github/")
        )
        identity = verify_evidence_lock(
            path,
            record["sha256"],
            expected_size=int(record["byte_size"]),
            root=root,
            allow_historical_revision=definition,
        )
        mode = str(identity["mode"])
        identity_modes[mode] = identity_modes.get(mode, 0) + 1
        if not identity["passed"]:
            failures.append(f"identity:{relative}")
        if path.is_symlink():
            failures.append(f"symlink:{relative}")
    return {
        "status": "pass" if not failures and manifest.get("all_previously_anchored_records_match") else "fail",
        "record_count": len(manifest.get("records", [])),
        "copy_required_count": len(copy_required),
        "copy_required_paths": copy_required,
        "identity_modes": identity_modes,
        "failures": sorted(failures),
    }


def evaluate_readiness(facts: dict[str, bool]) -> dict[str, Any]:
    technical_keys = [
        "required_documents",
        "citations",
        "claim_mapping",
        "synthetic_disclosure",
        "source_contract",
        "figures",
        "protected_evidence",
        "local_assets",
        "portable_identity",
        "source_artifact_integrity",
        "tests",
        "governance",
        "local_replay",
        "data_statement",
    ]
    technical = all(bool(facts.get(key)) for key in technical_keys)
    journal_format = bool(facts.get("journal_selected") and facts.get("format_rendered"))
    upload = bool(journal_format and facts.get("author_metadata") and facts.get("upload_declarations"))
    if technical and upload:
        disposition = "SUBMISSION_GO"
        overall = "GO"
    elif technical:
        disposition = "CONTENT_GO_UPLOAD_NO_GO"
        overall = "NO_GO"
    else:
        disposition = "CONTENT_NO_GO"
        overall = "NO_GO"
    return {
        "technical_content_package_ready": technical,
        "journal_format_ready": journal_format,
        "journal_upload_ready": upload,
        "overall_status": overall,
        "disposition": disposition,
    }


def write_claim_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "claim_id",
        "status",
        "sentence",
        "sentence_found",
        "evidence_paths",
        "evidence_sha256",
        "evidence_identity_modes",
        "evidence_verified",
        "gate_pass",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_readiness(
    *,
    root: Path,
    config: dict[str, Any],
    base_commit: str,
    validated_content_commit: str,
    full_pytest_log: Path,
    governance_log: Path,
    local_replay: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required_missing = [path for path in config["required_documents"] if not (root / path).is_file()]
    main_text = (root / "docs/manuscript/main_submission_v2.md").read_text(encoding="utf-8")
    bib_path = root / config["bibliography"]
    bib_text = bib_path.read_text(encoding="utf-8") if bib_path.is_file() else ""
    bib_keys = parse_bibtex_keys(bib_text)
    citation_keys: set[str] = set()
    for relative in config["citation_documents"]:
        path = root / relative
        if path.is_file():
            citation_keys |= parse_citation_keys(path.read_text(encoding="utf-8"))
    missing_citations = sorted(citation_keys - bib_keys)
    missing_dois = [doi for doi in config["required_dois"] if doi.lower() not in bib_text.lower()]
    claim_rows = audit_claim_rows(root, main_text, config["core_claims"])

    figure_manifest = json.loads((root / config["figure_manifest"]).read_text(encoding="utf-8"))
    figure_result = audit_figure_manifest(root, figure_manifest)
    protected_manifest = json.loads((root / config["protected_manifest"]).read_text(encoding="utf-8"))
    protected_result = audit_protected_manifest(root, protected_manifest)
    source_contract = json.loads((root / config["source_contract_summary"]).read_text(encoding="utf-8"))
    asset_validation_path = root / config["local_replay_asset_validation"]
    asset_validation = (
        json.loads(asset_validation_path.read_text(encoding="utf-8"))
        if asset_validation_path.is_file()
        else {"all_passed": False, "failures": ["validation_missing"]}
    )
    portable_identity_path = root / config["portable_evidence_identity_audit"]
    portable_identity = (
        json.loads(portable_identity_path.read_text(encoding="utf-8"))
        if portable_identity_path.is_file()
        else {"all_passed": False, "failures": ["audit_missing"]}
    )
    source_integrity_path = root / config["continuous_refinement_integrity_audit"]
    source_integrity = (
        json.loads(source_integrity_path.read_text(encoding="utf-8"))
        if source_integrity_path.is_file()
        else {"all_passed": False, "failures": ["audit_missing"]}
    )

    pytest_text = read_portable_log(full_pytest_log)
    governance_text = read_portable_log(governance_log)
    pytest_exit = parse_exit_code(pytest_text)
    governance_exit = parse_exit_code(governance_text)
    pytest_counts = parse_pytest_counts(pytest_text)

    normalized_main = normalized_text(main_text).lower()
    synthetic_missing = [
        phrase for phrase in config["synthetic_disclosure_phrases"] if normalized_text(phrase).lower() not in normalized_main
    ]
    forbidden_found = [phrase for phrase in config["forbidden_positive_assertions"] if phrase.lower() in normalized_main]
    data_text = " ".join(
        [
            (root / "docs/manuscript/data_code_availability.md").read_text(encoding="utf-8"),
            (root / "docs/manuscript/reproducibility_statement.md").read_text(encoding="utf-8"),
        ]
    ).lower()
    data_missing = [phrase for phrase in config["data_boundary_phrases"] if phrase.lower() not in data_text]

    claims_pass = all(row["gate_pass"] for row in claim_rows)
    source_pass = bool(source_contract.get("blocking_gates_pass"))
    facts = {
        "required_documents": not required_missing,
        "citations": not missing_citations and not missing_dois,
        "claim_mapping": claims_pass,
        "synthetic_disclosure": not synthetic_missing and not forbidden_found,
        "source_contract": source_pass,
        "figures": figure_result["status"] == "pass",
        "protected_evidence": protected_result["status"] == "pass",
        "local_assets": bool(asset_validation.get("all_passed"))
        and int(asset_validation.get("verified_asset_count", -1)) == 50,
        "portable_identity": bool(portable_identity.get("all_passed")),
        "source_artifact_integrity": bool(source_integrity.get("all_passed")),
        "tests": pytest_exit == 0 and pytest_counts["failed"] == 0 and pytest_counts["passed"] > 0,
        "governance": governance_exit == 0,
        "local_replay": local_replay,
        "data_statement": not data_missing,
        "journal_selected": config["journal_scope"].get("selected_journal") is not None,
        "format_rendered": False,
        "author_metadata": False,
        "upload_declarations": False,
    }
    readiness_gate = evaluate_readiness(facts)

    blocked_reasons: list[str] = []
    if not readiness_gate["technical_content_package_ready"]:
        blocked_reasons.extend(f"technical_gate_failed:{key}" for key in facts if key in {
            "required_documents", "citations", "claim_mapping", "synthetic_disclosure", "source_contract",
            "figures", "protected_evidence", "local_assets", "portable_identity",
            "source_artifact_integrity", "tests", "governance", "local_replay",
            "data_statement"
        } and not facts[key])
    blocked_reasons.extend(
        [
            "selected_journal_not_locked",
            "article_type_not_locked",
            "target_format_not_rendered_or_visually_checked",
            "author_metadata_and_declarations_incomplete",
            "public_reproduction_assets_not_archived",
            "q2_target_adequacy_requires_manual_judgment",
        ]
    )

    spec = importlib.util.find_spec("pinnpcm")
    environment = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(root),
        "pinnpcm_origin": None if spec is None else spec.origin,
        "pythonpath": os.environ.get("PYTHONPATH", ""),
        "pandoc_available": shutil.which("pandoc") is not None,
    }
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": config["task_id"],
        "base_commit": base_commit,
        "validated_content_commit": validated_content_commit,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "new_formal_scientific_experiments": int(source_contract.get("new_formal_scientific_experiments", 0)),
        "new_claim_bearing_device_forward_runs": int(source_contract.get("new_claim_bearing_device_forward_runs", 0)),
        "formula_contract_evaluations": int(source_contract.get("formula_contract_evaluations", 0)),
        "test_only_smoke_runs": pytest_counts["test_only_smoke_runs"],
        "external_validation": False,
        "qiu_author_intent_inferred": bool(source_contract.get("qiu_author_intent_inferred", False)),
        "qiu_author_code_verified": bool(source_contract.get("qiu_author_code_verified", False)),
        "requires_local_asset_pack": True,
        "clean_clone_reproducible": False,
        "scientific_claim_integrity": {
            "status": "pass" if claims_pass else "fail",
            "core_claim_count": len(claim_rows),
            "all_claim_gates_pass": claims_pass,
        },
        "synthetic_only_disclosure": {
            "status": "pass" if not synthetic_missing and not forbidden_found else "fail",
            "missing_phrases": synthetic_missing,
            "forbidden_positive_assertions_found": forbidden_found,
        },
        "mainline_evidence_sufficiency": {
            "status": "qualified_supported" if claims_pass else "manual_unverified_high_risk",
            "boundary": "synthetic reduced inverse under fixed or tightly bounded priors",
        },
        "source_contract": {
            "status": "pass" if source_pass else "fail",
            "claim_status": source_contract.get("claim_status"),
            "blocking_gates_pass": source_pass,
            "formula_contract_evaluations": source_contract.get("formula_contract_evaluations"),
        },
        "citations": {
            "status": "pass" if not missing_citations and not missing_dois else "fail",
            "citation_keys": sorted(citation_keys),
            "bibtex_keys": sorted(bib_keys),
            "missing_citations": missing_citations,
            "missing_required_dois": missing_dois,
        },
        "claim_sentence_mapping": {
            "status": "pass" if claims_pass else "fail",
            "mapped_claims": len(claim_rows),
            "failed_claim_ids": [row["claim_id"] for row in claim_rows if not row["gate_pass"]],
        },
        "figure_table_integrity": figure_result,
        "protected_evidence": protected_result,
        "local_replay_assets": {
            "status": "pass" if facts["local_assets"] else "fail",
            "required_asset_count": asset_validation.get("required_asset_count"),
            "verified_asset_count": asset_validation.get("verified_asset_count"),
            "sealed_member_payload_accessed": asset_validation.get(
                "sealed_member_payload_accessed"
            ),
            "failures": asset_validation.get("failures", []),
        },
        "portable_evidence_identity": {
            "status": "pass" if facts["portable_identity"] else "fail",
            "lock_count": portable_identity.get("lock_count"),
            "mode_counts": portable_identity.get("mode_counts", {}),
            "failures": portable_identity.get("failures", []),
        },
        "source_artifact_integrity": {
            "status": "pass" if facts["source_artifact_integrity"] else "fail",
            "summary_sha256": source_integrity.get("summary_sha256"),
            "summary_canonical_lf_sha256": source_integrity.get(
                "summary_canonical_lf_sha256"
            ),
            "cases_sha256": source_integrity.get("cases_sha256"),
            "row_count": source_integrity.get("row_count"),
            "scientific_forward_runs": source_integrity.get("scientific_forward_runs"),
            "failures": source_integrity.get("failures", []),
        },
        "tests": {
            "status": "pass" if facts["tests"] else "fail",
            "exit_code": pytest_exit,
            **pytest_counts,
            "log": str(full_pytest_log),
        },
        "governance": {
            "status": "pass" if facts["governance"] else "fail",
            "exit_code": governance_exit,
            "log": str(governance_log),
        },
        "public_reproducibility": {
            "local_clean_worktree_replay": local_replay,
            "requires_local_asset_pack": True,
            "verified_local_asset_pack_complete": facts["local_assets"],
            "detached_replay_with_verified_local_assets": local_replay and facts["local_assets"],
            "public_reproduction_assets_available": False,
            "clean_clone_reproducible": False,
            "third_party_redistribution_allowed": False,
            "data_availability_statement_consistent": not data_missing,
            "missing_data_boundary_phrases": data_missing,
        },
        "journal_scope": config["journal_scope"],
        **readiness_gate,
        "q2_target_adequacy": "manual_unverified_high_risk",
        "blocked_reasons": blocked_reasons,
        "required_document_failures": required_missing,
    }
    return result, claim_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed submission-readiness audit")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--config", type=Path, default=Path("configs/submission_readiness.yaml"))
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--validated-content-commit", required=True)
    parser.add_argument("--full-pytest-log", type=Path, required=True)
    parser.add_argument("--governance-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--claim-output", type=Path, required=True)
    parser.add_argument("--local-clean-worktree-replay", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    result, claim_rows = build_readiness(
        root=root,
        config=config,
        base_commit=args.base_commit,
        validated_content_commit=args.validated_content_commit,
        full_pytest_log=args.full_pytest_log.resolve(),
        governance_log=args.governance_log.resolve(),
        local_replay=args.local_clean_worktree_replay,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(json_ready(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    write_claim_csv(args.claim_output.resolve(), claim_rows)
    print(json.dumps({
        "overall_status": result["overall_status"],
        "disposition": result["disposition"],
        "technical_content_package_ready": result["technical_content_package_ready"],
        "journal_upload_ready": result["journal_upload_ready"],
    }, indent=2))
    return 0 if result["technical_content_package_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
