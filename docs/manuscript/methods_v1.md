# Methods V1

The reduced digital twin uses SI-unit variables. The port response is computed from a conductance field through a series or integral relation. The inverse target is \(\gamma_{\mathrm{sub}}\), while confounding parameters such as \(T_{\mathrm{sw}}\), \(\tau_m\), \(\sigma_{\mathrm{on0}}\), and \(\eta_A\) are fixed or tightly bounded.

The manuscript workflow is:

1. Generate and freeze the synthetic Ground Truth v1.1 benchmark.
2. Audit terminal-observation identifiability and show full hidden-field recovery is ill-posed.
3. Reduce the inverse target to \(\gamma_{\mathrm{sub}}\).
4. Quantify confounding with \(T_{\mathrm{sw}}\) and other nuisance parameters.
5. Calibrate or bound \(T_{\mathrm{sw}}\), then estimate \(\gamma_{\mathrm{sub}}\) from port \(G/I\) response.
6. Treat protocol design as a secondary robustness enhancer, not the main source of recoverability.

The quasi-2D module is a forward/preflight extension only. It tests whether residuals, boundary conditions, and terminal-current integrals are computable in a laterally resolved model.
