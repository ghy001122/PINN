# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `authorized_contract_scale_corrected_pending_implementation`

Current checkpoint: `A_IMPLEMENTATION_AND_SMOKE_FORMAL_BLOCKED`

## Objective

Build the independent, conservative reference judge required before any new-route dataset or PINN claim: a Qiu-inspired VO2 coplanar single-device real x-y model with source-scale-normalized region-specific passive K-state vertical thermal memory, a device-effective white-box hysteresis closure, differentiable terminal integration, RC coupling, and a complete energy ledger.

This phase implements Phase 1 of the authoritative execution guide. Phase 0 governance passed locally through the repository realignment evidence package. No Phase 1 scientific result is implied by activation.

## Manuscript Use

The reference solver supplies truth fields, port and event observables, conservation ledgers, convergence evidence, and later sparse independent anchors for R1. It also prevents inverse crime by remaining discretely independent from the PINN residual code.

## Authoritative Contracts

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_contract.md`
- `configs/geophase_phase1_2p5d_reference.yaml`
- `configs/qiu_vo2_phase1_source_contract.yaml`
- `configs/geo2p5d_stage.yaml`
- `docs/method_equations.md`
- `NEXT_ACTIONS.md`

## Allowed Work

- source/provenance checks already routed by the config;
- independent FVM and implicit time integration;
- electrical, thermal, K-state, hysteresis, RC, terminal, and ledger implementations;
- two independent device copies only for zero-coupling and label-symmetry behavior tests;
- CPU smoke and focused verification;
- preparation of the locked formal manifest and configuration hash, but not
  execution of the formal campaign without fresh user authorization;
- JSON/CSV, figure/table, report, claim-matrix, and manuscript-sentence updates following evaluated gates.

## Phase-Scoped Restrictions

Do not train a PINN, generate the Phase 2 formal dataset, run inverse recovery, fit literature/device parameters, digitize new curves, repair M44, use GPU/high-cost compute, modify frozen GT, run NbO2, claim full 3D/FEM equivalence, or introduce/claim nonzero dual-device thermal coupling. Nonzero coupling requires a later explicit substrate surface field or a high-order-validated nonlocal kernel. These restrictions protect the Phase 1 gate; they do not permanently prohibit later bounded work after explicit activation.

## Pass Gate

Every required gate must pass:

1. zero-solver algebraic source-scale checks for both electrical endmembers, global thermal conductance, total capacity, and positive scale factors;
2. manufactured electrical and thermal solutions;
3. terminal-current conservation;
4. active-plane plus all K-state energy ledger;
5. independent spatial and temporal refinement on fixed physical comparison grids;
6. passive K-state reduction aligned to a higher-order reference;
7. zero-drive and uniform-conductivity limits;
8. two-copy zero-coupling and label-symmetry limits, without a nonzero coupling claim;
9. literature-trend sanity within the declared source/prior envelope;
10. nonfinite, negative-passivity, ledger-tamper, and coordinate-swap failures close safely.

Conservation without mesh and time convergence is insufficient. Finite output is insufficient. Source-envelope variation below discretization error is non-voting.

## Exit And Stop Rules

- Pass: lock Phase 1 evidence and activate Phase 2 dataset/split design.
- Fail: record `failed_but_informative`; block Phase 2 and all R1-R3 work; choose one bounded foundation repair or reject the reduction.
- Source, coordinate, unit, boundary, or ledger error: stop extensions and repair before any formal rerun.
- The single formal execution and compute budget may not be exceeded without user approval.
- Checkpoint A must stop with `formal_execution_count=0`; Checkpoint B is not
  authorized by phase activation alone.

## Claim Boundary

A pass can support only: a literature-guided synthetic 2.5D reference benchmark passed its preregistered numerical and conservation gates. Qiu calibration or exact reproduction, experimental validation, successful R1/R2, OQ recovery, sensitivity fidelity, full 3D/FEM validation, and cross-material transfer remain `forbidden` without their own direct evidence.

## Round Close

Record actual work, gate results, goal-distance change, claim changes, blockers, the next single priority, and a continue/stop/downgrade disposition.
