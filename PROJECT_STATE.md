# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` / `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_EXACT_CONDENSED_B2_VALID_FAIL_NO_S0`.
- Base: `main@6e605ec660494d17bd8b192b59e0654b4c1d3b0a`.
- B1 implementation anchor: `2d60a973f8d61e58525e1c2b83db78961da226d1`.
- B2 execution identity: `57e3e29643daab9d9af76e7f946b46fc0e602269`.
- Frozen S2 physics, protocols, controller-v2, scientific thresholds,
  historical evidence, 63/60/3 plan, and Frozen GT v1.1 are unchanged.

The intended positive ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3. No rung is executed or supported.

## B1/B2 Outcome

| Evidence | Result | Boundary |
| --- | --- | --- |
| B1 exact reconstruction/parity | focused checks pass; auxiliary reconstruction remains at roundoff | implementation evidence only |
| B2 first root | `B2-ORIGINAL-S1-DT10p0NS`; L1, 9 V, `dt=10 ns` | valid prescribed-solver attempt |
| Nonlinear trajectory | 5 accepted Newton corrections, 6 converged LGMRES calls, 100 matvecs, 135 reduced evaluations | final Armijo search failed for every damping `1...1/128` |
| Last available residuals | reduced/full scaled `9.519603587211078e-3`; auxiliary `1.4392805451179502e-16` | `1e-8` root gate not reached; full defect not certified |
| B2 matrix | 0/1 executed roots passed; 23/24 unassessed | fail-fast terminal disposition |

The machine disposition is `B2_REDUCED_ROOT_VALID_FAIL`. It is
`failed_but_informative` evidence that this frozen exact-condensed Newton/LGMRES
identity did not qualify even its first root. It does not refute the algebraic
condensation identity or S2 physics.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| B1 exact-condensed code | `implemented`; software fact | No performance, trajectory, or physics claim. |
| B2 root qualification | `executed`; `failed_but_informative` | One valid root attempt failed the frozen globalization/root gate. |
| B3/B4/runtime | `forbidden` / unassessed | Not started after B2 fail-fast. |
| S0/Phase 1 | `forbidden` / unassessed | `scientific_vote=false`; `formal_execution_count=0`. |
| Phase 2/C01/C06/R1-R3 | `forbidden`; not executed | No data, training, baselines, seeds, OOD, field, port, event, or ledger result. |

This is literature-guided synthetic numerical digital-twin evidence about one
numerical solver identity, not experimental validation or a physical-law vote.

## Preserved Boundaries And Next Route

Strict-equivalence-v1 and equivalence-v2/v3 remain immutable and non-retryable;
equivalence-v4/v5 is forbidden. Historical E0/S0/controller/NLS results remain
immutable. S1 science is `forbidden`/unassessed; interruption facts are supported
infrastructure provenance only and cast no scientific vote.

No experiment is authorized. Re-entry requires a fresh bounded goal that names
a materially new reduced-root strategy and preserves the same physical,
controller, and certification gates. This B2 matrix cannot be resumed, and S0
cannot be bypassed before Phase 2/C01.
