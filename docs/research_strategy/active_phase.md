# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `phase1v2_s2_preregistered_pending_implementation`

Current checkpoint: `PHASE1_V2_S2_PREREGISTERED_PENDING_IMPLEMENTATION`

## Objective

Build the independent, conservative reference judge required before any new-route dataset or PINN claim: a Qiu-inspired VO2 coplanar single-device real x-y model with the source-scale-preserving locally distributed S2 nominal thermal closure, explicit VO2 and mask-local Ti/Au in-plane thermal terms, a device-effective white-box hysteresis closure, differentiable terminal integration, RC coupling, and a complete energy ledger.

This phase implements Phase 1 of the authoritative execution guide. Phase 0 governance passed locally through the repository realignment evidence package. No Phase 1 scientific result is implied by activation.

## Manuscript Use

The reference solver supplies truth fields, port and event observables, conservation ledgers, convergence evidence, and later sparse independent anchors for R1. It also prevents inverse crime by remaining discretely independent from the PINN residual code.

## Authoritative Contracts

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`
- `configs/geophase_phase1_v2_s2_reference.yaml`
- `configs/geophase_phase1_v2_formal_manifest.yaml`
- `configs/qiu_same_device_thermal_holdout_audit.yaml`
- `configs/geophase_phase1_s1_diffusive_sensitivity_mve.yaml`
- `configs/qiu_vo2_phase1_source_contract.yaml`
- `configs/geo2p5d_stage.yaml`
- `docs/method_equations.md`
- `NEXT_ACTIONS.md`

## Retained v6-v8 Work

- Source-scale preflights, independent FVM/implicit implementation, two
  region-specific passive-memory kernels, external RC coupling, and thermal,
  circuit, combined, and device-power ledgers exist.
- Manufactured/limit/failure-path behavior tests and bounded CPU smoke pass.
- The 96 formal cases exist only as a `planned_not_executed` manifest.
- Formal execution count remains zero; no Phase 1 pass/fail vote exists.

The v6-v8 fixed-bottom material-stack/K-state route is terminal
`failed_but_informative`. Its configs, 96-item `planned_not_executed` manifest,
tests, outputs, and hashes remain immutable and do not govern Phase 1-v2.

## Current Authorization Boundary

The user explicitly authorized a fresh Phase 1-v2 physical contract. S2 is
nominal and may proceed to implementation and non-voting smoke only after the
Phase 1-v2 preregistration commit is pushed. A bounded same-device source audit
(at most 4 h) and one S1 analytic MVE (at most 24 h active/48 h elapsed) may
then proceed without blocking S2. The source audit may not digitize or fit a
curve; S1 cannot become production during this MVE.

The preserved v6 preregistration SHA
`212a4277bf9cf8afe365d922adefe67bdd7595e1` and config SHA-256
`0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1`
remain historical locks, not runnable authorization. A non-voting Checkpoint A
evaluator reported the contact-covered 400/800 nm frequency metric
`0.1231 > 0.05`; that warning remains unchanged.

The final bounded v8 vertical-semantics repair executed from preregistration
SHA `a32375b74772da8192d390f4233ed0b15e23ae80` and config SHA-256
`e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b`.
Both raw pairs passed all mesh, passivity, identity, and finite checks, but the
separate formal-window-pullback depth-frequency RMSEs remained about
`0.4118 > 0.05` for bare and contact-covered regions. The result is
`NO_GO_VERTICAL_REFERENCE`: no depth/global scale was selected and K-state,
runtime, formal-v8 freezing, and formal execution were blocked. Formal count
remains zero.

No formal Phase 1-v2 campaign is authorized. Its formal execution count is
zero. Implementation, focused tests, and bounded non-voting smoke cannot
generate a positive Phase 1 result. If a correct S2 implementation fails its
physics, conservation, or convergence smoke, the positive 2D route stops and
the manuscript downgrades to the retained `gamma_sub`/identifiability route.

## Phase-Scoped Restrictions

Do not run a formal campaign, train a PINN, generate the Phase 2 formal dataset, run inverse recovery, fit literature/device parameters, digitize curves in the bounded audit, repair M44, use GPU/high-cost compute, modify frozen GT, run NbO2, claim full 3D/FEM equivalence, or introduce/claim nonzero dual-device thermal coupling. Do not resume the fixed-bottom depth ladder or material-stack-derived K-state route. Nonzero coupling requires a later explicit substrate surface field or independently validated nonlocal kernel.

## Pass Gate

The full Phase 1-v2 gate set is in its new contract/config. It requires nominal
S2 source-scale and positivity identities, forced manufactured responses,
conservation/ledgers, independent mesh/time convergence, mask and overlap
audits, analytic and zero-coupling limits, trend checks, and fail-closed
controls to pass together. Conservation or finite output alone is
insufficient. S1 is outside the nominal formal inventory.

## Exit And Stop Rules

- Pass requires every Phase 1-v2 configured gate and a separately authorized formal run.
- Fail is preserved as `failed_but_informative` and blocks Phase 2/R1-R3.
- `formal_execution_count=0`; preregistration or implementation never authorizes the formal campaign.

## Claim Boundary

A future pass can support only: a literature-guided synthetic 2.5D reference benchmark with a source-moment-anchored local S2 closure passed its preregistered numerical and conservation gates. Qiu calibration or exact reproduction, an identified thermal spectrum, experimental validation, successful R1/R2, OQ recovery, sensitivity fidelity, full 3D/FEM validation, and cross-material transfer remain `forbidden` without their own direct evidence.

## Round Close

Record actual work, gate results, goal-distance change, claim changes, blockers, the next single priority, and a continue/stop/downgrade disposition.
