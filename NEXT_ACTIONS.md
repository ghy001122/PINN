# Next Actions

## Authoritative Current Queue

Exactly one bottleneck is active: `N0_FULL_PINN_NUMERICAL_REPAIR`.

### Priority N0-R: bounded full-PINN convergence diagnosis — active

Keep the frozen GT, full-PINN equations, state variables, physical conductivity closure, seeds, and gates unchanged. Add only diagnostics needed to attribute the failed single-seed MVE:

1. fixed collocation train/evaluation split and per-residual generalization curves;
2. gradient-norm/conflict measurements for `r_phi`, `r_c`, `r_T`, `r_m`, boundary, and interface losses;
3. one-sided bilayer-interface and endpoint-flux residual breakdown;
4. comparison of data-free forward training with a declared sparse-port-anchor ablation, while never using full hidden fields for training;
5. a repair pre-registration before any new training run.

The unchanged success gate is at least 2/3 seeds with port NRMSE95 `<=0.10`, every normalized residual RMS `<=0.01`, finite physical states, and unchanged frozen GT hashes. Failure remains `failed_but_informative` and stops N1-N3.

### D0 — held at D0a failure boundary

Author/SI semantics are reproducible, but time-step convergence failed. D0b-D0d are not authorized by the current evidence. Before revisiting D0, preregister a stable integration-policy audit that does not tune against public trajectories. The 13 V numerical members remain sealed.

### N1-N3 — blocked

- N1 independent solver sensitivity: blocked until N0 passes.
- N2 PINN sensitivity fidelity: blocked until N1 and N0 pass.
- N3 conditional quotient inverse: blocked until D0c/D0d, N1 and N2 pass.

### Preserved manuscript path

Retain the existing calibration-gated constrained `gamma_sub` rank-1 result as the safe inverse evidence. Add D0a and N0 as explicit numerical/reviewer-defense limitations. Do not relabel them as validation or successful full-PINN evidence.

## Non-negotiable Boundaries

No frozen-GT edits, 13 V access without a valid fit lock, post-hoc gate relaxation, hidden seeds, synthetic-as-experimental wording, source-paper reproduction as repository validation, or PINN/solver attribution mixing. P1 remains a prerequisite only if a multidomain, two-dimensional, face-flux, or interface-innovation claim is activated.
