# Repository Tree

```text
.
|-- AGENTS.md
|-- LIVE_WORKSPACE.md
|-- PROJECT_GOAL.md
|-- CODEX_CONTEXT.md
|-- PROJECT_STATE.md
|-- NEXT_ACTIONS.md
|-- README.md
|-- configs/
|   |-- versioned active-task contracts
|   |-- source/provenance contracts
|   `-- historical and frozen experiment contracts
|-- data/
|   |-- external/
|   |-- literature/
|   |-- processed/
|   `-- raw/
|-- docs/
|   |-- archive/
|   |   |-- handoffs/
|   |   |-- historical_manuscripts/
|   |   |-- legacy_1d_route/
|   |   |-- retired_real_device_bridges/
|   |   `-- superseded_strategy/
|   |-- codex_reports/
|   |-- literature/ and literature_notes/
|   |-- manuscript/
|   |-- paper/
|   |-- project_state/
|   |-- research_strategy/
|   |   |-- active_phase.md
|   |   |-- sci_delivery_pipeline.md
|   |   `-- versioned design references and historical contracts
|   `-- project_prompts/, schemas/, and templates/
|-- outputs/
|   |-- figures/
|   |-- logs/
|   `-- tables/
|-- scripts/
|-- src/pinnpcm/
|   |-- physics/
|   |-- solvers/
|   |-- pinn/
|   |-- experiments/
|   |-- audit/
|   |-- baselines/
|   |-- external_data/
|   |-- utils/
|   `-- visualization/
|-- tests/
|-- EXPERIMENT_REGISTRY.md
|-- DATASET_REGISTRY.md
`-- FIGURE_REGISTRY.md
```

The responsibility-based target does not justify moving working historical code or creating empty future modules. Large generated artifacts remain ignored under `data/processed/` or `outputs/`. `outputs/tables/repository_file_disposition.csv` is the immutable Phase 0 snapshot, not a live inventory; current routing comes from the authority chain, while responsibilities are maintained in `docs/project_state/file_inventory.md`.
