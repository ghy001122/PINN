# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_invalid_s0_after_repair_budget_exhausted`

Current checkpoint:
`Q2_S0_STOP_INVALID_EXECUTION_AFTER_REPAIR_BUDGET_EXHAUSTED`

## Objective

Establish an independent conservative judge before Phase 2 or PINN: the
Qiu-inspired VO2 real `x-y` S2 model with hysteresis, RC/terminal coupling,
and complete ledgers, independently discretized from future PINN residuals.

The fresh S0 goal attempted this qualification directly on one frozen
implementation. It did not reuse E0 or equivalence execution paths.

## Frozen Authority

- `configs/geophase_s0_direct_physics_qualification_v2.yaml`
- `configs/geophase_phase1_v2_s2_reference_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml`
- `configs/geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml`
- `configs/qiu_vo2_phase1_source_contract_v3.yaml`
- `outputs/tables/geophase_phase1_v2_source_corrected_v3/formal_evaluation_manifest.csv`
- `outputs/tables/geophase_phase1_v2_source_corrected_v3/runtime_readiness/execution_dag.json`

Selected implementation origin: commit `1ae2704f...`, tree `d3833a4a...`.
Changing implementation, physics, thresholds, protocols, or the 63/60/3 plan
after observing results is forbidden.

## Actual S0 Execution

### Non-voting smoke

- V1: 4/4 passed.
- After the sole runner repair, V2: 4/4 passed.
- These are software/mechanism checks only and cast no scientific vote.

### Formal attempt V1

- Terminal: `INVALID_S0_EXECUTION`.
- Published units: 14/60.
- Root cause: nullable zero-drive LIM axes were passed to `int()`.
- Scientific vote: false; `formal_execution_count=0`.
- One bounded runner repair was consumed and remotely anchored.

### Formal attempt V2

- Terminal: `INVALID_S0_EXECUTION`.
- Published units: 25/60, all content-addressed and locally passing.
- Coverage: 5 FAIL, 9 MMS, 6 LIM, and 5 zero-drive REF units.
- First unpublished unit: `TRJ-P1V2-REF-quiescent_9V-S1T4`.
- Trigger: `controller-v2 forced remainder failed closed`.
- Scientific vote: false; `formal_execution_count=0`.
- Remaining 35 execution units and aggregate 63-item gates are unassessed.

The trigger is a fail-closed numerical execution-integrity boundary. Because
no auditable unit record was formed, it is neither a valid Phase 1 failure nor
a physical-law vote. The repair budget is exhausted, so this goal cannot
modify the runner/controller or retry.

## Claim And Lifecycle State

- S0 runner/control plane: `implemented`.
- S0 attempts: `executed`, validity `invalid`.
- S0/Phase 1 claim status: `forbidden` / unassessed.
- Phase 2, C01, C06, OOD, and manuscript-positive PINN claims: `forbidden`.
- Evidence type: literature-guided synthetic numerical digital-twin evidence.
- `formal_execution_count=0`; no formal campaign result exists.

The 25 partial unit passes may be cited only as bounded unit-level provenance;
they cannot be aggregated into a judge qualification or manuscript result.

## Stop And Next Technical Bottleneck

No further execution is authorized. The next scientifically useful problem is
the nonzero-drive controller forced-remainder boundary, not equivalence or
PINN training. Reopening requires a new versioned goal that explicitly changes
the exhausted repair policy and preregisters how controller convergence
failures become auditable unit outcomes. No existing S0 row may be resumed or
reused as a completed campaign.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains
immutable and non-retryable.
Equivalence-v4/v5 is forbidden (`equivalence-v4/v5`). Do not run Phase 2,
C01/C06, C1/C2/C3,
inverse work, S1, K-state, gamma_sub as the main route, FEM/3D, NbO2, or
nonzero coupling.
