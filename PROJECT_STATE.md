# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` / `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_EXACT_CONDENSED_V2_D0_VALID_FAIL_NO_D1`.
- Verified base: `main@c830b4844e58ba63c197429984ac1f5a00a9ccce`.
- D0 identity: `D0-EXACT-CONDENSED-V2-20260803-V1`.
- Frozen S2 physics, protocols, controller-v2, scientific thresholds, PR #23
  Stage A, PR #24 v1/B2 evidence, history, and Frozen GT are unchanged.

The intended positive ladder remains C01/R1 `HysGeo-Hybrid-PINN`, conditional
C06, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3. No rung is
executed or supported.

## D0 Outcome

| Evidence | Result | Boundary |
| --- | --- | --- |
| Frozen replay | PR #24 residual/damping history, 100 matvecs, 135 residual evaluations and failure match | exactly one non-voting replay |
| Original Jacobian | rank `250/250`; `cond_2=139.2163` | explicit L1 central difference |
| Fixed-point Jacobian | rank `250/250`; `cond_2=63.0577` | not rank-deficient |
| Direct corrections | SVD/QR linear backward errors `3.50e-14` / `9.47e-15` | finite linear solves |
| Admissible descent | baseline `||F_fp||inf=6.0661962635e-4`; at `1/128`, `6.1477053274e-4` | no strict decrease in allowed damping range |
| First observed decrease | `1/256`: `6.0635464266e-4` | forbidden by the frozen hard stop |

The machine disposition is `D0_MECHANISM_VALID_FAIL`. The result localizes the
failure to the admissible globalization range at this frozen state: neither
rank deficiency nor a nonfinite/direct-linear-solve failure caused the stop.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| Stage A exact condensation | `supported` bounded algebraic identity | Auxiliary reconstruction only; no root/runtime claim. |
| PR #24 v1 B2 | `executed`; `failed_but_informative` | Immutable 1/24 fail-fast evidence. |
| D0 mechanism audit | `executed`; `failed_but_informative` | One replay and explicit L1 Jacobians; no science vote. |
| v2/D1 onward | `forbidden` / not executed | No Jv freeze or production v2 identity. |
| S0/Phase 1 | `forbidden` / unassessed | `scientific_vote=false`; `formal_execution_count=0`. |
| Phase 2/C01/C06/R1-R3 | `forbidden`; not executed | No data, training, baseline, seed, OOD, field, port, event, or ledger result. |

All project-generated evidence here is literature-guided synthetic numerical
digital-twin evidence, not experimental validation.

## Preserved Boundaries

Equivalence-v1/v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is
forbidden. Do not lower the damping floor, tune a second mechanism, create v2,
resume B2, change S2/controller/gates, or bypass S0. A future pivot requires a
new explicit authorization and must not rewrite this result.
