# Next actions

## Immediate next step

The immediate step is `manuscript figure/table drafting and claim-boundary tightening` after the high-throughput `gamma_sub` identifiability pack and bounded F-SPS medium-budget benchmark. Use the existing synthetic numerical digital-twin evidence to draft the main SCI narrative around constrained `gamma_sub` recovery, profile-likelihood/phase-diagram limitations, protocol robustness, and explicit `T_sw` confounding boundaries.

Do not run new training or large ODE sweeps in the next phase unless a new task explicitly authorizes them. The constrained `gamma_sub` inversion remains the most stable paper mainline. F-SPS-PINN v2 remains a method-development line and should be positioned as appendix, discussion, or future work because the current medium-budget subset does not show superiority over the free-log-sigma shortcut.
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
7. Use the multi-protocol/profile-likelihood validation pack to strengthen the reviewer-defense narrative: multi-protocol checks increase experimental breadth, profile likelihood explains objective geometry, joint-boundary cases define nuisance-release limits, and protocol-design sensitivity adds forward-looking innovation.

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
