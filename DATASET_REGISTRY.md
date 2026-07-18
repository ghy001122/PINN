# Dataset Registry — Cumulative Historical Index

> Do not load by default. Current evidence routing is `docs/project_state/current_evidence_index.md`.

## M35 public VO2 multi-voltage provenance lock (2026-07-18)

- Manifest: `data/external/vo2_zhang_2024/multivoltage_prereg_manifest_v1.json`, derived only from the already-acquired publisher archive and existing D0a manifest.
- Parent Source Data SHA-256: `E8916E1B0861C7947119C3F175CEB2E625B197BC32B6B5602F1016823222FFE3`.
- Open public curves: Fig. 1b R-T plus Fig. 1c experimental 9/11/15/17 V traces. Each curve has a fixed curve ID, raw/SI units, conversion formula, permitted LOVO role, license, path, and SHA-256.
- Data type: publisher-supplied `public_external_raw`; preregistered baseline zeroing produces a derived evaluation view at runtime. Solver convergence traces are `solver_generated`, not measured or PINN-predicted.
- Evidence semantics: source-paper reproduction, repository-side refit, repository-withheld cross-voltage evaluation, and independent external validation remain separate.
- Sealed boundary: only the two 13 V archive member names, CRCs, and sizes are registered. Their `content_read_prelock=false`, `extracted_path=null`, and content `sha256=null`; no 13 V numeric value or derived statistic was accessed. No fit lock was generated.
- Frozen GT v1.1 was not modified.

## Priority D external-anchor planning (2026-07-14)

No external dataset was added in this review-integration round. The Qiu-associated VO2 Nature Communications source-data package is the primary provenance candidate; it may enter `data/external/` only with DOI, figure/source-data identity, units, license, access date, extraction method, and SHA-256. External validation remains `forbidden` until a fit/holdout result passes.
## Constrained gamma_sub evidence-lock artifact (2026-07-14)

- `outputs/tables/gamma_sub_evidence_lock_summary.json`
- Built from existing lightweight JSON/CSV evidence by `scripts/build_gamma_sub_evidence_lock.py` using `configs/gamma_sub_evidence_lock.yaml`.
- Type: documentation/evidence-index artifact; no new simulation or measurement.
- Claim boundary: synthetic numerical digital-twin evidence only; external quantitative validation remains absent.
## Control-volume multidomain OASIS v10 evidence
## Q2 SCI delivery-contract alignment

No dataset or external curve was added or modified. Frozen GT v1.1 remains unchanged; the required provenance-backed external quantitative anchor is still an open Definition-of-Done item.

- `outputs/tables/physical_semantics_v10_summary.json`
- `outputs/tables/physical_semantics_v10_cases.csv`
- `outputs/tables/cv_multidomain_oasis_training_summary.json`
- `outputs/tables/cv_multidomain_oasis_cases.csv`
- `outputs/tables/active_protocol_design_v3_summary.json`
- `outputs/tables/sequential_terminal_inverse_v3_summary.json`
- `outputs/tables/multiterminal_yz_forward_summary.json`
- `outputs/tables/oasis_generalization_v10_summary.json`
- `outputs/tables/oasis_algorithm_gate_v10_summary.json`

All are lightweight synthetic numerical evidence. They are not measured data.

## Phase-activated multidomain OASIS-PINN v9 evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin benchmark evidence, not experimental data:

- `outputs\tables\phase_activated_multilayer_forward_summary.json`
- `outputs\tables\phase_activated_multilayer_forward_cases.csv`
- `outputs\tables\multidomain_oasis_training_summary.json`
- `outputs\tables\active_protocol_identifiability_v2_summary.json`
- `outputs\tables\sequential_terminal_inverse_v2_summary.json`
- `outputs\tables\oasis_2d_field_resolution_v2_summary.json`
- `outputs\tables\phase_activated_algorithm_summary.json`

Frozen Ground Truth v1.1 input arrays remain ignored by Git and were not modified.

## Conservative multidomain OASIS-PINN v8 evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin benchmark evidence, not experimental data:

