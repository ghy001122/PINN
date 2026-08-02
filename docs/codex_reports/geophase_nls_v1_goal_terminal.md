# NLS-v1 Goal Terminal Report

## Conclusion

`GOAL_UNSUCCESSFUL_NLS_V1`

The NLS-v1 dual-gate correctness repair succeeded on both frozen nonlinear failure states, but the required standard 9 V qualification trajectory did not complete within its frozen six-hour per-run budget. Fresh S0, Phase 2, C01, C06, baselines, OOD evaluation, figures, and positive PINN manuscript evidence were not executed.

This is valid bounded numerical-method performance evidence. It is not an S2 physics PASS/FAIL and casts no scientific vote.

## Task Contract

- Base: `main@42e16ff7b9abd34b5ce7272eaa74ad60d49348d3`.
- Initial NLS anchor: `ee07846b89280fafdac18166f02ff688d8d92f58`.
- Immutable result evidence: `f3b7db17126c5591569cb98839a2df3211b1fef9`.
- Goal: repair the shared nonlinear solve, qualify complete standard/strict trajectories, then conditionally run fresh S0 and C01/C06.
- Frozen: S2 equations/parameters, protocols, controller-v2, `1e-8` residual and defect gates, ledger/event gates, 63/60/3 plan, historical evidence, and Frozen GT v1.1.
- NLS qualification budget: 8 active implementation/diagnosis hours, 24 aggregate CPU-hours, and 21600 seconds per qualification run.
- Prohibited: controller candidate 3/controller-v4, equivalence-v4/v5, relaxed gates, S0 bypass, and downstream PINN before a complete valid S0 PASS.

## Root Repair Result

The prior fallback could stop on a relaxed Picard increment without simultaneously satisfying the returned full fixed-point defect and scaled residual. NLS-v1 now records both quantities and returns success only when both are at most `1e-8`; Newton/Krylov/Armijo failures remain in structured telemetry.

The two immutable controller-v3 failure states both pass the corrected fallback:

| Replay | Iterations | Scaled residual | Full defect |
| --- | ---: | ---: | ---: |
| V2 failure state | 6 | `4.884209208104767e-9` | `5.008622738778001e-9` |
| V4 failure state | 4 | `5.853515129323472e-9` | `4.958286003997614e-9` |

The 200-iteration fallback was not enabled. The goal allowed Schur reduction only if these two frozen states could not pass in budget; that trigger was false, so Schur was not activated.

## Qualification Execution

One external launch was terminated before a long run was published and is retained as zero-vote host provenance. The canonical `NLSV1-QUAL-20260802-V1` invocation then produced the following bounded evidence.

### Standard quiescent 9 V T1

- Requested endpoint: `20 us`.
- Achieved endpoint: `17.060156249987655 us`.
- Output timestamps: 3413/4001.
- Wall time: `27136.618757699965 s`.
- Frozen per-run limit: `21600 s`.
- Stop reason: `maximum_wall_clock_reached`.
- Accepted steps: 61932; fallback steps: 61383 (`99.1135%`).
- Maximum scaled residual: `9.996601032876059e-9`.
- Maximum full defect: `9.998639027841705e-9`.
- Finite values and the observed current/power/ledger quantities remained within their local gates, but the trajectory was incomplete and therefore failed qualification.

The overrun ratio was `1.2563249424861096`; completion, timestamp, final-landing, and per-run performance gates all failed. This exact required path is sufficient to reject NLS-v1 qualification under the frozen budget without extrapolating a general S0 campaign feasibility claim.

### Strict quiescent 9 V T4

The strict path reached within `1.73133534418779e-17 s` of the requested endpoint. Its full NLS solve passed (`1.2596776847781368e-9` residual, `3.1042358683563975e-9` defect), but the solver attempted a numerically meaningless sub-floor remainder whose near-zero ledger ratios failed integrity.

The solver and evaluator now share the preregistered `1e-12` relative landing tolerance under the new identity `phase1_s2_dual_gate_nonlinear_solver_v1p1_endpoint_tolerance`. The regression proves a state already within that tolerance completes without invoking another nonlinear step.

## Why There Was No Long V2 Rerun

The endpoint correction only changes behavior within final-time tolerance. Standard T1 stopped roughly `2.94 us` before the endpoint, so its path and frozen wall-time rejection occur before the correction can act. Repeating that multi-hour run cannot satisfy the required qualification gate and would violate the goal's fail-fast efficiency policy.

Accordingly, V2 was versioned and statically/regression validated but not invoked as a full qualification. This is not a hidden PASS: `all_required_gates_pass=false` and the goal terminates unsuccessful.

## Disposition And Manuscript Impact

- NLS-v1 qualification: `failed_but_informative` bounded numerical-performance evidence.
- Fresh S0/Phase 1: `forbidden` / unassessed.
- `scientific_vote=false`; `formal_execution_count=0`.
- Phase 2, MLP, vanilla PINN, C01, C06, geometry/protocol OOD, and R1/R2/R3: not executed and `forbidden`.
- No new Methods/Results scientific claim or main paper figure is supported.

Allowed reviewer-defense use: the dual-gate root correction, exact frozen replay results, exact standard-trajectory budget boundary, and the endpoint-tolerance defect/correction.

Forbidden wording: S2 failed physically; Phase 1 failed scientifically; the full campaign is generally infeasible; PINN/C01 failed; Qiu was reproduced; or any experimental validation claim.

## Validation And Evidence

- Focused NLS tests: `11 passed`.
- Machine summary: `outputs/tables/geophase_nls_v1/nls_v1_terminal_summary.json`.
- Raw local qualification evidence: `outputs/tables/geophase_nls_v1/qualification/NLSV1-QUAL-20260802-V1/`.
- Standard run artifact SHA-256: `ca311b396567c5682b0fb310049e5539e75121bdf43678ad2660b4ffc9c5b053`.
- T4 failure SHA-256: `698a44460ca13d4a4c13efd137d276992bb83836d4395631fae567c5c93eb776`.
- Frozen controller failure source hashes remain unchanged.

## Next Scientific Bottleneck

The next useful task is not PINN and not another controller policy. A future newly authorized goal may evaluate a performance-oriented, mathematically equivalent reduced nonlinear solver against the same full standard/strict trajectories and all unchanged physical gates. It must use a new identity and cannot be described as resuming or retrying this NLS-v1 qualification.
