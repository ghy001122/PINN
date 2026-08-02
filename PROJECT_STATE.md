# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` / `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_NLS_V1_QUALIFICATION_REJECTED_NO_S0`.
- Base: `main@42e16ff7b9abd34b5ce7272eaa74ad60d49348d3`.
- NLS-v1 code anchor: `ee07846b89280fafdac18166f02ff688d8d92f58`.
- NLS-v1 result evidence: `f3b7db17126c5591569cb98839a2df3211b1fef9`.
- Frozen S2 physics, protocols, scientific thresholds, 63/60/3 plan, historical evidence, and Frozen GT v1.1 are unchanged.

The intended positive ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3. No rung is executed or supported.

## NLS-v1 Result

| Evidence | Result | Boundary |
| --- | --- | --- |
| Frozen controller V2 state | PASS in 6 fallback iterations | residual `4.884209208104767e-9`; defect `5.008622738778001e-9` |
| Frozen controller V4 state | PASS in 4 fallback iterations | residual `5.853515129323472e-9`; defect `4.958286003997614e-9` |
| Standard 9 V T1 | rejected by frozen performance gate | stopped at `17.06015625 us`; `27136.6188 > 21600 s`; 3413/4001 outputs |
| Strict 9 V T4 | invalid endpoint residue | full NLS passed, but a `1.73133534418779e-17 s` residue produced a cancellation-dominated ledger step |
| Endpoint correction | implemented and regression-tested as `v1p1` | uses the same `1e-12` relative landing tolerance in solver and evaluator |

The full V2 qualification was not invoked because the endpoint-only change cannot affect T1 before its wall-time stop. Both frozen failure states already pass, so the goal's conditional Schur trigger was false. Terminal disposition: `GOAL_UNSUCCESSFUL_NLS_V1`.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| NLS-v1/v1p1 code | `implemented`; software fact `supported` | Dual-gate fallback, structured telemetry, endpoint consistency, and focused regression. |
| NLS-v1 qualification | `executed`; `failed_but_informative` | One required standard trajectory exceeded its frozen wall-time gate before completion. |
| S0/Phase 1 | `forbidden` / unassessed | Fresh S0 never started; no scientific vote and `formal_execution_count=0`. |
| Phase 2/C01/C06 | `forbidden`; not executed | No dataset, training, baselines, OOD, field, port, event, ledger, or cost result. |
| R1/R2/R3 | `forbidden` | Sequential evidence ladder remains unmet. |

This is bounded numerical-method performance evidence, not experimental validation and not an S2 physical-law failure.

## Preserved Boundaries And Next Route

Strict-equivalence-v1 and equivalence-v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is forbidden. Historical E0/S0/controller-v3 outcomes remain immutable. No current experiment is authorized.

S1 science is `forbidden`/unassessed; interruption facts are supported infrastructure provenance only and cast no scientific vote.

The next high-value bottleneck is a performance-efficient, mathematically equivalent nonlinear solve that can reach the complete standard/strict qualification trajectories under fixed physical and scientific gates. Reopening requires a new bounded goal and identity; it cannot be framed as this NLS-v1 qualification's continuation or permission to bypass S0 before C01.
