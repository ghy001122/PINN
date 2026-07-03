# Journal Positioning Matrix

All entries refer to synthetic numerical digital-twin benchmark evidence, not measured experimental data.

| Target level | Fit assessment | Evidence supporting fit | Remaining gap | Positioning rule |
| --- | --- | --- | --- | --- |
| SCI third-zone method/application journal | Plausible | Frozen GT v1.1, identifiability audit, constrained `gamma_sub` inversion, calibration tolerance, ODE spot-check, quasi-2D preflight, stiffness preflight, phase-field alignment smoke | Manuscript polishing and concise figure assembly | Main claim should be calibration-gated sparse-port reduced inversion in a 1D benchmark. |
| SCI second-zone edge | Possible but not locked | Broad synthetic evidence chain and reviewer-defense matrix | No real experiment and no provenance-backed external curve fit; F-SPS not yet a proven performance method | Submit only if framed as a rigorous numerical inverse-method benchmark, not device validation. |
| High-impact device/experiment venue | Not ready | None for experimental validation | Missing fabricated-device data, measured thermal/state observables, and external curve calibration | Do not target with current evidence. |

## Literature Positioning

- Seiler 2025 supports the relevance of stiffness-aware/continuation ideas for stiff PINN residuals; the current audit is a lightweight residual preflight, not a full STL-PINN reproduction.
- Zhao 2025 supports phase-field inverse PINN alignment; the current Allen-Cahn smoke benchmark is supplementary full-field-anchor evidence, not sparse-port inversion.
- Lee 2024 and Jurj 2026 support compact memristor PINN and physics-regularized surrogate positioning; they do not validate the synthetic benchmark as measured device data.

## Current Submission Boundary

The safest submission line is a method-oriented computational paper: sparse-port observability audit -> target-space reduction -> constrained `gamma_sub` inversion under fixed or tightly bounded priors -> reviewer-defense stress tests.
