# Q2 M1 latent solver-projected PINN MVE v1

## Conclusion

Disposition: `GO_M1_LATENT_PROJECTION_PINN_MVE`. This is a single-seed diagnostic MVE on literature-guided synthetic numerical digital-twin evidence; it is not formal superiority or experimental validation.

## Frozen baseline and operator parity

Base is the unchanged PR #38 squash merge `425d485838ac90cb2b7dba36bad409a9ef931b28`; the result branch is `codex/q2-m1-latent-solver-projected-pinn-mve-v1`. The final commit is recorded in the Git handoff because this report is part of that commit.

PR #38 remains unchanged as the bounded negative result `NO_GO_M1_RCV_PINN_RESCUE` and was squash-merged before this branch. The dense float64 Torch M1 operator preserves the same Robin contacts, conservative face conductances, boundary-cell Joule partition, contact-corrected thermal closure, localized sink, ports, and ledgers.

Parity passed `12/12` cases; worst phi/T map errors were `2.129e-15` and `8.631e-10`.

## Train-only POD and actual training

The POD used complete temperature fields from the eight training cases only and selected rank `2` at cumulative energy `0.999997413`. This method is not data-free, mesh-free, or sparse-anchor-only; it is a projection-embedded physics-informed neural reduced-order model.

The sole latent network completed `1500` Adam steps in float64 at seed `20260809` with wall time `131.9` s.

## Frozen test metrics

| mode | T-rise L2 | phi L2 | current | fixed defect | sigma defect | max ledger | speedup |
|---|---:|---:|---:|---:|---:|---:|---:|
| N0 | 0.35704 | 0.0011841 | 0.013128 | 0.33994 | 0.014669 | 3.017e-01 | 50.9x |
| N1 | 0.013981 | 0.0011841 | 0.013128 | 0.013418 | 0.00060686 | 8.218e-14 | 36.2x |
| N2 | 0.00058126 | 3.4666e-05 | 0.00057603 | 0.013418 | 0.00060686 | 9.040e-14 | 17.9x |
| NC | 2.2332e-05 | 1.8651e-08 | 9.7372e-07 | 2.1347e-05 | 9.8586e-07 | 3.441e-05 | 3.25x |

## Decision boundary

N2 passed `1/2` complete fast test cases, achieved median speedup `17.9x`, and improved mean joint field score over N0 by `99.83%`. NC passed `0/2` certified cases with median total projection updates `10` and speedup `3.25x`.

The second N2 test case missed only the preregistered fixed-point gate (`0.0200141 > 0.02`); its T-rise, phi, current, sigma, and ledger gates passed. This near miss is preserved without threshold movement. NC exhausted eight additional relaxed iterations on both test cases and therefore does not support a certified-warm-start claim.

Critical ablation: A2 passed the same fast per-case thresholds on `2/2` test cases and achieved mean joint-field score `6.47161e-05`, versus `3.07963e-04` for N2. Thus the frozen N2 Fast-GO disposition is valid, but this MVE does not support a neural-specific advantage over the analytic two-projection baseline; resolving that comparison is the first requirement of formal OOD.

Allowed identity: `M1-LatentProj-PINN`, a learned low-rank initialization embedded in a frozen conservative M1 electrothermal projection. Operator parity is `supported`; M1 reference sufficiency remains `qualified_supported`; this single-seed MVE remains `diagnostic_non_voting`.

Forbidden sentences: data-free PINN, mesh-free PINN, sparse-anchor-only PINN, formal OOD superiority, experimental validation, full hysteresis, inverse recovery, or zero-shot material transfer.

## Figures

- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/thermal_pod_spectrum_and_modes.png`
- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/projection_operator_parity.png`
- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/field_comparison_n0_n1_n2_reference.png`
- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/fixed_point_defect_by_projection.png`
- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/port_and_ledger_by_projection.png`
- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/speed_accuracy_pareto.png`
- `outputs/figures/q2_m1_latent_solver_projected_pinn_mve_v1/Q2-M1-LATENT-PROJ-PINN-MVE-20260810-V1/direct_pinn_vs_projected_method.png`

## Single next priority

Preregister Q2_M1_LATENT_PROJECTION_PINN_FORMAL_OOD_V1 with analytic A2 as the first neural-specific value comparator; do not execute it in this round.
