# Final Claim Matrix

Allowed claims are restricted to synthetic numerical digital-twin evidence.

| Claim | Status | Required qualifier | Forbidden wording |
| --- | --- | --- | --- |
| Sparse-port full hidden-field recovery is ill-posed in the current benchmark | Supported | one-dimensional synthetic benchmark | unique full-field recovery |
| `gamma_sub` is a reduced inverse target | Supported conditionally | fixed or tightly bounded priors | unconditional identifiability |
| `T_sw` calibration is required before `gamma_sub` inversion | Supported | response-surface and ODE-backed synthetic audits | measured calibration result |
| 0.1 K residual `T_sw` tolerance is usable as a paper threshold | Supported as benchmark-specific | synthetic <=15% median-error criterion plus ODE spot-check | real experimental calibration capability requirement |
| Calibration gain dominates protocol gain | Supported | protocol gain is secondary and qualified | protocol identity alone solves inverse recovery |
| Calibrated protocol robustness can be shown | Qualified | synthetic ODE-backed, calibrated priors; worst-case errors remain non-negligible | experimentally validated stimulation protocol |
| Literature curve fitting validates model curves | Blocked | requires provenance-backed CSV/JSON data | fitted public curves without data |
| Quasi-2D extension improves physical-depth discussion | Supported as preflight only | forward/residual feasibility; supplementary/discussion placement | 2D inverse diagnosis is solved |
| F-SPS-PINN is superior | Not supported | appendix/future work only | performance superiority |

| Phase-transition stiffness residual cliff is a valid stress test | Supported as supplementary preflight | synthetic residual proxy; continuation/Fourier are stability aids only | full STL-PINN reproduction or stiffness solved |
| Phase-field inverse literature alignment | Supported as supplementary smoke | Allen-Cahn full-field-anchor mobility inversion; not sparse-port current | phase-field smoke is main-text core experiment |
| Third-zone SCI computational submission | Plausible with narrow scope | synthetic benchmark and reviewer-defense evidence only | experimental or full-device validation |
| Second-zone edge submission | Qualified and riskier | needs careful method-oriented framing | real-device or external-curve validation without data |

## Claim-Gate Resolution Update

All results remain synthetic numerical digital-twin benchmark evidence, not experimental data.

| Claim | Updated status | Evidence | Boundary |
| --- | --- | --- | --- |
| Reduced 2D forward benchmark | Supported | `outputs/tables/reduced_2d_phase_transition_forward_summary.json` | Reduced thin-film synthetic benchmark, not full FEM. |
| Terminal-only 2D inverse | Failed | `outputs/tables/reduced_2d_observability_limited_inverse_summary.json` | Use as honest negative result. |
| Augmented low-dimensional 2D inverse | Qualified supported | `outputs/tables/reduced_2d_observability_limited_inverse_summary.json` | Low-dimensional parameters only; no full-field recovery. |
| Stiffness-aware mitigation | Supported as residual-proxy benchmark | `outputs/tables/stiffness_aware_algorithm_benchmark_summary.json` | Not full STL-PINN reproduction. |
| Full STL-PINN and F-SPS superiority | Forbidden | `docs/paper/claim_gate_resolution_matrix.md` | Future work unless separately demonstrated. |

## Integrated High-Risk Claim Ladder Update

All statuses below are synthetic numerical digital-twin benchmark evidence.

| Claim | Updated status | Evidence | Boundary |
| --- | --- | --- | --- |
| Low-rank 2D hidden-field recovery with augmented dense anchors | Qualified supported | `outputs/tables/high_risk_claim_ladder_summary.json`; best protocol `terminal_plus_dense_anchors_5pct` median field error `0.08653171328673807` | Protocol-limited reduced benchmark, not sparse-port full 2D recovery. |
| Terminal-only full-field 2D rescue | Failed but informative | `outputs/tables/high_risk_claim_ladder_summary.json` | Defines observability boundary; do not claim solved terminal-only 2D inverse. |
| Actual reduced PINN stiffness mitigation | Qualified supported | `outputs/tables/integrated_stiffness_stl_summary.json`; continuation/adaptive gain `0.4845205762225727` | Reduced autograd PINN audit only. |
| Seiler-style multi-head STL transfer | Qualified supported | `outputs/tables/integrated_stiffness_stl_summary.json`; frozen-trunk gain `0.36685026479233396` | Seiler-style mechanics implemented; full literature reproduction still forbidden. |
| Fourier/F-SPS universal superiority | Forbidden | `outputs/tables/fourier_fsps_conditional_superiority_summary.json` | Only conditional sharp/front-regime benefit is supported. |
