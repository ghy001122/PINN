# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `D_PUBLIC_SOLVER_CONVERGENCE_RESOLUTION`.
- Frozen GT v1.1: unchanged and read-only.
- Safe inverse mainline: constrained `gamma_sub`, calibration-gated rank-1, `qualified_supported` only under locked synthetic conditions.
- Full PINN: mandatory architecture/paper scaffold; every bounded trained-forward route remains `failed_but_informative`, so sensitivity/inverse claims are `forbidden`.
- Public VO2: M35 D-PREG passes `21/21` checks. D-FIT stops at solver convergence after 8 open-data solver evaluations. No Jacobian, fit, multistart, fit lock, or 13 V access occurred.
- Project-generated experimental validation: absent.

## Current Gate Ledger

| Gate | Status | Direct boundary |
| --- | --- | --- |
| Frozen GT v1.1 | `supported` integrity baseline | Equations, parameters, arrays, and acceptance files unchanged. |
| P0 / P3 | `qualified_supported` | Reduced synthetic semantics; P3 is only a static pure-electrical three-parameter local-rank result. |
| P1 / P2 | `failed_but_informative` | P1 retains `E_T=0.37563055753707886` and interface residual `106.15460205078125`; P2 thermal/material-block identifiability remains unresolved. P1 is required only for multidomain/interface claims. |
| P4 | `forbidden` | No full STL or universal Fourier/F-SPS superiority. |
| D0a | `failed_but_informative` | Source/SI parity passes; time-step NRMSE95 `0.163148 > 0.01`. |
| M35 D-PREG | `supported` protocol/provenance fact | R-T and 9/11/15/17 V hashes, roles, equations, units, licenses, metrics, LOVO, eight starts, stop rules, and 13 V sealing are locked. Not fit evidence. |
| M35 D-FIT | `failed_but_informative`; refit `forbidden` | All four open voltages fail locked 5 ns versus 2.5 ns current/voltage NRMSE gates. Activity class, frequency, charge, and energy pass. Fit stops before Jacobian/optimization; no fit lock exists. |
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
| Public-data anchor | provenance/protocol locked; dynamic convergence fails | Establish a defensible event-aware solver reference before any public fit; 13 V stays sealed |
| Full 1D PINN | complete versioned scaffold; trained paths fail | Retain scaffold/failure boundary; no neural search until an independently justified route exists |
| Sensitivity/quotient inverse | absent or rejected implementations | Requires public solver convergence, reliable PINN forward fidelity, and solver/PINN Jacobian agreement |
| Submission package | incomplete | Assemble only locked supported/qualified claims and explicit negative boundaries |

## Current Single Priority

Preregister one solver-only convergence-resolution audit for the public compact model. Separate near-zero-range normalization at quiescent 9/17 V from event-time dephasing at oscillatory 11/15 V; compare finer fixed steps with an independent event-resolved/adaptive reference; lock instrument-scale absolute floors before inspecting results. Preserve M35 as failed, require raw-time waveform convergence, use event alignment only diagnostically, and do not fit, train, or access 13 V.

Compact routing: `docs/project_state/current_evidence_index.md`.
