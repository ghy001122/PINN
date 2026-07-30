# Phase 1-v2 Equivalence Metric-Validity Coverage Addendum

## Disposition

`COVERAGE_ADDENDUM_PASS`

The parent route remains `GO_VERSIONED_EQUIVALENCE_V2_AUDIT`, limited to
preparing a separately authorized v2 contract. This addendum does not run or
authorize the 57-row audit. Strict-equivalence-v1 remains
`NO_GO_EQUIVALENT_PERFORMANCE_REPAIR` at `12/57`.

## Task Contract

- Objective: close the real pre-merge coverage gap in draft PR #11 without
  repeating its metric-validity audit.
- Manuscript use: reviewer defense for the field taxonomy and fail-closed
  equivalence gate behind the independent Phase 1 reference judge.
- Inputs: the frozen v1 comparator and performance contract, the streaming
  schema, the source-corrected execution DAG, and the immutable PR #11
  preregistration and result files.
- Outputs: one static 57-row plan map, one 209-template field/formula catalog,
  27 required synthetic tamper controls plus one positive control, this report,
  and a machine summary.
- Allowed changes: comparator/schema-only code, tests, and this pre-merge
  addendum namespace.
- Prohibited: candidate/oracle/controller/scientific-solver execution; any of
  the remaining 45 v1 rows; regeneration of the first 12 rows, 9 physical
  bounds, 6 cancellation bounds, or 13 parent controls; C1/C2/C3; runtime or
  formal execution; PINN, Phase 2, or scientific-contract changes.
- Success gate: all parent hashes match, every one of the 57 planned rows maps
  to a static output contract, every comparison-field template is classified,
  all seven B-class votes remain exact, and every negative control is rejected.
- Failure route: `STOP_S2_ACTIVATE_GAMMA_SUB` without modifying the rules to
  fit a failed control.

## Identity And Preservation

- Branch: `codex/phase1-v2-equivalence-metric-validity`.
- Addendum base/PR #11 head before changes:
  `c28bfe0debee619c2856633b749c139d484dc671`.
- The final commit is recorded in the PR and handoff because a commit cannot
  contain its own identity.
- Parent preregistration SHA-256:
  `89492b603d51558d58ea51aa19a7c78c3fea8e5d3012bbd8723070ea6b1f2a8a`.
- Parent summary, field table, bound table, and controls retained hashes
  `7d9a022f...`, `e5d926b7...`, `bb219a21...`, and `b91e7068...`.
- The formula module, v1 comparator, streaming schema, performance contract,
  and execution DAG were hash-locked. No parent file was regenerated.
- Candidate/oracle executions: `0`; v1 row executions: `0`; remaining-row
  executions: `0`; `formal_execution_count=0`; formal artifacts: `0`.

## Complete Static Comparison Contract

The frozen 57-row plan was generated without executing a row:

| Family | Rows | Static output contract |
| --- | ---: | --- |
| electrical | 9 | electrical observation and structural guards |
| interval | 18 | three step paths, aggregate ledgers, diagnostics, exact topology, telemetry |
| progression | 9 | up to four accepted intervals, fixed scalar/snapshot schema, event/reversal topology |
| failure | 21 | materialized paths through the declared failure, failure class/location, exact topology |

The catalog contains 209 templates across ten reusable components. Repeated
history, scalar, and snapshot indices are represented parametrically; no
remaining row was executed to discover a field.

### A — Primary Physical Quantities

`T`, `s`, `b`, `V_d`, `phi`, currents, Joule powers, all four ledgers, and
embedded temporal errors retain the unchanged v1 normalized-difference gate:

\[
E_A\le10^{-12}.
\]

No A-class field or threshold was relaxed.

### B — Exact Topology And Disposition

The exact field set remains:

1. `nonlinear_method`;
2. `converged_disposition`;
3. `fallback_disposition`;
4. `accepted_rejected_sequence`;
5. `failure_classification`;
6. `event_count_direction_and_order`;
7. `reversal_count_direction_and_order`.

Both the field set and canonical values must match exactly. Telemetry values
are non-voting, but missing or unregistered telemetry fields remain a schema
failure.

### C — Lateral Flux And Conservation

Physical `x/y` face flux and `net_cell_outflow` remain voting. For
\(\delta T=T_c-T_o\), the unchanged parent formula is

