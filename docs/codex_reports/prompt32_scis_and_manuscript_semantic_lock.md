# Prompt 32: SCIS and manuscript semantic lock

Date: 2026-07-18
Base commit: `44dac1a5414f6a5eb84f9d8f2db2314d5d3a9f8a`
Commit-ordered preregistration: `189445a2df5969a9428cdd035a3a9be0cc5f81af`
Stage: `M32_SCIS` inside `M_GAMMA_SUB_MANUSCRIPT_ASSEMBLY`
Evidence type: synthetic numerical digital-twin, cached direct-solver scoring, static implementation audit
Claim disposition: `failed_but_informative`

## Executive result

M32 removes true-parameter access from the new SCIS inference path and cleanly separates point success, set coverage, certificate acceptance, conditional accuracy, and refusal. The nominal discrete-grid coverage gates pass, but the severe model-mismatch refusal gate fails: at true `gamma_sub=4.5e8` and `delta_T_sw_K=2`, all held-out cases are accepted while none of the point estimates is within the `15%` success radius. SCIS is therefore not an operational coverage/refusal certificate.

No ODE trajectory was generated, no PINN was trained, no frozen GT file changed, and sealed 13 V data were not accessed. The full-PINN architecture remains the mandatory paper scaffold, but no positive trained-PINN evidence is added.

## Commit-order and cache stop gate

The first commit locks `configs/gamma_sub_scis_v1.yaml`, the truth-free inference formula, finite-sample quantile, seed blocks, schema, cache-only implementation, and tests before any SCIS scoring output exists. The preregistration is an internal commit-ordered record, not an independent timestamp.

The subsequent preflight validates all 36 required CEBA base-solver cache entries:

- 15 candidate trajectories for each of triangle and LTP/LTD;
- three target trajectories (`delta_T_sw_K=0,0.2,2`) for each protocol;
- embedded cache-key equality, finite vectors, strict time ordering, and payload shape;
- zero solver fallback, zero new ODE evaluations, zero PINN training runs.

Any missing or invalid entry raises `CacheMissStop`. The preflight passed, authorizing cache-only scoring.

## CEBA point/set/abstention audit

The historical CEBA artifacts are unchanged and hash-locked. The implemented profile cutoff is exactly

$$
J_{\min}+0.05(J_{\max}-J_{\min}).
$$

However, `_score_trace` receives `true_gamma`, defines retained recoverable classes through truth-relative error, and locally assigns `threshold = 0.15`. The resulting abstention is an oracle diagnostic and cannot be executed on an unknown real parameter. CEBA did not define set coverage, a truth-free certificate acceptance rule, or conditional accuracy among accepted cases.

At `n=32`, `noise=0.02`, and five historical discovery seeds:

| Protocol | `delta_T_sw_K` | Point success | Oracle abstention | Historical combined success |
| --- | ---: | ---: | ---: | ---: |
| triangle | 0.0 | 1.0 | 1.0 | 0.0 |
| triangle | 0.2 | 0.0 | 1.0 | 0.0 |
| triangle | 2.0 | 0.0 | 0.0 | 0.0 |
| LTP/LTD | 0.0 | 1.0 | 1.0 | 0.0 |
| LTP/LTD | 0.2 | 1.0 | 1.0 | 0.0 |
| LTP/LTD | 2.0 | 0.0 | 0.0 | 0.0 |

Candidate-grid span also affects the five-percent retained set. Removing the low `1.5e8` endpoint changes the retained set in `22/30 = 73.33%` of audited protocol/delta/seed cases. Removing `1.0e9` changes the set in `10/30 = 33.33%`; among candidates shared by both grids the membership is unchanged for that high-end deletion. These are diagnostics and do not rewrite M31 parity or pilot results.

## Figure 5 semantic audit

The audit verifies the actual solver and objective contract:

- all six `candidate_name` entries use `simulator_protocol=ltp_ltd`;
- there are three distinct voltage-waveform hashes across the six candidates;
- `t_max`, positive/negative amplitudes, and `calibration_error_factor` vary across candidate labels;
- solver: `nx=7`, `nt=48`, Radau, `rtol=1e-4`, `atol=1e-6`;
- gamma grid: seven candidates from `3.75e8` through `1.0e9`;
- objective: `1.0*G_loss + 0.5*I_loss + 0.01*heat_residual_loss`;
- the heat residual is implemented on the candidate simulation and is not target-temperature supervision;
- `calibration_error_factor` is consumed, while configured `prior_width_factor` is not consumed;
- the historical output contains 720 finite simulator-backed cases.

Because calibration error, waveform, and duration vary together, the 720-case comparison cannot isolate causal protocol gain. Figure 5 is retained as `qualified_supported` only for bundled calibrated-configuration performance. Protocol gain, optimality, and experimental validation are forbidden.

## SCIS preregistration and results

For each candidate (\gamma_j), protocol, observation count, and noise condition, 50 calibration seeds define

$$
s_j(y)=J(\gamma_j;y)-\min_kJ(\gamma_k;y),
\qquad
C_\alpha(y)=\{\gamma_j:s_j(y)\le q_j\},
$$

with `alpha=0.10` and finite-sample rank `46/50`. Fifty disjoint held-out seeds determine the reported metrics. Ten separate discovery seeds are implementation diagnostics only. Inference receives objectives, candidate coordinates, thresholds, and the `0.15` radius; it does not receive true gamma.

