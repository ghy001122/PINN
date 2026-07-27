# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `phase1v2_s2_smoke_pass_pending_formal_readiness`

Current checkpoint: `PHASE1_V2_S2_SMOKE_PASS_PENDING_FORMAL_READINESS`

## Objective

Establish the independent conservative judge required before Phase 2 or any
positive PINN claim: a Qiu-inspired single-device VO2 x-y model with explicit
VO2 and mask-local Ti/Au thermal terms, the locally distributed S2 nominal
closure, white-box hysteresis, terminal integration, RC coupling, and complete
energy ledgers. It is discretely independent from future PINN residual code.

## Current Authority

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`
- `configs/geophase_phase1_v2_s2_reference.yaml`
- `configs/geophase_phase1_v2_formal_manifest.yaml`
- `configs/geophase_phase1_v2_execution_addendum.yaml`
- `configs/qiu_vo2_phase1_source_contract.yaml`
- `configs/geo2p5d_stage.yaml`
- `docs/method_equations.md`
- `NEXT_ACTIONS.md`

Bounded auxiliary contracts/evidence are routed through
`configs/qiu_same_device_thermal_holdout_audit.yaml`, the two S1 sensitivity
configs, and their named reports. They cannot modify S2 or the formal manifest.

## Current Evidence And Authorization

- Phase 1-v2 was preregistered before computation at `d37745b...`; the stricter
  S1 amendment is anchored at `bbaf5c3...`.
- S2 implementation and focused behavior tests exist. All seven bounded
  non-voting smoke cases pass after one registered zero-signal audit repair
  that changed no physics or scientific gate.
- The 63 formal evaluation items remain `planned_not_executed` and
  `formal_execution_count=0`. No formal run or registry is authorized.
- The bounded source audit found no eligible same-device direct thermal
  holdout; no curve was digitized or fit.
- S1 is closed at
  `STOP_S1_REFERENCE_EVALUATION_INFRASTRUCTURE_BLOCKED_BEFORE_ATOMIC_EVIDENCE`.
  Three tool timeouts prevented atomic output; two repeated the same binary
  comparator failure. No exact metric, K fit, production selection, or
  scientific vote exists. Further S1 work requires new authorization.
- The historical v6-v8 material-stack route is terminal
  `failed_but_informative`; its 96 formal items were never run. The final v8
  pullback depth-frequency errors stayed near `0.4118 > 0.05`.

## Pass And Stop Rules

A Phase 1-v2 pass requires every configured S2 source/positivity,
manufactured-response, terminal-current, ledger, mesh/time/event, mask/overlap,
limit, trend, and failure-path gate in one separately authorized formal run.
Smoke, conservation alone, or finite output cannot vote. A formal failure is
preserved as `failed_but_informative` and blocks Phase 2/R1-R3.

If a correctly implemented S2 fails physical, conservation, or convergence
gates, stop the positive 2D route and activate the retained
`gamma_sub`/identifiability downgrade. Do not alter gates after observation.

## Restrictions

Do not execute a formal item; create a real formal registry; train a PINN;
generate Phase 2 data; run inverse work; fit/digitize sources; rerun S1 or the
retired depth/K-state route; modify frozen GT; add nonzero coupling; or run
FEM/3D, M44, or NbO2. Do not claim Qiu calibration/reproduction, experimental
validation, successful Phase 1/R1/R2, OQ recovery, sensitivity fidelity, or
cross-material transfer; these positive claims remain `forbidden`.

## Immediate Next Checkpoint

Implement and test only the minimal runtime/formal-runner readiness layer for
the locked 63-item inventory. It must use non-formal IDs and temporary state,
must not create a formal artifact, and must stop for fresh user authorization
even if every readiness check passes.
