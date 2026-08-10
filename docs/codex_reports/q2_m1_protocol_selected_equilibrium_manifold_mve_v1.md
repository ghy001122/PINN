# Q2 M1 protocol-selected equilibrium-manifold MVE v1

## Conclusion

Disposition: `GO_PROTOCOL_SELECTED_EQUILIBRIUM_MANIFOLD`.

All outputs are `literature-guided synthetic numerical digital-twin evidence`. Four explicit device-terminal voltage protocols were executed; no neural model, hidden root identifier, root averaging, pseudo-arclength continuation, source-RC model, or time-domain attractor simulation was used.

## Frozen PR #41

PR #41 head `ee945aff570e53c952402b09dbbe180539b3362c` retained `NO_GO_SINGLE_VALUED_IMT_FORWARD_MAP` unchanged and was squash-merged as `53ef26de742f8c1ecab1c3aa6b579249d9729c27` before this branch.

## Protocol execution

| protocol | expected points | valid points | valid fraction | endpoint | completed |
|---|---:|---:|---:|---:|---:|
| G0_heating | 33 | 33 | 1.000000 | True | True |
| G0_cooling | 33 | 33 | 1.000000 | True | True |
| G1_heating | 33 | 33 | 1.000000 | True | True |
| G1_cooling | 33 | 33 | 1.000000 | True | True |


Every non-initial coarse point records the immediately preceding accepted equilibrium as its actual initialization provenance. Continuation reachability is quasi-static numerical protocol evidence, not a time-domain dynamics claim.

## Switching events

| protocol | lower V | upper V | estimate V | mean-state jump | resolved |
|---|---:|---:|---:|---:|---:|
| G0_heating | -- | -- | -- | 0.000000 | False |
| G0_cooling | 0.840625 | 0.843750 | 0.842187 | 0.853597 | True |
| G1_heating | -- | -- | -- | 0.000000 | False |
| G1_cooling | 1.062500 | 1.065625 | 1.064062 | 0.273568 | True |

Total event-refinement solves, including primary confirmation and half-step bisection: `12` / `24`.

## Local physical stability

The full 250 x 250 Jacobian is the derivative of the semi-discrete thermal dynamics after quasi-static electrical elimination, not the derivative of `P_alpha`. The Qiu source-contract device capacity `4.96e-11` J/K is divided uniformly over 250 cells only as a positive device-level time scale.

- evaluated states: `20` / `24`
- stable: `20`
- unstable: `0`
- indeterminate: `0`
- cumulative spectrum evaluations: `24` / `24` (`16` initial plus `8` fixed interior probes)

Only actually evaluated states classified `stable` enter the manuscript-stable dataset; unassessed protocol points remain numerical reachable equilibria only.

## Half-step reproducibility

| protocol | switch difference V | worst off-event T | worst off-event I | class reversal | pass |
|---|---:|---:|---:|---:|---:|
| G0_heating | -- | -- | -- | -- | N/A |
| G0_cooling | 0 | 1.06644e-08 | 1.09643e-09 | 0 | True |
| G1_heating | -- | -- | -- | -- | N/A |
| G1_cooling | 0 | 1.253e-09 | 3.92901e-10 | 0 | True |


## Context gates

| context | conservative switch separation V | stable sampled bistable span V | stable same-V pairs | max current separation | max T-rise separation | qualified |
|---|---:|---:|---:|---:|---:|---:|
| G0 | -- | 0.8 | 4 | 0.994376 | 0.994381 | True |
| G1 | -- | 0.8 | 4 | 0.994342 | 0.994355 | True |

## Surrogate eligibility without training

- eligibility executed: `True`
- eligible for a separately preregistered next task: `True`
- stable manuscript point count: `20`
- unknown-protocol practical ambiguity count: `66`
- POD diagnostic: `{"cumulative_energy_at_rank": 0.9992489343333766, "energy_target": 0.999, "executed": true, "fit_point_count": 20, "fit_point_ids": ["G0_heating_coarse_000", "G0_heating_coarse_008", "G0_heating_coarse_024", "G0_heating_coarse_032", "G0_cooling_coarse_000", "G0_cooling_coarse_008", "G0_cooling_coarse_024", "G0_cooling_coarse_032", "G0_cooling_event_refine_02", "G0_cooling_event_reachability_confirmation", "G1_heating_coarse_000", "G1_heating_coarse_008", "G1_heating_coarse_024", "G1_heating_coarse_032", "G1_cooling_coarse_000", "G1_cooling_coarse_008", "G1_cooling_coarse_024", "G1_cooling_coarse_032", "G1_cooling_event_refine_03", "G1_cooling_event_reachability_confirmation"], "no_holdout_diagnostic": true, "population": "actual_spectrum_stable_manuscript_eligible_points", "rank": 2, "rank_cap": 8, "rank_cap_pass": true, "singular_values": [103.5219792619969, 21.70409656888347, 2.6209498138971132, 1.2162318427649754, 0.23332096656670007, 0.07355195719647394, 0.024915051721126794, 0.007887017906934043, 0.003112983282513943, 0.00042239674031229846, 0.00035665182354962827, 6.188554905787303e-05, 2.9549459025213047e-05, 9.844170812619077e-07, 1.8068531762975364e-08, 4.726936506046689e-13, 4.25548292272276e-13, 3.9778240387081305e-13, 3.720856592590685e-13, 1.461233157747559e-14], "split_status": "eligibility_only_stable_point_fit_no_future_holdout_preregistered", "transform": "log1p_temperature_rise_in_1K_units"}`
- neural training executed: `False`

This task freezes no future train/validation/test split; the POD number is an eligibility-only stable-point diagnostic and cannot vote on generalization.

## Claim boundary

Allowed sentence: Although the fixed-parameter steady relation was multi-valued, explicit monotone voltage protocols selected reproducible, locally stable and continuously reachable heating/cooling equilibrium components within the frozen synthetic M1 model.

The most favorable result is limited to the frozen ideal device-terminal voltage-clamp protocol. Full hysteresis, minor loops, Qiu source/12-kOhm/RC reproduction, dynamic-attractor behavior, experimental validation, formal PINN superiority, inverse recovery, and material transfer remain forbidden.

## Artifacts and validation

- Tables: `outputs/tables/q2_m1_protocol_selected_equilibrium_manifold_mve_v1/Q2-M1-PROTOCOL-SELECTED-EQUILIBRIUM-MANIFOLD-MVE-20260810-V1`
- Fields: `data/processed/q2_m1_protocol_selected_equilibrium_manifold_mve_v1/Q2-M1-PROTOCOL-SELECTED-EQUILIBRIUM-MANIFOLD-MVE-20260810-V1`
- Figures: `outputs/figures/q2_m1_protocol_selected_equilibrium_manifold_mve_v1/Q2-M1-PROTOCOL-SELECTED-EQUILIBRIUM-MANIFOLD-MVE-20260810-V1`
- Focused validation command: `pytest -q tests/test_q2_m1_protocol_selected_equilibrium_manifold_mve_v1.py`
- Base: `53ef26de742f8c1ecab1c3aa6b579249d9729c27`
- Final commit, push, and draft PR are recorded in the final handoff because a commit cannot contain its own SHA.

## Next priority

Under fresh authorization, execute only `Q2_PROTOCOL_MANIFOLD_BRANCH_AWARE_SURROGATE_MVE_V1`: freeze a future split; compare analytic, ridge, single-head, and physically gated branch-aware latent baselines; preserve conservative projection; and require unknown-protocol set output or refusal. Do not infer a dynamic attractor or train a surrogate in this task.
