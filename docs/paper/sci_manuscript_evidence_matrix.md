# SCI Manuscript Evidence Matrix

## Scope

This matrix consolidates existing evidence for a high-quality method-oriented SCI manuscript. All evidence is synthetic numerical digital-twin benchmark evidence. It is not measured experimental data, not full three-dimensional device simulation, and not proof of sparse-port unique full hidden-field recovery.

## Core Manuscript Claim

The defensible core claim is:

- sparse-port full hidden-field recovery is ill-posed for `delta_T`, `c_v`, `m`, and `sigma` in the current one-dimensional benchmark;
- identifiability-guided target-space reduction is required;
- constrained `gamma_sub` inversion is conditionally identifiable when switching, defect, conductivity, and area priors are fixed or tightly bounded;
- `T_sw` is the most dangerous confounder and must remain explicitly bounded in the claim.

## Main-Text Evidence Table

| Experiment | Script/config | Summary file | Report file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- | --- |
| Ground Truth v1.1 acceptance | `scripts/run_gt_v1_acceptance.py`, `configs/gt_v1_acceptance_triangle.yaml` | `outputs/tables/gt_v1_acceptance/gt_triangle_metrics.json` | `docs/gt_v1_acceptance_report.md` | Figure 1 / Table 1 | The repository has a frozen synthetic hysteretic benchmark with visible thermal/defect/state dynamics | The data are measured device data or direct fabrication validation |
| PINN v0/v1/v1.1 diagnostics | `scripts/run_pinn_inverse_v0_ablation.py`, `scripts/run_pinn_inverse_v1_experiments.py`, `scripts/run_pinn_inverse_v1_1_experiments.py` | `outputs/tables/pinn_inverse_v0_ablation_summary.json`, `outputs/tables/pinn_inverse_v1_summary.json`, `outputs/tables/pinn_inverse_v1_1_summary.json` | `docs/pinn_inverse_v0_ablation_report.md`, `docs/pinn_inverse_v1_report.md`, `docs/pinn_inverse_v1_1_report.md` | Figure 2 / Table 2 | Direct full hidden-field inverse training remains anchor-dependent and diagnostically weak | v1/v1.1 is a strict PDE-constrained inverse PINN or solves hidden-field recovery |
| Identifiability audit | `scripts/analyze_pinn_identifiability.py` | `outputs/tables/pinn_identifiability_summary.json`, `outputs/tables/pinn_identifiability_correlation.csv` | `docs/pinn_identifiability_audit_report.md` | Figure 3 | Port observables mainly constrain integrated conductance and do not uniquely identify full hidden fields | Sparse port data uniquely recover `delta_T`, `c_v`, `m`, and `sigma` |
| `gamma_sub` scalar identifiability | `scripts/scan_gamma_sub_identifiability.py`, `scripts/invert_gamma_sub_v0.py` | `outputs/tables/gamma_sub_identifiability_summary.json` | `docs/gamma_sub_identifiability_report.md` | Figure 4a / Table 3 | `gamma_sub` is recoverable in a fixed-microphysics scalar inverse setting | `gamma_sub` is identifiable under arbitrary released parameters |
| Confounding audit | `scripts/audit_gamma_sub_confounding.py`, `scripts/invert_gamma_sub_with_mismatch.py` | `outputs/tables/gamma_sub_confounding_summary.json`, `outputs/tables/gamma_sub_sensitivity_ranking.csv` | `docs/gamma_sub_confounding_report.md` | Figure 4b / Table 3 | `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` can confound `gamma_sub`, with `T_sw` the main risk | Model mismatch does not affect `gamma_sub` recovery |
| Literature-backed constrained inversion | `scripts/invert_gamma_sub_constrained.py`, `configs/gamma_sub_constrained_inversion.yaml` | `outputs/tables/gamma_sub_constrained_inversion_summary.json`, `outputs/tables/gamma_sub_prior_width_sweep.csv` | `docs/gamma_sub_constrained_inversion_report.md` | Figure 5 / Table 4 | `gamma_sub` can be used as a reduced inverse target under fixed or tightly bounded priors | The method recovers all material parameters jointly |
| Paper-readiness robustness | `scripts/audit_gamma_sub_paper_readiness.py` | `outputs/tables/gamma_sub_paper_readiness_summary.json`, `outputs/tables/gamma_sub_observation_sensitivity.csv`, `outputs/tables/gamma_sub_offgrid_summary.csv` | `docs/gamma_sub_paper_readiness_report.md` | Table 5 | Off-grid and observation-count checks support bounded robustness claims | Candidate-grid inclusion alone proves continuous identifiability |
| Continuous off-grid refinement | `scripts/refine_gamma_sub_continuous.py` | `outputs/tables/gamma_sub_continuous_refinement_summary.json`, `outputs/tables/gamma_sub_continuous_refinement_cases.csv` | `docs/gamma_sub_continuous_refinement_report.md` | Figure 6 / Table 6 | Re-simulated scalar continuous refinement reduces off-grid dependence in tested cases | The optimizer is a general multi-parameter inverse solver |
| Observability-augmented `gamma_sub` audit | `scripts/audit_gamma_sub_observability_augmented.py`, `configs/gamma_sub_observability_augmented.yaml` | `outputs/tables/gamma_sub_observability_augmented_summary.json`, `outputs/tables/gamma_sub_observability_augmented_cases.csv` | `docs/gamma_sub_observability_augmented_report.md` | Table 7 / Discussion | Narrowing `T_sw` prior reduces `gamma_sub` bias; sparse temperature anchors alone do not solve the tested wide-mismatch confounding | Minimal temperature anchors prove full hidden-field recovery or real experimental thermal validation |
| Multi-protocol/profile-likelihood validation | `scripts/audit_gamma_sub_multi_protocol_recoverability.py`, `scripts/audit_gamma_sub_tsw_profile_likelihood.py`, `scripts/audit_gamma_sub_joint_inversion_boundary.py`, `scripts/audit_gamma_sub_protocol_observability_design.py`, `scripts/build_gamma_sub_sci_validation_figures.py` | `outputs/tables/gamma_sub_multi_protocol_recoverability_summary.json`, `outputs/tables/gamma_sub_tsw_profile_likelihood_summary.json`, `outputs/tables/gamma_sub_joint_inversion_boundary_summary.json`, `outputs/tables/gamma_sub_protocol_observability_design_summary.json` | `docs/codex_reports/gamma_sub_multi_protocol_and_profile_likelihood_validation_report.md` | Figure 8 / Table 9 / Discussion | Multi-protocol checks, profile-likelihood ridge geometry, nuisance-release ambiguity, and protocol-design sensitivity strengthen conditional `gamma_sub` recoverability claims | Unconditional joint identifiability or protocol-independent recovery |
| SCI gap-closing validation pack | `scripts/audit_gamma_sub_auxiliary_observability_sweep.py`, `scripts/audit_gamma_sub_tsw_confounding_phase_map.py`, `scripts/audit_gamma_sub_tsw_prior_width_sweep.py`, `scripts/audit_gamma_sub_temperature_anchor_placement.py`, `scripts/compare_gamma_sub_scalar_baselines.py`, `scripts/build_gamma_sub_gap_closing_figures.py` | `outputs/tables/gamma_sub_auxiliary_observability_sweep_summary.json`, `outputs/tables/gamma_sub_auxiliary_observability_sweep_cases.csv`, `outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json`, `outputs/tables/gamma_sub_tsw_confounding_phase_map_cases.csv`, `outputs/tables/gamma_sub_tsw_prior_width_sweep_summary.json`, `outputs/tables/gamma_sub_temperature_anchor_placement_summary.json`, `outputs/tables/gamma_sub_scalar_baseline_comparison.csv` | `docs/codex_reports/gamma_sub_auxiliary_observability_sweep_report.md`, `docs/codex_reports/gamma_sub_tsw_confounding_phase_map_report.md`, `docs/codex_reports/gamma_sub_tsw_prior_width_sweep_report.md`, `docs/codex_reports/gamma_sub_temperature_anchor_placement_report.md`, `docs/codex_reports/gamma_sub_scalar_baseline_comparison_report.md` | Figure 7 / Table 8 / Discussion | The auxiliary sweep shows calibrated T_sw dominates wide-mismatch recovery; the T_sw phase map identifies recoverable regions; prior-width narrowing drives error reduction; anchor placement alone does not fix the bias; scalar baselines show optimizer novelty is not the claim | Unconditional `gamma_sub` identifiability or full hidden-field recovery |

