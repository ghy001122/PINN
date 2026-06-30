# Next actions

## Immediate next step

The immediate step is `SCI manuscript figure and table drafting` with the gap-closing validation pack, T_sw confounding phase-map, auxiliary observability sweep, and reproducible figure-ready outputs now available. Use existing synthetic numerical digital-twin evidence to build a manuscript-ready claim matrix, figure/table routing, and reviewer-defense boundary. Do not run new training experiments in this phase.

The constrained `gamma_sub` inversion remains the most stable paper mainline. F-SPS-PINN v2 is a method-development line and should be positioned as appendix, discussion, or future work unless a separate method paper is explicitly opened.

## Main manuscript line

1. Present Ground Truth v1.1 as a synthetic one-dimensional reduced-order benchmark.
2. Show that sparse electrical port observations do not uniquely recover full hidden fields.
3. Use identifiability analysis to justify target-space reduction.
4. Present constrained `gamma_sub` inversion under fixed or tightly bounded priors.
5. Use confounding, prior-width, off-grid, observation-count, continuous-refinement, T_sw phase-map, and auxiliary-observability audits as reviewer-defense evidence.

## Appendix or supplementary line

- PINN inverse v0/v1/v1.1 negative and diagnostic results.
- F-SPS-PINN architecture MVP.
- v2 smoke training.
- v2 small-run free-log-sigma versus white-box `vo2_sigma` baseline.
- v2 phase-transition stress preflight.
- v2 Fourier on/off ablation.

These results are useful engineering evidence but do not currently support a claim of F-SPS-PINN performance superiority.

## Recommended tasks

1. Draft manuscript figures and tables from `docs/paper/sci_manuscript_evidence_matrix.md` and the generated `outputs/figures/gamma_sub_gap_closing/` figure-ready files.
2. Convert the main `gamma_sub` evidence chain into a concise Method/Result narrative.
3. Prepare a limitations section that explicitly names `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` confounding.
4. Keep F-SPS-PINN as an appendix or future-work subsection unless new evidence is separately authorized.
5. Use the new gap-closing audits to write a sharper limitations paragraph: `T_sw` prior width dominates, anchor placement alone did not fix the bias, and scalar optimizers are not the novelty, and non-calibrated synthetic auxiliary proxies did not overcome wide `T_sw` mismatch.
6. Keep all future results reproducible through scripts and lightweight JSON/CSV evidence.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics, manifest, equations, or default parameters.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field recovery.
- Do not claim F-SPS-PINN, Fourier features, stress preflight, or phase-transition closure solved the inverse problem.
- Do not start STL continuation, observability-augmented full-field recovery, experimental sparse temperature/state extension, VO2-NbO2 oscillator work, NeuroSPICE/NeuroPINN, or system-level mapping unless explicitly authorized.

## Deferred method enhancements

Record these as future options, not current manuscript-critical work:

- implement gamma_sub-PINN;
- add stiff transfer learning continuation;
- add observability-augmented full-field recovery or experimental sparse `T/m` extension;
- extend F-SPS-PINN as a separate method paper after stronger ablation evidence.
