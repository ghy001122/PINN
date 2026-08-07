# Q2 CurrentClamp-HysGeo-PINN v1 — CC-B Terminal Report

## Verdict

```text
INVALID_CC_B_EXECUTION
validity = invalid
lifecycle_state = executed
claim_status = forbidden
cc_b_scientific_vote = false
cc_b_matrix_launch_count = 0
scientific_vote = false
formal_execution_count = 0
```

The bounded CC-B task stopped in the paired non-voting smoke. The current-clamp
topology and two-dimensional implementation were created and focused tests
passed, but the first 0.4 mA constrained-stability certification returned
`INVALID_STABILITY`. The run therefore supplies execution provenance and two
valid local equilibrium records, not a CC-B scientific PASS or FAIL.

## Authority And Topology Closure

- Starting authority: `main@618103321441abac36c9a9836ff6b0cc30e2c76e`.
- Branch: `codex/q2-cc-a-topology-closure-cc-b-2d-gate-v1`.
- Run: `Q2-CC-B-2D-GATE-20260807-V1`.
- Evidence identity: `literature-guided synthetic numerical digital-twin evidence`.
- CC-A and its 14/14 admission result remain immutable.

The new configuration fixes the topology as:

```text
clamp_target = conductive_sheet_current
electrical_response = algebraic
dynamic_state = temperature_cells_only
I_cond(T,Vd) = I_set
Vd = I_set / G_hat(T)
parallel_capacitance = inactive external-source metadata
```

Thus no `Cp`, external RC state, series-load line, pseudo-arclength, dynamic
controller, or terminal-total-current clamp enters the CC-B equations. The
only permitted wording is **ideal algebraic conductive-channel current clamp**.

## Implemented Contract

Each temperature residual evaluation recomputes the audited S1
device-effective conductivity proxy, conservative unit-bias electrical field,
unit conductance, algebraic device voltage, physical face currents, Joule
power, lateral heat flux, vertical sink, and all ledgers. The registered solver
is the single no-fallback temperature-primary damped Newton–Krylov method.

The nominal S2 sink integrates once to `Sth`. LU and RD multiply the nominal
sink locally by `0.5` and are not renormalized. The constrained-stability
operator uses temperature cells only and re-solves the electrical projection
for every perturbation.

The four unresolved PR #31 engineering issues were incorporated in the same
branch:

1. CC-A claim-bearing thresholds are now contract-locked.
2. CC-A executions use unique initially empty output directories.
3. CC-A contract-load failures emit an atomic fail-closed invalid terminal.
4. CC-B removes `Cp` from the active topology and names the clamped current
   unambiguously.

## Focused Validation And Repair Budget

The preregistered maximum of two implementation-repair cycles was consumed:

1. The CC-B contract initially compared `0.7 mA × 17 V` to `0.0119 W` with
   bitwise equality. It was repaired to a machine-precision consistency check.
2. The first focused test run ended `20 passed, 2 failed`. The bounded repair
   corrected a manufactured central-difference truncation issue with fixed
   Richardson cancellation, made fail-closed paths portable across Windows
   drives, and added complex-array artifact canonicalization.

The final focused command was:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/test_q2_current_clamp_cc_a.py \
  tests/test_q2_current_clamp_cc_b.py -q
```

Result: `22 passed in 2.72 s` (`3.90 s` measured wall time).

No further implementation repair was legally available when the smoke stopped.

## Smoke Result

Command:

```text
.\.venv\Scripts\python.exe scripts\run_q2_current_clamp_cc_b.py --stage smoke
```

The two published prerequisite records were:

| Metric | L1 | L2 |
| --- | ---: | ---: |
| current | `0.2 mA` | `0.2 mA` |
| device voltage | `6.807374343064828 V` | `6.807374343066526 V` |
| mean conductive coordinate | `0.08147867887802991` | `0.0814786788779224` |
| scaled thermal residual | `1.4012e-13` | `1.0002e-12` |
| scaled electrical residual | `1.9361e-16` | `1.9361e-16` |
| maximum ledger error | `6.8804e-14` | `6.0920e-13` |

Both were nominal/heating, non-voting equilibria. Their source current equals
`I_set` to floating-point precision, and their terminal-field and
field-thermal ledgers pass.

The next 0.4 mA equilibrium progressed to constrained-stability certification,
where the certification returned `INVALID_STABILITY`. The invalid sub-gate was
not published as a certified case artifact; only the fail-closed category is
available. It must not be reinterpreted as a positive or negative eigenvalue.

Smoke cost was `4.046875 CPU s` and `4.3479541 wall s`.

## Unexecuted Work

The stop occurred before:

- the six uniform electrical mapping sentinels;
- the 14-root topology/operator regression;
- the RAM/disk/CPU budget projection;
- creation of `formal_launch.json`;
- any of the 36 formal grid-case solutions;
- the four `k=6`/`k=10` comparisons;
- the 18 L2 voting stability cases;
- transition-area or LU/RD two-dimensional-response aggregation;
- CC-C, ground-truth expansion, data generation, PINN, CC01, CC06, GPU, or inverse work.

Accordingly, `cc_b_matrix_launch_count=0` and all historical/global counters
remain unchanged.

## Evidence

- `outputs/tables/q2_current_clamp_hysgeo_cc_b/Q2-CC-B-2D-GATE-20260807-V1/terminal.json`
- `outputs/tables/q2_current_clamp_hysgeo_cc_b/Q2-CC-B-2D-GATE-20260807-V1/stages/smoke/summary.json`
- `outputs/tables/q2_current_clamp_hysgeo_cc_b/Q2-CC-B-2D-GATE-20260807-V1/smoke/equilibria/`
- `data/processed/q2_current_clamp_hysgeo_cc_b/Q2-CC-B-2D-GATE-20260807-V1/smoke/equilibria/`

## Claim Boundary And Next Step

Supported engineering wording is limited to implementation of the algebraic
conductive-channel clamp and the two valid non-voting 0.2 mA equilibrium
records. Forbidden claims include physical instability, CC-B PASS or valid
science FAIL, 2.5-D judge validity, intrinsic local VO2 conductivity, Qiu
voltage-driven reproduction, experimental validation, and any PINN result.

The only admissible follow-up is a separately authorized, versioned,
non-voting stability-telemetry closure that preserves every physical equation,
case, and threshold and publishes the exact invalid sub-gate. This task may not
be resumed or retried.