\[
B_x=2g_{x,\max}\|\delta T\|_\infty+
64\epsilon\max(g_{x,\max}T_*,q_{x,*}),
\]

\[
B_y=2g_{y,\max}\|\delta T\|_\infty+
64\epsilon\max(g_{y,\max}T_*,q_{y,*}),
\]

\[
B_L=\|L\|_\infty\|\delta T\|_\infty+
64\epsilon\max(\|L\|_\infty T_*,q_{L,*}).
\]

The same formula, factor `64`, and category rule apply to every grid, state,
path, and direction; only the preregistered operator and case scales vary.
No observed mismatch was used to choose a constant.

Signed cancellation residues remain recorded and vote against

\[
B_{\mathrm{cancel}}=
64\epsilon\,2\left(n_xq_{x,*}+n_yq_{y,*}\right).
\]

For `matrix_face_*`, candidate and oracle must each pass the original hard
gate, and their pass/fail dispositions must match exactly:

\[
E_{\mathrm{relative}}\le10^{-10}
\quad\lor\quad E_{\mathrm{roundoff}}\le1.
\]

## Comparator-Level Negative Controls

All 27 required negative controls were rejected and the one valid baseline was
accepted (`28/28` total). Coverage includes finite temperature perturbation,
internal-face sign flip, terminal-current/Joule/ledger tampering, global
outflow leakage, all seven B-class topology/disposition fields, failure
type/location and success/failure inversion, missing or extra numeric/topology/
telemetry fields, and injected validation errors. These tests import only the
frozen comparator and parent analytic formula; they do not import or execute
the candidate, oracle, controller, readiness path, or formal runner.

## Required Final Answers

1. **Does v1 NO-GO remain valid?** Yes. It remains an immutable
   strict-equivalence-v1 result at `12/57`; this addendum neither reruns nor
   reverses it.
2. **Does v1 prove the physical solutions are unequal?** No. Its first failure
   was under a dimensionally unsuitable self-normalized comparison for a
   near-zero cancellation residue. It rejects the v1 implementation-equivalence
   contract, while optimized physical equivalence remains unassessed.
3. **Is the metric error mathematically general?** Yes, within the stated
   taxonomy. The distinction follows operator error propagation and floating-
   point backward error, uses one formula and fixed factor for the whole field
   class, and is not fitted to the observed mismatch.
4. **Is `GO_VERSIONED_EQUIVALENCE_V2_AUDIT` supported?** Yes, for contract
   preparation only: the parent observed audit passed and this addendum closes
   the complete static-plan and B-class synthetic-control gap. It does not
   establish candidate equivalence or authorize execution.
5. **What advances the research next?** Keep PR #11 draft for user review.
   Only a later explicit authorization may freeze and run one equivalence-v2
   57-row audit. Until then, run nothing further; if that future audit fails an
   A, physical C, or exact B vote, stop S2 and route to the retained
   `gamma_sub` plus identifiability-boundary manuscript.

## Evidence

- Machine summary:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_addendum/coverage_addendum_summary.json`.
- Static field/formula catalog:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_addendum/static_field_contract.csv`.
- 57-row static map:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_addendum/plan_output_contract.csv`.
- Synthetic controls:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/coverage_addendum/synthetic_controls.csv`.

## Validation And Git Boundary

- Focused audit/preregistration/routing/workflow tests: `22 passed` via
  `python -m pytest` on the five named Phase1-v2 metric-validity test files.
- Fast-checkout governance: `pass_with_manual_review`, zero failed checks;
  Frozen GT `8/8` hashes unchanged; the authority-context budget is
  `24500/24576` bytes.
- Tracked JSON: `242/242` valid.
- Current historical evidence manifest: `20/20` checks passed.
- Staged-format check: `git diff --cached --check` passed.
- Evidence type: solver-free comparator/schema synthetic audit evidence, not
  a scientific solver result or measurement.
- Forbidden claims: candidate equivalence, runtime readiness, Phase 1 success
  or failure, Qiu validation, formal authorization, Phase 2, and R1/R2 remain
  `forbidden`/unassessed.
- PR #11 must remain draft. Final commit, push, and clean-checkout CI identities
  are recorded in the handoff; no ready or merge action is authorized.
