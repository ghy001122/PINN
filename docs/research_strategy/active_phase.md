# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `phase1v2_controller_v2_preregistered_pending_implementation`

Current checkpoint: `PHASE1_V2_CONTROLLER_V2_PREREGISTERED_PENDING_IMPLEMENTATION`

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
- `configs/geophase_phase1_v2_embedded_time_controller_v2.yaml`
- `configs/geophase_phase1_v2_critical_transition_failure_audit.yaml`
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
- The runtime execution addendum is anchored at `b830d4f3...` with SHA-256
  `9d477b79...`. Its non-formal preflight stopped at `NO_GO_RUNTIME`: the first
  required legal-critical streaming parity trajectory hit the locked
  transition-increment failure at the locked step floor. No accepted-step
  telemetry or campaign cost forecast was atomically available. The dormant
  formal-runner dry-run passed, unit-voltage scaling remains disabled, and no
  performance repair was consumed.
- The preregistered one-replay mechanism audit reproduced the original
  `full_history_control` failure. All six returned candidates passed integrity
  gates; branch memory alone triggered at the floor. Its disposition,
  `GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION`, supports a future request
  only; it is neither a production-floor selection nor a Phase 1/S2 pass.
- The user authorized the single controller revision. Its independent v2
  overlay must be pushed before implementation or computation, leaves the base
  S2 YAML immutable, and makes v1 unavailable as an active runtime selection.
  No controller-v2 readiness evidence exists yet.

## Pass And Stop Rules

A Phase 1-v2 pass requires every configured S2 source/positivity,
manufactured-response, terminal-current, ledger, mesh/time/event, mask/overlap,
limit, trend, and failure-path gate in one separately authorized formal run.
Smoke, conservation alone, or finite output cannot vote. A formal failure is
preserved as `failed_but_informative` and blocks Phase 2/R1-R3.

The historical controller remains stopped. The authorized controller-v2
overlay changes only numerical acceptance semantics and must pass C1, C2, and
C3 without changing physics, scientific gates, initial states, protocols, or
the manifest. No production floor may be inferred from the PR #7 bounds.

## Restrictions

Do not execute a formal item; create a real formal registry; train a PINN;
generate Phase 2 data; run inverse work; fit/digitize sources; rerun S1 or the
retired depth/K-state route; modify frozen GT; add nonzero coupling; or run
FEM/3D, M44, or NbO2. Do not claim Qiu calibration/reproduction, experimental
validation, successful Phase 1/R1/R2, OQ recovery, sensitivity fidelity, or
cross-material transfer; these positive claims remain `forbidden`.

## Immediate Next Checkpoint

Push the controller-v2 preregistration anchor, then implement and run only the
bounded C1--C3 readiness sequence. Do not rerun the audit or create a formal
registry. Phase 1/S2 science remains `forbidden` and unassessed.
