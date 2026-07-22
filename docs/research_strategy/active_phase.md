# Active Phase

Active phase ID: `Q2_M43_FINITE_WIDTH_THERMAL_SPREADING_CLOSURE`

## Objective and manuscript use

Run one bounded thermal-only closure audit required by M42 decision B. The
question is whether finite-source spreading can be represented by a converged,
source-auditable 2.5D thermal impedance/kernel. A pass may support a physically
meaningful reduction boundary; a failure terminates the 2D route and becomes a
reviewer-defense limitation. It cannot validate Qiu dynamics or a PINN.
The constrained `gamma_sub` mainline remains frozen and unchanged.

## Upstream decision

M42 passed its detached hermetic replay (`442 passed`, clean status, external
asset injection) and consumed `22/40` preflight forward calls. Its result is
`failed_but_informative`, decision B:

- source/local resistance error `1.33023`;
- domain sensitivity `0.84235`;
- mesh fine-pair sensitivity `0.13813`;
- time fine-pair sensitivity `0.00886`;
- finite-width/x-z closure error `0.67058`;
- smooth discrete enthalpy ledger `2.58e-14`;
- switching enthalpy unassessed because latent heat is not source-locked.

Thus pure x-z quantitative modeling and formal dynamic GT are not authorized.

## Allowed M43 scope

- analytic/series finite-source spreading benchmark;
- conservative finite-width thermal FVM with registered geometry and material
  priors;
- domain, mesh, time, and boundary-condition convergence;
- separation of spreading, one-dimensional, and contact/interface resistance;
- a bounded comparison to a 2.5D thermal-impedance representation.

Before execution, lock the new budget and thresholds. M42 thresholds may not
be retroactively changed. Use primary spreading-resistance literature only as
an equation/benchmark source, not as device evidence.

## Stop rule

If closure requires unregistered geometry/material values, or independent-
reference/domain/mesh errors remain above the new preregistered limits, select
C, stop all 2D development, and return immediately to manuscript submission.
No second repair round is allowed.

## Forbidden

Qiu parameter fitting or author-code equivalence; M40/M40R rerun; lumped
`Cth/Sth` as local PDE coefficients; unsourced latent heat; active hysteretic
device forward; M41; inverse or PINN; Zhang 13 V; external-validation,
experimental, arbitrary-field, or successful-neural claims.
