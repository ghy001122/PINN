# M36 event-resolved orbit convergence and conditional public fit

## Scope and manuscript use

M36 asks a narrower numerical question than M35: whether the public-source VO2
compact model has converged static observables and converged limit-cycle orbit
coordinates even when long-horizon raw-time traces accumulate phase error.  It
does not erase or relax the M35 raw-time failures, the historical D0a
`0.1631480017203279` failure, or any full-PINN evidence boundary.  Its possible
manuscript use is a solver-reliability result and, only after every upstream
gate passes, a repository-side open-voltage identifiability bridge.

## Frozen protocol before execution

- Open numerical/data scope: 9, 11, 15, and 17 V only.  The 13 V numeric
  payload remains sealed.
- Source-compatible family: explicit Euler at 2.5, 1.25, 0.625, and 0.3125 ns.
- Independent continuous-event references: DOP853 and Radau with identical
  `rtol=1e-9`, state-specific absolute tolerances, and root-located thermal
  extrema, 0.01 K reversal delay, and temperature-boundary crossings.
- The sampled source ledger and continuous root-located ledger are explicitly
  different event semantics.  Their agreement is an experimental gate, not an
  assumption.
- Static 9/17 V gates use absolute current/voltage errors normalized by
  pretrigger instrument noise, steady values, activity class, charge, and
  energy.  Oscillatory 11/15 V gates use fixed-index event pairing, period,
  phase-drift slope, linearly phase-normalized cycle shape, peak, duty, cycle
  charge/energy, conservation ledger, and a fixed 20 microsecond raw-time
  window.
- Full-horizon raw-time NRMSE is always reported but is diagnostic.  No DTW or
  post-hoc window/threshold adjustment is permitted.
- Conditional Jacobian and LOVO fitting are allowed automatically only if all
  numerical primary gates pass.  The event-time sensitivity is evaluated by
  root-located central differences.  A reversible `(C_th,S_e)` to
  `(tau_th,S_e)` transform is not allowed to claim increased Fisher rank.
- Both the M35 raw-time objective and the regime-aware orbit objective receive
  the same predeclared maximum forward budget, four LOVO folds, two coordinate
  systems, and the same eight deterministic starts.  All starts must be
  reported.

## Pre-execution evidence boundary

At this preregistration stage no M36 solver, Jacobian, optimization, PINN
training, or 13 V evaluation has been run.  A positive result is not presumed.
Failure of reference parity, event sequence, fixed-step trend, event-aware
Jacobian stability, or LOVO fitting closes the corresponding downstream route
without threshold changes or extra parameter searches.

## Results

Pending execution after the immutable preregistration commit.

## Claim disposition

Pending evidence.  `world-first`, independent external validation, unique raw
parameter recovery, trained-PINN success, and replacement of M35/D0a failures
remain forbidden.
