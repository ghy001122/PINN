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

## OASIS-PINN Multilayer Sandwich And High-Risk Resolution v6

Synthetic numerical digital-twin evidence only. Frozen Ground Truth v1.1 remains unchanged.

| Claim | Status | Evidence | Boundary |
|---|---|---|---|
| Literature prior registry complete | qualified_supported | `outputs/tables/literature_prior_consistency_summary.json` | Priors only, not measured parameters |
| Boundary-aware multilayer sandwich forward | qualified_supported | `outputs/tables/multilayer_sandwich_device_summary.json` | Not full FEM or device-grade |
| Augmented structured 2D field recovery | qualified_supported | `multi_terminal_plus_fisher_anchors` median error 0.19897395319670247 | Requires augmented Fisher anchors; terminal-only remains forbidden |
| Active terminal-only low-dimensional inverse | qualified_supported | `combined_terminal_protocol` median error 0.056375606896068575 | Low-dimensional parameters only |
| Phase-aware STL repair | failed_but_informative | Best gain 0.09389518340983438 | Full STL-PINN reproduction remains forbidden |
| Adaptive Fourier/F-SPS superiority | failed_but_informative | Pareto 0.6666666666666666; smooth degradation 0.1821856000041686 | Universal superiority remains forbidden |
| Low-dimensional sandwich inverse | qualified_supported | `combined` median error 0.04044092905036974 | Not arbitrary field inversion |

## OASIS-PINN Evidence Actualization v7 Update

All entries remain synthetic numerical digital-twin benchmark evidence, not experimental data. This section supersedes the v6 interpretation where v7 uses stricter simulator-backed or actual-training evidence.

| Claim | Updated status | Evidence | Boundary |
|---|---|---|---|
| Boundary-aware multilayer sandwich forward | failed_but_informative | `outputs/tables/multilayer_sandwich_device_summary.json`; `energy_balance_gate_passed = false`, median interface residual `1.0` | Residuals are computed, not stubbed; no full FEM/device-grade claim. |
| OASIS main port solver | qualified_supported as implementation | `src/pinnpcm/pinn/oasis_components.py` | `series_stack` is the physical default; `mean_sigma_ablation` is ablation only. |
| Active terminal-only low-dimensional rescue | failed_but_informative | `outputs/tables/terminal_only_active_protocol_rescue_simulator_summary.json`; success rates `0.0` | Simulator-backed terminal observables do not support the prior hand-crafted feature-matrix claim. |
| Low-dimensional sandwich inverse | failed_but_informative | `outputs/tables/multilayer_sandwich_low_dim_inverse_summary.json`; condition numbers up to finite sentinel `1e300` | Severe ill-conditioning; not arbitrary field inversion. |
| Structured 2D field recovery | forbidden | `outputs/tables/claim_resolution_2d_field_summary.json`; best median field error `0.7805643071194288`, holdout target, no leakage | Ensemble POD and Fisher anchors did not clear the recovery gate. |
| Phase-aware STL repair | failed_but_informative | `outputs/tables/phase_aware_stl_repair_summary.json`; actual torch smoke, best gain `0.01678575282349345` | Actualized but not a full STL-PINN reproduction. |
| Best stiffness-gated Fourier method | qualified_supported | `outputs/tables/adaptive_fourier_fsps_superiority_summary.json`; best gated method `stiffness_gated_fourier` | Condition-limited method-development evidence only. |
| Adaptive F-SPS itself | failed_but_informative | `outputs/tables/adaptive_fourier_fsps_superiority_summary.json`; `adaptive_f_sps_status = failed_but_informative` | Universal F-SPS/Fourier superiority remains forbidden. |

## Conservative Multidomain OASIS-PINN v8 Claim Gate

All entries are synthetic numerical digital-twin benchmark evidence, not experimental data.

| Claim | Status | Evidence | Boundary |
| --- | --- | --- | --- |
| Conservative multilayer P0 forward | qualified_supported | `outputs/tables/conservative_multilayer_forward_summary.json`; P0 gate `True`; energy median `0.0` | Reduced 2.5D finite-volume diagnostic only; not full FEM or device-grade. |
| Multidomain OASIS-PINN components | qualified_supported as implementation smoke | `outputs/tables/multidomain_oasis_pinn_summary.json` | Finite autograd smoke, not performance evidence. |
| Active terminal-only multidomain inverse | failed_but_informative | `outputs/tables/active_protocol_identifiability_summary.json`; best rank `0` | Terminal observables do not identify all tested parameters in this audit. |
| 2D field-resolution recovery | blocked | `outputs/tables/oasis_2d_field_resolution_summary.json`; `blocked_until_actual_electrode_BC_multi_terminal_solver_is_implemented` | Requires actual electrode-BC multi-terminal solver before any positive claim. |
| Phase-aware STL repair | failed_but_informative | `outputs/tables/phase_aware_stl_repair_summary.json`; best gain `0.10802334582762174` | Full STL-PINN and LoRA-STL remain forbidden. |
| Adaptive Fourier/F-SPS superiority | forbidden | `outputs/tables/adaptive_fourier_fsps_superiority_summary.json`; true Pareto used | No universal or adaptive-F-SPS superiority claim. |

## Phase-Activated Multidomain OASIS-PINN v9 Claim Gate

All entries are synthetic numerical digital-twin benchmark evidence, not experimental data.

| Claim | Status | Evidence | Boundary |
| --- | --- | --- | --- |
| Phase-activated multilayer forward | qualified_supported | `outputs/tables/phase_activated_multilayer_forward_summary.json`; VO2 `0.8888888888888888`, NbO2 `0.8888888888888888` activation rates | Reduced y-z finite-volume benchmark only. |
| Multidomain OASIS small training | qualified_supported as smoke/training gate | `outputs/tables/multidomain_oasis_training_summary.json`; full mortar success `True` | Not performance superiority. |
| Activated terminal trace inverse | failed_but_informative | `outputs/tables/active_protocol_identifiability_v2_summary.json`; `outputs/tables/sequential_terminal_inverse_v2_summary.json` | Jacobian gates pass, but strict block-error gate `False`; no full-field recovery claim. |
| 2D field recovery | blocked | `outputs/tables/oasis_2d_field_resolution_v2_summary.json` | Needs actual electrode-BC multi-terminal y-z solver. |
| STL/Fourier on activated PDE | blocked | `outputs/tables/phase_activated_algorithm_summary.json` | Needs canonical Seiler reproduction, front-aligned LoRA, and matched-budget Pareto audit. |

