# Claim-Gated Innovation Portfolio

## Current Disposition

The selected package is `GeoPhase-OQ-PINN`. The portfolio is ordered by
dependency, not by how attractive an acronym sounds. Only G0/E0 is currently
active; every neural or inverse claim remains `forbidden` until its upstream
gate passes.

The frozen 1D and constrained `gamma_sub` results remain historical baselines.
They motivate target reduction but do not satisfy the user's requirement for a
positive PINN contribution on a two-dimensional-or-higher structure.

## Mandatory Physical Foundation

### 1. Real x-y geometry plus passive K-state vertical thermal memory

- **Problem:** an x-z slice misses finite width/current crowding, while full 3D
  is too costly and previously failed numerical contracts.
- **Substantive delta:** resolve the Qiu-inspired device plane and collapse only
  the vertical thermal direction into a positive/passive dynamical reduction.
- **Gate:** manufactured, current, energy, mesh/time, K-order, and limit checks
  in `configs/geophase_e0_2p5d_reference.yaml`.
- **Failure:** block all GeoPhase training; do not replace convergence with a
  conservation-only claim.
- **Status:** active foundation; result not yet available.

## Primary Neural Contributions After E0

### 2. Transition-localized spectral mixture of experts

- **Problem:** smooth MLPs under-resolve sharp transition manifolds, while
  global Fourier encodings can pollute smooth regions.
- **Method:** smooth, spectral, and interface/port experts; activate spectral
  capacity only near the predicted phase-transition manifold using temperature,
  branch, field, SDF, and residual features.
- **Nearest-prior boundary:** Fourier/SIREN, domain decomposition, and region
  optimization are prior art; novelty can lie only in the physical allocation,
  not the existence of Fourier features or experts.
- **Gate:** at least 20% sharp-window error reduction, no smooth-region
  regression, and higher fixed-seed success rate under matched budgets.
- **Status:** primary candidate; `forbidden` as a result.

### 3. Phase-sharpness x electrothermal-feedback homotopy

- **Problem:** narrow transition width and Joule positive feedback create two
  coupled stiffness axes.
- **Method:** jointly decrease transition width and increase Joule coupling,
  inheriting weights between locked stages.
- **Nearest-prior boundary:** ordinary continuation and Seiler-style STL are
  prior art. Without the full multi-head/head-transfer experiment, call this
  physics-based homotopy, not STL reproduction.
- **Gate:** matched-budget, multi-seed gain over direct training, width-only
  continuation, and Joule-only continuation without ledger regression.
- **Status:** primary low-cost algorithm candidate; `forbidden` as a result.

### 4. Dual-discretization hybrid PINN insurance

- **Problem:** a one-month research constraint makes a data-free-only route too
  brittle.
- **Method:** combine physical residuals, port observations, and explicitly
  sparse solver field anchors; keep solver discretization distinct and test on
  unseen grids/geometries/protocols.
- **Boundary:** name it `hybrid PINN`; compare against data-free PINN and pure
  surrogate at matched labels and compute.
- **Gate:** positive field/port/event/ledger and geometry holdout performance.
- **Status:** authorized only after E0 and as a declared identity, not a hidden
  fallback.

## Inverse Contribution After Forward Fidelity

### 5. Event-canonicalized observation quotient

- **Problem:** terminal observations identify protocol/branch-dependent
  parameter combinations rather than a unique raw parameter vector.
- **Method:** align switch events, converge solver Jacobians, compute SVD
  subspaces, recover only supported quotient coordinates, and report the
  remaining parameter set/null directions.
- **Falsifiable hypothesis:** protocol/branch subspaces show stable rank change
  or rotation and combined protocols shrink the null-space intersection.
- **Downgrade:** if no stable rotation exists, retain a fixed low-rank quotient;
  do not manufacture a dynamic-quotient story.
- **Status:** highest scientific upside; blocked by E0 and forward fidelity.

### 6. PINN--solver sensitivity fidelity plus refusal

- **Problem:** accurate trajectories can carry wrong parameter derivatives.
- **Method:** match Jacobians or leading projectors on sparse solver probes and
  train refusal on non-identifiable/missing-physics cases.
- **Gate:** maximum leading-subspace angle <=15 degrees, consistent protocol
  ranking, fresh-case quotient error <=10%, refusal AUPRC >=0.80.
- **Failure:** restrict the network to forward use.
- **Status:** inverse hard gate; not a standalone acronym.

## Auxiliary Contribution

### 7. Material-specific composable physics kernels

- **Shared:** geometry/protocol encoding, thermal-memory interface, port/RC
  layer, training, sensitivity, and refusal workflow.
- **Separated:** VO2 IMT/hysteresis and SnSe/NbO2 Poole--Frenkel/thermal-runaway
  kernels, state meanings, thresholds, and parameters.
- **Allowed claim:** cross-model numerical validation of a reusable workflow.
- **Forbidden:** zero-shot material generalization or shared material truth.
- **Status:** G5 only after the VO2 forward/generalization route is dispositioned.

## Required Baselines

Independent FVM/implicit solver; vanilla PINN; global Fourier PINN;
domain-decomposed PINN/FBPINN-lite; hybrid PINN without proposed modules; pure
MLP/TCN surrogate; direct solver plus profile/LM/CMA-ES inverse; old 1D
`gamma_sub` inverse. Each comparison locks data, cases, seeds, stopping rules,
and compute.

## Deferred Or Stopped

- full STL reproduction: appendix MVE only if the main method is already secure;
- transition-localized discrepancy: only with an external or declared
  missing-physics holdout;
- counterfactual ambiguity and active protocol optimization: only after stable
  quotient geometry is observed;
- M44 repair, full 3D, full Landau, full LLP/minor-loop reproduction,
  NeuroPINN/VSN/QGAN, full multilevel FBPINN, VO2 vacancy PDE, and terminal-only
  full-field recovery: stopped for the current route.

## Manuscript Route Selection

- **Strong:** G0-G4 pass -> GeoPhase-OQ-PINN.
- **Robust:** G0-G3 pass, quotient fixed/limited -> GeoPhase-PINN.
- **Hybrid minimum:** data-free fails but declared hybrid G1-G3 passes -> hybrid
  geometry-aware physics-informed learning.
- **Stop:** no positive PINN forward/generalization route passes -> retain the
  negative evidence; do not submit a false positive neural-method paper.
