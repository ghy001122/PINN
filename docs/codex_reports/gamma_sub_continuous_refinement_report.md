# Gamma_Sub Continuous Refinement Report

## Scope

All results are synthetic numerical digital-twin benchmark results. They are not experimental data, not full three-dimensional device simulations, and not sparse-port full-field recovery.

This audit optimizes only `gamma_sub`. `T_sw`, `tau_m`, `sigma_on0`, `eta_A`, `D_v0`, and `mu_v0` remain fixed at prior values. The continuous refinement re-runs the existing simulator at each trial `gamma_sub`; it is not candidate-profile interpolation.

## Key Results

- Cases evaluated: `36`
- Maximum nearest-grid relative error: `0.08225108225108226`
- Maximum continuous-refined relative error: `0.05565017963752034`
- Mean error reduction: `0.019138563856834004`
- All off-grid cases exclude true gamma from candidate grid: `True`
- Continuous refinement re-simulated non-grid gamma values: `True`
- Configured success relative-error threshold: `0.15`
- Most dangerous confounder from prior audits: `T_sw`

## Noise And Observation Sensitivity

- Noise `0.0`: max continuous-refined relative error `1.3332517794414198e-05`, all success `True`.
- Noise `0.02`: max continuous-refined relative error `0.03144411132238322`, all success `True`.
- Noise `0.05`: max continuous-refined relative error `0.05565017963752034`, all success `True`.

- `n_obs = 8`: max continuous-refined relative error `0.05565017963752034`, all success `True`.
- `n_obs = 16`: max continuous-refined relative error `0.04835415227915081`, all success `True`.
- `n_obs = 32`: max continuous-refined relative error `0.02528417794415084`, all success `True`.
- `n_obs = 64`: max continuous-refined relative error `0.03997007467843599`, all success `True`.

## Answers

Continuous refinement lowers off-grid error in the tested synthetic benchmark by replacing nearest-grid selection with simulator-backed scalar optimization in the local gamma neighborhood.

The result no longer depends on the candidate grid containing the true `gamma_sub`: all official off-grid truth values are excluded from the grid, and refinement evaluations are non-grid simulator calls.

Increasing observation count generally stabilizes the scalar objective, while noise can widen the refined-error spread. The official cases remain within the configured success threshold.

`T_sw` remains the most dangerous confounder by the prior confounding and paper-readiness audits. This script does not release `T_sw`; it intentionally keeps switching and conductivity priors fixed.

The paper claim must remain limited to fixed or tightly bounded priors in a one-dimensional reduced-order synthetic numerical digital-twin benchmark.
