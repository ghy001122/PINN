# Method Equations

All variables use SI units unless explicitly noted. The default parameters are literature-guided synthetic priors or order-of-magnitude priors, not measured material parameters.

The independent Qiu-2024 M40 x-z electro-thermal-hysteresis-RC equations,
masked Al2O3 topology, contact/TBR face conductances, RC coupling, and E0
ledger are defined in `docs/physics/m40_qiu_2d_equations.md`. Those equations
form a source-constrained external-literature bridge and do not replace or
revise the frozen synthetic Ground Truth equations below.

## Active Phase 1 and R1-R3 2.5D Contract

This section defines the Phase 1 reference and later R1-R3 PINN equation
contract. It is a preregistered model, not a completed solver or positive
method result. The Phase 1 resolved plane is the single-device VO2 footprint
\(\Omega_{\mathrm{VO2}}\subset\mathbb R^2\), with \(x\) along the current path
and \(y\) along the device width. The masks
\(r(x,y)\in\{\mathrm{bare},\mathrm{contact}\}\) separate bare VO2 from
electrode-covered VO2. The interdevice substrate surface is not a Phase 1
field. Vertical transport is reduced to region-specific passive areal thermal
memory. The Qiu-inspired geometry is literature anchored, while unresolved
contact and local material quantities remain engineering priors routed through
`configs/qiu_vo2_phase1_source_contract.yaml`.

Let \(t_{\mathrm{pcm}}\,[\mathrm m]\) be the active-film thickness,
\(\phi\,[\mathrm V]\) the potential, \(\mathbf E=-\nabla_\parallel\phi\)
\([\mathrm{V\,m^{-1}}]\), and \(\mathbf K\,[\mathrm{A\,m^{-1}}]\) the sheet
current. In-plane charge conservation is

$$
\nabla_\parallel\!\cdot\mathbf K=0,
\qquad
\mathbf K=-t_{\mathrm{pcm}}\sigma(T,s,|\mathbf E|)
\nabla_\parallel\phi .
$$

Finite electrode contacts \(\Gamma_p\) use prescribed terminal potentials in
the Phase 1 baseline; non-contact boundaries are electrically insulating.
Contact resistance is omitted and therefore is not a validated Phase 1
interface. The observable terminal current is not a free network output:

$$
I_p(t)=\int_{\Gamma_p}\mathbf K\cdot\mathbf n\,d\ell .
$$

The active-plane energy equation is written per unit area so every term has
units \(\mathrm{W\,m^{-2}}\):

$$
\rho c_p t_{\mathrm{pcm}}\,\partial_t T
=\nabla_\parallel\!\cdot
\left(k_\parallel t_{\mathrm{pcm}}\nabla_\parallel T\right)
+t_{\mathrm{pcm}}\sigma|\nabla_\parallel\phi|^2
-q_z+q_{\mathrm{couple}} .
$$

The vertical reduction uses region-specific local areal capacities
\(c_{k,r}^A\,[\mathrm{J\,m^{-2}\,K^{-1}}]\), conductances
\(g_{k,r}\,[\mathrm{W\,m^{-2}\,K^{-1}}]\), and temperatures
\(z_k\,[\mathrm K]\). With \(z_0=T\), \(z_{K+1}=T_0\), and
\(r=r(x,y)\),

$$
c_{k,r}^A\partial_t z_k
=g_{k-1,r}(z_{k-1}-z_k)-g_{k,r}(z_k-z_{k+1}),
\qquad k=1,\ldots,K,
$$

$$
q_z=g_{0,r}(T-z_1).
$$

The fitted memory excludes the already resolved active-plane VO2 storage.
The bare-region independent reference contains an Al2O3 substrate branch. The
contact-covered reference contains the same substrate branch plus a passive
Ti/Au overlay branch. This produces a driving-point impedance at the active
VO2 temperature without counting its areal heat capacity twice.

