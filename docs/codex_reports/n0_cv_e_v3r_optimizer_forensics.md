# N0-CV-E v3r Optimizer Forensics

Preregistered commit: `18b703a366663b83947e8b84143481a99854362a`.

## Historical b380 status

The historical result remains `failed_but_informative`, with the narrower substatus `runtime_abort_unassessed`; the absence of a scored trajectory is not scientific model falsification.

## Instrumented replay and operational audit

The first locked replay completed all `1200` Adam steps and persisted six stage checkpoints, but the new score-only face-flux routine raised a Python name-binding error before L-BFGS. That attempt is preserved separately rather than overwritten. A process-local binding of the already-declared `dx=L_eff/nx` then allowed the identical locked training replay to be scored; it changed no training input, loss, optimizer, formula, gate, or checkpoint semantics. Because this was a post-lock operational repair, the positive-claim ceiling remains `failed_but_informative`.

The primary replay then entered L-BFGS but its strict JSON telemetry serializer encountered an infinite diagnostic step norm before the crash manifest could retain the precise attribution. A serializer-safe diagnostic replay from the same pre-L-BFGS checkpoint, without changing the optimizer or scientific algorithm, reproduced the historical failure type at strong-Wolfe closure `3`. The first non-finite object was parameter `backbone.net.0.weight` in `backbone.net.0`; all six monitored loss blocks were non-finite at detection. The primary summary's `exact_b380_failure_reproduced=false` flag is therefore preserved as the literal main-driver record, while `outputs/tables/n0_cv_e_v3r_forensic_resolution.json` records the narrower diagnostic conclusion.

## Post-Adam scientific score

Parameters, gradients, Adam `exp_avg`, and Adam `exp_avg_sq` are finite. Total loss decreases from `1.5062737616896e13` to `2.665305088e9`, while the post-Adam block-gradient norm ratio remains `3.32508e20` and the minimum pairwise cosine is `-0.0795448`.

| Gate | Value | Locked threshold | Result |
| --- | ---: | ---: | --- |
| Port full-trace NRMSE95 | `0.0955475` | `<=0.10` | pass |
| `r_c` RMS | `0.0226501` | `<=0.01` | fail |
| `r_T` RMS | `56586.4844` | `<=0.01` | fail |
| `r_m` RMS | `4.07622` | `<=0.01` | fail |
| Discrete electrical RMS | `2.68241e-11` | `<=0.01` | pass |
| One-sided interface-state RMS | max `0.0181465` | `<=0.05` | pass |
| Interface current/heat/defect score | `0.0955475 / 33211.9341 / 23.8718` | each `<=0.05` | fail |
| Energy-ledger gate value | `0.9999502` | `<=0.05` | fail |
| Defect-ledger gate value | `1.0` | `<=0.01` | fail |
| IC/BC, finite outputs, bounded states | all true | all true | pass |
| Field NRMSE95 | `T 1.75274; c_v 0.380476; m 0.427650; phi 0.00661590; sigma 0.247621` | each `<=0.25` | fail |

Structural analytic current and shared-face conservation are reported as invariants and do not vote for learned performance. Interface state uses one-sided face reconstruction; interface flux is scored against frozen-GT face flux.

## Recovery decision

Decision: `no_recovery_stop`. Five quantities exceed their locked gates by at least `20x`: `r_T` (`5.66e6x`), `r_m` (`407.6x`), heat flux (`6.64e5x`), defect flux (`477.4x`), and defect ledger (`100x`). The prerequisite for either the float64 or gradient-statistics arm is therefore false. Neither recovery arm nor either expansion seed was run, and N0 optimizer work is permanently stopped under this authorization.

No hidden-field or port labels, public data, 13 V data, gate relaxation, `nan_to_num`, or post-hoc multi-factor tuning were used.

The allowed conclusion is limited to optimizer/root-cause localization and a negative trained-forward boundary. Reliable full-PINN forward fidelity, conservation, sensitivity fidelity, and inverse readiness remain forbidden.
