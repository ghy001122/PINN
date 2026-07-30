# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `phase1v2_source_corrected_v3_performance_repair_preregistered_pending_implementation`

Current checkpoint:
`PHASE1_V2_SOURCE_CORRECTED_V3_PERFORMANCE_REPAIR_PREREGISTERED_PENDING_IMPLEMENTATION`

Equivalence-audit substate:
`NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`

## Objective

Establish the independent conservative judge required before Phase 2 or any
positive PINN claim: a Qiu-inspired single-device VO2 x-y model with explicit
VO2/mask-local Ti/Au terms, the S2 closure, white-box hysteresis, RC coupling,
terminal integration, and complete ledgers. Its discretization remains
independent from future PINN residual code.

## Current Authority

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`
- `configs/geophase_phase1_v2_s2_reference_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml`
- `configs/qiu_vo2_phase1_source_contract_v3.yaml`
- `configs/geo2p5d_stage_source_corrected_v3.yaml`
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
- Controller-v1 remains historical `NO_GO_RUNTIME`; its diagnostic supported
  the now-consumed controller revision.
- Controller-v2 C1/C2 passed bounded integrity/parity. C3 stopped at `0/18`
  intervals and `1/9` trajectories before forecast or dormant-runner votes:
  `NO_GO_RUNTIME_PERFORMANCE_ONLY`. This was not a physics/science vote.
- The source audit found no eligible holdout. S1 science is
  `forbidden`/unassessed; its interruption is infrastructure provenance only.
  v6-v8 remain terminal `failed_but_informative` historical evidence.
- Source-corrected v3 is anchored at `0ebe037...`. Qiu main Figure 2 and SI
  Figure S2 support 15.8 V, not 15.0 V, as the qualitative metallic-lock probe.
  The correction changes no S2 equation, controller semantic, scientific
  threshold, inventory count, or formal execution state; it is not calibration
  or independent validation.
- Contract SHA-256 is `84e1ecb...`; candidate commit/tree/identity are
  `1ae2704...`/`d3833a4...`/`39044f37...`.
- The historical loader launch remains invalid infrastructure provenance:
  `0/57` rows, zero votes, and no comparison.
- Harness identity `73f7d7d1...` enabled the sole valid audit. It completed
  `12/57` rows and fail-fast rejected plan 11,
  `EQ-INTERVAL-L1-legal_critical-base`, at
  `1.4757614757614759 > 1e-12`. Progression and failure-topology were not
  reached.
- Disposition is `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`. This rejects the
  optimized implementation's strict equivalence, not S2 physics. No retry,
  further optimization, C1/C2/C3, or formal execution is authorized.

## Pass And Stop Rules

A Phase 1-v2 pass requires every source/positivity, manufactured, terminal,
ledger, mesh/time/event, mask/overlap, limit, trend, and failure-path gate in a
separately authorized formal campaign. Smoke, C1/C2 integrity, or finite output
cannot vote.

Controller-v2 did not establish campaign runtime readiness. The authorized
performance attempt must be mathematically equivalent; only the separately
preregistered source correction changes the high-bias protocol/IDs. Physics,
tolerances, states, grids, controller semantics, threshold values, and the new
v3 manifest remain fixed.

## Restrictions

Do not run C1/C2/C3 readiness in this task; execute a formal item; create a real
formal registry; train a PINN; generate Phase 2 data; run inverse; fit or
digitize sources; rerun S1/v6-v8; modify frozen GT; add nonzero coupling; or
run FEM/3D, M44, or NbO2. Phase 1/Qiu/experimental, R1/R2, OQ, sensitivity,
and cross-material success claims remain `forbidden`.

## Immediate Next Checkpoint

Stop the source-corrected S2 positive route under the locked performance
budget. Preserve invalid-launch, harness, and valid-audit evidence; do not
retry, re-optimize, or run readiness. Await explicit activation of the retained
`gamma_sub` plus identifiability-boundary manuscript route. Phase 1 science
remains `forbidden` and unassessed.