## Appendix And Supplementary Evidence Table

| Evidence block | Files | Placement | Allowed use | Forbidden use |
| --- | --- | --- | --- | --- |
| v0/v1/v1.1 negative results | `docs/pinn_inverse_v0_ablation_report.md`, `docs/pinn_inverse_v1_report.md`, `docs/pinn_inverse_v1_1_report.md` | Supplementary ablation | Explain why target-space reduction is needed | Claim full hidden-field recovery |
| F-SPS-PINN architecture MVP | `docs/codex_reports/f_sps_pinn_architecture_mvp_report.md`, `src/pinnpcm/physics/vo2_constitutive.py`, `src/pinnpcm/pinn/network.py`, `src/pinnpcm/pinn/loss_balancer.py` | Appendix / future work | Show extensible architecture components | Claim validated device-level F-SPS-PINN performance |
| v2 smoke training | `docs/codex_reports/pinn_inverse_v2_f_sps_smoke_report.md`, `outputs/tables/pinn_inverse_v2_f_sps_smoke_summary.json` | Appendix | Show the white-box closure enters the train graph | Claim convergence or accuracy superiority |
| v2 small-run baseline | `docs/codex_reports/pinn_inverse_v2_f_sps_baseline_report.md`, `outputs/tables/pinn_inverse_v2_f_sps_baseline_summary.json`, `outputs/tables/pinn_inverse_v2_f_sps_baseline_runs.csv` | Appendix | Compare free-log-sigma and white-box closure under matched tiny budget | Claim formal benchmark superiority |
| v2 phase-transition stress preflight | `docs/codex_reports/pinn_inverse_v2_phase_transition_stress_report.md`, `outputs/tables/pinn_inverse_v2_phase_transition_stress_summary.json`, `outputs/tables/pinn_inverse_v2_phase_transition_stress_cases.csv` | Appendix / discussion | Show small-run numerical stability under synthetic stress cases | Claim solved phase-change stiffness |
| v2 Fourier on/off ablation | `docs/codex_reports/pinn_inverse_v2_fourier_ablation_report.md`, `outputs/tables/pinn_inverse_v2_fourier_ablation_summary.json`, `outputs/tables/pinn_inverse_v2_fourier_ablation_runs.csv` | Appendix / future work | Record that Fourier features are evaluable but not clearly better here | Claim F-SPS-PINN or Fourier superiority |

