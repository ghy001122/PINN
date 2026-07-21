# Experiment Registry — Cumulative Historical Index

> Do not load by default. Current claim/evidence routing is `docs/project_state/current_evidence_index.md`; use this file only to trace a named historical run.

## E1F/E1F-R Qiu author compact audit (2026-07-21)

- Original task: `Q2_E1F_QIU_AUTHOR_MODEL_EXTERNAL_ANCHOR_AND_BRIDGE_AUDIT`;
  preregistration commit `783f41ec2ddd01f055ac34e6424c403082132fdc`;
  preserved invalid-result commit `5e75cbfae505b801956df89bfce4a3c76989f659`.
- A post-run source/figure audit found two vote-invalidating defects: SI Eq. S3
  used an unreported `atanh`, and main Fig. 2b extraction captured blue/black
  legend strokes. The original six-integration artifact is therefore
  `implementation_contract_invalid`; none of its curve errors is a vote.
- Corrective task: `Q2_E1FR_QIU_SOURCE_EQUATION_CORRECTION`; preregistration
  commit `3792eb8d77cb1acab8644ea4a4a0a2a4d4552b2b`. It kept parameters,
  12 V SI Fig. S1, time interval, metric, and `0.10` gate unchanged, implemented
  literal printed Eq. S3, and did not simulate or score Fig. 2b.
- Formal execution `1/1` used two forward integrations. DOP853/Radau parity
  passed with worst waveform NRMSE `2.23216159e-07`; activity class, event
  count, and event-type sequence agreed.
- The corrected 12 V setting gate failed: current/voltage NRMSE were
  `0.353154`/`0.815643`; favorable envelope scores `0.320963/0.732598` also
  exceed `0.10`. Status is `failed_but_informative`; the conditional effective-
  coordinate preflight was not run.
- Main Fig. 2b remains `implementation_contract_invalid/unassessed`, not a
  holdout vote and not independent external validation. No refit, replacement
  curve, inverse, PINN training, or reduced-identifiability claim is authorized.
- The read-only source-to-PDE audit records resistance, thermal-capacitance,
  thermal-conductance, and timescale mismatch ratios of `2.330233`, `635.5145`,
  `206`, and `3.085022`. It refuses direct lumped-to-local parameter transfer
  and does not authorize another M40/M40R repair.
- M40/M40R and frozen GT hashes were reverified without rerunning either 2D
  solver. Evidence: `outputs/tables/e1fr_qiu_source_equation_correction.json`,
  `outputs/tables/e1fr_qiu_source_equation_correction.csv`,
  `outputs/tables/e1f_semantic_amendment.json`,
  `outputs/tables/e1f_source_to_pde_bridge_mismatch.csv`, and
  `docs/codex_reports/e1fr_qiu_source_equation_correction_results.md`.

## M40R Qiu E0 mesh and active-transient repair (2026-07-21)

- Task: `Q2_M40R_QIU_E0_MESH_AND_ACTIVE_TRANSIENT_REPAIR`.
- Baseline: `5e68d3bf25bcbe30bdce4840f9130c096a0177e1`.
- Preregistration commit: `b935631c13ca288961e1bf72ed37782418693e54`.
- The original M40 result remains byte-for-byte `failed_but_informative`.
- Repaired 8/16/32 current and fixed-grid p99 changes are `0.00592586` and
  `0.00847419`; every original numerical E0 gate passes.
- The source-composed active run fails closed at `360.22494 K` after
  `0.0920339 R_load C`, and current fine-pair NRMSE is `0.0342127 > 0.02`.
  M41 is not authorized; no parameter fit, inverse, PINN, or rescue rerun ran.
- Repository validation: `387 passed, 1 failed, 0 skipped in 526.77 s`; the
  sole failure is an allocation error in the historical PINN-v1 smoke
  subprocess. The full suite was not rerun.
- Evidence: `outputs/tables/m40r_qiu_e0_summary.json`,
  `outputs/tables/m40r_qiu_mesh_convergence.csv`,
  `outputs/tables/m40r_qiu_active_transient.json`, and
  `docs/codex_reports/m40r_qiu_e0_repair_results.md`.

## M40 Qiu VO2 real-device 2D bridge E0 (2026-07-21)

- Task: `Q2_M40_QIU_VO2_REAL_DEVICE_2D_BRIDGE_E0`.
- Baseline: `e3d47edf7aa4cfc57b0272da20dd1f5654f8c877`.
- Preregistration commit: `017260194e42d94633bf64354c922b238dc40c79`.
- Formal result: `failed_but_informative`; 12/14 gates pass. The finest-pair
  main-current change is `0.0247878 > 0.01` and the fixed-window p99 field
  change is `0.110664 > 0.02`. M41 is not authorized.
- Source: Qiu et al. 2024 main article and Supporting Information, DOI
  `10.1002/adma.202306818`; local raw copies are hash-locked and not tracked.
- Boundary: no inverse, PINN training, parameter search, M38, Zhang sealed
  13 V access, frozen-GT edit, or real-device calibration claim.
- Evidence: `outputs/tables/m40_qiu_e0_preregistration.json`,
  `outputs/tables/m40_qiu_e0_summary.json`, and
  `outputs/tables/m40_qiu_mesh_convergence.csv`.

## M36 event-resolved orbit convergence and conditional public fit (2026-07-19)

- Base snapshot: `31098e74156feb5ed83a0c14d037ffa8c22c24c2`; immutable preregistration commit: `661142c`.
- Preregistration: `outputs/tables/m36_event_resolved_orbit_preregistration.json`; all `20/20` history-hash, open-voltage, instrument-noise, solver, event, budget, LOVO, and sealed-path checks pass.
- Independent reference: DOP853 and Radau pass all locked parity gates at 9/11/15/17 V. At 11/15 V their reversal counts are exactly `196/196` and `344/344`; maximum event-time disagreement is below `1e-12 s`.
- Source-compatible Euler family: 2.5/1.25/0.625/0.3125 ns runs are complete. Only 9 V passes all primary gates. The finest 11 V run fails event-time, cycle-shape, and peak gates; 15 V fails event-time and has coarse-grid event-sequence instability; 17 V fails the maximum-current/noise gate.
- Stop disposition: `failed_but_informative`; no event-aware Jacobian, optimization, LOVO, parameter estimate, fit lock, PINN training, or 13 V numeric access was executed.
- Evidence: `outputs/tables/m36_event_resolved_orbit_summary.json`, `outputs/tables/m36_orbit_convergence_metrics.csv`, `outputs/tables/m36_event_times.csv`, and four `outputs/figures/m36_*.png` figures.
- Report: `docs/codex_reports/m36_event_resolved_orbit_results_and_q2_assessment.md`.

## M35 gradient semantics and public multi-voltage fail-closed round (2026-07-18)

