---
task_name: Q2_PHASE1_VERTICAL_SHAPE_SCALE_SEMANTICS_V8
base_sha: 61da2c41b9895ed3d0d7380907d0a8eecbedded6
preregistration_sha: a32375b74772da8192d390f4233ed0b15e23ae80
repair_yaml_sha256: e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b
implementation_sha: dc06a52fa990d6cd4af2f1dc84537de5e52bef0e
formal_v6_config_sha256: 0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1
v7_repair_config_sha256: 5ab66fb41b9af6fd605c351a86fa5928712528fcad8c9bc26cc55d18a0a92a18
source_contract_sha256: 857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252
formal_inventory_sha256: a617284bd8890adcab105851095801b6067307e5c85acfeb9b8a84c8467be045
evidence_type: nonvoting_preformal_vertical_shape_scale_readiness
claim_status: failed_but_informative
vertical_status: NO_GO_VERTICAL_REFERENCE
formal_execution_count: 0
formal_case_results_generated: 0
formal_campaign_executed: false
frozen_gt_modified: false
disposition: stop_current_k_state_route_before_normalization_k_state_runtime_and_formal_work
---

# Phase 1 v8 vertical shape--scale semantics screen

## Outcome

The final bounded v8 vertical repair stopped with
`NO_GO_VERTICAL_REFERENCE`. Both preregistered depth pairs passed every mesh,
finite-value, passivity, and response-identity foundation check. Both pairs
also passed the raw depth comparison on the inherited grid. They failed only
the separately gated, unnormalized depth-frequency comparison on the
formal-window pullback grid:

- 51.2/102.4 micrometres: bare `0.41181089527487524`, contact-covered
  `0.4117791211281936`;
- 102.4/204.8 micrometres: bare `0.41180466112723907`, contact-covered
  `0.41178877142256903`.

The unchanged limit is `0.05`. The primary pair therefore triggered the one
allowed fallback, and the fallback failed the same required metric. No
production depth was selected. The one-time device-effective global
conductance/capacity normalization was consequently not computed or applied,
and `production_normalization` remains `null`.

This result is `failed_but_informative` readiness evidence, not a formal Phase
1 result. It closes the preregistered v8 vertical route before K-state fitting,
runtime readiness, formal-runner work, or any formal case.

## Authority and execution boundary

- Starting `main`: `61da2c41b9895ed3d0d7380907d0a8eecbedded6`.
- Pushed v8 preregistration:
  `a32375b74772da8192d390f4233ed0b15e23ae80`.
- Locked v8 YAML SHA-256:
  `e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b`.
- Screening implementation and origin branch head:
  `dc06a52fa990d6cd4af2f1dc84537de5e52bef0e`.
- The formal-v6 config, v7 raw-builder protocol, Qiu source-only contract, and
  96-item inventory matched the hashes in the front matter. The v8 runner used
  the hash-locked v7 nonuniform-grid builders; it did not synthesize missing
  grid keys or modify v8.
- All evidence rows are `voting=false` and `formal_case=false`.
  `formal_execution_count=0`, `formal_case_results_generated=0`,
  `formal_campaign_executed=false`, and `formal_case_ids_used=[]`.

Exactly eight unique raw numerical builds were made, each builder invoked
once:

1. Ti/Au overlay coarse and fine;
2. 51.2 micrometre Al2O3 substrate coarse and fine;
3. 102.4 micrometre Al2O3 substrate coarse and fine;
4. 204.8 micrometre Al2O3 substrate coarse and fine.

The substrate branches were reused by both regions and the overlay branches
were reused across depths. The raw-build registry passed with no missing,
duplicate, or spec-hash-conflicting build.

## Raw response gates

The table reports step NRMSE `S`, non-voting impulse NRMSE diagnostic `I`, and
frequency log-magnitude RMSE `F`. Mesh gates are `S,F <= 0.01`; depth gates are
`S,F <= 0.05`. `mesh_D` and `mesh_2D` are shown as `S/F`; `depth` is shown as
`S/I/F`. Inherited and pullback families were evaluated separately; no
cross-family concatenation or weighted dilution was used.

