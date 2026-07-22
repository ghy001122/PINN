# M43 Finite-Width Thermal-Spreading Closure

## Outcome

M43 selected **M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY** with evidence status
`qualified_supported`. It executed
15 unique
thermal-only PDE forwards in
9.404 s wall time and
2.500 s process CPU time. The
largest grid contained 94461
cells. Failed or unassessed mandatory gates: ['none'].

## Evidence boundary

This is solver-generated manufactured component evidence for a homogeneous,
isotropic, constant-property half-space and a 500 nm by 100 nm isoflux source.
It is not Qiu-device reproduction, calibrated multilayer physics, external or
experimental validation, phase-change enthalpy, a reduced thermal-parameter
fit, inverse identification, or PINN evidence. No device forward, fit, inverse,
PINN training, GPU calculation, or sealed 13 V access occurred.

The M42 source/local resistance error remains 1.330233207545514 and latent
heat remains unresolved and unassessed. M43 cannot repair either blocker.

## Independent reference and finite-volume contract

The steady reference independently implements Yovanovich--Muzychka--Culham
Eq. (21), DOI `10.2514/2.6467`. The transient reference independently
integrates the source-area Green step kernel documented by Yovanovich (1997),
DOI `10.2514/6.1997-2458`. Neither reference imports the FVM implementation.

The comparator uses quarter symmetry, an exactly aligned explicit top-face
Neumann source, fixed far-field temperature, zero-flux symmetry/top-exterior
faces, and a source-face temperature reconstructed from the first cell center.
Domain extension is append-only. The sensible-energy ledger is discrete
bookkeeping and is not a device heat-capacity measurement.

## Preregistered mandatory gates

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
| `eq21_rho1_relative_error` | 0.0 | 0.0001 | pass |
| `eq21_rho5_relative_error` | 1.35987282040465e-16 | 0.0001 | pass |
| `green_early_limit_error` | 0.0001513837071895556 | 0.01 | pass |
| `green_long_limit_error` | 0.006302514612311379 | 0.01 | pass |
| `green_quadrature_refinement_change` | 4.0592203689078793e-14 | 0.0001 | pass |
| `steady_rho1_reference_error` | 0.007572031905103764 | 0.02 | pass |
| `steady_rho5_reference_error` | 0.009368911540438576 | 0.02 | pass |
| `rho5_mesh_pair_change` | 0.010276157287473837 | 0.02 | pass |
| `rho5_domain_pair_change` | 0.0008161811205175364 | 0.02 | pass |
| `steady_normalized_power_imbalance` | 9.175860071763964e-11 | 1e-06 | pass |
| `transient_3d_green_normalized_max_error` | 0.010950663729804022 | 0.02 | pass |
| `transient_time_pair_change` | 0.0002723829012095207 | 0.02 | pass |
| `transient_normalized_sensible_energy_imbalance` | 3.87655793525907e-09 | 0.0001 | pass |
| `finite_width_bias_mesh_pair_absolute_change` | 0.013686510785704042 | 0.02 | pass |
| `finite_width_bias_domain_pair_absolute_change` | 1.5252665996889903e-07 | 0.02 | pass |
| `source_area_integral_error` | 1.262177448353619e-16 | 1e-10 | pass |
| `source_power_integral_error` | 2.220446049250313e-16 | 1e-10 | pass |
| `near_zero_outflow_normalized_change` | 2.0631021373520696e-05 | 0.02 | pass |
| `finite_nan_clip_source_smearing_unit_error` | False | False | pass |
| `wall_clock_budget` | 9.404259799979627 | 28800.0 | pass |
| `cpu_time_budget` | 2.5 | 28800.0 | pass |

## Physical interpretation of the converged comparator

The converged 3D steady value at rho=5 is Theta=0.412033, within 0.937% of
the independent Eq. (21) value 0.408208. The matched x-z comparator does not
provide a quantitatively interchangeable model: its matched-base absolute
finite-width bias rises from 6.93% at the earliest locked time to 119.30% at
the latest time.
That bias itself is numerically resolved (mesh-pair curve change 1.37 percentage
points and domain-pair change 1.53e-7), so it is a physical dimensional-reduction
boundary rather than an unresolved grid artifact. This supports comparing
causal reduced thermal kernels against the locked 3D component response; it
does not authorize using the x-z model as a Qiu device surrogate.

The formal figure was subsequently rebuilt from the locked CSV artifacts only
to restore physical x coordinates and align the displayed bias with the formal
matched-base contract. This visualization-only amendment executed zero PDE
forwards and changed no case table, reference table, gate, or terminal decision;
its old/new hashes are recorded in
`outputs/tables/m43_figure_postprocessing_manifest.json`.

## Claim and next-step disposition

`M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY` authorizes only a bounded M44
comparison of 1-RC, 2-RC, and causal thermal kernels, including validity and
abstention boundaries. `M43_STOP_C_FREEZE_1D` permanently closes quantitative
Qiu 2D/2.5D/3D rescue and routes directly to the frozen one-dimensional,
calibration-gated rank-1 `gamma_sub` submission package. No result authorizes
Qiu coupled dynamics, pure x-z quantitative use, `gamma_sub/gamma_eff`, total
phase enthalpy, inverse identification, or PINN training.

## Version and integrity

The single full-suite invocation collected 499 tests and completed with 497
passes and two precommit evidence-identity failures in M35/M36 after 471.03 s.
Both failures were caused by the then-uncommitted M43 `.gitignore` revision;
after the result commit made that revision addressable in Git history, the two
identity checks plus all four M43 result-evidence checks passed (`6 passed in
16.78 s`). The full suite was not rerun because the execution contract permits
only one final full-suite invocation. The strict JSON audit parsed 206/206
tracked/final-validation files, and the project-governance audit returned no
failed checks (`pass_with_manual_review`). Raw logs and the machine record are
stored in `outputs/logs/m43_full_pytest.txt`,
`outputs/logs/m43_postcommit_identity_tests.txt`, and
`outputs/tables/m43_final_validation.json`.

- Base SHA: `0dc103f391d1206fe02c100987ecab68ed1d741d`
- Preregistration SHA: `a1f229a25b4392422af3ced7e354ada0b5605365`
- Runtime HEAD before the self-referential result commit:
  `a1f229a25b4392422af3ced7e354ada0b5605365`
- Result SHA: reported in the final Git handoff because a commit cannot contain
  its own SHA without changing it.
- Protected evidence SHA-256 and mtimes unchanged:
  `True` /
  `True`.
