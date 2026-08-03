# Controller-Relevance Final Forward Rescue — Terminal Report

## Executive disposition

```text
B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL
route = STOP_FINAL_FORWARD_SOLVER_RESCUE
scientific_vote = false
formal_execution_count = 0
```

The sole safeguarded-Anderson identity passed the two fixed controller
qualification states and the complete 12.5 V matched event window. It did not
preserve the frozen 9 V reversal direction/order sequence relative to NLS-v1.
The 9 V NLS-v1 window published 417 reversal records, whereas Anderson
published 364; the first direction mismatch occurs at zero-based index 11.
The B3 correctness gate therefore fails validly. Performance timing, B4,
fresh S0, Phase 2, C01, C06, and manuscript-result execution were not started.

This is a numerical-method consistency failure. It is not an S2 physical
failure, a Phase 1 scientific vote, a PINN result, Qiu quantitative
reproduction, or experimental validation.

## Contract and identity

- Task: `Q2_CONTROLLER_RELEVANCE_FINAL_RESCUE_TO_S0_C01_R1`.
- Execution base: `main@1c9758ef151299a4694b4edcc81dd48feec704ba`.
- Branch: `codex/controller-relevance-final-forward-rescue`.
- Anderson implementation anchor: `a43512a194f4e1ad99574effea8a72389f0fc1ae`.
- B3 execution anchor: `b4ab75df75fe254e1366db896336559fa8f52ea7`.
- Reporting-only metric repair: `58cba765f8111f20d7455879c325039d08a1788f`.
- Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

Frozen D0, exact-condensed v1, NLS-v1, controller-v2, S2 equations and
parameters, protocols, scientific gates, equivalence-v1/v2/v3, and Frozen GT
were not modified or rerun.

## R0–R2 result

| Stage | Result | Core evidence | Route |
| --- | --- | --- | --- |
| R0 | nonlinear floor failure for the real 9 V state; 12.5 V fixture accepted | Exact-condensed v1 reached the active floor with full defect `1.8387e-8`; no non-solver gate failed | R1 |
| R1 | `R1_CONTRACTION_PASS_R2_AUTHORIZED` | last-four geometric-mean defect ratio `0.4995588`; step-8/initial defect `0.0038959`; spectral radius `0.5000018`; max power norm `0.5000018` | R2 |
| R2 | `R2_CONTROLLER_ADMISSIBLE_QUALIFICATION_PASS` | real 9 V accepted at `0.625 ns`; critical fixture accepted at `0.15625 ns`; all root/integrity/ledger gates pass | B3 |

R0 invocation V1 failed before scientific work because an unpublished CSV
contained nested mappings. B3 invocation V1 failed before its first worker
because the Windows process handle was truncated by default `ctypes` typing.
Both are preserved as invalid, non-voting execution provenance. Their narrow
writer/WinAPI repairs did not alter a scientific metric or solver rule.

## B3 matched-window result

### 9 V quiescent window

The common initial state is NLS-v1's last accepted full state at
`17.06015625 us`; the relative window is `0.5 us` with 101 fixed output
samples.

| Metric | NLS-v1 | Safeguarded Anderson | Gate/result |
| --- | ---: | ---: | --- |
| Local window integrity | PASS | PASS | PASS |
| Accepted steps | 794 | 412 | telemetry |
| Rejected steps | 4 | 25 | telemetry |
| Controller growth events | 0 | 23 | candidate `>=1`: PASS |
| Fallback steps | 794 | 0 | candidate `=0`: PASS |
| Terminal-current NRMSE | — | `3.8932776e-4` | `<=0.01`: PASS |
| Device-voltage NRMSE | — | `8.1404015e-5` | `<=0.005`: PASS |
| Event sequence | upward | upward | PASS |
| Event absolute error | — | `4.5865687e-10 s` | `<=50 ns`: PASS |
| Reversal records | 417 | 364 | exact sequence: **FAIL** |

The first reversal direction mismatch is NLS-v1 `cooling_to_heating` versus
Anderson `heating_to_cooling` at zero-based index 11. This alone is sufficient
to stop B3.

### 12.5 V transition window

The sole locator found an upcrossing at `1.1010421196 us` and a downcrossing at
`1.9787850088 us`. The frozen matched window is
`[1.0510421196 us, 2.0 us]`.

| Metric | Result | Gate |
| --- | ---: | ---: |
| Terminal-current NRMSE | `1.1501689e-6` | `<=0.01` |
| Device-voltage NRMSE | `1.4570175e-7` | `<=0.005` |
| Maximum event error | `1.3388475e-12 s` | `<=50 ns` |
| Maximum relative event error | `6.7661680e-7` | `<=0.01` |
| Reversal direction/order | 5 versus 5, exact | required |
| Candidate growth/fallback | 10 / 0 | growth observed; no fallback |

