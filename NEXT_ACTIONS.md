# Next Actions

## Authoritative Current Queue

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CONTROLLER_V3_EXHAUSTED_NO_S0`.
- Goal disposition: `GOAL_UNSUCCESSFUL_CONTROLLER_V3_EXHAUSTED`.
- Candidate 1: rejected at the locked outer floor in the first 9 V qualification trajectory.
- Candidate 2: bounded subfloor recovery reached the frozen per-case rejection cap in the same trajectory.
- Controller numerical policy budget: 2/2 consumed.
- Published qualification runs: 0.
- Fresh S0 not started; `formal_execution_count=0`.
- Phase 2/C01/C06/baselines/OOD: not executed and forbidden.

## Single Next Priority

No experiment is authorized. If the route is reopened, use a new versioned goal for a bounded nonzero-drive implicit-solver convergence study based on the two immutable controller failure states. Its purpose is to determine whether the shared nonlinear step can converge without changing S2 physics, protocols, or scientific thresholds.

It must not:

1. resume V2/V4 or add a third controller-v3 candidate;
2. rerun equivalence-v1/v2/v3 or create equivalence-v4/v5;
3. bypass a complete valid S0 judge to generate Phase 2 data or train PINN;
4. restore S1/K-state, gamma_sub, FEM/3D, NbO2, inverse, or nonzero coupling.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains immutable and non-retryable. No retry is authorized.
