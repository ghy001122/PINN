from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "tables" / "project_governance_summary.json"
CLAIM_STATUSES = {"supported", "qualified_supported", "failed_but_informative", "forbidden"}
DISPOSITIONS = {
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
EXPECTED_PHASE = "Q2_PHASE1_2P5D_REFERENCE_SOLVER"

REQUIRED = [
    "AGENTS.md",
    "PROJECT_GOAL.md",
    "CODEX_CONTEXT.md",
    "PROJECT_STATE.md",
    "NEXT_ACTIONS.md",
    "README.md",
    "docs/AGENTS.md",
    "docs/project_prompts/critical_research_mode.md",
    "docs/research_strategy/active_phase.md",
    "docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md",
    "docs/research_strategy/phase1_geophase_2p5d_reference_contract.md",
    "docs/research_strategy/current_research_handoff.md",
    "docs/research_strategy/context_index.md",
    "docs/research_strategy/context_loading_policy.md",
    "docs/research_strategy/sci_delivery_pipeline.md",
    "docs/research_strategy/legacy_document_index.md",
    "docs/research_strategy/durable_project_memory.md",
    "docs/research_strategy/memory_policy.md",
    "docs/project_state/current_evidence_index.md",
    "docs/project_state/file_inventory.md",
    "docs/project_state/repo_tree.md",
    "docs/project_state/reproduction_quickstart.md",
    "docs/archive/README.md",
    "docs/archive/superseded_strategy/README.md",
    "configs/geo2p5d_stage.yaml",
    "configs/geophase_phase1_2p5d_reference.yaml",
    "tests/test_geophase_phase1_preregistration.py",
    "scripts/audit_repository_realignment.py",
    "outputs/tables/repository_file_disposition.csv",
    "outputs/tables/repository_realign_phase0_summary.json",
    "docs/codex_reports/repository_realign_phase0_2026-07-25.md",
    "docs/templates/codex_final_report.md",
    "src/pinnpcm/physics/AGENTS.md",
    "src/pinnpcm/pinn/AGENTS.md",
    "scripts/AGENTS.md",
    "tests/AGENTS.md",
    ".codex/README.md",
    ".codex/rules/project_safety.rules",
]

CRITICAL_MARKDOWN = [
    "AGENTS.md",
    "README.md",
    "PROJECT_GOAL.md",
    "CODEX_CONTEXT.md",
    "PROJECT_STATE.md",
    "NEXT_ACTIONS.md",
    "docs/project_state/current_evidence_index.md",
    "docs/project_state/file_inventory.md",
    "docs/project_state/repo_tree.md",
    "docs/research_strategy/active_phase.md",
    "docs/research_strategy/context_index.md",
    "docs/research_strategy/current_research_handoff.md",
    "docs/research_strategy/legacy_document_index.md",
    "docs/manuscript/README.md",
    "docs/manuscript/submission_go_no_go.md",
    "docs/archive/README.md",
]

CURRENT_ROUTE_FILES = [
    "AGENTS.md",
    "README.md",
    "PROJECT_GOAL.md",
    "CODEX_CONTEXT.md",
    "PROJECT_STATE.md",
    "NEXT_ACTIONS.md",
    "docs/research_strategy/active_phase.md",
    "docs/research_strategy/context_index.md",
    "docs/research_strategy/current_research_handoff.md",
    "docs/project_state/current_evidence_index.md",
    "docs/manuscript/README.md",
    "docs/manuscript/submission_go_no_go.md",
]

FROZEN_HASHES = {
    "configs/gt_v1_acceptance_triangle.yaml": "F2E6BEC6006827344BEBDDCF20519B5B87F923B349A8799596D06E9F254A2B02",
    "configs/gt_v1_acceptance_ltp_ltd.yaml": "F1F71F21F1D0D27532EEAD23A3A4B71B0864E6B0966E564104DCFFD7040C1D93",
    "docs/gt_v1_acceptance_report.md": "0F72718AFFB84F727771F8D4A1A16AFB9D7C0D15BD7984632B3BEB8155F91643",
    "data/processed/gt_v1_acceptance/manifest.json": "634554429B9E61A231E47BF35B9B5C66C1C316E5E11A86BDE0540B05FF5AE30F",
    "data/processed/gt_v1_acceptance/gt_triangle.npz": "4E4814D9C66A79CBE86417296B0A797E53FFFF2CEE2BD881548FBCD35E05C9F8",
    "data/processed/gt_v1_acceptance/obs_triangle_sparse.npz": "F45DAF53136A255B3666EBEB56E6298CE148A613C46FA596B795E7ADE68EA602",
    "data/processed/gt_v1_acceptance/gt_ltp_ltd.npz": "772D17178C77392BF8A0813ADA3DB4A7241C5FA4E6D72E091894271BFA13C247",
    "data/processed/gt_v1_acceptance/obs_ltp_ltd_sparse.npz": "7155BFF7C406FAB49E9670FA8A73AB6D0063459A80FEB705138E3FE61A351645",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check_markdown_links() -> dict:
    missing: list[dict[str, str]] = []
    checked = 0
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for rel in CRITICAL_MARKDOWN:
        source = ROOT / rel
        if not source.exists():
            continue
        for raw in pattern.findall(source.read_text(encoding="utf-8")):
            target = raw.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            checked += 1
            candidates = [(source.parent / target).resolve(), (ROOT / target).resolve()]
            if not any(candidate.exists() for candidate in candidates):
                missing.append({"source": rel, "target": target})
    return {"status": "pass" if not missing else "fail", "checked": checked, "missing": missing}


def phase_id(text: str) -> str | None:
    match = re.search(r"Active phase ID:\s*`([A-Z0-9_]+)`", text)
    return match.group(1) if match else None


def check_phase_consistency() -> dict:
    active = read("docs/research_strategy/active_phase.md")
    current = {rel: read(rel) for rel in [
        "CODEX_CONTEXT.md",
        "PROJECT_STATE.md",
        "NEXT_ACTIONS.md",
        "docs/research_strategy/current_research_handoff.md",
        "configs/geo2p5d_stage.yaml",
        "configs/geophase_phase1_2p5d_reference.yaml",
    ]}
    actual = phase_id(active)
    missing: list[str] = []
    if actual != EXPECTED_PHASE:
        missing.append(f"active_phase:{actual}")
    for rel, text in current.items():
        if EXPECTED_PHASE not in text:
            missing.append(f"{rel}:{EXPECTED_PHASE}")
    stage = read("configs/geo2p5d_stage.yaml")
    for marker in ["HysGeo-Hybrid-PINN", "GeoPhase-HomoMoE-PINN", "conditional_event_aligned_local_observable_subspace"]:
        if marker not in stage:
            missing.append(f"stage:{marker}")
    return {"status": "pass" if not missing else "fail", "active_phase_id": actual, "missing": missing}


def check_delivery_contract() -> dict:
    texts = {rel: read(rel) for rel in CURRENT_ROUTE_FILES}
    missing: list[str] = []
    goal_markers = [
        "Q2_SCI_DELIVERY_MODE",
        "North-Star Scientific Claim",
        "Mandatory Research Filter",
        "Stable Delivery Lanes",
        "Must-Have Definition Of Done",
        "HysGeo-Hybrid-PINN",
        "GeoPhase-HomoMoE-PINN",
        "User Confirmation Boundary",
        "Stretch failure cannot block paper delivery",
    ]
    for marker in goal_markers:
        if marker not in texts["PROJECT_GOAL.md"]:
            missing.append(f"PROJECT_GOAL.md:{marker}")
    for rel in ["README.md", "PROJECT_GOAL.md", "CODEX_CONTEXT.md", "PROJECT_STATE.md"]:
        for marker in ["HysGeo-Hybrid-PINN", "GeoPhase-HomoMoE-PINN", "R3"]:
            if marker not in texts[rel]:
                missing.append(f"{rel}:{marker}")
    for rel in ["AGENTS.md", "PROJECT_GOAL.md", "PROJECT_STATE.md", "docs/research_strategy/active_phase.md"]:
        if "forbidden" not in texts[rel]:
            missing.append(f"{rel}:forbidden")
    critical = read("docs/project_prompts/critical_research_mode.md")
    if "Do not use `forbidden` to block exploratory experiments." not in critical:
        missing.append("critical_research_mode:exploration_boundary")
    if "`forbidden` blocks manuscript wording, not bounded exploration." not in texts["AGENTS.md"]:
        missing.append("AGENTS.md:exploration_boundary")
    return {"status": "pass" if not missing else "fail", "missing": missing}


def check_no_obsolete_current_route() -> dict:
    obsolete = [
        "Q2_GEOPHASE_E0_REFERENCE_SOLVER_FOUNDATION",
        "configs/geophase_e0_2p5d_reference.yaml",
        "docs/research_strategy/geophase_oq_pinn_execution_contract.md",
        "docs/experiment_plan.md",
        "docs/research_strategy/innovation_portfolio.md",
        "tests/test_geophase_e0_preregistration.py",
    ]
    found: list[str] = []
    for rel in CURRENT_ROUTE_FILES:
        text = read(rel)
        for marker in obsolete:
            if marker in text:
                found.append(f"{rel}:{marker}")
    return {"status": "pass" if not found else "fail", "found": found}


def check_claim_matrix_vocabulary() -> dict:
    text = read("docs/paper/final_claim_matrix.md")
    obsolete_terms = ["partially_supported", "| failed |", "| Blocked |", "| Not supported |"]
    obsolete = [term for term in obsolete_terms if term in text]
    missing = [marker for marker in [
        "P1_reference_solver",
        "R1_hysgeo_hybrid",
        "R2_homomoe",
        "R3_observable_subspace",
        "Retained Historical Mainline Claims",
    ] if marker not in text]
    return {"status": "pass" if not obsolete and not missing else "fail", "obsolete": obsolete, "missing": missing}


def check_realignment_outputs() -> dict:
    csv_path = ROOT / "outputs/tables/repository_file_disposition.csv"
    summary_path = ROOT / "outputs/tables/repository_realign_phase0_summary.json"
    required_columns = {
        "path", "file_type", "size_bytes", "sha256", "last_git_commit",
        "referenced_by_other_files", "route", "lifecycle", "frozen_evidence",
        "unique_information", "disposition", "disposition_reason", "replacement",
    }
    problems: list[str] = []
    rows: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            if not required_columns <= columns:
                problems.append(f"csv_columns:{sorted(required_columns - columns)}")
            rows = list(reader)
        invalid = sorted({row.get("disposition", "") for row in rows} - DISPOSITIONS)
        if invalid:
            problems.append(f"invalid_dispositions:{invalid}")
        if len(rows) < 1000:
            problems.append(f"row_count:{len(rows)}")
    else:
        problems.append("missing_csv")
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"summary_json:{exc}")
            summary = {}
        if summary.get("task_id") != "Q2_REPOSITORY_REALIGNMENT_AND_PHASE0_GOVERNANCE":
            problems.append("summary_task_id")
    else:
        problems.append("missing_summary")
        summary = {}
    return {
        "status": "pass" if not problems else "fail",
        "rows": len(rows),
        "problems": problems,
        "summary_phase": summary.get("current_phase"),
    }


def check_phase0_report() -> dict:
    path = ROOT / "docs/codex_reports/repository_realign_phase0_2026-07-25.md"
    fields = [
        "task_id", "base_sha", "final_sha", "branch", "changed_files", "moved_files",
        "deleted_files", "tests", "frozen_gt_modified", "evidence_type",
        "claim_status", "current_phase", "next_single_priority", "push_status",
    ]
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    missing = [field for field in fields if re.search(rf"^{field}:", text, re.MULTILINE) is None]
    return {"status": "pass" if not missing else "fail", "missing": missing}


def run_audit(write_output: bool = True, require_frozen_payloads: bool = True) -> dict:
    checks: dict[str, dict] = {}

    missing_required = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    checks["required_files"] = {"status": "pass" if not missing_required else "fail", "missing": missing_required}

    handoff = read("docs/research_strategy/current_research_handoff.md")
    handoff_markers = ["CODEX_CONTEXT.md", "PROJECT_STATE.md", "active_phase.md", "current_evidence_index.md"]
    handoff_ok = all(marker in handoff for marker in handoff_markers) and len(handoff.encode("utf-8")) <= 2048
    checks["current_handoff"] = {
        "status": "pass" if handoff_ok else "fail",
        "bytes": len(handoff.encode("utf-8")),
        "missing_markers": [marker for marker in handoff_markers if marker not in handoff],
    }

    state = read("PROJECT_STATE.md")
    queue = read("NEXT_ACTIONS.md")
    snapshot_ok = state.count("## Authoritative Current Snapshot") == 1 and queue.count("## Authoritative Current Queue") == 1
    checks["single_current_snapshot"] = {
        "status": "pass" if snapshot_ok else "fail",
        "project_state_snapshot_headings": state.count("## Authoritative Current Snapshot"),
        "next_actions_queue_headings": queue.count("## Authoritative Current Queue"),
    }

    checks["phase_consistency"] = check_phase_consistency()
    checks["delivery_contract"] = check_delivery_contract()
    checks["no_obsolete_current_route"] = check_no_obsolete_current_route()
    checks["claim_matrix_vocabulary"] = check_claim_matrix_vocabulary()
    checks["critical_markdown_links"] = check_markdown_links()
    checks["realignment_outputs"] = check_realignment_outputs()
    checks["phase0_report"] = check_phase0_report()

    critical_text = "\n".join(read(rel) for rel in ["AGENTS.md", "PROJECT_GOAL.md", "PROJECT_STATE.md", "NEXT_ACTIONS.md"])
    all_present = all(status in critical_text for status in CLAIM_STATUSES)
    checks["claim_vocabulary"] = {"status": "pass" if all_present else "fail", "all_four_present": all_present}

    template = read("docs/templates/codex_final_report.md")
    template_fields = [
        "task_name", "base_sha", "final_sha", "branch", "tests", "reproduction_commands",
        "frozen_gt_modified", "evidence_type", "claim_status", "supported_claims",
        "forbidden_claims", "goal_distance_change", "claim_changes", "new_blockers",
        "next_single_priority", "disposition",
    ]
    missing_fields = [field for field in template_fields if re.search(rf"^{re.escape(field)}:", template, re.MULTILINE) is None]
    checks["final_report_template"] = {"status": "pass" if not missing_fields else "fail", "missing_fields": missing_fields}

    root_agents = (ROOT / "AGENTS.md").stat().st_size
    nested = [ROOT / "src/pinnpcm/physics/AGENTS.md", ROOT / "src/pinnpcm/pinn/AGENTS.md", ROOT / "scripts/AGENTS.md", ROOT / "tests/AGENTS.md", ROOT / "docs/AGENTS.md"]
    chain_sizes = {str(path.relative_to(ROOT)).replace("\\", "/"): root_agents + path.stat().st_size for path in nested}
    oversized = {path: size for path, size in chain_sizes.items() if size >= 32768}
    checks["agents_chain_size"] = {"status": "pass" if not oversized else "fail", "bytes": chain_sizes, "oversized": oversized}

    context_paths = [
        ROOT / "CODEX_CONTEXT.md",
        ROOT / "docs/research_strategy/active_phase.md",
        ROOT / "PROJECT_STATE.md",
        ROOT / "NEXT_ACTIONS.md",
        ROOT / "docs/project_state/current_evidence_index.md",
    ]
    context_bytes = {str(path.relative_to(ROOT)).replace("\\", "/"): path.stat().st_size for path in context_paths}
    context_total = sum(context_bytes.values())
    checks["low_token_context_budget"] = {
        "status": "pass" if context_total <= 24576 else "fail",
        "limit_bytes": 24576,
        "total_bytes": context_total,
        "files": context_bytes,
    }

    retired_generator = read("scripts/build_final_submission_figures.py")
    checks["retired_generator_guard"] = {
        "status": "pass" if "RETIRED" in retired_generator and "raise RuntimeError" in retired_generator else "fail",
        "path": "scripts/build_final_submission_figures.py",
    }

    duplicate_hashes: dict[str, list[str]] = {}
    for path in ROOT.rglob("*.md"):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if rel.startswith("docs/archive/"):
            continue
        duplicate_hashes.setdefault(sha256(path), []).append(rel)
    duplicate_groups = [paths for paths in duplicate_hashes.values() if len(paths) > 1]
    checks["no_duplicate_active_markdown"] = {
        "status": "pass" if not duplicate_groups else "fail",
        "groups": duplicate_groups,
    }

    frozen_details: dict[str, dict] = {}
    frozen_ok = True
    for rel, expected in FROZEN_HASHES.items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else None
        ignored_payload = rel.startswith("data/processed/gt_v1_acceptance/")
        deferred = bool(not require_frozen_payloads and ignored_payload and not path.exists())
        ok = deferred or actual == expected
        frozen_ok = frozen_ok and ok
        frozen_details[rel] = {
            "sha256": actual,
            "expected_sha256": expected,
            "hash_unchanged": ok,
            "deferred_to_full_validation": deferred,
        }
    frozen_deferred = any(item["deferred_to_full_validation"] for item in frozen_details.values())
    checks["frozen_gt_integrity"] = {
        "status": "deferred_to_full_validation" if frozen_ok and frozen_deferred else ("pass" if frozen_ok else "fail"),
        "files": frozen_details,
        "mtime_review": "manual_review_required",
        "mtime_reason": "Portable Git checkout mtimes are not authoritative; compare task pre/post hashes.",
    }

    rules = ROOT / ".codex/rules/project_safety.rules"
    checks["codex_rules"] = {
        "status": "manual_review_required" if rules.exists() else "fail",
        "syntax_file_present": rules.exists(),
        "automatic_project_loading": "manual_review_required",
        "note": "Client trust/loading remains a manual environment check.",
    }

    failed = [name for name, result in checks.items() if result["status"] == "fail"]
    manual = [
        name for name, result in checks.items()
        if result["status"] == "manual_review_required"
        or any(value == "manual_review_required" for value in result.values())
    ]
    summary = {
        "audit": "project_governance",
        "audit_scope": "full" if require_frozen_payloads else "fast_checkout",
        "overall_status": "fail" if failed else (
            "pass_with_deferred_full_validation" if frozen_deferred else (
                "pass_with_manual_review" if manual else "pass"
            )
        ),
        "failed_checks": failed,
        "manual_review_required": sorted(set(manual)),
        "checks": checks,
    }
    if write_output:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit current Q2 governance and frozen-evidence integrity.")
    parser.add_argument("--no-write", action="store_true", help="Do not update the tracked governance summary.")
    parser.add_argument(
        "--fast-checkout",
        action="store_true",
        help="Defer ignored frozen payload hashes to the trusted full workflow.",
    )
    args = parser.parse_args()
    result = run_audit(write_output=not args.no_write, require_frozen_payloads=not args.fast_checkout)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(1 if result["overall_status"] == "fail" else 0)
