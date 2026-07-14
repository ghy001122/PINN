from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "tables" / "project_governance_summary.json"
CLAIM_STATUSES = {"supported", "qualified_supported", "failed_but_informative", "forbidden"}

REQUIRED = [
    "AGENTS.md",
    "PROJECT_GOAL.md",
    "CODEX_CONTEXT.md",
    "PROJECT_STATE.md",
    "NEXT_ACTIONS.md",
    "README.md",
    "docs/AGENTS.md",
    "docs/research_strategy/active_phase.md",
    "docs/research_strategy/codex_new_dialog_handoff_d23a576.md",
    "docs/research_strategy/durable_project_memory.md",
    "docs/research_strategy/memory_policy.md",
    "docs/research_strategy/goal_status.md",
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
    "docs/research_strategy/context_index.md",
    "docs/research_strategy/current_research_handoff.md",
    "docs/research_strategy/memory_policy.md",
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


def check_phase_consistency() -> dict:
    active = (ROOT / "docs/research_strategy/active_phase.md").read_text(encoding="utf-8")
    context = (ROOT / "CODEX_CONTEXT.md").read_text(encoding="utf-8")
    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    combined = {"active_phase": active, "context": context, "project_state": state}
    required_markers = {
        "P0": ["qualified_supported"],
        "P1": ["failed", "0.37563055753707886"],
        "P2": ["failed_but_informative"],
        "P3": ["qualified", "forward"],
        "P4": ["blocked"],
    }
    missing: list[str] = []
    for name, text in combined.items():
        for gate in required_markers:
            if gate not in text:
                missing.append(f"{name}:{gate}")
    for marker in required_markers["P1"]:
        if marker not in active or marker not in context or marker not in state:
            missing.append(f"P1:{marker}")
    if "P4" in state and "forbidden" not in state:
        missing.append("project_state:P4 claim boundary")
    return {"status": "pass" if not missing else "fail", "missing": sorted(set(missing))}


def check_delivery_contract() -> dict:
    goal = (ROOT / "PROJECT_GOAL.md").read_text(encoding="utf-8")
    active = (ROOT / "docs/research_strategy/active_phase.md").read_text(encoding="utf-8")
    context = (ROOT / "CODEX_CONTEXT.md").read_text(encoding="utf-8")
    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    queue = (ROOT / "NEXT_ACTIONS.md").read_text(encoding="utf-8")
    required_goal_markers = [
        "Q2_SCI_DELIVERY_MODE",
        "North-Star Scientific Claim",
        "Mandatory Research Filter",
        "Ordered Research Priorities",
        "Must-Have Definition Of Done",
        "provenance-backed external quantitative anchor",
        "User Confirmation Boundary",
        "Stretch failure cannot block paper delivery",
    ]
    missing = [f"PROJECT_GOAL.md:{marker}" for marker in required_goal_markers if marker not in goal]
    active_markers = ["constrained `gamma_sub`", "Priority D"]
    for name, text in {
        "active_phase": active,
        "context": context,
        "project_state": state,
        "next_actions": queue,
    }.items():
        for marker in active_markers:
            if marker not in text:
                missing.append(f"{name}:{marker}")
    return {"status": "pass" if not missing else "fail", "missing": missing}


def check_claim_matrix_vocabulary() -> dict:
    paths = [ROOT / "docs/paper/claim_gate_resolution_matrix.md", ROOT / "docs/paper/final_claim_matrix.md"]
    obsolete_terms = ["partially_supported", "| failed |", "| Blocked |", "| Not supported |"]
    found: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in obsolete_terms:
            if term in text:
                found.append(f"{path.relative_to(ROOT)}:{term}")
    return {"status": "pass" if not found else "fail", "obsolete": found}


def run_audit(write_output: bool = True) -> dict:
    checks: dict[str, dict] = {}

    missing_required = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    checks["required_files"] = {"status": "pass" if not missing_required else "fail", "missing": missing_required}

    canonical = list((ROOT / "docs/research_strategy").glob("codex_new_dialog_handoff*.md"))
    pointer = (ROOT / "docs/research_strategy/current_research_handoff.md").read_text(encoding="utf-8")
    handoff_ok = len(canonical) == 1 and "codex_new_dialog_handoff_d23a576.md" in pointer
    checks["canonical_handoff"] = {
        "status": "pass" if handoff_ok else "fail",
        "canonical_count": len(canonical),
        "pointer_present": "codex_new_dialog_handoff_d23a576.md" in pointer,
    }

    state_text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    next_text = (ROOT / "NEXT_ACTIONS.md").read_text(encoding="utf-8")
    heading_ok = state_text.count("## Authoritative Current Snapshot") == 1 and next_text.count("## Authoritative Current Queue") == 1
    checks["single_current_snapshot"] = {
        "status": "pass" if heading_ok else "fail",
        "project_state_snapshot_headings": state_text.count("## Authoritative Current Snapshot"),
        "next_actions_queue_headings": next_text.count("## Authoritative Current Queue"),
    }

    checks["phase_consistency"] = check_phase_consistency()
    checks["delivery_contract"] = check_delivery_contract()
    checks["claim_matrix_vocabulary"] = check_claim_matrix_vocabulary()
    checks["critical_markdown_links"] = check_markdown_links()

    critical_text = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ["AGENTS.md", "PROJECT_GOAL.md", "PROJECT_STATE.md", "NEXT_ACTIONS.md"])
    obsolete = sorted(set(re.findall(r"claim_status:\s*([a-z_]+)", critical_text)) - CLAIM_STATUSES)
    all_present = all(status in critical_text for status in CLAIM_STATUSES)
    checks["claim_vocabulary"] = {"status": "pass" if all_present and not obsolete else "fail", "obsolete": obsolete, "all_four_present": all_present}

    template = (ROOT / "docs/templates/codex_final_report.md").read_text(encoding="utf-8")
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

    memorys = [str(path.relative_to(ROOT)).replace("\\", "/") for path in ROOT.rglob("memorys") if path.is_dir()]
    checks["no_authoritative_memorys_directory"] = {"status": "pass" if not memorys else "fail", "paths": memorys}

    frozen_details: dict[str, dict] = {}
    frozen_ok = True
    for rel, expected in FROZEN_HASHES.items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else None
        ok = actual == expected
        frozen_ok = frozen_ok and ok
        frozen_details[rel] = {
            "sha256": actual,
            "expected_sha256": expected,
            "hash_unchanged": ok,
            "mtime_observed": path.exists(),
        }
    checks["frozen_gt_integrity"] = {
        "status": "pass" if frozen_ok else "fail",
        "files": frozen_details,
        "mtime_review": "manual_review_required",
        "mtime_reason": "Portable Git checkout mtimes are not authoritative; compare pre/post mtimes in the active task.",
    }

    rules = ROOT / ".codex/rules/project_safety.rules"
    checks["codex_rules"] = {
        "status": "manual_review_required" if rules.exists() else "fail",
        "syntax_file_present": rules.exists(),
        "automatic_project_loading": "manual_review_required",
        "note": "Use codex execpolicy check for direct match tests; automatic trust/loading depends on the client.",
    }

    failed = [name for name, result in checks.items() if result["status"] == "fail"]
    manual = [name for name, result in checks.items() if result["status"] == "manual_review_required" or any(value == "manual_review_required" for value in result.values())]
    summary = {
        "audit": "project_governance",
        "overall_status": "fail" if failed else ("pass_with_manual_review" if manual else "pass"),
        "failed_checks": failed,
        "manual_review_required": sorted(set(manual)),
        "checks": checks,
    }
    if write_output:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = run_audit(write_output=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(1 if result["overall_status"] == "fail" else 0)
