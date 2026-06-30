# Active Phase

## Current Phase

`SCI manuscript evidence consolidation`

The literature-backed constrained `gamma_sub` inversion, continuous off-grid refinement, paper-readiness audit, and F-SPS-PINN v2 method-development checks are complete for the current sprint. The active work is now consolidation of evidence, claim boundaries, and manuscript-ready figure/table routing. This phase is documentation and evidence-chain work only; it does not open a new training campaign or a Ground Truth revision.

## Why This Phase Is Active

The completed audits show:

- port-only full hidden-field recovery is ill-posed for `delta_T`, `c_v`, `m`, and `sigma`;
- identifiability-guided target-space reduction is required for a defensible inverse problem;
- constrained `gamma_sub` inversion is the strongest paper mainline when switching and conductivity priors are fixed or tightly bounded;
- `T_sw` remains the limiting confounder and must be controlled in the claim boundary;
- F-SPS-PINN architecture MVP, v2 smoke training, v2 small-run baseline, phase-transition stress preflight, and Fourier on/off ablation are bounded method-development evidence;
- the v2 Fourier ablation did not prove performance superiority, so F-SPS-PINN should remain appendix, discussion, or future-work material unless a separate method paper is explicitly opened.

## Allowed Work

- consolidate manuscript evidence into paper-facing tables and claim-boundary documents;
- map existing scripts, configs, summary JSON/CSV files, and reports to proposed figures and tables;
- update project state files so reviewers can trace each claim to reproducible synthetic numerical evidence;
- keep the constrained `gamma_sub` inverse story as the main manuscript line;
- keep F-SPS-PINN v2 results as appendix, discussion, or future-work evidence.

## Not Allowed In This Phase

Do not do these unless a later explicit task authorizes them:

- modify frozen Ground Truth v1.1 configs, data, metrics, reports, default parameters, or equations;
- run new training experiments, long ablations, or overwrite existing outputs;
- replace the constrained `gamma_sub` manuscript line with F-SPS-PINN;
- claim F-SPS-PINN or Fourier features are performance-superior from the current small-run evidence;
- claim real VO2/NbO2 experimental validation;
- claim sparse-port observations uniquely recover full hidden fields;
- start STL continuation, dynamic gate training, frequency loss, observability-augmented sparse temperature/state recovery, NeuroSPICE, NeuroPINN, VSN, or system-level mapping.

## Evidence Boundary

All current results remain synthetic numerical digital-twin benchmark evidence. This phase supports manuscript organization and claim discipline; it does not create new experimental evidence, a full 3D device validation, or a port-only full-field recovery result.