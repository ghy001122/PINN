---
task_name: revision_rules_integration_audit_2026_07_28
objective: Integrate every supplied Revision of Rules and Command requirement into the existing repository authority and workflow without changing scientific authorization.
inputs:
  - E:/PINN/Revision of Rules and Command.md
  - applicable AGENTS.md chain
  - current authority documents and two-tier validation workflows
outputs:
  - this 75-item traceability audit
  - strengthened instruction, pipeline, report-template, router, and governance checks
allowed_changes:
  - governance and instruction Markdown
  - governance audit and focused contract tests
  - existing validation path filters
prohibited_actions:
  - frozen GT or claim-bearing evidence mutation
  - physics, threshold, 63-item manifest, active-phase, or scientific-claim changes
  - readiness, formal, PINN, inverse, FEM/3D, M44, or NbO2 execution
success_gate: All 75 RRC IDs have one auditable coverage row; semantic governance and workflow checks pass; frozen GT hashes and mtimes remain unchanged.
failure_route: Preserve the stricter active contract, stop any scientific expansion, and report unresolved principle conflicts for user decision.
budget: Documentation and lightweight CPU governance validation only.
assumptions:
  - The supplied revision is a governance source, not scientific evidence.
  - Existing stricter gates remain in force when they do not conflict in principle.
base_sha: 85e4257fc01af2e0bf706ef9001f263b1420ecaa
final_sha: null
branch: codex/revision-rules-governance
changed_files:
  - .github/workflows/read_only_validation.yml
  - AGENTS.md
  - docs/AGENTS.md
  - docs/codex_reports/revision_rules_integration_audit_2026-07-28.md
  - docs/manuscript/submission_go_no_go.md
  - docs/project_state/file_inventory.md
  - docs/project_state/reproduction_quickstart.md
  - docs/research_strategy/sci_delivery_pipeline.md
  - docs/templates/codex_final_report.md
  - scripts/AGENTS.md
  - scripts/audit_project_governance.py
  - src/pinnpcm/physics/AGENTS.md
  - src/pinnpcm/pinn/AGENTS.md
  - tests/AGENTS.md
  - tests/test_project_governance.py
  - tests/test_validation_workflow_contract.py
git_status: dedicated governance branch pending explicit-path commit
push_status: pending; final commit SHA and push result are reported at task delivery
pr_status: separate governance PR pending after PR 8 merge; PR 8 remains unchanged
run_id: null
parent_run_id: null
seed: null
environment: Python 3.11 workspace venv; Windows PowerShell
tests:
  - "focused governance/workflow tests: 9 passed"
  - "full governance audit: pass_with_manual_review; zero failed checks"
  - "fast-checkout governance audit: pass_with_manual_review; zero failed checks"
  - "historical evidence manifest: 23 entries, all passed"
  - "tracked JSON: 230/230 passed"
  - "frozen GT: 8/8 hashes and all pre/post mtimes unchanged"
reproduction_commands:
  - ./.venv/Scripts/python.exe -m pytest tests/test_project_governance.py tests/test_validation_workflow_contract.py -q
  - ./.venv/Scripts/python.exe scripts/audit_project_governance.py --no-write
  - ./.venv/Scripts/python.exe scripts/audit_project_governance.py --no-write --fast-checkout
  - ./.venv/Scripts/python.exe scripts/validate_historical_evidence_manifest.py
  - ./.venv/Scripts/python.exe scripts/validate_tracked_json.py
frozen_gt_modified: false
evidence_type: documentation governance evidence
lifecycle_state: implemented
execution_validity: valid
claim_status: supported
supported_claims:
  - The supplied governance requirements have versioned, auditable repository coverage.
forbidden_claims:
  - Any Phase 1 scientific pass or failure, readiness authorization, formal execution, PINN result, inverse result, or experimental validation.
actual_implementation:
  - Strengthened existing authorities and their semantic audit instead of duplicating the full rule source as a new current-state dashboard.
core_results:
  - Seventy-four numbered clauses and one chain principle were mapped.
anomalies_and_root_causes:
  - Two current routers retained superseded K-state/96-item/no-solver wording because prior governance checked file presence, not current semantics.
