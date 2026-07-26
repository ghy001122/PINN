# Live Workspace Routing

This file prevents reference layers from being mistaken for the live development checkout.

| Location | Role | Write / execution rule |
| --- | --- | --- |
| `E:\Python demo\PINN` | The only live Git development repository for `ghy001122/PINN` on this machine | Run repository edits, tests, commits, and evidence audits here. |
| `E:\PINN` | External local reference and archive area | Do not treat its files as current Git state or scientific evidence unless a repository provenance record explicitly admits them. |
| Codex or chat project-attached sources | Read-only reference layer | Use for context only; verify every current claim, path, and instruction against the live repository. |

Large conversation or context archives belong outside the development repository. Their hashes and roles may be recorded in `docs/project_state/local_external_asset_registry.json`, but their presence is not required for clone, test, replay, or manuscript evidence.

If the current working directory is not the live repository above, stop repository mutation and route the task to the live checkout before continuing.
