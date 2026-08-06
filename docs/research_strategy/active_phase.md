# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_after_current_clamp_cc_a_pass_awaiting_cc_b_authorization`

Current checkpoint: `Q2_CURRENT_CLAMP_CC_A_PASSED`

## Objective And Result

PR #30 preserves `A_STOP_STEADY_ROUTE` for the voltage-source-plus-series-load
topology. The new ideal-current-clamp CC-A task used the audited S1 major
branches and executed the fixed 0.1--0.7 mA admission matrix. All 14 formal
roots were unique, locally stable, inside the source/operating envelope, and
connected by their fixed-branch predictor/corrector traces. Both branches
passed the state-span and intermediate-state gates; all seven common currents
passed the branch-separation gate.

The terminal disposition is `PASS_CC_A_CURRENT_CLAMP_ADMISSION`. This is a
zero-dimensional branch-admission result, not dynamic reachability or a 2-D
physics result.

The prior `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED` /
`A_STOP_STEADY_ROUTE` checkpoint and PR #29 `STOP_BRANCHCONSERVE_PILOT`
remain immutable for their named voltage-driven steady implementations.

## Lifecycle And Claims

- v1 B0 steady implementation: `implemented`; claim status `forbidden`.
- v1 Batch 1 pilot: `executed`; `failed_but_informative` numerical-method
  evidence, preserved unchanged.
- v2 Stage A source oracle: `executed`; `failed_but_informative` bounded
  source-model evidence.
- current-clamp CC-A: `executed`; `qualified_supported` bounded lumped
  branch-admission evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- CC-B/CC-C, a 2.5-D judge, data generation, CC01, inverse, refusal, and all
  positive R1-R3 claims remain `forbidden` / unassessed.

## Stop

CC-B is not authorized. Do not reinterpret branch-conditioned continuation as
dynamic branch switching, use S1's device-effective resistance as an intrinsic
local conductivity, or bypass the required 2-D uniform-limit/stability gate
into data generation or training. No automatic PINN execution is authorized.

## Preserved History

The superseded dynamic checkpoints
`Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED` /
`STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4` and
`Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED` /
`B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL` remain immutable.  D0 and all
equivalence evidence were neither modified nor rerun.