artifact_paths:
  - docs/codex_reports/revision_rules_integration_audit_2026-07-28.md
goal_distance_change: Governance traceability and future execution discipline improved; scientific distance is unchanged.
claim_changes: []
new_blockers: []
next_single_priority: Preserve the current Phase 1-v2 performance-only NO-GO and await the already-required user decision.
next_problem_remedy: No scientific remedy is authorized by this documentation task.
disposition: stop
---

# Revision Rules Integration Audit

## Conclusion

All 74 numbered requirements and the final evidence-chain principle in the supplied document now have an explicit repository owner. Existing equivalent constraints were left in place; only genuine gaps or ambiguity were strengthened. This task changes governance and workflow coverage only. It does not modify or reinterpret the current Phase 1-v2 `NO_GO_RUNTIME_PERFORMANCE_ONLY` boundary.

Source identity:

- source: `E:/PINN/Revision of Rules and Command.md`
- lines audited: 1-109
- SHA-256: `937F6C5CCF6132C9E396C3906F07BCC87F218438109560105C1E9F71CBEBF304`
- source role: user-supplied governance authority for this integration; not scientific evidence and not a portable replay dependency

## Clause-By-Clause Coverage

`Existing` means an equivalent or stricter rule already existed and its owner was not rewritten merely for duplication. `Strengthened` means a missing operational detail, ambiguity resolution, router correction, or regression guard was added.

