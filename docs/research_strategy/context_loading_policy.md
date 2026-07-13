# Context Loading Policy

Load the minimum context required by the task.

## Tier 0: Every Non-Trivial Task

- `CODEX_CONTEXT.md`
- `docs/research_strategy/active_phase.md`

## Tier 1: Governance Or Goal Work

- `AGENTS.md` and applicable nested `AGENTS.md`
- `PROJECT_GOAL.md`
- `docs/research_strategy/goal_status.md`
- `docs/research_strategy/durable_project_memory.md`
- `docs/research_strategy/memory_policy.md`

## Tier 2: Current State Or Handoff

- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- task-relevant registries and latest report
- canonical full handoff only when full history is necessary
- archived files only for provenance or conflict resolution

## Tier 3: Literature, Paper, Or Review

- task-relevant digests and primary sources
- `references/papers/PAPER_REGISTRY.md`
- task-relevant `docs/paper/` or `docs/manuscript/` files
- external search only when local evidence is insufficient or the user requests current verification

## Tier 4: Code And Experiments

Read only relevant configs, source, scripts, tests, and lightweight outputs. Do not load the entire repository or every historical report.

## Authority And Conflict Rule

Current Git/code/outputs and the applicable AGENTS chain override local memory and archived prose. `active_phase.md` authorizes research scope; `PROJECT_STATE.md` records the current snapshot; `NEXT_ACTIONS.md` orders work.

Known filtered dependency warnings and the Windows `apply_patch` issue do not justify loading long history.