- Base snapshot: `144aa53de1f6d6f788f61729355b4de45fd9c241`.
- D-PREG: `outputs/tables/m35_public_multivoltage_preregistration.json`; all `21/21` provenance, role, equation, unit, licensing, LOVO, multistart, and sealed-path checks pass.
- M34-A: `outputs/tables/m34a_gradient_semantics_amendment.json` and `outputs/tables/m34a_gradient_direction_curves.csv`; all `32/32` fixed float64 module/seed directions show stable group-normalized VJP/central-difference parity. No autograd implementation error or total-loss-scale cancellation is supported, and the amendment has no training vote.
- D-FIT: `outputs/tables/m35_solver_convergence.csv` and `outputs/tables/m35_public_multivoltage_fit_summary.json`; eight solver evaluations were run on open 9/11/15/17 V only. All four voltages fail the locked current/voltage full-waveform convergence gates, while activity class, frequency, charge, and energy checks pass.
- Stop disposition: `failed_but_informative`; no prefit Jacobian, optimization, multistart, repository parameter estimate, fit lock, or PINN training was executed. The 13 V numeric content remained sealed and unaccessed.
- Report: `docs/codex_reports/m35_public_multivoltage_fit_and_gradient_amendment.md`.

## Project history/workflow/innovation audit (2026-07-14)

- Type: documentation, governance, and primary-literature review; no new scientific experiment.
- Output: `outputs/tables/project_history_workflow_innovation_audit_summary.json`.
- Report: `docs/codex_reports/project_history_workflow_innovation_audit_f14c068.md`.
- Validation: governance passed; full CPU suite `188 passed`.
- Claim impact: no status change; external anchor narrowed to a VO2 literature-family comparison.

## Post-d1121e16 review integration (2026-07-14)

- Type: documentation, provenance planning, and existing-evidence visualization; no new scientific experiment.
- Figure correction: Figure 1 title narrowed; Figure 2 adds existing 36-case off-grid recovery points.
- Priority decision: external quantitative anchor is active; P1 is limited to one later repair cycle.
- Report: `docs/codex_reports/post_d1121e16_review_integration_report.md`.
- Claim impact: none; all scientific statuses are unchanged.
## Priority A constrained gamma_sub evidence lock (2026-07-14)

- Config: `configs/gamma_sub_evidence_lock.yaml`
- Builder: `scripts/build_gamma_sub_evidence_lock.py`
- Regression test: `tests/test_gamma_sub_evidence_lock.py`
- Machine-readable output: `outputs/tables/gamma_sub_evidence_lock_summary.json`
- Report: `docs/codex_reports/post_d23a576_research_decision_audit.md`
- Status: `supported` as evidence assembly; no new experiment and no scientific claim upgrade.
- Disposition: move the locked mainline to manuscript; Priority B P1 validity repair is now active.
## Control-volume multidomain OASIS and inverse repair v10
## Q2 SCI delivery-contract alignment (governance only)

- Scope: synchronize the persistent delivery target, single-bottleneck policy, Definition of Done, stop rules, and round closeout contract.
- Experiment status: no experiment, config, metric, threshold, or historical result changed.
- Evidence impact: none; the current constrained `gamma_sub` evidence remains the manuscript mainline.
- Report: `docs/codex_reports/q2_sci_delivery_contract_alignment_report.md`.

- Physical semantics: `scripts/audit_physical_semantics_v10.py`
- CV training: `scripts/train_cv_multidomain_oasis_v10.py`
- Active protocol/noisy inverse: `scripts/audit_active_protocol_design_v3.py`
- Multi-terminal forward: `scripts/audit_multiterminal_yz_forward_v10.py`
- Generalization preflight: `scripts/audit_oasis_generalization_v10.py`
- Conditional algorithm gate: `scripts/audit_oasis_algorithms_v10.py`
- Core implementation: `src/pinnpcm/physics/multilayer_sandwich.py`, `src/pinnpcm/physics/multiterminal_yz.py`, `src/pinnpcm/pinn/oasis_components.py`
- Tests: `tests/test_physical_semantics_v10.py`, `tests/test_cv_multidomain_oasis_v10.py`, `tests/test_active_protocol_design_v3.py`, `tests/test_multiterminal_yz_v10.py`
- Status: P0 and P3 implementation gates pass; P1/P2 fail strict scientific gates; P4 blocked; generalization preflight only.

## Phase-activated multidomain OASIS-PINN v9

- Forward script: `scripts\audit_phase_activated_multilayer_forward.py`
- Multidomain training script: `scripts\train_multidomain_oasis_v9.py`
- Active inverse script: `scripts\audit_active_protocol_identifiability_v2.py`
- 2D gate script: `scripts\audit_oasis_2d_field_resolution_v2.py`
- Algorithm gate script: `scripts\audit_phase_activated_algorithms_v9.py`
- Physics implementation: `src\pinnpcm\physics\multilayer_sandwich.py`
- OASIS component implementation: `src\pinnpcm\pinn\oasis_components.py`
- Tests: `tests\test_phase_activated_multilayer_forward.py`, `tests\test_multidomain_oasis_training_v9.py`, `tests\test_active_protocol_identifiability_v2.py`, `tests\test_oasis_v9_gates.py`
- Report: `docs\codex_reports\phase_activated_multidomain_oasis_v9_report.md`

Status: P0 and P1 pass; P2 is improved but remains failed-but-informative under strict block-error gate; P3 and P4 are blocked.

## Conservative multidomain OASIS-PINN v8

- Conservative forward script: `scripts\audit_conservative_multilayer_forward.py`
- Multidomain OASIS smoke script: `scripts\audit_multidomain_oasis_pinn.py`
- Active protocol identifiability script: `scripts\audit_active_protocol_identifiability.py`
- 2D field-resolution gate script: `scripts\audit_oasis_2d_field_resolution.py`
- Updated phase-aware STL audit: `scripts\audit_phase_aware_stl_repair.py`
- Updated Fourier/F-SPS audit: `scripts\audit_adaptive_fourier_fsps_superiority.py`
- Physics implementation: `src\pinnpcm\physics\multilayer_sandwich.py`
- OASIS components: `src\pinnpcm\pinn\oasis_components.py`
- Tests: `tests\test_conservative_multilayer_forward.py`, `tests\test_multidomain_oasis_pinn.py`, `tests\test_active_protocol_identifiability.py`, `tests\test_oasis_2d_field_resolution.py`, plus updated STL/Fourier tests.
- Report: `docs\codex_reports\conservative_multidomain_oasis_pinn_v8_report.md`

Status: completed as bounded synthetic numerical supplementary evidence. Conservative P0 passes; multidomain component smoke passes; active terminal protocol rescue, 2D field recovery, full STL-PINN reproduction, LoRA-STL, and universal Fourier/F-SPS superiority are not supported.


﻿# Experiment registry

## Response-surface verification and manuscript claim consolidation pack

