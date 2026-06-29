# Active Phase

## Current Phase

`F-SPS-PINN architecture MVP`

The literature-backed constrained `gamma_sub` inversion stage is complete. The
current authorized phase is an isolated architecture MVP for phase-transition
PINN method components.

## Why This Phase Is Active

The completed identifiability, confounding, constrained-inversion,
paper-readiness, and continuous off-grid refinement audits show:

- port-only full hidden-field inversion is ill-posed for `delta_T`, `c_v`, `m`,
  and `sigma`;
- `gamma_sub` is identifiable only as a constrained reduced inverse target when
  switching and conductivity priors are fixed or tightly bounded;
- `T_sw` remains the limiting confounder;
- the next method step is to add isolated, differentiable, numerically stable
  phase-transition architecture components before they are connected to any new
  training workflow.

## Allowed Work

- add isolated F-SPS-PINN architecture MVP modules and unit tests;
- add a VO2-like white-box constitutive closure for synthetic numerical
  digital-twin benchmarks;
- add opt-in Fourier-pyramid embeddings without changing old model defaults;
- add dynamic residual gating and differentiable frequency/event metrics;
- update compact project context and Codex reports for this phase.

## Not Allowed In This Phase

Do not do these unless a later explicit task authorizes them:

- replace the old `log_sigma` / v0 / v1 / v1.1 main training paths;
- run long training experiments or overwrite existing results;
- modify frozen Ground Truth v1.1 configs, data, metrics, report, default
  parameters, or equations;
- claim real VO2/NbO2 experimental validation;
- start F-Pyramid production training, STL continuation, observability-augmented
  sparse temperature or state recovery, NeuroSPICE, NeuroPINN, VSN, or
  system-level mapping.

## Evidence Boundary

All current results remain synthetic numerical digital-twin benchmark evidence.
This phase adds architecture components only; it does not create a complete
experimental conclusion or a validated full device model.