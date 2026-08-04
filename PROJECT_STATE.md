# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED`.
- Execution base: `main@4f98ed5e16ce7a0645a51f83d19ae97414c4c185`.
- Result branch: `codex/nls-reference-time-convergence-closure-v2`.
- Terminal disposition: `STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4`.
- Selected GT solver: `none`.

Historical B3, exact-condensed/Anderson/NLS identities, controller-v2, frozen
S2 physics and protocols, equivalence history, and Frozen GT remain unchanged.
The intended positive ladder remains C01/R1 `HysGeo-Hybrid-PINN`, conditional
C06, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3; no positive rung
was executed.

## NLS Time-Convergence v2 Outcome

| Regime | Result | Evidence boundary |
| --- | --- | --- |
| NLS 12.5 V T1/T2/T4 | local/event/signed-loop gates pass; asymptotic gate fails | `Tc(b)`, `log(sigma)`, and terminal T P95 are nonmonotonic; only Vd passes final Richardson estimate |
| T8/9 V selected/held-out/cost | not executed | Blocked by the valid T4 stop |

The new T4 worker used `66.296875 s` CPU and `157.206668 s` wall time; the stage
used `163.017521 s` wall time. PR #27 T1/T2 atoms were not rerun or modified.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| NLS T1/T2/T4 time convergence | `numerically_validated`; `failed_but_informative` | Numerical-method evidence; no physical vote |
| T8/held-out/cost/sentinel/B4/S0 | `planned`; `forbidden` | No selected solver or downstream execution |
| Phase 2/C01/C06/R1-R3 | `planned`; `forbidden` | No data, training, baseline, seed, OOD, field, port, event, or ledger result |

`scientific_vote=false` and `formal_execution_count=0`. Evidence is
`literature-guided synthetic numerical digital-twin evidence`, not
experimental validation.

S1 science is `forbidden`/unassessed; interruption facts are supported as
infrastructure provenance only.

## Preserved Boundary

Do not run T8/T16, alter the metric contract, add another held-out, run
cost/sentinel/B4/S0, add or tune another solver, or bypass S0. Any manuscript
reroute requires a separate contract and cannot be described as 2.5D
positive-PINN success.
