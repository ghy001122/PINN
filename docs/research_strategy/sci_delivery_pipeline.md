# Engineering SCI Delivery Pipeline

## Purpose

This is the reusable execution contract for `Q2_SCI_DELIVERY_MODE`. It converts a research idea into a claim-bearing manuscript artifact with the lowest practical retry cost. It does not relax the scientific gates in `AGENTS.md`.

## Authority And Context

Read only what the task needs:

1. `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md`;
2. `PROJECT_GOAL.md`, `PROJECT_STATE.md`, and `NEXT_ACTIONS.md` for goal or scheduling work;
3. the applicable `AGENTS.md` chain;
4. `docs/project_state/current_evidence_index.md` and the task-relevant report/config/code;
5. historical handoffs, cumulative registries, and archived prose only to resolve a conflict.

Current state lives in `PROJECT_STATE.md`; authorization lives in `active_phase.md`; the queue lives in `NEXT_ACTIONS.md`. A memory file, old report, or cumulative registry cannot override those files.

## One-Round State Machine

```text
question
  -> manuscript use
  -> evidence type and claim status
  -> predeclared config, budget, gates, and failure interpretation
  -> implementation
  -> behavioral/conservation/leakage tests
  -> machine-readable JSON/CSV
  -> figure/table with caption boundary
  -> report
  -> claim matrix
  -> manuscript sentence or explicit no-claim result
  -> round close and next single bottleneck
```

If a stage is missing, the result stops at the previous evidence class. A smoke test cannot become an experiment, and a finite value cannot become a scientific success.

## Run Classes

| Class | Purpose | Required label | Typical budget |
| --- | --- | --- | --- |
| Documentation | governance, evidence mapping, manuscript assembly | no new scientific evidence | minutes |
| Smoke | import, shape, backward pass, finite output | smoke only | CPU, minutes |
| Preflight/proxy | rank, response surface, local Jacobian, residual stress | bounded proxy | CPU, minutes to hours |
| Full experiment | predeclared scientific gate on all required seeds/cases | direct synthetic evidence | declared before execution |
| External anchor | provenance-backed literature data with isolated holdout | external literature-curve evidence | one source at a time |
| Submission build | deterministic figures, tables, manuscript, supplement | delivery artifact | no claim upgrade |

High-cost work requires a written maximum wall time, seed/case count, and stop condition. No round may silently expand its budget.

## Gate Card

Every non-trivial run must state:

- unresolved question and manuscript location;
- evidence type: synthetic, external literature, or project-generated experiment;
- equations, variables, SI units, topology, boundary/interface conditions;
- train/fit/validation/holdout split and leakage barriers;
- baselines, ablations, seeds, and matched compute;
- metrics and exact thresholds;
- success wording, failure wording, and forbidden wording;
- output paths and reproduction command;
- frozen-GT read/write status.

## Failure Routing

| Failure | Required response |
| --- | --- |
| Physics/equation/topology defect | stop extensions and repair the foundation |
| Rank or identifiability failure | reduce the target, add observations, or report the boundary |
| Optimization failure with valid physics | run only the predeclared rescue budget, then stop |
| External provenance failure | keep the claim `forbidden`; do not digitize or substitute silently |
| Gate failure with complete evidence | preserve as `failed_but_informative` |
| Gate pass | lock artifacts and move to manuscript; stop tuning |

## Manuscript Assembly Gates

A claim enters the manuscript only when its code/config, behavioral test, JSON/CSV, figure/table, report, and exact qualifier agree. Main figures must answer distinct reviewer questions. Negative evidence belongs in the supplement when it defends a boundary; it should not be hidden or multiplied into several redundant reports.

The complete submission package must contain a single manuscript, supplement, final figure/table lists, claim matrix, code/data availability text, limitations, reviewer-defense matrix, and exact reproduction commands.

## Context And File Hygiene

- Keep low-token current context below 24 KiB in total for `CODEX_CONTEXT.md`, `active_phase.md`, `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, and `current_evidence_index.md`.
- Do not create another dashboard, current-state file, handoff, goal file, or evidence matrix when an authority already exists.
- Task reports are append-only evidence; current status prose is not repeated inside every report.
- Cumulative root registries are historical indexes. Daily routing uses `current_evidence_index.md`.
- Git history is the archive of replaced prose. Do not copy obsolete plans into new active documents.

## Round Close

Record actual work, tests, frozen-GT integrity, claim changes, distance-to-goal change, blockers, next single priority, and one disposition: `continue`, `stop`, `downgrade`, or `move_to_manuscript`.
