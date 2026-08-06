# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Active disposition: `A_STOP_STEADY_ROUTE`.
- Execution base: `main@0877714dbed92d4d43f031fab5032f5cbd56eae8`.
- Result branch: `codex/q2-qiu-source-consistent-branchconserve-v2`.
- `scientific_vote=false`; `formal_execution_count=0`.

PR #29 and its valid `STOP_BRANCHCONSERVE_PILOT` result were merged unchanged.
The separate v2 Stage A source audit then verified the Qiu S1--S7 formulas and
ran an independent 0-D fixed-point, local-stability, and continuous
quasistatic-reachability oracle. The direct `beta+k` patch was rejected. Under
S1, the 12 kOhm high-conductive roots at 15.8/17 V are algebraically present
but locally unstable. The preregistered 3/6/9/12/18/24/36 kOhm sentinel found
no dual-branch or forward domain meeting the nondegenerate-transition gate.
The terminal result is valid `failed_but_informative` source-oracle evidence.

The delivery ladder remains minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3.  None is unlocked by this result.

Stage B L1, B1/B2, Phase 2, rank-2 sensitivity, and all PINN work were not
executed and remain unauthorized. The result does not establish S2/Phase 1
physics or failure, a two-dimensional steady judge, Qiu reproduction, or a
PINN result.

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
