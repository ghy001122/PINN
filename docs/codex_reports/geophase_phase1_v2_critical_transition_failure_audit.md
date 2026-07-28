# Phase 1-v2 critical-transition failure mechanism audit

## Disposition

`GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION`

The bounded audit supports requesting separate authorization for exactly one
versioned time-controller revision. Phase 1 and S2 scientific results remain
`forbidden` and unassessed. This audit did not change the controller, select a
production floor, rerun readiness, or authorize a formal campaign.

## Locked identity and execution

- Merged PR #6 main SHA: `6a7c9e0ba7be2b5bc89f751c0751110af2bab7ef`.
- Scientific baseline tree: `ea0ee584c279dadece3c2f4292fa5200e0826dbf`.
- Audit preregistration commit: `17b5ed75a118c9bc774f313e1dc5b1856ba3c1d2`.
- Audit config SHA-256:
  `6bba56e6acb321eae00e6c006d6bd1c6131acfc55e6a80f7590e21e7cace27c8`.
- Diagnostic implementation commit:
  `b84b1f4a47bb2aa1bef2e8799bc32f896e8f5937`.
- Diagnostic implementation tree:
  `14950b1c5de62bce55787d042e633b6c01e72bc6`.
- Stable environment fingerprint:
  `e1d8fa04c47e97c8cd38c2871f0c2507d4e864aa6a3bc1289ac35dba3f03227d`.
- Real numerical replay count: `1/1`.
- Executed path: `full_history_control`; streaming status:
  `not_reached_by_preregistered_stop`.
- Replay wall clock: `8.6499172 s`; peak process working set after replay:
  `65,249,280 bytes`.

The replay verified the merged-main scientific blobs from Git, the locked S2
config/addendum/manifest/execution-DAG bytes, and the pushed instrumentation
commit before solving. Instrumentation observed returned candidates and the
rejection ladder; it did not modify equations, candidates, time steps, or
acceptance/rejection logic.

## Observed mechanism

The original exception, `S2 transition increment failed at locked floor`, was
reproduced at state time `0 s` on the attempted candidate ending at
`2.5e-10 s`. The attempted-step ladder was
`5e-9, 2.5e-9, 1.25e-9, 6.25e-10, 3.125e-10, 2.5e-10 s`.

At the locked-floor candidate:

- actual trigger: branch memory `b`;
- cell: row `4`, column `4`, at `(x,y)=(4.5e-8, 9.0e-8) m`;
- `max|Delta b|=0.3999002930674579 > 0.02`;
- `max|Delta s|=0.009896685349114254 < 0.02`;
- `T_n=336.4 K`, `T_candidate=336.388174947588 K`;
- `b_n=1`, `b_candidate=0.6000997069325421`;
- heating activation `h=0`, cooling activation
  `c=0.999688435247787`.

Using only that observed candidate and the locked backward-Euler equations:

- `conditional_frozen_activation_dt_max_b = 1.010415820055618e-11 s`;
- `conditional_observed_candidate_dt_max_s = 6.783481071445014e-10 s`;
- conservative branch worst-case envelope:
  `1.0101010101010101e-11 s`, diagnostic and non-voting only.

These are local conditional bounds. They are not a production floor, a global
root of the coupled update, or authorization to modify the controller.

## Candidate integrity

All six successfully returned candidates passed every required integrity gate:

- finite state: `6/6`;
- damped Newton-Krylov converged in two iterations for every candidate;
- maximum Krylov matvecs `34`, Armijo backtracks `0`, fallback iterations `0`;
- maximum scaled residual/update:
  `1.241839631274375e-12 / 1.2200240817605845e-12`;
- maximum thermal/circuit/combined/device-power ledger residuals:
  `3.780391016614554e-12`, `7.928414891701993e-15`,
  `5.709993936024088e-13`, and `1.5389713254532033e-15`;
- the largest signal-relative lateral mismatch was
  `3.6594288734424234e-7`, while its registered backward-error ratio was
  `0.0014169608723222258 <= 1`; all lateral audits passed the existing
  two-path rule.

No nonfinite, nonlinear, ledger, lateral-conservation, or coupling defect was
observed. The sole failure was the locked floor being too large to resolve the
existing branch-memory update under this preregistered candidate activation.

## Atomic evidence

- Telemetry JSON SHA-256:
  `d58c8aefb3db51a157dd9eb16c6856e9e211822df81559abad265950c72cfa45`.
- Attempted-step CSV SHA-256:
  `361e804f622998883719a9103c15e697b0c8f3337b41eefda06dc673e238c1f2`.
- Diagnosis JSON SHA-256:
  `5e30843f0e91c36a50a36e9c19297806ecd0c84a3aa09bc683a74069fd2522a5`.

The atomic records report `formal_execution_count=0`, formal artifact count
`0`, and no time-controller change.

## Validation and claim boundary

- Focused Phase 1-v2 compatibility tests: `59 passed`.
- Tracked JSON validation: `224` valid, `0` failures.
- Fast governance audit: no failed checks; frozen GT hashes remain `8/8`
  unchanged. Runtime-specific rule loading and file-mtime review remain manual.
- Full regression: not run, as required by the bounded audit scope.

Forbidden claims remain: Phase 1/S2 success, a production controller floor,
formal-campaign authorization, Qiu calibration/reproduction, experimental
validation, Phase 2 readiness, or positive R1/R2 evidence.

## Manuscript impact

For Contribution 1, the current runtime failure is now a localized,
reproducible time-resolution boundary rather than an unexplained S2 physics or
conservation failure. This is diagnostic evidence only. A positive conservative
2.5D reference-solver claim still requires a separately authorized controller
revision, repeated readiness, and the later all-gates formal campaign.

Phase 2, R1 `HysGeo-Hybrid-PINN`, and R2 `GeoPhase-HomoMoE-PINN` remain blocked.
If the separately authorized revision is not attempted or fails its locked
gates, the retained `gamma_sub`/identifiability downgrade remains the delivery
route.