- Anchor verification config: `configs\gamma_sub_response_surface_anchor_verification.yaml`
- Anchor verification script: `scripts\audit_gamma_sub_response_surface_anchor_verification.py`
- Anchor verification test: `tests\test_gamma_sub_response_surface_anchor_verification.py`
- Sequential protocol design config: `configs\gamma_sub_sequential_protocol_design.yaml`
- Sequential protocol design script: `scripts\audit_gamma_sub_sequential_protocol_design.py`
- Sequential protocol design test: `tests\test_gamma_sub_sequential_protocol_design.py`
- Balanced F-SPS config: `configs\f_sps_balanced_medium_budget_benchmark.yaml`
- Balanced F-SPS runner: `scripts\train_f_sps_balanced_medium_budget_benchmark.py`
- Balanced F-SPS test: `tests\test_f_sps_balanced_medium_budget_benchmark.py`
- Claim stress-test builder: `scripts\build_manuscript_claim_stress_test.py`
- Claim stress-test test: `tests\test_manuscript_claim_stress_test.py`
- Manuscript figure builder: `scripts\build_manuscript_ready_gamma_sub_figures.py`
- Outputs: `outputs\tables\gamma_sub_response_surface_anchor_verification_summary.json`, `outputs\tables\gamma_sub_response_surface_anchor_verification_cases.csv`, `outputs\tables\gamma_sub_sequential_protocol_design_summary.json`, `outputs\tables\gamma_sub_sequential_protocol_design_cases.csv`, `outputs\tables\f_sps_balanced_medium_budget_benchmark_summary.json`, `outputs\tables\f_sps_balanced_medium_budget_benchmark_cases.csv`, `outputs\tables\manuscript_claim_stress_test_summary.json`
- Manuscript docs: `docs\paper\claim_stress_test_matrix.md`, `docs\paper\proposed_main_figures.md`, `docs\paper\proposed_tables.md`, `docs\paper\manuscript_outline_v1.md`
- Report: `docs\codex_reports\gamma_sub_response_surface_verification_and_manuscript_claim_consolidation_report.md`

Status: completed as synthetic numerical digital-twin manuscript-defense evidence. It verifies response-surface anchors, adds sequential protocol-design preflight, balances F-SPS medium-budget coverage, and consolidates claim boundaries without modifying frozen Ground Truth.


## High-throughput gamma_sub identifiability and F-SPS medium-budget pack

- Dense profile config: `configs\gamma_sub_tsw_dense_profile_likelihood.yaml`
- Dense profile script: `scripts\audit_gamma_sub_tsw_dense_profile_likelihood.py`
- Dense profile test: `tests\test_gamma_sub_tsw_dense_profile_likelihood.py`
- Recoverability phase-diagram config: `configs\gamma_sub_recoverability_phase_diagram.yaml`
- Recoverability phase-diagram script: `scripts\audit_gamma_sub_recoverability_phase_diagram.py`
- Recoverability phase-diagram test: `tests\test_gamma_sub_recoverability_phase_diagram.py`
- Protocol actual-validation config: `configs\gamma_sub_protocol_actual_inversion_validation.yaml`
- Protocol actual-validation script: `scripts\audit_gamma_sub_protocol_actual_inversion_validation.py`
- Protocol actual-validation test: `tests\test_gamma_sub_protocol_actual_inversion_validation.py`
- Weighted protocol objective config: `configs\gamma_sub_weighted_protocol_objective.yaml`
- Weighted protocol objective script: `scripts\audit_gamma_sub_weighted_protocol_objective.py`
- Weighted protocol objective test: `tests\test_gamma_sub_weighted_protocol_objective.py`
- Statistical robustness config: `configs\gamma_sub_statistical_robustness.yaml`
- Statistical robustness script: `scripts\audit_gamma_sub_statistical_robustness.py`
- Statistical robustness test: `tests\test_gamma_sub_statistical_robustness.py`
- F-SPS medium-budget config: `configs\f_sps_medium_budget_benchmark.yaml`
- F-SPS medium-budget runner: `scripts\train_f_sps_medium_budget_benchmark.py`
- F-SPS medium-budget test: `tests\test_f_sps_medium_budget_benchmark.py`
- Shared response-surface helper: `scripts\gamma_sub_high_throughput_common.py`
- Figure builder: `scripts\build_high_throughput_sci_figures.py`
- Outputs: `outputs\tables\gamma_sub_tsw_dense_profile_likelihood_summary.json`, `outputs\tables\gamma_sub_tsw_dense_profile_likelihood_grid.csv`, `outputs\tables\gamma_sub_tsw_dense_profile_likelihood_profiles.csv`, `outputs\tables\gamma_sub_recoverability_phase_diagram_summary.json`, `outputs\tables\gamma_sub_recoverability_phase_diagram_cases.csv`, `outputs\tables\gamma_sub_protocol_actual_inversion_validation_summary.json`, `outputs\tables\gamma_sub_protocol_actual_inversion_validation_cases.csv`, `outputs\tables\gamma_sub_weighted_protocol_objective_summary.json`, `outputs\tables\gamma_sub_weighted_protocol_objective_cases.csv`, `outputs\tables\gamma_sub_statistical_robustness_summary.json`, `outputs\tables\gamma_sub_statistical_robustness_cases.csv`, `outputs\tables\f_sps_medium_budget_benchmark_summary.json`, `outputs\tables\f_sps_medium_budget_benchmark_cases.csv`
- Report: `docs\codex_reports\gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md`

Status: completed as lightweight response-surface and bounded training evidence. It strengthens the constrained `gamma_sub` manuscript line and records bounded F-SPS method-development evidence. It does not modify frozen Ground Truth, does not claim experimental validation, and does not prove F-SPS superiority.

## Gamma_sub multi-protocol and profile-likelihood validation pack

- Multi-protocol recoverability config: `configs\gamma_sub_multi_protocol_recoverability.yaml`
- Multi-protocol recoverability script: `scripts\audit_gamma_sub_multi_protocol_recoverability.py`
- Multi-protocol recoverability test: `tests\test_gamma_sub_multi_protocol_recoverability.py`
- Profile-likelihood config: `configs\gamma_sub_tsw_profile_likelihood.yaml`
- Profile-likelihood script: `scripts\audit_gamma_sub_tsw_profile_likelihood.py`
- Profile-likelihood test: `tests\test_gamma_sub_tsw_profile_likelihood.py`
- Joint inversion boundary config: `configs\gamma_sub_joint_inversion_boundary.yaml`
- Joint inversion boundary script: `scripts\audit_gamma_sub_joint_inversion_boundary.py`
- Joint inversion boundary test: `tests\test_gamma_sub_joint_inversion_boundary.py`
- Protocol observability design config: `configs\gamma_sub_protocol_observability_design.yaml`
- Protocol observability design script: `scripts\audit_gamma_sub_protocol_observability_design.py`
- Protocol observability design test: `tests\test_gamma_sub_protocol_observability_design.py`
- Shared helper: `scripts\gamma_sub_validation_common.py`
- Figure builder: `scripts\build_gamma_sub_sci_validation_figures.py`
- Outputs: `outputs\tables\gamma_sub_multi_protocol_recoverability_summary.json`, `outputs\tables\gamma_sub_multi_protocol_recoverability_cases.csv`, `outputs\tables\gamma_sub_tsw_profile_likelihood_summary.json`, `outputs\tables\gamma_sub_tsw_profile_likelihood_grid.csv`, `outputs\tables\gamma_sub_tsw_profile_likelihood_profiles.csv`, `outputs\tables\gamma_sub_joint_inversion_boundary_summary.json`, `outputs\tables\gamma_sub_joint_inversion_boundary_cases.csv`, `outputs\tables\gamma_sub_protocol_observability_design_summary.json`, `outputs\tables\gamma_sub_protocol_observability_design_cases.csv`
- Report: `docs\codex_reports\gamma_sub_multi_protocol_and_profile_likelihood_validation_report.md`

