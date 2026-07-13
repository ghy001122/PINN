# Memory Policy

Codex local memory is a non-authoritative recall aid. It must not replace versioned evidence or current repository state.

Authority order:

1. applicable repository `AGENTS.md` files;
2. current Git state, code, outputs, and tests;
3. `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md`;
4. `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, registries, and reports;
5. canonical handoff and archived history;
6. local memory.

When memory conflicts with Git, outputs, or the active phase, verify current evidence and ignore the stale memory. Do not copy transient HEADs, metrics, or next actions into durable memory.

Secrets, credentials, tokens, private identifiers, and personal local paths must not be written into memory. The `/memories` interface may be used only when the user permits reading or contributing local memory; it cannot replace the versioned evidence chain.

This repository intentionally does not create a `memorys/` directory. Stable project facts belong in `durable_project_memory.md`; changing status belongs in the authoritative state files.
