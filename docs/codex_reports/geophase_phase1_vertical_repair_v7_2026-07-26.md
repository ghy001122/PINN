---
task_name: Q2_PHASE1_CHECKPOINT_B_READINESS_V7
initial_preregistration_commit: 68d0577f42f7932d2a0b0ccfb5b020de1983ab9e
repair_protocol_commit: d6a386a77b79f186a75fbe12c06be0666f46d067
repair_yaml_sha256: 5ab66fb41b9af6fd605c351a86fa5928712528fcad8c9bc26cc55d18a0a92a18
formal_v6_config_sha256: 0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1
source_contract_sha256: 857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252
evidence_type: nonvoting_preformal_bounded_vertical_reference_repair
claim_status: failed_but_informative
formal_execution_count: 0
formal_case_results_generated: 0
formal_campaign_executed: false
vertical_status: NO_GO_VERTICAL_REFERENCE
k_state_status: BLOCKED_BY_VERTICAL_REFERENCE
disposition: stop_before_v7_formal_freeze_performance_and_formal_runner
---

# Phase 1 v7 bounded vertical-reference repair

## Outcome

The bounded repair did not make Checkpoint B ready. The preregistered maximum
pair, 102.4/204.8 micrometres, failed the unchanged frequency log-magnitude
limit of 0.05 in both regions. The electrode-covered value was
`0.4117887715`; the bare-region value was `0.4118046611`. Consequently no
production depth was selected, K-state fitting was not run, and the work
stopped before performance work, formal-runner implementation, or any formal
case.

This is `failed_but_informative`, not a Phase 1 scientific gate result. All
screening rows are non-voting, `formal_execution_count=0`, and all 96 formal
cases remain `planned_not_executed`.

## Reproducibility boundary

- The old contact-covered 400/800 nm warning was reproduced as
  `0.12312709438793715`, a relative difference of `3.03e-13` from the locked
  value `0.12312709438789984` and well inside the `1e-10` reproduction gate.
- The repair protocol was committed and pushed before screening.
  `68d0577...` carries the locked preregistration subject; the pre-screen
  amendment chain ends at `d6a386a...`, which locks the complete metric and
  identity definitions used here.
- Exactly 26 raw numerical build IDs were used: 20 reusable substrate builds,
  two reusable Ti/Au overlay builds, and four v6 reproduction builds. Every
  builder was invoked once; region and response evaluations did not create
  extra raw builds.
- The Qiu source-only contract remained byte-identical. The 0.05 gates, 96
  formal items, formal v6 config, frozen GT, materials, and source-author
  global G/C targets were not changed.
- The five machine-readable outputs were written before this report. No Phase
  1 figure or formal result file was generated.

## Root cause

The unscaled Al2O3 branch behaves correctly. At the maximum pair its raw
102.4/204.8 micrometre frequency difference is `0.0070212033`, consistent with
the analytic finite-versus-semi-infinite diagnostic `0.0069043284`; both are
below 0.05. Mesh errors are also below 0.01, and all passivity and response
identity checks pass.

The diagnostic evidence strongly attributes the failure to the point where
each candidate pair is independently anchored to the
same source-author global conductance and capacity. At the maximum pair the
locked scales are approximately `G_scale=12053.94` and `C_scale=3.22760`, so
their ratio increases the effective thermal diffusivity by `3734.65`. The raw
Al2O3 diffusivity is `1.16667e-5 m2/s`; after the two distinct global scales,
the corresponding 1 kHz penetration length is about `3.724 mm`, much larger
than the 204.8 micrometre comparator.

More importantly, this does not disappear by merely adding deeper candidates
under the same pair-wise re-anchoring rule. For a fixed-bottom homogeneous
branch, raw DC conductance scales approximately as `1/D` and capacity as `D`.
Re-anchoring every production depth to the same global G and C therefore makes
`G_scale/C_scale` scale as `D^2`, and the effective penetration length scale as
`D`. The dimensionless depth-to-penetration ratio stays roughly constant. The
observed full-kernel depth-frequency error accordingly remains near `0.41`
across the entire depth ladder even though the raw substrate error falls from
about `0.505` to `0.007`.

Thus the no-go is not evidence that the 0.05 gate is too strict, nor evidence
that Al2O3 requires only a still deeper finite truncation. It exposes a
semantic incompatibility between per-candidate pair G/C re-anchoring and using
those same re-anchored pairs to vote on depth invariance.

The H1--H5 columns are bounded diagnostic contrasts, not five independent
scientific experiments and not additive error decompositions. H1 records the
registered v6 independently re-anchored reproduction, H2 the shared-scale bare
kernel, H3 the like-depth mesh error, H4 the raw substrate-only depth error,
and H5 the shared-substrate-plus-overlay contact kernel. The pointwise file
contains the v6 complex admittances and the H4 raw-substrate responses so these
contrasts can be independently reaggregated.

## Stop and claim boundary

Per the preregistered maximum-pair stop rule:

- v7 formal configuration freezing is blocked;
- K=1/2/3/8 reduction is blocked rather than failed;
- runtime preflight, performance optimization, campaign state-machine work,
  and the 96-case formal campaign are not run;
- Phase 2, PINN training, inverse work, nonzero dual-device coupling, NbO2,
  M44 repair, and frozen-GT writes remain forbidden.

The next action requires a new user-authorized, versioned pre-formal protocol.
It should keep the Qiu source contract untouched and test a single fixed global
scale across the depth ladder, or formally separate source-author global G/C
amplitude anchors from the local dynamic-shape truncation vote. Adding deeper
candidates while retaining pair-specific re-anchoring is not recommended,
because the bounded evidence predicts the same dimensionless failure.

## Validation

- Focused v7/authority/workflow tests: `35 passed`.
- Pre-commit broad regression: `492 passed`, `2 deselected`, and two historical
  `.gitignore` identity checks failed only because the new allow-list bytes
  were not yet committed. After the evidence commit, those two checks plus the
  v7 focused set passed (`17 passed`). The full suite was not repeated.
- Project governance reports one independent local hygiene failure:
  ignored `%SystemDrive%/SogouInput` workspace pollution. It was not deleted
  under this scientific task. All other governance checks pass, tracked JSON
  parses, and frozen GT hashes remain unchanged.
- The source-only contract, formal v6 config, and 96-case inventory hashes are
  unchanged; no formal summary, convergence table, K selection, or figure was
  created.
