# M37 continuous-event cross-regime observability results

## Outcome

- Status: `stopped_at_nominal_solver_event_gate`.
- Claim status: `failed_but_informative`.
- M38 authorized: `false`.
- Forward evaluations: `{'DOP853': 4, 'Radau': 4, 'total': 8}`.
- Solver wall time: `236.112 s`.
- No fit, fit lock, PINN training, or 13 V numeric access occurred.

M37 is a local continuous-equation observability preflight at the source
parameter anchor. It is not source-compatible finite-step reproduction,
parameter recovery, experimental validation, or a trained-PINN result.

The execution is `failed_but_informative`, but the proposed observability
hypothesis is **unassessed**, not scientifically rejected. The stop was caused
by an observation-window mismatch in the preregistered nominal count check,
not by a DOP853/Radau disagreement or a physical trajectory failure.

## M36 superseding semantic audit

M36's historical JSON/CSV and failed vote remain unchanged. The new audit
replaces the overly broad wording `true_numerical_nonconvergence` for
11/15/17 V with finite-step accuracy-gate failure wording that records the
observed error-versus-step trend. This is not a gate relaxation or a pass.

The locked wording is:

- 11 V: `finite_step_accuracy_gate_failed_with_observed_overall_but_nonmonotone_fine_scale_convergence_trend`;
- 15 V: `finite_step_accuracy_gate_failed_after_event_sequence_stabilization_with_observed_convergence_trend`;
- 17 V: `finite_step_accuracy_gate_failed_with_observed_convergence_trend`.

Their log--log slopes remain `0.91869`, `1.07495`, and `0.91725`. M36's
historical `primary_gate_passed=false` values and all source files remain
unchanged.

## Nominal gate diagnosis

| Voltage | DOP853 full-horizon reversals | Radau full-horizon reversals | M36 stored count | Finite/activity | DOP853--Radau sequence |
| ---: | ---: | ---: | ---: | --- | --- |
| 9 V | 0 | 0 | 0 | pass | exact |
| 11 V | 216 | 216 | 196 | pass | exact |
| 15 V | 381 | 381 | 344 | pass | exact |
| 17 V | 4 | 4 | 0 | pass | exact |

M36's stored `reference_reversal_event_count` is calculated after its fixed
10% transient window. M37 compared that number against its own full-horizon
reversal signature. The numerical solvers therefore reproduced one another
exactly, while the comparison mixed two different observation windows. This
is an `implementation_contract_invalid` boundary. Treating it as evidence that
the continuous-event model itself is unstable or non-convergent would be
incorrect.

## Preregistered observability geometry

| Group | Rank | Singular values | Condition number | Step Jacobian change | Left-subspace angle |
| --- | ---: | --- | ---: | ---: | ---: |
| static_only | not reached | not reached | not reached | not reached | not reached |
| oscillatory_only | not reached | not reached | not reached | not reached | not reached |
| joint | not reached | not reached | not reached | not reached | not reached |

No parameter perturbation was executed, so all ranks, singular values,
condition numbers, Jacobian step changes, retained-subspace angles, and the
static/oscillatory direction angle are `not_reached`. The analytic quotient
policy was registered but could not be applied without a raw Jacobian. No
quotient simulation was run and no Fisher-rank increase is claimed.

## Claim boundary and next action

M38 is not authorized. This round cannot vote for stable rank, information
complementarity, or a public inverse. Per the preregistered stop rule, no
window correction, extra scale, threshold change, parameter search, or solver
rerun is performed in M37. The active delivery route returns to
`Q2_MANUSCRIPT_EVIDENCE_COMPRESSION`.

If this hypothesis is revisited later, the only scientifically legitimate
repair is a new bounded preregistration that applies the same explicitly named
window to both the M36 nominal reference count and every M37 perturbation. It
must preserve all current numerical thresholds and cannot reuse this invalid
run as a positive vote.

Forbidden claims remain: unique parameter recovery, independent external
validation, gamma_sub/S_e equivalence, 13 V evaluation, trained-PINN
success, and novelty for SVD/Fisher/event sensitivity or reversible
reparameterization.

## Q2 SCI contribution and remaining gap

M37 improves reviewer defense in two ways: it corrects M36's overly broad
failure wording, and it proves that DOP853/Radau nominal continuous-event
semantics remain identical at all four open voltages. It also prevents an
invalid count-window comparison from being promoted into an identifiability
claim.

It adds no positive observability, fitting, quotient, public-prediction, or
PINN evidence. The paper therefore still lacks public-data parameter
equivalence, cross-regime rank complementarity, a valid fit lock, 13 V
cross-voltage evaluation, trained full-PINN forward fidelity, and PINN--solver
sensitivity fidelity. The only safe positive inverse mainline remains the
calibration-gated synthetic rank-1 `gamma_sub` result.

## Validation

- Focused M37 tests: `10 passed in 1.79 s`.
- The single permitted full-suite run: `338 passed, 2 failed in 152.42 s`.
- Both full-suite failures were the same governance context-budget excess
  caused by the first verbose status update; no physics, solver, schema, hash,
  or M37 behavioral test failed.
- After compacting the authoritative status chain, the targeted governance
  suite passed `4/4 in 11.89 s`; the context total is `23856/24576` bytes and
  the governance audit has no failed checks.
- A second full-suite run was not performed because the execution contract
  permits exactly one. Strict JSON/CSV parsing passes, all M37 preregistration
  hashes match, Frozen GT has no diff, and 13 V remains unaccessed.

Base SHA: `ec2017a5c1d17720ab207473557948b48eba5f02`. The final result SHA is supplied
in the execution handoff because it cannot self-reference its own commit.
