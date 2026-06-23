# PINN inverse v1.1 residual-balancing report

## Scope

PINN inverse v1.1 tunes residual balancing and loss scheduling on top of the
v1 physics-regularized inverse pipeline. The benchmark remains the frozen
Ground Truth v1.1 triangle synthetic numerical digital-twin dataset. Ground
Truth frozen configs, data, main equations, acceptance report, and frozen
metrics were not modified.

v1.1 is still an approximate physics-regularized inverse workflow. It is not a
complete PDE-constrained inverse PINN.

## What changed from v1

v1.1 adds two configs:

- `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`
- `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`

It also extends `scripts\train_pinn_inverse_v1.py` with optional:

- residual running-scale balancing;
- residual loss warmup;
- per-field anchor weighting;
- sigma initial-state drift regularization.

The v1.1 batch runner is:

- `scripts\run_pinn_inverse_v1_1_experiments.py`

The lightweight summary is:

- `outputs\tables\pinn_inverse_v1_1_summary.json`

## Metric comparison

| run | relative_G_error | relative_I_error | nrmse_delta_T | nrmse_delta_c_v | nrmse_delta_m | nrmse_sigma |
|---|---:|---:|---:|---:|---:|---:|
| v0 full_anchor | 0.04331491706021674 | 0.05644935907792122 | 0.45881552519801055 | 0.2565041037277942 | 0.054121152492179136 | 0.03666896141668517 |
| v0 port_only | 0.07169673218475178 | 0.0676400156881798 | 0.4725309531484271 | 5.165463900541057 | 0.40788139868512785 | 0.3239361550038183 |
| v1 physics | 0.042727336748965214 | 0.05560840604920115 | 0.459679164519594 | 0.2570472758098848 | 0.05397013834881097 | 0.03645067947627571 |
| v1 port_physics | 0.10750809785303164 | 0.08434525408980736 | 0.4716395812043498 | 4.920043895115868 | 0.37468204237545 | 0.10966470169728927 |
| v1.1 physics_balanced | 0.04179092330243043 | 0.05390511891755371 | 0.4695037015933208 | 0.2581316506897529 | 0.052597555765579784 | 0.035571239321291886 |
| v1.1 port_physics_balanced | 0.06619276407141951 | 0.05792024748087449 | 0.4724478734618287 | 5.434511475058795 | 0.41367830135338995 | 0.2653110337224564 |

## Findings

Delta_T:

`delta_T` did not improve. The best v0/v1 values remain around
`nrmse_delta_T = 0.4588` to `0.4597`, while v1.1 gives
`0.4695037015933208` for the anchored run and `0.4724478734618287` for
port-physics. This means the current heat residual and scheduling do not solve
thermal identifiability.

Terminal port error:

`v1.1 physics_balanced` improves terminal conductance error relative to v0
full_anchor and v1 physics. `v1.1 port_physics_balanced` also improves
`relative_G_error` relative to v0 port_only:

- v0 port_only: `0.07169673218475178`
- v1.1 port_physics_balanced: `0.06619276407141951`

Sigma stability:

For the anchored run, v1.1 improves sigma nRMSE slightly:

- v0 full_anchor: `0.03666896141668517`
- v1 physics: `0.03645067947627571`
- v1.1 physics_balanced: `0.035571239321291886`

For port-physics, v1.1 sigma is more stable than v0 port_only
(`0.2653110337224564` versus `0.3239361550038183`) but worse than v1
port_physics (`0.10966470169728927`). This is a tradeoff: v1.1 improves terminal
fit but weakens sigma consistency relative to v1 port_physics.

Port-physics versus v0 port_only:

v1.1 port_physics_balanced is better than v0 port_only for terminal `G(t)` and
sigma nRMSE, but worse for `delta_c_v`, `delta_m`, and essentially unchanged
for `delta_T`. It is not a full hidden-field solution.

Paper-figure candidate:

v1.1 is not ready as a primary hidden-field reconstruction figure candidate,
because `delta_T` and hidden fields remain weak. It can be used as an audit
figure showing the tradeoff between port fit and physics regularization.

## Residual limitations

- The heat residual is still normalized and approximate.
- Port-only hidden fields remain non-identifiable from sparse terminal
  observations.
- The model still has a direct `log_sigma` head, though v1.1 constrains drift
  with sigma consistency and initial-state regularization.
- All outputs are synthetic numerical digital-twin benchmark results, not
  experimental data.
