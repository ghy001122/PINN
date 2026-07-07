# Next actions

## Standing critical research protocol

All future planning, Codex execution, result review, and manuscript integration must use the global Critical Research Mode defined in `AGENTS.md`, `docs/project_prompts/critical_research_mode.md`, and `docs/templates/codex_critical_preamble.md`.

This is a standing style and governance rule for the whole project. It is not limited to the latest claim-gate experiments.

The governing rule is exploration-first and claim-gated:

- Do not use `forbidden` to block bounded exploratory experiments.
- `forbidden` only means the current manuscript claim is not allowed yet.
- High-risk directions should be explored when they may improve paper quality, workload, novelty, reviewer defense, applicability, or generalization.
- Risky directions must be converted into bounded audits, stress ladders, rescue attempts, ablations, or negative-result tests.
- Final manuscript wording remains conservative and evidence-bound.

For each proposed task, record:

- claim target;
- evidence required;
- success threshold;
- failure interpretation;
- allowed wording;
- forbidden overclaim;
- required config/script/test/table/figure/report outputs;
- why the exploration is worth running now despite uncertainty.

Do not hide negative results. If a task fails, decide whether it is `failed_but_informative` or `forbidden` and update the claim matrix accordingly.

## Immediate next step

The immediate step is `manuscript assembly from locked calibration-gated gamma_sub evidence` unless an explicitly authorized research task targets a claim-gate gap or high-risk exploration opportunity.

The latest pack quantifies T_sw calibration tolerance, separates calibration gain from protocol gain, stress-tests calibrated protocol robustness with ODE-backed cases, confirms external curve fitting remains blocked without provenance-backed digitized curves, and locks final figure/table/claim routing.

The manuscript should be drafted around a narrow claim: calibration-gated sparse-port reduced inversion of `gamma_sub` under fixed or tightly bounded priors. New experiments are allowed when they are explicitly framed as claim-gate exploration with success/failure thresholds and no overclaim.

## Main manuscript line

1. Present Ground Truth v1.1 as a synthetic one-dimensional reduced-order benchmark.
2. Show that sparse electrical port observations do not uniquely recover full hidden fields.
3. Use identifiability analysis to justify target-space reduction.
4. Present constrained `gamma_sub` inversion under fixed or tightly bounded priors.
5. Use confounding, prior-width, off-grid, observation-count, continuous-refinement, T_sw phase-map, auxiliary-observability, response-surface anchor verification, sequential protocol preflight, and statistical robustness audits as reviewer-defense evidence.

## Appendix or supplementary line

- PINN inverse v0/v1/v1.1 negative and diagnostic results.
- F-SPS-PINN architecture MVP.
- v2 smoke training.
- v2 small-run free-log-sigma versus white-box `vo2_sigma` baseline.
- v2 phase-transition stress preflight.
- v2 Fourier on/off ablation.
- Balanced F-SPS medium-budget benchmark.
- Reduced 2D forward and observability claim-gate evidence.
- Stiffness-aware algorithm and mini-STL-style benchmark evidence.

These results are useful engineering and reviewer-defense evidence. They must not be upgraded into F-SPS superiority, full 2D recovery, terminal-only solved 2D inverse, full STL-PINN reproduction, or experimental validation unless direct evidence exists. The underlying directions may still be explored further through bounded claim-gate audits.

## Recommended tasks

1. Draft the manuscript around `docs/paper/manuscript_outline_v1.md` while enforcing claim gates.
2. Use `docs/paper/claim_stress_test_matrix.md` and `docs/paper/claim_gate_resolution_matrix.md` as overclaim guardrails.
3. Build final figures from `docs/paper/proposed_main_figures.md` and tables from `docs/paper/proposed_tables.md`.
4. Keep the wording explicit: synthetic numerical digital-twin benchmark, not experimental data.
5. Treat `T_sw` as the main limitation and required prior/calibration boundary.
6. Use sequential protocol design as a hypothesis/preflight result, not a validated experimental design.
7. For any new high-risk research branch, start from `docs/templates/codex_critical_preamble.md` and define the claim-gate thresholds before implementation.
8. Do not reject full-field recovery, terminal-only rescue, Seiler-style multi-head STL, or Fourier/F-SPS conditional superiority by default; convert them into bounded audits if they may raise paper quality or clarify reviewer-facing boundaries.

