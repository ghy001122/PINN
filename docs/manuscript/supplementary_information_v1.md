# Supplementary Information

## Calibration-gated inference of an effective heat-loss coordinate from sparse terminal observations in a synthetic phase-change-device benchmark

This document reports the evidence boundaries, audit details, and negative
results supporting the main manuscript. Every project result is synthetic
numerical digital-twin evidence unless explicitly identified as a publisher
source. No project-generated measured device data are present.

## S1. Evidence types and claim gates

The evidence chain distinguishes:

- `synthetic_gt`: frozen numerical benchmark truth;
- `solver_generated`: output of a declared repository simulator;
- `pinn_predicted`: output of a trained neural model;
- `publisher_source`: publisher-hosted article or Supporting Information;
- `digitized_publication_curve`: a derived, provenance-recorded extraction;
- `proxy/preflight/smoke`: an implementation check without scientific vote.

Only `supported`, `qualified_supported`, `failed_but_informative`, and
`forbidden` are used as claim statuses. Missing, non-finite, upstream-ineligible,
or threshold-failing results fail closed. A passing smoke test or finite
residual does not upgrade a scientific claim.

## S2. Frozen benchmark and observation operator

Ground Truth v1.1 contains the one-dimensional fields
\((\phi,c_v,T,m,\sigma)\), terminal observables \((V,I,G)\), and declared
boundary/interface metadata. The four frozen arrays, acceptance configurations,
acceptance report, and manifest are hash-checked by the governance audit. The
positive inverse target is
\(\gamma_{\mathrm{sub}}\), the coefficient multiplying the reduced
substrate-loss term \(-\gamma_{\mathrm{sub}}(T-T_0)\).

The observation operator integrates spatial conductivity through the
one-dimensional series resistance. This explains why terminal conductance is
almost perfectly correlated with mean conductivity while remaining
insufficient to distinguish all internal state decompositions.

## S3. Identifiability and complete-neural failure evidence

The port-only ablation fits integrated quantities much more reliably than the
complete hidden fields. The full neural formulation includes electrical,
defect, thermal, and phase residuals; initial, boundary, and interface losses;
terminal reconstruction; and global defect/energy ledgers. The bounded routes
are not positive solver evidence:

| Route | Evidence | Status | Reason |
|---|---|---|---|
| Initial full-neural MVE | port NRMSE 0.123764; four normalized residual RMS values above 0.01 | `failed_but_informative` | Joint port/residual contract fails |
| Instrumented control-volume replay | port NRMSE 0.0955475 | `failed_but_informative` | Thermal, phase, interface-flux, and global-ledger gates fail |
| Mixed state--flux variant | selected thermal/flux terms improve | `failed_but_informative` | Port, constitutive, PDE, field, interface, ledger, and no-regression gates fail |

These failures justify target reduction in this benchmark. They do not prove a
universal impossibility for every PINN architecture or optimization budget.

## S4. Reduced-inverse audit design

With microphysics fixed, the profile objective releases only
\(\gamma_{\mathrm{sub}}\). The audit sequence is:

1. nominal profile and truth recovery;
2. continuous off-grid refinement across noise and observation counts;
3. joint \((\gamma_{\mathrm{sub}},T_{\mathrm{sw}})\) confounding map;
4. recoverability phase diagram under prior width, noise, count, and protocol;
5. selected fresh simulator anchors for the dense response surface;
6. calibration-tolerance sweep and ODE-backed spot check;
7. calibration--protocol factorial decomposition;
8. statistical and broad stress audits retaining failed cases.

The dense joint surface contains 2501 interpolated locations derived from 77
simulator-backed locations. It is not represented as 2501 independent solves.
The response-surface tolerance study contains 1350 cases; the targeted
simulator-backed spot check contains 270 cases. The continuous off-grid audit
contains 36 cases, and the confounding map contains 42 cases.

## S5. Calibration and protocol decomposition

The bundled calibrated configuration in main Figure 5 contains 720
simulator-backed synthetic cases. Its factors do not isolate protocol. A
separate factorial audit gives:

| Component | Gain |
|---|---:|
| Calibration | 1.1216748795 |
| Protocol | 0.0149556651 |
| Interaction | 0.0014762924 |
| Total | 1.1381068369 |

Accordingly, the allowed statement is that calibration dominates and protocol
is a secondary modifier in the tested design. Protocol optimality and a
protocol-only causal gain are forbidden.

The broader 2400-case simulator-backed stress audit reports a best tested
calibrated short-pulse sequence success rate of 0.9604167 and worst-case
relative error of 0.4444. Because the worst case is large and the source result
explicitly rejects an unqualified main-figure role, this result remains
supplementary.

## S6. LLP source-contract amendment

