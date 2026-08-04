# NLS Reference Time-Convergence Closure v2 — Terminal Report

## Verdict

```text
STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4
```

The single authorized T4 run completed validly. Root/integrity, transition
event, and fixed-grid signed I–Vd loop gates passed, but the frozen prospective
time-convergence gate failed. T8, the selected-level 9 V check, held-out
continuation, and cost profiling were therefore not unlocked.

This is `failed_but_informative` numerical-method evidence with
`scientific_vote=false` and `formal_execution_count=0`. It is not an S2,
Phase 1, C01/C06, or PINN scientific failure.

## Task Contract

- Base: `main@4f98ed5e16ce7a0645a51f83d19ae97414c4c185`.
- Anchor: `38b4d692473bd1ecfe0c7277810e924622b1f7ee`.
- Contract SHA-256:
  `ce3ffe36f1f80749a08cf3a5f8eeb9b033a61e78c3d314687d1e3a9baa1f39fc`.
- Historical PR #27 T1/T2 JSON/NPZ artifacts were hash-verified and not rerun.
- The physical coordinates, thresholds, Richardson rules, T8 overlay,
  held-out window, and cost rules were frozen after PR #27 diagnosis and before
  observing T4. They were not preregistered before PR #27.
- NLS-v1, controller-v2, S2, production configuration, protocols, historical
  evidence, and Frozen GT were unchanged.

## Actual Execution

One new worker ran the frozen 12.5 V transition window
`[1.0510421196050138e-6, 2.0e-6] s` at L1/T4 with 5 ns outputs.

| Quantity | Value |
| --- | ---: |
| Completed outputs | 191/191 |
| Accepted steps | 394 |
| Fallback steps | 13 |
| Worker wall time | 157.2066676 s |
| Worker CPU time | 66.296875 s |
| Stage wall time | 163.0175213 s |
| Upward event | 1.1020587747340847 μs |
| Downward event | 1.9813235947710857 μs |

## Frozen Voting Metrics

Here `E12` compares T1/T2, `E24` compares T2/T4, `p` is the observed order,
and `e_hat` is the conservative fine-level Richardson estimate.

| Metric | E12 | E24 | p | e_hat | Limit | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| T RMSE (K) | 0.168047763 | 0.088502309 | 0.925084 | 0.098467710 | 0.05 | FAIL |
| T P95 (K) | 0.387560989 | 0.205411861 | 0.915904 | 0.231645537 | 0.10 | FAIL |
| T terminal P95 (K) | 0.028742964 | 0.039808381 | -0.469863 | fail-closed | 0.10 | FAIL nonmonotonic |
| Tc(b) RMSE (K) | 0.051005163 | 0.087406874 | -0.777103 | fail-closed | 0.025 | FAIL nonmonotonic |
| log sigma RMSE | 0.012423904 | 0.014440350 | -0.216987 | fail-closed | 0.005 | FAIL nonmonotonic |
| Current NRMSE | 0.019773228 | 0.010159244 | 0.960755 | 0.010735430 | 0.01 | FAIL |
| Vd NRMSE | 0.009026509 | 0.004626619 | 0.964210 | 0.004865032 | 0.005 | PASS |

Only one of seven continuous voting metrics passed its final fine-error gate.
Three metrics were nonmonotonic, so the T8 unlock condition was not met.

## Supplemental Coordinates

Raw `s` and `b` remain non-voting. For T2/T4, their RMSE values were
`0.0029026267` and `0.0242796872`; maximum absolute differences were
`0.0617251265` and `0.5846858356`. The derived `Tc(b)` and production
white-box `log(sigma)` coordinates remained voting and exposed the
nonmonotonic refinement.

## Evidence And Claim Boundary

- Lifecycle: `numerically_validated`.
- Claim status: `failed_but_informative`.
- Evidence: `literature-guided synthetic numerical digital-twin evidence`.
- Supported: this frozen T1/T2/T4 NLS reference sequence is not demonstrably
  asymptotic under the prospective physical-coordinate closure contract.
- Forbidden: selecting divisor 4 or 8 as GT; running T8, held-out, cost,
  sentinel, B4b, fresh S0, Phase 2, C01/C06, or asserting S2/PINN failure.

## Validation And Artifacts

- Focused regression before T4: `11 passed`.
- Machine summary:
  `outputs/tables/geophase_nls_time_convergence_v2/runtime_machine.csv`.
- Voting table:
  `outputs/tables/geophase_nls_time_convergence_v2/development/development_richardson_metrics.csv`.
- Atomic worker and full fields:
  `outputs/tables/geophase_nls_time_convergence_v2/development/workers/`.
- Machine terminal summary:
  `outputs/tables/geophase_nls_time_convergence_v2/terminal_summary.json`.

The only valid next decision is external to this stopped task: decide whether
to preserve the 2.5D solver work solely as a numerical limitation result or
open a separately contracted manuscript route. No further time-discretization
or solver rescue is authorized by this evidence.
