# Scripts Subtree Rules

These rules extend the root `AGENTS.md` for `scripts/`.

- Entrypoints must be CLI- and YAML-config-driven. Seeds, budgets, noise, thresholds, and claim gates must not be silently changed in scripts.
- Write lightweight machine-readable summaries with a stable schema; distinguish full runs, actual training, smoke tests, preflights, and documentation-only builders.
- Use `pathlib.Path` and repository-relative paths. Never hard-code the workspace path.
- Preserve frozen inputs and report their integrity for tasks that read GT v1.1.
- Prefer one task and one final commit. Do not create a second report-only commit; report the actual final SHA in the user handoff when self-reference prevents storing it inside the same commit.
- Use the file-editing mechanism required by the active Codex runtime; use a small workspace-scoped substitute only when the required mechanism is unavailable, and always inspect the diff.
- A script must not upgrade claim status merely because files exist or values are finite.
