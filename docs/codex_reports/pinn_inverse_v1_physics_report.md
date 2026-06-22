# Codex report: PINN inverse v1 physics residuals

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before v1 work: `44bf789356ca39e682a52e9a5f19a0f33fe9e3d9`
- Pushed v1 implementation commit hash: `5d315037cfffb789d9bd2b0d61e9ed0ab02f29a6`

## Scope

This task starts PINN inverse v1 as a physics-regularized inverse PINN stage on
the frozen Ground Truth v1.1 triangle synthetic numerical digital-twin
benchmark. It does not modify Ground Truth v1.1 frozen configs, frozen data,
main equations, acceptance report, or frozen metrics. It does not remove or
overwrite v0 or v0 ablation evidence.

All results remain synthetic numerical digital-twin benchmark outputs, not
experimental measurements.

## Added files

- `configs\pinn_inverse_v1_triangle_physics.yaml`
- `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`
- `configs\pinn_inverse_v1_triangle_port_physics.yaml`
- `src\pinnpcm\pinn\physics_residuals.py`
- `scripts\train_pinn_inverse_v1.py`
- `scripts\run_pinn_inverse_v1_experiments.py`
- `tests\test_pinn_inverse_v1.py`
- `docs\pinn_inverse_v1_physics_design.md`
- `docs\pinn_inverse_v1_report.md`
- `docs\codex_reports\pinn_inverse_v1_physics_report.md`
- `outputs\tables\pinn_inverse_v1_summary.json`

## Modified files

- `.gitignore`
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

## Deleted files

- None.

## v1 residual design

v1 keeps the v0 neural-field structure and adds approximate physics residuals:

- port consistency through one-dimensional series conductance reconstruction;
- lightweight heat residual using autograd `d(delta_T)/dt` and
  `d2(delta_T)/dx2`;
- conductive-state relaxation residual using autograd `dm/dt`;
- lightweight defect residual using autograd `dc_v/dt`, `dc_v/dx`, and
  `d2c_v/dx2`;
- sigma consistency between predicted positive `sigma` and a differentiable
  torch conductivity closure;
- no-flux style boundary penalties for `delta_T` and `c_v`.

The residuals are physics regularizers. v1 is not claimed as a complete
PDE-constrained inverse PINN.

## v1 metrics

Summary file:

- `outputs\tables\pinn_inverse_v1_summary.json`

| run | relative_G_error | relative_I_error | nrmse_delta_T | nrmse_delta_c_v | nrmse_delta_m | nrmse_sigma | final_heat_residual | final_state_residual | final_defect_residual | final_sigma_consistency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| triangle_physics | 0.042727336748965214 | 0.05560840604920115 | 0.459679164519594 | 0.2570472758098848 | 0.05397013834881097 | 0.03645067947627571 | 0.017007464542984962 | 0.007955554872751236 | 0.0005120213027112186 | 0.03274700045585632 |
| triangle_weak_anchor | 0.06023422693503565 | 0.07027316832500283 | 0.4698397713573344 | 2.7821646781579683 | 0.17047385980449117 | 0.0795399055268045 | 0.00033522373996675014 | 0.007747901603579521 | 0.0024670888669788837 | 0.10000892728567123 |
| triangle_port_physics | 0.10750809785303164 | 0.08434525408980736 | 0.4716395812043498 | 4.920043895115868 | 0.37468204237545 | 0.10966470169728927 | 1.7583115550223738e-06 | 0.0003062546020373702 | 0.006718229968100786 | 0.30754387378692627 |

## v1/v0 comparison

Against v0 full_anchor, `triangle_physics` slightly improves terminal error and
`sigma` nRMSE:

- v0 full_anchor `relative_G_error = 0.04331491706021674`;
- v1 triangle_physics `relative_G_error = 0.042727336748965214`;
- v0 full_anchor `nrmse_sigma = 0.03666896141668517`;
- v1 triangle_physics `nrmse_sigma = 0.03645067947627571`.

`delta_T` does not improve:

- v0 full_anchor `nrmse_delta_T = 0.45881552519801055`;
- v1 triangle_physics `nrmse_delta_T = 0.459679164519594`.

Against v0 port_only, `triangle_port_physics` improves hidden fields but worsens
terminal conductance fit:

- v0 port_only `relative_G_error = 0.07169673218475178`;
- v1 triangle_port_physics `relative_G_error = 0.10750809785303164`;
- v0 port_only `nrmse_sigma = 0.3239361550038183`;
- v1 triangle_port_physics `nrmse_sigma = 0.10966470169728927`;
- v0 port_only `nrmse_delta_c_v = 5.165463900541057`;
- v1 triangle_port_physics `nrmse_delta_c_v = 4.920043895115868`;
- v0 port_only `nrmse_delta_m = 0.40788139868512785`;
- v1 triangle_port_physics `nrmse_delta_m = 0.37468204237545`.

## Validation

- `python -m pytest`: passed.
- `python scripts\train_pinn_inverse_v1.py --config configs\pinn_inverse_v1_triangle_physics.yaml --epochs 2`: passed.
- `python scripts\run_pinn_inverse_v1_experiments.py`: passed.
- `outputs\tables\pinn_inverse_v1_summary.json`: generated.

## Residual issues

- `delta_T` remains the main absolute-error source.
- Port-only or port-physics hidden fields remain weakly identifiable from
  sparse terminal observations.
- The direct `sigma` head remains a surrogate closure, although v1 adds
  sigma-consistency regularization.
- The heat and defect residuals are normalized approximations rather than a
  full SI-unit PDE residual system.

## Next recommendation

Proceed to a v1.1 design focused on thermal identifiability and stricter
differentiable conductivity closure. Do not describe v1 as a complete
PDE-constrained inverse PINN until residuals and observability are strengthened
and audited.
