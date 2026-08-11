# Context Loading Policy

Load the minimum context required by the task.

## Tier 0: Every Non-Trivial Task

- `CODEX_CONTEXT.md`
- `docs/research_strategy/active_phase.md`

## Tier 1: Governance Or Goal Work

- `AGENTS.md` and applicable nested `AGENTS.md`
- `PROJECT_GOAL.md`
- `PROJECT_STATE.md`
- `docs/research_strategy/sci_delivery_pipeline.md`
- `docs/research_strategy/durable_project_memory.md`
- `docs/research_strategy/memory_policy.md`

## Tier 2: Current State Or Handoff

- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `docs/project_state/current_evidence_index.md`
- task-relevant report and evidence artifacts
- cumulative registries, legacy handoffs, and archived files only for provenance or conflict resolution

## Tier 3: Literature, Paper, Or Review

- task-relevant digests and primary sources
- `references/papers/PAPER_REGISTRY.md`
- `docs/literature/primary_source_decision_log_2026-07-14.md`
- task-relevant `docs/paper/` or `docs/manuscript/` files
- external search only when local evidence is insufficient or the user requests current verification

## Module-Recombination Routing

Invoke `$research-module-recombination` for innovation-point design, literature-method decomposition, 魔改/排列组合, method rerouting, contribution analysis, negative-result module salvage, or selection of the next research combination. Load only the task-relevant source papers, module cards, negative results, and claim surfaces after reading current authority.

Do not invoke it for routine bug fixes, variable renaming, formatting, log triage, or direct execution of an already-frozen config.

## Tier 4: Code And Experiments

Read only relevant configs, source, scripts, tests, and lightweight outputs. Do not load the entire repository or every historical report.

## Authority And Conflict Rule

Current Git/code/outputs and the applicable AGENTS chain override local memory and legacy prose. `active_phase.md` authorizes research scope; `PROJECT_STATE.md` records the current snapshot; `NEXT_ACTIONS.md` orders work. Retired surfaces are listed in `legacy_document_index.md`.

External chat-project source documents, generated AI reports, and Skill worked examples are advisory leads only. They neither establish current repository facts nor authorize execution; verify repository facts against the live checkout and evidence, and trace literature claims to primary sources.

Inspect remote state only when a push, pull request, CI/release fact, or other remote-dependent decision is in scope. Do not turn routine local work into a repeated cloud-status audit.

Known filtered dependency warnings and runtime-specific file-editing mechanics do not justify loading long history.
