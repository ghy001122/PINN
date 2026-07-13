# Physics Subtree Rules

These rules extend the root `AGENTS.md` for `src/pinnpcm/physics/`.

- Use SI units in equations, code, configs, tests, and outputs.
- Route VO2, NbO2, SnSe, V2O5, and Nb2O5 through material-appropriate mechanisms; do not reuse a state variable or transition temperature across families without evidence.
- Keep electrical and thermal topologies explicit. Substrate may be thermal-only; do not create electrical bypasses to simplify numerics.
- Enforce boundary, interface, current, heat-flux, and energy conservation with independently computed residuals; algebraic self-cancellation is not validation.
- Record parameter and equation provenance. Label engineering priors and ranges as such; never call them measurements.
- Put parameters in `params.py` or YAML. No opaque physical constants in solver bodies.
- Any equation change must update `docs/method_equations.md`, relevant configs, and behavior/conservation tests in the same task.
- Frozen GT equations and defaults remain read-only outside an explicit revision.
