# Exploration-First Claim-Gated Integration Report

## Scope

This documentation-only update integrates the user's clarification that the project must both explore aggressively and interpret cautiously.

The change extends the previous Critical Research Mode integration. It does not replace the skeptical SCI-review posture; it clarifies that skepticism must not become premature research refusal.

## Updated Files

- `AGENTS.md`
- `README.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `docs/project_prompts/critical_research_mode.md`
- `docs/templates/codex_critical_preamble.md`

## New File

- `docs/codex_reports/exploration_first_claim_gated_integration_report.md`

## Core Rule Added

Exploration-first, claim-gated:

- `forbidden` blocks unsupported manuscript claims, not bounded exploratory experiments.
- High-risk directions remain valid exploration targets when they may improve paper quality, workload, novelty, reviewer defense, applicability, or generalization.
- Risky directions should be converted into bounded audits, stress ladders, rescue attempts, ablations, or negative-result tests.
- Final manuscript wording remains conservative and evidence-bound.

## High-Risk Directions Clarified

The following remain not claimable without direct evidence, but are not banned as research directions:

- full or dense 2D hidden-field recovery;
- terminal-only 2D inverse rescue;
- full STL-PINN reproduction;
- Seiler-style multi-head STL;
- actual PINN stiffness training;
- Fourier/F-SPS conditional superiority;
- observability-augmented inverse diagnosis.

## Validation

No experiment code, configs, frozen Ground Truth data, generated outputs, or manuscript result tables were modified. Pytest was not run because this is a documentation/governance update only.

## Frozen GT Status

Frozen Ground Truth v1.1 remains unchanged.

## Claim Impact

This update changes project governance, not experimental conclusions. It makes the intended workflow explicit:

- explore aggressively;
- audit reproducibly;
- interpret conservatively;
- write only claims supported by repository evidence.
