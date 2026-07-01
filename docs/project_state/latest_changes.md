# Latest changes

## High-throughput gamma_sub identifiability and F-SPS medium-budget pack

Scope:

- Add dense response-surface, recoverability phase-diagram, protocol actual-validation, weighted-objective, and statistical robustness audits for constrained `gamma_sub` recovery.
- Add bounded F-SPS medium-budget planning benchmark without checkpoints or large output directories.
- Keep frozen Ground Truth v1.1 and existing v0/v1/v1.1 results unchanged.

Changed:

- Added `configs\gamma_sub_tsw_dense_profile_likelihood.yaml`.
- Added `configs\gamma_sub_recoverability_phase_diagram.yaml`.
- Added `configs\gamma_sub_protocol_actual_inversion_validation.yaml`.
- Added `configs\gamma_sub_weighted_protocol_objective.yaml`.
- Added `configs\gamma_sub_statistical_robustness.yaml`.
- Added `configs\f_sps_medium_budget_benchmark.yaml`.
- Added `scripts\gamma_sub_high_throughput_common.py`.
- Added six audit/training scripts and one high-throughput figure builder.
- Added six tests for the new audits and medium-budget benchmark.
- Added lightweight JSON/CSV evidence under `outputs\tables\`.
- Generated ignored figure-ready PNGs under `outputs\figures\high_throughput_sci\`.
- Added `docs\codex_reports\gamma_sub_high_throughput_identifiability_and_f_sps_medium_budget_report.md`.

Result:

All official high-throughput outputs are finite. The pack supports the constrained `gamma_sub` manuscript line as conditional synthetic numerical evidence, but it also sharpens the limitation that `T_sw` mismatch remains the dominant failure mode. The bounded F-SPS medium-budget subset does not support a performance-superiority claim.

## Gamma_sub multi-protocol and profile-likelihood validation pack

Scope:

- Add multi-protocol recoverability across triangle, LTP/LTD, derived multi-amplitude synthetic, and mixed-protocol objectives.
- Add a `gamma_sub` by `T_sw` profile-likelihood landscape to quantify objective ridge geometry.
- Add a joint inversion boundary audit that releases nuisance parameters in lightweight candidate grids.
- Add protocol observability design preflight using finite-difference sensitivity vectors.
- Keep frozen Ground Truth v1.1 read-only and do not add F-SPS-PINN experiments.

Changed:

- Added `configs\gamma_sub_multi_protocol_recoverability.yaml`.
- Added `configs\gamma_sub_tsw_profile_likelihood.yaml`.
- Added `configs\gamma_sub_joint_inversion_boundary.yaml`.
- Added `configs\gamma_sub_protocol_observability_design.yaml`.
- Added `scripts\gamma_sub_validation_common.py`.
- Added `scripts\audit_gamma_sub_multi_protocol_recoverability.py`.
- Added `scripts\audit_gamma_sub_tsw_profile_likelihood.py`.
- Added `scripts\audit_gamma_sub_joint_inversion_boundary.py`.
- Added `scripts\audit_gamma_sub_protocol_observability_design.py`.
- Added `scripts\build_gamma_sub_sci_validation_figures.py`.
- Added four tests under `tests\` for the new audits.
- Added lightweight JSON/CSV evidence under `outputs\tables\`.
- Generated ignored figure-ready PNGs under `outputs\figures\gamma_sub_sci_validation\`.
- Added `docs\codex_reports\gamma_sub_multi_protocol_and_profile_likelihood_validation_report.md`.

Result:

The official runs are finite and frozen inputs are unchanged. Multi-protocol recovery contains 48 cases, with `ltp_ltd` the best mean-error protocol and wide `T_sw` mismatch still failing across protocols. The profile landscape has condition number `10.762998753222757` and an elongated `gamma_sub`/`T_sw` ridge. The joint-boundary audit identifies `gamma_plus_T_sw_plus_tau_m` as most ambiguous and `gamma_plus_sigma_on0` as the worst gamma-error release. The protocol-design preflight ranks `multi_pulse` highest by distinguishability and recommends `long_pulse` and `short_pulse` under the configured rule.

## Auxiliary observability sweep

Scope:

- Compare port-only, sparse/dense synthetic temperature, temporal-derivative, switching-state, sigma-aggregate, and calibrated-`T_sw` observability modes under a controlled wide `T_sw` mismatch.
- Estimate only `gamma_sub`; keep frozen Ground Truth v1.1 read-only.
- Generate lightweight JSON/CSV evidence and figure-ready plots without adding training artifacts.

Changed:

- Added `configs\gamma_sub_auxiliary_observability_sweep.yaml`.
- Added `scripts\audit_gamma_sub_auxiliary_observability_sweep.py`.
- Added `tests\test_gamma_sub_auxiliary_observability_sweep.py`.
- Updated `scripts\build_gamma_sub_gap_closing_figures.py`.
- Added `outputs\tables\gamma_sub_auxiliary_observability_sweep_summary.json`.
- Added `outputs\tables\gamma_sub_auxiliary_observability_sweep_cases.csv`.
- Added `docs\codex_reports\gamma_sub_auxiliary_observability_sweep_report.md`.
- Generated ignored figure-ready PNGs `outputs\figures\gamma_sub_gap_closing\auxiliary_observability_heatmap.png` and `outputs\figures\gamma_sub_gap_closing\auxiliary_mode_comparison.png`.

Result:

The official 172-case sweep is finite and keeps frozen inputs unchanged. Only the calibrated-`T_sw` cases are recoverable at `relative_error <= 0.1` and `<= 0.2`; the best non-calibrated auxiliary proxy remains at relative error `1.0`. This strengthens the manuscript boundary that independent `T_sw` calibration dominates in the wide-mismatch regime.

## T_sw confounding phase-map audit

Scope:

- Add a two-dimensional `T_sw_delta_K` by `T_sw_prior_width` phase map for constrained `gamma_sub` recovery.
- Estimate only `gamma_sub`; keep frozen Ground Truth v1.1 read-only.
- Generate reproducible figure-ready gap-closing plots without adding training artifacts.

Changed:

- Added `configs\gamma_sub_tsw_confounding_phase_map.yaml`.
- Added `scripts\audit_gamma_sub_tsw_confounding_phase_map.py`.
- Added `tests\test_gamma_sub_tsw_confounding_phase_map.py`.
- Added `scripts\build_gamma_sub_gap_closing_figures.py`.
- Added `outputs\tables\gamma_sub_tsw_confounding_phase_map_summary.json`.
- Added `outputs\tables\gamma_sub_tsw_confounding_phase_map_cases.csv`.
- Added `docs\codex_reports\gamma_sub_tsw_confounding_phase_map_report.md`.
- Generated ignored figure-ready PNGs under `outputs\figures\gamma_sub_gap_closing\`.

Result:

The official 42-case phase map is finite and keeps frozen inputs unchanged. `gamma_sub` recovery is robust only in the low residual-`T_sw` region: 27 cases are recoverable at `relative_error <= 0.1`, 32 cases at `<= 0.2`, and the widest `T_sw` uncertainty still yields relative error `1.2222222222222223`.

## SCI gap-closing validation pack

Scope:

- Add T_sw prior-width sweep for `gamma_sub` error trend.
- Add temperature-anchor placement audit to test whether anchor failure is a placement artifact.
- Add scalar baseline comparison to show optimizer novelty is not the main claim.
- Keep frozen Ground Truth and F-SPS-PINN paths unchanged.

Result:

`gamma_sub` relative error falls from `1.2222222222222223` to `0.05555555555555555` as `T_sw_prior_width` narrows from `1.0` to `0.02`. Temperature-anchor placement variants do not reduce the wide-mismatch bias. Simple scalar baselines solve the fixed-prior reduced problem, so the contribution remains identifiability-guided target reduction plus prior-boundary auditing.

## Observability-augmented gamma_sub audit

Scope:

- Test whether minimal synthetic temperature anchors or narrower `T_sw` priors reduce `gamma_sub` / `T_sw` confounding.
- Keep frozen Ground Truth v1.1 files read-only.
- Do not add F-SPS-PINN experiments or large training runs.

Changed:

- Added `configs\gamma_sub_observability_augmented.yaml`.
- Added `scripts\audit_gamma_sub_observability_augmented.py`.
- Added `tests\test_gamma_sub_observability_augmented.py`.
- Added `outputs\tables\gamma_sub_observability_augmented_summary.json`.
- Added `outputs\tables\gamma_sub_observability_augmented_cases.csv`.
- Added `docs\gamma_sub_observability_augmented_report.md`.
- Added `docs\codex_reports\gamma_sub_observability_augmented_report.md`.

Result:

Sparse temperature anchors alone did not reduce the wide `T_sw` mismatch bias in this candidate-grid audit. Narrowing the `T_sw` prior reduced `gamma_sub` relative error from `1.2222222222222223` to `0.2222222222222222`.

## SCI manuscript evidence consolidation

Scope:

- Consolidate existing synthetic numerical digital-twin evidence into manuscript-ready claim, figure, and table routing.
- Keep constrained `gamma_sub` inversion as the main SCI paper line.
- Place F-SPS-PINN v2 smoke, baseline, stress, and Fourier evidence in appendix, discussion, or future work.
- Do not run new training experiments or modify frozen Ground Truth v1.1.

Changed:

- Added `docs\paper\sci_manuscript_evidence_matrix.md`.
- Updated `docs\paper\model_hierarchy_and_claim_boundary.md`.
- Updated `docs\paper\equation_variable_registry.md`.
- Updated `docs\paper\experiment_to_figure_mapping.md`.
- Updated `CODEX_CONTEXT.md`, `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, and `docs\research_strategy\active_phase.md`.
- Added `docs\codex_reports\sci_manuscript_evidence_consolidation_report.md`.

