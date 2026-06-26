# PINN And Phase-Change Literature Digest

This digest compresses the useful local reference-pack notes for future
low-token work. It is not a full literature review.

## Directly Relevant Threads

### Stiff PINN And Continuation Training

Seiler et al. 2025, "Stiff Transfer Learning for Physics-Informed Neural
Networks", is relevant for later continuation or stiff-transfer training. It
supports the idea that multi-physics inverse problems with disparate time scales
may require staged training, transfer, or continuation. This is deferred until
the active phase explicitly authorizes STL or continuation work.

### Memristor PINN And Surrogate Modeling

Lee et al. 2024, "A Compact Memristor Model Implemented Using Physics-Informed
Neural Networks", supports using PINN-like neural models for compact memristor
behavior. Jurj 2026, "physics-regularized neural surrogate framework for
printed memristors", supports physics-regularized surrogate modeling for
memristive devices. These sources support the general modeling route but do not
make the current synthetic benchmark experimental.

### Phase-Transition Inverse PINN

Zhao et al. 2025, "Physics-informed neural networks for inverse problems in
phase field models", supports inverse-PINN framing for phase-transition
systems. Its relevance is conceptual: the current project uses a reduced
one-dimensional electro-thermal-defect benchmark, not a full phase-field
solution.

### Thermal And Differentiable Surrogate Modeling

Li et al. 2026, "Composable neural emulators for thermoelectric generator
design and system-level optimization", supports differentiable thermal/electrical
surrogate design. It is useful background for future system-level mapping, which
is deferred.

## Secondary Or Deferred References

- Gao 2025 electromagnetic PINN: background for complex physical operators, not
  current scope.
- Luo 2026 GaN HEMT scalable PINN: background for device-scale PINNs, not
  current scope.
- Tang 2023 lumped kinetic PINN: background for reduced kinetics and parameter
  inference.
- Optical inverse-design PINN and quantum GAN inverse-design notes: not central
  to the current `gamma_sub` route.
- NeuroPINN or NeuroSPICE references: possible future extension, not current
  scope.

## Claim Boundary

These references support synthetic benchmark method design and constrained
inverse-problem motivation. They do not validate the current data as measured
device data.
