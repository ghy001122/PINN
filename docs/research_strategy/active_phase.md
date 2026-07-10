# Active Phase

## Current Phase

`OASIS-PINN evidence actualization v7`

The current phase actualizes the OASIS-PINN supplementary evidence chain by replacing proxy or hand-crafted evidence with simulator-backed, residual-computed, and claim-gated evidence. It does not revise frozen Ground Truth v1.1 and does not change the main manuscript line: calibration-gated constrained `gamma_sub` inversion remains the safest SCI core claim.

## Evidence Added Or Corrected

- Multilayer sandwich forward residuals are computed explicitly rather than stubbed: potential jump, normal-current mismatch, temperature jump, heat-flux mismatch, substrate Robin residual, and an energy-balance gate.
- The multilayer forward benchmark is downgraded to `failed_but_informative` because the official reduced energy-balance gate does not pass.
- OASIS-PINN port reconstruction now uses `series_stack` as the main physical port solver. `mean_sigma_ablation` remains available only as an explicit ablation path.
- Terminal-only active protocol rescue and low-dimensional sandwich inverse are now simulator-backed rather than hand-crafted feature-matrix evidence; both are `failed_but_informative` in the official v7 outputs.
- Structured 2D field recovery now uses a simulator-generated ensemble POD basis and a holdout target with no target leakage. The official v7 field-recovery status is `forbidden`.
- Phase-aware STL repair is an actual torch smoke audit, but remains `failed_but_informative`.
- Adaptive Fourier/F-SPS evidence remains actual autograd training. The best gated method is `stiffness_gated_fourier` with `qualified_supported` status, while `adaptive_f_sps` itself remains `failed_but_informative`; universal superiority remains forbidden.

## Claim Boundary

Allowed: synthetic numerical digital-twin supplementary evidence for model-structure checks, observability limits, simulator-backed negative results, and condition-limited stiffness-gated Fourier method development.

Forbidden: experimental validation, full FEM/device-grade reproduction, terminal-only arbitrary full-field recovery, full STL-PINN reproduction, universal Fourier/F-SPS superiority, or replacing the constrained `gamma_sub` manuscript core with OASIS-PINN claims.
