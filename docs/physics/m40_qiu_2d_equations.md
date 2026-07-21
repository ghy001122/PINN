# M40 Qiu VO2 x-z Equations and E0 Boundary Conditions

## Electrical conservation

On the conductive Ti/Au/VO2 domain,

\[
\nabla\cdot(\sigma(T,h)\nabla\phi)=0,\qquad
\mathbf J=-\sigma(T,h)\nabla\phi.
\]

Al2O3 is thermal-only and does not enter the electrical unknown map. All
unassigned electrical faces are insulating. At a material contact face,

\[
G_f=\frac{A_f}
{d_i/(2\sigma_i)+R_{c,f}^{\prime\prime}+d_j/(2\sigma_j)}.
\]

The terminal current is the signed sum of Dirichlet boundary-face fluxes,
not a volume proxy. The electrical ledger compares
`sum(V_terminal I_terminal)` with the independently accumulated face Joule
power.

## Thermal conservation

On Ti/Au/VO2/Al2O3,

\[
\rho c_p\frac{\partial T}{\partial t}
=\nabla\cdot(k\nabla T)+\mathbf J\cdot\mathbf E.
\]

The conservative thermal face conductance is

\[
K_f=\frac{A_f}
{d_i/(2k_i)+R_{th,f}^{\prime\prime}+d_j/(2k_j)}.
\]

The E0 finite domain uses an explicitly labeled bottom heat-loss prior; all
other unassigned thermal faces are adiabatic. The global ledger is

\[
\frac{E^{n+1}-E^n}{\Delta t}+Q_{out}^{n+1}-P_J^n=0.
\]

Storage, outer-boundary heat flux, and Joule input are reconstructed from
separate cell/face accumulations.

## Hysteretic history closure

`h=1` denotes insulating and `h=0` metallic. The Qiu-fitted major-branch
targets are

\[
h_{heat/cool}(T)=\frac12+\frac12\tanh\left[
\beta\left(T_c\mathbin{\pm}\frac{w}{2}-T\right)\right].
\]

M40 E0 advances a differentiable rate-smoothed target with finite relaxation
time. Incomplete relaxation preserves history and yields minor-loop memory.
This is a declared E0 closure, not exact reproduction of Qiu Supporting
Information equations S2-S4. The source's reversal ledger and proximity
function remain the compact-model reference.

The dynamic source-equivalent resistance is

\[
R(T,h)=R_0\exp(E_a/T)h+kR_m,
\]

and the remaining bulk-equivalent resistance after the explicit contact term
is mapped deterministically to `sigma(T,h)`. No neural or free conductivity
state exists.

## RC coupling

\[
C\frac{dV_1}{dt}=\frac{V_{in}-V_1}{R_{load}}-I_{dev},
\]

where `Idev` is the electrode boundary-flux integral. With `T,h` fixed over a
step, the implicit update uses the FVM device conductance and is checked by an
independent ampere residual.

## Preregistered E0 metrics

The exact thresholds live in
`configs/m40_qiu_vo2_real_device_2d.yaml`. The peak-field metric is fixed
before execution as the 99th percentile inside a physical VO2 window that
excludes 10 nm around contact edges and VO2 boundaries; this avoids treating
an ideal sharp electrode corner singularity as a convergent material QoI.
