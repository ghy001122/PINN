# M44 heterogeneous 3D thermal bridge preregistration

Task: `Q2_M44_QIU_HETEROGENEOUS_3D_THERMAL_BRIDGE_AND_REPRODUCTION_CLOSEOUT`

Base: `e433fe900cb4376b5e1d5cfe81333e527f5454a5`.

## Single scientific question

Under the reported Qiu-device length scales, do finite-width heterogeneous
layers and an unresolved heat-source location alter the small-signal sensible
thermal impedance enough that the homogeneous half-space component cannot be
used as a unique device thermal kernel?

The null result is admissible. M44 is thermal-only and cannot repair the M42
port-to-local resistance mismatch, identify a Joule map, add phase-change
enthalpy, reproduce Qiu dynamics, or authorize inverse/PINN work.

## Evidence and parameter boundary

- Reported geometry: 100 nm by 500 nm VO2 footprint, 100 nm VO2 thickness,
  15 nm Ti, 40 nm Au, and (012)-oriented Al2O3 substrate. The exact source
  locators are Qiu main-article p. 2 Fig. 1 caption and SI PDF p. 3
  (printed p. 2), Materials and Methods.
- The current-path assignment and all unreported overlap/contact support are
  literature-derived or engineering priors, never measurements.
- Constant-property, linear sensible heat only. Latent heat is outside the
  validated scope; it is not asserted to be physically zero.
- Perfect thermal contact is the voting baseline. Any nonzero TBR is
  non-voting and may not be fitted.
- Qiu SI PDF p. 6 (printed p. 5) quotes a VO2 volumetric heat capacity of
  `3.07e6 J m^-3 K^-1` at 336 K. It is used without inventing a density/heat-
  capacity factorization. The locked VO2 conductivity is a primary-literature-
  derived in-range branch; all other unmatched local material values are
  explicit engineering priors or non-orientation-matched literature brackets.
- All heat-source families use identical total step power and time points.

## Source families and observable

The voting families are:

1. `S_bulk`: uniform volumetric power in the VO2 footprint;
2. `S_contact`: uniform volumetric power in symmetric end regions occupying a
   locked 20% of each half current-path length;
3. `S_mixed`: 50% `S_bulk` plus 50% `S_contact`.

The contact fraction belongs to a preregistered engineering-prior interval
0.10--0.30 but only the locked 0.20 member votes in M44. Its placement along
the literature-derived 100 nm x-axis is not Qiu-reported; the alternate axis is
unassessed. It is not adjusted after results, and even a numerically robust
result remains conditional on this registered geometry family. The main
impedance is

\[
Z_{\mathrm{VO2}}(t)=\frac{\overline{T}_{\mathrm{VO2}}(t)-T_0}{P_{\rm full}}.
\]

Source-region mean temperature and VO2 maximum temperature are secondary
diagnostics. The source envelope uses the locked M43 steady resistance
\(R_{\rm ref}=52158.95646368626\ \mathrm{K\,W^{-1}}\).

## Independent references

1. Homogeneous recovery uses the locked M43 Eq. 21 and Green-reference
   artifacts, not a regenerated device curve.
2. The one-dimensional layered limit uses an independent linear finite-element
   method-of-lines reference with lumped capacity and exact modal propagation;
   it shares no grid, matrix assembly, source code, or time integrator with the
   3D FVM. For a 1D element of thickness \(h\),

\[
K_e=\frac{kA}{h}
\begin{bmatrix}1&-1\\-1&1\end{bmatrix},\qquad
M_e^{\rm lump}=\frac{C_vAh}{2}
\begin{bmatrix}1&0\\0&1\end{bmatrix}.
\]

The generalized symmetric eigensystem gives an exact-in-time response for that
independent semidiscrete operator. It is verified against the analytic series
for a single fixed-bottom slab and against \(\sum_i L_i/k_i\), then self-
refined to `<=0.002` before it may vote in the 2% layered gate. Krapez and Dohou,
DOI `10.1016/j.ijthermalsci.2014.02.007`, remains a primary multilayer-
reference locator rather than a claim that this code is their implementation.

## Numerical design and forward budget

The 3D model is a conservative, source/material-interface-aligned,
quarter-symmetry Cartesian FVM with harmonic face conductance. It uses fixed
ambient temperature on remote x/y/bottom boundaries and zero flux on symmetry
and exposed top/side boundaries. The x-z comparator uses the same short-axis,
depth, materials, source support, full width normalization, and power.

Exactly 31 unique thermal-only forward cases are registered:

- 2 homogeneous recovery cases (steady/transient);
- 2 layered one-dimensional recovery cases (steady/transient);
- for each of three source families, six heterogeneous 3D cases: steady and
  transient at `M2D2`, steady and transient at `M3D2`, transient at `M3D3`,
  and a fine-time transient at `M3D2` (18 cases);
- for each source family, x-z transient cases at `M2D2`, `M3D2`, and `M3D3`
  (9 cases).

No Cartesian sweep is allowed. The maximum is 32 forwards, 12 CPU hours, one
formal confirmatory invocation, and one result-bearing configuration hash.
Identical-case reruns, rescue rounds, and post-result gate changes are
forbidden.

## Locked gates

These are repository operational gates, not universal field standards.

- homogeneous steady and transient recovery error: `<=0.02` each;
- layered 1D steady and transient reference error: `<=0.02` each;
- source area/volume and total-power integration error: `<=1e-10`;
- steady normalized power imbalance: `<=1e-6`;
- transient normalized sensible-energy imbalance: `<=1e-4`;
- finest-pair `Zth` mesh, domain, and time changes: `<=0.02` each;
- VO2 mean-temperature mesh/domain/time change: `<=0.02`;
- local-source VO2 `Tmax` mesh/domain/time change: `<=0.05`;
- x-z bias mesh-pair and domain-pair absolute change: `<=0.02`;
- all voting `Zth` curves finite, nonnegative, causal, monotone, with finite
  steady limits;
- no NaN, clipping, negative properties, unit error, source smearing, or
  missing voting provenance.

A nonconvergent localized `Tmax` is retained as an abstention and fails its
gate; the source is not widened after inspection.

## Source-envelope and terminal decision

\[
E_{\rm source}=\max_{s,s',t}
\frac{|Z_s(t)-Z_{s'}(t)|}{R_{\rm ref}}.
\]

- `E_source <=0.05`: `M44_HET3D_GO_ROBUST` within the registered nuisance
  family only, never a unique Qiu-device kernel;
- `0.05 < E_source <=0.15`, or `E_source >0.15` with all numerical gates
  passing: `M44_HET3D_GO_CONDITIONAL_OR_ABSTAIN`; the latter is explicitly
  source-location dominated and forbids a unique Qiu kernel;
- any mandatory reference, provenance, conservation, or convergence failure:
  `M44_STOP_REAL_GEOMETRY_UPGRADE`.

The conditional decision may authorize M45 only to construct a source-aware
validity/refusal map. It cannot authorize a unique device kernel, inverse,
PINN, Qiu dynamic GT, or experimental claim. There is no fourth decision and
no M44 repair round.
