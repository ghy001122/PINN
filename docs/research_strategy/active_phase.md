# Active Phase

## Current Phase

`literature-backed constrained gamma_sub inversion completed`

The constrained reduced inverse-problem stage has been executed for the frozen
Ground Truth v1.1 triangle benchmark. The next step is not automatic method
expansion; it requires an explicit user request to start gamma_sub-PINN or any
other method enhancement.

## Why This Phase Is Active

The completed identifiability, confounding, and constrained-inversion audits
show:

- port-only full hidden-field inversion is ill-posed for `delta_T`, `c_v`, `m`,
  and `sigma`;
- `gamma_sub` is identifiable in nominal fixed-prior cases;
- `T_sw` is the limiting confounder and can destabilize `gamma_sub` inversion
  even under narrow prior-width stress tests;
- any paper claim must remain a constrained reduced inverse claim on a synthetic
  numerical digital-twin benchmark.

## Allowed Work

- inspect and document the constrained `gamma_sub` inversion evidence;
- maintain the prior registry and literature evidence chain;
- update project state, registries, and reproducibility notes;
- prepare a clearly scoped next task only when the user explicitly requests it;
- keep all claims synthetic, numerical, and digital-twin benchmark only.

## Not Allowed In This Phase

Do not start these workstreams unless this file is updated by an explicit user
request:

- F-Pyramid or other multi-resolution architecture work;
- stiff transfer learning or continuation training;
- observability-augmented sparse temperature or state measurements;
- NeuroSPICE, NeuroPINN, VSN, or system-level mapping;
- unconstrained full hidden-field recovery claims.

## Frozen Boundary

Do not modify frozen Ground Truth v1.1 configs, data, metrics, report, default
parameters, or equations during this phase.
