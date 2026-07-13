# PINN Subtree Rules

These rules extend the root `AGENTS.md` for `src/pinnpcm/pinn/`.

- A temporal or spatial smoothness term is not a PDE residual. Every physics residual must trace to a documented equation, variables, units, scaling, and boundary/interface condition.
- Prevent target leakage: targets, simulator fields, target statistics, and holdout bases may not enter inputs or constitutive closures unless declared as anchors or ablations.
- Keep local layer coordinates, global coordinates, and hard-BC transforms consistent and test their boundary values.
- Distinguish data-free PINN, sparse-anchor PINN, field-anchored physics-regularized surrogate, and smoke/preflight paths in names and reports.
- Finite loss, backward success, or loss decrease is not scientific success. Use the active P1 and stiffness claim gates.
- Compare architectures with matched data, seeds, epochs/evaluations, stopping rules, and compute budgets.
- Dynamic loss gates must be checked for collapse; Fourier/F-SPS/STL claims require cross-regime and multi-seed evidence.
- Preserve failed seeds and block-wise metrics; do not aggregate away a failing physical field or interface residual.
