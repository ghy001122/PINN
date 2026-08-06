# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_qiu_source_consistent_stage_a`

Current checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`

## Objective And Result

PR #29 preserves the v1 `STOP_BRANCHCONSERVE_PILOT` result. The independent v2
Stage A task audited Qiu S1--S7 and executed 16 source-oracle fixed-point cases
plus the conditional seven-load sentinel. Formula, nested-root, residual,
analytic/finite-difference Jacobian, and eigenpair gates passed.

The S1 high-conductive roots at 12 kOhm are locally unstable, and none of the
seven fixed load values provides a continuous robustly stable domain with the
required nondegenerate transition coverage. The terminal disposition is
`A_STOP_STEADY_ROUTE`.

## Lifecycle And Claims

- v1 B0 steady implementation: `implemented`; claim status `forbidden`.
- v1 Batch 1 pilot: `executed`; `failed_but_informative` numerical-method
  evidence, preserved unchanged.
- v2 Stage A source oracle: `executed`; `failed_but_informative` bounded
  source-model evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- Stage B L1, B1 physics/2D gates, B2 rank, Phase 2, C01, inverse, refusal, and
  all positive R1-R3 claims remain `forbidden` / unassessed.

## Stop

Stage B is not authorized. Do not reinterpret algebraic fixed-point existence
as local stability, use diagnostic S7 as a two-dimensional material law, or
bypass the failed nondegenerate-transition gate into data generation or
training. No automatic solver, circuit, or manuscript-core pivot is authorized.

## Preserved History

The superseded dynamic checkpoints
`Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED` /
`STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4` and
`Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED` /
`B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL` remain immutable.  D0 and all
equivalence evidence were neither modified nor rerun.