Status: completed as lightweight synthetic numerical validation evidence. It strengthens SCI manuscript experimental breadth and reviewer-defense scope without modifying frozen Ground Truth or adding F-SPS-PINN experiments.

## SCI gap-closing gamma_sub validation pack

- Auxiliary observability sweep config: `configs\gamma_sub_auxiliary_observability_sweep.yaml`
- Auxiliary observability sweep script: `scripts\audit_gamma_sub_auxiliary_observability_sweep.py`
- Auxiliary observability sweep test: `tests\test_gamma_sub_auxiliary_observability_sweep.py`
- Auxiliary observability sweep outputs: `outputs\tables\gamma_sub_auxiliary_observability_sweep_summary.json`, `outputs\tables\gamma_sub_auxiliary_observability_sweep_cases.csv`
- Auxiliary observability sweep report: `docs\codex_reports\gamma_sub_auxiliary_observability_sweep_report.md`- T_sw confounding phase-map config: `configs\gamma_sub_tsw_confounding_phase_map.yaml`
- T_sw confounding phase-map script: `scripts\audit_gamma_sub_tsw_confounding_phase_map.py`
- T_sw confounding phase-map test: `tests\test_gamma_sub_tsw_confounding_phase_map.py`
- T_sw confounding phase-map outputs: `outputs\tables\gamma_sub_tsw_confounding_phase_map_summary.json`, `outputs\tables\gamma_sub_tsw_confounding_phase_map_cases.csv`
- T_sw confounding phase-map report: `docs\codex_reports\gamma_sub_tsw_confounding_phase_map_report.md`
- Gap-closing figure builder: `scripts\build_gamma_sub_gap_closing_figures.py`
- T_sw prior-width config: `configs\gamma_sub_tsw_prior_width_sweep.yaml`
- T_sw prior-width script: `scripts\audit_gamma_sub_tsw_prior_width_sweep.py`
- T_sw prior-width test: `tests\test_gamma_sub_tsw_prior_width_sweep.py`
- T_sw prior-width outputs: `outputs\tables\gamma_sub_tsw_prior_width_sweep_summary.json`, `outputs\tables\gamma_sub_tsw_prior_width_sweep_cases.csv`
- T_sw prior-width report: `docs\codex_reports\gamma_sub_tsw_prior_width_sweep_report.md`
- Temperature-anchor placement config: `configs\gamma_sub_temperature_anchor_placement.yaml`
- Temperature-anchor placement script: `scripts\audit_gamma_sub_temperature_anchor_placement.py`
- Temperature-anchor placement test: `tests\test_gamma_sub_temperature_anchor_placement.py`
- Temperature-anchor placement outputs: `outputs\tables\gamma_sub_temperature_anchor_placement_summary.json`, `outputs\tables\gamma_sub_temperature_anchor_placement_cases.csv`
- Temperature-anchor placement report: `docs\codex_reports\gamma_sub_temperature_anchor_placement_report.md`
- Scalar baseline script: `scripts\compare_gamma_sub_scalar_baselines.py`
- Scalar baseline test: `tests\test_gamma_sub_scalar_baselines.py`
- Scalar baseline output: `outputs\tables\gamma_sub_scalar_baseline_comparison.csv`
- Scalar baseline report: `docs\codex_reports\gamma_sub_scalar_baseline_comparison_report.md`

Status: completed as lightweight synthetic numerical validation evidence. It strengthens the constrained `gamma_sub` manuscript line with auxiliary-observability, prior-width, anchor-placement, scalar-baseline, and T_sw phase-map audits without modifying frozen Ground Truth or adding F-SPS-PINN experiments.

## Observability-augmented gamma_sub audit

- Config: `configs\gamma_sub_observability_augmented.yaml`
- Script: `scripts\audit_gamma_sub_observability_augmented.py`
- Test: `tests\test_gamma_sub_observability_augmented.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_observability_augmented_summary.json`
- Cases CSV: `outputs\tables\gamma_sub_observability_augmented_cases.csv`
- Report: `docs\gamma_sub_observability_augmented_report.md`
- Codex report: `docs\codex_reports\gamma_sub_observability_augmented_report.md`

Status: completed as a lightweight synthetic numerical observability audit. Sparse temperature anchors alone did not reduce the wide `T_sw` mismatch bias; narrowing the `T_sw` prior did. No frozen Ground Truth file was modified.

## F-SPS-PINN v2 Fourier on/off ablation under stress

- Config: `configs\pinn_inverse_v2_fourier_ablation.yaml`
- Runner: `scripts\run_pinn_inverse_v2_fourier_ablation.py`
- Test: `tests\test_pinn_inverse_v2_fourier_ablation.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json`
- Runs CSV: `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`
- Report: `docs\codex_reports\pinn_inverse_v2_fourier_ablation_report.md`

Status: completed as a small-run synthetic numerical Fourier on/off ablation under sharp-transition stress. It compares `vo2_sigma_fourier_off` and `vo2_sigma_fourier_on` under matched settings. It is not a formal performance experiment and does not replace v0/v1/v1.1 paths.


## F-SPS-PINN v2 phase-transition stress preflight

- Config: `configs\pinn_inverse_v2_phase_transition_stress.yaml`
- Runner: `scripts\run_pinn_inverse_v2_phase_transition_stress.py`
- Test: `tests\test_pinn_inverse_v2_phase_transition_stress.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`
- Cases CSV: `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`
- Report: `docs\codex_reports\pinn_inverse_v2_phase_transition_stress_report.md`

Status: completed as a small-run synthetic numerical phase-transition stress preflight. It exercises `white_box_vo2_sigma` under `mild_transition`, `sharp_transition`, `near_threshold`, and `high_contrast` settings. It is not a formal performance experiment and does not replace v0/v1/v1.1 paths.


## F-SPS-PINN v2 small-run baseline

- Config: `configs\pinn_inverse_v2_f_sps_baseline.yaml`
- Runner: `scripts\run_pinn_inverse_v2_baseline.py`
- Test: `tests\test_pinn_inverse_v2_baseline.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json`
- Runs CSV: `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`
- Report: `docs\codex_reports\pinn_inverse_v2_f_sps_baseline_report.md`

