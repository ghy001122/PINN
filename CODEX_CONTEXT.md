# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_BRANCHCONSERVE_BATCH1_STOPPED`.
- Active disposition: `STOP_BRANCHCONSERVE_PILOT`.
- Execution base: `main@5ef0fd5230aa910bcb5196e03eabece5a2e51bd6`.
- Result branch: `codex/q2-branchconserve-2d-steady-mve-v1`.
- `scientific_vote=false`; `formal_execution_count=0`.

Batch 1 implemented the independent temperature-primary steady solver and
executed a non-voting nominal L1 smoke plus dual-branch atlas/cost pilot.  The
smoke and heating branch succeeded, but the frozen 15.8 V cooling endpoint had
no contiguous high-conductive load-line bracket.  The common stable+reachable
source-voltage domain is empty, so the conditional L2 sentinel and all Batch 2
work were not executed.

The delivery ladder remains minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3.  None is unlocked by this result.

The valid terminal evidence is `failed_but_informative` numerical-method
evidence only.  It does not establish S2/Phase 1 physics, a steady forward
judge, rank-2 sensitivity, or a PINN result.  Batch 2 is not authorized.

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