The raw local-stack reference supplies only relative impedance shape and
bare/contact region contrast. One positive conductance scale factor makes the
nominal area-integrated DC sink equal to the Qiu source-author device-level
\(S_{\mathrm{th}}=2.06\times10^{-4}\,\mathrm{W\,K^{-1}}\). A separate
positive capacity scale factor makes active-plane storage plus all passive
memory storage equal to
\(C_{\mathrm{th}}=4.96\times10^{-11}\,\mathrm{J\,K^{-1}}\). The nominal
active VO2 storage \(1.535\times10^{-14}\,\mathrm{J\,K^{-1}}\) is subtracted
before the memory-capacity target is formed. These global normalizations
preserve passivity but do not turn the fitted device-level quantities into
local material or interface properties.

The preregistered v8 shape--scale repair separates the raw material-stack
truncation vote from the later device-effective amplitude/time normalization.
For a candidate production depth \(D\), the area-integrated fine raw reference
defines only the temporary coordinate ratio

$$
r_D=\frac{a_C}{a_G}
=\frac{C_{\mathrm{target}}G_{\mathrm{raw},D}}
{G_{\mathrm{target}}C_{\mathrm{raw},D}}.
$$

The ratio does not scale any raw coefficient or response amplitude during the
depth vote. Instead, inherited raw grids and the effective-window pullback
grids are evaluated independently:

$$
f_{\mathrm{raw}}=r_D f_{\mathrm{eff}},
\qquad
t_{\mathrm{raw}}=\frac{t_{\mathrm{eff}}}{r_D}.
$$

Each grid family must separately pass the unchanged mesh and depth limits;
their errors may not be concatenated or averaged. Only after a raw depth is
selected are the two positive device-level scales applied once to the selected
fine production kernel. Scaling every conductance-like state-space coefficient
by \(a_G\) and every passive-memory capacity by \(a_C\) gives

$$
Y_{\mathrm{eff}}(s)
=a_GY_{\mathrm{raw}}\!\left(\frac{a_C}{a_G}s\right).
$$

This supports only device-effective amplitude/time normalization of a
source-shape-constrained passive kernel. It does not support intrinsic local
material calibration, Qiu-device reproduction, or scaled-depth invariance.

For the Phase 1 two-copy behavior fixture,

$$
q_{\mathrm{couple},1}=q_{\mathrm{couple},2}=0.
$$

No nonzero interdevice exchange is authorized because the interdevice
substrate field is unresolved. A later nonzero model requires either an
explicit substrate surface heat field or a high-order independently validated
passive nonlocal kernel with reciprocity, convergence, and ledger gates.

All \(c_{k,r}^A\) and \(g_{k,r}\) must be positive and each regional thermal
subsystem must be stable and passive. Phase 1 selects the smallest order
\(K\in\{2,3\}\) that passes every region against a higher-order reference;
\(K=1\) is an ablation, not the default model.

The VO2 conductivity is a white-box logarithmic mixture:

$$
\sigma_{\mathrm{VO_2}}(T,s)
=\exp\!\left[(1-s)\log\sigma_{\mathrm{ins}}(T)
+s\log\sigma_{\mathrm{met}}(T)\right],
$$

The endmembers are device-effective uniform-limit mappings of the Qiu
source-author resistance model, not intrinsic VO2 conductivities. With nominal
current-path length \(L\), width \(W\), active thickness \(t\), resistance
prefactor \(R_0\), activation temperature \(\Theta_a\), and metallic
resistance \(R_m\),

$$
\sigma_{\mathrm{ins}}^{\mathrm{eff}}(T)
=\frac{L}{Wt\,[R_0\exp(\Theta_a/T)+R_m]},
\qquad
\sigma_{\mathrm{met}}^{\mathrm{eff}}
=\frac{L}{WtR_m} .
$$

At the locked 325 K nominal state these are
\(39.2883183844845\,\mathrm{S\,m^{-1}}\) and
\(7619.04761904762\,\mathrm{S\,m^{-1}}\). The uniform-state boundary
integral therefore recovers the corresponding source-author endmember
resistance algebraically. Applying the closure pointwise in a nonuniform field
is an explicit device-effective modeling assumption; it is not local material
measurement or exact author-model reproduction. Out-of-domain extrapolation
is fail-closed.

The bounded conductive-state coordinate and differentiable branch memory obey