## Do not claim next without direct evidence

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics, manifest, equations, or default parameters unless an explicit Ground Truth revision task is opened.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field recovery.
- Do not claim F-SPS-PINN, Fourier features, stress preflight, or phase-transition closure solved the inverse problem.
- Do not claim every dense response-surface grid point is simulator-backed unless a future task re-solves those cases.
- Do not claim full STL-PINN reproduction unless the repository contains a true multi-head low-stiff pretraining and high-stiff transfer benchmark.
- Do not claim terminal-only 2D inverse solved unless the target, priors, protocol, and error thresholds are directly supported.

These are claim restrictions, not exploration bans. If the project can benefit from testing any of these directions, open a controlled claim-gate audit with explicit stop conditions and failure interpretation.

## Deferred method enhancements

Record these as future options or explicitly authorized claim-gate experiments, not automatic manuscript-critical work:

- implement gamma_sub-PINN;
- add stiff transfer learning continuation;
- add observability-augmented full-field recovery or experimental sparse `T/m` extension;
- extend F-SPS-PINN as a separate method paper after stronger ablation evidence;
- explore high-risk claim ladders for full-field recovery, terminal-only rescue, Seiler-style multi-head STL, and Fourier/F-SPS conditional superiority.

Deferred does not mean forbidden. It means the task needs a scoped rationale, success/failure thresholds, and a clear route into the claim matrix before execution.

## Immediate next after ODE spot-check manuscript lock

The immediate next step is manuscript assembly and figure/table drafting from the locked evidence package. A new method branch is acceptable only if it targets a reviewer-specific gap or is explicitly framed as bounded high-risk claim exploration.

Keep the main claim narrow: calibration-gated sparse-port reduced inversion of `gamma_sub` under fixed or tightly bounded `T_sw` priors in a one-dimensional synthetic numerical digital-twin benchmark. Quasi-2D remains supplementary extension feasibility unless a later claim-gated experiment supports stronger 2D inverse diagnosis.

## Immediate Next After Stiffness And Phase-Field Alignment

The immediate next step is manuscript assembly unless a new task explicitly targets a claim-gate gap or high-value exploration opportunity. Use the stiffness-continuation and phase-field smoke outputs as supplementary reviewer-defense evidence. Keep the main result on calibration-gated constrained `gamma_sub` inversion.

Recommended follow-up:

1. Assemble the paper figures and tables from the locked evidence chain.
2. Put stiffness-continuation and phase-field alignment in supplementary/discussion sections.
3. Scope full STL, F-Pyramid expansion, NeuroSPICE/NeuroPINN, or full 2D inverse training as claim-gate audits if they are pursued; do not write their positive claims before evidence exists.

## Immediate Next After Final Figure Literature Lock

The immediate next step is final manuscript assembly and human editing. Use the generated stiffness/phase-field/quasi-2D figures as supplementary evidence only. New training branches are acceptable when they address a specific reviewer-defense gap or are explicitly approved as bounded high-risk claim exploration.

## Immediate Next After Claim-Gate Experimental Resolution

Do not open another broad experiment branch before manuscript assembly unless it is explicitly scoped as claim-gate exploration. The next practical step is to integrate `docs/paper/claim_gate_resolution_matrix.md` into the manuscript and supplementary material, while preserving the option to run bounded high-risk audits when they can improve paper quality.

Use the new evidence as follows:

1. Main claim remains calibration-gated constrained `gamma_sub` inversion.
2. Supplementary claim: reduced 2D forward benchmark is finite and geometry-sensitive.
3. Qualified supplementary claim: low-dimensional 2D inverse diagnosis is feasible under augmented sparse observations.
4. Honest negative: terminal-only 2D inverse diagnosis fails.
5. Stiffness claim: continuation plus scale-aware weighting and mini-STL-style transfer mitigate residual-proxy degradation; do not claim full STL-PINN reproduction.

Still do not claim experimental validation, full hidden-field recovery, full FEM/device simulation, F-SPS superiority, or full STL unless direct repository evidence upgrades those claim gates. Those topics may still be investigated through bounded, reproducible exploration-first audits.

## Immediate Next After Integrated High-Risk Claim Ladder

Use the integrated quick-profile results as supplementary claim-gate evidence, not as the main paper claim.

Recommended next actions:

1. Keep the main manuscript centered on calibration-gated constrained `gamma_sub` inversion.
2. Route the 2D low-rank dense-anchor result, terminal-only failure, actual reduced stiffness training, Seiler-style transfer, and Fourier/F-SPS conditional benefit to supplementary or discussion sections.
3. If expanding this branch, run the extended high-risk ladder profile before making stronger 2D or Fourier claims.
4. Do not claim sparse terminal full hidden-field recovery, full STL-PINN reproduction, universal Fourier/F-SPS superiority, or experimental validation.
