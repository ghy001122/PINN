# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase:
  `Q2_POST_M44_SUBMISSION_FREEZE_AND_UPLOAD_LOCK`.
- Frozen GT v1.1 and all M40/M40R/E1F historical evidence are unchanged.
- The sole positive inverse mainline is the synthetic, tight-`T_sw`-calibrated,
  constrained `gamma_sub` rank-1 result (`qualified_supported`). It is not a material
  constant or experimental estimate.
- Complete PINN contracts exist, but every trained full-PINN route is
  `failed_but_informative`; forward, sensitivity, and inverse success claims
  remain `forbidden`.
- No project measurement, independent external quantitative validation, valid
  Qiu author-code reproduction, or Zhang 13 V evaluation exists.
- Historical P0/P3 are qualified synthetic sub-results. P1 remains
  `failed_but_informative` with field error `0.37563055753707886` and interface
  residual `106.15460205078125`; P2 remains failed and P4 remains `forbidden`.

## M42 closeout

M42 used a preregistered CPU-only dimensional-closure audit. A first detached
replay abort was caused by Git owner/sandbox `safe.directory` rejection plus an
incorrect guessed full SHA; it has no scientific vote. Process-local Git
configuration then produced a clean detached replay with `442 passed` and
external injection of all 50 assets.

The pilot/formal audit consumed `22/40` forward calls across 11 unique
manufactured or unit-load cases. It ran no claim-bearing device forward, curve
fit, inverse, PINN, or sealed-data access.

| M42 gate | Value | Limit | Result |
| --- | ---: | ---: | --- |
| current imbalance | `0` | `1e-6` | pass |
| contact-power closure | `4.20e-17` | `1e-6` | pass |
| smooth sensible-enthalpy ledger | `2.58e-14` | `1e-4` | pass; discrete bookkeeping only |
| switching enthalpy | unassessed | `1e-3` | fail closed; no sourced latent heat |
| finest-pair maximum | `0.13813` | `0.02` | fail |
| domain sensitivity maximum | `0.84235` | `0.02` | fail |
| source/local resistance error | `1.33023` | `0.01` | fail |
| finite-width/x-z closure maximum | `0.67058` | `0.10` | fail |
| time fine-pair maximum | `0.00886` | `0.02` | pass sub-result |

Final status: `failed_but_informative`, decision **B**. Pure x-z extrusion and
formal dynamic 2D GT are unauthorized. The result supports only the need for a
bounded finite-width/2.5D or coarse-3D thermal-spreading closure.

## M43 closeout

M43 ran a preregistered, CPU-only manufactured component audit of a finite
rectangular isoflux source on a homogeneous isotropic half-space. Independent
steady Eq. 21 and transient Green-function references were compared against a
conservative quarter-domain finite-volume solver.

- `15` unique thermal PDE forwards were executed; no device forward, fit,
  inverse, PINN, sealed-data access, or latent-heat insertion occurred.
- All `21/21` locked gates passed.
- Steady normalized reference errors were `0.00757203` (`rho=1`) and
  `0.00936891` (`rho=5`), both below `0.02`.
- The `rho=5` mesh/domain changes were `0.0102762` and `0.000816181`.
- Transient Green-reference error was `0.0109507`, time-pair change was
  `0.000272383`, and sensible-energy imbalance was `3.87656e-09`.
- Finite-width-bias mesh/domain changes were `0.0136865` and `1.52527e-07`.

Final status: `qualified_supported`, decision
`M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY`. This supports only the manufactured
finite-width thermal-spreading component. The latest research instruction
then routed M44 through a source-graded heterogeneous 3D thermal-only bridge;
that audit stopped and did not authorize the deferred reduction comparison.
M43 does not
repair M42's `1.33023` source/local resistance mismatch, resolve phase-change
latent heat, validate a Qiu device, establish `gamma_sub/gamma_eff`, or
authorize device dynamics, inverse identification, or PINN training.

## M44 closeout

M44 executed one receipt-bearing, preregistered heterogeneous 3D thermal-only
bridge with 31/31 unique forwards. It introduced no device fit, electrical
solve, latent heat, inverse, PINN, GPU, or sealed-data access. Homogeneous and
layered independent-reference recovery, source/power integration, steady and
transient ledgers, domain convergence, local-temperature convergence, x-z-bias
convergence, provenance, physical acceptability, and budget gates passed.

Three locked convergence gates failed:

| M44 gate | Value | Limit | Result |
| --- | ---: | ---: | --- |
| heterogeneous `Zth` finest mesh pair | `0.0632464` | `0.02` | fail |
| heterogeneous `Zth` finest time pair | `0.0544910` | `0.02` | fail |
| VO2 mean-temperature finest mesh pair | `0.0632464` | `0.02` | fail |

The registered source envelope was `0.0335790`, nominally within the robust
source-family band, but it cannot vote because mandatory convergence failed.
The heterogeneous response differed from the M43 homogeneous anchor by up to
`3.24964` in the registered normalization, and the matched x-z comparator
remained quantitatively forbidden across the registered interval. Final status:
`failed_but_informative`; decision `M44_STOP_REAL_GEOMETRY_UPGRADE`. Per the
locked stop rule, no M44R or M45 is authorized. M42's `1.33023` resistance
localization mismatch and unresolved latent heat remain unchanged.

## Delivery distance

| Deliverable | State | Gap |
| --- | --- | --- |
| Synthetic inverse mainline | locked/reproducible | manuscript integration and reviewer defense only |
| Real-device structure | source-traceable geometry, failed local bridge | no calibrated local parameters or positive dynamic validation |
| Thermal component physics | M43 manufactured homogeneous-half-space closure is `qualified_supported`; M44 heterogeneous bridge stopped | three preregistered convergence gates fail; no device or reduction claim |
| PINN | architecture scaffold plus negative training evidence | no positive neural claim |
| Submission | content package assembled | journal template, declarations, visual QA, lawful archive route |

## Single priority

Freeze scientific work and complete the submission package from the locked
one-dimensional `gamma_sub` mainline plus bounded M42--M44 limitations. Only
journal/template adaptation, declarations, visual QA, lawful asset routing,
claim-to-sentence auditing, and reproducibility packaging are authorized.
