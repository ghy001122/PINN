# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CURRENT_CLAMP_CC_A_PASSED`.
- Active disposition: `PASS_CC_A_CURRENT_CLAMP_ADMISSION`.
- PR #30 merge base: `0230b036c271e02f52bc8d4b25f0021eb0d1870b`.
- CC-A code anchor: `230f1e37fbefd88d554d54009db626d175a00444`.
- Result branch: `codex/q2-current-clamp-source-consistent-2p5d-v1`.
- `scientific_vote=false`; `formal_execution_count=0`.

PR #30 and its valid `A_STOP_STEADY_ROUTE` result were merged unchanged. That
negative result remains binding for voltage-source-plus-series-load steady
operation. A new, independent ideal-current-clamp Batch 1 then executed CC-A
on the audited S1 major branches. Heating and cooling each produced 7/7 unique,
locally stable, continuation-connected roots over the frozen 0.1--0.7 mA
range. Their conductive-state spans were `0.7760256851` and `0.6754940767`,
and all seven common currents had branch-state separation above `0.1`.

The valid terminal result is `PASS_CC_A_CURRENT_CLAMP_ADMISSION` with
`claim_status=qualified_supported`. It establishes only a bounded lumped
branch-admission fact and eligibility to request CC-B.

The superseded checkpoint `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED` and its
`A_STOP_STEADY_ROUTE` disposition remain immutable historical evidence; the
new control topology does not rewrite that result.

The delivery ladder remains minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3.  None is unlocked by this result.

CC-B/CC-C, two-dimensional fields, data generation, rank-2 sensitivity, and
all PINN work were not executed and remain unauthorized. The result does not
establish a 2.5-D judge, S2/Phase 1 success, Qiu reproduction, dynamic branch
switching, or a PINN result.

Historical dynamic solver/controller, S0/equivalence results, and Frozen GT
remain unchanged.  Read `docs/research_strategy/context_loading_policy.md`
before loading long history.

Preserved historical checkpoints include
`Q2_NLS_REFERENCE_TIME_CONVERGENCE_V2_STOPPED` /
`STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4` and
`Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED` /
`B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`; D0 remains immutable.
Equivalence-v1/v2/v3 remain immutable and non-retryable, and
equivalence-v4/v5 remains forbidden.
