# Phase 1-v2 equivalence-v2 comparator closure v3

## Conclusion and scope

This versioned, solver-free closure supersedes only the executable comparator
boundary introduced by PR #12. It does not rewrite that package or the frozen
strict-equivalence-v1 result:

- strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, `12/57`;
- the PR #12 YAML, report, preregistration, comparator and manifests retain
  their original paths and hashes;
- no v1 or v2 numerical row is executed by this closure;
- `equivalence_v2_execution_count=0` and `formal_execution_count=0`;
- optimized-candidate equivalence and Phase 1/S2 science remain `forbidden`
  and unassessed.

The manuscript destination is limited reviewer defense: it makes the future
implementation-equivalence contract fail closed on record completeness,
topology shape, row identity and exact plan completion. It is not scientific
or experimental evidence.

## Preserved predecessor identities

The machine contract
`configs/geophase_phase1_v2_equivalence_v2_comparator_closure_v3.yaml`
content-addresses every immutable predecessor. In particular, PR #12 remains
anchored by:

- closure YAML:
  `b04b8695f3829a43808c0b04ab2b36f9cac19b410cd32e88b56271a0aa5de48d`;
- closure report:
  `778d4d58829900fd31850ad9dcce70394ba91d0bf91160c7d21000419b0ae868`;
- closure preregistration:
  `a1846b84549d298fb8d0fe322e77e64ae9a7b6ea507fa8ac09d712642b9752bd`;
- PR #12 comparator:
  `40418f346ca990d996bf4987b0494e6f1d3f5bc9590cd0c615cd9a327994a30c`;
- 638-template manifest:
  `670dbb5acee9bc0bc4796e9c54d9de39c5a4016cc7344f1eff5f53291fb74f07`;
- 57-row plan manifest:
  `cc65de070be1efd9951d609a96e4e1311bbcbf178f9ff478d0a0a2cd3d149c0e`.

The v3 comparison engine path is
`src/pinnpcm/audit/geophase_phase1_v2_equivalence_v2_comparator_v3.py`; its
current content SHA-256 is
`e902e6f06b9213e1ce4278b003de588358fe03fe193391fafebc26aeda095851`.
The final closeout must recheck this value after the source and focused tests
are frozen rather than assuming this draft identity remains current.

## Closed false-PASS channels

### Dynamic index completeness

Every required history, streaming-scalar and streaming-snapshot template must
cover its exact canonical index domain. The scalar and snapshot domains are
zero-based, contiguous and established by their registered `time_s` anchor;
the history domain is the frozen four-interval domain. Candidate and oracle
cannot jointly omit the same required field at one index and pass merely
because another template establishes that index.

### Grid topology and cardinality

Every numerical field is bound to the frozen plan row's L1/L2/L4 topology.
The closure distinguishes cells, x faces, y faces, boundary faces and scalars:

| Grid | Cell | x face | y face | boundary face |
| --- | --- | --- | --- | --- |
| L1 | 25 x 10 | 25 x 9 | 24 x 10 | 70 |
| L2 | 50 x 20 | 50 x 19 | 49 x 20 | 140 |
| L4 | 100 x 40 | 100 x 39 | 99 x 40 | 280 |

Identical but wrong shapes on both sides are a record-validation failure, not
evidence of equivalence.

### Row and failure identity

The record converter derives `plan_index`, `sample_id`, `family`, `grid_id`
and `input_sha256` from the frozen plan. A caller cannot legalize an observation
by relabelling those fields. Failure rows additionally bind failure type and
location and retain the parsed error class and message. A missing failure,
unexpected failure, wrong location/type, or success/failure inversion fails
record validation.

### Exact terminal reduction

`PASS` consumes 57 explicit, content-addressed comparison outcomes. Their row
identities must be exactly the ordered indices `0..56`; every outcome must have
a valid comparison hash and `row_pass=true`. Missing, duplicated, reordered,
substituted or out-of-range outcomes cannot produce `PASS`.

## Unchanged A/B/C voting

The v3 engine adds integrity gates before the PR #12 record comparator and an
exact plan reducer after it. It delegates the mathematical votes to the frozen
PR #12 engine:

- A-class primary quantities retain the normalized `1e-12` gate;
- B-class topology remains canonical exact equality;
- physical x/y face flux and net-cell outflow remain voting under the same
  analytic mixed bounds;
- cancellation uses the same backward-error bound;
- candidate and oracle must each pass the unchanged lateral hard gate and the
  hard-gate dispositions must agree.

No threshold, formula, classification, solver, controller or v1 module is
changed.

## Solver-free sealed controls

The focused fixture matrix must reject common-mode dynamic omissions; wrong
L1/L2/L4 cell/x-face/y-face shapes; altered input, sample, family and failure
identity; success/failure inversions; and every missing, duplicate, reordered,
substituted or out-of-range terminal plan. A legal terminal `PASS` fixture must
contain exactly 57 explicit passing outcomes in the frozen order.

These fixtures are synthetic contract evidence only. They execute no candidate,
oracle, controller, C1/C2/C3, runtime or formal path and never count as an
equivalence audit row.

## Result tracking and current disposition

The future `equivalence_v2_audit` namespace is unignored only for
`preregistration.json`, `execution_authorization.json`,
`execution_registry.json`, `audit_journal.jsonl`, the four
`*_equivalence_v2.csv` tables, and `equivalence_v2_summary.json`. The audit
report is separately fixed at
`docs/codex_reports/geophase_phase1_v2_equivalence_v2_one_shot_audit.md`.
No broad output-tree exception is permitted.

The focused compatibility and sealed-control set passed `152/152`. The closure
is therefore ready subject to clean-checkout CI and merge without authority or
hash drift. Once those external gates pass, it supports only
`READY_FOR_ONE_EQUIVALENCE_V2_AUDIT`. The separately authorized one-shot must
still create its own frozen execution identity before scheduling row 0. This
closure itself creates no scheduler and casts no equivalence or scientific
vote.
