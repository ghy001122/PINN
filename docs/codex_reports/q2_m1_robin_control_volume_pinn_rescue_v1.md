# Q2 M1 Robin control-volume PINN rescue v1

## Frozen baseline

PR #37 at `c4ccd7a995fbd4027d92a10fcbf42b1e14906092` remains the immutable bounded negative result `NO_GO_GEOSTATE_PINN_IDEA_SCREEN`; it was squash-merged unchanged as `183f129545a2a047137745d36a0c432d02a28219`.

## Teacher--objective compatibility

Passed: `true` across `12/12` finite cases. Worst current/energy P95 were `7.287e-15` and `9.332e-08`; worst Robin/interface errors were `3.894e-13` and `1.392e-09`. No reference nonlinear solve was rerun.

## Structural corrections

The rescue removes M0 terminal hard lifting, uses M1 electrical Robin contacts and contact-corrected vertical thermal conductance, evaluates explicit three-region traces, trains only phi/T anchors, and replaces pointwise mixed-flux divergence with locked control-volume balances for P0-RCV.

## Actual single-seed results

All three models used seed `20260809`, float64, the same 5% geometry-only phi/T anchors, the same split, and exactly 1500 Adam steps.

| model | T-rise L2 | phi L2 | current | energy | interface | current-CV P95 | energy-CV P95 | passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0-R | 0.2062 | 0.0413 | 35.9296 | 0.7714 | 1.2963 | 0.2670 | 31.5428 | 0/2 |
| B1-R | 0.9444 | 0.2645 | 0.8965 | 0.9995 | 0.1036 | 0.0001 | 0.0946 | 0/2 |
| P0-RCV | 0.6193 | 0.1829 | 0.8914 | 0.8736 | 0.1029 | 0.0050 | 0.9470 | 0/2 |

Decision diagnostics: P0 field improvement over B0 `-224.21%`; conservation factor over B1 `1.144x`; catastrophic regression `False`.

## Disposition

`NO_GO_M1_RCV_PINN_RESCUE`

## Figures

- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/teacher_objective_residual_maps.png`
- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/m1_robin_boundary_profiles.png`
- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/field_comparison_b0_b1_p0.png`
- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/interface_flux_comparison.png`
- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/local_cv_residuals.png`
- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/port_energy_ledger_comparison.png`
- `outputs/figures/q2_m1_robin_control_volume_pinn_rescue_v1/Q2-M1-ROBIN-CV-PINN-RESCUE-20260810-V1/training_group_losses.png`

## Claim boundary

Allowed manuscript sentence: "The M1 teacher/objective contract is compatible, but the bounded single-seed direct coordinate-PINN rescue failed." M1 reference sufficiency remains `qualified_supported`; teacher--objective compatibility is an implementation/contract fact; this single-seed rescue is diagnostic and non-voting.

Forbidden manuscript sentence: any claim of formal PINN superiority, experimental validation, dynamic stability, complete hysteresis, or inverse recovery. Formal superiority requires a later authorized formal OOD and multiple seeds.

## Single next priority

Stop direct coordinate-PINN expansion and route to a limitation manuscript or solver-projected surrogate.