| Pair | Region | Grid family | mesh_D S/F | mesh_2D S/F | depth S/I/F | Depth gate |
| --- | --- | --- | --- | --- | --- | --- |
| 51.2/102.4 um | bare | inherited | `2.626822835085769e-06 / 0.001437479394018423` | `2.6545170820804796e-06 / 0.0014762528501781759` | `9.390590710653108e-09 / 4.290209774319183e-06 / 0.03094277601750607` | pass |
| 51.2/102.4 um | contact | inherited | `1.4672319805860798e-06 / 0.0011567675291319628` | `1.4841552686325412e-06 / 0.0011994654343954092` | `5.774354090691092e-09 / 1.5280813561469847e-06 / 0.03094296211133424` | pass |
| 51.2/102.4 um | bare | pullback | `8.999145607985889e-08 / 0.0009422608436620944` | `9.09907113264572e-08 / 0.0010205643609204024` | `2.830489972151566e-06 / 3.9139827239116684e-05 / 0.41181089527487524` | fail |
| 51.2/102.4 um | contact | pullback | `5.53540837517464e-08 / 0.0009267951909993257` | `5.596876980823399e-08 / 0.0010059172969872341` | `1.74104631101719e-06 / 3.9139827239116684e-05 / 0.4117791211281936` | fail |
| 102.4/204.8 um | bare | inherited | `2.6545170820804796e-06 / 0.0014762528501781759` | `2.6781879339533582e-06 / 0.001467186847601347` | `8.02745667291131e-09 / 3.667230845466729e-06 / 0.00702120333321564` | pass |
| 102.4/204.8 um | contact | inherited | `1.4841552686325412e-06 / 0.0011994654343954092` | `1.4986218901785121e-06 / 0.0011839080247746357` | `4.936151386685132e-09 / 1.3061864326626896e-06 / 0.007011980420595861` | pass |
| 102.4/204.8 um | bare | pullback | `4.5450642442382676e-08 / 0.0009479708835632692` | `4.5885348110968683e-08 / 0.0010257147156588367` | `1.4151890516813412e-06 / 3.906870365100807e-05 / 0.41180466112723907` | fail |
| 102.4/204.8 um | contact | pullback | `2.7957099133607822e-08 / 0.0009401551772325707` | `2.8224500717112422e-08 / 0.0010183235523714765` | `8.704958401037159e-07 / 3.906870365100807e-05 / 0.41178877142256903` | fail |

The global worst mesh values were step NRMSE
`2.6781879339533582e-06` and frequency RMSE
`0.0014762528501781759`, both well below `0.01`. The worst impulse diagnostic
over every comparison was `0.0012664597515786042`; impulse did not vote in the
raw depth selection.

For each of the four failed pullback depth groups, 32 of 63 frequency points
had absolute log-magnitude error above `0.05`. The common effective-frequency
interval was `1136.463666385725` to `4084238.652674517 Hz`. The primary raw
interval was `1.2169982946838915` to `4373.665100261895 Hz`; the fallback raw
interval was `0.3043029862200854` to `1093.6082298142928 Hz`. The worst point
was the lowest effective frequency:

- primary bare/contact: `0.6931437394429949` / `0.6931437332171235`;
- fallback bare/contact: `0.693143738089212` / `0.6931437347975109`.

The fallback inherited grid contains a worst individual point of
`0.05132608900476754` for bare and `0.05126457391107486` for contact, while
its preregistered 63-point RMSE is `0.00702120333321564` and
`0.007011980420595861`. The locked gate is RMSE, not a pointwise maximum, so
the inherited-grid pass is not a missed failure.

## Passivity and response identities

All 32 raw passivity/identity rows passed. Across both pairs, both regions,
both grid levels, and both coordinate families, the conservative extrema were:

| Check | Worst recorded value | Required condition |
| --- | ---: | --- |
| minimum capacity | `0.002203125 J m^-2 K^-1` | positive |
| minimum physical conductance | `4.656612873077393e-10 W m^-2 K^-1` | positive |
| minimum conductance-matrix eigenvalue | `51629.31533584492 W m^-2 K^-1` | positive |
| pole closest to zero | `-2733.7922064977292 s^-1` | strictly negative |
| minimum real-admittance relative margin | `0.5229332999492283` | at least `-1e-12` |
| maximum step-initial relative error | `1.430511474609375e-15` | at most `1e-10` |
| maximum step-DC relative error | `0.0` | at most `1e-10` |
| maximum impulse-integral relative error | `1.4305376685364108e-15` | at most `1e-10` |
| maximum impulse/step-derivative relative error | `6.527304022606066e-11` | at most `1e-10` |
| maximum frequency state-space relative error | `6.0225276298743435e-12` | at most `1e-10` |

Thus the stop is not caused by mesh resolution, a non-passive state-space
model, a response-identity defect, or a nonfinite value.

## Root-cause interpretation

The following is a bounded inference from the preregistered synthetic model,
not a material calibration or a Qiu-device claim.

The engineering-prior Al2O3 diffusivity is

$$
\alpha=\frac{k}{C_v}=\frac{35}{3.00\times10^6}
=1.1666666666666666\times10^{-5}\ \mathrm{m^2\,s^{-1}}.
$$

At the lowest pullback raw frequency, the penetration lengths
$\sqrt{\alpha/(\pi f)}$ are `1.7468413900034192 mm` for the primary pair and
`3.4933761535510836 mm` for the fallback pair, approximately 34.1 times each
production depth. In this low-frequency fixed-bottom regime, the finite slab
conductance scales approximately as $1/D$. A `D` versus `2D` comparison
therefore approaches an admittance ratio of two, consistent with the observed
worst log error near $\log 2=0.6931471805599453$.

