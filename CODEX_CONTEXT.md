# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Terminal checkpoint: `Q2_CONTROLLER_V3_EXHAUSTED_NO_S0`.
- Terminal goal: `Q2_CONTROLLER_V3_S0_TO_COMPLETE_C01_C06_METHOD_AND_R1_EVIDENCE`.
- Base: `main@b28aa97ccbdbc1b03b43e8deb13b3bbc35c71ead`.
- Immutable controller-result evidence commit: `73dc41f81760a805cec0f768179f327c3abcbe9d` on PR #21.

S2 equations, parameters, protocols, scientific thresholds, and the 63-item / 60-unit / 3-reuse plan were unchanged. The new controller path did not call historical E0, S0, readiness, or equivalence runners.

The long-term manuscript ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3. None is executed or supported.

## Controller-v3 Terminal Evidence

- Candidate 1, output-decoupled controller: rejected in 9 V qualification at `2.1094726562498093e-6 s`; the implicit solve failed closed at the locked outer floor. No qualification run was published.
- Candidate 2, bounded subfloor recovery to floor/16: rejected in the same 9 V qualification at `2.2577221679678546e-6 s`; the frozen 1000-rejection per-case cap was exceeded. No qualification run was published.
- Invocation V1 and V3 were external zero-publication host failures and cast no numerical vote. V2 and V4 are the two numerical policy dispositions.
- Controller policy budget: 2/2 consumed; a third policy is forbidden in this goal.

Terminal state: `GOAL_UNSUCCESSFUL_CONTROLLER_V3_EXHAUSTED`.

## Claim Boundary

Controller-v3 qualification is `failed_but_informative` numerical-method evidence. It is not an S2 physics vote. Fresh S0 never started, `formal_execution_count=0`, and Phase 2, MLP, vanilla PINN, C01, C06, OOD, and R1 evidence were not created.

Allowed: exact controller identities, failure states, timestamps, hashes, and the two bounded rejection dispositions.

Forbidden: S0/Phase 1 pass or scientific fail; runtime feasibility; positive or negative PINN conclusions; geometry/protocol OOD claims; Qiu quantitative reproduction; experimental validation; or any equivalence-v4/v5 route.

## Current Stop

No experiment is authorized. The next useful goal, if opened, is a bounded nonzero-drive implicit-solver convergence study using the two immutable failure states. It must not resume this qualification, add a third controller-v3 policy, or bypass the complete S0 judge before Phase 2/C01.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains immutable and non-retryable. Equivalence-v4/v5 is forbidden; no retry is authorized.

Read `docs/research_strategy/context_loading_policy.md` before loading long history.