All 12.5 V correctness gates pass. This does not override the 9 V failure.

## Reporting-only evaluator repair

The first B3 summary compared fixed times by bitwise equality. The two 9 V
grids differed by at most `2.3852448e-18 s`, within the production dense-output
tolerance, so the initial report incorrectly replaced the port NRMSE values
with a finite rejection penalty. The original summary/table were preserved;
the metrics were recomputed from the immutable worker JSON without rerunning
any solver. The repaired port metrics pass, while the reversal failure and
terminal disposition remain unchanged.

## Budget and commands

- B3 aggregate CPU: `312.703125 s / 10800 s`.
- B3 wall time: `822.772771 s`.
- Performance warm-up and three alternating timing repetitions: not executed.
- B4 aggregate CPU: `0`.
- Fresh S0 formal count: `0`.
- GPU hours: `0`.

Core execution commands:

```powershell
.\.venv\Scripts\python.exe scripts\run_geophase_controller_relevance_final_rescue.py --stage r0 --config configs\geophase_controller_relevance_final_rescue.yaml --output-root outputs\tables\geophase_controller_relevance_final_rescue\R0-CONTROLLER-RELEVANCE-20260804-V2
.\.venv\Scripts\python.exe scripts\run_geophase_controller_relevance_final_rescue.py --stage r1 --config configs\geophase_controller_relevance_final_rescue.yaml --output-root outputs\tables\geophase_controller_relevance_final_rescue\R1-CONTRACTION-20260804-V1
.\.venv\Scripts\python.exe scripts\run_geophase_controller_relevance_final_rescue.py --stage r2 --config configs\geophase_controller_relevance_final_rescue.yaml --output-root outputs\tables\geophase_controller_relevance_final_rescue\R2-ANDERSON-QUALIFICATION-20260804-V1
.\.venv\Scripts\python.exe scripts\run_geophase_controller_relevance_final_rescue.py --stage b3 --config configs\geophase_controller_relevance_final_rescue.yaml --output-root outputs\tables\geophase_controller_relevance_final_rescue\B3-MATCHED-WINDOW-20260804-V2
.\.venv\Scripts\python.exe scripts\run_geophase_controller_relevance_final_rescue.py --stage b3-recompute --config configs\geophase_controller_relevance_final_rescue.yaml --output-root outputs\tables\geophase_controller_relevance_final_rescue\B3-MATCHED-WINDOW-20260804-V2
```

Focused implementation/regression tests: `19 passed`; final current-route
assertion repair: `4 passed`.

Final repository closure checks:

- fast-checkout governance: no failed checks;
- tracked JSON: `340/340` parsed;
- current historical evidence checks: `20/20` passed;
- Frozen GT: `8/8` hashes unchanged.

## Lifecycle and claim gate

| Object | Lifecycle | Claim status | Allowed wording |
| --- | --- | --- | --- |
| R1 contraction audit | `numerically_validated` | `qualified_supported` | The named floor-terminal map is contractive under the frozen local audit. |
| Safeguarded Anderson R2 | `numerically_validated` | `qualified_supported` | The sole identity forms certified controller bundles at the two fixed R2 states. |
| B3 matched windows | `numerically_validated` | `failed_but_informative` | 12.5 V consistency passes; 9 V reversal topology does not. |
| B4/fresh S0 | `planned` / not executed | `forbidden` | No cost, full-trajectory, campaign, or physical-judge result. |
| Phase 2/C01/C06 | `planned` / not executed | `forbidden` | No data, training, baseline, OOD, or positive PINN evidence. |

## Current boundary and next recommendation

The final forward-solver rescue is stopped. Do not tune reversal detection,
change the window, relax topology, add a second solver, run B4/S0, or generate
training data under this task.

The only reasonable next decision is whether to authorize a separate C04
observable-subspace plus constrained `gamma_sub` calibration and
identifiability-boundary manuscript. It is worth considering as an honest
contingency paper because the 2.5D positive-PINN route remains blocked after
the final bounded rescue; it cannot be presented as the intended 2.5D R1
result and is not executed here.

## Evidence paths

- Machine summary: `outputs/tables/geophase_controller_relevance_final_rescue/B3-MATCHED-WINDOW-20260804-V2/b3_summary.json`.
- Terminal addendum: `outputs/tables/geophase_controller_relevance_final_rescue/B3-MATCHED-WINDOW-20260804-V2/b3_terminal_addendum.json`.
- Comparison table: `outputs/tables/geophase_controller_relevance_final_rescue/B3-MATCHED-WINDOW-20260804-V2/b3_comparisons.csv`.
- Raw worker payloads: `outputs/tables/geophase_controller_relevance_final_rescue/B3-MATCHED-WINDOW-20260804-V2/workers/`.
- Preserved pre-repair summary/table: the matching `*.pre_metric_repair.*` files.
