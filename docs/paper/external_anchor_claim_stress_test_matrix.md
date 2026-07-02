# External Anchor Claim Stress Test Matrix

All claims refer to synthetic numerical digital-twin benchmark evidence, not experimental measurements.

| Claim | Evidence | Limitation | Forbidden wording |
| --- | --- | --- | --- |
| Literature parameter sanity supports order-of-magnitude plausibility | `data/literature/literature_parameter_sanity_table.csv` | Priors only; not measured device parameters | measured material calibration |
| Digitized curve fitting, if available, supports normalized shape plausibility only | `outputs/tables/literature_curve_fit_external_anchor_v2_summary.json` | Blocked if no provenance-backed curve exists | direct device validation |
| External curves do not validate gamma_sub inversion | `docs/literature/literature_curve_provenance_notes.md` | External anchors are separate from inverse-target proof | gamma_sub validated by literature curves |
| T_sw calibration is necessary for reliable gamma_sub recovery | `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json` | Synthetic benchmark workflow evidence | unconditional gamma_sub identifiability |
| Calibrated sequential protocol improves synthetic ODE-backed recovery, if supported | `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json` | Simulator-backed synthetic setting only | experimental protocol optimization |
| F-SPS remains appendix or negative evidence | `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json` | No current superiority claim | F-SPS performance superiority |
| All results remain synthetic numerical digital-twin benchmark | `CODEX_CONTEXT.md` | No experimental measurements | real device validation |
