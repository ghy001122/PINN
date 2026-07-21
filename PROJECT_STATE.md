# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_M40_QIU_VO2_REAL_DEVICE_2D_BRIDGE_E0`.
- Frozen GT v1.1: unchanged and read-only.
- Safe inverse mainline: constrained `gamma_sub`, calibration-gated rank-1, `qualified_supported` only under locked synthetic conditions.
- Full PINN: mandatory architecture/paper scaffold; every bounded trained-forward route remains `failed_but_informative`, so sensitivity/inverse claims are `forbidden`.
- Public VO2: M36 finite-step gates remain failed. M37R fixes the count-window contract and passes nominal parity, but a 15 V `log_C_th=-1%` perturbation changes post-transient event topology before Jacobian/SVD; M38, fit, lock, and 13 V access remain absent.
- Project-generated experimental validation: absent.
- M40 Qiu bridge: source contract and E0 implementation are being
  preregistered. Formal E0 has not run, and no positive M40 claim exists yet.
  Qiu's local 2D thermal/contact parameters and raw numeric curves are absent.

## Current Gate Ledger

| Gate | Status | Direct boundary |
| --- | --- | --- |
| M40 Qiu 2D E0 | planned / formal result absent | Source-locked geometry/protocol plus explicitly labeled unresolved priors. Passing E0 could support only conservative implementation verification; calibration and experimental validation remain forbidden. |
| Frozen GT v1.1 | `supported` integrity baseline | Equations, parameters, arrays, and acceptance files unchanged. |
| P0 / P3 | `qualified_supported` | Reduced synthetic semantics; P3 is only a static pure-electrical three-parameter local-rank result. |
| P1 / P2 | `failed_but_informative` | P1 retains `E_T=0.37563055753707886` and interface residual `106.15460205078125`; P2 thermal/material-block identifiability remains unresolved. P1 is required only for multidomain/interface claims. |
| P4 | `forbidden` | No full STL or universal Fourier/F-SPS superiority. |
| D0a | `failed_but_informative` | Source/SI parity passes; time-step NRMSE95 `0.163148 > 0.01`. |
| M35 D-PREG | `supported` protocol/provenance fact | R-T and 9/11/15/17 V hashes, roles, equations, units, licenses, metrics, LOVO, eight starts, stop rules, and 13 V sealing are locked. Not fit evidence. |
| M35 D-FIT | `failed_but_informative`; refit `forbidden` | All four open voltages fail locked 5 ns versus 2.5 ns current/voltage NRMSE gates. Activity class, frequency, charge, and energy pass. Fit stops before Jacobian/optimization; no fit lock exists. |
| M36 reference parity | `supported` numerical fact only | Independently integrated DOP853 and Radau traces pass every locked parity/event gate at 9/11/15/17 V. At 11/15 V, reversal counts are exactly `196/196` and `344/344`, maximum event-time disagreements are `9.47e-13 s` and `1.18e-13 s`, and cycle-shape NRMSE is `9.51e-8` and `1.62e-8`. This validates the continuous-event numerical reference, not the public fit or source parameters. |
| M36 source-compatible Euler limit | `failed_but_informative`; public refit route closed | Only 9 V passes. At the finest `0.3125 ns`, 11 V fails event-time (`67.5 ns > 25 ns`), cycle-shape (`0.0548 > 0.05`), and peak (`0.0389 > 0.02`) gates; 15 V fails event-time (`248.8 ns > 25 ns`) and has coarse-grid event-sequence instability; 17 V fails maximum current/noise (`62.365 > 5`). No threshold was changed. |
| M37 semantic audit | wording correction `supported`; execution `failed_but_informative`; geometry `forbidden`/unassessed | M36's failed vote stays fixed; M37 exposes a full/post count-window mismatch and stops before perturbations. |
| M37R repaired observability vote | `failed_but_informative`; geometry `forbidden`/unassessed | The inclusive interval `[t0+0.1(T-t0),T]` reproduces nominal full/post counts `0/216/381/4` and `0/196/344/0` for both solvers. The first 15 V `log_C_th=-1%`, `h=0.01` DOP853 perturbation is finite and keeps activity class but gives full/post `379/343` versus nominal `381/344`, common prefix `0`; execution stops after `11` forwards before Jacobian/SVD. |
| D0b-D0d | completed evidence `forbidden` | No repository calibration, quotient audit, or 13 V evaluation. |
| N0 contracts | `supported` implementation facts | Complete 1D states/residuals/closures/boundaries/ledgers exist; this is not trained accuracy or novelty. |
| N0 v1-v3r | `failed_but_informative`; positive forward `forbidden` | Port-only improvements coexist with failed PDE/field/flux/ledger gates; v3r strong-Wolfe becomes non-finite. |
| M33 mixed state-flux PINN | preflight `supported`; training `failed_but_informative` | `16/16` no-training checks pass; the sole 1500-step seed fails port, PDE, constitutive, interface, ledger, and no-regression gates. |
| M34 contract audit | implementation facts `supported`; authorization `failed_but_informative` | M33 used adaptive group-norm exact penalties, not signed/vector ALM. The preregistered all-nonzero derivative gate fails (`30/44`, max error `0.0918561`); no corrected run. |
| M34-A amendment | diagnostic fact `supported`; no scientific vote | `32/32` float64 group-normalized directions show stable parity and second-order Taylor behavior. Neither autograd-error nor scale-cancellation classification is supported; training remains unauthorized. |
| SID/EC-OQ | `failed_but_informative`; implementation inactive | Derivative `3/9`; event-window, stability, and dual-geometry gates fail. |
| CPCF | frontier `forbidden`; software audit `failed_but_informative` | All 48 votes are contract-non-equivalent proxy diagnostics, not scientific frontier evidence. |
| CEBA | parity `supported`; boundary `failed_but_informative` | `6/6` direct-solver anchors pass, but the pilot abstains before a bracket; oracle/grid-dependent refusal is not deployable. |
| Figure 5 | bundled result `qualified_supported`; isolated protocol gain `forbidden` | Waveform, duration, and calibration error vary together; configured prior width is unused. |
| SCIS | `failed_but_informative` | Pooled nominal coverage `0.93233`, but 2 K mismatch acceptance is `1.0` with point success `0.0`. |
| N1-N3 / SC-LOS | `forbidden` | Upstream trained-forward, public-solver, and geometry gates have not passed. |

## Distance to Delivery Goal

| Deliverable | Current state | Remaining gap |
| --- | --- | --- |
| Synthetic inverse mainline | constrained `gamma_sub` evidence locked | Integrate supported claims, figures, limitations, and reviewer defense into the manuscript |
| Public-data anchor | provenance/parity locked; M37R nominal window fixed but perturbation topology fails | Numerical/hybrid-event limitation only; no public rank, fit, lock, or 13 V evaluation |
| Full 1D PINN | complete versioned scaffold; trained paths fail | Retain scaffold/failure boundary; no neural search until an independently justified route exists |
| Sensitivity/quotient inverse | absent or rejected implementations | Requires public solver convergence, reliable PINN forward fidelity, and solver/PINN Jacobian agreement |
| Submission package | incomplete | Assemble only locked supported/qualified claims and explicit negative boundaries |

## Current Single Priority

Lock and run M40 E0 once. Preserve the constrained `gamma_sub` rank-1
synthetic mainline and every M35-M37R/P1/M33/M34 failure. If any M40 gate
fails, stop before M41, inverse, or PINN; no M38, fit, or 13 V access is active.

Compact routing: `docs/project_state/current_evidence_index.md`.