$$
\tau_s\partial_t s=s_{\mathrm{eq}}(T,b)-s,
\qquad
s_{\mathrm{eq}}(T,b)=
\operatorname{sigmoid}\!\left(\frac{T-T_c(b)}{w_T}\right),
$$

$$
T_c(b)=\frac{1+b}{2}T_c^\uparrow+
\frac{1-b}{2}T_c^\downarrow,
\qquad
r=\tanh\!\left(\frac{\partial_tT}{r_b}\right),
$$

$$
a_+(r)=\max(r,0)^2,
\qquad
a_-(r)=\max(-r,0)^2,
$$

$$
\tau_b\partial_t b=
a_+(r)(1-b)-a_-(r)(1+b).
$$

Here \(s\in[0,1]\) is an effective conductive-state coordinate and
\(b\in[-1,1]\) is a project engineering closure for heating/cooling memory.
The squared one-sided activations are continuously differentiable at zero,
hold \(b\) exactly when \(\partial_tT=0\), drive it toward \(+1\) during
heating and toward \(-1\) during cooling, and preserve the bounded interval
under the locked backward-Euler update. This avoids an unphysical relaxation
of a stationary heating/cooling branch toward zero.
The branch equation is not a literal implementation of Qiu equations S3--S4
and cannot support an exact-author-model claim.

The external circuit closes the device field and terminal observation:

$$
C_p\frac{dV_d}{dt}
=\frac{V_{\mathrm{in}}-V_d}{R_L}-I_{\mathrm{dev}}(t).
$$

Initial conditions are \(T=z_k=T_0=325\,\mathrm K\), \(V_d=0\),
\(b_0=1\), and \(s=s_{\mathrm{eq}}(T_0,b_0)\). The Phase 1 lateral thermal
baseline is no-flux. Any later contact-resistance,
thermal-boundary-resistance, or nonzero interdevice-coupling term requires
explicit units, provenance, and interface tests.

The thermal ledger includes both active-plane and K-state storage:

$$
\frac{d}{dt}\int_\Omega\left[
\rho c_p t_{\mathrm{pcm}}(T-T_0)
+\sum_{k=1}^{K}c_{k,r(x,y)}^A(z_k-T_0)
\right]dA
=P_J-P_{\mathrm{sink}}-P_{\partial\Omega}.
$$

Here
\(P_J=\int_\Omega t_{\mathrm{pcm}}\sigma|\nabla_\parallel\phi|^2dA\),
\(P_{\mathrm{sink}}=\int_\Omega g_{K,r(x,y)}(z_K-T_0)dA\), and
\(P_{\partial\Omega}\) is the outward lateral heat flux. The Phase 1 two-copy
fixture has no device-device exchange term.

The field-to-port power identity is independently reconstructed as

$$
P_{\mathrm{device}}=V_d I_{\mathrm{dev}}=P_J.
$$

With source current \(I_{\mathrm{src}}=(V_{\mathrm{in}}-V_d)/R_L\), the
backward-Euler circuit ledger is

$$
P_{\mathrm{source}}
=P_{R_L}+P_C^{\mathrm{BE}}+P_{\mathrm{device}},
\qquad
P_{\mathrm{source}}=V_{\mathrm{in}}I_{\mathrm{src}},
\qquad
P_{R_L}=I_{\mathrm{src}}^2R_L.
$$

The capacitor term is reported without hiding backward-Euler numerical
dissipation:

$$
P_C^{\mathrm{BE}}
=C_pV_d^n\frac{V_d^n-V_d^{n-1}}{\Delta t}
=\frac{\tfrac12C_p[(V_d^n)^2-(V_d^{n-1})^2]}{\Delta t}
+\frac{C_p(V_d^n-V_d^{n-1})^2}{2\Delta t}.
$$

Thus the combined electrothermal ledger is

$$
P_{\mathrm{source}}
=P_{R_L}
+\frac{dE_C}{dt}
+P_{C,\mathrm{BE\ diss}}
+\frac{dE_{\mathrm{thermal}}}{dt}
+P_{\mathrm{sink}}
+P_{\partial\Omega},
$$

where \(P_{C,\mathrm{BE\ diss}}\ge 0\). Thermal, circuit, and combined
residuals are evaluated separately and fail closed. Omitting the algorithmic
capacitor term while using backward Euler is not accepted as a conservation
test.

