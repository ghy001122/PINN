# Active Phase

## Current Phase

`F-SPS-PINN v2 small-run baseline`

The literature-backed constrained `gamma_sub` inversion stage is complete. The F-SPS-PINN architecture MVP and v2 smoke training pipeline are also complete. The current authorized phase is a small-run synthetic numerical baseline that compares the old free `log_sigma` conductivity shortcut against the white-box `vo2_sigma(T, c_v, m)` closure under matched training settings.

## Why This Phase Is Active

The completed identifiability, confounding, constrained-inversion, paper-readiness, and continuous off-grid refinement audits show:

- port-only full hidden-field inversion is ill-posed for `delta_T`, `c_v`, `m`, and `sigma`;
- `gamma_sub` is identifiable only as a constrained reduced inverse target when switching and conductivity priors are fixed or tightly bounded;
- `T_sw` remains the limiting confounder;
- the architecture MVP is unit-tested and the v2 smoke loop confirms finite forward/backward/train behavior with `vo2_sigma`;
- the next method step is to compare the free conductivity shortcut with the white-box closure in a bounded small-run baseline.

## Allowed Work

- run the v2 small-run baseline with matched seed, epochs, anchor count, and sparse terminal observations;
- compare `free_log_sigma` and `white_box_vo2_sigma` as conductivity modes;
- commit lightweight JSON/CSV evidence only;
- update compact project context and Codex reports for this phase.

## Not Allowed In This Phase

Do not do these unless a later explicit task authorizes them:

- replace the old `log_sigma` / v0 / v1 / v1.1 main training paths;
- run long training experiments or overwrite existing results;
- modify frozen Ground Truth v1.1 configs, data, metrics, report, default parameters, or equations;
- claim F-SPS-PINN performance superiority from the small-run baseline;
- claim real VO2/NbO2 experimental validation;
- start STL continuation, observability-augmented sparse temperature or state recovery, NeuroSPICE, NeuroPINN, VSN, or system-level mapping.

## Evidence Boundary

All current results remain synthetic numerical digital-twin benchmark evidence. This phase is a bounded method-development comparison; it does not create a formal performance conclusion, a complete experimental conclusion, or a validated full device model.
