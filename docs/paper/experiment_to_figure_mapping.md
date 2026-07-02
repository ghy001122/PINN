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
| Multi-protocol/profile-likelihood validation | `outputs/tables/gamma_sub_multi_protocol_recoverability_summary.json`, `outputs/tables/gamma_sub_tsw_profile_likelihood_summary.json`, `outputs/tables/gamma_sub_joint_inversion_boundary_summary.json`, `outputs/tables/gamma_sub_protocol_observability_design_summary.json`, `outputs/figures/gamma_sub_sci_validation/` | Reviewer defense / result / discussion | Figure 8 / Table 7 / Supplementary Figure | Show multi-protocol generalization limits, objective ridge geometry, nuisance-release boundary, and protocol observability design guidance |
| SCI gap-closing validation pack | `outputs/tables/gamma_sub_auxiliary_observability_sweep_summary.json`, `outputs/tables/gamma_sub_auxiliary_observability_sweep_cases.csv`, `outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json`, `outputs/tables/gamma_sub_tsw_confounding_phase_map_cases.csv`, `outputs/tables/gamma_sub_tsw_prior_width_sweep_summary.json`, `outputs/tables/gamma_sub_temperature_anchor_placement_summary.json`, `outputs/tables/gamma_sub_scalar_baseline_comparison.csv`, `outputs/figures/gamma_sub_gap_closing/` | Reviewer defense / discussion | Figure 7 / Table 6 / Supplementary Table | Show auxiliary-observability limits, T_sw recoverability phase map, prior-width trend, anchor-placement limitation, and scalar-baseline framing |

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
5. Use constrained inversion, off-grid refinement, observation sensitivity, noise sensitivity, the T_sw confounding phase map, auxiliary-observability sweep, and multi-protocol/profile-likelihood validation as reviewer-defense evidence.
6. Move F-SPS-PINN v2 material to appendix, discussion, or future work unless a separate method paper is opened.

## Forbidden Mapping

Do not map these synthetic numerical results to an experimental validation figure unless real measured data are later added with documented provenance. Do not map current F-SPS-PINN v2 checks to a main-text performance-superiority claim.

## High-Throughput Addendum Mapping

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| Dense response-surface profile likelihood | `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_summary.json`, `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_grid.csv`, `outputs/figures/high_throughput_sci/dense_profile_landscape.png` | Main result / reviewer defense | Figure 9a / Table 10 | Show local objective landscape and uncertainty intervals for constrained `gamma_sub`/`T_sw` coupling |
| Recoverability phase diagram | `outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json`, `outputs/tables/gamma_sub_recoverability_phase_diagram_cases.csv`, `outputs/figures/high_throughput_sci/recoverability_phase_diagram.png` | Main result / reviewer defense | Figure 9b | Map protocol, prior-width, observation-count, and noise regions where recovery is plausible |
| Protocol actual-validation and weighted objectives | `outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json`, `outputs/tables/gamma_sub_weighted_protocol_objective_summary.json`, `outputs/figures/high_throughput_sci/protocol_actual_validation.png`, `outputs/figures/high_throughput_sci/weighted_protocol_objective.png` | Discussion / protocol design | Figure 10 / Supplementary Table | Separate sensitivity-proxy recommendations from actual response-surface recovery and test whether weighting helps |
| Statistical robustness | `outputs/tables/gamma_sub_statistical_robustness_summary.json`, `outputs/figures/high_throughput_sci/statistical_robustness_boxplot.png` | Reviewer defense / limitations | Figure 11 | Show seed/noise sensitivity and wide-mismatch failure modes |
| F-SPS medium-budget planning | `outputs/tables/f_sps_medium_budget_benchmark_summary.json`, `outputs/tables/f_sps_medium_budget_benchmark_cases.csv`, `outputs/figures/high_throughput_sci/f_sps_medium_budget_benchmark.png` | Appendix / future work | Supplementary Figure / Table | Record bounded method-development evidence without claiming superiority |

## Response-Surface Verification And Claim Consolidation Mapping

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| Response-surface anchor verification | `outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json`, `outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_4_anchor_verification.png` | Reviewer defense / result | Figure 4 / Table 5 | Qualify response-surface phase diagrams against simulator-backed anchors |
| Sequential protocol design preflight | `outputs/tables/gamma_sub_sequential_protocol_design_summary.json`, `outputs/tables/gamma_sub_sequential_protocol_design_cases.csv`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_5_protocol_design.png` | Protocol design / discussion | Figure 5 / Table 6 | Show value-of-information hypothesis for reducing the `gamma_sub`/`T_sw` ridge |
| Balanced F-SPS medium-budget benchmark | `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json`, `outputs/tables/f_sps_balanced_medium_budget_benchmark_cases.csv`, `outputs/figures/manuscript_ready_gamma_sub/appendix_f_sps_balanced_benchmark.png` | Appendix / future work | Appendix Figure A1 / Supplementary Table S1 | Record balanced method-development evidence without claiming F-SPS superiority |
| Claim stress-test matrix | `docs/paper/claim_stress_test_matrix.md`, `outputs/tables/manuscript_claim_stress_test_summary.json` | Supplementary evidence / writing guardrail | Supplementary Table S2 | Prevent overclaiming and map claims to evidence |
## Literature-Anchored Pack Mapping

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| Literature sanity and no-fabrication curve template | `data/literature/literature_parameter_sanity_table.csv`, `data/literature/literature_curve_registry.csv`, `docs/literature/` | Method / limitations | Table 3 / Supplementary Table | Anchor priors and document the absence of usable digitized curve data |
| T_sw calibration necessity | `outputs/tables/gamma_sub_tsw_calibration_necessity_summary.json` | Main result / limitations | Figure 5 | Quantify why T_sw calibration is required |
| Simulator-backed sequential validation | `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json` | Discussion / protocol design | Figure 5 / Supplementary Table | Validate the response-surface protocol ranking with ODE-backed cases |

## External Curve And Calibrated Workflow Mapping

| Evidence block | Primary files | Manuscript location | Candidate figure/table | Purpose |
| --- | --- | --- | --- | --- |
| Literature curve ingestion v2 | `outputs/tables/literature_curve_ingestion_summary.json`, `docs/literature/literature_curve_provenance_notes.md` | Methods / data provenance | Supplementary note | Document that no external curve points were fabricated |
| External curve fit v2 | `outputs/tables/literature_curve_fit_external_anchor_v2_summary.json` | Limitations / future data | Supplementary status | Show external curve fitting is ready but blocked by missing digitized curves |
| T_sw calibration workflow | `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json` | Main result | Figure 2 / Table 4 | Demonstrate calibration-before-inversion reduces error |
| Calibrated sequential protocol validation | `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json` | Main result / discussion | Figure 5 / Table 5 | Support protocol-design evidence under bounded priors |

