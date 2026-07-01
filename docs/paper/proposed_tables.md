# Proposed Tables

All proposed tables summarize synthetic numerical digital-twin benchmark evidence. They are not experimental datasets.

| Table | Content | Primary files | Main use |
| --- | --- | --- | --- |
| Table 1 | Frozen Ground Truth v1.1 acceptance metrics | `docs/gt_v1_acceptance_report.md`, `outputs/tables/gt_v1_acceptance/` | Benchmark definition |
| Table 2 | Direct full-field inverse diagnostics | `outputs/tables/pinn_inverse_v0_ablation_summary.json`, `outputs/tables/pinn_inverse_v1_summary.json`, `outputs/tables/pinn_inverse_v1_1_summary.json` | Motivate target-space reduction |
| Table 3 | Constrained `gamma_sub` prior registry and claim boundary | `docs/parameter_prior_registry.md`, `docs/literature_gamma_sub_evidence_chain.md` | Define allowed inverse target |
| Table 4 | Confounding and prior-width limits | `outputs/tables/gamma_sub_confounding_summary.json`, `outputs/tables/gamma_sub_prior_width_sweep.csv`, `outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json` | Show `T_sw` as dominant limitation |
| Table 5 | Response-surface anchor verification | `outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json`, `outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv` | Qualify dense phase diagrams |
| Table 6 | Sequential protocol design preflight | `outputs/tables/gamma_sub_sequential_protocol_design_summary.json`, `outputs/tables/gamma_sub_sequential_protocol_design_cases.csv` | Protocol design hypothesis ranking |
| Supplementary Table S1 | Balanced F-SPS medium-budget benchmark | `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json`, `outputs/tables/f_sps_balanced_medium_budget_benchmark_cases.csv` | Appendix method-development evidence |
| Supplementary Table S2 | Claim stress-test matrix | `docs/paper/claim_stress_test_matrix.md`, `outputs/tables/manuscript_claim_stress_test_summary.json` | Prevent overclaiming |
