# Phase 1-v2 Equivalence-v3 Independent Audit

Date: 2026-07-31

## Disposition

`VALID_FAIL` / `STOP_S2_IMPLEMENTATION_EQUIVALENCE_FAILED`

The single authorized equivalence-v3 attempt is consumed. It completed 12 of
57 ordered rows: 11 passed and plan index 11 failed record validation. Rows
12..56 are unassessed. No retry, rule change, runtime work, formal execution,
Phase 2 generation, or PINN work is authorized.

## Identity And Scope

- Main/base SHA: `3110b85d0931a36394b302f0df2d11b04a0959a8`.
- Frozen execution-code anchor: `01850a8e13bc671d5a19e612798d295b3af43d31`.
- Authority HEAD immediately before execution: `805279862d0d3771f6ed2ff601bd109682c42112`.
- Immutable result evidence commit: `bb8d5298af78b8c488ed7170445a25aef8df3794`.
- Branch: `codex/phase1-v2-equivalence-v3-independent-audit`; draft PR #16.
- Attempt: `EQV3-INDEPENDENT-ATTEMPT-001`; attempt limit one; automatic and
  manual retry both false.
- Historical strict-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, 12/57.
- Historical v2 remains `VALID_FAIL`, 10/57, execution count one.
- `equivalence_v3_execution_count=1`; `formal_execution_count=0`; formal
  artifact count zero.

Candidate, oracle, S2 equations and parameters, the 15.8 V protocol,
controller-v2, nonlinear solvers, scientific inventory, and A/B/C rules were
not modified. The attempt ran once in a single-process, single-thread
environment after current-head clean-checkout CI succeeded.

## Result

Plans 0..10 passed. Plan 11,
`EQ-INTERVAL-L1-legal_critical-base`, reached valid bilateral record comparison
and returned:

- stage: `record_comparison`;
- category: `validation_error`;
- issue count: 168;
- issue form: manifest-template cardinality mismatch (`observed=1`);
- failed A/B/C field list: empty;
- failed A/B/C category list: empty.

The candidate and oracle normalized-record SHA-256 values at the failing row
are `bbd481cb...` and `4ed67e74...`. Because record validation failed before
field voting, this attempt does not establish optimized-candidate
implementation equivalence and does not cast an S2-physics vote. Under the
frozen contract, the valid record-validation failure nevertheless consumes the
attempt and requires the STOP disposition above.

## Atomic Evidence

- [Summary](../../outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_v3_independent_audit/equivalence_v3_summary.json), SHA-256
  `4c98ae395bb193332359db390c7689d5dface0462442ce853b32203493f6a373`.
- [Journal](../../outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_v3_independent_audit/audit_journal.jsonl), SHA-256
  `67d944e17dec5f177a5ee8c65dfaf1030596e8abaed5d123ea12dbc61c617d55`;
  final record SHA-256 `e8ad3b1cb318f08c1581c0eb47931dbd1551b4ad20fde0af4787f08198f0e374`.
- Atomic family tables: electrical `9`, interval `3`, progression `0`,
  failure `0` rows.
- Content-addressed normalized records: 12 candidate plus 12 oracle records.
- Unassessed plan indices: 12..56 (45 rows).

## Validation

- Current-head GitHub fast validation run `30604219156`: success.
- Pre-execution authority check: local HEAD equaled remote branch HEAD; frozen
  v3 identity validated with 57 rows and execution count zero.
- Result-chain check: 26 journal entries, exact completed order 0..11, one
  terminal entry, all family-table hashes matched the summary, and all 24
  normalized-record filenames matched their content hashes.
- Focused authority-routing tests: `17 passed`.
- Fast-checkout governance: zero failed checks; low-context budget
  `23108/24576` bytes.
- Frozen GT: 8/8 hashes unchanged.
- `git diff --check`: passed. No full-suite test was run.

## Claim Boundary And Next Route

This is implementation-audit evidence, not experimental evidence and not a
Phase 1 scientific result. Implementation equivalence is not supported; S2
physics, Phase 1, Qiu reproduction, R1/R2 and PINN claims remain
`forbidden`/unassessed. The current S2 implementation-equivalence route stops.
Only a separately authorized decision may evaluate the retained fixed-rank-1
`gamma_sub` plus calibration-gate and identifiability-boundary downgrade; this
task did not start that route.
