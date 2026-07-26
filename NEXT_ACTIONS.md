# Next Actions

## Authoritative Current Queue

Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.

Authorized checkpoint: `A_IMPLEMENTATION_AND_SMOKE_FORMAL_BLOCKED`.

There is exactly one active task:

> Implement and validate the contract-hardened, independent, conservative, PINN-residual-separated Qiu-inspired VO2 single-device real x-y plus region-specific K-state vertical-memory 2.5D FVM/implicit reference solver.

## Manuscript Use

This solver is the numerical truth judge for later R1 fields, ports, phase events, interfaces, RC behavior, and energy ledgers. Without it, no positive new-route PINN claim is eligible.

## Required Inputs

- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
- `docs/research_strategy/phase1_geophase_2p5d_reference_contract.md`
- `configs/geophase_phase1_2p5d_reference.yaml`
- `configs/qiu_vo2_phase1_source_contract.yaml`
- `configs/geo2p5d_stage.yaml`
- `docs/method_equations.md`
- source/provenance contracts routed by the Phase 1 config

## Execution Order

1. Implement and pass the zero-solver algebraic source-scale checks: both uniform electrical endmembers, area-integrated DC thermal conductance, active-plus-memory capacity, and positive scale factors.
2. Implement the locked region masks, grid/time/protocol schedule, nonlinear tolerances, metric definitions, source-scale-normalized K-state identification, and 96-case inventory exactly as configured.
3. Implement the independent electrical, thermal, K-state, hysteresis, circuit, and ledger pieces under responsibility-based modules; do not share the PINN discrete residual implementation.
4. Add behavioral tests for manufactured solutions, failure paths, SI units, ports, passivity, region topology, and ledgers.
5. Run CPU smoke and focused preflights, write the exact 96-case manifest,
   configuration hash, environment manifest, and Checkpoint A summary, and
   verify `formal_execution_count=0`.
6. Stop and report. The sole formal campaign remains blocked until the user
   explicitly authorizes Checkpoint B from the locked preregistration SHA.

## Required Gates

- manufactured electrical and thermal solutions;
- exact algebraic recovery of the source-author electrical endmember resistances and nominal global thermal scales before solver execution;
- terminal-current conservation;
- active-plane plus K-state full energy ledger;
- independent mesh and time-step refinement on fixed physical comparison grids;
- K-state positive capacity/conductance, stable poles, passivity, and high-order reference alignment;
- zero-drive, uniform-conductivity, and two-copy decoupling/label-symmetry limits;
- literature-trend sanity without claiming calibration;
- all required gates pass together.

If any required gate fails, mark the result `failed_but_informative`, preserve the evidence, block Phase 2 and R1, and identify one repair or rejection decision.

## Scope Boundary

Phase 1 forbids PINN training, inverse work, device/literature parameter fitting, new literature-curve digitization, formal 3D/FEM work, M44 repair, frozen-GT writes, NbO2 execution, and nonzero dual-device thermal coupling. The preregistered passive K-state reduction fit is required and is not device calibration. These restrictions are phase-scoped, not permanent research bans. A later coupling route requires an explicit substrate surface field or high-order-validated nonlocal kernel and its own gate.
