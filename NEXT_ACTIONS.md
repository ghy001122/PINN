# Next Actions

## Authoritative Current Queue

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_EXACT_CONDENSED_V2_D0_VALID_FAIL_NO_D1`.
- Plan disposition: `D0_MECHANISM_VALID_FAIL`.
- D0 exactly reproduced PR #24's frozen 10 ns v1 failure.
- Both explicit L1 Jacobians are full rank and direct corrections are finite.
- The fixed-point direction does not lower `||F_fp||inf` for any permitted
  damping `1...1/128`; first decrease is at forbidden `1/256`.
- No Jv rule was selected and no v2 production identity was created.
- D1/D2/B3/B4/fresh S0 were not started; `formal_execution_count=0`.
- Phase 2, MLP, vanilla PINN, C01, C06, seeds, OOD, and manuscript-result
  execution remain `forbidden` / unassessed.

## Single Next Priority

The current two-dimensional forward route is stopped by its frozen D0 gate. Do
not repair or retry it under this plan. The only plan-defined recommendation is
a separately authorized pivot:

```text
C04 observable-subspace + gamma_sub calibration gate
+ identifiability-boundary manuscript
```

This recommendation is not an execution authorization. Any future task must
create a new contract and preserve the D0, B2, Stage A, historical equivalence,
S2/controller, and Frozen GT evidence unchanged.
