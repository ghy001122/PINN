# Model Hierarchy And Claim Boundary

## Scope Boundary

This project uses a one-dimensional reduced-order synthetic numerical
digital-twin benchmark for sparse-port inverse identifiability and constrained
`gamma_sub` inversion. It is not experimental data, not a full three-dimensional
device simulation, and not a proof of sparse-port full-field recovery.

## Model Hierarchy

| Layer | Included physics | Representative equation or relation | Excluded physics | Why adequate for current claim |
| --- | --- | --- | --- | --- |
| Terminal electrical response | One-dimensional quasi-static series conduction | `R_area = sum_i dx / sigma_i`, `J = V_app / R_area`, `I = A_eff J`, `G = I / (V_app + eps_V)` | Full Maxwell equations, contact microgeometry, stochastic filament branching | Adequate for testing whether sparse port `V/I/G` constrains an effective reduced parameter |
| Heat transport | One-dimensional heat diffusion, Joule heating, effective substrate cooling | `rho Cp dT/dt = -dq_T/dx + J E - gamma_sub (T - T0)` | 3D heat spreading, detailed electrode heat sinks, radiation, convection | Adequate for defining an identifiable effective heat-loss parameter `gamma_sub` |
| Defect transport | Effective vacancy concentration with drift, diffusion, and relaxation | `dc_v/dt = -dF_v/dx - k_r(T)(c_v - c_v0)` | Atomistic chemistry, phase separation, grain boundaries, stochastic defect creation | Adequate as a controlled hidden-field benchmark, not as a measured microscopic model |
| Conductive-state switching | Relaxation toward a temperature/defect-dependent equilibrium state | `dm/dt = (m_eq(T,c_v) - m) / tau_m` | Explicit nucleation, filament rupture, crystallographic phase fronts | Adequate for synthetic hysteresis and confounding analysis |
| Conductivity closure | Mixed off/on conductivity depending on `T`, `c_v`, and `m` | `sigma = exp((1-m) log sigma_off + m log sigma_on)` | Full band transport, tunneling, Schottky barriers, percolation networks | Adequate for port-level conductance and reduced inverse stress tests |
| Reduced inverse target | Single primary parameter `gamma_sub` under fixed or bounded priors | minimize port `G/I` loss plus candidate heat residual | Unconstrained joint inversion of all material and hidden-field parameters | Adequate for a methods paper claim only if priors are stated explicitly |

## Allowed Claims

- The benchmark is a synthetic numerical digital-twin testbed.
- Sparse terminal observations can constrain the integrated conductance response.
- Port-only full hidden-field inversion is ill-posed in the current setup.
- Under fixed or tightly bounded switching/conductivity priors, `gamma_sub` can
  be studied as a reduced inverse target.
- `T_sw` is a dominant confounder that limits the robustness of `gamma_sub`
  inversion.

## Forbidden Claims

- The generated data are measured experimental data.
- The model is a complete three-dimensional device simulation.
- Sparse port observations uniquely recover `delta_T`, `c_v`, `m`, and `sigma`.
- The recovered `gamma_sub` is a measured material parameter for a fabricated
  device.
- The current constrained inversion proves unconstrained multi-parameter
  identifiability.

## Paper Positioning

The defensible manuscript framing is a method-oriented SCI small paper on a
one-dimensional reduced-order digital-twin benchmark for sparse-port inverse
identifiability and constrained effective thermal-parameter inversion.