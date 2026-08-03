# Exact-Condensed B2 Terminal Report

## Disposition

```text
B2_REDUCED_ROOT_VALID_FAIL
```

- Run ID: `B2-EXACT-CONDENSED-20260803-V1`
- Base: `main@6e605ec660494d17bd8b192b59e0654b4c1d3b0a`
- B1 implementation anchor: `2d60a973f8d61e58525e1c2b83db78961da226d1`
- B2 execution identity: `57e3e29643daab9d9af76e7f946b46fc0e602269`
- Config SHA-256: `00e208adec7c770db58b9e7bedc1c69895d48e67665c1115d6c165d21106bada`
- Evidence type: `literature-guided synthetic numerical digital-twin evidence`

## What Ran

B1 added an independent exact-condensed temperature root and an independent
controller-v2 orchestration path. It did not modify the frozen production
implicit solver, NLS-v1, controller-v2, Stage A assets, historical evidence, or
Frozen GT. Focused software/parity checks passed before execution.

B2 was preregistered as a 24/24 fail-fast root qualification. It executed only
the first ordered case:

| Field | Value |
| --- | --- |
| Case | `B2-ORIGINAL-S1-DT10p0NS` |
| Source | first frozen controller-v3 failure replay previous state |
| Drive/grid/step | 9 V / L1 / 10 ns |
| Root wall time | `0.9530737000750378 s` |
| Newton corrections accepted | 5 |
| LGMRES calls/info | 6 / all `0` |
| Krylov matvecs | 100 |
| Reduced-residual evaluations | 135 |
| Recorded backtracks | 23 |

The next Newton correction exhausted the fixed damping ladder `1...1/128`
without satisfying Armijo, producing `ARMIJO_LINE_SEARCH_FAILURE`.

## Gate Evidence

| Quantity | Last available value | Gate / interpretation |
| --- | ---: | --- |
| Reduced residual infinity norm | `9.519603587211078e-3` | did not reach `1e-8` |
| Full scaled residual infinity norm | `9.519603587211078e-3` | did not reach `1e-8` |
| Auxiliary scaled residual infinity norm | `1.4392805451179502e-16` | within `1e-12` |
| Full fixed-point defect | not certified | no accepted final root |
| Raw thermal residual | `4.388114704544496e-6 W/cell` | diagnostic only |

Residual history was
`[1.559176e-2, 1.199795e-2, 8.144418e-3, 9.612938e-3,
9.540546e-3, 9.519604e-3]`. The auxiliary identity remained accurate; the
frozen Newton/LGMRES globalization did not produce a certified root.

Per the contract, B2 stopped immediately. Executed roots: 1; passed roots: 0;
unassessed roots: 23. No second solver/globalization strategy was attempted.

## Scientific Boundary

This is a valid `failed_but_informative` numerical-method result for the named
exact-condensed solver identity. `scientific_vote=false` and
`formal_execution_count=0`.

It does not establish S2 physical failure, Phase 1 PASS/FAIL, runtime or
campaign infeasibility, PINN/C01/C06 failure, Qiu quantitative reproduction, or
experimental validation. B3/B4, fresh S0, Phase 2, all training/baselines/OOD,
and manuscript-result execution were not started.

## Evidence Files

- `outputs/tables/geophase_exact_condensed/b2/B2-EXACT-CONDENSED-20260803-V1/b2_summary.json`
- `outputs/tables/geophase_exact_condensed/b2/B2-EXACT-CONDENSED-20260803-V1/b2_summary.partial.json`
- `outputs/tables/geophase_exact_condensed/b2/B2-EXACT-CONDENSED-20260803-V1/b2_root_results.csv`
- `outputs/tables/geophase_exact_condensed/b2/B2-EXACT-CONDENSED-20260803-V1/cases/B2-ORIGINAL-S1-DT10p0NS.json`

No further experiment is authorized under this consumed goal.
