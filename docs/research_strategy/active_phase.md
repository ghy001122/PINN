# Active Phase

Active phase ID: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`

Status: `stopped_after_valid_single_point_positive_instability`

Current checkpoint: `Q2_CC_B_STABILITY_REQUALIFIED_POSITIVE_UNSTABLE`

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

The parent smoke remains immutable `INVALID_CC_B_EXECUTION`. A separately
authorized componentwise-step repair and requalification produced:

```text
PASS_CC_B_STABILITY_REQUALIFICATION
validity = valid
stability_certification_status = VALID
physical_spectrum_classification = POSITIVE_UNSTABLE
stable = false
scientific_vote = false
formal_execution_count = 0
cc_b_matrix_launch_count = 0
```

The corrected L1 step is `2.0373376e-3 K`. L1/L2 k6/k10 certify all requested
pairs (`max eta=3.375e-7`), and the L1 dense full-spectrum reference agrees.
All four spectra classify the single 0.4 mA point as positive unstable with
`alpha_tau=2.34577...2.34587`. Uniform, the formal matrix, CC-C, data, and PINN
were not executed.

## Lifecycle And Claims

- CC-A: `executed`; `qualified_supported` bounded lumped branch-admission
  evidence remains unchanged.
- CC-B implementation: `implemented`; claim status `forbidden`.
- Parent CC-B smoke: `executed`, invalid, immutable, and `forbidden`.
- Stability requalification: `executed`, valid non-voting single-point
  positive-instability evidence; complete CC-B science remains `forbidden`.
- CC-B scientific result, 2.5-D judge, CC-C, CC01, CC06, inverse, and all
  positive R1-R3 claims remain `forbidden` / unassessed.
- Historical global counters remain `scientific_vote=false` and
  `formal_execution_count=0`; the CC-B matrix launch count is also zero.

## Stop

Do not rerun this identity or start uniform/formal stages or CC-C/PINN. A new
authorization may preregister one finite current bracket to test for stable
transition-bearing coverage. It may not tune currents after inspection or
convert this single-point result into a complete CC-B vote.

## Preserved History

PR #31 `PASS_CC_A_CURRENT_CLAMP_ADMISSION`, PR #30 `A_STOP_STEADY_ROUTE`,
PR #29 `STOP_BRANCHCONSERVE_PILOT`, dynamic solver/controller stops, D0, and
equivalence-v1/v2/v3 remain immutable and were not rerun.
