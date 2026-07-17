# N0 Optimizer Forensics and SID Discovery — Final Evidence Report

## Scope and manuscript use

This report closes the user-authorized `N0_OPTIMIZER_FORENSICS_AND_SID_DISCOVERY` phase. It contains two bounded, independently stoppable packages:

1. an instrumented replay of the historical N0-CV-E optimizer failure, with at most one conditional recovery arm; and
2. a solver-first event-window information-geometry discovery audit for SID/EC-OQ.

The phase does not revise frozen GT v1.1, historical N0/P1/P2/P3 evidence, D0 evidence, or the calibration-gated rank-1 `gamma_sub` mainline. Its manuscript value is reviewer defense: it separates runtime abort, post-Adam physical failure, optimizer instability, numerical derivative validity, and exploratory subspace geometry.

## Version and preregistration chain

- User-specified remote start: `b3800fd55dc1e2fd08ca802efc73d0e0bc7fab7a`.
- Definition/preregistration commit: `18b703a366663b83947e8b84143481a99854362a`.
- Remote: `https://github.com/ghy001122/PINN.git`, branch `main`.
- Both locks record a clean worktree, exact commit, `origin/main`, remote URL, config hash, and locked implementation hashes.
- Frozen GT, historical outputs, and old checkpoints were not overwritten.

## Package A — N0-CV-E v3r

The exact locked Adam schedule completed `1200` steps. Six checkpoints and persistent telemetry were written. The first replay then exposed a score-only implementation ordering defect before L-BFGS; the attempt, logs, and checkpoints are retained. A process-local binding of the already-specified `dx=L_eff/nx` enabled identical post-Adam scoring without changing the scientific algorithm. This operational repair caps all positive claims at `failed_but_informative`.

At Adam-1200, parameters, gradients, and Adam moments are finite and the total loss has fallen from `1.50627e13` to `2.66531e9`. However, only the port, discrete-electric, interface-state, IC/BC, finite-output, and state-bound gates pass. Thermal and phase residuals, fields, interface flux accuracy, and both conservation ledgers fail. Five metrics exceed their gates by at least `20x`, so the preregistered recovery eligibility is false. No float64 arm, balancing arm, or seed expansion was run.

The primary L-BFGS driver did not preserve exact attribution because an infinite diagnostic norm reached strict JSON serialization. A serializer-safe replay from the same pre-L-BFGS checkpoint reproduced the strong-Wolfe failure at closure `3`; the first non-finite parameter is `backbone.net.0.weight`, after which all six monitored loss blocks are non-finite. This resolves the optimizer failure type without changing the historical `b380` substatus: the old run remains `runtime_abort_unassessed`, while v3r separately demonstrates both a scoreable post-Adam physical failure and a reproducible L-BFGS instability.

Primary artifacts:

- `outputs/tables/n0_cv_e_v3r_forensic_resolution.json`
- `outputs/tables/n0_cv_e_v3r_post_adam_score.json`
- `outputs/tables/n0_cv_e_v3r_lbfgs_diagnostic_crash.json`
- `outputs/tables/n0_cv_e_v3r_telemetry.jsonl`
- `outputs/tables/n0_cv_e_v3r_checkpoint_manifest.json`
- `outputs/checkpoints/n0_cv_e_v3r/`
- `docs/codex_reports/n0_cv_e_v3r_optimizer_forensics.md`

Disposition: `failed_but_informative`; permanent N0 optimizer stop.

## Package B — solver-first SID/EC-OQ

The solver-only audit used terminal-current observations and `189` forward evaluations, below the locked cap of `420`. It computed pre-switch, switch, post-switch, and cooling/recovery windows, whitened finite-difference Jacobians, SVD/rank diagnostics, principal angles, bootstrap intervals, and matrix-free training-geometry proxies.

The central numerical prerequisite fails: only `3/9` derivative cases satisfy the locked `<=5%` agreement gate, and the maximum discrepancy is `0.648429`. The low-amplitude triangle's preregistered switch rule also spans its entire `160`-point trace because its normalized current-rate is constant on the ramp; the window was not adjusted after inspection. Although isolated diagnostics show rank consistency and a switch information ratio above two, they cannot vote after derivative failure. The corrected angle lower bound is only `0.49066 deg`, training-condition worsening is `1.90380` rather than `10`, and only one protocol has stable physical geometry. The last finite PINN checkpoint covers one locked triangle protocol, so it cannot support three-protocol dual-geometry evidence.

Primary artifacts:

- `outputs/tables/sid_ec_oq_summary.json`
- `outputs/tables/sid_ec_oq_cases.csv`
- `outputs/tables/sid_ec_oq_bootstrap.csv`
- `outputs/tables/sid_ec_oq_event_windows.json`
- `outputs/figures/sid_ec_oq_spectrum.png`
- `outputs/figures/sid_ec_oq_principal_angles.png`
- `outputs/figures/sid_training_information_geometry.png`
- `docs/codex_reports/sid_ec_oq_strict_review.md`

Disposition: `failed_but_informative`; delete both SID and EC-OQ from the active route and fall back to fixed rank-1 `gamma_sub`.

## Claim changes

Allowed:

- The historical b380 run is a runtime abort with no scoreable trajectory; it is not scientific model falsification.
- The v3r post-Adam trajectory passes a narrow port gate but fails the locked physics, field, interface-flux, and conservation evidence package.
- The same pre-L-BFGS checkpoint reproduces a strong-Wolfe non-finite parameter failure under serializer-safe diagnostic capture.
- The solver-first discovery audit fails its derivative, event-window, stability, and dual-geometry prerequisites.
- Trajectory agreement or isolated rank/angle diagnostics are insufficient for inverse or protocol-geometry claims.

Forbidden:

- reliable or conservative full-PINN forward evidence;
- PINN sensitivity fidelity or inverse readiness;
- SID dual geometry, protocol-dependent EC-OQ rotation/rank change, or quotient superiority;
- experimental validation, independent external validation, unique raw-parameter recovery, full hidden-field recovery, or standalone novelty for SVD/Fisher/event/gradient-balancing components.

## Distance to delivery and next action

This phase closes two speculative branches and strengthens the negative-evidence/reviewer-defense chain, but it does not upgrade the paper's central positive claim. The calibration-gated constrained rank-1 `gamma_sub` result remains the only safe inverse mainline. The unique next action is manuscript/submission assembly from the existing evidence lock, explicitly including D0a and N0/SID failures; no new training or identifiability branch should be opened in the active queue.
