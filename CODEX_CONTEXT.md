# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Delivery ladder: `HysGeo-Hybrid-PINN`, `GeoPhase-HomoMoE-PINN`, R3; no unlock.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CC_B_STABILITY_REQUALIFIED_POSITIVE_UNSTABLE`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Preserved parent CC-B disposition: `INVALID_CC_B_EXECUTION`.
- Stability-requalification disposition: `PASS_CC_B_STABILITY_REQUALIFICATION`.
- Baseline before this task: `main@b3d8e5a67be09f9bc8fcc908c3fe4ca0a8aba4ee`.
- Code anchor: `616fd9b2673f9591ff58900354c38dd3f9a6c1f9`.
- `cc_b_matrix_launch_count=0`; `scientific_vote=false`;
  `formal_execution_count=0`.

CC-A remains `qualified_supported` bounded lumped evidence. CC-B uses an ideal
algebraic conductive-channel clamp with temperature-only dynamics and
`Vd=I_set/G_hat(T)`; S1 is only a device-effective proxy.

The componentwise Jv correction gives `h=2.0373376e-3 K`. L1/L2 k6/k10
certify every pair (`max eta=3.375e-7`); a 250-state dense reference passes.
All classify `NOM/heating/0.4 mA` as `POSITIVE_UNSTABLE`
(`alpha_tau=2.34577...2.34587`).

This is valid non-voting single-point stability evidence, not a complete CC-B
science result. Uniform, the formal matrix, CC-C, GT, and PINN remain
unexecuted and require new authorization. The next admissible request is a
separate preregistered finite current bracket; it was not started.
Historical PR #29/#30/#31/#32 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
