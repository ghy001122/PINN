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

## Device-Scale Extensions

V10 multilayer OASIS evidence is supplementary. P1 is a field-anchored CV physics-regularized surrogate with a failed strict interface gate; P2 is local linearized block recovery with rank-deficient selected protocols; P3 supports only segmented-terminal forward/current integration and local three-parameter observability; P4 remains blocked.

## Reproduction And Artifact Mapping

The one-to-one equation/config/script/test/JSON-CSV/figure/limitation/sentence mapping and commands are authoritative in `docs/paper/gamma_sub_evidence_lock.md`. Figure 5 uses the 720-case calibrated sequential validation; the broader 2400-case stress audit is supplementary because its source marks it not main-figure ready.

## VO2 Reproduction And Complete-PINN Audit

Public VO2 data, author code and Zenodo artifacts were acquired with separate license and SHA-256 records. The author implementation was run without fitting and compared with an SI rewrite that preserves the declared 10 ns explicit update, temperature clipping and reversal-history order. The exact 13 V ZIP members were quarantined before numerical access. Because the paper reports that constants were optimized against experimental results, any future 13 V result can only be called a repository-withheld preregistered cross-voltage evaluation, not an independent external validation.

The versioned N0 model predicts \(\phi,c_v,T,m\), derives \(\sigma(c_v,T,m)\), and evaluates the electrostatic, defect, heat and phase residuals plus IC/BC and a series-resistance port operator. The frozen hidden fields and port traces are excluded from training and used only after optimization for scoring. The architecture is tested separately from the historical lightweight neural path.

The N0-R audit additionally compares the frozen FVM face/volume ledger with the continuous equations and four manufactured cases. It corrects the frozen-teacher electrode orientation only in a new matched-budget split path, using two layer-local state networks and exact independent traces at `L_int`. All derivatives are returned to global SI coordinates, and residual scales are fixed before training from layer-local storage, diffusion/drift/reaction, conduction/Joule/sink, and phase-relaxation terms. This path remains data-free; hidden fields are still score-only.