Status: completed as a small-run synthetic numerical baseline. It compares `free_log_sigma` and `white_box_vo2_sigma` under matched seed, epochs, anchor count, and sparse terminal observations. It is not a formal performance experiment and does not replace v0/v1/v1.1 paths.

## F-SPS-PINN v2 smoke training pipeline

- Config: `configs\pinn_inverse_v2_f_sps_smoke.yaml`
- Script: `scripts\train_pinn_inverse_v2_smoke.py`
- Test: `tests\test_pinn_inverse_v2_smoke.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`
- Report: `docs\codex_reports\pinn_inverse_v2_f_sps_smoke_report.md`

Status: completed as a minimal smoke training loop. It uses Fourier-pyramid features and `sigma = vo2_sigma(T, c_v, m)`, writes a lightweight JSON summary, and does not use the free `log_sigma` path. This is not a formal performance experiment.

## F-SPS-PINN architecture MVP

- VO2-like constitutive closure: `src\pinnpcm\physics\vo2_constitutive.py`
- Fourier pyramid and opt-in MLP: `src\pinnpcm\pinn\network.py`
- Dynamic residual gate: `src\pinnpcm\pinn\loss_balancer.py`
- Differentiable oscillation metrics: `src\pinnpcm\physics\oscillation_metrics.py`
- Tests: `tests\test_vo2_constitutive.py`, `tests\test_fourier_pyramid.py`, `tests\test_loss_balancer.py`, `tests\test_oscillation_metrics.py`
- Report: `docs\codex_reports\f_sps_pinn_architecture_mvp_report.md`

Status: completed as isolated architecture MVP, not a training result.

## Continuous off-grid gamma_sub refinement audit

- Script: `scripts\refine_gamma_sub_continuous.py`
- Test: `tests\test_gamma_sub_continuous_refinement.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_continuous_refinement_summary.json`
- Cases table: `outputs\tables\gamma_sub_continuous_refinement_cases.csv`
- Report: `docs\gamma_sub_continuous_refinement_report.md`
- Codex report: `docs\codex_reports\gamma_sub_continuous_refinement_report.md`

Status: completed as a simulator-backed off-grid scalar refinement audit. The lightweight JSON and CSV are committed evidence. No frozen Ground Truth file was modified.

## Paper-readiness gamma_sub robustness pack

- Script: `scripts\audit_gamma_sub_paper_readiness.py`
- Test: `tests\test_gamma_sub_paper_readiness.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_paper_readiness_summary.json`
- Observation-count table: `outputs\tables\gamma_sub_observation_sensitivity.csv`
- Off-grid table: `outputs\tables\gamma_sub_offgrid_summary.csv`
- Report: `docs\gamma_sub_paper_readiness_report.md`
- Codex report: `docs\codex_reports\gamma_sub_paper_readiness_report.md`

Status: completed as a paper-readiness robustness audit. The lightweight JSON
and CSV are committed evidence. No frozen Ground Truth file was modified.

## Literature-backed constrained gamma_sub inversion

- Config: `configs\gamma_sub_constrained_inversion.yaml`
- Script: `scripts\invert_gamma_sub_constrained.py`
- Test: `tests\test_gamma_sub_constrained.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_constrained_inversion_summary.json`
- Prior-width sweep: `outputs\tables\gamma_sub_prior_width_sweep.csv`
- Report: `docs\gamma_sub_constrained_inversion_report.md`
- Codex report: `docs\codex_reports\gamma_sub_constrained_inversion_report.md`

Status: completed as a constrained reduced inverse audit. The lightweight JSON
and CSV are committed evidence. No frozen Ground Truth file was modified.

## Local Codex context workflow integration

- Source pack: `E:\pinn_codex_reference_pack`
- Context entry: `CODEX_CONTEXT.md`
- Active phase: `docs\research_strategy\active_phase.md`
- Loading policy: `docs\research_strategy\context_loading_policy.md`
- Handoff: `docs\research_strategy\current_research_handoff.md`
- Report: `docs\codex_reports\local_codex_context_integration_report.md`
- Cleanup report:
  `docs\codex_reports\documentation_structure_cleanup_report.md`

Status: completed as documentation and workflow integration only. No new
experiment, training run, Ground Truth revision, or generated dataset was
created.

## Ground Truth v1.1 acceptance

- Runner: `scripts\run_gt_v1_acceptance.py`
- Data output: `data\processed\gt_v1_acceptance\`
- Figure output: `outputs\figures\gt_v1_acceptance\`
- Table output: `outputs\tables\gt_v1_acceptance\`
- Report: `docs\gt_v1_acceptance_report.md`
- Status: frozen synthetic benchmark.

## PINN inverse v0 baseline

- Config: `configs\pinn_inverse_v0_triangle.yaml`
- Runner: `scripts\train_pinn_inverse_v0.py`
- Output: `outputs\pinn_inverse_v0\triangle\`
- Status: runnable proof-of-concept.

## PINN inverse v0 ablation audit

- Runner: `scripts\run_pinn_inverse_v0_ablation.py`
- Summary: `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- Report: `docs\pinn_inverse_v0_ablation_report.md`

Runs:

- `configs\pinn_inverse_v0_triangle_full_anchor.yaml` ->
  `outputs\pinn_inverse_v0\triangle_full_anchor\`
- `configs\pinn_inverse_v0_triangle_weak_anchor.yaml` ->
  `outputs\pinn_inverse_v0\triangle_weak_anchor\`
- `configs\pinn_inverse_v0_triangle_port_only.yaml` ->
  `outputs\pinn_inverse_v0\triangle_port_only\`

Status: completed. Generated training outputs are reproducible and are not
committed, except the lightweight summary JSON.

## PINN inverse v1 physics-regularized audit

- Single-run trainer: `scripts\train_pinn_inverse_v1.py`
- Batch runner: `scripts\run_pinn_inverse_v1_experiments.py`
- Summary: `outputs\tables\pinn_inverse_v1_summary.json`
- Design: `docs\pinn_inverse_v1_physics_design.md`
- Report: `docs\pinn_inverse_v1_report.md`

Runs:

- `configs\pinn_inverse_v1_triangle_physics.yaml` ->
  `outputs\pinn_inverse_v1\triangle_physics\`
- `configs\pinn_inverse_v1_triangle_weak_anchor.yaml` ->
  `outputs\pinn_inverse_v1\triangle_weak_anchor\`
- `configs\pinn_inverse_v1_triangle_port_physics.yaml` ->
  `outputs\pinn_inverse_v1\triangle_port_physics\`

Status: completed as a physics-regularized approximation. Generated training
outputs are reproducible and are not committed, except the lightweight summary
JSON.

## PINN inverse v1.1 residual-balancing audit

- Batch runner: `scripts\run_pinn_inverse_v1_1_experiments.py`
- Summary: `outputs\tables\pinn_inverse_v1_1_summary.json`
- Report: `docs\pinn_inverse_v1_1_report.md`
- Codex report: `docs\codex_reports\pinn_inverse_v1_1_report.md`

Runs:

- `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml` ->
  `outputs\pinn_inverse_v1_1\triangle_physics_balanced\`
- `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml` ->
  `outputs\pinn_inverse_v1_1\triangle_port_physics_balanced\`

Status: completed as a residual-balancing audit. Generated training outputs are
reproducible and are not committed, except the lightweight summary JSON.

## PINN identifiability audit

- Analyzer: `scripts\analyze_pinn_identifiability.py`
- Input: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Summary: `outputs\tables\pinn_identifiability_summary.json`
- Correlation table: `outputs\tables\pinn_identifiability_correlation.csv`
- Report: `docs\pinn_identifiability_audit_report.md`
- Codex report: `docs\codex_reports\pinn_identifiability_audit_report.md`

Figures:

- `outputs\figures\pinn_identifiability\correlation_heatmap.png`
- `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
- `outputs\figures\pinn_identifiability\lag_correlation.png`

