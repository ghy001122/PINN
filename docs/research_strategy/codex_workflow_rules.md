# Codex Workflow Rules

## Start

1. Read `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md`.
2. Inspect `git status -sb` and preserve unrelated changes.
3. Load only task-relevant context through `context_loading_policy.md`.
4. State whether the task is documentation, smoke/preflight, actual experiment, review, or publication.

## Bottleneck Selection And Round Contract

- Activate exactly one bottleneck from the ordered queue in `PROJECT_GOAL.md`; do not bundle unrelated research tracks.
- Rank candidates by manuscript value x probability of useful evidence x reviewer-defense value / time-compute-risk.
- Before execution, state the target claim/artifact, budget, success threshold, failure interpretation, and allowed/forbidden wording.
- Use the complete evidence lifecycle: config -> implementation -> test -> JSON/CSV -> figure/table -> report -> claim matrix -> manuscript sentence.
- At closeout update the authoritative goal/phase/state/queue plus registries, latest changes, research log, and claim matrix without mechanically duplicating prose.
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
- Use the project virtual environment. On Windows, use workspace-scoped scripted edits rather than `apply_patch`.

## Validation

Documentation/governance changes:

```powershell
.\.venv\Scripts\python.exe scripts\audit_project_governance.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py
```

Code/experiment changes require task-specific tests plus full pytest when feasible. Always run `git diff --check` and inspect `git status --short` before commit.

## Commit And Report

Prefer one task and one final commit. Stage only intended files. Do not make a second report-only commit. A self-contained commit cannot contain its own final SHA; provide the actual final SHA in the final user report and use the report template field to reference the publication step explicitly.

Never reset hard, clean recursively, force-push, or discard user changes to obtain a clean tree.
