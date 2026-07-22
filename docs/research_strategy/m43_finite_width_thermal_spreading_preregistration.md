# M43 Finite-Width Thermal-Spreading Preregistration

## Locked question and manuscript use

M43 asks one question only: for a centered, uniform-isoflux rectangular source
of full area 500 nm by 100 nm on a homogeneous, isotropic half-space, do an
independent steady closed form, an independent transient Green-function
reference, and a conservative coarse three-dimensional finite-volume
discretization agree inside the locked two-percent limits?

A pass supports only a numerical thermal-spreading component for a later
reduction audit. A failure permanently terminates the Qiu two-/three-dimensional
quantitative rescue and routes the project to the frozen one-dimensional,
calibration-gated rank-1 gamma_sub manuscript.

## Evidence boundary

This is a solver-generated manufactured component-closure audit. It is not a
Qiu-device reproduction, external validation, local electrical model, phase
transition, total-enthalpy validation, inverse problem, or PINN experiment.
The M42 source/local resistance error 1.330233 and unresolved latent heat
remain upstream blockers regardless of the M43 result.

No Qiu curve, device resistance, contact partition, local Joule field,
R(T,H), hysteresis, latent heat, gamma_sub, gamma_eff, Cth, Gth, inverse,
PINN, GPU, or sealed 13 V input is allowed.

## Geometry, material, and coordinates

The full source is 2a by 2b = 500 nm by 100 nm, with a = 250 nm, b = 50 nm,
rho = a/b = 5, and As = 4ab = 5e-14 m2. The FVM uses x as the 100 nm direction
and y as the 500 nm direction. A same-area square (rho = 1) is development-only.

The homogeneous prior is k = 35 W m-1 K-1 and rho_m cp = 3.0e6 J m-3 K-1,
preserving the M42 constant-property engineering prior. Separate rho_m = 4000
kg m-3 and cp = 750 J kg-1 K-1 values are only a bookkeeping factorization,
not independent measurements. Alpha = k/(rho_m cp) = 1.1666667e-5 m2 s-1.

The horizon is tmax = 3 Rload C = 5.22 us. The only diffusion-length definition
is ell_d(t) = sqrt(alpha t), giving 7.803845206 um
at tmax.

## Boundary, source, and QoI contract

The quarter model has zero flux on x = 0 and y = 0, a top-face Neumann heat
flux over the exactly aligned quarter source, an adiabatic top outside the
source, and T - T0 = 0 on far x, far y, and bottom faces. For full power
P0 = 1 W, the quarter domain receives P0/4. The reported impedance is

Zth(t) = (T_source_surface_mean(t) - T0) / P0,

not temperature divided by quarter power. Surface face temperature is
reconstructed by T_face = T_cell + qflux*dz/(2k).

The steady QoI is Theta = k*sqrt(As)*Zth(infinity). Neither a source corner,
Tmax, nor a near-zero Qout relative error may vote.

The x-z comparator retains the 100 nm direction, is extruded through 500 nm,
receives P0/2 on its half domain, and is normalized by full P0. Its finite-width
bias is measured, not required to be small.

## Independent references

The steady reference is Yovanovich--Muzychka--Culham Eq. (21), DOI
10.2514/2.6467. The transient reference is built independently from the
surface point-source step kernel and source-area average in Yovanovich 1997,
DOI 10.2514/6.1997-2458. The Green reference is already a step response and
must not be time-integrated again. Jain 2024, DOI
10.1016/j.ijheatmasstransfer.2023.124946, is only a finite-thickness, steady,
isothermal scope boundary and does not vote.

Reference-only early and long diagnostics use Fo_A = 1e-8 and Fo_A = 1218.
FVM comparison uses the nine locked Fo_A values in YAML and normalizes waveform
errors by nonzero steady Rs.

## Grid and execution matrix

Every source edge is a grid face. M1/M2/M3 use successively isotropic
source-region spacing in all active spatial directions. The rho=1 quarter
source has 4 by 4 by 4, 8 by 8 by 8, and 16 by 16 by 16 source-region
cells in x, y, and z. The rho=5 quarter source has 2 by 10 by 2, 4 by 20
by 4, and 8 by 40 by 8 source-region cells in x, y, and z. Domain levels
extend from each source edge by
2 ell_d, 4 ell_d, and 6 ell_d. A largest-domain master grid is generated first;
D1/D2/D3 are exact prefixes, so extension only appends far cells.

The YAML freezes fifteen unique PDE forwards: five square steady development
cases, three rho=5 steady confirmatory cases, four rho=5 3D transients, and
three matched x-z transient comparators. Analytic quadrature is not a PDE
forward. There is one confirmatory attempt, no Cartesian sweep, no identical
rerun, no optional rescue, a 16-forward ceiling, an 8 CPU-hour ceiling, and a
one-day wall-clock boundary.

Execution is fail-fast: independent references and unit tests; square
development; rho=5 steady confirmation; 3D transient confirmation; x-z
comparator. Starting rho=5 freezes all grid, time, QoI, and threshold choices.

## Locked metrics and decision

Every threshold is in the YAML. Transient reference error is
max(abs(Z_FVM-Z_Green))/Rs. Mesh, domain, and time pairs are single-factor
comparisons. Bias convergence uses maximum absolute difference between bias
curves. Power and energy ledgers are normalized by quarter input power and
energy; near-zero outflow comparisons use input power/energy rather than Qout.

All mandatory gates passing selects
M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY. Any failure, incomplete confirmatory
run, budget exhaustion, or non-unique contract selects
M43_STOP_C_FREEZE_1D. There is no Decision A, third state, second solver, gate
relaxation, or M43R.

The source-area metric is the relative error
$|A_{\rm discrete}-A_{\rm expected}|/A_{\rm expected}$; the analogous source
power identity is normalized by expected sector power, and both use the locked
$10^{-10}$ ceiling. Steady mesh and domain
changes use $|\Theta_c-\Theta_f|/|\Theta_f|$. Transient Green and time-pair
errors use $\max_t|Z_1-Z_2|/R_s$, where $R_s$ is the nonzero analytical steady
reference. Bias convergence uses the maximum absolute difference between two
dimensionless bias curves. The near-zero outflow diagnostic compares only the
M3D3 base/fine time pair and takes the maximum of
$|Q_{b}-Q_f|/(P_0/4)$ and
$|E_{b}-E_f|/[(P_0/4)t]$ over the locked times. These definitions were
clarified before any formal M43 PDE forward and do not change a threshold.

## One-shot execution receipt

Before the first formal PDE call, the runner must atomically create a persistent
receipt and reserve the canonical case hash. Any existing receipt or formal
summary forbids a second invocation. A solver exception or budget exhaustion
leaves a terminal failed receipt and selects `M43_STOP_C_FREEZE_1D`; it does
not authorize a rerun.
