# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_exact_condensed_v2_d0_valid_mechanism_failure`

Current checkpoint: `Q2_EXACT_CONDENSED_V2_D0_VALID_FAIL_NO_D1`

## Objective And Frozen Authority

The authorized plan allowed one replay of PR #24's first failed root to decide
whether a fixed-point-defect Newton/Jv identity had an admissible descent
mechanism. S2 equations, parameters, protocols, controller-v2, production
implicit/NLS code, PR #23 Stage A, PR #24 v1 evidence, thresholds, historical
outputs, and Frozen GT remained read-only.

## Actual D0 Result

The replay exactly reproduced the frozen v1 history and failure. Both L1
explicit Jacobians are full rank, and the fixed-point direct correction is
finite with near-machine-precision linear backward error. However, no damping
in the allowed set `1...1/128` strictly lowers `||F_fp||inf`; the first decrease
appears only at forbidden damping `1/256`.

Terminal state: `D0_MECHANISM_VALID_FAIL`.

## Lifecycle And Claims

- D0 diagnostic: `executed`; `failed_but_informative` numerical-method
  evidence only.
- `scientific_vote=false`; `formal_execution_count=0`.
- No Jv rule was frozen and no v2 production solver identity was created.
- D1/D2/B3/B4, fresh S0, Phase 2, C01/C06, OOD, and R1/R2/R3 remain
  unexecuted and `forbidden`.

This is not an S2/Phase 1 scientific vote, runtime/campaign feasibility result,
or PINN result.

## Stop

The plan's D0 hard stop binds. Do not reduce the damping minimum, perform a
second mechanism-tuning replay, create v2, resume old B2, switch to another
solver, return to equivalence, or bypass S0 before Phase 2/C01. The only
plan-defined recommendation after this two-dimensional forward-route stop is a
separately authorized C04 observable-subspace plus `gamma_sub` calibration and
identifiability-boundary manuscript pivot; it is not authorized here.
