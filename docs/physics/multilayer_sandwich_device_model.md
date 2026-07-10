# Boundary-Aware Multilayer Sandwich Device Model

This document describes a reduced synthetic numerical digital-twin benchmark, not full FEM, device-grade simulation, or experimental validation.

## Stack

The model supports TE / PCM / optional thermal barrier / BE / substrate layers. Structure ablations include `pcm_only`, `pcm_plus_electrodes`, `pcm_plus_electrodes_substrate`, `full_stack_with_contact_resistance`, `full_stack_with_thermal_boundary_resistance`, and `full_stack_with_SnSe_barrier`.

## Electric Equations

Layerwise reduced form:

```text
div(sigma_i grad phi_i) = 0
J_i = -sigma_i grad phi_i
Q_J = sigma_i |grad phi_i|^2
I = integral_Gamma J dot n
G = I / V_dev
V_app = V_dev + R_L I
```

The implementation solves a vertical series stack per lateral column and audits interface potential jumps, normal-current continuity, lateral insulation, and load-line consistency.

## Thermal Equation

```text
rho_c_i dT_i/dt = div(k_i grad T_i) + Q_J - sink_i(T_i - T0)
```

Thermal interfaces audit temperature continuity or thermal boundary resistance and heat-flux consistency. Bottom substrate Robin heat sinking and optional top/lateral losses are included in reduced form.

## PCM State Equation

```text
tau_m dm/dt = s(T; T_sw, w) - m + D_m laplacian(m)
```

No-flux phase boundary conditions are implemented through edge-preserving finite differences.

## Claim Gate

A case can support only the wording `boundary-aware multilayer sandwich forward benchmark` when all fields are finite and configured residual gates pass. It cannot support full FEM, device-grade reproduction, or experimental validation.

## v7 Residual And Energy Gate Clarification

The v7 audit computes residual diagnostics explicitly. These diagnostics are claim-gate metrics, not new claims of full FEM fidelity:

```text
r_phi = Delta phi_contact / max(Delta phi_stack, eps)
r_J = max |J_i - J_{i+1}| / max |J|
r_T = median |T_i - T_{i+1}| / max Delta T
r_q = max |q_i + q_{i+1}| / max |q|
r_sub = mean |q_sub| / max mean |Q_J dz|
```

The reduced energy-balance gate compares accumulated Joule input with final thermal storage, substrate/sink loss, and boundary loss:

```text
epsilon_E = |E_J - E_store - E_sink - E_boundary| /
            max(|E_J| + |E_store| + |E_sink| + |E_boundary|, eps)
```

If `epsilon_E` exceeds the configured gate, the forward benchmark is downgraded even when fields remain finite. The official v7 run fails this gate, so multilayer forward wording is limited to failed-but-informative reduced-model evidence.
