# Research log

## Response-surface verification and manuscript claim consolidation pack

Date: 2026-07-01

Actions:

- Added response-surface anchor verification against simulator-backed profile source grids and phase-map cases.
- Added sequential protocol-design value-of-information preflight.
- Added balanced F-SPS medium-budget benchmark with model and epoch coverage checks.
- Added manuscript claim stress-test matrix, proposed main figures, proposed tables, manuscript outline, and figure builder.
- Generated lightweight JSON/CSV evidence and ignored figure-ready PNGs under `outputs\figures\manuscript_ready_gamma_sub\`.

Findings:

- Anchor verification evaluates 60 cases with classification agreement rate `0.8833333333333333`, mean absolute discrepancy `0.05373609469259508`, and median absolute discrepancy `0.03420116487516757`. This supports response-surface use only with explicit qualification.
- Sequential protocol design ranks `multi_pulse_to_ltp_ltd` best by response-surface gamma error (`0.07554331565883955`) and improves over the configured single-protocol references in the preflight model. It remains a hypothesis requiring stronger simulator-backed validation.
- Balanced F-SPS benchmark plans 36 cases and executes 12 finite CPU-bounded cases, with 3 executed cases for each model and 4 executed cases for each epoch budget. `white_box_vo2_sigma_fourier` is best in the executed subset; `f_sps_pinn` does not improve over free-log-sigma or white-box Fourier baselines.
- Claim stress testing binds 7 manuscript claims to evidence, limitations, and forbidden overclaims.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. Frozen Ground Truth v1.1 files are unchanged. Dense response-surface evidence remains interpolated unless explicitly marked as simulator-backed anchor data. F-SPS evidence remains appendix or future-work material.


## High-throughput gamma_sub identifiability and F-SPS medium-budget pack

Date: 2026-07-01

Actions:

- Added dense response-surface `gamma_sub` by `T_sw` profile-likelihood audit.
- Added recoverability phase diagram across protocol, `T_sw` mismatch, prior width, observation count, and noise.
- Added protocol actual-validation, weighted-protocol objective, and bootstrap/noise/seed robustness audits.
- Added bounded F-SPS medium-budget planning benchmark with gradient-norm summaries and explicit skipped cases.
- Generated lightweight JSON/CSV evidence and ignored figure-ready PNGs under `outputs\figures\high_throughput_sci\`.

Findings:

- Dense profile response surface has 2501 grid points derived from 77 simulator-backed source points; best dense pair is near `gamma_sub = 5.004315952035617e8`, `T_sw_offset_K = 0.0`, with true-pair rank 9.
- Recoverability phase diagram has 2688 finite cases; `ltp_ltd` has the lowest mean relative error and overall recoverability is 0.7024 at <= 0.1 error and 0.8095 at <= 0.2 error.
- Protocol actual-validation has ranking correlation 0.6571 between sensitivity proxy and response-surface actual error; `short_pulse` is best by actual error.
- Weighted protocol objectives do not improve over `ltp_ltd_only` in the tested narrow-prior case.
- Statistical robustness has 480 finite cases with 10 seeds; wide `T_sw` mismatch still drives failures.
- F-SPS medium-budget plans 45 cases and executes 8 finite cases across free-log-sigma, white-box VO2 sigma, Fourier VO2 sigma, and F-SPS labels; the executed subset does not support an F-SPS superiority claim.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. Dense high-throughput audits are response-surface evidence unless explicitly marked simulator-backed. Frozen Ground Truth v1.1 files are unchanged.

## Gamma_sub multi-protocol and profile-likelihood validation pack

Date: 2026-06-30

Actions:

- Added `configs\gamma_sub_multi_protocol_recoverability.yaml` and `scripts\audit_gamma_sub_multi_protocol_recoverability.py`.
- Added `configs\gamma_sub_tsw_profile_likelihood.yaml` and `scripts\audit_gamma_sub_tsw_profile_likelihood.py`.
- Added `configs\gamma_sub_joint_inversion_boundary.yaml` and `scripts\audit_gamma_sub_joint_inversion_boundary.py`.
- Added `configs\gamma_sub_protocol_observability_design.yaml` and `scripts\audit_gamma_sub_protocol_observability_design.py`.
- Added `scripts\gamma_sub_validation_common.py` and `scripts\build_gamma_sub_sci_validation_figures.py`.
- Added four smoke/schema tests for the new audits.
- Generated lightweight JSON/CSV evidence and ignored figure-ready PNGs under `outputs\figures\gamma_sub_sci_validation\`.

Findings:

- Multi-protocol recoverability: 48 finite cases; `ltp_ltd` has the lowest mean error, while wide `T_sw` mismatch still drives all tested protocols to large error.
- Profile likelihood: the `gamma_sub` by `T_sw` objective landscape has condition number `10.762998753222757`, true-pair rank `2`, and an elongated ridge.
- Joint boundary: `gamma_plus_T_sw_plus_tau_m` is the most ambiguous case; `gamma_plus_sigma_on0` gives the worst gamma error in the tested release grid.
- Protocol design: `multi_pulse` has the highest distinguishability score; `long_pulse` and `short_pulse` meet the configured recommendation rule.
- Frozen input hashes are unchanged.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. The pack strengthens conditional recoverability and reviewer-defense claims only; it does not prove experimental validation, F-SPS-PINN superiority, or sparse-port full hidden-field recovery.

## Auxiliary observability sweep

Date: 2026-06-30

Actions:

- Added `configs\gamma_sub_auxiliary_observability_sweep.yaml`.
- Added `scripts\audit_gamma_sub_auxiliary_observability_sweep.py`.
- Added `tests\test_gamma_sub_auxiliary_observability_sweep.py`.
- Updated `scripts\build_gamma_sub_gap_closing_figures.py`.
- Generated `outputs\tables\gamma_sub_auxiliary_observability_sweep_summary.json`.
- Generated `outputs\tables\gamma_sub_auxiliary_observability_sweep_cases.csv`.
- Generated reproducible figure-ready outputs under `outputs\figures\gamma_sub_gap_closing\`.
- Added `docs\codex_reports\gamma_sub_auxiliary_observability_sweep_report.md`.

Findings:

- The official sweep evaluates 172 finite cases while estimating only `gamma_sub`.
- Port-only under controlled `T_sw_delta_K = 2.0` mismatch remains at relative error `1.2222222222222223`.
- Sparse/dense synthetic T, T-derivative, m, and sigma proxies do not reach the 0.1 or 0.2 recovery thresholds in the wide-mismatch setting.
- The calibrated-`T_sw` cases recover `gamma_sub` with relative error `0.0`, reinforcing the claim that independent `T_sw` calibration dominates.
- Frozen input hashes are unchanged.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. Synthetic auxiliary observability is design guidance only; it is not real experimental measurement and does not imply full hidden-field recovery.
## T_sw confounding phase-map audit

Date: 2026-06-30

Actions:

- Added `configs\gamma_sub_tsw_confounding_phase_map.yaml`.
- Added `scripts\audit_gamma_sub_tsw_confounding_phase_map.py`.
- Added `tests\test_gamma_sub_tsw_confounding_phase_map.py`.
- Added `scripts\build_gamma_sub_gap_closing_figures.py`.
- Generated `outputs\tables\gamma_sub_tsw_confounding_phase_map_summary.json`.
- Generated `outputs\tables\gamma_sub_tsw_confounding_phase_map_cases.csv`.
- Generated reproducible figure-ready outputs under `outputs\figures\gamma_sub_gap_closing\`.
- Added `docs\codex_reports\gamma_sub_tsw_confounding_phase_map_report.md`.

Findings:

- The audit scans 42 combinations of `T_sw_delta_K` and `T_sw_prior_width` while estimating only `gamma_sub`.
- The applied residual mismatch is `effective_T_sw_delta_K = T_sw_delta_K * T_sw_prior_width`, explicitly separating calibration-error amplitude from residual prior width.
- 27 of 42 cases are recoverable at `relative_error <= 0.1`; 32 of 42 are recoverable at `relative_error <= 0.2`.
- The worst cases remain wide `T_sw` uncertainty, with maximum `gamma_sub` relative error `1.2222222222222223`.
- Frozen input hashes are unchanged.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. This audit does not claim real experiment, unconditional `gamma_sub` identifiability, or sparse-port full hidden-field recovery.

## SCI gap-closing validation pack

Date: 2026-06-30

Actions:

- Added `configs\gamma_sub_tsw_prior_width_sweep.yaml` and `scripts\audit_gamma_sub_tsw_prior_width_sweep.py`.
- Added `configs\gamma_sub_temperature_anchor_placement.yaml` and `scripts\audit_gamma_sub_temperature_anchor_placement.py`.
- Added `scripts\compare_gamma_sub_scalar_baselines.py`.
- Added tests for all three lightweight validation scripts.
- Generated lightweight JSON/CSV evidence and Codex reports.

Findings:

- T_sw prior-width sweep: `gamma_sub` relative error decreases from `1.2222222222222223` at width `1.0` to `0.05555555555555555` at width `0.02`.
- Temperature-anchor placement: uniform, random, and high-gradient anchors do not reduce the wide `T_sw` mismatch bias in this candidate-grid audit.
- Scalar baselines: simple scalar grid search and continuous scalar refinement are adequate for the fixed-prior reduced problem, so optimizer novelty is not the manuscript claim.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. Frozen GT is unchanged. No F-SPS-PINN experiment was added.

## Observability-augmented gamma_sub audit

Date: 2026-06-30

Actions:

- Added `configs\gamma_sub_observability_augmented.yaml`.
- Added `scripts\audit_gamma_sub_observability_augmented.py`.
- Added `tests\test_gamma_sub_observability_augmented.py`.
- Generated `outputs\tables\gamma_sub_observability_augmented_summary.json`.
- Generated `outputs\tables\gamma_sub_observability_augmented_cases.csv`.
- Added `docs\gamma_sub_observability_augmented_report.md`.
- Added `docs\codex_reports\gamma_sub_observability_augmented_report.md`.

Findings:

- Port-only inversion under wide `T_sw` mismatch gives `gamma_relative_error = 1.2222222222222223` and estimates the upper candidate bound `1.0e9`.
- Sparse synthetic temperature anchors with `n_T_anchor = 2, 4, 8` do not reduce that bias in this candidate-grid audit.
- Narrowing `T_sw` prior width to `0.1` reduces `gamma_relative_error` to `0.2222222222222222`.
- Frozen input hashes are unchanged.

Boundary:

This is a synthetic numerical digital-twin observability audit. It does not claim real temperature measurement, full hidden-field recovery, or F-SPS-PINN performance improvement.

## F-SPS-PINN v2 phase-transition stress preflight

Date: 2026-06-30

Actions:

- Added `configs\pinn_inverse_v2_phase_transition_stress.yaml`.
- Added `scripts\run_pinn_inverse_v2_phase_transition_stress.py`.
- Added `tests\test_pinn_inverse_v2_phase_transition_stress.py`.
- Generated `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`.
- Generated `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`.
- Added `docs\codex_reports\pinn_inverse_v2_phase_transition_stress_report.md`.

Findings:

- All four stress cases produced finite losses and used `white_box_vo2_sigma`.
- All stress cases decreased loss in the small CPU preflight budget.
- `near_threshold` is the hardest stress case in this preflight, with `relative_G_error = 1.0033520810671768`.
- Frozen input hashes and mtimes were unchanged.

Boundary:

This is a synthetic numerical digital-twin stress preflight only. It does not support a formal F-SPS-PINN performance superiority claim, real VO2/NbO2 experimental validation, or sparse-port full hidden-field recovery.




## Continuous off-grid gamma_sub refinement audit

Date: 2026-06-28

Actions:

- Added `scripts\refine_gamma_sub_continuous.py`.
- Added `tests\test_gamma_sub_continuous_refinement.py`.
- Generated `outputs\tables\gamma_sub_continuous_refinement_summary.json`.
- Generated `outputs\tables\gamma_sub_continuous_refinement_cases.csv`.
- Added `docs\gamma_sub_continuous_refinement_report.md`.
- Added `docs\codex_reports\gamma_sub_continuous_refinement_report.md`.

Findings:

- Official off-grid true values `4.38e8`, `4.62e8`, and `5.15e8` are excluded from the candidate grid.
- Continuous refinement re-runs the simulator at non-grid `gamma_sub` values rather than interpolating candidate profiles.
- Maximum nearest-grid relative error: `0.08225108225108226`.
- Maximum continuous-refined relative error: `0.05565017963752034`.
- Mean error reduction: `0.019138563856834004`.
- Clean, 2% noise, 5% noise, and `n_obs = 8, 16, 32, 64` cases all pass the configured `gamma_sub` success threshold.
- `T_sw` remains the most dangerous confounder from prior audits.

Boundary:

This audit supports a one-dimensional reduced-order synthetic numerical digital-twin benchmark claim under fixed or tightly bounded priors. It does not prove experimental-data inversion, full 3D simulation, or sparse-port full hidden-field recovery.



## Paper-readiness gamma_sub robustness pack

Date: 2026-06-27

Actions:

- Added `docs\paper\model_hierarchy_and_claim_boundary.md`.
- Added `docs\paper\equation_variable_registry.md`.
- Added `docs\paper\experiment_to_figure_mapping.md`.
- Added `scripts\audit_gamma_sub_paper_readiness.py`.
- Added `tests\test_gamma_sub_paper_readiness.py`.
- Generated `outputs\tables\gamma_sub_paper_readiness_summary.json`.
- Generated `outputs\tables\gamma_sub_observation_sensitivity.csv`.
- Generated `outputs\tables\gamma_sub_offgrid_summary.csv`.
- Added `docs\gamma_sub_paper_readiness_report.md`.
- Added `docs\codex_reports\gamma_sub_paper_readiness_report.md`.

Findings:

- Off-grid `gamma_sub = 4.62e8` was localized with nearest-grid relative error
  `0.025974025974025976` and refined relative error
  `4.054410066065334e-05`.
- `n_obs = 8, 16, 32, 64` all recovered nominal `gamma_sub = 4.5e8` with
  relative error `0.0`.
- `T_sw` remained the most dangerous confounder.
- Frozen GT hash checks remained unchanged.

Boundary:

This pack supports a one-dimensional reduced-order synthetic numerical
digital-twin benchmark claim only. It does not support experimental-data, full
3D device simulation, or sparse-port full hidden-field recovery claims.



## Literature-backed constrained gamma_sub inversion

Date: 2026-06-26

Actions:

- Added `configs\gamma_sub_constrained_inversion.yaml`.
- Added `scripts\invert_gamma_sub_constrained.py`.
- Added `tests\test_gamma_sub_constrained.py`.
- Added `docs\literature_gamma_sub_evidence_chain.md`.
- Added `docs\parameter_prior_registry.md`.
- Added `docs\gamma_sub_constrained_inversion_report.md`.
- Added `docs\codex_reports\gamma_sub_constrained_inversion_report.md`.
- Generated `outputs\tables\gamma_sub_constrained_inversion_summary.json`.
- Generated `outputs\tables\gamma_sub_prior_width_sweep.csv`.

Findings:

- Clean nominal `gamma_sub` was recovered as `450000000.0` with relative error
  `0.0`.
- The largest tested relative error was `1.2222222222222223`.
- `T_sw` was the most dangerous confounder in the prior-width sweep.
- The result supports a constrained reduced inverse problem, not port-only full
  hidden-field recovery.

Boundary:

All outputs are synthetic numerical digital-twin benchmark evidence. Frozen
Ground Truth v1.1 data, configs, metrics, manifest, equations, and default
parameters were not modified.



## Documentation structure cleanup

Date: 2026-06-26

Actions:

- Reviewed context and status Markdown references with `git grep`.
- Compressed repeated historical file lists in `PROJECT_STATE.md` and
  `docs\project_state\latest_changes.md`.
- Kept `CODEX_CONTEXT.md` plus `docs\research_strategy\active_phase.md` as the
  required low-token first-read pair.
- Kept `docs\research_strategy\context_loading_policy.md` as the full Tier 0
  through Tier 4 loading policy.
- Updated `docs\codex_reports\local_codex_context_integration_report.md` with
  concrete context-integration verification results.

Findings:

- `context_index.md`, `current_research_handoff.md`, and
  `codex_workflow_rules.md` are referenced and still provide unique routing or
  workflow value.
- No context files were deleted.

Boundary:

This was documentation-only cleanup. No research code, configs, tests, frozen
Ground Truth files, generated arrays, or generated figures were modified.



## Local Codex context integration

Date: 2026-06-26

Actions:

- Read the local reference pack at `E:\pinn_codex_reference_pack`.
- Added `CODEX_CONTEXT.md`.
- Added low-token context workflow files under `docs\research_strategy\`.
- Added compressed literature digests under `docs\literature_notes\`.
- Added reference-pack provenance and paper routing files under `references\`.
- Updated project state, registries, README, and project-state snapshots.

Findings:

- The active phase is literature-backed constrained `gamma_sub` inversion
  preparation.
- Port-only full hidden-field inversion remains ill-posed.
- The reduced `gamma_sub` route is conditional on fixed or narrow-prior
  confounding parameters, especially `T_sw`, `tau_m`, `sigma_on0`, and `eta_A`.
- F-Pyramid, STL, observability augmentation, and NeuroSPICE/NeuroPINN remain
  deferred method enhancements.

Boundary:

This was a documentation-only integration. No Ground Truth frozen files,
source code, configs, tests, training outputs, or large binary artifacts were
modified.



## PINN inverse v0 ablation audit

Date: 2026-06-22

Actions:

- Added `configs\pinn_inverse_v0_triangle_full_anchor.yaml`.
- Added `configs\pinn_inverse_v0_triangle_weak_anchor.yaml`.
- Added `configs\pinn_inverse_v0_triangle_port_only.yaml`.
- Added `scripts\run_pinn_inverse_v0_ablation.py`.
- Updated `scripts\train_pinn_inverse_v0.py` to report `nrmse_delta_T`,
  `nrmse_delta_c_v`, `nrmse_delta_m`, and `nrmse_sigma`.
- Added `outputs\tables\pinn_inverse_v0_ablation_summary.json`.
- Added `docs\pinn_inverse_v0_ablation_report.md`.

Findings:

- Full-anchor v0 reconstructs terminal conductance with
  `relative_G_error = 0.04331491706021674`.
- Port-only v0 still reconstructs terminal conductance with
  `relative_G_error = 0.07169673218475178`.
- Hidden fields are not uniquely identifiable from port-only supervision in the
  current v0 setup.
- `delta_c_v` shows the strongest field-anchor dependence.
- `delta_T` remains the main absolute RMSE source.

Ethics note:

All results in this repository are synthetic numerical benchmark results unless
explicitly documented otherwise in `docs\data_provenance.md`.



## PINN inverse v1 physics regularization

Date: 2026-06-22

Actions:

- Added `src\pinnpcm\pinn\physics_residuals.py`.
- Added `configs\pinn_inverse_v1_triangle_physics.yaml`.
- Added `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`.
- Added `configs\pinn_inverse_v1_triangle_port_physics.yaml`.
- Added `scripts\train_pinn_inverse_v1.py`.
- Added `scripts\run_pinn_inverse_v1_experiments.py`.
- Added `outputs\tables\pinn_inverse_v1_summary.json`.
- Added `docs\pinn_inverse_v1_physics_design.md`.
- Added `docs\pinn_inverse_v1_report.md`.

Findings:

- v1 adds heat, state, defect, sigma-consistency, and boundary residuals through
  torch autograd.
- `triangle_physics` slightly improves terminal port error and `sigma` nRMSE
  relative to v0 full_anchor.
- `triangle_port_physics` improves hidden-field regularity relative to v0
  port_only but worsens terminal `G(t)` error.
- `delta_T` remains the largest absolute error source and is not materially
  improved by the current lightweight heat residual.

Boundary:

v1 is physics-regularized and approximate. It is not yet a strict
PDE-constrained inverse PINN.



## PINN inverse v1.1 residual balancing

Date: 2026-06-23

Actions:

- Added `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`.
- Added `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`.
- Added `scripts\run_pinn_inverse_v1_1_experiments.py`.
- Extended `scripts\train_pinn_inverse_v1.py` with optional running-scale
  residual balancing, warmup scheduling, per-field anchor weights, and sigma
  initial-state regularization.
- Added `outputs\tables\pinn_inverse_v1_1_summary.json`.
- Added `docs\pinn_inverse_v1_1_report.md`.
- Added `docs\codex_reports\pinn_inverse_v1_1_report.md`.

Findings:

- v1.1 physics_balanced improves `relative_G_error` and sigma nRMSE slightly
  relative to v1 physics, but `delta_T` worsens.
- v1.1 port_physics_balanced improves terminal `G(t)` and sigma nRMSE relative
  to v0 port_only, but hidden `delta_c_v` and `m` remain weak.
- v1.1 is not a primary paper-figure candidate for hidden-field reconstruction.

Boundary:

All v1.1 results are synthetic numerical digital-twin benchmark outputs, not
experimental data.



## PINN identifiability audit

Date: 2026-06-23

Actions:

- Added `scripts\analyze_pinn_identifiability.py`.
- Generated `outputs\tables\pinn_identifiability_summary.json`.
- Generated `outputs\tables\pinn_identifiability_correlation.csv`.
- Generated `outputs\figures\pinn_identifiability\correlation_heatmap.png`.
- Generated `outputs\figures\pinn_identifiability\spatial_sensitivity.png`.
- Generated `outputs\figures\pinn_identifiability\lag_correlation.png`.
- Added `docs\pinn_identifiability_audit_report.md`.
- Added `docs\codex_reports\pinn_identifiability_audit_report.md`.

Findings:

- `G(t)` is nearly perfectly correlated with `mean_sigma`
  (`r = 0.9999966158284996`).
- `G(t)` is also highly correlated with aggregate `delta_T`, `delta_c_v`, and
  `m`, which makes terminal-only hidden-field decomposition non-unique.
- In the frozen benchmark, `sigma` aligns more strongly with `m`
  (`r = 0.8241268575488281`) than with `c_v`
  (`r = 0.3216744579750865`).
- v1.1 did not significantly improve `delta_T` because it improved residual
  balancing but did not add independent thermal observability.

Boundary:

The identifiability audit is a synthetic numerical digital-twin analysis. It is
not experimental evidence.



## v2a gamma_sub identifiability audit

Date: 2026-06-23

Actions:

- Added `scripts\scan_gamma_sub_identifiability.py`.
- Added `scripts\invert_gamma_sub_v0.py`.
- Added `outputs\tables\gamma_sub_identifiability_summary.json`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`.
- Generated `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`.
- Added `docs\gamma_sub_identifiability_report.md`.
- Added `docs\codex_reports\gamma_sub_identifiability_audit_report.md`.