- `outputs\tables\conservative_multilayer_forward_summary.json`
- `outputs\tables\conservative_multilayer_forward_cases.csv`
- `outputs\tables\multidomain_oasis_pinn_summary.json`
- `outputs\tables\active_protocol_identifiability_summary.json`
- `outputs\tables\active_protocol_identifiability_cases.csv`
- `outputs\tables\sequential_terminal_inverse_summary.json`
- `outputs\tables\oasis_2d_field_resolution_summary.json`
- `outputs\tables\phase_aware_stl_repair_summary.json`
- `outputs\tables\phase_aware_stl_repair_cases.csv`
- `outputs\tables\adaptive_fourier_fsps_superiority_summary.json`
- `outputs\tables\adaptive_fourier_fsps_superiority_cases.csv`

Frozen Ground Truth v1.1 input arrays remain ignored by Git and were not modified.


﻿# Dataset registry

## Response-surface verification and manuscript claim consolidation evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin benchmark evidence, not experimental data. They are generated from existing simulator-backed source grids, response-surface summaries, and bounded CPU training against frozen Ground Truth v1.1 inputs.

- `outputs\tables\gamma_sub_response_surface_anchor_verification_summary.json`
- `outputs\tables\gamma_sub_response_surface_anchor_verification_cases.csv`
- `outputs\tables\gamma_sub_sequential_protocol_design_summary.json`
- `outputs\tables\gamma_sub_sequential_protocol_design_cases.csv`
- `outputs\tables\f_sps_balanced_medium_budget_benchmark_summary.json`
- `outputs\tables\f_sps_balanced_medium_budget_benchmark_cases.csv`
- `outputs\tables\manuscript_claim_stress_test_summary.json`

Frozen Ground Truth v1.1 input arrays remain ignored by Git and were not modified.


## High-throughput gamma_sub and F-SPS medium-budget evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin benchmark evidence, not experimental data. They are generated from existing validated simulator-backed evidence or bounded CPU training against frozen Ground Truth v1.1 inputs.

- `outputs\tables\gamma_sub_tsw_dense_profile_likelihood_summary.json`
- `outputs\tables\gamma_sub_tsw_dense_profile_likelihood_grid.csv`
- `outputs\tables\gamma_sub_tsw_dense_profile_likelihood_profiles.csv`
- `outputs\tables\gamma_sub_recoverability_phase_diagram_summary.json`
- `outputs\tables\gamma_sub_recoverability_phase_diagram_cases.csv`
- `outputs\tables\gamma_sub_protocol_actual_inversion_validation_summary.json`
- `outputs\tables\gamma_sub_protocol_actual_inversion_validation_cases.csv`
- `outputs\tables\gamma_sub_weighted_protocol_objective_summary.json`
- `outputs\tables\gamma_sub_weighted_protocol_objective_cases.csv`
- `outputs\tables\gamma_sub_statistical_robustness_summary.json`
- `outputs\tables\gamma_sub_statistical_robustness_cases.csv`
- `outputs\tables\f_sps_medium_budget_benchmark_summary.json`
- `outputs\tables\f_sps_medium_budget_benchmark_cases.csv`

Frozen Ground Truth v1.1 input arrays remain ignored by Git and were not modified.

## Gamma_sub multi-protocol and profile-likelihood validation evidence

These lightweight tables were generated from frozen Ground Truth v1.1 parameters and in-memory synthetic protocol variants. They are synthetic numerical digital-twin validation evidence, not experimental data.

