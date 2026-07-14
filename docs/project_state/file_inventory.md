# File Inventory

## Authority And Governance

| File | Responsibility |
|---|---|
| `AGENTS.md` | Global behavior, ethics, engineering, frozen GT, claim rules. |
| nested `AGENTS.md` | Subtree-specific additions only. |
| `PROJECT_GOAL.md` | Stable Q2 delivery goal and Definition of Done. |
| `CODEX_CONTEXT.md` | Low-token current scientific context. |
| `PROJECT_STATE.md` | Single authoritative current snapshot. |
| `NEXT_ACTIONS.md` | Single active execution queue. |
| `docs/research_strategy/active_phase.md` | Authorized phase and P0-P4 gates. |
| `docs/research_strategy/sci_delivery_pipeline.md` | Reusable stage-gate execution workflow. |
| `docs/project_state/current_evidence_index.md` | Compact evidence routing. |
| `docs/research_strategy/innovation_portfolio.md` | Ranked claim-gated future research. |
| `docs/research_strategy/durable_project_memory.md` | Stable facts and pitfalls, no transient state. |
| `docs/research_strategy/memory_policy.md` | Memory authority and privacy. |
| `docs/research_strategy/legacy_document_index.md` | Retired document replacements. |

## Evidence Chain

- `configs/`: versioned physics, budgets, seeds, protocols, gates.
- `src/pinnpcm/physics/`: GT, constitutive laws, multilayer/topology and terminal solvers.
- `src/pinnpcm/pinn/`: neural fields, transforms, residuals, losses, OASIS/F-SPS components.
- `scripts/`: CLI, train, audit, build, ingest, and fit entrypoints.
- `tests/`: unit, behavior, conservation, frozen-integrity, and claim-gate checks.
- `outputs/tables/`: lightweight committed evidence.
- `docs/codex_reports/`: task-level evidence reports.
- `EXPERIMENT_REGISTRY.md`, `DATASET_REGISTRY.md`, `FIGURE_REGISTRY.md`: evidence routing.

## Current V10 Core Files

- `src/pinnpcm/physics/multilayer_sandwich.py`
- `src/pinnpcm/physics/multiterminal_yz.py`
- `src/pinnpcm/pinn/oasis_components.py`
- `src/pinnpcm/pinn/physics_residuals.py`
- `scripts/audit_physical_semantics_v10.py`
- `scripts/train_cv_multidomain_oasis_v10.py`
- `scripts/audit_active_protocol_design_v3.py`
- `scripts/audit_multiterminal_yz_forward_v10.py`
- `scripts/audit_oasis_generalization_v10.py`
- `outputs/tables/cv_multidomain_oasis_training_summary.json`
- `outputs/tables/sequential_terminal_inverse_v3_summary.json`
- `outputs/tables/multiterminal_yz_forward_summary.json`

## Frozen Files

The frozen v1.1 configs, report, manifest, and arrays listed in root `AGENTS.md` are read-only outside an explicit GT revision.

Historical inventories are available through Git history, cumulative registries, and retired documents. This inventory is a current routing document, not an exhaustive chronology.
