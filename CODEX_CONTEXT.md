# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Delivery ladder: minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
  `GeoPhase-HomoMoE-PINN`, and conditional `R3`; the current CC-B result
  unlocks none of them.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CC_B_STABILITY_TELEMETRY_CLOSED`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Preserved parent CC-B disposition: `INVALID_CC_B_EXECUTION`.
- Active diagnostic disposition: `PASS_CC_B_STABILITY_TELEMETRY_CLOSURE`.
- Baseline before this task: `main@1d2b3d66eaec3faa908c0e377a7da92467c76b00`.
- Execution branch: `codex/q2-cc-b-stability-telemetry-closure-v1`.
- `cc_b_matrix_launch_count=0`; `scientific_vote=false`;
  `formal_execution_count=0`.

CC-A remains valid `qualified_supported` lumped source-model evidence: all 14
fixed S1 major-branch roots were unique, locally stable, range-legal, and
continuation-connected. It did not itself validate a 2-D model.

The separately authorized CC-B implementation freezes an ideal algebraic
conductive-channel current clamp. Temperature cells are the only dynamic
state; every field residual resolves the unit-bias conservative electrical
problem and sets `Vd=I_set/G_hat(T)`. The Qiu parallel capacitance, external RC,
load line, and terminal-total-current clamp are absent. S1 is used only as a
source-scale-anchored device-effective distributed proxy, not an intrinsic
local VO2 conductivity.

Telemetry T1 persisted the 0.4 mA L1 input and reproduced the merged-PR32
L1/k6 contract. Input/operator/ARPACK paths passed, but 0/6 finite pairs met
the frozen Ritz gate (`eta=1.689e-5...3.230e-5 > 1e-6`). Thus
`PASS_CC_B_STABILITY_TELEMETRY_CLOSURE` localizes implementation invalidity;
it certifies no stability sign. T2 was not run (attempts 1, repairs 0).

CC-B science remains `forbidden`; L2, k10, uniform, the formal matrix, CC-C,
GT, and PINN remain unexecuted and require new authorization.
Historical PR #29/#30/#31/#32 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
