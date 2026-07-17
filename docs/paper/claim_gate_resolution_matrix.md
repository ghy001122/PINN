# Claim-Gate Resolution Matrix

All entries are synthetic numerical digital-twin benchmark evidence, not experimental data.

## Authoritative V10 Claim Gate

| Claim | Status | Evidence | Allowed wording | Forbidden wording |
| --- | --- | --- | --- | --- |
| Electrical/thermal topology and mechanism routing are implemented | qualified_supported | `outputs/tables/physical_semantics_v10_summary.json` | A reduced synthetic multilayer model separates electrical and thermal domains and routes VO2/NbO2 mechanisms explicitly. | Device-grade or experimentally calibrated model. |
| CV multidomain OASIS solves the activated fields | failed_but_informative | `outputs/tables/cv_multidomain_oasis_training_summary.json` | Strict CV/interface training exposes unresolved thermal and interface optimization. | P1 passed or OASIS field solver validated. |
| Active terminal inverse is noise robust | failed_but_informative | `outputs/tables/sequential_terminal_inverse_v3_summary.json` | Re-inverting noisy targets identifies block-specific failures. | Robust terminal inverse solved. |
| Segmented-electrode y-z forward is implemented | qualified_supported | `outputs/tables/multiterminal_yz_forward_summary.json` | The finite-volume forward solver passes current-balance and uniform-limit checks and increases local observability rank. | Full 2D hidden-field recovery. |
| STL/Fourier/F-SPS on v10 | forbidden | `outputs/tables/oasis_algorithm_gate_v10_summary.json` | Experiments remain blocked by the failed P1 gate. | Algorithm superiority or full STL reproduction. |
| OASIS generalizes across stacks/materials | failed_but_informative | `outputs/tables/oasis_generalization_v10_summary.json` | Leave-one-factor preflight exposes stack, pulse, interface, and cross-family gaps. | Cross-material neural-operator generalization. |

Historical claim evolution remains in `docs/paper/final_claim_matrix.md`, reports, and `RESEARCH_LOG.md`; this generated matrix keeps the current gate plus the active reduced-2D/stiffness audit.

## Reduced 2D And Stiffness Audit

| Claim | Status | Supporting table | Supporting figure | Allowed manuscript sentence | Forbidden overclaim | Required qualification |
| --- | --- | --- | --- | --- | --- | --- |
| 2D reduced forward supported? | supported | outputs/tables/reduced_2d_phase_transition_forward_summary.json | outputs/figures/reduced_2d_forward_snapshots.png; outputs/figures/reduced_2d_port_traces.png | A reduced 2D synthetic phase-transition forward benchmark is finite and geometry-sensitive. | This is full 2D FEM or experimental validation. | Reduced thin-film model only; supplementary evidence. |
| 2D low-dimensional inverse supported? | qualified_supported | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | outputs/figures/reduced_2d_observability_claim_gate.png | Low-dimensional reduced 2D inverse diagnosis is feasible under augmented sparse observations. | Sparse terminal data uniquely recover 2D fields. | Only low-dimensional parameters and only under augmented observations. |
| Terminal-only 2D inverse supported? | failed_but_informative | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | outputs/figures/reduced_2d_observability_claim_gate.png | Terminal-only sparse observations fail this reduced 2D inverse claim gate. | Terminal-only data solve 2D inverse diagnosis. | Use as honest negative evidence. |
| Augmented-observation 2D inverse supported? | qualified_supported | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | outputs/figures/reduced_2d_observability_claim_gate.png | Augmented sparse proxy observations can support low-dimensional reduced 2D parameter diagnosis. | Augmented observations recover full 2D fields. | Success threshold is benchmark-specific; not experimental. |
| Full 2D hidden-field recovery supported? | forbidden | outputs/tables/reduced_2d_observability_limited_inverse_summary.json | none | Full 2D hidden-field recovery remains unsupported. | Full 2D hidden fields are uniquely recovered. | No full-field 2D inverse training evidence exists. |
| Stiffness cliff exists? | supported | outputs/tables/stiffness_2d_story_figure_manifest.json | outputs/figures/stiffness_residual_vs_transition_width.png | Narrow phase-transition widths create a residual stiffness cliff in the synthetic preflight. | This proves stiff PINN training is solved. | Residual preflight only. |
| Stiffness cliff mitigated? | supported | outputs/tables/stiffness_aware_algorithm_benchmark_summary.json | outputs/figures/stiffness_algorithm_error_vs_width.png | Continuation plus scale-aware weighting mitigates stiffness-induced degradation in the residual-proxy benchmark. | Stiffness is solved generally. | Synthetic algorithm benchmark, not full training proof. |
| Mini-STL-style transfer supported? | qualified_supported | outputs/tables/stiffness_aware_algorithm_benchmark_summary.json | outputs/figures/stiffness_algorithm_claim_gate.png | Mini-STL-style transfer is supported as a lightweight continuation/initialization audit. | Full STL-PINN reproduction is complete. | Use mini-STL-style wording only. |
| Full STL-PINN reproduction supported? | forbidden | outputs/tables/stiffness_aware_algorithm_benchmark_summary.json | none | Full STL-PINN reproduction remains future work. | The repository reproduced full stiff transfer learning. | No full STL training implementation was run. |
| Fourier/F-SPS superiority supported? | forbidden | outputs/tables/pinn_inverse_v2_fourier_ablation_summary.json; outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json | none | F-SPS and Fourier evidence remain appendix/future-work diagnostics. | F-SPS-PINN or Fourier features are superior. | Existing small-run evidence does not establish superiority. |

## Summary

- Reduced 2D forward supported: `True`.
- Terminal-only 2D inverse failed: `True`.
- Augmented low-dimensional 2D inverse allowed: `True`.
- Full 2D field recovery allowed: `False`.
- Stiffness cliff mitigated: `True`.
- Full STL claim allowed: `False`.

## 2026-07-15 VO2 / Full-PINN v2 Gate

| Claim | Status | Evidence | Allowed wording | Forbidden wording |
| --- | --- | --- | --- | --- |
| D0a source/SI semantics | `qualified_supported` sub-result | `outputs/tables/vo2_d0a_source_reproduction.json` | The author implementation and independent SI rewrite agree at the declared 10 ns semantics. | Independent external validation or repository fit. |
| D0a completed reproduction | `failed_but_informative` | same JSON; `outputs/figures/vo2_d0a_source_semantics_v2.png` | The preregistered time-step convergence gate fails. | D0 passed or 13 V was evaluated. |
| N0 implementation contract | `supported` as code fact | `outputs/tables/full_pinn_contract_v1.json` | A versioned non-placeholder full 1D architecture exists. | Reliable trained full PINN. |
| N0 trained forward evidence | `failed_but_informative` | `outputs/tables/n0_cv_e_v3r_forensic_resolution.json` | v3r's port gate passes, but residual, field, interface-flux, and conservation gates fail; recovery is ineligible and N0 is stopped. | Reliable full-PINN forward, conservation, sensitivity, or inverse readiness. |
| Solver-first SID/EC-OQ discovery | `failed_but_informative` | `outputs/tables/sid_ec_oq_summary.json` | Derivative, event-window, stability, and dual-geometry gates fail; both ideas are deleted from the active route. | Protocol rank/rotation, SID, EC-OQ, or quotient superiority. |
| D0b-D0d and N1-N3 | `forbidden` as completed evidence | `outputs/tables/vo2_protocol_quotient_full_pinn_v2_summary.json` | Not run after upstream stop gates. | Public-data quotient, protocol rotation, sensitivity fidelity, or inverse success. |