When the production depth doubled, the recorded raw-device conductance ratio
was `0.49999999996875`, the raw memory-capacity ratio was
`1.999648951403392`, and the temporary coordinate ratio changed by
`0.2500438887624953`. The pullback therefore moved the deeper pair into nearly
the same dimensionless diffusion window. This is consistent with the almost
unchanged pullback frequency RMSE near `0.4118`, even though the inherited raw
frequency RMSE improved from about `0.03094` to `0.00702`.

Within the two preregistered pairs and the fixed-bottom raw-stack model, the
evidence therefore identifies a scale-window/boundary incompatibility rather
than a coarse-grid or passivity defect. It does not justify relaxing the
`0.05` gate, re-anchoring the comparator, adding an unregistered deeper pair,
or claiming that a local Al2O3 depth was calibrated. Because raw depth did not
pass on both required grid families, the v8 rule correctly prevented global
G/C normalization from being used to rescue the depth vote.

## Stop condition and artifact boundary

The readiness directory contains exactly seven files:

- `preregistration.json` and `environment_manifest.json`;
- `vertical_candidate_summary.csv`, `vertical_pointwise.csv`, and
  `vertical_passivity_identity.csv`;
- one-row `k_state_multistart.csv` and `k_state_selection.csv` placeholders,
  both marked `BLOCKED_BY_NO_GO_VERTICAL_REFERENCE`.

There is no production kernel, selected K, K-state optimizer result, runtime
preflight, formal-runner readiness result, or successful formal-v8 config.
Specifically, `runtime_preflight.json`, `formal_runner_readiness.json`, and
`configs/geophase_phase1_2p5d_reference_v8.yaml` do not exist. No formal
summary, convergence table, K-state formal selection, formal figure, or formal
case artifact was generated. The 96 formal inventory items remain
`planned_not_executed`.

Per the preregistered final-repair stop rule, the current K-state route stops
here. PINN training, Phase 2 data generation, inverse work, nonzero
dual-device coupling, NbO2 work, M44 repair, and frozen-GT modification remain
outside this task and were not performed.

## Claim boundary

- `supported`: the v8 protocol was preregistered and pushed before screening;
  eight raw builds and their non-voting evidence exist; mesh and
  passivity/identity foundations passed; the two required pullback depth gates
  failed; formal execution count remained zero.
- `failed_but_informative`: the final bounded v8 vertical-reference route did
  not produce a selectable production depth and cannot advance to K-state or
  Checkpoint B authorization.
- `forbidden`: Phase 1 passed; a converged 2.5D reference judge exists; a
  device-effective production kernel or K-state order was selected; runtime
  feasibility was established; Qiu was reproduced or calibrated; intrinsic
  local material properties were recovered; scaled-depth invariance,
  experimental validation, full FEM/3D equivalence, or any positive PINN or
  inverse result exists.

All evidence is literature-guided synthetic numerical digital-twin evidence,
not measurement evidence.

## Validation and reproduction

Focused v8 preregistration, explicit-grid, runner, and evidence tests passed:
`32 passed in 2.87 s`. The complete local test set mirrored by fast validation,
including v6/v7 compatibility and claim/evidence contracts, passed
`117 passed in 27.15 s`. No full regression was run for this vertical no-go
closeout, as required by its stop rule.

The governance audit passed the authority chain, context budget
(`23813/24576` bytes), phase/claim routing, frozen hashes, and all other checks.
Its local overall status remained failed only because the pre-existing ignored
`%SystemDrive%` pollution directory is physically present in this workstation
checkout. It was neither modified nor treated as scientific evidence; a clean
CI checkout does not contain it.

From the repository root, the bounded screen and focused evidence checks are
reproduced with:

```powershell
git show -s --format="%H %s" a32375b74772da8192d390f4233ed0b15e23ae80
git show -s --format="%H %s" dc06a52fa990d6cd4af2f1dc84537de5e52bef0e
Get-FileHash configs/geophase_phase1_vertical_shape_scale_v8.yaml -Algorithm SHA256

.\.venv\Scripts\python.exe scripts\run_geophase_phase1_vertical_shape_scale_v8.py `
  --preregistration-sha a32375b74772da8192d390f4233ed0b15e23ae80 `
  --repair-yaml-sha256 e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b

.\.venv\Scripts\python.exe -m pytest -q `
  tests\test_geophase_phase1_vertical_shape_scale_v8_preregistration.py `
  tests\test_geophase_phase1_vertical_shape_scale_v8.py `
  tests\test_geophase_phase1_vertical_shape_scale_v8_runner.py `
  tests\test_geophase_phase1_vertical_shape_scale_v8_evidence.py

.\.venv\Scripts\python.exe scripts\validate_tracked_json.py
.\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
git diff --check
```

The screen command is a non-formal reproduction only. It cannot run a formal
case or increment `formal_execution_count`.
