# Next Actions

## Authoritative Current Queue

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_EXACT_CONDENSED_B2_VALID_FAIL_NO_S0`.
- Goal disposition: `B2_REDUCED_ROOT_VALID_FAIL`.
- B1 exact-condensed implementation exists and passed focused software/parity
  checks; no performance or scientific claim follows.
- B2 stopped on root 1/24 with `ARMIJO_LINE_SEARCH_FAILURE`; 0 roots passed and
  23 remain unassessed.
- Last reduced/full scaled residual: `9.519603587211078e-3`; auxiliary residual:
  `1.4392805451179502e-16`; full fixed-point defect was not certified.
- B3/B4/fresh S0 were not started; `formal_execution_count=0`.
- Phase 2, MLP, vanilla PINN, C01, C06, baselines, seeds, and OOD were not
  executed and remain forbidden.

## Single Next Priority

No experiment is authorized. If research is reopened, use a fresh versioned
goal for one materially different reduced-root globalization/Jacobian strategy,
with the same S2 physics, controller-v2 semantics, `1e-8` full residual/defect
certification, ledgers, and fail-fast qualification gates.

It must not:

1. resume or reinterpret `B2-EXACT-CONDENSED-20260803-V1`;
2. add a second solver strategy under the consumed goal;
3. modify frozen Stage A, production solver/NLS/controller, scientific thresholds, or Frozen GT;
4. rerun equivalence-v1/v2/v3 or create equivalence-v4/v5;
5. bypass a complete valid S0 judge to generate Phase 2 data or train PINN;
6. restore S1/K-state, fallback portfolios, gamma_sub, FEM/3D, NbO2, inverse, or nonzero coupling.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains
immutable and non-retryable. No retry is authorized.
