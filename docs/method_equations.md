# Method Equations

All variables use SI units unless explicitly noted. The default parameters are literature-guided synthetic priors or order-of-magnitude priors, not measured material parameters.

## Domain and State Variables

The one-dimensional effective device domain is:

$$
x \in [0, L_{\mathrm{eff}}].
$$

The dynamic variables are:

$$
c_v(x,t), \quad T(x,t), \quad m(x,t),
$$

where \(c_v\) is the effective defect / oxygen-vacancy state, \(T\) is the local temperature, and \(m\) is the effective conductive-state fraction.

## Conductivity

The mixed conductivity is:

$$
\sigma = \exp\left[(1-m)\log(\sigma_{\mathrm{off}}) + m\log(\sigma_{\mathrm{on}})\right].
$$

The low-conductance branch is:

$$
\sigma_{\mathrm{off}} =
\sigma_{\mathrm{off0}}
\exp\left[-\frac{E_{\mathrm{off}}}{k_B}\left(\frac{1}{T}-\frac{1}{T_0}\right)\right]
\exp\left[\beta_{\mathrm{off}}(c_v-c_{v0})\right].
$$

The high-conductance branch is:

$$
\sigma_{\mathrm{on}} =
\sigma_{\mathrm{on0}}\exp\left[\beta_{\mathrm{on}}(c_v-c_{v0})\right].
$$

## Quasi-Static One-Dimensional Electrical Relation

At each RHS call:

$$
R_{\mathrm{area}} = \sum_i \frac{\Delta x}{\sigma_i},
$$

$$
J = \frac{V_{\mathrm{app}}(t)}{R_{\mathrm{area}}},
$$

$$
E_i = \frac{J}{\sigma_i},
$$

$$
I = A_{\mathrm{eff}}J,
$$

$$
G = \frac{I}{V_{\mathrm{app}}(t)+\epsilon_V}.
$$

The effective active area is:

$$
A_{\mathrm{eff}} = \eta_A A_{\mathrm{contact}},
$$

$$
A_{\mathrm{contact}} = \pi(50\times10^{-6})^2.
$$

## Defect Transport

The defect flux is:

$$
F_v = -D_v(T)\frac{\partial c_v}{\partial x}
+ \mu_v(T)c_v(1-c_v)E.
$$

The conservation equation is:

$$
\frac{\partial c_v}{\partial t}
= -\frac{\partial F_v}{\partial x}
- k_r(T)(c_v-c_{v0}).
$$

## Heat Equation

The heat flux is:

$$
q_T = -k_{\mathrm{th}}\frac{\partial T}{\partial x}.
$$

The thermal dynamics are:

$$
\rho C_p\frac{\partial T}{\partial t}
= -\frac{\partial q_T}{\partial x}
+ JE
- \gamma_{\mathrm{sub}}(T-T_0).
$$

## Conductive-State Relaxation

The conductive-state fraction follows:

$$
\frac{\partial m}{\partial t}
= \frac{m_{\mathrm{eq}}(T,c_v)-m}{\tau_m}.
$$

The equilibrium fraction is:

$$
m_{\mathrm{eq}} =
\frac{1}{1+\exp\left[-\frac{T-T_{\mathrm{sw}}+\alpha_c(c_v-c_{v0})}{\Delta T_{\mathrm{sw}}}\right]}.
$$

## Temperature Dependence

Arrhenius-type temperature-dependent parameters use:

$$
p(T) = p_0\exp\left[-\frac{E}{k_B}\left(\frac{1}{T}-\frac{1}{T_0}\right)\right].
$$

## Boundary Conditions

The Ground Truth solver uses no-flux boundary conditions:

$$
F_v(0,t)=0,\quad F_v(L_{\mathrm{eff}},t)=0,
$$

$$
q_T(0,t)=0,\quad q_T(L_{\mathrm{eff}},t)=0.
$$

## Reduced Multilayer Claim-Gate Residuals

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


## Conservative Multilayer v8 Residuals

The v8 conservative multilayer audit is a reduced finite-volume 2.5D stack diagnostic, not full FEM or experimental validation. For layer interface `i,j`, the implemented interface diagnostics use:

```text
R_TBR = q_n - (T_i - T_j) / Rth_ij
R_Robin = -k dT/dn - h_sub (T - T0)
R_J = Jn_i - Jn_j
R_phi = phi_i - phi_j - Rc_ij Jn
```

The thermal update uses per-column implicit vertical diffusion/storage and boundary exchange. The official audit removes the earlier artificial lateral factor, global sink shortcut, and temperature clipping from the v8 conservative path.

The energy ledger records accumulated Joule input, thermal storage, boundary loss, and interface-transfer magnitude:

```text
epsilon_E = |E_J - E_store - E_boundary| / max(|E_J| + |E_store| + |E_boundary|, eps)
```

For zero-source cases with only roundoff-level energies, `epsilon_E` is reported as zero to avoid a meaningless tiny-denominator ratio.
