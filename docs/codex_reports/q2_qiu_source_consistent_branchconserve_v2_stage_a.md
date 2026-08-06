# Q2 Qiu Source-Consistent BranchConserve v2 — Stage A Terminal Report

## Verdict

```text
A_STOP_STEADY_ROUTE
validity = valid
lifecycle_state = executed
claim_status = failed_but_informative
scientific_vote = false
formal_execution_count = 0
```

The formula-level source audit passed, but neither the original 12 kΩ circuit
nor any of the six other preregistered load values produced a continuous,
robustly stable, nondegenerate transition domain satisfying the frozen entry
gate. No Stage B L1 pilot, two-dimensional FVM run, B1/B2, dataset, Jacobian,
PINN, C01, or C06 work was executed.

This result rejects the present steady-route entry contract. It does not show
that Qiu's dynamic neuristor model, the repository S2 physics, or a PINN is
scientifically false.

## Task Contract

- Base: merge commit `0877714dbed92d4d43f031fab5032f5cbd56eae8`, which
  merged PR #29 unchanged.
- Objective: audit Qiu S1--S7 source semantics and run an independent 0-D
  fixed-point/stability/reachability oracle.
- Authorized execution: 16 base cases and, only after the 12 kΩ dual-branch
  failure, the fixed seven-load sentinel.
- Prohibited: PR #29 modification, new material fitting, continuous load
  optimization, S7 as 2-D production, Stage B, dynamic S0/controller work,
  B1/B2, Jacobian/SVD, PINN, or GPU use.
- Budget: Stage A CPU/calendar no more than 2 h; each load no more than 10 min.
- Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

## Source Audit

The primary PDF hashes and the locked source contract agree:

- main article SHA-256:
  `d842e8bf1b5ac609ab504d8bf6104cfd3efea59697a5c7ac21664a99eb7d3c67`;
- Supporting Information SHA-256:
  `d47ed95cd5782c3e632bbc440c1fcc681870e0ff303f0b05f8cd8f30cec70bfd`;
- source-contract SHA-256:
  `17a0accc906d68fffc35ee40be9d41c36bd1a7d0514e9a539cfcfd4fc4bcc621`.

For the unreversed major loop, \(T_{pr}\) is inactive and

\[
F_b(T)=\frac12\left[1+\tanh\left(\beta\left[T_c+\delta_b\frac w2-T\right]\right)\right].
\]

The branch midpoints are `336.3965 K` and `329.2035 K`. The equivalent
logistic scale is `1.976284584980237 K`; the v1 `7.193 K` expit scale is not
source-consistent. The independent formulas match the existing source-only
Qiu module with maximum discrepancy `0.0` on the audit grid.

The direct shortcut receives the fixed verdict:

```text
REJECT_DIRECT_BETA_K_PATCH
```

`beta` controls major-loop steepness, while `k=4.90` modifies the dynamic
thin-filament device resistance in S7. Applying both constants does not turn
v1 logarithmic conductivity mixing into S1, and S7 is not a distributable
local material law. The detailed mapping and allowed/forbidden wording are in
`source_to_code_discrepancy.csv`.

## Numerical Certification

The 16 base cases cover:

```text
Vs = 9.0, 12.5, 15.8, 17.0 V
branch = heating, cooling
resistance = S1_QS, S7_DYNAMIC_COMPARATOR
```

Every case returned one algebraic fixed point. Nested 4097/8193 partitions
gave the same root count; the worst fixed-point-set Hausdorff difference was
`1.1368683772161603e-13 K`. Across all 16 roots:

- maximum current residual: `2.0816681711721685e-16`;
- maximum thermal residual: `6.394884621840901e-15`;
- maximum analytic/central-difference Jacobian relative difference:
  `1.1639203521390195e-07`;
- maximum eigenpair relative residual: `8.393931201959218e-17`.

Thus the stop is not a schema, root-resolution, equilibrium-residual, or
eigensolver defect.

## S1 Fixed Points at 12 kΩ

