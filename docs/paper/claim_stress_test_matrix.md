# Manuscript Claim Stress-Test Matrix

All claims in this matrix are limited to synthetic numerical digital-twin benchmark evidence. They are not experimental measurements, not full 3D device simulation, and not proof of sparse-port full hidden-field recovery.

| Claim | Supporting tables | Strongest numerical result | Limitation | Forbidden overclaim | Section |
| --- | --- | --- | --- | --- | --- |
| Sparse-port full-field recovery is non-identifiable in the current one-dimensional benchmark. | `outputs/tables/pinn_identifiability_summary.json` | mean_sigma remains the dominant terminal-observable correlate; summary keys=['benchmark', 'best_lag_correlation_to_G', 'field_dynamic_ranges', 'hidden_field_correlations', 'input_path', 'interpretation'] | This proves an identifiability boundary for the synthetic benchmark, not a theorem for all devices. | Sparse port data uniquely recover delta_T, c_v, m, and sigma. | Results: identifiability boundary |
| gamma_sub recovery is conditionally possible under bounded T_sw prior. | `outputs/tables/gamma_sub_constrained_inversion_summary.json`, `outputs/tables/gamma_sub_prior_width_sweep.csv` | max tested constrained relative error=1.2222222222222223 | The claim requires fixed or tightly bounded switching/conductivity priors. | gamma_sub is identifiable under arbitrary released nuisance parameters. | Results: reduced inverse target |
| Wide T_sw mismatch is the dominant failure mode. | `outputs/tables/gamma_sub_confounding_summary.json`, `outputs/tables/gamma_sub_statistical_robustness_summary.json` | worst statistical case=wide_T_sw_mismatch | Other parameters also confound gamma_sub; T_sw is the strongest tested one, not the only risk. | Model mismatch does not affect gamma_sub inversion. | Discussion: confounding and priors |
| ltp_ltd and short_pulse style protocols improve recoverability relative to less informative choices. | `outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json`, `outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json` | phase-diagram best_protocol=ltp_ltd | Protocol rankings are response-surface guidance and need stronger validation before experimental prescription. | Any multi-protocol design automatically solves gamma_sub/T_sw ambiguity. | Results: protocol robustness |
| Naive weighted protocol objective does not improve over the best single protocol. | `outputs/tables/gamma_sub_weighted_protocol_objective_summary.json` | improves_over_best_single=False | Only tested configured weights; better optimized designs remain future work. | Weighted stimulation is useless in general. | Ablation: protocol objective |
| Response-surface phase diagrams are acceptable only with anchor verification and explicit qualification. | `outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json`, `outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv` | classification_agreement_rate=0.8833333333333333 | Dense profile is interpolated from simulator-backed source points, not thousands of fresh ODE solves. | All dense response-surface points are simulator-backed ODE solves. | Reviewer defense: response-surface validation |
| F-SPS-PINN does not currently support a superiority claim. | `outputs/tables/f_sps_medium_budget_benchmark_summary.json`, `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json` | balanced_f_sps_improves_over_free_log_sigma=False | F-SPS remains an appendix/future-work method-development line. | F-SPS-PINN is validated as more accurate than the free log_sigma shortcut. | Appendix: method development |

## Use Boundary

Use this file to decide which results belong in the main manuscript and which belong in appendix or future work. Do not convert response-surface or small-run method-development evidence into experimental validation claims.
## Literature-Anchored Pack Claim Stress Test

| Claim | Evidence | Limitation | Forbidden wording |
| --- | --- | --- | --- |
| Literature anchors support the prior ranges | `data/literature/literature_parameter_sanity_table.csv` | Anchors are order-of-magnitude or engineering priors | measured material parameters |
| External curve fitting is not yet complete | `outputs/tables/literature_curve_fit_external_anchor_summary.json` | No digitized curve CSV exists in the repo | fitted public curves without data |
| T_sw calibration is necessary | `outputs/tables/gamma_sub_tsw_calibration_necessity_summary.json` | Tested in synthetic response-surface setting | unconditional gamma_sub identifiability |
| Sequential protocol design is promising | `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json` | Still a synthetic preflight with prior-narrowing assumption | experimental protocol validation |

