# Gamma_Sub Paper-Readiness Robustness Report

## Scope

All results are synthetic numerical digital-twin benchmark results. They are not experimental data, not full three-dimensional device simulations, and not sparse-port full-field recovery.

The benchmark is a one-dimensional reduced-order digital-twin used for sparse-port inverse identifiability and constrained `gamma_sub` inversion.

## Core Results

- Off-grid true `gamma_sub`: `462000000.0`
- Nearest-grid estimate: `450000000.0`
- Nearest-grid relative error: `0.025974025974025976`
- Refined estimate: `462018731.3745052`
- Refined relative error: `4.054410066065334e-05`
- Most dangerous confounder across observation counts: `T_sw`

## Observation-Count Sensitivity

| n_obs | nominal relative error | worst confounder | worst confounder relative error |
| ---: | ---: | --- | ---: |
| `8` | `0.0` | `T_sw` | `0.1111111111111111` |
| `16` | `0.0` | `T_sw` | `0.1111111111111111` |
| `32` | `0.0` | `T_sw` | `0.1111111111111111` |
| `64` | `0.0` | `T_sw` | `0.1111111111111111` |

## Answers For Paper Readiness

- The current one-dimensional reduced benchmark is adequate for a method-oriented SCI small paper only if the claim is restricted to sparse-port identifiability and constrained reduced-parameter inversion.
- The off-grid test remains locatable: nearest-grid error is bounded by grid spacing, and local log-quadratic refinement gives a continuous estimate for diagnostic use.
- Increasing observation count mainly improves confidence in the nominal target; it does not remove confounding when `T_sw` is released.
- `T_sw` remains the most dangerous confounder in this paper-readiness pack.
- The main claim must remain: constrained `gamma_sub` inversion is viable under fixed or tightly bounded switching/conductivity priors in a synthetic numerical digital-twin benchmark.

## Forbidden Interpretations

- Do not describe these outputs as measured experimental data.
- Do not claim complete three-dimensional device physics.
- Do not claim sparse-port full hidden-field recovery for `delta_T`, `c_v`, `m`, or `sigma`.
