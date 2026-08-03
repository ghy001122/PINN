# Next Actions

## Authoritative Current Queue

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED`.
- Disposition: `B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`.
- R1 contraction and R2 fixed-state controller qualification passed within
  their bounded scopes.
- B3 port/event consistency passed in both windows and 12.5 V reversal
  consistency passed, but 9 V exact reversal direction/order failed: 417 NLS-v1
  records versus 364 Anderson records, first mismatch at zero-based index 11.
- Performance timing, B4, fresh S0, Phase 2, MLP, vanilla PINN, C01/C06, OOD,
  and manuscript-result execution were not started.
- `scientific_vote=false`; `formal_execution_count=0`.

## Single Next Priority

Do not retry or tune the final forward-solver rescue. The only next decision is
whether a separately contracted C04 observable-subspace plus constrained
`gamma_sub` calibration and identifiability-boundary contingency manuscript is
worth activating. It is not authorized by the current task and would be a
different paper identity, not a successful 2.5D positive-PINN R1 route.
