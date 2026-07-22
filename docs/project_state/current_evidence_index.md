# Current Evidence Index

This is the compact routing surface. Current status is authoritative in
`PROJECT_STATE.md`; cumulative history remains in the registries and Git.

## Locked safe mainline

- Evidence lock: `docs/paper/gamma_sub_evidence_lock.md`.
- Claim matrix: `docs/paper/final_claim_matrix.md`.
- Safe wording: calibration-gated rank-1 `gamma_sub`, synthetic and prior-
  qualified. No measured-material, experimental-validation, or successful-
  trained-PINN wording is permitted.

## Active round and Qiu bridge

M42 is preregistered at
`docs/research_strategy/m42_reference_and_2d_preregistration.md`. Until its
detached replay and bounded preflight run, it is a planned audit with no
scientific vote and no claim upgrade.

| Block | Status | Primary evidence |
| --- | --- | --- |
| Layered E1F/LLP source contract | Formula identity `supported`; no device-science vote | `outputs/tables/e1f_llp_source_contract_summary.json`; `outputs/tables/e1f_source_contract_amendment_v2.json`; `docs/physics/e1f_llp_source_contract.md` |
| E1F semantic amendment | Original formal run `implementation_contract_invalid`; no curve vote | `outputs/tables/e1f_semantic_amendment.json`; `docs/codex_reports/e1f_semantic_amendment.md` |
| E1F-R literal-S3 correction | `failed_but_informative`; solver parity passes, clean SI Fig. S1 current/voltage gates fail, Fig. 2b remains invalid/unassessed and unscored, coordinate preflight blocked | `outputs/tables/e1fr_qiu_source_equation_correction.json`; `outputs/tables/e1fr_qiu_source_equation_correction.csv`; `outputs/tables/e1fr_effective_coordinate_preflight.json`; `outputs/figures/e1fr/qiu_setting_correction.png`; `docs/codex_reports/e1fr_qiu_source_equation_correction_results.md` |
| Source-to-PDE refusal | mapping-audit fact `supported`; no calibration claim | `outputs/tables/e1f_source_to_pde_bridge_mismatch.csv`; `outputs/figures/e1f/source_to_pde_bridge_mismatch.png` |
| M40 Qiu 2D E0 | `failed_but_informative`; M41 not authorized | `outputs/tables/m40_qiu_e0_summary.json`; `outputs/tables/m40_qiu_mesh_convergence.csv`; `docs/codex_reports/m40_qiu_vo2_e0_results.md` |
| M40R bounded repair | original numerical E0 sub-result passes; overall `failed_but_informative`; M41 not authorized | `outputs/tables/m40r_qiu_e0_summary.json`; `outputs/tables/m40r_qiu_active_transient.json`; `docs/codex_reports/m40r_qiu_e0_repair_results.md` |

Current report: `docs/codex_reports/source_contract_amendment_results.md`.

## Main scientific evidence

| Block | Status | Primary evidence |
| --- | --- | --- |
| Frozen GT v1.1 | integrity `supported` | `docs/gt_v1_acceptance_report.md`; `data/processed/gt_v1_acceptance/manifest.json` |
| Sparse-port hidden-field boundary | `supported` in the configured synthetic benchmark | `outputs/tables/pinn_identifiability_summary.json`; `outputs/tables/pinn_inverse_v0_ablation_summary.json` |
| Constrained `gamma_sub` inverse | `qualified_supported` under fixed/tightly bounded microphysics and calibration | `outputs/tables/gamma_sub_evidence_lock_summary.json`; `docs/paper/gamma_sub_evidence_lock.md` |
| Calibration/confounding boundary | `qualified_supported` with retained failures | `outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json`; `outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json`; `outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json` |
| Conditional robustness | `qualified_supported`; wide mismatch retained | `outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json`; `outputs/tables/gamma_sub_statistical_robustness_summary.json`; `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json`; `outputs/tables/prompt32_figure5_semantic_audit.json` |

## Full-PINN and public-data boundaries

