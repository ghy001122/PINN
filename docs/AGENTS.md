# Documentation Subtree Rules

These rules extend the root `AGENTS.md` for `docs/`.

- Classify evidence explicitly as synthetic, external literature, or experimental. Do not blend categories.
- Prefer primary literature for equations, device structures, and parameter provenance. Record uncertainty and whether a value is measured, digitized, fitted, or an engineering prior.
- Use only `supported`, `qualified_supported`, `failed_but_informative`, and `forbidden` for claim gates.
- Task reports must record base SHA, actual final SHA when technically possible, validation, frozen-GT status, evidence type, and forbidden claims. Never use vague placeholders as proof.
- Response surfaces, anchor verification, local Jacobians, mini-STL, Fourier ablations, smoke tests, and proxy audits must retain their exact evidence boundary.
- Use LaTeX for mathematical expressions and define symbols, units, boundary conditions, and residuals.
- Archived status documents are historical evidence, not current authorization.
