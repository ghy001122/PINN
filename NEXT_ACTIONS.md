# Next Actions

## Authoritative Current Queue

Exactly one bottleneck is active:
`Q2_GEOPHASE_E0_REFERENCE_SOLVER_FOUNDATION`.

The revised paper requires a positive PINN method on a source-traceable 2.5D
phase-transition-device benchmark. The constrained `gamma_sub` result remains
a historical baseline, not the active manuscript core.

### Priority - G0/E0 independent 2.5D judge

Manuscript use: create the trustworthy numerical reference and conservation
contract without which no GeoPhase field, architecture, generalization, or
inverse claim can be scored.

Execution order:

1. validate `configs/geophase_e0_2p5d_reference.yaml` and the active equations,
   units, x-y coordinates, Qiu/engineering-prior split, branch closure,
   boundary conditions, K-state passivity, and output schema;
2. implement `src/pinnpcm/physics/geophase_2p5d.py` and an independent
   `src/pinnpcm/solvers/geophase_2p5d_fvm.py`; do not reuse PINN residual code
   as the reference judge;
3. add CPU tests for manufactured electrical/thermal solutions, port-current
   conservation, energy accounting, zero-drive/uniform limits, K-state
   passivity and reduction, coordinate/contact semantics, and failure paths;
4. run smoke/preflight cases and inspect convergence before consuming the one
   formal E0 run;
5. execute the bounded formal grid/time/K-order/single-dual-device matrix and
   write JSON/CSV, figures, report, claim-matrix update, and E1 go/no-go.

All configured E0 gates must pass. Conservation without independent mesh/time
convergence is not sufficient. If a physics, topology, coordinate, or ledger
defect appears, repair the foundation before the formal run. If a valid formal
gate fails, preserve `failed_but_informative` evidence and do not train E1.

### Locked downstream order

Only after E0 passes:

1. G1: complete/hybrid GeoPhase forward PINN;
2. G2: transition-localized spectral experts plus phase/Joule homotopy with
   vanilla, global-Fourier, continuation, domain-decomposition, and pure-
   surrogate baselines;
3. G3: held-out within-family geometry/protocol generalization;
4. G4: solver-first event-canonicalized quotient geometry, PINN sensitivity
   fidelity, fresh-case inverse, and refusal;
5. G5: Chen-inspired SnSe/NbO2 material-kernel replacement and cross-model
   numerical trend validation;
6. manuscript route selection from passed evidence.

### Current E0 execution boundary

- During E0, no M44 repair, old 1D retraining, full 3D, full
  Landau/phase-field, oxygen-vacancy PDE, or terminal-only full-field program.
  Directions outside G0--G5 require a separately activated future phase; they
  are not globally prohibited research topics.
- No GeoPhase training, GPU rental, inverse head, literature-curve refit, or
  NbO2 run before E0 passes and the next phase is explicitly activated.
- No free `log_sigma`, no shared VO2/NbO2 constitutive parameters, no best-seed
  reporting without failures, and no port-only success criterion.
- No claim of exact Qiu reproduction, experimental validation, full STL,
  universal Fourier superiority, world-first novelty, or zero-shot material
  generalization without direct evidence. `forbidden` is a manuscript claim
  status, not a ban on a later bounded, preregistered audit.
