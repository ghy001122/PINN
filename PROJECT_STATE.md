# Project state

## Current phase

The current authorized phase is `gamma_sub response-surface verification and manuscript claim consolidation`. The repository is strengthening reviewer-facing evidence for the constrained `gamma_sub` manuscript line while recording bounded F-SPS-PINN method-development evidence as appendix or future-work material.

F-SPS-PINN architecture MVP, v2 smoke training, v2 small-run baseline, v2 phase-transition stress preflight, v2 Fourier on/off ablation, and the medium-budget planning benchmark are complete or bounded as method-development evidence. The Fourier ablation did not prove F-SPS-PINN performance superiority, so F-SPS-PINN should remain appendix, discussion, or future-work material unless a separate method paper is opened.

The most defensible paper line remains the constrained reduced `gamma_sub` inverse problem under fixed or tightly bounded priors. The manuscript claim should focus on sparse-port inverse identifiability, target-space reduction, and constrained effective thermal-parameter inversion in a one-dimensional synthetic numerical digital-twin benchmark.

The high-throughput gamma_sub pack adds dense response-surface profile likelihood, recoverability phase diagram, protocol actual-validation, weighted protocol objective, bootstrap/noise/seed robustness, and F-SPS medium-budget planning evidence. The dense profile uses IDW interpolation from the prior simulator-backed profile grid rather than thousands of new ODE solves; this is explicitly response-surface evidence.

The response-surface verification and manuscript claim consolidation pack adds `configs\gamma_sub_response_surface_anchor_verification.yaml`, `scripts\audit_gamma_sub_response_surface_anchor_verification.py`, `configs\gamma_sub_sequential_protocol_design.yaml`, `scripts\audit_gamma_sub_sequential_protocol_design.py`, `configs\f_sps_balanced_medium_budget_benchmark.yaml`, `scripts\train_f_sps_balanced_medium_budget_benchmark.py`, `scripts\build_manuscript_claim_stress_test.py`, and `scripts\build_manuscript_ready_gamma_sub_figures.py`. Official outputs contain 60 anchor-verification cases with classification agreement rate `0.8833333333333333`, 8 sequential protocol candidates with `multi_pulse_to_ltp_ltd` best by response-surface gamma error, and 12 balanced F-SPS medium-budget executed cases across all four model labels and all three epoch budgets. The response-surface evidence is acceptable only with explicit qualification, sequential design remains a preflight hypothesis, and balanced F-SPS still does not support superiority over free-log-sigma or white-box Fourier baselines.

## Standing Critical Research Mode

All future research planning, Codex task design, Codex result review, manuscript drafting, and claim consolidation must follow Critical Research Mode. This is a standing project governance rule, not a temporary instruction for one task.

Authoritative files:

- `AGENTS.md`
- `docs/project_prompts/critical_research_mode.md`
- `docs/templates/codex_critical_preamble.md`

The project must preserve a skeptical SCI-review posture. Do not inflate weak results, do not hide negative results, and do not use vague language to avoid downgrading claims. Every research conclusion should be assigned one of: `supported`, `qualified_supported`, `failed_but_informative`, or `forbidden`.

The project is also exploration-first. Claim caution must not become experiment avoidance. High-risk directions remain valid exploration targets when they may improve paper quality, workload, novelty, reviewer defense, applicability, or generalization. They should be scoped as bounded, reproducible audits with explicit success thresholds, failure interpretations, allowed wording, and forbidden overclaim wording.

High-risk claims remain forbidden unless direct repository evidence upgrades them through claim gates: full 2D hidden-field recovery, terminal-only 2D inverse solved, full STL-PINN reproduction, Seiler-style multi-head STL, F-SPS/Fourier superiority, full FEM/device-grade simulation, and experimental validation. This restricts manuscript claims, not controlled exploration of the underlying directions.

## Research line

The only active research line is mesh-free, fully differentiable, multi-physics digital twin modeling plus PINN inverse identification for phase-change or memristive defect diagnosis and SCI paper preparation.

## Frozen benchmark