- `outputs\tables\gamma_sub_multi_protocol_recoverability_summary.json`
- `outputs\tables\gamma_sub_multi_protocol_recoverability_cases.csv`
- `outputs\tables\gamma_sub_tsw_profile_likelihood_summary.json`
- `outputs\tables\gamma_sub_tsw_profile_likelihood_grid.csv`
- `outputs\tables\gamma_sub_tsw_profile_likelihood_profiles.csv`
- `outputs\tables\gamma_sub_joint_inversion_boundary_summary.json`
- `outputs\tables\gamma_sub_joint_inversion_boundary_cases.csv`
- `outputs\tables\gamma_sub_protocol_observability_design_summary.json`
- `outputs\tables\gamma_sub_protocol_observability_design_cases.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.

## SCI gap-closing gamma_sub validation evidence

These lightweight tables were generated from frozen Ground Truth v1.1 parameters and sparse terminal observation times. They are synthetic numerical digital-twin validation evidence, not experimental data.

- `outputs\tables\gamma_sub_tsw_prior_width_sweep_summary.json`
- `outputs\tables\gamma_sub_tsw_prior_width_sweep_cases.csv`
- `outputs\tables\gamma_sub_temperature_anchor_placement_summary.json`
- `outputs\tables\gamma_sub_temperature_anchor_placement_cases.csv`
- `outputs\tables\gamma_sub_scalar_baseline_comparison.csv`
- `outputs\tables\gamma_sub_tsw_confounding_phase_map_summary.json`
- `outputs\tables\gamma_sub_tsw_confounding_phase_map_cases.csv`
- `outputs\tables\gamma_sub_auxiliary_observability_sweep_summary.json`
- `outputs\tables\gamma_sub_auxiliary_observability_sweep_cases.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.

## Observability-augmented gamma_sub evidence

These lightweight tables were generated from frozen Ground Truth v1.1 parameters and sparse terminal observation times. They are synthetic numerical digital-twin observability evidence, not experimental data.

- `outputs\tables\gamma_sub_observability_augmented_summary.json`
- `outputs\tables\gamma_sub_observability_augmented_cases.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.

## F-SPS-PINN v2 Fourier ablation evidence

These lightweight tables were generated from the frozen Ground Truth v1.1 triangle benchmark and sparse terminal observations. They are synthetic numerical digital-twin Fourier-ablation evidence, not formal performance results and not experimental data.

- `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json`
- `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.


## F-SPS-PINN v2 phase-transition stress evidence

These lightweight tables were generated from the frozen Ground Truth v1.1 triangle benchmark and sparse terminal observations. They are synthetic numerical digital-twin stress-preflight evidence, not formal performance results and not experimental data.

- `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.


## F-SPS-PINN v2 small-run baseline evidence

These lightweight tables were generated from the frozen Ground Truth v1.1 triangle benchmark and sparse terminal observations. They are synthetic numerical digital-twin small-run evidence, not formal performance results and not experimental data.

- `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json`
- `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.

## F-SPS-PINN v2 smoke training evidence

This lightweight JSON was generated from the frozen Ground Truth v1.1 triangle benchmark and sparse terminal observations. It is synthetic numerical digital-twin smoke evidence, not a performance result and not experimental data.

- `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`

The F-SPS-PINN architecture MVP itself produced no new dataset.

## Continuous off-grid gamma_sub refinement evidence

These lightweight tables were generated from the frozen Ground Truth v1.1 triangle benchmark and sparse terminal observations. They are synthetic numerical digital-twin benchmark evidence, not experimental data.

- `outputs\tables\gamma_sub_continuous_refinement_summary.json`
- `outputs\tables\gamma_sub_continuous_refinement_cases.csv`

The corresponding frozen input arrays remain ignored by Git and were not modified.

## Paper-readiness gamma_sub robustness evidence

These lightweight tables were generated from the frozen Ground Truth v1.1
triangle benchmark and sparse terminal observations. They are synthetic
numerical digital-twin benchmark evidence, not experimental data.

- `outputs\tables\gamma_sub_paper_readiness_summary.json`
- `outputs\tables\gamma_sub_observation_sensitivity.csv`
- `outputs\tables\gamma_sub_offgrid_summary.csv`

The corresponding frozen input arrays remain ignored by Git and were not
modified.

## Literature-backed constrained gamma_sub inversion evidence

These lightweight tables were generated from the frozen Ground Truth v1.1
triangle benchmark and sparse terminal observations. They are synthetic
numerical digital-twin benchmark evidence, not experimental data.

- `outputs\tables\gamma_sub_constrained_inversion_summary.json`
- `outputs\tables\gamma_sub_prior_width_sweep.csv`

The corresponding frozen input arrays remain ignored by Git and were not
modified.

## Reference-pack integration