Spatial and temporal refinement are compared only after conservative
restriction to the fixed physical base-cell grid and interpolation to the
fixed 5 ns output grid. For a candidate \(u\) and fine reference
\(u_{\mathrm{ref}}\),

$$
\operatorname{NRMSE}(u,u_{\mathrm{ref}})=
\frac{\operatorname{RMSE}(u-u_{\mathrm{ref}})}
{\max\!\left[\operatorname{RMS}(u_{\mathrm{ref}}-u_{\mathrm{ref}}(0)),
d_{\mathrm{floor}}\right]}.
$$

Backward-Euler stepping begins at the locked base maximum step. If an accepted
trial would satisfy

$$
\max\{\|s^n-s^{n-1}\|_\infty,\|b^n-b^{n-1}\|_\infty\}>0.02,
$$

the trial is rejected and retried by halving \(\Delta t\), never below the
locked transition maximum step. At most four rejections are permitted per
accepted step and 1000 per case; exceeding either cap fails closed. The
matrix-free LGMRES Newton correction is subjected to the locked Armijo
coefficient and damping floor rather than an implementation-default line
search.

The immutable v6 history used a normalized 400/800 nm substrate-truncation
comparison. Its recorded failure remains unchanged. The separately
preregistered v8 readiness repair instead tests raw 51.2/102.4 micrometre and,
only when its closed fallback rule is triggered, 102.4/204.8 micrometre pairs.
Both the inherited material-frame and pulled-back effective-window step and
frequency grids retain the 0.05 depth and 0.01 mesh limits. A successful v8
readiness result would require a new formal-v8 configuration and fresh user
authorization; it would not retroactively change v6 or constitute Phase 1
execution. Contact-overlap QoI sensitivity is always reported; geometry-robust
wording is forbidden whenever that effect exceeds the locked spatial fine-pair
discretization error. A literature/source-envelope trend can vote only when
its variation is at least the numerical-noise estimate.

The configured floors are \(10^{-12}\,\mathrm A\),
\(10^{-3}\,\mathrm K\), and \(10^{-6}\) for terminal current, temperature
rise, and conductive-state change. Below-floor signals cannot pass by NRMSE;
they are routed to absolute analytic-limit gates. Event crossings are ordered
without post-hoc time warping.

The independent FVM judge and the PINN residual implementation must not share
the same discrete residual code. Later PINN losses may include charge, active
energy, each K-state ODE, phase-state, branch-memory, RC, boundary/interface,
port, and global-ledger residuals, but smoothness alone is not a physics
residual. The SnSe/NbO2 auxiliary route replaces the VO2 conductivity/state
kernel with a Poole--Frenkel/electrothermal-runaway kernel; it does not reuse
VO2 thresholds, state semantics, or parameter values.

## Retained Historical 1D Equations

The remaining equations below are retained for frozen-GT replay, historical baselines, negative evidence, and reviewer defense. They are not the current final device structure and do not vote for Phase 1 or R1-R3.

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

## Versioned Complete 1D PINN Contract v1

The N0 path is separate from historical lightweight PINNs. Its state network is

```text
u_theta(x,t) = [phi(x,t), c_v(x,t), T(x,t), m(x,t)].
```

Conductivity is not an independent network output. It is derived from the frozen synthetic closure:

```text
sigma_off = sigma_off0(x) A_T(T) exp[beta_off (c_v-c_v0)]
sigma_on  = sigma_on0(x) exp[beta_on (c_v-c_v0)]
sigma = exp[(1-m) log(sigma_off) + m log(sigma_on)].
```

The strong-form residuals are

```text
r_phi = d/dx [sigma dphi/dx],
J_v = -D_v dc_v/dx + mu_v c_v(1-c_v) E,
r_c = dc_v/dt + dJ_v/dx + k_r(c_v-c_v0),
r_T = rho Cp dT/dt - d/dx(k dT/dx) - sigma E^2
      + gamma_sub(T-T0),
r_m = dm/dt - (m_eq(T,c_v)-m)/tau_m,
E = -dphi/dx.
```

The versioned output transform exactly imposes

