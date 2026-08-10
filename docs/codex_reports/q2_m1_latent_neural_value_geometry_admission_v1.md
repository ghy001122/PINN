# Q2 M1 latent neural-value geometry admission v1

## Conclusion

Disposition: `NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES`. The evidence is literature-guided synthetic numerical digital-twin evidence and remains diagnostic rather than formal OOD superiority or experimental validation.

## Frozen PR #39

PR #39 remained unchanged at head `e85e641a46deb8b9ac6c780ba32213acc510e7e0`, retaining `GO_M1_LATENT_PROJECTION_PINN_MVE` and `neural-specific advantage over A2 = false`; it was squash-merged as `56999bbe33065a7e80587c009ab78011d61b265c` before this branch.

## Geometry reference and sentinels

The dataset contains `36` M1 cases on the fixed 10 x 25 production grid with true 10/20/30 nm contact-mask and covered-sheet changes. Reference gates passed `36/36` cases; the six branch-specific localized near-transition checks passed: `True`.

The four preregistered M2 sentinels passed `4/4`; maximum current, Tmax, and resolved hotspot differences were `0.000629`, `0.01663 K`, and `0 W`.

The single implementation repair replaced symmetry-degenerate single-cell argmax comparison by a float64 machine-precision hotspot-set distance. It changed no threshold, data, or physical model and required zero additional nonlinear M1/M2 reference solves; diagnostic reconstruction solves are recorded separately.

## Train-only POD, ridge and actual neural training

Only the 20 train fields entered the POD, rank selection, input/coefficient normalization, ridge fit, or neural training. The selected POD rank is `2` at cumulative energy `0.999984445`; ridge used the frozen closed-form lambda `1e-8`.

Executed neural seeds: `20260809`. Conditional seeds executed: `False`; every executed seed completed exactly 1500 Adam steps.

The POD and neural mapper use complete train fields. This is a projection-embedded physics-informed neural reduced-order model, not a data-free, mesh-free, or sparse-anchor-only PINN.

## Matched-budget geometry-OOD metrics

| mode | T-rise L2 | phi L2 | current | joint | true defect | passes | median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | 0.004715 | 0.00067595 | 0.0028623 | 0.0026955 | 0.0044809 | 12/12 | 0.0056778 |
| A2 | 0.00025415 | 2.2528e-05 | 0.0001774 | 0.00013834 | 0.00023526 | 12/12 | 0.010755 |
| R1 | 0.019444 | 0.00051876 | 0.01903 | 0.0099815 | 0.018413 | 8/12 | 0.0052866 |
| R2 | 0.0010086 | 1.1911e-05 | 0.00096518 | 0.00051025 | 0.00094651 | 12/12 | 0.010517 |
| N1 | 0.0073964 | 0.00025945 | 0.0074049 | 0.0038279 | 0.0070327 | 11/12 | 0.003885 |
| N2 | 0.00036173 | 4.9619e-06 | 0.00035234 | 0.00018335 | 0.00033953 | 12/12 | 0.0079364 |

## Neural-specific value gate

The initial seed Path H result is `False` and Path S result is `False`. Final selected path: `None`; same-path seed passes: `0`.

Analytic A2 or the linear POD mapper already covers this bounded problem; the neural module did not establish independent necessity, so neural forward-architecture expansion stops.

## Break-even

Status: `not_applicable_no_admitted_neural_route`; no neural route was admitted, so deployment and research break-even are not applicable.

## Claim boundary and next priority

M1 operator parity is supported; M1 reference adequacy over the admitted 10-30 nm range is at most qualified_supported; direct-coordinate PINN remains failed_but_informative. Neural-specific admission is diagnostic only. Formal superiority, experimental validation, dynamic hysteresis, and inverse claims remain forbidden.

Stop neural forward-architecture expansion; retain the conservative projection operator and analytic A2 as numerical assets for the limitation manuscript.

## Figures

- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/geometry_masks_and_reference_fields.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/geometry_pod_spectrum_and_modes.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/matched_budget_accuracy.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/geometry_ood_field_comparison.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/a1_a2_r1_r2_n1_n2_pass_rates.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/true_fixed_point_defect.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/speed_accuracy_pareto.png`
- `outputs/figures/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1/break_even_queries.png`

## Artifact and execution identity

- Processed data and predictions: `data/processed/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1`
- Tables: `outputs/tables/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1`
- Checkpoint: `outputs/checkpoints/q2_m1_latent_neural_value_geometry_admission_v1/Q2-M1-LATENT-NEURAL-VALUE-GEOMETRY-ADMISSION-20260810-V1`
- Base: `56999bbe33065a7e80587c009ab78011d61b265c`
- Branch: `codex/q2-m1-latent-neural-value-geometry-admission-v1`
- Focused verification: `pytest -q tests/test_q2_m1_latent_neural_value_geometry_admission_v1.py` -> `7 passed`
