# Next Actions

## Authoritative Current Queue

Exactly one bottleneck is active: `N0_CV_LEDGER_REFORMULATION_PREFLIGHT`.

### Priority N0-CV: solver-consistent residual preflight — active

N0-R is closed as `failed_but_informative`. The v1 sign mismatch and finite-band interface proxy were repaired, but the data-free split model still fails global current/energy, defect/thermal residual, field, and port gates. Do not tune the completed branch.

The only next action is a new no-training preflight and preregistration for one solver-consistent control-volume/weak-form N0 MVE. It must:

1. reuse fixed diagnostic point content SHA `80e34ca549d86588d12ffbcde4a304e378197dba602bcccc6e4e7d1ead932731`;
2. express frozen arithmetic face-flux semantics and the declared-interface offset explicitly;
3. put terminal-current, defect-mass, and global-energy ledgers in the residual contract, not only post-training diagnostics;
4. retain the same state network, physical conductivity closure, score-only hidden fields, seeds, budgets, and unchanged gates;
5. remain a numerical consistency repair, not cPINN/XPINN/interface novelty.

Do not train that formulation until its config and equation/scale registry are locked. The unchanged final success gate remains 2/3 fixed seeds plus all port, residual, field, interface, current, energy, state-bound, and frozen-hash gates.

### D0 — held at D0a failure boundary

Author/SI semantics are reproducible, but time-step convergence failed. D0b-D0d are not authorized by the current evidence. Before revisiting D0, preregister a stable integration-policy audit that does not tune against public trajectories. The 13 V numerical members remain sealed.

### N1-N3 — blocked

- N1 independent solver sensitivity: blocked until N0 passes.
- N2 PINN sensitivity fidelity: blocked until N1 and N0 pass.
- N3 conditional quotient inverse: blocked until D0c/D0d, N1 and N2 pass.
- Solver-first SC-LOS: blocked because N0-R failed current/energy and held-out residual gates.

### Preserved manuscript path

Retain the existing calibration-gated constrained `gamma_sub` rank-1 result as the safe inverse evidence. Add D0a and N0 as explicit numerical/reviewer-defense limitations. Do not relabel them as validation or successful full-PINN evidence.

## Non-negotiable Boundaries

No frozen-GT edits, 13 V access without a valid fit lock, post-hoc gate relaxation, hidden seeds, synthetic-as-experimental wording, source-paper reproduction as repository validation, or PINN/solver attribution mixing. P1 remains a prerequisite only if a multidomain, two-dimensional, face-flux, or interface-innovation claim is activated.
