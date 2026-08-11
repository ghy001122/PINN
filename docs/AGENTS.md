# Documentation Subtree Rules

These rules extend the root `AGENTS.md` for `docs/`.

- Classify evidence explicitly as synthetic, external literature, or experimental. Do not blend categories.
- Prefer primary literature for equations, device structures, and parameter provenance. Record uncertainty and whether a value is measured, digitized, fitted, or an engineering prior.
- Internal reviews and project reports are leads, not fact sources. Verify equations, device parameters, trends, and novelty gaps against the original paper and supplement. Prefer original papers, supplements, public data/code, then reviews and search summaries; record page, figure/table, or equation locations for key parameters.
- ChatGPT-only `cite`, `filecite`, content-reference, or similar session-internal markers are not portable citations. Before repository or manuscript use, replace them with verified DOI/Bibliography references or exact repository evidence paths, and remove any numerical or novelty statement that cannot be traced. Recheck time-sensitive journal scope/ranking and repository or license metadata at the point of use.
- Recent-work novelty searches should prioritize 2023 onward, but foundational equations, classic PINN/numerical methods, and constitutive laws must cite the original or authoritative source rather than obeying an all-post-2023 cutoff.
- For every borrowed module, record the source method/problem, direct-transfer or adapted role, exact modification when applicable, physical or interface rationale, license, intended capability or supporting role, minimum discriminative evidence, allowed claim, and forbidden claim. A combination contribution may arise from adaptation, interface, workflow, functional composition, validation, or composability; it does not require modifying every module or winning every metric.
- Use only `supported`, `qualified_supported`, `failed_but_informative`, and `forbidden` for claim gates.
- Task reports must record base SHA, actual final SHA when technically possible, validation, frozen-GT status, evidence type, and forbidden claims. Never use vague placeholders as proof.
- Execution reports are conclusion-first and also record the task contract, assumptions, actual implementation, exact validation commands, core results, anomalies/root causes, claim changes, artifact paths, branch/commit/push/PR status, next highest-value problem, and remedy. State both what can and cannot be claimed, including scope and evidence gaps.
- Separate verified facts and direct evidence from interpretations, assumptions or hypotheses, and unresolved unknowns. If an inference is useful, name its supporting evidence and do not phrase it as an observed result.
- Use the smallest useful visual only when it materially clarifies a multi-item mapping, dependency, branch, sequence, state change, or layout. Prefer a compact table or flow diagram to repetitive prose, and omit decorative or redundant figures.
- Future plans, expectations, and suggestions cannot appear in an abstract or conclusion as completed contributions. Avoid “first”, “unique recovery”, “complete solution”, “absolute convergence”, or “replacement of FEM/FVM” without a systematic novelty search and direct evidence. Define technical terms; do not use new acronyms to disguise tuning or failure.
- Each main figure serves one claim; do not multiply redundant curves to imply workload.
- Claim-bearing figures and tables must be generated from and cite existing machine-readable JSON/CSV or source data. Do not recover project results by transcribing generated images, and do not rerun frozen experiments merely to fill or restyle a figure; provenance-governed digitization of external literature remains a separate `data/external/` workflow.
- Response surfaces, anchor verification, local Jacobians, mini-STL, Fourier ablations, smoke tests, and proxy audits must retain their exact evidence boundary.
- Use LaTeX for mathematical expressions and define symbols, units, boundary conditions, and residuals.
- Archived status documents are historical evidence, not current authorization.
