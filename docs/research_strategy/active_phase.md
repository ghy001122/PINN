# Active Phase

## Current Phase

`F-SPS-PINN v2 Fourier on/off ablation under stress`

The literature-backed constrained `gamma_sub` inversion stage is complete. The F-SPS-PINN architecture MVP, v2 smoke training pipeline, v2 small-run baseline, and v2 phase-transition stress preflight are complete. The current authorized phase is a small Fourier on/off ablation under the sharp-transition stress condition.

## Why This Phase Is Active

The completed identifiability, confounding, constrained-inversion, paper-readiness, continuous off-grid refinement, v2 baseline, and v2 stress-preflight audits show:

- port-only full hidden-field inversion is ill-posed for `delta_T`, `c_v`, `m`, and `sigma`;
- `gamma_sub` is identifiable only as a constrained reduced inverse target when switching and conductivity priors are fixed or tightly bounded;
- `T_sw` remains the limiting confounder;
- the v2 small-run baseline confirms both `free_log_sigma` and `white_box_vo2_sigma` paths can run under matched settings, but it does not support a performance-superiority claim;
- the v2 stress preflight confirms numerical stability and trainability for `white_box_vo2_sigma` under mild, sharp, near-threshold, and high-contrast synthetic stress cases, but it also does not support a performance-superiority claim;
- the next bounded method check is whether Fourier-pyramid features help under a shared sharp-transition stress condition.

## Allowed Work

- run a small CPU Fourier on/off ablation with epochs <= 50;
- keep `conductivity_mode = white_box_vo2_sigma` for the main comparison;
- keep the same seed, epochs, field-anchor points, loss weights, and sharp-transition stress condition for Fourier off and Fourier on;
- use the frozen Ground Truth v1.1 triangle data as read-only training target and sparse observation input;
- commit lightweight JSON/CSV evidence only;
- update compact project context and Codex reports for this phase.

## Not Allowed In This Phase

Do not do these unless a later explicit task authorizes them:

- open a new Ground Truth revision or modify frozen Ground Truth v1.1 configs, data, metrics, report, default parameters, or equations;
- replace the old `log_sigma` / v0 / v1 / v1.1 main training paths;
- run long training experiments or overwrite existing results;
- claim F-SPS-PINN performance superiority from the Fourier ablation;
- claim real VO2/NbO2 experimental validation;
- claim sparse-port unique full hidden-field recovery;
- claim stress preflight or Fourier ablation has solved phase-transition stiffness;
- start STL continuation, dynamic gate training, frequency loss, observability-augmented sparse temperature or state recovery, NeuroSPICE, NeuroPINN, VSN, or system-level mapping.

## Evidence Boundary

All current results remain synthetic numerical digital-twin benchmark evidence. This phase tests a small Fourier-feature switch under a fixed stress condition; it does not create a formal performance conclusion, a complete experimental conclusion, or a validated full device model.
