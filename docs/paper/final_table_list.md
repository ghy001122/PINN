# Final Table List

Tables report synthetic numerical digital-twin evidence unless explicitly marked as external-literature or mapping-audit evidence. Digitized publication curves are not raw or project-generated experimental measurements.

| Table | Content | Source |
| --- | --- | --- |
| Table 1 | Frozen GT v1.1 benchmark metrics | `docs/gt_v1_acceptance_report.md` |
| Table 2 | Identifiability and hidden-field limitation summary | `outputs/tables/pinn_identifiability_summary.json` |
| Table 3 | Prior registry and literature sanity | `docs/parameter_prior_registry.md`; `data/literature/literature_parameter_sanity_table.csv` |
| Table 4 | `T_sw` calibration tolerance plus ODE spot-check | `outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json`; `outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json` |
| Table 5 | Calibration-vs-protocol disentanglement | `outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json` |
| Table 6 | Bundled calibrated-configuration performance and semantic audit | `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json`; `outputs/tables/prompt32_figure5_semantic_audit.json` |
| Supplementary Table | SCIS nominal-coverage and mismatch-refusal gates | `outputs/tables/gamma_sub_scis_summary.json`; `outputs/tables/gamma_sub_scis_cases.csv` |
| Supplementary Table | Reviewer-defense matrix | `docs/manuscript/reviewer_defense_matrix.md` |
| Supplementary Table | Quasi-2D literature-source registry and residual preflight | `outputs/tables/quasi_2d_literature_source_registry.json`; `outputs/tables/pinn_quasi_2d_residual_preflight_summary.json` |
| Supplementary Table | F-SPS negative/small-run benchmark | `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json` |

| Supplementary Table | Stiffness and phase-field story manifest | `outputs/tables/stiffness_2d_story_figure_manifest.json` |
| Supplementary Table | Literature evidence lock for stiffness and 2D positioning | `docs/literature/drive_and_web_literature_evidence_lock.md` |
| Supplementary Table | VO2 D0a source discrepancies, provenance and stop-gate metrics | `outputs/tables/vo2_d0a_source_discrepancies.csv`; `outputs/tables/vo2_d0a_source_reproduction.json` |
| Supplementary Table | Full-PINN N0 contract and failed single-seed MVE | `outputs/tables/full_pinn_contract_v1.json`; `outputs/tables/full_pinn_single_seed_mve_v1.json` |
| Supplementary Table | N0-R teacher-equation compatibility, exact-trace repair, and gate comparison | `outputs/tables/n0_equation_parity_registry_v1.csv`; `outputs/tables/n0_global_conservation_audit_v1.json`; `outputs/tables/n0_baseline_repair_gate_comparison_v2.csv` |
| Supplementary Table | N0-CV-E v3 evidence-integrity audit, locked operator preflight, and fail-closed training result | `outputs/tables/n0_r_v2_evidence_integrity_audit.json`; `outputs/tables/n0_cv_e_v3_preflight.json`; `outputs/tables/n0_cv_e_v3_seed_20260715.json`; `outputs/tables/n0_cv_e_v3_model_comparison.csv` |
| Supplementary Table | N0 v3r optimizer forensics and current SID/EC-OQ implementation rejection | `outputs/tables/n0_cv_e_v3r_forensic_resolution.json`; `outputs/tables/sid_ec_oq_summary.json` |
| Supplementary Table | M33 mixed-flux preflight, complete gate result, and matched v3r comparison | `outputs/tables/m33_mixed_flux_preflight.json`; `outputs/tables/m33_mixed_flux_final_summary.json`; `outputs/tables/m33_mixed_flux_v3r_comparison.csv` |
| Supplementary Table | CEBA exact-source parity and preregistered abstention boundary | `outputs/tables/gamma_sub_ceba_parity_cases.csv`; `outputs/tables/gamma_sub_ceba_parity_summary.json`; `outputs/tables/gamma_sub_ceba_pilot_cases.csv`; `outputs/tables/gamma_sub_ceba_pilot_summary.json` |
| Supplementary Table | Original E1F implementation-contract invalidation plus E1F-R solver parity and failed clean SI Fig. S1 setting gate | `outputs/tables/e1f_semantic_amendment.json`; `outputs/tables/e1fr_qiu_source_equation_correction.json`; `outputs/tables/e1fr_qiu_source_equation_correction.csv` |
| Supplementary Table | E1F source-to-PDE mapping refusal and E1F-R upstream-blocked coordinate preflight | `outputs/tables/e1f_source_to_pde_bridge_mismatch.csv`; `outputs/tables/e1fr_effective_coordinate_preflight.json` |

## Non-voting software diagnostics

The CPCF operating points, pilot summary, invalid-attempt provenance, and Pareto image remain immutable historical records, but `outputs/tables/prompt31_cpcf_semantic_audit.json` forbids their use as a scientific supplementary table or frontier vote.