Result:

The current manuscript direction is narrowed to sparse-port inverse identifiability, target-space reduction, and constrained `gamma_sub` inversion under fixed or tightly bounded priors. F-SPS-PINN remains bounded method-development evidence and is not a main performance claim.

## F-SPS-PINN v2 Fourier on/off ablation under stress

Scope:

- Compare `vo2_sigma_fourier_off` and `vo2_sigma_fourier_on` under the same sharp-transition stress condition.
- Reuse v2 baseline data loading, training loop, metrics, and frozen-input checks.
- Keep frozen Ground Truth v1.1 and old v0/v1/v1.1 paths unchanged.
- Treat results as small-run synthetic numerical evidence only, not a formal performance conclusion.

Changed:

- Added `configs\pinn_inverse_v2_fourier_ablation.yaml`.
- Added `scripts\run_pinn_inverse_v2_fourier_ablation.py`.
- Added `tests\test_pinn_inverse_v2_fourier_ablation.py`.
- Added `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json`.
- Added `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`.
- Added opt-in `use_fourier` support to `src\pinnpcm\pinn\network.py` and v2 baseline utilities.
- Updated project state, registries, file inventory, and reproducibility notes.

Result:

Both Fourier-off and Fourier-on runs produced finite losses, used `white_box_vo2_sigma`, did not use free `log_sigma`, and preserved frozen input hashes and mtimes. Fourier on does not clearly outperform Fourier off in this small-run result.


