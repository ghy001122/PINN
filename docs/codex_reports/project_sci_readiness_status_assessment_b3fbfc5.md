# Project SCI Readiness Status Assessment

## Snapshot

- Assessed commit: `b3fbfc58ec23058351e7009e9a2797095faefd4a`
- Branch: `main`
- Assessment date: 2026-06-30
- Repository phase: `SCI manuscript evidence consolidation`
- Scope: synthetic numerical digital-twin benchmark only
- Frozen Ground Truth modified in this assessment: No
- New training or simulation run in this assessment: No

## Bottom-Line Judgment

The project is not yet ready to claim a high-quality SCI paper is fully complete, but it has reached a defensible manuscript core for a method-oriented SCI submission if the claim is narrowed.

The strongest publishable line is not full hidden-field PINN recovery and not F-SPS-PINN performance superiority. The strongest line is:

> Sparse-port full hidden-field recovery is ill-posed; identifiability-guided target-space reduction is needed; under fixed or tightly bounded priors, `gamma_sub` is a conditionally identifiable reduced inverse target in a one-dimensional synthetic numerical digital-twin benchmark.

This is a credible method-paper core. It still needs manuscript-grade figures, a concise comparison baseline, and a carefully written limitations section before submission.

## Current Evidence Status

### 1. Frozen Ground Truth v1.1 Benchmark

The project has a frozen synthetic Nb/NbOx/V2O5/Ni-inspired benchmark with visible hysteresis, conductance modulation, thermal response, defect evolution, and switching-state dynamics.

Strength:

- The benchmark is reproducible and frozen.
- It supports controlled inverse-problem testing.
- It avoids false experimental claims.

Limitation:

- It is not measured device data.
- It is one-dimensional and reduced-order.
- It cannot support claims about complete real-device physics.

Manuscript role:

- Main-text benchmark setup and synthetic testbed definition.

### 2. PINN v0/v1/v1.1 Full-Field Inversion Diagnostics

The v0/v1/v1.1 work established the inverse training pipeline and showed that port-only recovery of hidden fields remains anchor-dependent or underdetermined. Approximate physics residuals and residual balancing did not solve the `delta_T` problem.

Strength:

- These results are useful negative evidence.
- They justify moving away from full hidden-field recovery.
- They make the paper more honest than a pure success story.

Limitation:

- They are not strong enough to claim a successful full PDE-constrained inverse PINN.
- They should not be presented as a final hidden-field reconstruction method.

Manuscript role:

- Motivation and supplementary ablation.

### 3. Identifiability Audit

The identifiability audit found that terminal observations constrain integrated conductance but do not uniquely recover `delta_T`, `c_v`, `m`, and `sigma`.

Key interpretation:

- `G(t)` aligns strongly with aggregate conductivity behavior.
- Multiple hidden-field combinations can produce similar terminal response.
- Full hidden-field recovery from sparse electrical ports is ill-posed in this benchmark.

Strength:

- This is the logical pivot of the paper.
- It turns a failed full-field inverse task into a stronger identifiability argument.

Limitation:

- The audit is benchmark-specific.
- It does not prove universal impossibility for all devices or all observation protocols.

Manuscript role:

- Main result: why target-space reduction is necessary.

### 4. Constrained `gamma_sub` Inversion

The constrained inversion recovers nominal `gamma_sub = 4.5e8` exactly under fixed priors, including clean and noisy nominal cases. It also shows strong failure under `T_sw` mismatch.

Important values:

- Nominal true `gamma_sub`: `4.5e8`
- Nominal estimate: `4.5e8`
- Nominal relative error: `0.0`
- Worst tested relative error: `1.2222222222222223`
- Worst confounder: `T_sw`
- Unstable prior-width threshold in the sweep: `0.05`

Strength:

- Supports `gamma_sub` as a reduced inverse target.
- Provides direct evidence that priors matter.
- Exposes the main confounder instead of hiding it.

Limitation:

- The result is conditional, not universal.
- It does not prove joint identifiability when `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are released.

Manuscript role:

- Main result: constrained thermal-loss parameter inversion.

### 5. Confounding And Robustness Evidence

The confounding audit identifies `T_sw` as the most dangerous sensitivity source. `sigma_on0` and `tau_m` can also align with the `gamma_sub` response direction.

Strength:

- The paper can answer the key reviewer question: which parameter breaks the inversion?
- The result gives a clear claim boundary: fixed or tightly bounded priors are required.

Limitation:

- The method becomes weak if switching parameters are unknown.
- The current evidence does not support unconstrained multi-parameter inversion.

Manuscript role:

- Reviewer defense and limitation section.

### 6. Off-Grid And Continuous Refinement

The continuous refinement audit tested off-grid true values `4.38e8`, `4.62e8`, and `5.15e8` across `n_obs = 8, 16, 32, 64` and noise `0, 0.02, 0.05`.

Important values:

- Number of official cases: `36`
- Max nearest-grid relative error: `0.08225108225108226`
- Max continuous-refined relative error: `0.05565017963752034`
- All success under configured threshold: `true`
- Non-grid simulator evaluations used: `true`

Strength:

- Removes the strongest grid-hit criticism.
- Shows the inversion is not only selecting a candidate already containing the truth.
- Gives a compact robustness result for reviewers.

Limitation:

- Priors remain fixed.
- Some noisy cases show refinement can be worse than nearest-grid locally, although still within threshold.
- This is still scalar refinement, not full inverse modeling.

Manuscript role:

- Main or reviewer-defense figure/table.

### 7. F-SPS-PINN v2 Method Development

The F-SPS-PINN path includes architecture MVP, v2 smoke training, free `log_sigma` versus white-box `vo2_sigma` baseline, phase-transition stress preflight, and Fourier on/off ablation.

Key latest Fourier result:

- Fourier off `relative_G_error`: `0.6509982160898017`
- Fourier on `relative_G_error`: `0.6529524166709443`
- Fourier off `nrmse_sigma`: `0.24940025054427328`
- Fourier on `nrmse_sigma`: `0.24992714418015055`
- Both runs finite and frozen inputs unchanged.

Interpretation:

- The architecture is testable.
- The white-box closure can run through the train graph.
- Fourier features do not show a clear advantage in the current small-run stress setting.

Manuscript role:

- Appendix, discussion, or future work only.

Forbidden use:

- Do not claim F-SPS-PINN superiority.
- Do not claim Fourier features solve stiffness.
- Do not replace the `gamma_sub` mainline with F-SPS-PINN in the current manuscript.

## Innovation Assessment

The innovation is sufficient for a focused method paper if the scope is disciplined.

Strong innovation:

1. The project reframes a failed full-field inverse PINN task as an identifiability problem.
2. It demonstrates that sparse electrical port data are insufficient for unique hidden-field recovery in the benchmark.
3. It proposes target-space reduction to a physically meaningful effective thermal-loss parameter.
4. It audits confounders instead of overclaiming inverse success.
5. It adds off-grid continuous scalar refinement to avoid grid-hit criticism.

Weak or not-yet-proven innovation:

1. F-SPS-PINN is not yet a validated performance improvement.
2. The work does not yet include experimental validation.
3. The benchmark is reduced-order and one-dimensional.
4. The current inverse success depends on fixed or tightly bounded priors.

Overall innovation grade:

- For a synthetic benchmark / inverse-identifiability method paper: moderate to strong.
- For a top experimental device paper: insufficient.
- For a high-impact PINN algorithm paper: not yet sufficient without stronger baselines and broader validation.

## Workload Assessment

The engineering workload is substantial and probably sufficient:

- frozen synthetic GT benchmark;
- multiple PINN inverse versions;
- identifiability audit;
- `gamma_sub` scan and inversion;
- confounding and mismatch audits;
- constrained prior-width sweep;
- paper-readiness checks;
- continuous off-grid refinement;
- F-SPS-PINN method-development modules and smoke tests;
- evidence matrix and claim boundary documentation.

The manuscript workload is not yet complete:

- main figures must be generated and curated;
- a compact method narrative must be written;
- a baseline comparison should be added or clearly scoped;
- the limitation section must be explicit;
- the paper needs literature positioning and reviewer-facing wording.

## Practical Value

The practical value is not direct experimental device parameter extraction. The practical value is methodological:

- It warns against overclaiming hidden-field recovery from sparse terminal electrical data.
- It provides a workflow to test identifiability before choosing inverse targets.
- It shows how to reduce an underdetermined full-field inverse problem to a constrained effective-parameter inversion.
- It identifies `T_sw` as a critical prior that must be measured, calibrated, or tightly bounded in real applications.

The real-world implication is that a future experimental workflow should combine terminal electrical data with independent switching-temperature or thermal information before claiming thermal-loss parameter recovery.

## Reviewer Risk Assessment

### Risk 1: No experimental data

Severity: high.

Response:

- Position as synthetic numerical digital-twin benchmark.
- Do not claim device validation.
- Emphasize method and identifiability logic.

Residual gap:

- The paper may need a journal that accepts computational benchmark studies.

### Risk 2: One-dimensional reduced-order model

Severity: medium to high.

Response:

- Use model hierarchy and claim-boundary documents.
- State that the goal is inverse identifiability under controlled physics, not full device simulation.

Residual gap:

- Do not submit as a full device-physics paper.

### Risk 3: Strong prior dependence

Severity: high.

Response:

- This is not a weakness to hide; it is the main result.
- Show prior-width and `T_sw` confounding explicitly.

Residual gap:

- Need a clear statement: `gamma_sub` is recoverable only under fixed or tightly bounded priors.

### Risk 4: Why not recover full hidden fields?

Severity: medium.

Response:

- The identifiability audit directly answers this.
- The paper should say full hidden-field recovery is ill-posed from port-only observations.

Residual gap:

- Future work should add observability-augmented sparse temperature or state measurements.

### Risk 5: Compared with simpler methods, what is gained?

Severity: medium.

Response:

- The gain is not raw optimization superiority; it is an identifiability-guided inverse workflow.

Residual gap:

- Add or discuss a simple least-squares / grid-search / scalar optimizer baseline if the target journal expects algorithmic comparison.

## Readiness For High-Quality SCI

Current readiness:

- Code and evidence chain: strong.
- Main scientific story: viable if narrowed.
- Figures and manuscript: not yet ready.
- Claim discipline: good.
- Experimental validation: absent.
- High-quality SCI readiness: partial, not complete.

Recommended target framing:

> A method-oriented computational SCI paper on sparse-port inverse identifiability and constrained effective thermal-parameter inversion in a synthetic electro-thermal-defect digital-twin benchmark.

Not recommended:

- an experimental memristor device paper;
- a complete phase-change material physics paper;
- a paper claiming full hidden-field recovery;
- a paper centered on F-SPS-PINN superiority.

## Immediate Next Steps

1. Convert `docs/paper/sci_manuscript_evidence_matrix.md` into a manuscript outline.
2. Generate or curate the main figure set:
   - GT v1.1 benchmark and hysteresis;
   - identifiability/correlation matrix;
   - constrained `gamma_sub` objective and recovery;
   - confounding / prior-width sensitivity;
   - continuous off-grid refinement and observation/noise sensitivity.
3. Add one lightweight baseline comparison or explicitly justify why the paper is an identifiability study rather than an optimizer-comparison paper.
4. Write the limitations section before the abstract to prevent overclaiming.
5. Keep F-SPS-PINN as supplementary method-development evidence.
6. Do not run more F-SPS-PINN experiments unless a separate method paper is opened.

## Final Assessment

The project is scientifically useful and has a credible publication path, but it should not be described as already sufficient for a high-quality SCI paper. It is sufficient to begin manuscript drafting around a narrowed contribution. The paper can be strong if it is honest about being a synthetic numerical benchmark and if it treats prior dependence and full-field non-identifiability as central findings rather than weaknesses.