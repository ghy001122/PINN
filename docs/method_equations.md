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

## Constrained gamma_sub Inverse Objective

The main inverse releases only the effective substrate-dissipation parameter
\(\gamma_{\mathrm{sub}}\). The nuisance vector
\(\boldsymbol\psi=(T_{\mathrm{sw}},\tau_m,\sigma_{\mathrm{on0}},\eta_A,\ldots)\)
is fixed or restricted to a declared narrow prior. For an observed series \(y\)
and simulated series \(\hat y\), the relative root-mean-square error is

$$
\operatorname{rRMSE}(\hat y,y)=
\frac{\sqrt{N^{-1}\sum_{j=1}^{N}(\hat y_j-y_j)^2}}
{\max\!\left(\sqrt{N^{-1}\sum_{j=1}^{N}y_j^2},10^{-30}\right)}.
$$

The configured reduced objective is

$$
\mathcal J(\gamma_{\mathrm{sub}};\boldsymbol\psi)=
w_G\operatorname{rRMSE}(\hat G,G)^2
+w_I\operatorname{rRMSE}(\hat I,I)^2
+w_H\mathcal R_H,
$$

where the locked configuration uses \(w_G=1\), \(w_I=0.5\), and
\(w_H=0.01\), and \(\mathcal R_H\) is the reduced heat-residual loss used by
the audit scripts. The discrete estimate is

$$
\hat\gamma_{\mathrm{sub}}=
\underset{\gamma\in\Gamma_{\mathrm{declared}}}{\operatorname{argmin}}
\;\mathcal J(\gamma;\boldsymbol\psi),
$$

followed, only in the continuous-refinement audit, by a local off-grid
refinement around the best declared candidates. This is a constrained scalar
profile search in a synthetic benchmark, not a proof of joint global
identifiability and not a neural full-field inverse.
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


## Phase-Activated Multidomain v9 Equations

The v9 forward audit is a reduced synthetic y-z finite-volume digital-twin benchmark. It is not full FEM and not experimental validation.

For NbO2, the local conduction kernel uses a monotonic Poole-Frenkel form:

```text
J = J0 E exp[-(Ea - sqrt(q^3 |E| / (pi eps0 epsr)) / q) / (kB T)]
```

No local ad-hoc NDR term is used; any NDR-like behavior must arise from electrothermal coupling and the external load line.

For VO2, the switching target uses branch memory with independent heating and cooling thresholds:

```text
Tc = Tc_up on heating, Tc_down on cooling
s_eq = sigmoid((T - Tc) / width)
dm/dt = (s_eq - m) / tau_m
```

The generic family uses a reduced Allen-Cahn/free-energy inspired target:

```text
s_eq = clip(sigmoid((T - Tc)/width) - 0.25 m(1-m)(m-0.5), 0, 1)
```

The v9 stack uses independent interface maps:

```text
{TE/PCM, PCM/barrier, barrier/BE, BE/substrate} -> {Rc_ij, Rth_ij}
```

The y-z thermal update includes vertical finite-volume coupling, top/substrate Robin exchange, and conservative no-flux lateral conduction. The activation gate records `max_delta_T`, `delta_m`, `conductance_ratio`, `Vth`, `Vhold`, and hysteresis area. Cases that do not activate are excluded from inverse/positive claim routing.

## Control-Volume Multidomain OASIS v10 Equations

The v10 branch separates the electrical and thermal topology:

```text
Omega_e = TE union PCM union optional barrier union BE
Omega_T = Omega_e union substrate
```

The substrate is not assigned an artificial high electrical conductivity. The
vertical current terminates at the bottom electrode, while heat continues into
the substrate. NbO2 uses the field-dependent Poole-Frenkel kernel above without
the v9 effective phase-fraction multiplier on the primary path. VO2 has separate
`normalized_activated` and literature-shape-anchored parameter profiles.

The autonomous RC circuit is integrated as

```text
C dVdev/dt = (Vin - Vdev)/RL - Idev(Vdev,T,m).
```

The cell-centered control-volume residuals are

```text
R_phi,K = sum_faces J_f A_f,
J_f = -(phi_R - phi_L) / (0.5 dz_L/sigma_L + Rc_f + 0.5 dz_R/sigma_R),

R_T,K = rho c V_K (T_K^(n+1)-T_K^n)/dt
        - sum_faces q_f A_f - Q_J,K V_K,
q_f = -(T_R - T_L) / (0.5 dz_L/k_L + Rth_f + 0.5 dz_R/k_R),
Q_J = sigma |E|^2.
```

For adjacent independent layer experts, the interface laws are evaluated from
separate one-sided face derivatives:

```text
Jn_i + Jn_j = 0,
phi_i - phi_j - Rc_ij Jn_i = 0,
qn_i + qn_j = 0,
T_i - T_j - Rth_ij qn_i = 0.
```

The segmented-electrode y-z solver independently discretizes

```text
div(sigma grad(phi)) = 0,
I_k = integral_Gamma_k (-sigma grad(phi)) dot n dGamma,
```

with assigned Dirichlet electrode faces and insulating unassigned boundaries.
Its current-balance and uniform-series limits are implementation gates, not
evidence of hidden-field inversion.