Primary nominal results (`noise=0.02`):

- held-out cases: 3000;
- pooled set coverage: `0.932333` (`>=0.90`, pass);
- worst candidate: `gamma_sub=4.75e8`, coverage `0.85` (`>=0.80`, pass);
- point success: `0.996`;
- certificate acceptance: `1.0`;
- conditional point accuracy among accepted cases: `0.996` (`>=0.90`, pass);
- true `4.5e8` nominal acceptance: `1.0` (`>=0.80`, pass).

Stress and sensitivity results at true `4.5e8`:

| Condition | Point success | Certificate acceptance | Interpretation |
| --- | ---: | ---: | --- |
| `delta=0` | 1.0 | 1.0 | nominal only |
| `delta=0.2 K` | 0.375 | 1.0 | mismatch warning missed |
| `delta=2 K` | 0.0 | 1.0 | refusal gate failed |

Deleting the pre-registered remote `1.0e9` candidate and recalibrating with the same locked calibration seeds changes `0.0` of the acceptance/refusal decisions (`<=0.10`, pass). The zero-noise block contains 3400 rows in 68 conditions; all 50 seed replicas within each condition produce identical decisions. It is reported only as deterministic sanity, not coverage or robustness evidence.

### Gate disposition

| Gate | Result |
| --- | --- |
| nominal pooled coverage `>=0.90` | pass (`0.932333`) |
| worst-candidate coverage `>=0.80` | pass (`0.85`) |
| true `4.5e8` nominal acceptance `>=0.80` | pass (`1.0`) |
| conditional accuracy given acceptance `>=0.90` | pass (`0.996`) |
| `delta=2 K` acceptance `<=0.20` | **fail (`1.0`)** |
| remote-candidate decision change `<=0.10` | pass (`0.0`) |
| seed separation | pass |
| cache-only / zero new ODE | pass |
| zero PINN training | pass |

The all-gates claim is rejected. Alpha, seeds, grid, radius, and acceptance rule were not changed after inspection.

## Literature novelty boundary

The six-source primary-literature red team is recorded in `docs/literature/scis_profile_set_uq_red_team_v1.md`. Profile likelihood, simulation-based calibration, conformal/set-valued coverage, simulator-based inverse confidence regions, and inverse-problem UQ all have direct precedent. SCIS, mixed formulations, augmented Lagrangians, and event conditioning cannot be claimed as innovations by component. The project-specific complete-PINN plus solver-verified sensitivity plus conditioned identifiable-coordinate/refusal combination remains an unverified hypothesis.

## Allowed and forbidden manuscript wording

Allowed:

- CEBA exact-source parity is supported; its boundary hypothesis remains `failed_but_informative`.
- Historical CEBA point success and oracle abstention may be reported separately as a synthetic diagnostic.
- M32 SCIS achieved nominal held-out coverage on the frozen discrete candidate grid and locked simulator/noise population.
- SCIS failed to refuse severe switching-temperature mismatch.
- Figure 5 reports conditional performance of a bundled synthetic calibrated configuration.

Forbidden:

- CEBA or SCIS provides a deployable runtime coverage/refusal certificate;
- nominal coverage implies robustness to model mismatch;
- continuous-parameter, experimental, cross-device, or cross-material coverage;
- Figure 5 isolates protocol gain or selects an optimal experimental protocol;
- any new full-PINN training, sensitivity, inverse, independent 13 V, or experimental-validation claim;
- world-first claims based on absence of a search result.

## Distance to delivery and next single priority

This round resolves three reviewer-facing semantic risks: it exposes oracle leakage in CEBA abstention, prevents Figure 5 from being read as a causal protocol study, and tests a truth-free replacement under a fail-closed gate. The replacement fails where refusal matters, so the safe paper mainline remains the calibration-gated rank-1 `gamma_sub` result with complete-PINN architecture retained as mandatory scaffold and negative trained-forward evidence disclosed.

The immediate highest-value, high-feasibility action is manuscript assembly: propagate the Figure 5 label, CEBA oracle limitation, and SCIS mismatch-refusal failure into captions, limitations, and reviewer defense without starting another UQ or neural experiment. After manuscript closure, any new research phase should return to independent solver/field/interface/conservation fidelity for the complete PINN before attempting sensitivity or inverse claims.

## Validation

Focused result-lock tests pass `16/16`. The single full-suite run reports `280 passed, 2 failed in 251.27 s`; both failures are governance assertions caused by the five-file low-token context budget after the first documentation expansion, not numerical, cache, physics, or SCIS failures. The authority surface was compacted without removing evidence, reducing the audited total to `24185 < 24576` bytes. The first explicit governance attempt then exposed two exact parser markers removed during compaction; after restoring only those routing markers, the final governance audit reports `pass_with_manual_review`, zero failed checks, all eight frozen-GT hashes unchanged, and the expected portable-mtime/client-autoload manual reviews. The full suite was not rerun, per the one-run constraint.

The single strict tracked-JSON pass parses `148` tracked JSON files with zero failures. Git diff check, the two-commit limit, one push, and one remote fast-CI observation are final commit/handoff preconditions and are recorded in `outputs/tables/prompt32_final_validation.json` and the handoff.
