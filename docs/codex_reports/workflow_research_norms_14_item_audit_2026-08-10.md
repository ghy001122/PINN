---
task_name: workflow_research_norms_14_item_audit_2026_08_10
objective: Audit the current instruction and research-workflow documentation against fourteen user-supplied collaboration, execution, validation, safety, and research-posture requirements, then add only genuine gaps.
inputs:
  - applicable root and nested AGENTS.md files
  - project memory, workflow, policy, README, template, and command-safety documents
  - current authority chain and the prior RRC-001 through RRC-075 governance mapping
outputs:
  - this fourteen-item traceability report
  - minimal updates to existing instruction, workflow, durable-memory, and report-template owners
allowed_changes:
  - governance and instruction Markdown
  - the existing governance audit and its focused regression test
prohibited_actions:
  - scientific source code, scientific tests, configs, frozen GT, raw evidence, active phase, project state, queue, or manuscript-core changes
  - scientific execution, training, threshold changes, or publication actions
success_gate: All fourteen requirements have an explicit non-conflicting owner; documentation checks and a focused semantic coverage check complete; frozen GT remains unchanged.
failure_route: Preserve the higher-authority or stricter existing rule, leave unresolved conflicts visible, and make no scientific or state changes.
budget: One inventory pass, one minimal documentation patch, and one validation closeout.
assumptions:
  - Periodic updates means concise evidence-bearing updates during extended work, not arbitrary time-based churn of repository state files.
  - Sub-agent use remains conditional on runtime and user authorization.
base_sha: d0f0e6799f4f956262e0670999ab34f41baea4b1
final_sha: null
branch: codex/q2-m1-protocol-selected-equilibrium-manifold-mve-v1
changed_files:
  - AGENTS.md
  - docs/AGENTS.md
  - docs/research_strategy/codex_workflow_rules.md
  - docs/research_strategy/durable_project_memory.md
  - docs/research_strategy/sci_delivery_pipeline.md
  - docs/templates/codex_final_report.md
  - docs/codex_reports/workflow_research_norms_14_item_audit_2026-08-10.md
  - scripts/audit_project_governance.py
  - tests/test_project_governance.py
git_status: uncommitted documentation changes
push_status: not requested
pr_status: not requested
run_id: null
parent_run_id: null
seed: null
environment: Python 3.11 workspace venv; Windows PowerShell
tests:
  - "focused fourteen-item semantic coverage: 16/16 checks passed, including 14/14 matrix rows"
  - "git diff --check: passed"
  - "pre-amendment project governance audit: failed phase_consistency and low_token_context_budget; revision rules, final-report template, AGENTS chain size, and frozen-GT integrity passed"
  - "pre-amendment tests/test_project_governance.py: 3 passed, 2 failed on the same pre-existing governance-audit state"
  - "post-amendment arbitrary-size-gate regression: 1 passed"
  - "post-amendment governance audit: only phase_consistency remains failed; document byte-gate checks are absent; frozen-GT integrity passed"
reproduction_commands:
  - ./.venv/Scripts/python.exe scripts/audit_project_governance.py --no-write
  - ./.venv/Scripts/python.exe -m pytest tests/test_project_governance.py -q
  - git diff --check
frozen_gt_modified: false
evidence_type: documentation governance evidence
lifecycle_state: implemented
execution_validity: valid
claim_status: supported
supported_claims:
  - The fourteen requested workflow and research-norm requirements have explicit repository coverage after this patch.
forbidden_claims:
  - Any scientific result, claim upgrade, phase authorization, PINN result, experimental validation, or correction of pre-existing state-governance drift.
actual_implementation:
  - Added one cross-cutting root rule section and short operational checklist instead of creating a competing authority.
  - Added documentation-specific fact separation and visualization rules, stable user-preference memory, and explicit final-report evidence categories.
  - On user amendment, removed all three document-size pass/fail gates from the live governance audit rather than replacing 24,576 bytes with another threshold.
core_results:
  - Eight requirements already had strong direct coverage, three had partial coverage that was made explicit, and three had no direct rule and were added.
  - The focused semantic check passed all 16 assertions, including all fourteen matrix rows, durable-memory routing, and cross-document ownership.
  - The pre-amendment governance check confirmed the report template, prior 75-rule mapping, and all eight frozen-GT hashes. After the user amendment, the arbitrary size-gate failure was removed by policy and only the stale phase-consistency audit remains failed.
verified_facts:
  - No tracked workspace file named Memory.md or Rules.md exists; their roles are served by durable_project_memory.md, memory_policy.md, codex_workflow_rules.md, and .codex/rules/project_safety.rules.
  - The initial governance audit failed phase_consistency and low_token_context_budget before the fourteen-item patch; the user subsequently authorized removal of arbitrary document-size gates.
interpretations:
  - Centralizing cross-cutting behavior in root AGENTS.md and the short workflow checklist minimizes duplication while preserving discoverability.
