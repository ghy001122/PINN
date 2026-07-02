# File inventory

## Response-surface verification and manuscript claim consolidation files

- `configs\gamma_sub_response_surface_anchor_verification.yaml`: anchor-verification config.
- `scripts\audit_gamma_sub_response_surface_anchor_verification.py`: compares response-surface predictions with simulator-backed source-grid and phase-map anchors.
- `tests\test_gamma_sub_response_surface_anchor_verification.py`: config and smoke/schema test.
- `configs\gamma_sub_sequential_protocol_design.yaml`: sequential protocol-design preflight config.
- `scripts\audit_gamma_sub_sequential_protocol_design.py`: value-of-information preflight runner.
- `tests\test_gamma_sub_sequential_protocol_design.py`: config and smoke/schema test.
- `configs\f_sps_balanced_medium_budget_benchmark.yaml`: balanced F-SPS medium-budget benchmark config.
- `scripts\train_f_sps_balanced_medium_budget_benchmark.py`: balanced F-SPS runner that reuses v2 baseline utilities.
- `tests\test_f_sps_balanced_medium_budget_benchmark.py`: balanced coverage, finite metric, and frozen-input test.
- `scripts\build_manuscript_claim_stress_test.py`: writes claim stress-test Markdown and summary JSON.
- `tests\test_manuscript_claim_stress_test.py`: claim matrix smoke test.
- `scripts\build_manuscript_ready_gamma_sub_figures.py`: builds ignored figure-ready PNGs from lightweight tables.
- `docs\paper\claim_stress_test_matrix.md`: claim/evidence/limitation/forbidden-overclaim matrix.
- `docs\paper\proposed_main_figures.md`: main-figure routing plan.
- `docs\paper\proposed_tables.md`: table routing plan.
- `docs\paper\manuscript_outline_v1.md`: manuscript outline and claim boundary.
- `docs\codex_reports\gamma_sub_response_surface_verification_and_manuscript_claim_consolidation_report.md`: final task report.


## Low-token Codex context workflow

- `CODEX_CONTEXT.md`: first-read project context for non-trivial Codex tasks.
- `docs\research_strategy\active_phase.md`: current authorized phase,
  currently SCI manuscript evidence consolidation.
- `docs\research_strategy\context_loading_policy.md`: Tier 0 through Tier 4
  context-loading rules.
- `docs\research_strategy\context_index.md`: quick routing index for context
  files, registries, and reports.
- `docs\research_strategy\current_research_handoff.md`: concise handoff from
  GT v1.1 through v0/v1/v1.1 and the `gamma_sub` audits.
- `docs\research_strategy\codex_workflow_rules.md`: workflow, research,
  engineering, and verification rules.
- `docs\research_strategy\next_task_literature_backed_constrained_gamma_sub.md`:
  prepared next-task scaffold, not executed in the context-integration task.

## Literature and reference routing

- `docs\literature_notes\pinn_phase_change_literature_digest.md`: compressed
  local notes on PINN, phase-transition, memristor, and surrogate references.
- `docs\literature_notes\gamma_sub_evidence_digest.md`: compressed rationale
  for reduced `gamma_sub` inversion and confounding limits.
- `references\project_sources\README.md`: local reference-pack provenance and
  non-copy policy.
- `references\papers\PAPER_REGISTRY.md`: compact paper routing registry.

## Core package

