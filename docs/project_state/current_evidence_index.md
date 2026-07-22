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

## Real-device/source bridge

| Block | Status and boundary | Evidence |
| --- | --- | --- |
| Qiu LLP contract | formula identity `supported`; no author-code claim | `outputs/tables/e1f_llp_source_contract_summary.json`; `docs/physics/e1f_llp_source_contract.md` |
| E1F/E1F-R | original has no vote; literal-S3 curve audit `failed_but_informative` | `outputs/tables/e1fr_qiu_source_equation_correction.json`; `docs/codex_reports/e1fr_qiu_source_equation_correction_results.md` |
| Source-to-PDE mapping | refusal fact `supported`; no local calibration | `outputs/tables/e1f_source_to_pde_bridge_mismatch.csv` |
| M40/M40R | static implementation/numerical subfacts; active bridge `failed_but_informative` | `outputs/tables/m40r_qiu_e0_summary.json`; `outputs/tables/m40r_qiu_active_transient.json` |
| M42 foundation | `failed_but_informative`, decision B; no claim upgrade | `outputs/tables/m42_qiu_2d_preflight_summary.json`; `outputs/tables/m42_qiu_2d_preflight_cases.csv`; `outputs/figures/m42/qiu_scale_domain_mesh_preflight.png`; `docs/codex_reports/m42_qiu_2d_physics_foundation_preflight.md` |

M42 replay passed `442` tests. The 22 bounded calls contain no claim-bearing
device forward, fit, inverse, PINN, or sealed-13-V access. Source mapping,
domain, mesh, out-of-plane, and switching-enthalpy gates fail; only a bounded
M43 thermal-spreading closure is authorized.

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

After the one-round M43 decision, only journal/template/declaration/visual-QA
and lawful archive work may delay submission.
