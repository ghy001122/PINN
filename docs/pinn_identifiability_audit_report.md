# PINN identifiability audit

## Scope

This audit analyzes whether terminal observations `V(t)`, `I(t)`, and `G(t)`
can uniquely identify hidden fields in the frozen Ground Truth v1.1 triangle
synthetic numerical digital-twin benchmark.

Frozen Ground Truth v1.1 configs, data, main equations, acceptance metrics, and
existing v0/v1/v1.1 results were not modified.

## Inputs and outputs

Input:

- `data\processed\gt_v1_acceptance\gt_triangle.npz`

Script:

- `scripts\analyze_pinn_identifiability.py`

Generated lightweight evidence:

- `outputs\tables\pinn_identifiability_summary.json`
- `outputs\tables\pinn_identifiability_correlation.csv`

Generated figures:

- `outputs\figures\pinn_identifiability\correlation_heatmap.png`
- `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
- `outputs\figures\pinn_identifiability\lag_correlation.png`

## Main correlations

Terminal `G(t)` correlations with field summaries:

| field summary | Pearson r with G(t) |
|---|---:|
| `mean_delta_T` | 0.9549574996859841 |
| `max_delta_T` | 0.9549574289516599 |
| `mean_delta_c_v` | -0.9581640749145087 |
| `max_abs_delta_c_v` | 0.9473551593678594 |
| `mean_m` | 0.9953127170309772 |
| `mean_sigma` | 0.9999966158284996 |

Hidden-field correlations:

| field pair | Pearson r |
|---|---:|
| `delta_T` vs `sigma` | 0.6988542299422462 |
| `c_v` vs `sigma` | 0.3216744579750865 |
| `delta_c_v` vs `sigma` | -0.49255846850127327 |
| `m` vs `sigma` | 0.8241268575488281 |
| `delta_T` vs `m` | 0.8541353336498209 |
| `c_v` vs `m` | 0.44175184060613176 |

Best lag correlations with `G(t)`:

| field summary | lag steps | Pearson r |
|---|---:|---:|
| `mean_delta_T` | 37 | 0.9629198348385506 |
| `mean_delta_c_v` | 40 | -0.9640506641000847 |
| `mean_m` | -5 | 0.9964124490525389 |
| `mean_sigma` | 0 | 0.9999966158284996 |

Peak spatial sensitivity to `G(t)`:

| field | x (m) | Pearson r |
|---|---:|---:|
| `delta_T` | 9.838709677419355e-08 | 0.9549575414821615 |
| `delta_c_v` | 8.870967741935484e-08 | -0.9888456857766619 |
| `m` | 1.6129032258064515e-09 | 0.9958147029486689 |
| `sigma` | 3.7096774193548384e-08 | 0.9999980973748842 |

## Answers

Delta_T identifiability:

`delta_T` is not stably identifiable from terminal observations alone. Its
aggregate time series is highly correlated with `G(t)`, but it is also strongly
correlated with `m` and `sigma`. The terminal port loss primarily sees the
integrated conductance, so multiple hidden-field combinations can explain
similar `G(t)`.

c_v identifiability:

`c_v` is harder to recover as a spatial hidden field than aggregate
`delta_T`. Although `mean_delta_c_v` and `max_abs_delta_c_v` correlate strongly
with `G(t)`, the mean defect variation is small and spatially structured. This
matches the v0/v1/v1.1 port-only behavior where terminal fit can be acceptable
while `delta_c_v` field errors remain large.

Sigma driver:

In this frozen benchmark, `sigma` is more closely aligned with `m` than with
`c_v`. The global `m`-`sigma` correlation is `0.8241268575488281`, while
`c_v`-`sigma` is `0.3216744579750865` and `delta_c_v`-`sigma` is
`-0.49255846850127327`.

Uniqueness of hidden-field recovery:

Current terminal observations are insufficient to uniquely recover
`delta_T`, `c_v`, `m`, and `sigma`. `G(t)` is an integrated response and is
nearly perfectly correlated with `mean_sigma`, but it does not uniquely encode
the spatial decomposition among thermal, defect, state, and conductivity
fields.

Why v1.1 did not improve delta_T:

v1.1 improves some terminal and sigma metrics by balancing residual losses and
limiting sigma drift, but it does not add independent thermal observability.
The heat residual remains an approximate regularizer, not an independent
measurement. Therefore the training can match port conductance without
materially improving `delta_T`.

## Recommended next step

The next step should be observability-first rather than another architecture
change. Add or simulate auxiliary thermal or spatial observations, test sparse
observation sensitivity, and adjust the paper narrative to state that port-only
PINN inversion diagnoses conductance-level dynamics but cannot uniquely recover
all hidden fields.

All results in this report are synthetic numerical digital-twin benchmark
results, not experimental measurements.
