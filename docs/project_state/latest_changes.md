# Latest changes

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
