# Proposed Main Figures

All figures are for a synthetic numerical digital-twin benchmark. They must not be described as experimental measurements or full three-dimensional device validation.

| Figure | Evidence | Primary files | Claim boundary |
| --- | --- | --- | --- |
| Figure 1 | Digital-twin benchmark and sparse-port inverse setup | `docs/gt_v1_acceptance_report.md`, `data/processed/gt_v1_acceptance/manifest.json` | Synthetic one-dimensional benchmark only |
| Figure 2 | `gamma_sub`/`T_sw` confounding landscape and ridge | `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_grid.csv`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_2_confounding_profile.png` | Response-surface evidence from 77 simulator-backed profile source points |
| Figure 3 | Recoverability phase diagram | `outputs/tables/gamma_sub_recoverability_phase_diagram_cases.csv`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_3_recoverability_phase_diagram.png` | Conditional recoverability under bounded priors |
| Figure 4 | Response-surface anchor verification | `outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_4_anchor_verification.png` | Dense points remain interpolated; anchors verify only the sampled source evidence |
| Figure 5 | Protocol actual validation and sequential design | `outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json`, `outputs/tables/gamma_sub_sequential_protocol_design_summary.json`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_5_protocol_design.png` | Protocol design is preflight evidence, not experimental optimization |
| Figure 6 | Statistical robustness | `outputs/tables/gamma_sub_statistical_robustness_summary.json`, `outputs/figures/manuscript_ready_gamma_sub/main_figure_6_statistical_robustness.png` | Robustness is conditional on fixed or tightly bounded confounders |

## Appendix Figure

| Figure | Evidence | Primary files | Claim boundary |
| --- | --- | --- | --- |
| Appendix Figure A1 | Balanced F-SPS medium-budget benchmark | `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json`, `outputs/figures/manuscript_ready_gamma_sub/appendix_f_sps_balanced_benchmark.png` | Method-development evidence only; no F-SPS superiority claim |
## Literature-Anchored Figure Addendum

- Add or update Figure 5 with `outputs/figures/manuscript_style_gamma_sub/figure_tsw_calibration_necessity.png` and `outputs/figures/manuscript_style_gamma_sub/figure_simulator_backed_protocol_validation.png`.
- Use `outputs/figures/manuscript_style_gamma_sub/figure_literature_parameter_sanity.png` as supplementary prior-boundary evidence.
- Captions must state synthetic numerical digital-twin benchmark and no experimental validation.
