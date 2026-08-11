---
task_name: chatgpt_global_instruction_integration_audit_2026_08_11
objective: Review five user-provided ChatGPT project Markdown instruction/reference documents against the live repository governance chain, integrate only durable non-duplicative requirements, and publish one governance-only change set.
inputs:
  - five Markdown files in the user-provided ChatGPT project sources directory
  - applicable root and nested AGENTS.md files
  - root and project-local README, memory-policy, workflow, authority-routing, critical-research, command-safety, and Skill documents
outputs:
  - minimal updates to existing governance owners
  - this source-to-rule coverage and disposition report
allowed_changes:
  - workflow, research-norm, instruction, context-routing, and governance-report Markdown
prohibited_actions:
  - scientific code, configs, tests, data, results, frozen GT, claim matrix, active phase, project state, queue, or experiment execution
success_gate: Every durable source requirement is either mapped to existing coverage, integrated at one appropriate owner, or explicitly rejected as transient, conflicting, duplicated, or out of scope; focused semantic checks pass and frozen GT remains unchanged.
failure_route: Preserve the higher-authority repository rule, record the unresolved conflict, and do not import transient source snapshots or expand into scientific work.
budget: One external-source inventory, one parallel read-only coverage audit, one bounded documentation patch, one proportional validation closeout, and one atomic publication.
assumptions:
  - External ChatGPT project documents are advisory sources rather than repository authority.
  - The excluded DOCX is outside the user-declared five-Markdown scope.
  - Current PR, SHA, metric, and manuscript-priority snapshots belong in live state/evidence owners rather than durable global rules.
base_sha: 417e33ce8e6344efb998099417bbba354c5deea5
final_sha: null
branch: codex/global-reference-governance-integration-v1
changed_files:
  - AGENTS.md
  - README.md
  - docs/AGENTS.md
  - docs/research_strategy/context_index.md
  - docs/research_strategy/context_loading_policy.md
  - docs/research_strategy/current_research_handoff.md
  - docs/research_strategy/durable_project_memory.md
  - src/pinnpcm/physics/AGENTS.md
  - src/pinnpcm/pinn/AGENTS.md
  - docs/codex_reports/chatgpt_global_instruction_integration_audit_2026-08-11.md
git_status: uncommitted governance-only documentation changes
push_status: pending publication
pr_status: not requested; GitHub CLI authentication is unavailable, so the authorized Git push path is used without inventing a PR result
run_id: null
parent_run_id: null
seed: null
environment: Python 3.11 workspace venv; Windows PowerShell
tests:
  - external source identity: 5/5 SHA-256 matches passed
  - focused new-rule semantic coverage: 10/10 passed
  - git diff --check: passed
  - tests/test_project_governance.py: 4 passed, 2 failed only through pre-existing stale phase/delivery audit expectations
  - project governance audit: frozen GT, revision rules, critical links, and duplicate-Markdown checks passed; phase_consistency and delivery_contract remained stale-audit failures
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
  - The five scoped external Markdown documents were reviewed and their durable requirements were deduplicated against the live governance owners.
  - The integrated rules close specific citation, figure-data, authority-import, 2.5D, multistability, baseline, and inverse-identifiability gaps without changing scientific evidence or authorization.
forbidden_claims:
  - Any new scientific result, claim upgrade, phase change, experiment authorization, PINN success, inverse success, experimental validation, or correction of the underlying scientific-state registries.
actual_implementation:
  - Added only high-confidence missing rules to the existing authority, documentation, physics, PINN, and context-routing owners.
  - Removed stale phase-specific routing prose from README, context index, and current handoff instead of replacing it with another fixed snapshot.
  - Kept the research-module-recombination Skill unchanged because its mode, provenance, bounded-search, utility, evidence, and NO-GO salvage contracts already cover the external module-recombination material.
core_results:
  - Most external content was either a current scientific snapshot or already covered by repository rules and the latest Skill.
  - Eight durable operational gaps were closed and three routing surfaces were made snapshot-free.
  - No scientific file, frozen artifact, phase authority, state snapshot, queue, claim matrix, experiment, training run, or generated result was changed.
verified_facts:
  - The live checkout was clean at the start and its tree matched origin/main before this branch was created.
  - No tracked workspace file named Memory.md or Rules.md exists; durable_project_memory.md, memory_policy.md, codex_workflow_rules.md, and .codex/rules/project_safety.rules own those responsibilities.
  - The referenced research task reports that the latest research-module-recombination Skill is merged and ready for a first formal FAST_SCAN use.
interpretations:
  - Stable behavioral rules belong in AGENTS/context policy; time-sensitive PR outcomes and manuscript priorities should remain in current state/evidence surfaces.
  - Snapshot-free routers reduce future drift without weakening the active phase or evidence gates.
