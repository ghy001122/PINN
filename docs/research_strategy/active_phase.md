# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_branchconserve_pilot`

Current checkpoint: `Q2_BRANCHCONSERVE_BATCH1_STOPPED`

## Objective And Result

Batch 1 tested whether a unique temperature-primary steady solver could form a
nominal stable+reachable major-branch judge before any defect, Jacobian, SVD,
or PINN work.  The nominal L1 smoke passed, and the heating atlas produced 15
in-domain points with four points in its initial stable+reachable component.

The required cooling endpoint at source voltage `15.8 V` had no certified
contiguous high-conductive load-line bracket under the frozen 33-point scan and
solver budgets.  Therefore the common branch domain is empty and the terminal
disposition is `STOP_BRANCHCONSERVE_PILOT`.

## Lifecycle And Claims

- B0 steady implementation: `implemented`; claim status `forbidden`.
- Batch 1 pilot: `executed`; `failed_but_informative` numerical-method
  evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- L2 sentinel, B1 physics/2D gates, B2 rank, Phase 2, C01, inverse, refusal,
  and all positive R1-R3 claims remain `forbidden` / unassessed.

## Stop

Batch 2 is not authorized.  Do not reinterpret the endpoint failure as S2 or
Phase 1 physics, and do not bypass it into data generation or training.  Any
new endpoint construction or continuation parameterization requires a separate
versioned contract and fresh authorization.

## Preserved History

The superseded dynamic checkpoints
`Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED` /
`STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4` and
`Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED` /
`B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL` remain immutable.  D0 and all
equivalence evidence were neither modified nor rerun.
