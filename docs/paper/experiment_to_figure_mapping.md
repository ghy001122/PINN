# Experiment To Figure Mapping

## Scope

This mapping is for manuscript planning only. All entries refer to synthetic numerical digital-twin benchmark outputs, not experimental measurements.

## Main Text Candidate Mapping

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| Ground Truth v1.1 acceptance | `docs/gt_v1_acceptance_report.md`, `data/processed/gt_v1_acceptance/gt_triangle.npz`, `outputs/tables/gt_v1_acceptance/` | Method and benchmark setup | Figure 1 / Table 1 | Establish synthetic benchmark, hysteresis, and coupled thermal/defect/state dynamics |
| PINN inverse v0/v1/v1.1 diagnostics | `docs/pinn_inverse_v0_ablation_report.md`, `docs/pinn_inverse_v1_report.md`, `docs/pinn_inverse_v1_1_report.md`, `outputs/tables/pinn_inverse_v0_ablation_summary.json`, `outputs/tables/pinn_inverse_v1_summary.json`, `outputs/tables/pinn_inverse_v1_1_summary.json` | Motivation / ablation | Figure 2 / Table 2 | Show field-anchor dependence and why direct full hidden-field recovery is not the main claim |
| Identifiability audit | `docs/pinn_identifiability_audit_report.md`, `outputs/tables/pinn_identifiability_summary.json`, `outputs/tables/pinn_identifiability_correlation.csv` | Main result | Figure 3 | Demonstrate sparse-port full hidden-field recovery is ill-posed |
| `gamma_sub` identifiability and confounding | `docs/gamma_sub_identifiability_report.md`, `docs/gamma_sub_confounding_report.md`, `outputs/tables/gamma_sub_identifiability_summary.json`, `outputs/tables/gamma_sub_confounding_summary.json`, `outputs/tables/gamma_sub_sensitivity_ranking.csv` | Main result and discussion | Figure 4 / Table 3 | Motivate target-space reduction and identify `T_sw` as limiting confounder |
| Constrained `gamma_sub` inversion | `docs/gamma_sub_constrained_inversion_report.md`, `outputs/tables/gamma_sub_constrained_inversion_summary.json`, `outputs/tables/gamma_sub_prior_width_sweep.csv` | Main result | Figure 5 / Table 4 | Show constrained reduced inverse success and prior-width limits |
| Off-grid and observation robustness | `docs/gamma_sub_paper_readiness_report.md`, `docs/gamma_sub_continuous_refinement_report.md`, `outputs/tables/gamma_sub_paper_readiness_summary.json`, `outputs/tables/gamma_sub_continuous_refinement_summary.json`, `outputs/tables/gamma_sub_continuous_refinement_cases.csv` | Reviewer defense / result | Figure 6 / Table 5 | Show off-grid continuous refinement and observation-count/noise sensitivity |

## Supplementary Or Appendix Mapping

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| F-SPS-PINN architecture MVP | `docs/codex_reports/f_sps_pinn_architecture_mvp_report.md`, `src/pinnpcm/physics/vo2_constitutive.py`, `src/pinnpcm/pinn/network.py`, `src/pinnpcm/pinn/loss_balancer.py` | Appendix / future work | Supplementary table | Document method-development components without claiming validated performance |
| v2 smoke training | `docs/codex_reports/pinn_inverse_v2_f_sps_smoke_report.md`, `outputs/tables/pinn_inverse_v2_f_sps_smoke_summary.json` | Appendix | Supplementary table | Show white-box `vo2_sigma` enters the training graph and backpropagates |
| v2 small-run baseline | `docs/codex_reports/pinn_inverse_v2_f_sps_baseline_report.md`, `outputs/tables/pinn_inverse_v2_f_sps_baseline_summary.json`, `outputs/tables/pinn_inverse_v2_f_sps_baseline_runs.csv` | Appendix | Supplementary table | Compare free `log_sigma` and white-box `vo2_sigma` as a bounded small-run check |
| v2 phase-transition stress preflight | `docs/codex_reports/pinn_inverse_v2_phase_transition_stress_report.md`, `outputs/tables/pinn_inverse_v2_phase_transition_stress_summary.json`, `outputs/tables/pinn_inverse_v2_phase_transition_stress_cases.csv` | Appendix / discussion | Supplementary table | Show numerical stability under synthetic VO2-like stress cases |
| v2 Fourier on/off ablation | `docs/codex_reports/pinn_inverse_v2_fourier_ablation_report.md`, `outputs/tables/pinn_inverse_v2_fourier_ablation_summary.json`, `outputs/tables/pinn_inverse_v2_fourier_ablation_runs.csv` | Appendix / future work | Supplementary table | Record that Fourier features are evaluable but did not clearly outperform in the current small run |

## Narrative Order

1. Present the one-dimensional synthetic benchmark and its physical couplings.
2. Show why direct port-only hidden-field inversion is underdetermined.
3. Reduce the inverse target to `gamma_sub` under literature-guided priors.
4. Audit confounders and state that `T_sw` must be fixed or tightly bounded.
5. Use constrained inversion, off-grid refinement, observation sensitivity, and noise sensitivity as reviewer-defense evidence.
6. Move F-SPS-PINN v2 material to appendix, discussion, or future work unless a separate method paper is opened.

## Forbidden Mapping

Do not map these synthetic numerical results to an experimental validation figure unless real measured data are later added with documented provenance. Do not map current F-SPS-PINN v2 checks to a main-text performance-superiority claim.