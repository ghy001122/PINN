# Next Actions

## Authoritative Current Queue

- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint:
  `Q2_PHASE1_V2_LEDGER_SCHEMA_CLOSURE_AND_EQUIVALENCE_V3_INDEPENDENT_AUDIT`.
- Historical consumed checkpoint: `PHASE1_V2_EQUIVALENCE_V2_ONE_SHOT_AUDIT`
  (`VALID_FAIL`, no retry).
- Strict-equivalence-v1: `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`.
- Metric validity: `GO_VERSIONED_EQUIVALENCE_V2_AUDIT`.
- Source-corrected v3 anchor: `0ebe037...`.
- Equivalence-v2 one-shot: `VALID_FAIL`, `10/57`,
  `STOP_S2_ACTIVATE_GAMMA_SUB`; no retry.
- Equivalence-v3 independent audit: `VALID_FAIL`, `12/57`,
  `STOP_S2_IMPLEMENTATION_EQUIVALENCE_FAILED`; no retry.
- The 63 formal evaluations / 60 executions / 3 reuses remain
  `planned_not_executed`; `formal_execution_count=0` and formal artifacts are
  zero.

## Single Next Action

PR #11/12 lock 638 templates, 57 rows and unchanged A/B/C rules; their
solver-free controls are metric evidence, not an equivalence pass.

Closure v3 merged at `85d5c7ba...`. Retain:

- `1e-12` for primary fields;
- preregistered analytic mixed bounds for physical lateral fields;
- exact controller hard-gate and event/reversal/failure topology votes;
- no candidate, oracle, physics, controller, parameter, protocol, inventory,
  or scientific-gate change.

The v2 runner `85c3709...` stopped at plan 9 after 10 rows: rows 0..8 passed;
row 9 had `RECORD_VALIDATION_FAILURE` on 91 ledger `scale_group` fields; rows
10..56 are unassessed. Do not retry or change rules.

PR #14 merged v2 evidence at `f49ac79...`; closure-v4 merged at `3110b85...`.
Independent v3 (`01850a8...`) consumed its sole attempt: plans 0..10 passed;
plan 11 failed record cardinality validation before A/B/C voting; rows 12..56
are unassessed. V3 count is one and formal count is zero.

No computation is authorized. Preserve the result and stop S2 implementation-
equivalence work. A future assessment of the retained fixed-rank-1 `gamma_sub`
plus calibration-gate and identifiability-boundary downgrade requires explicit
authorization and was not started here.

## Locked Side And Historical Routes

- S1 science remains `forbidden`/unassessed; its timeouts are supported
  infrastructure provenance only and cannot be rerun.
- v6-v8 remains terminal `failed_but_informative`; its 96 items are unexecuted.
- Frozen GT v1.1 and all historical evidence identities remain immutable.

## Scope Boundary

Do not rerun equivalence-v2; its sole authorized attempt is consumed.
Do not run C1/C2/C3, a formal campaign, PINN training, Phase 2 generation,
inverse work, source fitting/digitization, S1/v6-v8, M44, NbO2, FEM/3D, or
nonzero dual-device coupling.
