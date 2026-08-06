# Q2 CurrentClamp-HysGeo-PINN v1 — CC-A Terminal Report

## Verdict

```text
PASS_CC_A_CURRENT_CLAMP_ADMISSION
validity = valid
lifecycle_state = executed
claim_status = qualified_supported
scientific_vote = false
formal_execution_count = 0
CC-B authorized = false
CC-B executed = false
```

Under the preregistered S1 quasistatic major-branch law, ideal current control
produced a non-degenerate set of unique, locally stable, branch-conditioned
continuation-connected equilibria over the fixed 0.1--0.7 mA range. This is a
zero-dimensional admission result. It makes a separately authorized CC-B
two-dimensional pilot eligible; it does not validate a 2.5-D judge or a PINN.

## Authority And Scope

- PR #30 was merged unchanged as `0230b036c271e02f52bc8d4b25f0021eb0d1870b`.
- PR #30's valid `A_STOP_STEADY_ROUTE` result remains immutable for the
  voltage-source-plus-series-load topology.
- CC-A code anchor: `230f1e37fbefd88d554d54009db626d175a00444`.
- Run identity: `Q2-CC-A-ADMISSION-20260806-V1`.
- Authorized work: CC-0 implementation and one bounded CC-A execution.
- Not authorized or executed: CC-B/CC-C, two-dimensional fields, data
  generation, MLP, PINN, CC01, CC06, GPU work, or CC-I2.
- Evidence identity: `literature-guided synthetic numerical digital-twin
  evidence`.

The branch label is external protocol metadata. The result demonstrates
continuation connectivity under a fixed major-branch constitutive law, not
dynamic branch switching, minor-loop memory, or physical switching
reachability.

## Frozen Model And Gate

The source resistance is Qiu S1 only:

\[
F_b(T)=\frac12\{1+\tanh[\beta(T_c+\delta_b w/2-T)]\},
\qquad
R_b^{QS}(T)=R_0e^{E_a/T}F_b(T)+R_m.
\]

The ideal-current equilibrium and lumped local-stability eigenvalue are

\[
S_{th}(T-T_0)-I_{set}^2R_b^{QS}(T)=0,
\qquad
\lambda=\frac{I_{set}^2R_b'(T)-S_{th}}{C_{th}}.
\]

Formal currents were fixed before execution at 0.1--0.7 mA. Heating began at
the non-voting zero-current low-state anchor. Cooling began at an externally
preconditioned 0.7 mA high-state endpoint. The root domain was 300--380 K and
the conservative operating envelope was (V_d\le17) V.

## Numerical Results

All 14 formal branch/current cases returned exactly one resolved root. The
predictor/corrector trace matched every root and terminated normally.

| Metric | Heating | Cooling | Gate |
| --- | ---: | ---: | ---: |
| continuation-connected points | 7 | 7 | at least 5 each |
| conductive-state span | 0.7760256851 | 0.6754940767 | at least 0.5 each |
| intermediate points, (0.1\le s\le0.9) | 5 | 6 | at least 2 each |
| endpoint state at 0.7 mA | 0.7854589559 | 0.9005535528 | cooling at least 0.9 |

The seven common currents all exceeded the required branch-state separation
of 0.1. Their absolute separations from 0.1 to 0.7 mA were:

```text
0.2156262, 0.4100841, 0.3687151, 0.2679662,
0.1956070, 0.1476565, 0.1150946
```

Across all formal roots:

- temperature range: `326.7599791--338.9612572 K`;
- device-voltage range: `2.5185049--6.8073743 V`;
- maximum scaled equilibrium residual: `3.772996312397117e-14`;
- maximum S1 analytic/central-FD derivative relative error:
  `5.263847595874937e-08`;
- least-negative dimensionless stability value
  \(\alpha_\tau=\lambda C_{th}/S_{th}\): `-1.117022838726888`.

Thus every selected point was finite, range-legal, inside the voltage
operating envelope, and locally stable with margin beyond the frozen
`-1e-3` threshold.

## Source-Scale Mapping Boundary

Batch 1 also certified only the algebraic uniform-port relation

\[
g_{geom}=Wt_v/L=5\times10^{-7}\;\mathrm m,
\qquad
\sigma_b^{eff}=1/(g_{geom}R_b^{QS}).
\]

The maximum resistance round-trip relative error was
`1.5986875514822344e-16`. This is a device-effective distributed proxy. No
two-dimensional FVM field was executed, and the result cannot be used as an
intrinsic local VO2 conductivity or contact-current-crowding claim.

## Budget And Validation

Formal command:

```text
.\.venv\Scripts\python.exe scripts\run_q2_current_clamp_cc_a.py
```

- aggregate CPU: `0.21875 s` (cap `1800 s`);
- calendar wall: `0.2515203000002657 s` (cap `1800 s`);
- BLAS/OpenMP/NumExpr threads: `1`;
- pre-execution focused regression: `29 passed`;
- no implementation repair or repeated scientific run was used.

## Evidence

- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/all_roots.csv`
- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/continuation.csv`
- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/gate_summary.json`
- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/source_mapping_contract.json`
- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/summary.json`
- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/terminal.json`
- `outputs/tables/q2_current_clamp_hysgeo/Q2-CC-A-ADMISSION-20260806-V1/artifact_manifest.json`

## Claim Boundary And Stop

Allowed wording:

> Under a source-audited S1 major-branch oracle, ideal current control admits
> a preregistered non-degenerate set of locally stable,
> branch-conditioned continuation-connected lumped equilibria.

Forbidden wording includes Qiu voltage-driven quantitative reproduction,
experimental validation, dynamic switching reachability, intrinsic local VO2
conductivity, two-dimensional forward validation, and any PINN/CC01/CC06
success claim.

Batch 1 stops here. `PASS_CC_A_CURRENT_CLAMP_ADMISSION` permits only a user
decision on a separately bounded CC-B uniform-limit/L1--L2 pilot.
