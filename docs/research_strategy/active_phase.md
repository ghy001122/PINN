# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_nls_v1_qualification_performance_gate`

Current checkpoint: `Q2_NLS_V1_QUALIFICATION_REJECTED_NO_S0`

## Objective And Frozen Authority

The goal repaired the shared implicit fallback so success requires both the full fixed-point defect and frozen scaled residual at `1e-8`, then attempted bounded standard/strict qualification before any fresh S0 or PINN work. S2 equations, physical parameters, protocols, controller-v2, scientific thresholds, and the 63/60/3 plan remained frozen.

Historical E0/S0/controller/equivalence outputs and Frozen GT v1.1 remained read-only.

## Actual NLS Qualification

| Evidence | Result | Disposition |
| --- | --- | --- |
| Frozen failure replay V2 | residual `4.884209208104767e-9`, defect `5.008622738778001e-9`, 6 iterations | pass |
| Frozen failure replay V4 | residual `5.853515129323472e-9`, defect `4.958286003997614e-9`, 4 iterations | pass |
| Standard quiescent 9 V T1 | 3413/4001 outputs; reached `17.06015625 us`; `27136.6188 > 21600 s` | performance gate failed |
| Strict quiescent 9 V T4 | final residue `1.73133534418779e-17 s`; full NLS residual/defect passed but ledger cancellation failed | invalid endpoint defect |

The endpoint tolerance mismatch was corrected under the `phase1_s2_dual_gate_nonlinear_solver_v1p1_endpoint_tolerance` identity and covered by focused regression. It cannot alter the earlier T1 path or its frozen wall-time rejection, so no long V2 rerun was launched. The conditional Schur-reduced upgrade was not eligible because both frozen failure replays passed.

Terminal state: `GOAL_UNSUCCESSFUL_NLS_V1`.

## Lifecycle And Claims

- NLS-v1/v1p1 implementations: `implemented`; software fact `supported`.
- NLS-v1 qualification: `executed`; `failed_but_informative` bounded numerical-performance evidence.
- Fresh S0: not started; `forbidden` / unassessed.
- `formal_execution_count=0`.
- Phase 2, MLP, vanilla PINN, C01, C06, OOD, and R1/R2/R3: not executed and `forbidden`.

This boundary is not an S2 physical-law failure, Phase 1 scientific vote, or PINN result.

## Stop And Next Bottleneck

An intervening bounded Stage A diagnostic proved that `s`, `b`, and `Vd` are
exactly condensable within each frozen backward-Euler step when prior full state
history is retained. No reduced nonlinear solver or trajectory was executed.

No experiment is authorized. A future goal may assess a new exact
temperature-primary condensed nonlinear solver under the unchanged full
qualification gates. It may not resume this qualification, use learned or
tabulated closures, add controller candidate 3/controller-v4, relax gates,
return to equivalence, or bypass S0 before Phase 2/C01.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains immutable and non-retryable. Equivalence-v4/v5 is forbidden (`equivalence-v4/v5`). No retry is authorized.
