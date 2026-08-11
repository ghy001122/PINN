# Legacy Instruction Conflict Audit — 2026-08-11

## Conclusion

The workspace contained no new byte/token/line/file-count governance gate and
no instruction file that warranted deletion. The high-confidence conflicts
were lifecycle and routing errors: old contracts still called themselves
active, a dated submission decision was presented as current, the long Q2
guide still prescribed Phase 0 -> Phase 1 -> R1 as the immediate route, and
several indexes hard-coded Phase 1-v2 as a universal prerequisite.

This change reclassifies those surfaces without rewriting their scientific
results. Current authorization now consistently routes through the applicable
`AGENTS.md` chain, `active_phase.md`, `PROJECT_STATE.md`, and `NEXT_ACTIONS.md`;
historical contracts retain their original text behind an explicit lifecycle
notice.

## Task Contract

- Objective: reconcile old workflow, research-governance, and instruction
  documents with the latest repository rules and actual phase lifecycle.
- Base SHA: `256a4107593af8d00513b3910b90824037f52944`.
- Branch: `codex/global-reference-governance-integration-v1`.
- Inputs: all 278 tracked Markdown files, including 6 applicable/nested
  `AGENTS.md` files and 11 Markdown files under `docs/archive/`; current
  authority/state files; current project-local Skill; repository rule files;
  Git history and cloud identity only where needed for publication.
- Allowed changes: workflow, research-norm, instruction, lifecycle, context,
  provenance-routing, and manuscript-routing documentation.
- Prohibited changes: scientific code, configs, tests, data payloads, generated
  evidence, frozen GT, experiment results, claim outcomes, current phase state,
  thresholds, or a substantive research run.
- Success gate: stale live routing is removed or visibly reclassified; current
  authority remains singular; historical evidence remains recoverable; focused
  semantic and governance checks give real results.
- Failure route: preserve the questionable surface and report the conflict
  instead of guessing or rewriting scientific history.
- Budget: one bounded audit/edit/validation loop; no repeated unchanged audit.

## Findings And Disposition

| Conflict class | Representative surfaces | Disposition |
| --- | --- | --- |
| Historical phase described as current | Phase 1-v2 contracts, reproduction quickstart, file inventory, method equations | Added lifecycle notices or changed only the router/heading; retained contract bodies and results. |
| Old linear prerequisite treated as universal | `PROJECT_GOAL.md`, workflow checklist, Q2 guide, current evidence candidate table | Scoped prerequisites and NO-GOs to their named implementation, premise, data contract, budget, and interfaces; delegated current eligibility to the active phase. |
| Exploration language could bypass an explicit phase prohibition | Critical Research Mode and durable project memory | Distinguished claim status `forbidden` from an authorization-binding active-phase prohibition. |
| Old positive-only manuscript gate blocked the current limitation route | manuscript README/registry, historical archive index, final figure roster | Preserved positive R1 evidence requirements while permitting a separately versioned limitation/negative manuscript when the active evidence route authorizes it. |
| Dated decision or report used as live state | `submission_go_no_go.md`, `docs/codex_reports/` | Reclassified the dated decision and added a directory-level report lifecycle policy. |
| Long design guide used as current router | root/context/archive indexes and the guide itself | Downgraded it to a versioned long-term design reference; replaced its “current immediately” route and mandatory remote-main check. |
| Skill mode flattened into full execution design | SCI delivery pipeline | Added `FAST_SCAN`, `FULL_DESIGN`, and `CLOSEOUT_SALVAGE` routing; only separately authorized full design can become an execution contract. |
| External AI/local pack could be mistaken for authority | Q2 guide source list and `references/project_sources/README.md` | Marked these as advisory integration provenance requiring original-source/current-repository verification. |
| Stale directory responsibility | project tree and literature-data README | Replaced transient Phase 1/current-run wording with semantic ownership and provenance rules. |

No complete document was deleted. Archive/report files contain unique
preregistration, negative-result, replay, or reviewer-defense provenance, and a
hash grouping of the audited archive/report/reference Markdown set found no
exact duplicate suitable for high-confidence deletion.

## Protected Boundaries

- No scientific implementation, config, test, dataset payload, figure/table,
  experiment registry outcome, claim matrix row, or active phase/state file was
  changed.
- Frozen Ground Truth v1.1 paths and content were not touched.
- Historical metrics and exact terminal dispositions remain unchanged.
- Task-relative scientific-state wording observed in `CODEX_CONTEXT.md` and
  PR-attribution wording observed in `NEXT_ACTIONS.md` were left unchanged
  because correcting them would cross this governance-only task into current
  research-state maintenance.

## Validation

- Current stored-evidence contract tests: `26 passed` in `21.63 s` for the M1
  self-consistent IMT gate, protocol-selected equilibrium manifold, and
  protocol-manifold branch-aware surrogate suites. These are read-only tests;
  no training or reference solve was launched.
- Governance audit: frozen GT integrity passed for all 8 controlled files;
  current-router semantics, required files, single current snapshot, critical
  links, revision-rule integration, claim vocabulary, archive hygiene, and
  duplicate-active-Markdown checks passed.
- Governance audit overall remains `fail` on two pre-existing stale checker
  assumptions: `phase_consistency` still expects
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`, and `delivery_contract` still expects old
  literal markers. This task did not modify the Python audit or tests because
  the authorized scope is documentation only.
- Focused governance pytest: `4 passed, 2 failed`; both failures are the same
  stale `phase_consistency`/overall-audit condition, not a new documentation
  defect. The initially exposed stale quickstart-marker check was resolved by a
  truthful “formerly titled” historical label; its audit now passes.
- Four content-addressed equivalence contracts were initially found to reject
  inline lifecycle notices through frozen SHA tests. Their edits were fully
  reverted; no lock hash was changed. The focused equivalence suite then gave
  `152 passed, 1 failed`, with the sole failure an existing stale expectation
  that `NEXT_ACTIONS.md` repeat an older Qiu checkpoint; no SHA assertion failed.
- Semantic scope check: 39 tracked Markdown modifications plus 2 new Markdown
  audit/index files (41 intended paths total); zero changes under
  `configs/`, `src/`, `scripts/`, `tests/`, `outputs/`, or `data/processed/`;
  11 directly opened non-content-addressed historical contracts carry lifecycle
  notices. Frozen content-addressed contracts are classified only through
  external indexes and remain byte-clean relative to HEAD.
- `git diff --check`: pass. Reported CRLF-to-LF normalization notices are Git
  working-copy warnings, not whitespace errors.

The publication commit SHA, push status, and PR status are reported in the user
closeout because a commit cannot contain its own SHA.

## Claim And Goal Impact

- Scientific evidence added: none.
- Scientific claim upgrade/downgrade: none.
- Phase or experiment authorization change: none; this edit clarifies existing
  authorization ownership.
- Goal-distance change: lower risk of stale-stage execution, false global
  prohibitions, and accidental blockage of the authorized limitation/negative
  manuscript route.
- Next scientific priority: unchanged and owned by `NEXT_ACTIONS.md`.
