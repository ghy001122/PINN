# PINN inverse v1 report

## Scope

PINN inverse v1 adds physics-regularized losses to the existing inverse v0
pipeline. The benchmark is the frozen Ground Truth v1.1 triangle synthetic
numerical digital-twin dataset:

- `data\processed\gt_v1_acceptance\gt_triangle.npz`
- `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`

Ground Truth v1.1 frozen configs, data, main equations, acceptance report, and
frozen metrics were not modified.

## What v1 adds over v0

v1 adds:

- `src\pinnpcm\pinn\physics_residuals.py`
- `configs\pinn_inverse_v1_triangle_physics.yaml`
- `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`
- `configs\pinn_inverse_v1_triangle_port_physics.yaml`
- `scripts\train_pinn_inverse_v1.py`
- `scripts\run_pinn_inverse_v1_experiments.py`

The added residuals are:

- lightweight heat residual;
- conductive-state relaxation residual;
- lightweight defect residual;
- sigma consistency residual;
- no-flux style boundary residual.

These residuals use torch autograd for `d/dt`, `d/dx`, and `d2/dx2`. They are
physics regularizers, not a complete PDE-constrained inverse PINN.

## Metrics

Summary file:

- `outputs\tables\pinn_inverse_v1_summary.json`

| run | relative_G_error | relative_I_error | nrmse_delta_T | nrmse_delta_c_v | nrmse_delta_m | nrmse_sigma | final_heat_residual | final_state_residual | final_defect_residual | final_sigma_consistency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| triangle_physics | 0.042727336748965214 | 0.05560840604920115 | 0.459679164519594 | 0.2570472758098848 | 0.05397013834881097 | 0.03645067947627571 | 0.017007464542984962 | 0.007955554872751236 | 0.0005120213027112186 | 0.03274700045585632 |
| triangle_weak_anchor | 0.06023422693503565 | 0.07027316832500283 | 0.4698397713573344 | 2.7821646781579683 | 0.17047385980449117 | 0.0795399055268045 | 0.00033522373996675014 | 0.007747901603579521 | 0.0024670888669788837 | 0.10000892728567123 |
| triangle_port_physics | 0.10750809785303164 | 0.08434525408980736 | 0.4716395812043498 | 4.920043895115868 | 0.37468204237545 | 0.10966470169728927 | 1.7583115550223738e-06 | 0.0003062546020373702 | 0.006718229968100786 | 0.30754387378692627 |

## v1 versus v0

Reference v0 values from `outputs\tables\pinn_inverse_v0_ablation_summary.json`:

- v0 full_anchor: `relative_G_error = 0.04331491706021674`,
  `nrmse_delta_T = 0.45881552519801055`,
  `nrmse_delta_c_v = 0.2565041037277942`,
  `nrmse_delta_m = 0.054121152492179136`,
  `nrmse_sigma = 0.03666896141668517`.
- v0 weak_anchor: `relative_G_error = 0.060000174387631715`,
  `nrmse_delta_T = 0.46955335930796416`,
  `nrmse_delta_c_v = 2.7812821135348074`,
  `nrmse_delta_m = 0.17516756534619493`,
  `nrmse_sigma = 0.08235574256119227`.
- v0 port_only: `relative_G_error = 0.07169673218475178`,
  `nrmse_delta_T = 0.4725309531484271`,
  `nrmse_delta_c_v = 5.165463900541057`,
  `nrmse_delta_m = 0.40788139868512785`,
  `nrmse_sigma = 0.3239361550038183`.

Findings:

- `triangle_physics` slightly improves terminal port errors and `sigma` nRMSE
  relative to v0 full_anchor, but `delta_T` is not improved.
- `triangle_weak_anchor` keeps terminal error close to v0 weak_anchor and
  slightly improves `m` and `sigma`, but `delta_T` and `delta_c_v` remain
  essentially unchanged.
- `triangle_port_physics` improves hidden-field regularity relative to v0
  port_only for `delta_c_v`, `m`, and especially `sigma`, but terminal
  `G(t)` error becomes worse than v0 port_only.

## Answers to audit questions

Delta_T improvement:

`delta_T` did not materially improve in v1. It remains the main absolute error
source, around 4 K RMSE. The current heat residual is too lightweight and
normalized to identify thermal dynamics from sparse terminal data alone.

Field-anchor dependence:

Field-anchor dependence is reduced only partially. In the port-physics run,
`sigma`, `m`, and `delta_c_v` improve relative to v0 port_only, but they remain
far worse than anchored runs. Hidden fields are still not uniquely identified
from terminal data plus the current approximate residuals.

Port-physics conductance reconstruction:

`triangle_port_physics` can reconstruct `G(t)` at a usable smoke-audit level,
but its `relative_G_error = 0.10750809785303164` is worse than v0 port_only.
The physical regularizers improve hidden-field plausibility while trading off
some terminal fit.

Hardest hidden field:

`delta_c_v` remains the hardest hidden field under weak or zero field anchors.
`delta_T` remains the largest absolute-error source.

Still-unproven assumptions:

- The normalized heat residual is not yet a strict thermal PDE residual.
- The defect residual is a stabilizing approximation, not a validated ionic
  transport law.
- The direct `sigma` head is still a surrogate closure, although v1 adds a
  consistency penalty to a differentiable conductivity relation.
- Better identifiability may require richer observations, stronger physical
  closure, or staged training.

All results are synthetic numerical digital-twin benchmark outputs, not
experimental measurements.
