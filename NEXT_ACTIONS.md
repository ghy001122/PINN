# Next Actions

## Authoritative Current Queue

Exactly one bottleneck is active: `D_PUBLIC_MULTIVOLTAGE_PREREGISTRATION`. The constrained `gamma_sub` result remains the safe rank-1 synthetic mainline.

### Priority D-PREG — public multi-voltage preregistration

Preregister a repository-side fit using provenance-locked public `9/11/15/17 V` curves, with sealed `13 V` reserved for a later repository-withheld cross-voltage evaluation. This phase does not authorize fitting, 13 V access, or neural training.

Lock before execution:

1. source artifact, curve ID, voltage, units, license, parent hash, and permitted role for every curve;
2. separate semantics for source-paper reproduction, repository refit, repository-withheld cross-voltage evaluation, and genuinely independent validation;
3. model equations, initial/event rules, parameter roles, time step, solver-convergence gate, and paper/code discrepancies;
4. preprocessing, interpolation, time-zero handling, complete-trace/activity metrics, thresholds, multistart initialization, optimizer budget, and fail-closed rules;
5. fixed fit/calibration roles for 9/11/15/17 V and R-T evidence, without reading 13 V values;
6. explicit handling of D0a's failed time-step convergence without overwriting its artifacts;
7. a cryptographic fit lock that blocks 13 V until all choices and multistart results are frozen;
8. no 13 V refit, best-seed-only reporting, or post-hoc threshold change.

### Locked boundaries

- **N0/M33/M34:** M33-v1 failed eight gate blocks. M34 shows its optimizer was not signed/vector ALM, but its stricter derivative-parity preflight failed (`30/44` nonzero coordinates pass; maximum relative error `0.0918561`). No corrected run was authorized. M33-v1 is permanently closed; this is not a universal failure claim for mixed PINNs or ALM.
- **SID/EC-OQ:** inactive after derivative, event-window, stability, and geometry failures. Any revisit needs a new authorized numerical contract.
- **CPCF/CEBA/SCIS:** closed as scientific expansion routes. CPCF is non-voting; CEBA has parity but no bracket and uses an oracle abstention; SCIS fails severe-mismatch refusal.
- **N1-N3/SC-LOS:** unrun and positive claims remain `forbidden`.
- **Other work:** DWR, operator learning, further UQ, 2D, new hysteresis, latent heat, actual external fitting, and all neural search are outside this phase. Manuscript assembly remains a delivery obligation, not a competing research phase.

## Non-negotiable boundaries

No frozen-GT edits, 13 V access without a valid fit lock, post-hoc gate/window relaxation, hidden seeds, synthetic-as-experimental wording, solver/PINN attribution mixing, or novelty claims for standard SVD/Fisher/event/gradient-balancing/mixed/ALM components.
