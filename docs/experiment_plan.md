# Experiment Plan

## v2 Scientific Hypothesis

Public VO2 terminal observations may identify physical-timescale quotients or equivalence classes rather than unique raw parameters, and phase branch/drive protocol may change the observable quotient. A complete phase-transition PINN should infer only supported coordinates and refuse unsupported raw recovery.

This remains an untested hypothesis because upstream gates failed.

## Executed Stage Chain

| Stage | Execution | Result | Stop consequence |
| --- | --- | --- | --- |
| D0a exact-source reproduction | 6 forward evaluations; author code, SI rewrite, R-T and 11 V no-fit checks | `failed_but_informative`: 5-to-2.5 ns NRMSE95 `0.163148 > 0.01` | D0c-pre/D0b/D0c-post/D0d not run; 13 V remains sealed |
| N0 contract audit | architecture, hard IC/electrical BC, manufactured equilibrium | preflight passed | allowed one fixed-seed training MVE |
| N0 160-epoch pilot | one CPU seed | gate failed; finite/physical | expanded epochs only because 1200 was fixed before results; no seed expansion |
| N0 1200-epoch MVE | same config and seed | `failed_but_informative`; port and all residual gates fail | N1-N3 not run |
| N0 v3r instrumented replay | 1200 Adam steps plus same-checkpoint strong-Wolfe diagnostic | port passes, five physics/ledger metrics exceed `20x`; optimizer non-finite localized | this N0 optimizer route stopped; no recovery/seed expansion |
| Solver-first SID/EC-OQ | `189` forward evaluations, `36` cases, fixed event windows | `failed_but_informative`; derivative `3/9`, window/stability/dual-geometry gates fail | current implementation rejected/inactive; broader hypothesis requires a new authorized contract |
| CPCF bounded pilot | `48` cases, `12` operating points, `8` fresh solver anchors | `failed_but_informative`; only gate b passes | full sweep stopped; supplementary decision table only |

## Preserved Pre-registration

- D0a budget: 60 forward evaluations; actual 6.
- N0 seeds: `20260715`, `20260716`, `20260717`; only the first was run because the MVE failed.
- N0 positive gate: at least 2/3 seeds, port NRMSE95 `<=0.10`, all four residual RMS values `<=0.01`, finite physical states.
- No thresholds were relaxed; failed seeds and both pilot/full-epoch traces are retained.
- Frozen GT equations, parameters and arrays are unchanged.
- 13 V was not numerically opened; no `fit_lock.json` exists.

## Blocked Stages

D0b-D0d are blocked by D0a. N1 independent solver sensitivity, N2 PINN sensitivity fidelity and N3 conditional quotient inverse are blocked by N0. Their configs, scripts and result files are intentionally not fabricated as placeholders.

## Active Next Experiment

No scientific experiment is active. The single project action is manuscript/submission assembly from the locked calibration-gated `gamma_sub` evidence and the D0/N0/SID/CPCF failure boundaries. N0 retraining, CPCF expansion, D0/13 V, and SID/EC-OQ reopening are not authorized.

The highest-value future research gate is a provenance-backed branch-resolved thermal-data feasibility audit before any H1 latent-heat or H2 history-state MVE. H3 two-dimensional geometry remains blocked until a one-dimensional structural error is demonstrated. These are registry items, not an execution queue.
