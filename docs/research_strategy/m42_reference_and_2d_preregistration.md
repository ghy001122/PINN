# M42 Qiu Reference and 2D/2.5D Preregistration

## Manuscript use and unique hypothesis

M42 is a bounded solver preflight, not a new positive device claim. It asks
whether the source-constrained Qiu geometry can support a quantitative x-z
reference after finite-width heat spreading and source-to-local mapping are
audited. The falsifiable hypothesis is:

> A finite-width Qiu-class VO2 device can be promoted from the failed M40 x-z
> extrusion only if source-level resistance, contact-power closure, total-
> enthalpy conservation, domain truncation, mesh/time convergence, and out-of-
> plane thermal closure pass before inverse or PINN work begins.

The intended manuscript value is a fail-closed model-selection boundary. A
pass could authorize a later formal reference solver. A failure can only
justify a 2.5D/3D closure audit or return to the locked one-dimensional
synthetic manuscript; it cannot be relabeled as real-device validation.

## Evidence hierarchy and literature roles

Evidence levels are kept separate: formula identity, author-code parity,
numerical convergence, literature-curve agreement, and independent holdout.
Passing one level never implies a higher level.

| Source | M42 role | Prohibited transfer or claim |
| --- | --- | --- |
| Qiu et al. 2024, DOI `10.1002/adma.202306818` | Primary geometry, hysteresis, circuit, and lumped-scale source | No unpublished author-code equivalence, raw-data holdout, or local use of lumped `Cth/Sth` |
| Zhang et al. 2024, DOI `10.1038/s41467-024-51254-4` | Discrete author-code and public-source semantics comparator | Author-code parity is not independent physics validation; sealed 13 V remains inaccessible |
| Chen et al. 2025, DOI `10.1002/adfm.202423800` | Future cross-material trend comparator | No SnSe/NbO2 parameter transfer into Qiu VO2 |
| Liu et al. 2024, DOI `10.1109/LED.2024.3362829` | Future geometry-family holdout motivation | No NbOx mechanism or parameter transfer and no quantitative validation claim |

Qiu formula and dual-solver parity facts remain available, as do the failed SI
Fig. S1 current/voltage comparisons. Missing author code, raw arrays, reversal
update details, initial conditions, and event deadband prohibit exact author-
code reproduction. No curve is redigitized, refit, replaced, or rescued here.

Zhang's discrete source-code behavior, a continuous numerical reference,
time-step convergence, and experiment/theory agreement remain distinct. Chen
and Liu are registered only for later trend or geometry-family tests. STL,
Fourier/F-SPS, Lee, and Jurj are future matched baselines; none is reproduced
in M42.

## Physics and geometry contract

The reported 100 nm by 500 nm footprint, 100 nm VO2 thickness, and 15/40 nm
Ti/Au thicknesses are source quantities. Contact overlap, local contact
resistivity, substrate truncation, thermal boundary resistance, phase-
dependent local heat capacity, latent heat, and local history relaxation are
unresolved. All are prohibited from silently becoming measured parameters.

The electrical domain is VO2/Ti/Au. The substrate is thermal-only. Contact
faces must enforce a potential jump and their dissipated power must close the
terminal ledger:

\[
P_{port}=VI=P_{bulk}+P_{contact}.
\]

Thermal storage is evaluated as total enthalpy. With no source-locked latent
heat, the pilot sets the numerical latent-heat term to zero and reports the
missing phase-change enthalpy as a model gap; it does not infer that the real
latent heat is zero. Secant, tangent, and dynamic heat capacities are not
interchanged. The default hysteresis contract is the Qiu S1--S4 path-dependent
operator. A relaxation time is an extension and is forbidden in the default
reference.

The time horizon is three `Rload*C`. The substrate/lateral domain is selected
from `sqrt(alpha*t)`, not the historical 400 nm truncation. Three domain,
mesh, and time-step levels are locked. A pure x-z extrusion is compared with
no more than three finite-width 2.5D/coarse-3D thermal spots.

## Locked gates, budget, and leakage barriers

- CPU only, at most 40 forward solves and 8 wall-clock hours; no parameter or
  hyperparameter sweep.
- Current imbalance `<=1e-6`.
- Smooth total-enthalpy imbalance `<=1e-4`; switching-window imbalance
  `<=1e-3`.
- Finest-pair `I`, `Tmean`, `Tmax`, and `Qout` changes each `<=2%`.
- Domain sensitivity `<=2%`.
- Uniform two-dimensional/source-resistance limit error `<=1%`.
- No clipping, NaN, or unregistered constitutive extrapolation.
- Dynamic horizon at least three `Rload*C`.
- If finite-width or domain closure error exceeds `10%`, pure two-dimensional
  quantitative modeling is rejected and the result routes to decision B.

No M42 curve data are fit or used as a holdout. M40/M40R, E1F/E1F-R, D0/M36,
frozen GT, and the Zhang seal are read-only. The gates cannot be changed after
the pilot is observed.

## Decision and stop rules

- **A**: authorize a later formal 2D dynamic GT only if every gate passes.
- **B**: authorize only a bounded 2.5D/3D closure preflight if out-of-plane or
  domain closure exceeds 10%, while leaving formal 2D, inverse, and PINN
  unauthorized.
- **C**: stop the 2D route and return to the locked 1D manuscript if the
  foundation is nonrecoverable or requires unregistered assumptions.

If the detached replay fails, all scientific forward calls stop. Read-only
literature responsibility and analytic audits may still be recorded, but no
content or claim upgrade is permitted.