## External Curve Ingestion And Calibration Workflow Claims

| Claim | Supporting evidence | Limitation | Forbidden overclaim |
| --- | --- | --- | --- |
| External curve fitting is blocked until provenance-backed digitized CSV/Sheet data exist. | `outputs/tables/literature_curve_ingestion_summary.json`, `docs/literature/literature_curve_provenance_notes.md` | Google Drive currently supplies PDFs, not curve tables | Fitted public curves without numeric data |
| T_sw calibration before inversion is required. | `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json` | Response-surface workflow evidence | Unconditional joint `T_sw`/`gamma_sub` identifiability |
| Calibrated multi-pulse-to-LTP/LTD is the best current synthetic sequential candidate. | `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json` | ODE-backed synthetic preflight only | Experimentally validated pulse protocol |

## Calibration-Gated Submission Lock Addendum

| Evidence block | Script/config | Summary file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- |
| T_sw calibration tolerance sweep | `scripts/audit_gamma_sub_tsw_calibration_tolerance_sweep.py`, `configs/gamma_sub_tsw_calibration_tolerance_sweep.yaml` | `outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json` | Figure 3 / Table 4 | Residual T_sw error must be about `0.1` K or tighter in this synthetic audit | Real calibration accuracy requirement |
| Calibration-vs-protocol disentanglement | `scripts/audit_gamma_sub_calibration_protocol_disentanglement.py` | `outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json` | Figure 4 / Table 5 | Calibration dominates total gain; protocol gain is smaller and qualified | Protocol identity alone solves ambiguity |
| Calibrated protocol robustness final | `scripts/audit_gamma_sub_calibrated_protocol_robustness_final.py` | `outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json` | Figure 5 / Table 6 | `calibrated_short_pulse_to_ltp_ltd` is best in the tested ODE-backed synthetic grid | Experimental protocol validation |
| Targeted external curve extraction | `scripts/attempt_literature_curve_extraction_from_sources.py` | `outputs/tables/literature_targeted_curve_extraction_attempt_summary.json` | Figure 7 / Supplement | No provenance-backed digitized curves were found; no curve data were fabricated | Literature curve fit success |

## VO2 D0a and Full-PINN N0 Addendum

| Candidate claim | Evidence | Strongest result | Limitation | Forbidden wording |
| --- | --- | --- | --- | --- |
| Exact-source semantics are reproduced | `outputs/tables/vo2_d0a_source_reproduction.json` | author/SI dynamic-current NRMSE95 `4.55e-14` | full D0a gate fails because 5-to-2.5 ns NRMSE95 is `0.163148` | independent validation or converged external reproduction |
| Public 13 V is a withheld evaluation | sealed manifest only | content was not read | no fit lock or 13 V evaluation exists; source-model development may have used experimental results | independent external holdout or successful cross-voltage evaluation |
| Full 1D PINN forward gate passes | `outputs/tables/n0_cv_e_v3r_forensic_resolution.json` | v3r port NRMSE95 `0.0955475`; finite Adam state and declining loss | residual/field/flux/ledger gates fail; five metrics exceed `20x`; strong-Wolfe closure 3 becomes non-finite | reliable full PINN, conservation, sensitivity fidelity, or inverse success |
| Protocol-conditioned quotient hypothesis is supported | `outputs/tables/sid_ec_oq_summary.json` plus cumulative v2 summary | solver-first discovery completed within budget | derivative passes `3/9`; event-window, condition, protocol-count, and neighborhood gates fail; D0c/D0d/N1-N3 remain unrun | protocol rank/rotation, SID/EC-OQ, or quotient superiority |
| CPCF establishes a reliable resource frontier | `outputs/tables/gamma_sub_cpcf_pilot_summary.json`; `outputs/tables/gamma_sub_cpcf_pilot_operating_points.csv` | `5` sample-nondominated points are bootstrap-stable in the bounded grid | fresh anchors violate the locked tolerance and no `20%` improvement/CI-direction gate passes; full sweep did not run | cost optimality, monetary/laboratory cost, device-general resource prescription, or main contribution |

