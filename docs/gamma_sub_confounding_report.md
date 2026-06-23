# gamma_sub robustness and confounding audit

## Scope

This audit tests whether `gamma_sub` remains a reliable reduced inverse
parameter when plausible model-mismatch sources are introduced. It does not
modify Ground Truth v1.1 frozen data, configs, equations, acceptance metrics, or
existing v0/v1/v1.1 and gamma_sub audit results.

All results are synthetic numerical digital-twin benchmark results, not
experimental measurements.

## Inputs and outputs

Input:

- `data\processed\gt_v1_acceptance\gt_triangle.npz`

Scripts:

- `scripts\audit_gamma_sub_confounding.py`
- `scripts\invert_gamma_sub_with_mismatch.py`

Lightweight evidence:

- `outputs\tables\gamma_sub_confounding_summary.json`
- `outputs\tables\gamma_sub_sensitivity_ranking.csv`

## Sensitivity ranking

The confounding audit perturbs one parameter at a time around the frozen
Ground Truth v1.1 triangle benchmark. `gamma_sub` is perturbed with all other
parameters fixed; `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are perturbed with
`gamma_sub` fixed.

| rank | parameter | aggregate sensitivity | cosine with gamma_sub |
|---:|---|---:|---:|
| 1 | `T_sw` | 248.28742849880723 | 0.9046382724137423 |
| 2 | `eta_A` | 0.7856742013183865 | -0.43584559677733203 |
| 3 | `gamma_sub` | 0.32884370993900625 | 1.0 |
| 4 | `sigma_on0` | 0.2919421082128766 | -0.9468534328639979 |
| 5 | `tau_m` | 0.21023972551107956 | 0.9419308101833433 |

The closest response-shape confounders for `gamma_sub` are:

- `sigma_on0`, cosine `-0.9468534328639979`;
- `tau_m`, cosine `0.9419308101833433`;
- `T_sw`, cosine `0.9046382724137423`.

`T_sw` is the most sensitive parameter in this local audit. Its sensitivity is
large because a small absolute shift in switching temperature strongly changes
the state transition and therefore the terminal conductance and thermal fields.

## Mismatch inversion

The mismatch audit generates synthetic targets with one parameter mismatch, but
the inverse model still fixes that parameter at its nominal value and optimizes
only `gamma_sub`.

| target case | clean relative gamma bias | max noisy absolute relative gamma error |
|---|---:|---:|
| `nominal` | -5.589729404449463e-07 | 0.009824713728360865 |
| `T_sw_plus_2K` | 1.2222222222222205 | 1.2222222222222205 |
| `tau_m_x1p5` | 0.4154717417582663 | 0.42065381510153455 |
| `sigma_on0_x1p15` | -0.15910675758527623 | 0.18068653765608245 |
| `eta_A_x1p15` | -0.37638404015035737 | 0.37481697935328445 |

The worst clean-bias case is:

- `T_sw_plus_2K`

The tested mismatch reliability flag is:

- `gamma_sub_reliable_under_tested_mismatch = false`

## Answers

Is `gamma_sub` more identifiable than `T_sw`, `tau_m`, or `sigma_on0`?

Not generally. In the fixed-microphysics audit, `gamma_sub` was identifiable as
a single scalar. In the confounding audit, `T_sw` is more sensitive than
`gamma_sub`, while `tau_m` and `sigma_on0` have response shapes that are close
to `gamma_sub` in the audited terminal and thermal metrics.

Which parameters most easily confound `gamma_sub`?

The strongest shape confounders are `sigma_on0`, `tau_m`, and `T_sw`. `eta_A`
does not mimic the thermal response as closely, but it directly scales terminal
current/conductance and still causes a large `gamma_sub` bias when mismatched.

Is `gamma_sub` inversion reliable under model mismatch?

No, not as a broad standalone claim. It is reliable for the nominal reduced
problem, but it is not robust to the tested mismatches. A `T_sw + 2K` target
pushes the `gamma_sub` estimate to the upper bound, and `tau_m`, `sigma_on0`,
and `eta_A` mismatches also create systematic bias.

Under what conditions should the paper claim be limited?

The claim should be limited to a reduced inverse problem with fixed or
independently calibrated microscopic switching, conductivity, and geometric
scale parameters. The result should be described as a synthetic numerical
digital-twin benchmark, not experimental validation.

Can this proceed to a gamma_sub-PINN main method?

Yes, but only as a constrained reduced-inverse branch. The next method should
either keep `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` fixed by prior calibration
or explicitly include a joint-identifiability section. It should not claim that
terminal-only data uniquely identifies `gamma_sub` under arbitrary model
mismatch.
