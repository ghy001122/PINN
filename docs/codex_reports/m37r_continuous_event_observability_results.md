# M37R repaired continuous-event observability results

## Outcome

- Status: `stopped_at_dop853_perturbation_post_transient_event_gate`.
- Claim status: `failed_but_informative`.
- Decision route: `B_local_continuous_jacobian_geometry_not_numerically_reliable`.
- Forward evaluations: `{'DOP853': 7, 'Radau': 4, 'total': 11}`.
- Cache hits: `0`.
- Solver wall time: `397.477 s`.
- GPU use: `0`; fit, optimization, bootstrap, PINN training, M38, and 13 V access: `not executed`.

M37R is solver-generated local continuous-model observability evidence at
the declared published-source parameter anchor. It is not a public-data fit,
parameter recovery result, trained-PINN result, or experimental validation.

## Repaired event-window contract

All M36 reference rows, nominal runs, perturbations, and both solvers use
the exact interval $[t_0+0.1(T-t_0),T]$. Both endpoints are inclusive and
no floating tolerance is applied. Full-horizon counts are diagnostics only;
post-transient counts and signatures alone vote on reproduction/topology.

| Voltage | DOP853 full | DOP853 post | Radau full | Radau post | M36 post | Nominal gate |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 9 | 0 | 0 | 0 | 0 | 0 | pass |
| 11 | 216 | 196 | 216 | 196 | 196 | pass |
| 15 | 381 | 344 | 381 | 344 | 344 | pass |
| 17 | 4 | 0 | 4 | 0 | 0 | pass |

## Scientific stop diagnosis

The nominal implementation contract is closed. The first two perturbation
traces (`9 V` and `11 V`) for `log_C_th=-1%`, `h=0.01` remain finite,
activity-consistent, and topology-compatible. The next trace, at `15 V`, is
finite and remains `sustained_spiking`, but its full/post counts are `379/343`
instead of nominal `381/344`. The post-transient signature has common-prefix
length `0`, so the first retained reversal type differs. This violates the
preregistered exact-common-prefix topology rule even though the count differs
by only one. Execution therefore stops after `11` forwards, as required.

This is not a source-window implementation error and not evidence for a rank
or direction rotation. It is a local hybrid-event differentiability boundary:
the declared central-difference column cannot be formed reliably at this
anchor under the locked feature/topology contract.

## Jacobian and SVD geometry

| Group | Rank | Singular values | Effective rank | Condition | Jacobian change | Left angle |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| static_only | not reached | not reached | not reached | not reached | not reached | not reached |
| oscillatory_only | not reached | not reached | not reached | not reached | not reached | not reached |
| joint | not reached | not reached | not reached | not reached | not reached | not reached |

Static/oscillatory acute top-direction angle: `not reached` degrees.
No whitened Jacobian was completed. The machine JSON therefore stores empty
Jacobian/group objects, and the spectra CSV contains one `not_reached` row.

## Independent-solver crosscheck

| Group | Min column cosine | DOP853 rank | Radau rank | Retained singular difference | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| static_only | not reached | not reached | not reached | not reached | not reached |
| oscillatory_only | not reached | not reached | not reached | not reached | not reached |
| joint | not reached | not reached | not reached | not reached | not reached |

## Preregistered gate vote

| Gate | Pass |
| --- | --- |
| `nominal_window_reproduction` | `true` |
| `all_states_finite` | `true` |
| `all_activity_classes_exact` | `true` |
| `all_post_transient_event_topologies_compatible` | `false` |
| `two_finest_white_jacobian_stability` | `false` |
| `two_finest_retained_left_subspace_stability` | `false` |
| `dop853_radau_column_direction_consistency` | `false` |
| `dop853_radau_retained_singular_value_consistency` | `false` |
| `dop853_radau_rank_consistency` | `false` |
| `joint_rank` | `false` |
| `joint_condition` | `false` |
| `static_oscillatory_complementarity` | `false` |
| `analytic_rank_invariance` | `false` |
| `forward_budget` | `false` |
| `wall_clock_budget` | `false` |
| `all` | `false` |

The early-stop schema records every downstream or not-reached closure gate as
`false`, including the two final budget-closure flags. Those flags do not mean
that a cap was exceeded: observed use was `11/72` forwards and `397.477/7200 s`.
They mean the full geometry vote did not reach final closure. This fail-closed
serialization does not alter the topology failure or the decision route.

## Claim and manuscript routing

The positive local complementarity claim is `failed_but_informative`.
The route returns to `Q2_MANUSCRIPT_EVIDENCE_COMPRESSION`; no rescue
step, smoothing, saltation variant, extra feature, extra step, or fit is allowed.

The analytic quotient transform is reversible and is reported only as an
audit; it does not create rank or constitute a novelty claim.

Forbidden wording remains: public fit, unique recovery, experimental or
independent external validation, gamma_sub/S_e equivalence, trained-PINN
success, 13 V evaluation, world-first, or standalone SVD/Fisher/event novelty.

## Validation

- Preformal contract tests: `9 passed, 5 result-only skips`.
- Postformal M37R result tests: `14 passed`.
- Governance plus M37R targeted tests: `18 passed`; governance audit has no
  failed checks and the final compact context is `24392/24576` bytes.
- The single permitted full suite: `354 passed in 426.31 s`.
- Frozen GT hashes are unchanged; preregistered M35/M36/M37 read-only hashes
  remain locked; 13 V access is `false`; no second scientific or full-suite
  run was performed.

Base SHA: `d91b5e76aaff8066408159e0414985e7f2000475`. Formal-run SHA: `beb5e3d8aefa1b2ae1b90263224121c38914fe96`.
The final evidence commit is supplied in the execution handoff because it
cannot self-reference its own commit.
