# Claim-Gate Resolution Matrix

All entries are synthetic numerical digital-twin benchmark evidence, not experimental data.

## Control-Volume Multidomain OASIS v10

| Claim | Status | Evidence | Allowed wording | Forbidden wording |
| --- | --- | --- | --- | --- |
| Electrical/thermal topology and mechanism routing are implemented | qualified_supported | `physical_semantics_v10_summary.json` | A reduced synthetic multilayer model separates electronic and thermal domains and routes VO2/NbO2 mechanisms explicitly. | Device-grade or experimentally calibrated model. |
| CV multidomain OASIS solves the activated fields | failed_but_informative | `cv_multidomain_oasis_training_summary.json` | Strict CV/interface training exposes unresolved thermal and interface optimization. | P1 passed or OASIS field solver validated. |
| Active terminal inverse is noise robust | failed_but_informative | `sequential_terminal_inverse_v3_summary.json` | Re-inverting noisy targets identifies block-specific failures. | Robust terminal inverse solved. |
| Segmented-electrode y-z forward is implemented | qualified_supported | `multiterminal_yz_forward_summary.json` | The finite-volume forward solver passes current balance and uniform-limit regression and increases local observability rank. | Full 2D hidden-field recovery. |
| STL/Fourier/F-SPS on v10 | forbidden | `oasis_algorithm_gate_v10_summary.json` | Experiments remain blocked by the failed P1 gate. | Algorithm superiority or full STL reproduction. |
| OASIS generalizes across stacks/materials | failed_but_informative | `oasis_generalization_v10_summary.json` | Leave-one-factor preflight exposes severe stack, pulse, interface, and cross-family gaps. | Cross-material generalization. |

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
## Port-Physical 2D Inverse And Stiffness-Gated Training v3

All entries remain synthetic numerical digital-twin benchmark evidence, not experimental data. This section supersedes any interpretation that phase-mean terminal proxies or residual-proxy multipliers prove hidden-field recovery or method superiority.

| Claim | Status | Supporting table | Supporting figure | Allowed manuscript sentence | Forbidden overclaim | Required qualification |
| --- | --- | --- | --- | --- | --- | --- |
| Port-physical 2D inverse improves hidden-field recovery | forbidden | outputs/tables/port_physical_2d_inverse_summary.json | outputs/figures/port_physical_2d_inverse_error_by_protocol.png | A physically defined sheet-conductance observation was tested, but it did not improve over the v2 actual low-rank inverse. | Port-physical observations solve 2D hidden-field recovery. | Uses white-box sigma and port G, but field recovery remains below the gate. |
| POD/SVD basis improves 2D inverse | failed_but_informative | outputs/tables/port_physical_2d_inverse_summary.json | outputs/figures/port_physical_2d_inverse_error_by_protocol.png | In this quick profile, the analytic basis outperformed the POD basis, so POD is not yet a positive claim. | Learned POD basis guarantees field recovery. | POD was ensemble-derived and synthetic. |
| Fisher anchor placement improves 2D inverse | failed_but_informative | outputs/tables/port_physical_2d_inverse_summary.json | outputs/figures/port_physical_2d_anchor_placement_comparison.png | Fisher-style anchors were tested but did not clear the recovery gate. | Fisher anchors make sparse 2D recovery solved. | Anchor placement remains an optimization target. |
| Stiffness-gated Fourier/F-SPS hybrid | qualified_supported | outputs/tables/stiffness_gated_fourier_fsps_summary.json | outputs/figures/stiffness_gated_gain_vs_chi.png | A stiffness-indicator gate reduced smooth-regime degradation while preserving sharp/front gain in this small actual-training audit. | F-SPS/Fourier is universally superior. | Reduced synthetic quick profile; no experimental or universal claim. |
| STL repair audit | failed_but_informative | outputs/tables/integrated_stiffness_stl_summary.json | outputs/figures/integrated_stl_transfer_gain.png | Matched-budget STL repair was implemented but did not clear the gain/success gate. | Full STL-PINN reproduction is complete. | Use as negative evidence and repair target. |

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

