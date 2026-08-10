# Codex Workflow Checklist

The full stage-gate contract is `docs/research_strategy/sci_delivery_pipeline.md`. This file is the short execution checklist.

## Start

1. Confirm `LIVE_WORKSPACE.md`, then read `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md`.
2. Inspect `git status -sb` and preserve unrelated changes.
3. Load only task-relevant context through `context_loading_policy.md`.
4. State whether the task is documentation, smoke/preflight, actual experiment, review, or publication.
5. Use a phase-scoped `codex/` branch for Phase 1 implementation or contract changes; merge through review rather than developing directly on `main`.

## Communication, Coordination, And Stop Discipline

- Lead with the decision and verified facts. Mark interpretations, assumptions or hypotheses, and unresolved unknowns explicitly; keep wording concise and direct.
- Use a compact table, flowchart, timeline, or dependency diagram when it materially reduces the effort needed to understand a complex mapping or sequence. Do not add a visual when short prose is clearer.
- For extended work, report meaningful progress periodically: actual state change, decisive evidence or blocker, and next action. Skip command narration and unchanged-status updates.
- Use sub-agents only when the runtime and user authorization permit them and the subtasks are independent, bounded, and genuinely parallelizable. Assign one integration owner, prevent overlapping edits or duplicate audits, and verify every delegated result before relying on it.
- Begin with an explicit plan. Revise it only after material evidence changes the route, and run validation in proportion to risk. Do not repeat an unchanged audit or check; after a declared pass, fail, or blocker, close the loop and route the result.
- Do not create or adjust byte, token, line, or file-count gates merely to keep documentation compact. Check ownership, relevance, duplication, and staleness; use a numeric limit only when a cited external system or explicit approved contract truly imposes it.
- Do not let defensive governance work displace an eligible high-value bounded research experiment. Explore authorized ideas aggressively, then apply conservative evidence and manuscript gates.

## Bottleneck Selection And Round Contract

- Activate exactly one bottleneck from the ordered queue in `PROJECT_GOAL.md`; do not bundle unrelated research tracks.
- Rank candidates by manuscript value x probability of useful evidence x reviewer-defense value / time-compute-risk.
- Before execution, state the target claim/artifact, budget, success threshold, failure interpretation, and allowed/forbidden wording.
- Use the complete evidence lifecycle: config -> implementation -> test -> JSON/CSV -> figure/table -> report -> claim matrix -> manuscript sentence.
- At closeout update the active phase/state/queue, compact evidence index, task report, and claim matrix only where their responsibilities changed. Cumulative registries do not require mechanical prose duplication.
- Report goal-distance change, claim changes, blockers, next single priority, and disposition: continue / stop / downgrade / manuscript.

## Research Execution

- Every task must serve a claim, equation, figure/table, ablation, generalization result, reviewer defense, limitation, reproducibility item, or submission artifact.
- High-risk exploration requires thresholds, failure interpretation, and allowed/forbidden wording.
- Keep synthetic, external-literature, and experimental evidence separate.
- Do not modify frozen GT v1.1 outside an explicit revision.

## Engineering And Outputs

- Put parameters, seeds, budgets, noise, and gates in YAML.
- Prefer lightweight JSON/CSV evidence under `outputs/tables/`.
- Reports use repository-relative paths and the final-report YAML schema.
- Use the project virtual environment and the file-editing mechanism required by the active Codex runtime. Use a workspace-scoped substitute only when that mechanism is unavailable, then inspect the diff.

## Validation

Documentation/governance changes:

```powershell
.\.venv\Scripts\python.exe scripts\audit_project_governance.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py
```

Code/experiment changes require task-specific tests plus one final full pytest when feasible. Mark current Phase 1 tests with `current` and `phase1`; do not move the historical flat test suite merely for appearance. Before merging claim-bearing Phase 1 work, run the manual `full claim-bearing validation` workflow on the reviewed branch. Always run `git diff --check` and inspect `git status --short` before commit.

## Commit And Report

Prefer one task and one final commit. Stage only intended files. Do not make a second report-only commit. A self-contained commit cannot contain its own final SHA; provide the actual final SHA in the final user report and use the report template field to reference the publication step explicitly.

Never reset hard, clean recursively, force-push, or discard user changes to obtain a clean tree.