The public VO\(_2\) source [@qiu2024] prints a reversal-temperature expression
in its Supporting Information. Earlier LLP formulations establish the model
family [@dealmeida2002; @dealmeida2003], while a later explicit electrothermal
comparator provides a separate event-rule formulation [@sena2026]. These
sources are not interchangeable. The audit therefore separates four layers:

| Layer | Contract | Result | Permitted interpretation |
|---|---|---|---|
| A | Literal printed Qiu SI Eq. S3/S4 transcription | Transcription fidelity passes; literal reversal has maximum phase-fraction jump 0.119145 in the audit | Printed-formula sensitivity only |
| B | Analytic inverse of the configured tanh limiting-branch anchor | 4002 branch/grid evaluations; maximum inverse identity error \(3.55\times10^{-15}\); realized reversal-continuity gate passes | The `atanh` term is source-traceable as an analytic anchor inverse |
| C | Sena--de Almeida 2026 explicit electrothermal LLP | Literature comparator only; author code not verified | Later event-rule comparison, not Qiu author intent |
| D | Historical repository implementation | Numerically matches its declared Layer-B contract | Repository implementation history only |

For the configured proximity kernel,
\(P(0)=0.999999997324712\); the deficit
\(2.6752879911384753\times10^{-9}\) is analytic for the printed kernel rather
than a floating-point rounding artifact. The blocking implementation-fidelity
and realized-continuity gates pass. Return-point memory and wiping-out
diagnostics are non-blocking and do not authorize those physical claims.

Executable Qiu author code, complete reversal-event rules, and all numerical
initialization details are unavailable. Therefore neither Layer A nor Layer B
is claimed to reproduce unpublished author intent or code. The earlier E1F
artifact has no scientific vote because its formal contract and a digitized
curve extraction were invalid. The corrected literal-S3 sensitivity study
passes DOP853--Radau parity but fails the clean 12 V source-curve setting gate;
it remains `failed_but_informative` and does not refute general LLP behavior.

## S7. Main-figure provenance

The six main figures are committed as their existing original PNG bytes. They
were not regenerated during manuscript assembly. Their SHA-256 values and
source table hashes are recorded in
`outputs/tables/main_submission_figure_manifest.json`.

Figure 3 contains visually similar protocol rows because the configured audit
finds little isolated protocol effect; this is not a rendering error. Figure 5
is explicitly a bundle result and must not be captioned as protocol-only gain.

## S8. Data availability and replay boundary

The repository versions all text, code, configurations, lightweight JSON/CSV
results, manifests, and the six main figures. Frozen NPZ arrays are a local
asset pack and publisher PDFs are third-party source files that are hash-locked
locally but not redistributed. A local clean-worktree replay therefore requires
copying hash-verified frozen arrays and governance metadata into the detached
validation worktree. Public-clone reproduction without that asset pack is not
claimed. The asset pack can be supplied on reasonable request where policy and
licensing permit.

## S9. Manufactured finite-width thermal-spreading closure

A separate preregistered audit tested only a homogeneous, isotropic,
constant-property half-space under a centered 500 nm by 100 nm uniform-isoflux
surface source. It used no device electrical model, measured curve, phase
transition, inverse calculation, or neural network. The steady source-area
mean reference was independently implemented from the rectangular isoflux
half-space solution of Yovanovich, Muzychka, and Culham
[@yovanovich1999]; the transient source-area mean reference used the half-space
surface-source Green function of Yovanovich [@yovanovich1997]. Neither
reference imported the finite-volume grid, operator, or ledger implementation.

For source area \(A_s\), full input power \(P_0\), conductivity \(k\), and
source-mean temperature rise \(\overline{\Delta T}_s\), the locked quantities
were

\[
\Theta=k\sqrt{A_s}\,\frac{\overline{\Delta T}_s}{P_0},
\qquad
Z_{\mathrm{th}}(t)=\frac{\overline{\Delta T}_s(t)}{P_0}.
\]

The quarter-domain finite-volume model received \(P_0/4\) through an exactly
aligned top-face Neumann flux while reporting temperature over the full
\(P_0\). Far boundaries were fixed at the reference temperature; symmetry and
top faces outside the source were adiabatic. The x-z extrusion was retained
only as a comparator for finite-width bias and did not receive a quantitative
model claim.

