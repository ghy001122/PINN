# Current Evidence Index

Current status is authoritative in `PROJECT_STATE.md`; this file routes the
minimum direct evidence. Registries and Git preserve cumulative history.

## Safe manuscript mainline

| Block | Status | Evidence |
| --- | --- | --- |
| Frozen GT v1.1 | integrity `supported` | `docs/gt_v1_acceptance_report.md`; `data/processed/gt_v1_acceptance/manifest.json` |
| Sparse-port hidden-field boundary | configured synthetic `supported` | `outputs/tables/pinn_identifiability_summary.json`; `outputs/tables/pinn_inverse_v0_ablation_summary.json` |
| Calibration-gated rank-1 `gamma_sub` | synthetic/prior-qualified `qualified_supported` | `docs/paper/gamma_sub_evidence_lock.md`; `outputs/tables/gamma_sub_evidence_lock_summary.json` |
| Protocol after calibration | bundled conditional `qualified_supported` | `outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json` |

No item above is experimental evidence or a measured material constant.

## Real-device/source bridge and thermal component

| Block | Status and boundary | Evidence |
| --- | --- | --- |
| Qiu LLP contract | formula identity `supported`; no author-code claim | `outputs/tables/e1f_llp_source_contract_summary.json`; `docs/physics/e1f_llp_source_contract.md` |
| E1F/E1F-R | original has no vote; literal-S3 curve audit `failed_but_informative` | `outputs/tables/e1fr_qiu_source_equation_correction.json`; `docs/codex_reports/e1fr_qiu_source_equation_correction_results.md` |
| Source-to-PDE mapping | refusal fact `supported`; no local calibration | `outputs/tables/e1f_source_to_pde_bridge_mismatch.csv` |
| M40/M40R | static implementation/numerical subfacts; active bridge `failed_but_informative` | `outputs/tables/m40r_qiu_e0_summary.json`; `outputs/tables/m40r_qiu_active_transient.json` |
| M42 foundation | `failed_but_informative`, decision B; no claim upgrade | `outputs/tables/m42_qiu_2d_preflight_summary.json`; `outputs/tables/m42_qiu_2d_preflight_cases.csv`; `outputs/figures/m42/qiu_scale_domain_mesh_preflight.png`; `docs/codex_reports/m42_qiu_2d_physics_foundation_preflight.md` |
| M43 finite-width thermal component | manufactured/component-only `qualified_supported`; no device claim | `outputs/tables/m43_finite_width_thermal_spreading_summary.json`; `outputs/tables/m43_execution_receipt.json`; `outputs/tables/m43_finite_width_thermal_spreading_cases.csv`; `outputs/tables/m43_transient_green_reference.csv`; `outputs/tables/m43_figure_postprocessing_manifest.json`; `outputs/tables/m43_postcommit_attestation.json`; `outputs/figures/m43/m43_thermal_spreading_closure.png`; `docs/codex_reports/m43_finite_width_thermal_spreading_closure.md` |
| Classic reproduction closeout | formula/code/curve/validation responsibility locked; no new run | `outputs/tables/m44_classic_reproduction_closeout.json`; `docs/literature/m44_classic_reproduction_closeout_matrix.md` |
| M44 heterogeneous 3D bridge | `failed_but_informative`; `M44_STOP_REAL_GEOMETRY_UPGRADE` | `outputs/tables/m44_qiu_heterogeneous_3d_thermal_summary.json`; `outputs/tables/m44_execution_receipt.json`; `outputs/tables/m44_qiu_heterogeneous_3d_thermal_cases.csv`; `outputs/tables/m44_geometry_material_source_provenance.csv`; `outputs/tables/m44_final_validation.json`; `outputs/figures/m44/m44_qiu_heterogeneous_3d_thermal_bridge.png`; `docs/codex_reports/m44_qiu_heterogeneous_3d_thermal_bridge.md` |

M42 replay passed `442` tests, but its source/local resistance mismatch remains
`1.33023` and switching enthalpy remains unresolved/unassessed. M43 executed 15
unique thermal-only PDE forwards and passed `21/21` gates for a manufactured
finite-source homogeneous-half-space component. It does not repair the Qiu
source bridge or authorize device dynamics. M44 passed independent-reference,
ledger, provenance, and domain gates but failed its locked mesh, early-time,
and VO2 mean-temperature convergence gates (`0.06325`, `0.05449`, and
`0.06325`, each above `0.02`). The real-geometry upgrade is stopped; M45 and
all device, inverse, or PINN extensions are unauthorized.

## Neural and high-risk boundaries

| Block | Status | Evidence |
| --- | --- | --- |
| Complete PINN contracts | implementation `supported`; training `failed_but_informative` | `outputs/tables/full_pinn_contract_v1.json`; `outputs/tables/n0_cv_e_v3r_summary.json`; `outputs/tables/m33_mixed_flux_final_summary.json` |
| SID/EC-OQ | `failed_but_informative`, inactive | `outputs/tables/sid_ec_oq_summary.json` |
| D0/M35-M37R | provenance/parity facts plus fail-closed topology boundary | `outputs/tables/m37r_cross_regime_jacobian.json`; `docs/codex_reports/m37r_continuous_event_observability_results.md` |
| P1/P2/P4 | failed or forbidden | `docs/paper/final_claim_matrix.md` |

Reliable full-PINN forward, PINN sensitivity/inverse, terminal-only arbitrary
2D field recovery, exact Qiu reproduction, experimental validation, 13 V
holdout, full STL reproduction, and universal Fourier/F-SPS superiority remain
`forbidden`.

## Reproducibility and submission

- Local asset pack: `configs/local_replay_asset_manifest_v1.json` (`50/50`).
- Portable identities: `outputs/tables/portable_evidence_identity_audit.json`.
- Submission readiness: `outputs/tables/submission_readiness.json`.
- Manuscript: `docs/manuscript/main_submission_v2.md` and
  `docs/manuscript/supplementary_information_v1.md`.

M44 selected the preregistered stop decision. Scientific results are frozen;
only journal/template, declaration, visual-QA, lawful archive, claim-audit, and
submission-packaging work may delay submission.
