# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_EXACT_CONDENSED_B2_VALID_FAIL_NO_S0`.
- Goal: `Q2_EXACT_CONDENSED_SOLVER_TO_FRESH_S0_C01_C06_R1_EVIDENCE`.
- Base: `main@6e605ec660494d17bd8b192b59e0654b4c1d3b0a`.
- B1 implementation anchor: `2d60a973f8d61e58525e1c2b83db78961da226d1`.
- B2 execution identity: `57e3e29643daab9d9af76e7f946b46fc0e602269`.

PR #23 Stage A assets, the production implicit solver, NLS-v1,
controller-v2, historical run identities/equivalence evidence, and Frozen GT
v1.1 remained byte-for-byte unchanged.

The long-term delivery ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3; none is executed or supported.

## Exact-Condensed Result

B1 implemented a new temperature-primary exact-condensed solver and independent
controller orchestration. Focused residual-parity, exact auxiliary
reconstruction, zero-drive, nested-grid pack/unpack, embedded-step, and hard
budget tests passed. This is an `implemented` software fact only.

The preregistered B2 run `B2-EXACT-CONDENSED-20260803-V1` stopped fail-fast on
its first of 24 roots: `B2-ORIGINAL-S1-DT10p0NS`, the first frozen 9 V replay
state at L1 and `dt=10 ns`. After five accepted Newton corrections and six
converged LGMRES calls, none of the permitted damping values from `1` through
`1/128` passed Armijo. The last available reduced/full scaled residual was
`9.519603587211078e-3`; the exact auxiliary residual remained
`1.4392805451179502e-16`. No final full fixed-point defect was certified.

Terminal disposition: `B2_REDUCED_ROOT_VALID_FAIL`. One root was executed,
zero passed, and 23 remain unassessed. B3, B4, fresh S0, Phase 2, MLP, vanilla
PINN, C01, C06, OOD, and manuscript-result execution did not start.

## Claim Boundary And Stop

- B1 solver/controller: `implemented`; software fact only.
- B2 qualification: `executed`; `failed_but_informative` numerical-method
  evidence for this frozen solver identity.
- `scientific_vote=false`; `formal_execution_count=0`.
- S0/Phase 1, runtime feasibility, Phase 2, C01/C06, and R1/R2/R3 remain
  `forbidden` / unassessed.

This result is not an S2 physical-law failure, a campaign cost result, a PINN
result, Qiu quantitative reproduction, or experimental validation. The goal's
single solver strategy stopped at its first valid B2 failure; no second
globalization/solver strategy is authorized.

No experiment is authorized. Any future re-entry requires a new versioned goal
and solver identity; it may not change frozen physics/controller/thresholds,
resume this B2 matrix, return to equivalence, or bypass a valid S0 judge before
Phase 2/C01.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains
immutable and non-retryable. Equivalence-v4/v5 is forbidden; no retry is
authorized.

Read `docs/research_strategy/context_loading_policy.md` before loading long
history.
