# Related Work V1

Physics-informed inverse modeling connects observed responses to governing equations, but inverse uniqueness depends on observability and parameter confounding. Phase-transition and memristor PINN studies motivate physics regularization, stiff dynamics handling, and thermal/electrical coupling, but they do not remove the need to audit identifiability for each observation set.

For this manuscript, literature is used as prior and model-structure motivation: electrothermal switching motivates \(T_{\mathrm{sw}}\), Joule heating motivates the thermal sink \(\gamma_{\mathrm{sub}}\), and phase-field / localized-heater studies motivate the quasi-2D preflight. These are literature-guided / engineering priors, not measured parameters copied into this benchmark.

External curve fitting remains blocked because no provenance-backed digitized numerical curve table is currently available. The manual digitization queue is a future-data task, not validation evidence.

## Stiffness And Phase-Field Alignment

Seiler 2025 motivates treating sharp phase-transition residuals as a stiffness stressor for PINN training and continuation-style stabilization. In this repository, that literature is used only for supplementary positioning: the stiffness-continuation audit shows a synthetic residual cliff as transition width narrows, but it does not reproduce a full STL-PINN method.

Zhao 2025 motivates inverse-PINN formulations for phase-field models. The Allen-Cahn smoke benchmark in this repository estimates a mobility coefficient from synthetic full-field anchors and supports related-work alignment only; it is not the sparse-port `gamma_sub` inverse problem. Lee 2024 and Jurj 2026 support compact memristor PINN and physics-regularized surrogate framing, not experimental validation.
