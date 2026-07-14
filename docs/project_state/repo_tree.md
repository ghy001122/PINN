# Repository Tree

```text
.
|-- AGENTS.md
|-- PROJECT_GOAL.md
|-- CODEX_CONTEXT.md
|-- PROJECT_STATE.md
|-- NEXT_ACTIONS.md
|-- README.md
|-- .codex/
|   |-- README.md
|   `-- rules/project_safety.rules
|-- configs/
|-- data/
|   |-- external/
|   `-- processed/gt_v1_acceptance/   # frozen synthetic GT v1.1
|-- docs/
|   |-- AGENTS.md
|   |-- archive/
|   |-- codex_reports/
|   |-- manuscript/
|   |-- paper/
|   |-- project_state/
|   |-- research_strategy/
|   `-- templates/
|-- outputs/
|   |-- figures/
|   `-- tables/
|-- scripts/
|   `-- AGENTS.md
|-- src/pinnpcm/
|   |-- physics/AGENTS.md
|   `-- pinn/AGENTS.md
`-- tests/
    `-- AGENTS.md
```

Large generated artifacts remain under `data/processed/` or `outputs/`. The governance entrypoint is `AGENTS.md`; the low-token research entrypoint is `CODEX_CONTEXT.md`; compact evidence routing is `docs/project_state/current_evidence_index.md`.
