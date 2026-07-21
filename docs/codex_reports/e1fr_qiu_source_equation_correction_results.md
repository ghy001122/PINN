# E1F-R Qiu literal-S3 corrective audit

- Status: `failed_but_informative`.
- This is a post-lock corrective source-figure audit, not an independent holdout or exact author-code reproduction.
- The original E1F run remains `implementation_contract_invalid`; none of its numerical curve errors casts a scientific vote.
- Main Fig. 2b remains `implementation_contract_invalid/unassessed` because legend pixels contaminated the extraction. It was neither simulated nor scored here.

## Locked numerical results

- DOP853/Radau parity passed: `True`; worst waveform NRMSE `2.23216159e-07`.
- SI Fig. S1 current NRMSE: `0.353153987`.
- SI Fig. S1 voltage NRMSE: `0.815642721`.
- Locked setting gate (`<=0.10`) passed: `False`.
- Effective-coordinate preflight: `not_run_upstream_gate_failed`. Any local rank is not global identifiability.
- Formal integrations: `2`; wall time `7.181 s`.

## Claim boundary

The literal-S3 corrective audit failed at SI Fig. S1 setting curve. The result defines a source-equation implementation boundary; no refit, replacement curve, or downstream inverse route is authorized.

Exact author-code reproduction, independent external validation, public-data inverse recovery, M41, trained-PINN success, and direct lumped-to-local-PDE parameter transfer remain forbidden.

## Failure attribution

The corrected failure is not explained by numerical integration: DOP853 and
Radau agree in the waveform, activity class, event count, and event sequence.
It is also not explained by the declared pixel-jitter sensitivity: the most
favorable current and voltage envelope scores are `0.320963` and `0.732598`,
still far above `0.10`. The comparison figure shows both cumulative timing
drift and a large device-voltage amplitude mismatch.

The remaining discrepancy cannot be uniquely assigned from the public source.
The paper/SI do not supply executable reversal-update code, numerical initial-
condition and event-deadband contracts, integrator details, or public raw
arrays; SI Fig. S1 does not explicitly identify the trace as experiment or
simulation. These missing contracts are scientifically different from a
solver bug. Refitting them after observing the curve would turn an
implementation check into an unregistered calibration exercise and is not
authorized.

The independent bridge audit establishes a second, separate boundary. The
source/local resistance factor `2.330233` and source/local capacitance,
conductance, and time-scale ratios `635.5145`, `206`, and `3.085022` show that
author-fitted device-level lumped quantities cannot be inserted directly into
the M40 local PDE. They do not identify the missing local parameters.

## Progress and distance to the manuscript goal

This round closes three ambiguities: it separates invalid implementation from
scientific failure, supplies a literal-equation and dual-solver audit, and
prevents a contaminated same-paper curve from being presented as a holdout.
It therefore strengthens reproducibility and reviewer defense. It does not add
positive external validation, trained full-PINN evidence, or an authorized
public-data inverse. The only positive inverse line remains the calibrated,
synthetic, rank-1 `gamma_sub` result.

For a near-term submission, the defensible paper identity is therefore
**identifiability-gated physics-informed digital-twin inversion**, not a new
successful full-PINN solver and not a calibrated real-device replica. The Qiu
and full-PINN results belong in limitations/supplementary reviewer defense.
Q2-journal acceptance remains high risk because the positive line is synthetic;
no further solver or neural rescue is likely to repair that gap within the
submission deadline without introducing new uncontrolled assumptions.

## Highest-value next route

1. Freeze science now: no E1F/E1F-R, M40/M40R, M41, M37R, public inverse, or
   neural rescue.
2. Within two days, finish the integrated manuscript around three claims only:
   hidden-field/target-selection boundary, calibrated `gamma_sub` recovery,
   and retained failure regions.
3. Build one contract-matched comparison table from already locked synthetic
   evidence. If existing runs are not directly comparable, mark the comparison
   unassessed rather than launching another broad experiment.
4. Complete claim-by-claim citation, figure, supplement, reproducibility, and
   reviewer-defense audits; then make a journal-scope go/no-go decision.
5. Submit the strongest honest version rather than delay for another high-risk
   positive external/PINN rescue. A submission or preprint within one month is
   controllable; journal acceptance or publication within one month is not.

## Validation

- E1F/E1F-R targeted evidence tests: `25 passed`.
- Final full CPU suite: `419 passed in 375.64 s`.
- Project-governance audit: `pass_with_manual_review`, with no failed checks;
  frozen GT hashes pass and the five-file authoritative context is `22354`
  bytes against the `24576`-byte budget.
- Frozen GT, M40/M40R, original E1F artifacts, and the Zhang 13 V seal were not
  modified or numerically accessed by E1F-R.
