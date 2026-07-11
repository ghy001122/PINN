# Active Phase

## Current Phase

`conservative multidomain OASIS-PINN v8 evidence actualization`

The current phase implements and audits conservative multidomain OASIS-PINN v8 as bounded supplementary evidence. It does not revise frozen Ground Truth v1.1 and does not change the main manuscript line: calibration-gated constrained `gamma_sub` inversion remains the safest SCI core claim.

## Evidence Added Or Corrected

- Conservative finite-volume multilayer P0 now uses explicit per-interface `Rc/Rth`, adaptive substeps, semi-implicit thermal solves, and conservation tests. The official P0 gate passes with energy-balance median `0.0` and interface residual median `6.620044358862851e-17`.
- OASIS-PINN multidomain components now have an actual autograd smoke: ordered stack encoder, per-layer experts, hard Dirichlet output transform, interface mortar loss, and series-stack port solve are finite.
- Active terminal protocol identifiability uses normalized Jacobians and terminal observables only. The official rank gate fails, so sequential terminal inverse is `failed_but_informative`.
- 2D field recovery is blocked until an actual electrode-BC multi-terminal solver is implemented; no positive full-field claim is produced.
- Phase-aware STL repair now runs a 100-step matched-budget actual torch diagnostic, but remains `failed_but_informative`; front-coordinate and LoRA-STL are explicitly not implemented.
- Adaptive Fourier/F-SPS evidence now uses true Pareto dominance rather than legacy gain tolerance as the claim gate; no universal or adaptive-F-SPS superiority claim is supported.

## Claim Boundary

Allowed: synthetic numerical digital-twin supplementary evidence for conservative multilayer implementation, finite multidomain OASIS-PINN components, honest identifiability failures, and blocked claim gates.

Forbidden: experimental validation, full FEM/device-grade reproduction, terminal-only arbitrary full-field recovery, full STL-PINN reproduction, LoRA-STL implementation, universal Fourier/F-SPS superiority, or replacing the constrained `gamma_sub` manuscript core with OASIS-PINN claims.
