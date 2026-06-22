# Research log

## PINN inverse v0 ablation audit

Date: 2026-06-22

Actions:

- Added `configs\pinn_inverse_v0_triangle_full_anchor.yaml`.
- Added `configs\pinn_inverse_v0_triangle_weak_anchor.yaml`.
- Added `configs\pinn_inverse_v0_triangle_port_only.yaml`.
- Added `scripts\run_pinn_inverse_v0_ablation.py`.
- Updated `scripts\train_pinn_inverse_v0.py` to report `nrmse_delta_T`,
  `nrmse_delta_c_v`, `nrmse_delta_m`, and `nrmse_sigma`.
- Added `outputs\tables\pinn_inverse_v0_ablation_summary.json`.
- Added `docs\pinn_inverse_v0_ablation_report.md`.

Findings:

- Full-anchor v0 reconstructs terminal conductance with
  `relative_G_error = 0.04331491706021674`.
- Port-only v0 still reconstructs terminal conductance with
  `relative_G_error = 0.07169673218475178`.
- Hidden fields are not uniquely identifiable from port-only supervision in the
  current v0 setup.
- `delta_c_v` shows the strongest field-anchor dependence.
- `delta_T` remains the main absolute RMSE source.

Ethics note:

All results in this repository are synthetic numerical benchmark results unless
explicitly documented otherwise in `docs\data_provenance.md`.

## PINN inverse v1 physics regularization

Date: 2026-06-22

Actions:

- Added `src\pinnpcm\pinn\physics_residuals.py`.
- Added `configs\pinn_inverse_v1_triangle_physics.yaml`.
- Added `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`.
- Added `configs\pinn_inverse_v1_triangle_port_physics.yaml`.
- Added `scripts\train_pinn_inverse_v1.py`.
- Added `scripts\run_pinn_inverse_v1_experiments.py`.
- Added `outputs\tables\pinn_inverse_v1_summary.json`.
- Added `docs\pinn_inverse_v1_physics_design.md`.
- Added `docs\pinn_inverse_v1_report.md`.

Findings:

- v1 adds heat, state, defect, sigma-consistency, and boundary residuals through
  torch autograd.
- `triangle_physics` slightly improves terminal port error and `sigma` nRMSE
  relative to v0 full_anchor.
- `triangle_port_physics` improves hidden-field regularity relative to v0
  port_only but worsens terminal `G(t)` error.
- `delta_T` remains the largest absolute error source and is not materially
  improved by the current lightweight heat residual.

Boundary:

v1 is physics-regularized and approximate. It is not yet a strict
PDE-constrained inverse PINN.
