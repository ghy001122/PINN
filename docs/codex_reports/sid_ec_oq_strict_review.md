# Solver-first SID / EC-OQ strict review

Preregistered commit: `18b703a366663b83947e8b84143481a99854362a`.

All physical-identifiability geometry uses solver-generated, noise-whitened terminal current only. No hidden fields, public labels, 13 V data, or PINN-predicted physics were used.

## Numerical derivative gate

Converged cases: `3/9`; maximum relative discrepancy: `0.648429`.

The three anchor outcomes are already inconsistent: the low-amplitude triangle passes (`0.009737`), while the high-amplitude triangle (`0.072743`) and multipulse (`0.387241`) fail the `<=0.05` derivative gate. Consequently, numerical rank and angle observations remain diagnostics and cannot vote for a scientific rank/rotation claim.

## Event-window evidence

Best 95% bootstrap angle lower bound: `0.49066` degrees; best rank-change consistency: `1`; best switch information ratio: `10.2087`.

The preregistered low-amplitude triangle switch window spans all `160` samples because the normalized current-rate term is constant on the triangle ramp. The window was not moved after inspection. This is a failed event-window boundary, not evidence for switch-localized geometry.

## Training geometry boundary

The last finite Adam checkpoint supports only `['locked_triangle_0p20']`. It is therefore not evidence of a three-protocol dual geometry, even when its matrix-free VJP sketch is finite.

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
| Derivative convergence | `3/9`, maximum difference `0.648429` | all `<=0.05` | fail |
| Bootstrap angle lower bound | `0.49066 deg` | `>15 deg`, unless rank vote valid | fail |
| Rank-change consistency | `1.0` | `>=0.80` | non-voting because derivative gate fails |
| Switch information ratio | `10.2087` | `>=2` | pass |
| Switch training-condition ratio | `1.90380` | `>=10` | fail |
| Stable physical protocols | `1` | `>=3` | fail |
| Neighborhood direction stability | false | true | fail |

## Decision

SID retained: `False`; EC-OQ retained: `False`; disposition: `fallback_fixed_rank1_gamma_sub_delete_sid_and_ec_oq`.

Pairwise raw angles as large as `79.3 deg` are not claimable because the derivative and stability prerequisites fail. The only permitted manuscript use is a `failed_but_informative` numerical/window boundary; protocol-dependent rotation, rank change, SID dual geometry, and EC-OQ are deleted from the active scientific route.

A finite targeted search cannot establish world-first novelty. Fisher/SVD identifiable combinations, event-aware differentiation, gradient balancing, NNCG/SOAP, PirateNet, causal schedules, IRK-PINN, DWR, PINO, DeepONet, and Preisach/LLP remain prior components or baselines.
