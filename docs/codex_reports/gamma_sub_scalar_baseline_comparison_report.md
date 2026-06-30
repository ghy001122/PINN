# Gamma_Sub Scalar Baseline Comparison Report

All results are synthetic numerical digital-twin benchmark evidence, not experimental data and not full hidden-field recovery.

This comparison shows that the manuscript contribution should not be framed as a complex optimizer. The core contribution is identifiability-guided target reduction plus prior-boundary auditing.

| target case | method | gamma_true | gamma_est | relative error |
| --- | --- | ---: | ---: | ---: |
| `nominal_frozen` | `candidate_grid_scalar_search` | 450000000.0 | 450000000.0 | 0.0 |
| `nominal_frozen` | `continuous_scalar_least_squares_refinement` | 450000000.0 | 449679908.8362173 | 0.000711313697294924 |
| `nominal_frozen` | `existing_constrained_gamma_sub_workflow` | 450000000.0 | 450000000.0 | 0.0 |
| `offgrid_4p62e8` | `candidate_grid_scalar_search` | 462000000.0 | 450000000.0 | 0.025974025974025976 |
| `offgrid_4p62e8` | `continuous_scalar_least_squares_refinement` | 462000000.0 | 462004341.2446258 | 9.396633389192226e-06 |
| `offgrid_4p62e8` | `existing_constrained_gamma_sub_workflow` | 462000000.0 | 450000000.0 | 0.025974025974025976 |

Frozen inputs unchanged: `True`.

Interpretation: simple scalar search and scalar refinement are adequate for the reduced problem when priors are fixed. The paper's value is the evidence chain that motivates reducing the inverse target and exposes the prior/confounder boundary, not optimizer novelty.
## Validation

Commands run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_tsw_prior_width_sweep.py tests/test_gamma_sub_temperature_anchor_placement.py tests/test_gamma_sub_scalar_baselines.py tests/test_gamma_sub_observability_augmented.py tests/test_gamma_sub_constrained.py tests/test_gamma_sub_continuous_refinement.py
.\.venv\Scripts\python.exe -m pytest
```

Results:

- Targeted tests: `10 passed in 19.93s`.
- Full test suite: `62 passed, 274 warnings in 230.02s`.
- Warnings are existing third-party matplotlib/pyparsing deprecation warnings from the gamma_sub plotting smoke path.
