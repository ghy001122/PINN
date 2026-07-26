# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `checkpoint_b_readiness_v8_failed_but_informative`

Current checkpoint: `B_READINESS_V8_NO_GO_VERTICAL_REFERENCE`

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

## Completed Checkpoint A Work

- Source-scale preflights, independent FVM/implicit implementation, two
  region-specific passive-memory kernels, external RC coupling, and thermal,
  circuit, combined, and device-power ledgers exist.
- Manufactured/limit/failure-path behavior tests and bounded CPU smoke pass.
- The 96 formal cases exist only as a `planned_not_executed` manifest.
- Formal execution count remains zero; no Phase 1 pass/fail vote exists.

## Current Authorization Boundary

No further scientific execution is authorized. Checkpoint B is not eligible
under the preserved v6 preregistration SHA
`212a4277bf9cf8afe365d922adefe67bdd7595e1` and config SHA-256
`0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1`;
those identities are historical locks, not runnable authorization.
A non-voting Checkpoint A evaluator reported the contact-covered 400/800 nm
frequency metric `0.1231 > 0.05`; this is a pre-formal failure warning and did
not authorize any post-hoc gate change.

The final bounded v8 vertical-semantics repair executed from preregistration
SHA `a32375b74772da8192d390f4233ed0b15e23ae80` and config SHA-256
`e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b`.
Both raw pairs passed all mesh, passivity, identity, and finite checks, but the
separate formal-window-pullback depth-frequency RMSEs remained about
`0.4118 > 0.05` for bare and contact-covered regions. The result is
`NO_GO_VERTICAL_REFERENCE`: no depth/global scale was selected and K-state,
runtime, formal-v8 freezing, and formal execution were blocked. Formal count
remains zero.

There is no authorized compute task. The current K-state route is stopped;
further work requires an explicit user decision activating a new physical
model, a different reduction route, or a manuscript/delivery downgrade.

## Phase-Scoped Restrictions

Do not train a PINN, generate the Phase 2 formal dataset, run inverse recovery, fit literature/device parameters, digitize new curves, repair M44, use GPU/high-cost compute, modify frozen GT, run NbO2, claim full 3D/FEM equivalence, or introduce/claim nonzero dual-device thermal coupling. Nonzero coupling requires a later explicit substrate surface field or a high-order-validated nonlocal kernel. These restrictions protect the Phase 1 gate; they do not permanently prohibit later bounded work after explicit activation.

## Pass Gate

The full gate set remains in the Phase 1 contract/config. It requires source
scale, manufactured solutions, conservation/ledgers, independent mesh/time
convergence, passive K-state reduction, analytic and zero-coupling limits,
trend checks, and fail-closed controls to pass together. Conservation or
finite output alone is insufficient.

## Exit And Stop Rules

- Pass requires every configured gate and a separately authorized formal run.
- Fail is preserved as `failed_but_informative` and blocks Phase 2/R1-R3.
- `formal_execution_count=0`; phase activation alone never authorizes B.

## Claim Boundary

A pass can support only: a literature-guided synthetic 2.5D reference benchmark passed its preregistered numerical and conservation gates. Qiu calibration or exact reproduction, experimental validation, successful R1/R2, OQ recovery, sensitivity fidelity, full 3D/FEM validation, and cross-material transfer remain `forbidden` without their own direct evidence.

## Round Close

Record actual work, gate results, goal-distance change, claim changes, blockers, the next single priority, and a continue/stop/downgrade disposition.
