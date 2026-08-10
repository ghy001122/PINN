# Research Module Recombination Workflow

## Contents

1. Operating principles
2. Authority and paper bottleneck
3. Source-module decomposition
4. Adaptation design
5. Bounded combination pool
6. Pruning and utility ranking
7. Minimum evidence
8. Claim and story routing
9. Negative-result salvage
10. Closeout

## 1. Operating Principles

- Treat cited architectures, PINNs, POD, FVM, MoE, continuation, refusal, and other known components as legitimate source modules when properly attributed.
- Permit directly transferred modules; do not manufacture changes merely to create an appearance of novelty.
- Locate a potential contribution in adaptation, interfaces, workflow, functional composition, validation, composability, or a new evidence-backed capability.
- Keep component provenance and contribution type independent from claim_status.
- Do not require every metric to beat every baseline. Test the metric or function that discriminates the intended contribution.
- Do not enumerate an unbounded power set or add complexity without a task-driven purpose.
- Bind a negative result to its frozen contract rather than treating it as a universal family ban.
- Preserve academic attribution, license, provenance, evidence, and active-phase boundaries.

## 2. Authority And Paper Bottleneck

Before designing a combination:

1. Read the applicable AGENTS.md chain.
2. Read CODEX_CONTEXT.md and docs/research_strategy/active_phase.md.
3. Read PROJECT_GOAL.md for goal or manuscript-route work.
4. Load only task-relevant reports, claim rows, literature, code, and artifacts.
5. State the unresolved bottleneck and its manuscript destination.
6. Separate verified facts, evidence-based interpretations, assumptions, and unknowns.

Do not use this workflow to activate a prohibited experiment. A useful combination remains a hypothesis until an authorized gate is opened.

## 3. Source-Module Decomposition

Decompose no more than ten core modules. Give each module a stable ID such as A, B, or C.

Record:

- source paper, repository, DOI, or authoritative documentation;
- original purpose;
- original inputs and outputs;
- physical or algorithmic assumptions;
- original evidence and evaluation scope;
- code or data license when reuse is involved;
- direct transfer, adaptation candidate, or supporting role;
- adjacent interfaces;
- intended system capability;
- manuscript location;
- minimum evidence;
- forbidden wording.

Prefer primary sources. A review can identify a lead but cannot replace the original source for a claim about equations, originality, or measured parameters.

## 4. Adaptation Design

For each selected adaptation candidate:

1. State the original behavior.
2. State the exact proposed change.
3. Identify the physical, numerical, interface, deployment, or evidence reason.
4. Record which assumptions, inputs, outputs, losses, control flow, or interfaces change.
5. Name the new capability expected from the adaptation.
6. Define the minimum discriminative evidence and one-factor ablation.
7. Record allowed and forbidden claim language.

Allowed classes include:

- physical-variable or material-mechanism adaptation;
- geometry, boundary, or interface adaptation;
- network input/output or loss adaptation;
- control-flow, protocol, or history adaptation;
- solver coupling and conservative projection;
- branch semantics;
- uncertainty, refusal, or set output;
- composability and deployment contract;
- evaluation or evidence-contract adaptation.

Leave a module unmodified when direct transfer is the correct and attributable design.

## 5. Bounded Combination Pool

Build combinations such as A' + C, A' + D, A' + C', or A' + B' + C + D'. A prime means a documented adaptation; its absence means attributed direct transfer.

Limits per round:

- at most ten decomposed modules;
- at most twelve candidate combinations;
- at most three deeply scored combinations;
- one active combination;
- two fallbacks.

Do not enumerate all 2^N combinations.

## 6. Pruning And Utility Ranking

Prune a candidate when it:

- violates the physical model or interface contract;
- requires unavailable or provenance-unclear data;
- conflicts with a license;
- exceeds the authorized budget;
- duplicates another candidate without a distinct capability;
- bypasses an active-phase prerequisite or evidence gate;
- adds complexity without a measurable contribution axis.

Score the remaining combinations from 1 to 10 on:

- manuscript distinctiveness;
- usable-evidence probability;
- implementation readiness;
- asset reuse;
- reviewer-defense value;
- negative-result salvage value;
- modular reuse;
- time cost;
- compute cost;
- integration risk.

Suggested ranking aid:

utility = (manuscript value × usable-evidence probability × asset reuse × reviewer defense × salvage value) / max(time cost × compute cost × integration risk, epsilon)

Document the reasons behind scores. Do not present the ranking as a scientific measurement.

## 7. Minimum Evidence

For an MVE, prefer three matched views:

1. strongest direct baseline;
2. one critical interface or module ablation;
3. complete combination.

Choose metrics that discriminate the intended increment:

- performance: accuracy, speed, stability, robustness, or data efficiency;
- function: branch preservation, random access, set output, refusal, or protocol semantics;
- physics: conservation, closure, interface continuity, or admissible domain;
- composition: replaceability, reuse, interoperability, or deployment contract;
- knowledge: a reproducible failure boundary or new physical insight.

Do not require a full ablation matrix during an idea screen. Expand to complete matched-budget and multi-seed evidence only after the relevant formal stage is authorized.

## 8. Claim And Story Routing

For each candidate, map:

- target claim;
- contribution type;
- manuscript section, figure, table, ablation, or reviewer question;
- pass threshold and allowed wording;
- fail threshold and negative wording;
- retained supporting role;
- forbidden wording.

Keep these axes separate:

- contribution provenance and role;
- lifecycle_state;
- execution validity;
- claim_status.

A known component can participate in a qualified_supported combination claim. A new-looking combination can remain forbidden when its evidence is absent.

When a baseline dominates one metric, check whether a different preregistered contribution axis is supported. Do not move thresholds after seeing results. If there is no performance, functional, interface, workflow, applicability, validation, composability, or reusable-negative increment, record combination_increment_evidence_insufficient.

## 9. Negative-Result Salvage

For every valid bounded NO-GO:

1. Identify the failed module and failed interface.
2. Preserve the exact implementation, data, physics, budget, metrics, and thresholds.
3. Inventory retained operators, datasets, interfaces, tests, evaluation methods, and negative evidence.
4. State which claims are closed and which remain unanswered.
5. Propose only combinations whose premise, interface, task, or claim materially differs.
6. Compare expected manuscript value with execution cost and risk.
7. Open a new bounded MVE only when current authority permits it.

Use precise diagnoses:

- source_attribution_missing;
- adaptation_not_documented;
- combination_increment_not_measured;
- interface_not_closed;
- workflow_not_executed;
- headline_claim_not_supported;
- baseline_dominates_current_metric;
- component_is_supporting_not_headline;
- evidence_insufficient_for_current_claim.

Reserve misconduct language for plagiarism, hidden sources, fabricated evidence, false priority, copied work presented as original, or license violations.

## 10. Closeout

Output:

1. Target Paper Claim
2. Source Module Genealogy
3. Adaptation Ledger
4. Candidate Combination Matrix
5. Top-3 Utility Ranking
6. Selected Minimal Evidence Plan
7. Pass/Fail Claim Routing
8. Codex-Ready Execution Prompt

End with one active combination, two fallbacks, a bounded evidence contract, and an explicit stop or downgrade route. If execution was not authorized, stop at the plan and label all expected outcomes as hypotheses.
