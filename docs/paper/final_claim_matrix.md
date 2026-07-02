# Final Claim Matrix

Allowed claims are restricted to synthetic numerical digital-twin evidence.

| Claim | Status | Required qualifier | Forbidden wording |
| --- | --- | --- | --- |
| Sparse-port full hidden-field recovery is ill-posed in the current benchmark | Supported | one-dimensional synthetic benchmark | unique full-field recovery |
| `gamma_sub` is a reduced inverse target | Supported conditionally | fixed or tightly bounded priors | unconditional identifiability |
| `T_sw` calibration is required before `gamma_sub` inversion | Supported | response-surface and ODE-backed synthetic audits | measured calibration result |
| 0.1 K residual `T_sw` tolerance is usable as a paper threshold | Supported as benchmark-specific | synthetic <=15% median-error criterion plus ODE spot-check | real experimental calibration capability requirement |
| Calibration gain dominates protocol gain | Supported | protocol gain is secondary and qualified | protocol identity alone solves inverse recovery |
| Calibrated protocol robustness can be shown | Qualified | synthetic ODE-backed, calibrated priors; worst-case errors remain non-negligible | experimentally validated stimulation protocol |
| Literature curve fitting validates model curves | Blocked | requires provenance-backed CSV/JSON data | fitted public curves without data |
| Quasi-2D extension improves physical-depth discussion | Supported as preflight only | forward/residual feasibility; supplementary/discussion placement | 2D inverse diagnosis is solved |
| F-SPS-PINN is superior | Not supported | appendix/future work only | performance superiority |
