# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_B3V2_REFERENCE_NOT_TIME_REFINED_STOPPED`.
- Active disposition: `STOP_REFERENCE_NOT_TIME_REFINED`.
- Selected GT solver: `none`.
- Execution base: `main@51898e4406916b3675cb74f4888bf3986e0c76a1`.
- Result branch: `codex/b3v2-continuum-final-gt-route`.

The B3v2 task treated historical adaptive-path reversal lists as supplemental
telemetry and tested solution-level NLS self-refinement before any Anderson
comparison. PR #26-era B3, its solvers/controllers, S2, parameters, protocols,
equivalence history, and Frozen GT remained unchanged.

Equivalence-v1/v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is
forbidden.

The delivery ladder remains minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3. None is unlocked or supported by
the current result.

## B3v2 Result

Four valid NLS-v1 development workers completed. The 9 V T1/T2 fields and port
traces were identical. At 12.5 V, temperature RMSE was `0.1680477625 K`
against `0.05 K`, conductive-state RMSE was `0.00255163054` against `0.0005`,
branch-memory RMSE was `0.01416810089` against `0.0005`, current NRMSE was
`0.01977322760` against `0.01`, and voltage NRMSE was `0.00902650893` against
`0.005`. Event topology and timing passed.

The terminal disposition is `STOP_REFERENCE_NOT_TIME_REFINED`. Anderson,
held-out evaluation, B4a/B4b, fresh S0, Phase 2, MLP, vanilla PINN, C01, C06,
OOD, and manuscript-result execution were not started.

## Claim Boundary

- B3v2 NLS reference refinement: `numerically_validated`;
  `failed_but_informative` numerical-method evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- Selected GT solver is `none`; all downstream positive claims remain
  `forbidden`.

This is not an S2 physical failure, Phase 1 scientific result, campaign-cost
result, PINN result, Qiu quantitative reproduction, or experimental
validation. Do not run Anderson, unlock held-out cases, run B4/S0, or generate
training data under this task. Read
`docs/research_strategy/context_loading_policy.md` before loading long history.
