# PINN inverse v0 ablation audit

This audit evaluates PINN inverse v0 on the frozen Ground Truth v1.1 triangle
synthetic numerical digital-twin benchmark. It does not use or claim measured
experimental data.

## Scope

- Repository: `https://github.com/ghy001122/PINN`
- Main research line: mesh-free, fully differentiable, multi-physics digital twin plus PINN inverse identification for phase-change or memristive defect diagnosis.
- Frozen data: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Sparse observation file: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary table: `outputs\tables\pinn_inverse_v0_ablation_summary.json`

Ground Truth v1.1 frozen configs, frozen data, acceptance report, acceptance
metrics, main equations, and default Ground Truth parameters were not changed.

## Loss weights

| run | config | w_port_data | w_ic | w_field_anchor | w_smooth | w_physics_light |
|---|---|---:|---:|---:|---:|---:|
| full_anchor | `configs\pinn_inverse_v0_triangle_full_anchor.yaml` | 1.0 | 1.0 | 1.0 | 1.0e-3 | 1.0e-3 |
| weak_anchor | `configs\pinn_inverse_v0_triangle_weak_anchor.yaml` | 1.0 | 1.0 | 0.1 | 1.0e-3 | 1.0e-3 |
| port_only | `configs\pinn_inverse_v0_triangle_port_only.yaml` | 1.0 | 1.0 | 0.0 | 1.0e-3 | 1.0e-3 |

## Metrics

The normalized RMSE values use the frozen Ground Truth v1.1 triangle acceptance
scales:

- `max_delta_T = 8.750689766759194`
- `max_abs_delta_c_v = 0.00207390149033114`
- `max_abs_delta_m = 0.19195497789296317`
- `sigma_min = 0.0022561446979527944`
- `sigma_max = 0.0237445194669558`

| run | relative_G_error | relative_I_error | rmse_delta_T | nrmse_delta_T | rmse_delta_c_v | nrmse_delta_c_v | rmse_delta_m | nrmse_delta_m | rmse_sigma | nrmse_sigma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_anchor | 0.04331491706021674 | 0.05644935907792122 | 4.014952321180476 | 0.45881552519801055 | 0.0005319642429971257 | 0.2565041037277942 | 0.010388824630177936 | 0.054121152492179136 | 0.0007879563852751732 | 0.03666896141668517 |
| weak_anchor | 0.060000174387631715 | 0.07142255466034995 | 4.108915776243605 | 0.46955335930796416 | 0.00576810512029118 | 2.7812821135348074 | 0.03362428613359303 | 0.17516756534619493 | 0.0017696910604520749 | 0.08235574256119227 |
| port_only | 0.07169673218475178 | 0.0676400156881798 | 4.134971776192909 | 0.4725309531484271 | 0.0107126632815838 | 5.165463900541057 | 0.07829486486755462 | 0.40788139868512785 | 0.006960861499627958 | 0.3239361550038183 |

## Interpretation

The port-only run still reconstructs the terminal conductance trajectory at a
useful v0 level: `relative_G_error = 0.07169673218475178`. This shows that the
surrogate sigma closure and port data loss can fit `G(t)` from sparse terminal
observations.

The hidden fields are not identifiable from the current port-only objective.
Reducing or removing `L_field_anchor` produces large degradation in
`delta_c_v`, `m`, and `sigma`. The strongest field-anchor dependence appears in
`delta_c_v`, where nRMSE grows from `0.2565041037277942` in full_anchor to
`5.165463900541057` in port_only. `sigma` also degrades substantially, from
`0.03666896141668517` to `0.3239361550038183`.

`delta_T` remains the dominant absolute RMSE source across all runs, with
`rmse_delta_T` near 4 K. Its nRMSE changes only modestly across this ablation,
which means the current inverse v0 architecture and loss weighting do not yet
recover thermal dynamics tightly even when field anchors are available.

The current sigma path is a v0 surrogate closure: the network predicts a
positive `sigma(x,t)` directly and the port loss integrates it through the
series electrostatic relation. This is appropriate for proving the inverse
training pipeline, but it is not a strict PDE-constrained inverse PINN and
should not be described as such.

## Reproducibility

Run:

```powershell
python -m pytest
python scripts/run_pinn_inverse_v0_ablation.py
```

Expected generated directories:

- `outputs\pinn_inverse_v0\triangle_full_anchor\`
- `outputs\pinn_inverse_v0\triangle_weak_anchor\`
- `outputs\pinn_inverse_v0\triangle_port_only\`

Each directory contains `train_history.json`, `metrics.json`,
`loss_curve.png`, `compare_g_time.png`, `pred_delta_T_map.png`,
`pred_delta_c_v_map.png`, `pred_delta_m_map.png`, and `pred_sigma_map.png`.
These generated training outputs are reproducible and are not committed.