| Rule | Source | Requirement digest | Disposition | Authoritative coverage |
| --- | --- | --- | --- | --- |
| RRC-001 | L3 | One-month default, PINN plus phase-transition-material Q2 objective, efficiency/value filter | Existing | `PROJECT_GOAL.md`; execution guide header and mandatory filter |
| RRC-002 | L4 | Real in-plane 2.5D identity, VO2 primary, material-specific NbO2 auxiliary | Existing | `PROJECT_GOAL.md`; execution guide Sections 2-3; physics rules |
| RRC-003 | L5 | Pre-task summary: objective, inputs/outputs, scope, prohibitions, gates/routes, budget | Strengthened | root `AGENTS.md` Task Contract; pipeline Pre-Execution Contract; final-report template |
| RRC-004 | L6 | Recheck only requirement deltas; ask only for material ambiguity | Strengthened | root Task Contract; pipeline Pre-Execution Contract |
| RRC-005 | L7 | Blocking ambiguity stops; non-blocking uses reversible conservative assumption and is reported | Strengthened | root Task Contract; pipeline; report assumptions field |
| RRC-006 | L8 | No adjacent scope expansion, repository overhaul, 3D/phase-field, unified material law, or extra branch | Strengthened | root scope discipline and special complexity gate |
| RRC-007 | L9 | Map each task to problem, claim, figure/table, ablation, or reviewer question | Existing | root Delivery Selection; `PROJECT_GOAL.md`; execution guide Section 0 |
| RRC-008 | L10 | Explain equations, network I/O, losses, control flow, data, and intended effect; no shorthand-only plan | Strengthened | root Task Contract; pipeline Pre-Execution Contract |
| RRC-009 | L11 | Separate five lifecycle states | Strengthened | root dual-axis evidence fields; pipeline lifecycle table; report template |
| RRC-010 | L12 | One formal active stage; later routes cannot run before predecessors | Existing | root/goal one-bottleneck rule; `active_phase.md`; phase ladder |
| RRC-011 | L16 | Formal preregistration freezes hypothesis through repair plan and Git SHA | Strengthened | pipeline Debug/Formal contract and Gate Card; execution guide Phase 0 |
| RRC-012 | L17 | Debug/formal isolation; debug excluded from main evidence; formal uses frozen clean environment | Strengthened | pipeline Run Classes; scripts rules |
| RRC-013 | L18 | Fixed claim-bearing scale ladder from analytic limits to full multi-seed run | Strengthened | pipeline scale-up paragraph; tests rules; execution guide phases |
| RRC-014 | L19 | Independent 2.5D solver gates precede formal PINN judging | Existing | `PROJECT_GOAL.md`; execution guide Gate 1; active phase restrictions |
| RRC-015 | L20 | R1 minimum positive 2.5D hybrid forward/conservation/OOD role | Existing, stricter | goal and guide require both geometry and protocol OOD, not merely either one |
| RRC-016 | L21 | R2 only after R1; separate expert/homotopy ablations and synergy | Existing | goal R2 lane; execution guide Phase 5/Gate 5 |
| RRC-017 | L22 | Solver-first R3 before inverse head, protocol design, or refusal | Existing | goal R3 lane; execution guide Phase 6 |
| RRC-018 | L23 | Extra epochs cannot mask structural failure | Strengthened | PINN subtree rules; pipeline failure classification |
| RRC-019 | L24 | High-risk max attempts/time and conservative downgrade | Strengthened | pipeline formal contract and Gate Card; root high-risk audit rule |
| RRC-020 | L25 | Active-contract prohibition cannot be silently restarted | Strengthened | root authorization layering; pipeline active-route rule |
| RRC-021 | L29 | One-to-one literature-device/domain mapping with dimensions, regions, electrodes, BCs, coordinates | Strengthened | physics subtree rules; execution guide physical contract |
| RRC-022 | L30 | Geometry comparisons use physical units; normalized coordinates are input-only | Strengthened | physics subtree rules |
| RRC-023 | L31 | Device-level G/C defaults to identifiable S2; higher memory needs independent evidence | Existing and strengthened | execution guide S2/S1 contract; physics subtree rule |
| RRC-024 | L32 | Device-effective Qiu thermal quantities are not intrinsic VO2 properties | Existing | goal; execution guide Sections 3.1/3.3; physics rule |
| RRC-025 | L33 | VO2 and NbO2 use separate constitutive kernels and parameters | Existing | root/physics rules; execution guide Sections 3.5/3.8 |
| RRC-026 | L34 | State s is effective conductive coordinate/internal variable, not measured phase fraction | Existing and strengthened | execution guide Section 3.5; physics subtree rule |
| RRC-027 | L35 | Variable definition/unit/scope/ICBC/code name plus dimensional/limit/sign checks | Strengthened | physics subtree variable-to-code contract; docs equation rule |
| RRC-028 | L36 | 2.5D is conservative reduction with closed current/energy/vertical/port/RC ledger | Existing | root claim boundary; physics rules; execution guide Sections 3.2-3.7 |
| RRC-029 | L37 | White-box kernel before freely predicting all hidden physics | Strengthened | execution guide B prime; physics subtree rule |
| RRC-030 | L38 | 3D, full phase-field, or vacancy PDE only after localized irreparable reduced-model defect | Existing and clarified | execution guide stop rule; root special complexity gate |
| RRC-031 | L42 | Exact synthetic digital-twin identity; digitization/reproduction are not own experiments | Existing and clarified | root evidence types; goal/guide; docs rules |
| RRC-032 | L43 | No unique full hidden-field claim from sparse ports without identifiability | Existing | critical research mode; goal; execution guide R3 |
| RRC-033 | L44 | Port fit needs Jacobian, subspace, profile, and finite perturbation checks for inverse | Existing | execution guide Phase 6; PINN rules |
| RRC-034 | L45 | Solver/profile success is not PINN success | Strengthened | PINN subtree direct-solver boundary; root high-risk claims |
| RRC-035 | L46 | FVM anchors require `hybrid PINN`, never data-free/self-supervised relabeling | Existing | PINN subtree identity rules; goal/guide |
| RRC-036 | L47 | Different GT/PINN discretization and noise/jitter/bias/drift/model-missing safeguards | Existing and strengthened | execution guide Phase 2; PINN subtree rules |
| RRC-037 | L48 | Case/geometry/protocol/regime holdout; no adjacent point split | Existing and strengthened | execution guide Phase 2; PINN subtree rules |
| RRC-038 | L49 | Test truth cannot construct bases/statistics/thresholds/refusal | Existing and strengthened | PINN leakage rule; execution guide Phase 6 |
| RRC-039 | L50 | Solver, vanilla PINN, supervised proxy; inverse adds solver/profile baseline | Existing and strengthened | execution guide Phase 3; pipeline/PINN formal baseline rule |
| RRC-040 | L51 | Match data, collocation, search, compute; disclose parameter differences | Existing | PINN rules; execution guide fairness contract |
| RRC-041 | L52 | At least five preregistered seeds and full distribution/worst-case reporting | Existing and strengthened | execution guide fairness contract; pipeline/PINN rules |
| RRC-042 | L53 | One-core-module-at-a-time ablation | Strengthened | pipeline and PINN subtree rules |
| RRC-043 | L54 | No post-hoc metric/threshold/domain/GT changes after failure | Existing | execution guide metrics gate; tests threshold rule; root frozen rule |
| RRC-044 | L58 | Four and only four claim statuses | Existing | root Claim Gate; critical research mode; goal |
| RRC-045 | L59 | Execution facts and scientific claims remain separate | Existing | root Review Posture; pipeline state machine |
| RRC-046 | L60 | Invalid/interrupted/unevaluated is forbidden plus invalid validity; only valid gate miss is informative failure | Strengthened | root dual-axis rule; pipeline lifecycle/validity rule |
| RRC-047 | L61 | Historical identifiability and M37/M44 failures cannot be rewritten | Existing | goal retained history; archive policy; claim matrix |
| RRC-048 | L62 | Plans and expectations cannot masquerade as completed abstract/conclusion contributions | Strengthened | docs subtree rules; pipeline manuscript gate |
| RRC-049 | L63 | Absolute novelty/recovery/convergence/replacement terms require search and evidence | Strengthened | docs subtree rules; execution guide completion checklist |
| RRC-050 | L64 | PINN must show a positive role unavailable to pure MLP | Existing | goal North-Star/Definition of Done; execution guide R1/reviewer defense |
| RRC-051 | L65 | Title downgrades with R3/R2 evidence | Existing | goal downgrade rules; execution guide paper identities |
| RRC-052 | L66 | One claim per main figure; prioritize informative nonredundant evidence | Existing and strengthened | goal lifecycle; execution guide main figures; docs rule |
| RRC-053 | L70 | Search implementation/callers/tests/license/compatibility before reuse or addition | Strengthened | root scope discipline; scripts subtree rule |
| RRC-054 | L71 | Frozen historical assets read-only; new configs/outputs are isolated | Strengthened | root Engineering Rules; archive policy; scripts frozen rule |
| RRC-055 | L72 | Formal run stores run ID, SHA, seed, environment, parent | Strengthened | pipeline Run Identity; scripts rules; report template |
| RRC-056 | L73 | Preserve evidence-value package, not every rebuildable cache | Strengthened | pipeline Run Identity; scripts rules |
| RRC-057 | L74 | Structured outputs without scattered or competing roots | Strengthened with path reconciliation | `outputs/runs/<run_id>/...` in pipeline/scripts; existing `outputs/` rule preserved |
| RRC-058 | L75 | Rebuildable environment and exact launch command | Strengthened | scripts rules; report template/pipeline |
| RRC-059 | L76 | Classify code/environment/numerical/config/scientific failure before repair | Strengthened | pipeline Failure Routing; scripts rules |
| RRC-060 | L77 | Existing report/experiment registry records full failure history | Strengthened without new registry | pipeline/scripts rules; report anomaly fields |
| RRC-061 | L78 | Repair adds old-error regression and reruns smallest affected valid work | Strengthened | tests/scripts/root rules; pipeline repair rule |
| RRC-062 | L79 | No opportunistic unrelated repair | Strengthened | root scope discipline |
| RRC-063 | L80 | Atomic commits; report branch/SHA/push/PR | Strengthened | root/scripts rules; report template |
| RRC-064 | L81 | No ceremonial repeated governance/branch/rename/history rewrite | Existing and strengthened | pipeline hygiene; root/scripts rules |
| RRC-065 | L82 | Clean replay from frozen commit/config into new output directory | Existing and operationally clarified | guide reproduction checklist; pipeline isolated-worktree replay gate |
| RRC-066 | L86 | Internal reviews are leads; facts return to original paper/supplement | Strengthened | docs subtree source hierarchy |
| RRC-067 | L87 | Primary/supplement/data/code source priority and pinpoint citations | Strengthened | docs subtree rules |
| RRC-068 | L88 | No all-post-2023 rule; cite original/authoritative foundations | Strengthened | docs subtree rules |
| RRC-069 | L89 | Borrowed-module provenance/license/modification/ablation/claim audit | Existing and strengthened | execution guide source-audit template; docs subtree rule |
| RRC-070 | L90 | Recombination is not originality without problem-driven novelty, synergy, insight | Existing | execution guide reviewer verdict and source audit; docs rule |
| RRC-071 | L91 | Defined evidence-bound language; no acronym camouflage | Strengthened | docs subtree rules; critical research mode |
| RRC-072 | L92 | Conclusion-first report with implementation/results/errors/artifacts/Git/next remedy | Strengthened | docs rules; expanded final-report template |
| RRC-073 | L93 | Every report states what can and cannot be claimed | Existing and strengthened | docs rules; report template evidence-boundary section |
| RRC-074 | L94 | Next priority remains solver -> R1 -> R2 -> solver-first R3 | Existing | project goal phase ladder; active phase; execution guide |
| RRC-075 | L96-108 | Requirement contract -> frozen implementation -> small validation -> formal experiment -> audit -> downgrade | Existing and reinforced | pipeline state machine and formal scale ladder |

