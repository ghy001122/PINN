# Phase 1-v2 execution and formal-runner addendum

Status: preregistered execution semantics pending push; no runtime preflight or
formal evaluation has executed under this addendum.

This addendum closes execution ambiguities in the already locked Phase 1-v2
S2 contract. Its machine authority is
`configs/geophase_phase1_v2_execution_addendum.yaml`. It does not change the
S2 equations, parameters, solver tolerances, adaptive controller, scientific
gates, protocols, 63 evaluation IDs, 60 unique execution units, three legal
trajectory reuses, or `formal_execution_count=0`.

## Dependency graph and execution order

Every non-reused manifest row maps to its declared trajectory ID. The three
nominal-overlap TOP evaluations map to their physically identical REF S4T4
trajectories. This gives exactly 63 evaluations, 60 unique units, and three
reuses. Any missing, duplicate, or additional mapping invalidates the future
campaign.

A future authorized run verifies the immutable contract and environment first,
then evaluates the five source-scale foundations, FAIL, MMS, LIM, REF, DUAL0,
and the six unique TOP units. The three reused TOP evaluations are computed
only after their REF dependencies exist. A source-scale, FAIL, MMS, LIM,
finite-value, nonlinear, terminal-balance, ledger, device-power, or lateral
face foundation failure preserves completed evidence, blocks unscheduled
dependent items, and stops costly work.

For every REF protocol, the spatial diagnostic pair is S1T4--S2T4 and the
voting fine pair is S2T4--S4T4. The temporal diagnostic pair is S4T1--S4T2 and
the voting fine pair is S4T2--S4T4. The same pair identities govern event-time
comparisons. Every REF and TOP trajectory ends at 20 microseconds.

## Previously underspecified groups

- TOP uses S4/T4 for 20 microseconds. O10 and O30 are independent; O20 reuses
  the matching nominal REF S4T4 trajectory.
- DUAL0 uses L1/T1 for 20 microseconds with exactly zero coupling. The A-only
  and B-only drives are 12.5/0 V and 0/12.5 V. Equal and swapped-label tests
  apply the same 12.5 V protocol to both independent copies.
- FAIL uses L1/T1 and stops as soon as the declared injected fault is detected
  and fail-closed behavior is verified. It never continues merely to fill a
  time window.
- LIM uses analytic, static, single-cell, or one-step fixtures where possible.
  Only the zero-drive drift limit needs a full L1/T1 20-microsecond trajectory.

These are refinements of existing IDs and gates, not new formal items.

## Event and topology semantics

Event sequences are compared only after direction and order agree. Two empty
sequences are `NA` when the protocol does not require events. A one-sided empty
sequence, unequal counts, or a direction/order mismatch is `FAIL`. Matching
events are paired in order and the largest absolute time difference votes
against the existing 50 ns gate. The 12.5 V transition protocol still must
pass its separate trend requirement; event-convergence `NA` cannot rescue a
missing required event.

For each protocol and each registered QoI independently,

\[
E=\max(q_{10},q_{20},q_{30})-\min(q_{10},q_{20},q_{30}),\qquad
N=\left|q_{S4T4}-q_{S2T4}\right|,
\]

and the source-envelope vote requires

\[
\frac{E}{\max(N,\epsilon_q)}\ge 1.
\]

The locked floors are (10^{-12}\,\mathrm A) for terminal current,
(10^{-3}\,\mathrm K) for temperature rise, and (10^{-6}) for conductive
state change. No cross-protocol or cross-QoI averaging is allowed. Geometry-
robust wording is forbidden whenever overlap sensitivity exceeds the matching
nominal spatial fine-pair error.

## Streaming and equivalent optimization

The execution path lands on the existing 4001-point, 5 ns physical comparison
grid and streams ports, state summaries, four ledgers, and scalar events.
Accepted-step full-field history is forbidden. Full fields are retained only
at 0, 5, 10, 15, and 20 microseconds, protocol discontinuities, and bounded
event neighborhoods. At most 16 event-neighborhood full-field snapshots are
retained: before/after every event when there are at most eight, otherwise
before/after the earliest four and latest four. Scalar records remain complete
for all events.

Per-case data are written to a temporary directory, validated, hashed, and
atomically renamed. Memory must not scale as accepted steps times full-grid
history. Streaming and short-history paths must agree in parity tests.

Permitted optimizations are limited to sparse topology reuse, invariant matrix
or factorization caching, same-state unit-voltage electrical scaling with
quadratic Joule scaling, case-level CPU parallelism, and streaming. Electrical
scaling cannot cross a nonlinear iterate or accepted step. Cached and uncached
paths must agree for fields, ports, states, and all four ledgers. Each worker
uses one BLAS/OpenMP thread.

The lateral matrix/face audit remains exactly the registered relative test OR
the (64\epsilon\|L\|\|T\|) floating-point backward-error test. Tampering must
fail both. No third acceptance rule is permitted.

## Non-formal runtime preflight

The preflight uses only `PRE-*` identities and a temporary directory on CPU.
Its 900 s budget excludes tests and CI. At launch it records RAM, physical and
logical cores, disk, thread settings, and a content-addressed environment
identity. A formal run on another workstation must repeat this same preflight.

The mandatory matrix covers 10x25, 20x50, and 40x100 grids; deterministic
equilibrium, legal critical, and high-conductive states; base and floor steps;
and nine trajectories capped at 128 accepted steps or 1 microsecond. If budget
remains, one coarse 12.5 V trajectory runs until 20 microseconds or 600 s wall
time. Its timeout alone is not a NO-GO, and its oscillation behavior is never
scored.

Telemetry includes accepted/rejected steps, Newton/Krylov/Armijo/fallback
counts, step-time quantiles, accepted-step sizes, failures, four ledgers, peak
RSS, predicted disk, and streaming volume. Initial states and protocols are
declared before execution and cannot be searched for easier behavior.

## Cost and dormant-runner gate

Observed accepted-step rates and step-time distributions produce a conservative
60-unit forecast. The predeclared 1.25 step/time margins and LPT scheduling are
used with the workstation's memory- and physical-core-limited worker count.
Readiness requires a margin-bearing makespan no greater than 11,520 s, an
unreserved forecast no greater than 14,400 s, aggregate worker RSS no greater
than 70 percent of launch-available RAM, and at least 20 percent disk free after
the forecast. All parity, finite, ledger, and critical-state checks must pass.

Streaming, sparse reuse, caching, and parallelism are the baseline and consume
no repair. Only a performance-only failure after every scientific and software
integrity check passes may use one mathematically equivalent engineering
repair, followed by exactly the same preflight once. The existing S2 software-
repair allowance is exhausted; a new physics, conservation, or nonlinear
implementation defect is preserved and returned to the user without repair.

The dormant runner is exercised only with synthetic/injected `PRE-*` states in
a temporary directory. It validates all hashes, the 63/60/3 graph, immutable
registry identity, append-only transitions, atomic cases, fail-fast blocking,
same-ID resume, mismatch refusal, and separation of scientific and
infrastructure failures. It cannot call a formal execution unit or create a
real run ID.

Only a future explicit authorization may atomically create the real registry
and change the formal count to one immediately before scheduling the first
unit. Resuming the same run ID never increments the count.

## Claim and stop boundary

This round can end only as `GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION` or
`NO_GO_RUNTIME`. A GO is workstation-bound runtime evidence, not a Phase 1
scientific result, and still stops for user authorization. A NO-GO reports one
primary cause and whether the single performance-repair opportunity was used.
No formal artifact, trend result, Phase 2 data, or PINN result may be produced.
