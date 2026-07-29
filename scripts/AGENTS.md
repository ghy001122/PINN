# Scripts Subtree Rules

These rules extend the root `AGENTS.md` for `scripts/`.

- Entrypoints must be CLI- and YAML-config-driven. Seeds, budgets, noise, thresholds, and claim gates must not be silently changed in scripts.
- Write lightweight machine-readable summaries with a stable schema; distinguish full runs, actual training, smoke tests, preflights, and documentation-only builders.
- Use `pathlib.Path` and repository-relative paths. Never hard-code the workspace path.
- Preserve frozen inputs and report their integrity for tasks that read GT v1.1.
- Separate debug and formal run identities and output paths. A formal run must record `run_id`, Git SHA, seed, environment, parent experiment, lifecycle state, execution validity, and claim status from its frozen preregistration.
- Preserve the evidence package: config snapshot, exact command, relevant non-secret environment variables, logs, raw metrics, figure source data, manifest, failure reason, and final report; never record credentials or tokens. Use `outputs/runs/<run_id>/...` when a run hierarchy is needed; do not create an ungoverned competing root or scatter artifacts.
- Classify failures before repair and record symptom, triggering config, root cause, repair commit, regression test, and historical-result impact in the existing task report or experiment registry. Reuse an existing implementation after checking semantics, call sites, tests, compatibility, and license.
- Prefer one task and one final commit. Do not create a second report-only commit; report the actual final SHA in the user handoff when self-reference prevents storing it inside the same commit.
- Keep formal commits atomic and report branch, commit SHA, push status, and PR status. Do not create ceremonial branches or rewrite history when the current tree already satisfies the task.
- Use the file-editing mechanism required by the active Codex runtime; use a small workspace-scoped substitute only when the required mechanism is unavailable, and always inspect the diff.
- A script must not upgrade claim status merely because files exist or values are finite.
