# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_b3_matched_window_reversal_topology_failure`

Current checkpoint:
`Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED`

## Objective And Frozen Authority

The completed task was the final bounded controller-relevance rescue after PR
#25 D0. It permitted production-controller R0, a conditional contraction audit,
one safeguarded-Anderson identity, and downstream work only after every gate
passed. D0, exact-condensed v1, NLS-v1, controller-v2, S2, protocols,
thresholds, equivalence history, and Frozen GT remained read-only.

## Actual Result

R0 reached the active 9 V floor with a nonlinear certification failure and
routed correctly to R1. R1 passed its preregistered local contraction gate. R2
then certified the sole safeguarded-Anderson identity on both fixed controller
qualification states.

B3 formed a valid matched-window result. Both methods passed local integrity,
terminal-current and device-voltage NRMSE, and event timing/topology gates in
the 9 V and 12.5 V windows. The 12.5 V reversal sequence also matched. The 9 V
reversal sequence did not: NLS-v1 produced 417 records and Anderson 364, with
the first direction mismatch at zero-based index 11.

Terminal state: `B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`.

## Lifecycle And Claims

- R1 contraction audit: `numerically_validated`; `qualified_supported` within
  its frozen terminal-root context.
- R2 controller qualification: `numerically_validated`;
  `qualified_supported` at its two fixed states.
- B3: `numerically_validated`; `failed_but_informative` numerical-method
  consistency evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- B4, fresh S0, Phase 2, C01/C06, OOD, and positive R1-R3 claims are unexecuted
  and `forbidden`.

## Stop

The final forward-solver rescue is consumed and stopped. Do not tune the
reversal detector, change the 9 V window, relax exact topology, add a second
solver, run B4/S0, or bypass S0 into data generation or training. A separate
C04 observable-subspace plus constrained `gamma_sub` calibration and
identifiability-boundary manuscript is only a recommendation for a future
decision; it is not authorized here and cannot be represented as the intended
2.5D positive-PINN R1 result.
