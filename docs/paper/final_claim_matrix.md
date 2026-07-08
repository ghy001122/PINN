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

## Actualized High-Risk Claim Ladder v2 Update

All statuses below are synthetic numerical digital-twin benchmark evidence.

| Claim | Updated status | Evidence | Boundary |
| --- | --- | --- | --- |
| Actual low-rank 2D field inverse | forbidden | `outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json`; best protocol `terminal_plus_sparse_anchors_2pct` median field error `0.544268189851365` | Heuristic support is not enough; actual coefficient inverse did not clear field gate. |
| Terminal-only low-dimensional parameter inverse | qualified_supported | `outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json`; terminal median parameter error `0.029775671121156505` | Parameter-only under strong priors; field recovery forbidden. |
| Actual stiffness continuation | qualified_supported | `outputs/tables/integrated_stiffness_stl_summary.json`; adaptive gain `0.37795297711408815` | Reduced actual-training audit only. |
| Seiler-style multi-head STL | failed_but_informative | `outputs/tables/integrated_stiffness_stl_summary.json`; frozen-trunk gain `-0.12675208187398518` | Implemented but not positive in expanded grid; full reproduction forbidden. |
| Actual Fourier/F-SPS conditional benefit | failed_but_informative | `outputs/tables/fourier_fsps_actual_training_summary.json`; best sharp method `f_sps_sampling` sharp gain `0.4391566795808073`, smooth degradation `0.8471974813135894` | Sharp gain is offset by smooth degradation; universal superiority forbidden. |
## Port-Physical 2D Inverse And Stiffness-Gated Training v3 Update

All statuses below are synthetic numerical digital-twin benchmark evidence.

| Claim | Updated status | Evidence | Boundary |
| --- | --- | --- | --- |
| Port-physical 2D field inverse | forbidden | `outputs/tables/port_physical_2d_inverse_summary.json`; best protocol `port_only` median field error `0.7692662179470062`; v2 reference `0.544268189851365` | White-box port conductance is more physical than phase-mean proxy, but it does not recover full fields. |
| POD/SVD basis | failed_but_informative | Analytic median field error `0.5118682682514191`; POD median field error `1.1138866245746613` | POD did not help in the quick profile; basis learning needs better ensemble design. |
| Fisher anchors | failed_but_informative | Fisher median field error `0.7785263955593109`; sensitivity median field error `0.7783682346343994` | Fisher-style anchors are not yet a positive observability claim. |
| Stiffness-gated hybrid | qualified_supported | `outputs/tables/stiffness_gated_fourier_fsps_summary.json`; sharp gain `0.17299439024092061`; smooth degradation `0.0` | Condition-limited method-development evidence only; universal superiority remains forbidden. |
| STL repair | failed_but_informative | `outputs/tables/integrated_stiffness_stl_summary.json`; best repair `STL_repair_head_only`; gain `-0.14315251294108938` | Repair did not turn STL into a positive claim; full STL-PINN reproduction remains forbidden. |
