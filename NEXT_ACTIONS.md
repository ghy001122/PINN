# Next Actions

## Authoritative Current Queue

- Phase/checkpoint: `Q2_PHASE1_2P5D_REFERENCE_SOLVER` /
  `Q2_CC_B_STABILITY_TELEMETRY_CLOSED`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Parent disposition: `INVALID_CC_B_EXECUTION`.
- Diagnostic disposition: `PASS_CC_B_STABILITY_TELEMETRY_CLOSURE`.
- The algebraic conductive-channel clamp implementation exists and focused
  tests pass, but the paired smoke became invalid at the first 0.4 mA
  constrained-stability certification.
- Two non-voting 0.2 mA nominal-heating equilibrium records are valid locally;
  they do not vote for CC-B physics.
- `cc_b_matrix_launch_count=0`, `scientific_vote=false`, and
  `formal_execution_count=0`.
- The new L1/k6 telemetry path closes through ARPACK return, then localizes the
  invalidity at Ritz certification: six finite pairs return, but 0/6 meet the
  frozen relative-residual gate. No physical stability sign is certified.
- Uniform, L2, k10, budget, formal matrix, CC-C, data, PINN, CC01, CC06,
  inverse, and refusal were not executed and remain unauthorized.

## Single Next Priority

The telemetry task is complete and must not be replayed. If the route is
reopened, authorize one versioned, bounded
`Q2_CC_B_STABILITY_REQUALIFICATION_V1`. Its first question is whether the
frozen constrained operator can produce a Ritz-certified spectrum at the
required resolution without changing topology, source, Jv, eigensolver, or
thresholds. It must preserve the current T1 artifacts, forbid post-hoc tuning,
and stop before the 36-case matrix or any PINN work.
