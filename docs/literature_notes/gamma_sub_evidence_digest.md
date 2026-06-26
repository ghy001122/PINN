# gamma_sub Evidence Digest

This digest records the reduced inverse-problem rationale for `gamma_sub`.

## Why gamma_sub Became The Reduced Target

The v0/v1/v1.1 inverse PINN work showed that terminal observations can match
conductance-level response while hidden fields remain non-unique. The
identifiability audit confirmed that terminal `G(t)` is strongly tied to
aggregate conductivity but cannot uniquely decompose `delta_T`, `c_v`, `m`, and
`sigma`.

The reduced route is therefore to invert an effective thermal dissipation
parameter, `gamma_sub`, while keeping the micro-kinetic defect and switching
parameters constrained by literature-guided or engineering priors.

## Existing Numerical Evidence

- The `gamma_sub` identifiability audit found stable single-parameter recovery
  when `D_v0`, `mu_v0`, `T_sw`, `tau_m`, and related parameters were fixed.
- The confounding audit found that `T_sw` can be more locally sensitive than
  `gamma_sub`, while `sigma_on0` and `tau_m` can produce response shapes close
  to `gamma_sub`.
- Mismatched synthetic targets can produce systematic bias if `gamma_sub` is
  inverted while confounders are held at incorrect nominal values.

## Current Working Hypothesis

`gamma_sub` can remain a useful paper-level reduced inverse target only under
explicit prior constraints on:

- `T_sw`
- `tau_m`
- `sigma_on0`
- `eta_A`
- defect transport parameters such as `D_v0` and `mu_v0`

## Literature-Prior Role

The next method step should not claim unconstrained identifiability. It should
test relative error versus confounder prior width and noise level, then state
the narrow conditions under which `gamma_sub` is recoverable.

## Synthetic Benchmark Boundary

All evidence in the current repository is synthetic numerical digital-twin
benchmark evidence. It is not experimental validation of thermal dissipation in
a fabricated device.
