# Codex report: PINN inverse v0 ablation audit

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Commit hash: `ffad313297c78cfc158e6ae270c3b86639d79e1d`

## Scope

This task audited PINN inverse v0 on the frozen Ground Truth v1.1 triangle
synthetic numerical digital-twin benchmark. It did not modify frozen Ground
Truth v1.1 configs, frozen data, acceptance metrics, acceptance report, main
Ground Truth equations, or default Ground Truth parameters.

## Added files

- `configs\pinn_inverse_v0_triangle_full_anchor.yaml`
- `configs\pinn_inverse_v0_triangle_weak_anchor.yaml`
- `configs\pinn_inverse_v0_triangle_port_only.yaml`
- `scripts\run_pinn_inverse_v0_ablation.py`
- `docs\pinn_inverse_v0_ablation_report.md`
- `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- `PROJECT_STATE.md`
- `RESEARCH_LOG.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs\project_state\repo_tree.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\reproducibility.md`
- `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md`

## Modified files

- `.gitignore`
- `scripts\train_pinn_inverse_v0.py`
- `tests\test_pinn_inverse_v0.py`

## Deleted files

- None.

## Core ablation metrics

| run | relative_G_error | relative_I_error | nrmse_delta_T | nrmse_delta_c_v | nrmse_delta_m | nrmse_sigma |
|---|---:|---:|---:|---:|---:|---:|
| triangle_full_anchor | 0.04331491706021674 | 0.05644935907792122 | 0.45881552519801055 | 0.2565041037277942 | 0.054121152492179136 | 0.03666896141668517 |
| triangle_weak_anchor | 0.060000174387631715 | 0.07142255466034995 | 0.46955335930796416 | 2.7812821135348074 | 0.17516756534619493 | 0.08235574256119227 |
| triangle_port_only | 0.07169673218475178 | 0.0676400156881798 | 0.4725309531484271 | 5.165463900541057 | 0.40788139868512785 | 0.3239361550038183 |

## Audit conclusions

`triangle_port_only` can still reconstruct terminal conductance at v0 level:
`relative_G_error = 0.07169673218475178`. This means port constraints plus the
surrogate sigma closure are enough to fit the terminal signal moderately well.

The hidden field most dependent on field anchors is `delta_c_v`. Its normalized
RMSE rises from `0.2565041037277942` in `triangle_full_anchor` to
`5.165463900541057` in `triangle_port_only`.

`delta_T` remains the main absolute error source, with RMSE near 4 K in all
three runs. This is a current limitation of inverse v0.

PINN inverse v0 is an inverse training pipeline proof-of-concept. It is not a
strict PDE-constrained inverse PINN. The current `sigma(x,t)` path is a positive
network-predicted surrogate closure.

All results are synthetic numerical digital-twin benchmark results, not
experimental data.

## Validation

- `python -m pytest`: passed.
- `python scripts\run_pinn_inverse_v0_ablation.py`: passed.
- `outputs\tables\pinn_inverse_v0_ablation_summary.json`: generated.

## Residual issues

- Hidden fields are weakly identifiable from port-only data.
- `delta_T` is still under-constrained.
- The v0 sigma closure is useful for auditability but should be replaced or
  constrained by a differentiable physical conductivity relation in the next
  phase.

## Next recommendation

Move to PINN inverse v0.1 by tying `sigma` more tightly to `c_v`, `delta_T`, and
`m`, then add light physics residual audits before claiming PDE-constrained
inverse performance.
