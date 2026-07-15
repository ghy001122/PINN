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

Only a bounded N0 diagnostic is active. It must pre-register any repair before new training and separate collocation generalization, residual scaling/gradient conflict, endpoint/interface fluxes and sparse-port-anchor ablation. The frozen fields remain score-only. A failure retains the historical `gamma_sub` calibration-gated inverse as the safe mainline.
