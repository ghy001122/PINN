# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Terminal checkpoint:
  `Q2_S0_STOP_INVALID_EXECUTION_AFTER_REPAIR_BUDGET_EXHAUSTED`.
- Fresh task:
  `Q2_S0_DIRECT_PHYSICS_QUALIFICATION_TO_C01_C06_R1_MANUSCRIPT_EVIDENCE`.
- Base after the prior E0 closeout: `main@d1dd6921...`.
- Result evidence commit: `adf6cc4...` on PR #20.
- S2 physics/configuration, controller-v2, source contract, and the 63-item /
  60-unit / 3-reuse plan remain unchanged.
- The manuscript ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2
  `GeoPhase-HomoMoE-PINN`, and conditional R3; none is executed or supported.

The fresh S0 route did not reuse or rerun the old E0 or equivalence runners.
It implemented a direct single-implementation runner, passed two 4/4
non-voting smoke runs, and attempted the frozen formal plan under a 14,400 s
CPU budget.

## Terminal S0 Evidence

- `S0-FORMAL-20260801-V1`: `INVALID_S0_EXECUTION`, 14/60 units published,
  `formal_execution_count=0`, no global scientific vote. The nullable
  zero-drive LIM axes triggered `int(None)`; the one permitted runner repair
  resolved them mechanically from the frozen execution addendum.
- `S0-FORMAL-20260801-V2`: `INVALID_S0_EXECUTION`, 25/60 units published,
  `formal_execution_count=0`, no global scientific vote. The published units
  comprise 5 FAIL controls, 9 MMS, 6 LIM, and 5 zero-drive REF units; each
  published payload and hash is valid.
- Before the first nonzero-drive unit could be published,
  `TRJ-P1V2-REF-quiescent_9V-S1T4` raised
  `controller-v2 forced remainder failed closed`.
- The remaining 35 units and all dependent 63-item aggregate gates are
  unassessed. No Phase 2 data, C01/vanilla/MLP training, OOD result, or
  manuscript-positive PINN evidence was created.

The controller exception is a fail-closed execution-integrity boundary. It is
not a global S2 physics vote and cannot be reclassified post hoc. The one code
repair allowed by this goal is consumed; no retry or second repair is allowed.

## Claim Boundary

Allowed: exact S0 execution provenance; two valid non-voting smoke results;
the 25 content-addressed partial unit records; frozen identities; and the fact
that the direct judge remains unqualified.

Forbidden: S0 or Phase 1 pass/fail as a global scientific result; runtime
feasibility; C01/R1/R2 success; geometry/protocol OOD claims; Qiu quantitative
reproduction; experiment/FEM/3D validation; or interpreting the controller
exception as a physical-law failure.

Frozen GT v1.1 remains read-only. Strict-equivalence-v1 remains immutable.
Equivalence-v2 remains immutable and non-retryable; equivalence-v3 does too.
`formal_execution_count=0`.

## Current Stop

No experiment is authorized. A future route may be opened only by a new goal
that explicitly addresses the nonzero-drive forced-remainder numerical-
integration boundary and changes the exhausted repair policy. It must not be
an equivalence audit, a continuation of either S0 attempt, or a PINN shortcut.

Read `docs/research_strategy/context_loading_policy.md` before loading long
history.