## Claim Boundary

Allowed claims:

- This is a synthetic numerical digital-twin benchmark.
- Sparse port data can constrain integrated conductance but not uniquely recover all hidden fields.
- Identifiability analysis motivates reducing the inverse target to `gamma_sub`.
- Constrained `gamma_sub` inversion is conditionally stable under fixed or tightly bounded priors.
- `T_sw` is the main confounder and must be independently fixed or tightly bounded.

Forbidden claims:

- measured experimental validation;
- real VO2/NbO2 device validation;
- complete three-dimensional device simulation;
- unique sparse-port full hidden-field recovery;
- unconstrained joint parameter identifiability;
- F-SPS-PINN or Fourier-feature performance superiority from current small-run evidence.

## Figure Priority

Main text priority:

1. Ground Truth v1.1 benchmark and hysteresis.
2. Identifiability/correlation evidence showing full hidden-field ill-posedness.
3. Constrained `gamma_sub` inversion and objective profile.
4. Confounding and prior-width sensitivity, with `T_sw` highlighted through the two-dimensional phase map.
5. Off-grid continuous refinement and observation/noise sensitivity.
6. Observability-augmented `gamma_sub` audit showing that independent `T_sw` calibration is more decisive than sparse temperature anchors alone in the current candidate-grid test.
7. Multi-protocol/profile-likelihood validation showing generalization limits, objective ridge geometry, nuisance-release boundary, and protocol-design guidance.

