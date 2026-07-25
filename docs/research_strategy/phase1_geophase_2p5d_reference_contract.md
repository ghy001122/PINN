# Phase 1 GeoPhase 2.5D Reference-Solver Contract

## Identity

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`
- Status: `authorized_pending_implementation`
- Manuscript use: independent truth and conservation judge for later R1/R2 work
- Evidence type after execution: literature-guided solver-generated synthetic numerical digital-twin evidence
- Threshold authority: `configs/geophase_phase1_2p5d_reference.yaml`
- Stage routing: `configs/geo2p5d_stage.yaml`

This contract narrows Phase 1 of the full execution guide. It does not duplicate or replace the guide and it records no solver result.

## Model Boundary

Resolve the Qiu-inspired coplanar device in the real x-y plane. Represent vertical heat transport by a passive K-state areal thermal memory fitted and verified against an independent higher-order 1D multilayer diffusion reference. Use finite contacts, terminal boundary integrals, a white-box VO2 conductive-state/hysteresis closure, external load/parallel-capacitance dynamics, and an active-plane plus K-state energy ledger.

Geometry and source facts are literature anchored where documented. Contact overlap, local material properties, closure time scales, and reduction choices remain engineering priors unless provenance explicitly says otherwise. The model is not a calibrated Qiu device, author-code reproduction, full 3D model, or experimental validation.

## Independence Contract

The reference implementation must use conservative cell-centered finite volumes and implicit time integration. Its discrete residual, flux reconstruction, nonlinear solve, and ledger computation must not call or reuse the later PINN residual implementation. Fixed physical comparison grids are required for mesh/time refinement. Shared continuous equations and parameter YAML are allowed; shared discrete residual code is not.

## Required Responsibilities

Implementation may add responsibility-based modules only when real behavior is implemented:

- `src/pinnpcm/physics/`: material kernels, source-traceable parameters, geometry, interfaces, and continuous ledgers.
- `src/pinnpcm/solvers/`: independent FVM assembly, implicit stepping, nonlinear convergence, port integration, and refinement comparison.
- `src/pinnpcm/evaluation/`: gate metrics and machine-readable summaries.
- `scripts/`: one config-driven CLI with deterministic CPU smoke/formal modes.
- `tests/`: manufactured, conservation, units, passivity, limits, and failure-path behavior.

Do not create empty `inverse/`, solver, or evaluation placeholders merely to match the eventual architecture.

## Verification Gate

All configured gates vote together:

1. manufactured electrical linear-field and thermal source/diffusion cases;
2. terminal-current imbalance;
3. active-plane and full plane-plus-memory energy ledgers;
4. independent spatial and temporal fine-pair convergence;
5. positive K-state capacities/conductances, stable real poles, passivity, and step/impulse/frequency alignment to the higher-order reference;
6. zero-drive, uniform-conductivity, zero-coupling, decoupled dual-device, and symmetric dual-device limits;
7. nonfinite nonlinear solve, negative-passivity, ledger tamper, and coordinate swap fail closed;
8. literature-trend sanity inside the declared envelope.

Finite output, current balance alone, or a smaller source envelope below discretization error cannot pass Phase 1.

## Execution And Output Contract

Use the config's single formal execution limit, CPU and wall-clock budget, fixed parameters, refinement levels, and output paths. Development uses smoke/focused tests. The formal run writes JSON/CSV before figures/tables and a report. It may not train a PINN, fit parameters, run inverse work, digitize new literature curves, modify frozen GT, repair M44, execute NbO2, or expand to full 3D.

## Disposition

- Pass: lock the evidence, update the claim matrix with the narrowly supported synthetic reference statement, and activate Phase 2 dataset/split design.
- Fail: preserve all artifacts as `failed_but_informative`, block Phase 2 and R1-R3, and propose one bounded repair or reduction-rejection decision.
- Budget overrun or ambiguous source semantics: stop and request the authority required by `AGENTS.md`.

## Claim Wording

Allowed after a complete pass only: a literature-guided synthetic 2.5D reference benchmark passed its preregistered numerical, conservation, convergence, passivity, and limit gates.

Forbidden: Qiu calibration or exact reproduction, measured-device agreement, full 3D/FEM validation, successful R1/R2, observation-quotient recovery, PINN sensitivity fidelity, arbitrary terminal-only hidden-field recovery, or cross-material generalization.
