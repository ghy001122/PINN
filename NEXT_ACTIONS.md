# Next Actions

## Authoritative Current Queue

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_NLS_V1_QUALIFICATION_REJECTED_NO_S0`.
- Goal disposition: `GOAL_UNSUCCESSFUL_NLS_V1`.
- Both frozen nonlinear failure states pass the NLS dual residual/defect gate.
- Required standard 9 V qualification: stopped at 3413/4001 outputs and `17.06015625 us` after `27136.6188 s`, beyond the frozen `21600 s` per-run cap.
- Conditional Schur upgrade: not activated because its frozen-replay trigger was false.
- Fresh S0 not started; `formal_execution_count=0`.
- Phase 2/C01/C06/baselines/OOD: not executed and forbidden.

## Single Next Priority

No experiment is authorized. If the route is reopened, create a new bounded goal for a performance-efficient, mathematically equivalent reduced nonlinear solver. It must retain S2 physics, protocols, `1e-8` residual/defect gates, ledger/event gates, and the full standard/strict qualification trajectories.

It must not:

1. resume `NLSV1-QUAL-20260802-V1/V2` or activate Schur under the consumed goal;
2. add controller candidate 3/controller-v4;
3. rerun equivalence-v1/v2/v3 or create equivalence-v4/v5;
4. bypass a complete valid S0 judge to generate Phase 2 data or train PINN;
5. restore S1/K-state, gamma_sub, FEM/3D, NbO2, inverse, or nonzero coupling.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains immutable and non-retryable. No retry is authorized.