The local reference pack at `E:\pinn_codex_reference_pack` was read and
compressed into documentation. No raw reference-pack files, PDF, DOCX, ZIP, NPZ,
cache, virtual environment, or large figure artifact was copied into the
repository.

The documentation-structure cleanup did not create or modify datasets.

## Frozen synthetic benchmark data

These files are generated by `scripts\run_gt_v1_acceptance.py` and are used as
the current benchmark source. They are synthetic numerical digital-twin data,
not experimental measurements.

- `data\processed\gt_v1_acceptance\gt_triangle.npz`
- `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- `data\processed\gt_v1_acceptance\gt_ltp_ltd.npz`
- `data\processed\gt_v1_acceptance\obs_ltp_ltd_sparse.npz`
- `data\processed\gt_v1_acceptance\manifest.json`

## PINN inverse v0 generated outputs

These are reproducible training artifacts and are ignored by Git:

- `outputs\pinn_inverse_v0\triangle\`
- `outputs\pinn_inverse_v0\triangle_full_anchor\`
- `outputs\pinn_inverse_v0\triangle_weak_anchor\`
- `outputs\pinn_inverse_v0\triangle_port_only\`

## Lightweight committed evidence

- `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- `outputs\tables\pinn_inverse_v1_summary.json`
- `outputs\tables\pinn_inverse_v1_1_summary.json`
- `outputs\tables\pinn_identifiability_summary.json`
- `outputs\tables\pinn_identifiability_correlation.csv`
- `outputs\tables\gamma_sub_identifiability_summary.json`
- `outputs\tables\gamma_sub_confounding_summary.json`
- `outputs\tables\gamma_sub_sensitivity_ranking.csv`

These JSON and CSV files store compact scalar metrics and correlations for
cloud review without committing large generated arrays or figures.
## Literature And Lightweight Evidence Tables

New lightweight committed data/table artifacts:

- `data/literature/literature_parameter_sanity_table.csv`
- `data/literature/literature_curve_registry.csv`
- `outputs/tables/literature_phase_change_parameter_sanity_summary.json`
- `outputs/tables/literature_curve_fit_external_anchor_summary.json`
- `outputs/tables/literature_curve_fit_external_anchor_cases.csv`
- `outputs/tables/gamma_sub_tsw_calibration_necessity_summary.json`
- `outputs/tables/gamma_sub_tsw_calibration_necessity_cases.csv`
- `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json`
- `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_cases.csv`

No frozen Ground Truth data were modified. No digitized external curve data were fabricated.

## External curve ingestion and calibrated gamma_sub evidence

These lightweight CSV/JSON files are synthetic numerical digital-twin manuscript evidence, not experimental data:

- `data/literature/literature_curve_ingestion_registry.csv`
- `outputs/tables/literature_curve_ingestion_summary.json`
- `outputs/tables/literature_curve_ingestion_cases.csv`
- `outputs/tables/literature_curve_fit_external_anchor_v2_summary.json`
- `outputs/tables/literature_curve_fit_external_anchor_v2_cases.csv`
- `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json`
- `outputs/tables/gamma_sub_tsw_calibration_workflow_cases.csv`
- `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json`
- `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_cases.csv`
- `outputs/tables/external_anchor_claim_stress_test_summary.json`
- `outputs/tables/submission_ready_gamma_sub_figures_summary.json`

No frozen Ground Truth file was modified. No digitized external curve data were fabricated.

## Calibration tolerance, protocol disentanglement, and submission lock evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin benchmark evidence, not experimental data:

- `outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json`
- `outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_cases.csv`
- `outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json`
- `outputs/tables/gamma_sub_calibration_protocol_disentanglement_cases.csv`
- `outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json`
- `outputs/tables/gamma_sub_calibrated_protocol_robustness_final_cases.csv`
- `outputs/tables/literature_targeted_curve_extraction_attempt_summary.json`
- `outputs/tables/literature_targeted_curve_extraction_attempt_cases.csv`
- `outputs/tables/final_submission_lock_summary.json`
- `data/literature/manual_digitization_queue.csv`

No frozen Ground Truth data were modified. No external curve points were fabricated.

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