Supplementary priority:

1. v0/v1/v1.1 diagnostic tables.
2. F-SPS-PINN v2 smoke summary.
3. v2 free-log-sigma versus white-box `vo2_sigma` baseline.
4. v2 phase-transition stress preflight.
5. v2 Fourier on/off ablation.

## Manuscript Direction

The fastest route to a high-quality SCI manuscript is to stop expanding F-SPS-PINN experiments for now and write a focused paper on sparse-port inverse identifiability, target-space reduction, and constrained `gamma_sub` inversion. F-SPS-PINN can strengthen the discussion as a future architecture for better physics closures, but it is not the current main result.

## High-Throughput Pack Addendum

| Evidence block | Script/config | Summary file | Report file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- | --- |
| Dense gamma_sub/T_sw profile and recoverability phase diagram | `scripts/audit_gamma_sub_tsw_dense_profile_likelihood.py`, `scripts/audit_gamma_sub_recoverability_phase_diagram.py` | `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_summary.json`, `outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json` | `docs/codex_reports/gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md` | Figure 9 / Table 10 | Response-surface evidence maps recoverable and non-recoverable regions for constrained `gamma_sub` under bounded `T_sw` priors | This is not thousands of fresh ODE solves and not proof of unconditional joint identifiability |
| Protocol actual-validation and weighted objective | `scripts/audit_gamma_sub_protocol_actual_inversion_validation.py`, `scripts/audit_gamma_sub_weighted_protocol_objective.py` | `outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json`, `outputs/tables/gamma_sub_weighted_protocol_objective_summary.json` | `docs/codex_reports/gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md` | Figure 10 / Supplementary Table | Protocol choice affects constrained gamma_sub robustness; weighted combinations must beat best single-protocol evidence before being claimed useful | Multi-protocol weighting is not automatically superior |
| Bootstrap/noise/seed robustness | `scripts/audit_gamma_sub_statistical_robustness.py` | `outputs/tables/gamma_sub_statistical_robustness_summary.json` | `docs/codex_reports/gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md` | Figure 11 / Supplementary Table | Nominal/narrow-prior cases are more stable than wide T_sw mismatch across seeds/noise | Robustness under wide unknown priors or real measurement noise |
| F-SPS medium-budget planning benchmark | `scripts/train_f_sps_medium_budget_benchmark.py`, `configs/f_sps_medium_budget_benchmark.yaml` | `outputs/tables/f_sps_medium_budget_benchmark_summary.json`, `outputs/tables/f_sps_medium_budget_benchmark_cases.csv` | `docs/codex_reports/gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md` | Appendix table | White-box VO2/Fourier/F-SPS training paths are executable in a bounded CPU matrix | F-SPS-PINN performance superiority |

## Response-Surface Verification And Claim Consolidation Addendum

