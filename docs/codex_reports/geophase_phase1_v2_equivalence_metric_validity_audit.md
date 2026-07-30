# Phase 1-v2 Equivalence Metric Validity Audit

## Disposition

`GO_VERSIONED_EQUIVALENCE_V2_AUDIT`

This is a solver-free metric-validity result. It authorizes only a separately
versioned frozen-candidate 57-row equivalence-v2 audit after fresh user
authorization. It does not reverse strict-equivalence-v1, establish optimized
solver equivalence, authorize runtime readiness, or support a Phase 1 result.

## Task Contract

- Objective: determine whether the strict-equivalence-v1 failure was caused by
  a general metric-category error while retaining physical lateral fluxes as
  voting quantities.
- Manuscript use: reviewer defense for the independent reference-judge
  equivalence gate in Contribution 1.
- Frozen inputs: PR #10 strict-v1 JSON/CSV, candidate/oracle identities,
  source-corrected S2 config, comparator source, FVM lateral audit, and
  controller hard gate.
- Allowed outputs: three non-formal CSV tables, one JSON summary, tests, this
  report, and targeted authority/claim routing.
- Prohibited: candidate/oracle execution, any 57-row rerun, threshold
  relaxation, physical-field demotion, solver modification, C1/C2/C3,
  formal execution, PINN, Phase 2, inverse, or frozen-GT changes.
- Success gate: all frozen hashes match; the v1 failure decomposes into valid
  metric categories; physical lateral quantities pass analytic mixed bounds;
  and every synthetic tamper control behaves fail-closed.
- Failure route: `STOP_S2_ACTIVATE_GAMMA_SUB`.

## Identity And Preservation

- PR #10 merge/base: `f40cce457269787f579430ec30d59c46fea08765`.
- Preregistration commit:
  `460cbefbe692c4e7fab22e951ea3de71318601ae`.
- Preregistration YAML SHA-256:
  `89492b603d51558d58ea51aa19a7c78c3fea8e5d3012bbd8723070ea6b1f2a8a`.
- Result implementation/evidence commit:
  `5301ce0cf8929f73b43de961064cfd4ed77c6ccf`.
- Strict-equivalence-v1 remains
  `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, with `12/57` completed and fail-fast
  at plan 11. Its atomic artifacts and hashes are unchanged.
- Frozen candidate commit/tree remain `1ae2704...` / `d3833a4...`; the PR #8
  oracle remains unchanged.
- `formal_execution_count=0`; formal artifact count is zero.

## Metric Categories

The v1 comparator used one self-normalized relative formula for quantities with
different numerical meanings. The versioned validity audit kept every field
voting but assigned the following semantics.

1. Primary physical/state/port/ledger fields and prescribed no-flux boundary
   fields retain the unchanged v1 threshold `1e-12`.
2. Physical `x_face_flux_W`, `y_face_flux_W`, and
   `net_cell_outflow_W` use analytic propagation bounds and remain voting.
3. `matrix_face_relative_mismatch` and `matrix_face_roundoff_ratio` vote via
   the original controller predicate:

   \[
   E_{\mathrm{relative}}\le10^{-10}
   \quad\lor\quad
   E_{\mathrm{roundoff}}\le1.
   \]

4. Pair-cancellation and global zero-residual diagnostics use an analytic
   floating-point roundoff bound; their raw signed values remain recorded.

For a shared static face conductance and
\(\delta T=T_{\mathrm{candidate}}-T_{\mathrm{oracle}}\), the physical bounds
are

\[
|\delta q_x|\le2g_{x,\max}\|\delta T\|_\infty+B_{x,\mathrm{fp}},
\]

\[
|\delta q_y|\le2g_{y,\max}\|\delta T\|_\infty+B_{y,\mathrm{fp}},
\]

\[
\|\delta(LT)\|_\infty
\le\|L\|_\infty\|\delta T\|_\infty+B_{L,\mathrm{fp}},
\]

where every floating-point term uses the preregistered factor
\(64\epsilon_{\mathrm{mach}}\); no empirical multiplier was fitted.

## Results

| Audit item | Result |
| --- | --- |
| Frozen hashes | all matched |
| Failing-row numeric fields | 229 |
| Non-lateral fields | 202; `0` v1 failures |
| Lateral fields | 27; `21` v1 failures and `6` v1 passes |
| Physical lateral bound checks | `9/9` pass; all remain voting |
| Cancellation/roundoff checks | `6/6` pass |
| Original three-path hard-gate dispositions | `3/3` pass |
| Synthetic tamper controls | `13/13` pass |
| Solver/equivalence-row executions | `0/0` |

The largest physical-bound ratio was
`0.12964720443313635`, for
`second_half_step.lateral.y_face_flux_W`: the observed difference was
`5.33529487256601e-18 W` versus an analytic bound of
`4.115240969439962e-17 W`. The largest cancellation-bound ratio was
`0.00016535158450852334`.

The negative controls rejected a primary-field error above `1e-12`, each
physical lateral flux above its analytic bound, physical-field demotion,
candidate/oracle hard-gate failure or mismatch, an above-bound cancellation
residue, and a missing required field. A within-bound physical flux and a
within-bound cancellation residue passed.

## Interpretation And Claim Boundary

The valid result is:

> A solver-free audit found a general category mismatch in the v1 equivalence
> metric and justified a separately versioned audit protocol; optimized-solver
> equivalence remains unassessed.

The metric-validity claim is `qualified_supported`. Strict-equivalence-v1
remains `failed_but_informative`; the optimized candidate, runtime feasibility,
S2 science, Phase 1, R1, and R2 remain `forbidden`/unassessed. It remains
forbidden to claim that all lateral fields are telemetry or that the optimized
solver is equivalent.

## Evidence And Validation

- Machine summary:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/metric_validity_summary.json`.
- Field table:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/field_classification.csv`.
- Analytic-bound table:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/observed_bound_audit.csv`.
- Negative controls:
  `outputs/tables/geophase_phase1_v2_source_corrected_v3/equivalence_metric_validity/negative_controls.csv`.
- Focused contract/audit/routing/workflow/claim tests: `18 passed`.
- Fast-checkout governance: `pass_with_manual_review`, zero failed checks;
  frozen GT hashes `8/8` unchanged.
- Tracked JSON: `241/241` valid.
- No numerical solver, strict-equivalence row, runtime preflight, formal case,
  PINN, inverse, or data-generation path ran.

## Single Next Decision

Await fresh user authorization for one separately versioned, frozen-candidate
equivalence-v2 audit over the original 57-row plan. Without that authorization,
or if any primary/physical/topology vote fails in that future audit, stop S2 and
activate the retained `gamma_sub` plus identifiability-boundary route.
