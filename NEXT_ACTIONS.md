# Next actions

## Immediate next step

The immediate step is `main-manuscript drafting and final figure/table assembly from calibrated gamma_sub evidence`.

The latest v2 pack confirms that external literature curve fitting is ethically blocked until provenance-backed digitized CSV/Sheet data are added, while the T_sw calibration-before-inversion workflow and ODE-backed calibrated sequential protocol validation strengthen the constrained `gamma_sub` manuscript line. The next work should assemble final main figures, tables, and prose from existing synthetic numerical digital-twin evidence, not start a new large experiment.

The constrained `gamma_sub` inversion remains the most stable paper mainline. F-SPS-PINN v2 remains appendix, discussion, or future-work material because current evidence still does not support a performance-superiority claim.

## Main manuscript line

1. Present Ground Truth v1.1 as a synthetic one-dimensional reduced-order benchmark.
2. Show that sparse electrical port observations do not uniquely recover full hidden fields.
3. Use identifiability analysis to justify target-space reduction.
4. Present constrained `gamma_sub` inversion under fixed or tightly bounded priors.
5. Use confounding, prior-width, off-grid, observation-count, continuous-refinement, T_sw phase-map, auxiliary-observability, response-surface anchor verification, sequential protocol preflight, and statistical robustness audits as reviewer-defense evidence.

## Appendix or supplementary line

- PINN inverse v0/v1/v1.1 negative and diagnostic results.
- F-SPS-PINN architecture MVP.
- v2 smoke training.
- v2 small-run free-log-sigma versus white-box `vo2_sigma` baseline.
- v2 phase-transition stress preflight.
- v2 Fourier on/off ablation.
- Balanced F-SPS medium-budget benchmark.

These results are useful engineering evidence but do not currently support a claim of F-SPS-PINN performance superiority.

## Recommended tasks

1. Draft the manuscript around `docs/paper/manuscript_outline_v1.md`.
2. Use `docs/paper/claim_stress_test_matrix.md` as the overclaim guardrail.
3. Build final figures from `docs/paper/proposed_main_figures.md` and tables from `docs/paper/proposed_tables.md`.
4. Keep the wording explicit: synthetic numerical digital-twin benchmark, not experimental data.
5. Treat `T_sw` as the main limitation and required prior/calibration boundary.
6. Use sequential protocol design as a hypothesis/preflight result, not a validated experimental design.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics, manifest, equations, or default parameters.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field recovery.
- Do not claim F-SPS-PINN, Fourier features, stress preflight, or phase-transition closure solved the inverse problem.
- Do not claim every dense response-surface grid point is simulator-backed unless a future task re-solves those cases.
- Do not start STL continuation, observability-augmented full-field recovery, experimental sparse temperature/state extension, VO2-NbO2 oscillator work, NeuroSPICE/NeuroPINN, or system-level mapping unless explicitly authorized.

## Deferred method enhancements

Record these as future options, not current manuscript-critical work:

- implement gamma_sub-PINN;
- add stiff transfer learning continuation;
- add observability-augmented full-field recovery or experimental sparse `T/m` extension;
- extend F-SPS-PINN as a separate method paper after stronger ablation evidence.
