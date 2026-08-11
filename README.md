# PINN Phase-Transition Device Research

This repository is a reproducible Python 3.11 research codebase and evidence package for a Q2 SCI delivery objective. Historical routes, valid negative results, and retained numerical assets remain versioned evidence, but this README does not repeat a transient phase, checkpoint, branch, or execution count. Read the live authority chain below before interpreting status or starting work; no overview text authorizes an experiment or upgrades a scientific claim.

## Workspace preflight

Read [LIVE_WORKSPACE.md](LIVE_WORKSPACE.md) before mutation. It distinguishes a verified Git checkout from machine-local archives and read-only project mirrors; its absolute paths are observations for the current workstation, not portable scientific authority.

## Authoritative entry chain

1. [AGENTS.md](AGENTS.md) and the applicable nested `AGENTS.md`
2. [CODEX_CONTEXT.md](CODEX_CONTEXT.md)
3. [active_phase.md](docs/research_strategy/active_phase.md)
4. [PROJECT_GOAL.md](PROJECT_GOAL.md) for the stable delivery contract
5. [PROJECT_STATE.md](PROJECT_STATE.md)
6. [NEXT_ACTIONS.md](NEXT_ACTIONS.md)
7. [current_evidence_index.md](docs/project_state/current_evidence_index.md)
8. [SCI delivery pipeline](docs/research_strategy/sci_delivery_pipeline.md) and only the task-relevant contract/config named by the active authority; the [Q2 SCI execution guide](docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md) is a versioned long-term design reference, not a source of current action

`AGENTS.md` and nested `AGENTS.md` files govern execution, evidence, and claim discipline. Archived strategy and manuscripts are provenance only and cannot authorize current work.

## Degradable research ladder

| Route | Role | Authority boundary |
| --- | --- | --- |
| R1 `HysGeo-Hybrid-PINN` | Minimum manuscript route: 2.5D geometry, white-box hysteresis, source-scale-preserving thermal closure, differentiable port/energy ledgers, and explicit sparse independent-solver anchors | Long-term delivery lane; current eligibility comes only from `active_phase.md` |
| R2 `GeoPhase-HomoMoE-PINN` | Preferred method route: R1 plus transition-localized spectral experts and dual-axis stiffness homotopy | Long-term conditional lane; this table is not execution authorization |
| R3 conditional observable-subspace/OQ | Solver-first event-aligned local observable-subspace inverse, PINN sensitivity fidelity, and refusal | Long-term conditional lane; this table is not execution authorization |

The ladder is a degradable delivery contract, not the current execution queue. A stopped or completed active contract is not reopened by this overview; any new route must satisfy the current authorization, evidence, baseline, budget, and stop gates.

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
