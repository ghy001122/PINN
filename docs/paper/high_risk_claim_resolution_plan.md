# High-Risk Claim Resolution Plan

All entries in this plan are synthetic numerical digital-twin benchmark targets. They are not experimental validation and do not modify frozen Ground Truth v1.1.

## Current Resolution Status

| Claim target | Current status | Evidence | Allowed wording | Forbidden wording |
|---|---|---|---|---|
| Boundary-aware multilayer sandwich forward | qualified_supported | `outputs/tables/multilayer_sandwich_device_summary.json`; finite rate 1.0; interface residual median 0.0; current continuity median 0.0 | Reduced boundary-aware multilayer sandwich forward benchmark | Full FEM, device-grade reproduction, or experimental validation |
| Literature-prior registry | qualified_supported | `outputs/tables/literature_prior_consistency_summary.json`; 3 device families; provenance fields True | Literature-guided shape/parameter plausibility priors | Measured material parameters or experimental validation |
| Augmented 2D hidden-field recovery | qualified_supported | Best protocol `multi_terminal_plus_fisher_anchors`; median field error 0.19897395319670247; success rate 0.75 | Structured field recovery under augmented Fisher-anchor protocol | Terminal-only arbitrary full 2D hidden-field recovery |
| Active terminal-only low-dimensional inverse | qualified_supported | Best protocol `combined_terminal_protocol`; median parameter error 0.056375606896068575; success rate 1.0 | Low-dimensional terminal diagnosis under combined active protocols | Single-trace arbitrary full-field recovery |
| Phase-aware STL repair | failed_but_informative | Best algorithm `progressive_width_stl`; gain 0.09389518340983438 | Reduced transfer diagnostic only | Full STL-PINN reproduction |
| Adaptive Fourier/F-SPS | failed_but_informative | Sharp gain 0.4079553978360986; Pareto win rate 0.6666666666666666; smooth degradation 0.1821856000041686 | Failed-but-informative regime-specific method evidence | Universal F-SPS/Fourier superiority |
| Low-dimensional sandwich inverse | qualified_supported | Best protocol `combined`; median parameter error 0.04044092905036974 | Low-dimensional sandwich-parameter inversion under combined protocol | Full arbitrary field inverse |
| Experimental validation | forbidden | No provenance-backed measured data added | Synthetic numerical digital-twin benchmark | Measured experimental validation |

## Rule

Explore aggressively; interpret conservatively. A failed gate is still useful if it clarifies observability, stiffness, boundary-condition, or prior-dependence limits.
