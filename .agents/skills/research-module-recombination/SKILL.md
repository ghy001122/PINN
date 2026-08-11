---
name: research-module-recombination
description: Use for SCI innovation-point design, literature method decomposition, 魔改/排列组合, module recombination, research rerouting, contribution mapping, minimum-ablation planning, and module salvage after negative results. Build attributed source modules, adapted variants, and bounded high-value combinations without requiring every component to be novel or every metric to beat all baselines; preserve academic attribution, evidence gates, active-phase limits, and claim boundaries. Do not use for routine bug fixes, formatting, log reading, or direct execution of an already-frozen experiment.
---

# Research Module Recombination

## Purpose

Turn cited methods and existing project assets into a bounded, attributed research combination with a discriminative evidence plan and manuscript route. Separate module provenance and contribution type from evidence strength.

## When To Trigger

Use this skill for innovation-point design, literature-method decomposition, adaptive module reuse, bounded combination design, research rerouting, contribution analysis, negative-result salvage, or selection of the next research combination.

## When Not To Trigger

Do not use it for routine bug fixes, variable renaming, formatting, log triage, direct execution of a frozen config, or an experiment whose method and gate are already fixed. Do not use it to reopen a route prohibited by the active phase.

## Invocation Modes

Honor an explicit mode first:

- `$research-module-recombination FAST_SCAN`
- `$research-module-recombination FULL_DESIGN`
- `$research-module-recombination CLOSEOUT_SALVAGE`

Use `FAST_SCAN` for innovation screening, next-route selection, or post-failure candidate ranking before any experiment. Decompose at most six core modules, generate at most six combinations, deeply score at most three, choose one active route and two fallbacks, and target 20–30 minutes. Do not execute experiments or generate a full execution prompt by default. Return:

1. Target Paper Claim
2. Compact Source Module Genealogy
3. Candidate Combination Matrix
4. Top-3 Utility Ranking
5. One Active Route And Two Fallbacks
6. Minimum Evidence Contract
7. Pass/Fail Manuscript Routing

Use `FULL_DESIGN` only after an active combination has been selected and a complete method and execution contract is needed. Return the full eight-section output in Required Output. Treat the prompt as a design artifact, not execution authorization; active phase, user authorization, claim gates, data boundaries, Frozen Ground Truth, and budget remain binding.

Use `CLOSEOUT_SALVAGE` after a valid experiment or NO-GO to freeze the result, recover assets, and route stop, paper, fallback, or a possible new MVE. Do not generate a new experiment prompt by default. Return:

1. Frozen Disposition And Contract
2. Failed Module And Failed Interface
3. Retained Scientific And Software Assets
4. Publishable Positive/Negative Evidence
5. Closed And Unanswered Claims
6. Recombination Candidates
7. Manuscript Routing
8. Stop / Paper / New-MVE Decision

When no mode is specified, route innovation screening or next-route selection to `FAST_SCAN`, a selected method needing a full contract to `FULL_DESIGN`, and experiment closeout or NO-GO salvage to `CLOSEOUT_SALVAGE`. Never let implicit invocation default to the longest `FULL_DESIGN` output. Convert a salvage candidate into an execution contract only after an explicit `FULL_DESIGN` request and active-phase authorization.

## Academic Attribution Boundary

- Cite every directly transferred or adapted module at its primary paper, repository, DOI, or authoritative source.
- Record code and data licenses before reuse.
- Never claim a transferred component as original.
- Describe the exact adaptation, interface, workflow, or new system capability that may constitute the contribution.
- Keep synthetic, literature, and experimental evidence distinct.
- Reject plagiarism, hidden sources, fabricated evidence, false priority, license violations, and copied work presented as original.

Read [references/workflow.md](references/workflow.md) for the complete attribution and decision workflow.

## Contribution Taxonomy

Record one or more contribution roles independently of claim status:

- directly_transferred_module
- adapted_module
- interface_contribution
- workflow_contribution
- functional_composition
- validation_contribution
- composability_contribution
- supporting_module

Keep claim_status on its existing evidence axis: supported, qualified_supported, failed_but_informative, or forbidden. A component having prior art does not make a compliant combination forbidden.

## Module-Decomposition Workflow

1. Read the current authority chain and identify the paper bottleneck and target claim.
2. Decompose cited works and retained project assets into at most ten source modules.
3. Record each module's purpose, inputs, outputs, assumptions, evidence, source, license, and adjacent interfaces.
4. Mark each module as a direct transfer, an adaptation candidate, or a supporting module.
5. Load [references/templates.md](references/templates.md) and complete only the cards needed for this task.

## Adaptation Ledger

For every adapted module, record the original behavior, exact modification, physical or algorithmic reason, changed assumptions, changed interface, intended capability, minimum evidence, and forbidden wording.

Permitted adaptation classes include physical-variable, material-mechanism, geometry, boundary/interface, network I/O, loss/constraint, control-flow, protocol/history, solver-coupling, branch-semantics, uncertainty/refusal, composability, deployment-contract, evaluation-protocol, and evidence-contract adaptations. Do not force an unnecessary modification onto every module.

## Combination Enumeration And Pruning