## Principle-Conflict Resolution

1. The five lifecycle values and four claim statuses are orthogonal. `claim_supported` remains a lifecycle milestone; it is not a fifth claim word.
2. `invalid` is an execution-validity value paired with `claim_status: forbidden`, not an added claim status.
3. Clarification policy and action authorization are separate: unchanged requirements are inherited, while frozen/destructive/dependency/provenance/budget/history actions retain their approval gates.
4. A `forbidden` claim does not alone ban bounded exploration, but an explicit `active_phase.md` execution prohibition does. Reopening needs versioned authorization.
5. The fixed scale ladder governs claim-bearing expansion. Debug/mechanism/proxy work remains non-voting and cannot skip gates.
6. Full 3D, full phase-field, vacancy PDE, and unified multi-material work use the revision's stricter special gate even though other high-risk ideas may receive bounded exploration.
7. The exact synthetic-evidence phrase applies to project-generated scientific model outputs; governance facts, external literature evidence, and future provenance-backed measurements remain separate evidence types.
8. The suggested `runs/` layout is reconciled as `outputs/runs/<run_id>/...`; no repository migration or duplicate root is created.
9. Clean replay uses an isolated worktree/clone and new output directory; it never resets or cleans the user's active worktree.

## Workflow And Router Findings

- The existing public fast plus manual trusted-full validation design remains the only CI structure.
- Fast-validation path filters now cover project Codex policy, `docs/AGENTS.md`, research prompts, and report templates so authority-only changes cannot silently miss CI.
- The governance audit now checks all 75 mapping IDs, core semantic markers, expanded report fields, and current-router semantics.
- `reproduction_quickstart.md`, `submission_go_no_go.md`, and the active file inventory were corrected from retired K-state/96-item/no-solver wording to the current Phase 1-v2 S2/controller-v2 boundary.
- Clean claim-bearing replay is a future precondition. No formal scientific result exists, so the current full-validation workflow is not misrepresented as already replaying unavailable main figures or tables.

## Evidence Boundary

Can be claimed: the supplied governance requirements were exhaustively mapped, missing operational controls were integrated, and regression guards passed their focused and governance validations.

Cannot be claimed: Phase 1 success or scientific failure, campaign runtime feasibility, formal authorization/execution, R1/R2/R3 evidence, Qiu reproduction, PINN success, inverse success, experimental validation, or any change to the active performance-only stop.

## Validation And Closeout

- Focused governance/workflow contract tests: `9 passed`.
- Full and fast-checkout governance audits: `pass_with_manual_review`, zero failed checks; the 75-ID map, semantic markers, report fields, router semantics, links, context budget, and duplicate checks passed.
- Historical evidence manifest: all 23 entries passed; no history verification was requested for this documentation task.
- Tracked JSON: `230/230` passed.
- Frozen GT: all eight SHA-256 values and every pre/post mtime were byte-for-byte/time-for-time unchanged.
- Remaining manual notes are unchanged project limitations: project-local Codex policy auto-loading/syntax cannot be verified in this runtime, and portable Git mtimes are not generally authoritative (the task-specific comparison above was completed).
- No scientific run, readiness rerun, formal item, or output builder was executed.