## F-SPS-PINN v2 phase-transition stress preflight

Scope:

- Exercise the white-box `vo2_sigma` path under `mild_transition`, `sharp_transition`, `near_threshold`, and `high_contrast` settings.
- Reuse v2 baseline data loading, training loop, metrics, and frozen-input checks.
- Keep frozen Ground Truth v1.1 and old v0/v1/v1.1 paths unchanged.
- Treat results as stress-preflight synthetic numerical evidence only, not a formal performance conclusion.

Changed:

- Added `configs\pinn_inverse_v2_phase_transition_stress.yaml`.
- Added `scripts\run_pinn_inverse_v2_phase_transition_stress.py`.
- Added `tests\test_pinn_inverse_v2_phase_transition_stress.py`.
- Added `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`.
- Added `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`.
- Updated project state, registries, file inventory, and reproducibility notes.

Result:

All four stress cases produced finite losses, used `white_box_vo2_sigma`, did not use free `log_sigma`, and preserved frozen input hashes and mtimes. This is a preflight stability check only.


## F-SPS-PINN v2 small-run baseline

Scope:

- Compare `free_log_sigma` and `white_box_vo2_sigma` under matched seed, epochs, field-anchor count, and sparse terminal observations.
- Keep frozen Ground Truth v1.1 and old v0/v1/v1.1 paths unchanged.
- Treat results as small-run synthetic numerical evidence only, not a formal performance conclusion.

Changed:

- Added `configs\pinn_inverse_v2_f_sps_baseline.yaml`.
- Added `scripts\run_pinn_inverse_v2_baseline.py`.
- Added `tests\test_pinn_inverse_v2_baseline.py`.
- Added `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json`.
- Added `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`.
- Updated project state, registries, file inventory, and reproducibility notes.

Result:

Both baseline modes produced finite losses and loss decreases in the 8-epoch CPU small run. The white-box `vo2_sigma` path did not use free `log_sigma`; the free-log-sigma run remains only an ablation baseline. Frozen input hashes and mtimes were unchanged.



