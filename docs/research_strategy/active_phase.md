# Active Phase

## Current Phase

`F-SPS-PINN v2 phase-transition stress preflight`

The literature-backed constrained `gamma_sub` inversion stage is complete. The F-SPS-PINN architecture MVP, v2 smoke training pipeline, and v2 small-run baseline are complete. The current authorized phase is a stress preflight that tests whether the white-box `vo2_sigma(T, c_v, m)` closure remains numerically stable under synthetic phase-transition stiffness settings.

## Why This Phase Is Active

The completed identifiability, confounding, constrained-inversion, paper-readiness, and continuous off-grid refinement audits show:

- port-only full hidden-field inversion is ill-posed for `delta_T`, `c_v`, `m`, and `sigma`;
- `gamma_sub` is identifiable only as a constrained reduced inverse target when switching and conductivity priors are fixed or tightly bounded;
- `T_sw` remains the limiting confounder;
- the v2 small-run baseline confirms both `free_log_sigma` and `white_box_vo2_sigma` paths can run under matched settings, but it does not support a performance-superiority claim;
- the next method check is to stress the white-box VO2 closure with sharper transition, near-threshold, and high-contrast synthetic parameters.

## Allowed Work

- run a small CPU phase-transition stress preflight with epochs <= 20;
- test `white_box_vo2_sigma` under `mild_transition`, `sharp_transition`, `near_threshold`, and `high_contrast` cases;
- use the frozen Ground Truth v1.1 triangle data as read-only training target and sparse observation input;
- commit lightweight JSON/CSV evidence only;
- update compact project context and Codex reports for this phase.

## Not Allowed In This Phase

Do not do these unless a later explicit task authorizes them:

- open a new Ground Truth revision or modify frozen Ground Truth v1.1 configs, data, metrics, report, default parameters, or equations;
- replace the old `log_sigma` / v0 / v1 / v1.1 main training paths;
- run long training experiments or overwrite existing results;
- claim F-SPS-PINN performance superiority from the stress preflight;
- claim real VO2/NbO2 experimental validation;
- claim sparse-port unique full hidden-field recovery;
- start STL continuation, observability-augmented sparse temperature or state recovery, NeuroSPICE, NeuroPINN, VSN, or system-level mapping.

## Evidence Boundary

All current results remain synthetic numerical digital-twin benchmark evidence. This phase tests numerical stability and small-scale response under phase-transition parameter stress; it does not create a formal performance conclusion, a complete experimental conclusion, or a validated full device model.
