# OASIS-PINN Architecture

OASIS-PINN means Observability-Aware Sandwich Inverse and Stiffness-gated PINN. This is a method-development architecture scaffold for synthetic numerical digital-twin benchmarks, not a completed performance claim.

## Modules

1. Literature stack encoder.
2. Layer-wise neural field for `phi_l`, `T_l`, and optional `m`.
3. White-box constitutive kernel.
4. Differentiable port/circuit layer.
5. Observation operator `H_p`.
6. Stiffness-gated training controller.
7. Claim-gated inverse head.

## White-Box Kernels

- NbO2 reduced kernel: thermal-assisted Poole-Frenkel/NDR-like response.
- VO2 reduced kernel: hysteretic R(T)-like response.
- Generic PCM kernel: `sigma = (1-m) sigma_ins(T) + m sigma_met(T)`.

## Stiffness Indicator

```text
chi = max_s s(1-s)/w = 0.25/w
```

If `chi > chi_c`, the controller selects Fourier/front-focused/asinh branches. Otherwise it selects a vanilla or low-frequency branch.

## Claim Boundary

OASIS-PINN is a structured architecture proposal and testable implementation scaffold. It does not by itself prove full hidden-field recovery, terminal-only inverse uniqueness, F-SPS superiority, or experimental validation.
