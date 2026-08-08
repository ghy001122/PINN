# Q2 CC-B Stability Requalification v1

## Verdict

```text
PASS_CC_B_STABILITY_REQUALIFICATION
stability_certification_status = VALID
physical_spectrum_classification = POSITIVE_UNSTABLE
stable = false
scientific_vote = false
formal_execution_count = 0
cc_b_matrix_launch_count = 0
```

The task successfully requalified the single preregistered
`NOM/heating/0.4 mA` constrained-temperature stability problem. The result is
an honest negative physical classification for this point, not a CC-B science
PASS and not authority to launch the formal matrix or train a PINN.

Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

## Identity And Repair

- Starting authority: `main@b3d8e5a67be09f9bc8fcc908c3fe4ca0a8aba4ee`
  (PR #33 merge).
- Frozen code anchor: `616fd9b2673f9591ff58900354c38dd3f9a6c1f9`.
- Run identity: `Q2-CC-B-STABILITY-REQUALIFICATION-20260808-V1`.
- Branch: `codex/q2-cc-b-stability-requalification-v1`.
- Parent L1 input SHA-256:
  `55b12deb98e3b1d9d11afc9d3e7ff0f5bfb2b74ef86115a25a6d19f158190e4d`.

The only numerical-semantic repair replaced the two-dimensional matrix
infinity norm used for the temperature scale with the maximum absolute
temperature component. It changed the PR #33 L1 centered-difference step from
approximately `2.0373e-2 K` to `2.037337577546412e-3 K`, without changing the
direction norm, centered difference, dynamic RHS, mass matrix, current
projection, ARPACK settings, Ritz threshold, or stability margin. The terminal
aggregator was also corrected to read maximum Ritz residuals and pair counts
from the recorder when a failure outcome contains empty arrays. Historical PR
#33 artifacts remain unchanged.

## Focused Verification

Approved command:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/test_q2_current_clamp_cc_a.py \
  tests/test_q2_current_clamp_cc_b.py \
  tests/test_q2_cc_b_stability_telemetry.py \
  tests/test_q2_cc_b_stability_requalification.py \
  tests/test_project_governance.py -q
```

Result: `53 passed in 8.73 s` with all BLAS/OpenMP thread variables fixed to
one; the 48 CC-A/CC-B/stability tests also pass independently. New tests cover
layout-independent temperature scaling, L1/L2 step
invariance, the authenticated PR #33 step, recorder parity, failure residual
aggregation, and deterministic real/complex spectrum classification.

## Numerical Evidence

The requalification command was:

```text
.\.venv\Scripts\python.exe \
  scripts/run_q2_cc_b_stability_requalification.py \
  --config configs/q2_cc_b_stability_requalification_v1.yaml
```

### Step diagnostics

| Metric | Result | Gate |
| --- | ---: | ---: |
| corrected `h` | `2.037337577546412e-3 K` | frozen formula |
| `h` versus `h/2` | `2.991812391178056e-8` | `<=1e-4` |
| `2h` versus `h` | `1.196519128075805e-7` | `<=4e-4` |

`h/4` was saved only as a non-voting roundoff observation.

### Matrix-free spectra

| Run | returned/finite/certified | max eta | max Ritz residual rate (1/s) | alpha (1/s) | alpha tau | class |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| L1/k6 | 6/6/6 | `3.165640253232459e-7` | `2.201757656154799` | `9.742936233237829e6` | `2.345872025090274` | positive unstable |
| L1/k10 | 10/10/10 | `3.195533707491550e-7` | `2.144700207432946` | `9.742936233238911e6` | `2.345872025090534` | positive unstable |
| L2/k6 | 6/6/6 | `3.365335649230180e-7` | `2.289155397384564` | `9.742493650007509e6` | `2.345765461361031` | positive unstable |
| L2/k10 | 10/10/10 | `3.374773683026290e-7` | `2.251412810373865` | `9.742493650921335e6` | `2.345765461581060` | positive unstable |

The L1 and L2 k6/k10 `alpha_tau` differences are respectively
`2.60e-13` and `2.200284e-10`, both below `1e-4`. The L1/L2 k6 difference is
`1.065637292427e-4`; no post-hoc cross-grid magnitude threshold was added, and
the preregistered physical classification is identical.

### Dense L1 reference

The `250 x 250` explicit matrix was built column by column from the same
corrected centered Jv, then solved with a dense full eigensolver. It is an
independent eigensolver/representation, not an independent physical operator.

- maximum dense relative eigenpair residual:
  `7.483559036157789e-14` (`<=1e-10`);
- dense `alpha_tau`: `2.345871982739824`;
- dense/ARPACK `alpha_tau` difference: `4.235044981371061e-8`
  (`<=1e-4`);
- classification: `POSITIVE_UNSTABLE`, matching matrix-free L1/k6.

### L2 equilibrium

The new L2 `0.4 mA` equilibrium has `Vd=5.895042849006654 V`, thermal
residual `3.24933227245032e-13`, last scaled update
`5.768573722103218e-9`, electrical residual
`3.872150616019659e-16`, and maximum ledger error
`3.549609810299558e-14`. All frozen input gates pass.

## Budget And Claim Boundary

- calendar wall: `54.81670110000414 s`;
- aggregate process CPU: `53.21875 s`;
- repair/replay after code freeze: zero;
- workers: one; BLAS/OpenMP threads: one; GPU: not used.

The execution supports only this statement: under the frozen ideal algebraic
conductive-channel current clamp and the source-scale-anchored device-effective
2.5-D proxy, the `NOM/heating/0.4 mA` equilibrium has a certified positive
rightmost constrained thermal eigenvalue on L1 and L2. It does not establish a
stable current window, a complete CC-B PASS/FAIL, a Qiu experimental
reproduction, an intrinsic local VO2 conductivity, or any PINN result.

The only admissible next request is a separate preregistered, finite current
bracket for stable branch/transition coverage. This task did not start it.

## Artifacts

- Compact terminal and summaries:
  `outputs/tables/q2_current_clamp_cc_b_stability_requalification/Q2-CC-B-STABILITY-REQUALIFICATION-20260808-V1/`
- Large dense operator and L2 field:
  `data/processed/q2_current_clamp_cc_b_stability_requalification/Q2-CC-B-STABILITY-REQUALIFICATION-20260808-V1/`
- Config: `configs/q2_cc_b_stability_requalification_v1.yaml`

PR, current-head CI, and merge identity are recorded in the final task handoff
after GitHub closure; they do not alter this numerical evidence.
