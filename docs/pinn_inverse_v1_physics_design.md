# PINN inverse v1 physics design

## Scope

PINN inverse v1 adds lightweight physics regularization to the existing inverse
v0 pipeline on the frozen Ground Truth v1.1 triangle synthetic numerical
digital-twin benchmark. It does not modify Ground Truth v1.1 frozen configs,
frozen data, main equations, acceptance report, or frozen metrics.

The v1 residuals are regularizers for inverse identification. They are not a
complete reproduction of the Ground Truth PDE solver and must not be described
as strict PDE-constrained inverse PINN performance.

## Variables and units

- `x`: device thickness coordinate in m.
- `t`: time in s.
- `V(t)`: terminal voltage in V.
- `I(t)`: terminal current in A.
- `G(t)`: terminal conductance in S.
- `c_v(x,t)`: normalized vacancy or defect concentration.
- `delta_T(x,t)`: temperature rise above `T0`, in K.
- `m(x,t)`: normalized conductive or phase state in `[0, 1]`.
- `sigma(x,t)`: electrical conductivity in S/m.

The neural field uses normalized coordinates `(x_norm, t_norm)`. Autograd
derivatives are computed with respect to normalized coordinates and converted
where needed by `L_eff` and the total time span.

## Loss terms

The total v1 objective contains:

- `L_port_data`: reconstruct `I(t)` and `G(t)` by integrating predicted
  `sigma(x,t)` through the one-dimensional series resistance relation.
- `L_ic`: match the initial `c_v`, `delta_T`, and `m` fields to the frozen
  synthetic Ground Truth initial state.
- `L_field_anchor`: optional field supervision for audit and identifiability.
  It can be reduced or set to zero in configs.
- `L_smooth`: first-difference regularization in space and time.
- `L_heat_residual`: lightweight thermal residual.
- `L_state_residual`: conductive-state relaxation residual.
- `L_defect_residual`: lightweight defect migration or relaxation residual.
- `L_sigma_consistency`: consistency between predicted positive `sigma` and a
  differentiable conductivity closure.
- `L_boundary`: no-flux style boundary regularization on `delta_T` and `c_v`.

## Residual definitions

### Port consistency

The strictest term in v1 is the port relation:

```text
R_area(t) = sum_x dx / sigma(x,t)
I_pred(t) = eta_A A_contact V(t) / R_area(t)
G_pred(t) = I_pred(t) / (V(t) + eps_V)
```

This follows the same series electrostatic structure used by the synthetic
Ground Truth generator.

### Heat residual

The v1 heat residual is a normalized approximation:

```text
r_T = d(delta_T / T_scale)/dt_norm
      - a_T d2(delta_T / T_scale)/dx_norm2
      - b_T (V/V_peak)^2 (sigma/sigma_ref)
      + c_T (delta_T/T_scale)
```

This term encourages temporal smoothness, diffusion-like smoothing, Joule-like
heating, and substrate-like cooling. It is not a full SI-unit heat equation.

### State residual

The conductive state residual is closer to the Ground Truth state relaxation:

```text
m_eq = sigmoid((T - T_sw + alpha_c (c_v - c_v0)) / dT_sw)
r_m = tau_m dm/dt - (m_eq - m)
```

Here `T = T0 + delta_T`. This is a differentiable torch approximation of the
state relaxation relation.

### Defect residual

The defect residual is a normalized lightweight drift-diffusion-relaxation
regularizer:

```text
r_c = dc_v/dt_norm
      - a_c d2c_v/dx_norm2
      + b_c (V/V_peak) dc_v/dx_norm
      + c_c (c_v - c_v0)
```

This is an approximation intended to reduce unphysical hidden-field variation,
not a complete ionic transport PDE claim.

### Sigma consistency

The model still predicts a positive `sigma(x,t)` directly. v1 adds:

```text
r_sigma = log(sigma_pred) - log(sigma_physics(c_v, T, m, x))
```

`sigma_physics` is a torch conductivity closure with Arrhenius off-branch,
on-branch interpolation, and bilayer parameter support when the frozen
Ground Truth parameters contain NbOx and V2O5 layer values.

## Boundary and initial conditions

The initial condition is supervised by `L_ic` at `t=0`. Boundary regularization
uses no-flux style penalties:

```text
d(delta_T)/dx_norm = 0 at x_norm = 0 and 1
dc_v/dx_norm = 0 at x_norm = 0 and 1
```

These are lightweight stabilizers, not a claim that all experimental boundary
physics has been captured.

## Strict vs approximate components

Stricter components:

- Series port reconstruction from `sigma(x,t)`.
- Torch autograd derivatives for all residuals.
- State relaxation form for `m`.
- Positive and bounded neural-field transforms.

Approximate v1 components:

- Normalized heat residual.
- Normalized defect residual.
- Direct positive `sigma` head plus sigma-consistency regularization.
- No-flux boundary regularization.

All outputs are synthetic numerical digital-twin benchmark results, not
experimental measurements.
