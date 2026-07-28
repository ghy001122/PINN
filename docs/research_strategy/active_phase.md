# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `phase1v2_controller_v2_no_go_runtime_performance_only`

Current checkpoint: `PHASE1_V2_CONTROLLER_V2_NO_GO_RUNTIME_PERFORMANCE_ONLY`

## Objective

Establish the independent conservative judge required before Phase 2 or any
positive PINN claim: a Qiu-inspired single-device VO2 x-y model with explicit
VO2/mask-local Ti/Au terms, the S2 closure, white-box hysteresis, RC coupling,
terminal integration, and complete ledgers. Its discretization remains
independent from future PINN residual code.

## Current Authority

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`
- `configs/geophase_phase1_v2_s2_reference.yaml`
- `configs/geophase_phase1_v2_formal_manifest.yaml`
- `configs/geophase_phase1_v2_execution_addendum.yaml`
- `configs/geophase_phase1_v2_embedded_time_controller_v2.yaml`
- `configs/qiu_vo2_phase1_source_contract.yaml`
- `configs/geo2p5d_stage.yaml`
- `docs/method_equations.md`
- `NEXT_ACTIONS.md`

The source audit, S1 sensitivity, controller-v1 failure, and critical mechanism
audit are bounded auxiliary/history evidence; none can modify S2 or the formal
manifest.

## Current Evidence And Authorization

- S2 anchor `d37745b...`; controller-v2 anchor `406207b...`. The base S2 YAML
  remains byte-identical. All 63 formal items are `planned_not_executed` and
  `formal_execution_count=0`.
- The solver and seven bounded smoke cases exist. One historical zero-signal
  audit repair changed no physics or scientific gate.
- Controller-v1 remains historical `NO_GO_RUNTIME`. Its single-replay audit
  supported exactly one controller revision; that revision has now executed.
- Controller-v2 C1 passed 23 accepted intervals. C2 passed 128 intervals with
  finite/nonlinear, first-half/second-half/aggregate four-ledger, lateral,
  bounded-state, and streaming-parity checks. No event/reversal was observed
  in the bounded window; the only allowed label is
  `NA_not_observed_within_bounded_C2_window`.
- C3 reached the 880 s worker backstop inside its 900 s envelope at `0/18`
  single-interval samples and `1/9` trajectories. Forecast and dormant runner
  were not reached. Disposition: `NO_GO_RUNTIME_PERFORMANCE_ONLY`.
- This is not controller/physics/scientific failure, four-hour infeasibility,
  or a memory/disk vote. The controller-revision opportunity is consumed; the
  one pure-equivalence performance opportunity is unconsumed and not
  automatically authorized.
- The source audit found no eligible holdout. S1 science is
  `forbidden`/unassessed; its interruption is infrastructure provenance only.
  v6-v8 remain terminal `failed_but_informative` historical evidence.

## Pass And Stop Rules

A Phase 1-v2 pass requires every source/positivity, manufactured, terminal,
ledger, mesh/time/event, mask/overlap, limit, trend, and failure-path gate in a
separately authorized formal campaign. Smoke, C1/C2 integrity, or finite output
cannot vote.

Controller-v2 did not establish campaign runtime readiness. Any later use of
the sole performance opportunity requires fresh authorization and must be
mathematically equivalent: physics, tolerances, states, protocols, grids,
controller semantics, scientific gates, and manifest remain fixed.

## Restrictions

Do not rerun readiness without authorization; execute a formal item; create a
real formal registry; train a PINN; generate Phase 2 data; run inverse; fit or
digitize sources; rerun S1/v6-v8; modify frozen GT; add nonzero coupling; or run
FEM/3D, M44, or NbO2. Phase 1/Qiu/experimental, R1/R2, OQ, sensitivity, and
cross-material success claims remain `forbidden`.

## Immediate Next Checkpoint

Stop and request a user decision on the single unconsumed pure-equivalence
performance opportunity. Even a future readiness GO would still require fresh
formal-campaign authorization.
