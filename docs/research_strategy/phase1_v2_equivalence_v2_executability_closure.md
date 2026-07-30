# Phase 1-v2 equivalence-v2 contract executability closure

## Status and scope

This document is the superseding, solver-free execution contract correction for
the dormant one-shot equivalence-v2 audit. It does not replace or reinterpret
the original strict-equivalence-v1 result:

- strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, `12/57`;
- the previously observed 12 rows, their hashes, candidate, oracle and v1
  comparator are immutable;
- no remaining v1 row and no v2 row was executed by this closure;
- `equivalence_v2_execution_count=0` and `formal_execution_count=0`;
- this package contains no plan scheduler, scientific runner, runtime preflight
  or formal-runner entry point.

The original v2 preregistration remains at its original path and hash. The new
machine contract is
`configs/geophase_phase1_v2_equivalence_v2_executability_closure.yaml`; its
`supersedes` records name and hash every preserved predecessor.

## Record-only comparison boundary

The frozen comparison engine is
`src/pinnpcm/audit/geophase_phase1_v2_equivalence_v2_comparator.py`. It accepts
only two normalized observation mappings, the frozen contract and the two
frozen manifests. It imports no candidate, oracle, controller, numerical
solver, runtime-readiness code or formal runner. Its exact source SHA-256 is
recorded in the YAML contract and machine preregistration.

The public contract loader starts from the machine preregistration, verifies
the YAML contract bytes against the externally recorded SHA-256, and only then
loads the contract's internal engine and manifest records. A contract that
rewrites its own internal identities therefore cannot bootstrap trust; a
contract-byte mismatch is typed `INVALID_INFRA`.

Every record is bound to exactly one row of the content-addressed 57-row plan.
The plan index, sample ID, family, grid, progression interval count, failure
path and 15.8 V voltage scale cannot be supplied freely by a caller. This
prevents changing an A-class denominator or C-class operator context while both
sides still agree on the altered metadata.

## Direct 638-template contract

The comparison engine directly loads:

`outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_correction/mechanical_field_contract.csv`

with SHA-256
`670dbb5acee9bc0bc4796e9c54d9de39c5a4016cc7344f1eff5f53291fb74f07`.
The 638 rows are the parsed result of the frozen manifest, not a generated
loop count. The stable template identity is
`(family, value_kind, field_pattern)`. Duplicate identities, unknown category
or comparator, unknown cardinality rule, invalid `required_when`, altered row
count or unregistered fields fail closed.

All templates map exactly once to one of these handlers:

| Handler | Frozen templates |
|---|---:|
| A strict primary-physics vote | 544 |
| B exact topology vote | 21 |
| C analytic mixed physical-flux vote | 21 |
| C original lateral hard-gate disposition vote | 22 |
| C analytic cancellation/backward-error vote | 15 |
| non-voting telemetry structural validation | 15 |

`required_when`, the six frozen cardinality rules, canonical expanded indices,
NA, missing/extra, nonfinite and production validation errors are executable
record rules. Empty ordered event/reversal sequences are the only valid
no-event representation. A shared invalid `NA` sentinel is not accepted merely
because candidate and oracle are equal.

## A, B and C decisions

### A: primary physical quantities

Temperature, conductive state, branch memory, device voltage, electrical
potential, terminal current, field/device Joule power, four ledgers and
embedded temporal error retain the original normalized `1e-12` threshold.
Neither the threshold nor denominator identities changed. Ledger denominator
groups are derived canonically from each field path; non-ledger fields must
have no group. Candidate and oracle cannot jointly rename a group to change
the denominator scale.

### B: discrete topology and state machine

Accepted/rejected chronology, event/reversal count-direction-order,
nonlinear/converged/fallback dispositions and failure type/location use
canonical exact equality. Malformed tokens and contextually invalid absence are
record-validation failures before equality voting.

### C: lateral conservation and flux

Physical `x/y face flux` and `net_cell_outflow` remain voting quantities. The
same formula and constants apply to every grid and direction; each row selects
the content-addressed L1/L2/L4 operator context from the frozen plan:

\[
B_x=2g_{x,\max}\|\Delta T\|_\infty
+64\epsilon\max(g_{x,\max}T_{\rm scale},q_{\rm scale}),
\]

\[
B_y=2g_{y,\max}\|\Delta T\|_\infty
+64\epsilon\max(g_{y,\max}T_{\rm scale},q_{\rm scale}),
\]

\[
B_{\rm net}=\|L\|_\infty\|\Delta T\|_\infty
+64\epsilon\max(\|L\|_\infty T_{\rm scale},q_{\rm scale}).
\]

Cancellation and roundoff residues preserve their signed raw values and vote
under

\[
B_{\rm cancel}=64\epsilon\,2
\left(n_xq_{x,\rm scale}+n_yq_{y,\rm scale}\right).
\]

For streaming scalar cancellation, the scale is the maximum of all voting
history x/y flux denominators in the same observation. Candidate and oracle
must each independently pass the unchanged lateral hard gate

\[
r_{\rm relative}\le10^{-10}\quad\lor\quad r_{\rm roundoff}\le1,
\]

and their hard-gate dispositions must match. No observed mismatch magnitude is
used to define any bound.

## Unique terminal state

Terminal classification uses typed failure stages, never error-message text:

- authority, environment, manifest/contract hash, I/O, parsing, canonical
  serialization or execution-integrity failure before a complete bilateral
  record: `INVALID_INFRA`;
- valid contract/manifest followed by missing, extra, nonfinite, invalid NA,
  validation error or A/B/C vote failure: `VALID_FAIL`;
- only exact completion of indices `0..56` with every field and vote passing:
  `PASS`.

A valid fail-fast field failure takes precedence over an incomplete plan;
incomplete execution without such a valid comparison failure is infrastructure
invalid. A synthetic PASS fixture likewise must provide 57 explicit, ordered,
individually passing row outcomes; a single passing comparison plus an index
list cannot represent plan completion. The truth table is exhaustive and
mutually exclusive.

## Data partition

The machine representation is inclusive and unambiguous:

- metric development: `inclusive_start=0`, `inclusive_end=11`, exactly 12;
- held out: `inclusive_start=12`, `inclusive_end=56`, exactly 45.

The sets are disjoint and their union is exactly `0..56`. The first 12 remain
v1 metric-development provenance, not v2 results; the remaining 45 remain
unexecuted held-out audit rows.

## Sealed synthetic contract evidence

Content-addressed, solver-free fixtures start from synthetic raw
attempt/progression/failure records, pass through the frozen production
extractors, become plain records, load the real 638-template manifest, and end
at the new comparator and unique terminal classifier. They cover a valid
baseline and tampering of A, B and C fields, record schema/NA/nonfinite errors,
manifest I/O/hash/schema failures and the full terminal truth table.

Fixture outputs are canonical JSON with stable content hashes. They are
`synthetic_contract_evidence_nonvoting`, have `audit_row_count=0`, live outside
the equivalence-v2 result namespace, and cannot be cited as an audit row or a
scientific result.

## Disposition

Passing this closure supports only:

`READY_FOR_ONE_EQUIVALENCE_V2_AUDIT`

It means the versioned contract can be executed in a future separately
authorized one-shot audit. It does not authorize, schedule or execute any of
the 57 rows and does not support optimized-solver equivalence or Phase 1
science.