## Stiffness Continuation And Phase-Field Alignment Evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin supplementary evidence, not experimental data:

- `outputs/tables\phase_transition_stiffness_continuation_audit_summary.json`
- `outputs/tables\phase_transition_stiffness_continuation_audit_cases.csv`
- `outputs/tables\phase_field_inverse_alignment_smoke_summary.json`
- `outputs/tables\phase_field_inverse_alignment_smoke_cases.csv`

No frozen Ground Truth v1.1 file was modified.

## Final Figure Literature Lock And Stiffness 2D Story Evidence

This lightweight manifest is synthetic numerical digital-twin supplementary evidence, not experimental data:

- `outputs/tables/stiffness_2d_story_figure_manifest.json`

The generated PNG files under `outputs/figures/` are reproducible and ignored by Git. No frozen Ground Truth v1.1 file was modified.

## Claim-Gate Experimental Resolution Evidence

These lightweight JSON/CSV files are synthetic numerical digital-twin benchmark evidence, not experimental data:

- `outputs	ables
educed_2d_phase_transition_forward_summary.json`
- `outputs	ables
educed_2d_phase_transition_forward_cases.csv`
- `outputs	ables
educed_2d_observability_limited_inverse_summary.json`
- `outputs	ables
educed_2d_observability_limited_inverse_cases.csv`
- `outputs	ables\stiffness_aware_algorithm_benchmark_summary.json`
- `outputs	ables\stiffness_aware_algorithm_benchmark_cases.csv`

Generated PNGs under `outputsigures\` are reproducible and ignored by Git. No frozen Ground Truth v1.1 file was modified.

## Integrated high-risk claim ladder quick-profile evidence

These lightweight tables are synthetic numerical digital-twin benchmark evidence, not experimental data. Generated figures remain ignored by Git.

- `outputs/tables/high_risk_claim_ladder_summary.json`
- `outputs/tables/high_risk_claim_ladder_cases.csv`
- `outputs/tables/integrated_stiffness_stl_summary.json`
- `outputs/tables/integrated_stiffness_stl_cases.csv`
- `outputs/tables/fourier_fsps_conditional_superiority_summary.json`
- `outputs/tables/fourier_fsps_conditional_superiority_cases.csv`

Frozen Ground Truth v1.1 files were not modified.

## Actualized high-risk claim ladder v2 evidence

These lightweight tables are synthetic numerical digital-twin benchmark evidence, not experimental data.

- `outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json`
- `outputs/tables/high_risk_claim_ladder_actual_inverse_cases.csv`
- `outputs/tables/fourier_fsps_actual_training_summary.json`
- `outputs/tables/fourier_fsps_actual_training_cases.csv`
- Updated: `outputs/tables/integrated_stiffness_stl_summary.json`
- Updated: `outputs/tables/integrated_stiffness_stl_cases.csv`

Frozen Ground Truth v1.1 files were not modified.
## Port-Physical 2D Inverse And Stiffness-Gated Training v3 Evidence

These lightweight tables are synthetic numerical digital-twin benchmark evidence, not experimental data:

- `outputs/tables/port_physical_2d_inverse_summary.json`
- `outputs/tables/port_physical_2d_inverse_cases.csv`
- `outputs/tables/stiffness_gated_fourier_fsps_summary.json`
- `outputs/tables/stiffness_gated_fourier_fsps_cases.csv`
- Updated: `outputs/tables/integrated_stiffness_stl_summary.json`
- Updated: `outputs/tables/integrated_stiffness_stl_cases.csv`

No frozen Ground Truth v1.1 files were modified.

## OASIS-PINN Multilayer Sandwich And High-Risk Resolution v6

No new large dataset was added. The pack generated lightweight synthetic numerical CSV/JSON tables under `outputs/tables/`. Generated figures under `outputs/figures/` are reproducible and not committed by default. Frozen Ground Truth v1.1 data were not modified.

## OASIS-PINN Evidence Actualization v7 Tables

These lightweight tables are synthetic numerical digital-twin benchmark evidence, not experimental data:

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

No frozen Ground Truth v1.1 files were modified.