| Evidence block | Script/config | Summary file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- |
| Response-surface anchor verification | `scripts/audit_gamma_sub_response_surface_anchor_verification.py`, `configs/gamma_sub_response_surface_anchor_verification.yaml` | `outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json`, `outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv` | Figure 4 / Table 5 | Response-surface phase diagrams are acceptable manuscript evidence only with explicit qualification and anchor checks | All 2501 dense profile points are new simulator-backed ODE solves |
| Sequential protocol design preflight | `scripts/audit_gamma_sub_sequential_protocol_design.py`, `configs/gamma_sub_sequential_protocol_design.yaml` | `outputs/tables/gamma_sub_sequential_protocol_design_summary.json`, `outputs/tables/gamma_sub_sequential_protocol_design_cases.csv` | Figure 5 / Table 6 | Sequential protocol design is a promising response-surface hypothesis for shrinking the `gamma_sub`/`T_sw` ridge | The sequence is experimentally validated or guaranteed to outperform in real devices |
| Balanced F-SPS medium-budget benchmark | `scripts/train_f_sps_balanced_medium_budget_benchmark.py`, `configs/f_sps_balanced_medium_budget_benchmark.yaml` | `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json`, `outputs/tables/f_sps_balanced_medium_budget_benchmark_cases.csv` | Appendix Figure A1 / Supplementary Table S1 | F-SPS paths are executable under balanced coverage | F-SPS-PINN is superior to free-log-sigma or white-box Fourier baselines |
| Manuscript claim stress test | `scripts/build_manuscript_claim_stress_test.py` | `outputs/tables/manuscript_claim_stress_test_summary.json`, `docs/paper/claim_stress_test_matrix.md` | Supplementary Table S2 | Each manuscript claim is bound to supporting evidence, limitations, and forbidden overclaims | Synthetic benchmark evidence is experimental validation |
## Literature-Anchored Calibration Addendum

| Evidence block | Script/config | Summary file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- |
| Literature parameter sanity | `scripts/audit_literature_phase_change_parameter_sanity.py`, `configs/literature_phase_change_parameter_sanity.yaml` | `outputs/tables/literature_phase_change_parameter_sanity_summary.json`, `data/literature/literature_parameter_sanity_table.csv` | Table 3 / Supplementary Table | Literature and engineering priors are plausible anchors for a synthetic benchmark | Literature values are measured parameters of the simulated device |
| External curve-fit template | `scripts/fit_literature_phase_change_curves.py`, `configs/literature_curve_fit_external_anchor.yaml` | `outputs/tables/literature_curve_fit_external_anchor_summary.json` | Data provenance note | No external curve was fabricated; fitting is blocked until provenance-backed digitized data are added | Public curves were fit when no digitized numerical data exist |
| T_sw calibration necessity | `scripts/audit_gamma_sub_tsw_calibration_necessity.py` | `outputs/tables/gamma_sub_tsw_calibration_necessity_summary.json` | Figure 5 / Table 4 | T_sw must be independently calibrated or tightly bounded | gamma_sub is stable under arbitrary T_sw uncertainty |
| Simulator-backed sequential validation | `scripts/audit_gamma_sub_simulator_backed_sequential_protocol_validation.py` | `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json` | Figure 5 / Table 5 | `multi_pulse_to_ltp_ltd` remains the best tested synthetic sequential candidate | The protocol is experimentally validated or guaranteed for real devices |

## External Curve Ingestion And Calibrated Gamma_Sub Addendum

| Evidence block | Script/config | Summary file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- |
| Literature curve ingestion v2 | `scripts/ingest_literature_digitized_curves.py`, `configs/literature_curve_ingestion.yaml` | `outputs/tables/literature_curve_ingestion_summary.json` | Data provenance note | No provenance-backed digitized curves are currently available; fitting is blocked rather than fabricated | Public curves were fit without digitized data |
| External curve fit v2 | `scripts/fit_literature_phase_change_curves_v2.py`, `configs/literature_curve_fit_external_anchor_v2.yaml` | `outputs/tables/literature_curve_fit_external_anchor_v2_summary.json` | Supplementary provenance status | External anchors can be added once proper CSV curves exist | Literature curves validate `gamma_sub` inversion |
| T_sw calibration workflow | `scripts/audit_gamma_sub_tsw_calibration_workflow.py` | `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json` | Figure 2 / Table 4 | Calibration before inversion reduces synthetic `gamma_sub` error under bounded priors | Unconstrained joint recovery of `T_sw` and `gamma_sub` |
| Calibrated sequential protocol validation | `scripts/audit_gamma_sub_calibrated_sequential_protocol_validation.py` | `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json` | Figure 5 / Table 5 | `calibrated_multi_pulse_to_ltp_ltd` is the strongest current synthetic ODE-backed protocol candidate | Experimentally validated stimulation protocol |

