# M43 Thermal-Spreading Source Contract

## Steady isoflux rectangle

For a uniform-isoflux rectangle 2a by 2b on an isotropic half-space, As = 4ab
and rho = max(a,b)/min(a,b) >= 1. Yovanovich, Muzychka, and Culham (1999),
DOI 10.2514/2.6467, Eq. (21), gives

Theta_infinity(rho) = sqrt(rho)/pi * [
  asinh(1/rho) + asinh(rho)/rho
  + rho/3 * (1 + rho^-3 - (1 + rho^-2)^(3/2))
].

The locked double-precision references are

Theta_infinity(1) = 0.47320100440933854
Theta_infinity(5) = 0.4082084030088908.

Here Theta = k*sqrt(As)*Rs. Rs is already the half-space spreading resistance
based on source-area mean surface temperature and total source power. No R1D
is added. Swapping sides or scaling geometry leaves Theta unchanged;
Rs scales with 1/k and 1/sqrt(As) and is independent of heat-flux amplitude.

Primary source:
https://www.mhtlab.uwaterloo.ca/pdf_papers/mhtl99-2.pdf

## Transient half-space Green reference

For z > 0,

dtheta/dt = alpha*Laplacian(theta),

with zero initial temperature rise and surface flux
-k*dtheta/dz = qflux*indicator(As)*H(t). The source-averaged step response
implied by Yovanovich (1997), DOI 10.2514/6.1997-2458, is

Zth(t) = 1/(2*pi*k*As^2) * integral_As integral_As [
  erfc(norm(r-rprime)/(2*sqrt(alpha*t))) / norm(r-rprime)
] dAprime dA.

This is already the step response. A second time integration is forbidden.
The implementation uses independent dimensionless overlap quadrature and does
not import FVM grid, matrix, boundary, or ledger code.

With Fo_A = alpha*t/As,

Theta(t) = k*sqrt(As)*Zth(t) ~ 2*sqrt(Fo_A)/sqrt(pi)

as Fo_A tends to zero, and Theta tends to Eq. (21) as Fo_A tends to infinity.
The reference must verify finiteness, non-negativity, monotonicity, the steady
upper bound, both asymptotes, and quadrature refinement.

Diffusion length is always ell_d = sqrt(alpha*t). The factor 2*sqrt(alpha*t)
inside erfc is part of the kernel, not a second diffusion-length definition.

Primary source:
https://www.mhtlab.uwaterloo.ca/pdf_papers/mhtl97-8.pdf

## Numerical comparison contract

The 3D quarter-domain source is an explicit top-face Neumann flux with quarter
input P0/4. Source area and full-power normalization are audited. FVM comparison
uses source-surface area mean, not a cell-center mean or sharp-edge maximum.
Far-domain temperature is fixed at T0; source exterior and symmetry faces are
adiabatic.

The finite domain is a numerical truncation of a half-space. Its extra
resistance or deficit cannot be relabeled as physical R1D, contact resistance,
device Cth, or device Gth. The transient sensible-energy ledger is discrete
bookkeeping, not Qiu-device or phase-change enthalpy evidence.

Source integration is audited with the relative quantities
$|A_{\rm discrete}-A_{\rm expected}|/A_{\rm expected}$ and
$|P_{\rm discrete}-P_{\rm expected}|/P_{\rm expected}$. Transient waveform
and time-pair errors are normalized by the nonzero analytical steady $R_s$.
When outward heat is near zero, the base/fine difference is normalized by
sector input power or sector input energy, never by outward heat itself.

Jain (2024), DOI 10.1016/j.ijheatmasstransfer.2023.124946, concerns a
finite-thickness steady isothermal source and is non-voting here.

The registered source-region grid is isotropic: square development meshes use
4/8/16 cells in each of x, y, z; rho=5 meshes use 2/4/8 cells across the 50 nm
quarter short axis and depth, with 10/20/40 cells across the 250 nm quarter
long axis.
