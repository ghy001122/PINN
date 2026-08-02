# Codex Context

## Current Route

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_NLS_V1_QUALIFICATION_REJECTED_NO_S0`.
- Goal: `Q2_NLS_V1_S0_TO_C01_C06_R1_COMPLETE_METHOD_EVIDENCE`.
- Base: `main@42e16ff7b9abd34b5ce7272eaa74ad60d49348d3`.
- NLS-v1 anchor: `ee07846b89280fafdac18166f02ff688d8d92f58`.
- Immutable NLS result commit: `f3b7db17126c5591569cb98839a2df3211b1fef9`.

S2 equations, physical parameters, protocols, controller-v2, and the 63/60/3 scientific plan were unchanged. Historical E0/S0/equivalence evidence and Frozen GT v1.1 remain read-only.

The long-term ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2 `GeoPhase-HomoMoE-PINN`, and conditional R3; none is currently executed or supported.

## NLS-v1 Qualification Result

The fallback now accepts only when both the full fixed-point defect and frozen scaled residual are at most `1e-8`. The two frozen controller-v3 failure states pass in 6 and 4 fallback iterations, respectively. The conditional Schur-reduced upgrade therefore was not activated.

The canonical `NLSV1-QUAL-20260802-V1` run produced one non-passing artifact. Standard 9 V T1 stopped at `1.7060156249987655e-5 s` after `27136.6188 s`, exceeding the frozen `21600 s` per-run limit; it published 3413/4001 output timestamps and did not reach 20 microseconds. In T4, a final residue of `1.73133534418779e-17 s` triggered a meaningless sub-floor ledger step. That endpoint defect was fixed under a new `v1p1` identity and covered by regression.

The endpoint-only correction cannot change the T1 path before its wall-time stop. A full V2 rerun was therefore not launched: it could not satisfy the already-failed hard qualification gate and would only repeat a long run. Terminal state: `GOAL_UNSUCCESSFUL_NLS_V1`.

## Claim Boundary

NLS-v1 qualification is `failed_but_informative` bounded numerical-performance evidence. It is not an S2 physics vote. Fresh S0 never started, `formal_execution_count=0`, and Phase 2, MLP, vanilla PINN, C01, C06, OOD, and R1/R2/R3 were not executed.

Allowed: dual-gate repair behavior, frozen replay metrics, exact T1/T4 performance and endpoint evidence, and the frozen-budget rejection of this NLS-v1 qualification.

Forbidden: S0/Phase 1 scientific PASS or FAIL; general campaign infeasibility; positive or negative PINN conclusions; Qiu quantitative reproduction; experimental validation; or equivalence-v4/v5.

## Current Stop

No experiment is authorized. A future goal may evaluate a versioned, mathematically equivalent performance-oriented reduced solver against the same physical gates and full qualification trajectory. It must not call this a retry, activate Schur under the consumed goal, add controller candidate 3/controller-v4, return to equivalence, or bypass S0 before Phase 2/C01.

Equivalence-v2 remains immutable and non-retryable. Equivalence-v3 remains immutable and non-retryable. Equivalence-v4/v5 is forbidden; no retry is authorized.

Read `docs/research_strategy/context_loading_policy.md` before loading long history.
