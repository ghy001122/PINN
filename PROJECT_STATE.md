# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_M43_FINITE_WIDTH_THERMAL_SPREADING_CLOSURE` (planned,
  bounded successor to M42 decision B).
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

## Delivery distance

| Deliverable | State | Gap |
| --- | --- | --- |
| Synthetic inverse mainline | locked/reproducible | manuscript integration and reviewer defense only |
| Real-device structure | source-traceable geometry, failed local bridge | no calibrated local parameters or positive dynamic validation |
| 2D/2.5D physics | M42 quantifies large closure errors | one final thermal-spreading closure or stop |
| PINN | architecture scaffold plus negative training evidence | no positive neural claim |
| Submission | content package assembled | journal template, declarations, visual QA, lawful archive route |

## Single priority

Preregister and run one low-cost M43 thermal-spreading closure using an
independent analytical/series benchmark and a refined finite-width solver. If
it cannot reduce domain and mesh uncertainty below locked limits without new
unsourced parameters, terminate the 2D route and freeze the 1D manuscript.
