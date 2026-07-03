# Stiffness And Quasi-2D Storyboard

## Purpose

This storyboard explains how stiffness-continuation, phase-field alignment, and quasi-2D preflight evidence should enter the paper without changing the main `gamma_sub` claim.

## Story Order

1. Main text: identify sparse-port ill-posedness and reduce the inverse target to `gamma_sub`.
2. Main text: show calibration-gated inversion and the dominance of `T_sw` calibration.
3. Supplementary: show the residual stiffness cliff with transition width.
4. Supplementary: show continuation as a stabilizing preflight, not full STL.
5. Supplementary: show Fourier-feature caution because gain is not uniform.
6. Related work / supplementary: show phase-field full-field-anchor mobility inversion as paradigm alignment.
7. Discussion: use quasi-2D preflight to argue physical extensibility and observability limits.

## Figure Routing

- `outputs/figures/stiffness_residual_vs_transition_width.png`: residual cliff defense.
- `outputs/figures/stiffness_continuation_gain_vs_width.png`: continuation aid.
- `outputs/figures/stiffness_fourier_gain_caution.png`: no Fourier superiority.
- `outputs/figures/phase_field_m_true_vs_estimated.png`: phase-field inverse alignment.
- `outputs/figures/phase_field_noise_sensitivity.png`: noise sensitivity.

## Short Manuscript Sentence

The supplementary results show that phase-transition cliffs create residual stiffness and that phase-field inverse problems are a relevant literature neighbor, but the validated manuscript claim remains calibration-gated sparse-port reduced inversion of `gamma_sub`.

## Experimental Resolution Update

All results remain synthetic numerical digital-twin benchmark evidence, not experimental data.

The storyboard now has three reproducible claim-gate experiments:

1. `scripts/audit_reduced_2d_phase_transition_forward.py` converts quasi-2D narration into a reduced 2D forward benchmark with geometry and lateral-coupling scans.
2. `scripts/audit_reduced_2d_observability_limited_inverse.py` separates terminal-only failure from augmented sparse-observation low-dimensional inverse support.
3. `scripts/audit_stiffness_aware_algorithm_benchmark.py` tests continuation, scale-aware weighting, and mini-STL-style transfer as stiffness-mitigation strategies.

The correct wording is supplementary and qualified: reduced 2D forward behavior is supported; low-dimensional 2D inverse diagnosis is supported only under augmented observations; full-field 2D recovery remains forbidden.
