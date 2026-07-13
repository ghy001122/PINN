# Active Phase

Governance links: `PROJECT_GOAL.md`, `docs/research_strategy/goal_status.md`, and `docs/research_strategy/codex_new_dialog_handoff_d23a576.md`. Governance consolidation does not authorize a new research experiment or change the v10 gates below.
## Current Phase

`control-volume multidomain OASIS and inverse repair v10`

The current phase actualizes control-volume physics and valid noisy-target inversion after v9 exposed supervised/smoothness and profile-likelihood gaps. It does not revise frozen Ground Truth v1.1 and does not replace the main manuscript line: calibration-gated constrained `gamma_sub` inversion remains the safest SCI core claim.

## V10 Gate Result

- P0 physical semantics: passed as a reduced synthetic implementation gate. Electrical current stops at BE; substrate is thermal-only. VO2 normalized and literature-shape profiles are separate; NbO2 uses PF plus electrothermal feedback without primary-path phase fraction.
- P1 control-volume multidomain training: failed. Median `E_T=0.37563055753707886`, median `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success rate `0.0`.
- P2 repaired noisy inverse: failed_but_informative. Noisy targets are re-inverted, but thermal blocks and interval coverage fail strict gates; selected protocols are not full-rank for all family parameters.
- P3 segmented-electrode y-z forward: qualified implementation support. Uniform-limit relative error `7.666968074108158e-12`; observability rank increases from `1` to `3`. No field-recovery claim follows.
- P4 STL/Fourier/F-SPS: blocked because P1 failed.
- Generalization: formal leave-one-factor preflight only; cross-stack, pulse, interface, and especially cross-material transfer remain weak.

## Evidence Added Or Corrected

- P0 phase-activated multilayer forward now uses SnSe as a low-`k`, high-`sigma` barrier prior, material-family-specific VO2/NbO2/generic kernels, independent per-interface `Rc/Rth`, coupled y-z lateral conduction, and activation gates.
- Official P0 activation rates: VO2 normalized `1.0`, VO2 literature anchored `1.0`, NbO2 PF/electrothermal `0.6666666666666666`; P0 activation gate `True`.
- P0 v10 topology checks: electrical/thermal domains are separated, substrate sigma bypass is removed, autonomous RC ODE is used, and the NbO2 phase-fraction shortcut is disabled on the primary path.
- P1 control-volume multidomain training now uses actual CV residuals, one-sided interface losses, and monolithic/ordered/CV/hard-BC/mortar variants. The strict full-mortar gate fails: median `E_T=0.37563055753707886`, median `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success rate `0.0`.
- P2 active terminal inverse v3 re-inverts noisy targets and routes VO2/NbO2 through material-specific parameter blocks. It remains `failed_but_informative`: selected protocols are rank deficient for full family vectors, thermal blocks fail, and interval coverage is below gate.
- P3 segmented-electrode y-z forward is implemented and passes the uniform-series/current-balance implementation gate, but it is only forward/observability support. It does not establish 2D hidden-field recovery.
- P4 STL/Fourier remains blocked because the strict P1 gate failed; matched-budget algorithm superiority cannot be claimed on a failed base solver.

## Claim Boundary

Allowed: synthetic numerical digital-twin evidence that v10 implements electrical/thermal topology separation, mechanism-routed material kernels, strict CV/mortar training audits, repaired noisy-target terminal inverse audits, and segmented-electrode y-z forward/current integration. P1/P2 remain failed_but_informative; only P0 physical semantics and P3 forward/observability implementation are qualified-supported in this phase.

Qualified/limited: P2 terminal inverse has strong Jacobian rank evidence and low total median error, but strict block-wise sequential recovery is not fully supported.

Forbidden: experimental validation, full FEM/device-grade reproduction, terminal-only arbitrary full-field recovery, full STL-PINN reproduction, LoRA-STL implementation, universal Fourier/F-SPS superiority, or replacing the constrained `gamma_sub` manuscript core with OASIS-PINN claims.