- `src\pinnpcm\physics\`: Ground Truth physics, electrostatics, conductivity,
  parameters, and voltage protocols.
- `src\pinnpcm\pinn\`: PINN skeleton plus inverse v0 data loading, model,
  losses, and residual utilities.
- `src\pinnpcm\utils\`: YAML, JSON, path, and seed helpers.
- `src\pinnpcm\visualization\`: plotting helpers.


## High-throughput gamma_sub and F-SPS medium-budget files

- `configs\gamma_sub_tsw_dense_profile_likelihood.yaml`: dense response-surface profile-likelihood config.
- `configs\gamma_sub_recoverability_phase_diagram.yaml`: high-throughput recoverability phase-diagram config.
- `configs\gamma_sub_protocol_actual_inversion_validation.yaml`: protocol actual-validation config.
- `configs\gamma_sub_weighted_protocol_objective.yaml`: weighted protocol objective config.
- `configs\gamma_sub_statistical_robustness.yaml`: bootstrap/noise/seed robustness config.
- `configs\f_sps_medium_budget_benchmark.yaml`: bounded F-SPS medium-budget planning config.
- `scripts\gamma_sub_high_throughput_common.py`: shared response-surface helpers.
- `scripts\audit_gamma_sub_tsw_dense_profile_likelihood.py`: dense profile-likelihood response-surface audit.
- `scripts\audit_gamma_sub_recoverability_phase_diagram.py`: recoverability phase-diagram audit.
- `scripts\audit_gamma_sub_protocol_actual_inversion_validation.py`: protocol actual-validation audit.
- `scripts\audit_gamma_sub_weighted_protocol_objective.py`: weighted protocol objective audit.
- `scripts\audit_gamma_sub_statistical_robustness.py`: bootstrap/noise/seed robustness audit.
- `scripts\train_f_sps_medium_budget_benchmark.py`: bounded F-SPS medium-budget planning benchmark.
- `scripts\build_high_throughput_sci_figures.py`: figure-ready plot builder for the high-throughput pack.
- `tests\test_gamma_sub_tsw_dense_profile_likelihood.py`, `tests\test_gamma_sub_recoverability_phase_diagram.py`, `tests\test_gamma_sub_protocol_actual_inversion_validation.py`, `tests\test_gamma_sub_weighted_protocol_objective.py`, `tests\test_gamma_sub_statistical_robustness.py`, `tests\test_f_sps_medium_budget_benchmark.py`: schema/smoke/frozen-input tests for this pack.
## Current PINN inverse v0 files

- `src\pinnpcm\pinn\data.py`: loads frozen Ground Truth data, sparse
  observations, and manifest metadata.
- `src\pinnpcm\pinn\models.py`: constrained neural field model for `c_v`,
  `delta_T`, `m`, and positive surrogate `sigma`.
- `src\pinnpcm\pinn\losses.py`: series port reconstruction, normalized MSE,
  smoothness, and light feasibility losses.
- `src\pinnpcm\pinn\physics_residuals.py`: autograd-based v1 heat, state,
  defect, sigma-consistency, and boundary residuals.
- `scripts\train_pinn_inverse_v0.py`: single-run training entry point.
- `scripts\run_pinn_inverse_v0_ablation.py`: three-run ablation audit runner.
  It also supports `--smoke-test`, which runs one epoch per ablation in ignored
  smoke-test output directories without overwriting the official ablation
  summary.
- `scripts\train_pinn_inverse_v1.py`: single-run v1 physics-regularized
  training entry point.
- `scripts\run_pinn_inverse_v1_experiments.py`: three-run v1 experiment runner.
- `scripts\run_pinn_inverse_v1_1_experiments.py`: two-run v1.1
  residual-balancing experiment runner.
- `scripts\analyze_pinn_identifiability.py`: reads the frozen triangle
  benchmark and computes terminal-to-hidden-field correlations, hidden-field
  correlations, lag correlations, and spatial sensitivity profiles.
- `scripts\scan_gamma_sub_identifiability.py`: scans fixed-microphysics
  `gamma_sub` values and writes port/thermal sensitivity evidence.
- `scripts\invert_gamma_sub_v0.py`: optimizes only `gamma_sub` with
  finite-difference Adam plus L-BFGS-B using terminal `G/I` loss and a
  candidate heat-residual regularizer.
- `scripts\audit_gamma_sub_confounding.py`: perturbs `gamma_sub`, `T_sw`,
  `tau_m`, `sigma_on0`, and `eta_A` to rank response sensitivity and
  confounding directions.
- `scripts\invert_gamma_sub_with_mismatch.py`: generates mismatched synthetic
  targets and then optimizes only `gamma_sub` with nominal fixed parameters to
  quantify systematic bias.
- `scripts\invert_gamma_sub_constrained.py`: performs the literature-backed constrained reduced inverse audit with `gamma_sub` as the only primary inverse target and bounded `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` confounders.
- `scripts\audit_gamma_sub_paper_readiness.py`: runs off-grid `gamma_sub` and
  observation-count robustness checks for paper-readiness defense.
- `scripts\refine_gamma_sub_continuous.py`: performs simulator-backed continuous scalar refinement for off-grid `gamma_sub`, with true off-grid cases, observation-count sensitivity, and noise sensitivity.
- `configs\gamma_sub_observability_augmented.yaml`: config for the lightweight observability-augmented `gamma_sub` audit.
- `scripts\audit_gamma_sub_observability_augmented.py`: tests sparse synthetic temperature anchors and narrowed `T_sw` prior width for reducing `gamma_sub` / `T_sw` confounding.
- `configs\gamma_sub_tsw_prior_width_sweep.yaml`: config for T_sw prior-width trend audit.
- `scripts\audit_gamma_sub_tsw_prior_width_sweep.py`: scans T_sw prior width while estimating only `gamma_sub`.
- `configs\gamma_sub_temperature_anchor_placement.yaml`: config for temperature-anchor placement audit.
- `scripts\audit_gamma_sub_temperature_anchor_placement.py`: compares uniform, random, and high-gradient synthetic temperature anchors.
- `scripts\compare_gamma_sub_scalar_baselines.py`: compares candidate-grid search, continuous scalar least-squares refinement, and the constrained gamma_sub workflow.
- `configs\gamma_sub_tsw_confounding_phase_map.yaml`: config for the two-dimensional `T_sw_delta_K` by `T_sw_prior_width` phase-map audit.
- `scripts\audit_gamma_sub_tsw_confounding_phase_map.py`: scans the T_sw confounding phase map while estimating only `gamma_sub`.
- `scripts\build_gamma_sub_gap_closing_figures.py`: builds reproducible figure-ready PNGs from gap-closing JSON/CSV evidence.
- `configs\gamma_sub_multi_protocol_recoverability.yaml`: config for multi-protocol `gamma_sub` recoverability audit.
- `scripts\audit_gamma_sub_multi_protocol_recoverability.py`: compares triangle, LTP/LTD, derived multi-amplitude synthetic, and mixed-protocol objectives while estimating only `gamma_sub`.
- `configs\gamma_sub_tsw_profile_likelihood.yaml`: config for `gamma_sub` by `T_sw` profile-likelihood landscape.
- `scripts\audit_gamma_sub_tsw_profile_likelihood.py`: scans the port-objective landscape and extracts ridge/condition-number diagnostics.
- `configs\gamma_sub_joint_inversion_boundary.yaml`: config for nuisance-release boundary audit.
- `scripts\audit_gamma_sub_joint_inversion_boundary.py`: releases `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` in lightweight candidate grids to quantify ambiguity.
- `configs\gamma_sub_protocol_observability_design.yaml`: config for candidate stimulation protocol sensitivity design.
- `scripts\audit_gamma_sub_protocol_observability_design.py`: ranks candidate protocols by `gamma_sub` sensitivity and `T_sw` sensitivity alignment.
- `scripts\gamma_sub_validation_common.py`: shared helpers for lightweight `gamma_sub` validation audits.
- `scripts\build_gamma_sub_sci_validation_figures.py`: builds figure-ready PNGs from the new JSON/CSV evidence.
- `tests\test_gamma_sub_multi_protocol_recoverability.py`, `tests\test_gamma_sub_tsw_profile_likelihood.py`, `tests\test_gamma_sub_joint_inversion_boundary.py`, `tests\test_gamma_sub_protocol_observability_design.py`: smoke and schema tests for the new audits.
- `configs\gamma_sub_auxiliary_observability_sweep.yaml`: config for auxiliary observability modes under controlled `T_sw` mismatch.
- `scripts\audit_gamma_sub_auxiliary_observability_sweep.py`: compares synthetic auxiliary information channels while estimating only `gamma_sub`.
- `configs\pinn_inverse_v2_f_sps_smoke.yaml`: v2 smoke config for a short CPU training loop using white-box `vo2_sigma`.
- `scripts\train_pinn_inverse_v2_smoke.py`: minimal F-SPS-PINN v2 smoke trainer; predicts `T`, `c_v`, and `m`, computes `sigma` through `vo2_sigma`, and writes a lightweight summary JSON.
- `configs\pinn_inverse_v2_f_sps_baseline.yaml`: small-run baseline config comparing `free_log_sigma` and `white_box_vo2_sigma`.
- `scripts\run_pinn_inverse_v2_baseline.py`: matched small-run baseline runner that writes JSON/CSV evidence without modifying frozen GT or old v0/v1/v1.1 paths.
- `configs\pinn_inverse_v2_phase_transition_stress.yaml`: stress-preflight config for mild, sharp, near-threshold, and high-contrast VO2 closure cases.
- `scripts\run_pinn_inverse_v2_phase_transition_stress.py`: reuses v2 baseline utilities to run phase-transition stress cases and write lightweight JSON/CSV evidence.
- `configs\pinn_inverse_v2_fourier_ablation.yaml`: Fourier on/off ablation config under the sharp-transition VO2 closure stress case.
- `scripts\run_pinn_inverse_v2_fourier_ablation.py`: reuses v2 baseline utilities to compare Fourier-off and Fourier-on runs and write lightweight JSON/CSV evidence.

## Current test coverage

- 	ests\test_gamma_sub_tsw_dense_profile_likelihood.py, 	ests\test_gamma_sub_recoverability_phase_diagram.py, 	ests\test_gamma_sub_protocol_actual_inversion_validation.py, 	ests\test_gamma_sub_weighted_protocol_objective.py, 	ests\test_gamma_sub_statistical_robustness.py, and 	ests\test_f_sps_medium_budget_benchmark.py: check the high-throughput gamma_sub and F-SPS medium-budget configs, finite outputs, schema fields, and frozen input preservation where relevant.

- `tests\test_pinn_inverse_v0.py`: data loading, model forward, conductance
  reconstruction, single-run smoke test, ablation config checks, ablation smoke
  test, and nRMSE metrics checks.
- `tests\test_pinn_inverse_v1.py`: v1 config checks, physics residual finite
  checks, autograd derivative checks, and v1 training smoke test.
- `tests\test_pinn_identifiability.py`: identifiability analyzer output smoke
  test using temporary table and figure directories.
- `tests\test_gamma_sub_identifiability.py`: smoke tests for the gamma_sub scan,
  single-parameter inversion, confounding audit, and mismatch inversion scripts
  using reduced temporary outputs.
- `tests\test_gamma_sub_constrained.py`: verifies the constrained gamma_sub config scope and runs a reduced smoke test with temporary JSON/CSV outputs.
- `tests\test_gamma_sub_paper_readiness.py`: checks paper docs, paper-readiness
  schema, finite off-grid and observation-sensitivity outputs, and frozen GT
  hash preservation.
- `tests\test_gamma_sub_continuous_refinement.py`: checks continuous-refinement summary schema, finite outputs, off-grid truth exclusion, simulator-backed non-grid evaluations, and frozen GT hash preservation.
- `tests\test_gamma_sub_observability_augmented.py`: checks observability-augmented config scope, smoke execution, finite outputs, mode coverage, and frozen GT hash preservation.
- `tests\test_gamma_sub_tsw_prior_width_sweep.py`: checks prior-width config scope, finite trend outputs, and frozen GT hash preservation.
- `tests\test_gamma_sub_temperature_anchor_placement.py`: checks placement modes, finite outputs, and frozen GT hash preservation.
- `tests\test_gamma_sub_scalar_baselines.py`: checks scalar baseline comparison outputs and frozen GT hash preservation.
- `tests\test_gamma_sub_tsw_confounding_phase_map.py`: checks phase-map config scope, finite outputs, recoverability fields, matrix schema, and frozen GT hash preservation.
- `tests\test_gamma_sub_auxiliary_observability_sweep.py`: checks auxiliary-observability config scope, finite outputs, mode coverage, calibrated-`T_sw` coverage, and frozen GT hash preservation.
- `tests\test_gamma_sub_multi_protocol_recoverability.py`, `tests\test_gamma_sub_tsw_profile_likelihood.py`, `tests\test_gamma_sub_joint_inversion_boundary.py`, and `tests\test_gamma_sub_protocol_observability_design.py`: check config scope, finite outputs, schema fields, and frozen GT hash preservation for the SCI validation pack.
- `tests\test_vo2_constitutive.py`: checks VO2-like conductivity positivity, differentiability, finite extreme-temperature behavior, and Bruggeman safeguards.
- `tests\test_fourier_pyramid.py`: checks Fourier pyramid shape and differentiability.
- `tests\test_loss_balancer.py`: checks dynamic residual gate normalization, differentiability, and anti-collapse behavior.
- `tests\test_oscillation_metrics.py`: checks differentiable spectral and pulse metrics, including zero-signal backward stability.
- `tests\test_pinn_inverse_v2_smoke.py`: checks v2 smoke config/script execution, summary JSON, VO2 sigma use, no free `log_sigma`, and frozen input hash/mtime preservation.
- `tests\test_pinn_inverse_v2_baseline.py`: checks v2 baseline config/script execution, summary JSON/CSV, mode flags, finite metrics, and frozen input hash/mtime preservation.
- `tests\test_pinn_inverse_v2_phase_transition_stress.py`: checks stress config/script execution, summary JSON/CSV schema, finite metrics, mode flags, and frozen input hash/mtime preservation.
- `tests\test_pinn_inverse_v2_fourier_ablation.py`: checks Fourier ablation config/script execution, summary JSON/CSV schema, finite metrics, mode flags, and frozen input hash/mtime preservation.

## Evidence-chain reports

- docs\codex_reports\gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md: final Codex report for the high-throughput gamma_sub identifiability and F-SPS medium-budget pack.

- `docs\paper\sci_manuscript_evidence_matrix.md`: manuscript-ready evidence matrix that maps existing synthetic numerical benchmark results to main-text claims, appendix evidence, proposed figures/tables, allowed claims, and forbidden overclaims.
- `docs\codex_reports\sci_manuscript_evidence_consolidation_report.md`: final Codex report for the documentation-only manuscript evidence consolidation task.
- `docs\gamma_sub_observability_augmented_report.md`: project-facing report for sparse temperature-anchor and narrowed-`T_sw` prior observability audit.
- `docs\codex_reports\gamma_sub_observability_augmented_report.md`: Codex report for the observability-augmented `gamma_sub` audit.
- `docs\codex_reports\gamma_sub_tsw_prior_width_sweep_report.md`: Codex report for T_sw prior-width trend audit.
- `docs\codex_reports\gamma_sub_temperature_anchor_placement_report.md`: Codex report for anchor-placement audit.
- `docs\codex_reports\gamma_sub_scalar_baseline_comparison_report.md`: Codex report for scalar baseline comparison.
- `docs\codex_reports\gamma_sub_tsw_confounding_phase_map_report.md`: Codex report for the two-dimensional T_sw confounding phase-map audit.
- `docs\codex_reports\gamma_sub_auxiliary_observability_sweep_report.md`: Codex report for the auxiliary-observability sweep.
- `docs\codex_reports\gamma_sub_multi_protocol_and_profile_likelihood_validation_report.md`: Codex report for the multi-protocol, profile-likelihood, joint-boundary, and protocol-design validation pack.
- `docs\paper\model_hierarchy_and_claim_boundary.md`: paper-defense hierarchy,
  included/excluded physics, and allowed/forbidden claims.
- `docs\paper\equation_variable_registry.md`: variable units and equation
  registry for electrical, thermal, defect, switching, conductivity, and port
  relations.
- `docs\paper\experiment_to_figure_mapping.md`: maps GT, v0/v1/v1.1,
  identifiability, confounding, constrained inversion, and paper-readiness
  evidence to manuscript sections and candidate figures/tables.
- `docs\gamma_sub_paper_readiness_report.md`: project-facing robustness report
  for off-grid and observation-count checks.
- `docs\codex_reports\gamma_sub_paper_readiness_report.md`: final Codex report
  for this paper-readiness task.
- `docs\gamma_sub_continuous_refinement_report.md`: project-facing report for simulator-backed continuous off-grid `gamma_sub` refinement.
- `docs\codex_reports\gamma_sub_continuous_refinement_report.md`: final Codex report for the continuous off-grid `gamma_sub` refinement audit.
- `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md`: main ablation
  audit report for commit `ffad313297c78cfc158e6ae270c3b86639d79e1d`.
- `docs\codex_reports\evidence_chain_patch_report.md`: evidence-chain patch
  report for state-file consistency and smoke-test verification.
- `docs\codex_reports\pinn_inverse_v1_physics_report.md`: final Codex report
  for the v1 physics-regularized implementation and experiment run.
- `docs\codex_reports\pinn_inverse_v1_1_report.md`: final Codex report for
  the v1.1 residual-balancing audit.
- `docs\codex_reports\pinn_identifiability_audit_report.md`: final Codex
  report for the terminal-observation identifiability audit.
- `docs\pinn_identifiability_audit_report.md`: project-facing report that
  explains why terminal-only observations do not uniquely recover all hidden
  fields.
- `docs\gamma_sub_identifiability_report.md`: project-facing report for the
  reduced `gamma_sub` inverse audit.
- `docs\codex_reports\gamma_sub_identifiability_audit_report.md`: final Codex
  report for the `gamma_sub` identifiability patch.
- `docs\gamma_sub_confounding_report.md`: project-facing report for the
  `gamma_sub` robustness and mismatch audit.
- `docs\codex_reports\gamma_sub_confounding_audit_report.md`: final Codex
  report for the `gamma_sub` confounding patch.
- `docs\codex_reports\local_codex_context_integration_report.md`: final Codex
  report for the local reference-pack and low-token workflow integration.
- `docs\codex_reports\documentation_structure_cleanup_report.md`: final Codex
  report for Markdown deduplication and context-integration verification.
- `docs\literature_gamma_sub_evidence_chain.md`: literature and engineering-prior evidence chain for the constrained gamma_sub reduced inverse target.
- `docs\parameter_prior_registry.md`: prior table for gamma_sub and bounded confounders.
- `docs\gamma_sub_constrained_inversion_report.md`: project-facing constrained gamma_sub inversion report.
- `docs\codex_reports\gamma_sub_constrained_inversion_report.md`: final Codex report for this constrained inversion task.
- `docs\codex_reports\f_sps_pinn_architecture_mvp_report.md`: final Codex report for the isolated F-SPS-PINN architecture MVP.
- `docs\codex_reports\pinn_inverse_v2_f_sps_smoke_report.md`: final Codex report for the v2 smoke training pipeline.
- `docs\codex_reports\pinn_inverse_v2_f_sps_baseline_report.md`: final Codex report for the v2 small-run baseline.
- `docs\codex_reports\pinn_inverse_v2_phase_transition_stress_report.md`: final Codex report for the v2 phase-transition stress preflight.
- `docs\codex_reports\pinn_inverse_v2_fourier_ablation_report.md`: final Codex report for the v2 Fourier on/off ablation.

## Frozen files not to modify during PINN audit

- `configs\gt_v1_acceptance_triangle.yaml`
- `configs\gt_v1_acceptance_ltp_ltd.yaml`
- `docs\gt_v1_acceptance_report.md`
- `data\processed\gt_v1_acceptance\manifest.json`
- Ground Truth equations and default Ground Truth parameters.
## Literature-Anchored Gamma_Sub Pack Files

Configs:

- `configs/literature_phase_change_parameter_sanity.yaml`
- `configs/literature_curve_fit_external_anchor.yaml`
- `configs/gamma_sub_tsw_calibration_necessity.yaml`
- `configs/gamma_sub_simulator_backed_sequential_protocol_validation.yaml`

Scripts:

- `scripts/audit_literature_phase_change_parameter_sanity.py`
- `scripts/fit_literature_phase_change_curves.py`
- `scripts/audit_gamma_sub_tsw_calibration_necessity.py`
- `scripts/audit_gamma_sub_simulator_backed_sequential_protocol_validation.py`
- `scripts/build_manuscript_style_gamma_sub_figures.py`

Tests:

- `tests/test_literature_phase_change_parameter_sanity.py`
- `tests/test_literature_curve_fit_external_anchor.py`
- `tests/test_gamma_sub_tsw_calibration_necessity.py`
- `tests/test_gamma_sub_simulator_backed_sequential_protocol_validation.py`

Docs/data:

- `docs/literature/literature_parameter_sanity_notes.md`
- `docs/literature/literature_curve_fit_notes.md`
- `data/literature/literature_parameter_sanity_table.csv`
- `data/literature/literature_curve_registry.csv`
- `docs/paper/main_figure_captions_v1.md`
- `docs/paper/supplementary_figure_captions_v1.md`
- `docs/paper/table_captions_v1.md`
- `docs/paper/visual_style_guide.md`

## External Curve Ingestion And Calibrated Gamma_Sub Workflow Files

- Ingestion config: `configs/literature_curve_ingestion.yaml`
- Ingestion script: `scripts/ingest_literature_digitized_curves.py`
- Ingestion test: `tests/test_literature_curve_ingestion.py`
- External fit v2 config: `configs/literature_curve_fit_external_anchor_v2.yaml`
- External fit v2 script: `scripts/fit_literature_phase_change_curves_v2.py`
- External fit v2 test: `tests/test_literature_curve_fit_external_anchor_v2.py`
- T_sw calibration workflow config: `configs/gamma_sub_tsw_calibration_workflow.yaml`
- T_sw calibration workflow script: `scripts/audit_gamma_sub_tsw_calibration_workflow.py`
- T_sw calibration workflow test: `tests/test_gamma_sub_tsw_calibration_workflow.py`
- Calibrated sequential protocol config: `configs/gamma_sub_calibrated_sequential_protocol_validation.yaml`
- Calibrated sequential protocol script: `scripts/audit_gamma_sub_calibrated_sequential_protocol_validation.py`
- Calibrated sequential protocol test: `tests/test_gamma_sub_calibrated_sequential_protocol_validation.py`
- Claim stress builder: `scripts/build_external_anchor_claim_stress_test.py`
- Claim stress test: `tests/test_external_anchor_claim_stress_test.py`
- Figure/text builder: `scripts/build_submission_ready_gamma_sub_figures.py`
- Outputs: `outputs/tables/literature_curve_ingestion_summary.json`, `outputs/tables/literature_curve_ingestion_cases.csv`, `outputs/tables/literature_curve_fit_external_anchor_v2_summary.json`, `outputs/tables/literature_curve_fit_external_anchor_v2_cases.csv`, `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json`, `outputs/tables/gamma_sub_tsw_calibration_workflow_cases.csv`, `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json`, `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_cases.csv`, `outputs/tables/external_anchor_claim_stress_test_summary.json`, `outputs/tables/submission_ready_gamma_sub_figures_summary.json`
- Reports: `docs/gamma_sub_tsw_calibration_workflow_report.md`, `docs/gamma_sub_calibrated_sequential_protocol_validation_report.md`, `docs/codex_reports/external_curve_ingestion_and_calibration_workflow_manuscript_report.md`

Status: completed as synthetic numerical digital-twin manuscript-defense evidence. It does not modify frozen Ground Truth and does not claim experimental validation.

