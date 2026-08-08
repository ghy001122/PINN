# Q2 CC-B Branch Stability/Transition Bracket v1

## Verdict

```text
STOP_NUMERICAL_SEMANTICS_NOT_CLOSED
validity = invalid
local_evidence_status = FORBIDDEN
scientific_vote = false
formal_execution_count = 0
cc_b_matrix_launch_count = 0
```

The preregistered R1 fixed lattice stopped because
`NOM/heating/0.35 mA/L1` exhausted the frozen full-thermal-residual evaluation
budget before producing an equilibrium-valid state. The task therefore did not
run R2 boundary refinement or R3 L2 anchor qualification. It does not establish
a stable transition span, a candidate linear-stability boundary, a patterned
branch, a complete CC-B result, Ground Truth eligibility, or any PINN result.

Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

## Identity And Frozen Scope

- Starting authority: `main@22ed32018d5463e171be960beb00710a055a1f13`
  (PR #34 merge).
- Frozen implementation/result identities:
  `616fd9b2673f9591ff58900354c38dd3f9a6c1f9` and
  `d544de2fc239a46ab401b2f32349f6f8b9cd769e`.
- New code anchor: `3e46d9ff60c4764be1c64a730c54111daa5bd84c`.
- Run identity:
  `Q2-CC-B-BRANCH-STABILITY-TRANSITION-BRACKET-20260808-V1`.
- Branch: `codex/q2-cc-b-branch-stability-transition-bracket-v1`.
- Active topology remained the ideal algebraic conductive-channel current
  clamp with temperature cells as the only dynamic state and
  `Vd=I_set/G_hat(T)`.

The task did not modify the frozen CC-B model, equilibrium solver, Jv,
current projection, ARPACK configuration, Ritz gate, stability margin,
source mapping, S2 parameters, geometry, or grid. PR #34 and earlier evidence
remain immutable.

## Implementation And Focused Verification

The new versioned contract and runner register the fixed 26-point L1/k6
lattice, strict branch ordering, non-recovering stable-continuation labels,
deterministic boundary refinement, L2 anchor selection, and phase-invariant
mass-weighted mode metrics. They call the existing production equilibrium and
stability APIs and do not copy the physical evaluator or Jv.

Focused commands and results:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/test_q2_current_clamp_cc_a.py \
  tests/test_q2_current_clamp_cc_b.py \
  tests/test_q2_cc_b_stability_telemetry.py \
  tests/test_q2_cc_b_stability_requalification.py \
  tests/test_q2_cc_b_branch_stability_transition_bracket.py -q

61 passed in 4.16 s

.\.venv\Scripts\python.exe -m pytest tests/test_project_governance.py -q

5 passed in 10.52 s
```

The new 13 tests cover lattice identity/order, strict PR #34 reuse,
non-recovering continuation, deterministic bisection, phase/sign/scale-invariant
mode metrics, x/y coordinate orientation, terminal routing, and forbidden
imports.

## R0 Authority Gate

R0 authenticated 19 authority files, all 14 CC-A roots, the parent configs,
PR #34 terminal/summary/manifest, L1/L2 equilibrium records, k6/k10 Ritz
artifacts, and four frozen numerical-core hashes. It fixed the lattice at 26
points and locked `NOM/heating/0.4 mA/L1/k6` to exact PR #34 reuse rather than
a second scientific execution.

R0 wall/CPU time was `0.1884243 / 0.046875 s`.

## R1 Fixed Lattice

Execution order was heating `0.10 -> 0.70 mA`, followed by cooling
`0.70 -> 0.10 mA`, at 0.05 mA spacing. It produced 25 new executions and one
authenticated PR #34 reuse.

| Quantity | Result |
| --- | ---: |
| requested fixed points | 26 |
| equilibrium-valid points | 25 |
| spectrum-certified points | 25 |
| invalid points | 1 |
| maximum valid Ritz `eta` | `6.6205976e-7` |
| R1 wall / CPU | `164.9685 / 125.3594 s` |

The sole invalid point was:

```text
NOM / heating / 0.35 mA / L1
equilibrium_code = CCB_KRYLOV_BUDGET
failure_detail = full thermal residual evaluation budget exhausted
spectrum = not executed
```

This is an equilibrium numerical-closure failure, not a certified stable or
unstable spectrum and not a physical failure. The one-execution rule and the
task's prohibition on a second numerical-semantic repair required immediate
termination before R2/R3.

## Non-Voting Diagnostic Context

The following observations are preserved only to localize the next question;
they do not override the invalid terminal:

- Heating has three stable continuation-connected L1 points at 0.10, 0.15,
  and 0.20 mA, but none passes the provisional transition gate. Its valid
  transition-bearing points are positive unstable.
- Cooling starts from a positive-unstable 0.70 mA externally preconditioned
  endpoint, so no cooling point is stable-continuation-connected. Independently
  initialized 0.10 and 0.15 mA equilibria are stable and transition-bearing,
  but they cannot restore that broken chain.
- Nineteen valid transition-bearing positive-unstable points (9 heating,
  10 cooling) have rightmost modes classified `transverse-dominated`.
  Their y-gradient energy fractions range from `0.9544425` to `0.9948919`,
  while uniform overlaps are effectively zero.

These mode records are non-voting linear diagnostics. They do not prove a
pitchfork, filament, nonlinear patterned branch, dynamic symmetry breaking, or
real-device behavior. Because R1 is numerically incomplete, the task does not
issue `STOP_CC_B_PATTERNED_BRANCH_REQUIRED`.

## Skipped Stages And Claim Boundary

- R2 boundary refinement: `SKIPPED_NUMERICAL_SEMANTICS_NOT_CLOSED`.
- R3 L1/k10 and L2/k6/k10 anchor qualification:
  `SKIPPED_NUMERICAL_SEMANTICS_NOT_CLOSED`.
- LU/RD, the 36-case matrix, CC-C, Ground Truth, data generation, C01/C06,
  MLP, vanilla PINN, inverse, SVD, refusal, and GPU work were not executed.
- No continuous current interval was certified; no boundary bracket was
  refined; no L2 sampled admissible span exists.

## Budget

R0+R1 numerical wall/CPU time was approximately
`165.1569 / 125.4063 s`, with one worker, one BLAS/OpenMP thread, and no GPU.
This is well below the `7200 s` wall and `14400 s` CPU ceilings. The stop was
numerical, not resource-budget exhaustion.

## Artifacts

- Compact evidence and terminal:
  `outputs/tables/q2_current_clamp_cc_b_branch_stability_transition_bracket/Q2-CC-B-BRANCH-STABILITY-TRANSITION-BRACKET-20260808-V1/`
- Recoverable equilibrium fields:
  `data/processed/q2_current_clamp_cc_b_branch_stability_transition_bracket/Q2-CC-B-BRANCH-STABILITY-TRANSITION-BRACKET-20260808-V1/`
- Config: `configs/q2_cc_b_branch_stability_transition_bracket_v1.yaml`.

## Single Next Priority

The highest-value next problem is not a patterned-branch solve or a PINN. It is
a separately preregistered, non-voting
`Q2_CC_B_HEATING_0P35_EQUILIBRIUM_TELEMETRY_CLOSURE_V1` that replays only the
failed input with the frozen solver/configuration and persists Newton, Krylov,
residual-evaluation, predictor, and budget telemetry. It must not alter solver
budgets or physics. Only a localized implementation invalidity could justify a
new repair authorization; otherwise the numerical stop remains binding. All
25 valid point artifacts should be reused unchanged in any later aggregation.

PR, current-head CI, and merge identity are recorded after GitHub closure; they
do not change the numerical disposition.
