# Live Workspace Routing

This file prevents reference layers from being mistaken for a writable development checkout without making one workstation path a portable repository requirement.

## Portable live-checkout identity

A checkout is eligible for repository mutation when all of the following hold:

1. it is a Git worktree for `ghy001122/PINN` or an explicitly authorized fork;
2. its current branch, `HEAD`, remote relationship, and worktree changes have been inspected;
3. the applicable `AGENTS.md` chain and current authority documents are available;
4. it is writable and is not a synced chat/project source mirror.

No absolute Windows path is a universal precondition for tests, replay, CI, or contribution from a portable clone.

## Current-machine routing record

| Location | Observed role on 2026-07-26 | Write / execution rule |
| --- | --- | --- |
| `E:\Python demo\PINN` | Current-machine verified checkout for `ghy001122/PINN` | Use for the user's normal local development after the portable identity checks above. |
| `E:\PINN` | Current-machine external reference and archive area | Do not treat its files as Git state or scientific evidence unless a repository provenance record explicitly admits them. |
| Codex or chat project-attached sources | Read-only reference layer | Use for context only; verify every current claim, path, and instruction against a verified Git checkout. |

Large conversation or context archives belong outside the development repository. Their hashes and roles may be recorded in `docs/project_state/local_external_asset_registry.json`, but their presence is not required for clone, test, replay, or manuscript evidence.

If a task starts in a reference mirror, route it to a verified checkout before mutation. If the current-machine path changes, update only this routing record and the local asset registry; do not rewrite scientific evidence or make the new path a global rule.
