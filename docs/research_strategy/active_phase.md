# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_controller_v3_candidates_exhausted`

Current checkpoint: `Q2_CONTROLLER_V3_EXHAUSTED_NO_S0`

## Objective And Frozen Authority

The goal attempted to qualify one of at most two nonzero-drive controller-v3 policies, then conditionally run a fresh S0 judge and C01/C06. S2 equations, physical parameters, protocols, thresholds, controller-v2 inner step/embedded estimator, and the 63/60/3 plan remained frozen.

Historical E0/S0/equivalence outputs and Frozen GT v1.1 remained read-only.

## Actual Controller Qualification

| Candidate | Versioned change | Terminal boundary | Disposition |
| --- | --- | --- | --- |
| 1 | Output reconstruction decoupled from accepted solver landings | 9 V at `2.1094726562498093e-6 s`; implicit solve failed closed at locked outer floor | rejected; 0 published qualification runs |
| 2 | Same path plus bounded geometric recovery to floor/16 | 9 V at `2.2577221679678546e-6 s`; frozen 1000-rejection case cap exceeded | rejected; 0 published qualification runs |

V1 and V3 were external zero-publication host invocations. V2 and V4 are the two numerical controller dispositions. Both policies are consumed; no third candidate is allowed.

Terminal state: `GOAL_UNSUCCESSFUL_CONTROLLER_V3_EXHAUSTED`.

## Lifecycle And Claims

- Controller-v3 implementations: `implemented` and `executed` in bounded non-voting qualification.
- Controller-v3 qualification claim: `failed_but_informative`.
- Fresh S0: not started; `forbidden` / unassessed.
- `formal_execution_count=0`.
- Phase 2, MLP, vanilla PINN, C01, C06, OOD, and R1/R2/R3: not executed and `forbidden`.

The controller boundary is numerical-integration evidence, not a physical-law failure or PINN result.

## Stop And Next Bottleneck

No experiment is authorized. A future goal may study the nonzero-drive implicit solver at the two content-addressed failure states, with a new identity and bounded solver-level policy. It may not resume this qualification, add controller candidate 3, relax physics/science gates, return to equivalence, or bypass S0 before Phase 2/C01.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains immutable and non-retryable. Equivalence-v4/v5 is forbidden (`equivalence-v4/v5`). No retry is authorized.
