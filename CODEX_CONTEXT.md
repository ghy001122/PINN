# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Delivery ladder: minimum R1 `HysGeo-Hybrid-PINN`, preferred R2
  `GeoPhase-HomoMoE-PINN`, and conditional `R3`; the current CC-B result
  unlocks none of them.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CURRENT_CLAMP_CC_B_INVALID`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Active disposition: `INVALID_CC_B_EXECUTION`.
- Baseline before this task: `main@618103321441abac36c9a9836ff6b0cc30e2c76e`.
- Execution branch: `codex/q2-cc-a-topology-closure-cc-b-2d-gate-v1`.
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

Focused CC-A/CC-B tests ended `22 passed`. The paired non-voting smoke then
published valid nominal-heating 0.2 mA L1/L2 equilibrium records, but the first
0.4 mA stability certification returned `INVALID_STABILITY`. Because the two
allowed implementation-repair cycles had already been consumed, the task
stopped without repair or rerun. Uniform mapping/operator gates, the budget
gate, the one-shot 36-case matrix, CC-C, GT, and all PINN work were not run.

Do not interpret this as physical instability, CC-B failure, S2 failure, or a
PINN result. A new explicit authorization is required even for a stability
telemetry closure. Historical PR #29/#30/#31 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
