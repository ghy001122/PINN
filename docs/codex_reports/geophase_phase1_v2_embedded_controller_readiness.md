# Phase 1-v2 embedded-controller readiness

Disposition: `NO_GO_RUNTIME_PERFORMANCE_ONLY`

Evidence status: `supported` bounded target-workstation performance provenance;
campaign runtime feasibility remains `forbidden`/unassessed. This is a
non-formal, CPU-only preflight, not a Phase 1 scientific result and not
authorization for the 63-item campaign.

## Locked identity

- PR #7 merge/main baseline: `8a8541f19ab5b5baeda5102a70e593f996c59224`.
- Controller-v2 preregistration commit:
  `406207b02adaa37953ff4d3813aaeee3235c004f`.
- Base S2 YAML SHA-256:
  `0600498590a8c100ec8dee95621719ea655354ec118015868cb07fedf89f85d5`.
- Controller-v2 overlay SHA-256:
  `eaca81d59b9a52c21fe60fab213a8f7fd65d83a674fd2ef27746d164e163c528`.
- Resolved runtime identity SHA-256:
  `b0030d0156d68f2940fb686dbd88ae55db7ed8a9352b8f06bff59ca64b09fea7`.
- Frozen core implementation commit:
  `cc00eab50c5c4ca98e11ce2763e92d635c9fcd2f`.
- Readiness execution commit:
  `d3f8627d50788cbb06a5b412729cdc7dd7c7fe78`.

## Sequential gates

| Gate | Status | Direct evidence |
| --- | --- | --- |
| C1 | `pass` | One locked `PRE-CTRL-LEGAL-CRITICAL` run reached its requested final time with 23 accepted intervals. Full, first-half, second-half, and aggregate integrity passed; full-history/streaming maximum relative difference was `3.3864e-16`. |
| C2 | `pass` | One bounded trajectory completed 128 accepted intervals and `2.625e-7 s`. Embedded error, finite/nonlinear state, all four ledger layers, lateral audit, bounds, and streaming parity passed. No event or reversal was observed, recorded only as `NA_not_observed_within_bounded_C2_window`. |
| C3 | `fail` (`performance_only`) | The global worker deadline was reached at `0/18` single-interval samples and `1/9` short trajectories (the one row is the legal C2 reuse), before the campaign forecast and dormant-runner dry-run could execute. No controller-integrity or scientific gate failed. |

## Runtime boundary

- Parent-observed preflight wall clock: `880.0950008 s`; worker supervisor:
  `880 s`; contractual outer limit: `900 s`.
- C2 step-time telemetry: p50 `2.15266 s`, p90 `2.77825 s`, maximum
  `11.3578 s`; 399 coupled solves for 128 accepted intervals and five rejected
  outer intervals.
- C2 observed peak RSS: `99,266,560 bytes`.
- Available RAM at launch: `955,195,392 bytes`; disk free at launch:
  `70,040,465,408 bytes`.
- A 60-unit p95/hard makespan, campaign output volume, aggregate worker RSS,
  and disk-reserve vote were not eligible because C3 did not complete. The
  forecast CSV therefore contains its schema header only.
- Dormant formal runner: `not_reached`.
- Performance repair consumed: `false`; the single pure-equivalence
  performance opportunity remains available only after fresh authorization.

## Claim boundary

Supported: the versioned controller-v2 passed the bounded C1 and C2 numerical
integrity checks on this workstation; the complete runtime-readiness preflight
did not finish before its locked worker backstop.

Forbidden: Phase 1-v2 passed or scientifically failed; the 60-unit campaign is
four-hour feasible; a campaign memory or disk budget passed; formal execution
is authorized; event/trend gates passed; Qiu was reproduced; Phase 2 or R1/R2
is unlocked.

`formal_execution_count=0`; `formal_artifact_count=0`. No `P1V2-*` evaluation
ID was dispatched and no formal trend/event gate voted.