Findings:

- With `D_v0`, `mu_v0`, `T_sw`, and `tau_m` fixed, `gamma_sub` is stably
  recovered from terminal `G/I` plus a candidate heat-residual regularizer.
- Clean best estimate: `450001503.273578` versus target `4.5e8`.
- Clean relative error: `3.3406079510847727e-06`.
- Maximum noisy mean relative error over 2 percent and 5 percent synthetic
  noise tests: `0.009843655826927688`.
- Multi-start inversions were consistent for all tested noise cases.
- Joint confusion with `T_sw` and `tau_m` remains unproven because those
  parameters were fixed in this reduced audit.

Boundary:

This is synthetic numerical digital-twin evidence for a reduced scalar inverse
problem, not experimental validation and not proof of full hidden-field
identifiability.



## gamma_sub robustness and confounding audit

Date: 2026-06-23

Actions:

- Added `scripts\audit_gamma_sub_confounding.py`.
- Added `scripts\invert_gamma_sub_with_mismatch.py`.
- Added `outputs\tables\gamma_sub_confounding_summary.json`.
- Added `outputs\tables\gamma_sub_sensitivity_ranking.csv`.
- Added `docs\gamma_sub_confounding_report.md`.
- Added `docs\codex_reports\gamma_sub_confounding_audit_report.md`.

