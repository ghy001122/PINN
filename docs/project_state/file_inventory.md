# File Inventory

The exhaustive, machine-readable disposition for every tracked file is `outputs/tables/repository_file_disposition.csv`. This document records responsibilities and current entry points; it is not a second chronology.

## Authority And Governance

| File | Responsibility |
| --- | --- |
| `AGENTS.md` and nested instruction files | Long-lived execution, ethics, engineering, frozen-evidence, and subtree constraints. |
| `PROJECT_GOAL.md` | Stable Q2 delivery ladder and Definition of Done. |
| `CODEX_CONTEXT.md` | Low-token current route, boundary, and one priority. |
| `PROJECT_STATE.md` | Single authoritative current fact snapshot. |
| `docs/research_strategy/active_phase.md` | Earliest unpassed phase and authorization boundary. |
| `NEXT_ACTIONS.md` | Single current execution queue. |
| canonical execution guide | Full R1/R2/R3 research, downgrade, paper, and reviewer-defense plan. |
| Phase 1 technical contract and YAML | Current solver-only implementation/gate contract. |
| `docs/project_state/current_evidence_index.md` | Current/historical/candidate/forbidden evidence router. |
| `docs/archive/README.md` | Historical lifecycle and replacement index. |

## Evidence Chain

- `configs/`: versioned physics, budget, seed, protocol, output, and gate contracts.
- `src/pinnpcm/physics/`: continuous physics, material kernels, geometry, topology, interfaces, SI parameters, and ledgers.
- `src/pinnpcm/solvers/`: reusable numerical solvers, including the future Phase 1 independent implementation when it exists.
- `src/pinnpcm/pinn/`: neural fields, transforms, residuals, losses, and historical PINN components.
- `src/pinnpcm/experiments/`, `audit/`, and `baselines/`: experiment orchestration, audits, and baselines.
- `scripts/`: config-driven CLIs, builders, validation, and audit entrypoints.
- `tests/`: unit, behavior, conservation, frozen-integrity, governance, and claim-gate tests.
- `outputs/tables/`: lightweight committed evidence and governance summaries.
- `data/external/`: provenance-backed external inputs; `data/processed/` includes frozen/read-only and generated assets.
- cumulative registries and `docs/codex_reports/`: exact run/evidence chronology.

## Active Phase 1 Files

- `configs/geo2p5d_stage.yaml`
- `configs/geophase_phase1_2p5d_reference.yaml`
- `docs/research_strategy/phase1_geophase_2p5d_reference_contract.md`
- `docs/method_equations.md`
- `tests/test_geophase_phase1_preregistration.py`

No Phase 1 implementation or output is listed because none exists yet.

## Historical And Frozen Assets

Historical code, tables, reports, and manuscript packages remain in stable replay paths unless safely moved into `docs/archive/`. Frozen Ground Truth v1.1 paths and hashes are controlled by `AGENTS.md` and the governance audit. Logical archiving is used when a move would break manifests, tests, or evidence references.

## Disposition Semantics

Allowed values are `KEEP_CURRENT`, `KEEP_EVERGREEN`, `UPDATE`, `MERGE`, `ARCHIVE`, `DELETE_DUPLICATE`, `DELETE_GENERATED`, `LEAVE_IN_PLACE_FROZEN`, and `REVIEW_BLOCKED`. Phase 0 found no tracked deletion candidate; intentional directory `.gitkeep` files are retained.