| Preregistered diagnostic | Value | Maximum | Result |
|---|---:|---:|---|
| Steady Eq. (21), \(\rho=1\), golden relative error | 0 | \(10^{-4}\) | pass |
| Steady Eq. (21), \(\rho=5\), golden relative error | \(1.36\times10^{-16}\) | \(10^{-4}\) | pass |
| 3D steady reference error, \(\rho=1\) | 0.007572 | 0.02 | pass |
| 3D steady reference error, \(\rho=5\) | 0.009369 | 0.02 | pass |
| \(\rho=5\) mesh-pair change | 0.010276 | 0.02 | pass |
| \(\rho=5\) domain-pair change | 0.000816 | 0.02 | pass |
| Steady normalized power imbalance | \(9.18\times10^{-11}\) | \(10^{-6}\) | pass |
| Green early-limit error | 0.000151 | 0.01 | pass |
| Green long-limit error | 0.006303 | 0.01 | pass |
| 3D transient Green-normalized maximum error | 0.010951 | 0.02 | pass |
| Transient time-pair change | 0.000272 | 0.02 | pass |
| Normalized sensible-energy imbalance | \(3.88\times10^{-9}\) | \(10^{-4}\) | pass |
| Finite-width-bias mesh-pair absolute change | 0.013687 | 0.02 | pass |
| Finite-width-bias domain-pair absolute change | \(1.53\times10^{-7}\) | 0.02 | pass |
| Source area/power integration errors | \(1.26/2.22\times10^{-16}\) | \(10^{-10}\) | pass |

All 21 gates, including finite-value, no-clipping/no-smearing, near-zero
outflow, and execution-budget checks, passed in one formal invocation with 15
unique thermal-only PDE forwards. The largest grid contained 94,461 cells.
The machine-readable evidence is
`outputs/tables/m43_finite_width_thermal_spreading_summary.json`,
`outputs/tables/m43_finite_width_thermal_spreading_cases.csv`, and
`outputs/tables/m43_transient_green_reference.csv`; the locked config is
`configs/m43_finite_width_thermal_spreading.yaml`, the figure is
`outputs/figures/m43/m43_thermal_spreading_closure.png`, and the report is
`docs/codex_reports/m43_finite_width_thermal_spreading_closure.md`.

This `qualified_supported` result establishes only numerical closure of the
registered manufactured thermal component. It does not repair the M42
source/local resistance mismatch, supply phase-change latent heat, validate a
Qiu or other physical device, authorize the x-z comparator as a quantitative
model, or support inverse/PINN claims. It conditionally authorizes only an M44
heterogeneous thermal-family audit; it does not itself authorize RC/kernel
fitting.

## S10. Heterogeneous 3D thermal-family stop boundary

M44 extended the numerical contract to a constant-property, sensible-heat,
Qiu-scale heterogeneous 3D family with explicitly graded geometry, material,
and source assumptions. It did not solve an electrical problem, infer a Joule
map, fit a Qiu curve, introduce latent heat, or run an inverse method or PINN.
One receipt-bearing formal execution completed all 31 preregistered
thermal-only forwards.

Independent homogeneous-half-space and one-dimensional layered limits,
source and power integration, discrete steady/transient ledgers, domain
truncation, local maximum-temperature convergence, provenance, physical
acceptability, and the execution budget passed. Three of 22 locked gates
failed:

| Preregistered M44 diagnostic | Value | Maximum | Result |
|---|---:|---:|---|
| Heterogeneous (Z_{\mathrm{th}}) finest mesh-pair change | 0.063246 | 0.02 | fail |
| Heterogeneous (Z_{\mathrm{th}}) finest time-pair change | 0.054491 | 0.02 | fail |
| VO2 mean-temperature finest mesh-pair change | 0.063246 | 0.02 | fail |
| Heterogeneous (Z_{\mathrm{th}}) finest domain-pair change | (2.05\times10^{-7}) | 0.02 | pass |
| Transient sensible-energy imbalance | (3.47\times10^{-11}) | (10^{-4}) | pass |

The temperature and thermal-impedance mesh entries encode the same underlying
spatial sensitivity because the registered impedance uses VO2 mean temperature
divided by fixed input power. Thus the three failed entries expose two
independent deficiencies: near-source spatial resolution and early-time
resolution. The 0.033579 source-family envelope is descriptive and non-voting,
because it is smaller than the registered mesh and time-discretization
differences. Likewise, the matched x-z discrepancy is mesh/domain stable on
the locked time grid and consistent with the M43 finite-width boundary, but
M44 did not independently establish its time-discretization convergence.

The terminal decision is `M44_STOP_REAL_GEOMETRY_UPGRADE`
(`failed_but_informative`). It means that the heterogeneous family did not
close within the preregistered budget and M43-normalized operational gates; it
does not prove that heterogeneous 3D thermal models cannot converge in
general. No M44 repair, M45 reduction, unique Qiu thermal kernel, inverse, or
PINN is authorized. M42's 1.330233 lumped-to-local resistance mismatch and the
unresolved latent-heat scope remain unchanged.

## S11. Additional forbidden claims

The evidence does not support real experimental validation, unconditional
\(\gamma_{\mathrm{sub}}\) identifiability, complete two-dimensional hidden-field
recovery, terminal-only two-dimensional inverse success, full or Seiler-style
STL-PINN reproduction, universal F-SPS/Fourier superiority, or full
device-grade FEM/3D multiphysics reproduction.

## Supplementary references

References use the shared `references.bib` file.