## Continuous off-grid gamma_sub refinement audit

Scope:

- Replace candidate-profile interpolation with simulator-backed continuous scalar refinement for off-grid `gamma_sub`.
- Test true `gamma_sub = 4.38e8, 4.62e8, 5.15e8`, `n_obs = 8, 16, 32, 64`, and noise `0, 0.02, 0.05`.
- Keep frozen Ground Truth v1.1 and all prior v0/v1/v1.1, identifiability, confounding, constrained inversion, and paper-readiness evidence unchanged.

Changed:

- Added `scripts\refine_gamma_sub_continuous.py`.
- Added `tests\test_gamma_sub_continuous_refinement.py`.
- Added `outputs\tables\gamma_sub_continuous_refinement_summary.json`.
- Added `outputs\tables\gamma_sub_continuous_refinement_cases.csv`.
- Added `docs\gamma_sub_continuous_refinement_report.md`.
- Added `docs\codex_reports\gamma_sub_continuous_refinement_report.md`.
- Updated project state, registries, and reproducibility notes.

Result:

All official off-grid cases exclude true `gamma_sub` from the candidate grid and evaluate non-grid simulator calls during refinement. Maximum nearest-grid relative error is `0.08225108225108226`; maximum continuous-refined relative error is `0.05565017963752034`; `T_sw` remains the limiting confounder.



## Paper-readiness gamma_sub robustness pack

Scope:

- Add manuscript-defense documents for model hierarchy, equation variables, and
  experiment-to-figure mapping.
- Add a lightweight audit for off-grid `gamma_sub` localization and
  observation-count sensitivity.
- Keep frozen Ground Truth v1.1 and existing v0/v1/v1.1, identifiability,
  confounding, and constrained-inversion evidence unchanged.

Changed:

- Added `docs\paper\model_hierarchy_and_claim_boundary.md`.
- Added `docs\paper\equation_variable_registry.md`.
- Added `docs\paper\experiment_to_figure_mapping.md`.
- Added `scripts\audit_gamma_sub_paper_readiness.py`.
- Added `tests\test_gamma_sub_paper_readiness.py`.
- Added `outputs\tables\gamma_sub_paper_readiness_summary.json`.
- Added `outputs\tables\gamma_sub_observation_sensitivity.csv`.
- Added `outputs\tables\gamma_sub_offgrid_summary.csv`.
- Added `docs\gamma_sub_paper_readiness_report.md`.
- Added `docs\codex_reports\gamma_sub_paper_readiness_report.md`.
- Updated project state, registries, and reproducibility notes.

Result:

Off-grid `gamma_sub = 4.62e8` was localized with nearest-grid relative error
`0.025974025974025976` and refined relative error `4.054410066065334e-05`.
Nominal recovery stayed exact for `n_obs = 8, 16, 32, 64`; `T_sw` remained the
most dangerous confounder.



## Recent history index

For complete historical details, use:

- chronological findings: `RESEARCH_LOG.md`
- experiment outputs and runners: `EXPERIMENT_REGISTRY.md`
- dataset and lightweight evidence: `DATASET_REGISTRY.md`
- generated figures: `FIGURE_REGISTRY.md`
- file ownership and reports: `docs\project_state\file_inventory.md`
- stage reports: `docs\codex_reports\`



## Documentation structure cleanup

Scope:

- Reduce repeated status material in the explanatory Markdown files.
- Keep `CODEX_CONTEXT.md` plus `docs\research_strategy\active_phase.md` as the
  low-token first-read pair.
- Keep `docs\research_strategy\context_loading_policy.md` as the complete Tier
  0 through Tier 4 loading rule.
- Do not delete referenced context files without a stronger uniqueness audit.

Changed:

- `PROJECT_STATE.md`: shortened to current phase, frozen benchmark, current
  evidence, boundary, and pointers to registries.
- `docs\project_state\latest_changes.md`: converted from a full historical
  changelog into a recent-change summary plus index.
- `AGENTS.md`: keeps top-level engineering rules and points to the context
  loading policy for detailed Codex workflow.
- `docs\codex_reports\local_codex_context_integration_report.md`: now records
  concrete verification results from the context-integration task.



## Local Codex context workflow integration

Added the low-token context workflow files and compressed literature/reference
notes. Frozen Ground Truth v1.1 files, source code, configs, tests, large
generated data, and generated figures were not modified in that documentation
integration task.