```text
phi(0,t)=0, phi(L,t)=V(t),
c_v(x,0)=c_v0 + delta_c exp[-(x-x_d)^2/(2 w_d^2)],
T(x,0)=T0,
m(x,0)=m_eq(T0,c_v(x,0)).
```

The defect and thermal endpoints use zero normal flux. Bilayer one-sided current, defect and heat fluxes are included as a bounded loss/diagnostic, but no positive interface or P1 claim follows from their implementation.

The cell-center terminal observation is

```text
R_area(t) = mean_x[1/sigma(x,t)] L_eff,
I(t) = A_eff V(t) / R_area(t),
G(t) = I(t) / [V(t)+eps_V].
```

For the frozen GT, history is represented by continuous `m`; the explicit VO2 event ledger `(branch,T_r,m_r)` is declared but inactive. No learned event head is used. Frozen full fields are score-only and never training labels in N0.

The equations and contract preflight are implementation facts. The trained N0 MVE failed its port and residual gates, so these equations currently support no positive full-PINN accuracy or inverse claim.

## N0-R Teacher-Compatible Dual-Domain Audit

The frozen GT electrostatic reconstruction uses the driven left electrode and grounded right electrode:

$$
\phi(0,t)=V(t),\qquad \phi(L_{\mathrm{eff}},t)=0,\qquad E=-\partial_x\phi.
$$

The v1 single-global-network transform used the opposite electrode orientation. N0-R preserves the historical implementation and evidence, but the new split diagnostic path uses the frozen-teacher orientation.

For the declared interface $L_{\mathrm{int}}$, the layer-local coordinates are

$$
\xi_L=\frac{x}{L_{\mathrm{int}}},\qquad
\xi_R=\frac{x-L_{\mathrm{int}}}{L_{\mathrm{eff}}-L_{\mathrm{int}}},
$$

and every spatial derivative is mapped back to SI coordinates through

$$
\partial_x=L_d^{-1}\partial_{\xi_d},\qquad d\in\{L,R\}.
$$

Independent one-sided traces impose the operational interface residuals

$$
[\phi]=[c_v]=[T]=[m]=0,
$$

$$
[\sigma E]=[F_v]=[-k\partial_xT]=0.
$$

The preregistered layer-local normalization uses dimensional term sums rather than post-hoc rescaling:

$$
S_{\phi,d}=\frac{\sigma_{\mathrm{ref},d}V_*}{L_d^2},
$$

$$
S_{c,d}=\frac{1}{t_*}+\frac{D_d}{L_d^2}
+\frac{0.25\mu_dV_*}{L_{\mathrm{eff}}L_d}+k_{r0},
$$

$$
S_{T,d}=\frac{\rho C_pT_*}{t_*}+\frac{k_dT_*}{L_d^2}
+\sigma_{\mathrm{ref},d}\left(\frac{V_*}{L_{\mathrm{eff}}}\right)^2
+\gamma_{\mathrm{sub}}T_*,
$$

$$
S_m=\frac{1}{t_*}+\frac{1}{\tau_m}.
$$

These are repository operational scales, not universal nondimensional laws. The N0-R single-seed run passed the local exact-interface gates but failed the held-out defect/thermal, terminal-current, energy, field, and port gates. Therefore this section supports an implementation and failure-boundary description only; it does not support reliable full-PINN forward evidence or interface novelty.

## N0-CV-E v3 Solver-Consistent Cell Contract

The final bounded N0 formulation predicts only bounded cell-centered states

$$
u_\theta(t)=\{c_i(t),T_i(t),m_i(t)\}_{i=1}^{31},
$$

with hard initial conditions. It returns the complete state/observable set by applying the frozen constitutive closure and analytic series-electric relation:

$$
\sigma_i=\max[\sigma(c_i,T_i,m_i),\epsilon_\sigma],\qquad
R_A=\sum_i\frac{\Delta x}{\sigma_i}+\epsilon_R,
$$

$$
J=\frac{V(t)}{R_A},\qquad E_i=\frac{J}{\sigma_i},\qquad
\phi_i=V(t)-\left[\sum_{k\le i}E_k\Delta x-\frac12E_i\Delta x\right],
$$

