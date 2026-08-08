# Q2 CC-B Stability Telemetry Closure v1

## Executive verdict

```text
PASS_CC_B_STABILITY_TELEMETRY_CLOSURE
telemetry_closure_status = PASS
closure_class = implementation_invalidity_localized
stability_certification_status = INVALID
physical_spectrum_classification = NOT_APPLICABLE
stable = null
```

The previously opaque `INVALID_STABILITY` is now reproducibly localized to
the frozen Ritz-residual certification gate for
`nominal/heating/0.4 mA/L1/k6`. The equilibrium input, temperature mass
matrix, conservative unit-bias electrical solves, fixed-current projection,
central-difference Jv probes, ARPACK return cardinality, finite values, atomic
artifacts, and terminal aggregation all pass their registered execution gates.

This is a valid non-voting diagnostic closure, not a CC-B scientific result.
It does not establish physical stability or instability and does not authorize
L2, the uniform gate, the 36-case matrix, CC-C, data generation, or PINN work.

## Task contract

- Task: `Q2_CC_B_STABILITY_TELEMETRY_CLOSURE_V1`
- Review revision: `20260808-R1`
- Campaign: `Q2-CC-B-STABILITY-TELEMETRY-CLOSURE-20260808-V1`
- Base: `main@1d2b3d66eaec3faa908c0e377a7da92467c76b00`
- Parent PR #32 head: `003aaad5c0c58c7ecb93c2fd24d87d3166b2d023`
- Reproduction wording: `merged-PR32 numerical-contract reproduction`
- Sole case: `NOM/heating/0.4 mA/L1/k6`
- Evidence type: `literature-guided synthetic numerical digital-twin evidence`
- Frozen counters: `formal_execution_count=0`, `cc_b_matrix_launch_count=0`

The parent config, terminal, and smoke hashes were reauthenticated as:

```text
56384a56893c1f9752e00e1dcece242a788805df2148b5022903adc6c314de8d
4fd2e2c0ca090788e38b8e96b19a0543285149cfe899c3febd84fae57a95f6d3
817f301f3f03ea03e7ef57b095c89ce12829b90d531aae3b55c5da54a0d3c183
```

## Implementation

The historical `CCBStabilityOutcome` API remains intact. An optional recorder
is disabled by default and therefore does not alter the parent numerical path.
When enabled, it observes every central-difference Jv, its two fresh
unit-bias electrical solves, `G_hat`, the algebraic `Vd=I_set/G_hat`
projection, fixed-current error, timing, ARPACK return, partial/full pairs,
and the independent Ritz reconstruction.

The dedicated campaign layer adds:

- an authenticated one-case YAML contract;
- atomic T1/T2 attempt and repair counters;
- input-before-stability persistence and readback certification;
- two fixed deterministic Jv probes;
- aggregate `jv_calls.csv` and `jv_calls.npz` checkpoints every 64 matvecs;
- detailed arrays only for fixed probes, first failure, last success, and Ritz
  pairs;
- distinct closure, stability-certification, and physical-spectrum fields;
- a fail-closed four-terminal state machine.

No source, S2 coefficient, equilibrium solver, Jv formula/step, ARPACK
parameter, Ritz threshold, or stability margin changed.

## Validation commands

```text
.\.venv\Scripts\python.exe -m py_compile src\pinnpcm\current_clamp\cc_b_model.py src\pinnpcm\current_clamp\cc_b_stability.py src\pinnpcm\current_clamp\cc_b_stability_telemetry.py scripts\run_q2_cc_b_stability_telemetry.py tests\test_q2_cc_b_stability_telemetry.py

.\.venv\Scripts\python.exe -m pytest tests\test_q2_cc_b_stability_telemetry.py -q
# 16 passed in 7.63 s

.\.venv\Scripts\python.exe -m pytest tests\test_q2_cc_b_stability_telemetry.py tests\test_q2_current_clamp_cc_b.py tests\test_q2_current_clamp_cc_a.py -q
# 38 passed in 2.10 s

.\.venv\Scripts\python.exe scripts\run_q2_cc_b_stability_telemetry.py --attempt T1 --repair-count 0 --preexecution-cpu-s 20 --preexecution-wall-s 20
```

