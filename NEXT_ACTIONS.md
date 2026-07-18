# Next Actions

## Authoritative Current Queue

Exactly one bottleneck is active: `D_PUBLIC_SOLVER_CONVERGENCE_RESOLUTION`. The constrained `gamma_sub` result remains the safe rank-1 synthetic mainline.

### Priority D-CONV — public compact-solver convergence resolution

M35 D-PREG passed all `21/21` checks, but D-FIT stopped before Jacobian or fitting because the locked 5 ns versus 2.5 ns full-waveform convergence gate failed at every open voltage. The next round is a solver-only resolution audit. It does not authorize fitting, 13 V access, PINN training, or retrospective repair of M35.

Lock before execution in a new preregistration:

1. preserve M35's failed NRMSE gates and D0a's `0.163148` failure as immutable historical evidence;
2. separate quiescent-trace normalization failure at 9/17 V from oscillatory event-time/phase accumulation at 11/15 V;
3. compare fixed steps no coarser than `2.5/1.25/0.625 ns` against an independently implemented event-resolved or adaptive reference;
4. preregister both raw-time full-waveform error and event-aligned diagnostics, with absolute instrument-scale floors fixed from the already-open pretrigger traces rather than selected after solver inspection;
5. require event count/class, frequency, charge, energy, and raw-time trajectory convergence; event alignment may diagnose dephasing but cannot replace the raw-time gate;
6. stop without fitting if numerical convergence remains unstable or if the source discontinuity/event ordering prevents a defensible reference;
7. keep `13 V` sealed and forbid any multistart fit until the new numerical contract passes.

### Locked boundaries

- **N0/M33/M34:** M33-v1 failed eight gate blocks. M34 shows its optimizer was not signed/vector ALM, and its stricter preregistered derivative-parity preflight failed (`30/44` nonzero coordinates pass; maximum relative error `0.0918561`). M34-A subsequently finds stable parity in `32/32` post-hoc group-normalized directions, supporting neither an autograd implementation error nor a cancellation explanation. It is non-voting and no corrected run was authorized. M33-v1 is permanently closed; this is not a universal failure claim for mixed PINNs or ALM.
- **M35 public VO2:** D-PREG is a valid lock, not fit evidence. D-FIT is `failed_but_informative`; no Jacobian, multistart, refit, fit lock, or 13 V evaluation occurred.
- **SID/EC-OQ:** inactive after derivative, event-window, stability, and geometry failures. Any revisit needs a new authorized numerical contract.
- **CPCF/CEBA/SCIS:** closed as scientific expansion routes. CPCF is non-voting; CEBA has parity but no bracket and uses an oracle abstention; SCIS fails severe-mismatch refusal.
- **N1-N3/SC-LOS:** unrun and positive claims remain `forbidden`.
- **Other work:** DWR, operator learning, further UQ, 2D, new hysteresis, latent heat, public-data fitting, and all neural search are outside this phase. Manuscript assembly remains a delivery obligation, not a competing research phase.

## Non-negotiable boundaries

No frozen-GT edits, 13 V access without a valid fit lock plus new explicit authorization, post-hoc gate/window relaxation, hidden seeds, synthetic-as-experimental wording, solver/PINN attribution mixing, or novelty claims for standard SVD/Fisher/event/gradient-balancing/mixed/ALM components.
