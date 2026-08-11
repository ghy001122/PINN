# PINN Subtree Rules

These rules extend the root `AGENTS.md` for `src/pinnpcm/pinn/`.

- A temporal or spatial smoothness term is not a PDE residual. Every physics residual must trace to a documented equation, variables, units, scaling, and boundary/interface condition.
- Prevent target leakage: targets, simulator fields, target statistics, and holdout bases may not enter inputs or constitutive closures unless declared as anchors or ablations.
- For multistable problems, use deployable protocol or history metadata. Never average distinct roots into a single target or expose internal `root_id`, cold/hot initialization labels, or other solver-only selectors as model inputs. Evaluate ambiguity detection, false-unique rate, candidate-set coverage, set size, and refusal as separate capabilities.
- Keep local layer coordinates, global coordinates, and hard-BC transforms consistent and test their boundary values.
- Distinguish data-free PINN, sparse-anchor PINN, field-anchored physics-regularized surrogate, and smoke/preflight paths in names and reports.
- Finite loss, backward success, or loss decrease is not scientific success. Use the applicable active-phase and stiffness claim gates.
- A direct-solver/profile success, including constrained `gamma_sub`, is a baseline result and never a PINN result. Only an actually trained PINN that passes its frozen metrics can support a positive PINN claim.
- Do not add epochs to mask structural failure from non-identifiability, wrong boundary conditions, wrong constitutive physics, or solver--PINN sensitivity mismatch. Repair the structure or stop under the preregistered rescue budget.
- Compare architectures with matched data, seeds, epochs/evaluations, stopping rules, and compute budgets.
- Formal comparisons include the independent solver, vanilla PINN, pure supervised surrogate, and the strongest applicable simple non-neural baseline such as an analytic map, linear/ridge-POD model, or conservative solver projection; inverse comparisons also include direct solver/profile methods. Match data, collocation, hyperparameter-search, and approximate wall-clock/GPU budgets, and disclose parameter-count differences. A network participating in the computation is not by itself evidence of neural-specific value.
- Ground Truth and PINN must use different discretization expressions. Use case-, geometry-, protocol-, or regime-level holdouts, never random adjacent space-time points. Derive bases, normalization, thresholds, and refusal rules only from training/calibration data; include noise, time jitter, port bias, parameter drift, and model-missing stress tests where the contract requires them.
- Before an inverse neural head or terminal-only recovery claim, establish solver-side identifiability with converged Jacobian/SVD, profile, or finite-perturbation evidence, then freeze the observable target, observation protocol, and refusal contract.
- Claim-bearing ablations remove one core module at a time. Unless a preregistered contract states a justified exception, formal main results use at least five seeds and report median, IQR, 95th percentile, failure rate, and worst case.
- Dynamic loss gates must be checked for collapse; Fourier/F-SPS/STL claims require cross-regime and multi-seed evidence.
- Preserve failed seeds and block-wise metrics; do not aggregate away a failing physical field or interface residual.
