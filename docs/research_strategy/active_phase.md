# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_after_invalid_cc_b_smoke`

Current checkpoint: `Q2_CURRENT_CLAMP_CC_B_INVALID`

Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`

Preserved historical stop identities:

- `STOP_REFERENCE_NOT_ASYMPTOTIC_OR_INVALID_T4`
- `B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`
- `Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED`

Equivalence-v1/v2/v3 remain immutable and non-retryable; equivalence-v4/v5
remain forbidden.

## Objective And Result

The independently authorized CC-B task closed the intended control topology as
an **ideal algebraic conductive-channel current clamp**: temperature cells are
the only dynamic state, the conductive sheet current is constrained to
`I_set`, and `Vd=I_set/G_hat(T)` is algebraic. The Qiu parallel capacitance is
inactive external-source metadata and is absent from CC-B equilibrium and
stability.

The CC-B implementation, focused tests, and non-voting paired smoke were run.
The 0.2 mA nominal-heating L1/L2 equilibria produced valid atomic records with
current, power, thermal-ledger, and residual checks passing. The next 0.4 mA
stability call returned `INVALID_STABILITY` before a publishable smoke case was
formed. The terminal disposition is therefore:

```text
INVALID_CC_B_EXECUTION
validity = invalid
cc_b_scientific_vote = false
cc_b_matrix_launch_count = 0
scientific_vote = false
formal_execution_count = 0
```

This is not a valid CC-B PASS or scientific FAIL. Uniform gates, the resource
projection, all 36 formal grid-case solutions, CC-C, data generation, and PINN
work were not executed.

## Lifecycle And Claims

- CC-A: `executed`; `qualified_supported` bounded lumped branch-admission
  evidence remains unchanged.
- CC-B implementation: `implemented`; claim status `forbidden`.
- CC-B smoke: `executed` with `validity=invalid`; claim status `forbidden`.
- CC-B scientific result, 2.5-D judge, CC-C, CC01, CC06, inverse, and all
  positive R1-R3 claims remain `forbidden` / unassessed.
- Historical global counters remain `scientific_vote=false` and
  `formal_execution_count=0`; the CC-B matrix launch count is also zero.

## Stop

The two preregistered implementation-repair cycles were consumed before the
smoke. Do not repair, rerun, resume, execute the uniform/budget/formal stages,
or start CC-C/PINN under this task identity. Reopening requires a new bounded
authorization that treats this invalid run as immutable and first closes the
stability failure telemetry without changing topology, source physics, cases,
or thresholds.

## Preserved History

PR #31 `PASS_CC_A_CURRENT_CLAMP_ADMISSION`, PR #30 `A_STOP_STEADY_ROUTE`,
PR #29 `STOP_BRANCHCONSERVE_PILOT`, dynamic solver/controller stops, D0, and
equivalence-v1/v2/v3 remain immutable and were not rerun.
