# Codex Workflow Rules

## Context Discipline

- Read `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md` first
  for every non-trivial task.
- Follow `docs/research_strategy/context_loading_policy.md` before loading
  longer context.
- Do not read all historical reports, raw reference packs, or long literature
  notes unless the task justifies it.

## Research Discipline

- Keep the single research line: multiphysics digital twin plus PINN inverse
  identification for memristive or phase-change defect diagnosis.
- Treat current outputs as synthetic numerical digital-twin benchmark data.
- Use `data/external/` and `docs/data_provenance.md` for any future digitized
  literature curves.
- Keep deferred method enhancements out of active code until explicitly
  authorized by `docs/research_strategy/active_phase.md`.

## Engineering Discipline

- Do not modify frozen Ground Truth v1.1 files during PINN or context tasks.
- Do not commit large generated data, images, caches, or virtual environments.
- Prefer lightweight JSON/CSV evidence under `outputs/tables/` for cloud review.
- Keep Markdown and YAML files multi-line and readable.
- Use project-relative paths in reports and user-facing summaries.

## Verification Discipline

For documentation-only changes, run:

```powershell
python -m pytest
git status --short
git diff --name-only
```

For experiment changes, run the task-specific smoke or full reproduction command
requested by the user.

## Windows Execution Rules

- Do not use `apply_patch` in this repository unless the user explicitly asks to
  test it again. The known Windows sandbox helper popup costs time and tokens.
- For file edits, use small workspace-scoped Python/PowerShell scripts and then
  inspect `git diff --name-only`.
- Treat filtered matplotlib/pyparsing deprecation warnings as known external
  dependency noise. Do not mention them in final answers when pytest passes.
- If a warning becomes an error, appears from project source, or blocks a test,
  investigate and report it normally.