- Generate at most twelve combinations; never enumerate an unbounded power set.
- Permit direct modules alongside adapted variants such as A + C', A' + C, or A' + B' + C + D'.
- Prune combinations that violate physics, authority, data provenance, license, interface compatibility, compute budget, or active-phase gates.
- Remove redundant complexity that adds no capability or discriminative claim.
- Keep at most three combinations for detailed scoring.

## Utility Ranking

Use ordinal scores from 1 to 5. For benefit dimensions, `1` means very weak/very low and `5` means very strong/very high; `2`, `3`, and `4` mean weak, medium, and strong. For raw cost or risk dimensions, `1` means lowest cost/risk and `5` means highest. Do not use decimals or 7–10 pseudo-precision, and explain only non-obvious scores that affect ranking.

Score manuscript distinctiveness, usable-evidence probability, implementation readiness, asset reuse, reviewer-defense value, negative-result salvage value, modular reuse, compute cost, and integration risk. Also record both a raw estimate and a favorable 1–5 score for:

- `time_to_first_figure`: record an actual estimate; score `5` for <=0.5 day, `4` for <=1 day, `3` for <=2 days, `2` for <=4 days, and `1` for >4 days or unknown.
- `time_to_manuscript_claim`: include positive, bounded-domain, interface, or reusable-negative claims that pass the Claim Gate; score `5` for <=1 day, `4` for <=2 days, `3` for <=4 days, `2` for <=7 days, and `1` for >7 days or unknown.
- `new_data_or_solver_runs_required`: record anticipated reference solves, continuations, training runs, stability spectra, and OOD cases; score `5` for no new run, `4` for <=10, `3` for <=50, `2` for <=200, and `1` for >200, unknown scale, or new data infrastructure.

Use the score only as a decision aid:

paper_utility = (manuscript value × usable-evidence probability × asset reuse × reviewer defense × salvage value × time_to_first_figure_score × time_to_manuscript_claim_score × low_new_run_burden_score) / max(compute cost × integration risk, epsilon)

Select one active combination and two fallbacks. Never present the utility score as an objective scientific law, invent time estimates to raise it, or let it override physical feasibility or the active-phase gate.

## Minimum Evidence Design

Design the smallest experiment that discriminates the target contribution. A headline MVE normally compares:

1. the strongest direct baseline;
2. one key interface or module ablation;
3. the complete combination.

Accept evidence dimensions beyond minimum error: new functionality, applicability, branch preservation, set output, refusal, random access, conservation, composability, speed, data efficiency, stability, robustness, or new physical understanding. Reserve full ablation matrices and multi-seed matched-budget claims for an authorized formal stage.

## Negative-Result Module Salvage

After a valid NO-GO, identify:

1. the failed module;
2. the failed interface;
3. retained valid assets;
4. publishable negative evidence;
5. modules eligible for recombination;
6. the new premise, interface, task, or claim that differs from the frozen failure;
7. whether a new bounded MVE has sufficient expected value.

Bind the NO-GO to its named implementation, data contract, physical premise, budget, metrics, and interfaces. Do not turn it into a family-wide prohibition without direct evidence.

Use precise diagnoses such as source_attribution_missing, adaptation_not_documented, combination_increment_not_measured, interface_not_closed, workflow_not_executed, headline_claim_not_supported, baseline_dominates_current_metric, component_is_supporting_not_headline, or evidence_insufficient_for_current_claim.

## Claim And Story Mapping

Map every candidate to a target paper claim, manuscript location, minimum evidence, pass wording, fail wording, fallback story, and forbidden wording. If a metric does not beat the strongest baseline, inspect functional, interface, workflow, applicability, validation, and reusable-negative increments before downgrading the combination.

Use [references/pinn_pcm_worked_example.md](references/pinn_pcm_worked_example.md) only as a historical method demonstration. It never overrides current authority.

## Efficiency Rules

- Activate one combination per round and retain at most two fallbacks.
- Reuse compatible data, operators, tests, and negative evidence.
- Avoid broad literature inventories, exhaustive combination search, decorative complexity, and full ablations during idea screening.
- Stop when the declared gate passes, fails, or reaches a recorded blocker.
- Do not run experiments unless the user and active phase authorize them.

## Required Output

For `FULL_DESIGN`, return these eight sections unless the user asks for a narrower review:

1. Target Paper Claim
2. Source Module Genealogy
3. Adaptation Ledger
4. Candidate Combination Matrix
5. Top-3 Utility Ranking
6. Selected Minimal Evidence Plan
7. Pass/Fail Claim Routing
8. Codex-Ready Execution Prompt

For `FAST_SCAN` and `CLOSEOUT_SALVAGE`, use the mode-specific output above. For an idea-only or review request, an execution prompt remains unauthorized and may be marked omitted, but source attribution and module relationships remain mandatory.

## Project Authority And Fallback

Read the applicable AGENTS.md chain, CODEX_CONTEXT.md, active_phase.md, and task-relevant evidence before using project facts. The active phase, evidence gates, frozen Ground Truth, data provenance, academic ethics, and user budget override this skill.

If the project files are unavailable, state which authority and evidence are missing, work only at the level of a clearly labeled hypothesis, and do not invent project state, citations, or execution permission.
