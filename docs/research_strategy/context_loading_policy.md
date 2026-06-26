# Context Loading Policy

This repository uses a low-token context workflow. Codex should load only the
minimum context needed for the active task.

## Tier 0: Every Non-Trivial Task

Read these first:

- `CODEX_CONTEXT.md`
- `docs/research_strategy/active_phase.md`

## Tier 1: Task-Relevant Context

Read only when directly relevant:

- `docs/research_strategy/next_task_*.md`
- the most recent matching file under `docs/codex_reports/`
- necessary lightweight summary JSON or CSV files under `outputs/tables/`

Examples:

- For constrained `gamma_sub` work, read
  `docs/research_strategy/next_task_literature_backed_constrained_gamma_sub.md`.
- For v1/v1.1 comparisons, read the relevant Codex report and summary JSON.

## Tier 2: Phase Changes Or State Updates

Read when updating project state, registries, or handoff documents:

- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `RESEARCH_LOG.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/project_state/*`

## Tier 3: Literature, Parameters, Paper, Or Review Tasks

Read when literature evidence, parameter priors, paper strategy, or reviewer
defense is needed:

- `docs/literature_notes/*`
- `references/project_sources/README.md`
- `references/papers/PAPER_REGISTRY.md`
- Google Drive literature only if the local digest is insufficient or the user
  explicitly asks for a literature check.

Do not default to reading complete papers or all external reference text.

## Tier 4: Code Tasks

Read only the related code when implementation or debugging is required:

- relevant files under `src/`
- relevant scripts under `scripts/`
- relevant configs under `configs/`
- relevant tests under `tests/`

## Rule

Never load all long context by default. Future long-context reads must be
justified by the active task.
