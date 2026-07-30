# Phase 1-v2 equivalence-v2 one-shot audit

## Current disposition

`VALID_FAIL / STOP_S2_ACTIVATE_GAMMA_SUB`

The single authorized attempt executed once and stopped at the first valid
record-validation failure. Rows `0..8` passed; row `9`,
`EQ-INTERVAL-L1-equilibrium-base`, failed before A/B/C voting because 91 ledger
fields did not carry the canonical manifest-defined `scale_group`. Rows
`10..56` remain unassessed. No retry or rule change is allowed.

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

## Executed evidence state

| Item | Current value |
|---|---:|
| equivalence-v2 execution count | 1 |
| completed v2 rows | 10/57 |
| passed v2 rows | 9 |
| formal execution count | 0 |
| formal artifacts | 0 |
| terminal state | `VALID_FAIL` |
| terminal event | `RECORD_VALIDATION_FAILURE` |
| first failed row | `9 / EQ-INTERVAL-L1-equilibrium-base` |
| first failed field/category | 91 canonical ledger `scale_group` validation issues; record-validity stage before A/B/C votes |
| unassessed rows | `10..56` (47 rows) |

Candidate and oracle record SHA-256 were identical on the failed row
(`6b14db5d...`), but the shared record did not satisfy the frozen manifest's
canonical ledger grouping. Therefore this result does not prove S2 physics
unequal; it does prove that the frozen one-shot contract did not yield a valid
implementation-equivalence pass. Equivalence-v2, Phase 1/S2 science,
runtime-readiness, and PINN claims remain `forbidden`/unassessed.

## Terminal interpretation

The actual terminal state is `VALID_FAIL`. The journal contains 22 chained
records and terminates at SHA-256 `13d010ff...`; its file SHA-256 is
`9dd51259...`. The immutable registry records
`equivalence_v2_execution_count=1`, `completed_rows=10`, and
`formal_execution_count=0`. The required route is
`STOP_S2_ACTIVATE_GAMMA_SUB`; the retained fixed-rank-1 `gamma_sub` plus
calibration gate and identifiability-boundary route is only a recommendation
and was not started.

## Validation and publication status

The immutable pre-execution runner anchor is
`85c3709337430dddb93f69f13e4214532513f5f3`; current-head pre-execution CI run
`30564151079` succeeded before the attempt. Closeout validation is:

- one-shot identity/result and journal-chain tests: `8 passed`;
- project governance: `pass_with_manual_review`, zero failed checks;
- Frozen GT: `8/8` hashes unchanged;
- tracked JSON: `251/251` valid;
- staged diff format: passed.

The branch is `codex/phase1-v2-equivalence-v2-one-shot-audit`; the final result
commit and clean-checkout CI are reported in draft PR #14. Evidence is
literature-guided synthetic numerical digital-twin implementation-audit
evidence, not measurement or experimental validation. Strict-v1 remains
`NO_GO`, `12/57`; no historical v1 or closure-v3 record was modified. Phase 1,
S2 scientific success/failure, runtime feasibility and PINN claims remain
forbidden.
