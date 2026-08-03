# Exact-Condensed v2 D0 Terminal Report

## Disposition

```text
D0_MECHANISM_VALID_FAIL
```

The single authorized diagnostic replay is valid and reproducible, but the
fixed-point direct Newton direction has no strict defect decrease for any
allowed damping from `1` through `1/128`. The plan therefore stops before Jv
selection, v2 production identity creation, D1, or any downstream execution.

## Task Contract

- Base: `main@c830b4844e58ba63c197429984ac1f5a00a9ccce`.
- Diagnostic: `D0-EXACT-CONDENSED-V2-20260803-V1`.
- Input: PR #24 case `B2-ORIGINAL-S1-DT10p0NS` only.
- Allowed: one deterministic replay, explicit L1 Jacobians, line profiles,
  fixed-direction Jv assessment, and a non-voting dyadic map only after the
  mechanism gate.
- Frozen: Stage A, v1 solver/B2 evidence, production implicit/NLS/controller,
  S2 physics, protocols, thresholds, history, and Frozen GT.
- Budget: 30 minutes CPU wall; one diagnostic replay.
- Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

## Execution

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_geophase_exact_condensed_v2_d0.py -q
.\.venv\Scripts\python.exe scripts\run_geophase_exact_condensed_v2_d0.py `
  --config configs\geophase_exact_condensed_v2_d0.yaml `
  --output-root outputs\tables\geophase_exact_condensed_v2\d0\D0-EXACT-CONDENSED-V2-20260803-V1
```

BLAS/OpenMP/NumExpr threads were fixed to one for the diagnostic invocation.
Focused tests passed `5/5`. Diagnostic wall time was `9.6197008999 s`.

## Frozen Replay

The replay matches PR #24 exactly:

- residual history:
  `[1.559176e-2, 1.199795e-2, 8.144418e-3, 9.612938e-3,
  9.540546e-3, 9.519604e-3]`;
- accepted damping: `[1, 1/8, 1/2, 1/32, 1/128]`;
- Krylov matvecs: `100`;
- original-residual evaluations: `135`;
- terminal failure: `ARMIJO_LINE_SEARCH_FAILURE`.

The 10 ns replay is not a B2 continuation or rerun identity and casts no vote.

## Jacobian And Linear-Solve Evidence

| Quantity | Original scaled T residual | Fixed-point defect |
| --- | ---: | ---: |
| residual/defect infinity norm | `9.5196035872e-3` | `6.0661962635e-4` |
| numerical rank | `250/250` | `250/250` |
| largest singular value | `3.1981206479e-1` | `1.4918391542e-2` |
| smallest singular value | `2.2972321132e-3` | `2.3658329105e-4` |
| condition number | `139.2162607` | `63.0576719` |

The v1 final LGMRES correction has explicit-original-Jacobian linear backward
error `1.8741301658e-1`, despite the historical LGMRES `info=0`. In contrast,
the fixed-point SVD and pivoted-QR corrections have backward errors
`3.5030786440e-14` and `9.4726106189e-15`, with relative correction difference
`3.8236922496e-15`. Thus the D0 stop is not rank loss or failure to solve the
explicit linearized system.

## Hard-Stop Trigger

Baseline fixed-point defect:

```text
||F_fp||inf = 6.066196263505657e-4
```

Selected line-profile values:

| damping | `||F_fp||inf` | relative to baseline |
| ---: | ---: | --- |
| `1` | `5.8264408685e-3` | worse |
| `1/8` | `1.1669416531e-3` | worse |
| `1/32` | `7.4614958967e-4` | worse |
| `1/64` | `6.5265427412e-4` | worse |
| `1/128` | `6.1477053274e-4` | worse |
| `1/256` | `6.0635464266e-4` | first strict decrease, forbidden |

The plan explicitly requires a strict decrease at some damping in
`1...1/128`. Because this condition fails, Jv candidates were not evaluated,
no Jv scheme/multiplier was frozen, the dyadic root map was not launched, and
the proposed solver identity was not created. Lowering the damping minimum
would be an unauthorized post-result rule change.

## Evidence And Claim Boundary

- D0 lifecycle: `executed`.
- D0 claim status: `failed_but_informative` numerical-method evidence.
- `scientific_vote=false`.
- `formal_execution_count=0`.
- D1/D2/B3/B4, fresh S0, Phase 2, C01/C06, OOD, and R1/R2/R3: not executed and
  `forbidden`.

This result does not establish S2 physical failure, Phase 1 PASS/FAIL, runtime
feasibility, campaign cost, a PINN result, Qiu reproduction, or experimental
validation.

## Artifacts

- `configs/geophase_exact_condensed_v2_d0.yaml`
- `outputs/tables/geophase_exact_condensed_v2/d0/D0-EXACT-CONDENSED-V2-20260803-V1/d0_summary.json`
- `d0_replay_trace.json`
- `d0_jacobians_and_corrections.npz`
- `d0_line_profiles.csv`
- `d0_jv_candidates.csv` and `d0_jv_direction_errors.csv` (empty by hard stop)
- `d0_v1_dyadic_root_map.csv` (empty by hard stop)

The final branch/commit/PR/CI identity is reported in the task handoff because
the commit cannot contain its own SHA.

## Next Route

The exact-condensed v2 forward route is stopped. The plan's only recommendation
is a separately authorized C04 observable-subspace plus `gamma_sub` calibration
and identifiability-boundary manuscript pivot. This report does not authorize
that pivot.