Status: completed as a descriptive identifiability audit. The summary JSON and
CSV are lightweight committed evidence; generated figures are reproducible and
ignored by Git.

## v2a gamma_sub identifiability audit

- Scan script: `scripts\scan_gamma_sub_identifiability.py`
- Inversion script: `scripts\invert_gamma_sub_v0.py`
- Input: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Summary: `outputs\tables\gamma_sub_identifiability_summary.json`
- Report: `docs\gamma_sub_identifiability_report.md`
- Codex report: `docs\codex_reports\gamma_sub_identifiability_audit_report.md`

Figures:

- `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`

Status: completed as a reduced scalar inverse-problem audit. The summary JSON
is lightweight committed evidence; generated figures are reproducible and
ignored by Git.

## gamma_sub robustness and confounding audit

- Confounding script: `scripts\audit_gamma_sub_confounding.py`
- Mismatch inversion script: `scripts\invert_gamma_sub_with_mismatch.py`
- Input: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Summary: `outputs\tables\gamma_sub_confounding_summary.json`
- Sensitivity ranking: `outputs\tables\gamma_sub_sensitivity_ranking.csv`
- Report: `docs\gamma_sub_confounding_report.md`
- Codex report: `docs\codex_reports\gamma_sub_confounding_audit_report.md`

Status: completed as a robustness audit. The lightweight JSON and CSV are
committed evidence.
## Literature-Anchored Gamma_Sub Calibration And Protocol Validation

Status: completed as synthetic numerical digital-twin reviewer-defense evidence.

Files:

- `configs/literature_phase_change_parameter_sanity.yaml`
- `scripts/audit_literature_phase_change_parameter_sanity.py`
- `configs/literature_curve_fit_external_anchor.yaml`
- `scripts/fit_literature_phase_change_curves.py`
- `configs/gamma_sub_tsw_calibration_necessity.yaml`
- `scripts/audit_gamma_sub_tsw_calibration_necessity.py`
- `configs/gamma_sub_simulator_backed_sequential_protocol_validation.yaml`
- `scripts/audit_gamma_sub_simulator_backed_sequential_protocol_validation.py`
- `scripts/build_manuscript_style_gamma_sub_figures.py`
- `tests/test_literature_phase_change_parameter_sanity.py`
- `tests/test_literature_curve_fit_external_anchor.py`
- `tests/test_gamma_sub_tsw_calibration_necessity.py`
- `tests/test_gamma_sub_simulator_backed_sequential_protocol_validation.py`

Key result: best simulator-backed sequential candidate is `multi_pulse_to_ltp_ltd`; T_sw calibration remains required.

## External curve ingestion and calibrated gamma_sub manuscript workflow pack

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

## Calibration tolerance, protocol disentanglement, and submission lock pack

- Tolerance config: `configs/gamma_sub_tsw_calibration_tolerance_sweep.yaml`
- Tolerance script: `scripts/audit_gamma_sub_tsw_calibration_tolerance_sweep.py`
- Tolerance test: `tests/test_gamma_sub_tsw_calibration_tolerance_sweep.py`
- Disentanglement config: `configs/gamma_sub_calibration_protocol_disentanglement.yaml`
- Disentanglement script: `scripts/audit_gamma_sub_calibration_protocol_disentanglement.py`
- Disentanglement test: `tests/test_gamma_sub_calibration_protocol_disentanglement.py`
- Final robustness config: `configs/gamma_sub_calibrated_protocol_robustness_final.yaml`
- Final robustness script: `scripts/audit_gamma_sub_calibrated_protocol_robustness_final.py`
- Final robustness test: `tests/test_gamma_sub_calibrated_protocol_robustness_final.py`
- Targeted curve extraction config: `configs/literature_targeted_curve_extraction_attempt.yaml`
- Targeted curve extraction script: `scripts/attempt_literature_curve_extraction_from_sources.py`
- Targeted curve extraction test: `tests/test_literature_targeted_curve_extraction_attempt.py`
- Final submission lock script: `scripts/build_final_submission_figures.py`
- Report: `docs/codex_reports/calibration_tolerance_protocol_disentanglement_and_submission_lock_report.md`

Status: completed as synthetic numerical digital-twin manuscript-defense evidence. Frozen Ground Truth remains unchanged.

## ODE spot-check manuscript lock and quasi-2D preflight pack

- Added `configs/gamma_sub_tsw_tolerance_ode_spotcheck.yaml`, `scripts/audit_gamma_sub_tsw_tolerance_ode_spotcheck.py`, and `tests/test_gamma_sub_tsw_tolerance_ode_spotcheck.py`.
- Added manuscript draft package under `docs/manuscript/`.
- Added reviewer-defense matrix builder and `docs/manuscript/reviewer_defense_matrix.md`.
- Added quasi-2D literature registry, model boundary docs, forward preflight, and residual preflight.
- Generated lightweight tables: `outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json`, `outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_cases.csv`, `outputs/tables/quasi_2d_literature_source_registry.json`, `outputs/tables/gt_quasi_2d_phase_transition_preflight_summary.json`, and `outputs/tables/pinn_quasi_2d_residual_preflight_summary.json`.
- ODE spot-check cases: `270`; 0.1 K supported: `True`.
- Quasi-2D cases: `4`; fields finite: `True`; observables finite: `True`.
- Residual preflight finite: `True`; 2D inverse claim allowed: `False`.

Boundary: synthetic numerical digital-twin evidence only. Main manuscript claim remains unchanged: calibration-gated sparse-port reduced inversion of `gamma_sub` under fixed or tightly bounded `T_sw` priors.

## Stiffness continuation and phase-field alignment evidence

