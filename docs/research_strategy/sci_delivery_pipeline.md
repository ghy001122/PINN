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

## Pre-Execution Requirement Contract

Before substantive work, record a compact contract with: objective, inputs, outputs, allowed changes, prohibited actions, success gate, failure route, and budget. Map it to the unresolved problem and the exact claim, figure/table, ablation, or reviewer question it may serve. A method/version name alone is insufficient: record its equations, variables, network inputs/outputs, losses, control flow, data source, and intended effect when applicable.

Review only changed requirements. A blocking ambiguity is one that would alter the physical model, claim, data boundary, compute budget, or an irreversible action; stop for it. For a non-blocking ambiguity, use the smallest reversible conservative default and record the assumption in the closeout report. Do not attach adjacent refactors, new research branches, full 3D/phase-field work, or multi-material unification to an otherwise bounded task.

Every evidence record keeps two independent axes:

| Axis | Allowed values | Meaning |
| --- | --- | --- |
| `lifecycle_state` | `planned`, `implemented`, `executed`, `numerically_validated`, `claim_supported` | How far the work actually progressed. |
| `claim_status` | `supported`, `qualified_supported`, `failed_but_informative`, `forbidden` | What the evidence permits the manuscript to say. |

`claim_supported` is not a fifth claim status. Use `validity: invalid` plus `claim_status: forbidden` for a misconfigured, interrupted, prerequisite-blocked, or unevaluated run. Reserve `failed_but_informative` for a valid, completed method that misses its frozen scientific gate.

## One-Round State Machine

```text
question
  -> requirement contract and manuscript use
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

For claim-bearing scale-up, use this order: analytic/limit cases -> short single-device run -> one-seed small sample -> multiple conditions -> multiple seeds -> full formal scale. Bounded debug or mechanism audits may run outside the formal ladder only as explicitly non-voting evidence; they cannot authorize a later stage.

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

Debug and formal runs use separate identities and output locations. Debug artifacts never enter a main table, main figure, or claim matrix. Before a formal run, freeze the hypothesis, config, train/validation/test split, seeds, baselines, metrics, success thresholds, stop conditions, permitted rescue, maximum debug attempts, conservative downgrade route, and Git SHA. Formal results must originate from that frozen contract in a clean environment.

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
- maximum debug attempts, wall time, case/seed budget, and conservative fallback;
- lifecycle state, execution validity, claim status, formal `run_id`, parent run, Git SHA, and environment identity.

Formal baselines must include the independent numerical solver, vanilla PINN, and a pure supervised surrogate; inverse work also includes direct solver/profile methods. Match data, collocation, hyperparameter-search, and approximate wall-clock/GPU budgets, and disclose parameter-count differences. Claim-bearing ablations remove one core module at a time. Unless a frozen contract justifies otherwise, formal main results use at least five preregistered seeds and report median, IQR, 95th percentile, failure rate, and worst case rather than the best seed.

## Failure Routing

| Failure | Required response |
| --- | --- |
| Physics/equation/topology defect | stop extensions and repair the foundation |
| Rank or identifiability failure | reduce the target, add observations, or report the boundary |
| Optimization failure with valid physics | run only the predeclared rescue budget, then stop |
| External provenance failure | keep the claim `forbidden`; do not digitize or substitute silently |
| Gate failure with complete evidence | preserve as `failed_but_informative` |
| Gate pass | lock artifacts and move to manuscript; stop tuning |

Classify an error before repair as a code defect, environment failure, numerical instability, configuration error, or scientific-hypothesis failure. Log the symptom, triggering config/run, root cause, repair commit, regression test, and effect on historical results in the existing task report or experiment registry. A repair must reproduce the old defect in a regression and rerun the smallest affected valid experiment; structural failures are not repaired by adding epochs or repeated unregistered tuning.

Routes explicitly prohibited by the active phase cannot be restarted through this generic failure table. Reopening requires new evidence, changed premises, expected manuscript value, and updated preregistration and phase contract.

## Manuscript Assembly Gates

A claim enters the manuscript only when its code/config, behavioral test, JSON/CSV, figure/table, report, and exact qualifier agree. Main figures must answer distinct reviewer questions. Negative evidence belongs in the supplement when it defends a boundary; it should not be hidden or multiplied into several redundant reports.

The complete submission package must contain a single manuscript, supplement, final figure/table lists, claim matrix, code/data availability text, limitations, reviewer-defense matrix, and exact reproduction commands.

Each main figure serves one claim. Plans and expected contributions cannot appear as completed abstract/conclusion results. Absolute priority language such as “first”, “unique recovery”, “complete solution”, “absolute convergence”, or “replacement of FEM/FVM” requires a systematic novelty search and direct evidence.

Before a formal conclusion is locked, replay the claim-bearing metrics and at least the core table and figure from the frozen commit/config into a new output directory in an isolated clean worktree or clone. Never clean or reset a user's active worktree to satisfy this gate.

## Run Identity And Evidence Package

Every formal run records a unique `run_id`, Git SHA, seed, environment, and parent experiment. Store large outputs under `outputs/` or `data/processed/`; when a run hierarchy is useful, use `outputs/runs/<run_id>/{logs,metrics,figures,checkpoints,manifests,reports}` rather than a competing repository root. Preserve the config snapshot, exact command, relevant non-secret environment variables, logs, raw metrics, figure source data, manifest, failure reason, and final report; never record credentials or tokens. Rebuildable caches and temporary checkpoints may be omitted or cleaned under the declared retention policy.

## Context And File Hygiene

- Keep current context task-relevant, current, role-separated, and non-duplicative. Judge hygiene by semantic ownership, staleness, duplication, and necessity; do not use arbitrary byte, token, line, or file-count pass/fail quotas. Cite and handle a genuine external-system hard limit once rather than repeatedly tuning governance thresholds.
- Do not create another dashboard, current-state file, handoff, goal file, or evidence matrix when an authority already exists.
- Task reports are append-only evidence; current status prose is not repeated inside every report.
- Cumulative root registries are historical indexes. Daily routing uses `current_evidence_index.md`.
- Git history is the archive of replaced prose. Do not copy obsolete plans into new active documents.

## Round Close

Record actual work, tests, frozen-GT integrity, claim changes, distance-to-goal change, blockers, next single priority, and one disposition: `continue`, `stop`, `downgrade`, or `move_to_manuscript`.
