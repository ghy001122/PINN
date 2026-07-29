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
REVISION_RULES_REPORT = "docs/codex_reports/revision_rules_integration_audit_2026-07-28.md"
REVISION_RULE_SOURCE_SHA256 = "937F6C5CCF6132C9E396C3906F07BCC87F218438109560105C1E9F71CBEBF304"
EXPECTED_REVISION_RULE_IDS = {f"RRC-{index:03d}" for index in range(1, 76)}

REQUIRED = [
    "AGENTS.md",
    "LIVE_WORKSPACE.md",
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
    "docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md",
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
    "configs/geophase_phase1_v2_s2_reference.yaml",
    "configs/geophase_phase1_v2_formal_manifest.yaml",
    "configs/geophase_phase1_s1_diffusive_sensitivity_mve.yaml",
    "configs/qiu_same_device_thermal_holdout_audit.yaml",
    "configs/qiu_vo2_phase1_source_contract.yaml",
    "tests/test_geophase_phase1_preregistration.py",
    "tests/test_geophase_phase1_v2_preregistration.py",
    "outputs/tables/geophase_phase1_v2/preregistration.json",
    "outputs/tables/geophase_phase1_v2/formal_evaluation_manifest.csv",
    "outputs/tables/geophase_phase1_v2/formal_evaluation_manifest.json",
    "docs/codex_reports/geophase_phase1_v2_s2_preregistration_2026-07-27.md",
    "scripts/audit_repository_realignment.py",
    "outputs/tables/repository_file_disposition.csv",
    "outputs/tables/repository_realign_phase0_summary.json",
    "docs/codex_reports/repository_realign_phase0_2026-07-25.md",
    "docs/codex_reports/phase1_contract_hardening_workspace_cleanup_2026-07-26.md",
    "docs/codex_reports/executive_guide_alignment_source_scale_review_2026-07-26.md",
    REVISION_RULES_REPORT,
    "docs/project_state/local_external_asset_registry.json",
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
    "LIVE_WORKSPACE.md",
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
    REVISION_RULES_REPORT,
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
        "configs/geophase_phase1_v2_s2_reference.yaml",
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


def check_revision_rules_integration() -> dict:
    report_path = ROOT / REVISION_RULES_REPORT
    if not report_path.exists():
        return {
            "status": "fail",
            "source_sha256": REVISION_RULE_SOURCE_SHA256,
            "expected_rule_count": len(EXPECTED_REVISION_RULE_IDS),
            "mapped_rule_count": 0,
            "missing_ids": sorted(EXPECTED_REVISION_RULE_IDS),
            "unexpected_ids": [],
            "duplicate_ids": [],
            "missing_markers": [f"{REVISION_RULES_REPORT}:missing"],
            "problems": [f"missing_report:{REVISION_RULES_REPORT}"],
        }
    report = read(REVISION_RULES_REPORT)
    row_ids = re.findall(r"^\|\s*(RRC-\d{3})\s*\|", report, re.MULTILINE)
    counts = {rule_id: row_ids.count(rule_id) for rule_id in set(row_ids)}
    missing_ids = sorted(EXPECTED_REVISION_RULE_IDS - set(row_ids))
    unexpected_ids = sorted(set(row_ids) - EXPECTED_REVISION_RULE_IDS)
    duplicate_ids = sorted(rule_id for rule_id, count in counts.items() if count != 1)

    required_markers = {
        "AGENTS.md": [
            "## Task Contract And Scope Discipline",
            "`lifecycle_state`: exactly",
            "`claim_supported` is a lifecycle milestone, not a fifth claim status.",
            "`validity: invalid`",
            "active-contract prohibition is authorization-binding",
        ],
        "docs/research_strategy/sci_delivery_pipeline.md": [
            "## Pre-Execution Requirement Contract",
            "analytic/limit cases -> short single-device run",
            "Formal baselines must include",
            "## Run Identity And Evidence Package",
            "isolated clean worktree or clone",
        ],
        "src/pinnpcm/physics/AGENTS.md": [
            "Map every claim-bearing 2D/2.5D model one-to-one",
            "Normalized coordinates may be network inputs",
            "dimensional, sign, and analytic/limit checks",
        ],
        "src/pinnpcm/pinn/AGENTS.md": [
            "A direct-solver/profile success",
            "at least five seeds",
            "remove one core module at a time",
        ],
        "scripts/AGENTS.md": [
            "A formal run must record `run_id`",
            "`outputs/runs/<run_id>/...`",
            "repair commit, regression test",
        ],
        "tests/AGENTS.md": [
            "a regression that reproduces the old failure",
            "debug artifacts remain non-voting",
        ],
        "docs/AGENTS.md": [
            "Internal reviews and project reports are leads, not fact sources.",
            "Execution reports are conclusion-first",
            "Each main figure serves one claim",
        ],
        "docs/templates/codex_final_report.md": [
            "objective:",
            "allowed_changes:",
            "prohibited_actions:",
            "lifecycle_state:",
            "execution_validity:",
            "anomalies_and_root_causes:",
            "push_status:",
            "pr_status:",
        ],
    }
    missing_markers: list[str] = []
    for rel, markers in required_markers.items():
        text = read(rel)
        missing_markers.extend(f"{rel}:{marker}" for marker in markers if marker not in text)
    if REVISION_RULE_SOURCE_SHA256 not in report:
        missing_markers.append(f"{REVISION_RULES_REPORT}:source_sha256")

    problems = [
        *(f"missing_id:{rule_id}" for rule_id in missing_ids),
        *(f"unexpected_id:{rule_id}" for rule_id in unexpected_ids),
        *(f"duplicate_id:{rule_id}" for rule_id in duplicate_ids),
        *missing_markers,
    ]
    return {
        "status": "pass" if not problems else "fail",
        "source_sha256": REVISION_RULE_SOURCE_SHA256,
        "expected_rule_count": len(EXPECTED_REVISION_RULE_IDS),
        "mapped_rule_count": len(set(row_ids) & EXPECTED_REVISION_RULE_IDS),
        "missing_ids": missing_ids,
        "unexpected_ids": unexpected_ids,
        "duplicate_ids": duplicate_ids,
        "missing_markers": missing_markers,
        "problems": problems,
    }


def check_current_router_semantics() -> dict:
    requirements = {
        "docs/project_state/reproduction_quickstart.md": [
            "Active Phase 1-v2 Read-Only Verification",
            "63 formal evaluation items",
            "NO_GO_RUNTIME_PERFORMANCE_ONLY",
            "do not rerun readiness",
        ],
        "docs/manuscript/submission_go_no_go.md": [
            "NO-GO at Phase 1-v2 runtime readiness",
            "NO_GO_RUNTIME_PERFORMANCE_ONLY",
            "63-item manifest",
        ],
        "docs/project_state/file_inventory.md": [
            "configs/geophase_phase1_v2_s2_reference.yaml",
            "implemented Phase 1-v2 S2 reference",
            "All 63 formal items remain `planned_not_executed`",
            "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        ],
    }
    obsolete = {
        "docs/project_state/reproduction_quickstart.md": [
            "No formal solver command exists yet",
            "exact 96-case inventory",
            "passive K-state fit",
        ],
        "docs/manuscript/submission_go_no_go.md": ["region-specific K-state"],
        "docs/project_state/file_inventory.md": [
            "No Phase 1 implementation or scientific output is listed",
            "future Phase 1 independent implementation when it exists",
        ],
    }
    missing: list[str] = []
    found_obsolete: list[str] = []
    for rel, markers in requirements.items():
        text = read(rel)
        missing.extend(f"{rel}:{marker}" for marker in markers if marker not in text)
        found_obsolete.extend(
            f"{rel}:{marker}" for marker in obsolete.get(rel, []) if marker in text
        )
    return {
        "status": "pass" if not missing and not found_obsolete else "fail",
        "missing": missing,
        "obsolete": found_obsolete,
    }


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
        "P1_v6_v8_material_stack_reference",
        "P1v2_s2_reference_solver",
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
    inventory_doc = read("docs/project_state/file_inventory.md")
    if "Phase 0 snapshot" not in inventory_doc or "not a live manifest" not in inventory_doc:
        problems.append("phase0_snapshot_boundary_not_labeled")
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


def check_workspace_routing_and_hygiene() -> dict:
    routing = read("LIVE_WORKSPACE.md")
    required_markers = [
        "ghy001122/PINN",
        "Portable live-checkout identity",
        "Current-machine routing record",
        "No absolute Windows path is a universal precondition",
        r"E:\PINN",
        "reference layer",
        "local_external_asset_registry.json",
    ]
    missing_markers = [marker for marker in required_markers if marker not in routing]

    pollution_root = ROOT / "%SystemDrive%"
    archives_root = ROOT / "outputs" / "archives"
    archive_files = []
    if archives_root.exists():
        archive_files = sorted(
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in archives_root.rglob("*")
            if path.is_file()
        )
    problems = list(missing_markers)
    if pollution_root.exists():
        problems.append("workspace_pollution:%SystemDrive%")
    if archive_files:
        problems.extend(f"repository_archive:{path}" for path in archive_files)
    return {
        "status": "pass" if not problems else "fail",
        "missing_markers": missing_markers,
        "pollution_root_present": pollution_root.exists(),
        "repository_archive_files": archive_files,
        "problems": problems,
    }


def check_local_external_asset_registry() -> dict:
    path = ROOT / "docs/project_state/local_external_asset_registry.json"
    problems: list[str] = []
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "fail", "problems": [str(exc)], "assets": 0}

    if registry.get("schema_version") != "local_external_asset_registry_v1":
        problems.append("schema_version")
    assets = registry.get("assets", [])
    if not assets:
        problems.append("assets_empty")
    for index, asset in enumerate(assets):
        prefix = f"asset_{index}"
        if asset.get("git_tracked") is not False:
            problems.append(f"{prefix}:git_tracked")
        if asset.get("required_for_clone_test_or_replay") is not False:
            problems.append(f"{prefix}:replay_dependency")
        digest = asset.get("sha256", "")
        if re.fullmatch(r"[0-9A-F]{64}", digest) is None:
            problems.append(f"{prefix}:sha256")
        if not isinstance(asset.get("bytes"), int) or asset["bytes"] <= 0:
            problems.append(f"{prefix}:bytes")
        if asset.get("evidence_role") != "project_context_archive_only":
            problems.append(f"{prefix}:evidence_role")
    return {
        "status": "pass" if not problems else "fail",
        "problems": problems,
        "assets": len(assets),
        "external_presence": "not_required_for_portable_governance",
    }


def check_phase1_contract_hardening() -> dict:
    config = read("configs/geophase_phase1_2p5d_reference.yaml")
    source = read("configs/qiu_vo2_phase1_source_contract.yaml")
    contract = read("docs/research_strategy/phase1_geophase_2p5d_reference_contract.md")
    required_config_markers = [
        "schema_version: geophase_phase1_2p5d_reference_v6",
        "formal_execution_count: 0",
        "checkpoint_a_must_stop_before_formal_campaign: true",
        "formal_campaign_requires_fresh_user_authorization: true",
        "source_only_config: configs/qiu_vo2_phase1_source_contract.yaml",
        "interdevice_substrate_resolved: false",
        "nonzero_dual_device_coupling_in_phase1: forbidden",
        "formal_case_inventory_total: 96",
        "fixed_physical_comparison_grid:",
        "fixed_physical_comparison_time_grid:",
        "zero_signal_policy:",
        "reduction_fit_contract:",
        "device_effective_normalization:",
        "analytic_source_scale_preflights:",
        "families: [thermal, circuit, combined_electrothermal]",
        "backward_euler_numerical_dissipation",
        "source_model_consistency_gate_not_independent_external_validation",
    ]
    required_source_markers = [
        "schema_version: qiu_vo2_phase1_source_contract_v2",
        "literature_reported:",
        "source_author_fitted_lumped_quantities:",
        "phase1_engineering_priors:",
        "unresolved_semantics:",
        "inherit_parameter_numeric_vote: false",
        "inherit_field_or_convergence_vote: false",
        "phase1_device_effective_normalization:",
        "local_intrinsic_material_property: false",
    ]
    required_contract_markers = [
        "Formal Case Inventory",
        "**96**",
        "Dual-Device Boundary",
        "nonzero dual-device",
        "without post-hoc time warping",
        "source-scale preflights",
        "Checkpoint Separation",
        "formal_execution_count=0",
        "combined electrothermal",
    ]
    missing = [
        f"config:{marker}" for marker in required_config_markers if marker not in config
    ]
    missing.extend(
        f"source:{marker}" for marker in required_source_markers if marker not in source
    )
    missing.extend(
        f"contract:{marker}" for marker in required_contract_markers if marker not in contract
    )
    if "inherited_provenance_config" in config:
        missing.append("config:historical_inherited_provenance_config_present")
    guide = read("docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md")
    for marker in [
        "v1.2-phase1v2-s2",
        "759DC17CBD7D6C884AF25F71ABF00ED833EEBDD7E7E477604B33EA7E6A75B517",
        "Repository adaptation record",
    ]:
        if marker not in guide:
            missing.append(f"guide:{marker}")
    return {"status": "pass" if not missing else "fail", "missing": missing}


def check_phase1v2_preregistration() -> dict:
    config = read("configs/geophase_phase1_v2_s2_reference.yaml")
    contract = read(
        "docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md"
    )
    manifest = read("configs/geophase_phase1_v2_formal_manifest.yaml")
    preregistration = json.loads(
        read("outputs/tables/geophase_phase1_v2/preregistration.json")
    )
    required_config_markers = [
        "schema_version: geophase_phase1_v2_s2_reference_v1",
        "task_id: Q2_PHASE1_V2_S2_REFERENCE",
        "formal_execution_count: 0",
        "formal_evaluation_item_total: 63",
        "nominal_vertical_memory_state_fields: []",
        "phase1v2_source_allowlist:",
        "overlap_audit_memory_rule:",
        "S1_sensitivity_route:",
    ]
    required_contract_markers = [
        "S2 nominal thermal closure",
        "63 evaluation items",
        "formal execution count is zero",
        "failed_but_informative",
    ]
    contract_normalized = " ".join(contract.split())
    required_manifest_markers = [
        "schema_version: geophase_phase1_v2_formal_manifest_v1",
        "total_evaluation_items: 63",
        "unique_execution_units: 60",
        "reused_evaluation_items: 3",
        "S1_items_in_formal_manifest: forbidden",
    ]
    missing = [
        f"config:{marker}"
        for marker in required_config_markers
        if marker not in config
    ]
    missing.extend(
        f"contract:{marker}"
        for marker in required_contract_markers
        if marker not in contract_normalized
    )
    missing.extend(
        f"manifest:{marker}"
        for marker in required_manifest_markers
        if marker not in manifest
    )
    if preregistration.get("formal_execution_count") != 0:
        missing.append("preregistration:formal_execution_count")
    if preregistration.get("evaluation_item_count") != 63:
        missing.append("preregistration:evaluation_item_count")
    if preregistration.get("status") != "preregistered_not_executed":
        missing.append("preregistration:status")
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
    checks["revision_rules_integration"] = check_revision_rules_integration()
    checks["current_router_semantics"] = check_current_router_semantics()
    checks["no_obsolete_current_route"] = check_no_obsolete_current_route()
    checks["claim_matrix_vocabulary"] = check_claim_matrix_vocabulary()
    checks["critical_markdown_links"] = check_markdown_links()
    checks["realignment_outputs"] = check_realignment_outputs()
    checks["phase0_report"] = check_phase0_report()
    checks["workspace_routing_and_hygiene"] = check_workspace_routing_and_hygiene()
    checks["local_external_asset_registry"] = check_local_external_asset_registry()
    checks["phase1_contract_hardening"] = check_phase1_contract_hardening()
    checks["phase1v2_preregistration"] = check_phase1v2_preregistration()

    critical_text = "\n".join(read(rel) for rel in ["AGENTS.md", "PROJECT_GOAL.md", "PROJECT_STATE.md", "NEXT_ACTIONS.md"])
    all_present = all(status in critical_text for status in CLAIM_STATUSES)
    checks["claim_vocabulary"] = {"status": "pass" if all_present else "fail", "all_four_present": all_present}

    template = read("docs/templates/codex_final_report.md")
    template_fields = [
        "task_name", "objective", "inputs", "outputs", "allowed_changes",
        "prohibited_actions", "success_gate", "failure_route", "budget", "assumptions",
        "base_sha", "final_sha", "branch", "changed_files", "git_status", "push_status",
        "pr_status", "run_id", "parent_run_id", "seed", "environment", "tests",
        "reproduction_commands", "frozen_gt_modified", "evidence_type", "lifecycle_state",
        "execution_validity", "claim_status", "supported_claims", "forbidden_claims",
        "actual_implementation", "core_results", "anomalies_and_root_causes",
        "artifact_paths", "goal_distance_change", "claim_changes", "new_blockers",
        "next_single_priority", "next_problem_remedy", "disposition",
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
