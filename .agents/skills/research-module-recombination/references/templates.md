# Compact Research-Recombination Templates

## Contents

1. Source Module Card
2. Adaptation Ledger
3. Combination Matrix
4. Utility Scorecard
5. Minimum Evidence Card
6. Manuscript Contribution Map
7. Negative-Result Salvage Card
8. Codex Research Task Contract

Use only the fields needed for the current decision. Keep evidence and hypotheses separate.

## Invocation Mode Selector

- Requested/selected mode: FAST_SCAN | FULL_DESIGN | CLOSEOUT_SALVAGE
- Routing reason:
- Mode budget/limits:
- Execution authorized: yes | no

Use `FAST_SCAN` for bounded screening, `FULL_DESIGN` for an already selected method contract, and `CLOSEOUT_SALVAGE` for a completed result or NO-GO. Implicit invocation must not default to `FULL_DESIGN`.

## A. Source Module Card

- Module ID:
- Source paper/repository/DOI:
- Original purpose:
- Original inputs and outputs:
- Assumptions:
- Original evidence:
- Code/data license:
- Role: directly_transferred_module | adapted_module | supporting_module
- Exact modification (if adapted):
- Adjacent interfaces:
- Intended system capability:
- Manuscript location:
- Minimum evidence:
- Forbidden wording:

## B. Adaptation Ledger

| Module | Original behavior | Exact adaptation | Reason | Changed interface/assumption | Intended capability | Required ablation | Allowed claim | Forbidden claim |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A → A' |  |  |  |  |  |  |  |  |

## C. Combination Matrix

| Candidate | Modules | Direct/adapted roles | New capability | Key interface | Main incompatibility | Evidence status | Route |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 |  |  |  |  |  |  | active/fallback/pruned |

Limits: twelve candidates, three deeply scored, one active, two fallbacks.

## D. Utility Scorecard

Use ordinal 1–5 scores and explain only non-obvious values that change ranking. Benefit scores use `1 = very weak/very low`, `2 = weak`, `3 = medium`, `4 = strong`, and `5 = very strong/very high`. Raw cost/risk scores use `1 = lowest` and `5 = highest`.

| Candidate | Manuscript value | Usable-evidence probability | Readiness | Asset reuse | Reviewer defense | Salvage | Modular reuse | Compute cost (1 low, 5 high) | Integration risk (1 low, 5 high) | Utility/rank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
|  |  |  |  |  |  |  |  |  |  |  |

Record raw estimates and favorable ranking scores separately:

| Candidate | Time to first figure (raw) | Score | Time to manuscript claim (raw) | Score | New data/solver runs required (raw counts by type) | Low-run-burden score |
| --- | --- | ---: | --- | ---: | --- | ---: |
|  |  |  |  |  |  |  |

- `time_to_first_figure`: score `5` for <=0.5 day, `4` for <=1 day, `3` for <=2 days, `2` for <=4 days, and `1` for >4 days or unknown.
- `time_to_manuscript_claim`: score `5` for <=1 day, `4` for <=2 days, `3` for <=4 days, `2` for <=7 days, and `1` for >7 days or unknown.
- `new_data_or_solver_runs_required`: list reference solves, continuations, training runs, stability spectra, and OOD cases; score `5` for none, `4` for <=10, `3` for <=50, `2` for <=200, and `1` for >200, unknown scale, or new data infrastructure.

Ranking aid:

`paper_utility = (manuscript value × usable-evidence probability × asset reuse × reviewer defense × salvage value × time_to_first_figure_score × time_to_manuscript_claim_score × low_new_run_burden_score) / max(compute cost × integration risk, epsilon)`

Treat utility as a ranking aid, not a scientific result. Do not use decimal pseudo-precision, invent estimates, or override physical and active-phase gates.

## E. Minimum Evidence Card

- Candidate and target claim:
- Evidence type:
- Strongest direct baseline:
- Critical interface/module ablation:
- Complete combination:
- Matched resources:
- Primary discriminative metric/function:
- Secondary safety metrics:
- Success threshold and wording:
- Failure threshold and wording:
- Budget and stop condition:
- Output table/figure/report:
- Frozen data/GT status:

## F. Manuscript Contribution Map

| Contribution | Type | Source modules | Evidence artifact | Manuscript location | Claim status | Allowed sentence | Forbidden sentence |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | interface/workflow/function/validation/composability |  |  |  |  |  |  |

## G. Negative-Result Salvage Card

- Frozen implementation and disposition:
- Failed module:
- Failed interface:
- Bound data/physics/budget/metrics:
- Retained operators/data/interfaces/tests:
- Publishable negative evidence:
- Closed claims:
- Unanswered claims:
- Recombination candidates:
- Material difference from the failed contract:
- Bounded MVE value and cost:
- Route: stop | manuscript | supporting asset | new authorized MVE

## H. Codex Research Task Contract

- Task ID and method identity:
- Invocation mode: FAST_SCAN | FULL_DESIGN | CLOSEOUT_SALVAGE
- Unresolved problem and manuscript destination:
- Current authority and prerequisite:
- Source modules and attribution:
- Direct modules:
- Adapted modules and exact modifications:
- Inputs/data provenance:
- Governing equations/interfaces:
- Named-method network inputs and outputs (if applicable):
- Loss groups and fixed weights (if applicable):
- Training or execution control flow:
- Intended physical or methodological effect:
- Outputs:
- Allowed modifications:
- Prohibited actions:
- Baselines and ablation:
- Metrics and fixed gates:
- Budget:
- Time to first figure estimate and score:
- Time to manuscript claim estimate and score:
- New reference/continuation/training/stability/OOD runs and low-burden score:
- Evidence chain: config → implementation → test → JSON/CSV → figure/table → report → claim matrix → manuscript sentence:
- Pass claim:
- Fail/negative claim:
- Forbidden wording:
- Active combination:
- Fallback 1:
- Fallback 2:
- Stop condition:
