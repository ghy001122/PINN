# M36 event-resolved orbit results and Q2 SCI assessment

## Executive result

M36 completed exactly the preregistered open-data numerical stage and stopped
at its primary solver gate. The independent DOP853 and Radau implementations
agree at all four open voltages, so the continuous-event reference itself is
credible. The source-compatible explicit-Euler family, however, passes all
primary gates only at 9 V. Consequently, the event-aware Jacobian, LOVO
multistart calibration, and fit-lock stages were not executed. The 13 V numeric
payload remained sealed and unaccessed.

This is `failed_but_informative`, not a repaired M35 result. M35's raw-time
failures and D0a's `0.1631480017203279` failure remain unchanged.

## Protocol and provenance integrity

- Pre-execution lock: `20/20` checks passed in
  `outputs/tables/m36_event_resolved_orbit_preregistration.json`.
- Immutable preregistration commit: `661142c`.
- Open voltages only: 9, 11, 15, and 17 V.
- Fixed Euler steps: 2.5, 1.25, 0.625, and 0.3125 ns.
- Independent references: DOP853 and Radau at `rtol=1e-9`, with explicit
  voltage/temperature tolerances and root-located extrema, reversal delay, and
  temperature-boundary events.
- No threshold, event window, start, parameter bound, or activity rule changed
  after simulation.
- No PINN training, Frozen GT edit, M34-A/M35 rerun, or 13 V access occurred.

The sampled source ledger and continuous root-located ledger remain explicitly
different semantics. M36 tested their limiting agreement; it did not silently
rename the continuous model as exact source code.

## Independent-reference result

| Voltage | Regime | DOP853/Radau parity | Reversal counts | Maximum event-time disagreement | Cycle-shape NRMSE |
| ---: | --- | --- | ---: | ---: | ---: |
| 9 V | static | pass | 0 / 0 | n/a | n/a |
| 11 V | oscillatory | pass | 196 / 196 | `9.47e-13 s` | `9.51e-8` |
| 15 V | oscillatory | pass | 344 / 344 | `1.18e-13 s` | `1.62e-8` |
| 17 V | static | pass | 0 / 0 | n/a | n/a |

At 11/15 V, period relative disagreement is `2.46e-9` and `2.95e-10`;
cycle-energy-ledger residuals are below `2e-7`. These results support only a
numerical-reference claim. They do not validate the source parameters or the
experimental device.

## Source-compatible Euler result

| Voltage | Automated classification | Finest-step evidence | Gate disposition |
| ---: | --- | --- | --- |
| 9 V | `normalization_artifact_resolved_by_absolute_noise_floor_metrics` | current/voltage RMSE are `0.000164` and `0.00197` of the locked noise floors; finest normalized score `0.0118` | pass |
| 11 V | `true_numerical_nonconvergence` | event error `67.5 ns > 25 ns`; cycle shape `0.0548 > 0.05`; peak error `0.0389 > 0.02`; score `2.70` | fail |
| 15 V | `true_numerical_nonconvergence` with coarse-grid event-sequence instability | event error `248.8 ns > 25 ns`; 2.5 ns grid has `342` versus `344` reference reversals; finest score `9.95` | fail |
| 17 V | `true_numerical_nonconvergence` | current RMSE is only `0.269` noise floors, but maximum current error is `62.365 > 5` noise floors; score `12.47` | fail |

All four normalized score sequences decrease overall toward the independent
reference, with fitted log-log slopes from `0.917` to `1.075`. That trend is
not enough: the finest locked step still fails primary thresholds at 11, 15,
and 17 V. In particular, the visually close phase-normalized 15 V cycles do
not override the fixed-index event-time gate. Calling 15 V a pure
phase-shadowing success would be post-hoc gate relaxation.

The 11 V long-horizon raw current NRMSE is `0.156`, but orbit shape and peak
gates still fail. The 15 V long-horizon current NRMSE is `0.267`, yet its orbit
shape, charge, energy, duty, and conservation metrics pass; the fixed event
error alone still blocks it. The 17 V failure is a localized maximum-error
boundary rather than an RMS or near-zero-normalization failure.

## Conditional work correctly skipped

Because `m36_primary_gates_pass=false`:

- no static/oscillatory/joint Jacobian or SVD was calculated;
- no event-time sensitivity, saltation-equivalent comparison, or quotient
  geometry was claimed;
- none of the eight deterministic LOVO starts was run;
- no repository parameter estimate or equivalence class was produced;
- no fit lock was created;
- no 13 V evaluation was authorized.

This prevents an attractive phase-aligned waveform from being used to justify
an inverse problem whose forward numerical contract has not passed.

## Primary-literature red team

