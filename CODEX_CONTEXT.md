# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED`.
- Active disposition: `B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`.
- Route: `STOP_FINAL_FORWARD_SOLVER_RESCUE`.
- Execution base: `main@1c9758ef151299a4694b4edcc81dd48feec704ba`.
- Result branch: `codex/controller-relevance-final-forward-rescue`.

The delivery ladder remains minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3; none has positive execution
evidence.

PR #25 D0, exact-condensed v1, NLS-v1, controller-v2, S2 equations and
parameters, protocols, equivalence-v1/v2/v3, and Frozen GT v1.1 remain
unchanged. The D0 conclusion remains historical bounded evidence and was not
rerun.

Equivalence-v1/v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is
forbidden.

## Final Rescue Result

- R0 routed the real 9 V floor-terminal nonlinear failure to R1; the fixed
  12.5 V critical-transition fixture accepted.
- R1 passed its frozen contraction gate: last-four geometric-mean defect ratio
  `0.4995588`, step-8/initial defect `0.0038959`, spectral radius `0.5000018`,
  and maximum power norm `0.5000018`.
- R2's sole safeguarded-Anderson identity formed certified controller bundles
  at the two fixed qualification states: 9 V at `0.625 ns` and the critical
  fixture at `0.15625 ns`.
- B3 passed port and event consistency in both matched windows and passed the
  complete 12.5 V reversal sequence. The 9 V reversal sequence failed exact
  consistency: NLS-v1 published 417 records, Anderson 364, with the first
  direction mismatch at zero-based index 11.

The terminal disposition is therefore
`B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`. Performance timing, B4, fresh S0,
Phase 2, MLP, vanilla PINN, C01, C06, OOD, and manuscript-result execution were
not started.

## Claim Boundary

- R1 and R2: `numerically_validated`; `qualified_supported` only at their
  frozen audit/qualification states.
- B3: `numerically_validated`; `failed_but_informative` numerical-method
  consistency evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- B4/S0/Phase 2/C01/C06/R1-R3 positive claims remain `forbidden`.

This is not an S2 physical failure, a Phase 1 scientific result, a runtime or
campaign-cost result, a PINN result, Qiu quantitative reproduction, or
experimental validation. Do not tune reversal detection, change the matched
window, relax topology, add a solver, run B4/S0, or generate training data
under this task. Read `docs/research_strategy/context_loading_policy.md` before
loading long history.
