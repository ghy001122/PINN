## Control-volume multidomain OASIS and inverse repair v10

## Workspace governance, memory, and goal hierarchy

Scope:

- Consolidate root and subtree AGENTS without changing research evidence.
- Create a stable project goal, compact dashboard, durable-memory policy, and project-local command-safety rules.
- Replace conflicting root current-state prose with single v10 snapshot/queue files while preserving old content under `docs/archive/`.
- Add an automated governance and frozen-GT integrity audit.

Result:

Governance-only change. No experiment was run, no historical metric was rewritten, and frozen GT v1.1 was not modified.
Scope:

- Correct v9 evidence semantics by separating electrical and thermal topology, removing the substrate-conductance bypass, adding actual control-volume residuals, repairing noisy-target re-inversion, and adding segmented-electrode y-z forward checks.
- Keep all evidence synthetic numerical digital-twin benchmark evidence; frozen Ground Truth v1.1 remains unchanged.

Changed:

- Added v10 physical-semantics, CV training, active-protocol inverse, segmented-forward, generalization, and algorithm-gate scripts/tests/evidence tables.
- Added `docs/codex_reports/cv_multidomain_oasis_and_inverse_repair_v10_report.md` and the v10 lightweight JSON/CSV tables listed in `DATASET_REGISTRY.md`.
- Added `docs/research_strategy/codex_new_dialog_handoff_d23a576.md` as the new-dialog handoff anchored to `d23a576b2d8bb17a1d1f72a0cf81cc457d42e048`.

Result:

P0 physical semantics are `qualified_supported`; P1 CV/mortar training is `failed_but_informative`; P2 repaired noisy inverse is `failed_but_informative`; P3 segmented-electrode y-z forward is `qualified_supported` for forward/observability only; P4 remains `not_run_blocked`. The constrained `gamma_sub` line remains the SCI core claim, and OASIS v10 is supplementary implementation/negative-result evidence.


## Phase-activated multidomain OASIS-PINN v9

Scope:

- Activate real reduced-device physics after v8 showed nearly zero heating/phase change.
- Add material-family-specific kernels, independent interface maps, coupled y-z lateral conduction, activation gates, manufactured/refinement checks, multidomain training, activated terminal inverse, and blocked 2D/STL/Fourier gates.

Result:

P0 and P1 pass. P2 improves substantially but strict block-wise sequential inverse remains failed-but-informative. P3 and P4 remain blocked.

## Conservative multidomain OASIS-PINN v8

Scope:

- Add a conservative finite-volume 2.5D multilayer forward audit with per-interface contact and thermal-boundary terms.
- Add actual-autograd multidomain OASIS-PINN component smoke.
- Add terminal-only active protocol normalized-Jacobian and sequential inverse gate.
- Add a 2D field-resolution block gate that refuses positive claims without actual electrode-BC multi-terminal support.
- Tighten phase-aware STL repair and Fourier/F-SPS evidence under matched-budget and true-Pareto rules.

Result:

Conservative P0 and component smoke pass; active terminal rescue, 2D field recovery, full STL-PINN reproduction, LoRA-STL, and universal Fourier/F-SPS superiority remain unsupported.


﻿# Latest changes

## Response-surface verification and manuscript claim consolidation pack

Scope:

- Verify response-surface evidence against simulator-backed source-grid anchors.
- Add sequential protocol-design value-of-information preflight.
- Add balanced F-SPS medium-budget coverage across all model labels and epoch budgets.
- Build claim stress-test, proposed figure/table docs, manuscript outline, and manuscript-ready figure builder.
- Keep frozen Ground Truth v1.1 and existing v0/v1/v1.1/gamma_sub/F-SPS results unchanged.

Changed:

