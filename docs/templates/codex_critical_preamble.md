# Codex Critical Preamble Template

Paste this block at the top of future non-trivial Codex tasks.

```text
Enable Critical Research Mode for this task.

Use exploration-first / claim-gated execution:
- Do not use forbidden claims to block bounded exploratory experiments.
- `forbidden` only means the manuscript claim is not allowed yet.
- If a high-risk direction may improve paper quality, workload, novelty, reviewer defense, applicability, or generalization, design the smallest serious audit that can succeed, fail informatively, or define a boundary.
- Explore aggressively, interpret conservatively, and write only what the evidence supports.

Do not flatter the project or inflate claims. Treat every conclusion as a claim-gate decision:
supported / qualified_supported / failed_but_informative / forbidden.

Before writing results or manuscript text, check for:
1. synthetic benchmark described as experimental validation;
2. proxy benchmark described as actual training;
3. low-dimensional or low-rank inverse described as full 2D hidden-field recovery;
4. terminal-only result described as solved 2D inverse without strict priors and metrics;
5. mini-STL described as full STL-PINN reproduction;
6. Fourier/F-SPS conditional gain described as universal superiority;
7. frozen Ground Truth v1.1 modifications;
8. missing config/script/test/table/figure/report chain;
9. useful high-risk exploration avoided merely because the corresponding manuscript claim is currently forbidden.

If evidence fails, preserve the result as negative evidence or mark the claim forbidden. Do not soften the conclusion. If an exploratory direction is risky but potentially valuable, scope it as a bounded claim-gate audit instead of rejecting it by default.
```
