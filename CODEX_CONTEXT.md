# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_EXACT_CONDENSED_V2_D0_VALID_FAIL_NO_D1`.
- Active plan disposition: `D0_MECHANISM_VALID_FAIL`.
- Verified base: `main@c830b4844e58ba63c197429984ac1f5a00a9ccce`.
- D0 identity: `D0-EXACT-CONDENSED-V2-20260803-V1`.

PR #23 Stage A assets, PR #24 v1 solver/B2 evidence, the production implicit
solver, NLS-v1, controller-v2, historical run/equivalence identities, and
Frozen GT v1.1 remained unchanged.

The delivery ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3. None is executed or supported.

## D0 Result

D0 reproduced the frozen PR #24 10 ns failure exactly: six residual values,
five accepted damping values, 100 Krylov matvecs, 135 original-residual
evaluations, and terminal `ARMIJO_LINE_SEARCH_FAILURE` all match.

At the last accepted iterate, both explicit L1 central-difference Jacobians are
full rank (`250/250`). The original-residual Jacobian has condition number
`139.2163`; the fixed-point-defect Jacobian has condition number `63.0577`.
The fixed-point SVD/QR corrections solve their explicit linear system to
backward errors `3.50e-14` and `9.47e-15`, respectively.

The fixed-point defect nevertheless increases from `6.066196263505657e-4` to
`6.147705327432650e-4` at the smallest permitted damping `1/128`. The first
strict decrease occurs only at `1/256`, outside the frozen admissible range.
This triggers the plan's D0 hard stop before Jv selection, v2 production
identity creation, or the non-voting dyadic root map.

Terminal disposition: `D0_MECHANISM_VALID_FAIL`.

## Claim Boundary And Stop

- D0: `executed`; `failed_but_informative` numerical-method evidence.
- `scientific_vote=false`; `formal_execution_count=0`.
- D1/D2/B3/B4, fresh S0, Phase 2, MLP, vanilla PINN, C01/C06, OOD, and
  R1/R2/R3: not executed and `forbidden`.

This result is not an S2 physical-law failure, solver runtime result, campaign
cost result, PINN result, Qiu quantitative reproduction, or experimental
validation. The plan forbids lowering the damping floor, tuning a second
mechanism, creating v2 after this failure, or switching solver identities.

Equivalence-v1/v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is
forbidden. Read `docs/research_strategy/context_loading_policy.md` before
loading long history.