No full-suite, Frozen GT, uniform, L2, k10, formal-matrix, or PINN command was
run.

## T1 results

The verified parent 0.2 mA L1 NPZ initialized a new, explicitly non-voting
0.4 mA L1 equilibrium. It was atomically persisted before stability and then
read back and independently re-evaluated.

| Quantity | Result |
| --- | ---: |
| `Vd` | `5.895042849006573 V` |
| active-area mean conductive-state coordinate | `0.5063480795578005` |
| temperature range | `336.4466851437019–336.4466851437021 K` |
| scaled thermal residual | `5.2708226675782296e-14` |
| last scaled update | `5.76723202249527e-09` |
| scaled electrical residual | `5.421010862427522e-16` |
| maximum ledger error | `9.563715551066287e-15` |

The mass sum closes exactly to `Cth=4.96e-11 J/K`. Across all preregistered
operator probes, the maximum scaled electrical residual is
`4.64658073922359e-16` and the maximum normalized current-projection error is
`3.097720492815727e-16`.

Jv diagnostics:

| Gate | Result |
| --- | ---: |
| repeatability | `0` |
| h versus h/2 | `2.9912998913734553e-06 <= 1e-4` |
| homogeneity, non-voting | `0` |
| additivity, non-voting | `1.924054590105198e-06 <= 1e-4` |
| 2h versus h, non-voting | `1.1964864998055863e-05 <= 4e-4` |

ARPACK returned six finite pairs normally. The independent residual
reconstruction then produced:

```text
lambda_real [/s] =
  9.7428520460e6, 8.1464614761e6, 9.1091326431e6,
  6.9899598155e6, 5.8038208636e6, 4.7385365111e6

Ritz residual rate rho [/s] =
  164.57381777, 199.16728358, 223.00775930,
  187.03476760, 184.07677338, 153.05069307

relative eta =
  1.68917497e-5, 2.44483183e-5, 2.44817776e-5,
  2.67576313e-5, 3.17164809e-5, 3.22991482e-5
```

All six exceed the frozen `eta <= 1e-6` certification threshold, so
`certified_pair_count=0`. The positive raw Ritz values are not an admissible
physical-instability result because the pairs are uncertified. The only valid
statement is that the failure lies at `RITZ_CERTIFICATION` after a normal,
finite six-pair ARPACK return.

Telemetry totals are 256 recorded Jv calls overall; the core stability call
reports 249 matrix-vector products and 498 dynamic-RHS evaluations. Its wall
time is `1.275823500007391 s`. The terminal budget account, including the
conservative 20 s pre-execution allowance, is `21.812349700005143 s` wall and
`21.59375 s` CPU, well below 7200 s.

## Repair, replay, and identity

- `campaign_attempt_count=1`
- `implementation_repair_count=0`
- T2 was not eligible and was not run.
- No result-triggered executable, schema, or config change occurred.

The numerical run occurred from the verified base commit plus the exact
uncommitted telemetry worktree. To avoid repeating the parent identity
ambiguity, `execution_source_manifest.json` freezes the SHA-256 of every new
or modified execution source. The code-anchor commit is required to contain
those exact bytes; its SHA is reported in the PR and final handoff rather than
self-referenced inside this report.

## Claim effect

| Claim | Status after this task |
| --- | --- |
| The parent stability invalidity is localized to Ritz certification | `supported` software/diagnostic fact |
| The 0.4 mA L1 equilibrium is a valid non-voting diagnostic input | `qualified_supported` local numerical evidence |
| The 0.4 mA L1 field is physically stable or unstable | `forbidden` |
| CC-B passes or fails its 2.5-D scientific gate | `forbidden` |
| Uniform/L2/formal matrix, CC-C, CC01, CC06, or inverse evidence exists | `forbidden` |

The next admissible action, if separately authorized, is a versioned
`Q2_CC_B_STABILITY_REQUALIFICATION_V1` that addresses whether a frozen,
certifiable constrained spectrum can be obtained at the required resolution.
It must not reinterpret these uncertified positive Ritz values, tune the
existing threshold, or auto-launch the CC-B matrix.
