# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` / `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CONTROLLER_V3_EXHAUSTED_NO_S0`.
- Base: `main@b28aa97ccbdbc1b03b43e8deb13b3bbc35c71ead`.
- Controller terminal evidence: `73dc41f81760a805cec0f768179f327c3abcbe9d` on PR #21.
- S2 physics, source contract, controller-v2 inner estimator, and 63/60/3 scientific plan are unchanged.
- Frozen GT v1.1 and historical claim-bearing evidence are unchanged.

The intended positive ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3. No rung is executed or supported.

## Controller-v3 Result

| Invocation | Role | Terminal | Published runs | Scientific vote |
| --- | --- | --- | ---: | --- |
| V1 | external launch provenance | `INVALID_EXTERNAL_INVOCATION` | 0 | false |
| V2 | candidate 1 | locked-floor implicit failure at `2.1094726562498093e-6 s` | 0 | false |
| V3 | external host provenance | `INVALID_EXTERNAL_INVOCATION` | 0 | false |
| V4 | candidate 2 | per-case rejection cap at `2.2577221679678546e-6 s` | 0 | false |

Candidate 1 decoupled fixed outputs from solver landings. Candidate 2 added bounded geometric recovery to floor/16 without forced acceptance or relaxed gates. Candidate 2 advanced only `1.4824951171804533e-7 s` farther before the frozen 1000-rejection case cap bound. Both permitted numerical policies are consumed.

Terminal disposition: `GOAL_UNSUCCESSFUL_CONTROLLER_V3_EXHAUSTED`.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| Controller-v3 code | `implemented`; software fact `supported` | Versioned output-decoupling and bounded subfloor policies with focused tests. |
| Controller-v3 qualification | `executed`; `failed_but_informative` | Two numerical candidates rejected in the first 9 V case; no qualification run published. |
| S0/Phase 1 | `forbidden` / unassessed | Fresh S0 never started; no scientific vote and `formal_execution_count=0`. |
| Phase 2/C01/C06 | `forbidden`; not executed | No dataset, training, baselines, OOD, field, port, event, ledger, or cost result. |
| R1/R2/R3 | `forbidden` | Sequential evidence ladder remains unmet. |

This is bounded numerical-integration evidence, not experimental validation and not an S2 physical-law failure. All project-generated evidence retains the identity `literature-guided synthetic numerical digital-twin evidence` where scientific model output is discussed.

## Preserved Boundaries And Next Route

strict-equivalence-v1 and equivalence-v2/v3 remain immutable and non-retryable; equivalence-v4/v5 is forbidden. Historical E0/S0 outcomes remain immutable. No current experiment is authorized.

S1 science is `forbidden`/unassessed; interruption facts are supported infrastructure provenance only and cast no scientific vote.

The next high-value bottleneck is the shared nonzero-drive implicit-step convergence at the two frozen failure states. Reopening requires a new bounded goal and solver-level identity; it cannot be framed as qualification continuation, controller candidate 3, equivalence work, or permission to bypass S0 before C01.
