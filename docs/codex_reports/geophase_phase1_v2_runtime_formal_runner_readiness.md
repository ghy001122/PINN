# Phase 1-v2 runtime and dormant formal-runner readiness

Disposition: `NO_GO_RUNTIME`

Evidence type: non-voting synthetic numerical runtime-readiness and dormant-
runner integrity evidence. Base `main` was
`a390dba6855ef06308a537eec4a16d42dc022bff`; the execution addendum was
preregistered at `b830d4f3f45f634883de906972a7712f311cfa93` before any new
runtime calculation. The final Git commit is the commit containing this report;
the exact code-tree content hash below is self-contained and the commit SHA is
reported in the draft PR and handoff.

This round executed only non-formal `PRE-*` runtime probes and synthetic
runner-state injections. It did not execute a formal evaluation item,
create a real formal run ID, or change the formal execution count.

## Locked identities

- Execution addendum SHA-256: `9d477b79a6a598b5032f104bea5b92290026b798e6599c2e9813c9ba11083640`
- Execution DAG SHA-256: `1f8a5ef122898974224c2208a0b41af0f776b5ef07bca444f5f0a727b5c9c87a`
- Environment SHA-256: `bd21ef249fa2078050ed970830fd58b1a2a6ba31e6a0f990cf7227b4ac838134`
- Code-tree content SHA-256: `2b9077d3bdff6ba685ac614d24a30f85c03f4e91f5ff41d92650ec877974a809`

## Runtime result

- Preflight wall clock: `not atomically captured before fail-closed exception`.
- Passing samples: `0`; failing samples: `1`.
- Peak RSS: `None` bytes.
- Performance repair consumed: `false`.
- Unit-voltage scaling: `disabled`; its L1 thermal-ledger parity was
  `4.410635541795736e-12 > 1e-12`, so it is not part of the runner.
- Dormant runner dry-run: `pass`.

The post-failure workstation measurement reported 10 physical/12 logical CPU
cores and 8.30 GB total RAM. Available RAM at that later recorder launch was
124,137,472 bytes; this is not the failed process's peak RSS and is not used as
an independent NO-GO cause. No campaign disk or makespan claim is made.

## Stop cause

RuntimeError: S2 transition increment failed at locked floor

This is a runtime-readiness failure, not a formal Phase 1 scientific failure.
The S2 scientific result remains `forbidden` and unassessed. The existing S2
software-repair allowance is exhausted; the performance-only repair was not
eligible because performance was not the sole failure.

## Validation

- Phase1-v2 focused tests: `53 passed`.
- Local focused-CI-equivalent suite: `184 passed`, `1 expected S1 skip`.
- Governance audit: no failed checks.
- Tracked JSON: `222` valid, `0` failures.
- Historical evidence manifest: pass.
- Frozen GT: `8/8` hashes unchanged.
- Full regression: not run, by the declared fail-closed scope after a new
  nonlinear critical-state failure.

## Claim boundary

Allowed: runtime readiness was assessed on the named workstation under
the locked S2 contract using non-voting PRE probes.

Forbidden: Phase 1-v2 passed, any formal scientific gate passed, the
Qiu device was reproduced, or Phase 2/PINN work is unlocked.

`formal_execution_count=0`; formal artifact count is `0`.
