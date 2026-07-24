# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_GEOPHASE_E0_REFERENCE_SOLVER_FOUNDATION`.
- The user explicitly authorized a core-line change from the locked 1D
  submission route to a positive `GeoPhase-OQ-PINN` research route.
- The target physical model is a Qiu-inspired VO2 coplanar x-y device with
  vertical K-state thermal memory (2.5D); Chen-inspired SnSe/NbO2 is auxiliary
  material-specific cross-model numerical validation.
- Frozen GT v1.1 is unchanged and read-only. The constrained `gamma_sub`
  result remains a `qualified_supported` historical low-dimensional baseline.
- No x-y K-state reference solver, transition-localized GeoPhase network,
  positive GeoPhase training, sensitivity-fidelity result, observation-
  quotient inverse, refusal model, or NbO2 cross-model result currently exists.
- All project-generated data remain synthetic numerical digital-twin evidence;
  no project experimental validation exists.
- The previously validated manuscript v2 content package is retained as a
  historical technical fallback, not the selected current manuscript.
- Historical statements that permanently closed additional 1D PINN training
  apply only to their named N0/M33 contracts. They do not close the distinct
  GeoPhase G0--G5 route, which remains sequential and fail-closed.

## Active Route Gate Ledger

| Gate | Status | Direct boundary |
| --- | --- | --- |
| G0 2.5D independent reference | `forbidden` as a positive result; preregistration fact `supported` | Equation and YAML contracts exist after route activation; solver implementation and every manufactured/conservation/convergence/reduction gate remain pending. |
| G1 GeoPhase forward PINN | `forbidden` | Cannot start until G0 passes. Field, port, event, interface, and ledger gates must pass jointly. |
| G2 localized experts/homotopy | `forbidden` | Transition-localized MoE and joint phase/Joule homotopy are not implemented or compared under matched budgets. |
| G3 geometry generalization | `forbidden` | No locked x-y geometry split or held-out result exists. |
| G4 OQ/sensitivity/refusal | `forbidden` | Solver-first quotient geometry, PINN sensitivity fidelity, fresh-case inverse, and refusal are unrun. |
| G5 SnSe/NbO2 cross-model | `forbidden` | No material-specific cross-model run exists; zero-shot transfer is outside scope. |

## Retained Historical Evidence

| Gate | Status | Direct boundary |
| --- | --- | --- |
| `gamma_sub` inverse | `qualified_supported` | Frozen 1D synthetic rank-1 inverse under fixed/tightly bounded microphysics and calibration; not a measured material constant or final device model. |
| P0 / P3 | `qualified_supported` | Reduced synthetic semantics; P3 is a static three-parameter local-rank result, not arbitrary 2D field recovery. |
| P1 / P2 | `failed_but_informative` | P1 retains `E_T=0.37563055753707886` and interface residual `106.15460205078125`; P2 full thermal/material identifiability remains unresolved. |
| P4 | `forbidden` | No full STL reproduction or universal Fourier/F-SPS superiority. |
| Complete 1D PINN | Contracts `supported`; trained paths `failed_but_informative` | Operator/manufactured checks exist, but no bounded training route passes port, field, PDE, flux, and ledger gates jointly. |
| M40/M40R Qiu x-z bridge | `failed_but_informative` | Reusable source and implementation lessons only; no M41, Qiu calibration, or x-y/2.5D quantitative inheritance. |
| M44 historical 3D bridge | `failed_but_informative` historical/non-voting | Rolled back from live code; do not repair, revive, or cite it as a current device-grade solver. |
| Public Qiu/Zhang source routes | Mixed source/parity facts plus `failed_but_informative` stops | No positive quantitative external validation, fit lock, 13 V result, or author-code equivalence. |
| Historical submission replay | implementation/reproducibility fact `supported` | Local assets `50/50`, portable locks `157/157`, and detached tests `440/440` describe the retired v2 package and do not support GeoPhase claims. |

Detailed historical paths remain routed by
`docs/project_state/current_evidence_index.md`; cumulative history remains in
the registries and Git.

## Live Workspace Capability Audit

| Capability | Reuse decision |
| --- | --- |
| Qiu geometry, circuit, source provenance | Reuse source facts and engineering-prior labels; do not inherit x-z results as x-y validation. |
| Conservative FVM, face flux, RC, ledgers | Adapt implementation patterns into a new independent solver module. |
| VO2 and NbO2 closures | Reuse only after checking state semantics and units; keep material kernels separate. |
| Fourier/CV/interface/PINN utilities | Baselines or components only; no novelty or performance status transfers. |
| SVD/principal-angle utilities | Reuse after solver derivative convergence; historical failed SID/EC-OQ does not prove the new quotient hypothesis. |
| K-state vertical thermal memory | Not implemented in live `main`; build and test from the new contract. |

## Distance To Delivery Goal

| Deliverable | Current state | Remaining gap |
| --- | --- | --- |
| 2.5D physical foundation | Equation/config contract activated | Implement and pass all E0 gates. |
| Positive PINN method | Candidate architecture only | G1/G2 implementation, fair baselines, multiple seeds, and joint physical gates. |
| Generalization | Design only | Locked within-family geometry/protocol holdouts and no-refit evaluation. |
| Identifiability-gated inverse | Historical tools/negative evidence only | G4 solver geometry, sensitivity fidelity, fresh nonlinear inverse, and refusal. |
| Cross-model evidence | Literature motivation only | Separate SnSe/NbO2 kernel and trend-gated numerical validation. |
| Manuscript | Historical v2 retained | New evidence-selected draft, figures/tables, claim matrix, SI, and reviewer defense. |

## Current Single Priority

Implement and validate the config-locked G0/E0 independent 2.5D reference
solver. Do not begin GeoPhase training or downstream G1--G5 work until every
required E0 gate passes and the result report explicitly authorizes E1.
