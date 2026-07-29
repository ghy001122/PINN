# Documentation Subtree Rules

These rules extend the root `AGENTS.md` for `docs/`.

- Classify evidence explicitly as synthetic, external literature, or experimental. Do not blend categories.
- Prefer primary literature for equations, device structures, and parameter provenance. Record uncertainty and whether a value is measured, digitized, fitted, or an engineering prior.
- Internal reviews and project reports are leads, not fact sources. Verify equations, device parameters, trends, and novelty gaps against the original paper and supplement. Prefer original papers, supplements, public data/code, then reviews and search summaries; record page, figure/table, or equation locations for key parameters.
- Recent-work novelty searches should prioritize 2023 onward, but foundational equations, classic PINN/numerical methods, and constitutive laws must cite the original or authoritative source rather than obeying an all-post-2023 cutoff.
- For every borrowed module, record the source method/problem, project modification, physical necessity, license, new capability, one-factor ablation, allowed claim, and forbidden claim. Module recombination is not originality without a problem-driven change, otherwise unavailable capability, synergistic ablation, and new scientific insight.
- Use only `supported`, `qualified_supported`, `failed_but_informative`, and `forbidden` for claim gates.
- Task reports must record base SHA, actual final SHA when technically possible, validation, frozen-GT status, evidence type, and forbidden claims. Never use vague placeholders as proof.
- Execution reports are conclusion-first and also record the task contract, assumptions, actual implementation, exact validation commands, core results, anomalies/root causes, claim changes, artifact paths, branch/commit/push/PR status, next highest-value problem, and remedy. State both what can and cannot be claimed, including scope and evidence gaps.
- Future plans, expectations, and suggestions cannot appear in an abstract or conclusion as completed contributions. Avoid “first”, “unique recovery”, “complete solution”, “absolute convergence”, or “replacement of FEM/FVM” without a systematic novelty search and direct evidence. Define technical terms; do not use new acronyms to disguise tuning or failure.
- Each main figure serves one claim; do not multiply redundant curves to imply workload.
- Response surfaces, anchor verification, local Jacobians, mini-STL, Fourier ablations, smoke tests, and proxy audits must retain their exact evidence boundary.
- Use LaTeX for mathematical expressions and define symbols, units, boundary conditions, and residuals.
- Archived status documents are historical evidence, not current authorization.