- Stiffness config: `configs\phase_transition_stiffness_continuation_audit.yaml`
- Stiffness script: `scripts/audit_phase_transition_stiffness_continuation.py`
- Stiffness test: `tests/test_phase_transition_stiffness_continuation.py`
- Stiffness outputs: `outputs/tables\phase_transition_stiffness_continuation_audit_summary.json`, `outputs/tables\phase_transition_stiffness_continuation_audit_cases.csv`
- Phase-field config: `configs\phase_field_inverse_alignment_smoke.yaml`
- Phase-field script: `scripts/audit_phase_field_inverse_alignment_smoke.py`
- Phase-field test: `tests/test_phase_field_inverse_alignment_smoke.py`
- Phase-field outputs: `outputs/tables\phase_field_inverse_alignment_smoke_summary.json`, `outputs/tables\phase_field_inverse_alignment_smoke_cases.csv`
- Positioning docs: `docs\paper\journal_positioning_matrix.md`, `docs\paper
ovelty_gap_map.md`, `docs\paper\sci_two_three_zone_gap_assessment.md`
- Report: `docs\codex_reports\stiffness_continuation_phasefield_alignment_and_submission_positioning_report.md`

Status: completed as supplementary synthetic numerical digital-twin reviewer-defense evidence. Not a main-text core experiment and not experimental validation.

## Final figure literature lock and stiffness 2D story pack

- Literature lock: `docs/literature/drive_and_web_literature_evidence_lock.md`
- Figure builder: `scripts/build_stiffness_2d_story_figures.py`
- Figure-builder test: `tests/test_stiffness_2d_story_figures.py`
- Figure manifest: `outputs/tables/stiffness_2d_story_figure_manifest.json`
- Generated ignored figures: `outputs/figures/stiffness_residual_vs_transition_width.png`, `outputs/figures/stiffness_continuation_gain_vs_width.png`, `outputs/figures/stiffness_fourier_gain_caution.png`, `outputs/figures/phase_field_m_true_vs_estimated.png`, `outputs/figures/phase_field_noise_sensitivity.png`
- Story docs: `docs/paper/final_submission_figure_table_claim_lock_v2.md`, `docs/paper/stiffness_and_quasi_2d_storyboard.md`, `docs/manuscript/abstract_final_candidate.md`, `docs/manuscript/cover_letter_draft.md`, `docs/manuscript/submission_checklist.md`
- Report: `docs/codex_reports/final_figure_literature_lock_and_stiffness_2d_story_report.md`

Status: completed as final supplementary figure/story lock. It does not modify frozen Ground Truth and does not claim F-SPS/Fourier superiority or solved 2D inverse diagnosis.

## Claim-Gate Experimental Resolution: 2D Observability And Stiffness Algorithms

- Reduced 2D forward config: `configs
educed_2d_phase_transition_forward.yaml`
- Reduced 2D forward script: `scriptsudit_reduced_2d_phase_transition_forward.py`
- Reduced 2D forward test: `tests	est_reduced_2d_phase_transition_forward.py`
- Observability config: `configs
educed_2d_observability_limited_inverse.yaml`
- Observability script: `scriptsudit_reduced_2d_observability_limited_inverse.py`
- Observability test: `tests	est_reduced_2d_observability_limited_inverse.py`
- Stiffness algorithm config: `configs\stiffness_aware_algorithm_benchmark.yaml`
- Stiffness algorithm script: `scriptsudit_stiffness_aware_algorithm_benchmark.py`
- Stiffness algorithm test: `tests	est_stiffness_aware_algorithm_benchmark.py`
- Claim gate builder: `scriptsuild_claim_gate_resolution_matrix.py`
- Claim gate test: `tests	est_claim_gate_resolution_matrix.py`
- Claim gate matrix: `docs\paper\claim_gate_resolution_matrix.md`
- Report: `docs\codex_reports\claim_gate_experimental_resolution_2d_observability_and_stiffness_algorithms_report.md`

Status: completed as synthetic numerical digital-twin supplementary claim-gate evidence. It supports reduced 2D forward behavior, qualified low-dimensional 2D inverse under augmented observations, and stiffness-mitigation wording. It does not support terminal-only 2D inverse recovery, full 2D hidden-field recovery, full STL-PINN reproduction, or F-SPS superiority.

## Integrated high-risk claim ladder quick profile

- Config: `configs/high_risk_claim_ladder.yaml`
- Unified module: `src/pinnpcm/experiments/high_risk_claim_ladder.py`
- High-risk ladder runner: `scripts/audit_high_risk_claim_ladder.py`
- Actual stiffness/STL runner: `scripts/audit_integrated_stiffness_stl.py`
- Fourier/F-SPS conditional runner: `scripts/audit_fourier_fsps_conditional_superiority.py`
- Tests: `tests/test_high_risk_claim_ladder.py`, `tests/test_integrated_stiffness_stl.py`, `tests/test_fourier_fsps_conditional_superiority.py`
- Tables: `outputs/tables/high_risk_claim_ladder_summary.json`, `outputs/tables/high_risk_claim_ladder_cases.csv`, `outputs/tables/integrated_stiffness_stl_summary.json`, `outputs/tables/integrated_stiffness_stl_cases.csv`, `outputs/tables/fourier_fsps_conditional_superiority_summary.json`, `outputs/tables/fourier_fsps_conditional_superiority_cases.csv`
- Figures: `outputs/figures/high_risk_2d_hidden_field_ladder_error.png`, `outputs/figures/high_risk_2d_observability_protocols.png`, `outputs/figures/high_risk_2d_sensitivity_anchor_map.png`, `outputs/figures/integrated_stiffness_error_by_algorithm.png`, `outputs/figures/integrated_stiffness_convergence.png`, `outputs/figures/integrated_stl_transfer_gain.png`, `outputs/figures/fourier_fsps_gain_heatmap.png`, `outputs/figures/fourier_fsps_failure_modes.png`
- Report: `docs/codex_reports/integrated_high_risk_claim_ladder_report.md`

Status: completed as bounded synthetic numerical claim-gate exploration. It upgrades only protocol-limited or condition-limited supplementary claims and preserves forbidden overclaims for terminal-only full 2D recovery, full STL-PINN reproduction, and universal Fourier/F-SPS superiority.

## Actualized high-risk claim ladder v2

- Actual low-rank inverse module: `src/pinnpcm/experiments/high_risk_actual_inverse.py`
- Updated high-risk runner: `scripts/audit_high_risk_claim_ladder.py`
- Updated stiffness/STL runner: `scripts/audit_integrated_stiffness_stl.py`
- Updated actual Fourier/F-SPS runner: `scripts/audit_fourier_fsps_conditional_superiority.py`
- Tests: `tests/test_high_risk_claim_ladder.py`, `tests/test_integrated_stiffness_stl.py`, `tests/test_fourier_fsps_conditional_superiority.py`
- Tables: `outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json`, `outputs/tables/high_risk_claim_ladder_actual_inverse_cases.csv`, `outputs/tables/integrated_stiffness_stl_summary.json`, `outputs/tables/integrated_stiffness_stl_cases.csv`, `outputs/tables/fourier_fsps_actual_training_summary.json`, `outputs/tables/fourier_fsps_actual_training_cases.csv`
- Figures: `outputs/figures/high_risk_actual_inverse_error_by_protocol.png`, `outputs/figures/integrated_stiffness_gradient_spike.png`, `outputs/figures/integrated_stiffness_residual_imbalance.png`, `outputs/figures/fourier_fsps_actual_gain_heatmap.png`
- Report: `docs/codex_reports/actualize_high_risk_claim_ladder_v2_report.md`

