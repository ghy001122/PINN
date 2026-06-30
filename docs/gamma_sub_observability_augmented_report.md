# Gamma_Sub Observability-Augmented Audit Report

## Scope

All results are synthetic numerical digital-twin benchmark results. They are not measured experimental data, not full three-dimensional device simulations, and not sparse-port full hidden-field recovery.

This audit keeps frozen Ground Truth v1.1 files read-only and optimizes only `gamma_sub`. It introduces controlled synthetic `T_sw` mismatch targets, optional sparse temperature anchors, and narrower `T_sw` prior width to test whether minimal extra observability can reduce `gamma_sub` / `T_sw` confounding.

## Key Results

- Cases evaluated: `9`
- Port-only baseline relative error: `1.2222222222222223`
- Best temperature-anchor relative error: `1.2222222222222223`
- Best T_sw-prior relative error: `0.2222222222222222`
- Best combined relative error: `0.2222222222222222`
- Temperature anchors reduced bias: `False`
- Narrow T_sw prior reduced bias: `True`
- Combined observability reduced bias: `True`
- Frozen inputs unchanged: `True`

## Case Table

| case | mode | n_T_anchor | T_sw prior width | gamma_est | relative error | interpretation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `port_only_wide_tsw` | `port_only` | 0 | 1.0 | 1000000000.0 | 1.2222222222222223 | Port-only baseline under wide T_sw mismatch; exposes gamma_sub/T_sw confounding. |
| `port_plus_temperature_anchor_n2` | `port_plus_temperature_anchor` | 2 | 1.0 | 1000000000.0 | 1.2222222222222223 | This setting matched the port-only gamma_sub bias in this candidate-grid audit. |
| `port_plus_temperature_anchor_n4` | `port_plus_temperature_anchor` | 4 | 1.0 | 1000000000.0 | 1.2222222222222223 | This setting matched the port-only gamma_sub bias in this candidate-grid audit. |
| `port_plus_temperature_anchor_n8` | `port_plus_temperature_anchor` | 8 | 1.0 | 1000000000.0 | 1.2222222222222223 | This setting matched the port-only gamma_sub bias in this candidate-grid audit. |
| `port_plus_tsw_prior_wide` | `port_plus_tsw_prior` | 0 | 1.0 | 1000000000.0 | 1.2222222222222223 | This setting matched the port-only gamma_sub bias in this candidate-grid audit. |
| `port_plus_tsw_prior_narrow` | `port_plus_tsw_prior` | 0 | 0.1 | 550000000.0 | 0.2222222222222222 | Auxiliary observability or tighter T_sw prior reduced gamma_sub bias in this synthetic case. |
| `port_plus_temperature_anchor_and_tsw_prior_n2` | `port_plus_temperature_anchor_and_tsw_prior` | 2 | 0.1 | 550000000.0 | 0.2222222222222222 | Auxiliary observability or tighter T_sw prior reduced gamma_sub bias in this synthetic case. |
| `port_plus_temperature_anchor_and_tsw_prior_n4` | `port_plus_temperature_anchor_and_tsw_prior` | 4 | 0.1 | 550000000.0 | 0.2222222222222222 | Auxiliary observability or tighter T_sw prior reduced gamma_sub bias in this synthetic case. |
| `port_plus_temperature_anchor_and_tsw_prior_n8` | `port_plus_temperature_anchor_and_tsw_prior` | 8 | 0.1 | 550000000.0 | 0.2222222222222222 | Auxiliary observability or tighter T_sw prior reduced gamma_sub bias in this synthetic case. |

## Answers

Sparse port-only observations are not enough because terminal `G/I` can be matched by different combinations of effective heat loss and switching-temperature behavior. The prior confounding audits already showed that `T_sw` is a dominant sensitivity source, and this audit uses that mismatch as a controlled stress target.

In this candidate-grid audit, sparse synthetic temperature anchors alone did not reduce the gamma_sub bias under the wide T_sw mismatch target. These anchors are synthetic observability probes, not real experimental temperature measurements.

Tightening the T_sw prior reduced gamma_sub bias and is the dominant improvement in this audit. This supports an experimental-design rule: switching-temperature behavior should be independently calibrated or tightly bounded before robust `gamma_sub` extraction is claimed.

The combined cases improved relative to port-only because the T_sw prior was narrowed; the current evidence should not be read as proof that the sparse temperature anchors alone solve the confounding.

The practical implication is that terminal electrical data alone are insufficient for robust thermal-loss inference under switching-temperature uncertainty. Minimal extra observability is useful only if it constrains the dominant confounder or is sufficiently informative about thermal dynamics.

This audit still does not justify full hidden-field recovery. It supports only a constrained reduced inverse story for `gamma_sub` in a synthetic numerical benchmark.
