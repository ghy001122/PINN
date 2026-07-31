# Phase 1-v2 independent equivalence-v3 audit contract

## Current disposition

This is a prospective, authorized-but-not-started execution contract based on
`main@3110b85d0931a36394b302f0df2d11b04a0959a8`. It has executed zero v3
audit rows. The runner, adapter, CLI, contract hash, and remote commit must be
frozen in a draft PR and pass current-head clean-checkout CI before plan row 0
may be scheduled.

The manuscript use is limited to implementation-equivalence provenance for
the independent S2 reference judge. Even a future equivalence pass would not
constitute Phase 1, Qiu reproduction, runtime, formal-campaign, or PINN
evidence.

## Immutable history

- Strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, `12/57`.
- Equivalence-v2 remains `VALID_FAIL / RECORD_VALIDATION_FAILURE`, `10/57`;
  its execution count is one, plan 9 cast no A/B/C vote, and rows 10–56 remain
  unassessed.
- Equivalence-v3 is a new task identity. It cannot reuse, stitch, resume, or
  rewrite any v1/v2 row or artifact.
- `formal_execution_count=0` and formal artifacts remain zero.

## Frozen inputs

Closure-v4 merged at `3110b85...`. The new audit directly freezes its
comparator, config, preregistration, 252-row ledger-group manifest, report and
summary. It also freezes the 638-field manifest, ordered 57-row plan, candidate
`1ae2704...` / tree `d3833a4...`, oracle `85e4257...` / tree `50ef221...`, and
the existing single-process/single-thread environment contract.

The A-class `1e-12` rule, B-class exact equality, C-class analytic bounds and
lateral hard-gate dispositions are unchanged. Candidate, oracle, S2 physics,
controller-v2, nonlinear solvers, the 15.8 V protocol and the 63-item formal
inventory are immutable.

## One-shot execution semantics

The only permitted order is plan index 0 through 56, once, in one process and
one thread. Rows 0–11 retain the `metric-development` label and rows 12–56
retain the `held-out` label, but both partitions belong to the same attempt;
no subset pre-run is allowed. Immediately before row 0, the registry must
atomically change `equivalence_v3_execution_count` from 0 to 1. Automatic and
manual retry are false, and the first valid failure is terminal.

Before execution, the draft PR must freeze hashes for:

- `configs/geophase_phase1_v2_equivalence_v3_independent_audit.yaml`;
- `src/pinnpcm/audit/geophase_phase1_v2_equivalence_v3_one_shot.py`;
- `src/pinnpcm/audit/geophase_phase1_v2_equivalence_v3_production_adapter.py`;
- `scripts/run_geophase_phase1_v2_equivalence_v3_independent_audit.py`.

Until those hashes and a successful current-head CI are recorded, the state is
`AUTHORIZED_NOT_STARTED`, not executable.

## Terminal states

- `PASS`: all 57 explicit ordered rows are valid and every A/B/C vote passes.
- `VALID_FAIL`: auditable bilateral records exist, but a genuine
  missing/extra/nonfinite/invalid-NA condition or A/B/C vote fails.
- `INVALID_INFRA`: authority, environment, schema, normalization, I/O,
  serialization, journal, or execution integrity prevents a valid vote.

A future `PASS` may support only implementation equivalence under this frozen
contract and routes to a separate runtime-feasibility decision. `VALID_FAIL`
stops S2 implementation equivalence. `INVALID_INFRA` casts neither an
equivalence nor a scientific vote. No terminal state automatically starts
runtime, formal execution, Phase 2, PINN, or a downgrade experiment.
