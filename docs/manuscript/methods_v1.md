# Methods V1

## Evidence Scope

The manuscript reports a one-dimensional synthetic numerical digital-twin benchmark. It does not use measured device data, does not claim device-grade FEM/3D reproduction, and does not infer arbitrary complete hidden fields from sparse terminals.

## Frozen Benchmark And Observation Map

Ground Truth v1.1 is frozen by `configs/gt_v1_acceptance_triangle.yaml`, `configs/gt_v1_acceptance_ltp_ltd.yaml`, and `data/processed/gt_v1_acceptance/manifest.json`. The state variables and SI units follow `docs/method_equations.md`. In the quasi-static one-dimensional electrical model,

$$
R_{\mathrm{area}}(t)=\sum_i\frac{\Delta x}{\sigma_i(t)},\qquad
I(t)=A_{\mathrm{eff}}\frac{V_{\mathrm{app}}(t)}{R_{\mathrm{area}}(t)},\qquad
G(t)=\frac{I(t)}{V_{\mathrm{app}}(t)+\epsilon_V}.
$$

Sparse observations are terminal \(V(t)\), \(I(t)\), and \(G(t)\). Hidden \(T(x,t)\), \(c_v(x,t)\), \(m(x,t)\), and \(\sigma(x,t)\) are retained for synthetic audit only.

## Identifiability Gate And Target Reduction

Before inversion, `scripts/analyze_pinn_identifiability.py` and the v0 ablation quantify terminal-to-field dependence and test port-only field recovery. Failure of the configured full-field recovery motivates target-space reduction; it is not interpreted as a universal mathematical impossibility theorem.

The primary inverse releases only the effective substrate-dissipation parameter \(\gamma_{\mathrm{sub}}\) in

$$
\rho C_p\frac{\partial T}{\partial t}
=-\frac{\partial q_T}{\partial x}+JE-\gamma_{\mathrm{sub}}(T-T_0),
$$

while microphysical parameters are fixed and nuisance parameters, especially \(T_{\mathrm{sw}}\), are fixed or tightly bounded.

## Constrained Objective And Off-Grid Refinement

For simulated and observed terminal series, the configured objective is

$$
\mathcal J(\gamma_{\mathrm{sub}})=
\operatorname{rRMSE}(\hat G,G)^2
+0.5\operatorname{rRMSE}(\hat I,I)^2
+0.01\mathcal R_H.
$$

The declared candidate profile is searched with multiple starting windows. A separate continuous-refinement audit locally refines off-grid targets around the best candidates. Exact definitions and boundaries are locked in `docs/method_equations.md#constrained-gamma-sub-inverse-objective`.

## Calibration, Confounding, And Protocol Sequence

The workflow is calibration before inversion:

1. audit the \(\gamma_{\mathrm{sub}}\)-\(T_{\mathrm{sw}}\) ridge;
2. constrain or probe \(T_{\mathrm{sw}}\);
3. estimate \(\gamma_{\mathrm{sub}}\);
4. compare protocols only under matched prior control;
5. retain wrong-calibration and wide-prior controls.

The protocol search is finite and benchmark-specific. It is not a continuous global optimum or an experimental stimulation design.

## Robustness And Claim Gate

Noise, random seed, observation count, off-grid truth, prior width, and protocol are audited without averaging away the wide-\(T_{\mathrm{sw}}\)-mismatch failures. A positive mainline claim is allowed only with status `supported` or `qualified_supported` in `docs/paper/final_claim_matrix.md`.

## CPCF Semantic Audit And Direct-Solver CEBA

CPCF is retained only as a historical software artifact. A superseding machine audit compares sampled voltage-array hashes, solver/grid/tolerance settings, the gamma candidate grid, objective implementation, `T_sw` units, seed participation, bootstrap semantics, direct-solver case counts, and Pareto qualification. Because those contracts are non-equivalent, CPCF has `scientific_vote=false`; its plot is not a scientific supplementary figure.

The replacement CEBA audit uses only the exact frozen triangle and exact LTP/LTD protocols. Candidate trajectories are generated with the historical `nx=21`, `nt=160/180`, Radau `rtol=1e-5`, `atol=1e-7`, the same fifteen-point `gamma_sub` grid, and the historical port-only objective

$$
\mathcal J_{\mathrm{CEBA}}=
\operatorname{rRMSE}(\hat G,G)^2+
0.5\operatorname{rRMSE}(\hat I,I)^2.
$$

The calibration coordinate is the absolute error `delta_T_sw_K`; no normalized cost or protocol/noise factor is used. Candidate cache keys contain only waveform hash, `gamma_sub`, and solver hash; target keys contain waveform hash, absolute `delta_T_sw_K`, and solver hash. Observation count, noise, and seed are post-trajectory scoring operations. Six direct-source anchors must reproduce best gamma, relative error, recoverability, objective value/order, waveform hash, and solver hash before the pilot can run. Pilot success requires seed success probability at least `0.80`, abstention at most `0.20`, a direct success/failure bracket, and unchanged classification under one refined solver. The total cap is 60 unique solver trajectories, two workers, and 30 minutes.

