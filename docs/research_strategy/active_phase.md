# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_exact_condensed_b2_valid_root_failure`

Current checkpoint: `Q2_EXACT_CONDENSED_B2_VALID_FAIL_NO_S0`

## Objective And Frozen Authority

The goal introduced an independent exact temperature-primary condensed solver
and controller orchestration, then required 24/24 frozen reduced roots before
any matched-window, cost, full-trajectory, S0, data, or PINN work. S2 equations,
parameters, protocols, controller-v2, production implicit/NLS code, thresholds,
Stage A evidence, historical outputs, and Frozen GT remained read-only.

## Actual B1/B2 Result

B1 focused checks support only an `implemented` software lifecycle state. The
preregistered B2 run `B2-EXACT-CONDENSED-20260803-V1` then executed the first
frozen root (`B2-ORIGINAL-S1-DT10p0NS`). Five Newton corrections were accepted,
six LGMRES calls converged, and the auxiliary algebraic residual remained
`1.4392805451179502e-16`. At the next correction, every permitted damping from
`1` through `1/128` failed Armijo. The last available reduced/full scaled
residual was `9.519603587211078e-3`; no final full fixed-point defect was
certified.

Terminal state: `B2_REDUCED_ROOT_VALID_FAIL`.

## Lifecycle And Claims

- Exact-condensed solver/controller: `implemented`; software fact only.
- B2 qualification: `executed`; `failed_but_informative` numerical-method
  evidence for this frozen solver identity.
- Roots: 1/24 executed, 0 passed, 23 unassessed.
- `scientific_vote=false`; `formal_execution_count=0`.
- B3, B4, fresh S0, Phase 2, MLP, vanilla PINN, C01, C06, OOD, and R1/R2/R3:
  not executed and `forbidden`.

This boundary is not an S2 physical-law failure, runtime/campaign feasibility
result, Phase 1 vote, PINN result, Qiu quantitative reproduction, or
experimental validation.

## Stop And Next Bottleneck

The goal's only permitted solver strategy failed its first valid B2 root, so
all downstream stages are closed. No experiment is authorized. A future goal
may investigate one materially new reduced-root globalization/Jacobian identity
under the same physics, controller, residual/defect, ledger, and budget gates.
It may not resume this matrix, add another strategy under this goal, return to
equivalence, or bypass S0 before Phase 2/C01.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains
immutable and non-retryable. Equivalence-v4/v5 is forbidden (`equivalence-v4/v5`).
No retry is authorized.
