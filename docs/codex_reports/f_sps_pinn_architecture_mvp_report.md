# F-SPS-PINN Architecture MVP Report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Commit hash: `0dbef58db3bb82b632d63eb4a58927a0e699a31b`

## Scope

This task implements an isolated F-SPS-PINN architecture MVP for synthetic numerical digital-twin benchmark work. It does not replace the existing v0/v1/v1.1 training workflows, does not modify frozen Ground Truth v1.1, and does not claim real VO2/NbO2 experimental validation.

## Changed Files

- `CODEX_CONTEXT.md`
- `docs/research_strategy/active_phase.md`
- `docs/codex_reports/f_sps_pinn_architecture_mvp_report.md`
- `src/pinnpcm/physics/vo2_constitutive.py`
- `src/pinnpcm/physics/oscillation_metrics.py`
- `src/pinnpcm/pinn/network.py`
- `src/pinnpcm/pinn/loss_balancer.py`
- `tests/test_vo2_constitutive.py`
- `tests/test_fourier_pyramid.py`
- `tests/test_loss_balancer.py`
- `tests/test_oscillation_metrics.py`
- `tests/test_imports.py`

## Implemented Modules

- `vo2_constitutive.py`: differentiable VO2-like white-box conductivity closure with `phase_fraction_from_temperature`, insulating and metallic branches, stable effective-medium mixing, and `vo2_sigma`.
- `network.py`: opt-in `FourierPyramidEmbedding` and `StiffAwareMLP`; existing `FourierFeatureMLP` behavior is preserved.
- `loss_balancer.py`: `DynamicResidualGate` and `gated_residual_loss` for residual weighting with anti-collapse safeguards.
- `oscillation_metrics.py`: differentiable frequency, pulse-width, and oscillation signature losses for future oscillator-aware synthetic benchmarks.

## Numerical-Stability Safeguards

- Conductivity outputs are clamped to positive finite ranges.
- Temperature-dependent conductivity uses log-space evaluation and exponent clamps.
- Phase transition width has a lower bound to avoid division by near-zero values.
- Extreme temperature inputs are covered by unit tests.

## Differentiability Safeguards

- VO2-like conductivity and phase fraction use torch operations and support autograd with respect to temperature.
- Fourier pyramid embedding is deterministic, differentiable, and opt-in.
- Dynamic residual gating keeps trainable logits differentiable.
- Oscillation losses avoid hard peak detection and hard thresholding in the main gradient path.

## EMA sqrt/discriminant Safeguards

- Default effective-medium mode is stable `linear` mixing.
- Optional `bruggeman` mode clamps the phase fraction away from exact endpoints and clamps the quadratic discriminant before `torch.sqrt`.
- Unit tests cover near-zero Bruggeman inputs without NaN/Inf values or gradients.

## FFT Magnitude Safeguards

- Frequency estimation uses `torch.fft.rfft` but computes spectral power as `real**2 + imag**2 + eps`.
- The implementation does not use `torch.abs` for complex FFT magnitude on the training-loss path.
- Frequency estimation uses soft spectral weights instead of `torch.argmax`.
- Zero-signal backward is tested and remains finite.

## Dynamic-Gate Anti-Collapse Safeguards

- Temperature-scaled softmax uses `tau > 1` by default.
- Detached EMA residual-scale normalization reduces raw residual magnitude dominance.
- Entropy regularization discourages early one-hot behavior.
- Minimum weight floor keeps each residual active.
- Extreme residual-scale tests verify weights remain normalized and do not collapse to one loss.

## Validation

Executed:

```powershell
python -m pytest
```

Result:

```text
47 passed, 274 warnings
```

The warnings are existing matplotlib/pyparsing deprecation warnings from prior gamma_sub smoke tests. No test failed.

## Boundary Checks

- Modified frozen GT: No.
- Replaced old `log_sigma` main path: No.
- Modified v0/v1/v1.1 training scripts or outputs: No.
- Ran long training experiments: No.
- Claimed real VO2/NbO2 experimental validation: No.

## Next Step

Add a lightweight v2 smoke training config/script that explicitly opts into the new white-box conductivity closure and Fourier pyramid modules, while keeping old `log_sigma` as an ablation baseline.