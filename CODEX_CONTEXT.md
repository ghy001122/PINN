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

The separately authorized telemetry closure regenerated and persisted the
nominal-heating 0.4 mA L1 equilibrium before stability, then reproduced the
merged-PR32 L1/k6 numerical contract with 256 recorded Jv calls. Input,
mass, electrical, fixed-current, finite/repeatable Jv, h/h2, ARPACK return,
artifact, and terminal gates passed. ARPACK returned six finite pairs, but all
six failed the frozen relative Ritz-residual gate (`eta=1.689e-5...3.230e-5`
versus `1e-6`). The valid non-voting terminal is therefore telemetry closure
with `closure_class=implementation_invalidity_localized`, not a certified
stability result. T2 was not run; attempt count is one and repair count zero.

Do not interpret the positive raw Ritz values as physical instability: the
pairs are uncertified. CC-B remains scientifically `forbidden`; uniform,
L2/k6, k10, the 36-case matrix, CC-C, GT, and all PINN work remain unexecuted.
A new explicit authorization is required for any stability requalification.
Historical PR #29/#30/#31/#32 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
