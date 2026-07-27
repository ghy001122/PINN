# PINN Phase-Transition Device Research

This repository is a reproducible Python 3.11 research codebase and evidence package for a Q2 SCI delivery objective. The historical Phase 1 Checkpoint A implementation and final v8 screen ended the fixed-bottom material-stack/K-state route at `NO_GO_VERTICAL_REFERENCE`; its 96 items remain permanently `planned_not_executed`. The active Phase 1-v2 contract uses S2, a source-scale-preserving locally distributed single-RC nominal closure, while S1 diffusive memory is non-blocking model-form sensitivity. The fresh 63-item campaign has not run (`formal_execution_count=0`), and no Phase 1-v2 scientific result, positive PINN result, inverse result, or experimental validation exists.

## Workspace preflight

Read [LIVE_WORKSPACE.md](LIVE_WORKSPACE.md) before mutation. It distinguishes a verified Git checkout from machine-local archives and read-only project mirrors; its absolute paths are observations for the current workstation, not portable scientific authority.

## Authoritative entry chain

1. [CODEX_CONTEXT.md](CODEX_CONTEXT.md)
2. [PROJECT_GOAL.md](PROJECT_GOAL.md)
3. [PROJECT_STATE.md](PROJECT_STATE.md)
4. [active_phase.md](docs/research_strategy/active_phase.md)
5. [NEXT_ACTIONS.md](NEXT_ACTIONS.md)
6. [current_evidence_index.md](docs/project_state/current_evidence_index.md)
7. [Q2 SCI execution guide](docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md)
8. [Phase 1-v2 technical contract](docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md)
9. [Qiu Phase 1 source-only contract](configs/qiu_vo2_phase1_source_contract.yaml)

`AGENTS.md` and nested `AGENTS.md` files govern execution, evidence, and claim discipline. Archived strategy and manuscripts are provenance only and cannot authorize current work.

## Degradable research ladder

| Route | Role | Current status |
| --- | --- | --- |
| R1 `HysGeo-Hybrid-PINN` | Minimum manuscript route: 2.5D geometry, white-box hysteresis, source-scale-preserving S2 thermal closure, differentiable port/RC/energy ledgers, and explicit sparse independent-solver anchors | candidate; result claim `forbidden` |
| R2 `GeoPhase-HomoMoE-PINN` | Preferred method route: R1 plus transition-localized spectral experts and dual-axis stiffness homotopy | candidate; result claim `forbidden` |
| R3 conditional observable-subspace/OQ | Solver-first event-aligned local observable-subspace inverse, PINN sensitivity fidelity, and refusal | conditional candidate; result claim `forbidden` |

R1 is the minimum route that must be attempted through its preregistered gates. R2 is pursued only after stable R1 evidence. R3 is optional and cannot block an R1/R2 paper.

## Evidence boundary

All project-generated results are literature-guided synthetic numerical digital-twin evidence unless a provenance record explicitly says otherwise. Frozen Ground Truth v1.1, constrained `gamma_sub`, failed complete-PINN runs, M40/M40R/M44, OASIS, and SID/OQ audits remain retained historical evidence. They do not validate the new 2.5D route. Exact Qiu reproduction, measured-device validation, full FEM/3D equivalence, terminal-only arbitrary hidden-field recovery, universal spectral superiority, and VO2-to-NbO2 zero-shot transfer remain forbidden claims without new direct evidence.

## Repository responsibilities

- `configs/`: versioned phase, physics, budget, seed, and gate contracts.
- `src/pinnpcm/`: reusable physics, solver, PINN, inverse, and evaluation implementations; no empty future modules are created.
- `scripts/`: reproducible command-line runs and audits.
- `tests/`: behavior, conservation, frozen-integrity, governance, and claim-gate tests.
- `outputs/tables/`: lightweight machine-readable evidence and governance summaries.
- `docs/codex_reports/`: task-level evidence reports.
- `docs/archive/`: non-authoritative but recoverable strategy, negative evidence, and manuscript history.

The Phase 1 formal baseline resolves one VO2 device. A two-copy fixture tests only zero-coupling and label symmetry. Nonzero interdevice thermal coupling is not represented and cannot be claimed until a later explicit substrate field or high-order-validated nonlocal kernel is activated.

## Local validation

Use the workspace Python 3.11 environment:

    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
    .\.venv\Scripts\python.exe scripts\validate_tracked_json.py
    git diff --check

Generated large artifacts remain ignored under `data/processed/` or `outputs/`. Do not modify frozen GT outside an explicitly authorized new revision.
