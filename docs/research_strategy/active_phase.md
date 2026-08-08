# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_after_invalid_fixed_lattice_equilibrium`

Current checkpoint: `Q2_CC_B_BRANCH_STABILITY_BRACKET_NUMERICAL_STOP`

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

The parent smoke and the valid PR #34 single-point requalification remain
immutable. A separately authorized branch stability/transition bracket then
produced:

```text
STOP_NUMERICAL_SEMANTICS_NOT_CLOSED
validity = invalid
local_evidence_status = FORBIDDEN
scientific_vote = false
formal_execution_count = 0
cc_b_matrix_launch_count = 0
```

Of 26 fixed L1/k6 points, 25 produced valid equilibria and fully certified
spectra (`max eta=6.621e-7`). Heating 0.35 mA exhausted the frozen full thermal
residual evaluation budget (`CCB_KRYLOV_BUDGET`) before spectrum execution.
R2 boundary refinement and R3 L2 qualification were therefore ineligible.
Nineteen transverse-dominated positive-unstable transition modes are retained
only as invalid-task diagnostic context. Uniform, the formal matrix, CC-C,
data, and PINN were not executed.

## Lifecycle And Claims

CC-A remains `executed/qualified_supported` bounded lumped evidence. PR #34 is
valid non-voting single-point instability evidence. The branch bracket is
`executed/invalid/forbidden`; CC-B, CC-C, GT, PINN, inverse, and all positive
R1-R3 claims remain forbidden. Scientific/formal/matrix counters are zero.

## Stop

Do not rerun this identity or start R2/R3, uniform/formal stages, patterned
branches, or CC-C/PINN. A new authorization may preregister one non-voting
telemetry closure for the heating 0.35 mA equilibrium failure, using the frozen
solver/config and reusing all other point artifacts unchanged.

## Preserved History

PR #31 `PASS_CC_A_CURRENT_CLAMP_ADMISSION`, PR #30 `A_STOP_STEADY_ROUTE`,
PR #29 `STOP_BRANCHCONSERVE_PILOT`, dynamic solver/controller stops, D0, and
equivalence-v1/v2/v3 remain immutable and were not rerun.
