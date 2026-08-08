# Q2 CC-B Patterned-Branch Decision MVE v1

## Verdict

```text
NO_GO_CC_B_STABLE_PATTERNED_TRANSITION_SPAN
validity = valid
claim_status = failed_but_informative
scientific_vote = false
formal_execution_count = 0
cc_b_matrix_launch_count = 0
patterned_mve_execution_count = 1
ground_truth_generated = false
pinn_executed = false
```

The bounded nonlinear search closed the uniform linear-boundary semantics,
constructed reflection-paired nonlinear patterned equilibria, and followed
both frozen major-branch identities with pseudo-arclength continuation. It did
not find a single locally stable patterned point: all 18 heating and 16 cooling
L1 patterned records were spectrum-certified and positive unstable. The
preregistered L2 gate was therefore ineligible. This is a valid negative result
for the frozen search domain, not evidence that other models or all nonlinear
branches are globally absent.

Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

## Identity And Scope

- Starting authority: `main@4c30021c45782e3803f1f285328e09b4411789df`
  (PR #35 merge).
- Branch: `codex/q2-cc-b-patterned-branch-decision-mve-v1`.
- Final numerical code anchor:
  `6c655955c7c8718c3e21248da55ef7887dbd3fdc`.
- Final run identity:
  `Q2-CC-B-PATTERNED-BRANCH-DECISION-MVE-20260808-V1-R4`.
- Final config SHA-256:
  `6f87fb2cd5385f40fcd34693575ea8ab234271398c81ed4da5df70215b6d14db`.
- Final terminal SHA-256:
  `9cf5030992d32720c0404c34838a4f123bb7a4cc84211bcd3b68f86d7aeb15b4`.
- Manifest: 772 repo-relative entries; all paths and SHA-256 values were
  independently re-read and verified.

The ideal algebraic conductive-channel current clamp, S1 device-effective
distributed proxy, S2 thermal totals, geometry, grid, equilibrium solver,
componentwise Jv step, fixed-current projection, ARPACK settings, Ritz gate,
and stability margin were unchanged. No LU/RD, 36-case matrix, Ground Truth,
PINN, inverse, dynamic S0, external RC, or source-voltage trajectory was run.

## Implementation And Focused Verification

The task added one versioned config, a runner, and a bounded orchestration
module. It reuses the production CC-B evaluator, equilibrium solve, constrained
temperature operator, Ritz certification, grid transfer, and atomic artifacts.
The new code supplies:

- side-effect-free 0.35 mA equilibrium telemetry;
- independent endpoint recomputation and three fixed bisections per branch;
- mass-normalized transverse-mode orientation and reflection checks;
- a bordered Newton--Krylov amplitude corrector;
- bounded pseudo-arclength continuation through folds;
- conditional L2 qualification and explicit skipped-stage artifacts;
- LF-stable CSV bytes, repo-relative manifests, plots, and fail-closed terminal
  routing.

Two local array-layout defects were exposed before scientific interpretation:
the augmented seed and mirror metric mixed flattened and `(ny,nx)` fields.
They were repaired only by deterministic shape canonicalization, each with a
regression. The V1 and V1-R1 invalid terminals were preserved locally and not
reinterpreted. R2 produced the same scientific NO-GO as R3; R3 completed the
preregistered skipped-L2 tables and heatmap. Final R4 changes only artifact
canonicalization: all nested CSV bytes are normalized to LF before manifest
hashing, closing the Git-stable-byte requirement without changing numerics.

Final focused command:

```text
.\.venv\Scripts\python.exe -m pytest -q \
  tests/test_q2_current_clamp_cc_a.py \
  tests/test_q2_current_clamp_cc_b.py \
  tests/test_q2_cc_b_stability_telemetry.py \
  tests/test_q2_cc_b_stability_requalification.py \
  tests/test_q2_cc_b_branch_stability_transition_bracket.py \
  tests/test_q2_cc_b_patterned_branch_mve.py

76 passed in 5.93 s
```

## Stage T: 0.35 mA Telemetry Closure

The exact frozen `NOM/heating/0.35 mA/L1` replay reproduced a genuine local
budget stop:

| Quantity | Result |
| --- | ---: |
| outcome | `CLOSED_TRUE_LOCAL_STAGNATION` |
| solver code | `CCB_KRYLOV_BUDGET` |
| full residual evaluations | 640 |
| Jv evaluations | 319 |
| LGMRES callbacks | 15 |
| Newton iterations reached | 3 |
| best scaled residual | `4.7307580e-10` |

The small historical residual does not certify an equilibrium because the
frozen last-update and final postcertification path were not completed. No
solver budget, initial-condition portfolio, or threshold was changed.

## Stage B: Candidate Linear-Stability Boundaries

All four endpoints were independently recomputed under the new identity. Three
deterministic bisections produced:

| Branch | Final bracket (mA) | Endpoint `alpha_tau` | Selected critical current (mA) |
| --- | --- | --- | ---: |
| heating | `[0.23750, 0.24375]` | `[-0.0564112, +0.0271825]` | 0.24375 |
| cooling | `[0.18125, 0.18750]` | `[-0.0327603, +0.0318249]` | 0.18750 |

Both selected modes passed the preregistered semantic screens:

| Metric | Heating | Cooling |
| --- | ---: | ---: |
| k6/k10 `alpha_tau` difference | `1.41e-14` | `2.30e-13` |
| leading spectral gap, scaled | `0.14259` | `0.14264` |
| operator/reflection equivariance error | `2.02e-11` | `1.92e-11` |
| odd-reflection residual | `1.51e-8` | `9.65e-9` |
| static/dynamic action error | `1.36e-16` | `1.22e-16` |
| analytic/FD current-column error | `4.75e-12` | `1.59e-11` |
| y-gradient energy fraction | `0.949995` | `0.950251` |

The crossings therefore close as simple, transverse, reflection-odd candidate
linear-stability boundaries with a static near-null direction. They are not a
proof of a dynamical bifurcation, filament formation, or real-device symmetry
breaking.

## Stage S: Augmented Branch Switching

The frozen amplitude ladder attempted both orientations at `0.05 w_T*` and
`0.10 w_T*`. All 8 bordered correctors converged and passed equilibrium,
ledger, range, reflection, and k6 spectrum certification.

| Quantity | Result |
| --- | ---: |
| maximum augmented residual | `6.77e-14` |
| maximum last update | `8.54e-10` |
| maximum mirror-pair error | `7.55e-10 K` |
| observed amplitude range | `0.09882...0.19794 K` |
| stable augmented roots | 0/8 |

Thus the transverse linear modes do connect locally to nonlinear
reflection-paired patterned equilibria, but the obtained roots remain positive
unstable.

## Stage C: Bounded Pseudo-Arclength Atlas

| Quantity | Heating | Cooling |
| --- | ---: | ---: |
| accepted L1 patterned records | 18 | 16 |
| sampled current range (mA) | `0.177129...0.295408` | `0.129028...0.237859` |
| `alpha_tau` range | `0.005616...2.297345` | `0.007984...0.920379` |
| spectrum-certified stable records | 0 | 0 |
| transition-bearing records | 17 | 16 |
| maximum patterned amplitude | `1.5390 K` | `1.3144 K` |
| maximum Ritz `eta` | `1.840e-7` | `3.045e-7` |

Across all 34 records, the maximum scaled thermal residual was `6.35e-14`,
maximum last update `7.33e-9`, maximum scaled electrical residual `4.65e-16`,
and maximum ledger error `3.91e-14`. Temperatures remained
`326.274...339.269 K`, and the largest device voltage was `6.966 V`.

Some continuation directions returned to the reflection-symmetric branch;
those zero-amplitude points were retained in the atlas but failed the patterned
gate. The nonzero patterned direction also remained positive unstable. No
stable-transition L1 component existed.

## Stage Q And Claim Boundary

Stage Q is explicitly `SKIPPED_NO_L1_CANDIDATE`. Its empty
`l2_anchor_qualification.csv`, `reflection_pair_metrics.csv`, selected-anchor
record, and stage JSON are present. Consequently:

- no L2 patterned equilibrium was run;
- no patterned-anchor L1/L2 or k6/k10 qualification exists;
- no span, M1d, Ground Truth, or C01 unlock occurred.

Allowed manuscript sentence:

> In the frozen ideal-current-clamp, source-scale-anchored two-dimensional
> electrothermal proxy, certified transverse stability crossings connect to
> reflection-paired nonlinear patterned equilibria; however, all 34 bounded
> continuation records remain locally unstable, so the preregistered search
> yields no stable transition-bearing patterned span.

Forbidden are global nonexistence, conductive-filament formation, dynamic
attractor or ramp accessibility, equivalence to the Qiu source-voltage/RC
experiment, intrinsic local VO2 validation, or any positive GT/PINN claim.

## Runtime And Artifacts

The final R4 used `205.897 s` wall and `187.578 s` CPU with one worker,
one BLAS/OpenMP thread, and no GPU. All final stage caps passed. Including the
two early invalid layout attempts and the valid R2 precursor, numerical wall
time remained under eight minutes and inside the aggregate authorized budget.

- Compact evidence:
  `outputs/tables/q2_cc_b_patterned_branch_decision_mve/Q2-CC-B-PATTERNED-BRANCH-DECISION-MVE-20260808-V1-R4/`
- Recoverable arrays:
  `data/processed/q2_cc_b_patterned_branch_decision_mve/Q2-CC-B-PATTERNED-BRANCH-DECISION-MVE-20260808-V1-R4/`
- Config: `configs/q2_cc_b_patterned_branch_decision_mve_v1.yaml`.

## Single Next Priority

Do not launch M1d, GT, C01, another current bracket, or a solver/network
portfolio. The current-clamp steady GT/PINN route is stopped by this valid
negative boundary. The only appropriate next action is a concise route
closeout/manuscript decision that preserves this Figure 1 negative atlas and
chooses a genuinely different, separately authorized physical premise if the
project continues.

PR, current-head CI, and merge identity are recorded at GitHub closure; they
do not alter the numerical disposition.
