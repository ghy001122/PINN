# Phase 1-v2 equivalence-v2 one-shot audit

## Current disposition

`PREPARED_PENDING_REMOTE_ANCHOR_NOT_EXECUTED`

This version records only the authorized execution identity. It is not an
equivalence result: no candidate or oracle numerical row has executed under
equivalence-v2, and the result sections below therefore report the actual
pre-execution state rather than inferred outcomes.

## Task contract

- Task: `Q2_PHASE1_V2_EQUIVALENCE_V2_ONE_SHOT_AUDIT`.
- Base: comparator-closure-v3 merge
  `85d5c7ba5b0da8c3919e2ccc5a844ded4dcbec68`.
- Scope: one frozen, single-process, single-thread, non-retryable pass over the
  original ordered plan indices `0..56`.
- Metric-development partition: indices `0..11`, 12 rows.
- Held-out partition: indices `12..56`, 45 rows.
- Attempt limit: one. Automatic and manual retry are both disabled.
- Counter rule: atomically change `equivalence_v2_execution_count` from zero to
  one immediately before plan index zero is scheduled.
- Formal boundary: `formal_execution_count=0`; no formal case or Phase 2/PINN
  work is authorized.

The execution config is
`configs/geophase_phase1_v2_equivalence_v2_one_shot_execution.yaml`. The
machine authorization and mutable one-shot registry are
`outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_v2_audit/execution_authorization.json`
and
`outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_v2_audit/execution_registry.json`.

## Frozen evidence and comparison boundary

- Strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, `12/57`.
- The frozen candidate, oracle, S2 physics, controller-v2, nonlinear methods,
  15.8 V protocol, scientific inventory, and v1 evidence are unchanged.
- A-class primary physical quantities retain the `1e-12` gate.
- B-class topology and state-machine fields require canonical exact equality.
- C-class flux and cancellation fields use only comparator-closure-v3's frozen
  analytical and hard-gate rules.
- The 638-field manifest and 57-row plan manifest must load with their frozen
  SHA-256 identities before execution.
- The one-shot control plane may consume the frozen v3 comparator entrypoints;
  it may not invoke the v1 audit runner or v1 observation comparator.

## Pre-execution evidence state

| Item | Current value |
|---|---:|
| equivalence-v2 execution count | 0 |
| completed v2 rows | 0 |
| result artifacts | 0 |
| formal execution count | 0 |
| formal artifacts | 0 |
| terminal state | not formed before the one-shot attempt |
| first failed row/field/category | not assessed |

No equivalence-v2 claim, Phase 1/S2 scientific claim, runtime-readiness claim,
or PINN claim is supported by this prospective execution identity.

## Allowed terminal interpretation after the one-shot attempt

- `PASS`: only 57 explicit ordered row passes support the narrow statement that
  the optimized candidate is implementation-equivalent to the frozen oracle
  under the versioned equivalence-v2 contract.
- `VALID_FAIL`: the first valid A/B/C or record-validity failure stops the
  attempt; unvisited rows remain unassessed and the route becomes
  `STOP_S2_ACTIVATE_GAMMA_SUB` without starting that alternative.
- `INVALID_INFRA`: authority, environment, I/O, serialization, journal, or
  execution-integrity failure produces no equivalence or scientific vote and
  cannot be retried automatically.

## Validation and publication status

The solver-free control plane, production adapter, and CLI source hashes are
bound in the config and machine authorization, and the prospective focused
set passes locally. The remote anchor commit and clean-checkout CI are not yet
complete in this pre-anchor version. Execution is fail-closed until those
remaining identities replace the explicit zero-commit sentinel. The report
will be updated with the single attempt's actual terminal evidence, but
historical v1 and closure-v3 records will remain unchanged.