- `configs\gt_v1_acceptance_triangle.yaml`
- `configs\gt_v1_acceptance_ltp_ltd.yaml`
- `docs\gt_v1_acceptance_report.md`
- `data\processed\gt_v1_acceptance\manifest.json`
- `data\processed\gt_v1_acceptance\gt_triangle.npz`
- `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- `data\processed\gt_v1_acceptance\gt_ltp_ltd.npz`
- `data\processed\gt_v1_acceptance\obs_ltp_ltd_sparse.npz`

Ground Truth v1.1 remains frozen across subsequent inverse, audit, and documentation-integration workflows unless an explicit Ground Truth revision is opened.

## Current evidence

The high-throughput gamma_sub identifiability pack adds `configs\gamma_sub_tsw_dense_profile_likelihood.yaml`, `configs\gamma_sub_recoverability_phase_diagram.yaml`, `configs\gamma_sub_protocol_actual_inversion_validation.yaml`, `configs\gamma_sub_weighted_protocol_objective.yaml`, `configs\gamma_sub_statistical_robustness.yaml`, `configs\f_sps_medium_budget_benchmark.yaml`, and matching scripts/tests. Official response-surface runs produce 2501 dense profile points, 2688 recoverability phase-diagram cases, 24 protocol-validation cases, 9 weighted-objective cases, and 480 statistical robustness cases. `ltp_ltd` remains the best recoverability protocol in the phase diagram, `short_pulse` is best in protocol actual-validation, weighted objectives do not improve over `ltp_ltd_only`, and wide `T_sw` mismatch remains the dominant failure mode.

The F-SPS medium-budget planning benchmark writes `outputs\tables\f_sps_medium_budget_benchmark_summary.json` and `outputs\tables\f_sps_medium_budget_benchmark_cases.csv`. It plans 45 cases and executes 8 finite CPU-bounded cases across free-log-sigma, white-box VO2 sigma, Fourier VO2 sigma, and F-SPS labels. The executed subset does not support an F-SPS superiority claim; it is appendix or future-work evidence only.
The identifiability audit confirms that `G(t)` is nearly perfectly correlated with `mean_sigma`, while aggregate `delta_T`, `delta_c_v`, and `m` are also strongly correlated with `G(t)`. Terminal observations constrain the integrated conductance response but do not uniquely recover the hidden thermal, defect, state, and conductivity fields.

The v2a reduced audit confirms that `gamma_sub` is stably invertible in the single-parameter setting when `D_v0`, `mu_v0`, `T_sw`, `tau_m`, and other microscopic parameters remain fixed. This does not prove joint identifiability with switching or defect parameters released.

The confounding audit shows that this reduced inverse story must stay conditional. `T_sw` is more sensitive than `gamma_sub`, `sigma_on0` and `tau_m` have response vectors close to `gamma_sub`, and mismatch inversion can produce large systematic gamma bias.

The constrained inversion audit adds a literature-guided prior registry and a bounded prior-width sweep. It recovers the clean nominal `gamma_sub = 4.5e8` exactly on the frozen benchmark candidate grid, but the maximum tested relative error reaches `1.2222222222222223` under `T_sw` mismatch.

The paper-readiness robustness pack adds off-grid and observation-count checks. For off-grid `gamma_sub = 4.62e8`, the nearest-grid estimate has relative error `0.025974025974025976`, while local log-quadratic refinement has relative error `4.054410066065334e-05`. For `n_obs = 8, 16, 32, 64`, nominal recovery remains exact and `T_sw` remains the most dangerous confounder.

The continuous off-grid refinement audit replaces log-quadratic profile interpolation with scalar continuous optimization that re-runs the simulator at each trial `gamma_sub`. Across 36 official synthetic numerical digital-twin cases (`gamma_sub = 4.38e8, 4.62e8, 5.15e8`; `n_obs = 8, 16, 32, 64`; noise `0, 0.02, 0.05`), the maximum nearest-grid relative error is `0.08225108225108226`, the maximum continuous-refined relative error is `0.05565017963752034`, all true values are excluded from the candidate grid, and all refinement cases evaluate non-grid simulator calls.

The F-SPS-PINN architecture MVP added a VO2-like white-box conductivity closure, opt-in Fourier-pyramid embedding, dynamic residual gate, and differentiable oscillation metrics. These modules passed unit tests and preserve the old free `log_sigma` path as an ablation baseline.

The v2 smoke training pipeline adds `configs\pinn_inverse_v2_f_sps_smoke.yaml` and `scripts\train_pinn_inverse_v2_smoke.py`. It runs a 3-epoch CPU smoke test, reconstructs terminal `G/I` using `sigma = vo2_sigma(T, c_v, m)`, writes `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`, and confirms frozen input hashes and mtimes are unchanged.

The v2 small-run baseline adds `configs\pinn_inverse_v2_f_sps_baseline.yaml` and `scripts\run_pinn_inverse_v2_baseline.py`. It compares `free_log_sigma` and `white_box_vo2_sigma` with the same seed, epochs, anchor count, and sparse terminal observations, writes `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json` and `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`, and confirms frozen input hashes and mtimes are unchanged. The result is not a performance-superiority claim.

The v2 phase-transition stress preflight adds `configs\pinn_inverse_v2_phase_transition_stress.yaml` and `scripts\run_pinn_inverse_v2_phase_transition_stress.py`. It runs `mild_transition`, `sharp_transition`, `near_threshold`, and `high_contrast` cases using `white_box_vo2_sigma` with temperature-derived phase fraction, writes `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json` and `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`, and confirms frozen input hashes and mtimes are unchanged. The result is a stress preflight only, not a performance-superiority claim.

The v2 Fourier ablation adds `configs\pinn_inverse_v2_fourier_ablation.yaml` and `scripts\run_pinn_inverse_v2_fourier_ablation.py`. It compares `vo2_sigma_fourier_off` and `vo2_sigma_fourier_on` under the same sharp-transition stress condition, writes `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json` and `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`, and confirms frozen input hashes and mtimes are unchanged. Fourier on does not clearly outperform Fourier off in this small-run result. The manuscript evidence matrix routes this F-SPS-PINN evidence to appendix, discussion, or future work rather than the main claim.

The observability-augmented audit adds `configs\gamma_sub_observability_augmented.yaml` and `scripts\audit_gamma_sub_observability_augmented.py`. Under a controlled wide `T_sw` mismatch target, port-only `gamma_sub` inversion again hits the upper candidate bound with relative error `1.2222222222222223`. Sparse synthetic temperature anchors with `n_T_anchor = 2, 4, 8` do not reduce that bias in this candidate-grid audit. Narrowing the `T_sw` prior width from `1.0` to `0.1` reduces the relative error to `0.2222222222222222`, confirming that independent switching-temperature calibration is more critical than terminal data alone.
The SCI gap-closing validation pack adds three lightweight audits. The `T_sw` prior-width sweep shows a monotonic candidate-grid trend: as `T_sw_prior_width` narrows from `1.0` to `0.02`, `gamma_sub` relative error decreases from `1.2222222222222223` to `0.05555555555555555`. The temperature-anchor placement audit shows that uniform, random, and high-gradient sparse synthetic temperature anchors still do not reduce the wide `T_sw` mismatch bias, so the anchor failure is not simply a uniform-placement artifact. The scalar baseline comparison shows that simple scalar grid search and continuous scalar least-squares are already adequate for the reduced problem under fixed priors; the manuscript contribution is identifiability-guided target reduction and prior-boundary auditing, not optimizer novelty.

The T_sw confounding phase-map audit adds `configs\gamma_sub_tsw_confounding_phase_map.yaml` and `scripts\audit_gamma_sub_tsw_confounding_phase_map.py`. It scans `T_sw_delta_K = [0.0, 0.04, 0.1, 0.2, 0.4, 1.0, 2.0]` and `T_sw_prior_width = [0.02, 0.05, 0.1, 0.2, 0.5, 1.0]` while estimating only `gamma_sub`. The applied residual mismatch is explicitly `effective_T_sw_delta_K = T_sw_delta_K * T_sw_prior_width`. Official results contain 42 finite cases, with 27 recoverable at relative error <= 0.1 and 32 recoverable at <= 0.2. The worst case remains large `T_sw` uncertainty with `gamma_sub` relative error `1.2222222222222223`. Frozen input hashes are unchanged.

The auxiliary observability sweep adds `configs\gamma_sub_auxiliary_observability_sweep.yaml` and `scripts\audit_gamma_sub_auxiliary_observability_sweep.py`. It compares `port_only`, `port_plus_sparse_T`, `port_plus_dense_T`, `port_plus_T_temporal_derivative_proxy`, `port_plus_m_proxy`, `port_plus_sigma_aggregate_proxy`, and `port_plus_calibrated_T_sw` under controlled `T_sw_delta_K = 2.0` mismatch while estimating only `gamma_sub`. Official results contain 172 finite cases; only 2 cases are recoverable at `relative_error <= 0.1` and `<= 0.2`, both from calibrated `T_sw`. The best non-calibrated auxiliary proxy remains at relative error `1.0`, so the evidence strengthens the conclusion that independent `T_sw` calibration dominates in the wide-mismatch regime.
The multi-protocol/profile-likelihood validation pack adds four reviewer-facing audits while estimating only `gamma_sub`. Multi-protocol recoverability evaluates 48 finite cases across triangle, LTP/LTD, derived multi-amplitude synthetic, and mixed-protocol objectives; `ltp_ltd` has the lowest mean error, but all protocols still fail under wide `T_sw` mismatch. The profile-likelihood landscape has condition number `10.762998753222757` and an elongated `gamma_sub`/`T_sw` ridge. The joint-boundary audit identifies `gamma_plus_T_sw_plus_tau_m` as the most ambiguous release and `gamma_plus_sigma_on0` as the worst gamma-error case. The protocol-design preflight ranks `multi_pulse` highest by distinguishability and recommends `long_pulse` and `short_pulse` under the configured sensitivity-angle rule. Frozen input hashes are unchanged.
The manuscript evidence consolidation adds `docs\paper\sci_manuscript_evidence_matrix.md` to bind each allowed paper claim to existing scripts, lightweight tables, reports, and forbidden overclaims.

Detailed historical file lists and reproduction entries live in:

- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `RESEARCH_LOG.md`
- `docs\project_state\file_inventory.md`
- `docs\codex_reports\`

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin benchmark results. They are not measured experimental data, not full 3D device simulation results, and not sparse-port full hidden-field recovery.

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

## Stiffness Continuation And Phase-Field Alignment Pack

This supplementary defense pack adds a phase-transition stiffness-continuation residual audit and a phase-field inverse alignment smoke benchmark. It does not modify frozen Ground Truth v1.1 and does not change the main claim: calibration-gated sparse-port reduced inversion of `gamma_sub` under fixed or tightly bounded priors.

Key results:

- Stiffness audit cases: `180`; all finite: `True`; cliff ratio sharpest/widest: `11.894639315460832`; sharpest finite width: `0.5`.
- Phase-field smoke cases: `27`; all finite: `True`; median M relative error: `0.04331110242687686`; success rate <= 0.1: `0.8148148148148148`.

Boundary: these are supplementary synthetic numerical digital-twin defense results. They do not prove F-SPS-PINN superiority, full STL-PINN reproduction, sparse-port phase-field recovery, or experimental validation.

## Final Figure Literature Lock And Stiffness 2D Story Pack

This pack locks Drive/web/repo-local literature evidence and builds supplementary stiffness/phase-field figures from existing lightweight tables. It also adds final submission storyboards and checklist documents. Frozen Ground Truth v1.1 remains unchanged.

Key outputs:

- `docs/literature/drive_and_web_literature_evidence_lock.md`
- `scripts/build_stiffness_2d_story_figures.py`
- `outputs/tables/stiffness_2d_story_figure_manifest.json`
- `docs/paper/final_submission_figure_table_claim_lock_v2.md`
- `docs/paper/stiffness_and_quasi_2d_storyboard.md`
- `docs/manuscript/abstract_final_candidate.md`
- `docs/manuscript/cover_letter_draft.md`
- `docs/manuscript/submission_checklist.md`

Boundary: stiffness and phase-field evidence are supplementary. The main manuscript claim remains calibration-gated constrained `gamma_sub` inversion.

## Claim-Gate Experimental Resolution Pack

This pack adds reproducible supplementary claim-gate experiments without modifying frozen Ground Truth v1.1.

- Reduced 2D forward benchmark: `108` cases, finite fields/residuals, geometry effect `True`, lateral-coupling effect `True`.
- 2D observability ladder: terminal-only failure `True`, minimal reliable protocol `terminal_multi_pulse`, augmented low-dimensional inverse allowed `True`, full field recovery allowed `False`.
- Stiffness-aware algorithm benchmark: continuation-plus-scale-aware gain `0.4890181621870298`, mini-STL-style gain `0.4334945926584622`, full STL claim allowed `False`.

The main manuscript line remains constrained `gamma_sub`. These results are supplementary synthetic numerical digital-twin evidence for reviewer defense and claim boundaries. They also identify follow-up exploration targets: dense/full-field 2D recovery ladders, terminal-only rescue under stronger priors, true Seiler-style multi-head STL, actual PINN stiffness training, and Fourier/F-SPS conditional superiority audits. Those topics are not positive manuscript claims yet, but they remain valid bounded exploration opportunities.
