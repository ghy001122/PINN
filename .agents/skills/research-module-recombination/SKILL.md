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

Score each shortlisted combination from 1 to 10 on manuscript distinctiveness, usable-evidence probability, implementation readiness, asset reuse, reviewer-defense value, negative-result salvage value, modular reuse, time cost, compute cost, and integration risk.

Use the score only as a decision aid:

utility = (manuscript value × usable-evidence probability × asset reuse × reviewer defense × salvage value) / max(time cost × compute cost × integration risk, epsilon)

Select one active combination and two fallbacks. Never present the utility score as an objective scientific law.

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

Return these eight sections unless the user asks for a narrower review:

1. Target Paper Claim
2. Source Module Genealogy
3. Adaptation Ledger
4. Candidate Combination Matrix
5. Top-3 Utility Ranking
6. Selected Minimal Evidence Plan
7. Pass/Fail Claim Routing
8. Codex-Ready Execution Prompt

For an idea-only or review request, the execution prompt may be omitted, but source attribution and module relationships remain mandatory.

## Project Authority And Fallback

Read the applicable AGENTS.md chain, CODEX_CONTEXT.md, active_phase.md, and task-relevant evidence before using project facts. The active phase, evidence gates, frozen Ground Truth, data provenance, academic ethics, and user budget override this skill.

If the project files are unavailable, state which authority and evidence are missing, work only at the level of a clearly labeled hypothesis, and do not invent project state, citations, or execution permission.