| Block | Status | Primary evidence |
| --- | --- | --- |
| Full-PINN contracts | `supported` implementation facts | `outputs/tables/full_pinn_contract_v1.json`; `src/pinnpcm/pinn/full_pinn_1d.py`; `src/pinnpcm/pinn/full_pinn_n0_cv_e.py`; `src/pinnpcm/pinn/mixed_flux_pinn.py` |
| Trained full-PINN routes | `failed_but_informative`; positive forward/sensitivity/inverse `forbidden` | `outputs/tables/full_pinn_single_seed_mve_v1.json`; `outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json`; `outputs/tables/n0_cv_e_v3r_forensic_resolution.json`; `outputs/tables/m33_mixed_flux_final_summary.json`; `outputs/tables/m34_contract_audit_summary.json` |
| Zhang D0/M35 | provenance/source semantics retained; fit route `failed_but_informative` | `data/external/vo2_zhang_2024/manifest.json`; `outputs/tables/vo2_d0a_source_reproduction.json`; `outputs/tables/m35_public_multivoltage_fit_summary.json` |
| M36 numerical reference | nominal parity fact `supported`; source-compatible convergence fails | `outputs/tables/m36_event_resolved_orbit_summary.json`; `outputs/tables/m36_orbit_convergence_metrics.csv` |
| M37/M37R observability | window repair fact `supported`; geometry unassessed/`forbidden` | `outputs/tables/m37_cross_regime_jacobian.json`; `outputs/tables/m37r_cross_regime_jacobian.json`; `outputs/tables/m37r_event_window_audit.csv` |
| D0b-D0d / N1-N3 / SC-LOS | unrun or blocked; positive claims `forbidden` | failed upstream convergence, trained-forward, and topology gates; 13 V remains sealed |

## Extension boundaries

| Block | Status | Primary evidence |
| --- | --- | --- |
| P0 / P3 | `qualified_supported` reduced synthetic results | `outputs/tables/multiterminal_yz_forward_summary.json`; claim matrix |
| P1 / P2 | `failed_but_informative` | `outputs/tables/cv_multidomain_oasis_training_summary.json`; `outputs/tables/active_protocol_design_v3_summary.json`; `outputs/tables/sequential_terminal_inverse_v3_summary.json` |
| P4 | `forbidden` | `outputs/tables/oasis_algorithm_gate_v10_summary.json` |
| SID/EC-OQ | `failed_but_informative`; inactive | `outputs/tables/sid_ec_oq_summary.json`; `outputs/tables/sid_ec_oq_cases.csv` |
| CPCF | frontier inference `forbidden`; proxy audit non-voting | `outputs/tables/prompt31_cpcf_semantic_audit.json`; `outputs/tables/gamma_sub_cpcf_superseding_claim_record.json` |
| CEBA / SCIS | parity subfacts retained; deployable boundary/refusal unsupported | `outputs/tables/gamma_sub_ceba_parity_summary.json`; `outputs/tables/gamma_sub_ceba_pilot_summary.json`; `outputs/tables/gamma_sub_scis_summary.json` |

## Evidence taxonomy

- `synthetic_gt`: frozen benchmark arrays; not measured data.
- `public_external_raw`: publisher-supplied numeric source data with provenance.
- `external_literature_source_document`: hash-locked publisher PDFs; not project
  measurements and not assumed redistributable.
- `derived` / `interpolated`: transformations retaining parent hashes. Qiu
  digitized traces are derived publication curves; Fig. 2b is
  `implementation_contract_invalid/unassessed`.
- `solver_generated`: numerical trajectories and audits.
- `pinn_predicted`: neural outputs only; solver outputs must never be relabeled.

## Submission routing

- Current manuscript entry: `docs/manuscript/README.md`; v1 remains immutable
  historical content and v2 is the validated content-package target.
- Go/no-go: `docs/manuscript/submission_go_no_go.md`.
- Figures/tables: `docs/paper/final_figure_list.md` and
  `docs/paper/final_table_list.md`.
- Local replay evidence: `configs/local_replay_asset_manifest_v1.json`,
  `outputs/tables/local_replay_asset_validation.json`,
  `outputs/tables/portable_evidence_identity_audit.json`,
  `outputs/tables/gamma_sub_continuous_refinement_integrity_audit.json`, and
  `outputs/tables/submission_readiness.json`.
- Current single priority: lock journal/article type, author declarations,
  template rendering/visual QA, and the public/restricted asset route without
  reopening failed science.
