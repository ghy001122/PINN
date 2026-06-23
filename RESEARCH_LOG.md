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

## PINN inverse v1.1 residual balancing

Date: 2026-06-23

Actions:

- Added `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`.
- Added `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`.
- Added `scripts\run_pinn_inverse_v1_1_experiments.py`.
- Extended `scripts\train_pinn_inverse_v1.py` with optional running-scale
  residual balancing, warmup scheduling, per-field anchor weights, and sigma
  initial-state regularization.
- Added `outputs\tables\pinn_inverse_v1_1_summary.json`.
- Added `docs\pinn_inverse_v1_1_report.md`.
- Added `docs\codex_reports\pinn_inverse_v1_1_report.md`.

Findings:

- v1.1 physics_balanced improves `relative_G_error` and sigma nRMSE slightly
  relative to v1 physics, but `delta_T` worsens.
- v1.1 port_physics_balanced improves terminal `G(t)` and sigma nRMSE relative
  to v0 port_only, but hidden `delta_c_v` and `m` remain weak.
- v1.1 is not a primary paper-figure candidate for hidden-field reconstruction.

Boundary:

All v1.1 results are synthetic numerical digital-twin benchmark outputs, not
experimental data.

## PINN identifiability audit

Date: 2026-06-23

Actions:

- Added `scripts\analyze_pinn_identifiability.py`.
- Generated `outputs\tables\pinn_identifiability_summary.json`.
- Generated `outputs\tables\pinn_identifiability_correlation.csv`.
- Generated `outputs\figures\pinn_identifiability\correlation_heatmap.png`.
- Generated `outputs\figures\pinn_identifiability\spatial_sensitivity.png`.
- Generated `outputs\figures\pinn_identifiability\lag_correlation.png`.
- Added `docs\pinn_identifiability_audit_report.md`.
- Added `docs\codex_reports\pinn_identifiability_audit_report.md`.

Findings:

- `G(t)` is nearly perfectly correlated with `mean_sigma`
  (`r = 0.9999966158284996`).
- `G(t)` is also highly correlated with aggregate `delta_T`, `delta_c_v`, and
  `m`, which makes terminal-only hidden-field decomposition non-unique.
- In the frozen benchmark, `sigma` aligns more strongly with `m`
  (`r = 0.8241268575488281`) than with `c_v`
  (`r = 0.3216744579750865`).
- v1.1 did not significantly improve `delta_T` because it improved residual
  balancing but did not add independent thermal observability.

Boundary:

The identifiability audit is a synthetic numerical digital-twin analysis. It is
not experimental evidence.

## v2a gamma_sub identifiability audit

Date: 2026-06-23

Actions:

- Added `scripts\scan_gamma_sub_identifiability.py`.
- Added `scripts\invert_gamma_sub_v0.py`.
- Added `outputs\tables\gamma_sub_identifiability_summary.json`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`.
- Added `docs\gamma_sub_identifiability_report.md`.
- Added `docs\codex_reports\gamma_sub_identifiability_audit_report.md`.

Findings:

- With `D_v0`, `mu_v0`, `T_sw`, and `tau_m` fixed, `gamma_sub` is stably
  recovered from terminal `G/I` plus a candidate heat-residual regularizer.
- Clean best estimate: `450001503.273578` versus target `4.5e8`.
- Clean relative error: `3.3406079510847727e-06`.
- Maximum noisy mean relative error over 2 percent and 5 percent synthetic
  noise tests: `0.009843655826927688`.
- Multi-start inversions were consistent for all tested noise cases.
- Joint confusion with `T_sw` and `tau_m` remains unproven because those
  parameters were fixed in this reduced audit.

Boundary:

This is synthetic numerical digital-twin evidence for a reduced scalar inverse
problem, not experimental validation and not proof of full hidden-field
identifiability.

## gamma_sub robustness and confounding audit

Date: 2026-06-23

Actions:

- Added `scripts\audit_gamma_sub_confounding.py`.
- Added `scripts\invert_gamma_sub_with_mismatch.py`.
- Added `outputs\tables\gamma_sub_confounding_summary.json`.
- Added `outputs\tables\gamma_sub_sensitivity_ranking.csv`.
- Added `docs\gamma_sub_confounding_report.md`.
- Added `docs\codex_reports\gamma_sub_confounding_audit_report.md`.

Findings:

- `T_sw` has the largest aggregate sensitivity in the local perturbation audit.
- `sigma_on0` and `tau_m` are the closest response-shape confounders for
  `gamma_sub`.
- Mismatch inversion is not robust as an unconstrained claim: `T_sw_plus_2K`
  pushes the recovered `gamma_sub` to the upper bound.
- The gamma_sub branch remains useful only as a constrained reduced inverse
  problem with independently fixed or calibrated switching, conductivity, and
  geometric-scale parameters.

Boundary:

All results are synthetic numerical digital-twin benchmark outputs, not
experimental measurements.
