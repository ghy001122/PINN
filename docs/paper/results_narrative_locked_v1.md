# Results Narrative Locked V1

All results are synthetic numerical digital-twin benchmark evidence, not experimental data.

The manuscript should present a narrow chain: sparse-port hidden-field recovery is ill-posed, target-space reduction is required, `gamma_sub` is conditionally recoverable under fixed or tightly bounded priors, and `T_sw` calibration is the central boundary condition.

The tolerance sweep quantifies the required calibration boundary. The ODE-backed spot-check adds `270` simulator-backed cases and reports median errors by calibration error `{'0.04': 0.1111111111111111, '0.1': 0.1111111111111111, '0.2': 0.2222222222222222}`. Under the configured <=15% median-error criterion, `whether_0p1K_threshold_supported_by_ode_spotcheck` is `True`.

Calibration-vs-protocol disentanglement shows calibration gain dominates protocol gain; protocol design remains a secondary robustness enhancer. The quasi-2D module is extension feasibility only and must not be written as main evidence for inverse diagnosis.

External curve fitting is not claimed because the targeted extraction attempt found no provenance-backed digitized numerical curve table.
