# Claim-Gate Resolution Matrix

All entries are synthetic numerical digital-twin benchmark evidence, not experimental data.

| Claim | Status | Supporting table | Supporting figure | Allowed manuscript sentence | Forbidden overclaim | Required qualification |
| --- | --- | --- | --- | --- | --- | --- |
| 2D reduced forward supported? | supported | outputs/tables/reduced_2d_phase_transition_forward_summary.json | outputs/figures/reduced_2d_forward_snapshots.png; outputs/figures/reduced_2d_port_traces.png | A reduced 2D synthetic phase-transition forward benchmark is finite and geometry-sensitive. | This is full 2D FEM or experimental validation. | Reduced thin-film model only; supplementary evidence. |
| 2D low-dimensional inverse supported? | partially_supported | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | outputs/figures/reduced_2d_observability_claim_gate.png | Low-dimensional reduced 2D inverse diagnosis is feasible under augmented sparse observations. | Sparse terminal data uniquely recover 2D fields. | Only low-dimensional parameters and only under augmented observations. |
| Terminal-only 2D inverse supported? | failed | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | outputs/figures/reduced_2d_observability_claim_gate.png | Terminal-only sparse observations fail this reduced 2D inverse claim gate. | Terminal-only data solve 2D inverse diagnosis. | Use as honest negative evidence. |
| Augmented-observation 2D inverse supported? | partially_supported | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | outputs/figures/reduced_2d_observability_claim_gate.png | Augmented sparse proxy observations can support low-dimensional reduced 2D parameter diagnosis. | Augmented observations recover full 2D fields. | Success threshold is benchmark-specific; not experimental. |
| Full 2D hidden-field recovery supported? | forbidden | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | none | Full 2D hidden-field recovery remains unsupported. | Full 2D hidden fields are uniquely recovered. | No full-field 2D inverse training evidence exists. |
| Stiffness cliff exists? | supported | outputs/tables/stiffness_2d_story_figure_manifest.json | outputs/figures/stiffness_residual_vs_transition_width.png | Narrow phase-transition widths create a residual stiffness cliff in the synthetic preflight. | This proves stiff PINN training is solved. | Residual preflight only. |
| Stiffness cliff mitigated? | supported | outputs/tables/stiffness_aware_algorithm_benchmark_summary.json | outputs/figures/stiffness_algorithm_error_vs_width.png | Continuation plus scale-aware weighting mitigates stiffness-induced degradation in the residual-proxy benchmark. | Stiffness is solved generally. | Synthetic algorithm benchmark, not full training proof. |
| Mini-STL-style transfer supported? | partially_supported | outputs/tables/stiffness_aware_algorithm_benchmark_summary.json | outputs/figures/stiffness_algorithm_claim_gate.png | Mini-STL-style transfer is supported as a lightweight continuation/initialization audit. | Full STL-PINN reproduction is complete. | Use mini-STL-style wording only. |
| Full STL-PINN reproduction supported? | forbidden | outputs/tables/stiffness_aware_algorithm_benchmark_summary.json | none | Full STL-PINN reproduction remains future work. | The repository reproduced full stiff transfer learning. | No full STL training implementation was run. |
| Fourier/F-SPS superiority supported? | forbidden | outputs/tables/pinn_inverse_v2_fourier_ablation_summary.json; outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json | none | F-SPS and Fourier evidence remain appendix/future-work diagnostics. | F-SPS-PINN or Fourier features are superior. | Existing small-run evidence does not establish superiority. |

## Summary

- Reduced 2D forward supported: `True`.
- Terminal-only 2D inverse failed: `True`.
- Augmented low-dimensional 2D inverse allowed: `True`.
- Full 2D field recovery allowed: `False`.
- Stiffness cliff mitigated: `True`.
- Full STL claim allowed: `False`.

## Integrated High-Risk Claim Ladder Quick Profile

All entries remain synthetic numerical digital-twin benchmark evidence, not experimental data.

