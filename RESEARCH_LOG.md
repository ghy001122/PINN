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