| Primary source | Existing mechanism and limitation | M36 implication |
| --- | --- | --- |
| [Zhang et al., Nature Communications 2024](https://doi.org/10.1038/s41467-024-51254-4) | The thermal-neuristor compact model uses hysteretic VO2 resistance and a 10 ns Euler-Maruyama integration; the Methods state that constants were optimized to reproduce experiment. | The public curves are not independent validation, and M36's solver findings are a reproduction/numerical-semantics boundary. |
| [Ahmed and Wilson, Journal of Nonlinear Science 2024](https://doi.org/10.1007/s00332-023-09994-y) | Neural networks already infer reduced phase-amplitude coordinate models from observable oscillator data. | Phase normalization or a phase-amplitude neural representation cannot be the standalone novelty. |
| [Wedgwood et al., Journal of Mathematical Neuroscience 2013](https://doi.org/10.1186/2190-8567-3-2) | Classical moving phase-amplitude coordinates describe distance from a limit cycle but have a finite region where the coordinate transformation can lose invertibility. | Cycle coordinates are established analysis tools and must be restricted to a verified limit-cycle regime. |
| [Khan, Saxena and Barton, SIAM J. Scientific Computing 2011](https://doi.org/10.1137/100804632) | Hybrid limit-cycle sensitivity theory already separates period, amplitude, and relative-phase sensitivity and accounts for jumps at discrete transitions. | Event/saltation-aware sensitivity is a baseline, not a new contribution; M36 did not reach this stage. |
| [Kharazmi et al., Nature Computational Science 2021](https://doi.org/10.1038/s43588-021-00158-0) | PINN-based structural/practical identifiability and uncertainty analysis already exist, and the paper stresses non-uniqueness under sparse/noisy data. | “PINN plus identifiability” is not novel, and no M36 trained-PINN or inverse claim exists. |

The only proposed differentiator remains the unproven combination of a full
phase-transition PINN, independently verified sensitivity geometry, and a
branch/protocol-conditioned identifiable quotient. M36 does not support that
combination and supplies no world-first basis.

## Final validation and administrative lock correction

The single permitted full-repository test run completed in `353.02 s` with
`329 passed, 1 failed`. The sole failure was not scientific: M35 had hash-locked
the repository-wide `.gitignore`, while the M36 preregistration commit appended
tracking exceptions for M36 result files. This cross-round administrative
conflict was corrected by restoring the exact M35 `.gitignore` hash and
force-staging the M36 outputs. The original M36 preregistration remains
permanently preserved in commit
`661142c634867796e607427fe8efffe8bcb47e55`; its working lock record was amended
only to reference the restored administrative-file hash. No scientific code,
configuration, threshold, event rule, or generated result changed.

After that correction, the focused M35/M36 integrity suite passed `6/6` in
`0.95 s`, and direct recomputation found zero hash mismatches in either locked
file set. Strict JSON/CSV parsing passed, the governance audit returned
`pass_with_manual_review` with no failed checks, and every Frozen GT v1.1 hash
matched its expected value. A second full test run was intentionally not
performed because the execution contract allowed exactly one. Accordingly,
this report does not misstate the final tree as having received a second clean
full-suite run.

## Net progress toward a Q2 SCI paper

What improved:

1. The numerical ambiguity behind M35 is resolved more sharply. A high-order
   continuous-event reference is reproducible across two independent methods.
2. The 9 V failure is correctly identified as a near-zero normalization issue,
   while 11/15/17 V retain concrete, voltage-specific failure boundaries.
3. The project avoided an invalid public fit and protected the sealed 13 V
   evaluation from leakage.
4. Four reviewable figures and strict event/conservation tables now support a
   numerical-methods limitation section or supplement.

What did not improve:

1. There is still no public-data calibration, parameter-equivalence result,
   protocol-dependent subspace evidence, fit lock, or 13 V evaluation.
2. There is still no trained full-PINN forward success, sensitivity fidelity,
   or inverse result.
3. The proposed protocol-conditioned quotient hypothesis remains untested, not
   supported.
4. M36 strengthens reviewer defense but does not create a new positive headline
   claim.

The distance to a defensible Q2 paper therefore remains material. Engineering
reproducibility and claim governance are strong, but the positive scientific
center is still the narrower synthetic, calibration-gated rank-1 `gamma_sub`
result. A Q2 submission centered on a successful public quotient inverse or a
validated trained full PINN is not currently supportable. Journal acceptance
cannot be promised, and the likely paper must be reframed as an evidence-bounded
synthetic inverse study with explicit full-PINN and public-source limitations.

## Unique next action

Close the present public-refit route and perform manuscript evidence
compression. Build the main text around the locked `gamma_sub` result, retain
the complete full-PINN architecture only with its failed training boundary,
move M36 to numerical reproducibility/limitations and reviewer defense, and
remove unsupported public calibration, quotient, protocol-rank, 13 V, and
trained-PINN-success language. Do not add finer steps, new starts, new
parameters, or another public-solver rescue round.
