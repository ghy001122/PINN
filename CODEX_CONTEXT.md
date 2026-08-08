# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Delivery ladder: `HysGeo-Hybrid-PINN`, `GeoPhase-HomoMoE-PINN`, R3; no unlock.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CC_B_BRANCH_STABILITY_BRACKET_NUMERICAL_STOP`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Preserved parent CC-B disposition: `INVALID_CC_B_EXECUTION`.
- Stability-requalification disposition: `PASS_CC_B_STABILITY_REQUALIFICATION`.
- Branch-bracket disposition: `STOP_NUMERICAL_SEMANTICS_NOT_CLOSED`.
- Baseline before this task: `main@22ed32018d5463e171be960beb00710a055a1f13`.
- Code anchor: `3e46d9ff60c4764be1c64a730c54111daa5bd84c`.
- `cc_b_matrix_launch_count=0`; `scientific_vote=false`;
  `formal_execution_count=0`.

CC-A remains `qualified_supported` bounded lumped evidence. CC-B uses an ideal
algebraic conductive-channel clamp with temperature-only dynamics and
`Vd=I_set/G_hat(T)`; S1 is only a device-effective proxy.

The preregistered 26-point L1/k6 lattice produced 25 equilibrium-valid,
spectrum-certified points (including one exact PR #34 reuse). Heating 0.35 mA
exhausted the frozen full-residual evaluation budget before a valid equilibrium,
so R2 boundary refinement and R3 L2 anchor qualification were not executed.
The terminal is invalid and all stable-span/patterned-branch claims remain
forbidden. Nineteen transverse-dominated positive-unstable transition-mode
records are retained as non-voting diagnostics only.

The only admissible next request is a versioned, non-voting telemetry closure
for the single heating 0.35 mA equilibrium failure. It may not modify physics,
solver budgets, or reuse the other 25 points as a scientific vote.
Historical PR #29/#30/#31/#32 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
