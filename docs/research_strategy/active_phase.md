# Active Phase

Active phase ID: `N0_CV_LEDGER_REFORMULATION_PREFLIGHT`

## Current Phase

`Q2 SCI delivery - solver-consistent full-PINN conservation preflight`

The bounded N0-R strong-form dual-domain repair is closed as `failed_but_informative`. Historical P0-P4, D0a, the original N0 failure, frozen GT v1.1, and all failed artifacts remain unchanged facts. A complete PINN remains an indispensable paper scaffold, but no positive trained-forward claim is available.

The calibration-gated constrained `gamma_sub` rank-1 result remains the safe `qualified_supported` inverse mainline while N0 is unresolved.

## Manuscript Use

Decide whether one solver-consistent control-volume or weak-form residual formulation is sufficiently specified to justify a final bounded N0 MVE. Its purpose would be to close the gap between locally normalized strong-form residuals and the required terminal-current, defect-mass, and global-energy ledgers. It is a numerical consistency repair, not an interface/cPINN/XPINN innovation claim.

## Closed N0-R Evidence

- Original contract and seed `20260715` 1200-epoch baseline were reproduced exactly. The pre-repair full suite reported `199 passed in 244.49s`.
- Four non-trivial manufactured cases pass. The reconstructed frozen FVM maximum normalized mass, energy, and current errors are at roundoff scale.
- The v1 full PINN reverses the frozen teacher's electrical boundary orientation. The frozen `nx=31` material mask places the arithmetic interface face `0.18 dx` from declared `L_int`.
- Controlled `nx=31 -> 63` solver-generated port NRMSE95 is `0.001225`; frozen GT was not modified.
- The preregistered split repair has `5704` parameters versus the `5812`-parameter baseline, exact one-sided state/current/heat/defect traces, hard teacher-compatible electrical boundaries, hard dynamic-state initial conditions, and physical conductivity closure.
- Seed `20260715` repair result: port `0.120358`; held-out `r_phi/r_c/r_T/r_m=0.006634/0.048286/0.027081/0.008616`; maximum field error `1.149469`; maximum exact-interface flux RMS `0.008965`; terminal-current error `0.519809`; global-energy imbalance `0.998556`.
- Sparse-port anchor was not run because residual/current/energy gates failed. Seed expansion was not run because the data-free pilot failed.
- N0 trained evidence remains `failed_but_informative`; reliable full-PINN forward evidence remains `forbidden`.

Primary report: `docs/codex_reports/n0_full_pinn_bounded_repair_v2_report.md`.

Machine summary: `outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json`.

## Single Active Bottleneck

Produce a no-training equation/config preflight for at most one solver-consistent N0 residual formulation. It must:

1. reuse fixed-point content SHA `80e34ca549d86588d12ffbcde4a304e378197dba602bcccc6e4e7d1ead932731`;
2. express face-current, heat, and defect fluxes with the frozen FVM arithmetic-face semantics or an explicitly quantified conservative alternative;
3. include terminal-current, defect-mass, and energy ledgers in the residual contract;
4. keep frozen full fields score-only and forbid port anchoring until all physics/conservation gates pass;
5. retain the existing seeds, matched budget, and unchanged operational gates.

No training is authorized merely by this status file. A new config and code/equation hash lock must precede any MVE.

## Stop And Claim Boundary

Do not re-tune the completed strong-form branch. If a solver-consistent residual cannot be specified without changing frozen GT or relaxing gates, stop N0 training and preserve the negative result in the manuscript.

SC-LOS and N1-N3 remain blocked. Allowed wording is limited to the supported teacher-equation audit, the supported exact-trace implementation fact, and the failed trained-forward boundary. Reliable full-PINN forward evidence, sensitivity fidelity, quotient inverse recovery, protocol-dependent identifiability, independent external validation, and experimental validation remain `forbidden`.