$$
I=A_{\mathrm{eff}}J,\qquad G=\frac{I}{V+\epsilon_V}.
$$

For an interior face (i+1/2), the defect and heat fluxes reproduce the frozen arithmetic-face convention:

$$
J^v_{i+1/2}=-\bar D_{i+1/2}\frac{c_{i+1}-c_i}{\Delta x}
+\bar\mu_{i+1/2}\bar c_{i+1/2}(1-\bar c_{i+1/2})\bar E_{i+1/2},
$$

$$
q_{i+1/2}=-\bar k_{i+1/2}\frac{T_{i+1}-T_i}{\Delta x},
$$

with (J^v_{1/2}=J^v_{N+1/2}=q_{1/2}=q_{N+1/2}=0). The cell right-hand sides are

$$
\dot c_i=-\frac{J^v_{i+1/2}-J^v_{i-1/2}}{\Delta x}
-k_{r,i}(c_i-c_{v0}),
$$

$$
\rho C_p\dot T_i=-\frac{q_{i+1/2}-q_{i-1/2}}{\Delta x}
+JE_i-\gamma_{\mathrm{sub}}(T_i-T_0),
$$

$$
\dot m_i=\frac{m_{\mathrm{eq}}(T_i,c_i)-m_i}{\tau_m}.
$$

Training blocks use the dimensionless cellwise differences between neural time derivatives and these right-hand sides, plus adjacent-state trapezoidal defect-mass and energy ledgers. The registry fixes (L_*=100\,\mathrm{nm}), (t_*=3\,\mathrm{ms}), (V_*=0.2\,\mathrm{V}), (T_*=20\,\mathrm{K}), (sigma_*=2.4\,\mathrm{S\,m^{-1}}), and (J_*=4.8\times10^6\,\mathrm{A\,m^{-2}}) before training.

The locked no-training parity and conservation checks pass, but the sole primary optimization terminates before checkpoint and result scoring. These equations therefore support only an operator-implementation fact and a `failed_but_informative` optimization boundary; they do not support trained full-PINN forward evidence.

## M33 First-Order Mixed State--Flux Contract

M33 preserves the frozen N0-CV-E cell states, material partition, analytic
series-electrical head, boundary orientation, and finite-volume arithmetic.
It adds explicit face outputs

$$
q^c_{i+1/2,\theta}(t),\qquad q^T_{i+1/2,\theta}(t),
$$

with SI units (\mathrm{m\,s^{-1}}) and (\mathrm{W\,m^{-2}}), respectively.
The endpoint heads are hard constrained to the frozen zero-flux conditions.
The former second-order state residual is separated into constitutive and
conservation residuals:

$$
r_{q_c}=\frac{q^c_\theta-F_v(c_v,T,E)}{q^c_*},\qquad
r_c=\frac{\partial_t c_v+\nabla_h\!\cdot q^c_\theta+k_r(c_v-c_{v0})}{r_{c,*}},
$$

$$
r_{q_T}=\frac{q^T_\theta+k_{\mathrm{th}}\nabla_h T}{q^T_*},\qquad
r_T=\frac{\partial_tT-[-\nabla_h\!\cdot q^T_\theta+JE-\gamma_{\mathrm{sub}}(T-T_0)]/(\rho C_p)}{r_{T,*}}.
$$

The phase and electrical equations remain

$$
r_m=\partial_t m-\frac{m_{\mathrm{eq}}-m}{\tau_m},\qquad
r_J=\frac{\sigma E-J}{J_*}.
$$

At the bilayer face, state continuity uses the same preregistered one-sided
linear trace reconstruction as v3r. The heat and defect interface values are
read directly from the explicit shared face heads; opposite outward normals
give the oriented jump law. Adjacent-time global mass and energy ledgers use
the explicit head boundary fluxes, while the terminal-current ledger retains
the frozen analytic series relation.

M33 groups constitutive, conservation, phase/current, IC/BC, interface, and
global-ledger violations in independently updated augmented-Lagrangian blocks.
Mixed formulations and augmented Lagrangians are established components and
carry no standalone novelty claim. Any trained claim remains conditional on
the unchanged v3r port, field, PDE, interface, and conservation gates.
