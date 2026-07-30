# Phase 1-v2 Metric-Validity Coverage Correction

## Disposition

`COVERAGE_CORRECTION_PASS`

The parent metric-validity route remains
`GO_VERSIONED_EQUIVALENCE_V2_AUDIT`, limited to preparing a separately
authorized v2 contract. Strict-equivalence-v1 remains immutable at
`NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, `12/57`. No candidate, oracle,
controller, audit row, readiness task, or formal item was executed.

## Task Contract

- Objective: verify and close only the two pre-merge coverage gaps in draft
  PR #11.
- Manuscript use: reviewer defense for completeness and fail-closed topology
  semantics behind the independent Phase 1 judge.
- Inputs: the frozen production comparator, streaming source schema, frozen
  57-row plan, source-corrected execution DAG, and immutable parent/addendum
  evidence.
- Outputs: a mechanically derived field contract, a 57-row static map, raw
  production-extractor topology controls, a machine summary, tests, and this
  report.
- Prohibited: regeneration of parent results; execution of the frozen first
  12 or held-out 45 rows; equivalence-v2, C1/C2/C3, runtime, formal, PINN, or
  Phase 2 work.
- Success gate: every authority hash matches, all 57 rows map to a production
  output family, field names come from production extractors/streaming AST,
  all B votes stay exact, and every raw-record negative control is rejected.
- Failure route: `COVERAGE_ADDENDUM_FAIL / STOP_S2_ACTIVATE_GAMMA_SUB` without
  changing rules to accommodate a failure.

## Identity And Preservation

- Branch: `codex/phase1-v2-equivalence-metric-validity`.
- PR #11 HEAD before correction:
  `a26dcb527e34f093fa304d81e9d212392ac5a08a`.
- The correction commit is recorded in PR #11 and the task handoff because a
  commit cannot contain its own final identity.
- Frozen comparator SHA-256:
  `05868658ca199737600d796fbdcd4eb2661d222cc749e95a3530c1ea7078ebdc`.
- Streaming schema SHA-256:
  `80ab0f1729a94074b8cfd850f4e8f8450be28c7d2d6e33382f5a7b5294dc5923`.
- Execution DAG SHA-256:
  `da93d717e0fae2fb5431457b921f901a8651bd987346f4df493a94144ded786a`.
- Parent summary and original coverage files retained every preregistered
  hash. The parent `9/9`, `6/6`, and `13/13` results were not recomputed.
- `formal_execution_count=0`; `equivalence_v2_execution_count=0`; formal
  artifacts `=0`.

## Gap 1: Mechanical Field Universe

The original addendum's 209-template completeness claim was based on a
hand-maintained mirror. That addendum and its hash remain historical evidence,
but the completeness claim is superseded.

The correction obtains names and conditional shapes by:

1. invoking frozen `electrical_observation`, `_attempt_observation`, and
   `_progression_observation` on solver-free synthetic raw records;
2. parsing the frozen streaming source AST for scalar, event, reversal, and
   ledger schema keys without importing its controller execution path;
3. enumerating accepted/rejected, present/missing path, integrity-filtered
   failure, eventful, and no-event scenarios;
4. mapping the frozen `build_equivalence_plan` output and source-corrected DAG
   to the mechanically obtained family contracts.

This produces 638 **family-qualified parameterized templates**:

| Family | Plan rows | Templates |
| --- | ---: | ---: |
| electrical | 9 | 8 |
| interval | 18 | 241 |
| progression | 9 | 209 |
| failure | 21 | 180 |

The total is an output, not a preregistered target. It is not directly
comparable to the 229 materialized numeric fields in the first failing v1 row:
the latter is one observed row, while this contract spans all four families,
conditional paths, normalized repeated indices, exact votes, and telemetry.
Every field records `required_when` and a static cardinality rule; dynamic
record cardinality remains fail-closed through exact candidate/oracle field
sets and progression validation.

A-class primary physical quantities retain the original `1e-12` gate. All
seven B-class fields retain canonical exact equality. Physical `x/y` face
flux and `net_cell_outflow` remain voting under the parent analytic mixed
bound. Cancellation residues retain the parent backward-error bound, while
`matrix_face_*` and streaming lateral hard-gate fields retain exact hard-gate
disposition. No formula, constant, or observed-result-dependent scale changed.

## Gap 2: Raw B-Class Controls

The correction starts from `SimpleNamespace`/dictionary raw attempt,
progression, event, reversal, and failure records. Each record passes through
the frozen production `_attempt_observation` or `_progression_observation`
path before comparison; no test constructs or mutates final `exact_votes`.

One valid baseline and 20 negative controls passed (`21/21`). They cover:

- accepted/rejected sequence;
- event and reversal count, direction, chronology, and order;
- nonlinear method, converged disposition, and fallback disposition;
- failure type, location, and success/failure inversion;
- missing and unregistered topology/numeric/source fields; and
- injected progression validation error.

Every negative control was rejected. Production-extractor validation, field-
set validation, and exact-vote comparison each contributed where appropriate.

## Required Final Answers

1. **Does v1 NO-GO remain valid?** Yes. The valid frozen result remains
   `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR` at `12/57`.
2. **Does v1 prove the physical solutions are unequal?** No. It rejects the
   strict-v1 implementation-equivalence contract; optimized physical
   equivalence remains `forbidden`/unassessed.
3. **Is the metric error mathematically general?** The parent qualified answer
   remains yes within its frozen taxonomy and analytic bounds. This correction
   adds coverage evidence only; it neither recomputes nor changes that proof.
4. **Is `GO_VERSIONED_EQUIVALENCE_V2_AUDIT` satisfied?** Yes for contract
   preparation only. The mechanical-universe and raw-B-control gaps both pass.
5. **What advances research next?** Merge the reviewed evidence, freeze one
   versioned v2 contract on a separate branch, and stop. Running any of its 57
   rows still requires a later explicit authorization.

## Evidence And Claim Boundary

- Summary:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_correction/coverage_correction_summary.json`.
- Mechanical fields:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_correction/mechanical_field_contract.csv`.
- Mechanical plan:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_correction/mechanical_plan_contract.csv`.
- Raw controls:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_correction/raw_topology_controls.csv`.
- Evidence type: solver-free production-extractor/schema coverage evidence,
  not a scientific solver result, measurement, or equivalence pass.
- Still forbidden/unassessed: optimized equivalence, runtime readiness,
  Phase 1 success/failure, Qiu validation, Phase 2, R1, and R2.

## Validation And Git Boundary

- Focused metric-validity, coverage, routing, and workflow tests: `28 passed`.
- The correction CLI check returned `COVERAGE_CORRECTION_PASS` before the four
  immutable correction artifacts were published once.
- Final governance, tracked-JSON, Frozen-GT, and staged-format results are
  recorded in the task handoff after the final staged tree is known.
- PR #11 may merge only after its correction commit has clean-checkout CI,
  unchanged authority hashes, and an unchanged remote HEAD.
