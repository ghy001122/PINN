# Active Phase

## Current Phase

`literature-backed constrained gamma_sub inversion preparation`

The active objective is to prepare the next reduced inverse-problem stage:
constrained inversion of the effective heat-dissipation parameter `gamma_sub`
under literature-guided priors for confounding parameters.

## Why This Phase Is Active

The completed identifiability and confounding audits show:

- port-only full hidden-field inversion is ill-posed for `delta_T`, `c_v`, `m`,
  and `sigma`;
- `gamma_sub` is conditionally identifiable when micro-kinetic parameters are
  fixed;
- `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are confounders that must be
  bounded by priors before making a reduced inverse-problem claim.

## Allowed Work

- integrate and maintain low-token context documents;
- prepare literature-backed prior tables and evidence chains;
- implement constrained `gamma_sub` inversion only when explicitly requested;
- update project state, registries, and reproducibility notes;
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