unresolved_unknowns: []
anomalies_and_root_causes:
  - The existing phase-consistency audit still expects Q2_PHASE1_2P5D_REFERENCE_SOLVER while the live authority chain records Q2_PHASE1G_M1_PROTOCOL_SELECTED_EQUILIBRIUM_MANIFOLD_MVE.
  - The now-removed low-token context audit reported 34688 bytes against a 24576-byte limit before the user amendment; this remains historical diagnostic context, not a current gate.
artifact_paths:
  - docs/codex_reports/workflow_research_norms_14_item_audit_2026-08-10.md
goal_distance_change: Workflow clarity, execution efficiency, and collaboration discipline improve; scientific distance to the manuscript goal is unchanged.
claim_changes: []
new_blockers: []
next_single_priority: Preserve the live scientific queue; address the two pre-existing governance-audit failures only in a separately scoped state-governance repair.
next_problem_remedy: None is authorized by this documentation-only task.
disposition: stop
---

# Workflow And Research Norms: Fourteen-Item Coverage Audit

## Conclusion

The live instruction chain already covered scientific sourcing, goal and scope discipline, confirmation boundaries, restrained code changes, behavioral validation, asset protection, pre-execution planning, and aggressive-but-claim-gated research. This patch adds or makes explicit only the missing collaboration and efficiency rules. It does not change scientific authorization, evidence, or current state.

## Coverage Matrix

| ID | Requirement | Pre-patch finding | Authoritative coverage after patch |
| --- | --- | --- | --- |
| 1 | Visualize genuinely complex explanations | Missing | Root `AGENTS.md` communication rules; `docs/AGENTS.md`; short workflow checklist |
| 2 | Be concise and separate facts from guesses | Partial: concise reporting and evidence classes existed, but fact/inference/unknown labels were not explicit | Root and docs rules; final-report evidence-separation fields |
| 3 | Research from reliable sources | Strong existing coverage | `docs/AGENTS.md` primary-source hierarchy; provenance and literature tiers |
| 4 | Stay aligned with user goals and constraints | Strong existing coverage | Project goal, one-bottleneck selection, task contract, and scope discipline |
| 5 | Ask only for key decisions | Strong existing coverage | Root confirmation boundary and blocking-ambiguity rule |
| 6 | Use sub-agents purposefully and avoid meaningless parallelism | Missing | Root integration-owner rule and short workflow checklist |
| 7 | Keep code changes restrained; no unrelated refactor | Strong existing coverage | Root scope discipline and subtree implementation rules |
| 8 | Test actual behavior and results | Strong existing coverage | Root review posture, tests rules, and evidence state machine |
| 9 | Protect existing code and data | Strong existing coverage | Frozen-GT, unrelated-change, immutable-evidence, and destructive-operation rules |
| 10 | Report key outcomes without noisy progress | Partial: conclusion-first closeout existed, but update content was not bounded | Root and short workflow milestone-update rules |
| 11 | Update periodically | Missing | Evidence-bearing milestone and extended-wait update rule |
| 12 | Plan before execution | Strong existing coverage | Pre-execution task contract, gate card, and active-plan rules |
| 13 | Stay efficient; prevent endless audit/verification loops | Partial: one-bottleneck and stop gates existed, but unchanged re-audits were not explicitly barred | Root bounded-loop rule and short workflow stop discipline |
| 14 | Explore boldly; reject over-defensive research | Strong existing coverage, now operationally reinforced | Critical Research Mode, root exploration rule, and workflow checklist |

## Scope And Conflict Resolution

- `README.md` already routes execution to `AGENTS.md` and the canonical workflow, so duplicating these rules there would increase drift risk.
- `.codex/rules/project_safety.rules` is intentionally command-prefix safety policy, not a research-behavior owner; it remains unchanged.
- `durable_project_memory.md` records the stable preferences but remains non-authoritative under `memory_policy.md`.
- Periodic communication is tied to meaningful progress or extended waits, while unchanged-status chatter is prohibited; this resolves requirements 10 and 11 without encouraging noise.
- Sub-agent use is conditional on authorization and genuine independence, so it cannot override a runtime or task-specific prohibition on delegation.

## User Amendment: Structural Context Hygiene

The user explicitly rejected recurring document byte thresholds as an inefficient source of audit churn. The current rules now evaluate context and instruction hygiene through semantic ownership, currentness, task relevance, duplication, and staleness. The governance audit no longer makes the current handoff, AGENTS chain, or authority-context set pass or fail by byte count. A numeric limit is eligible only when a cited external system or explicit user-approved contract genuinely imposes it; it must not be repeatedly retuned as prose evolves.

This amendment does not rewrite historical reports that truthfully recorded the former 24,576-byte gate. It changes only current and future governance behavior.

## Evidence Boundary

This is documentation-governance evidence only. It does not validate a solver, execute a research phase, train a PINN, upgrade a claim, or repair the two pre-existing governance-audit failures.
