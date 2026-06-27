# Experiment To Figure Mapping

## Scope

This mapping is for manuscript planning only. All entries refer to synthetic
numerical digital-twin benchmark outputs, not experimental measurements.

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| Ground Truth v1.1 acceptance | `docs/gt_v1_acceptance_report.md`, `data/processed/gt_v1_acceptance/gt_triangle.npz`, `outputs/tables/gt_v1_acceptance/` | Method and Result | Figure 1 or Table 1 | Establish the synthetic benchmark, hysteresis, thermal/defect/state dynamics |
| PINN inverse v0 | `configs/pinn_inverse_v0_triangle.yaml`, `docs/pinn_inverse_v0_ablation_report.md`, `outputs/tables/pinn_inverse_v0_ablation_summary.json` | Ablation | Figure 2 / Table 2 | Show port reconstruction and field-anchor dependence |
| PINN inverse v1 | `docs/pinn_inverse_v1_report.md`, `outputs/tables/pinn_inverse_v1_summary.json` | Ablation or Supplement | Supplementary Table | Show approximate residual regularization did not solve hidden-field identifiability |
| PINN inverse v1.1 | `docs/pinn_inverse_v1_1_report.md`, `outputs/tables/pinn_inverse_v1_1_summary.json` | Ablation or Supplement | Supplementary Table | Show residual balancing and remaining `delta_T` difficulty |
| Identifiability audit | `docs/pinn_identifiability_audit_report.md`, `outputs/tables/pinn_identifiability_summary.json`, `outputs/tables/pinn_identifiability_correlation.csv` | Result and Discussion | Figure 3 | Demonstrate sparse-port full hidden-field recovery is ill-posed |
| gamma_sub identifiability audit | `docs/gamma_sub_identifiability_report.md`, `outputs/tables/gamma_sub_identifiability_summary.json` | Result | Figure 4 / Table 3 | Motivate target-space reduction to `gamma_sub` |
| gamma_sub confounding audit | `docs/gamma_sub_confounding_report.md`, `outputs/tables/gamma_sub_confounding_summary.json`, `outputs/tables/gamma_sub_sensitivity_ranking.csv` | Result and Discussion | Figure 5 / Table 4 | Identify `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` as confounders |
| Constrained gamma_sub inversion | `docs/gamma_sub_constrained_inversion_report.md`, `outputs/tables/gamma_sub_constrained_inversion_summary.json`, `outputs/tables/gamma_sub_prior_width_sweep.csv` | Main Result | Table 5 | Show constrained reduced inverse success and prior-width limit |
| Paper-readiness robustness pack | `docs/gamma_sub_paper_readiness_report.md`, `outputs/tables/gamma_sub_paper_readiness_summary.json`, `outputs/tables/gamma_sub_observation_sensitivity.csv`, `outputs/tables/gamma_sub_offgrid_summary.csv` | Reviewer defense / Supplement | Table 6 | Test off-grid robustness and observation-count sensitivity |

## Narrative Order

1. Present the one-dimensional synthetic benchmark and its physical couplings.
2. Show why direct port-only hidden-field inversion is underdetermined.
3. Reduce the inverse target to `gamma_sub` under literature-guided priors.
4. Audit confounders and state that `T_sw` must be fixed or tightly bounded.
5. Use paper-readiness robustness results as reviewer-defense evidence.

## Forbidden Mapping

Do not map these synthetic numerical results to an experimental validation
figure unless real measured data are later added with documented provenance.