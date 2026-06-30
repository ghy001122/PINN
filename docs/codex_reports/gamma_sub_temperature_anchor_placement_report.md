# Gamma_Sub Temperature-Anchor Placement Report

All results are synthetic numerical digital-twin benchmark evidence, not experimental data and not full hidden-field recovery.

This audit tests whether sparse temperature anchors failed because their placement was weak. It compares uniform, random, and high-gradient anchor locations under the same controlled wide `T_sw` mismatch target.

## Key Results

- Port-only baseline relative error: `1.2222222222222223`.
- Best placement mode: `uniform` with relative error `1.2222222222222223`.
- Any placement reduced gamma bias: `False`.
- Frozen inputs unchanged: `True`.

## Cases

| case | placement | seed | gamma_est | relative error | temp anchor loss |
| --- | --- | ---: | ---: | ---: | ---: |
| `port_only` | `none` | None | 1000000000.0 | 1.2222222222222223 | 0.0 |
| `uniform_anchors` | `uniform` | None | 1000000000.0 | 1.2222222222222223 | 0.0028658864924597568 |
| `high_gradient_anchors` | `high_gradient` | None | 1000000000.0 | 1.2222222222222223 | 0.0004057813858711021 |
| `random_anchors_seed_2026` | `random` | 2026 | 1000000000.0 | 1.2222222222222223 | 0.002586977379759817 |
| `random_anchors_seed_2027` | `random` | 2027 | 1000000000.0 | 1.2222222222222223 | 0.003143201719087289 |
| `random_anchors_seed_2028` | `random` | 2028 | 1000000000.0 | 1.2222222222222223 | 0.0029748606361854704 |

## Interpretation

If high-gradient or random anchors still do not reduce `gamma_sub` bias, the earlier temperature-anchor failure is not just a uniform-placement artifact. It indicates that a small number of synthetic temperature points, at the tested loss weight and candidate grid, is insufficient to overcome the dominant `T_sw` mismatch. This supports a stricter manuscript claim: independent `T_sw` calibration is more important than sparse thermal anchors alone in the current benchmark.
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