The CEBA semantic audit keeps point success separate from abstention. The historical profile cutoff is exactly

$$
J_{\min}+0.05\left(J_{\max}-J_{\min}\right),
$$

but its retained-class abstention reads the synthetic truth and uses a locally hard-coded `0.15` class radius. It is therefore an oracle diagnostic, not a deployable uncertainty decision. M32 does not alter this historical rule.

The independent Simulation-Calibrated Identifiability Set (SCIS) uses only the 36 already cached CEBA base-solver trajectories. For candidate (\gamma_j), the calibration score is

$$
s_j(y)=J(\gamma_j;y)-\min_k J(\gamma_k;y),
$$

and the candidate-specific threshold (q_j) is the finite-sample split-conformal order statistic with one-based rank

$$
r=\min\!\left\{n,\left\lceil(n+1)(1-\alpha)\right\rceil\right\},
\qquad \alpha=0.10.
$$

Inference forms (C_\alpha(y)=\{\gamma_j:s_j(y)\le q_j\}) without receiving the true parameter. It accepts only when the set is nonempty and every member is within relative distance `0.15` of the objective minimizer. Discovery, calibration, and held-out seeds are disjoint; `delta_T_sw_K=0` is the only coverage population, whereas `0.2 K` and `2 K` are mismatch stress tests. Any cache miss is a hard stop with no solver fallback.

## Device-Scale Extensions

V10 multilayer OASIS evidence is supplementary. P1 is a field-anchored CV physics-regularized surrogate with a failed strict interface gate; P2 is local linearized block recovery with rank-deficient selected protocols; P3 supports only segmented-terminal forward/current integration and local three-parameter observability; P4 remains blocked.

## Reproduction And Artifact Mapping

The one-to-one equation/config/script/test/JSON-CSV/figure/limitation/sentence mapping and commands are authoritative in `docs/paper/gamma_sub_evidence_lock.md`. Figure 5 uses the 720-case calibrated sequential validation, but the six candidate labels all invoke `simulator_protocol=ltp_ltd` while jointly varying waveform, duration, and calibration-error factor. Its heat term is an implemented candidate-simulation residual, not measured temperature supervision, and the configured `prior_width_factor` is not consumed by the script. Figure 5 therefore reports bundled calibrated-configuration performance and does not isolate causal protocol gain. The broader 2400-case stress audit remains supplementary because its source marks it not main-figure ready.

## VO2 Reproduction And Complete-PINN Audit

Public VO2 data, author code and Zenodo artifacts were acquired with separate license and SHA-256 records. The author implementation was run without fitting and compared with an SI rewrite that preserves the declared 10 ns explicit update, temperature clipping and reversal-history order. The exact 13 V ZIP members were quarantined before numerical access. Because the paper reports that constants were optimized against experimental results, any future 13 V result can only be called a repository-withheld preregistered cross-voltage evaluation, not an independent external validation.

The versioned N0 model predicts \(\phi,c_v,T,m\), derives \(\sigma(c_v,T,m)\), and evaluates the electrostatic, defect, heat and phase residuals plus IC/BC and a series-resistance port operator. The frozen hidden fields and port traces are excluded from training and used only after optimization for scoring. The architecture is tested separately from the historical lightweight neural path.

The N0-R audit additionally compares the frozen FVM face/volume ledger with the continuous equations and four manufactured cases. It corrects the frozen-teacher electrode orientation only in a new matched-budget split path, using two layer-local state networks and exact independent traces at `L_int`. All derivatives are returned to global SI coordinates, and residual scales are fixed before training from layer-local storage, diffusion/drift/reaction, conduction/Joule/sink, and phase-relaxation terms. This path remains data-free; hidden fields are still score-only.

The final N0-CV-E v3 formulation instead predicts bounded cell-centered (c_i(t),T_i(t),m_i(t)) on the unchanged 31-cell frozen grid. Conductivity follows the frozen constitutive closure, while (phi_i,sigma_i,E_i,J,I,G) are computed by a differentiable analytic series-electric head with the same cell-center convention as the teacher. Defect and heat fluxes use the frozen arithmetic face average and zero end fluxes; reaction, Joule, substrate-sink, and phase-relaxation terms are translations of the frozen right-hand side. The loss contains dimensionless cellwise (r_c,r_T,r_m), the structurally exact discrete-current check, and adjacent-state global defect/energy ledgers. Neither frozen full fields nor port traces enter training. Configuration, diagnostics, code hashes, seeds, schedule, and gates were locked before the no-training preflight and optimization attempt.

Physical-model upgrades follow an evidence-triggered H0-H3 ladder. H1 enthalpy/latent heat requires a provenance-backed external thermal residual; H2 history-state freedom requires heating/cooling or minor-loop discrepancy; H3 two-dimensional geometry requires proven one-dimensional structural error. Every new term must have a conservation derivation, SI dimensional audit, primary literature source, and independent-solver test before entering a PINN loss.
