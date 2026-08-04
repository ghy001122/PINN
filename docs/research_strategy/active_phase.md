# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_nls_reference_not_asymptotic_t4`

Current checkpoint: `Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED`

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

PR #27 T1/T2 results remained immutable. The prospective physical-coordinate
contract was frozen before one valid 12.5 V T4 worker ran. Local, event, and
signed I-Vd loop gates passed, but `Tc(b)`, `log(sigma)`, and terminal T P95
were nonmonotonic; only Vd passed its final Richardson estimate. The terminal
state is `STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4`, with no selected GT
solver.

## Lifecycle And Claims

- NLS T1/T2/T4 reference time convergence: `numerically_validated`;
  `failed_but_informative` numerical-method evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- T8, selected-level 9 V, held-out, cost/sentinel, B4, fresh S0, Phase 2,
  C01/C06, OOD, and positive R1-R3 claims were not executed and remain
  `forbidden`.

## Stop

Do not run T8, change time metrics, unlock held-out, run cost/sentinel/B4/S0,
or bypass S0 into data generation or training. Any manuscript reroute requires
a separate contract and cannot be described as a successful 2.5D positive-PINN
result.
