# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_B3V2_REFERENCE_NOT_TIME_REFINED_STOPPED`.
- Execution base: `main@51898e4406916b3675cb74f4888bf3986e0c76a1`.
- Result branch: `codex/b3v2-continuum-final-gt-route`.
- Terminal disposition: `STOP_REFERENCE_NOT_TIME_REFINED`.
- Selected GT solver: `none`.

Historical B3, exact-condensed/Anderson/NLS identities, controller-v2, frozen
S2 physics and protocols, equivalence history, and Frozen GT remain unchanged.
The intended positive ladder remains C01/R1 `HysGeo-Hybrid-PINN`, conditional
C06, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3; no positive rung
was executed.

## B3v2 Outcome

| Regime | Result | Evidence boundary |
| --- | --- | --- |
| NLS 9 V T1/T2 | exact full-field and port equality | Valid bounded solution-level reference evidence |
| NLS 12.5 V T1/T2 | event gate passes; field and port gates fail | T RMSE `0.1680477625 K`; s RMSE `0.00255163054`; b RMSE `0.01416810089`; current NRMSE `0.01977322760`; voltage NRMSE `0.00902650893` |
| Anderson/held-out/B4a | not executed | Blocked by the NLS reference gate |

Development used `401.453125 s` aggregate CPU and `757.4825843 s` wall time.
The aggregation-only scope correction did not rerun or modify any worker/field
artifact and preserved its original aggregate files.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| B3v2 NLS reference refinement | `numerically_validated`; `failed_but_informative` | Numerical-method evidence; no physical vote |
| Anderson/held-out/B4/S0 | `planned`; `forbidden` | No selected solver or downstream execution |
| Phase 2/C01/C06/R1-R3 | `planned`; `forbidden` | No data, training, baseline, seed, OOD, field, port, event, or ledger result |

`scientific_vote=false` and `formal_execution_count=0`. Evidence is
`literature-guided synthetic numerical digital-twin evidence`, not
experimental validation.

S1 science is `forbidden`/unassessed; interruption facts are supported as
infrastructure provenance only.

## Preserved Boundary

Do not run Anderson/held-out/B4/S0, add or tune another solver, rerun frozen
audits, or bypass S0. The only next decision is whether to authorize a separate
C04/`gamma_sub` identifiability-boundary contingency manuscript; it is not
activated and cannot be described as 2.5D positive-PINN success.
