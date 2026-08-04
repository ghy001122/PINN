# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_b3v2_reference_not_time_refined`

Current checkpoint: `Q2_B3V2_REFERENCE_NOT_TIME_REFINED_STOPPED`

## Objective And Frozen Authority

B3v2 was the final bounded solution-level validity and GT-selection route. It
made adaptive-path reversal telemetry non-voting for this new task and required
NLS-v1 to pass its own T1/T2 full-field, port, integrity, and transition-event
gates before Anderson could run. Historical B3 and all solver/controller/S2
identities remained read-only.

The superseded checkpoint
`Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED` and its
`B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL` disposition remain immutable
history. D0 and equivalence-v1/v2/v3 were not rerun or revised.

## Actual Result

All four NLS development workers were valid. Quiescent 9 V T1/T2 refinement
passed exactly. Transition 12.5 V retained matching event topology and timing,
but failed temperature, conductive-state, branch-memory, current, and voltage
self-refinement gates. The terminal state is
`STOP_REFERENCE_NOT_TIME_REFINED`, with `selected_gt_solver=none`.

## Lifecycle And Claims

- NLS reference refinement: `numerically_validated`;
  `failed_but_informative` numerical-method evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- Anderson, held-out, B4, fresh S0, Phase 2, C01/C06, OOD, and positive R1-R3
  claims were not executed and remain `forbidden`.

## Stop

Do not run Anderson development, unlock the held-out case, run B4/S0, or bypass
S0 into data generation or training. The only next decision is whether to
authorize a separate C04 observable-subspace plus constrained `gamma_sub`
calibration and identifiability-boundary manuscript. It is not authorized here
and is not a successful 2.5D positive-PINN result.
