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
