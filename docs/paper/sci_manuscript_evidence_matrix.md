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

Supplementary priority:

1. v0/v1/v1.1 diagnostic tables.
2. F-SPS-PINN v2 smoke summary.
3. v2 free-log-sigma versus white-box `vo2_sigma` baseline.
4. v2 phase-transition stress preflight.
5. v2 Fourier on/off ablation.

## Manuscript Direction

The fastest route to a high-quality SCI manuscript is to stop expanding F-SPS-PINN experiments for now and write a focused paper on sparse-port inverse identifiability, target-space reduction, and constrained `gamma_sub` inversion. F-SPS-PINN can strengthen the discussion as a future architecture for better physics closures, but it is not the current main result.
