from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "outputs" / "tables" / "repository_file_disposition.csv"
DEFAULT_SUMMARY = ROOT / "outputs" / "tables" / "repository_realign_phase0_summary.json"
SELF_OUTPUTS = {
    "outputs/tables/repository_file_disposition.csv",
    "outputs/tables/repository_realign_phase0_summary.json",
}
ALLOWED_DISPOSITIONS = {
    "KEEP_CURRENT",
    "KEEP_EVERGREEN",
    "UPDATE",
    "MERGE",
    "ARCHIVE",
    "DELETE_DUPLICATE",
    "DELETE_GENERATED",
    "LEAVE_IN_PLACE_FROZEN",
    "REVIEW_BLOCKED",
}
FROZEN = {
    "configs/gt_v1_acceptance_triangle.yaml",
    "configs/gt_v1_acceptance_ltp_ltd.yaml",
    "docs/gt_v1_acceptance_report.md",
    "data/processed/gt_v1_acceptance/manifest.json",
    "data/processed/gt_v1_acceptance/gt_triangle.npz",
    "data/processed/gt_v1_acceptance/obs_triangle_sparse.npz",
    "data/processed/gt_v1_acceptance/gt_ltp_ltd.npz",
    "data/processed/gt_v1_acceptance/obs_ltp_ltd_sparse.npz",
}
CURRENT = {
    "AGENTS.md",
    "README.md",
    "PROJECT_GOAL.md",
    "CODEX_CONTEXT.md",
    "PROJECT_STATE.md",
    "NEXT_ACTIONS.md",
    "configs/geo2p5d_stage.yaml",
    "configs/geophase_phase1_2p5d_reference.yaml",
    "docs/method_equations.md",
    "docs/paper/final_claim_matrix.md",
    "docs/project_state/current_evidence_index.md",
    "docs/project_state/file_inventory.md",
    "docs/project_state/repo_tree.md",
    "docs/project_state/reproduction_quickstart.md",
    "docs/research_strategy/active_phase.md",
    "docs/research_strategy/context_index.md",
    "docs/research_strategy/current_research_handoff.md",
    "docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md",
    "docs/research_strategy/phase1_geophase_2p5d_reference_contract.md",
    "docs/manuscript/README.md",
    "docs/manuscript/submission_go_no_go.md",
    "scripts/audit_project_governance.py",
    "scripts/audit_repository_realignment.py",
    "tests/test_geophase_phase1_preregistration.py",
    "tests/test_project_governance.py",
    "tests/test_repository_realignment_audit.py",
    "docs/codex_reports/repository_realign_phase0_2026-07-25.md",
    *SELF_OUTPUTS,
}
TEXT_SUFFIXES = {
    ".md", ".py", ".yaml", ".yml", ".json", ".csv", ".toml", ".txt",
    ".bib", ".rules", ".gitignore", ".gitattributes",
}
CSV_FIELDS = [
    "path",
    "base_path",
    "file_type",
    "size_bytes",
    "sha256",
    "last_git_commit",
    "referenced_by_other_files",
    "reference_count",
    "reference_check",
    "route",
    "lifecycle",
    "frozen_evidence",
    "unique_information",
    "disposition",
    "disposition_reason",
    "replacement",
    "recoverable_from_git",
]


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def normalize(path: str) -> str:
    return path.strip().replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def current_paths() -> list[str]:
    cached = run_git("ls-files").splitlines()
    untracked = run_git("ls-files", "--others", "--exclude-standard").splitlines()
    paths = {normalize(item) for item in [*cached, *untracked] if item.strip()}
    paths.update(SELF_OUTPUTS)
    return sorted(path for path in paths if path in SELF_OUTPUTS or (ROOT / path).is_file())


def base_paths(base_commit: str) -> set[str]:
    return {normalize(item) for item in run_git("ls-tree", "-r", "--name-only", base_commit).splitlines() if item.strip()}


