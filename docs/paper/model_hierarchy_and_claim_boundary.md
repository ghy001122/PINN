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

## Mandatory Full-PINN Scaffold And Current Boundary

The latest project requirement makes a complete physics-informed neural network an indispensable architecture and manuscript scaffold. The versioned N0 path predicts `phi`, `c_v`, `T`, and `m`; derives conductivity from these states; evaluates electrostatic, defect, heat, and phase residuals; enforces IC/BC; and derives terminal current through the series-resistance observation operator.

This architectural fact does not upgrade the scientific claim. Earlier N0 paths fail the port and residual gates; the v3r Adam-1200 state passes the port narrowly but still fails residual, field, interface-flux, and conservation-ledger gates, with five metrics above the locked `20x` stop threshold. Trained full-PINN evidence, sensitivity fidelity, and inverse recovery therefore remain `forbidden`. Historical lightweight PINNs remain explicitly separate baselines. P1 remains a gate only for a newly activated multidomain, 2D, face-flux, or interface-innovation claim.

The public VO2 compact model is a separate hierarchy layer and realism anchor. Its data and parameters do not become frozen-GT measurements, and solver-generated source reproduction is never labeled PINN output.

## Evidence-Triggered Physical Upgrade Ladder

| Level | Model responsibility | Activation evidence | Required gate before any claim | Current disposition |
| --- | --- | --- | --- | --- |
| H0 | Current 1D electrothermal/defect/phase model with explicit port operator and complete multidomain PINN scaffold | Frozen GT v1.1 and current locked synthetic protocol | Existing conservation, units, independent-solver, and claim gates | Active hierarchy; reduced `gamma_sub` inverse is `qualified_supported`, trained full PINN is not |
| H1 | Add enthalpy/latent-heat physics | Provenance-backed external thermal residual that H0 cannot explain within locked uncertainty | Conservation derivation, SI dimensional check, primary phase-change literature, independent-solver convergence, and held-out thermal improvement `>=20%` | Inactive registry hypothesis; no qualifying thermal residual exists |
| H2 | Add explicit branch/history state beyond H0 | Provenance-backed heating/cooling or minor-loop discrepancy | Explicit history update, units/state bounds, primary VO2 hysteresis literature, independent-solver event checks, and held-out minor-loop improvement `>=20%` | Inactive registry hypothesis; required branch-resolved data are absent |
| H3 | Enter 2D geometry or interface innovation | Demonstrated 1D structural model error that cannot be resolved within H0-H2 | Conserved face/interface derivation, dimensional audit, manufactured interface tests, global ledgers, and independent 2D solver | `forbidden` as an active claim; no proven 1D structural-error trigger |

No new physical term may be added merely to improve fit. Every upgrade requires a conservation derivation, dimensional check, primary literature, and an independent numerical-solver test before it can enter the PINN loss. The complete PINN architecture remains the unifying scaffold even while its positive trained claims are blocked.

The CPCF pilot does not add a hierarchy level. Its normalized resource index has no monetary semantics, and failed anchor/improvement/bootstrap gates restrict it to a supplementary rejection table.

## F-SPS-PINN Placement

F-SPS-PINN architecture MVP, v2 smoke training, v2 small-run baseline, v2 phase-transition stress preflight, and v2 Fourier on/off ablation are engineering evidence for possible future method development. They should be placed in appendix, discussion, or future-work material for the current manuscript.

Current F-SPS-PINN evidence does not justify a main-text performance-superiority claim. It also does not replace the constrained `gamma_sub` reduced inverse line as the most defensible current paper contribution.
