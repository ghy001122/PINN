# Current Evidence Index

This is a routing index; current status remains authoritative in `PROJECT_STATE.md`.

## Locked safe mainline

- Evidence lock: `docs/paper/gamma_sub_evidence_lock.md`.
- Claim matrix: `docs/paper/final_claim_matrix.md`.
- Safe inverse wording: calibration-gated rank-1 `gamma_sub`, synthetic and prior-qualified.

## VO2 D0, full-PINN N0, SID, CPCF, and CEBA evidence

| Block | Status | Primary evidence |
| --- | --- | --- |
| M40 Qiu conservative 2D E0 | planned/preregistering; formal result absent | `configs/m40_qiu_vo2_real_device_2d.yaml`; `data/external/qiu_2024_thermal_neuristor/manifest.json`; `docs/physics/m40_qiu_model_responsibility.md`; no positive result until `outputs/tables/m40_qiu_e0_summary.json` exists |
| D0a provenance/source semantics | `qualified_supported` sub-result | `data/external/vo2_zhang_2024/manifest.json`; `outputs/tables/vo2_d0a_source_discrepancies.csv` |
| D0a completion gate | `failed_but_informative` | `outputs/tables/vo2_d0a_source_reproduction.json`; `outputs/figures/vo2_d0a_source_semantics_v2.png` |
| M35 D-PREG public multi-voltage lock | `supported` provenance/protocol fact; not fit evidence | `outputs/tables/m35_public_multivoltage_preregistration.json`; `data/external/vo2_zhang_2024/multivoltage_prereg_manifest_v1.json`; `configs/m35_public_multivoltage_fit.yaml` |
| M35 D-FIT | `failed_but_informative`; refit/fit-lock claim `forbidden` | `outputs/tables/m35_solver_convergence.csv`; `outputs/tables/m35_public_multivoltage_fit_summary.json`; stops before Jacobian and fitting |
| M36 preregistration | `supported` protocol/threshold/hash lock; not scientific outcome evidence | `outputs/tables/m36_event_resolved_orbit_preregistration.json`; `configs/m36_event_resolved_orbit_convergence.yaml` |
| M36 independent event-resolved reference | `supported` numerical parity fact; no parameter or validation claim | `outputs/tables/m36_event_resolved_orbit_summary.json`; `outputs/tables/m36_orbit_convergence_metrics.csv`; DOP853/Radau pass at all four open voltages |
| M36 source-compatible Euler convergence | `failed_but_informative`; public refit route closed | `outputs/tables/m36_event_times.csv`; `outputs/figures/m36_error_dt_convergence.png`; `outputs/figures/m36_event_time_drift.png`; only 9 V passes all primary gates; no Jacobian, fit, or lock |
| M37/M37R observability | wording/window repair `supported`; execution `failed_but_informative`; geometry unassessed/`forbidden` | `outputs/tables/m37_cross_regime_jacobian.json`; `outputs/tables/m37r_cross_regime_jacobian.json`; nominal windows pass, then 15 V `log_C_th=-1%` changes topology before Jacobian/SVD |
| D0b-D0d | not completed / positive claims `forbidden` | D0a/M35 convergence stop rules; 13 V sealed; no fit lock |
| N0 architecture contracts | `supported` as implementation facts | `outputs/tables/full_pinn_contract_v1.json`; `src/pinnpcm/pinn/full_pinn_1d.py`; `src/pinnpcm/pinn/full_pinn_n0_cv_e.py` |
| N0 v1 trained forward | `failed_but_informative` | `outputs/tables/full_pinn_single_seed_mve_v1.json` |
| N0 teacher/FVM and exact-trace v2 | mixed implementation support; trained result `failed_but_informative` | `outputs/tables/n0_teacher_equation_compatibility_v1.json`; `outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json` |
| Historical N0-CV-E v3 | `failed_but_informative / runtime_abort_unassessed` | `outputs/tables/n0_cv_e_v3_semantic_amendment.json`; `outputs/tables/n0_cv_e_v3_summary.json` |
| N0-CV-E v3r preregistration | locked at clean remote commit | `outputs/tables/n0_cv_e_v3r_preregistration.json`; `configs/n0_cv_e_v3r_optimizer_forensics.yaml` |
| N0-CV-E v3r post-Adam and crash forensics | `failed_but_informative`; N0 stopped | `outputs/tables/n0_cv_e_v3r_forensic_resolution.json`; `outputs/tables/n0_cv_e_v3r_post_adam_score.json`; `outputs/tables/n0_cv_e_v3r_lbfgs_diagnostic_crash.json` |
| M33 mixed state--flux MVE | preflight `supported`; trained result `failed_but_informative`; M33-v1 closed | `outputs/tables/m33_mixed_flux_preregistration.json`; `outputs/tables/m33_mixed_flux_preflight.json`; `outputs/tables/m33_mixed_flux_training_history.json`; `outputs/tables/m33_mixed_flux_final_summary.json`; `outputs/tables/m33_mixed_flux_v3r_comparison.csv`; `outputs/figures/m33_mixed_flux_forward_fidelity.png` |
| M34 optimizer/gradient/ledger audit | implementation facts `supported`; corrected-run authorization `failed_but_informative`; no training executed | `outputs/tables/m34_contract_audit_preregistration.json`; `outputs/tables/m34_contract_audit_summary.json`; `outputs/tables/m34_alm_toy_benchmark.csv`; `outputs/tables/m34_gradient_geometry.csv`; `outputs/tables/m34_ledger_reconciliation.csv` |
| M34-A post-hoc gradient semantics | `supported` diagnostic parity fact; original authorization failure unchanged | `outputs/tables/m34a_gradient_semantics_amendment.json`; `outputs/tables/m34a_gradient_direction_curves.csv`; `32/32` stable directions, no autograd-error evidence, no training authorization |
| Solver-first SID/EC-OQ | `failed_but_informative`; current implementation rejected/inactive | `outputs/tables/sid_ec_oq_summary.json`; `outputs/tables/sid_ec_oq_cases.csv`; `outputs/tables/sid_ec_oq_bootstrap.csv` |
| CPCF superseding semantic audit | frontier inference `forbidden`; software audit `failed_but_informative` | `outputs/tables/prompt31_cpcf_semantic_audit.json`; `outputs/tables/gamma_sub_cpcf_superseding_claim_record.json` |
| Historical CPCF preregistration and pilot | immutable, non-voting diagnostic only | `outputs/tables/gamma_sub_cpcf_preregistration.json`; `outputs/tables/gamma_sub_cpcf_pilot_summary.json`; `outputs/tables/gamma_sub_cpcf_pilot_operating_points.csv` |
| CPCF invalid attempt provenance | no scientific vote | `outputs/tables/gamma_sub_cpcf_attempt1_invalid_provenance.json`; `outputs/tables/gamma_sub_cpcf_attempt1_invalid_summary.json` |
| CEBA exact-source parity | implementation parity `supported` | `outputs/tables/gamma_sub_ceba_parity_cases.csv`; `outputs/tables/gamma_sub_ceba_parity_summary.json` |
| CEBA bounded pilot | `failed_but_informative`; no boundary claim | `outputs/tables/gamma_sub_ceba_pilot_cases.csv`; `outputs/tables/gamma_sub_ceba_pilot_summary.json`; `outputs/figures/gamma_sub_ceba_boundary_v1.png` |
| CEBA point/set/abstention semantics | diagnostic `supported`; deployable refusal `forbidden` | `outputs/tables/prompt32_ceba_semantic_audit.json` |
| Figure 5 semantic lock | bundled configuration `qualified_supported`; isolated protocol gain `forbidden` | `outputs/tables/prompt32_figure5_semantic_audit.json`; `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json` |
| M32 SCIS | `failed_but_informative`; nominal coverage passes, mismatch refusal fails | `outputs/tables/gamma_sub_scis_preregistration.json`; `outputs/tables/gamma_sub_scis_cache_preflight.json`; `outputs/tables/gamma_sub_scis_summary.json`; `outputs/tables/gamma_sub_scis_cases.csv`; `outputs/figures/gamma_sub_scis_certificate_v1.png` |
| N1-N3 / SC-LOS | not run / `forbidden` | failed upstream trained-forward and geometry gates |

Current report: `docs/codex_reports/m37r_continuous_event_observability_results.md`.

## Preserved extension ledger

| Gate | Status | Boundary |
| --- | --- | --- |
| P0 | `qualified_supported` | reduced synthetic physical semantics |
| P1 | `failed_but_informative` | historical interface/training failure preserved |
| P2 | `failed_but_informative` | thermal/full-rank inverse gates fail |
| P3 | `qualified_supported` | local rank `1 -> 3` in a three-parameter basis only |
| P4 | `forbidden` | no full STL or universal Fourier/F-SPS claim |

## Evidence-type separation

- `public_external_raw`: Zhang paper/Source Data/Zenodo/GitHub artifacts.
- `derived` or `interpolated`: processed copies with raw-parent hashes.
- `solver_generated`: author-compatible, repository SI, event-geometry, and operator-preflight trajectories.
- `pinn_predicted`: completed neural trajectories, including the scoreable v3r post-Adam trajectory.
- `synthetic_gt`: frozen benchmark arrays, never N0 training labels.

None is project-generated experimental measurement.