unresolved_unknowns: []
anomalies_and_root_causes:
  - The governance audit still hard-codes Q2_PHASE1_2P5D_REFERENCE_SOLVER while active_phase.md records the later completed Phase 1H checkpoint.
  - The delivery-contract audit still requires GeoPhase-HomoMoE-PINN and R3 markers in CODEX_CONTEXT.md even though that current context now records the later stopped forward-neural route.
  - Fast CI path filtering and the governance audit do not yet explicitly include .agents/** Skill files; this adjacent non-document infrastructure issue was recorded but not bundled into the user-scoped documentation integration.
artifact_paths:
  - docs/codex_reports/chatgpt_global_instruction_integration_audit_2026-08-11.md
goal_distance_change: Governance portability, evidence traceability, and context efficiency improve; scientific distance to the manuscript goal is unchanged.
claim_changes: []
new_blockers: []
next_single_priority: Publish this governance-only commit, then let the referenced research task refresh the live authority chain and use the latest Skill only under its active-phase contract.
next_problem_remedy: Treat stale audit expectations and .agents CI coverage as a separately scoped governance-infrastructure repair rather than extending this documentation task.
disposition: stop
---

# ChatGPT Global Instruction Integration Audit

## Conclusion

The five external Markdown files are useful as synchronized research context, but most of their content is either transient post-PR43 state or already owned by the repository's root rules, Critical Research Mode, delivery pipeline, and latest `research-module-recombination` Skill. This integration therefore adds only durable missing constraints and removes stale routing snapshots. It does not import the external files wholesale and does not perform research.

## Reviewed External Sources

The sources were read as UTF-8 from the user-provided ChatGPT project directory. Hashes identify the reviewed versions without making that machine-local directory a repository dependency.

| Source | SHA-256 | Durable disposition |
| --- | --- | --- |
| `Critical Research Mode for PINN Phase-Transition Project.md` | `69041ABB121609E5B85BABA77816A13765206EB4DD90AF9C265135A21C52F4DF` | Add portable-citation and true-2.5D rules; retain current PR/disposition text only as external context. |
| `deep-research-report-2026.8.5(1).md` | `FC105DE9868C93E1B974FBB535295DD3DD81BA52F43F56875627AD848B1A1AFD` | Add multistability, simple-baseline, and inverse-identifiability rules; do not import result metrics. |
| `PINN_phase_change_Deep_Research_brainstorm_revised_2026-07-24(6).md` | `DE63F81B75AE242726A8409C1B3055EB2CC81A308D6269615260E6FC41BC8EB4` | Existing Skill already owns bounded recombination and salvage; retain brainstorm only as a lead. |
| `PINN-based_Phase_Change_Materials_Research_Executive_Guide.md` | `DC1D7A93D33AA7AD9932E78D0B76D6052DD7D4FC21B39D64BCF06477541974AD` | Add machine-readable figure-data rule; do not copy current manuscript routing into stable policy. |
| `Prompt of PINN(2).md` | `17D122F3379F66205CE37547C7F05CE495D95E5C36A3304677EA4FD7F9ACC2DB` | Add advisory-source and on-demand remote-verification rules; preserve the repository's existing authority order. |

## Coverage And Changes

| Durable requirement | Pre-change finding | Owner after integration |
| --- | --- | --- |
| External AI/chat-project documents cannot establish facts or authorize work | Implicit through memory/archive rules, not explicit for imported source documents | `context_loading_policy.md`; `context_index.md`; current handoff |
| Remote cloud state is checked only when it affects the task | External prompt over-broadly required it every time | `context_loading_policy.md` |
| Session-internal citation markers cannot enter formal evidence | Missing explicit rule | `docs/AGENTS.md` |
| Claim figures/tables trace to machine-readable evidence; no image transcription or frozen rerun for layout | Figure source data was required, but these failure modes were not explicit | `docs/AGENTS.md` |
| Claim-bearing 2.5D means actual x-y geometry plus documented vertical reduction | Partially covered by device mapping; one-dimensional fallback was not locally barred | `src/pinnpcm/physics/AGENTS.md` |
| Multistable learning uses deployable selection semantics and separate ambiguity/coverage/refusal metrics | Present in executed evidence, not durable PINN subtree rules | `src/pinnpcm/pinn/AGENTS.md` |
| Neural value is tested against the strongest applicable analytic/linear/reduced baseline | Independent solver, vanilla PINN, and supervised surrogate existed; simple analytic/ridge/POD dominance was not generalized | `src/pinnpcm/pinn/AGENTS.md` |
| Terminal-only inverse work requires solver-side identifiability before a neural head | Broad claim boundary existed; explicit precondition was missing locally | `src/pinnpcm/pinn/AGENTS.md` |
| Prerequisite language must follow the active phase rather than a hard-coded old phase | Root high-risk boundary named an obsolete active Phase 1 gate | `AGENTS.md` |
| README/index/handoff should route rather than repeat transient status | Three surfaces contained outdated Phase 1-v2/E0 snapshots | `README.md`; `context_index.md`; current handoff; durable-memory wording |

## Deliberately Not Duplicated

- The fourteen collaboration and efficiency requirements from the prior audit already remain explicitly covered; no new byte/token/line/file-count gate was added.
- Module provenance, contribution taxonomy, `FAST_SCAN`/`FULL_DESIGN`/`CLOSEOUT_SALVAGE`, bounded combinations, utility ranking, minimum evidence, and NO-GO salvage already have one complete owner in the latest Skill.
- PR #36--#44 SHAs, metrics, the current NO-GO, and the current limitation-manuscript priority are time-sensitive state/evidence, not durable global instructions.
- The external prompt's alternate authority order was rejected because `active_phase.md` owns authorization while `PROJECT_STATE.md` owns the snapshot.
- The external prompt's every-task cloud check was narrowed to remote-dependent work to avoid repeated status audits.

## Evidence Boundary

This is documentation-governance evidence only. It neither executes nor validates a scientific method, and it does not change the current scientific disposition.
