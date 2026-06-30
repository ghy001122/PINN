# Active Phase

## Current Phase

`SCI gap-closing validation pack`

The current task is to close reviewer-facing validation gaps for the constrained `gamma_sub` manuscript line. This phase does not continue F-SPS-PINN, does not open a new Ground Truth revision, and does not claim experimental validation.

## Why This Phase Is Active

The completed audits show:

- port-only full hidden-field recovery is ill-posed for `delta_T`, `c_v`, `m`, and `sigma`;
- identifiability-guided target-space reduction is required for a defensible inverse problem;
- constrained `gamma_sub` inversion is the strongest paper mainline when switching and conductivity priors are fixed or tightly bounded;
- `T_sw` remains the limiting confounder and must be controlled in the claim boundary;
- the observability-augmented gamma_sub audit shows that sparse temperature anchors alone did not reduce the wide `T_sw` mismatch bias in the current candidate-grid setup, while narrowing the `T_sw` prior reduced the gamma error;
- the multi-protocol recoverability, profile-likelihood landscape, joint-inversion boundary, and protocol-design audits now provide reviewer-facing evidence on generalization, objective geometry, nuisance-release ambiguity, and stimulation design;
- F-SPS-PINN architecture MVP, v2 smoke training, v2 small-run baseline, phase-transition stress preflight, and Fourier on/off ablation are bounded method-development evidence only.

## Allowed Work

- run lightweight validation audits that strengthen the constrained `gamma_sub` manuscript story;
- scan `T_sw` prior-width effects while estimating only `gamma_sub`;
- test whether temperature-anchor placement explains the failure of sparse anchors in the previous observability audit;
- compare simple scalar baselines to show that the manuscript contribution is identifiability-guided target reduction and prior-boundary auditing, not a more complicated optimizer;
- build a two-dimensional T_sw confounding phase map that separates calibration-error amplitude from residual prior-width effects;
- run auxiliary observability sweeps that compare synthetic T, derivative, m, sigma, and calibrated-`T_sw` information channels;
- run multi-protocol, profile-likelihood, joint-boundary, and protocol-design audits that estimate only `gamma_sub`;
- update project state, registries, lightweight tables, and Codex reports.

## Not Allowed In This Phase

Do not do these unless a later explicit task authorizes them:

- modify frozen Ground Truth v1.1 configs, data, metrics, reports, default parameters, or equations;
- run new F-SPS-PINN experiments or long training experiments;
- replace the constrained `gamma_sub` manuscript line with F-SPS-PINN;
- claim real VO2/NbO2 experimental validation;
- claim sparse-port observations uniquely recover full hidden fields;
- claim unconditional `gamma_sub` identifiability under arbitrary released priors;
- start STL continuation, dynamic gate training, frequency loss, observability-augmented full-field recovery, experimental sparse temperature/state extension, NeuroSPICE, NeuroPINN, VSN, or system-level mapping.

## Evidence Boundary

All current results remain synthetic numerical digital-twin benchmark evidence. This phase strengthens manuscript defensibility; it does not create real experimental evidence, full 3D device validation, or port-only full-field recovery.
