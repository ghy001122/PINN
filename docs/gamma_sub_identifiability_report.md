# gamma_sub identifiability audit

## Scope

This audit tests a reduced inverse problem: can the effective thermal
dissipation parameter `gamma_sub` be identified from terminal `V(t)`, `I(t)`,
and `G(t)` when microscopic defect and switching parameters are fixed?

Frozen Ground Truth v1.1 configs, data, equations, acceptance metrics, and
existing v0/v1/v1.1 results were not modified.

All results are synthetic numerical digital-twin benchmark results, not
experimental measurements.

## Inputs and outputs

Input:

- `data\processed\gt_v1_acceptance\gt_triangle.npz`

Scripts:

- `scripts\scan_gamma_sub_identifiability.py`
- `scripts\invert_gamma_sub_v0.py`

Lightweight evidence:

- `outputs\tables\gamma_sub_identifiability_summary.json`

Generated figures:

- `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`

The figures are generated outputs and are not committed.

## Fixed parameters

The reduced inverse audit fixes:

- `D_v0 = 8.0e-16`
- `mu_v0 = 5.0e-16`
- `T_sw = 313.0`
- `tau_m = 4.0e-4`
- all other Ground Truth v1.1 frozen defaults except scanned or optimized
  `gamma_sub`

The target value is:

- `gamma_sub = 4.5e8`

## Scan results

The scan uses:

- `2.5e8`
- `3.25e8`
- `4.0e8`
- `4.5e8`
- `5.5e8`
- `7.0e8`
- `9.0e8`

Selected scan metrics:

| gamma_sub | max_delta_T (K) | rel RMSE G | rel RMSE I | rel RMSE mean_delta_T |
|---:|---:|---:|---:|---:|
| 2.5e8 | 10.541970440391253 | 0.12868825294084366 | 0.1643215458721257 | 0.13088506510907863 |
| 3.25e8 | 9.797577849471963 | 0.07362439052638536 | 0.09275391611520022 | 0.07842789079539493 |
| 4.0e8 | 9.144201316538613 | 0.027151646434961423 | 0.03379330841839163 | 0.030147378943518578 |
| 4.5e8 | 8.750689766759194 | 0.0 | 0.0 | 0.0 |
| 5.5e8 | 8.047700146874945 | 0.046942127536423565 | 0.05721643553407634 | 0.055971479910501075 |
| 7.0e8 | 7.1615363071311435 | 0.10330071175555203 | 0.1237571794465595 | 0.13066188803928325 |
| 9.0e8 | 6.214086172625741 | 0.16018739403134102 | 0.18836827021448252 | 0.21612167873280314 |

Local log sensitivities around the target:

- `G_mean`: `-0.15019058781477293`
- `I_rms`: `-0.23031552388593468`
- `iv_loop_area`: `-0.7438301016792098`
- `max_delta_T`: `-0.4011056409189491`
- `mean_delta_T_peak`: `-0.40110602519849947`

The scan shows a monotonic thermal response and a measurable terminal response
as `gamma_sub` changes.

## Inversion results

The inversion optimizes only `gamma_sub` in log space. It uses:

- coarse manual finite-difference Adam;
- fine `L-BFGS-B`;
- terminal `G/I` loss;
- a candidate heat-equation residual regularizer;
- no hidden target temperature supervision.

Multi-start initial values:

- `2.0e8`
- `4.5e8`
- `9.0e8`

Noise cases:

| noise level | mean estimate | estimate std | mean relative gamma error | multi-start consistent |
|---:|---:|---:|---:|---|
| 0.0 | 449992392.12455654 | 6551.85692204503 | 1.9133461841742195e-05 | true |
| 0.02 | 446203568.803992 | 6403.332831647908 | 0.008436513768906815 | true |
| 0.05 | 445570354.8778825 | 4512.739221560651 | 0.009843655826927688 | true |

The best clean estimate is:

- `450001503.273578`

The clean relative error is:

- `3.3406079510847727e-06`

The maximum noisy mean relative error across the tested noise cases is:

- `0.009843655826927688`

## Answers

Is `gamma_sub` identifiable?

Yes, in this reduced inverse problem. With `D_v0`, `mu_v0`, `T_sw`, `tau_m`,
and other microscopic parameters fixed, terminal `G(t)` and `I(t)` provide a
stable enough signature to recover `gamma_sub` near the frozen target.

Do multiple initial values converge consistently?

Yes. The tested initial values converge to nearly identical estimates in clean,
2 percent noise, and 5 percent noise cases. The relative multi-start standard
deviation remains far below 5 percent of the target value.

Is it robust under noise?

For the tested synthetic noise levels, yes. The mean relative gamma error stays
below 1 percent for 2 percent and 5 percent noise in this audit.

Is it confused with `T_sw` or `tau_m`?

Not in this reduced audit because `T_sw` and `tau_m` are fixed. If `T_sw`,
`tau_m`, and `gamma_sub` are all released together, confounding is still
plausible because switching state and heat dissipation both affect terminal
conductance. A future joint-identifiability scan is needed before claiming
unique multi-parameter recovery.

Is it suitable as a paper reduced-inverse-problem main line?

Yes, as a cautious reduced inverse problem. It is stronger than the current
port-only hidden-field recovery story because it asks for one physically
interpretable scalar parameter instead of unique recovery of all hidden fields.
The paper narrative should state that this is a synthetic numerical
digital-twin benchmark and that microscopic parameters are fixed during
`gamma_sub` inversion.