| Claim | Status | Supporting table | Supporting figure | Allowed manuscript sentence | Forbidden overclaim | Required qualification |
| --- | --- | --- | --- | --- | --- | --- |
| Reduced 2D low-rank hidden-field recovery with dense anchors | qualified_supported | outputs/tables/high_risk_claim_ladder_summary.json | outputs/figures/high_risk_2d_hidden_field_ladder_error.png | Protocol-limited low-rank 2D hidden-field reconstruction is supported only with augmented dense/sensitivity observations. | Sparse terminal data uniquely recover full 2D hidden fields. | Reduced low-rank benchmark; best protocol `terminal_plus_dense_anchors_5pct`; not full-grid device recovery. |
| Terminal-only full 2D hidden-field recovery | failed_but_informative | outputs/tables/high_risk_claim_ladder_summary.json | outputs/figures/high_risk_2d_observability_protocols.png | Terminal-only full-field rescue fails and defines an observability boundary. | Terminal-only 2D inverse is solved. | Negative result should be used as reviewer-defense boundary. |
| Terminal-only low-dimensional 2D inverse under strong priors | qualified_supported | outputs/tables/high_risk_claim_ladder_summary.json | outputs/figures/high_risk_2d_observability_protocols.png | Multi-pulse terminal data can support low-dimensional inverse wording under strong priors. | Terminal-only full hidden-field recovery. | Low-dimensional target only. |
| Actual reduced PINN stiffness mitigation | qualified_supported | outputs/tables/integrated_stiffness_stl_summary.json | outputs/figures/integrated_stiffness_error_by_algorithm.png; outputs/figures/integrated_stiffness_convergence.png | Continuation/asinh/adaptive residual handling mitigates stiffness-induced degradation in an actual reduced autograd PINN audit. | Stiff PINN training is solved generally. | Reduced synthetic benchmark; not experimental. |
| Seiler-style multi-head transfer | qualified_supported | outputs/tables/integrated_stiffness_stl_summary.json | outputs/figures/integrated_stl_transfer_gain.png | A Seiler-style shared-trunk, multi-head, frozen-trunk transfer audit improves the reduced benchmark. | Full Seiler et al. STL-PINN reproduction is complete. | Reduced benchmark only; not full reproduction. |
| Fourier/F-SPS conditional benefit | qualified_supported | outputs/tables/fourier_fsps_conditional_superiority_summary.json | outputs/figures/fourier_fsps_gain_heatmap.png; outputs/figures/fourier_fsps_failure_modes.png | Fourier/F-SPS-style choices are conditionally beneficial in sharp/front regimes. | Fourier/F-SPS is universally superior. | Residual-proxy condition sweep; no actual training superiority claim. |

## Actualized High-Risk Claim Ladder v2

All entries remain synthetic numerical digital-twin benchmark evidence, not experimental data. This section supersedes the previous heuristic/proxy interpretation where the actualized evidence is stricter.

| Claim | Status | Supporting table | Supporting figure | Allowed manuscript sentence | Forbidden overclaim | Required qualification |
| --- | --- | --- | --- | --- | --- | --- |
| Actual low-rank 2D hidden-field inverse | forbidden | outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json | outputs/figures/high_risk_actual_inverse_error_by_protocol.png | Actual coefficient inversion did not clear the field-recovery gate in the quick profile; use as observability-boundary evidence unless improved by stronger observations. | The heuristic ladder proves 2D hidden-field recovery. | Low-rank inverse only; full arbitrary 2D recovery remains forbidden. |
| Terminal-only low-dimensional parameter inverse | qualified_supported | outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json | outputs/figures/high_risk_actual_inverse_error_by_protocol.png | Terminal-only multi-pulse data support only low-dimensional parameter wording under strong priors. | Terminal-only data recover full fields. | Parameter target only; no field recovery. |
| Terminal-only 2D field rescue | failed_but_informative | outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json | outputs/figures/high_risk_actual_inverse_error_by_protocol.png | Terminal-only field rescue remains a negative observability result. | Terminal-only 2D inverse is solved. | Failed-but-informative boundary. |
| Actual stiffness continuation/asinh/adaptive | qualified_supported | outputs/tables/integrated_stiffness_stl_summary.json | outputs/figures/integrated_stiffness_error_by_algorithm.png | Continuation/asinh/adaptive residual handling mitigates stiffness in the expanded reduced actual-training audit. | Stiff PINN training is solved generally. | Reduced synthetic benchmark only. |
| Seiler-style multi-head STL expanded audit | failed_but_informative | outputs/tables/integrated_stiffness_stl_summary.json | outputs/figures/integrated_stl_transfer_gain.png | Shared-trunk multi-head transfer was implemented, but the expanded 90-case quick profile did not clear the gain gate. | Full STL-PINN reproduction is complete. | Use as negative/boundary evidence unless future full reproduction succeeds. |
| Actual Fourier/F-SPS conditional benefit | failed_but_informative | outputs/tables/fourier_fsps_actual_training_summary.json | outputs/figures/fourier_fsps_actual_gain_heatmap.png | Actual training shows sharp-regime gains for `f_sps_sampling` but smooth-regime degradation prevents a positive conditional-benefit claim in this run. | Fourier/F-SPS is universally superior. | Actual small training benchmark; not performance proof. |
| Fourier/F-SPS universal superiority | forbidden | outputs/tables/fourier_fsps_actual_training_summary.json | outputs/figures/fourier_fsps_actual_gain_heatmap.png | Universal superiority remains unsupported. | F-SPS/Fourier generally improves all regimes. | Requires cross-regime improvement without smooth degradation. |
