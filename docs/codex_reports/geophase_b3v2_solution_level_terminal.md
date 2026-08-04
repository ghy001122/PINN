# B3v2 Solution-Level Validity Terminal Report

## Verdict

```text
STOP_REFERENCE_NOT_TIME_REFINED
selected_gt_solver = none
validity = valid
lifecycle_state = numerically_validated
claim_status = failed_but_informative
scientific_vote = false
formal_execution_count = 0
```

The frozen NLS-v1 reference did not pass its own T1-versus-T2 solution-level
time-refinement gate in the 12.5 V transition window. The task therefore
stopped before Anderson development, the one held-out unlock, B4a, B4b, fresh
S0, Phase 2, C01, C06, or manuscript-result execution. This is bounded
numerical-method evidence, not a vote on S2 physics or PINN validity.

Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

## Seven-Item Plan Closure

| Item | Terminal status | Result |
| --- | --- | --- |
| 1. Authority and contract | completed | Started from `main@51898e4406916b3675cb74f4888bf3986e0c76a1`; frozen inputs verified. |
| 2. Passive recorder, metrics, tests | completed | Common-time full-field capture and solution-level evaluator implemented; recorder parity tests pass. |
| 3. NLS development and reference envelope | completed | Four valid NLS workers executed; reference self-refinement gate failed at 12.5 V. |
| 4. Anderson development | forbidden/not executed | Blocked by the mandatory NLS-reference gate. |
| 5. Held-out unlock | forbidden/not executed | No solver was eligible for the single unlock. |
| 6. B4a cost projection | forbidden/not executed | No selected ground-truth solver. |
| 7. Evidence, claims, and Git closure | completed | Terminal evidence and route state frozen; no downstream execution. |

## Execution And Results

All four workers were valid, passed their local root/integrity gates, and
captured lossless full fields on a common physical-time grid. The adaptive-path
reversal records were preserved only as supplemental, non-voting telemetry.

| Regime | Pair | Result |
| --- | --- | --- |
| 9 V quiescent | NLS T1 vs T2 | Field metrics and current/voltage NRMSE are exactly zero; reference gate passes. |
| 12.5 V transition | NLS T1 vs T2 | Field and port gates fail; event topology/timing gate passes. |

### 12.5 V field refinement

| Field | RMSE | RMSE gate | P95 | P95 gate | Terminal P95 | Terminal gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Temperature (K) | `0.1680477625` | `0.05` | `0.3875609889` | `0.10` | `0.0287429643` | `0.10` |
| Conductive state | `0.00255163054` | `0.0005` | `0.00489949009` | `0.001` | `0.00145960668` | `0.001` |
| Branch memory | `0.01416810089` | `0.0005` | `0.00142864341` | `0.001` | `0.00378615412` | `0.001` |

Maximum absolute discrepancies, reported but not used as gates, were
`0.3990236591 K`, `0.00852068774`, and `0.1732535284`, respectively.

### Port, event, and trajectory diagnostics

| Metric | 9 V | 12.5 V | Gate |
| --- | ---: | ---: | ---: |
| Terminal-current NRMSE | `0` | `0.01977322760` | `<=0.01` |
| Device-voltage NRMSE | `0` | `0.00902650893` | `<=0.005` |
| Macro-event count | `1/1` supplemental | `2/2` | Transition only: exact count/direction/order |
| Maximum event-time absolute error | n/a | `6.687642997e-10 s` | `<=5e-8 s` |
| Maximum event-time relative error | n/a | `0.0006073848685` | `<=0.01` |

The 9 V macro crossing is retained in the raw/common-grid record but is not an
NLS self-refinement vote under this contract. An aggregation-only correction
made that scope explicit; no solver or worker was rerun, and all pre-correction
aggregate files were preserved under `development/pre_contract_repair/`.

Trajectory total variation at 12.5 V changed from `41.17580452` to
`41.97118017` for temperature, `1.038267376` to `1.043451782` for conductive
state, and `2.425252035` to `2.426102435` for branch memory. The normalized
loop areas were `0.6366251842` versus `0.6476644992` for I-Vd and
`0.2854388338` versus `0.2877210890` for s-T.

## Budget And Commands

- Development wall time: `757.4825843 s`.
- Aggregate CPU time: `401.453125 s`.
- Both remain below the frozen `4 h` wall and `12 CPU-hour` limits.
- Worker thread variables were fixed to one for OpenMP, OpenBLAS, MKL,
  NumExpr, and vecLib.

Executed scientific command:

```powershell
.\.venv\Scripts\python.exe scripts\run_geophase_b3v2_solution_level.py --stage development-nls --config configs\geophase_b3v2_solution_level.yaml --output-root outputs\tables\geophase_b3v2_solution_level
```

Aggregation-only repair command:

```powershell
.\.venv\Scripts\python.exe scripts\run_geophase_b3v2_solution_level.py --stage development-nls-recompute --config configs\geophase_b3v2_solution_level.yaml --output-root outputs\tables\geophase_b3v2_solution_level
```

## Evidence

- Machine summary: `outputs/tables/geophase_b3v2_solution_level/development/nls_development_summary.json`
- Field metrics: `outputs/tables/geophase_b3v2_solution_level/development/nls_refinement_metrics.csv`
- Frozen failed envelope: `outputs/tables/geophase_b3v2_solution_level/development/reference_envelope.json`
- Envelope SHA-256: `66a52bf31185fc586590b344248885446f51e8f7ee51dd00156e0a05b9dd016d`
- Atomic workers and lossless arrays: `outputs/tables/geophase_b3v2_solution_level/development/workers/`
- Pre-correction aggregates: `outputs/tables/geophase_b3v2_solution_level/development/pre_contract_repair/`

## Claim Boundary And Route

Supported only within the frozen development windows:

- the passive full-field recorder produces common-time solution evidence;
- 9 V NLS T1/T2 self-refinement passes exactly;
- 12.5 V NLS T1/T2 self-refinement validly fails the frozen field and port
  gates while preserving event topology/timing.

Forbidden:

- selecting NLS-v1 or safeguarded Anderson as the final ground-truth solver;
- Anderson accuracy or acceleration claims;
- B4 cost, full-trajectory, fresh-S0, Phase-1, Phase-2, C01/C06, OOD, or PINN
  claims;
- S2 physical failure, Qiu quantitative reproduction, or experimental
  validation.

The sole next research decision is whether to authorize a separate C04
observable-subspace/constrained-`gamma_sub` identifiability-boundary manuscript.
It is not started by this task and cannot be represented as a successful 2.5D
positive-PINN route.
