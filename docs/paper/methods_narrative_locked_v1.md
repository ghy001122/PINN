# Methods Narrative Locked V1

The method is a calibration-gated sparse-port reduced inversion workflow. First, use literature/engineering priors and a calibration or probe step to constrain `T_sw`. Second, estimate only `gamma_sub` from port `G/I` response with fixed or tightly bounded nuisance parameters. Third, audit protocol robustness with ODE-backed synthetic cases. This is not a full hidden-field PINN recovery claim.

The ODE spot-check reuses the frozen Ground Truth simulator with reduced CPU settings and estimates only `gamma_sub` over candidate values. It is simulator-backed synthetic evidence, not a response-surface lookup and not experimental calibration.

The quasi-2D module defines laterally resolved forward fields and autograd residual checks for future extension feasibility. It is not part of the main inverse claim.
