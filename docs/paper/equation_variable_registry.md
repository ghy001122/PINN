# Equation Variable Registry

## Scope

This registry summarizes the equations used in the one-dimensional synthetic
numerical digital-twin benchmark. Values are literature-guided or engineering
priors, not measured material parameters.

## Domain And Variables

| Symbol | Unit | Meaning | Role |
| --- | --- | --- | --- |
| `x` | m | Effective one-dimensional coordinate | Spatial coordinate |
| `t` | s | Time | Temporal coordinate |
| `L_eff` | m | Effective active thickness | Domain length |
| `V_app(t)` | V | Applied terminal voltage | Input protocol |
| `I(t)` | A | Terminal current | Port output |
| `G(t)` | S | Terminal conductance | Port output and inverse target observable |
| `c_v(x,t)` | dimensionless | Effective vacancy/defect state | Hidden field |
| `T(x,t)` | K | Temperature | Hidden field |
| `m(x,t)` | dimensionless | Conductive-state fraction in `[0,1]` | Hidden field |
| `sigma(x,t)` | S m^-1 | Effective conductivity | Hidden field and port closure |
| `gamma_sub` | W m^-3 K^-1 | Effective volumetric heat loss | Reduced inverse target |
| `T_sw` | K | Switching midpoint temperature | Confounder/prior |
| `tau_m` | s | Conductive-state relaxation time | Confounder/prior |
| `eta_A` | dimensionless | Effective active-area factor | Confounder/prior |

## Electrical Port Closure

`R_area = sum_i dx / sigma_i`

`J = V_app(t) / R_area`

`E_i = J / sigma_i`

`A_eff = eta_A A_contact`

`I(t) = A_eff J`

`G(t) = I(t) / (V_app(t) + eps_V)`

Physical meaning: the electrical model is a quasi-static one-dimensional series
resistor closure used to map hidden conductivity fields to measurable port
signals.

## Heat Equation

`q_T = -k_th dT/dx`

`rho Cp dT/dt = -d q_T/dx + J E - gamma_sub (T - T0)`

Physical meaning: `gamma_sub` captures effective substrate/environment thermal
loss in the reduced one-dimensional heat balance.

## Defect Transport

`F_v = -D_v(T) d c_v/dx + mu_v(T) c_v (1 - c_v) E`

`d c_v/dt = -d F_v/dx - k_r(T) (c_v - c_v0)`

Physical meaning: `c_v` is an effective hidden defect state used for controlled
synthetic dynamics, not a measured atomistic vacancy map.

## Conductive-State Dynamics

`d m/dt = (m_eq(T,c_v) - m) / tau_m`

`m_eq = 1 / (1 + exp(-(T - T_sw + alpha_c (c_v - c_v0)) / dT_sw))`

Physical meaning: `m` captures a coarse switching fraction that couples thermal
and defect states to conductivity.

## Conductivity Closure

`sigma = exp((1 - m) log(sigma_off) + m log(sigma_on))`

`sigma_off = sigma_off0 exp[-E_off/k_B (1/T - 1/T0)] exp[beta_off (c_v - c_v0)]`

`sigma_on = sigma_on0 exp[beta_on (c_v - c_v0)]`

Physical meaning: conductivity is a reduced closure tying `T`, `c_v`, and `m`
to the terminal response. It is adequate for synthetic identifiability tests,
not a complete transport model.

## Boundary Conditions

Defect and thermal no-flux boundaries are used in the Ground Truth solver:

`F_v(0,t) = F_v(L_eff,t) = 0`

`q_T(0,t) = q_T(L_eff,t) = 0`

## Claim Boundary

These equations support a synthetic numerical digital-twin benchmark for method
development. They do not establish measured device parameters or full-field
experimental recovery.
## F-SPS-PINN V2 Closure Note

The v2 method-development path also includes a white-box VO2-like closure `vo2_sigma(T, c_v, m)` and an optional Fourier-pyramid feature embedding. In the current manuscript evidence chain, these are appendix or future-work method components. They should not be presented as the primary validated conductivity law for the frozen Ground Truth v1.1 benchmark, and they should not be used to claim performance superiority from the small-run v2 checks.