Findings:

- `T_sw` has the largest aggregate sensitivity in the local perturbation audit.
- `sigma_on0` and `tau_m` are the closest response-shape confounders for
  `gamma_sub`.
- Mismatch inversion is not robust as an unconstrained claim: `T_sw_plus_2K`
  pushes the recovered `gamma_sub` to the upper bound.
- The gamma_sub branch remains useful only as a constrained reduced inverse
  problem with independently fixed or calibrated switching, conductivity, and
  geometric-scale parameters.

Boundary:

All results are synthetic numerical digital-twin benchmark outputs, not
experimental measurements.
## Literature-Anchored Calibration And Simulator-Backed Protocol Validation

Added a reviewer-defense pack for the constrained `gamma_sub` manuscript line. The pack confirmed that missing digitized literature curves are handled as a blocked/template state, not fabricated data; T_sw calibration is required; and ODE-backed sequential validation supports `multi_pulse_to_ltp_ltd` as the strongest tested preflight candidate. All evidence remains synthetic numerical digital-twin benchmark evidence.

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

## Stiffness Continuation And Phase-Field Alignment

Added supplementary reviewer-defense evidence for phase-transition residual stiffness and phase-field inverse-PINN alignment. Stiffness audit: `180` finite cases, cliff ratio `11.894639315460832`. Phase-field smoke: `27` finite cases, median relative M error `0.04331110242687686`. These results support manuscript positioning only and do not change the constrained `gamma_sub` main claim.

## Final Figure Literature Lock And Stiffness 2D Story

Locked Drive/web/repo-local literature evidence and generated supplementary stiffness/phase-field figure manifest. Stiffness cliff ratio remains `11.894639315460832`; phase-field median M relative error remains `0.04331110242687686`. These results improve reviewer defense and story depth but do not change the main `gamma_sub` claim.