| Vs (V) | Branch | T (K) | Vd (V) | I (mA) | conductive coordinate | alpha tau | Local stability |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 9.0 | heating | 331.2130 | 6.71165 | 0.19070 | 0.06768 | -0.34047 | stable |
| 9.0 | cooling | 332.3668 | 3.07195 | 0.49400 | 0.83210 | 1.21560 | unstable |
| 12.5 | heating | 338.9549 | 4.11319 | 0.69890 | 0.78492 | 4.17663 | unstable, diagnostic only |
| 12.5 | cooling | 334.2544 | 2.22686 | 0.85609 | 0.92796 | 1.25943 | unstable, diagnostic only |
| 15.8 | heating | 340.6097 | 3.01914 | 1.06507 | 0.89396 | 4.44907 | unstable |
| 15.8 | cooling | 335.3566 | 1.83300 | 1.16392 | 0.95745 | 1.19446 | unstable |
| 17.0 | heating | 341.0229 | 2.78674 | 1.18444 | 0.91221 | 4.18687 | unstable |
| 17.0 | cooling | 335.6918 | 1.73095 | 1.27242 | 0.96384 | 1.12445 | unstable |

The S1 high-conductive algebraic roots exist but fail the frozen local
stability gate. Algebraic existence was therefore not promoted to a cooling
endpoint. At 12 kΩ, the heating continuous component contains 20 voting
biases only through `9.5 V`, but its conductive-coordinate span is just
`0.10526067022017915`; cooling has no valid high stable endpoint. The common
dual-branch domain is empty.

For context only, S7's 17 V cooling root is stable, but S7 remains a
non-voting dynamic-filament comparator and cannot rescue the two-dimensional
production route.

## Load-Design Sentinel

The required 12 kΩ failure triggered the complete finite sentinel:

| RL (kΩ) | Common voting biases | Dual PASS | Heating span | Cooling span | Forward PASS |
| ---: | ---: | --- | ---: | ---: | --- |
| 3 | 1 | no | 0.09263 | 0.01269 | no |
| 6 | 0 | no | 0.07759 | 0.00587 | no |
| 9 | 0 | no | 0.12854 | 0 | no |
| 12 | 0 | no | 0.10526 | 0 | no |
| 18 | 0 | no | 0.12408 | 0 | no |
| 24 | 0 | no | 0.09983 | 0 | no |
| 36 | 0 | no | 0.15001 | 0 | no |

The 3 kΩ case forms stable high and low components, but they share only one
voting source voltage and neither component spans a nondegenerate transition
region. No load satisfies the dual-branch or forward nondegeneracy gate.
There was no continuous optimization and no post-hoc load insertion.

`12.5 V` was excluded from every voting set and retained only as a diagnostic
source-voltage regime.

## Budget and Validation

Actual execution:

```text
.\.venv\Scripts\python.exe scripts/run_q2_qiu_source_consistency_stage_a.py --config configs/q2_qiu_source_consistent_branchconserve_v2_stage_a.yaml --run-id Q2-QIU-SOURCE-STAGEA-20260806-V1
```

- aggregate CPU: `8.078125 s`;
- calendar wall: `8.407801199999994 s`;
- all seven load evaluations were below `1.42 s`;
- focused Stage A tests: `18 passed` before execution;
- no GPU or two-dimensional solver was invoked.

The final focused and route validation is recorded in the task handoff. Frozen
GT and historical dynamic/equivalence evidence were outside the modification
set and were not rerun.

## Evidence

- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/source_to_code_discrepancy.csv`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/fixed_points.csv`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/stationary_points.csv`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/stability.csv`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/continuous_reachability.csv`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/load_design_sentinel.csv`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/source_oracle_summary.json`
- `outputs/tables/q2_qiu_source_consistent_branchconserve_v2/Q2-QIU-SOURCE-STAGEA-20260806-V1/terminal.json`

## Claim Boundary and Stop

Supported only as bounded, conditional source-oracle evidence:

> Under the preregistered S1 quasistatic source oracle and seven finite load
> values, no continuous robustly stable domain met the nondegenerate
> transition entry gate for a new two-dimensional steady pilot.

Forbidden conclusions remain Qiu quantitative reproduction, experimental
validation, S2 or Phase 1 failure, a two-dimensional source-consistent judge,
stable cooling in the 2-D model, or any PINN/C01 result.

Stage B is not authorized. The steady BranchConserve route stops here under
this contract; no automatic method or circuit pivot follows from this task.