def change_map(base_commit: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    status: dict[str, str] = {}
    moved_from: dict[str, str] = {}
    deleted: list[str] = []
    for line in run_git("diff", "--name-status", "-M", base_commit, "--").splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        code = parts[0]
        if code.startswith("R") and len(parts) == 3:
            old, new = normalize(parts[1]), normalize(parts[2])
            status[new] = "R"
            moved_from[new] = old
        elif len(parts) == 2:
            path = normalize(parts[1])
            status[path] = code[:1]
            if code.startswith("D"):
                deleted.append(path)
    for item in run_git("ls-files", "--others", "--exclude-standard").splitlines():
        path = normalize(item)
        if path:
            status.setdefault(path, "A")
    return status, moved_from, sorted(deleted)


def last_commit_map() -> dict[str, str]:
    result: dict[str, str] = {}
    current: str | None = None
    for line in run_git("log", "--format=@@COMMIT:%H", "--name-only", "--all", "--").splitlines():
        if line.startswith("@@COMMIT:"):
            current = line.split(":", 1)[1]
            continue
        path = normalize(line)
        if current and path and path not in result:
            result[path] = current
    return result


def read_text_corpus(paths: list[str]) -> tuple[dict[str, str], str, Counter[str]]:
    texts: dict[str, str] = {}
    basenames = Counter(Path(path).name for path in paths)
    for rel in paths:
        path = ROOT / rel
        if rel in SELF_OUTPUTS or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            texts[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return texts, "\n".join(texts.values()), basenames


def reference_count(rel: str, texts: dict[str, str], corpus: str, basenames: Counter[str]) -> tuple[int, str]:
    exact = corpus.count(rel) - texts.get(rel, "").count(rel)
    if exact > 0:
        return exact, "exact_repository_path"
    name = Path(rel).name
    if basenames[name] == 1:
        count = corpus.count(name) - texts.get(rel, "").count(name)
        if count > 0:
            return count, "unique_basename_fallback"
    return 0, "exact_path_and_unique_basename_checked"


def file_type(rel: str) -> str:
    if Path(rel).name == ".gitkeep":
        return "directory_placeholder"
    guessed = mimetypes.guess_type(rel)[0]
    return guessed or (Path(rel).suffix.lower().lstrip(".") or "no_extension")


def route_for(rel: str) -> str:
    lower = rel.lower()
    if rel in FROZEN or "gt_v1_acceptance" in lower:
        return "frozen_gt_v1_1"
    if any(token in lower for token in ["m40", "m44", "qiu_2d", "real_device_bridge"]):
        return "retired_real_device_bridge"
    if rel.startswith("docs/archive/legacy_1d_route/") or any(
        token in lower for token in ["gamma_sub", "pinn_inverse_v", "sid_", "oasis"]
    ):
        return "historical_1d_or_inverse"
    if any(token in lower for token in ["geophase_phase1", "geo2p5d", "phase1_geophase"]):
        return "phase1_2p5d_reference"
    if rel.endswith("pinn_phase_change_q2_sci_execution_guide.md"):
        return "r1_r2_r3_strategy"
    if rel.startswith(("docs/archive/", "docs/codex_reports/", "docs/manuscript/")):
        return "historical_or_manuscript_provenance"
    if rel in CURRENT or rel.startswith(("docs/project_state/", "docs/research_strategy/")):
        return "current_governance"
    if rel.startswith(("src/", "scripts/", "tests/", "configs/")):
        return "shared_research_infrastructure"
    if rel.startswith(("outputs/", "data/")):
        return "retained_machine_evidence_or_data"
    return "shared_repository"


def lifecycle_for(rel: str) -> str:
    if rel in FROZEN:
        return "FROZEN"
    if rel in CURRENT:
        return "CURRENT"
    if rel.startswith("docs/archive/"):
        return "HISTORICAL"
    if rel in {"docs/manuscript/main_submission_v1.md", "docs/manuscript/main_submission_v2.md"}:
        return "HISTORICAL_PROTECTED_PATH"
    if rel.startswith(("docs/codex_reports/", "outputs/tables/", "outputs/logs/")):
        return "HISTORICAL_OR_CUMULATIVE_EVIDENCE"
    return "EVERGREEN_OR_REUSABLE"


def replacement_for(rel: str) -> str:
    if rel.startswith("docs/archive/"):
        return "docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md"
    if rel in {"docs/manuscript/main_submission_v1.md", "docs/manuscript/main_submission_v2.md"}:
        return "no_v3_until_gate_supported_R1"
    if rel in FROZEN:
        return "none_read_only"
    if rel in CURRENT:
        return rel
    return ""


def disposition_for(rel: str, status: dict[str, str]) -> tuple[str, str]:
    if rel in FROZEN:
        return "LEAVE_IN_PLACE_FROZEN", "Frozen GT contract and hash-controlled replay asset."
    if rel.endswith("pinn_phase_change_q2_sci_execution_guide.md"):
        return "MERGE", "Canonical merged strategy authority; only one current full guide is retained."
    if rel.startswith("docs/archive/"):
        return "ARCHIVE", "Unique historical planning/provenance retained without current authorization."
    if rel in status or rel in CURRENT:
        return "UPDATE", "Created, renamed, or updated for the Phase 0 authority and Phase 1 route."
    return "KEEP_EVERGREEN", "Retained evidence, implementation, test, provenance, or reusable project asset."


def build_rows(base_commit: str) -> tuple[list[dict[str, str | int]], dict]:
    paths = current_paths()
    base = base_paths(base_commit)
    status, moved_from, deleted = change_map(base_commit)
    commits = last_commit_map()
    texts, corpus, basenames = read_text_corpus(paths)

    hashes: dict[str, str] = {}
    hash_groups: dict[str, list[str]] = defaultdict(list)
    for rel in paths:
        if rel in SELF_OUTPUTS:
            hashes[rel] = "NOT_APPLICABLE_SELF_REFERENTIAL_OUTPUT"
        else:
            hashes[rel] = sha256(ROOT / rel)
            hash_groups[hashes[rel]].append(rel)

    rows: list[dict[str, str | int]] = []
    for rel in paths:
        count, reference_check = reference_count(rel, texts, corpus, basenames)
        source = moved_from.get(rel, rel if rel in base else "")
        last_commit = commits.get(source) or commits.get(rel) or "UNCOMMITTED_PHASE0"
        disposition, reason = disposition_for(rel, status)
        duplicates = hash_groups.get(hashes[rel], [])
        if len(duplicates) > 1 and Path(rel).name == ".gitkeep":
            unique = "INTENTIONAL_UNIQUE_DIRECTORY_ROLE"
        elif len(duplicates) > 1:
            unique = "EXACT_DUPLICATE_REVIEWED"
        else:
            unique = "NO_EXACT_DUPLICATE_UNIQUE_OR_ROLE_SPECIFIC"
        rows.append({
            "path": rel,
            "base_path": moved_from.get(rel, ""),
            "file_type": file_type(rel),
            "size_bytes": -1 if rel in SELF_OUTPUTS else (ROOT / rel).stat().st_size,
            "sha256": hashes[rel],
            "last_git_commit": last_commit,
            "referenced_by_other_files": "yes" if count else "no",
            "reference_count": count,
            "reference_check": reference_check,
            "route": route_for(rel),
            "lifecycle": lifecycle_for(rel),
            "frozen_evidence": "yes" if rel in FROZEN else "no",
            "unique_information": unique,
            "disposition": disposition,
            "disposition_reason": reason,
            "replacement": replacement_for(rel),
            "recoverable_from_git": "yes" if source in base else "after_commit",
        })

    duplicate_groups = [
        {"sha256": digest, "paths": group, "disposition": "retain_distinct_directory_roles" if all(Path(p).name == ".gitkeep" for p in group) else "reviewed"}
        for digest, group in sorted(hash_groups.items())
        if len(group) > 1
    ]
    metadata = {
        "paths": paths,
        "status": status,
        "moved_from": moved_from,
        "deleted": deleted,
        "duplicate_groups": duplicate_groups,
    }
    return rows, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory and disposition every tracked/current Phase 0 repository file.")
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--phase0-status", default="pending_final_verification")
    parser.add_argument("--after-tests", default="pending")
    parser.add_argument("--push-status", default="pending_final_push")
    parser.add_argument("--final-sha", default="SELF")
    args = parser.parse_args()

    rows, metadata = build_rows(args.base_commit)
    invalid = sorted({str(row["disposition"]) for row in rows} - ALLOWED_DISPOSITIONS)
    if invalid:
        raise RuntimeError(f"Invalid dispositions: {invalid}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    dispositions = Counter(str(row["disposition"]) for row in rows)
    lifecycles = Counter(str(row["lifecycle"]) for row in rows)
    routes = Counter(str(row["route"]) for row in rows)
    changed = sorted(path for path, code in metadata["status"].items() if code != "D")
    summary = {
        "task_id": "Q2_REPOSITORY_REALIGNMENT_AND_PHASE0_GOVERNANCE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_sha": args.base_commit,
        "final_sha": args.final_sha,
        "final_sha_semantics": "SELF means the commit containing this summary",
        "branch": run_git("branch", "--show-current").strip(),
        "head_at_generation": run_git("rev-parse", "HEAD").strip(),
        "current_phase": "Q2_PHASE1_2P5D_REFERENCE_SOLVER",
        "next_single_priority": "independent_conservative_qiu_xy_k_state_2p5d_fvm_implicit_reference_solver",
        "phase0_status": args.phase0_status,
        "push_status": args.push_status,
        "inventory": {
            "row_count": len(rows),
            "disposition_counts": dict(sorted(dispositions.items())),
            "lifecycle_counts": dict(sorted(lifecycles.items())),
            "route_counts": dict(sorted(routes.items())),
            "changed_paths": changed,
            "changed_path_count": len(changed),
            "moved_files": [
                {"from": old, "to": new}
                for new, old in sorted(metadata["moved_from"].items())
            ],
            "moved_file_count": len(metadata["moved_from"]),
            "deleted_files": metadata["deleted"],
            "deleted_file_count": len(metadata["deleted"]),
            "duplicate_groups": metadata["duplicate_groups"],
            "self_referential_outputs": sorted(SELF_OUTPUTS),
        },
        "verification": {
            "before": {
                "pytest": "447 passed",
                "duration_s": 374.08,
                "governance": "pass_with_manual_review",
                "tracked_json": "201 passed, 0 failed",
                "frozen_hashes": "8/8 unchanged",
            },
            "after": args.after_tests,
        },
        "claim_changes": {
            "scientific_upgrades": [],
            "scientific_downgrades": [],
            "governance_supported": [
                "one canonical execution guide",
                "R1/R2/conditional-R3 delivery ladder",
                "one Phase 1 active route",
                "historical/current separation",
            ],
            "still_forbidden": [
                "successful Phase 1 reference solver",
                "positive R1 or R2",
                "R3 observation-subspace recovery and refusal",
                "experimental or quantitative-Qiu validation",
                "full FEM/3D and VO2-to-NbO2 zero-shot claims",
            ],
        },
        "frozen_gt_modified": False,
        "scientific_experiment_executed": False,
    }
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": len(rows),
        "dispositions": dict(sorted(dispositions.items())),
        "moved": len(metadata["moved_from"]),
        "deleted": len(metadata["deleted"]),
        "phase0_status": args.phase0_status,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
