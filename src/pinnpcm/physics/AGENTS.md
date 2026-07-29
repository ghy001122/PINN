# Physics Subtree Rules

These rules extend the root `AGENTS.md` for `src/pinnpcm/physics/`.

- Use SI units in equations, code, configs, tests, and outputs.
- Route VO2, NbO2, SnSe, V2O5, and Nb2O5 through material-appropriate mechanisms; do not reuse a state variable or transition temperature across families without evidence.
- Keep electrical and thermal topologies explicit. Substrate may be thermal-only; do not create electrical bypasses to simplify numerics.
- Enforce boundary, interface, current, heat-flux, and energy conservation with independently computed residuals; algebraic self-cancellation is not validation.
- Record parameter and equation provenance. Label engineering priors and ranges as such; never call them measurements.
- Map every claim-bearing 2D/2.5D model one-to-one to the source device: literature structure, physical dimensions, material regions, electrode locations, coordinate system, boundary conditions, and simulation domain. A schematic alone is insufficient.
- Geometry comparators use SI-valued physical coordinates. Normalized coordinates may be network inputs but cannot replace physical film-thickness, spacing, or substrate-depth evidence.
- With only device-level `G_theta` and `C_theta`, use the identifiable single-RC/S2 baseline. Upgrade to K-state or diffusive memory only with independent transient evidence or a validated higher-order reference. Never relabel device/interface/electrode/substrate effective quantities as intrinsic VO2 properties.
- Without microscopy, state `s` means only an effective conductive-state coordinate or hysteresis internal variable, never a measured metallic-phase volume fraction.
- Maintain a variable-to-code contract giving definition, SI unit, scope, initial/boundary/interface conditions, and code name; cover dimensional, sign, and analytic/limit checks.
- Prefer a white-box material kernel. Do not freely predict state, defects, conductivity, and all hidden fields simultaneously and rely on losses alone to create physical meaning.
- Put parameters in `params.py` or YAML. No opaque physical constants in solver bodies.
- Any equation change must update `docs/method_equations.md`, relevant configs, and behavior/conservation tests in the same task.
- Frozen GT equations and defaults remain read-only outside an explicit revision.