Status: completed as stricter synthetic numerical actual-inverse/training evidence. It actualizes and downgrades prior heuristic/proxy conclusions where thresholds are not met.
## Port-Physical 2D Inverse And Stiffness-Gated Training v3

Status: completed as synthetic numerical claim-gate evidence.

Code and tests:

- `src/pinnpcm/experiments/port_physical_2d_inverse.py`
- `scripts/audit_port_physical_2d_inverse.py`
- `scripts/audit_stiffness_gated_fourier_fsps.py`
- Updated: `scripts/audit_integrated_stiffness_stl.py`
- `tests/test_port_physical_2d_inverse.py`
- `tests/test_stiffness_gated_fourier_fsps.py`
- Updated: `tests/test_integrated_stiffness_stl.py`

Evidence:

- `outputs/tables/port_physical_2d_inverse_summary.json`
- `outputs/tables/port_physical_2d_inverse_cases.csv`
- `outputs/tables/stiffness_gated_fourier_fsps_summary.json`
- `outputs/tables/stiffness_gated_fourier_fsps_cases.csv`
- Updated: `outputs/tables/integrated_stiffness_stl_summary.json`
- Updated: `outputs/tables/integrated_stiffness_stl_cases.csv`

Claim result: port-physical 2D field recovery remains forbidden; stiffness-gated hybrid is qualified_supported as a condition-limited method-development audit; STL repair remains failed_but_informative.

## OASIS-PINN Multilayer Sandwich And High-Risk Resolution v6

Status: completed as supplementary synthetic numerical claim-gate evidence, not main manuscript proof.

Scripts:

- `scripts/audit_literature_prior_consistency.py`
- `scripts/audit_multilayer_sandwich_device.py`
- `scripts/audit_claim_resolution_2d_field.py`
- `scripts/audit_terminal_only_active_protocol_rescue.py`
- `scripts/audit_phase_aware_stl_repair.py`
- `scripts/audit_adaptive_fourier_fsps_superiority.py`
- `scripts/audit_multilayer_sandwich_low_dim_inverse.py`

Core modules:

- `src/pinnpcm/physics/multilayer_sandwich.py`
- `src/pinnpcm/pinn/oasis_components.py`
- `src/pinnpcm/experiments/claim_resolution_2d_field.py`

Outputs:

- `outputs/tables/literature_prior_consistency_summary.json`
- `outputs/tables/multilayer_sandwich_device_summary.json`
- `outputs/tables/claim_resolution_2d_field_summary.json`
- `outputs/tables/terminal_only_active_protocol_rescue_summary.json`
- `outputs/tables/phase_aware_stl_repair_summary.json`
- `outputs/tables/adaptive_fourier_fsps_superiority_summary.json`
- `outputs/tables/multilayer_sandwich_low_dim_inverse_summary.json`

Claim routing: multilayer forward, augmented Fisher-anchor structured recovery, active low-dimensional terminal diagnosis, and low-dimensional sandwich inverse get qualified support. STL repair and adaptive F-SPS remain failed-but-informative. Experimental validation, terminal-only arbitrary full-field recovery, full STL reproduction, full FEM/device-grade reproduction, and universal F-SPS superiority remain forbidden.

## OASIS-PINN Simulator-Backed Evidence Actualization v7

Status: completed as stricter synthetic numerical claim-gate evidence. This pack supersedes the proxy-positive interpretation of selected v6 results.

Updated code and tests:

- `src/pinnpcm/physics/multilayer_sandwich.py`: computed multilayer interface residuals and energy-balance gate; added simulator parameter knobs used by inverse audits.
- `src/pinnpcm/pinn/oasis_components.py`: `series_stack` is the default physical port solver; `mean_sigma_ablation` is explicit ablation-only; `resistor_network` remains optional.
- `src/pinnpcm/experiments/claim_resolution_2d_field.py`: simulator-ensemble POD basis with a holdout target and no target leakage.
- `scripts/audit_multilayer_sandwich_device.py`: writes computed residual and energy-balance columns.
- `scripts/audit_terminal_only_active_protocol_rescue.py`: simulator-backed terminal-only protocol audit; writes new simulator summary/cases outputs.
- `scripts/audit_multilayer_sandwich_low_dim_inverse.py`: simulator-backed low-dimensional sandwich inverse with finite condition-number reporting.
- `scripts/audit_phase_aware_stl_repair.py`: actual torch STL smoke audit.
- `scripts/audit_adaptive_fourier_fsps_superiority.py`: chi_c sweep and separate best-gated versus adaptive_f_sps statuses.
- Tests updated: `tests/test_multilayer_sandwich_device.py`, `tests/test_oasis_components.py`, `tests/test_terminal_only_active_protocol_rescue.py`, `tests/test_multilayer_sandwich_low_dim_inverse.py`, `tests/test_claim_resolution_2d_field.py`, `tests/test_phase_aware_stl_repair.py`, `tests/test_adaptive_fourier_fsps_superiority.py`.

Lightweight outputs:

- `outputs/tables/multilayer_sandwich_device_summary.json`
- `outputs/tables/multilayer_sandwich_device_cases.csv`
- `outputs/tables/terminal_only_active_protocol_rescue_simulator_summary.json`
- `outputs/tables/terminal_only_active_protocol_rescue_simulator_cases.csv`
- `outputs/tables/multilayer_sandwich_low_dim_inverse_summary.json`
- `outputs/tables/multilayer_sandwich_low_dim_inverse_cases.csv`
- `outputs/tables/claim_resolution_2d_field_summary.json`
- `outputs/tables/claim_resolution_2d_field_cases.csv`
- `outputs/tables/phase_aware_stl_repair_summary.json`
- `outputs/tables/phase_aware_stl_repair_cases.csv`
- `outputs/tables/adaptive_fourier_fsps_superiority_summary.json`
- `outputs/tables/adaptive_fourier_fsps_superiority_cases.csv`

Claim result: multilayer forward, terminal-only rescue, low-dimensional sandwich inverse, holdout POD field recovery, and phase-aware STL are downgraded or remain negative/informative. Only `stiffness_gated_fourier` receives condition-limited qualified support; universal F-SPS/Fourier superiority remains forbidden.

## Source-Contract Amendment And Fallback Submission Lock v2

- Evidence type: formula-contract audit; no new claim-bearing device forward run.
- Config: `configs/qiu_llp_source_contract.yaml`.
- Outputs: `outputs/tables/e1f_llp_source_contract_summary.json`, `outputs/tables/e1f_llp_source_contract_cases.csv`, and `outputs/tables/e1f_source_contract_amendment_v2.json`.
- Result: G1 source-transcription fidelity and G2 tanh-anchor realized continuity pass; G3 manufactured hysteresis properties remain non-blocking diagnostics.
- Claim: `supported` only for the configured tanh-anchor inverse identity; Qiu-author equivalence and external validation remain `forbidden`.
