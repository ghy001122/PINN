# Phase 1-v2 ledger record-schema closure v4

## Conclusion and task boundary

This is an implemented, solver-free schema-closure contract based on
`main@f49ac79fcf8cb617e15665ab57c84375ae6c5b8c`. It may establish only that
production ledger identity and comparison normalization are mechanically and
unambiguously wired for a separately versioned audit. It executes no
candidate, oracle, controller, runtime, formal, Phase 2, or PINN path.

The manuscript destination is limited reviewer-defense provenance for the
reference-solver implementation-equivalence chain. It is not scientific or
experimental evidence.

## Immutable predecessor results

This closure does not rewrite either earlier audit:

- strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, `12/57`;
- equivalence-v2 remains `VALID_FAIL / RECORD_VALIDATION_FAILURE`, `10/57`;
- equivalence-v2 rows `0..8` passed, plan 9 failed record validation, and rows
  `10..56` remain unassessed;
- its candidate and oracle plan-9 record hashes remain identical, and no A/B/C
  vote was cast on that row;
- `equivalence_v2_execution_count=1`, `equivalence_v3_execution_count=0`, and
  `formal_execution_count=0`.

PR #14 was merged only to place this immutable negative/provenance result in
the default-branch authority chain. The merge does not convert it to a pass or
authorize its retry.

## A1. Single ledger-schema source

The schema module is
`src/pinnpcm/audit/geophase_phase1_v2_ledger_record_schema_v4.py`. Its final
local freeze SHA-256 is
`4f7d9e8715c90fd8e336724bb36cba6c9882cf919b70e0fee314dbb4589aa39d`.

It must mechanically consume pure production ledger constructors and the
production observation extractor without running a candidate, oracle,
controller, or solver. The resulting content-addressed manifest is planned at
`outputs/tables/geophase_phase1_v2_source_corrected_v3/ledger_record_schema_closure_v4/ledger_group_manifest.csv`;
its identity is
`cc0b4fd769567740975f6e7ded6110e826dad484fcda76fa76514ccd476a87f5`.

The manifest columns are `family`, `profile`, `field_pattern`,
`producer_balance_name`, `normalized_scale_group_id`, `required_when`,
`source_constructor`, and `source_extractor`. The ledger-power template count
must be derived by filtering the frozen mechanical field contract. The
expected result is 252 templates, but neither a fixed loop nor that number may
serve as the proof of completeness. Production names such as the concrete S2
ledger names may not be re-entered as a hand-maintained list.

## A2. Production identity versus normalization identity

Every normalized record must carry two different identities:

- `ledger_balance_name` is the actual production balance name and remains in
  canonical JSON and the record hash;
- `scale_group_id` is mechanically derived from the structural ledger slot and
  is used only for the ledger denominator normalization.

Every signed term in one ledger must map to exactly one group. Different
ledgers cannot collide, split, merge, or exchange slots. Candidate and oracle
using the same wrong string is a failure, not common-mode evidence of
equivalence.

The closure proves by mechanical member-set matching and exact max-absolute
group-denominator reconstruction that field membership and every ledger
denominator are identical before and after the schema repair. The A-class `1e-12` gate,
B-class exact comparison, C-class analytic bounds, and lateral hard gates
remain byte-for-byte semantically unchanged. Candidate, oracle, S2, and v1
modules remain immutable.

## A3. Production-real sealed fixtures

The solver-free fixture matrix must traverse the real production extraction
path for L1, L2, and L4; full, first-half, second-half, and aggregate profiles;
and thermal, circuit, combined, and device-power ledgers.

It must accept the genuine production-name baseline and reject all of the
following common-mode or structural defects:

- both records using the old simplified name;
- both records using a forged name;
- swapped ledger slots or one wrongly grouped field;
- one ledger split across groups or several ledgers merged;
- missing, extra, or colliding groups;
- any ledger-power template not consumed exactly once.

Any missed negative control produces `SCHEMA_CLOSURE_FAIL`. The comparator or
schema may not be relaxed to accommodate a fixture result.

## A4. Explicit terminal stages

Terminal classification uses structured stages and categories, never error
message text:

- `INVALID_INFRA`: producer, schema, normalization, serialization, I/O, or
  canonical-record formation fails before auditable bilateral records exist;
- `VALID_FAIL`: the schema is valid and both auditable records exist, but a
  real missing/extra/nonfinite/invalid-NA condition or A/B/C vote fails;
- `PASS`: the complete ordered 57-row plan is valid and every field and vote
  passes.

This Stage-A contract cannot itself produce an equivalence `PASS`, because it
executes zero numerical audit rows.

## A5. Content-addressed record publication

The new schema module atomically publishes a complete
normalized candidate or oracle record as canonical JSON with its SHA-256. The
write path is temporary write, flush/fsync, hash verification, then atomic
rename. A journal may reference only a successfully published record hash.

Stage A tested this ability with synthetic contract records only. It did not
publish unapproved scientific execution results. The machine preregistration
is planned at
`outputs/tables/geophase_phase1_v2_source_corrected_v3/ledger_record_schema_closure_v4/preregistration.json`, with
identity frozen after the config and code identities.

## A6. Validation, Git, and stop rules

The direct v4 sealed-fixture suite passed `41/41`; the combined v4,
predecessor-comparator and workflow-contract focused set passed `103/103`.
The added terminal round-trip controls prove that true record-content errors
remain `VALID_FAIL`, whereas producer/schema/normalization failures remain
`INVALID_INFRA`.
Closeout runs one
focused suite and one governance, tracked-JSON, Frozen-GT, and format pass,
followed by current-head clean-checkout CI. All predecessor hashes must remain
unchanged before the closure PR can merge.

Subject to current-head clean-checkout CI and predecessor-hash revalidation,
the Stage-A conclusion is that the record-schema contract is
mechanically closed for a separately authorized equivalence-v3 audit. It does
not support optimized-candidate equivalence, S2 or Phase 1 success/failure,
runtime feasibility, or any PINN claim.

Stage A stops with `SCHEMA_CLOSURE_FAIL` if mechanical coverage, grouping
invariants, production-real controls, terminal staging, or atomic record
publication cannot close without changing frozen rules. It must not recalculate
metric validity, repeat the 209/638 coverage work, run an audit row, optimize
again, or enter C1/C2/C3, runtime, formal, Phase 2, PINN, FEM/3D, or NbO2.
