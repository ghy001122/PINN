# Gamma_Sub T_sw Prior-Width Sweep Report

All results are synthetic numerical digital-twin benchmark evidence, not experimental data and not full hidden-field recovery.

This audit estimates only `gamma_sub` while the synthetic target has controlled `T_sw` mismatch. It quantifies how gamma error changes as the allowed switching-temperature uncertainty narrows.

## Key Results

- Widest prior width: `1.0` with relative error `1.2222222222222223`.
- Narrowest prior width: `0.02` with relative error `0.05555555555555555`.
- Error reduction from widest to narrowest: `1.1666666666666667`.
- Trend nonincreasing as prior narrows: `True`.
- Frozen inputs unchanged: `True`.

## Cases

| T_sw prior width | T_sw delta K | gamma_est | relative error | objective | G_loss | I_loss |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 | 2.0 | 1000000000.0 | 1.2222222222222223 | 0.12120439676120218 | 0.08237142046334764 | 0.07766307179632437 |
| 0.5 | 1.0 | 1000000000.0 | 1.2222222222222223 | 0.010789130857114304 | 0.007982404880493302 | 0.005610571153857297 |
| 0.2 | 0.4 | 650000000.0 | 0.4444444444444444 | 0.002147597085479307 | 0.001623644183029587 | 0.0010454609145607143 |
| 0.1 | 0.2 | 550000000.0 | 0.2222222222222222 | 0.0005350220029081567 | 0.00040889512491461467 | 0.0002499776402179519 |
| 0.05 | 0.1 | 500000000.0 | 0.1111111111111111 | 0.00013020556727863207 | 9.961391482986705e-05 | 5.899396150215068e-05 |
| 0.02 | 0.04 | 475000000.0 | 0.05555555555555555 | 2.128418442982263e-05 | 1.2626558307323979e-05 | 1.517098981195838e-05 |

## Interpretation

The sweep supports the manuscript claim boundary: `gamma_sub` recovery is strongly conditioned on the uncertainty in `T_sw`. As the synthetic `T_sw` mismatch shrinks, the terminal-response target becomes less confounded with heat-loss changes, and the recovered `gamma_sub` moves closer to the true value in this candidate-grid audit.
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
