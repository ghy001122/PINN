# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Delivery ladder: `HysGeo-Hybrid-PINN`, `GeoPhase-HomoMoE-PINN`, R3; no unlock.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CC_B_PATTERNED_BRANCH_VALID_NO_GO`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Preserved parent CC-B disposition: `INVALID_CC_B_EXECUTION`.
- Stability-requalification disposition: `PASS_CC_B_STABILITY_REQUALIFICATION`.
- Branch-bracket disposition: `STOP_NUMERICAL_SEMANTICS_NOT_CLOSED`.
- Patterned-MVE disposition: `NO_GO_CC_B_STABLE_PATTERNED_TRANSITION_SPAN`.
- Baseline before this task: `main@4c30021c45782e3803f1f285328e09b4411789df`.
- Patterned-MVE code anchor: `6c655955c7c8718c3e21248da55ef7887dbd3fdc`.
- `cc_b_matrix_launch_count=0`; `scientific_vote=false`;
  `formal_execution_count=0`.

CC-A remains `qualified_supported` bounded lumped evidence. CC-B uses an ideal
algebraic conductive-channel clamp with temperature-only dynamics and
`Vd=I_set/G_hat(T)`; S1 is only a device-effective proxy.

The patterned MVE validly closed the 0.35 mA frozen-budget stop, both candidate
boundaries, 8 mirror-paired roots, and 34 L1 continuation records. All 34 are
certified positive unstable; L2 was ineligible. This is bounded
`failed_but_informative` evidence, not complete CC-B or global nonexistence.

Do not launch M1d, matrix/GT/PINN/inverse, or another search. Next: route
closeout, or a separately justified physical premise without proxy retuning.
Historical PR #29/#30/#31/#32 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
