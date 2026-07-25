# Next Actions

## Authoritative Current Queue

Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.

There is exactly one active task:

> Implement and validate an independent, conservative, PINN-residual-separated Qiu-inspired VO2 real x-y plus K-state vertical-memory 2.5D FVM/implicit reference solver.

## Manuscript Use

This solver is the numerical truth judge for later R1 fields, ports, phase events, interfaces, RC behavior, and energy ledgers. Without it, no positive new-route PINN claim is eligible.

## Required Inputs

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_contract.md`
- `configs/geophase_phase1_2p5d_reference.yaml`
- `configs/geo2p5d_stage.yaml`
- `docs/method_equations.md`
- source/provenance contracts routed by the Phase 1 config

## Execution Order

1. Confirm equation, coordinate, geometry, material, boundary, circuit, ledger, budget, and output schemas.
2. Implement the independent electrical, thermal, K-state, hysteresis, circuit, and ledger pieces under responsibility-based modules; do not share the PINN discrete residual implementation.
3. Add behavioral tests for manufactured solutions, failure paths, SI units, ports, passivity, and ledgers.
4. Run smoke and focused verification before the single formal bounded execution.
5. Write JSON/CSV, figures/tables, a report, claim-matrix row, and manuscript-eligible sentence only after all gates are evaluated.

## Required Gates

- manufactured electrical and thermal solutions;
- terminal-current conservation;
- active-plane plus K-state full energy ledger;
- independent mesh and time-step refinement on fixed physical comparison grids;
- K-state positive capacity/conductance, stable poles, passivity, and high-order reference alignment;
- zero-drive, uniform-conductivity, decoupled/symmetric single-dual-device limits;
- literature-trend sanity without claiming calibration;
- all required gates pass together.

If any required gate fails, mark the result `failed_but_informative`, preserve the evidence, block Phase 2 and R1, and identify one repair or rejection decision.

## Scope Boundary

Phase 1 forbids PINN training, inverse work, parameter fitting, new literature-curve digitization, formal 3D/FEM work, M44 repair, frozen-GT writes, and NbO2 execution. These are phase-scoped restrictions, not permanent research bans. Later directions require explicit activation by the guide's gates.
