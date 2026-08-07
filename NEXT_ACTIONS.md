# Next Actions

## Authoritative Current Queue

- Phase/checkpoint: `Q2_PHASE1_2P5D_REFERENCE_SOLVER` /
  `Q2_CURRENT_CLAMP_CC_B_INVALID`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Disposition: `INVALID_CC_B_EXECUTION`.
- The algebraic conductive-channel clamp implementation exists and focused
  tests pass, but the paired smoke became invalid at the first 0.4 mA
  constrained-stability certification.
- Two non-voting 0.2 mA nominal-heating equilibrium records are valid locally;
  they do not vote for CC-B physics.
- `cc_b_matrix_launch_count=0`, `scientific_vote=false`, and
  `formal_execution_count=0`.
- Uniform, budget, formal matrix, CC-C, data, PINN, CC01, CC06, inverse, and
  refusal were not executed and remain unauthorized.

## Single Next Priority

The proposed stability telemetry closure is not authorized under the current
task.

If the route is reopened, authorize a new versioned, non-voting
`CC_B_STABILITY_TELEMETRY_CLOSURE` only. It must preserve the present topology,
source mapping, cases, and gates; reproduce the 0.4 mA stability failure once,
persist the exact sub-gate and Ritz/Jv telemetry, and decide whether the failure
is implementation invalidity or a valid unstable spectrum. It must not launch
the 36-case matrix or any PINN work without a new downstream authorization.