- Added `configs\gamma_sub_response_surface_anchor_verification.yaml`.
- Added `configs\gamma_sub_sequential_protocol_design.yaml`.
- Added `configs\f_sps_balanced_medium_budget_benchmark.yaml`.
- Added `scripts\audit_gamma_sub_response_surface_anchor_verification.py`.
- Added `scripts\audit_gamma_sub_sequential_protocol_design.py`.
- Added `scripts\train_f_sps_balanced_medium_budget_benchmark.py`.
- Added `scripts\build_manuscript_claim_stress_test.py`.
- Added `scripts\build_manuscript_ready_gamma_sub_figures.py`.
- Added four tests for new scripts and schema checks.
- Added lightweight JSON/CSV evidence under `outputs\tables\`.
- Generated ignored figure-ready PNGs under `outputs\figures\manuscript_ready_gamma_sub\`.
- Added `docs\paper\claim_stress_test_matrix.md`, `docs\paper\proposed_main_figures.md`, `docs\paper\proposed_tables.md`, and `docs\paper\manuscript_outline_v1.md`.

Result:

Anchor verification uses 60 cases and supports the response-surface phase diagrams only with explicit qualification. Sequential protocol design identifies `multi_pulse_to_ltp_ltd` as the best response-surface preflight candidate, but this remains a hypothesis requiring stronger validation. Balanced F-SPS executes 12 finite cases with even model/epoch coverage and still does not support F-SPS superiority.


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
## Literature-Anchored Calibration And Simulator-Backed Protocol Validation Pack

This pack adds literature/engineering-prior sanity checks, external-curve provenance handling, a T_sw calibration-necessity audit, and simulator-backed sequential protocol validation for the constrained `gamma_sub` manuscript line. All outputs remain synthetic numerical digital-twin benchmark evidence, not experimental data.

Key results:

- Literature sanity checks cover `8` parameters; `1` item is flagged as boundary-sensitive.
- No provenance-backed digitized literature curve CSV was found; external curve fitting is blocked rather than fabricated.
- T_sw calibration necessity: minimum reliable tested T_sw prior width is `0.02`, wide-prior relative error is `0.8309764722472351`, and wrong-calibration relative error is `0.3021732626353582`.
- Simulator-backed sequential protocol validation runs `150` finite ODE-backed cases. Best mean-error candidate is `multi_pulse_to_ltp_ltd` and it matches the response-surface preflight best: `True`.
- Frozen GT hashes are unchanged: `True`.

Claim boundary: this strengthens reviewer defense for constrained reduced `gamma_sub` inversion under fixed or tightly bounded priors. It does not prove sparse-port full hidden-field recovery, real device calibration, or F-SPS-PINN superiority.

## External Curve Ingestion And Calibrated Gamma_Sub Manuscript Workflow Pack

This pack adds provenance-backed literature-curve ingestion infrastructure, external curve-fit v2 blocked handling, T_sw calibration-before-inversion workflow evidence, ODE-backed calibrated sequential protocol validation, external-anchor claim stress testing, and manuscript draft scaffolding.

Key results:

- Literature curve ingestion found `0` valid provenance-backed digitized CSV curves from `0` scanned files; blocked reason: `no_provenance_backed_digitized_curve_csv_found`.
- External curve fitting v2 fit `0` curves and remains blocked because `blocked: no provenance-backed digitized curves available`.
- T_sw calibration workflow: no-calibration relative error `0.8309764722472351`, best workflow `synthetic_probe_calibrated_T_sw` relative error `0.037771657829419776`, wrong-calibration control relative error `0.3021732626353582`.
- Calibrated sequential validation: `720` ODE-backed cases; best protocol `calibrated_multi_pulse_to_ltp_ltd`; success-rate gain over no calibration `0.4833333333333333`; frozen GT unchanged `True`.

Claim boundary: this strengthens a constrained reduced `gamma_sub` manuscript under fixed or tightly bounded priors. It does not prove experimental validation, sparse-port full hidden-field recovery, or F-SPS-PINN superiority.

## Calibration Tolerance, Protocol Disentanglement, And Submission Lock Pack

This pack adds reviewer-defense evidence for the constrained `gamma_sub` manuscript line. All outputs are synthetic numerical digital-twin benchmark evidence, not experimental data.

Key results:

- T_sw calibration tolerance sweep: maximum median-error-compatible calibration error is `0.1` K and maximum compatible post-calibration prior width is `0.05` under the <=15% criterion.
- Calibration-vs-protocol disentanglement: total gain `1.1381068369066785`, calibration gain `1.1216748794829614`, protocol gain `0.014955665059772812`, interaction gain `0.0014762923639442468`. Protocol advantage survives equal-prior control: `True`, but the previous protocol claim needs qualification: `True`.
- ODE-backed calibrated protocol robustness: `2400` simulator-backed cases. Best protocol is `calibrated_short_pulse_to_ltp_ltd` with success rate `0.9604166666666667` and worst-case error `0.4444444444444444`. Ready as main figure without qualification: `False`.
- Targeted external curve extraction found `0` valid digitized curve tables and queued `6` manual digitization candidates. External curve fitting remains blocked: `no_provenance_backed_digitized_curve_tables_found`.
- Final figure/table/claim lock: `7` figures, `7` tables, claim matrix locked `True`.

Claim boundary: the paper can claim calibration-gated constrained `gamma_sub` recovery under fixed or tightly bounded priors. It cannot claim experimental protocol validation, public-curve fitting, unconditional identifiability, or sparse-port full hidden-field recovery.

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

## Stiffness continuation and phase-field alignment pack

Scope:

- Add a lightweight phase-transition residual-stiffness audit over transition width, T_sw offset, model type, continuation strategy, and seed.
- Add a lightweight Allen-Cahn phase-field mobility inverse smoke benchmark for related-work alignment.
- Add journal-positioning, novelty-gap, and SCI two/three-zone gap documents.
- Keep frozen Ground Truth v1.1 and all prior main results unchanged.

Result:

The stiffness audit produces `180` finite cases and supports a residual-cliff defense with sharpest/widest ratio `11.894639315460832`. The phase-field smoke benchmark produces `27` finite cases with median M relative error `0.04331110242687686`. Both are supplementary synthetic numerical evidence only.

## Final figure literature lock and stiffness 2D story pack

Scope:

- Lock Drive/web/repo-local literature evidence for stiffness, phase-field inverse alignment, diffuse-interface/enthalpy phase-change background, VO2 phase-field motivation, compact memristor PINN, and physics-regularized surrogate framing.
- Generate five supplementary stiffness/phase-field figures from existing lightweight JSON/CSV tables.
- Add final submission storyboards, abstract candidate, cover letter draft, and checklist.
- Keep frozen Ground Truth v1.1 unchanged and keep the main `gamma_sub` claim unchanged.

Result:

The project now has a clearer third-zone SCI submission package: main text around calibration-gated constrained `gamma_sub`, supplementary stiffness/phase-field/quasi-2D defense, and explicit second-zone risk boundaries.

## Claim-Gate Experimental Resolution Pack

- Added reduced 2D forward benchmark script/config/test and generated lightweight summary/cases tables.
- Added reduced 2D observability ladder for terminal-only, multi-pulse, proxy-temperature, and multi-contact observations.
- Added stiffness-aware algorithm residual-proxy benchmark with direct, continuation, scale-aware, combined, and mini-STL-style transfer strategies.
- Added `docs/paper/claim_gate_resolution_matrix.md` and updated manuscript/reviewer-defense docs.
- Frozen Ground Truth v1.1 was not modified; outputs are synthetic numerical digital-twin evidence only.

## Integrated high-risk claim ladder quick profile

Scope:

- Add a unified reduced 2D high-risk claim ladder with quick and extended profiles.
- Add actual reduced autograd PINN stiffness training and Seiler-style shared-trunk multi-head transfer audit.
- Add Fourier/F-SPS conditional superiority residual-proxy sweep.
- Keep frozen Ground Truth v1.1, v0/v1/v1.1, constrained `gamma_sub`, and prior claim-gate results unchanged.

Result:

The official quick outputs are finite. Dense augmented anchors support only protocol-limited low-rank 2D hidden-field wording; terminal-only full-field recovery remains failed_but_informative. Actual reduced PINN training clears the stiffness-mitigation gate, and Seiler-style multi-head transfer clears the reduced benchmark transfer gate. Fourier/F-SPS-style methods are conditionally useful in sharp/front regimes, while universal superiority remains forbidden.

## Actualized high-risk claim ladder v2

Scope:

- Replace the 2D heuristic field claim with actual low-rank coefficient inversion evidence.
- Expand actual stiffness PINN/STL quick audit from 20 to 90 cases and add gradient/residual diagnostics.
- Replace Fourier/F-SPS residual-proxy multipliers with actual reduced autograd training.

Result:

The actualized evidence is stricter than the previous quick profile. Actual 2D field recovery remains `forbidden`, terminal-only field recovery remains `failed_but_informative`, and only terminal low-dimensional parameter recovery is `qualified_supported`. Continuation/asinh/adaptive stiffness handling remains `qualified_supported`, but Seiler-style multi-head transfer is `failed_but_informative` after the expanded grid. Fourier/F-SPS actual training is `failed_but_informative` for conditional benefit and `forbidden` for universal superiority.
## Port-Physical 2D Inverse And Stiffness-Gated Training v3 Pack

This pack adds port-physical reduced 2D inverse evidence, stiffness-gated Fourier/F-SPS actual-training evidence, and a matched-budget STL repair audit. All outputs remain synthetic numerical digital-twin benchmark evidence, not experimental data.

Key results:

- Port-physical 2D inverse: `320` finite cases, `uses_port_physical_observation = true`, `uses_phase_mean_as_terminal_observation = false`.
- Port-physical best protocol is `port_only`, but median field error is `0.7692662179470062`, worse than the v2 actual low-rank inverse reference `0.544268189851365`; field recovery remains `forbidden`.
- Analytic basis outperforms POD in this quick profile; POD is `failed_but_informative`, not a positive basis-learning claim.
- Fisher anchors do not clear the recovery gate; anchor placement remains an optimization target.
- Stiffness-gated hybrid: `96` finite actual-training cases, sharp/front gain `0.17299439024092061`, smooth degradation `0.0`, status `qualified_supported` as condition-limited method-development evidence.
- STL repair: integrated stiffness/STL audit expanded to `162` cases; best repair is `STL_repair_head_only` with gain `-0.14315251294108938`, status `failed_but_informative`.

Claim boundary: this improves physical realism and reviewer defense, but does not change the main manuscript line. Full 2D hidden-field recovery, full STL-PINN reproduction, universal Fourier/F-SPS superiority, and experimental validation remain forbidden.

## OASIS-PINN Multilayer Sandwich And High-Risk Resolution v6

Added literature-prior consistency audit, boundary-aware multilayer sandwich forward benchmark, OASIS-PINN components, 2D field resolution ladder, active terminal-only low-dimensional rescue, phase-aware STL repair audit, adaptive Fourier/F-SPS actual-training audit, and low-dimensional sandwich inverse smoke. All outputs are synthetic numerical digital-twin evidence and are claim-gated.

## OASIS-PINN Evidence Actualization v7

Scope:

- Replace v6 proxy-positive evidence with simulator-backed or actual-training audits.
- Compute multilayer residuals and energy balance explicitly rather than using stub values.
- Keep frozen Ground Truth v1.1 unchanged and keep the main `gamma_sub` manuscript line unchanged.

Result:

The stricter evidence downgrades several high-risk supplementary claims. Multilayer forward fails the energy-balance gate, terminal-only and low-dimensional sandwich inverse audits are failed-but-informative, holdout POD 2D field recovery is forbidden, and phase-aware STL remains weak. The only positive method-development result is condition-limited `stiffness_gated_fourier`; `adaptive_f_sps` and universal superiority remain unsupported.
