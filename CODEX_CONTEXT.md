# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED`.
- Active disposition: `STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4`.
- Selected GT solver: `none`.
- Execution base: `main@4f98ed5e16ce7a0645a51f83d19ae97414c4c185`.
- Result branch: `codex/nls-reference-time-convergence-closure-v2`.

The B3v2 task treated historical adaptive-path reversal lists as supplemental
telemetry and tested solution-level NLS self-refinement before any Anderson
comparison. PR #26-era B3, its solvers/controllers, S2, parameters, protocols,
equivalence history, and Frozen GT remained unchanged.

Equivalence-v1/v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is
forbidden.

The delivery ladder remains minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3. None is unlocked or supported by
the current result.

## NLS Time-Convergence v2 Result

PR #27 T1/T2 atoms were reused without rerun. One valid 12.5 V T4 worker
completed. Local integrity, event, and signed I-Vd loop gates passed, but
`Tc(b)`, production white-box `log(sigma)`, and terminal-temperature P95 were
nonmonotonic. Temperature RMSE and current NRMSE were monotonic, but their
Richardson estimates remained above gate (`0.0984677 > 0.05 K` and
`0.0107354 > 0.01`).

The terminal disposition is `STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4`.
T8, selected-level 9 V, held-out, cost profiling, sentinel, B4b, fresh S0,
Phase 2, MLP, vanilla PINN, C01, C06, OOD, and manuscript-result execution were
not started.

## Claim Boundary

- NLS T1/T2/T4 reference time convergence: `numerically_validated`;
  `failed_but_informative` numerical-method evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- Selected GT solver is `none`; all downstream positive claims remain
  `forbidden`.

This is not an S2 physical failure, Phase 1 scientific result, campaign-cost
result, PINN result, Qiu quantitative reproduction, or experimental
validation. Do not run T8, unlock held-out cases, run cost/sentinel/B4/S0, or
generate training data under this task. Read
`docs/research_strategy/context_loading_policy.md` before loading long history.
