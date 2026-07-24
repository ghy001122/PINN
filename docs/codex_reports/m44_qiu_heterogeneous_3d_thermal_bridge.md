# M44 Qiu-scale heterogeneous 3D thermal bridge

## Decision

`M44_STOP_REAL_GEOMETRY_UPGRADE` (`failed_but_informative`).

This is a thermal-only small-signal sensible-heat component result.  It is not
a Qiu device reproduction, experimental validation, identified Joule map,
phase-change enthalpy result, inverse result, or PINN result.

## Execution

- Preregistration commit: `1b87c67387affddae85ac73a4de51abe42883b50`
- Runtime branch / HEAD: `research/m44-qiu-heterogeneous-3d-thermal-bridge` / `1b87c67387affddae85ac73a4de51abe42883b50`
- Unique registered forwards: `31` / `31`
- CPU / wall time: `4550.203125` / `4595.649036700022` s
- Maximum active-cell count: `56400`
- Source envelope: `0.03357903168816547` (M43-Rref normalized)
- Maximum non-voting heterogeneous departure from M43 Green: `3.2496439005408013`
- Non-voting steady source envelope: `0.010308406355108744`

## Gates

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
| `causal_positive_monotone_finite_steady` | True | True | pass |
| `cpu_time_budget` | 4550.203125 | 43200 | pass |
| `finite_nan_clip_negative_property_unit_source_smearing_error` | False | False | pass |
| `homogeneous_steady_recovery_error` | 0.012033076388268268 | 0.02 | pass |
| `homogeneous_transient_recovery_error` | 0.013232849723381906 | 0.02 | pass |
| `layered_1d_steady_reference_error` | 8.222252116674672e-11 | 0.02 | pass |
| `layered_1d_transient_reference_error` | 0.000969844493325245 | 0.02 | pass |
| `layered_reference_self_refinement_change` | 0.0003157487912563086 | 0.002 | pass |
| `missing_voting_provenance` | False | False | pass |
| `single_slab_reference_error` | 2.1798859146386463e-05 | 0.002 | pass |
| `source_geometry_integration_error` | 5.642372883946981e-16 | 1e-10 | pass |
| `source_power_integration_error` | 2.1175823681357508e-16 | 1e-10 | pass |
| `steady_normalized_power_imbalance` | 8.202921171094821e-11 | 1e-06 | pass |
| `transient_normalized_sensible_energy_imbalance` | 3.465838298983169e-11 | 0.0001 | pass |
| `unique_forward_budget` | 31 | 32 | pass |
| `vo2_mean_temperature_pair_change` | 0.06324641077402296 | 0.02 | fail |
| `vo2_tmax_pair_change` | 0.01358814542866259 | 0.05 | pass |
| `xz_bias_domain_pair_absolute_change` | 8.668702125236294e-06 | 0.02 | pass |
| `xz_bias_mesh_pair_absolute_change` | 0.0024643939909769486 | 0.02 | pass |
| `zth_domain_pair_change` | 2.0478190828374415e-07 | 0.02 | pass |
| `zth_mesh_pair_change` | 0.06324641077402296 | 0.02 | fail |
| `zth_time_pair_change` | 0.0544910227619362 | 0.02 | fail |

## Evidence boundary

M42's source/local-resistance mismatch remains `1.330233207545514`.
Latent heat remains `outside_validated_scope_unresolved`.  A
numerically passing M44 result cannot identify a unique Qiu thermal kernel;
source-location and geometry provenance remain explicit nuisance boundaries.

## Post-run independent audit

The formal receipt contains `31/31` unique canonical case hashes, one formal
runner invocation, zero prohibited runs, and exact pre-run identity matches for
all seven M43 attested artifacts. Protected historical and frozen evidence
retained both SHA-256 and mtime identity across the run.

Three mandatory gates failed without threshold modification:

| Failed gate | Value | Gate | Dominant registered location |
| --- | ---: | ---: | --- |
| VO2-mean / Zth mesh change | 0.0632464 | 0.02 | `S_contact`, 5.22 us |
| VO2-mean combined change | 0.0632464 | 0.02 | same mesh pair |
| Zth time-step change | 0.0544910 | 0.02 | `S_contact`, 12.857 ns |

Independent recomputation from the 31-row case CSV reproduces these maxima.
All three source families show the same qualitative failure pattern. Domain
change is only `2.04782e-7`, so extending the far field would not address the
failed gates. Homogeneous and layered references, source geometry/power,
steady power, transient sensible energy, local Tmax, provenance, and x-z bias
convergence pass their locked gates.

The registered source-location envelope is only `0.0335790` of M43 `Rref`, but
the mesh and time differences are respectively about `1.88` and `1.62` times
larger. The machine label `source_location_robust` is therefore a threshold-only
classification and is non-voting after mandatory convergence failure. The
non-voting heterogeneous-to-M43 departure reaches `3.24964`; it changes both
the physical stack and observation operator and cannot be attributed to one
material or mechanism. The matched x-z comparator exceeds the 10% claim
boundary for every source from `1.285714e-8` through `5.22e-6` s. Its mesh and
domain changes are stable on the locked time grid, but M44 has no fine-time x-z
case and does not independently establish its time-step convergence.

## Execution incident and final disposition

The first CLI launch stopped before receipt creation and before any thermal
forward because direct script execution did not place the repository root on
`sys.path`. The import path was repaired, a dedicated regression test was
added, and the pre-receipt check passed `37/37`. This engineering incident has
no scientific vote and is retained here rather than hidden. The subsequent
receipt-bearing run is the sole formal scientific run.

Per the preregistered kill rule, there is no M44 repair round. The terminal
decision is `M44_STOP_REAL_GEOMETRY_UPGRADE`; M45 reduction fitting is not
authorized. The project returns to its frozen one-dimensional,
calibration-gated `gamma_sub` submission line. M42's `1.330233` resistance
localization mismatch and unresolved latent heat remain unchanged.

## Post-run workspace recovery and final validation

After the sole formal run completed but before the result commit, an external
workspace reset moved the local M44 branch pointer back to the M43 result and
then switched the active worktree to `main`. The preregistration commit was
recovered from the reflog. The already generated code, machine tables, report,
and figure were recovered from Git objects; no scientific forward was rerun.
The figure raw SHA-256 matches the formal summary exactly. The three CSV
artifact identities match their formal SHA-256 values after the repository's
declared CRLF checkout normalization. Scientific metrics and gates were not
changed during recovery.

Final validation then passed `45/45` targeted tests and the sole complete CPU
suite passed `540/540` tests in 373.05 s. Governance completed with no failed
check (`pass_with_manual_review` for client rule loading and portable mtime
review), 299 JSON and 94 YAML files parsed strictly, and `git diff --check`
passed. The machine record is
`outputs/tables/m44_final_validation.json`; the complete test log is
`outputs/logs/m44_full_pytest.txt`.
