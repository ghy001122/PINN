# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Delivery ladder: historical/high-spec R1 `HysGeo-Hybrid-PINN`, active fallback R1-Lite `GeoState-MC-Hybrid-PINN`, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3.
- Active phase: `Q2_PHASE1C_M1_ROBIN_CONTROL_VOLUME_PINN_RESCUE`.
- Checkpoint: `Q2_M1_ROBIN_CONTROL_VOLUME_PINN_RESCUE_V1_VALID_NO_GO`.
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

The ideal-current-clamp route is immutable and terminal; do not rerun, repair,
retune, or reinterpret it. The separately authorized active premise is
`state-conditioned quasi-static electrothermal fields` on the Qiu-inspired
coplanar 2.5D geometry. This round is a model-form and single-seed engineering
screen only; a positive PINN superiority claim remains `forbidden`.
The valid fast-track selected M1 (contact Robin closure) as the simplest
reference. B0/B1/M0 each completed 1000 Adam steps, but M0 passed zero complete
test cases (`T` relative L2 mean `0.21194`, energy error `0.14167`, interface
mismatch `0.74008`), giving `NO_GO_GEOSTATE_PINN_IDEA_SCREEN`. The first M2
downstream attempt is immutable invalid metric evidence and does not vote.
PR #37 and those metrics were preserved unchanged and squash-merged as
`183f129545a2a047137745d36a0c432d02a28219`.

The sole M1 Robin/control-volume structural rescue reused the frozen 12-case
teacher without rerunning a reference solve. Teacher/objective compatibility
passed 12/12 cases. B0-R/B1-R/P0-RCV each completed exactly 1500 Adam steps at
seed `20260809`, but all passed 0/2 complete test cases. P0-RCV mean T-rise,
phi, current, energy, interface, current-CV, and energy-CV errors were
`0.61932`, `0.18294`, `0.89136`, `0.87358`, `0.10295`, `0.00496`, and
`0.94696`, giving `NO_GO_M1_RCV_PINN_RESCUE`. Direct coordinate-PINN
architecture expansion is terminal; formal OOD remains forbidden.
Historical PR #29/#30/#31/#32 results, dynamic stops, D0,
equivalence-v1/v2/v3, and Frozen GT remain immutable.
