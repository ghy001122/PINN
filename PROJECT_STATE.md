# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `PHASE1_V2_CONTROLLER_V2_NO_GO_RUNTIME_PERFORMANCE_ONLY`.
- R1 `HysGeo-Hybrid-PINN` remains the minimum manuscript route; R2
  `GeoPhase-HomoMoE-PINN` is the preferred upgrade; R3 is conditional.
- Phase 1-v2 is a Qiu-inspired single-device VO2 x-y plane with explicit VO2,
  mask-local Ti/Au terms, and the source-scale-preserving S2 closure. Qiu
  quantities constrain device-level uniform-mode coefficients, not a local
  material stack or thermal spectrum.
- S2 anchor `d37745b...`; base config SHA-256 `06004985...`. The 63 formal
  items remain `planned_not_executed`; `formal_execution_count=0`; no formal
  campaign is authorized.
- The solver and `7/7` non-voting smoke cases pass after one historical
  zero-signal audit-metric repair. This is software evidence only.
- Historical controller-v1 runtime readiness is `NO_GO_RUNTIME`: its critical
  PRE trajectory hit the locked state-increment floor. The one-replay audit
  isolated a branch-memory time-resolution mechanism and supported one
  versioned controller revision.
- Controller-v2 was preregistered at `406207b...` with the base S2 YAML
  byte-identical. C1 passed 23 accepted intervals. C2 passed 128 intervals and
  finite/nonlinear, four-ledger, lateral, bounded-state, and streaming-parity
  checks. Event/reversal status is only
  `NA_not_observed_within_bounded_C2_window`.
- C3 reached the 880 s worker backstop inside the 900 s envelope at `0/18`
  single-interval samples and `1/9` trajectories. No cost, aggregate RSS/disk,
  or dormant-runner vote was eligible. Disposition:
  `NO_GO_RUNTIME_PERFORMANCE_ONLY`.
- The controller-revision opportunity is consumed. The single pure-equivalence
  performance opportunity is unconsumed and awaits fresh authorization.
- The S1 scientific claim is `forbidden`/unassessed; its timeouts are supported
  infrastructure provenance only. The v6-v8 material-stack route remains
  `failed_but_informative` with no formal execution.
- Phase 1 science, Phase 2, R1-R3, nonzero coupling, FEM/3D, and NbO2 remain
  blocked. Frozen GT v1.1 is unchanged. New evidence is synthetic numerical
  digital-twin evidence, not measurement or experimental validation.

## Current Evidence

| Item | Status | Boundary |
| --- | --- | --- |
| Phase 0 governance | `supported` | Repository routing/integrity only. |
| S2 contract and 63-item manifest | `supported` preregistration facts | Formal count zero; all items unexecuted. |
| S2 implementation/smoke | `supported` software facts | Solver and 7/7 non-voting smoke; no science vote. |
| Source audit | `supported` bounded provenance audit | No eligible holdout found; not proof of nonexistence or validation. |
| S1 diffusive model-form claim | `forbidden` / unassessed | No atomic metric, K fit, or scientific vote. |
| S1 interruption provenance | `supported` infrastructure provenance only | Timeouts/stdout do not establish scientific failure. |
| Controller-v1 readiness | `failed_but_informative` | Historical floor failure; no formal result. |
| Critical mechanism audit | `supported` bounded diagnostic | One replay; branch-memory-only trigger; no production floor. |
| Controller-v2 C1/C2 integrity | `supported` bounded readiness | Hash-locked overlay; integrity/parity pass; no formal/science vote. |
| Controller-v2 campaign runtime feasibility | `forbidden` / unassessed | C3 produced no forecast, aggregate resource, or dormant-runner vote. |
| Controller-v2 C3 performance provenance | `supported` bounded readiness provenance | The locked preflight stopped at its worker backstop; no science vote. |
| v6-v8 material-stack route | `failed_but_informative` | v8 depth-frequency gate failed; 96 items unexecuted. |
| Phase 1-v2 reference result | `forbidden` | Requires every gate in an authorized formal campaign. |
| R1/R2/R3 positive claims | `forbidden` | Require sequential direct evidence. |

## Retained Historical Evidence

- Frozen synthetic 1D GT v1.1 is immutable.
- Constrained `gamma_sub` recovery remains `qualified_supported` only inside
  its named prior/calibration boundary and is the downgrade route.
- Complete-PINN, M40/M40R, M44, OASIS, public-source, and other retained
  outcomes keep their claim-matrix statuses; none validates Phase 1-v2.

## Delivery Boundary

Stop at `NO_GO_RUNTIME_PERFORMANCE_ONLY`. The only next decision is whether to
authorize one mathematically equivalent performance optimization and an
identical readiness rerun. Such work may not change physics, tolerances,
protocols, grids, controller semantics, scientific gates, or the manifest.
Formal execution, Phase 2, R1, and R2 remain blocked.

Do not rerun S1 or v6-v8; train a PINN; generate Phase 2 data; run inverse;
modify frozen GT; add nonzero coupling; run FEM/3D, M44, or NbO2; or claim
Phase 1/Qiu/experimental success.
