# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_invalid_second_e0_runner_defect`

Current checkpoint:
`Q2_PHASE1_E0_SINGLE_IMPLEMENTATION_PHYSICS_VALIDATION`

Immediate checkpoint:
`Q2_PHASE1_E0_STOP_SECOND_IMPLEMENTATION_DEFECT`

## Objective

Establish the independent conservative judge required before Phase 2 or PINN:
the Qiu-inspired VO2 real `x-y` S2 model, hysteresis, RC/terminal coupling, and
ledgers, with discretization independent from future PINN residual code.

The direct-physics preflight was authorized and attempted, but no physical gate
completed. The second runner implementation defect exhausted the registered
one-repair budget.

## Current Authority

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_e0_single_implementation_physics_validation.md`
- `configs/geophase_phase1_e0_single_implementation_physics_validation.yaml`
- `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`
- `configs/geophase_phase1_v2_s2_reference_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml`
- `configs/qiu_vo2_phase1_source_contract_v3.yaml`
- `docs/method_equations.md`
- `NEXT_ACTIONS.md`

Historical equivalence contracts, runners, outputs, and reports are immutable
evidence only; they cannot modify this E0 route or vote for S2 physics.

## Selected Implementation

- Origin commit: `1ae2704f6d84a3733d9de58aa23d992aa0c471a5`.
- Origin tree: `d3833a4a5dd067dab72c84f15fe2f8e726bd9512`.
- Frozen identity: `39044f37...`.
- Role: one implementation awaiting direct physical validation.
- PR #8 equivalence: `forbidden` / unassessed and not required by E0.
- Switching implementation after any E0 numerical result: forbidden.
- Reuse of future PINN residual code: forbidden.
- The activation package's former `86c32f6d...` tree label was a metadata
  defect: that object is the preceding preregistration commit. The correction
  was made before any E0 numerical execution and does not change solver bytes.

## Preserved History

- Strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, 12/57; no retry.
- Equivalence-v2 remains `VALID_FAIL / RECORD_VALIDATION_FAILURE`, 10/57;
  rows 10..56 unassessed; no retry.
- Equivalence-v3 remains `VALID_FAIL`, 12/57; plan 11 failed record-cardinality
  validation before A/B/C voting; rows 12..56 unassessed; no retry.
- Equivalence-v4/v5 is forbidden.
- S1 science remains `forbidden`/unassessed. The v6-v8 material-stack route
  remains historical `failed_but_informative` evidence.

## Current Evidence And Authorization

- PR #16 merged the immutable v3 evidence at `06096e7...`.
- S2/controller-v2 software and bounded smoke/C1/C2 evidence remain supported
  only within their recorded scope.
- The source-corrected 15.8 V contract and 63/60/3 scientific inventory are
  unchanged and remain `planned_not_executed`.
- `formal_execution_count=0`; formal artifacts are zero.
- E0 preflight invocations: 2; valid executions: 0; completed cases: 0.
- Sole runner repair: consumed; remaining repair budget: 0.
- Terminal state: `INVALID_E0_EXECUTION`; scientific vote: false.
- Formal campaign authorization: false.
- Phase 1 science and R1-R3 remain `forbidden`/unassessed.

## Terminal E0 Evidence

- Invocation 1: invalid before dispatch because the worker call was unreachable;
  zero registry cases and no vote.
- After the single permitted repair and current-head CI, invocation 2 reached
  the first foundation record but failed canonical JSON serialization on a
  NumPy `bool_`; zero published cases and no vote.
- Authority, journal, registry, summary, and the first-invalid-attempt record
  are preserved in the E0 output namespace and terminal report.

## Failure Rules

- Schema, runner, environment, config, or implementation-code defects use
  `validity: invalid` and `claim_status: forbidden`; they cast no scientific
  vote. The one bounded repair was consumed; the second defect is terminal for
  this goal.
- A complete readiness failure may be `failed_but_informative` for readiness
  only; Phase 1 science remains unassessed.
- A performance/resource-only failure cannot falsify S2 physics; a target-
  machine or budget change requires fresh user authorization.
- Only a valid formal scientific-gate failure may become a Phase 1
  `failed_but_informative` result.

These rules are prospective and do not reclassify v1/v2/v3.

## Restrictions

Do not rerun or repair E0 in this goal. Do not run C1/C2/C3, the 63-item formal
campaign, Phase 2, PINN, inverse, S1/v6-v8, FEM/3D, M44, NbO2, or nonzero
coupling; do not modify frozen GT; and do not create equivalence-v4/v5.
